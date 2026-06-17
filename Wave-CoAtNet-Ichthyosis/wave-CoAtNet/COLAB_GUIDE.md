# WaveCoAtNet: Complete Colab Execution Guide

> Q1 Journal Paper -- Full experimental pipeline across 3 accounts.

---

## CRITICAL RULES

1. **NEVER** use `rm -rf` on the Drive folder
2. **NEVER** re-clone if files already exist -- use `git pull` instead
3. **ALWAYS** work from the Drive path, not local Colab `/content/`
4. All outputs save to Drive automatically and survive runtime resets

---

## ACCOUNT 1: Train All 12 Models + Figures + Strong Accept Metrics

### Cell 1: Setup

```python
from google.colab import drive
drive.mount('/content/drive')

import os
WORK = '/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet'

if not os.path.exists(WORK):
    os.makedirs('/content/drive/MyDrive/WaveCoAtNet_experiments', exist_ok=True)
    %cd /content/drive/MyDrive/WaveCoAtNet_experiments
    !git clone https://github.com/Cyrax321/wave-coAtNet.git
else:
    %cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet
    !git pull origin main

%cd {WORK}
!pip install -q -r requirements.txt

import torch
assert torch.cuda.is_available(), "No GPU. Go to Runtime > Change runtime type > GPU"
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"CWD: {os.getcwd()}")
```

### Cell 2: Train WaveCoAtNet (~30 min)

```python
%cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet
!python proposed/train_wavecoatnet.py

import os
for f in ['best_wavecoatnet.pth', 'wavecoatnet_y_pred.npy', 'wavecoatnet_y_true.npy']:
    print(f"  {'OK' if os.path.exists(f) else 'MISSING'} {f}")
```

### Cell 3: Train 7 Pretrained Baselines (~2.5h)

```python
%cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet

for name, script in [
    ("EfficientNet-B0 (Pretrained)", "baselines/pretrained/train_efficientnet_b0.py"),
    ("Swin-T (Pretrained)",          "baselines/pretrained/train_swin_t.py"),
    ("ViT-B/16 (Pretrained)",        "baselines/pretrained/train_vit_b16.py"),
    ("CoAtNet (Pretrained)",          "baselines/pretrained/train_coatnet.py"),
    ("GFT",                           "baselines/pretrained/train_gft.py"),
    ("BiomedCLIP",                    "baselines/pretrained/train_biomedclip.py"),
    ("DINOv2",                        "baselines/pretrained/train_dinov2.py"),
]:
    print(f"\n{'='*60}\n  Training: {name}\n{'='*60}")
    !python {script}

import os
preds = sorted([f for f in os.listdir('.') if f.endswith('_y_pred.npy')])
print(f"\nPrediction files: {len(preds)}/8")
for p in preds: print(f"  {p}")
```

### Cell 4: Train 4 Scratch Baselines (~1h)

```python
%cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet

for name, script in [
    ("CNN (Scratch)",              "baselines/scratch/train_cnn.py"),
    ("EfficientNet-B0 (Scratch)",  "baselines/scratch/train_efficientnet_b0.py"),
    ("Swin-T (Scratch)",           "baselines/scratch/train_swin_t.py"),
    ("ViT (Scratch)",              "baselines/scratch/train_vit.py"),
]:
    print(f"\n{'='*60}\n  Training: {name}\n{'='*60}")
    !python {script}

import os
preds = sorted([f for f in os.listdir('.') if f.endswith('_y_pred.npy') and not f.startswith('ablation')])
print(f"\nTotal prediction files: {len(preds)}/12")
for p in preds: print(f"  [OK] {p}")
```

### Cell 5: Grad-CAM (~10 min)

```python
%cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet
!python evaluation/gradcam.py --checkpoint best_wavecoatnet.pth

import os
if os.path.exists('gradcam'):
    files = os.listdir('gradcam')
    print(f"Grad-CAM: {len(files)} files generated")
    for f in sorted(files): print(f"  {f}")
```

### Cell 6: All 13 Publication Figures (~5 min)

```python
%cd /content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet
!python evaluation/generate_visualizations.py

import os
if os.path.exists('figures'):
    files = sorted(os.listdir('figures'))
    print(f"\nFigures generated: {len(files)}")
    for f in files: print(f"  figures/{f}")
```

### Cell 7: View All Figures

```python
from IPython.display import display, Image
import os
os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')

if os.path.exists('gradcam/gradcam_grid.png'):
    print("--- Grad-CAM Grid ---")
    display(Image(filename='gradcam/gradcam_grid.png', width=800))

if os.path.exists('figures'):
    for f in sorted(os.listdir('figures')):
        if f.endswith('.png'):
            print(f"\n--- {f} ---")
            display(Image(filename=f'figures/{f}', width=700))
```

### Cell 8: Strong Accept Metrics

