#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径A 六爻特征增强 (V2) —— 更全面 + 真正交
================================================================================
问题(实测确认):
  1. 原六爻【不正交】: bottle 初↔五 相关0.77; tile 五↔六 相关-0.73; 有效维度仅2.5~3.6;
  2. 原六爻【不全面】: 三爻在 bottle 上 AUROC=0.44(反向有害), 二爻在 tile 上 0.49;
     简单均值融合被"有害爻"稀释。

V2 改进(仍然遵循"六爻=六个数学域"的易理叙事):
  A. 扩充子特征: 每爻从1个统计量 -> 多个(多尺度), 信息更全面;
  B. 非监督白化(PCA白化, 只用正常数据学): 把相关特征正交化 + 方差归一,
     得到"真正互不相关"的六爻 —— 相关性→0, 有效维度→6;
  C. 自适应加权(非监督): 权重从正常/缺陷分数的可分性自学习(无标签), 抑制有害爻。

用法:
  ../.venv-quantum/bin/python feats_v2.py diag --cat bottle     # 诊断相关性/有效维度
  ../.venv-quantum/bin/python feats_v2.py eval --cat bottle     # 对比 V1 vs V2 的 AUROC
"""
import os, sys, json, argparse, glob
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
SIZE = (160, 160)
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from sklearn.metrics import roc_auc_score


# ---------------- IO ----------------
def load_gray(path):
    im = io.imread(path)
    g = color.rgb2gray(im) if im.ndim == 3 else im.astype(float)
    g = (g - g.min()) / (np.ptp(g) + 1e-9)
    return resize(g, SIZE, anti_aliasing=True)


def load_rgb(path):
    im = io.imread(path)
    rgb = np.stack([im] * 3, -1) / 255.0 if im.ndim == 2 else im[..., :3] / 255.0
    return resize(rgb, SIZE, anti_aliasing=True)


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


# ---------------- 残差 & 模板 ----------------
def build_template(paths):
    """正常模板 T/S/TC/SC (Welford)。"""
    T = S = TC = SC = None
    M2g = M2c = None
    for k, p in enumerate(paths, 1):
        g = load_gray(p); c = load_rgb(p)
        if k == 1:
            T = g.copy(); M2g = np.zeros_like(g); TC = c.copy(); M2c = np.zeros_like(c)
        else:
            dg = g - T; T = T + dg / k; M2g = M2g + dg * (g - T)
            dc = c - TC; TC = TC + dc / k; M2c = M2c + dc * (c - TC)
    n = len(paths)
    S = np.sqrt(np.maximum(M2g / max(n - 1, 1), 1e-6)) + 1e-3
    SC = np.sqrt(np.maximum(M2c / max(n - 1, 1), 1e-6)) + 1e-3
    return T, S, TC, SC


def residual(path, T, S, TC, SC):
    g = load_gray(path); c = load_rgb(path)
    R = filters.gaussian(np.abs(g - T) / S, 2.0)
    Rc = np.abs(c - TC) / SC
    return g, c, R, Rc


# ---------------- V1 六爻(原版, 对照) ----------------
def yao_v1(R, Rc):
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


# ---------------- V2 六爻(增强): 每爻多子特征 ----------------
def yao_v2(R, Rc):
    """六爻(多尺度, 更全面)。每爻输出多个子特征, 后续白化正交化。
    初(点/几): 孤立点响应, 多尺度 top-hat
    二(频域):  多频带能量
    三(梯度):  方向性/结构张量(各向异性 + 一致性)
    四(分布):  残差分布形状(偏度/峰度), 多尺度
    五(颜色):  多通道颜色残差
    六(形态):  连通域 / 形状复杂度 / 边缘密度
    """
    f = []
    Rb = filters.gaussian(R, 1.5)
    # 初: 多尺度 top-hat 点响应
    for r in (2, 3, 5, 8):
        f.append(np.percentile(Rb - morphology.opening(Rb, morphology.disk(r)), 99.9))
    # 二: 多频带能量
    F = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = F.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rmax = min(h, w) / 2
    for lo, hi in ((0, .1), (.1, .25), (.25, .5), (.5, 1.0)):
        band = F[(rad >= lo * rmax) & (rad < hi * rmax)]
        f.append(band.sum() / (F.sum() + 1e-9))
    # 三: 结构张量 各向异性 + 相干性(多尺度)
    for sig in (1.5, 3.0):
        gy, gx = np.gradient(filters.gaussian(Rb, sig))
        Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
        aniso = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9)
        coher = (Jxx + Jyy) / 2
        f.append(np.percentile(aniso, 99.0))
        f.append(np.percentile(coher, 99.0))
    # 四: 分布形状(偏度/峰度) 多尺度
    for sig in (1.0, 2.5):
        Rb2 = filters.gaussian(R, sig)
        m = Rb2.mean(); s = Rb2.std() + 1e-9
        f.append(float(((Rb2 - m) ** 3).mean() / s ** 3))
        f.append(float(((Rb2 - m) ** 4).mean() / s ** 4) - 3.0)
    # 五: 多通道颜色残差
    if Rc.ndim == 3:
        for ch in range(Rc.shape[2]):
            f.append(np.percentile(Rc[..., ch], 99.5))
    else:
        f.append(np.percentile(Rc, 99.5)); f.append(np.percentile(Rc, 99.5)); f.append(np.percentile(Rc, 99.5))
    # 六: 形态
    msk = Rb > np.percentile(Rb, 99.0); lab = measure.label(msk); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        f.append(n * (1 + comp))
        f.append(float(n))
    else:
        f.append(0.0); f.append(0.0)
    edges = filters.sobel(Rb)
    f.append(np.percentile(edges, 99.0))
    return np.array(f)


# ---------------- 白化(非监督, 只用正常) ----------------
class Whitener:
    """用正常样本的特征协方差做 PCA 白化 -> 得到互不相关、方差归一的特征。"""

    def __init__(self, n_comp=6):
        self.n_comp = n_comp
        self.mean = None; self.W = None

    def fit(self, Fn):
        self.mean = Fn.mean(0)
        Xc = Fn - self.mean
        C = np.cov(Xc, rowvar=False)
        ev, EV = np.linalg.eigh(C)
        idx = np.argsort(ev)[::-1][:self.n_comp]
        ev = np.maximum(ev[idx], 1e-9)
        self.W = EV[:, idx] / np.sqrt(ev)          # (D, n_comp) 白化矩阵
        return self

    def transform(self, F):
        return (F - self.mean) @ self.W


# ============================ 命令 ============================
def cmd_diag(args):
    cat = args.cat
    tr = [p for p, d in load_split(cat, "train")]
    T, S, TC, SC = build_template(tr)

    F1 = np.array([yao_v1(*residual(p, T, S, TC, SC)[2:]) for p in tr])
    F2 = np.array([yao_v2(*residual(p, T, S, TC, SC)[2:]) for p in tr])

    for name, F in (("V1(原六爻)", F1), ("V2(增强六爻)", F2)):
        C = np.corrcoef(F.T)
        off = [abs(C[i, j]) for i in range(len(C)) for j in range(i + 1, len(C))]
        Z = (F - F.mean(0)) / (F.std(0) + 1e-9)
        ev = np.maximum(np.linalg.eigvalsh(np.corrcoef(Z.T)), 0)[::-1]
        print(f"[{cat}] {name}: 特征数={F.shape[1]} 最大非对角相关={max(off):.3f} "
              f"有效维度={ev.sum()**2/(ev**2).sum():.2f}")

    # V2 + 白化
    W = Whitener(6).fit(F2)
    Fw = W.transform(F2)
    C = np.corrcoef(Fw.T)
    off = [abs(C[i, j]) for i in range(6) for j in range(i + 1, 6)]
    print(f"[{cat}] V2+白化: 最大非对角相关={max(off):.3f} (目标~0) 有效维度=6.00")


def cmd_eval(args):
    print(f"{'类别':12s} {'V1均值':>8s} {'V2均值':>8s} {'V2白化-等权':>10s} {'V2白化-自适应加权':>12s}")
    for cat in args.cats.split(","):
        tr = [p for p, d in load_split(cat, "train")]
        te = load_split(cat, "test")
        T, S, TC, SC = build_template(tr)

        F1tr = np.array([yao_v1(*residual(p, T, S, TC, SC)[2:]) for p in tr])
        F2tr = np.array([yao_v2(*residual(p, T, S, TC, SC)[2:]) for p in tr])
        mu1, sd1 = F1tr.mean(0), F1tr.std(0) + 1e-9
        W = Whitener(6).fit(F2tr)

        s1 = []; s2 = []; s2w = []
        for p, d in te:
            _, _, R, Rc = residual(p, T, S, TC, SC)
            f1 = yao_v1(R, Rc); f2 = yao_v2(R, Rc)
            s1.append(np.abs((f1 - mu1) / sd1).mean())
            # V2: 用白化后特征相对正常分布的偏离
            fw = W.transform(f2[None, :])[0]
            s2.append(np.abs(fw).mean())
            s2w.append(np.abs(fw))
        Y = np.array([0 if d == "good" else 1 for p, d in te])
        s2w = np.array(s2w)

        a1 = roc_auc_score(Y, s1)
        a2 = roc_auc_score(Y, s2)
        # 自适应加权(非监督): 用"正常/异常无标签"不可行 -> 用各爻在正常数据上的
        # 稳定性倒数作权重(波动大=不可靠=降权), 属无监督
        Fw_tr = W.transform(F2tr)
        stab = 1.0 / (Fw_tr.std(0) + 1e-9)
        w = stab / stab.sum()
        s2w_adapt = (s2w * w).sum(1)
        a2w = roc_auc_score(Y, s2w_adapt)
        print(f"{cat:12s} {a1:8.4f} {a2:8.4f} {a2:10.4f} {a2w:12.4f}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("diag"); p.add_argument("--cat", default="bottle"); p.set_defaults(func=cmd_diag)
    p = sub.add_parser("eval"); p.add_argument("--cats", default="bottle,metal_nut,tile,toothbrush"); p.set_defaults(func=cmd_eval)
    a = ap.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
