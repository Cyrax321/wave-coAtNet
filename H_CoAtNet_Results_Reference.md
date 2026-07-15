# H-CoAtNet: Extracted Reference Data

This file serves as a safe backup of all quantitative results, architecture tables, and observations for the original `H-CoAtNet` model extracted from the manuscript. We will reuse this data when constructing the unified 13-model comparison table and discussing architectures.

## 1. Overall Performance Metrics
*Extracted from old Table 8.*

| Metric | Score |
| :--- | :--- |
| **Test Accuracy** | 0.9051 (90.51%) |
| **Macro Average F1-Score** | 0.8605 |
| **Weighted Average F1-Score** | 0.9024 |

## 2. Class-Wise Performance
*Extracted from old Table 9.*

| Disease Subtype | Precision | Recall (Sensitivity) | F1-Score |
| :--- | :--- | :--- | :--- |
| **Harlequin Ichthyosis (HI)** | 0.9667 | 0.9062 | 0.9355 |
| **Healthy Skin** | 0.9574 | 1.0000 | 0.9783 |
| **Ichthyosis Vulgaris (IV)** | 0.9000 | 0.9783 | 0.9375 |
| **Lamellar Ichthyosis (LI)** | 0.8750 | 0.6364 | 0.7368 |
| **Netherton Syndrome (NS)** | 0.6667 | 0.7692 | 0.7143 |

## 3. H-CoAtNet Architecture Details
*Extracted from old Table 2.*

| No. | Layer | Output Shape |
| :--- | :--- | :--- |
| 1 | Input | (224, 224, 3) |
| 2 | Conv2d (Stem) | (96, 56, 56) |
| 3 | LayerNorm 1 | (96, 56, 56) |
| 4 | ConvNeXtBlock 1-9 | (96, 56, 56) |
| 5 | LayerNorm 2 | (96, 56, 56) |
| 6 | Conv2d 2 (Downsample) | (192, 28, 28) |
| 7 | ConvNeXtBlock 10-12 | (192, 28, 28) |
| 8 | Transformer Block 1 | (784, 192) |
| 9 | Transformer Block 2 | (784, 192) |
| 10 | LayerNorm 3 | (192, 28, 28) |
| 11 | Conv2d 3 (Downsample) | (384, 14, 14) |
| 12 | ConvNeXtBlock 13-21 | (384, 14, 14) |
| 13 | LayerNorm 4 | (384, 14, 14) |
| 14 | Conv2d 4 (Downsample) | (768, 7, 7) |
| 15 | ConvNeXtBlock 22-24 | (768, 7, 7) |
| 16 | HierarchicalSE 1 | (49, 768) |
| 17 | HierarchicalSE 2 | (36, 768) |
| 18 | LayerNorm 5 (Head) | (768) |
| 19 | Dense (Output) | (5) |

## 4. Other Notable Observations Extracted from Text
*   **Harlequin Ichthyosis:** Achieved near-perfect precision (0.9667) and high recall (0.9062), minimizing false negatives for the most life-threatening condition.
*   **Healthy Skin:** Perfect recall (1.0000), meaning it never misdiagnosed healthy skin as a disease.
*   **Training Dynamics:** Demonstrated rapid convergence, achieving 80% validation accuracy within the first 5 epochs and maintaining stable improvement without significant oscillation.
*   **Token Efficiency:** Progressive token pruning (from 75% to 50% retention via the Hierarchical Squeeze-and-Excitation mechanisms) demonstrated high computational efficiency without sacrificing classification accuracy.
*   **Parameter Count:** The parameter count for H-CoAtNet was not explicitly written in the old paper (unlike GFT which was listed as 2,010,472, EfficientNet at 4,011,391, and CNN at 242,181), but we know from the codebase that the standard CoAtNet is ~27M.

## 5. Mathematically Reconstructed Data (Kappa)
*Derived via algebraic solver from Precision and Recall fractions for N=158 test set.*

| Metric | Value |
| :--- | :--- |
| **Total Test Images (N)** | 158 |
| **Total True Positives** | 143 |
| **Observed Agreement ($P_o$)** | 0.9051 |
| **Expected Agreement ($P_e$)** | 0.2395 |
| **Cohen's Kappa ($\kappa$)** | **0.8755** |

### Reconstructed Support Distribution
*   **Harlequin Ichthyosis (HI):** 32 Actual Images (29 Correct)
*   **Healthy Skin:** 45 Actual Images (45 Correct)
*   **Ichthyosis Vulgaris (IV):** 46 Actual Images (45 Correct)
*   **Lamellar Ichthyosis (LI):** 22 Actual Images (14 Correct)
*   **Netherton Syndrome (NS):** 13 Actual Images (10 Correct)
