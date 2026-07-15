import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, ConnectionPatch

def draw_icml_architecture():
    # Ultra-wide landscape layout perfect for spanning \begin{figure*}
    fig, ax = plt.subplots(1, 1, figsize=(18, 9))
    
    # Coordinate system
    ax.set_xlim(0, 42)
    ax.set_ylim(0, 18)
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

    # ── Helper Functions ────────────────────────────────────────
    def draw_block(x, y, w, h, label, sublabel, fc, ec, fontsize=9, sublabel_size=7):
        box = FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle=f"round,pad=0.04,rounding_size=0.15",
            facecolor=fc, edgecolor=ec, linewidth=1.5, zorder=3
        )
        ax.add_patch(box)
        offset = 0.15 if sublabel else 0
        ax.text(x, y + offset, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=C_TEXT, zorder=4)
        if sublabel:
            ax.text(x, y - 0.25, sublabel, ha='center', va='center',
                    fontsize=sublabel_size, color=C_DIM_TEXT, fontstyle='italic', zorder=4)

    def draw_dashed_box(x, y, w, h, label, color):
        box = FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.1,rounding_size=0.3",
            facecolor=color, edgecolor=color, linewidth=1.5,
            alpha=0.1, linestyle='--', zorder=1
        )
        ax.add_patch(box)
        ax.text(x - w/2 + 0.2, y + h/2 - 0.4, label, ha='left', va='center',
                fontsize=9, fontweight='bold', color=color, zorder=5)

    def arrow(x1, y1, x2, y2, color=C_ARROW, style=None, lw=1.5,
              connectionstyle='arc3,rad=0', ls='-', zorder=2, rad=0.0):
        if rad != 0.0:
            connectionstyle = f'arc3,rad={rad}'
        a = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle='simple,tail_width=4,head_width=12,head_length=12',
            facecolor=color, edgecolor=color,
            linewidth=1.0, mutation_scale=1.0,
            connectionstyle=connectionstyle,
            linestyle=ls, zorder=zorder, alpha=0.85
        )
        ax.add_patch(a)

    def ortho_arrow(x1, y1, x2, y2, color=C_ARROW, ls='-', lw=1.5, direction='hv', zorder=2):
        shaft_lw = 4.0
        if direction == 'hv':
            ax.plot([x1, x2], [y1, y1], color=color, ls=ls, lw=shaft_lw, zorder=zorder, solid_capstyle='projecting', alpha=0.85)
            a = FancyArrowPatch((x2, y1), (x2, y2), arrowstyle='simple,tail_width=4,head_width=12,head_length=12', 
                                facecolor=color, edgecolor=color, linestyle=ls, zorder=zorder, mutation_scale=1.0, alpha=0.85)
            ax.add_patch(a)
        else:
            ax.plot([x1, x1], [y1, y2], color=color, ls=ls, lw=shaft_lw, zorder=zorder, solid_capstyle='projecting', alpha=0.85)
            a = FancyArrowPatch((x1, y2), (x2, y2), arrowstyle='simple,tail_width=4,head_width=12,head_length=12', 
                                facecolor=color, edgecolor=color, linestyle=ls, zorder=zorder, mutation_scale=1.0, alpha=0.85)
            ax.add_patch(a)

    def dim_label(x, y, text, fontsize=6.5, color=C_DIM_TEXT):
        ax.text(x, y, text, ha='center', va='center',
                fontsize=fontsize, color=color, zorder=5,
                fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.9))

    def callout_line(x1, y1, x2, y2, color):
        ax.plot([x1, x2], [y1, y2], color=color, linestyle=':', linewidth=1.5, alpha=0.6, zorder=0)

    # ── Constants ──────────────────────────────────────────────
    BW, BH = 2.4, 0.9
    Y_CNN = 15.5
    Y_TRUNK = 13.5
    Y_VIT = 11.5
    STEP = 2.8

    # ================================================================
    # MAIN PIPELINE (TOP HALF)
    # ================================================================
    x = 2.0
    draw_block(x, Y_TRUNK, BW, BH, 'Input Image', '224×224×3', C_INPUT, '#90CAF9')
    dim_label(x, Y_TRUNK - BH/2 - 0.2, 'B×3×224×224')
    arrow(x + BW/2, Y_TRUNK, x + STEP - BW/2, Y_TRUNK)
    x += STEP

    draw_block(x, Y_TRUNK, BW, BH, 'CNN Stem', 'ConvNeXt-T', C_CNN_BG, C_CNN_BORDER)
    arrow(x + BW/2, Y_TRUNK, x + STEP - BW/2, Y_TRUNK)
    x += STEP

    draw_block(x, Y_TRUNK, BW, BH, 'Stage 1', 'ConvNeXt × 3', C_CNN_BG, C_CNN_BORDER)
    dim_label(x, Y_TRUNK - BH/2 - 0.2, 'B×96×56×56')
    arrow(x + BW/2, Y_TRUNK, x + STEP - BW/2, Y_TRUNK)
    x_s1 = x
    x += STEP

    draw_block(x, Y_TRUNK, BW, BH, 'Stage 2', 'ConvNeXt × 3', C_CNN_BG, C_CNN_BORDER)
    dim_label(x, Y_TRUNK - BH/2 - 0.2, 'B×192×28×28')
    x_s2 = x

    # SPLIT LOGIC
    # Stage 2 connects upward to Stage 3 (CNN Path)
    x_cnn = x_s2 + STEP
    arrow(x_s2 + BW/2, Y_TRUNK, x_cnn - BW/2, Y_CNN, rad=0.2)
    
    # CNN PATH (TOP)
    draw_block(x_cnn, Y_CNN, BW, BH, 'Stage 3', 'ConvNeXt × 9', C_CNN_BG, C_CNN_BORDER)
    dim_label(x_cnn, Y_CNN - BH/2 - 0.2, 'B×384×14×14')
    arrow(x_cnn + BW/2, Y_CNN, x_cnn + STEP - BW/2, Y_CNN)
    x_cnn += STEP

    draw_block(x_cnn, Y_CNN, BW, BH, 'CBAM', 'Attention', C_CBAM, C_CBAM_BD)
    arrow(x_cnn + BW/2, Y_CNN, x_cnn + STEP - BW/2, Y_CNN)
    x_cnn += STEP

    draw_block(x_cnn, Y_CNN, BW, BH, 'Stage 4', 'ConvNeXt × 3', C_CNN_BG, C_CNN_BORDER)
    dim_label(x_cnn, Y_CNN - BH/2 - 0.2, 'B×768×7×7')
    arrow(x_cnn + BW/2, Y_CNN, x_cnn + STEP - BW/2, Y_CNN)
    x_cnn += STEP

    draw_block(x_cnn, Y_CNN, BW, BH, 'CBAM', 'Attention', C_CBAM, C_CBAM_BD)
    arrow(x_cnn + BW/2, Y_CNN, x_cnn + STEP - BW/2, Y_CNN)
    x_cnn += STEP

    draw_block(x_cnn, Y_CNN, BW, BH, 'Flatten', 'Transpose', '#ECEFF1', '#78909C')
    dim_label(x_cnn, Y_CNN - BH/2 - 0.2, 'B×49×768')
    x_end_cnn = x_cnn

    # VIT PATH (BOTTOM)
    x_vit = x_s2 + STEP
    draw_block(x_vit, Y_VIT, BW, BH, 'WG-FDCA', 'See Callout A', C_WAVELET, C_WAVELET_BD)
    dim_label(x_vit, Y_VIT - BH/2 - 0.2, 'B×784×192')
    arrow(x_vit + BW/2, Y_VIT, x_vit + STEP - BW/2, Y_VIT)
    
    # Arrows from Stage 1 and 2 to WG-FDCA
    arrow(x_s1, Y_TRUNK - BH/2, x_vit - BW/4, Y_VIT + BH/2, color=C_WAVELET_BD, ls='--', rad=0.15)
    arrow(x_s2, Y_TRUNK - BH/2, x_vit + BW/4, Y_VIT + BH/2, color=C_WAVELET_BD, ls='--', rad=-0.15)
    x_wgfdca = x_vit
    x_vit += STEP

    draw_block(x_vit, Y_VIT, BW, BH, 'Pos Embed', 'Add', C_VIT, C_VIT_BD)
    arrow(x_vit + BW/2, Y_VIT, x_vit + STEP - BW/2, Y_VIT)
    x_vit += STEP

    draw_block(x_vit, Y_VIT, BW, BH, 'ViT Blocks', 'MHSA+FFN × 2', C_VIT, C_VIT_BD)
    arrow(x_vit + BW/2, Y_VIT, x_vit + STEP - BW/2, Y_VIT)
    x_vit += STEP

    draw_block(x_vit, Y_VIT, BW, BH, 'Project', '192 → 768', C_VIT, C_VIT_BD)
    arrow(x_vit + BW/2, Y_VIT, x_vit + STEP - BW/2, Y_VIT)
    x_vit += STEP

    draw_block(x_vit, Y_VIT, BW, BH, 'Adaptive Pool', '28x28 → 7x7', C_VIT, C_VIT_BD)
    dim_label(x_vit, Y_VIT - BH/2 - 0.2, 'B×49×768')
    x_end_vit = x_vit

    # FUSION
    x_fus = max(x_end_cnn, x_end_vit) + 2.0
    draw_block(x_fus, Y_TRUNK, 0.8, 0.8, '⊕', '', C_FUSION, C_FUSION_BD, fontsize=12)
    ortho_arrow(x_end_cnn + BW/2, Y_CNN, x_fus, Y_TRUNK + 0.4, direction='hv', color=C_FUSION_BD)
    ortho_arrow(x_end_vit + BW/2, Y_VIT, x_fus, Y_TRUNK - 0.4, direction='hv', color=C_FUSION_BD)

    # DOWNSTREAM
    x_down = x_fus + 1.8
    draw_block(x_down, Y_TRUNK, BW, BH, 'PA-DTS', 'See Callout B', C_NOVEL, C_NOVEL_BD)
    arrow(x_fus + 0.4, Y_TRUNK, x_down - BW/2, Y_TRUNK)
    x_padts = x_down

    x_down += STEP
    draw_block(x_down, Y_TRUNK, BW, BH, 'PGAP', 'Attention Pool', C_NOVEL, C_NOVEL_BD)
    arrow(x_down - STEP + BW/2, Y_TRUNK, x_down - BW/2, Y_TRUNK)
    x_pgap = x_down
    
    # GAP Bypass
    y_gap = Y_TRUNK + 2.0
    draw_block(x_down, y_gap, BW, BH, 'GAP', 'Global Pool', '#ECEFF1', '#78909C')
    ortho_arrow(x_fus + 0.9, Y_TRUNK, x_down - BW/2, y_gap, direction='vh', color='#78909C', ls='--')

    x_down += STEP
    draw_block(x_down, Y_TRUNK, BW, BH, 'DPA', 'Dual-Path Aggr', C_NOVEL, C_NOVEL_BD)
    arrow(x_down - STEP + BW/2, Y_TRUNK, x_down - BW/2, Y_TRUNK)
    ortho_arrow(x_down - STEP + BW/2, y_gap, x_down, Y_TRUNK + BH/2, direction='hv', color='#78909C', ls='--')
    dim_label(x_down, Y_TRUNK - BH/2 - 0.2, 'B×768 (Embed)')
    x_dpa = x_down

    x_down += STEP
    draw_block(x_down, Y_TRUNK, BW, BH, 'Classifier', 'LN→Drop→Linear', C_OUTPUT, C_OUTPUT_BD)
    arrow(x_down - STEP + BW/2, Y_TRUNK, x_down - BW/2, Y_TRUNK)

    x_down += STEP - 0.4
    draw_block(x_down, Y_TRUNK, BW-0.4, BH-0.2, 'Logits', '5 Classes', C_OUTPUT, C_OUTPUT_BD)
    arrow(x_down - STEP + 0.4 + BW/2, Y_TRUNK, x_down - (BW-0.4)/2, Y_TRUNK)
    
    x_down += STEP - 0.6
    draw_block(x_down, Y_TRUNK, BW-0.6, BH-0.2, 'CE Loss', '', C_LOSS, C_LOSS_BD)
    arrow(x_down - STEP + 0.6 + (BW-0.4)/2, Y_TRUNK, x_down - (BW-0.6)/2, Y_TRUNK)

    # ================================================================
    # CALLOUT A: WG-FDCA
    # ================================================================
    box_A_w, box_A_h = 13.0, 7.0
    box_A_x, box_A_y = 8.0, 4.5
    draw_dashed_box(box_A_x, box_A_y, box_A_w, box_A_h, 'Callout A: Wavelet-Guided Frequency-Decomposed Cross-Attention (WG-FDCA)', C_WAVELET_BD)
    
    # Connecting lines from main block to callout
    callout_line(x_wgfdca - BW/2, Y_VIT - BH/2, box_A_x - box_A_w/2, box_A_y + box_A_h/2, C_WAVELET_BD)
    callout_line(x_wgfdca + BW/2, Y_VIT - BH/2, box_A_x + box_A_w/2, box_A_y + box_A_h/2, C_WAVELET_BD)

    c_x = box_A_x - 3.5
    c_y = box_A_y + 1.5
    draw_block(c_x, c_y, BW+0.4, BH, '2D Haar DWT', 'Sub-band Decomp', C_WAVELET, C_WAVELET_BD)
    
    # LL Path
    arrow(c_x + (BW+0.4)/2, c_y + 0.3, c_x + 3.0, c_y + 0.3, color=C_WAVELET_BD)
    ax.text(c_x + 1.8, c_y + 0.55, 'LL (Structure)', ha='center', va='center', fontsize=7, color=C_WAVELET_BD, fontweight='bold')
    # High Freq Path
    arrow(c_x + (BW+0.4)/2, c_y - 0.3, c_x + 3.0, c_y - 0.3, color=C_WAVELET_BD)
    ax.text(c_x + 1.8, c_y - 0.55, 'LH, HL, HH (Texture)', ha='center', va='center', fontsize=7, color=C_WAVELET_BD, fontweight='bold')

    # Dual CA
    c_x2 = c_x + 4.5
    draw_block(c_x2, c_y, BW+0.4, BH+0.4, 'Dual Cross-Attn', 'Parallel Q-K-V', C_WAVELET, C_WAVELET_BD)
    
    # Freq Gate
    arrow(c_x2, c_y - (BH+0.4)/2, c_x2, c_y - 2.0, color=C_WAVELET_BD)
    draw_block(c_x2, c_y - 2.5, BW+0.4, BH, 'Freq Gate', 'Adaptive Balancing', C_WAVELET, C_WAVELET_BD)
    
    # FFN
    arrow(c_x2 + (BW+0.4)/2, c_y - 2.5, c_x2 + 3.3, c_y - 2.5, color=C_WAVELET_BD)
    draw_block(c_x2 + 4.5, c_y - 2.5, BW, BH, 'FFN', 'Feed Forward', C_WAVELET, C_WAVELET_BD)

    # Input lines to DWT and CA inside callout
    ax.text(box_A_x - box_A_w/2 + 0.5, c_y, 'from Stage 1', ha='left', va='center', fontsize=7, color=C_DIM_TEXT)
    arrow(box_A_x - box_A_w/2 + 1.8, c_y, c_x - (BW+0.4)/2, c_y, color=C_WAVELET_BD, ls='--')
    
    ax.text(c_x2, c_y + 1.6, 'from Stage 2 (Queries)', ha='center', va='center', fontsize=7, color=C_DIM_TEXT)
    arrow(c_x2, c_y + 1.4, c_x2, c_y + (BH+0.4)/2, color=C_WAVELET_BD, ls='--')

    # Output line
    arrow(c_x2 + 4.5 + BW/2, c_y - 2.5, box_A_x + box_A_w/2 - 0.5, c_y - 2.5, color=C_WAVELET_BD)
    ax.text(box_A_x + box_A_w/2 - 0.4, c_y - 2.5, 'to Pos Embed', ha='right', va='bottom', fontsize=7, color=C_DIM_TEXT)

    # ================================================================
    # CALLOUT B: PROTOTYPE REGULARIZATION
    # ================================================================
    box_B_w, box_B_h = 18.0, 7.0
    box_B_x, box_B_y = 28.0, 4.5
    draw_dashed_box(box_B_x, box_B_y, box_B_w, box_B_h, 'Callout B: Prototype-Anchored Regularization & Aggregation', C_LOSS_BD)

    callout_line(x_padts, Y_TRUNK - BH/2, box_B_x - box_B_w/2, box_B_y + box_B_h/2, C_LOSS_BD)
    callout_line(x_dpa, Y_TRUNK - BH/2, box_B_x + box_B_w/2, box_B_y + box_B_h/2, C_LOSS_BD)

    # Prototypes in center
    p_x, p_y = box_B_x - 1.5, box_B_y + 1.5
    draw_block(p_x, p_y, BW+1.0, BH, 'Learnable Prototypes', 'Class Memory [5 × 768]', C_LOSS, C_LOSS_BD)

    # SCTR & Ortho
    s_x = p_x - 4.5
    o_x = p_x + 4.5
    draw_block(s_x, p_y - 2.5, BW+0.5, BH, 'SCTR Loss', 'Contrastive Reg', C_LOSS, C_LOSS_BD)
    draw_block(o_x, p_y - 2.5, BW+0.5, BH, 'Ortho Loss', 'Penalty', C_LOSS, C_LOSS_BD)
    
    # EMA Update
    e_x = p_x + 6.0
    e_y = p_y
    draw_block(e_x, e_y, BW+0.5, BH, 'EMA Update', 'Momentum 0.99', C_LOSS, C_LOSS_BD)

    # Wiring inside Callout B
    # Prototypes to Ortho
    arrow(p_x, p_y - BH/2, o_x, p_y - 2.5 + BH/2, color=C_LOSS_BD, ls=':')
    # Prototypes to SCTR
    arrow(p_x - 1.0, p_y - BH/2, s_x + 1.0, p_y - 2.5 + BH/2, color=C_LOSS_BD, ls=':')
    
    # DPA embeddings drop into SCTR and EMA
    ax.text(s_x - 1.5, p_y, 'DPA Embeddings\n(from pipeline)', ha='center', va='center', fontsize=7, color=C_DIM_TEXT)
    arrow(s_x - 1.5, p_y - 0.4, s_x - 1.0, p_y - 2.5 + BH/2, color=C_LOSS_BD, ls=':', rad=0.2)
    arrow(e_x + 2.0, p_y + 2.0, e_x, e_y + BH/2, color=C_LOSS_BD, ls='-.', rad=0.3)
    ax.text(e_x + 2.0, p_y + 2.2, 'DPA Embeddings', ha='center', va='center', fontsize=7, color=C_DIM_TEXT)

    # EMA updates Prototypes
    arrow(e_x - (BW+0.5)/2, e_y, p_x + (BW+1.0)/2, p_y, color=C_LOSS_BD, ls='-.')

    # Prototypes up to PA-DTS and PGAP
    arrow(p_x - 0.5, p_y + BH/2, p_x - 0.5, box_B_y + box_B_h/2 - 0.2, color=C_NOVEL_BD, ls=':')
    ax.text(p_x - 0.6, p_y + 1.5, 'to PA-DTS', ha='right', va='center', fontsize=7, color=C_NOVEL_BD)
    
    arrow(p_x + 0.5, p_y + BH/2, p_x + 0.5, box_B_y + box_B_h/2 - 0.2, color=C_NOVEL_BD, ls=':')
    ax.text(p_x + 0.6, p_y + 1.5, 'to PGAP', ha='left', va='center', fontsize=7, color=C_NOVEL_BD)

    plt.savefig('wavecoatnet_architecture_icml.png', dpi=300, bbox_inches='tight')
    plt.savefig('wavecoatnet_architecture_icml.pdf', bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    draw_icml_architecture()
