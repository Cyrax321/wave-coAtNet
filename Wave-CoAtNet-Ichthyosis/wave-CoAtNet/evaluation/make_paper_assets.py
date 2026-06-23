"""
make_paper_assets.py — Auto-generate ALL A* paper figures & tables
==================================================================
Reads the matched 5-fold predictions saved by crossval_all.py (and,
optionally, the dataset for a sample-image grid) and emits every figure
and table a top-venue paper needs — no GPU required, pure CPU.

Run AFTER crossval_all.py has produced fold predictions in CV_OUT_DIR.

USAGE:
    python evaluation/make_paper_assets.py
    python evaluation/make_paper_assets.py --dataset_dir /path/to/roboflow  # adds sample grid

OUTPUTS (in CV_OUT_DIR/assets/):
  Figures (300 DPI PNG + PDF):
    fig_cv_comparison_ci.*      bar chart, accuracy ± 95% CI, all models
    fig_perclass_f1_heatmap.*   per-class F1, all models
    fig_confusion_grid.*        pooled confusion matrix per model
    fig_kappa_bar.*             Cohen's kappa per model
    fig_stability_box.*         per-fold accuracy/F1 spread (WaveCoAtNet)
    fig_training_curves.*       val-accuracy curves (mean across folds)
    fig_sample_images.*         5-class sample grid (needs --dataset_dir)
  Tables (Markdown + LaTeX + CSV):
    tab_main_comparison.{md,tex,csv}
    tab_perclass_sensspec.{md,tex,csv}
    tab_cv_folds.{md,tex,csv}
"""

import os
import csv
import json
import glob
import argparse

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score,
                             confusion_matrix, cohen_kappa_score)

OUT_DIR = os.environ.get("CV_OUT_DIR",
                         "/content/drive/MyDrive/WaveCoAtNet_experiments/cv_matched")
N_FOLDS = 5
DISPLAY = {  # pretty names for the paper
    "wavecoatnet": "WaveCoAtNet (ours)",
    "convnext_tiny": "CoAtNet/ConvNeXt-T",
    "swin_tiny": "Swin-T",
    "dinov2": "DINOv2",
}
plt.rcParams.update({"font.size": 11, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 120, "savefig.bbox": "tight"})


def assets_dir():
    d = os.path.join(OUT_DIR, "assets")
    os.makedirs(d, exist_ok=True)
    return d


def discover_models():
    """Any model with at least one saved fold pred."""
    found = []
    for f in sorted(glob.glob(os.path.join(OUT_DIR, "*_fold_1_y_pred.npy"))):
        key = os.path.basename(f).replace("_fold_1_y_pred.npy", "")
        found.append(key)
    # stable order: ours first, then rest
    order = ["wavecoatnet", "convnext_tiny", "swin_tiny", "dinov2"]
    return sorted(found, key=lambda k: order.index(k) if k in order else 99)


def load_folds(key):
    """Return list of (y_true, y_pred) per available fold, and pooled arrays."""
    per_fold, yt_all, yp_all = [], [], []
    for k in range(1, N_FOLDS + 1):
        yt = os.path.join(OUT_DIR, f"{key}_fold_{k}_y_true.npy")
        yp = os.path.join(OUT_DIR, f"{key}_fold_{k}_y_pred.npy")
        if os.path.exists(yt) and os.path.exists(yp):
            t, p = np.load(yt), np.load(yp)
            per_fold.append((t, p))
            yt_all.append(t); yp_all.append(p)
    if not per_fold:
        return [], None, None
    return per_fold, np.concatenate(yt_all), np.concatenate(yp_all)


def fold_metrics(per_fold):
    accs = np.array([accuracy_score(t, p) for t, p in per_fold])
    mf1s = np.array([f1_score(t, p, average='macro', zero_division=0) for t, p in per_fold])
    return accs, mf1s


def ci95(x):
    if len(x) < 2:
        return 0.0
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x))


def get_class_names(n):
    f = os.path.join(OUT_DIR, "class_names.json")
    if os.path.exists(f):
        return json.load(open(f))
    return [f"Class{i}" for i in range(n)]