```python
import os, csv, time
import numpy as np
import torch
import torch.nn as nn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
    recall_score, cohen_kappa_score, confusion_matrix, roc_auc_score)
from sklearn.preprocessing import label_binarize
from IPython.display import display, Image

os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')
os.makedirs('figures', exist_ok=True)

class_names = ['Harlequin ichthyosis', 'Healthy skin', 'Ichthyosis vulgaris',
               'Lamellar ichthyosis', 'Netherton syndrome']
n_classes = len(class_names)

MODEL_REGISTRY = [
    ('WaveCoAtNet (Proposed)',      'wavecoatnet'),
    ('ConvNeXt-Tiny (CoAtNet)',     'coatnet'),
    ('EfficientNet-B0 (PT)',        'efficientnet_pretrained'),
    ('EfficientNet-B0 (Scratch)',   'efficientnet_scratch'),
    ('Swin-T (PT)',                 'swin_pretrained'),
    ('Swin-T (Scratch)',            'swin_scratch'),
    ('ViT-B/16 (PT)',               'vit_pretrained'),
    ('ViT (Scratch)',               'vit_scratch'),
    ('GFT',                         'gft'),
    ('BiomedCLIP',                  'biomedclip'),
    ('DINOv2',                      'dinov2'),
    ('CNN (Scratch)',                'cnn'),
]

results = []
for label, prefix in MODEL_REGISTRY:
    yt_f = f'{prefix}_y_true.npy'
    yp_f = f'{prefix}_y_pred.npy'
    if os.path.exists(yt_f) and os.path.exists(yp_f):
        results.append((label, prefix, np.load(yt_f), np.load(yp_f)))
print(f"Loaded {len(results)}/12 models\n")

# ── 1. Comprehensive Table ──
print("="*100)
print("  TABLE 2: COMPREHENSIVE MODEL COMPARISON")
print("="*100)
print(f"{'Model':<28s} {'Acc%':>7s} {'Prec%':>7s} {'Rec%':>7s} {'F1%':>7s} {'WF1%':>7s} {'Kappa':>7s} {'AUC':>7s}")
print("-"*100)

table_data = []
for label, prefix, yt, yp in results:
    acc = accuracy_score(yt, yp) * 100
    prec = precision_score(yt, yp, average='macro', zero_division=0) * 100
    rec = recall_score(yt, yp, average='macro', zero_division=0) * 100
    f1 = f1_score(yt, yp, average='macro', zero_division=0) * 100
    wf1 = f1_score(yt, yp, average='weighted', zero_division=0) * 100
    kappa = cohen_kappa_score(yt, yp)
    yt_bin = label_binarize(yt, classes=range(n_classes))
    yp_bin = label_binarize(yp, classes=range(n_classes))
    try:
        auc_val = roc_auc_score(yt_bin, yp_bin, average='macro')
    except:
        auc_val = 0
    print(f"{label:<28s} {acc:>6.2f} {prec:>6.2f} {rec:>6.2f} {f1:>6.2f} {wf1:>6.2f} {kappa:>6.4f} {auc_val:>6.4f}")
    table_data.append({'Model': label, 'Accuracy': acc, 'Precision': prec, 'Recall': rec,
                       'Macro_F1': f1, 'Weighted_F1': wf1, 'Kappa': kappa, 'AUC': auc_val})

with open('figures/full_comparison_table.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(table_data[0].keys()))
    writer.writeheader()
    for row in sorted(table_data, key=lambda x: x['Accuracy'], reverse=True):
        writer.writerow({k: f'{v:.4f}' if isinstance(v, float) else v for k, v in row.items()})
print("\nSaved: figures/full_comparison_table.csv")

# ── 2. Sensitivity & Specificity Heatmap ──
sens_matrix, spec_matrix, model_labels = [], [], []
for label, prefix, yt, yp in results:
    cm = confusion_matrix(yt, yp, labels=range(n_classes))
    sens_row, spec_row = [], []
    for i in range(n_classes):
        tp = cm[i, i]; fn = cm[i, :].sum() - tp
        fp = cm[:, i].sum() - tp; tn = cm.sum() - tp - fn - fp
        sens_row.append(tp / (tp + fn) if (tp + fn) > 0 else 0)
        spec_row.append(tn / (tn + fp) if (tn + fp) > 0 else 0)
    sens_matrix.append(sens_row)
    spec_matrix.append(spec_row)
    model_labels.append(label)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, 8))
sns.heatmap(np.array(sens_matrix)*100, annot=True, fmt='.1f', cmap='YlOrRd',
            xticklabels=[c[:15] for c in class_names], yticklabels=model_labels,
            annot_kws={"size": 8}, linewidths=0.5, ax=ax1, vmin=0, vmax=100,
            cbar_kws={'label': 'Sensitivity (%)'})
ax1.set_title('Sensitivity (Recall) per Class', fontsize=12, fontweight='bold')
plt.setp(ax1.get_xticklabels(), rotation=25, ha='right')

sns.heatmap(np.array(spec_matrix)*100, annot=True, fmt='.1f', cmap='YlGnBu',
            xticklabels=[c[:15] for c in class_names], yticklabels=model_labels,
            annot_kws={"size": 8}, linewidths=0.5, ax=ax2, vmin=80, vmax=100,
            cbar_kws={'label': 'Specificity (%)'})
ax2.set_title('Specificity per Class', fontsize=12, fontweight='bold')
plt.setp(ax2.get_xticklabels(), rotation=25, ha='right')
plt.tight_layout()
plt.savefig('figures/sensitivity_specificity_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/sensitivity_specificity_heatmap.png")

# ── 3. Bootstrap 95% CI ──
print(f"\n{'='*80}")
print("  95% BOOTSTRAP CONFIDENCE INTERVALS")
print(f"{'='*80}")

ci_data = []
for label, prefix, yt, yp in results:
    np.random.seed(42)
    boot_accs = [accuracy_score(yt[idx], yp[idx]) * 100
                 for idx in (np.random.choice(len(yt), len(yt), replace=True) for _ in range(2000))]
    ci_lo, ci_hi = np.percentile(boot_accs, [2.5, 97.5])
    mean_acc = np.mean(boot_accs)
    print(f"  {label:<28s} {mean_acc:>6.2f}% [{ci_lo:.2f}%, {ci_hi:.2f}%]")
    ci_data.append((label, mean_acc, ci_lo, ci_hi))

fig, ax = plt.subplots(figsize=(10, 8))
y_pos = np.arange(len(ci_data))
means = [c[1] for c in ci_data]
ci_los = [c[1] - c[2] for c in ci_data]
ci_his = [c[3] - c[1] for c in ci_data]
colors = ['#2563EB' if 'Proposed' in c[0] else '#6B7280' for c in ci_data]

ax.barh(y_pos, means, xerr=[ci_los, ci_his], height=0.6, color=colors,
        alpha=0.8, capsize=4, ecolor='#374151')
ax.set_yticks(y_pos)
ax.set_yticklabels([c[0] for c in ci_data], fontsize=9)
ax.set_xlabel('Test Accuracy (%)', fontsize=11)
ax.set_title('Model Comparison with 95% Bootstrap Confidence Intervals', fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
for i, (label, mean, lo, hi) in enumerate(ci_data):
    ax.text(mean + ci_his[i] + 0.5, i, f'{mean:.1f}%', va='center', fontsize=8, fontweight='bold')
plt.tight_layout()
plt.savefig('figures/confidence_intervals_forest.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/confidence_intervals_forest.png")

# ── 4. Inference Time ──
print(f"\n{'='*80}")
print("  INFERENCE TIME COMPARISON")
print(f"{'='*80}")

from torchvision import models
from timm import create_model

dummy = torch.randn(1, 3, 224, 224).cuda()

inference_models = {
    'EfficientNet-B0': lambda: models.efficientnet_b0(num_classes=5),
    'Swin-T': lambda: create_model('swin_tiny_patch4_window7_224', num_classes=5),
    'ViT-B/16': lambda: create_model('vit_base_patch16_224', num_classes=5),
    'ConvNeXt-Tiny': lambda: create_model('convnext_tiny', num_classes=5),
    'CNN (3-layer)': lambda: nn.Sequential(
        nn.Conv2d(3,32,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(32,64,3,padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(64,128,3,padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1),
        nn.Flatten(), nn.Linear(128, 5)),
}

timing_results = []
print(f"{'Model':<20s} {'Time (ms)':>12s} {'FPS':>8s} {'Params (M)':>12s}")
print("-"*55)

# WaveCoAtNet first
try:
    import sys
    sys.path.insert(0, 'proposed')
    from train_wavecoatnet import WaveCoAtNet
    m = WaveCoAtNet(num_classes=5).cuda().eval()
    if os.path.exists('best_wavecoatnet.pth'):
        m.load_state_dict(torch.load('best_wavecoatnet.pth', map_location='cuda', weights_only=True))
    params = sum(p.numel() for p in m.parameters()) / 1e6
    with torch.no_grad():
        for _ in range(10): m(dummy)
    times = []
    with torch.no_grad():
        for _ in range(100):
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            m(dummy)
            torch.cuda.synchronize()
            times.append((time.perf_counter() - t0) * 1000)
    mean_t = np.mean(times)
    print(f"{'WaveCoAtNet':<20s} {mean_t:>10.2f}ms {1000/mean_t:>7.1f} {params:>10.1f}M")
    timing_results.append({'model': 'WaveCoAtNet', 'time_ms': mean_t, 'fps': 1000/mean_t, 'params_M': params})
    del m; torch.cuda.empty_cache()
except Exception as e:
    print(f"WaveCoAtNet ERROR: {e}")

for name, builder in inference_models.items():
    try:
        m = builder().cuda().eval()
        params = sum(p.numel() for p in m.parameters()) / 1e6
        with torch.no_grad():
            for _ in range(10): m(dummy)
        times = []
        with torch.no_grad():
            for _ in range(100):
                torch.cuda.synchronize()
                t0 = time.perf_counter()
                m(dummy)
                torch.cuda.synchronize()
                times.append((time.perf_counter() - t0) * 1000)
        mean_t = np.mean(times)
        print(f"{name:<20s} {mean_t:>10.2f}ms {1000/mean_t:>7.1f} {params:>10.1f}M")
        timing_results.append({'model': name, 'time_ms': mean_t, 'fps': 1000/mean_t, 'params_M': params})
        del m; torch.cuda.empty_cache()
    except Exception as e:
        print(f"{name:<20s} ERROR: {e}")

if timing_results:
    with open('figures/inference_timing.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['model','time_ms','fps','params_M'])
        writer.writeheader()
        writer.writerows(timing_results)

    fig, ax = plt.subplots(figsize=(10, 6))
    names = [r['model'] for r in timing_results]
    times_ms = [r['time_ms'] for r in timing_results]
    colors = ['#2563EB' if 'Wave' in n else '#6B7280' for n in names]
    bars = ax.barh(names, times_ms, color=colors, alpha=0.85)
    for bar, t in zip(bars, times_ms):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f'{t:.1f}ms', va='center', fontsize=9, fontweight='bold')
    ax.set_xlabel('Inference Time (ms)', fontsize=11)
    ax.set_title('Single Image Inference Time (GPU)', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.savefig('figures/inference_timing_bar.png', dpi=300)
    plt.close()
    print("Saved: figures/inference_timing_bar.png")

# ── 5. GFLOPs ──
!pip install -q fvcore
from fvcore.nn import FlopCountAnalysis

print(f"\n{'='*80}")
print("  GFLOPs COMPARISON")
print(f"{'='*80}")
print(f"{'Model':<20s} {'GFLOPs':>10s} {'Params (M)':>12s}")
print("-"*45)

try:
    m = WaveCoAtNet(num_classes=5).cuda().eval()
    flops = FlopCountAnalysis(m, dummy).total() / 1e9
    params = sum(p.numel() for p in m.parameters()) / 1e6
    print(f"{'WaveCoAtNet':<20s} {flops:>9.2f} {params:>10.1f}M")
    del m; torch.cuda.empty_cache()
except Exception as e:
    print(f"WaveCoAtNet GFLOPs ERROR: {e}")

for name, builder in inference_models.items():
    try:
        m = builder().cuda().eval()
        flops = FlopCountAnalysis(m, dummy).total() / 1e9
        params = sum(p.numel() for p in m.parameters()) / 1e6
        print(f"{name:<20s} {flops:>9.2f} {params:>10.1f}M")
        del m; torch.cuda.empty_cache()
    except Exception as e:
        print(f"{name:<20s} ERROR: {e}")

# ── 6. Display new figures ──
for f in ['figures/sensitivity_specificity_heatmap.png',
          'figures/confidence_intervals_forest.png',
          'figures/inference_timing_bar.png']:
    if os.path.exists(f):
        print(f"\n--- {os.path.basename(f)} ---")
        display(Image(filename=f, width=700))

# ── 7. Training convergence curves ──
print(f"\n{'='*80}")
print("  TRAINING CONVERGENCE CURVES")
print(f"{'='*80}")
for suffix in ['loss_curves', 'acc_curves']:
    files = sorted([f for f in os.listdir('.') if f.endswith(f'{suffix}.png')])
    if files:
        for f in files:
            print(f"\n--- {f} ---")
            display(Image(filename=f, width=500))

print(f"\n{'='*60}")
print("  ALL STRONG ACCEPT METRICS EXTRACTED")
print(f"{'='*60}")
```

