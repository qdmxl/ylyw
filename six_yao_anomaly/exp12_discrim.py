#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判别力增强 (exp12): 多尺度 + 局部对比度归一化
================================================================================
问题: tile(0.81)/metal_nut(0.66) 判别力不足。它们缺陷小、与背景对比度低。
思路:
  1) 多尺度残差: 在多个高斯尺度上算残差并取最大响应(小缺陷在细尺度突出);
  2) 局部对比度归一化(LCN): 残差除以局部背景波动, 让"绝对小但相对突出"的缺陷显现;
  3) 六爻在这些增强场上重新提取。
对照: 原单尺度残差 vs 多尺度 vs 多尺度+LCN。
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES = os.path.join(BASE, "results")
SIZE = (160, 160)


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


def lcn(R, sigma=8.0):
    """局部对比度归一化: (R - 局部均值) / (局部std + eps)。"""
    mu = filters.gaussian(R, sigma)
    sd = np.sqrt(np.maximum(filters.gaussian(R ** 2, sigma) - mu ** 2, 0)) + 1e-3
    return (R - mu) / sd


def multiscale_residual(g, T, S, sigmas=(0.0, 1.0, 2.0, 3.0)):
    """多尺度残差: 在多个模糊尺度上算 |g-T|/S, 取逐像素最大(增强小缺陷)。"""
    Rs = []
    for s in sigmas:
        gg = filters.gaussian(g, s) if s > 0 else g
        TT = filters.gaussian(T, s) if s > 0 else T
        Rs.append(np.abs(gg - TT) / (S + 1e-6))
    return np.max(np.stack(Rs, 0), 0)


def ortho6_enh(R, Rc, use_lcn=False):
    """六爻(改进: 用 max 型统计, 捕捉局部高对比缺陷, 尤其 metal_nut/划痕类)。"""
    out = np.zeros(6)
    Rb = filters.gaussian(R, 1.5)
    if use_lcn:
        Rb = lcn(Rb, 6.0)
    # 初(点/几): 峰值型 —— 残差场的极值(而非分位)
    out[0] = Rb.max()
    # 二(频): 高频能量占比
    F = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = F.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = F[rad > min(h, w) * 0.25].sum() / (F.sum() + 1e-9)
    # 三(梯): 结构张量各向异性
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), 99.0)
    # 四(分布): 偏离均值的最强值 / 标准差(峰度型, 对局部异常敏感)
    s = Rb.std() + 1e-9
    out[3] = np.abs(Rb - Rb.mean()).max() / s
    # 五(色): 颜色残差峰值
    out[4] = Rc.max() if Rc.ndim == 3 else Rc.max()
    # 六(形): 高对比连通区域峰值密度
    msk = Rb > Rb.max() * 0.6; lab = measure.label(msk); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp) * Rb.max()
    return out


def run(cat, n_train=40):
    from sklearn.metrics import roc_auc_score
    tr = [p for p, d in load_split(cat, "train")]
    T = np.mean([load_gray(p) for p in tr[:n_train]], 0)
    S = np.std([load_gray(p) for p in tr[:n_train]], 0) + 1e-3
    TC = np.mean([load_rgb(p) for p in tr[:n_train]], 0)
    SC = np.std([load_rgb(p) for p in tr[:n_train]], 0) + 1e-3

    # 正常样本各方案的六爻分布
    def feats(path, mode):
        g = load_gray(path); c = load_rgb(path)
        Rc = np.abs(c - TC) / SC
        if mode == "base":
            R = np.abs(g - T) / S
            return ortho6_enh(filters.gaussian(R, 2.0), Rc, use_lcn=False)
        if mode == "multiscale":
            R = multiscale_residual(g, T, S)
            return ortho6_enh(filters.gaussian(R, 2.0), Rc, use_lcn=False)
        if mode == "ms_lcn":
            R = multiscale_residual(g, T, S)
            return ortho6_enh(filters.gaussian(R, 2.0), Rc, use_lcn=True)

    res = {}
    for mode in ["base", "multiscale", "ms_lcn"]:
        F0 = np.array([feats(p, mode) for p in tr[:n_train]])
        mu, sd = F0.mean(0), F0.std(0) + 1e-9
        te = load_split(cat, "test")
        Z, Y = [], []
        for p, d in te:
            Z.append(np.abs((feats(p, mode) - mu) / sd)); Y.append(0 if d == "good" else 1)
        Z = np.array(Z); Y = np.array(Y)
        res[mode] = roc_auc_score(Y, Z.mean(1))
        # 最强单爻
        per_yao = [roc_auc_score(Y, Z[:, i]) for i in range(6)]
        res[mode + "_best_yao"] = max(per_yao)
    print(f"[{cat}] 判别力对比:")
    print(f"  原单尺度         AUROC={res['base']:.4f} (最强单爻={res['base_best_yao']:.4f})")
    print(f"  多尺度           AUROC={res['multiscale']:.4f} (最强单爻={res['multiscale_best_yao']:.4f})")
    print(f"  多尺度+LCN       AUROC={res['ms_lcn']:.4f} (最强单爻={res['ms_lcn_best_yao']:.4f})")
    return dict(cat=cat, base=float(res['base']), multiscale=float(res['multiscale']),
                ms_lcn=float(res['ms_lcn']))


if __name__ == "__main__":
    cats = ["bottle", "tile", "metal_nut", "toothbrush"]
    out = [run(c) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp12_discrim_power.json"), "w"), ensure_ascii=False, indent=2)
    print("\n平均:")
    for k in ["base", "multiscale", "ms_lcn"]:
        print(f"  {k:12s}: {np.mean([r[k] for r in out]):.4f}")
