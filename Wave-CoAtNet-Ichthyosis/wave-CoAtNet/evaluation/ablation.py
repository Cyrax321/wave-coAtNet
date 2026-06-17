"""
WaveCoAtNet: Ablation Study
==============================
Trains ten model conditions to isolate the contribution of each novel
module. All conditions use identical hyperparameters, seed, and data split.

    python evaluation/ablation.py --condition full

Conditions:
  full             -- WaveCoAtNet (all: WG-FDCA + 4 ViT + CBAM + PA-DTS + PGAP + DPA + SCTR)
  no_dpa           -- Full but with PGAP only (no Dual-Path Aggregation)
  no_pgap          -- Full but with mean-pooling instead of PGAP+DPA
  no_wgfdca        -- Plain cross-attention instead of wavelet-decomposed
  no_transformer   -- CNN + PA-DTS only (no ViT blocks, no cross-attention)
  no_padts         -- WG-FDCA + ViT, but uses global avg pool (no token selection)
  no_sctr          -- Full architecture but without contrastive loss
  fixed_pruning    -- WG-FDCA + ViT + old SE with fixed 75/50% pruning
  no_prototypes    -- WG-FDCA + ViT + SE-based selection (no prototypes)
  baseline         -- Plain ConvNeXt-Tiny fine-tuned
"""

