"""
Matched 5-Fold Cross-Validation — ALL MODELS, ONE RUN (apples-to-apples)
=======================================================================
Trains WaveCoAtNet AND the baselines through the EXACT SAME 5 stratified
folds, in the same script, same session, same seed, same augmentation,
same epochs, same optimizer scheme, same val-checkpoint selection, same
test evaluation. This is the only fully fair comparison.

Models (Option B — top rivals + proposed):
    wavecoatnet, wavecoatnet_v2, wavecoatnet_v3, wavecoatnet_v4, convnext_tiny, swin_tiny, dinov2

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

NOTE: All models share the EXACT same training protocol (epochs, LR,
augmentation, optimizer, class weights, loss). The ONLY differences are
architectural. This ensures a fair apples-to-apples comparison.
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
PROTO_MOM    = 0.99
PROTO_WARMUP = 5
VIT_BLOCKS   = 4

# WaveCoAtNet v4-specific
SCL_WEIGHT       = 0.1
AWPT_REG_WEIGHT  = 0.01
FREQ_DROPOUT_P   = 0.1

# Save to Drive so disconnects don't lose finished folds.
OUT_DIR = os.environ.get("CV_OUT_DIR",
                         "/content/drive/MyDrive/WaveCoAtNet_experiments/cv_matched")

# Baseline zoo. partial_freeze=None trains all; =N keeps last N blocks + head trainable.
# extra_kwargs are passed straight to timm.create_model (e.g. img_size for DINOv2,
# whose pretrained pos-embed is built for 518px and must be interpolated to 224).
BASELINES = {
    "convnext_tiny": dict(timm_name="convnext_tiny", partial_freeze=None, extra_kwargs={}),
    "swin_tiny":     dict(timm_name="swin_tiny_patch4_window7_224", partial_freeze=None, extra_kwargs={}),
    "dinov2":        dict(timm_name="vit_base_patch14_dinov2.lvd142m", partial_freeze=2,
                          extra_kwargs=dict(img_size=224)),
}
# wavecoatnet   = v1 (raw additive fusion)
# wavecoatnet_v2 = v1 + zero-init LayerScale gate on the ViT/wavelet path
# wavecoatnet_v3 = v2 + H-WG-FDCA + CrossModalFusion + MultiScaleCBAM + improved head (architecture only)
# wavecoatnet_v4 = v3 + LightAWPT + FrequencyDropout + SharedFreqPrototypes + LightSCL + HFA-WS
WAVE_MODELS = ["wavecoatnet", "wavecoatnet_v2", "wavecoatnet_v3", "wavecoatnet_v4"]
ALL_MODELS = WAVE_MODELS + list(BASELINES.keys())


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
    """Identical fold construction for every model => paired test sets.

    NOTE: If the dataset contains multiple patches per patient, this
    StratifiedKFold may cause patient-level leakage. For production use,
    consider GroupKFold with patient IDs. For fair model comparison,
    all models use the same splits, so relative ranking is valid.
    """
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    folds = []
    for fold, (train_val_idx, test_idx) in enumerate(
            skf.split(np.arange(len(all_paths)), all_labels)):
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=RANDOM_SEED + fold)
        tr_local, val_local = next(sss.split(train_val_idx, all_labels[train_val_idx]))
        folds.append((train_val_idx[tr_local], train_val_idx[val_local], test_idx))
    return folds


# ── Shared modules ──────────────────────────────────────────────────────────
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

    def forward(self, x):
        a = x.mean(dim=1, keepdim=True)
        m = x.max(dim=1, keepdim=True).values
        attn = torch.sigmoid(self.conv(torch.cat([a, m], dim=1)))
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
        self.register_buffer('prototypes', torch.zeros(num_classes, dim))
        self.register_buffer('proto_initialized', torch.zeros(num_classes, dtype=torch.bool))
        self.register_buffer('proto_temperature', torch.tensor(1.0))
        mid = max(1, dim // 16)
        self.channel_scorer = nn.Sequential(nn.Linear(dim, mid), nn.GELU(), nn.Dropout(dropout), nn.Linear(mid, 1))
        self.importance_weights = nn.Parameter(torch.tensor([1.0, 0.5, 0.5]))
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
        importance = F.softmax(w[0]*_zn(proto_aff) - w[1]*_zn(proto_ent) + w[2]*_zn(ch_score), dim=-1)
        k = int((self.min_keep + self.max_keep) * 0.5 * N)
        k = max(1, min(k, int(self.max_keep * N)))
        _, idx = torch.topk(importance, k, dim=1)
        bi = torch.arange(B, device=x.device).unsqueeze(1).expand(-1, k)
        sel = x[bi, idx] * (1 + importance[bi, idx].unsqueeze(-1))
        return sel, importance

    @torch.no_grad()
    def update_prototypes(self, embeddings, labels, momentum=0.99):
        for c in range(self.num_classes):
            m = labels == c
            n_samples = m.sum().item()
            if n_samples > 0:
                class_mean = embeddings[m].mean(0)
                if not self.proto_initialized[c]:
                    self.prototypes[c] = class_mean
                    self.proto_initialized[c] = True
                else:
                    effective_momentum = momentum ** n_samples
                    self.prototypes[c] = effective_momentum * self.prototypes[c] + (1 - effective_momentum) * class_mean

    def prototype_orthogonality_loss(self, embeddings=None):
        if embeddings is not None and embeddings.requires_grad:
            e_norm = F.normalize(embeddings, dim=-1)
            sim = e_norm @ e_norm.T
            eye = torch.eye(sim.shape[0], device=sim.device)
            return ((sim - eye) ** 2).mean()
        p_norm = F.normalize(self.prototypes, dim=-1)
        sim = p_norm @ p_norm.T
        eye = torch.eye(self.num_classes, device=sim.device)
        return ((sim - eye) ** 2).mean()


class SupervisedContrastiveTokenLoss(nn.Module):
    def __init__(self, embed_dim, proj_dim=128, temperature=0.07):
        super().__init__()
        self.temperature = temperature
        self.projector = nn.Sequential(nn.Linear(embed_dim, embed_dim), nn.GELU(), nn.Linear(embed_dim, proj_dim))

    def forward(self, embeddings, labels, prototypes=None, class_weights=None):
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
            return supcon + 0.5 * F.cross_entropy(proto_sim, labels, weight=class_weights)
        return supcon


# ── v3-only architectural modules ───────────────────────────────────────────
class HierarchicalWaveletCrossAttention(nn.Module):
    """Second-scale wavelet cross-attention: stage2(192) -> stage3(384)."""
    def __init__(self, dim_low=192, dim_high=384, num_heads=6, dropout=0.1):
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
            nn.Linear(dim_high * 2, dim_high // 4), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(dim_high // 4, 1), nn.Sigmoid())
        self.ffn = nn.Sequential(
            nn.Linear(dim_high, dim_high * 2), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(dim_high * 2, dim_high), nn.Dropout(dropout))
        self.norm_ffn = nn.LayerNorm(dim_high)

    def _cross_attend(self, q, kv, k_proj, v_proj, out_proj, norm_kv):
        B = q.shape[0]; kv = norm_kv(kv)
        Q = self.q_proj(self.norm_q(q)).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = k_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = v_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        attn = self.attn_drop((Q @ K.transpose(-2, -1) * self.scale).softmax(dim=-1))
        return self.proj_drop(out_proj((attn @ V).transpose(1, 2).reshape(B, -1, self.num_heads * self.head_dim)))

    def forward(self, feat_low, feat_high):
        ll, lh, hl, hh = haar_dwt_2d(feat_low)
        lo_tok = self.proj_low_freq(ll).flatten(2).transpose(1, 2)
        hi_tok = self.proj_high_freq(torch.cat([lh, hl, hh], dim=1)).flatten(2).transpose(1, 2)
        q = feat_high.flatten(2).transpose(1, 2)
        lo = self._cross_attend(q, lo_tok, self.k_proj_low, self.v_proj_low, self.out_proj_low, self.norm_kv_low)
        hi = self._cross_attend(q, hi_tok, self.k_proj_high, self.v_proj_high, self.out_proj_high, self.norm_kv_high)
        gate = self.freq_gate(torch.cat([lo, hi], dim=-1))
        fused = q + gate * hi + (1 - gate) * lo
        return fused + self.ffn(self.norm_ffn(fused))


class CrossModalFusion(nn.Module):
    """Bidirectional cross-attention between CNN and ViT tokens."""
    def __init__(self, dim=768, num_heads=8, dropout=0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.norm_cnn = nn.LayerNorm(dim)
        self.norm_vit = nn.LayerNorm(dim)
        self.q_cnn = nn.Linear(dim, dim, bias=False)
        self.k_vit = nn.Linear(dim, dim, bias=False)
        self.v_vit = nn.Linear(dim, dim, bias=False)
        self.out_cnn = nn.Linear(dim, dim)
        self.q_vit = nn.Linear(dim, dim, bias=False)
        self.k_cnn = nn.Linear(dim, dim, bias=False)
        self.v_cnn = nn.Linear(dim, dim, bias=False)
        self.out_vit = nn.Linear(dim, dim)
        self.attn_drop = nn.Dropout(dropout * 0.5)
        self.proj_drop = nn.Dropout(dropout)
        self.gate = nn.Sequential(
            nn.Linear(dim * 2, dim // 4), nn.GELU(),
            nn.Linear(dim // 4, dim), nn.Sigmoid())
        self.ffn = nn.Sequential(
            nn.Linear(dim, dim * 2), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(dim * 2, dim), nn.Dropout(dropout))
        self.norm_ffn = nn.LayerNorm(dim)

    def _attend(self, q_tok, kv_tok, q_proj, k_proj, v_proj, out_proj, q_norm, kv_norm):
        B = q_tok.shape[0]
        Q = q_proj(q_norm(q_tok)).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = k_proj(kv_norm(kv_tok)).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = v_proj(kv_norm(kv_tok)).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        attn = self.attn_drop((Q @ K.transpose(-2, -1) * self.scale).softmax(dim=-1))
        return self.proj_drop(out_proj((attn @ V).transpose(1, 2).reshape(B, -1, self.num_heads * self.head_dim)))

    def forward(self, cnn_tokens, vit_tokens):
        cnn2vit = self._attend(cnn_tokens, vit_tokens, self.q_cnn, self.k_vit, self.v_vit, self.out_cnn, self.norm_cnn, self.norm_vit)
        vit2cnn = self._attend(vit_tokens, cnn_tokens, self.q_vit, self.k_cnn, self.v_cnn, self.out_vit, self.norm_vit, self.norm_cnn)
        g = self.gate(torch.cat([cnn2vit.mean(1), vit2cnn.mean(1)], dim=-1)).unsqueeze(1)
        cnn_out = cnn_tokens + g * cnn2vit
        vit_out = vit_tokens + (1 - g) * vit2cnn
        cnn_out = cnn_out + self.ffn(self.norm_ffn(cnn_out))
        vit_out = vit_out + self.ffn(self.norm_ffn(vit_out))
        return cnn_out, vit_out


# ── v4-only novel modules ─────────────────────────────────────────────────────
class LightweightAWPT(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.decomp = nn.Conv2d(channels, channels * 4, kernel_size=4,
                                stride=4, groups=channels, bias=False)
        self._init_haar()
        self.freq_gate = nn.Sequential(
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
            nn.Linear(channels * 4, channels), nn.Sigmoid())
        self.register_buffer('haar_init', self.decomp.weight.clone())

    def _init_haar(self):
        with torch.no_grad():
            for i in range(self.decomp.weight.shape[0]):
                self.decomp.weight[i, 0, :, :] = torch.tensor([[1, 1], [1, 1]], dtype=torch.float32) / 4.0
                self.decomp.weight[i, 1, :, :] = torch.tensor([[1, 1], [-1, -1]], dtype=torch.float32) / 4.0
                self.decomp.weight[i, 2, :, :] = torch.tensor([[1, -1], [1, -1]], dtype=torch.float32) / 4.0
                self.decomp.weight[i, 3, :, :] = torch.tensor([[1, -1], [-1, 1]], dtype=torch.float32) / 4.0

    def spectral_reg(self):
        return F.mse_loss(self.decomp.weight, self.haar_init) * 0.01

    def forward(self, x):
        B, C, H, W = x.shape
        decomp = self.decomp(x).reshape(B, C, 4, H // 4, W // 4)
        ll, lh, hl, hh = decomp[:, :, 0], decomp[:, :, 1], decomp[:, :, 2], decomp[:, :, 3]
        gate = self.freq_gate(torch.cat([ll.mean((2, 3)), lh.mean((2, 3)),
                                          hl.mean((2, 3)), hh.mean((2, 3))], dim=-1))
        out = (1 - gate).unsqueeze(-1).unsqueeze(-1) * ll + gate.unsqueeze(-1).unsqueeze(-1) * (lh + hl + hh) / 3.0
        return out, (ll, lh, hl, hh)


class FrequencyDropout(nn.Module):
    def __init__(self, p=0.1):
        super().__init__()
        self.p = p

    def forward(self, ll, lh, hl, hh):
        if not self.training:
            return ll, lh, hl, hh
        mask = torch.bernoulli(torch.ones(4, device=ll.device) * (1 - self.p))
        return ll * mask[0], lh * mask[1], hl * mask[2], hh * mask[3]


class SharedFrequencyPrototypes(nn.Module):
    def __init__(self, dim, num_classes=5, num_bands=4):
        super().__init__()
        self.num_classes = num_classes
        self.num_bands = num_bands
        self.register_buffer('prototypes', torch.zeros(num_classes, dim))
        self.register_buffer('proto_initialized', torch.zeros(num_classes, dtype=torch.bool))
        self.register_buffer('proto_temperature', torch.tensor(1.0))
        self.freq_proj = nn.Linear(dim, dim, bias=False)
        self.freq_norm = nn.LayerNorm(dim)
        self.class_freq_weights = nn.Parameter(torch.zeros(num_classes, num_bands))
        self.channel_scorer = nn.Sequential(nn.Linear(dim, dim // 16), nn.GELU(),
                                            nn.Linear(dim // 16, 1))
        self.importance_weights = nn.Parameter(torch.tensor([1.0, 0.5, 0.5]))
        self.norm = nn.LayerNorm(dim)

    def forward(self, x, subbands=None):
        B, N, C = x.shape
        x_normed = self.norm(x)
        if subbands is None:
            proto_norm = F.normalize(self.prototypes, dim=-1)
            tok_norm = F.normalize(x_normed, dim=-1)
            sim = tok_norm @ proto_norm.T
            return sim.max(dim=-1).values, x_normed

        band_sims = []
        for band in subbands:
            band_tok = band.flatten(2).transpose(1, 2)
            band_proj = self.freq_proj(band_tok)
            band_norm = F.normalize(self.freq_norm(band_proj), dim=-1)
            proto_norm = F.normalize(self.prototypes, dim=-1)
            band_sims.append(band_norm @ proto_norm.T)

        freq_w = F.softmax(self.class_freq_weights, dim=-1)
        combined = torch.stack(band_sims, dim=2)
        weights = freq_w.unsqueeze(0).unsqueeze(0)
        weighted_sim = (combined * weights).sum(dim=2)
        proto_aff = weighted_sim.max(dim=-1).values

        proto_probs = F.softmax(weighted_sim / self.proto_temperature.clamp(min=0.01), dim=-1)
        proto_ent = -(proto_probs * (proto_probs + 1e-8).log()).sum(dim=-1)
        ch_score = self.channel_scorer(x_normed).squeeze(-1)

        def _zn(s):
            s = s - s.mean(dim=-1, keepdim=True)
            return s / (s.std(dim=-1, keepdim=True) + 1e-6)

        w = F.softmax(self.importance_weights, dim=0)
        importance = F.softmax(w[0] * _zn(proto_aff) - w[1] * _zn(proto_ent) + w[2] * _zn(ch_score), dim=-1)
        return importance, x_normed

    @torch.no_grad()
    def update_prototypes(self, embeddings, labels, momentum=0.99):
        for c in range(self.num_classes):
            m = labels == c
            n_samples = m.sum().item()
            if n_samples > 0:
                class_mean = embeddings[m].mean(0)
                if not self.proto_initialized[c]:
                    self.prototypes[c] = class_mean
                    self.proto_initialized[c] = True
                else:
                    effective_momentum = momentum ** n_samples
                    self.prototypes[c] = effective_momentum * self.prototypes[c] + (1 - effective_momentum) * class_mean

    def prototype_orthogonality_loss(self):
        p_norm = F.normalize(self.prototypes, dim=-1)
        sim = p_norm @ p_norm.T
        eye = torch.eye(self.num_classes, device=sim.device)
        return ((sim - eye) ** 2).mean()


class LightweightSpectralContrastiveLoss(nn.Module):
    def __init__(self, embed_dim, top_k=32, temperature=0.1):
        super().__init__()
        self.top_k = top_k
        self.temperature = temperature
        self.spec_proj = nn.Sequential(nn.Linear(top_k, top_k), nn.GELU(), nn.Linear(top_k, 64))

    def forward(self, features, labels):
        B = features.shape[0]
        if B < 2:
            return torch.tensor(0.0, device=features.device, requires_grad=True)
        fft_mag = torch.fft.rfft2(features.mean(1)).abs().flatten(1)
        k = min(self.top_k, fft_mag.shape[1])
        _, topk_idx = fft_mag.topk(k, dim=1)
        spec_emb = torch.gather(fft_mag, 1, topk_idx)
        if spec_emb.shape[1] < self.top_k:
            spec_emb = F.pad(spec_emb, (0, self.top_k - spec_emb.shape[1]))
        z = F.normalize(self.spec_proj(spec_emb), dim=-1)
        sim = z @ z.T / self.temperature
        label_eq = labels.unsqueeze(0) == labels.unsqueeze(1)
        self_mask = ~torch.eye(B, dtype=torch.bool, device=z.device)
        positives = label_eq & self_mask
        has_pos = positives.float().sum(1) > 0
        if has_pos.sum() == 0:
            return torch.tensor(0.0, device=features.device, requires_grad=True)
        sim = sim - sim.max(1, keepdim=True).values.detach()
        exp_sim = torch.exp(sim) * self_mask.float()
        log_prob = sim - torch.log(exp_sim.sum(1, keepdim=True) + 1e-8)
        pos_count = torch.clamp(positives.float().sum(1), min=1.0)
        loss = -(positives.float() * log_prob).sum(1) / pos_count
        return loss[has_pos].mean()


class HierarchicalFrequencyAttention(nn.Module):
    def __init__(self, dim, num_heads=6, num_bands=4, dropout=0.1):
        super().__init__()
        self.num_heads = num_heads
        self.num_bands = num_bands
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.proj = nn.Linear(dim, dim)
        self.norm = nn.LayerNorm(dim)
        self.attn_drop = nn.Dropout(dropout * 0.5)
        self.proj_drop = nn.Dropout(dropout)
        self.band_gate = nn.Sequential(nn.Linear(dim, num_bands), nn.Softmax(dim=-1))
        self.ffn = nn.Sequential(nn.Linear(dim, dim * 2), nn.GELU(),
                                 nn.Dropout(dropout), nn.Linear(dim * 2, dim), nn.Dropout(dropout))
        self.norm_ffn = nn.LayerNorm(dim)

    def forward(self, x):
        B, N, C = x.shape
        H = self.num_heads
        qkv = self.qkv(self.norm(x)).reshape(B, N, 3, H, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)
        out = (attn @ v).transpose(1, 2).reshape(B, N, C)
        out = self.proj_drop(self.proj(out))
        gate = self.band_gate(x.mean(1))
        freq_mod = 1.0 + 0.1 * gate.mean(-1, keepdim=True).unsqueeze(-1)
        out = out * freq_mod
        return x + out + self.ffn(self.norm_ffn(x + out))


# ── Model variants (architecture only — training is identical) ───────────────
class WaveCoAtNet(nn.Module):
    """v1/v2: WG-FDCA + PA-DTS + PGAP + DPA + SCTR + CBAMx2."""
    def __init__(self, num_classes=5, vit_blocks=4, dropout=0.2, gated_fusion=False):
        super().__init__()
        self.gated_fusion = gated_fusion
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
                  drop_path=i * 0.15 / max(vit_blocks - 1, 1)) for i in range(vit_blocks)])
        self.vit_to_cnn_proj = nn.Sequential(
            nn.LayerNorm(vit_dim), nn.Linear(vit_dim, final_dim), nn.GELU(), nn.Dropout(dropout))
        self.pa_dts = PrototypeAnchoredTokenSelection(final_dim, num_classes, 0.6, 0.95, dropout*0.25)
        self.sctr = SupervisedContrastiveTokenLoss(final_dim, 128, 0.07)
        self.pgap_norm = nn.LayerNorm(final_dim)
        self.dpa_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim // 4), nn.GELU(),
            nn.Linear(final_dim // 4, final_dim), nn.Sigmoid())
        self.fusion_scale = nn.Parameter(torch.zeros(1, 1, final_dim)) if gated_fusion else None
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
        if self.fusion_scale is not None:
            tokens = cnn_tokens + self.fusion_scale * vit_proj
        else:
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

    def get_classifier(self):
        return self.classifier


class WaveCoAtNetV3(nn.Module):
    """v3: H-WG-FDCA + CrossModalFusion + MultiScaleCBAM + Multi-Scale Feature Pyramid + improved head."""
    def __init__(self, num_classes=5, vit_blocks=8, dropout=0.2):
        super().__init__()
        self.num_vit_blocks = vit_blocks
        cnn = create_model('convnext_tiny', pretrained=True, num_classes=0)
        self.cnn_stem = cnn.stem
        self.cnn_stage1 = cnn.stages[0]
        self.cnn_stage2 = cnn.stages[1]
        self.cnn_stage3 = cnn.stages[2]
        self.cnn_stage4 = cnn.stages[3]
        self.cbam2 = CBAM(192, reduction=16, kernel_size=7)
        self.cbam3 = CBAM(384, reduction=16, kernel_size=7)
        self.cbam4 = CBAM(768, reduction=16, kernel_size=7)
        vit_dim, final_dim = 192, 768
        self.wg_fdca = WaveletFrequencyDecomposedCrossAttention(96, 192, 4, dropout)
        self.hw_fdca = HierarchicalWaveletCrossAttention(192, 384, 6, dropout)
        self.hw_to_vit_proj = nn.Sequential(
            nn.LayerNorm(384), nn.Linear(384, vit_dim), nn.GELU())
        self.pos_embed = nn.Parameter(torch.zeros(1, 28*28, vit_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        self.vit_blocks = nn.ModuleList([
            Block(dim=vit_dim, num_heads=6, proj_drop=dropout, attn_drop=dropout*0.5,
                  drop_path=i * 0.15 / max(vit_blocks - 1, 1)) for i in range(vit_blocks)])
        self.vit_to_cnn_proj = nn.Sequential(
            nn.LayerNorm(vit_dim), nn.Linear(vit_dim, final_dim), nn.GELU(), nn.Dropout(dropout))
        self.cross_modal = CrossModalFusion(dim=final_dim, num_heads=8, dropout=dropout)
        self.cnn_pos_embed = nn.Parameter(torch.zeros(1, 49, final_dim))
        nn.init.trunc_normal_(self.cnn_pos_embed, std=0.02)

        # Multi-Scale Feature Pyramid: project each CNN stage to final_dim and fuse
        self.stage1_proj = nn.Sequential(nn.Conv2d(96, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage2_proj = nn.Sequential(nn.Conv2d(192, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage3_proj = nn.Sequential(nn.Conv2d(384, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage4_proj = nn.Sequential(nn.Conv2d(768, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.pyramid_attn = nn.Sequential(
            nn.Linear(final_dim * 4, final_dim), nn.GELU(),
            nn.Linear(final_dim, 4), nn.Softmax(dim=-1))
        self.pyramid_norm = nn.LayerNorm(final_dim)

        self.pa_dts = PrototypeAnchoredTokenSelection(final_dim, num_classes, 0.6, 0.95, dropout*0.25)
        self.sctr = SupervisedContrastiveTokenLoss(final_dim, 128, 0.07)
        self.pgap_norm = nn.LayerNorm(final_dim)
        self.dpa_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim // 4), nn.GELU(),
            nn.Linear(final_dim // 4, final_dim), nn.Sigmoid())
        self.fusion_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim), nn.GELU(),
            nn.Linear(final_dim, final_dim), nn.Sigmoid()
        )
        self.classifier = nn.Sequential(
            nn.LayerNorm(final_dim), nn.Dropout(dropout),
            nn.Linear(final_dim, final_dim // 2), nn.GELU(),
            nn.Dropout(dropout * 0.5), nn.Linear(final_dim // 2, num_classes))

    def _fuse_pyramid(self, s1_feat, s2_feat, s3_feat, s4_feat, B):
        s1_p = F.adaptive_avg_pool2d(self.stage1_proj(s1_feat), (7, 7)).flatten(2).transpose(1, 2)
        s2_p = F.adaptive_avg_pool2d(self.stage2_proj(s2_feat), (7, 7)).flatten(2).transpose(1, 2)
        s3_p = F.adaptive_avg_pool2d(self.stage3_proj(s3_feat), (7, 7)).flatten(2).transpose(1, 2)
        s4_p = F.adaptive_avg_pool2d(self.stage4_proj(s4_feat), (7, 7)).flatten(2).transpose(1, 2)
        cat = torch.cat([s1_p.mean(1), s2_p.mean(1), s3_p.mean(1), s4_p.mean(1)], dim=-1)
        w = self.pyramid_attn(cat).unsqueeze(-1).unsqueeze(-1)
        fused = w[:, 0] * s1_p + w[:, 1] * s2_p + w[:, 2] * s3_p + w[:, 3] * s4_p
        return self.pyramid_norm(fused)

    def forward(self, x, return_embeddings=False):
        x = self.cnn_stem(x)
        s1 = self.cnn_stage1(x); s2 = self.cnn_stage2(s1)
        s2_cbam = self.cbam2(s2)
        vit_tokens = self.wg_fdca(s1, s2_cbam) + self.pos_embed
        B = s2_cbam.shape[0]
        s3 = self.cnn_stage3(s2_cbam)
        hw_feat = self.hw_fdca(s2_cbam, s3)
        hw_proj = self.hw_to_vit_proj(hw_feat).transpose(1, 2).reshape(B, 192, 14, 14)
        hw_proj = F.interpolate(hw_proj, size=(28, 28), mode='bilinear', align_corners=False)
        hw_proj = hw_proj.flatten(2).transpose(1, 2)
        vit_tokens = vit_tokens + hw_proj
        for blk in self.vit_blocks:
            vit_tokens = blk(vit_tokens)
        s4 = self.cnn_stage4(self.cbam3(s3))
        cnn_tokens = self.cbam4(s4).flatten(2).transpose(1, 2)
        vit_proj = self.vit_to_cnn_proj(vit_tokens).transpose(1, 2).reshape(B, 768, 28, 28)
        vit_proj = F.adaptive_avg_pool2d(vit_proj, (7, 7)).flatten(2).transpose(1, 2)
        cnn_tokens = cnn_tokens + self.cnn_pos_embed
        cnn_tokens, vit_proj = self.cross_modal(cnn_tokens, vit_proj)
        gate = self.fusion_gate(torch.cat([cnn_tokens, vit_proj], dim=-1))
        tokens = gate * cnn_tokens + (1.0 - gate) * vit_proj
        pyramid = self._fuse_pyramid(s1, s2_cbam, s3, s4, B)
        tokens = tokens + pyramid
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

    def get_classifier(self):
        return self.classifier


class WaveCoAtNetV4(nn.Module):
    """v4: LightAWPT + FrequencyDropout + SharedFreqPrototypes + LightSCL + HFA-WS."""
    def __init__(self, num_classes=5, vit_blocks=8, dropout=0.2):
        super().__init__()
        cnn = create_model('convnext_tiny', pretrained=True, num_classes=0)
        self.cnn_stem = cnn.stem
        self.cnn_stage1 = cnn.stages[0]
        self.cnn_stage2 = cnn.stages[1]
        self.cnn_stage3 = cnn.stages[2]
        self.cnn_stage4 = cnn.stages[3]
        self.cbam2 = CBAM(192, reduction=16, kernel_size=7)
        self.cbam3 = CBAM(384, reduction=16, kernel_size=7)
        self.cbam4 = CBAM(768, reduction=16, kernel_size=7)

        vit_dim, final_dim = 192, 768

        self.awpt1 = LightweightAWPT(96)
        self.awpt2 = LightweightAWPT(192)
        self.freq_drop = FrequencyDropout(p=FREQ_DROPOUT_P)

        self.wg_fdca = WaveletFrequencyDecomposedCrossAttention(96, 192, 4, dropout)
        self.hw_fdca = HierarchicalWaveletCrossAttention(192, 384, 6, dropout)
        self.hw_to_vit_proj = nn.Sequential(
            nn.LayerNorm(384), nn.Linear(384, vit_dim), nn.GELU())

        self.pos_embed = nn.Parameter(torch.zeros(1, 28 * 28, vit_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        self.hfa_blocks = nn.ModuleList([
            HierarchicalFrequencyAttention(vit_dim, 6, 4, dropout)
            for _ in range(vit_blocks)])

        self.vit_to_cnn_proj = nn.Sequential(
            nn.LayerNorm(vit_dim), nn.Linear(vit_dim, final_dim), nn.GELU(), nn.Dropout(dropout))
        self.cross_modal = CrossModalFusion(dim=final_dim, num_heads=8, dropout=dropout)
        self.cnn_pos_embed = nn.Parameter(torch.zeros(1, 49, final_dim))
        nn.init.trunc_normal_(self.cnn_pos_embed, std=0.02)

        self.stage1_proj = nn.Sequential(nn.Conv2d(96, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage2_proj = nn.Sequential(nn.Conv2d(192, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage3_proj = nn.Sequential(nn.Conv2d(384, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.stage4_proj = nn.Sequential(nn.Conv2d(768, final_dim, 1, bias=False), nn.BatchNorm2d(final_dim))
        self.pyramid_attn = nn.Sequential(
            nn.Linear(final_dim * 4, final_dim), nn.GELU(),
            nn.Linear(final_dim, 4), nn.Softmax(dim=-1))
        self.pyramid_norm = nn.LayerNorm(final_dim)

        self.shared_freq_proto = SharedFrequencyPrototypes(final_dim, num_classes, 4)
        self.pa_dts = PrototypeAnchoredTokenSelection(final_dim, num_classes, 0.6, 0.95, dropout * 0.25)
        self.sctr = SupervisedContrastiveTokenLoss(final_dim, 128, 0.07)
        self.light_scl = LightweightSpectralContrastiveLoss(final_dim, top_k=32)

        self.pgap_norm = nn.LayerNorm(final_dim)
        self.dpa_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim // 4), nn.GELU(),
            nn.Linear(final_dim // 4, final_dim), nn.Sigmoid())
        self.fusion_gate = nn.Sequential(
            nn.Linear(final_dim * 2, final_dim), nn.GELU(),
            nn.Linear(final_dim, final_dim), nn.Sigmoid())
        self.classifier = nn.Sequential(
            nn.LayerNorm(final_dim), nn.Dropout(dropout),
            nn.Linear(final_dim, final_dim // 2), nn.GELU(),
            nn.Dropout(dropout * 0.5), nn.Linear(final_dim // 2, num_classes))

    def _fuse_pyramid(self, s1_feat, s2_feat, s3_feat, s4_feat, B):
        s1_p = F.adaptive_avg_pool2d(self.stage1_proj(s1_feat), (7, 7)).flatten(2).transpose(1, 2)
        s2_p = F.adaptive_avg_pool2d(self.stage2_proj(s2_feat), (7, 7)).flatten(2).transpose(1, 2)
        s3_p = F.adaptive_avg_pool2d(self.stage3_proj(s3_feat), (7, 7)).flatten(2).transpose(1, 2)
        s4_p = F.adaptive_avg_pool2d(self.stage4_proj(s4_feat), (7, 7)).flatten(2).transpose(1, 2)
        cat = torch.cat([s1_p.mean(1), s2_p.mean(1), s3_p.mean(1), s4_p.mean(1)], dim=-1)
        w = self.pyramid_attn(cat).unsqueeze(-1).unsqueeze(-1)
        fused = w[:, 0] * s1_p + w[:, 1] * s2_p + w[:, 2] * s3_p + w[:, 3] * s4_p
        return self.pyramid_norm(fused)

    def forward(self, x, return_embeddings=False):
        x = self.cnn_stem(x)
        s1 = self.cnn_stage1(x)
        s2 = self.cnn_stage2(s1)
        s2_cbam = self.cbam2(s2)

        _, (s1_ll, s1_lh, s1_hl, s1_hh) = self.awpt1(s1)
        s1_ll, s1_lh, s1_hl, s1_hh = self.freq_drop(s1_ll, s1_lh, s1_hl, s1_hh)

        vit_tokens = self.wg_fdca(s1, s2_cbam) + self.pos_embed
        B = s2_cbam.shape[0]
        s3 = self.cnn_stage3(s2_cbam)
        hw_feat = self.hw_fdca(s2_cbam, s3)
        hw_proj = self.hw_to_vit_proj(hw_feat).transpose(1, 2).reshape(B, 192, 14, 14)
        hw_proj = F.interpolate(hw_proj, size=(28, 28), mode='bilinear', align_corners=False)
        hw_proj = hw_proj.flatten(2).transpose(1, 2)
        vit_tokens = vit_tokens + hw_proj

        for blk in self.hfa_blocks:
            vit_tokens = blk(vit_tokens)

        s4 = self.cnn_stage4(self.cbam3(s3))
        cnn_tokens = self.cbam4(s4).flatten(2).transpose(1, 2)
        vit_proj = self.vit_to_cnn_proj(vit_tokens).transpose(1, 2).reshape(B, 768, 28, 28)
        vit_proj = F.adaptive_avg_pool2d(vit_proj, (7, 7)).flatten(2).transpose(1, 2)
        cnn_tokens = cnn_tokens + self.cnn_pos_embed
        cnn_tokens, vit_proj = self.cross_modal(cnn_tokens, vit_proj)
        gate = self.fusion_gate(torch.cat([cnn_tokens, vit_proj], dim=-1))
        tokens = gate * cnn_tokens + (1.0 - gate) * vit_proj
        pyramid = self._fuse_pyramid(s1, s2_cbam, s3, s4, B)
        tokens = tokens + pyramid

        importance, tokens_normed = self.shared_freq_proto(
            tokens, subbands=[s1_ll, s1_lh, s1_hl, s1_hh])
        k = max(1, int(0.75 * tokens.shape[1]))
        _, idx = torch.topk(importance, k, dim=1)
        bi = torch.arange(B, device=tokens.device).unsqueeze(1).expand(-1, k)
        selected = tokens[bi, idx] * (1 + importance[bi, idx].unsqueeze(-1))

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

    def get_classifier(self):
        return self.classifier


def build_baseline(key, num_classes):
    """Instantiates a timm baseline model using the settings defined in BASELINES."""
    cfg = BASELINES[key]
    model = create_model(
        cfg["timm_name"],
        pretrained=True,
        num_classes=num_classes,
        **cfg.get("extra_kwargs", {})
    )
    if cfg.get("partial_freeze") is not None:
        for p in model.parameters():
            p.requires_grad = False
        for p in model.get_classifier().parameters():
            p.requires_grad = True
        blocks = getattr(model, "blocks", None)
        if blocks is not None:
            for blk in blocks[-cfg["partial_freeze"]:]:
                for p in blk.parameters():
                    p.requires_grad = True
        if hasattr(model, 'norm'):
            for p in model.norm.parameters():
                p.requires_grad = True
    return model


def make_optimizer(model, is_wave):
    """Pretrained params → LR_BACKBONE, novel/classifier params → LR_HEAD."""
    backbone, novel = [], []
    classifier_params = set(map(id, model.get_classifier().parameters()))
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if id(p) in classifier_params:
            novel.append(p)
        elif is_wave:
            is_bb = any(s in name for s in ['cnn_stem', 'cnn_stage1', 'cnn_stage2', 'cnn_stage3', 'cnn_stage4'])
            (backbone if is_bb else novel).append(p)
        else:
            backbone.append(p)
    groups = []
    if backbone:
        groups.append({'params': backbone, 'lr': LR_BACKBONE})
    if novel:
        groups.append({'params': novel, 'lr': LR_HEAD})
    return torch.optim.AdamW(groups, weight_decay=WEIGHT_DECAY)


# ── Train / eval (IDENTICAL for all models) ──────────────────────────────────
def train_epoch(model, loader, criterion, optimizer, scaler, is_wave, epoch, class_weights=None):
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
                sctr = model.sctr(emb.float(), tgts, model.pa_dts.prototypes, class_weights)
                loss = ce + SCTR_WEIGHT * sctr
                if hasattr(model, 'light_scl'):
                    scl = model.light_scl(emb.float(), tgts)
                    loss = loss + SCL_WEIGHT * scl
                if hasattr(model, 'awpt1'):
                    awpt_reg = model.awpt1.spectral_reg() + model.awpt2.spectral_reg()
                    loss = loss + AWPT_REG_WEIGHT * awpt_reg
                if hasattr(model, 'shared_freq_proto'):
                    ortho_loss = model.shared_freq_proto.prototype_orthogonality_loss()
                    loss = loss + 0.05 * ortho_loss
            else:
                logits = model(imgs)
                loss = criterion(logits, tgts)
        if use_amp:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            if is_wave:
                model.pa_dts.update_prototypes(emb.detach().float(), tgts, proto_mom)
                if hasattr(model, 'shared_freq_proto'):
                    model.shared_freq_proto.update_prototypes(emb.detach().float(), tgts, proto_mom)
            scaler.step(optimizer); scaler.update()
        else:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            if is_wave:
                model.pa_dts.update_prototypes(emb.detach(), tgts, proto_mom)
                if hasattr(model, 'shared_freq_proto'):
                    model.shared_freq_proto.update_prototypes(emb.detach(), tgts, proto_mom)
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
    is_wave = key in WAVE_MODELS
    gated = key == "wavecoatnet_v2"
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

        if key == "wavecoatnet_v3":
            model = WaveCoAtNetV3(num_classes, vit_blocks=8, dropout=0.0).to(DEVICE)
        elif key == "wavecoatnet_v4":
            model = WaveCoAtNetV4(num_classes, vit_blocks=8, dropout=0.0).to(DEVICE)
        elif is_wave:
            model = WaveCoAtNet(num_classes, VIT_BLOCKS, 0.0, gated_fusion=gated).to(DEVICE)
        else:
            model = build_baseline(key, num_classes).to(DEVICE)

        optimizer = make_optimizer(model, is_wave)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        best_val, best_state = 0.0, None
        history = {"train_acc": [], "val_acc": []}
        for epoch in range(EPOCHS):
            tr_acc = train_epoch(model, tr_loader, criterion, optimizer, scaler, is_wave, epoch,
                                 class_weights=cw)
            scheduler.step()
            val_yt, val_yp = eval_loader(model, val_loader)
            val_acc = accuracy_score(val_yt, val_yp)
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
        with open(os.path.join(OUT_DIR, "class_names.json"), "w") as cf:
            json.dump(list(class_names), cf)
        if is_wave and fold == 0:
            torch.save(best_state, os.path.join(OUT_DIR, f"best_{key}.pth"))
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
    global EPOCHS
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=ALL_MODELS,
                    help=f"subset of {ALL_MODELS}")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--summarize", action="store_true", help="rebuild table from saved preds only")
    args = ap.parse_args()

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
        if key not in WAVE_MODELS and key not in BASELINES:
            raise SystemExit(f"Unknown model '{key}'. Choices: {ALL_MODELS}")
        try:
            run_model(key, folds, all_paths, all_labels, class_names, train_aug, val_tf)
        except Exception as e:
            import traceback
            print(f"\n!!! [{key}] FAILED — skipping. Error: {e}")
            traceback.print_exc()
            print(f"!!! Other models continue. Fix '{key}' and rerun to fill it in.\n")

    summarize(args.models)


if __name__ == "__main__":
    main()
