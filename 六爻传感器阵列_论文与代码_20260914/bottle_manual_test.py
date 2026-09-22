#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径A 手工测试工具 (bottle)
================================================================================
功能:
  1. train  : 用若干正常(good)图学习"正常模板"(Welford T/S + 六爻标定 mu/sd),
              并把模型保存到 model_bottle.npz —— 之后无需重新学习。
  2. test   : 给一张图, 加载已保存的模型, 输出【正常 / 缺陷】判断 + 异常分数。
              --all  : 批量跑 test 集, 打印混淆矩阵与准确率。

判断逻辑(与 expA_ortho_online.py 的 S2 正交六爻一致):
  异常分数 = 六爻标准化偏离的均值(相对训练期正常分布 mu/sd)
  分数 > 阈值 -> 缺陷, 否则正常。
  阈值默认由训练期正常样本的分数分布自动定(mean + k*std), 也可 -t 手调。

用法:
  cd /home/lijinhan/.openclaw/workspace-quantum/quantum_ylyw
  # 学习(一次即可, 可指定用多少张正常图)
  ../.venv-quantum/bin/python bottle_manual_test.py train --n 30
  # 单图测试
  ../.venv-quantum/bin/python bottle_manual_test.py test data/mvtec/bottle/test/good/000.png
  ../.venv-quantum/bin/python bottle_manual_test.py test data/mvtec/bottle/test/broken_large/000.png
  # 批量测试整个 test 集
  ../.venv-quantum/bin/python bottle_manual_test.py test --all
  # 带可视化(保存残差热图)
  ../.venv-quantum/bin/python bottle_manual_test.py test <img> --viz
