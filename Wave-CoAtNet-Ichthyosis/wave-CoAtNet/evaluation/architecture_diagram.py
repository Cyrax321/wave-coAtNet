"""
WaveCoAtNet Architecture Diagram - Publication Quality
Clean, professional diagram for research paper.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Professional color scheme
COLORS = {
    'input': '#E3F2FD',
    'cnn': '#1976D2',
    'cbam': '#FF9800',
    'wavelet': '#4CAF50',
    'vit': '#7B1FA2',
    'fusion': '#F44336',
    'prototype': '#00897B',
    'classifier': '#37474F',
    'loss': '#FF5722',
    'arrow': '#424242',
    'text_white': '#FFFFFF',
    'text_dark': '#212121',
    'bg': '#FAFAFA',
}

def draw_box(ax, x, y, w, h, label, color, fontsize=9, bold=False, sublabel=None, alpha=1.0):
    """Draw a rounded rectangle with label."""
    box = FancyBboxPatch((x, y), w, h, 
                         boxstyle="round,pad=0.015",
                         facecolor=color, edgecolor='#333333', 
                         linewidth=1.0, alpha=alpha)
    ax.add_patch(box)
    
    weight = 'bold' if bold else 'normal'
    text_color = COLORS['text_white'] if color not in [COLORS['input']] else COLORS['text_dark']
    
    if sublabel:
        ax.text(x + w/2, y + h/2 + 0.015, label, ha='center', va='center',
                fontsize=fontsize, color=text_color, fontweight=weight)
        ax.text(x + w/2, y + h/2 - 0.02, sublabel, ha='center', va='center',
                fontsize=fontsize-2, color=text_color, fontweight='normal', style='italic')
    else:
        ax.text(x + w/2, y + h/2, label, ha='center', va='center',
                fontsize=fontsize, color=text_color, fontweight=weight)

def draw_arrow(ax, x1, y1, x2, y2, color=COLORS['arrow'], lw=1.2, style='->'):
    """Draw an arrow between points."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))

def draw_curved_arrow(ax, x1, y1, x2, y2, color=COLORS['arrow'], lw=1.2, connectionstyle="arc3,rad=0.2"):
    """Draw a curved arrow."""
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw, 
                               connectionstyle=connectionstyle))

