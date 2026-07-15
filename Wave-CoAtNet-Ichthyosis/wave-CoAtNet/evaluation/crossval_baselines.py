"""
Matched 5-Fold Cross-Validation for BASELINES (Option B)
=========================================================
Runs the SAME 5 stratified folds as crossval.py (seed=42) so baseline
predictions are paired image-for-image with WaveCoAtNet's per-fold preds.

Option B scope: top rivals only (CoAtNet/ConvNeXt-Tiny, Swin-T, DINOv2).
Add/remove names in MODELS below.

RESUMABLE: each fold's predictions are saved immediately to OUT_DIR.
On restart, any (model, fold) whose preds already exist is SKIPPED.
So a Colab disconnect costs at most the in-progress fold.

Run one model at a time to stay inside a free-tier session:
    python evaluation/crossval_baselines.py --model convnext_tiny
    python evaluation/crossval_baselines.py --model swin_tiny
    python evaluation/crossval_baselines.py --model dinov2
Or all sequentially (only if you have the hours):
    python evaluation/crossval_baselines.py --model all

After all models + WaveCoAtNet folds exist, summarize + compare:
    python evaluation/crossval_baselines.py --summarize

Outputs (per model) in OUT_DIR:
    {model}_fold_{k}_y_true.npy
    {model}_fold_{k}_y_pred.npy
    baselines_cv_summary.csv
"""

import os
import csv
import argparse

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torch.amp import autocast, GradScaler
from torchvision import datasets, transforms
from PIL import Image

from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, classification_report
from tqdm import tqdm
from timm import create_model

# ── Config (MUST match crossval.py for paired comparison) ────────────────────
RANDOM_SEED  = 42
TARGET_SIZE  = (224, 224)
BATCH_SIZE   = 24
EPOCHS       = 30          # lower to 15 to ~halve compute (logs plateau by ep ~10)
LR_BACKBONE  = 1e-5
LR_HEAD      = 1e-4
WEIGHT_DECAY = 0.01
DROPOUT      = 0.2
N_FOLDS      = 5
GRAD_CLIP    = 1.0
DEVICE       = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Save to Drive so disconnects don't lose finished folds. Change if needed.
OUT_DIR = os.environ.get("CV_OUT_DIR", "/content/drive/MyDrive/WaveCoAtNet_experiments/cv_baselines")

# Option B model zoo. Key -> (timm name, freeze_prefixes, n_unfrozen_blocks)
# freeze=None trains everything; freeze=N freezes all but the last N blocks + head.
MODELS = {
    # Their "CoAtNet" baseline in the logs is a pretrained convnext_tiny.
    "convnext_tiny": dict(timm_name="convnext_tiny", partial_freeze=None),
    "swin_tiny":     dict(timm_name="swin_tiny_patch4_window7_224", partial_freeze=None),
    # DINOv2 ViT-B/14: freeze most of the encoder, fine-tune last blocks + head.
    "dinov2":        dict(timm_name="vit_base_patch14_dinov2.lvd142m", partial_freeze=2),
}


def set_seed(seed):
    import random
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True


# ── Path dataset + sample collection (identical to crossval.py) ──────────────
class PathDataset(Dataset):
    def __init__(self, paths, labels, transform=None):
        self.paths, self.labels, self.transform = paths, labels, transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert('RGB')
        if self.transform:
            img = self.transform(img)
        return img, self.labels[idx]


def collect_all_samples(dataset_dir):
    base = datasets.ImageFolder(os.path.join(dataset_dir, "train"))
    class_names = base.classes
    all_paths, all_labels = [], []
    for split in ["train", "valid", "test"]:
        d = os.path.join(dataset_dir, split)
        if not os.path.exists(d):
            continue
        ds = datasets.ImageFolder(d)
        assert ds.classes == class_names, f"Class mismatch in {split}"
        for path, label in ds.samples:
            all_paths.append(path); all_labels.append(label)
    return all_paths, all_labels, class_names


def build_model(key, num_classes):
    cfg = MODELS[key]
    model = create_model(cfg["timm_name"], pretrained=True, num_classes=num_classes)
    if cfg["partial_freeze"] is not None:
        # Freeze everything, then unfreeze classifier head + last N transformer blocks.
        for p in model.parameters():
            p.requires_grad = False
        head = model.get_classifier()
        for p in head.parameters():
            p.requires_grad = True
        blocks = getattr(model, "blocks", None)
        if blocks is not None:
            for blk in blocks[-cfg["partial_freeze"]:]:
                for p in blk.parameters():
                    p.requires_grad = True
    return model


