# Wave-CoAtNet: Wavelet-Enhanced Hybrid CNN-Transformer for Rare Ichthyosis Classification

## Overview

Wave-CoAtNet is a deep learning architecture engineered for sample-efficient multi-class classification of rare ichthyosis subtypes. The model integrates 2D Discrete Wavelet Transform (DWT) subband decomposition with depthwise separable convolution (MBConv) and relative self-attention blocks, preserving fine dermal scale patterns across multiple spatial resolutions.

## Architecture

```
Input Image (3 x 224 x 224)
        |
        v
[ 2D Wavelet Subband Decomposition (DWT: LL, LH, HL, HH) ]
        |
        v
[ Stage 1: MBConv Depthwise Separable Convolution + Squeeze-and-Excitation ]
        |
        v
[ Stage 2: Wavelet Pooling & Cross-Scale Feature Fusion ]
        |
        v
[ Stage 3: Multi-Head Self-Attention with Relative Position Bias ]
        |
        v
[ Global Average Pooling & Linear Classification Head ]
        |
        v
Predicted Subtype (5 Classes)
```

### Key Technical Components

1. Discrete Wavelet Decomposition: Captures high-frequency epidermal textures and low-frequency structural geometry without spatial downsampling artifacts.
2. Hybrid Inductive Bias: Combines local convolutional inductive priors in early stages with global attention context in deeper layers.
3. Class-Balanced Objective: Incorporates focal margin scaling and effective sample weighting to handle severe rare-disease class imbalance.

## Experimental Results

The architecture was evaluated across five rare ichthyosis subtypes using 5-fold cross-validation against 12 standard baselines (including ResNet, EfficientNet, ConvNeXt, Swin Transformer, and ViT).

- Quadratic Weighted Kappa: 0.942
- Macro F1-Score: 0.938
- Multiclass ROC-AUC: 0.979

## Repository Structure

- `Wave-CoAtNet-Ichthyosis/`: Core PyTorch modules, wavelet layers, and attention mechanisms.
- `models/`: Architecture definitions, hybrid blocks, and positional bias implementations.
- `training/`: Loss formulations, learning rate schedulers, and optimization pipelines.
- `eval/`: Quadratic weighted kappa metrics, stratified confusion matrices, and ROC-AUC evaluation scripts.
- `docs/`: Technical ablation logs, experimental protocols, and paper manuscripts.

## Research Methodology

Experimental exploration, hyperparameter tuning, and ablation suites are driven through an agent-accelerated research workflow, with human-in-the-loop oversight governing model architecture decisions, experimental controls, and clinical validity.
