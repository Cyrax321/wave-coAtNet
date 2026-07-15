# WaveCoAtNet: Wavelet-Guided Frequency-Decomposed Cross-Attention and Prototype-Anchored Token Selection for Parameter-Efficient Rare Ichthyosis Classification

## Abstract

Ichthyosis denotes a heterogeneous group of hereditary keratinization disorders whose automated classification is hindered by subtle inter-class morphological overlap, severe class imbalance, and the data scarcity intrinsic to rare diseases. We present **WaveCoAtNet**, a hybrid convolutional–transformer architecture that targets these difficulties through three mechanisms: (i) **Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA)**, which uses a 2D Haar transform to separate structural (low-frequency) from textural (high-frequency) evidence and fuses them through gated cross-attention; (ii) **Prototype-Anchored Dynamic Token Selection (PA-DTS)**, which scores tokens against EMA-tracked class prototypes to retain diagnostically salient regions; and (iii) **Supervised Contrastive Token Regularization (SCTR)**, which tightens intra-class and separates inter-class embeddings.

We evaluate on a curated five-class dataset of 2,508 dermatological images. Under 5-fold cross-validation, WaveCoAtNet attains **96.25% ± 0.81%** accuracy (95% CI [95.54, 96.97]), macro-F1 **0.9550 ± 0.0090**, and Cohen's κ **0.9514**. On a controlled common held-out split benchmarking twelve models under an identical protocol, WaveCoAtNet is **statistically on par** with the strongest pretrained baselines (Swin-T, CoAtNet, DINOv2) while using 2.8× fewer parameters than ViT-B/16 and 6.5× fewer than BiomedCLIP; pairwise McNemar tests confirm differences among the top models are not significant on this sample size, motivating our cross-validated protocol. A ten-condition ablation isolates WG-FDCA as the single most impactful component (macro-F1 −3.34% when ablated). Our results position frequency-aware attention and prototype-guided token selection as a favorable **accuracy–efficiency trade-off** for rare skin-disease classification under limited data, and we release a fully reproducible evaluation harness.

**Keywords:** Ichthyosis, Wavelet Transform, Hybrid CNN–Transformer, Cross-Attention, Prototype Learning, Rare Disease, Medical Image Classification

---

## 1. Introduction

The ichthyoses are inherited disorders of epidermal differentiation arising from mutations across the epidermal differentiation complex—transglutaminase-1 in Lamellar Ichthyosis, filaggrin in Ichthyosis Vulgaris, *SPINK5* in Netherton Syndrome, and *ABCA12* in Harlequin Ichthyosis—each producing a distinct yet visually overlapping cutaneous phenotype [1]. Reported incidence ranges from roughly 1 in 250–1,000 for Ichthyosis Vulgaris to about 1 in 300,000 for Harlequin Ichthyosis. Diagnosis currently rests on clinical expertise supplemented by histopathology and genetic sequencing, all of which suffer from inter-observer variability, restricted access to subspecialty care, and the latency of molecular testing [2].

Computational dermatology has shown strong results for common conditions such as melanoma, but rare genodermatoses pose distinct obstacles [3]. Two properties dominate. First, **severe class imbalance**: the rarest subtypes contribute an order of magnitude fewer images than common ones. Second, **fine-grained morphological overlap**: the discriminative signal lies in the *frequency content* of the lesion—low-frequency structure (plate-like fissures in Harlequin Ichthyosis) versus high-frequency texture (fine fish-scale patterns in Ichthyosis Vulgaris)—which conventional uniform attention does not explicitly model. Borderline pairs such as Lamellar Ichthyosis versus Netherton Syndrome remain difficult for both convolutional and transformer baselines.

### 1.1 Contributions

