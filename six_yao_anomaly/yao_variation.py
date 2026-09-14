#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爻变特征 V5 (理念: 要「爻变」不要「爻正交」)
================================================================================
核心思想(经用户纠正):
  六爻不是六个独立传感器, 而是【一个「变」的六阶段结构】。爻与爻天然关联(承/乘/应/比),
  相关不是冗余而是「卦的内在联系」。因此不应正交化 —— 正交化恰恰抹掉了"爻变的传导"。

爻变张量(丙式 = 时间维爻变 + 爻位间传导):
  设某样本(或时刻)的六爻向量 y ∈ R^6 (保留原始量纲, 不做正交)。
  对一个窗口/序列 [y(1),...,y(T)]:
  (1) 时间维爻变:   dy_i(t) = y_i(t) - y_i(t-1)
  (2) 爻位间传导:   P_ij = corr(dy_i, dy_j)  (6x6, 变化在爻之间的传导/耦合)
                    L_ij = argmax_t [dy_j(t) > thr] - argmax_t [dy_i(t) > thr]  (先后延迟)
  (3) 关联结构:     R = corr(y)  (6x6, 正常"卦象"的固有结构)
  异常检测子 = [时间爻变统计, 传导矩阵 P 偏离正常, 关联矩阵 R 偏离正常]

在静态 MVTec 上的"序列"构造: 用同一 category 的正常模板 -> 缺陷图作为"演化终点",
  构造 good -> defect 的插值序列, 得到爻变轨迹。这样即使没有真视频, 也能得到
  "爻变"的过程性描述(且用于知几实验: 看哪一爻先动)。

对照实验(论文核心):
  (a) 原始六爻特征 (V1思路: 六爻原始/标准值)      -> 判别力最强但不正交
  (b) 正交化六爻   (V3/V4思路)                    -> 正交但判别力↓
  (c) 爻变张量特征 (本文件)                       -> 预期: 保留关联 + 提升/保持判别力
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters, morphology, feature
from skimage.transform import resize
from skimage.morphology import skeletonize
from scipy import ndimage

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


# ============ 六爻: 用 V1 思路(原始/关联性最强的那套) ============
def ortho6(R, Rc):
    """V1 六爻定义(判别力最强, 爻间相关高 —— 正是我们要保留的"关联")。"""
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
    msk = Rb > np.percentile(Rb, 99.0); lab = measure_label(msk); n = lab.max()
    if n > 0:
        per = regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp)
    return out


def measure_label(m):
    return ndimage.label(m)[0]


def regionprops(lab):
    from skimage.measure import regionprops as rp
    return rp(lab)


def yao_from_img(g, rgb, T, S, TC, SC):
    R = filters.gaussian(np.abs(g - T) / S, 2.0)
    Rc = np.abs(rgb - TC) / SC
    return ortho6(R, Rc)


def build_templates(train, n=40):
    rg = [load_gray(p) for p in train[:n]]
    rc = [load_rgb(p) for p in train[:n]]
    T = np.mean(rg, 0); S = np.std(rg, 0) + 1e-3
    TC = np.mean(rc, 0); SC = np.std(rc, 0) + 1e-3
    F0 = np.array([yao_from_img(rg[i], rc[i], T, S, TC, SC) for i in range(len(rg))])
    return T, S, TC, SC, F0


# ============ 构造 good -> defect 的插值序列(得到"爻变轨迹") ============
def make_sequence_rgb(good_g, good_rgb, defect_g, defect_rgb, T_steps=12):
    """good 与 defect 的线性插值序列(灰度与彩色均插值, 保留颜色通道)。"""
    seq = []
    for k in range(T_steps + 1):
        a = k / T_steps
        sg = (1 - a) * good_g + a * defect_g
        if good_rgb.ndim == 3 and defect_rgb.ndim == 3:
            srgb = (1 - a) * good_rgb + a * defect_rgb
        else:
            srgb = np.stack([sg] * 3, -1)
        seq.append((sg, srgb))
    return seq


# ============ 爻变张量特征 ============
def yao_variation_features(seq_y):
    """seq_y: (T+1, 6) 六爻随时间的轨迹。返回爻变张量特征。
    - 时间维爻变: dy (取稳健统计)
    - 爻位间传导: P=corr(dy), 先后延迟 L
    - 关联结构:   R=corr(y)
    """
    y = np.array(seq_y)
    dy = np.diff(y, axis=0)                       # (T,6)
    feats = {}
    # (1) 时间维: 各爻变化幅度(稳健)
    feats["dy_mag"] = np.median(np.abs(dy), axis=0)              # (6)
    feats["dy_total"] = np.abs(y[-1] - y[0])                     # (6) 总变
    # (2) 传导: corr(dy) 上三角
    if dy.shape[0] >= 3 and dy.std(0).min() > 1e-12:
        P = np.corrcoef(dy.T)
        P = np.nan_to_num(P)
    else:
        P = np.zeros((6, 6))
    iu = np.triu_indices(6, 1)
    feats["P"] = P[iu]                                           # (15)
    # (3) 关联: corr(y) 上三角
    if y.shape[0] >= 3 and y.std(0).min() > 1e-12:
        R = np.corrcoef(y.T); R = np.nan_to_num(R)
    else:
        R = np.eye(6)
    feats["R"] = R[iu]                                           # (15)
    # (4) 先后延迟: 各爻首次"显著动"的时刻差
    thr = 3 * (np.median(np.abs(dy - np.median(dy, 0)), 0) * 1.4826 + 1e-9)
    first = []
    for i in range(6):
        idx = np.where(np.abs(dy[:, i]) > max(thr[i], 1e-9))[0]
        first.append(int(idx[0]) if len(idx) else -1)
    feats["first"] = np.array(first, float)                      # (6)
    return feats


