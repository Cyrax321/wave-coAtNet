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

