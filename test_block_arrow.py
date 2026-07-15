import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

fig, ax = plt.subplots(figsize=(5, 5))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)

def ortho_arrow(x1, y1, x2, y2, direction='hv'):
    color = 'blue'
    ls = '-'
    lw = 4
    if direction == 'hv':
        ax.plot([x1, x2], [y1, y1], color=color, ls=ls, lw=lw, solid_capstyle='projecting')
        a = FancyArrowPatch((x2, y1), (x2, y2), arrowstyle='simple,tail_width=4,head_width=12,head_length=12', 
                            facecolor=color, edgecolor=color)
        ax.add_patch(a)
    else:
        ax.plot([x1, x1], [y1, y2], color=color, ls=ls, lw=lw, solid_capstyle='projecting')
        a = FancyArrowPatch((x1, y2), (x2, y2), arrowstyle='simple,tail_width=4,head_width=12,head_length=12', 
                            facecolor=color, edgecolor=color)
        ax.add_patch(a)

ortho_arrow(1, 8, 4, 6, 'hv')
ortho_arrow(6, 8, 9, 6, 'vh')

plt.savefig('test_block_arrow.png')