def create_architecture_diagram():
    """Create a clean, publication-quality architecture diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(18, 11))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.set_facecolor(COLORS['bg'])
    fig.set_facecolor('white')
    
    # Title
    ax.text(0.5, 0.97, 'WaveCoAtNet Architecture', ha='center', va='top',
            fontsize=18, fontweight='bold', color=COLORS['text_dark'])
    ax.text(0.5, 0.945, 'Wavelet-enhanced Convolutional Attention Network with Frequency-Decomposed Cross-Attention',
            ha='center', va='top', fontsize=11, color='#616161', style='italic')
    
    # ==================== TOP ROW: CNN BACKBONE ====================
    y_top = 0.88
    
    # Input
    draw_box(ax, 0.02, y_top, 0.07, 0.06, 'Input', COLORS['input'], fontsize=9, sublabel='224×224×3')
    
    # Stem
    draw_box(ax, 0.11, y_top, 0.07, 0.06, 'Stem', COLORS['cnn'], fontsize=9, sublabel='7×7, s2')
    
    # Stage 1
    draw_box(ax, 0.20, y_top, 0.07, 0.06, 'Stage 1', COLORS['cnn'], fontsize=9, sublabel='56×56×96')
    
    # Stage 2
    draw_box(ax, 0.29, y_top, 0.07, 0.06, 'Stage 2', COLORS['cnn'], fontsize=9, sublabel='28×28×192')
    
    # Arrows in top row
    draw_arrow(ax, 0.09, y_top+0.03, 0.11, y_top+0.03)
    draw_arrow(ax, 0.18, y_top+0.03, 0.20, y_top+0.03)
    draw_arrow(ax, 0.27, y_top+0.03, 0.29, y_top+0.03)
    
    # ==================== MIDDLE ROW: CNN PATH (Upper) ====================
    y_cnn = 0.72
    
    # Label for CNN path
    ax.text(0.02, y_cnn + 0.04, 'CNN Path', fontsize=10, fontweight='bold', color=COLORS['cnn'])
    
    # Stage 3
    draw_box(ax, 0.29, y_cnn, 0.07, 0.06, 'Stage 3', COLORS['cnn'], fontsize=9, sublabel='14×14×384')
    
    # CBAM 3
    draw_box(ax, 0.38, y_cnn, 0.06, 0.06, 'CBAM', COLORS['cbam'], fontsize=8, sublabel='384')
    
    # Stage 4
    draw_box(ax, 0.46, y_cnn, 0.07, 0.06, 'Stage 4', COLORS['cnn'], fontsize=9, sublabel='7×7×768')
    
    # CBAM 4
    draw_box(ax, 0.55, y_cnn, 0.06, 0.06, 'CBAM', COLORS['cbam'], fontsize=8, sublabel='768')
    
    # Flatten
    draw_box(ax, 0.63, y_cnn, 0.06, 0.06, 'Flatten', COLORS['cnn'], fontsize=8)
    
    # CNN Tokens
    draw_box(ax, 0.71, y_cnn, 0.08, 0.06, 'CNN Tokens', COLORS['cnn'], fontsize=9, sublabel='49×768')
    
    # Arrows in CNN path
    draw_arrow(ax, 0.36, y_cnn+0.03, 0.38, y_cnn+0.03)
    draw_arrow(ax, 0.44, y_cnn+0.03, 0.46, y_cnn+0.03)
    draw_arrow(ax, 0.53, y_cnn+0.03, 0.55, y_cnn+0.03)
    draw_arrow(ax, 0.61, y_cnn+0.03, 0.63, y_cnn+0.03)
    draw_arrow(ax, 0.69, y_cnn+0.03, 0.71, y_cnn+0.03)
    
    # Vertical arrow from Stage 2 to Stage 3
    draw_arrow(ax, 0.325, y_top, 0.325, y_cnn+0.06)
    
    # ==================== MIDDLE ROW: ViT PATH (Lower) ====================
    y_vit = 0.52
    
    # Label for ViT path
    ax.text(0.02, y_vit + 0.04, 'ViT Path', fontsize=10, fontweight='bold', color=COLORS['vit'])
    
    # WG-FDCA (Novel Module 1)
    draw_box(ax, 0.08, y_vit, 0.14, 0.07, 'WG-FDCA', COLORS['wavelet'], fontsize=11, bold=True,
             sublabel='Wavelet Cross-Attention')
    
    # Position Embedding
    draw_box(ax, 0.24, y_vit+0.01, 0.06, 0.05, 'Pos Embed', COLORS['vit'], fontsize=7)
    
    # ViT Blocks (Novel)
    draw_box(ax, 0.32, y_vit, 0.10, 0.07, 'ViT ×4', COLORS['vit'], fontsize=10, bold=True,
             sublabel='Transformer Blocks')
    
    # Project 192→768
    draw_box(ax, 0.44, y_vit+0.01, 0.06, 0.05, 'Project', COLORS['vit'], fontsize=7, sublabel='192→768')
    
    # ViT Tokens
    draw_box(ax, 0.52, y_vit, 0.08, 0.06, 'ViT Tokens', COLORS['vit'], fontsize=9, sublabel='49×768')
    
    # Arrows in ViT path
    draw_arrow(ax, 0.22, y_vit+0.035, 0.24, y_vit+0.035)
    draw_arrow(ax, 0.30, y_vit+0.035, 0.32, y_vit+0.035)
    draw_arrow(ax, 0.42, y_vit+0.035, 0.44, y_vit+0.035)
    draw_arrow(ax, 0.50, y_vit+0.035, 0.52, y_vit+0.035)
    
    # Vertical arrows from Stage 1 and Stage 2 to WG-FDCA
    draw_curved_arrow(ax, 0.235, y_top, 0.15, y_vit+0.07, color=COLORS['wavelet'], lw=1.0)
    draw_curved_arrow(ax, 0.325, y_top, 0.15, y_vit+0.07, color=COLORS['wavelet'], lw=1.0)
    
    # ==================== FUSION ====================
    y_fusion = 0.38
    
    # Fusion box
    draw_box(ax, 0.62, y_fusion, 0.08, 0.06, 'Add', COLORS['fusion'], fontsize=10, bold=True)
    
    # Arrows to fusion
    draw_arrow(ax, 0.75, y_cnn, 0.66, y_fusion+0.06)
    draw_arrow(ax, 0.56, y_vit, 0.66, y_fusion+0.06)
    
    # Plus sign
    ax.text(0.695, y_fusion+0.08, '+', fontsize=14, fontweight='bold', color=COLORS['fusion'], ha='center')
    
    # ==================== DOWNSTREAM MODULES ====================
    y_down = 0.22
    
    # Label for downstream
    ax.text(0.02, y_down + 0.04, 'Downstream Modules', fontsize=10, fontweight='bold', color=COLORS['prototype'])
    
    # PA-DTS (Novel Module 2)
    draw_box(ax, 0.08, y_down, 0.12, 0.07, 'PA-DTS', COLORS['prototype'], fontsize=10, bold=True,
             sublabel='Token Selection')
    
    # PGAP (Novel Module 3)
    draw_box(ax, 0.22, y_down, 0.10, 0.07, 'PGAP', COLORS['prototype'], fontsize=10, bold=True,
             sublabel='Attn Pooling')
    
    # DPA (Novel Module 4)
    draw_box(ax, 0.34, y_down, 0.10, 0.07, 'DPA', COLORS['prototype'], fontsize=10, bold=True,
             sublabel='Dual-Path')
    
    # Classifier
    draw_box(ax, 0.46, y_down, 0.10, 0.07, 'Classifier', COLORS['classifier'], fontsize=10, bold=True,
             sublabel='5 classes')
    
    # Output
    draw_box(ax, 0.58, y_down, 0.08, 0.07, 'Output', COLORS['classifier'], fontsize=10, bold=True)
    
    # Arrows in downstream
    draw_arrow(ax, 0.66, y_fusion, 0.14, y_down+0.07)
    draw_arrow(ax, 0.20, y_down+0.035, 0.22, y_down+0.035)
    draw_arrow(ax, 0.32, y_down+0.035, 0.34, y_down+0.035)
    draw_arrow(ax, 0.44, y_down+0.035, 0.46, y_down+0.035)
    draw_arrow(ax, 0.56, y_down+0.035, 0.58, y_down+0.035)
    
    # ==================== SCTR LOSS ====================
    y_loss = 0.08
    
    # SCTR Loss box
    draw_box(ax, 0.08, y_loss, 0.12, 0.06, 'SCTR Loss', COLORS['loss'], fontsize=9, bold=True,
             sublabel='Auxiliary')
    
    # Dashed arrow from fusion to SCTR
    ax.annotate('', xy=(0.14, y_loss+0.06), xytext=(0.62, y_fusion),
                arrowprops=dict(arrowstyle='->', color=COLORS['loss'], lw=1.2, linestyle='dashed'))
    
    # Dashed arrow from PA-DTS prototypes to SCTR
    ax.annotate('', xy=(0.14, y_loss+0.06), xytext=(0.14, y_down),