def savefig(fig, name):
    d = assets_dir()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(d, f"{name}.{ext}"), dpi=300)
    plt.close(fig)
    print(f"  saved {name}.png / .pdf")


# ── Figures ──────────────────────────────────────────────────────────────────
def fig_cv_comparison_ci(models, stats):
    names = [DISPLAY.get(m, m) for m in models]
    means = [stats[m]["acc_mean"] * 100 for m in models]
    errs  = [stats[m]["acc_ci"] * 100 for m in models]
    colors = ["#c0392b" if m == "wavecoatnet" else "#2c7fb8" for m in models]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(names, means, yerr=errs, capsize=6, color=colors, edgecolor="black", alpha=0.9)
    for b, m, e in zip(bars, means, errs):
        ax.text(b.get_x() + b.get_width()/2, m + e + 0.3, f"{m:.2f}%",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("5-fold accuracy (%)")
    ax.set_title("Matched 5-Fold Cross-Validation Accuracy (mean ± 95% CI)")
    lo = min(means) - max(errs) - 3
    ax.set_ylim(max(0, lo), max(means) + max(errs) + 3)
    plt.xticks(rotation=15)
    savefig(fig, "fig_cv_comparison_ci")


def fig_perclass_f1_heatmap(models, class_names):
    mat = []
    for m in models:
        per_fold, yt, yp = load_folds(m)
        f1s = f1_score(yt, yp, average=None, zero_division=0)
        mat.append(f1s)
    mat = np.array(mat)
    fig, ax = plt.subplots(figsize=(1.6*len(class_names)+2, 0.7*len(models)+2))
    im = ax.imshow(mat, cmap="YlGnBu", vmin=max(0, mat.min()-0.05), vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(class_names))); ax.set_xticklabels(class_names, rotation=30, ha="right")
    ax.set_yticks(range(len(models))); ax.set_yticklabels([DISPLAY.get(m, m) for m in models])
    for i in range(len(models)):
        for j in range(len(class_names)):
            ax.text(j, i, f"{mat[i,j]:.3f}", ha="center", va="center",
                    color="white" if mat[i,j] > 0.6 else "black", fontsize=9)
    fig.colorbar(im, ax=ax, label="F1-score")
    ax.set_title("Per-Class F1 (pooled 5-fold)")
    savefig(fig, "fig_perclass_f1_heatmap")


def fig_confusion_grid(models, class_names):
    n = len(models)
    cols = min(n, 2); rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(5.5*cols, 4.8*rows))
    axes = np.array(axes).reshape(-1)
    for ax, m in zip(axes, models):
        _, yt, yp = load_folds(m)
        cm = confusion_matrix(yt, yp)
        im = ax.imshow(cm, cmap="Blues")
        ax.set_title(DISPLAY.get(m, m), fontweight="bold")
        ax.set_xticks(range(len(class_names))); ax.set_xticklabels(class_names, rotation=40, ha="right", fontsize=8)
        ax.set_yticks(range(len(class_names))); ax.set_yticklabels(class_names, fontsize=8)
        thr = cm.max() / 2
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > thr else "black", fontsize=8)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Pooled 5-Fold Confusion Matrices", fontsize=13, fontweight="bold")
    savefig(fig, "fig_confusion_grid")


def fig_kappa_bar(models):
    names = [DISPLAY.get(m, m) for m in models]
    kappas = []
    for m in models:
        _, yt, yp = load_folds(m)
        kappas.append(cohen_kappa_score(yt, yp))
    colors = ["#c0392b" if m == "wavecoatnet" else "#7fbf7b" for m in models]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(names, kappas, color=colors, edgecolor="black", alpha=0.9)
    for b, k in zip(bars, kappas):
        ax.text(b.get_x()+b.get_width()/2, k+0.005, f"{k:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Cohen's κ (pooled 5-fold)")
    ax.set_ylim(min(kappas)-0.05, 1.0)
    ax.set_title("Agreement (Cohen's κ) Across Models")
    plt.xticks(rotation=15)
    savefig(fig, "fig_kappa_bar")