### Cell 9: Extra A* Paper Figures

```python
import os, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
    recall_score, cohen_kappa_score, roc_auc_score, classification_report)
from sklearn.preprocessing import label_binarize
from IPython.display import display, Image

os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')
os.makedirs('figures', exist_ok=True)

class_names = ['Harlequin ichthyosis', 'Healthy skin', 'Ichthyosis vulgaris',
               'Lamellar ichthyosis', 'Netherton syndrome']
n_classes = len(class_names)

MODEL_REGISTRY = [
    ('WaveCoAtNet (Proposed)',      'wavecoatnet'),
    ('ConvNeXt-Tiny (CoAtNet)',     'coatnet'),
    ('EfficientNet-B0 (PT)',        'efficientnet_pretrained'),
    ('EfficientNet-B0 (Scratch)',   'efficientnet_scratch'),
    ('Swin-T (PT)',                 'swin_pretrained'),
    ('Swin-T (Scratch)',            'swin_scratch'),
    ('ViT-B/16 (PT)',               'vit_pretrained'),
    ('ViT (Scratch)',               'vit_scratch'),
    ('GFT',                         'gft'),
    ('BiomedCLIP',                  'biomedclip'),
    ('DINOv2',                      'dinov2'),
    ('CNN (Scratch)',                'cnn'),
]

results = []
for label, prefix in MODEL_REGISTRY:
    yt_f = f'{prefix}_y_true.npy'
    yp_f = f'{prefix}_y_pred.npy'
    if os.path.exists(yt_f) and os.path.exists(yp_f):
        results.append((label, prefix, np.load(yt_f), np.load(yp_f)))
print(f"Loaded {len(results)}/12 models\n")

# ── 1. Radar/Spider Chart: Proposed vs Top-3 Baselines ──
print("="*60)
print("  RADAR CHART: Proposed vs Top-3 Baselines")
print("="*60)

model_scores = []
for label, prefix, yt, yp in results:
    acc = accuracy_score(yt, yp) * 100
    prec = precision_score(yt, yp, average='macro', zero_division=0) * 100
    rec = recall_score(yt, yp, average='macro', zero_division=0) * 100
    f1 = f1_score(yt, yp, average='macro', zero_division=0) * 100
    kappa = cohen_kappa_score(yt, yp) * 100
    model_scores.append((label, prefix, [acc, prec, rec, f1, kappa]))

# Sort by accuracy and pick proposed + top-3 baselines
proposed = [s for s in model_scores if s[1] == 'wavecoatnet']
baselines_sorted = sorted([s for s in model_scores if s[1] != 'wavecoatnet'], key=lambda x: x[2][0], reverse=True)
radar_models = proposed + baselines_sorted[:3]

categories = ['Accuracy', 'Precision', 'Recall', 'Macro F1', "Cohen's Kappa"]
N_cat = len(categories)
angles = np.linspace(0, 2 * np.pi, N_cat, endpoint=False).tolist()
angles += angles[:1]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
radar_colors = ['#2563EB', '#DC2626', '#16A34A', '#D97706']
for i, (label, prefix, scores) in enumerate(radar_models):
    values = scores + scores[:1]
    ax.plot(angles, values, 'o-', linewidth=2, color=radar_colors[i], label=label, markersize=6)
    ax.fill(angles, values, alpha=0.1, color=radar_colors[i])
ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=10, fontweight='bold')
ax.set_ylim(0, 105)
ax.set_title('Performance Comparison: Proposed vs Top-3 Baselines', fontsize=13, fontweight='bold', pad=20)
ax.legend(loc='lower right', bbox_to_anchor=(1.3, 0), fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('figures/radar_chart_comparison.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/radar_chart_comparison.png")

# ── 2. Per-Class Precision-Recall Table as Image ──
print("\n--- Per-Class Precision-Recall Table ---")
table_rows = []
for label, prefix, yt, yp in results:
    report = classification_report(yt, yp, target_names=class_names, output_dict=True, zero_division=0)
    row = [label]
    for cls in class_names:
        row.extend([f"{report[cls]['precision']*100:.1f}", f"{report[cls]['recall']*100:.1f}", f"{report[cls]['f1-score']*100:.1f}"])
    table_rows.append(row)

headers = ['Model']
for cls in class_names:
    short = cls[:12] + '..' if len(cls) > 14 else cls
    headers.extend([f'{short}\nPrec', f'{short}\nRec', f'{short}\nF1'])

fig, ax = plt.subplots(figsize=(max(20, len(headers)*1.5), max(6, len(table_rows)*0.5+2)))
ax.axis('off')
table = ax.table(cellText=table_rows, colLabels=headers, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(6)
table.scale(1, 1.4)
for j in range(len(headers)):
    cell = table[0, j]
    cell.set_facecolor('#2563EB')
    cell.set_text_props(color='white', fontweight='bold', fontsize=6)
for i, row in enumerate(table_rows):
    is_proposed = 'Proposed' in row[0]
    for j in range(len(headers)):
        cell = table[i+1, j]
        if is_proposed:
            cell.set_facecolor('#DBEAFE')
            cell.set_text_props(fontweight='bold')
        elif i % 2 == 0:
            cell.set_facecolor('#F9FAFB')
ax.set_title('Per-Class Precision, Recall, F1 Scores', fontsize=14, fontweight='bold', pad=20)
plt.tight_layout()
plt.savefig('figures/per_class_precision_recall_table.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/per_class_precision_recall_table.png")

# ── 3. Training Convergence Overlay (all models on one plot) ──
print("\n--- Training Convergence Overlay ---")
conv_files = sorted([f for f in os.listdir('.') if f.endswith('_acc_curves.png') or f.endswith('_loss_curves.png')])
if conv_files:
    fig, axes = plt.subplots(1, min(len(conv_files), 6), figsize=(min(len(conv_files), 6)*5, 5))
    if not hasattr(axes, '__len__'): axes = [axes]
    for i, cf in enumerate(conv_files[:6]):
        axes[i].imshow(plt.imread(cf))
        axes[i].axis('off')
        axes[i].set_title(cf.replace('_curves.png','').replace('_',' ').title(), fontsize=9)
    fig.suptitle('Training Convergence Curves (All Models)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('figures/training_convergence_overlay.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: figures/training_convergence_overlay.png")
else:
    print("  SKIP: No convergence curve PNGs found")

# ── 4. Cohen's Kappa Comparison Table ──
print("\n--- Cohen's Kappa Comparison ---")
kappa_data = []
for label, prefix, yt, yp in results:
    kappa = cohen_kappa_score(yt, yp)
    kappa_data.append((label, kappa))
kappa_data.sort(key=lambda x: x[1], reverse=True)

fig, ax = plt.subplots(figsize=(10, max(5, len(kappa_data)*0.5)))
names = [k[0] for k in kappa_data]
kappas = [k[1] for k in kappa_data]
colors = ['#2563EB' if 'Proposed' in n else '#6B7280' for n in names]
bars = ax.barh(names, kappas, color=colors, alpha=0.85)
for bar, kv in zip(bars, kappas):
    ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
            f'{kv:.4f}', va='center', fontsize=9, fontweight='bold')
ax.set_xlabel("Cohen's Kappa", fontsize=11)
ax.set_title("Cohen's Kappa Agreement Comparison", fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
ax.set_xlim(0, max(kappas) * 1.15)
plt.tight_layout()
plt.savefig('figures/cohens_kappa_comparison.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/cohens_kappa_comparison.png")

with open('figures/cohens_kappa_table.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Model', 'Kappa'])
    for name, kv in kappa_data:
        writer.writerow([name, f'{kv:.4f}'])
print("Saved: figures/cohens_kappa_table.csv")

# ── 5. AUC-ROC Macro Average Bar Chart ──
print("\n--- AUC-ROC Macro Average ---")
auc_data = []
for label, prefix, yt, yp in results:
    yt_bin = label_binarize(yt, classes=range(n_classes))
    yp_bin = label_binarize(yp, classes=range(n_classes))
    try:
        auc_val = roc_auc_score(yt_bin, yp_bin, average='macro')
    except:
        auc_val = 0
    auc_data.append((label, auc_val))
auc_data.sort(key=lambda x: x[1], reverse=True)

fig, ax = plt.subplots(figsize=(10, max(5, len(auc_data)*0.5)))
names = [a[0] for a in auc_data]
aucs = [a[1] for a in auc_data]
colors = ['#2563EB' if 'Proposed' in n else '#6B7280' for n in names]
bars = ax.barh(names, aucs, color=colors, alpha=0.85)
for bar, av in zip(bars, aucs):
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
            f'{av:.4f}', va='center', fontsize=9, fontweight='bold')
ax.set_xlabel('AUC-ROC (Macro Average)', fontsize=11)
ax.set_title('AUC-ROC Macro Average Comparison', fontsize=13, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
ax.set_xlim(0, max(aucs) * 1.1)
plt.tight_layout()
plt.savefig('figures/auc_roc_macro_bar.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/auc_roc_macro_bar.png")

# ── 6. LaTeX-Ready Table Export ──
print("\n--- LaTeX Table Export ---")
latex_lines = []
latex_lines.append(r'\begin{table}[htbp]')
latex_lines.append(r'\centering')
latex_lines.append(r'\caption{Comprehensive model comparison on the ichthyosis classification dataset.}')
latex_lines.append(r'\label{tab:results}')
latex_lines.append(r'\resizebox{\textwidth}{!}{%')
latex_lines.append(r'\begin{tabular}{lcccccc}')
latex_lines.append(r'\toprule')
latex_lines.append(r'Model & Acc (\%) & Prec (\%) & Rec (\%) & F1 (\%) & Kappa & AUC \\')
latex_lines.append(r'\midrule')

rows_for_latex = []
for label, prefix, yt, yp in results:
    acc = accuracy_score(yt, yp) * 100
    prec = precision_score(yt, yp, average='macro', zero_division=0) * 100
    rec = recall_score(yt, yp, average='macro', zero_division=0) * 100
    f1 = f1_score(yt, yp, average='macro', zero_division=0) * 100
    kappa = cohen_kappa_score(yt, yp)
    yt_bin = label_binarize(yt, classes=range(n_classes))
    yp_bin = label_binarize(yp, classes=range(n_classes))
    try:
        auc_val = roc_auc_score(yt_bin, yp_bin, average='macro')
    except:
        auc_val = 0
    rows_for_latex.append((label, acc, prec, rec, f1, kappa, auc_val))

rows_for_latex.sort(key=lambda x: x[1], reverse=True)
for label, acc, prec, rec, f1, kappa, auc_val in rows_for_latex:
    bold = r'\textbf' if 'Proposed' in label else ''
    if bold:
        latex_lines.append(f'\\textbf{{{label}}} & \\textbf{{{acc:.2f}}} & \\textbf{{{prec:.2f}}} & \\textbf{{{rec:.2f}}} & \\textbf{{{f1:.2f}}} & \\textbf{{{kappa:.4f}}} & \\textbf{{{auc_val:.4f}}} \\\\')
    else:
        latex_lines.append(f'{label} & {acc:.2f} & {prec:.2f} & {rec:.2f} & {f1:.2f} & {kappa:.4f} & {auc_val:.4f} \\\\')

latex_lines.append(r'\bottomrule')
latex_lines.append(r'\end{tabular}}')
latex_lines.append(r'\end{table}')

latex_table = '\n'.join(latex_lines)
with open('figures/results_table.tex', 'w') as f:
    f.write(latex_table)
print("Saved: figures/results_table.tex")
print("\nLaTeX table preview:")
print(latex_table)

# ── Display new figures ──
for f in ['figures/radar_chart_comparison.png',
          'figures/per_class_precision_recall_table.png',
          'figures/cohens_kappa_comparison.png',
          'figures/auc_roc_macro_bar.png']:
    if os.path.exists(f):
        print(f"\n--- {os.path.basename(f)} ---")
        display(Image(filename=f, width=700))

print(f"\n{'='*60}")
print("  ALL A* PAPER OUTPUTS GENERATED")
print(f"{'='*60}")
```

