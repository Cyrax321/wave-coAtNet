"""
WaveCoAtNet: Wavelet-enhanced Convolutional Attention Network
             with Frequency-Decomposed Cross-Attention,
             Prototype-Anchored Token Selection, and
             Supervised Contrastive Token Regularization
==============================================================================
Proposed method for ichthyosis subtype classification.

Novel contributions:
  1. Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA) --
     Decomposes stage1 CNN features via 2D Haar DWT into structure (LL) and
     texture (LH+HL+HH) sub-bands, then performs frequency-selective cross-
     attention from stage2 queries with a learned per-token frequency gate.

  2. Prototype-Anchored Dynamic Token Selection (PA-DTS) --
     Selects diagnostically relevant tokens by scoring them against learnable
     class prototypes (updated via EMA). Uses a learnable prototype
     temperature for adaptive similarity sharpness. Combines prototype
     affinity, affinity entropy, and channel attention for importance
     ranking with adaptive keep-ratio prediction.

  3. Supervised Contrastive Token Regularization (SCTR) --
     Auxiliary SupCon loss on mean-pooled token embeddings that forces same-
     class representations to cluster and different-class to separate,
     improving inter-class discriminability for rare subtypes.

  4. Prototype-Guided Attention Pooling (PGAP) --
     Replaces naive mean-pooling with prototype-affinity-weighted
     aggregation of selected tokens, sharpening classifier focus on
     diagnostically relevant evidence.

  5. Dual-Path Aggregation (DPA) --
     Combines the selective pathway (PA-DTS + PGAP) with a holistic global
     average pooling pathway through a learned content-dependent gate.
     Ensures diagnostic information is preserved even when token selection
     is aggressive or prototype attention is immature during early training.

  6. CBAM (Convolutional Block Attention Module) --
     Channel and spatial attention applied after deep CNN stages (stage3,
     stage4) to recalibrate feature responses. Channel attention highlights
     informative feature channels while spatial attention focuses on
     discriminative spatial regions (e.g. lesion boundaries, scale patterns).
"""

import os
import time
import random

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.amp import autocast, GradScaler
from torchvision import datasets, transforms

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from torchinfo import summary
from sklearn.metrics import classification_report, confusion_matrix
from roboflow import Roboflow
from timm import create_model
from timm.models.vision_transformer import Block