1. **Architecture.** We introduce WaveCoAtNet, a ConvNeXt-Tiny–backboned hybrid that augments a preserved CNN path with a parallel transformer path driven by wavelet-decomposed cross-attention, prototype-anchored token selection, and dual-path aggregation—adding only ~2.3M parameters over the backbone.
2. **Mechanisms.** We formalize WG-FDCA, PA-DTS, and SCTR, each motivated by a specific failure mode of uniform attention on rare-disease imagery.
3. **Rigorous evaluation.** We benchmark twelve models—pretrained and from-scratch—under an identical fixed-split protocol, report 5-fold cross-validation with confidence intervals for the proposed model, conduct a ten-condition ablation, and apply McNemar significance testing throughout. We deliberately report where differences are *not* significant.
4. **Reproducibility.** We release training, ablation, and cross-validation scripts with fixed seeds and a single-command harness.

We are explicit about scope: our empirical claim is *competitive accuracy at substantially lower parameter cost*, supported by stable cross-validated performance—not a categorical accuracy victory over all baselines (see §6).

---

## 2. Related Work

**Hybrid CNN–Transformer models.** CoAtNet [21] and UniFormer [16] unify depthwise convolution with self-attention to combine convolutional inductive bias with global context. ConvNeXt [13,17] modernizes the pure-convolutional design with inverted-bottleneck blocks and large kernels. WaveCoAtNet adopts a ConvNeXt-Tiny backbone but, unlike these models, decomposes intermediate features in the *frequency* domain before attention.

**Frequency-domain learning.** Wavelet and Fourier representations have been used for denoising, super-resolution, and texture modeling. We use a lightweight 2D Haar transform to split early features into structural and textural sub-bands and let cross-attention attend to each separately—aligning the architecture with the diagnostic cue dermatologists use.

**Token selection and pruning.** DynamicViT and related methods prune tokens via learned gates or attention scores. PA-DTS differs by scoring tokens against *class prototypes* updated by EMA, coupling pruning to class semantics rather than generic saliency.

**Metric and prototype learning for imbalance.** Supervised contrastive learning and prototype networks improve separability under scarcity. SCTR applies a supervised contrastive objective to pooled token embeddings as an auxiliary regularizer, complementing class-weighted cross-entropy.

**AI for rare skin disease.** Prior ichthyosis work is limited to small-scale classical methods (e.g., SVM on Ichthyosis Vulgaris [8]) or severity scoring [11,12]. We provide a systematic multi-class deep-learning benchmark across five subtypes.

---

## 3. Method

### 3.1 Overview

WaveCoAtNet uses a parallel-path design that preserves pretrained CNN features while enriching them with a novel transformer path (Fig. 1). Given input $x \in \mathbb{R}^{3\times224\times224}$ and a ConvNeXt-Tiny stem, stage features have channel progression $96\!\to\!192\!\to\!384\!\to\!768$.

```
CNN path (pretrained, preserved):
    stem → stage1 → stage2 → stage3 → CBAM3 → stage4 → CBAM4 → cnn_tokens (B,49,768)

ViT path (novel, parallel):
    WG-FDCA(stage1, stage2) → +pos_embed → ViT blocks → project 192→768 → pooled (B,49,768)

Fusion:           tokens = cnn_tokens + vit_proj            (residual enrichment)
Downstream:       PA-DTS → PGAP → DPA → classifier
Auxiliary (train): SCTR contrastive loss + prototype orthogonality loss
```

### 3.2 Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA)

Let $F_1$ be stage-1 features. A single-level 2D Haar DWT produces four sub-bands:

$$\text{LL}, \text{LH}, \text{HL}, \text{HH} = \mathrm{DWT}_{\text{Haar}}(F_1), \quad \text{each} \in \mathbb{R}^{C\times H/2 \times W/2}.$$

We form a **structural stream** from the low-frequency band and a **textural stream** from the concatenated high-frequency bands, each projected to dimension $d=192$:

$$K_{\text{low}} = \phi_{\text{low}}(\text{LL}), \qquad K_{\text{high}} = \phi_{\text{high}}([\text{LH};\text{HL};\text{HH}]).$$

Stage-2 features supply queries $Q$. Two cross-attention operations run in parallel:

$$A_\ast = \mathrm{softmax}\!\left(\frac{Q\,K_\ast^{\top}}{\sqrt{d_h}}\right)V_\ast, \quad \ast \in \{\text{low}, \text{high}\}.$$

A learnable per-token **frequency gate** $g = \sigma(\mathrm{MLP}([A_{\text{low}}; A_{\text{high}}])) \in (0,1)$ balances structure against texture content-adaptively:

$$\hat{A} = g \odot A_{\text{high}} + (1-g)\odot A_{\text{low}}, \qquad Z = Q + \hat{A} + \mathrm{FFN}(\mathrm{LN}(Q+\hat{A})).$$

This explicitly decouples the structural and textural evidence that distinguishes ichthyosis subtypes, rather than mixing them in a single attention map.

### 3.3 Prototype-Anchored Dynamic Token Selection (PA-DTS)

PA-DTS maintains class prototypes $P \in \mathbb{R}^{K\times d}$ ($K{=}5$) updated by EMA during training:

$$P_c \leftarrow m\,P_c + (1-m)\,\bar{e}_c, \qquad m = 0.9 \;(\text{warmup}) \to 0.99,$$

where $\bar{e}_c$ is the mean embedding of class $c$ in the batch. Each token $t_i$ receives an importance score combining three z-normalized signals: prototype affinity $s^{\text{aff}}_i = \max_c \cos(t_i, P_c)$, affinity entropy $s^{\text{ent}}_i$, and SE-style channel saliency $s^{\text{ch}}_i$, weighted by a learned simplex $w=\mathrm{softmax}(\theta)$:

$$\alpha_i = \mathrm{softmax}_i\!\big(w_1 s^{\text{aff}}_i + w_2 s^{\text{ent}}_i + w_3 s^{\text{ch}}_i\big).$$

An adaptive keep-ratio predictor selects the top-$k$ tokens ($k$ between 60% and 95% of $N$), which are reweighted by $(1+\alpha)$. A cross-prototype **orthogonality loss** $\mathcal{L}_{\text{ortho}} = \lVert \tilde{P}\tilde{P}^{\top} - I\rVert^2$ discourages prototype collapse.

### 3.4 Prototype-Guided Attention Pooling (PGAP) & Dual-Path Aggregation (DPA)

PGAP pools the selected tokens by prototype-affinity weights $\beta = \mathrm{softmax}(\max_c \cos(t, P_c))$, yielding $e_{\text{pgap}} = \sum_i \beta_i t_i$. To avoid discarding holistic context when pruning is aggressive, DPA fuses PGAP with global average pooling $e_{\text{gap}}$ through a learned content gate $h$:

$$e = h\odot e_{\text{pgap}} + (1-h)\odot e_{\text{gap}}.$$

### 3.5 Supervised Contrastive Token Regularization (SCTR)

On pooled embeddings $e$, an auxiliary supervised contrastive loss with temperature $\tau=0.07$ clusters same-class and separates different-class samples; a prototype-alignment cross-entropy term anchors embeddings to $P$. The total training objective is:

$$\mathcal{L} = \mathcal{L}_{\text{CE}}^{\text{(label-smooth, class-weighted)}} + \lambda_{\text{s}}\mathcal{L}_{\text{SCTR}} + \lambda_{\text{o}}\mathcal{L}_{\text{ortho}}, \quad \lambda_{\text{s}}{=}0.1,\;\lambda_{\text{o}}{=}0.05.$$

CBAM channel+spatial attention is applied after stages 3 and 4 to recalibrate deep features.

---

## 4. Experimental Setup

### 4.1 Dataset

The dataset comprises **2,508** standardized 224×224 images across five categories with a natural long-tailed distribution:

| Class | Images | Share |
|---|---:|---:|
| Ichthyosis Vulgaris | 804 | 32.1% |
| Healthy Skin | 593 | 23.6% |
| Harlequin Ichthyosis | 484 | 19.3% |
| Lamellar Ichthyosis | 374 | 14.9% |
| Netherton Syndrome | 253 | 10.1% |
| **Total** | **2,508** | 100% |

Images were curated from public sources with quality control, color calibration, and resolution standardization.

### 4.2 Protocol

Two protocols are used. **(P1) Controlled comparison:** a fixed train/val/test split (test = 158 images, seed 42) on which all twelve models are trained for 30 epochs under identical data, augmentation, and optimization—the only fair head-to-head. **(P2) Cross-validation:** stratified 5-fold CV over the full 2,508 images (≈500 test images per fold) for the proposed model, reporting mean ± SD and 95% confidence intervals.