---

## ACCOUNT 2: Ablation (10 conditions)

### Cell 1: Setup + Run All 10

```python
from google.colab import drive
drive.mount('/content/drive')

import os
WORK = '/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet'
if not os.path.exists(WORK):
    os.makedirs('/content/drive/MyDrive/WaveCoAtNet_experiments', exist_ok=True)
    %cd /content/drive/MyDrive/WaveCoAtNet_experiments
    !git clone https://github.com/Cyrax321/wave-coAtNet.git

%cd {WORK}
!pip install -q -r requirements.txt

# Runs ALL 10 conditions automatically (~6h)
!python evaluation/ablation.py
```

### Cell 2: Extract Ablation Data

```python
import os, csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, f1_score, cohen_kappa_score,
    confusion_matrix, classification_report)
from scipy.stats import chi2 as chi2_dist
from IPython.display import display, Image

os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')
os.makedirs('figures', exist_ok=True)

class_names = ['Harlequin ichthyosis', 'Healthy skin', 'Ichthyosis vulgaris',
               'Lamellar ichthyosis', 'Netherton syndrome']
n_classes = len(class_names)

CONDITIONS = [
    ('full',           'WaveCoAtNet (Full)'),
    ('no_dpa',         'w/o DPA'),
    ('no_pgap',        'w/o PGAP+DPA'),
    ('no_wgfdca',      'w/o WG-FDCA'),
    ('no_transformer', 'w/o Transformer'),
    ('no_padts',       'w/o PA-DTS (GAP)'),
    ('no_sctr',        'w/o SCTR'),
    ('fixed_pruning',  'w/ Fixed Pruning'),
    ('no_prototypes',  'w/o Prototypes'),
    ('baseline',       'ConvNeXt-Tiny Baseline'),
]

results = []
for cond, label in CONDITIONS:
    yt_f = f'ablation_{cond}_y_true.npy'
    yp_f = f'ablation_{cond}_y_pred.npy'
    if os.path.exists(yt_f) and os.path.exists(yp_f):
        results.append((cond, label, np.load(yt_f), np.load(yp_f)))
        print(f"  Loaded: {cond}")
    else:
        print(f"  MISSING: {cond}")

print(f"\nLoaded {len(results)}/10 conditions\n")

# ── Comprehensive ablation table with deltas ──
print("="*80)
print("  ABLATION RESULTS TABLE")
print("="*80)

full_acc, full_f1 = None, None
print(f"{'Condition':<25s} {'Acc%':>7s} {'dAcc':>7s} {'F1%':>7s} {'dF1':>7s} {'Kappa':>7s}")
print("-"*60)

for cond, label, yt, yp in results:
    acc = accuracy_score(yt, yp) * 100
    f1 = f1_score(yt, yp, average='macro', zero_division=0) * 100
    kappa = cohen_kappa_score(yt, yp)
    if cond == 'full':
        full_acc, full_f1 = acc, f1
        d_acc, d_f1 = '-', '-'
    else:
        d_acc = f"{acc - full_acc:+.2f}"
        d_f1 = f"{f1 - full_f1:+.2f}"
    print(f"{label:<25s} {acc:>6.2f} {d_acc:>7s} {f1:>6.2f} {d_f1:>7s} {kappa:>6.4f}")

# ── Ablation bar chart ──
labels_plot = [r[1] for r in results]
accs_plot = [accuracy_score(r[2], r[3])*100 for r in results]
f1s_plot = [f1_score(r[2], r[3], average='macro', zero_division=0)*100 for r in results]

x = np.arange(len(labels_plot))
w = 0.35
fig, ax = plt.subplots(figsize=(14, 7))
acc_colors = ['#2563EB' if 'Full' in l else '#93C5FD' for l in labels_plot]
f1_colors = ['#DC2626' if 'Full' in l else '#FCA5A5' for l in labels_plot]
bars1 = ax.bar(x - w/2, accs_plot, w, color=acc_colors, alpha=0.85, label='Accuracy (%)')
bars2 = ax.bar(x + w/2, f1s_plot, w, color=f1_colors, alpha=0.85, label='Macro F1 (%)')

for bar in list(bars1) + list(bars2):
    ax.annotate(f'{bar.get_height():.1f}', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                xytext=(0, 3), textcoords='offset points', ha='center', fontsize=7, fontweight='bold')

if full_acc is not None:
    for i, l in enumerate(labels_plot):
        if 'Full' not in l:
            d = accs_plot[i] - full_acc
            color = '#DC2626' if d < 0 else '#16A34A'
            ax.annotate(f'{d:+.1f}%', xy=(x[i] - w/2, accs_plot[i]),
                        xytext=(0, -15), textcoords='offset points',
                        ha='center', fontsize=7, color=color, fontstyle='italic', fontweight='bold')

ax.set_xticks(x)
ax.set_xticklabels(labels_plot, rotation=30, ha='right', fontsize=9)
ax.set_ylabel('Score (%)', fontsize=11)
ax.set_title('Ablation Study: Contribution of Each Novel Module', fontsize=13, fontweight='bold')
ax.legend(fontsize=9)
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 105)
plt.tight_layout()
plt.savefig('figures/ablation_bar_detailed.png', dpi=300, bbox_inches='tight')
plt.close()
print("\nSaved: figures/ablation_bar_detailed.png")

# ── Ablation per-class F1 heatmap ──
f1_matrix = []
cond_labels = []
for cond, label, yt, yp in results:
    per_class = f1_score(yt, yp, average=None, zero_division=0, labels=range(n_classes)) * 100
    f1_matrix.append(per_class)
    cond_labels.append(label)

fig, ax = plt.subplots(figsize=(12, 6))
sns.heatmap(np.array(f1_matrix), annot=True, fmt='.1f', cmap='YlGnBu',
            xticklabels=[c[:15] for c in class_names], yticklabels=cond_labels,
            annot_kws={"size": 9}, linewidths=0.5, linecolor='white',
            vmin=0, vmax=100, ax=ax, cbar_kws={'label': 'F1 Score (%)'})
ax.set_title('Ablation: Per-Class F1 Scores', fontsize=13, fontweight='bold')
plt.xticks(rotation=25, ha='right')
plt.tight_layout()
plt.savefig('figures/ablation_f1_heatmap.png', dpi=300, bbox_inches='tight')
plt.close()
print("Saved: figures/ablation_f1_heatmap.png")

# ── McNemar: full vs each ablation ──
print(f"\n{'='*80}")
print("  McNEMAR: Full vs Each Ablation")
print(f"{'='*80}")

full_yt, full_yp = None, None
for cond, label, yt, yp in results:
    if cond == 'full':
        full_yt, full_yp = yt, yp
        break

if full_yt is not None:
    mcnemar_rows = []
    for cond, label, yt, yp in results:
        if cond == 'full': continue
        correct_full = (full_yt == full_yp).astype(int)
        correct_abl = (yt == yp).astype(int)
        b = np.sum((correct_full == 1) & (correct_abl == 0))
        c = np.sum((correct_full == 0) & (correct_abl == 1))
        if b + c == 0:
            chi2_val, pval = 0.0, 1.0
        else:
            chi2_val = (abs(b - c) - 1) ** 2 / (b + c)
            pval = 1 - chi2_dist.cdf(chi2_val, df=1)
        sig = "***" if pval < 0.001 else "**" if pval < 0.01 else "*" if pval < 0.05 else "ns"
        print(f"  {label:<25s} chi2={chi2_val:.3f}  p={pval:.4f}  {sig}")
        mcnemar_rows.append({'condition': label, 'chi2': chi2_val, 'p_value': pval, 'sig': sig})

    with open('ablation_mcnemar.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['condition','chi2','p_value','sig'])
        writer.writeheader()
        writer.writerows(mcnemar_rows)
    print("Saved: ablation_mcnemar.csv")

# ── Ablation CM grid ──
cm_files = [f'ablation_{c}_cm.png' for c, _ in CONDITIONS if os.path.exists(f'ablation_{c}_cm.png')]
if len(cm_files) >= 4:
    fig, axes = plt.subplots(2, 5, figsize=(30, 12))
    for i, cm_f in enumerate(cm_files[:10]):
        ax = axes[i//5, i%5]
        ax.imshow(plt.imread(cm_f))
        ax.axis('off')
    for i in range(len(cm_files), 10):
        axes[i//5, i%5].axis('off')
    fig.suptitle('Ablation: Confusion Matrices (All Conditions)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('figures/ablation_cm_grid.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: figures/ablation_cm_grid.png")

for f in ['figures/ablation_bar_detailed.png', 'figures/ablation_f1_heatmap.png', 'figures/ablation_cm_grid.png']:
    if os.path.exists(f):
        display(Image(filename=f, width=700))
```

