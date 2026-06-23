"""
Matched 5-Fold Cross-Validation — ALL MODELS, ONE RUN (apples-to-apples)
=======================================================================
Trains WaveCoAtNet AND the baselines through the EXACT SAME 5 stratified
folds, in the same script, same session, same seed, same augmentation,
same epochs, same optimizer scheme, same val-checkpoint selection, same
test evaluation. This is the only fully fair comparison.

Models (Option B — top rivals + proposed):
    wavecoatnet, convnext_tiny, swin_tiny, dinov2

RESUMABLE: every (model, fold) saves its test predictions to OUT_DIR
immediately. On restart, finished (model, fold) pairs are skipped, so a
Colab disconnect costs at most the in-progress fold.

USAGE (single Colab run, end to end):
    python evaluation/crossval_all.py
        -> trains all models on all folds, then prints the comparison table.

Useful flags:
    --models wavecoatnet swin_tiny      # subset
    --epochs 15                         # ~halve compute (logs plateau ~ep 10)
    --summarize                         # just rebuild the table from saved preds

Outputs in OUT_DIR:
    {model}_fold_{k}_y_true.npy / _y_pred.npy
    matched_cv_summary.csv
    matched_cv_summary.txt
"""

import os
import csv
import argparse
import random

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torch.amp import autocast, GradScaler
from torchvision import datasets, transforms
from PIL import Image

from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, classification_report
from tqdm import tqdm
from timm import create_model
from timm.models.vision_transformer import Block

# ── Config (shared by ALL models — that is the point) ────────────────────────
RANDOM_SEED  = 42
TARGET_SIZE  = (224, 224)
BATCH_SIZE   = 24
EPOCHS       = 30
LR_BACKBONE  = 1e-5
LR_HEAD      = 1e-4
WEIGHT_DECAY = 0.01
DROPOUT      = 0.2
N_FOLDS      = 5
GRAD_CLIP    = 1.0
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# WaveCoAtNet-specific
SCTR_WEIGHT  = 0.1
ORTHO_WEIGHT = 0.05
PROTO_MOM    = 0.99
PROTO_WARMUP = 5
VIT_BLOCKS   = 4

# Save to Drive so disconnects don't lose finished folds.
OUT_DIR = os.environ.get("CV_OUT_DIR",
                         "/content/drive/MyDrive/WaveCoAtNet_experiments/cv_matched")

# Baseline zoo. partial_freeze=None trains all; =N keeps last N blocks + head trainable.
BASELINES = {
    "convnext_tiny": dict(timm_name="convnext_tiny", partial_freeze=None),
    "swin_tiny":     dict(timm_name="swin_tiny_patch4_window7_224", partial_freeze=None),
    "dinov2":        dict(timm_name="vit_base_patch14_dinov2.lvd142m", partial_freeze=2),
}
ALL_MODELS = ["wavecoatnet"] + list(BASELINES.keys())