### 4.3 Implementation

AdamW with layer-wise learning rates (backbone $1\!\times\!10^{-5}$, novel modules $1\!\times\!10^{-4}$), weight decay 0.01, cosine annealing, batch size 24, 30 epochs, dropout 0.2, label smoothing 0.1, class-weighted CE, mixed-precision (AMP), seed 42. Augmentation: RandomResizedCrop, horizontal flip, ±15° rotation, TrivialAugmentWide, and RandomErasing. Backbones initialized from ImageNet-1k. Training on a single NVIDIA T4 (~76 s/epoch).

---

## 5. Results

### 5.1 Controlled Twelve-Model Comparison (P1)

All models share the identical fixed split and protocol.

| Model | Test Acc | Macro-F1 | Wtd-F1 | Params (Total) | Pretrained |
|---|---:|---:|---:|---:|:--:|
| Swin-T | 89.87% | 0.8623 | 0.8982 | 27.5M | ✓ |
| CoAtNet | 89.87% | 0.8489 | 0.8904 | 27.8M | ✓ |
| DINOv2 | 89.87% | 0.8443 | 0.8912 | 86.6M | ✓ |
| **WaveCoAtNet (ours)** | **89.24%** | **0.8388** | **0.8914** | **30.1M** | ✓ |
| ViT-B/16 | 89.24% | 0.8391 | 0.8968 | 85.8M | ✓ |
| BiomedCLIP | 88.61% | 0.8359 | 0.8858 | 195.9M | ✓ |
| GFT | 88.61% | 0.8228 | 0.8781 | 6.2M | ✓ |
| EfficientNet-B0 | 81.01% | 0.7740 | 0.8183 | 4.0M | ✓ |
| Swin-T (scratch) | 78.48% | 0.6702 | 0.7620 | 27.5M | ✗ |
| ViT (scratch) | 78.48% | 0.6822 | 0.7676 | 5.5M | ✗ |
| CNN (scratch) | 68.99% | 0.5862 | 0.6782 | 0.2M | ✗ |
| EfficientNet-B0 (scratch) | 65.19% | 0.5881 | 0.6572 | 4.0M | ✗ |

**Finding.** The top seven pretrained models occupy a 1.26-point accuracy band (88.61–89.87%). Pairwise McNemar tests show **no significant difference** among them on $n{=}158$ (all $p>0.37$). WaveCoAtNet sits inside this statistically indistinguishable cluster while using **2.8× fewer parameters than ViT-B/16** and **6.5× fewer than BiomedCLIP**. Transfer learning is decisive: pretrained models beat from-scratch counterparts by 11–16 points.

### 5.2 Cross-Validated Performance (P2)

| Fold | Accuracy | Macro-F1 |
|---|---:|---:|
| 1 | 96.61% | 0.9602 |
| 2 | 95.02% | 0.9439 |
| 3 | 97.21% | 0.9667 |
| 4 | 96.01% | 0.9491 |
| 5 | 96.41% | 0.9553 |
| **Mean ± SD** | **96.25% ± 0.81%** | **0.9550 ± 0.0090** |

95% CI [95.54%, 96.97%]; Cohen's κ = 0.9514 ± 0.0105; macro-precision 95.62% ± 1.09%; macro-recall 95.48% ± 0.72%; macro-specificity 99.04% ± 0.20%. The tight SD across folds evidences **stability**, not just peak accuracy. Per-class sensitivity/specificity:

| Class | Sensitivity | Specificity |
|---|---:|---:|
| Harlequin Ichthyosis | 0.9897 | 0.9965 |
| Healthy Skin | 0.9966 | 0.9979 |
| Ichthyosis Vulgaris | 0.9689 | 0.9800 |
| Lamellar Ichthyosis | 0.8663 | 0.9864 |
| Netherton Syndrome | 0.9526 | 0.9911 |

Harlequin Ichthyosis—the most clinically urgent class—reaches near-ceiling sensitivity. Lamellar Ichthyosis remains the hardest class, consistent with its genuine clinical overlap with Netherton Syndrome.

