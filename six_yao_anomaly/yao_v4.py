#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻 V4 (路线甲-1): 六个经典独立图像算子
================================================================================
教训: 用"图像残差的六个统计量"做六爻 -> 要么退化(正常图恒定), 要么相关(读同一残差)。
V4 改用六个【经典独立图像算子】, 每个天生正交且都对缺陷敏感:

  初(几/点)    : Hessian 小尺度斑点响应 (DoG/LoG) —— 对"点状萌生"最敏感
  二(应/频)    : 小波包高频带能量占比 —— 频域独立通道
  三(进/梯度)  : Gabor 多方向滤波的最强方向响应 (结构/方向性)
  四(互/局部)  : LBP(局部二值模式)纹理谱的方差/熵 —— 局部微观纹理
  五(色/色度)  : Lab 色度(a*,b*)的稳健偏离 —— 与灰度解耦
  六(成/形态)  : 形态学粒度谱(开运算能量随尺度衰减率) —— 形态/尺度

每个算子作用于【原始图】, 统计量相对正常基线标准化。
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters, morphology, feature
from skimage.transform import resize

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


# ================= 六个经典独立算子的标量特征 =================
def _dog_spot(g):
    """初(点): Hessian/DoG 斑点响应最强值 (小尺度)。"""
    dog = filters.gaussian(g, 1.0) - filters.gaussian(g, 2.5)
    return np.percentile(np.abs(dog), 99.5)


def _wavelet_energy(g):
    """二(频): 小波包高频带能量占比。优先用 pywt(Haar); 无则用 scipy 的 DWT/差分近似。"""
    try:
        from pywt import dwt2
        cA, (cH, cV, cD) = dwt2(g, "haar", mode="periodization")
        hi = cH ** 2 + cV ** 2 + cD ** 2
        return float(hi.sum() / ((hi.sum() + cA ** 2).sum()) + 1e-9)
    except Exception:
        # 回退: 用 Haar 近似(下采样+差分) 的高频能量占比
        a = g[::2, ::2]
        hx = np.diff(g, axis=1)[::2, ::2]
        hy = np.diff(g, axis=0)[::2, ::2]
        hi = hx ** 2 + hy ** 2
        return float(hi.sum() / ((hi.sum() + a ** 2).sum()) + 1e-9)


def _gabor_dir(g):
    """三(进/梯度): 8 方向 Gabor 响应, 取最强方向与方向各向异性。"""
    strong = 0.0
    resp = []
    for th in np.linspace(0, np.pi, 8, endpoint=False):
        r = np.abs(filters.gabor(g, frequency=0.15, theta=th))
        resp.append(r.mean()); strong = max(strong, r.max())
    resp = np.array(resp)
    aniso = (resp.max() - resp.min()) / (resp.mean() + 1e-9)
    return float(strong * (1 + aniso))


def _lbp_entropy(g):
    """四(互/局部): LBP 纹理直方图熵 + 方差。"""
    gq = (g * 255).astype(np.uint8)
    lbp = feature.local_binary_pattern(gq, 8, 1, method="uniform")
    hist, _ = np.histogram(lbp, bins=np.arange(0, 12), density=True)
    p = hist + 1e-9
    ent = -np.sum(p * np.log(p))
    return float(ent + hist.std())


def _chroma_dev(rgb):
    """五(色): Lab 色度 (a*,b*) 的稳健高分位偏离。"""
    if rgb.ndim != 3:
        return 0.0
    lab = color.rgb2lab(rgb)
    A, B = lab[..., 1], lab[..., 2]
    return np.percentile(np.sqrt(A ** 2 + B ** 2), 99.0)


def _granulometry(g):
    """六(成/形态): 形态学粒度谱 (开运算能量随尺度衰减)。"""
    gq = (g * 255).astype(np.uint8)
    e = []
    for r in [1, 2, 3, 5, 8]:
        op = morphology.opening(gq, morphology.disk(r))
        e.append(float(op.mean()))
    e = np.array(e)
    # 衰减率(相邻尺度相对差)
    dec = np.mean(np.abs(np.diff(e)) / (np.abs(e[:-1]) + 1e-9))
    return float(e.std() + dec)


def yao6(g, rgb):
    return np.array([_dog_spot(g), _wavelet_energy(g), _gabor_dir(g),
                     _lbp_entropy(g), _chroma_dev(rgb), _granulometry(g)])


def build_baseline(train, n=40):
    rg = [load_gray(p) for p in train[:n]]
    rc = [load_rgb(p) for p in train[:n]]
    F0 = np.array([yao6(rg[i], rc[i]) for i in range(len(rg))])
    return F0, rg, rc


def _scale_of(F0):
    mu = F0.mean(0); sd = F0.std(0)
    gmax = np.abs(F0).max(0) - np.abs(F0).min(0) + 1e-12
    floor = np.maximum(0.05 * np.abs(mu) + 1e-6, 0.02 * gmax)
    return mu, np.maximum(sd, floor)


def cmd_diag(cat):
    train = [p for p, d in load_split(cat, "train")]
    F0, _, _ = build_baseline(train)
    mu, sd = _scale_of(F0)
    C = np.corrcoef(F0.T)
    off = [abs(C[i, j]) for i in range(6) for j in range(i + 1, 6)]
    Z = (F0 - mu) / sd
    ev = np.maximum(np.linalg.eigvalsh(np.corrcoef(Z.T)), 0)[::-1]
    print(f"[{cat}] V4 六爻: 最大非对角相关={max(off):.3f} 有效维度={ev.sum()**2/(ev**2).sum():.2f}")
    print("         " + " ".join(f"{n:>8s}" for n in YAO))
    for i, n in enumerate(YAO):
        print(f"  {n:>8s} " + " ".join(f"{C[i,j]:8.2f}" for j in range(6)))
    from sklearn.metrics import roc_auc_score
    te = load_split(cat, "test")
    Zt = []
    for p, d in te:
        g = load_gray(p); rgb = load_rgb(p)
        ft = yao6(g, rgb)
        Zt.append(np.abs((ft - mu) / sd))
    Zt = np.array(Zt); Y = np.array([0 if d == "good" else 1 for p, d in te])
    print("  单爻判别力(AUROC):")
    for i, n in enumerate(YAO):
        print(f"    {n}: {roc_auc_score(Y, Zt[:,i]):.4f}")
    print(f"  六爻均值: {roc_auc_score(Y, Zt.mean(1)):.4f}")
    print(f"  正常样本各爻 mean/sd: " + ", ".join(f"{mu[i]:.3g}/{sd[i]:.3g}" for i in range(6)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="bottle")
    a = ap.parse_args()
    cmd_diag(a.cat)
