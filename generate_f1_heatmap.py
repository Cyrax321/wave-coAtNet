import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

# Data from Table 9
models = [
    'WaveCoAtNet (Proposed)',
    'H-CoAtNet (Proposed Baseline)',
    'EfficientNet-B0 (PT)',
    'Swin-T (PT)',
    'ViT-B/16 (PT)',
    'CoAtNet (PT)',
    'GFT',
    'BiomedCLIP',
    'DINOv2',
    'CNN (Scratch)',
    'EfficientNet-B0 (Scratch)',
    'Swin-T (Scratch)',
    'ViT (Scratch)'
]

classes = ['Harlequin Ichthyosis', 'Healthy Skin', 'Ichthyosis Vulgaris', 'Lamellar Ichthyosis', 'Netherton Syndrome']

data = [
    [0.9508, 0.9890, 0.9474, 0.6486, 0.8125], # WaveCoAtNet
    [0.9355, 0.9783, 0.9375, 0.7368, 0.7143], # H-CoAtNet
    [0.9355, 0.8864, 0.7857, 0.5600, 0.5625], # EffNet PT
    [0.9355, 0.9778, 0.9474, 0.6486, 0.7500], # Swin-T PT
    [0.9508, 0.9778, 0.9247, 0.5946, 0.7429], # ViT PT
    [0.9508, 0.9677, 0.9474, 0.7027, 0.7333], # CoAtNet PT
    [0.9062, 0.9462, 0.9213, 0.7179, 0.5806], # GFT
    [0.9180, 0.9890, 0.9348, 0.5946, 0.6857], # BiomedCLIP
    [0.9677, 0.9670, 0.9375, 0.5714, 0.7500], # DINOv2
    [0.6286, 0.7727, 0.7640, 0.2000, 0.4828], # CNN Scratch
    [0.7647, 0.8706, 0.7674, 0.3556, 0.3750], # EffNet Scratch
    [0.7812, 0.8941, 0.7416, 0.4815, 0.3333], # Swin Scratch
    [0.7302, 0.8864, 0.7470, 0.3478, 0.2778]  # ViT Scratch
]

df = pd.DataFrame(data, index=models, columns=classes)

# Sort DataFrame by average F1-score across all classes to make the visual hierarchy clear
df['Mean F1'] = df.mean(axis=1)
df = df.sort_values('Mean F1', ascending=False)
df = df.drop('Mean F1', axis=1)

# Plotting
plt.figure(figsize=(12, 8))
# Use a highly professional medical imaging colormap (YlGnBu or rocket/mako)
sns.heatmap(df, annot=True, fmt=".4f", cmap="YlGnBu", linewidths=.5, cbar_kws={'label': 'F1 Score'})

plt.title('Per-Class F1 Score Heatmap Across All Models', fontsize=16, fontweight='bold', pad=20)
plt.ylabel('Architectures', fontsize=12, fontweight='bold')
plt.xlabel('Ichthyosis Classes', fontsize=12, fontweight='bold')

plt.xticks(rotation=45, ha='right')
plt.tight_layout()

plt.savefig('f1_score_heatmap.png', dpi=300, bbox_inches='tight')
print("Heatmap generated successfully as f1_score_heatmap.png")