---

## ACCOUNT 3: 5-Fold Cross-Validation

### Cell 1: Setup + Run

```python
from google.colab import drive
drive.mount('/content/drive')

import os
WORK = '/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet'
if not os.path.exists(WORK):
    os.makedirs('/content/drive/MyDrive/WaveCoAtNet_experiments', exist_ok=True)
    %cd /content/drive/MyDrive/WaveCoAtNet_experiments
    !git clone https://github.com/Cyrax321/wave-coAtNet.git

%cd {WORK}
!pip install -q -r requirements.txt

!python evaluation/crossval.py
```

### Cell 2: Extract Cross-Val Data + Figures

```python
import os, csv, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, f1_score, cohen_kappa_score,
    roc_auc_score, confusion_matrix)
from sklearn.preprocessing import label_binarize
from IPython.display import display, Image

os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')
os.makedirs('figures', exist_ok=True)

class_names = ['Harlequin ichthyosis', 'Healthy skin', 'Ichthyosis vulgaris',
               'Lamellar ichthyosis', 'Netherton syndrome']
n_classes = len(class_names)

# ── Summary ──
print("="*60)
print("  CROSS-VALIDATION SUMMARY")
print("="*60)
if os.path.exists('crossval_summary.txt'):
    with open('crossval_summary.txt') as f: print(f.read())

if os.path.exists('crossval_results.csv'):
    with open('crossval_results.csv') as f: print(f.read())

if os.path.exists('mcnemar_results.csv'):
    print("\n--- McNemar Results ---")
    with open('mcnemar_results.csv') as f: print(f.read())

# ── Headline claim with CI ──
if os.path.exists('crossval_results.csv'):
    with open('crossval_results.csv') as f:
        rows = list(csv.DictReader(f))
    accs = [float(r['accuracy']) for r in rows]
    f1s = [float(r['macro_f1']) for r in rows]
    ci95 = 1.96 * np.std(accs, ddof=1) / np.sqrt(len(accs))
    print(f"\n--- HEADLINE CLAIM ---")
    print(f"  Accuracy: {np.mean(accs)*100:.2f}% +/- {np.std(accs, ddof=1)*100:.2f}%")
    print(f"  95% CI:   [{(np.mean(accs)-ci95)*100:.2f}%, {(np.mean(accs)+ci95)*100:.2f}%]")
    print(f"  Macro F1: {np.mean(f1s):.4f} +/- {np.std(f1s, ddof=1):.4f}")

# ── Cohen's Kappa + Sensitivity/Specificity from cross-val folds ──
all_yt, all_yp = [], []
for k in range(1, 6):
    if os.path.exists(f'fold_{k}_y_true.npy'):
        all_yt.append(np.load(f'fold_{k}_y_true.npy'))
        all_yp.append(np.load(f'fold_{k}_y_pred.npy'))
if all_yt:
    yt = np.concatenate(all_yt)
    yp = np.concatenate(all_yp)
    print(f"\nCohen's Kappa: {cohen_kappa_score(yt, yp):.4f}")

    cm = confusion_matrix(yt, yp, labels=range(n_classes))
    print(f"\n{'Class':<25s} {'Sensitivity':>12s} {'Specificity':>12s}")
    print("-"*50)
    for i, cls in enumerate(class_names):
        tp = cm[i, i]; fn = cm[i, :].sum() - tp
        fp = cm[:, i].sum() - tp; tn = cm.sum() - tp - fn - fp
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0
        print(f"  {cls:<23s} {sens:>11.4f} {spec:>11.4f}")

# ── Cross-val bar chart ──
folds = [int(r['fold']) for r in rows]
accs_pct = [float(r['accuracy'])*100 for r in rows]
f1s_pct = [float(r['macro_f1'])*100 for r in rows]
wf1s_pct = [float(r['weighted_f1'])*100 for r in rows]

fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(folds))
w = 0.3
bars1 = ax.bar(x - w, accs_pct, w, label='Accuracy (%)', color='#2563EB', alpha=0.85)
bars2 = ax.bar(x, f1s_pct, w, label='Macro F1 (%)', color='#DC2626', alpha=0.85)
bars3 = ax.bar(x + w, wf1s_pct, w, label='Weighted F1 (%)', color='#16A34A', alpha=0.85)
ax.axhline(np.mean(accs_pct), color='#2563EB', linestyle='--', alpha=0.5, label=f'Mean Acc ({np.mean(accs_pct):.1f}%)')
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        ax.annotate(f'{bar.get_height():.1f}', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords='offset points', ha='center', fontsize=7, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels([f'Fold {f}' for f in folds], fontsize=10)
ax.set_ylabel('Score (%)', fontsize=11)
ax.set_title('5-Fold Stratified Cross-Validation: WaveCoAtNet', fontsize=13, fontweight='bold')
ax.legend(fontsize=8, loc='lower right')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(min(min(accs_pct), min(f1s_pct)) - 5, 105)
plt.tight_layout()
plt.savefig('figures/crossval_folds_bar.png', dpi=300)
plt.close()
print("\nSaved: figures/crossval_folds_bar.png")

# ── Box plot ──
fig, ax = plt.subplots(figsize=(8, 6))
data = [accs_pct, f1s_pct, wf1s_pct]
bp = ax.boxplot(data, patch_artist=True, labels=['Accuracy', 'Macro F1', 'Weighted F1'],
                widths=0.5, showmeans=True, meanprops=dict(marker='D', markerfacecolor='white', markersize=8))
for patch, color in zip(bp['boxes'], ['#2563EB', '#DC2626', '#16A34A']):
    patch.set_facecolor(color); patch.set_alpha(0.7)
for i, d in enumerate(data):
    jitter = np.random.normal(0, 0.04, len(d))
    ax.scatter([i+1+j for j in jitter], d, color='black', alpha=0.6, s=30, zorder=5)
    ax.text(i+1, max(d)+1.5, f'{np.mean(d):.1f}+/-{np.std(d, ddof=1):.1f}%',
            ha='center', fontsize=8, fontweight='bold')
ax.set_ylabel('Score (%)', fontsize=11)
ax.set_title('Cross-Validation Score Distribution', fontsize=13, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('figures/crossval_boxplot.png', dpi=300)
plt.close()
print("Saved: figures/crossval_boxplot.png")

# ── Fold CM grid ──
fold_cms = [f'fold_{k}_cm.png' for k in range(1, 6) if os.path.exists(f'fold_{k}_cm.png')]
if fold_cms:
    fig, axes = plt.subplots(1, 5, figsize=(25, 5))
    for i, cm_f in enumerate(fold_cms):
        axes[i].imshow(plt.imread(cm_f)); axes[i].axis('off')
        axes[i].set_title(f'Fold {i+1}', fontsize=11, fontweight='bold')
    fig.suptitle('Per-Fold Confusion Matrices', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig('figures/crossval_cm_grid.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved: figures/crossval_cm_grid.png")

for f in ['figures/crossval_folds_bar.png', 'figures/crossval_boxplot.png', 'figures/crossval_cm_grid.png']:
    if os.path.exists(f):
        display(Image(filename=f, width=700))

print("\n--- Saved Files ---")
for f in sorted(glob.glob('crossval_*') + glob.glob('mcnemar_*') + glob.glob('fold_*')):
    print(f"  {f} ({os.path.getsize(f)/1024:.1f} KB)")
```