def flatten_variation(feats):
    return np.concatenate([feats["dy_mag"], feats["dy_total"],
                           feats["P"], feats["R"], feats["first"]])


# ============ 对照实验 ============
def run_compare(cat, n_train=40, n_test=None, T_steps=12):
    from sklearn.metrics import roc_auc_score
    train = [p for p, d in load_split(cat, "train")]
    T, S, TC, SC, F0 = build_templates(train, n_train)
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    # 让六爻量纲近似可比(仅用于构造序列; 不做正交)
    def norm6(f):
        return (f - mu) / sd

    test = load_split(cat, "test")
    if n_test:
        test = test[:n_test]
    Yc, F_raw, F_orth, F_var = [], [], [], []
    rng = np.random.default_rng(0)
    good_imgs = [load_gray(p) for p, d in load_split(cat, "train")][:n_train]
    good_rgbs = [load_rgb(p) for p, d in load_split(cat, "train")][:n_train]
    for p, d in test:
        g = load_gray(p); rgb = load_rgb(p)
        f = yao_from_img(g, rgb, T, S, TC, SC)
        F_raw.append(norm6(f))
        # 正交化版本: 用正常样本白化
        W = np.linalg.inv(np.cov(F0.T) + 1e-6 * np.eye(6))
        L = np.linalg.cholesky(W).T
        F_orth.append(L @ (f - mu))
        # 爻变: 用随机 good 作起点(灰度+彩色), 到该测试图(灰度+彩色)的插值序列
        gi = rng.integers(len(good_imgs))
        good_g = good_imgs[gi]; good_rgb = good_rgbs[gi]
        seq = make_sequence_rgb(good_g, good_rgb, g, rgb, T_steps)
        seq_y = []
        for sg, srgb in seq:
            seq_y.append(norm6(yao_from_img(sg, srgb, T, S, TC, SC)))
        feats = yao_variation_features(seq_y)
        F_var.append(flatten_variation(feats))
        Yc.append(0 if d == "good" else 1)
    Yc = np.array(Yc)
    F_raw = np.array(F_raw); F_orth = np.array(F_orth); F_var = np.array(F_var)

    # 对爻变特征做【正常基线标准化】(用 good-good 序列估正常变化分布)
    base_var = []
    for _ in range(min(40, len(good_imgs) * 2)):
        i, j = rng.integers(len(good_imgs), size=2)
        seq = make_sequence_rgb(good_imgs[i], good_rgbs[i], good_imgs[j], good_rgbs[j], T_steps)
        sy = [norm6(yao_from_img(sg, srgb, T, S, TC, SC)) for sg, srgb in seq]
        base_var.append(flatten_variation(yao_variation_features(sy)))
    base_var = np.array(base_var)
    bmu, bsd = base_var.mean(0), base_var.std(0) + 1e-9
    Fvz = np.abs((F_var - bmu) / bsd)

    def auc(F):
        return roc_auc_score(Yc, np.abs(F).mean(1))
    def aucz(Fz):
        return roc_auc_score(Yc, Fz.mean(1))
    print(f"\n[{cat}] n_test={len(Yc)} (good={sum(Yc==0)} defect={sum(Yc==1)})")
    print(f"  (a) 原始六爻特征      AUROC={auc(F_raw):.4f}   维度={F_raw.shape[1]}")
    print(f"  (b) 正交化六爻特征    AUROC={auc(F_orth):.4f}  维度={F_orth.shape[1]}")
    print(f"  (c) 爻变张量特征      AUROC={aucz(Fvz):.4f}   维度={F_var.shape[1]}")
    # 精简版: 只用有信号的 dy + R (去掉噪声大的 P/L)
    sel = np.r_[0:12, 27:42]
    print(f"  (c') 爻变精简(dy+R)  AUROC={aucz(Fvz[:, sel]):.4f}  维度={len(sel)}")
    # 用 p90（而非 mean）聚合, 避免噪声成分平权稀释
    print(f"  (c'') 爻变 p90聚合     AUROC={roc_auc_score(Yc, np.percentile(Fvz[:, sel], 90, axis=1)):.4f}")
    # 爻变特征的内部结构: P/R 各自判别力
    print(f"      ├ 时间爻变(dy)   AUROC={aucz(Fvz[:,:12]):.4f}")
    print(f"      ├ 传导矩阵(P)    AUROC={aucz(Fvz[:,12:27]):.4f}")
    print(f"      ├ 关联矩阵(R)    AUROC={aucz(Fvz[:,27:42]):.4f}")
    print(f"      └ 先后延迟(L)    AUROC={aucz(Fvz[:,42:48]):.4f}")
    return dict(cat=cat, auc_raw=float(auc(F_raw)), auc_orth=float(auc(F_orth)),
                auc_var=float(aucz(Fvz)),
                auc_var_lite=float(aucz(Fvz[:, sel])) if 'sel' in dir() else None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", nargs="+", default=["bottle", "tile", "metal_nut", "toothbrush"])
    a = ap.parse_args()
    out = []
    for c in a.cats:
        out.append(run_compare(c))
    json.dump(out, open(os.path.join(BASE, "results", "exp6_yaobian_compare.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\n保存 results/exp6_yaobian_compare.json")