def set_seed(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True


# ── Data ─────────────────────────────────────────────────────────────────────
class PathDataset(Dataset):
    def __init__(self, paths, labels, transform=None):
        self.paths, self.labels, self.transform = paths, labels, transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert('RGB')
        if self.transform:
            img = self.transform(img)
        return img, self.labels[idx]


def collect_all_samples(dataset_dir):
    base = datasets.ImageFolder(os.path.join(dataset_dir, "train"))
    class_names = base.classes
    all_paths, all_labels = [], []
    for split in ["train", "valid", "test"]:
        d = os.path.join(dataset_dir, split)
        if not os.path.exists(d):
            continue
        ds = datasets.ImageFolder(d)
        assert ds.classes == class_names, f"Class mismatch in {split}"
        for path, label in ds.samples:
            all_paths.append(path); all_labels.append(label)
    return all_paths, all_labels, class_names


def get_folds(all_paths, all_labels):
    """Identical fold construction for every model => paired test sets."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    folds = []
    for fold, (train_val_idx, test_idx) in enumerate(
            skf.split(np.arange(len(all_paths)), all_labels)):
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=RANDOM_SEED + fold)
        tr_local, val_local = next(sss.split(train_val_idx, all_labels[train_val_idx]))
        folds.append((train_val_idx[tr_local], train_val_idx[val_local], test_idx))
    return folds


# ── WaveCoAtNet (matches proposed/train_wavecoatnet.py) ──────────────────────
def haar_dwt_2d(x):
    x_l = (x[:, :, :, 0::2] + x[:, :, :, 1::2]) * 0.5
    x_h = (x[:, :, :, 0::2] - x[:, :, :, 1::2]) * 0.5
    ll = (x_l[:, :, 0::2, :] + x_l[:, :, 1::2, :]) * 0.5
    lh = (x_l[:, :, 0::2, :] - x_l[:, :, 1::2, :]) * 0.5
    hl = (x_h[:, :, 0::2, :] + x_h[:, :, 1::2, :]) * 0.5
    hh = (x_h[:, :, 0::2, :] - x_h[:, :, 1::2, :]) * 0.5
    return ll, lh, hl, hh


class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        mid = max(1, channels // reduction)
        self.fc = nn.Sequential(nn.Linear(channels, mid, bias=False), nn.ReLU(inplace=True),
                                nn.Linear(mid, channels, bias=False))

    def forward(self, x):
        B, C = x.shape[:2]
        a = self.fc(self.avg_pool(x).view(B, C))
        m = self.fc(self.max_pool(x).view(B, C))
        return x * torch.sigmoid(a + m).view(B, C, 1, 1)


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False)
        self.bn = nn.BatchNorm2d(1)

    def forward(self, x):
        a = x.mean(dim=1, keepdim=True)
        m = x.max(dim=1, keepdim=True).values
        attn = torch.sigmoid(self.bn(self.conv(torch.cat([a, m], dim=1))))
        return x * attn


class CBAM(nn.Module):
    def __init__(self, channels, reduction=16, kernel_size=7):
        super().__init__()
        self.channel_attn = ChannelAttention(channels, reduction)
        self.spatial_attn = SpatialAttention(kernel_size)

    def forward(self, x):
        return self.spatial_attn(self.channel_attn(x))


class WaveletFrequencyDecomposedCrossAttention(nn.Module):
    def __init__(self, dim_low=96, dim_high=192, num_heads=4, dropout=0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim_high // num_heads
        self.scale = self.head_dim ** -0.5
        self.proj_low_freq = nn.Sequential(
            nn.Conv2d(dim_low, dim_high, 1, bias=False), nn.BatchNorm2d(dim_high), nn.GELU())
        self.proj_high_freq = nn.Sequential(
            nn.Conv2d(dim_low * 3, dim_high, 1, bias=False), nn.BatchNorm2d(dim_high), nn.GELU())
        self.q_proj = nn.Linear(dim_high, dim_high, bias=False)
        self.norm_q = nn.LayerNorm(dim_high)
        self.k_proj_low = nn.Linear(dim_high, dim_high, bias=False)
        self.v_proj_low = nn.Linear(dim_high, dim_high, bias=False)
        self.out_proj_low = nn.Linear(dim_high, dim_high)
        self.norm_kv_low = nn.LayerNorm(dim_high)
        self.k_proj_high = nn.Linear(dim_high, dim_high, bias=False)
        self.v_proj_high = nn.Linear(dim_high, dim_high, bias=False)
        self.out_proj_high = nn.Linear(dim_high, dim_high)
        self.norm_kv_high = nn.LayerNorm(dim_high)
        self.attn_drop = nn.Dropout(dropout * 0.5)
        self.proj_drop = nn.Dropout(dropout)
        self.freq_gate = nn.Sequential(
            nn.Linear(dim_high * 2, dim_high // 4), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(dim_high // 4, 1), nn.Sigmoid())
        self.ffn = nn.Sequential(
            nn.Linear(dim_high, dim_high * 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(dim_high * 2, dim_high), nn.Dropout(dropout))
        self.norm_ffn = nn.LayerNorm(dim_high)

    def _cross_attend(self, q_tokens, kv_tokens, k_proj, v_proj, out_proj, norm_kv):
        B = q_tokens.shape[0]
        kv = norm_kv(kv_tokens)
        Q = self.q_proj(self.norm_q(q_tokens)).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = k_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = v_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        attn = self.attn_drop((Q @ K.transpose(-2, -1) * self.scale).softmax(dim=-1))
        out = (attn @ V).transpose(1, 2).reshape(B, -1, self.num_heads * self.head_dim)
        return self.proj_drop(out_proj(out))

    def forward(self, feat_low, feat_high):
        ll, lh, hl, hh = haar_dwt_2d(feat_low)
        low_tokens = self.proj_low_freq(ll).flatten(2).transpose(1, 2)
        high_tokens = self.proj_high_freq(torch.cat([lh, hl, hh], dim=1)).flatten(2).transpose(1, 2)
        q_tokens = feat_high.flatten(2).transpose(1, 2)
        low_out = self._cross_attend(q_tokens, low_tokens, self.k_proj_low, self.v_proj_low, self.out_proj_low, self.norm_kv_low)
        high_out = self._cross_attend(q_tokens, high_tokens, self.k_proj_high, self.v_proj_high, self.out_proj_high, self.norm_kv_high)
        gate = self.freq_gate(torch.cat([low_out, high_out], dim=-1))
        fused = q_tokens + gate * high_out + (1 - gate) * low_out
        return fused + self.ffn(self.norm_ffn(fused))


class PrototypeAnchoredTokenSelection(nn.Module):
    def __init__(self, dim, num_classes=5, min_keep=0.6, max_keep=0.95, dropout=0.0):
        super().__init__()
        self.dim = dim; self.num_classes = num_classes
        self.min_keep = min_keep; self.max_keep = max_keep
        self.register_buffer('prototypes', torch.randn(num_classes, dim) * 0.02)
        self.proto_temperature = nn.Parameter(torch.tensor(1.0))
        mid = max(1, dim // 16)
        self.channel_scorer = nn.Sequential(nn.Linear(dim, mid), nn.GELU(), nn.Dropout(dropout), nn.Linear(mid, 1))
        self.importance_weights = nn.Parameter(torch.tensor([1.0, 0.5, 0.5]))
        self.keep_predictor = nn.Sequential(nn.Linear(dim + 3, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
        self.norm = nn.LayerNorm(dim)

    def forward(self, x):
        B, N, C = x.shape
        x_normed = self.norm(x)
        p_norm = F.normalize(self.prototypes, dim=-1)
        t_norm = F.normalize(x_normed, dim=-1)
        sim = t_norm @ p_norm.T
        proto_aff = sim.max(dim=-1).values
        proto_probs = F.softmax(sim / self.proto_temperature.clamp(min=0.01), dim=-1)
        proto_ent = -(proto_probs * (proto_probs + 1e-8).log()).sum(dim=-1)
        ch_score = self.channel_scorer(x_normed).squeeze(-1)

        def _zn(s):
            s = s - s.mean(dim=-1, keepdim=True)
            return s / (s.std(dim=-1, keepdim=True) + 1e-6)

        w = F.softmax(self.importance_weights, dim=0)
        importance = F.softmax(w[0]*_zn(proto_aff) + w[1]*_zn(proto_ent) + w[2]*_zn(ch_score), dim=-1)
        g = self.keep_predictor(torch.cat([x.mean(dim=1), torch.stack([importance.mean(1), importance.std(1), importance.max(1).values], -1)], -1)).squeeze(-1)
        g = self.min_keep + g * (self.max_keep - self.min_keep)
        k = torch.clamp((g.mean()*N).long(), min=max(1, int(self.min_keep*N)), max=int(self.max_keep*N)).item()
        _, idx = torch.topk(importance, k, dim=1)
        bi = torch.arange(B, device=x.device).unsqueeze(1).expand(-1, k)
        sel = x[bi, idx] * (1 + importance[bi, idx].unsqueeze(-1))
        return sel, importance

    @torch.no_grad()
    def update_prototypes(self, embeddings, labels, momentum=0.99):
        for c in range(self.num_classes):
            m = labels == c
            if m.sum() > 0:
                self.prototypes[c] = momentum*self.prototypes[c] + (1-momentum)*embeddings[m].mean(0)

    def prototype_orthogonality_loss(self):
        p_norm = F.normalize(self.prototypes, dim=-1)
        sim = p_norm @ p_norm.T
        eye = torch.eye(self.num_classes, device=sim.device)
        return ((sim - eye) ** 2).mean()


class SupervisedContrastiveTokenLoss(nn.Module):
    def __init__(self, embed_dim, proj_dim=128, temperature=0.07):
        super().__init__()
        self.temperature = temperature
        self.projector = nn.Sequential(nn.Linear(embed_dim, embed_dim), nn.GELU(), nn.Linear(embed_dim, proj_dim))

    def forward(self, embeddings, labels, prototypes=None):
        B = embeddings.shape[0]
        if B < 2:
            return torch.tensor(0.0, device=embeddings.device, requires_grad=True)
        z = F.normalize(self.projector(embeddings), dim=-1)
        sim = z @ z.T / self.temperature
        label_eq = labels.unsqueeze(0) == labels.unsqueeze(1)
        self_mask = ~torch.eye(B, dtype=torch.bool, device=z.device)
        positives = label_eq & self_mask
        has_pos = positives.float().sum(1) > 0
        if has_pos.sum() == 0:
            supcon = torch.tensor(0.0, device=embeddings.device, requires_grad=True)
        else:
            sim = sim - sim.max(1, keepdim=True).values.detach()
            exp_sim = torch.exp(sim) * self_mask.float()
            log_prob = sim - torch.log(exp_sim.sum(1, keepdim=True) + 1e-8)
            pos_count = torch.clamp(positives.float().sum(1), min=1.0)
            loss_per = -(positives.float() * log_prob).sum(1) / pos_count
            supcon = loss_per[has_pos].mean()
        if prototypes is not None:
            p_norm = F.normalize(prototypes.detach(), dim=-1)
            e_norm = F.normalize(embeddings, dim=-1)
            proto_sim = e_norm @ p_norm.T / self.temperature
            return supcon + 0.5 * F.cross_entropy(proto_sim, labels)
        return supcon


class WaveCoAtNet(nn.Module):
    def __init__(self, num_classes=5, vit_blocks=4, dropout=0.2):
        super().__init__()
        cnn = create_model('convnext_tiny', pretrained=True, num_classes=0)
        self.cnn_stem   = cnn.stem
        self.cnn_stage1 = cnn.stages[0]
        self.cnn_stage2 = cnn.stages[1]
        self.cnn_stage3 = cnn.stages[2]
        self.cnn_stage4 = cnn.stages[3]
        self.cbam3 = CBAM(384); self.cbam4 = CBAM(768)
        vit_dim, final_dim = 192, 768
        self.wg_fdca = WaveletFrequencyDecomposedCrossAttention(96, 192, 4, dropout)
        self.pos_embed = nn.Parameter(torch.zeros(1, 28*28, vit_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        self.vit_blocks = nn.ModuleList([
            Block(dim=vit_dim, num_heads=6, proj_drop=dropout, attn_drop=dropout*0.5,
                  drop_path=0.1 * (i + 1) / vit_blocks) for i in range(vit_blocks)])
        self.vit_to_cnn_proj = nn.Sequential(
            nn.LayerNorm(vit_dim), nn.Linear(vit_dim, final_dim), nn.GELU(), nn.Dropout(dropout))
        self.pa_dts = PrototypeAnchoredTokenSelection(final_dim, num_classes, 0.6, 0.95, dropout*0.25)
        self.sctr = SupervisedContrastiveTokenLoss(final_dim, 128, 0.07)
        self.pgap_norm = nn.LayerNorm(final_dim)
        self.dpa_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim // 4), nn.GELU(),
            nn.Linear(final_dim // 4, final_dim), nn.Sigmoid())
        self.classifier = nn.Sequential(nn.LayerNorm(final_dim), nn.Dropout(dropout), nn.Linear(final_dim, num_classes))

    def forward(self, x, return_embeddings=False):
        x = self.cnn_stem(x)
        s1 = self.cnn_stage1(x); s2 = self.cnn_stage2(s1)
        vit_tokens = self.wg_fdca(s1, s2) + self.pos_embed
        for blk in self.vit_blocks:
            vit_tokens = blk(vit_tokens)
        B = s2.shape[0]
        x = self.cbam3(self.cnn_stage3(s2))
        x = self.cbam4(self.cnn_stage4(x))
        cnn_tokens = x.flatten(2).transpose(1, 2)
        vit_proj = self.vit_to_cnn_proj(vit_tokens).transpose(1, 2).reshape(B, 768, 28, 28)
        vit_proj = F.adaptive_avg_pool2d(vit_proj, (7, 7)).flatten(2).transpose(1, 2)
        tokens = cnn_tokens + vit_proj
        selected, _ = self.pa_dts(tokens)
        pgap_tokens = self.pgap_norm(selected)
        proto_normed = F.normalize(self.pa_dts.prototypes.detach(), dim=-1)
        query_normed = F.normalize(pgap_tokens, dim=-1)
        diag_relevance = (query_normed @ proto_normed.T).max(dim=-1).values
        attn_weights = F.softmax(diag_relevance, dim=-1).unsqueeze(-1)
        pgap_embed = (selected * attn_weights).sum(dim=1)
        gap_embed = tokens.mean(dim=1)
        dpa_g = self.dpa_gate(torch.cat([pgap_embed, gap_embed], dim=-1))
        embeddings = dpa_g * pgap_embed + (1 - dpa_g) * gap_embed
        logits = self.classifier(embeddings)
        if return_embeddings:
            return logits, embeddings
        return logits


# ── Baseline build / optimizer ───────────────────────────────────────────────
def build_baseline(key, num_classes):
    cfg = BASELINES[key]
    model = create_model(cfg["timm_name"], pretrained=True, num_classes=num_classes)
    if cfg["partial_freeze"] is not None:
        for p in model.parameters():
            p.requires_grad = False
        for p in model.get_classifier().parameters():
            p.requires_grad = True
        blocks = getattr(model, "blocks", None)
        if blocks is not None:
            for blk in blocks[-cfg["partial_freeze"]:]:
                for p in blk.parameters():
                    p.requires_grad = True
    return model


def make_optimizer(model, is_wave):
    backbone, novel = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if is_wave:
            is_bb = any(s in name for s in ['cnn_stem', 'cnn_stage1', 'cnn_stage2', 'cnn_stage3', 'cnn_stage4'])
        else:
            is_bb = not any(s in name for s in ['head', 'classifier', 'fc'])
        (backbone if is_bb else novel).append(p)
    groups = []
    if backbone:
        groups.append({'params': backbone, 'lr': LR_BACKBONE})
    if novel:
        groups.append({'params': novel, 'lr': LR_HEAD})
    return torch.optim.AdamW(groups, weight_decay=WEIGHT_DECAY)


# ── Train / eval ─────────────────────────────────────────────────────────────
def train_epoch(model, loader, criterion, optimizer, scaler, is_wave, epoch):
    model.train()
    use_amp = scaler is not None
    proto_mom = 0.9 if (is_wave and epoch < PROTO_WARMUP) else PROTO_MOM
    correct, total = 0, 0
    for imgs, tgts in tqdm(loader, desc="  train", leave=False):
        imgs, tgts = imgs.to(DEVICE, non_blocking=True), tgts.to(DEVICE, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with autocast('cuda', enabled=use_amp):
            if is_wave:
                logits, emb = model(imgs, return_embeddings=True)
                ce = criterion(logits, tgts)
                sctr = model.sctr(emb.float(), tgts, model.pa_dts.prototypes)
                ortho = model.pa_dts.prototype_orthogonality_loss()
                loss = ce + SCTR_WEIGHT * sctr + ORTHO_WEIGHT * ortho
            else:
                logits = model(imgs)
                loss = criterion(logits, tgts)
        if use_amp:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            if is_wave:
                model.pa_dts.update_prototypes(emb.detach().float(), tgts, proto_mom)
            scaler.step(optimizer); scaler.update()
        else:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            if is_wave:
                model.pa_dts.update_prototypes(emb.detach(), tgts, proto_mom)
            optimizer.step()
        with torch.no_grad():
            correct += (logits.argmax(1) == tgts).sum().item()
            total += tgts.size(0)
    return correct / max(total, 1)


@torch.no_grad()
def eval_loader(model, loader):
    model.eval()
    preds, targets = [], []
    use_amp = DEVICE.type == 'cuda'
    for imgs, tgts in tqdm(loader, desc="  eval ", leave=False):
        imgs = imgs.to(DEVICE, non_blocking=True)
        with autocast('cuda', enabled=use_amp):
            out = model(imgs)
        preds.extend(out.argmax(1).cpu().numpy())
        targets.extend(tgts.numpy())
    return np.array(targets), np.array(preds)


def run_model(key, folds, all_paths, all_labels, class_names, train_aug, val_tf):
    is_wave = key == "wavecoatnet"
    num_classes = len(class_names)
    scaler = GradScaler('cuda') if DEVICE.type == 'cuda' else None
    os.makedirs(OUT_DIR, exist_ok=True)

    for fold, (train_idx, val_idx, test_idx) in enumerate(folds):
        pred_file = os.path.join(OUT_DIR, f"{key}_fold_{fold+1}_y_pred.npy")
        if os.path.exists(pred_file):
            print(f"[{key}] fold {fold+1}: done — skip.")
            continue

        print(f"\n{'='*60}\n  [{key}] FOLD {fold+1}/{N_FOLDS}\n{'='*60}")
        set_seed(RANDOM_SEED + fold)

        def subset(idx, tf):
            return PathDataset([all_paths[i] for i in idx],
                               [int(all_labels[i]) for i in idx], tf)

        tr_ds, val_ds, te_ds = subset(train_idx, train_aug), subset(val_idx, val_tf), subset(test_idx, val_tf)
        print(f"  Train {len(tr_ds)} | Val {len(val_ds)} | Test {len(te_ds)}")

        g = torch.Generator(); g.manual_seed(RANDOM_SEED + fold)
        nw = 0 if os.name == 'nt' else 2
        pin = torch.cuda.is_available()
        tr_loader  = DataLoader(tr_ds, BATCH_SIZE, shuffle=True, num_workers=nw, pin_memory=pin, generator=g)
        val_loader = DataLoader(val_ds, BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin)
        te_loader  = DataLoader(te_ds, BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin)

        counts = np.bincount([int(all_labels[i]) for i in train_idx], minlength=num_classes)
        cw = torch.tensor([len(train_idx) / (c * num_classes + 1e-6) for c in counts],
                          dtype=torch.float).to(DEVICE)
        criterion = nn.CrossEntropyLoss(weight=cw, label_smoothing=0.1)

        model = (WaveCoAtNet(num_classes, VIT_BLOCKS, DROPOUT) if is_wave
                 else build_baseline(key, num_classes)).to(DEVICE)
        optimizer = make_optimizer(model, is_wave)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        best_val, best_state = 0.0, None
        history = {"train_acc": [], "val_acc": []}
        for epoch in range(EPOCHS):
            tr_acc = train_epoch(model, tr_loader, criterion, optimizer, scaler, is_wave, epoch)
            scheduler.step()
            val_yt, val_yp = eval_loader(model, val_loader)
            val_acc = accuracy_score(val_yt, val_yp)
            # train acc comes free from the training pass (running estimate) — no extra eval.
            history["train_acc"].append(float(tr_acc))
            history["val_acc"].append(float(val_acc))
            if epoch % 5 == 0 or epoch == EPOCHS - 1:
                print(f"  Epoch {epoch+1:2d}/{EPOCHS} | Val Acc: {val_acc:.4f}")
            if val_acc > best_val:
                best_val = val_acc
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        model.load_state_dict({k: v.to(DEVICE) for k, v in best_state.items()})
        y_true, y_pred = eval_loader(model, te_loader)
        acc = accuracy_score(y_true, y_pred)
        mf1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        print(f"  [{key}] Fold {fold+1}: Acc={acc*100:.2f}%  MacroF1={mf1:.4f}")
        print(classification_report(y_true, y_pred, target_names=class_names, digits=4))

        np.save(os.path.join(OUT_DIR, f"{key}_fold_{fold+1}_y_true.npy"), y_true)
        np.save(pred_file, y_pred)
        import json
        with open(os.path.join(OUT_DIR, f"{key}_fold_{fold+1}_history.json"), "w") as hf:
            json.dump(history, hf)
        # Save class names once (asset generator needs them).
        with open(os.path.join(OUT_DIR, "class_names.json"), "w") as cf:
            json.dump(list(class_names), cf)
        # Keep WaveCoAtNet fold-1 checkpoint for Grad-CAM (gradcam.py reads it).
        if is_wave and fold == 0:
            torch.save(best_state, os.path.join(OUT_DIR, "best_wavecoatnet.pth"))
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def summarize(models):
    rows = []
    for key in models:
        accs, mf1s = [], []
        for fold in range(1, N_FOLDS + 1):
            yt = os.path.join(OUT_DIR, f"{key}_fold_{fold}_y_true.npy")
            yp = os.path.join(OUT_DIR, f"{key}_fold_{fold}_y_pred.npy")
            if not (os.path.exists(yt) and os.path.exists(yp)):
                continue
            t, p = np.load(yt), np.load(yp)
            accs.append(accuracy_score(t, p))
            mf1s.append(f1_score(t, p, average='macro', zero_division=0))
        if not accs:
            continue
        accs, mf1s = np.array(accs), np.array(mf1s)
        sd = accs.std(ddof=1) if len(accs) > 1 else 0.0
        ci = 1.96 * sd / np.sqrt(len(accs)) if len(accs) > 1 else 0.0
        rows.append(dict(model=key, folds=len(accs),
                         acc_mean=accs.mean(), acc_sd=sd,
                         acc_ci_lo=accs.mean() - ci, acc_ci_hi=accs.mean() + ci,
                         macro_f1_mean=mf1s.mean(),
                         macro_f1_sd=(mf1s.std(ddof=1) if len(mf1s) > 1 else 0.0)))
    rows.sort(key=lambda r: -r["acc_mean"])

    lines = ["=" * 80,
             "  MATCHED 5-FOLD CROSS-VALIDATION — MODEL COMPARISON (apples-to-apples)",
             "=" * 80,
             f"{'Model':<16}{'Folds':>6}{'Acc Mean':>11}{'±SD':>8}{'95% CI':>20}{'MacroF1':>10}",
             "-" * 80]
    for r in rows:
        lines.append(f"{r['model']:<16}{r['folds']:>6}{r['acc_mean']*100:>10.2f}%{r['acc_sd']*100:>7.2f}%"
                     f"  [{r['acc_ci_lo']*100:>5.2f}, {r['acc_ci_hi']*100:>5.2f}]{r['macro_f1_mean']:>10.4f}")
    lines += ["=" * 80,
              "If WaveCoAtNet's 95% CI does NOT overlap a rival's CI -> meaningful gap.",
              "If CIs overlap -> report 'competitive', not 'superior'."]
    text = "\n".join(lines)
    print("\n" + text)
    if rows:
        with open(os.path.join(OUT_DIR, "matched_cv_summary.txt"), "w") as f:
            f.write(text + "\n")
        with open(os.path.join(OUT_DIR, "matched_cv_summary.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nSaved: {os.path.join(OUT_DIR, 'matched_cv_summary.csv')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=ALL_MODELS,
                    help=f"subset of {ALL_MODELS}")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--summarize", action="store_true", help="rebuild table from saved preds only")
    args = ap.parse_args()

    global EPOCHS
    EPOCHS = args.epochs

    if args.summarize:
        summarize(args.models); return

    set_seed(RANDOM_SEED)
    from roboflow import Roboflow
    rf = Roboflow(api_key="gXuxxWEMFJ8nK73o7pN7")
    dataset = rf.workspace("hi-l9ueo").project("ich-s-7lnsj").version(1).download("folder")
    ddir = dataset.location
    valid_path = os.path.join(ddir, "valid")
    validation_path = os.path.join(ddir, "validation")
    if not os.path.exists(valid_path) and os.path.exists(validation_path):
        os.rename(validation_path, valid_path)

    all_paths, all_labels, class_names = collect_all_samples(ddir)
    all_labels = np.array(all_labels)
    print(f"Total samples: {len(all_paths)} | Classes: {class_names}")
    print(f"Label distribution: {np.bincount(all_labels)}")

    folds = get_folds(all_paths, all_labels)  # built ONCE, shared by every model

    train_aug = transforms.Compose([
        transforms.RandomResizedCrop(TARGET_SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(15),
        transforms.TrivialAugmentWide(), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.2))])
    val_tf = transforms.Compose([
        transforms.Resize(TARGET_SIZE), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    for key in args.models:
        if key != "wavecoatnet" and key not in BASELINES:
            raise SystemExit(f"Unknown model '{key}'. Choices: {ALL_MODELS}")
        run_model(key, folds, all_paths, all_labels, class_names, train_aug, val_tf)

    summarize(args.models)


if __name__ == "__main__":
    main()