---

## FINAL: Publication Readiness Check (any account)

```python
import os
os.chdir('/content/drive/MyDrive/WaveCoAtNet_experiments/wave-coAtNet/wave-CoAtNet')

print("="*60)
print("  PUBLICATION READINESS CHECK")
print("="*60)

preds = sorted([f for f in os.listdir('.') if f.endswith('_y_pred.npy') and not f.startswith('ablation')])
print(f"\n[1] Model predictions: {len(preds)}/12")
for p in preds: print(f"    [OK] {p}")
missing_models = {'wavecoatnet','coatnet','efficientnet_pretrained','efficientnet_scratch',
                  'swin_pretrained','swin_scratch','vit_pretrained','vit_scratch',
                  'gft','biomedclip','dinov2','cnn'}
for m in sorted(missing_models - {p.replace('_y_pred.npy','') for p in preds}):
    print(f"    [MISSING] {m}_y_pred.npy")

abl = sorted([f for f in os.listdir('.') if f.startswith('ablation_') and f.endswith('_y_pred.npy')])
print(f"\n[2] Ablation predictions: {len(abl)}/10")
for p in abl: print(f"    [OK] {p}")

print(f"\n[3] Data tables:")
for csv_f in ['ablation_results.csv','crossval_summary.txt','crossval_results.csv',
              'mcnemar_results.csv','ablation_mcnemar.csv','figures/full_comparison_table.csv',
              'figures/inference_timing.csv','figures/mcnemar_pvalues.csv','figures/comprehensive_results.csv']:
    status = 'OK' if os.path.exists(csv_f) else 'MISSING'
    print(f"    [{status}] {csv_f}")

fig_count = 0
print(f"\n[4] Publication figures:")
if os.path.exists('figures'):
    for f in sorted(os.listdir('figures')):
        print(f"    [OK] figures/{f}"); fig_count += 1

gc_count = 0
print(f"\n[5] Grad-CAM:")
if os.path.exists('gradcam'):
    for f in sorted(os.listdir('gradcam')):
        print(f"    [OK] gradcam/{f}"); gc_count += 1

total_preds = len(preds) + len(abl)
if total_preds >= 22 and fig_count >= 20 and gc_count > 0:
    print(f"\n{'='*60}")
    print("  ALL COMPLETE -- READY TO WRITE THE PAPER")
    print(f"{'='*60}")
else:
    print(f"\n{'='*60}")
    print(f"  INCOMPLETE: preds={total_preds}/22  figs={fig_count}/20+  gradcam={'OK' if gc_count else 'MISSING'}")
    print(f"{'='*60}")
```