# ===========================
# Reproducibility
# ===========================
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
torch.manual_seed(RANDOM_SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(RANDOM_SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = True

# ===========================
# Configuration
# ===========================
API_KEY = "gXuxxWEMFJ8nK73o7pN7"
TARGET_SIZE = (224, 224)
BATCH_SIZE = 24
EPOCHS = 50
LR_BACKBONE = 1e-5          # lower LR for pretrained ConvNeXt stages (matches baselines)
LR_HEAD = 2e-4              # higher LR for novel modules + classifier
WEIGHT_DECAY = 0.01
DROPOUT = 0.2
SCTR_WEIGHT = 0.1           # weight for contrastive loss term
PROTO_MOMENTUM = 0.99       # EMA momentum for prototype tracking
ORTHO_WEIGHT = 0.05         # weight for cross-prototype orthogonality loss
PROTO_WARMUP_EPOCHS = 5     # epochs with fast prototype adaptation (momentum=0.9)
FREEZE_BACKBONE_EPOCHS = 5  # freeze backbone for first N epochs to warm up novel modules
WARMUP_EPOCHS = 5           # LR warmup epochs
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ===========================
# Utility: 2D Haar Discrete Wavelet Transform
# ===========================
def haar_dwt_2d(x: torch.Tensor):
    """
    Apply 2D Haar Discrete Wavelet Transform to feature maps.

    Args:
        x: (B, C, H, W) with H and W even

    Returns:
        ll, lh, hl, hh: each (B, C, H/2, W/2)
    """
    x_l = (x[:, :, :, 0::2] + x[:, :, :, 1::2]) * 0.5
    x_h = (x[:, :, :, 0::2] - x[:, :, :, 1::2]) * 0.5
    ll = (x_l[:, :, 0::2, :] + x_l[:, :, 1::2, :]) * 0.5
    lh = (x_l[:, :, 0::2, :] - x_l[:, :, 1::2, :]) * 0.5
    hl = (x_h[:, :, 0::2, :] + x_h[:, :, 1::2, :]) * 0.5
    hh = (x_h[:, :, 0::2, :] - x_h[:, :, 1::2, :]) * 0.5
    return ll, lh, hl, hh


# ===========================
# Novel Module 6: CBAM (Convolutional Block Attention Module)
# ===========================
class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        mid = max(1, channels // reduction)
        self.fc = nn.Sequential(
            nn.Linear(channels, mid, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(mid, channels, bias=False),
        )

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
    """
    Convolutional Block Attention Module.

    Sequentially applies channel attention (which features are important)
    and spatial attention (where those features are important). Applied
    after deep CNN stages to recalibrate features before tokenization.

    Args:
        channels:  Number of input channels
        reduction: Channel attention bottleneck reduction ratio
        kernel_size: Spatial attention convolution kernel size
    """
    def __init__(self, channels, reduction=16, kernel_size=7):
        super().__init__()
        self.channel_attn = ChannelAttention(channels, reduction)
        self.spatial_attn = SpatialAttention(kernel_size)

    def forward(self, x):
        x = self.channel_attn(x)
        x = self.spatial_attn(x)
        return x


# ===========================
# Novel Module 1: Wavelet-Guided Frequency-Decomposed Cross-Attention
# ===========================
class WaveletFrequencyDecomposedCrossAttention(nn.Module):
    """
    Frequency-selective cross-attention between CNN stages via wavelet
    decomposition.

    Stage1 features are decomposed via 2D Haar DWT into:
      - Low-frequency stream (LL sub-band): captures structural patterns
        like plate-like fissures in Harlequin Ichthyosis
      - High-frequency stream (LH+HL+HH): captures fine texture details
        like fish-scale patterns in Ichthyosis Vulgaris

    Stage2 features serve as queries. Two separate cross-attention operations
    attend to the low-freq and high-freq key/value streams. A learnable
    per-token frequency gate dynamically balances structure vs texture
    based on image content.

    Args:
        dim_low:   Channel dimension of stage1 output (96 for ConvNeXt-Tiny)
        dim_high:  Channel dimension of stage2 output (192 for ConvNeXt-Tiny)
        num_heads: Number of attention heads per stream
        dropout:   Dropout rate
    """
    def __init__(self, dim_low: int = 96, dim_high: int = 192,
                 num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim_high // num_heads
        self.scale = self.head_dim ** -0.5

        self.proj_low_freq = nn.Sequential(
            nn.Conv2d(dim_low, dim_high, kernel_size=1, bias=False),
            nn.BatchNorm2d(dim_high),
            nn.GELU(),
        )
        self.proj_high_freq = nn.Sequential(
            nn.Conv2d(dim_low * 3, dim_high, kernel_size=1, bias=False),
            nn.BatchNorm2d(dim_high),
            nn.GELU(),
        )

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
            nn.Linear(dim_high * 2, dim_high // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_high // 4, 1),
            nn.Sigmoid(),
        )

        self.ffn = nn.Sequential(
            nn.Linear(dim_high, dim_high * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_high * 2, dim_high),
            nn.Dropout(dropout),
        )
        self.norm_ffn = nn.LayerNorm(dim_high)

    def _cross_attend(self, q_tokens, kv_tokens, k_proj, v_proj, out_proj, norm_kv):
        B, N = q_tokens.shape[:2]
        kv = norm_kv(kv_tokens)

        Q = self.q_proj(self.norm_q(q_tokens))
        K = k_proj(kv)
        V = v_proj(kv)

        Q = Q.reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.reshape(B, -1, self.num_heads, self.head_dim).transpose(1, 2)

        attn = (Q @ K.transpose(-2, -1)) * self.scale
        attn = self.attn_drop(attn.softmax(dim=-1))

        out = (attn @ V).transpose(1, 2).reshape(B, -1, self.num_heads * self.head_dim)
        return self.proj_drop(out_proj(out))

    def forward(self, feat_low: torch.Tensor, feat_high: torch.Tensor) -> torch.Tensor:
        ll, lh, hl, hh = haar_dwt_2d(feat_low)

        low_feat = self.proj_low_freq(ll)
        high_feat = self.proj_high_freq(torch.cat([lh, hl, hh], dim=1))

        low_tokens = low_feat.flatten(2).transpose(1, 2)
        high_tokens = high_feat.flatten(2).transpose(1, 2)
        q_tokens = feat_high.flatten(2).transpose(1, 2)

        low_out = self._cross_attend(q_tokens, low_tokens,
                                     self.k_proj_low, self.v_proj_low,
                                     self.out_proj_low, self.norm_kv_low)
        high_out = self._cross_attend(q_tokens, high_tokens,
                                      self.k_proj_high, self.v_proj_high,
                                      self.out_proj_high, self.norm_kv_high)

        gate_input = torch.cat([low_out, high_out], dim=-1)
        gate = self.freq_gate(gate_input)

        fused_ca = gate * high_out + (1 - gate) * low_out

        fused = q_tokens + fused_ca
        fused = fused + self.ffn(self.norm_ffn(fused))

        return fused


# ===========================
# Novel Module 2: Prototype-Anchored Dynamic Token Selection
# ===========================
class PrototypeAnchoredTokenSelection(nn.Module):
    """
    Selects diagnostically relevant tokens by scoring them against learnable
    class prototypes that are updated via exponential moving average.

    Token importance is a learned combination of three signals:
      1. Prototype affinity -- cosine similarity to nearest class prototype
      2. Affinity entropy -- entropy of similarity distribution
      3. Channel attention -- SE-style global channel scoring

    Args:
        dim:         Token embedding dimension
        num_classes: Number of disease classes
        min_keep:    Minimum fraction of tokens to retain
        max_keep:    Maximum fraction of tokens to retain
        dropout:     Dropout rate
    """
    def __init__(self, dim: int, num_classes: int = 5,
                 min_keep: float = 0.6, max_keep: float = 0.95,
                 dropout: float = 0.0):
        super().__init__()
        self.dim = dim
        self.num_classes = num_classes
        self.min_keep = min_keep
        self.max_keep = max_keep

        self.register_buffer('prototypes', torch.randn(num_classes, dim) * 0.02)
        self.proto_temperature = nn.Parameter(torch.tensor(1.0))

        mid = max(1, dim // 16)
        self.channel_scorer = nn.Sequential(
            nn.Linear(dim, mid), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(mid, 1),
        )

        self.importance_weights = nn.Parameter(torch.tensor([1.0, 0.5, 0.5]))

        self.keep_predictor = nn.Sequential(
            nn.Linear(dim + 3, 32),
            nn.GELU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

        self.norm = nn.LayerNorm(dim)

    def forward(self, x: torch.Tensor):
        B, N, C = x.shape
        x_normed = self.norm(x)

        prototypes_normed = F.normalize(self.prototypes, dim=-1)
        tokens_normed = F.normalize(x_normed, dim=-1)
        similarity = tokens_normed @ prototypes_normed.T
        proto_affinity = similarity.max(dim=-1).values

        proto_probs = F.softmax(similarity / self.proto_temperature.clamp(min=0.01), dim=-1)
        proto_entropy = -(proto_probs * (proto_probs + 1e-8).log()).sum(dim=-1)

        channel_score = self.channel_scorer(x_normed).squeeze(-1)

        def _znorm(s):
            s = s - s.mean(dim=-1, keepdim=True)
            return s / (s.std(dim=-1, keepdim=True) + 1e-6)

        proto_affinity_n = _znorm(proto_affinity)
        proto_entropy_n = _znorm(proto_entropy)
        channel_score_n = _znorm(channel_score)

        w = F.softmax(self.importance_weights, dim=0)
        combined = (w[0] * proto_affinity_n +
                    w[1] * proto_entropy_n +
                    w[2] * channel_score_n)
        importance = F.softmax(combined, dim=-1)

        global_feat = x.mean(dim=1)
        imp_stats = torch.stack([
            importance.mean(dim=1),
            importance.std(dim=1),
            importance.max(dim=1).values,
        ], dim=-1)
        keep_ratio = self.keep_predictor(
            torch.cat([global_feat, imp_stats], dim=-1)).squeeze(-1)
        keep_ratio = self.min_keep + keep_ratio * (self.max_keep - self.min_keep)

        k_val = torch.clamp(
            (keep_ratio * N).long(),
            min=max(1, int(self.min_keep * N)),
            max=int(self.max_keep * N)
        )[0].item()

        _, top_k_idx = torch.topk(importance, k_val, dim=1)
        batch_idx = torch.arange(B, device=x.device).unsqueeze(1).expand(-1, k_val)
        selected = x[batch_idx, top_k_idx]

        sel_importance = importance[batch_idx, top_k_idx].unsqueeze(-1)
        selected = selected * (1.0 + sel_importance)

        return selected, importance

    @torch.no_grad()
    def update_prototypes(self, embeddings: torch.Tensor, labels: torch.Tensor,
                          momentum: float = 0.99):
        for c in range(self.num_classes):
            mask = labels == c
            if mask.sum() > 0:
                class_mean = embeddings[mask].mean(dim=0)
                self.prototypes[c] = (momentum * self.prototypes[c] +
                                      (1.0 - momentum) * class_mean)

    def prototype_orthogonality_loss(self) -> torch.Tensor:
        p_norm = F.normalize(self.prototypes, dim=-1)
        sim = p_norm @ p_norm.T
        eye = torch.eye(self.num_classes, device=sim.device)
        off_diag = sim - eye
        return (off_diag ** 2).mean()


# ===========================
# Novel Module 3: Supervised Contrastive Token Regularization
# ===========================
class SupervisedContrastiveTokenLoss(nn.Module):
    """
    Supervised contrastive loss applied to mean-pooled token embeddings.

    Args:
        embed_dim:   Dimension of input embeddings
        proj_dim:    Dimension of contrastive projection space
        temperature: Softmax temperature for similarity scaling
    """
    def __init__(self, embed_dim: int, proj_dim: int = 128,
                 temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature
        self.projector = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Linear(embed_dim, proj_dim),
        )

    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor,
                prototypes: torch.Tensor = None) -> torch.Tensor:
        B = embeddings.shape[0]
        if B < 2:
            return torch.tensor(0.0, device=embeddings.device, requires_grad=True)

        z = F.normalize(self.projector(embeddings), dim=-1)

        sim = z @ z.T / self.temperature

        label_eq = labels.unsqueeze(0) == labels.unsqueeze(1)
        self_mask = ~torch.eye(B, dtype=torch.bool, device=z.device)
        positives = label_eq & self_mask

        has_pos = positives.float().sum(dim=1) > 0
        if has_pos.sum() == 0:
            supcon_loss = torch.tensor(0.0, device=embeddings.device, requires_grad=True)
        else:
            sim_max = sim.max(dim=1, keepdim=True).values.detach()
            sim = sim - sim_max

            exp_sim = torch.exp(sim) * self_mask.float()
            log_prob = sim - torch.log(exp_sim.sum(dim=1, keepdim=True) + 1e-8)

            pos_count = torch.clamp(positives.float().sum(dim=1), min=1.0)
            loss_per_sample = -(positives.float() * log_prob).sum(dim=1) / pos_count
            supcon_loss = loss_per_sample[has_pos].mean()

        if prototypes is not None:
            p_norm = F.normalize(prototypes.detach(), dim=-1)
            e_norm = F.normalize(embeddings, dim=-1)
            proto_sim = e_norm @ p_norm.T / self.temperature
            alignment_loss = F.cross_entropy(proto_sim, labels)
            return supcon_loss + 0.5 * alignment_loss

        return supcon_loss


# ===========================
# WaveCoAtNet Model
# ===========================
class WaveCoAtNet(nn.Module):
    """
    WaveCoAtNet: Wavelet-enhanced Convolutional Attention Network
    for ichthyosis classification.

    Architecture:
      1. ConvNeXt-Tiny stem + stages 1-2 (local feature extraction)
      2. WG-FDCA -- wavelet-decomposed frequency-selective cross-attention
      3. Positional embedding + ViT transformer blocks (global context)
      4. ConvNeXt stages 3-4 + CBAM (deep semantic features with attention)
      5. PA-DTS -- prototype-anchored adaptive token selection
      6. PGAP -- prototype-guided attention pooling on selected tokens
      7. DPA -- dual-path aggregation blending selective + holistic paths
      8. LayerNorm -> Linear classifier
      9. SCTR -- auxiliary contrastive loss on embeddings (training only)

    ConvNeXt-Tiny channel progression: 96 -> 192 -> 384 -> 768
    """
    def __init__(
        self,
        base_model: str = 'convnext_tiny',
        num_classes: int = 5,
        vit_blocks: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()

        cnn_backbone = create_model(base_model, pretrained=True, num_classes=0)
        self.cnn_stem   = cnn_backbone.stem
        self.cnn_stage1 = cnn_backbone.stages[0]
        self.cnn_stage2 = cnn_backbone.stages[1]
        self.cnn_stage3 = cnn_backbone.stages[2]
        self.cnn_stage4 = cnn_backbone.stages[3]

        # Novel Module 6: CBAM after deep stages for feature recalibration
        self.cbam3 = CBAM(384, reduction=16, kernel_size=7)
        self.cbam4 = CBAM(768, reduction=16, kernel_size=7)

        vit_dim = 192

        # Novel Module 1: Wavelet-Guided Frequency-Decomposed Cross-Attention
        self.wg_fdca = WaveletFrequencyDecomposedCrossAttention(
            dim_low=96, dim_high=192, num_heads=4, dropout=dropout
        )

        # ViT blocks for global context modelling
        num_vit_tokens = 28 * 28
        self.pos_embed = nn.Parameter(torch.zeros(1, num_vit_tokens, vit_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        self.vit_blocks = nn.ModuleList([
            Block(dim=vit_dim, num_heads=6,
                  proj_drop=dropout, attn_drop=dropout * 0.5,
                  drop_path=0.2 * (i + 1) / vit_blocks)
            for i in range(vit_blocks)
        ])

        # Novel Module 2: Prototype-Anchored Dynamic Token Selection
        final_embed_dim = 768
        self.pa_dts = PrototypeAnchoredTokenSelection(
            dim=final_embed_dim, num_classes=num_classes,
            min_keep=0.6, max_keep=0.95, dropout=dropout * 0.25
        )

        # Novel Module 3: Supervised Contrastive Token Regularization
        self.sctr = SupervisedContrastiveTokenLoss(
            embed_dim=final_embed_dim, proj_dim=128, temperature=0.07
        )

        # Novel Module 4: Prototype-Guided Attention Pooling (PGAP)
        self.pgap_proj = nn.Linear(final_embed_dim, final_embed_dim)
        self.pgap_norm = nn.LayerNorm(final_embed_dim)

        # Novel Module 5: Dual-Path Aggregation (DPA)
        self.gap_proj = nn.Linear(final_embed_dim, final_embed_dim)
        self.dpa_gate = nn.Sequential(
            nn.Linear(final_embed_dim * 2, final_embed_dim // 4),
            nn.GELU(),
            nn.Linear(final_embed_dim // 4, final_embed_dim),
            nn.Sigmoid(),
        )

        self.num_vit_blocks = vit_blocks

        # Classification head
        self.classifier = nn.Sequential(
            nn.LayerNorm(final_embed_dim),
            nn.Dropout(dropout),
            nn.Linear(final_embed_dim, num_classes),
        )

    def forward(self, x: torch.Tensor,
                return_embeddings: bool = False) -> torch.Tensor:
        x = self.cnn_stem(x)
        feat_stage1 = self.cnn_stage1(x)
        feat_stage2 = self.cnn_stage2(feat_stage1)

        # WG-FDCA: wavelet-guided cross-attention fusion
        fused_tokens = self.wg_fdca(feat_stage1, feat_stage2)

        # ViT global context
        fused_tokens = fused_tokens + self.pos_embed
        for blk in self.vit_blocks:
            fused_tokens = blk(fused_tokens)

        # Reshape back to spatial and pass through deep CNN stages + CBAM
        B = fused_tokens.shape[0]
        x = fused_tokens.transpose(1, 2).reshape(B, 192, 28, 28)
        x = self.cbam3(self.cnn_stage3(x))
        x = self.cbam4(self.cnn_stage4(x))

        # Tokenize final features
        x = x.flatten(2).transpose(1, 2)

        # PA-DTS: prototype-anchored token selection
        selected, _ = self.pa_dts(x)

        # PGAP: Prototype-Guided Attention Pooling
        pgap_tokens = self.pgap_norm(selected)
        pgap_queries = self.pgap_proj(pgap_tokens)
        proto_normed = F.normalize(self.pa_dts.prototypes.detach(), dim=-1)
        query_normed = F.normalize(pgap_queries, dim=-1)
        proto_affinity = query_normed @ proto_normed.T
        diag_relevance = proto_affinity.max(dim=-1).values
        attn_weights = F.softmax(diag_relevance, dim=-1).unsqueeze(-1)
        pgap_embed = (selected * attn_weights).sum(dim=1)

        # DPA: Dual-Path Aggregation
        gap_embed = self.gap_proj(x.mean(dim=1))
        dpa_g = self.dpa_gate(torch.cat([pgap_embed, gap_embed], dim=-1))
        embeddings = dpa_g * pgap_embed + (1 - dpa_g) * gap_embed

        logits = self.classifier(embeddings)

        if return_embeddings:
            return logits, embeddings
        return logits


# ===========================
# Training & Evaluation Utilities
# ===========================
def train_epoch(model, loader, criterion, optimizer, epoch=0, sctr_weight=SCTR_WEIGHT, scaler=None):
    """Train one epoch with combined CE + SCTR loss and prototype updates."""
    model.train()
    total_loss, total_ce, total_sctr = 0.0, 0.0, 0.0
    all_preds, all_targets = [], []

    proto_mom = 0.9 if epoch < PROTO_WARMUP_EPOCHS else PROTO_MOMENTUM
    use_amp = scaler is not None

    for images, targets in tqdm(loader, desc="Training", leave=False):
        images, targets = images.to(DEVICE, non_blocking=True), targets.to(DEVICE, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)

        with autocast('cuda', enabled=use_amp):
            logits, embeddings = model(images, return_embeddings=True)
            ce_loss = criterion(logits, targets)
            sctr_loss = model.sctr(embeddings.float(), targets, model.pa_dts.prototypes)
            ortho_loss = model.pa_dts.prototype_orthogonality_loss()
            loss = ce_loss + sctr_weight * sctr_loss + ORTHO_WEIGHT * ortho_loss

        if use_amp:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            model.pa_dts.update_prototypes(embeddings.detach().float(), targets, momentum=proto_mom)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            model.pa_dts.update_prototypes(embeddings.detach(), targets, momentum=proto_mom)
            optimizer.step()

        total_loss += loss.item()
        total_ce += ce_loss.item()
        total_sctr += sctr_loss.item()
        _, predicted = logits.max(1)
        all_preds.extend(predicted.cpu().numpy())
        all_targets.extend(targets.cpu().numpy())

    n = len(loader)
    avg_loss = total_loss / n if n > 0 else 0.0
    accuracy = (np.array(all_preds) == np.array(all_targets)).mean() if all_preds else 0.0
    return avg_loss, accuracy


def evaluate(model, loader, criterion, desc="Evaluating"):
    """Evaluate model on a data loader."""
    model.eval()
    total_loss, all_preds, all_targets = 0.0, [], []
    use_amp = DEVICE.type == 'cuda'
    with torch.no_grad():
        for images, targets in tqdm(loader, desc=desc, leave=False):
            images, targets = images.to(DEVICE, non_blocking=True), targets.to(DEVICE, non_blocking=True)
            with autocast('cuda', enabled=use_amp):
                outputs = model(images)
                loss = criterion(outputs, targets)
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(targets.cpu().numpy())
    avg_loss = total_loss / len(loader) if len(loader) > 0 else 0.0
    accuracy = (np.array(all_preds) == np.array(all_targets)).mean() if all_preds else 0.0
    return avg_loss, accuracy, all_targets, all_preds


def plot_curves(history: dict, out_dir: str = "."):
    """Plot training/validation/test curves."""
    for metric in ['loss', 'acc']:
        plt.figure(figsize=(10, 6))
        plt.plot(history[f'train_{metric}'], label=f'Train {metric.capitalize()}')
        plt.plot(history[f'val_{metric}'],   label=f'Validation {metric.capitalize()}')
        plt.plot(history[f'test_{metric}'],  label=f'Test {metric.capitalize()}', linestyle='--')
        plt.title(f'WaveCoAtNet {metric.capitalize()} Over Epochs')
        plt.xlabel('Epoch')
        plt.ylabel(metric.capitalize())
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f'wavecoatnet_{metric}_curves.png'), dpi=300)
        plt.close()


# ===========================
# Main Training Logic
# ===========================
def main():
    print(f"Using device: {DEVICE}")
    print(f"Random seed: {RANDOM_SEED}")

    if not API_KEY:
        raise EnvironmentError(
            "ROBOFLOW_API_KEY environment variable is not set. "
            "Run: export ROBOFLOW_API_KEY=<your_key>"
        )

    print("Downloading dataset from Roboflow...")
    rf = Roboflow(api_key=API_KEY)
    project = rf.workspace("hi-l9ueo").project("ich-s-7lnsj")
    dataset = project.version(1).download("folder")
    DATASET_DIR = dataset.location

    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(TARGET_SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.TrivialAugmentWide(),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.2)),
    ])
    val_test_transform = transforms.Compose([
        transforms.Resize(TARGET_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_dataset      = datasets.ImageFolder(os.path.join(DATASET_DIR, "train"), transform=train_transform)
    validation_dataset = datasets.ImageFolder(os.path.join(DATASET_DIR, "valid"), transform=val_test_transform)
    test_dataset       = datasets.ImageFolder(os.path.join(DATASET_DIR, "test"),  transform=val_test_transform)

    num_workers = 0 if os.name == 'nt' else 4
    pin = torch.cuda.is_available()
    g = torch.Generator()
    g.manual_seed(RANDOM_SEED)

    train_loader      = DataLoader(train_dataset,      batch_size=BATCH_SIZE, shuffle=True,  num_workers=num_workers, pin_memory=pin, persistent_workers=num_workers > 0, generator=g)
    validation_loader = DataLoader(validation_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=num_workers, pin_memory=pin, persistent_workers=num_workers > 0)
    test_loader       = DataLoader(test_dataset,       batch_size=BATCH_SIZE, shuffle=False, num_workers=num_workers, pin_memory=pin, persistent_workers=num_workers > 0)

    class_names = train_dataset.classes
    num_classes = len(class_names)
    print(f"Found {num_classes} classes: {class_names}")

    counts = np.bincount(train_dataset.targets)
    class_weights = torch.tensor(
        [len(train_dataset) / (c * num_classes + 1e-6) for c in counts],
        dtype=torch.float
    ).to(DEVICE)
    print("Class weights:", class_weights.cpu().numpy().round(4))

    model     = WaveCoAtNet(num_classes=num_classes, dropout=DROPOUT, vit_blocks=4).to(DEVICE)
    criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.1)

    # Layer-wise LR: pretrained backbone gets lower LR, novel modules get higher LR
    # This matches the training protocol used by all pretrained baselines.
    backbone_params = []
    novel_params = []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if any(s in name for s in ['cnn_stem', 'cnn_stage1', 'cnn_stage2', 'cnn_stage3', 'cnn_stage4']):
            backbone_params.append(p)
        else:
            novel_params.append(p)
    print(f"Param groups: backbone={sum(p.numel() for p in backbone_params):,}, "
          f"novel={sum(p.numel() for p in novel_params):,}")

    optimizer = torch.optim.AdamW([
        {'params': backbone_params, 'lr': LR_BACKBONE},
        {'params': novel_params,    'lr': LR_HEAD},
    ], weight_decay=WEIGHT_DECAY)

    # Warmup + Cosine LR schedule
    warmup_sched = torch.optim.lr_scheduler.LinearLR(
        optimizer, start_factor=0.01, total_iters=WARMUP_EPOCHS)
    cosine_sched = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=EPOCHS - WARMUP_EPOCHS)
    scheduler = torch.optim.lr_scheduler.SequentialLR(
        optimizer, [warmup_sched, cosine_sched], milestones=[WARMUP_EPOCHS])

    try:
        print("\n--- Model Summary ---")
        summary(model, input_size=(BATCH_SIZE, 3, *TARGET_SIZE))
    except Exception as e:
        print(f"Model summary unavailable: {e}")

    scaler = GradScaler('cuda') if DEVICE.type == 'cuda' else None

    history = {k: [] for k in ['train_loss', 'train_acc', 'val_loss', 'val_acc', 'test_loss', 'test_acc']}
    epoch_times = []
    best_val_acc = 0.0

    for epoch in range(EPOCHS):
        print(f"\n--- Epoch {epoch + 1}/{EPOCHS} ---")
        t0 = time.time()

        # Backbone freezing: freeze for first N epochs to let novel modules warm up
        if epoch == 0:
            print(f"  [Backbone FROZEN for first {FREEZE_BACKBONE_EPOCHS} epochs]")
            for p in backbone_params:
                p.requires_grad = False
        elif epoch == FREEZE_BACKBONE_EPOCHS:
            print(f"  [Backbone UNFROZEN]")
            for p in backbone_params:
                p.requires_grad = True

        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, epoch=epoch, scaler=scaler)
        val_loss,  val_acc,  _, _ = evaluate(model, validation_loader, criterion, "Validating")
        test_loss, test_acc, _, _ = evaluate(model, test_loader,       criterion, "Testing")
        scheduler.step()

        elapsed = time.time() - t0
        epoch_times.append(elapsed)

        history['train_loss'].append(train_loss);  history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss);      history['val_acc'].append(val_acc)
        history['test_loss'].append(test_loss);    history['test_acc'].append(test_acc)

        print(f"  Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f} | Test Acc: {test_acc:.4f}")
        print(f"  Losses -- Train: {train_loss:.4f} | Val: {val_loss:.4f} | Test: {test_loss:.4f}")
        print(f"  Epoch time: {elapsed:.1f}s | LR: {scheduler.get_last_lr()[0]:.2e}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), 'best_wavecoatnet.pth')
            print(f"  New best model saved (Val Acc = {best_val_acc:.4f})")

    avg_epoch_time = np.mean(epoch_times)
    print(f"\nAverage epoch time: {avg_epoch_time:.1f}s")

    print("\n--- Final Evaluation (Best Checkpoint) ---")
    model.load_state_dict(torch.load('best_wavecoatnet.pth', weights_only=True))
    _, final_test_acc, y_true, y_pred = evaluate(model, test_loader, criterion, "Final Test")
    print(f"Final Test Accuracy: {final_test_acc * 100:.2f}%")

    np.save('wavecoatnet_y_true.npy', np.array(y_true))
    np.save('wavecoatnet_y_pred.npy', np.array(y_pred))
    print("Predictions saved to wavecoatnet_y_true.npy and wavecoatnet_y_pred.npy")

    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=class_names, digits=4))

    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(12, 10))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=class_names, yticklabels=class_names,
        annot_kws={"size": 12}
    )
    plt.xlabel('Predicted Label', fontsize=13)
    plt.ylabel('True Label', fontsize=13)
    plt.title('Confusion Matrix -- WaveCoAtNet', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('confusion_matrix_wavecoatnet.png', dpi=300)
    plt.close()

    plot_curves(history)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print("\n--- Hyperparameter Summary ---")
    print(f"  Architecture     : WaveCoAtNet (ConvNeXt-Tiny + WG-FDCA + {model.num_vit_blocks} ViT + CBAM + PA-DTS + PGAP + DPA + SCTR)")
    print(f"  Backbone         : convnext_tiny (pretrained=True, ImageNet-1k)")
    print(f"  Input resolution : {TARGET_SIZE[0]}x{TARGET_SIZE[1]}")
    print(f"  Batch size       : {BATCH_SIZE}")
    print(f"  Epochs           : {EPOCHS}")
    print(f"  Optimiser        : AdamW (backbone_lr={LR_BACKBONE}, head_lr={LR_HEAD}, weight_decay={WEIGHT_DECAY})")
    print(f"  LR schedule      : LinearWarmup({WARMUP_EPOCHS}ep) + CosineAnnealing")
    print(f"  Backbone freeze  : first {FREEZE_BACKBONE_EPOCHS} epochs")
    print(f"  Proto warmup     : {PROTO_WARMUP_EPOCHS} epochs at momentum=0.9, then {PROTO_MOMENTUM}")
    print(f"  Loss             : CE(label_smoothing=0.1, class_weights) + {SCTR_WEIGHT}*SupCon(T=0.07)")
    print(f"  Dropout          : {DROPOUT}")
    print(f"  Prototype EMA    : momentum={PROTO_MOMENTUM}")
    print(f"  Random seed      : {RANDOM_SEED}")
    print(f"  Trainable params : {n_params:,}")
    print(f"  Avg epoch time   : {avg_epoch_time:.1f}s  (device: {DEVICE})")


if __name__ == '__main__':
    main()
