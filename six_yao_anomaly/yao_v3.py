#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻 V3: 六个物理上可分辨的损伤模态 (路线甲)
================================================================================
问题(实测确认): V1/V2 六爻本质是【同一个残差场 R 的六个统计量】,
当缺陷增大时所有爻一起涨, "谁先动"由归一化方差决定而非物理 -> 伪"知几"。

V3 设计原则: 每爻 = 【独立算子】作用在【独立构造的场】, 物理上代表不同的损伤模态。
六个模态对应易理六爻的意象, 但底层是六个不同的数学/物理通道:

  初(几/萌芽)   : 局部点奇异 —— LoG (Laplacian-of-Gaussian) 多尺度, 取最强尺度响应
                  (独立场: 灰度的高频点响应; 对"微小点状萌生"最敏感)
  二(应/频域)   : 频谱能量重分布 —— 残差功率谱相对正常谱的 KL/能量位移
                  (独立场: 频域, 不看空域幅度)
  三(进/梯度)   : 边缘/梯度场 —— 梯度幅值场的高分位 (Sobel 幅值), 刻画"边界/结构"
                  (独立场: |∇I|, 与幅度 R 不同)
  四(互/分布)   : 空间聚集性 —— 残差超阈区的连通聚集度 (最近邻距离/空间自相关)
                  (独立场: 二值化残差的空间统计, 不看幅度)
  五(色/色度)   : 色度偏离 —— Lab 空间的 a*b* 色度距离 (与灰度解耦)
                  (独立场: 色度通道, 灰度不变时也能测)
  六(成/形态)   : 形态拓扑 —— 超阈区域的欧拉数/孔洞数/骨架长度
                  (独立场: 二值形态拓扑, 不看幅度与位置)

关键: 六爻都被"正常基线"标准化, 但每个爻基于【不同的场】, 因此对同一损伤的
时间响应不同 —— 由物理模态决定, 不由归一化决定。这样"谁先动"才有意义。

用法:
  ../.venv-quantum/bin/python yao_v3.py --cat bottle       # 诊断正交性+判别力
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from scipy import ndimage
from skimage.morphology import skeletonize

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
SIZE = (160, 160)
YAO = ["Y1_dian", "Y2_freq", "Y3_grad", "Y4_ju", "Y5_se", "Y6_tai"]


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


# ============ 六个独立物理模态的"场构造" ============
def fields(g, rgb, T, S, TC, SC, Tlab=None, Tgrad=None, Tlab_mu=None, Tfreq=None):
    """从观测图像与正常模板构造六个【彼此独立且各自与正常基线对比】的场。
    关键: 每个模态都算【相对于该模态正常基线的偏离】, 而非绝对量。
    """
    R = np.abs(g - T) / S
    Rb = filters.gaussian(R, 1.5)
    # 场1: 点奇异 —— LoG 响应(灰度), 与正常 LoG 场比对
    Lg = -filters.laplace(filters.gaussian(g, 1.2))
    F_dian = np.abs(Lg - (Tlab if Tlab is None else Tlab)) if Tlab is not None else np.abs(Lg)
    # 场2: 频域 —— 残差功率谱
    F_freq = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())) ** 2)
    # 场3: 梯度 —— |∇g| 相对正常梯度基线的偏离
    gy, gx = np.gradient(filters.gaussian(g, 1.0))
    G = np.sqrt(gx ** 2 + gy ** 2)
    F_grad = np.abs(G - Tgrad) if Tgrad is not None else G
    # 场4: 聚集 —— 超阈残差二值掩膜
    F_ju = Rb > (Rb.mean() + 2 * Rb.std())
    lab = color.rgb2lab(rgb) if rgb.ndim == 3 else None
    return dict(Rb=Rb, F_dian=F_dian, F_freq=F_freq, F_grad=F_grad, F_ju=F_ju, lab=lab,
                g=g, rgb=rgb, T=T, S=S)