import os
import csv
import time
import random
import argparse

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.amp import autocast, GradScaler
from torchvision import datasets, transforms

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from timm import create_model
from timm.models.vision_transformer import Block

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(RANDOM_SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = True

TARGET_SIZE  = (224, 224)
BATCH_SIZE   = 24
EPOCHS       = 30
LR_BACKBONE  = 1e-5
LR_HEAD      = 1e-4
WEIGHT_DECAY = 0.01
DROPOUT      = 0.2
SCTR_WEIGHT  = 0.1
ORTHO_WEIGHT = 0.05
PROTO_MOM    = 0.99
PROTO_WARMUP = 5
VIT_BLOCKS   = 4
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")
RESULTS_CSV  = "ablation_results.csv"

VALID_CONDITIONS = (
    'full', 'no_dpa', 'no_pgap', 'no_wgfdca', 'no_transformer',
    'no_padts', 'no_sctr', 'fixed_pruning', 'no_prototypes', 'baseline'
)


# ── Haar DWT ────────────────────────────────────────────────────────────────
def haar_dwt_2d(x):
    x_l = (x[:, :, :, 0::2] + x[:, :, :, 1::2]) * 0.5
    x_h = (x[:, :, :, 0::2] - x[:, :, :, 1::2]) * 0.5
    ll = (x_l[:, :, 0::2, :] + x_l[:, :, 1::2, :]) * 0.5
    lh = (x_l[:, :, 0::2, :] - x_l[:, :, 1::2, :]) * 0.5
    hl = (x_h[:, :, 0::2, :] + x_h[:, :, 1::2, :]) * 0.5
    hh = (x_h[:, :, 0::2, :] - x_h[:, :, 1::2, :]) * 0.5
    return ll, lh, hl, hh


# ── CBAM ────────────────────────────────────────────────────────────────────
class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        mid = max(1, channels // reduction)
        self.fc = nn.Sequential(
            nn.Linear(channels, mid, bias=False), nn.ReLU(inplace=True),
            nn.Linear(mid, channels, bias=False))

    def forward(self, x):
        B, C = x.shape[:2]
        avg_out = self.fc(self.avg_pool(x).view(B, C))
        max_out = self.fc(self.max_pool(x).view(B, C))
        return x * torch.sigmoid(avg_out + max_out).view(B, C, 1, 1)


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False)
        self.bn = nn.BatchNorm2d(1)

    def forward(self, x):
        avg_out = x.mean(dim=1, keepdim=True)
        max_out = x.max(dim=1, keepdim=True).values
        attn = torch.sigmoid(self.bn(self.conv(torch.cat([avg_out, max_out], dim=1))))
        return x * attn


class CBAM(nn.Module):
    def __init__(self, channels, reduction=16, kernel_size=7):
        super().__init__()
        self.channel_attn = ChannelAttention(channels, reduction)
        self.spatial_attn = SpatialAttention(kernel_size)

    def forward(self, x):
        return self.spatial_attn(self.channel_attn(x))


# ── WG-FDCA (Novel Module 1) ─────────────────────────────────────────────────
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


# ── Plain cross-attention (for no_wgfdca ablation) ───────────────────────────
class PlainCrossAttention(nn.Module):
    def __init__(self, dim_low=96, dim_high=192, num_heads=4, dropout=0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim_high // num_heads
        self.scale = self.head_dim ** -0.5
        self.proj_low = nn.Sequential(
            nn.Conv2d(dim_low, dim_high, 1, bias=False), nn.BatchNorm2d(dim_high), nn.GELU())
        self.downsample_low = nn.AdaptiveAvgPool2d(28)
        self.q_proj = nn.Linear(dim_high, dim_high, bias=False)
        self.k_proj = nn.Linear(dim_high, dim_high, bias=False)
        self.v_proj = nn.Linear(dim_high, dim_high, bias=False)
        self.out_proj = nn.Linear(dim_high, dim_high)
        self.attn_drop = nn.Dropout(dropout * 0.5)
        self.proj_drop = nn.Dropout(dropout)
        self.norm_q = nn.LayerNorm(dim_high)
        self.norm_kv = nn.LayerNorm(dim_high)
        self.ffn = nn.Sequential(
            nn.Linear(dim_high, dim_high * 2), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(dim_high * 2, dim_high), nn.Dropout(dropout))
        self.norm_ffn = nn.LayerNorm(dim_high)

    def forward(self, feat_low, feat_high):
        B = feat_low.shape[0]
        kv_tokens = self.downsample_low(self.proj_low(feat_low)).flatten(2).transpose(1, 2)
        q_tokens = feat_high.flatten(2).transpose(1, 2)
        q = self.norm_q(q_tokens); kv = self.norm_kv(kv_tokens)
        Q = self.q_proj(q).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(kv).reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        attn = self.attn_drop((Q @ K.transpose(-2, -1) * self.scale).softmax(dim=-1))
        out = (attn @ V).transpose(1, 2).reshape(B, -1, self.num_heads * self.head_dim)
        out = self.proj_drop(self.out_proj(out))
        fused = q_tokens + out
        return fused + self.ffn(self.norm_ffn(fused))


# ── PA-DTS (Novel Module 2) ──────────────────────────────────────────────────
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
        off_diag = sim - eye
        return (off_diag ** 2).mean()


# ── SE-based token selection without prototypes (for no_prototypes ablation) ──
class SETokenSelection(nn.Module):
    def __init__(self, dim, min_keep=0.3, max_keep=0.8, dropout=0.0):
        super().__init__()
        self.min_keep = min_keep; self.max_keep = max_keep
        mid = max(1, dim // 16)
        self.se = nn.Sequential(nn.Linear(dim, mid), nn.GELU(), nn.Dropout(dropout),
                                nn.Linear(mid, dim), nn.Sigmoid())
        self.keep_predictor = nn.Sequential(nn.Linear(dim + 3, 32), nn.GELU(), nn.Linear(32, 1), nn.Sigmoid())
        self.norm = nn.LayerNorm(dim)

    def forward(self, x):
        B, N, C = x.shape
        x_n = self.norm(x)
        gates = self.se(x_n.mean(dim=1)).unsqueeze(1)
        out = x * gates
        scores = out.norm(dim=-1)
        scores = (scores - scores.mean(-1, keepdim=True)) / (scores.std(-1, keepdim=True) + 1e-6)
        importance = F.softmax(scores, dim=-1)
        g = self.keep_predictor(torch.cat([x.mean(1), torch.stack([importance.mean(1), importance.std(1), importance.max(1).values], -1)], -1)).squeeze(-1)
        g = self.min_keep + g * (self.max_keep - self.min_keep)
        k = torch.clamp((g.mean()*N).long(), min=max(1, int(self.min_keep*N)), max=int(self.max_keep*N)).item()
        _, idx = torch.topk(importance, k, dim=1)
        bi = torch.arange(B, device=x.device).unsqueeze(1).expand(-1, k)
        return out[bi, idx], importance


# ── Fixed-ratio SE pruning (for fixed_pruning ablation) ──────────────────────
class FixedSEPruning(nn.Module):
    def __init__(self, dim, reduction=16, dropout=0.0):
        super().__init__()
        mid = max(1, dim // reduction)
        self.se = nn.Sequential(nn.Linear(dim, mid), nn.GELU(), nn.Dropout(dropout),
                                nn.Linear(mid, dim), nn.Sigmoid())
    def forward(self, x):
        gates = self.se(x.mean(dim=1)).unsqueeze(1)
        out = x * gates
        scores = out.norm(dim=-1)
        scores = (scores - scores.mean(-1, keepdim=True)) / (scores.std(-1, keepdim=True) + 1e-6)
        return out, F.softmax(scores, dim=-1)


def select_topk(tokens, importance, k):
    B, N, C = tokens.size(); k = min(k, N)
    _, idx = torch.topk(importance, k, dim=1)
    bi = torch.arange(B, device=tokens.device).unsqueeze(1).expand(-1, k)
    return tokens[bi, idx]


# ── SCTR Loss (Novel Module 3) ───────────────────────────────────────────────
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
            supcon_loss = torch.tensor(0.0, device=embeddings.device, requires_grad=True)
        else:
            sim = sim - sim.max(1, keepdim=True).values.detach()
            exp_sim = torch.exp(sim) * self_mask.float()
            log_prob = sim - torch.log(exp_sim.sum(1, keepdim=True) + 1e-8)
            pos_count = torch.clamp(positives.float().sum(1), min=1.0)
            loss_per = -(positives.float() * log_prob).sum(1) / pos_count
            supcon_loss = loss_per[has_pos].mean()
        if prototypes is not None:
            p_norm = F.normalize(prototypes.detach(), dim=-1)
            e_norm = F.normalize(embeddings, dim=-1)
            proto_sim = e_norm @ p_norm.T / self.temperature
            alignment_loss = F.cross_entropy(proto_sim, labels)
            return supcon_loss + 0.5 * alignment_loss
        return supcon_loss


# ── Ablation model factory ───────────────────────────────────────────────────
def build_model(condition: str, num_classes: int) -> nn.Module:
    assert condition in VALID_CONDITIONS, f"Unknown: {condition}. Choose from {VALID_CONDITIONS}"

    class AblationModel(nn.Module):
        def __init__(self, condition, num_classes):
            super().__init__()
            self.condition = condition
            self.use_sctr = condition not in ('fixed_pruning', 'baseline', 'no_sctr')
            self.use_pgap = condition in ('full', 'no_dpa', 'no_wgfdca', 'no_sctr')
            self.use_dpa = condition in ('full', 'no_wgfdca', 'no_sctr')

            if condition == 'baseline':
                self.model = create_model('convnext_tiny', pretrained=True, num_classes=num_classes)
                return

            cnn = create_model('convnext_tiny', pretrained=True, num_classes=0)
            self.cnn_stem = cnn.stem
            self.cnn_stage1 = cnn.stages[0]
            self.cnn_stage2 = cnn.stages[1]
            self.cnn_stage3 = cnn.stages[2]
            self.cnn_stage4 = cnn.stages[3]

            self.cbam3 = CBAM(384, reduction=16, kernel_size=7)
            self.cbam4 = CBAM(768, reduction=16, kernel_size=7)

            has_ca = condition != 'no_transformer'
            has_vit = condition != 'no_transformer'
            use_wavelet = condition not in ('no_wgfdca',)
            use_padts = condition in ('full', 'no_dpa', 'no_pgap', 'no_wgfdca', 'no_sctr')
            use_se_selection = condition == 'no_prototypes'
            use_fixed = condition == 'fixed_pruning'

            final_dim = 768

            if has_ca:
                vit_dim = 192
                self.cross_attn = WaveletFrequencyDecomposedCrossAttention(96, 192, 4, DROPOUT) if use_wavelet else PlainCrossAttention(96, 192, 4, DROPOUT)

            if has_vit:
                vit_dim = 192
                self.pos_embed = nn.Parameter(torch.zeros(1, 28*28, vit_dim))
                nn.init.trunc_normal_(self.pos_embed, std=0.02)
                self.vit_blocks = nn.ModuleList([
                    Block(dim=vit_dim, num_heads=6, proj_drop=DROPOUT, attn_drop=DROPOUT*0.5,
                          drop_path=0.1 * (i + 1) / VIT_BLOCKS)
                    for i in range(VIT_BLOCKS)])
                # Bridge ViT (192-dim) -> CNN (768-dim) for parallel fusion
                self.vit_to_cnn_proj = nn.Sequential(
                    nn.LayerNorm(vit_dim), nn.Linear(vit_dim, final_dim), nn.GELU(), nn.Dropout(DROPOUT))

            if use_padts:
                self.token_selector = PrototypeAnchoredTokenSelection(final_dim, num_classes, 0.6, 0.95, DROPOUT*0.25)
            elif use_se_selection:
                self.token_selector = SETokenSelection(final_dim, 0.6, 0.95, DROPOUT*0.25)
            elif use_fixed:
                self.selection_sizes = [int(49*0.75), int(49*0.50)]
                self.hse_blocks = nn.ModuleList([FixedSEPruning(final_dim, 16, DROPOUT*0.25) for _ in self.selection_sizes])

            if self.use_pgap:
                # No pgap_proj: same space as prototypes
                self.pgap_norm = nn.LayerNorm(final_dim)

            if self.use_dpa:
                # No gap_proj: same space as prototypes
                self.dpa_gate = nn.Sequential(
                    nn.Linear(final_dim * 2, final_dim // 4), nn.GELU(),
                    nn.Linear(final_dim // 4, final_dim), nn.Sigmoid())

            if self.use_sctr:
                self.sctr = SupervisedContrastiveTokenLoss(final_dim, 128, 0.07)

            self.classifier = nn.Sequential(nn.LayerNorm(final_dim), nn.Dropout(DROPOUT), nn.Linear(final_dim, num_classes))

        def forward(self, x, return_embeddings=False):
            if self.condition == 'baseline':
                out = self.model(x)
                if return_embeddings:
                    return out, torch.zeros(x.shape[0], 768, device=x.device)
                return out

            has_ca = self.condition != 'no_transformer'
            has_vit = self.condition != 'no_transformer'
            use_padts = self.condition in ('full', 'no_dpa', 'no_pgap', 'no_wgfdca', 'no_sctr')
            use_se_sel = self.condition == 'no_prototypes'
            use_fixed = self.condition == 'fixed_pruning'
            use_gap = self.condition == 'no_padts'

            x = self.cnn_stem(x)
            s1 = self.cnn_stage1(x)
            s2 = self.cnn_stage2(s1)

            if has_ca:
                # ViT path (parallel)
                vit_tokens = self.cross_attn(s1, s2) + self.pos_embed
                for blk in self.vit_blocks:
                    vit_tokens = blk(vit_tokens)
                # CNN path (pretrained, preserved)
                B = s2.shape[0]
                x = self.cbam3(self.cnn_stage3(s2))
                x = self.cbam4(self.cnn_stage4(x))
                cnn_tokens = x.flatten(2).transpose(1, 2)  # (B, 49, 768)
                # Parallel fusion
                vit_proj = self.vit_to_cnn_proj(vit_tokens)
                vit_proj = vit_proj.transpose(1, 2).reshape(B, 768, 28, 28)
                vit_proj = F.adaptive_avg_pool2d(vit_proj, (7, 7)).flatten(2).transpose(1, 2)
                x = cnn_tokens + vit_proj
            else:
                x = self.cbam3(self.cnn_stage3(s2))
                x = self.cbam4(self.cnn_stage4(x))
                x = x.flatten(2).transpose(1, 2)

            if use_padts or use_se_sel:
                selected, _ = self.token_selector(x)
                if self.use_pgap:
                    pgap_tokens = self.pgap_norm(selected)
                    proto_normed = F.normalize(self.token_selector.prototypes.detach(), dim=-1)
                    query_normed = F.normalize(pgap_tokens, dim=-1)
                    diag_rel = (query_normed @ proto_normed.T).max(dim=-1).values
                    attn_w = F.softmax(diag_rel, dim=-1).unsqueeze(-1)
                    pgap_embed = (selected * attn_w).sum(dim=1)
                    if self.use_dpa:
                        gap_embed = x.mean(dim=1)
                        dpa_g = self.dpa_gate(torch.cat([pgap_embed, gap_embed], dim=-1))
                        embeddings = dpa_g * pgap_embed + (1 - dpa_g) * gap_embed
                    else:
                        embeddings = pgap_embed
                else:
                    embeddings = selected.mean(dim=1)
            elif use_fixed:
                current = x
                for hse, k in zip(self.hse_blocks, self.selection_sizes):
                    t_attn, imp = hse(current)
                    current = select_topk(t_attn, imp, k)
                embeddings = current.mean(dim=1)
            else:
                embeddings = x.mean(dim=1)

            logits = self.classifier(embeddings)
            if return_embeddings:
                return logits, embeddings
            return logits

    return AblationModel(condition, num_classes).to(DEVICE)


# ── Training & evaluation ────────────────────────────────────────────────────
def train_epoch(model, loader, criterion, optimizer, use_sctr=True, epoch=0, sctr_weight=SCTR_WEIGHT, scaler=None):
    model.train()
    total_loss, preds, targets = 0.0, [], []
    proto_mom = 0.9 if epoch < PROTO_WARMUP else PROTO_MOM
    use_amp = scaler is not None

    for imgs, tgts in tqdm(loader, desc="  train", leave=False):
        imgs, tgts = imgs.to(DEVICE, non_blocking=True), tgts.to(DEVICE, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)

        with autocast('cuda', enabled=use_amp):
            logits, emb = model(imgs, return_embeddings=True)
            ce = criterion(logits, tgts)
            loss = ce
            if use_sctr and hasattr(model, 'sctr'):
                protos = model.token_selector.prototypes if hasattr(model, 'token_selector') and hasattr(model.token_selector, 'prototypes') else None
                sctr = model.sctr(emb.float(), tgts, prototypes=protos)
                loss = loss + sctr_weight * sctr
            if hasattr(model, 'token_selector') and hasattr(model.token_selector, 'prototype_orthogonality_loss'):
                loss = loss + ORTHO_WEIGHT * model.token_selector.prototype_orthogonality_loss()

        if use_amp:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            if hasattr(model, 'token_selector') and hasattr(model.token_selector, 'update_prototypes'):
                model.token_selector.update_prototypes(emb.detach().float(), tgts, proto_mom)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            if hasattr(model, 'token_selector') and hasattr(model.token_selector, 'update_prototypes'):
                model.token_selector.update_prototypes(emb.detach(), tgts, proto_mom)
            optimizer.step()

        total_loss += loss.item()
        preds.extend(logits.argmax(1).cpu().numpy())
        targets.extend(tgts.cpu().numpy())
    return total_loss / len(loader), accuracy_score(targets, preds)


@torch.no_grad()
def evaluate(model, loader, criterion):
    model.eval()
    total_loss, preds, targets = 0.0, [], []
    use_amp = DEVICE.type == 'cuda'
    for imgs, tgts in tqdm(loader, desc="  eval ", leave=False):
        imgs, tgts = imgs.to(DEVICE, non_blocking=True), tgts.to(DEVICE, non_blocking=True)
        with autocast('cuda', enabled=use_amp):
            out = model(imgs)
            total_loss += criterion(out, tgts).item()
        preds.extend(out.argmax(1).cpu().numpy())
        targets.extend(tgts.cpu().numpy())
    y_true = np.array(targets); y_pred = np.array(preds)
    return total_loss / len(loader), accuracy_score(y_true, y_pred), y_true, y_pred


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WaveCoAtNet Ablation Study")
    parser.add_argument('--condition', choices=list(VALID_CONDITIONS) + ['all'], default='all')
    args = parser.parse_args()

    labels = {
        'full':           'WaveCoAtNet (Full)',
        'no_dpa':         'w/o DPA (PGAP only)',
        'no_pgap':        'w/o PGAP+DPA (Mean Pool)',
        'no_wgfdca':      'w/o WG-FDCA (Plain CA)',
        'no_transformer': 'w/o Transformer',
        'no_padts':       'w/o PA-DTS (GAP)',
        'no_sctr':        'w/o SCTR (CE only)',
        'fixed_pruning':  'w/ Fixed Pruning',
        'no_prototypes':  'w/o Prototypes (SE only)',
        'baseline':       'ConvNeXt-Tiny Baseline',
    }

    if args.condition == 'all':
        conditions = list(VALID_CONDITIONS)
        print(f"Running ALL {len(conditions)} ablation conditions sequentially...")
    else:
        conditions = [args.condition]

    for idx, condition in enumerate(conditions, 1):
        print(f"\n{'='*60}")
        print(f"  [{idx}/{len(conditions)}] Ablation: {labels[condition]}")
        print(f"{'='*60}")
        print(f"Device: {DEVICE} | Seed: {RANDOM_SEED}")

    from roboflow import Roboflow
    rf = Roboflow(api_key="gXuxxWEMFJ8nK73o7pN7")
    dataset = rf.workspace("hi-l9ueo").project("ich-s-7lnsj").version(1).download("folder")
    DATASET_DIR = dataset.location

    valid_path = os.path.join(DATASET_DIR, "valid")
    validation_path = os.path.join(DATASET_DIR, "validation")
    if not os.path.exists(valid_path) and os.path.exists(validation_path):
        os.rename(validation_path, valid_path)
        print(f"  Renamed 'validation' -> 'valid'")

    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(TARGET_SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(15),
        transforms.TrivialAugmentWide(), transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.2))])
    val_transform = transforms.Compose([
        transforms.Resize(TARGET_SIZE), transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])

    train_ds = datasets.ImageFolder(os.path.join(DATASET_DIR, "train"), transform=train_transform)
    val_ds   = datasets.ImageFolder(os.path.join(DATASET_DIR, "valid"), transform=val_transform)
    test_ds  = datasets.ImageFolder(os.path.join(DATASET_DIR, "test"),  transform=val_transform)

    nw = 0 if os.name == 'nt' else 4
    pin = torch.cuda.is_available()
    g = torch.Generator(); g.manual_seed(RANDOM_SEED)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=nw, pin_memory=pin, persistent_workers=nw > 0, generator=g)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin, persistent_workers=nw > 0)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin, persistent_workers=nw > 0)

    class_names = train_ds.classes
    num_classes = len(class_names)
    counts = np.bincount(train_ds.targets)
    cw = torch.tensor([len(train_ds)/(c*num_classes+1e-6) for c in counts], dtype=torch.float).to(DEVICE)

    scaler = GradScaler('cuda') if DEVICE.type == 'cuda' else None

    for idx, condition in enumerate(conditions, 1):
        print(f"\n{'='*60}")
        print(f"  [{idx}/{len(conditions)}] Training: {labels[condition]}")
        print(f"{'='*60}")

        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)
        torch.manual_seed(RANDOM_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(RANDOM_SEED)

        model = build_model(condition, num_classes)
        criterion = nn.CrossEntropyLoss(weight=cw, label_smoothing=0.1)

        backbone_params, novel_params = [], []
        for name, p in model.named_parameters():
            if not p.requires_grad:
                continue
            if any(s in name for s in ['cnn_stem', 'cnn_stage1', 'cnn_stage2', 'cnn_stage3', 'cnn_stage4', 'model.']):
                backbone_params.append(p)
            else:
                novel_params.append(p)
        optimizer = torch.optim.AdamW([
            {'params': backbone_params, 'lr': LR_BACKBONE},
            {'params': novel_params,    'lr': LR_HEAD},
        ], weight_decay=WEIGHT_DECAY)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        use_sctr = hasattr(model, 'use_sctr') and model.use_sctr
        best_val_acc = 0.0
        ckpt = f"ablation_{condition}_best.pth"
        t_start = time.time()

        for epoch in range(EPOCHS):
            tr_loss, tr_acc = train_epoch(model, train_loader, criterion, optimizer, use_sctr=use_sctr, epoch=epoch, scaler=scaler)
            vl_loss, vl_acc, _, _ = evaluate(model, val_loader, criterion)
            scheduler.step()
            if epoch % 5 == 0 or epoch == EPOCHS - 1:
                print(f"  Epoch {epoch+1:2d}/{EPOCHS} | Train {tr_acc:.4f} | Val {vl_acc:.4f}")
            if vl_acc > best_val_acc:
                best_val_acc = vl_acc
                torch.save(model.state_dict(), ckpt)

        total_time = time.time() - t_start
        model.load_state_dict(torch.load(ckpt, weights_only=True))
        _, test_acc, y_true, y_pred = evaluate(model, test_loader, criterion)
        macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        wtd_f1   = f1_score(y_true, y_pred, average='weighted', zero_division=0)
        n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

        print(f"\n--- Ablation Results: {labels[condition]} ---")
        print(f"  Test Accuracy  : {test_acc*100:.2f}%")
        print(f"  Macro F1       : {macro_f1:.4f}")
        print(f"  Weighted F1    : {wtd_f1:.4f}")
        print(f"  Parameters     : {n_params:,}")
        print(f"  Training time  : {total_time:.1f}s")
        print(classification_report(y_true, y_pred, target_names=class_names, digits=4))

        np.save(f'ablation_{condition}_y_true.npy', y_true)
        np.save(f'ablation_{condition}_y_pred.npy', y_pred)

        cm = confusion_matrix(y_true, y_pred)
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                    xticklabels=class_names, yticklabels=class_names, annot_kws={"size": 11})
        plt.title(f'Ablation: {labels[condition]}', fontsize=13, fontweight='bold')
        plt.xlabel('Predicted', fontsize=12); plt.ylabel('True', fontsize=12)
        plt.tight_layout()
        plt.savefig(f'ablation_{condition}_cm.png', dpi=300)
        plt.close()

        row = {
            'condition': labels[condition],
            'test_accuracy': round(test_acc*100, 2),
            'macro_f1': round(macro_f1, 4),
            'weighted_f1': round(wtd_f1, 4),
            'n_params': n_params,
            'train_time_s': round(total_time, 1),
        }
        file_exists = os.path.exists(RESULTS_CSV)
        with open(RESULTS_CSV, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"Results appended to {RESULTS_CSV}")

        del model, optimizer, scheduler, criterion
        torch.cuda.empty_cache()

    print(f"\n{'='*60}")
    print(f"  ALL {len(conditions)} ABLATION CONDITIONS COMPLETE")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