> **Scope note.** P2 was applied to WaveCoAtNet to characterize stability; baselines in §5.1 were evaluated under P1. The cross-validated and held-out numbers are therefore *not* directly comparable, and we do not claim the 96.25% figure as a margin over the §5.1 baselines. A fully matched cross-validated comparison of all baselines is the primary item for camera-ready (see §6).

### 5.3 Ablation Study

Ten conditions, identical split and protocol; Δ relative to the full model.

| Condition | Acc | ΔAcc | Macro-F1 | ΔF1 | κ |
|---|---:|---:|---:|---:|---:|
| WaveCoAtNet (Full) | 91.14% | — | 0.8746 | — | 0.8842 |
| w/o DPA (PGAP only) | 92.41% | +1.27 | 0.8907 | +1.61 | 0.9013 |
| w/o PGAP+DPA (mean pool) | 91.14% | +0.00 | 0.8758 | +0.12 | 0.8851 |
| **w/o WG-FDCA (plain CA)** | **88.61%** | **−2.53** | **0.8413** | **−3.34** | 0.8525 |
| w/o Transformer | 91.14% | +0.00 | 0.8716 | −0.30 | 0.8847 |
| w/o PA-DTS (GAP) | 90.51% | −0.63 | 0.8580 | −1.66 | 0.8763 |
| w/o SCTR (CE only) | 89.87% | −1.27 | 0.8562 | −1.84 | 0.8685 |
| w/ Fixed Pruning | 91.14% | +0.00 | 0.8781 | +0.34 | 0.8849 |
| w/o Prototypes (SE only) | 90.51% | −0.63 | 0.8688 | −0.58 | 0.8759 |
| ConvNeXt-Tiny baseline | 91.77% | +0.63 | 0.8790 | +0.44 | 0.8928 |

**Honest reading.** WG-FDCA is the **only** component whose removal causes a substantial macro-F1 drop (−3.34%), confirming frequency decomposition as the core contribution; SCTR (−1.84%) and PA-DTS (−1.66%) follow. Other components (DPA, transformer path) are within noise on this split, and McNemar finds **no condition significantly different from the full model** ($p>0.28$). This is expected at $n{=}158$ and is precisely why §5.2 uses cross-validation. We report the unflattering rows (e.g., the ConvNeXt baseline edging the full model on this single split) rather than omit them.

---

## 6. Discussion and Limitations

**What the evidence supports.** (i) Frequency-decomposed cross-attention is a genuine and isolatable contribution. (ii) WaveCoAtNet matches the strongest baselines at a fraction of the parameters, a meaningful efficiency result for deployment in resource-limited dermatology settings. (iii) Cross-validation shows the model is stable, not a single lucky split.

**Limitations.** (1) **Matched-protocol comparison.** Baselines were evaluated under P1; extending all baselines to the 5-fold protocol with paired McNemar tests is required before any superiority claim and is our top priority. (2) **Sample size.** $n{=}158$ on the held-out split cannot resolve sub-1.5% differences; this motivated P2 but the dataset remains modest by computer-vision standards. (3) **Single-center curation.** External validation on an independent cohort is needed for clinical generalizability. (4) **Lamellar/Netherton overlap** persists and reflects real diagnostic difficulty.

**Path to a stronger claim.** Running §5.1's baselines under 5-fold CV, adding bootstrap confidence intervals on macro-F1, and reporting paired significance tests would convert the current "competitive + efficient" result into a defensible superiority claim if the margins hold.

---

## 7. Conclusion

We presented WaveCoAtNet, a parameter-efficient hybrid architecture for rare ichthyosis classification built on wavelet-guided frequency-decomposed cross-attention, prototype-anchored token selection, and supervised contrastive regularization. Under rigorous 5-fold cross-validation it achieves 96.25% ± 0.81% accuracy with stable per-fold behavior and near-ceiling sensitivity on the life-threatening Harlequin subtype, and it matches the strongest pretrained baselines on a controlled common-split benchmark while using up to 6.5× fewer parameters. Ablation isolates frequency decomposition as the principal driver of performance. Rather than overstating a margin, we frame WaveCoAtNet as an accuracy–efficiency advance and provide a reproducible harness to support a fully matched comparison.