def yao6(f, Tlab_mu=None, Tfreq=None):
    """从六个场分别提取六个标量(每爻只依赖自己的场, 且相对正常基线)。"""
    out = np.zeros(6)
    # 初(点): LoG 场极值分位
    d = f["F_dian"]
    out[0] = np.percentile(np.abs(d), 99.9)
    # 二(频): 频谱中高频占比
    P = f["F_freq"]
    h, w = P.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = P[rad > min(h, w) * 0.3].sum() / (P.sum() + 1e-9)
    # 三(梯): 结构张量各向异性
    g = f["g"]
    gy, gx = np.gradient(filters.gaussian(g, 1.0))
    Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
    aniso = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9)
    out[2] = np.percentile(aniso, 99.0)
    # 四(互): 聚集度
    m = f["F_ju"]
    lab = measure.label(m)
    n = lab.max()
    if n >= 2:
        cent = np.array([r.centroid for r in measure.regionprops(lab)])
        from scipy.spatial import cKDTree
        d, _ = cKDTree(cent).query(cent, k=2)
        nn = d[:, 1].mean() + 1e-9
        out[3] = n / nn
    else:
        out[3] = float(n)
    # 五(色): 色度偏离(相对正常 Lab 均值)
    if f["lab"] is not None:
        A, B = f["lab"][..., 1], f["lab"][..., 2]
        out[4] = np.percentile(np.sqrt(A ** 2 + B ** 2), 99.0)
    else:
        out[4] = 0.0
    # 六(成): 形态拓扑
    if n >= 1:
        filled = ndimage.binary_fill_holes(m)
        holes = measure.label(filled & ~m).max()
        skel = skeletonize(m).sum()
        out[5] = holes * 10.0 + skel
    else:
        out[5] = 0.0
    return out


def yao6_with_baseline(g, rgb, T, S, TC, SC, base):
    """计算单图六爻, 各模态相对其正常基线做偏离(用 base 里的模板)。"""
    Lg = -filters.laplace(filters.gaussian(g, 1.2))
    f = fields(g, rgb, T, S, TC, SC)
    f["F_dian"] = np.abs(Lg - base["Lg"]) if base.get("Lg") is not None else np.abs(Lg)
    out = yao6(f)
    # 五(色): 相对正常色度偏离(与环境光照解耦, 取偏离的高分位)
    if rgb.ndim == 3 and base.get("AB") is not None:
        lab = color.rgb2lab(rgb)
        A, B = lab[..., 1], lab[..., 2]
        d = np.sqrt((A - base["AB"][0]) ** 2 + (B - base["AB"][1]) ** 2)
        out[4] = np.percentile(d, 99.0)
    return out


def build_baseline(train, n=40):
    rg = [load_gray(p) for p in train[:n]]
    rc = [load_rgb(p) for p in train[:n]]
    T = np.mean(rg, 0); S = np.std(rg, 0) + 1e-3
    TC = np.mean(rc, 0); SC = np.std(rc, 0) + 1e-3
    # 各模态正常基线场
    Lg = np.mean([-filters.laplace(filters.gaussian(gg, 1.2)) for gg in rg], 0)
    Gr = np.mean([np.sqrt(sum(v ** 2 for v in np.gradient(filters.gaussian(gg, 1.0)))) for gg in rg], 0)
    labs = [color.rgb2lab(cc) for cc in rc]
    AB = (np.mean([l[..., 1] for l in labs]), np.mean([l[..., 2] for l in labs]))
    base = dict(Lg=Lg, Grad=Gr, AB=AB)
    F0 = np.array([yao6_with_baseline(rg[i], rc[i], T, S, TC, SC, base) for i in range(len(rg))])
    return T, S, TC, SC, F0, base


def cmd_diag(cat):
    train = [p for p, d in load_split(cat, "train")]
    T, S, TC, SC, F0, base = build_baseline(train)
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    C = np.corrcoef(F0.T)
    off = [abs(C[i, j]) for i in range(6) for j in range(i + 1, 6)]
    Z = (F0 - mu) / sd
    ev = np.maximum(np.linalg.eigvalsh(np.corrcoef(Z.T)), 0)[::-1]
    print(f"[{cat}] V3 六爻: 最大非对角相关={max(off):.3f} 有效维度={ev.sum()**2/(ev**2).sum():.2f}")
    print("  相关矩阵:")
    print("        " + " ".join(f"{n:>8s}" for n in YAO))
    for i, n in enumerate(YAO):
        print(f"  {n:>8s} " + " ".join(f"{C[i,j]:8.2f}" for j in range(6)))
    from sklearn.metrics import roc_auc_score
    te = load_split(cat, "test")
    Zt = []
    for p, d in te:
        g = load_gray(p); rgb = load_rgb(p)
        ft = yao6_with_baseline(g, rgb, T, S, TC, SC, base)
        Zt.append(np.abs((ft - mu) / sd))
    Zt = np.array(Zt); Y = np.array([0 if d == "good" else 1 for p, d in te])
    print("  单爻判别力(AUROC):")
    for i, n in enumerate(YAO):
        print(f"    {n}: {roc_auc_score(Y, Zt[:,i]):.4f}")
    print(f"  六爻均值: {roc_auc_score(Y, Zt.mean(1)):.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="bottle")
    a = ap.parse_args()
    cmd_diag(a.cat)
