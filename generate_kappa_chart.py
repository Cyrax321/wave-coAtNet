import matplotlib.pyplot as plt
import numpy as np

# Data
models = [
    'CNN (Scratch)',
    'ViT (Scratch)',
    'EfficientNet-B0 (Scratch)',
    'Swin-T (Scratch)',
    'EfficientNet-B0 (PT)',
    'GFT',
    'BiomedCLIP',
    'ViT-B/16 (PT)',
    'DINOv2',
    'Swin-T (PT)',
    'H-CoAtNet (Hybrid Baseline)',
    'ConvNeXt-Tiny (CoAtNet)',
    'WaveCoAtNet (Proposed)'
]

kappa_scores = [
    0.5317,
    0.5788,
    0.6095,
    0.6319,
    0.7239,
    0.8271,
    0.8439,
    0.8521,
    0.8594,
    0.8680,
    0.8755,
    0.8757,
    0.8844
]

# Set up the plot
plt.figure(figsize=(10, 7))

# Colors
# Default gray for baselines, light blue for H-CoAtNet, dark blue for WaveCoAtNet
colors = ['#808691'] * len(models)
colors[models.index('H-CoAtNet (Hybrid Baseline)')] = '#5B9BD5' # Light Blue
colors[models.index('WaveCoAtNet (Proposed)')] = '#3A74ED'    # Dark Blue

# Create horizontal bars
bars = plt.barh(models, kappa_scores, color=colors)

# Add values at the end of each bar
for bar in bars:
    width = bar.get_width()
    plt.text(width + 0.01, 
             bar.get_y() + bar.get_height()/2, 
             f'{width:.4f}', 
             ha='left', va='center', fontweight='bold', fontsize=9)

# Formatting
plt.title("Cohen's Kappa Agreement Comparison (13 Models)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Cohen's Kappa", fontsize=12)
plt.xlim(0, 1.0)
plt.grid(axis='x', linestyle='-', alpha=0.3)

# Remove top and right spines
plt.gca().spines['top'].set_visible(False)
plt.gca().spines['right'].set_visible(False)

# Add a vertical line at 0
plt.axvline(x=0, color='black', linewidth=1)

# Ensure tight layout
plt.tight_layout()

# Save the plot
plt.savefig('kappa_comparison_13_models.png', dpi=300, bbox_inches='tight')
print("Chart generated successfully as kappa_comparison_13_models.png")