def fig_stability_box(models):
    data, labels = [], []
    for m in models:
        per_fold, _, _ = load_folds(m)
        if len(per_fold) >= 2:
            accs, _ = fold_metrics(per_fold)
            data.append(accs * 100); labels.append(DISPLAY.get(m, m))
    if not data:
        return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bp = ax.boxplot(data, patch_artist=True, tick_labels=labels)
    for patch in bp["boxes"]:
        patch.set_facecolor("#aed6f1")
    ax.set_ylabel("Per-fold accuracy (%)")
    ax.set_title("Cross-Validation Stability (per-fold spread)")
    plt.xticks(rotation=15)
    savefig(fig, "fig_stability_box")


def fig_training_curves(models):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    plotted = False
    for m in models:
        curves = []
        for k in range(1, N_FOLDS + 1):
            hf = os.path.join(OUT_DIR, f"{m}_fold_{k}_history.json")
            if os.path.exists(hf):
                curves.append(json.load(open(hf))["val_acc"])
        if not curves:
            continue
        L = min(len(c) for c in curves)
        arr = np.array([c[:L] for c in curves])
        mean = arr.mean(0) * 100
        ax.plot(range(1, L+1), mean, marker="o", ms=3, label=DISPLAY.get(m, m))
        plotted = True
    if not plotted:
        plt.close(fig); return
    ax.set_xlabel("Epoch"); ax.set_ylabel("Validation accuracy (%) — mean over folds")
    ax.set_title("Training Dynamics"); ax.legend()
    savefig(fig, "fig_training_curves")