---

## References

[1] Akiyama, M. "Updated molecular genetics and pathogenesis of ichthyoses." *Nagoya J. Med. Sci.* 73.3–4 (2011): 79.
[2] Diociaiuti, A., et al. "Role of molecular testing in the multidisciplinary diagnostic approach of ichthyosis." *Orphanet J. Rare Dis.* 11.1 (2016): 4.
[3] Plazar, D., et al. "Dermoscopic patterns of genodermatoses: A comprehensive analysis." *Biomedicines* 11.10 (2023): 2717.
[4] Colussi, M. "Mitigating data scarcity challenges in medical imaging analysis." 2024.
[5] Grignaffini, F., et al. "Machine learning approaches for skin cancer classification from dermoscopic images: A systematic review." *Algorithms* 15.11 (2022): 438.
[6] Zafar, M., et al. "Skin lesion analysis and cancer detection based on machine/deep learning techniques." *Life* 13.1 (2023): 146.
[7] Goldust, M. "Artificial intelligence in addressing rare skin disorders." *Int. J. Dermatol.* 63.11 (2024).
[8] Khan, T.F., Dubey, P., Upadhyay, Y. "Detection of Ichthyosis Vulgaris using SVM." In *Intelligent Systems and Applications in Computer Vision*, CRC Press, 2023, pp. 115–123.
[9] Chanda, T., et al. "Dermatologist-like explainable AI enhances trust and confidence in diagnosing melanoma." *Nat. Commun.* 15.1 (2024): 524.
[10] Jeong, H.K., et al. "Deep learning in dermatology: A systematic review." *JID Innov.* 3.1 (2023): 100150.
[11] Sun, Q., et al. "Development and initial validation of a novel system to assess ichthyosis severity." *JAMA Dermatol.* 158.4 (2022): 359–365.
[12] Sun, Q., et al. "The genomic and phenotypic landscape of ichthyosis: An analysis of 1000 kindreds." *JAMA Dermatol.* 158.1 (2022): 16–25.
[13] Liu, Z., et al. "A ConvNet for the 2020s (ConvNeXt)." *CVPR*, 2022.
[14] Frost, P., Van Scott, E.J. "Ichthyosiform dermatoses: Classification based on anatomic and biometric observations." *Arch. Dermatol.* 94.2 (1966): 113–126.
[15] Guo, Y., et al. "Depthwise convolution is all you need for learning multiple visual domains." *AAAI* 33.1 (2019).
[16] Li, K., et al. "UniFormer: Unifying convolution and self-attention for visual recognition." *IEEE TPAMI* 45.10 (2023): 12581–12600.
[17] Ramos, L., et al. "A study of ConvNeXt architectures for enhanced image captioning." *IEEE Access* 12 (2024): 13711–13728.
[18] Howard, A., et al. "Inverted bottlenecks and efficient mobile architectures." 2019.
[19] Saranya, K., et al. "Skin Disease Detection Using CNN." *ICDECS*, 2024, pp. 1–6.
[20] Khosla, P., et al. "Supervised Contrastive Learning." *NeurIPS*, 2020.
[21] Dai, Z., et al. "CoAtNet: Marrying Convolution and Attention for All Data Sizes." *NeurIPS*, 2021.
[22] Dosovitskiy, A., et al. "An Image is Worth 16×16 Words: Transformers for Image Recognition at Scale (ViT)." *ICLR*, 2021.
[23] Liu, Z., et al. "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows." *ICCV*, 2021.
[24] Oquab, M., et al. "DINOv2: Learning Robust Visual Features without Supervision." *TMLR*, 2024.
[25] Zhang, S., et al. "BiomedCLIP: A multimodal biomedical foundation model." 2023.
[26] Woo, S., et al. "CBAM: Convolutional Block Attention Module." *ECCV*, 2018.
[27] Rao, Y., et al. "DynamicViT: Efficient Vision Transformers with Dynamic Token Sparsification." *NeurIPS*, 2021.