"""
import os, sys, json, argparse
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
MODEL_PATH = os.path.join(BASE, "model_bottle.npz")
FIG = os.path.join(BASE, "figures", "manual"); os.makedirs(FIG, exist_ok=True)

SIZE = (160, 160)

# ---- 复用主实验的加载/特征定义, 保证与已验证结果完全一致 ----
from skimage import io, color
from skimage.transform import resize
from skimage import filters, measure, morphology


def load_gray(path):
    im = io.imread(path)
    g = color.rgb2gray(im) if im.ndim == 3 else im.astype(float)
    g = (g - g.min()) / (np.ptp(g) + 1e-9)
    return resize(g, SIZE, anti_aliasing=True)


def load_rgb(path):
    im = io.imread(path)
    rgb = np.stack([im] * 3, -1) / 255.0 if im.ndim == 2 else im[..., :3] / 255.0
    return resize(rgb, SIZE, anti_aliasing=True)


def ortho6(R, Rc):
    """正交六爻: 与 expA_ortho_online.py 完全一致。"""
    out = np.zeros(6)
    Rb = filters.gaussian(R, 1.5)
    peaks = Rb - morphology.opening(Rb, morphology.disk(3))
    out[0] = np.percentile(peaks, 99.9)
    F = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = F.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = F[rad > min(h, w) * 0.25].sum() / (F.sum() + 1e-9)
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), 99.0)
    m = Rb.mean(); s = Rb.std() + 1e-9
    out[3] = float(((Rb - m) ** 3).mean() / s ** 3)
    out[4] = np.percentile(Rc[..., 1], 99.5) if Rc.ndim == 3 else np.percentile(Rc, 99.5)
    msk = Rb > np.percentile(Rb, 99.0); lab = measure.label(msk); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp)
    return out


def feats_of_templates(g, c, T, S, TC, SC):
    R = filters.gaussian(np.abs(g - T) / S, 2.0)
    Rc = np.abs(c - TC) / SC
    return ortho6(R, Rc)


def load_split(cat, split):
    d = os.path.join(DATA, cat, split); items = []
    if not os.path.isdir(d):
        return items
    for defect in sorted(os.listdir(d)):
        dd = os.path.join(d, defect)
        if not os.path.isdir(dd):
            continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                items.append((os.path.join(dd, f), defect))
    return items


# ============================== train ==============================
def cmd_train(args):
    cat = "bottle"
    train = load_split(cat, "train")
    n = min(args.n, len(train)) if args.n else len(train)
    order = np.random.default_rng(0).permutation(len(train))[:n]

    Tm = None; M2g = None; TCm = None; M2c = None
    for k, i in enumerate(order, 1):
        g = load_gray(train[i][0]); c = load_rgb(train[i][0])
        if k == 1:
            Tm = g.copy(); M2g = np.zeros_like(g); TCm = c.copy(); M2c = np.zeros_like(c)
        else:
            dg = g - Tm; Tm = Tm + dg / k; M2g = M2g + dg * (g - Tm)
            dc = c - TCm; TCm = TCm + dc / k; M2c = M2c + dc * (c - TCm)
        if k % 50 == 0 or k == n:
            print(f"  已学习 {k}/{n} 张正常图")

    Sg = np.sqrt(np.maximum(M2g / max(n - 1, 1), 1e-6)) + 1e-3
    SCg = np.sqrt(np.maximum(M2c / max(n - 1, 1), 1e-6)) + 1e-3

    # 用训练(正常)样本自我标定六爻分布 mu/sd
    Ftr = np.array([feats_of_templates(load_gray(train[i][0]), load_rgb(train[i][0]), Tm, Sg, TCm, SCg)
                    for i in order])
    mu = Ftr.mean(0); sd = Ftr.std(0) + 1e-9

    # 训练期正常样本的异常分数 -> 自动阈值
    tr_scores = np.array([np.abs((f - mu) / sd).mean() for f in Ftr])
    thr = float(tr_scores.mean() + args.k * tr_scores.std())

    np.savez(MODEL_PATH, Tm=Tm, Sg=Sg, TCm=TCm, SCg=SCg, mu=mu, sd=sd,
             thr=np.array([thr]), n=np.array([n]))
    print(f"\n✅ 模型已保存 -> {MODEL_PATH}")
    print(f"   正常图样本数 n = {n}")
    print(f"   自动阈值 thr = {thr:.4f}  (mean+{args.k}*std, 正常分数 {tr_scores.mean():.3f}±{tr_scores.std():.3f})")


# ============================== test ==============================
def score_one(path, model):
    g = load_gray(path); c = load_rgb(path)
    F = feats_of_templates(g, c, model["Tm"], model["Sg"], model["TCm"], model["SCg"])
    s = float(np.abs((F - model["mu"]) / model["sd"]).mean())
    return s, g, c


def cmd_test(args):
    if not os.path.exists(MODEL_PATH):
        print("❌ 未找到模型, 请先运行:  python bottle_manual_test.py train --n 30"); return
    m = dict(np.load(MODEL_PATH))
    thr = float(m["thr"][0])

    if args.all:
        test = load_split("bottle", "test")
        tp = tn = fp = fn = 0
        wrong = []
        for path, defect in test:
            s, _, _ = score_one(path, m)
            pred = 1 if s > thr else 0
            gt = 0 if defect == "good" else 1
            if gt == 1 and pred == 1: tp += 1
            elif gt == 0 and pred == 0: tn += 1
            elif gt == 0 and pred == 1: fp += 1; wrong.append((path, defect, s))
            else: fn += 1; wrong.append((path, defect, s))
        tot = tp + tn + fp + fn
        print(f"批量测试 (阈值 {thr:.4f}), 共 {tot} 张")
        print(f"  正常判对 TN={tn}  |  缺陷判对 TP={tp}")
        print(f"  误报 FP={fp} (正常被判缺陷)  |  漏报 FN={fn} (缺陷被判正常)")
        print(f"  准确率 = {(tp + tn) / tot:.4f}")
        print(f"  缺陷召回率 = {tp / max(tp + fn, 1):.4f}")
        if args.show_wrong and wrong:
            print("\n  判错样例:")
            for p, d, s in wrong[:20]:
                print(f"    [{d:12s}] score={s:.3f}  {os.path.relpath(p, BASE)}")
        return

    if not args.image:
        print("❌ 请给图片路径, 或用 --all 批量测试"); return
    if not os.path.exists(args.image):
        print(f"❌ 图片不存在: {args.image}"); return

    s, g, c = score_one(args.image, m)
    is_defect = s > thr
    print(f"图片: {args.image}")
    print(f"异常分数 = {s:.4f}   (阈值 {thr:.4f})")
    print("=" * 46)
    if is_defect:
        print("🔴 判定: 有缺陷  (DEFECT)")
    else:
        print("🟢 判定: 正常  (OK / good)")
    print("=" * 46)

    if args.viz:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from skimage import filters as f2
        R = f2.gaussian(np.abs(g - m["Tm"]) / m["Sg"], 2.0)
        fig, ax = plt.subplots(1, 3, figsize=(12, 4))
        ax[0].imshow(g, cmap="gray"); ax[0].set_title("input (gray)"); ax[0].axis("off")
        ax[1].imshow(R, cmap="hot"); ax[1].set_title("residual R=|x-T|/S"); ax[1].axis("off")
        ax[2].imshow(g, cmap="gray"); ax[2].imshow(R, cmap="jet", alpha=0.45)
        ax[2].set_title(f"overlay\nscore={s:.3f} thr={thr:.3f} -> {'DEFECT' if is_defect else 'OK'}")
        ax[2].axis("off")
        out = os.path.join(FIG, os.path.splitext(os.path.basename(args.image))[0] + "_score.png")
        plt.tight_layout(); fig.savefig(out, dpi=130)
        print(f"可视化已保存 -> {out}")


def main():
    ap = argparse.ArgumentParser(description="路径A bottle 手工测试工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_tr = sub.add_parser("train", help="学习正常模板并保存模型")
    p_tr.add_argument("--n", type=int, default=30, help="用多少张正常图(默认30)")
    p_tr.add_argument("--k", type=float, default=3.0, help="阈值 = mean + k*std (默认3.0)")
    p_tr.set_defaults(func=cmd_train)
    p_te = sub.add_parser("test", help="测试单张图或整个test集")
    p_te.add_argument("image", nargs="?", help="图片路径")
    p_te.add_argument("--all", action="store_true", help="批量测试整个test集")
    p_te.add_argument("--viz", action="store_true", help="保存残差热图")
    p_te.add_argument("--show-wrong", action="store_true", help="批量测试时列出判错样例")
    p_te.set_defaults(func=cmd_test)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
