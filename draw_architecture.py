import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

def draw_architecture():
    # Landscape orientation: wide width, shorter height
    fig, ax = plt.subplots(1, 1, figsize=(32, 14))
    ax.set_xlim(-1, 48)
    ax.set_ylim(-6, 12)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.patch.set_facecolor('#FFFFFF')

    # ── ICML / Standard draw.io Professional Palette ───────────
    C_INPUT      = '#f5f5f5'
    C_CNN_BG     = '#dae8fc'
    C_CNN_BORDER = '#6c8ebf'
    C_NOVEL      = '#ffe6cc'
    C_NOVEL_BD   = '#d79b00'
    C_VIT        = '#d5e8d4'
    C_VIT_BD     = '#82b366'
    C_WAVELET    = '#f8cecc'
    C_WAVELET_BD = '#b85450'
    C_FUSION     = '#fff2cc'
    C_FUSION_BD  = '#d6b656'
    C_OUTPUT     = '#ffffff'
    C_OUTPUT_BD  = '#000000'
    C_LOSS       = '#f5f5f5'
    C_LOSS_BD    = '#666666'
    C_CBAM       = '#e1d5e7'
    C_CBAM_BD    = '#9673a6'
    C_ARROW      = '#333333'
    C_TEXT       = '#111111'
    C_DIM_TEXT   = '#555555'
    C_GATE       = '#e1d5e7'
    C_GATE_BD    = '#9673a6'

    # ── Helper Functions ────────────────────────────────────────
    def draw_block(x, y, w, h, label, sublabel, fc, ec, fontsize=10,
                   sublabel_size=7.5, bold=True, radius=0.15):
        box = FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle=f"round,pad=0.06,rounding_size={radius}",
            facecolor=fc, edgecolor=ec, linewidth=1.8, zorder=3
        )
        ax.add_patch(box)
        weight = 'bold' if bold else 'normal'
        label_offset = 0.15 if sublabel else 0
        ax.text(x, y + label_offset,
                label, ha='center', va='center',
                fontsize=fontsize, fontweight=weight, color=C_TEXT, zorder=4)
        if sublabel:
            ax.text(x, y - 0.22,
                    sublabel, ha='center', va='center',
                    fontsize=sublabel_size, color=C_DIM_TEXT, zorder=4,
                    fontstyle='italic')

    def arrow(x1, y1, x2, y2, color=C_ARROW, style='-|>', lw=1.5,
              connectionstyle='arc3,rad=0', linestyle='-', zorder=2):
        a = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle=style, color=color,
            linewidth=lw, mutation_scale=14,
            connectionstyle=connectionstyle,
            linestyle=linestyle, zorder=zorder
        )
        ax.add_patch(a)

    def ortho_arrow(x1, y1, x2, y2, color=C_ARROW, ls='-', lw=1.5, direction='hv', zorder=2):
        # direction='hv' means horizontal then vertical.
        # direction='vh' means vertical then horizontal.
        if direction == 'hv':
            ax.plot([x1, x2], [y1, y1], color=color, ls=ls, lw=lw, zorder=zorder)
            ax.plot([x2, x2], [y1, y2], color=color, ls=ls, lw=lw, zorder=zorder)
        else:
            ax.plot([x1, x1], [y1, y2], color=color, ls=ls, lw=lw, zorder=zorder)
            ax.plot([x1, x2], [y2, y2], color=color, ls=ls, lw=lw, zorder=zorder)
        
        if direction == 'hv':
            dy = -1 if y2 < y1 else 1
            dx = 0
        else:
            dx = -1 if x2 < x1 else 1
            dy = 0
            
        ax.annotate('', xy=(x2, y2), xytext=(x2 - dx*0.01, y2 - dy*0.01),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=14),
                    zorder=zorder)

    def dim_label(x, y, text, fontsize=7, color=C_DIM_TEXT):
        ax.text(x, y, text, ha='center', va='center',
                fontsize=fontsize, color=color, zorder=5,
                fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.12', fc='white',
                          ec='none', alpha=0.85))

    # ── Layout Constants ────────────────────────────────────────
    BW, BH = 2.8, 1.0
    Y_TRUNK = 4.0
    Y_CNN = 7.5
    Y_VIT = 0.5
    STEP_X = 3.6

    # ================================================================
    # TITLE
    # ================================================================
    ax.text(23.5, 11.5,
            'WaveCoAtNet: Wavelet-Enhanced Convolutional Attention Network',
            ha='center', va='center', fontsize=18, fontweight='bold',
            color='#1A237E', zorder=5)
    ax.text(23.5, 10.7,
            'Architecture for Automated Ichthyosis Subtype Classification',
            ha='center', va='center', fontsize=13, color=C_DIM_TEXT, zorder=5,
            fontstyle='italic')

    # ================================================================
    # TRUNK (Early Stages)
    # ================================================================
    x = 1.0
    draw_block(x, Y_TRUNK, BW, BH, 'Input Image', '224 × 224 × 3', C_INPUT, '#90CAF9')
    dim_label(x, Y_TRUNK - BH/2 - 0.25, 'B×3×224×224')
    
    x += STEP_X
    draw_block(x, Y_TRUNK, BW, BH, 'CNN Stem', 'ConvNeXt-Tiny', C_CNN_BG, C_CNN_BORDER)
    arrow(x - STEP_X + BW/2, Y_TRUNK, x - BW/2, Y_TRUNK)

    x += STEP_X
    draw_block(x, Y_TRUNK, BW, BH, 'Stage 1', 'ConvNeXt Block × 3', C_CNN_BG, C_CNN_BORDER)
    arrow(x - STEP_X + BW/2, Y_TRUNK, x - BW/2, Y_TRUNK)
    x_s1 = x
    dim_label(x, Y_TRUNK - BH/2 - 0.25, 'B×96×56×56')

    x += STEP_X
    draw_block(x, Y_TRUNK, BW, BH, 'Stage 2', 'ConvNeXt Block × 3', C_CNN_BG, C_CNN_BORDER)
    arrow(x - STEP_X + BW/2, Y_TRUNK, x - BW/2, Y_TRUNK)
    x_s2 = x
    dim_label(x, Y_TRUNK - BH/2 - 0.25, 'B×192×28×28')

    # Split Point
    x_split = x + 1.8
    ax.plot(x_split, Y_TRUNK, 'o', color=C_ARROW, markersize=7, zorder=5)
    arrow(x + BW/2, Y_TRUNK, x_split, Y_TRUNK)
    
    # Branching Arrows
    arrow(x_split, Y_TRUNK, x_split + 1.2, Y_CNN, connectionstyle='arc3,rad=-0.2')
    arrow(x_split, Y_TRUNK, x_split + 1.2, Y_VIT, connectionstyle='arc3,rad=0.2')

    # Background Box for CNN Branch
    x_cnn_start = x_split + 1.8
    cnn_bg = FancyBboxPatch((x_cnn_start - BW/2 - 0.4, Y_CNN - BH/2 - 0.6), STEP_X*4 + 0.8, BH + 1.2,
                            boxstyle="round,pad=0.1,rounding_size=0.3", fc=C_CNN_BG, ec=C_CNN_BORDER,
                            lw=1.0, alpha=0.1, zorder=1, linestyle='--')
    ax.add_patch(cnn_bg)
    ax.text(x_cnn_start + STEP_X*2, Y_CNN + BH/2 + 0.3, 'Pretrained CNN Branch',
            ha='center', va='center', fontsize=10, fontweight='bold', color=C_CNN_BORDER, zorder=5)

    # ================================================================
    # CNN PATH (Top)
    # ================================================================
    x_cnn = x_cnn_start
    draw_block(x_cnn, Y_CNN, BW, BH, 'Stage 3', 'ConvNeXt Block × 9', C_CNN_BG, C_CNN_BORDER)
    dim_label(x_cnn, Y_CNN - BH/2 - 0.25, 'B×384×14×14')

    x_cnn += STEP_X
    draw_block(x_cnn, Y_CNN, BW, BH, 'CBAM', 'Channel+Spatial', C_CBAM, C_CBAM_BD)
    arrow(x_cnn - STEP_X + BW/2, Y_CNN, x_cnn - BW/2, Y_CNN)

    x_cnn += STEP_X
    draw_block(x_cnn, Y_CNN, BW, BH, 'Stage 4', 'ConvNeXt Block × 3', C_CNN_BG, C_CNN_BORDER)
    arrow(x_cnn - STEP_X + BW/2, Y_CNN, x_cnn - BW/2, Y_CNN)
    dim_label(x_cnn, Y_CNN - BH/2 - 0.25, 'B×768×7×7')

    x_cnn += STEP_X
    draw_block(x_cnn, Y_CNN, BW, BH, 'CBAM', 'Channel+Spatial', C_CBAM, C_CBAM_BD)
    arrow(x_cnn - STEP_X + BW/2, Y_CNN, x_cnn - BW/2, Y_CNN)

    x_cnn += STEP_X
    draw_block(x_cnn, Y_CNN, BW, BH, 'Flatten', 'Transpose', '#ECEFF1', '#78909C')
    arrow(x_cnn - STEP_X + BW/2, Y_CNN, x_cnn - BW/2, Y_CNN)
    x_end_cnn = x_cnn

    # ================================================================
    # ViT PATH (Bottom)
    # ================================================================
    x_vit = x_split + 2.5
    # WG-FDCA is a larger block containing two sub-blocks
    wg_w = 3.6
    wg_h = 2.4
    wg_bg = FancyBboxPatch((x_vit - wg_w/2, Y_VIT - wg_h/2), wg_w, wg_h,
                           boxstyle="round,pad=0.1,rounding_size=0.3", fc=C_WAVELET, ec=C_WAVELET_BD,
                           lw=1.5, alpha=0.3, zorder=1, linestyle='--')
    ax.add_patch(wg_bg)
    ax.text(x_vit, Y_VIT + wg_h/2 + 0.3, 'Wavelet-Guided Cross-Attention',
            ha='center', va='center', fontsize=9, fontweight='bold', color=C_WAVELET_BD)
    
    y_dwt = Y_VIT + 0.6
    y_ca = Y_VIT - 0.6
    draw_block(x_vit, y_dwt, BW, 0.8, '2D Haar DWT', 'Freq Decomp', C_WAVELET, C_WAVELET_BD)
    draw_block(x_vit, y_ca, BW, 0.8, 'Cross-Attention', 'Fusion', C_WAVELET, C_WAVELET_BD)
    arrow(x_vit, y_dwt - 0.4, x_vit, y_ca + 0.4, color=C_WAVELET_BD)

    # Route Stage 1 to DWT
    ortho_arrow(x_s1, Y_TRUNK - BH/2, x_vit - BW/2, y_dwt, color=C_WAVELET_BD, ls='--', direction='vh')
    # Route Stage 2 to CA
    ortho_arrow(x_s2, Y_TRUNK - BH/2, x_vit - BW/2, y_ca, color=C_WAVELET_BD, ls='--', direction='vh')

    # ViT Path continued
    x_vit += STEP_X + 0.5
    draw_block(x_vit, Y_VIT, BW, BH, 'Pos Embed', 'Add', C_VIT, C_VIT_BD)
    arrow(x_vit - STEP_X - 0.5 + wg_w/2, Y_VIT, x_vit - BW/2, Y_VIT)

    x_vit += STEP_X
    draw_block(x_vit, Y_VIT, BW, BH, 'ViT Blocks', 'MHSA + FFN × 4', C_VIT, C_VIT_BD)
    arrow(x_vit - STEP_X + BW/2, Y_VIT, x_vit - BW/2, Y_VIT)

    x_vit += STEP_X
    draw_block(x_vit, Y_VIT, BW, BH, 'Project', '192 → 768', C_VIT, C_VIT_BD)
    arrow(x_vit - STEP_X + BW/2, Y_VIT, x_vit - BW/2, Y_VIT)

    x_vit += STEP_X
    draw_block(x_vit, Y_VIT, BW, BH, 'Adaptive Pool', '28x28 → 7x7', C_VIT, C_VIT_BD)
    arrow(x_vit - STEP_X + BW/2, Y_VIT, x_vit - BW/2, Y_VIT)
    x_end_vit = x_vit

    # ViT background box
    vit_bg = FancyBboxPatch((x_split + 1.2, Y_VIT - 1.8), x_end_vit - (x_split + 1.2) + BW/2 + 0.5, 3.6,
                            boxstyle="round,pad=0.1,rounding_size=0.3", fc=C_VIT, ec=C_VIT_BD,
                            lw=1.0, alpha=0.1, zorder=0, linestyle='--')
    ax.add_patch(vit_bg)

    # ================================================================
    # FUSION
    # ================================================================
    x_fusion = max(x_end_cnn, x_end_vit) + 2.5
    draw_block(x_fusion, Y_TRUNK, 1.2, 1.2, '⊕', '', C_FUSION, C_FUSION_BD, fontsize=18, radius=0.6)
    
    ortho_arrow(x_end_cnn + BW/2, Y_CNN, x_fusion, Y_TRUNK + 0.6, color=C_FUSION_BD, direction='hv')
    ortho_arrow(x_end_vit + BW/2, Y_VIT, x_fusion, Y_TRUNK - 0.6, color=C_FUSION_BD, direction='hv')
    
    # ================================================================
    # DOWNSTREAM (NOVEL MODULES)
    # ================================================================
    x_down = x_fusion + STEP_X - 0.5
    draw_block(x_down, Y_TRUNK, BW, BH, 'PA-DTS', 'Token Selection', C_NOVEL, C_NOVEL_BD)
    arrow(x_fusion + 0.6, Y_TRUNK, x_down - BW/2, Y_TRUNK)

    # GAP Branch (Above PGAP)
    x_gap = x_down + STEP_X
    draw_block(x_gap, Y_TRUNK + 2.0, BW, BH, 'GAP', 'Global Pool', '#ECEFF1', '#78909C')
    ortho_arrow(x_down + BW/2 + 0.3, Y_TRUNK, x_gap - BW/2, Y_TRUNK + 2.0, direction='hv', color='#78909C', ls='--')

    draw_block(x_gap, Y_TRUNK, BW, BH, 'PGAP', 'Proto Attention Pool', C_NOVEL, C_NOVEL_BD)
    arrow(x_down + BW/2, Y_TRUNK, x_gap - BW/2, Y_TRUNK)

    x_down += STEP_X * 2
    draw_block(x_down, Y_TRUNK, BW, BH, 'DPA', 'Dual-Path Aggr.', C_NOVEL, C_NOVEL_BD)
    arrow(x_gap + BW/2, Y_TRUNK, x_down - BW/2, Y_TRUNK)
    ortho_arrow(x_gap + BW/2, Y_TRUNK + 2.0, x_down - BW/2, Y_TRUNK + 0.3, direction='hv', color='#78909C', ls='--')
    dim_label(x_down, Y_TRUNK - BH/2 - 0.25, 'B×768 (Final Embed)')
    x_dpa = x_down

    x_down += STEP_X
    draw_block(x_down, Y_TRUNK, BW, BH, 'Classifier', 'Linear', C_OUTPUT, C_OUTPUT_BD)
    arrow(x_dpa + BW/2, Y_TRUNK, x_down - BW/2, Y_TRUNK)

    x_down += STEP_X - 0.5
    draw_block(x_down, Y_TRUNK, BW-0.5, BH-0.2, 'Logits', '5 Classes', C_OUTPUT, C_OUTPUT_BD)
    arrow(x_down - STEP_X + 0.5 + BW/2, Y_TRUNK, x_down - (BW-0.5)/2, Y_TRUNK)

    # ================================================================
    # PROTOTYPES & LOSSES
    # ================================================================
    Y_LOSS = -2.5
    x_loss_start = x_fusion + STEP_X

    # Prototypes (Top right)
    x_proto = x_dpa
    y_proto = Y_TRUNK + 3.5
    draw_block(x_proto, y_proto, BW+0.5, BH, 'Learnable Prototypes', 'Class Memory', C_LOSS, C_LOSS_BD)
    # Proto to PA-DTS
    ortho_arrow(x_proto - (BW+0.5)/2, y_proto, x_fusion + STEP_X - 0.5, Y_TRUNK + BH/2, color=C_LOSS_BD, ls=':', direction='hv')
    # Proto to PGAP
    ortho_arrow(x_proto - (BW+0.5)/2, y_proto - 0.2, x_gap, Y_TRUNK + BH/2, color=C_LOSS_BD, ls=':', direction='hv')

    # CE Loss
    draw_block(x_down, Y_LOSS, BW, BH, 'Cross-Entropy', 'Classification Loss', C_LOSS, C_LOSS_BD)
    arrow(x_down, Y_TRUNK - (BH-0.2)/2, x_down, Y_LOSS + BH/2)

    # SCTR Loss
    x_sctr = x_dpa
    draw_block(x_sctr, Y_LOSS, BW, BH, 'SCTR Loss', 'SupCon Regularization', C_LOSS, C_LOSS_BD)
    ortho_arrow(x_dpa, Y_TRUNK - BH/2, x_sctr, Y_LOSS + BH/2, color=C_LOSS_BD, ls=':', direction='vh')
    ortho_arrow(x_proto - 1.0, y_proto - BH/2, x_sctr - 1.0, Y_LOSS + BH/2, color=C_LOSS_BD, ls=':', direction='vh')

    # Ortho Loss
    x_ortho = x_sctr + STEP_X
    draw_block(x_ortho, Y_LOSS, BW, BH, 'Orthogonality Loss', 'Penalize overlap', C_LOSS, C_LOSS_BD)
    ortho_arrow(x_proto + 1.0, y_proto - BH/2, x_ortho, Y_LOSS + BH/2, color=C_LOSS_BD, ls=':', direction='vh')

    # EMA Update
    x_ema = x_ortho + STEP_X
    draw_block(x_ema, Y_LOSS, BW, BH, 'EMA Update', 'momentum 0.99', C_LOSS, C_LOSS_BD)
    ortho_arrow(x_dpa + BW/2, Y_TRUNK, x_ema, Y_LOSS + BH/2, color=C_LOSS_BD, ls='-.', direction='hv')
    # EMA up to proto
    ortho_arrow(x_ema + 0.5, Y_LOSS + BH/2, x_proto + (BW+0.5)/2, y_proto, color=C_LOSS_BD, ls='-.', direction='vh')

    # ================================================================
    # LEGEND
    # ================================================================
    legend_y = -5.0
    startX = 3.0
    items = [
        (C_CNN_BG, C_CNN_BORDER, 'CNN Backbone'),
        (C_VIT, C_VIT_BD, 'ViT Path'),
        (C_WAVELET, C_WAVELET_BD, 'Wavelet Modules'),
        (C_CBAM, C_CBAM_BD, 'Attention'),
        (C_NOVEL, C_NOVEL_BD, 'Novel Aggregation'),
        (C_LOSS, C_LOSS_BD, 'Loss & Prototypes')
    ]
    
    for i, (fc, ec, label) in enumerate(items):
        draw_block(startX + i * 5.5, legend_y, 0.8, 0.5, '', '', fc, ec, radius=0.1)
        ax.text(startX + 0.6 + i * 5.5, legend_y, label, ha='left', va='center', fontsize=9, color=C_DIM_TEXT)

    plt.savefig('wavecoatnet_architecture_landscape.png', dpi=300, bbox_inches='tight')
    plt.savefig('wavecoatnet_architecture_landscape.pdf', bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    draw_architecture()