def make_optimizer(model):
    backbone, novel = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        # Heads/classifiers get the higher LR; pretrained body gets the lower one.
        if any(s in name for s in ["head", "classifier", "fc"]):
            novel.append(p)
        else:
            backbone.append(p)
    groups = []
    if backbone:
        groups.append({"params": backbone, "lr": LR_BACKBONE})
    if novel:
        groups.append({"params": novel, "lr": LR_HEAD})
    return torch.optim.AdamW(groups, weight_decay=WEIGHT_DECAY)


def train_one_epoch(model, loader, criterion, optimizer, scaler):
    model.train()
    use_amp = scaler is not None
    for imgs, tgts in tqdm(loader, desc="  train", leave=False):
        imgs, tgts = imgs.to(DEVICE, non_blocking=True), tgts.to(DEVICE, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        with autocast('cuda', enabled=use_amp):
            loss = criterion(model(imgs), tgts)
        if use_amp:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            scaler.step(optimizer); scaler.update()
        else:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
            optimizer.step()


@torch.no_grad()
def eval_loader(model, loader):
    model.eval()
    preds, targets = [], []
    use_amp = DEVICE.type == 'cuda'
    for imgs, tgts in tqdm(loader, desc="  eval ", leave=False):
        imgs = imgs.to(DEVICE, non_blocking=True)
        with autocast('cuda', enabled=use_amp):
            out = model(imgs)
        preds.extend(out.argmax(1).cpu().numpy())
        targets.extend(tgts.numpy())
    return np.array(targets), np.array(preds)


def get_folds(all_paths, all_labels):
    """Identical fold construction to crossval.py — guarantees paired test sets."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    folds = []
    for fold, (train_val_idx, test_idx) in enumerate(
            skf.split(np.arange(len(all_paths)), all_labels)):
        sss = StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=RANDOM_SEED + fold)
        tr_local, val_local = next(sss.split(train_val_idx, all_labels[train_val_idx]))
        folds.append((train_val_idx[tr_local], train_val_idx[val_local], test_idx))
    return folds


def run_model(key, all_paths, all_labels, class_names, train_aug, val_tf):
    num_classes = len(class_names)
    folds = get_folds(all_paths, all_labels)
    scaler = GradScaler('cuda') if DEVICE.type == 'cuda' else None
    os.makedirs(OUT_DIR, exist_ok=True)

    for fold, (train_idx, val_idx, test_idx) in enumerate(folds):
        pred_file = os.path.join(OUT_DIR, f"{key}_fold_{fold+1}_y_pred.npy")
        if os.path.exists(pred_file):
            print(f"[{key}] fold {fold+1}: already done — skipping.")
            continue

        print(f"\n{'='*60}\n  [{key}] FOLD {fold+1}/{N_FOLDS}\n{'='*60}")
        set_seed(RANDOM_SEED + fold)

        def subset(idx, tf):
            return PathDataset([all_paths[i] for i in idx],
                               [int(all_labels[i]) for i in idx], tf)

        tr_ds, val_ds, te_ds = subset(train_idx, train_aug), subset(val_idx, val_tf), subset(test_idx, val_tf)
        g = torch.Generator(); g.manual_seed(RANDOM_SEED + fold)
        nw = 0 if os.name == 'nt' else 2
        pin = torch.cuda.is_available()
        tr_loader  = DataLoader(tr_ds, BATCH_SIZE, shuffle=True, num_workers=nw, pin_memory=pin, generator=g)
        val_loader = DataLoader(val_ds, BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin)
        te_loader  = DataLoader(te_ds, BATCH_SIZE, shuffle=False, num_workers=nw, pin_memory=pin)

        counts = np.bincount([int(all_labels[i]) for i in train_idx], minlength=num_classes)
        cw = torch.tensor([len(train_idx) / (c * num_classes + 1e-6) for c in counts],
                          dtype=torch.float).to(DEVICE)
        criterion = nn.CrossEntropyLoss(weight=cw, label_smoothing=0.1)

        model = build_model(key, num_classes).to(DEVICE)
        optimizer = make_optimizer(model)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

        best_val, best_state = 0.0, None
        for epoch in range(EPOCHS):
            train_one_epoch(model, tr_loader, criterion, optimizer, scaler)
            scheduler.step()
            val_yt, val_yp = eval_loader(model, val_loader)
            val_acc = accuracy_score(val_yt, val_yp)
            if epoch % 5 == 0 or epoch == EPOCHS - 1:
                print(f"  Epoch {epoch+1:2d}/{EPOCHS} | Val Acc: {val_acc:.4f}")
            if val_acc > best_val:
                best_val = val_acc
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        model.load_state_dict({k: v.to(DEVICE) for k, v in best_state.items()})
        y_true, y_pred = eval_loader(model, te_loader)
        acc = accuracy_score(y_true, y_pred)
        mf1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        print(f"  [{key}] Fold {fold+1}: Acc={acc*100:.2f}%  MacroF1={mf1:.4f}")
        print(classification_report(y_true, y_pred, target_names=class_names, digits=4))

        # Save immediately — this is the resume checkpoint.
        np.save(os.path.join(OUT_DIR, f"{key}_fold_{fold+1}_y_true.npy"), y_true)
        np.save(pred_file, y_pred)

        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def summarize():
    """Build mean±SD + 95% CI per model from saved fold preds. Compares via CI overlap."""
    rows = []
    keys = list(MODELS.keys()) + ["wavecoatnet"]
    for key in keys:
        accs, mf1s = [], []
        # WaveCoAtNet uses crossval.py's naming: fold_{k}_y_pred.npy (no prefix).
        prefix = "" if key == "wavecoatnet" else f"{key}_"
        for fold in range(1, N_FOLDS + 1):
            yt = os.path.join(OUT_DIR, f"{prefix}fold_{fold}_y_true.npy")
            yp = os.path.join(OUT_DIR, f"{prefix}fold_{fold}_y_pred.npy")
            if not (os.path.exists(yt) and os.path.exists(yp)):
                continue
            t, p = np.load(yt), np.load(yp)
            accs.append(accuracy_score(t, p))
            mf1s.append(f1_score(t, p, average='macro', zero_division=0))
        if not accs:
            print(f"[{key}] no folds found — skipping.")
            continue
        accs, mf1s = np.array(accs), np.array(mf1s)
        # 95% CI of the mean across folds (t would be stricter; SD-based is what the paper reports).
        ci = 1.96 * accs.std(ddof=1) / np.sqrt(len(accs)) if len(accs) > 1 else 0.0
        rows.append(dict(
            model=key, folds=len(accs),
            acc_mean=accs.mean(), acc_sd=accs.std(ddof=1) if len(accs) > 1 else 0.0,
            acc_ci_lo=accs.mean() - ci, acc_ci_hi=accs.mean() + ci,
            macro_f1_mean=mf1s.mean(), macro_f1_sd=mf1s.std(ddof=1) if len(mf1s) > 1 else 0.0))

    rows.sort(key=lambda r: -r["acc_mean"])
    print("\n" + "=" * 78)
    print("  MATCHED 5-FOLD CV — MODEL COMPARISON")
    print("=" * 78)
    print(f"{'Model':<16}{'Folds':>6}{'Acc Mean':>11}{'±SD':>8}{'95% CI':>20}{'MacroF1':>10}")
    print("-" * 78)
    for r in rows:
        print(f"{r['model']:<16}{r['folds']:>6}{r['acc_mean']*100:>10.2f}%{r['acc_sd']*100:>7.2f}%"
              f"  [{r['acc_ci_lo']*100:>5.2f}, {r['acc_ci_hi']*100:>5.2f}]{r['macro_f1_mean']:>10.4f}")
    print("=" * 78)
    print("Interpretation: if WaveCoAtNet's CI does NOT overlap a rival's CI, the")
    print("difference is meaningful. Overlap => report as 'competitive', not 'superior'.")

    with open(os.path.join(OUT_DIR, "baselines_cv_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nSaved: {os.path.join(OUT_DIR, 'baselines_cv_summary.csv')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None,
                    help="convnext_tiny | swin_tiny | dinov2 | all")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()

    global EPOCHS
    EPOCHS = args.epochs

    if args.summarize:
        summarize(); return

    if args.model is None:
        ap.error("pass --model <name|all> or --summarize")

    set_seed(RANDOM_SEED)
    from roboflow import Roboflow
    rf = Roboflow(api_key="gXuxxWEMFJ8nK73o7pN7")
    dataset = rf.workspace("hi-l9ueo").project("ich-s-7lnsj").version(1).download("folder")
    ddir = dataset.location

    valid_path = os.path.join(ddir, "valid")
    validation_path = os.path.join(ddir, "validation")
    if not os.path.exists(valid_path) and os.path.exists(validation_path):
        os.rename(validation_path, valid_path)

    all_paths, all_labels, class_names = collect_all_samples(ddir)
    all_labels = np.array(all_labels)
    print(f"Total samples: {len(all_paths)} | Classes: {class_names}")
    print(f"Label distribution: {np.bincount(all_labels)}")

    train_aug = transforms.Compose([
        transforms.RandomResizedCrop(TARGET_SIZE, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(15),
        transforms.TrivialAugmentWide(), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.2))])
    val_tf = transforms.Compose([
        transforms.Resize(TARGET_SIZE), transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    targets = list(MODELS.keys()) if args.model == "all" else [args.model]
    for key in targets:
        if key not in MODELS:
            raise SystemExit(f"Unknown model '{key}'. Choices: {list(MODELS.keys())} or 'all'")
        run_model(key, all_paths, all_labels, class_names, train_aug, val_tf)

    print("\nDone. After all models finish, run:  python evaluation/crossval_baselines.py --summarize")


if __name__ == "__main__":
    main()