def fig_sample_images(dataset_dir, class_names):
    from PIL import Image
    if not dataset_dir:
        return
    cols = 4
    fig, axes = plt.subplots(len(class_names), cols, figsize=(2.2*cols, 2.2*len(class_names)))
    for r, cname in enumerate(class_names):
        imgs = []
        for split in ["train", "valid", "test"]:
            d = os.path.join(dataset_dir, split, cname)
            if os.path.isdir(d):
                imgs += [os.path.join(d, f) for f in os.listdir(d)
                         if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        for c in range(cols):
            ax = axes[r, c] if len(class_names) > 1 else axes[c]
            ax.axis("off")
            if c < len(imgs):
                try:
                    ax.imshow(Image.open(imgs[c]).convert("RGB").resize((160, 160)))
                except Exception:
                    pass
            if c == 0:
                ax.set_title(cname, loc="left", fontsize=10, fontweight="bold")
    fig.suptitle("Representative Samples per Class", fontsize=13, fontweight="bold")
    savefig(fig, "fig_sample_images")


# ── Tables ───────────────────────────────────────────────────────────────────
def write_table(name, headers, rows):
    d = assets_dir()
    # Markdown
    with open(os.path.join(d, f"{name}.md"), "w") as f:
        f.write("| " + " | ".join(headers) + " |\n")
        f.write("|" + "|".join(["---"]*len(headers)) + "|\n")
        for r in rows:
            f.write("| " + " | ".join(str(x) for x in r) + " |\n")
    # LaTeX
    with open(os.path.join(d, f"{name}.tex"), "w") as f:
        f.write("\\begin{tabular}{" + "l"*len(headers) + "}\n\\hline\n")
        f.write(" & ".join(headers) + " \\\\\n\\hline\n")
        for r in rows:
            f.write(" & ".join(str(x) for x in r) + " \\\\\n")
        f.write("\\hline\n\\end{tabular}\n")
    # CSV
    with open(os.path.join(d, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(headers); w.writerows(rows)
    print(f"  saved {name}.md / .tex / .csv")


def table_main(models, stats):
    headers = ["Model", "Acc Mean (%)", "±SD", "95% CI", "Macro-F1", "Cohen κ"]
    rows = []
    for m in models:
        s = stats[m]
        rows.append([DISPLAY.get(m, m), f"{s['acc_mean']*100:.2f}", f"{s['acc_sd']*100:.2f}",
                     f"[{(s['acc_mean']-s['acc_ci'])*100:.2f}, {(s['acc_mean']+s['acc_ci'])*100:.2f}]",
                     f"{s['mf1_mean']:.4f}", f"{s['kappa']:.4f}"])
    write_table("tab_main_comparison", headers, rows)


def table_perclass_sensspec(class_names):
    """Sensitivity/specificity for WaveCoAtNet (pooled folds)."""
    _, yt, yp = load_folds("wavecoatnet")
    if yt is None:
        return
    cm = confusion_matrix(yt, yp)
    headers = ["Class", "Sensitivity", "Specificity", "Precision", "F1"]
    rows = []
    total = cm.sum()
    for i, c in enumerate(class_names):
        tp = cm[i, i]; fn = cm[i].sum() - tp; fp = cm[:, i].sum() - tp
        tn = total - tp - fn - fp
        sens = tp / (tp + fn) if (tp+fn) else 0
        spec = tn / (tn + fp) if (tn+fp) else 0
        prec = tp / (tp + fp) if (tp+fp) else 0
        f1 = 2*prec*sens/(prec+sens) if (prec+sens) else 0
        rows.append([c, f"{sens:.4f}", f"{spec:.4f}", f"{prec:.4f}", f"{f1:.4f}"])
    write_table("tab_perclass_sensspec", headers, rows)


def table_cv_folds():
    per_fold, _, _ = load_folds("wavecoatnet")
    if not per_fold:
        return
    headers = ["Fold", "Accuracy (%)", "Macro-F1", "Weighted-F1"]
    rows = []
    accs, mf1s = [], []
    for k, (t, p) in enumerate(per_fold, 1):
        a = accuracy_score(t, p); mf = f1_score(t, p, average='macro', zero_division=0)
        wf = f1_score(t, p, average='weighted', zero_division=0)
        accs.append(a); mf1s.append(mf)
        rows.append([k, f"{a*100:.2f}", f"{mf:.4f}", f"{wf:.4f}"])
    accs, mf1s = np.array(accs), np.array(mf1s)
    rows.append(["Mean±SD", f"{accs.mean()*100:.2f}±{accs.std(ddof=1)*100:.2f}",
                 f"{mf1s.mean():.4f}±{mf1s.std(ddof=1):.4f}", "—"])
    write_table("tab_cv_folds", headers, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_dir", default=None, help="Roboflow folder for sample-image grid")
    args = ap.parse_args()

    models = discover_models()
    if not models:
        raise SystemExit(f"No fold predictions found in {OUT_DIR}. Run crossval_all.py first.")
    print(f"Models found: {models}")

    # Determine class count/names from any pooled preds
    _, yt0, _ = load_folds(models[0])
    n_classes = int(max(yt0)) + 1
    class_names = get_class_names(n_classes)

    # Compute summary stats per model
    stats = {}
    for m in models:
        per_fold, yt, yp = load_folds(m)
        accs, mf1s = fold_metrics(per_fold)
        stats[m] = dict(acc_mean=accs.mean(), acc_sd=(accs.std(ddof=1) if len(accs) > 1 else 0.0),
                        acc_ci=ci95(accs), mf1_mean=mf1s.mean(),
                        kappa=cohen_kappa_score(yt, yp))
    models = sorted(models, key=lambda m: -stats[m]["acc_mean"])

    print("\nGenerating figures...")
    fig_cv_comparison_ci(models, stats)
    fig_perclass_f1_heatmap(models, class_names)
    fig_confusion_grid(models, class_names)
    fig_kappa_bar(models)
    fig_stability_box(models)
    fig_training_curves(models)
    fig_sample_images(args.dataset_dir, class_names)

    print("\nGenerating tables...")
    table_main(models, stats)
    table_perclass_sensspec(class_names)
    table_cv_folds()

    print(f"\nAll assets in: {assets_dir()}")
    print("Figures: 300 DPI PNG + PDF. Tables: Markdown + LaTeX + CSV.")


if __name__ == "__main__":
    main()
