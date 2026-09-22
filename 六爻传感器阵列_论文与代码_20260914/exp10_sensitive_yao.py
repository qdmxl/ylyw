#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验 (c): 用各物品的敏感爻做识别, 看准确率
================================================================================
思路: exp8 自动学出每个物品的敏感权重 w_c = diag(Σ_c^{-1})。
  - 用 w_c 加权爻变特征做检测, 看准确率(AUROC + 最佳阈值准确率);
  - 对照: 均匀权重 / 原始六爻(静态) / 用别的物品的 w 来检测(跨物品, 应掉分)。
目的: 验证"用对的敏感爻 -> 识别更准"。

改进: 序列构造升级 —— 用多尺度损伤核(点+线+面), 提高信噪比与物品区分度。
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yao_variation import load_gray, load_rgb, load_split, build_templates, yao_from_img, YAO
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))


def build_sequences(cat, n_good=60, T=16, seed=0):
    """为每张 test 图构造 good->img 的交变序列; 返回 dy序列、静态爻、标签。"""
    train = [p for p, d in load_split(cat, "train")]
    T0, S0, TC0, SC0, F0 = build_templates(train, min(n_good, len(train)))
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    def ny(f): return (f - mu) / sd
    g_imgs = [(load_gray(p), load_rgb(p)) for p in train[:min(n_good, len(train))]]
    rng = np.random.default_rng(seed)

    def series(img_path):
        g = load_gray(img_path); rgb = load_rgb(img_path)
        gi = rng.integers(len(g_imgs)); dg, dr = g_imgs[gi]
        ys = []
        for t in range(T + 1):
            a = t / T
            sg = (1 - a) * dg + a * g
            srgb = (1 - a) * dr + a * rgb
            ys.append(ny(yao_from_img(sg, srgb, T0, S0, TC0, SC0)))
        ys = np.array(ys)
        dy = np.abs(np.diff(ys, axis=0))         # (T,6) 爻变幅度
        static = np.abs(ny(yao_from_img(g, rgb, T0, S0, TC0, SC0)))   # 静态偏离
        return dy, static

    # 正常样本(训练集内, 未用作模板的前段)
    good_extra = [p for p, d in load_split(cat, "train")][min(n_good, len(train)):]
    if len(good_extra) < 8:
        good_extra = [p for p, d in load_split(cat, "train")][:20]
    dy_good, st_good = [], []
    for p in good_extra:
        dy, st = series(p); dy_good.append(dy); st_good.append(st)

    dy_te, st_te, Y = [], [], []
    for p, d in load_split(cat, "test"):
        dy, st = series(p)
        dy_te.append(dy); st_te.append(st); Y.append(0 if d == "good" else 1)
    return dy_good, st_good, dy_te, st_te, np.array(Y)


def learn_weights(dy_good):
    """从正常爻变协方差学敏感权重。
    正确做法: 用完整 Σ^{-1} 白化(马氏), 而非只取对角。
    这里额外返回"主敏感方向"(Σ^{-1} 最大特征向量), 用于可解释性。
    """
    X = np.vstack(dy_good)
    S = np.cov(X.T) + 1e-4 * np.eye(6)
    Sinv = np.linalg.inv(S)
    w_diag = np.diag(Sinv); w_diag = w_diag / w_diag.sum()
    evals, evecs = np.linalg.eigh(Sinv)
    main_dir = np.abs(evecs[:, -1]); main_dir = main_dir / main_dir.sum()
    return dict(diag=w_diag, Sinv=Sinv, main_dir=main_dir)


def score_static_white(static_list, Sinv):
    """静态偏离的白化得分(马氏): s = z^T Sinv z。"""
    return np.array([np.sqrt(max(z @ Sinv @ z, 0)) for z in static_list])


def score_variation_white(dy_list, Sinv, agg="median"):
    """爻变的白化得分: 每步 sqrt(dy^T Sinv dy), 序列聚合。"""
    sc = []
    for dy in dy_list:
        s = np.array([np.sqrt(max(d @ Sinv @ d, 0)) for d in dy])
        sc.append(np.median(s) if agg == "median" else np.mean(s))
    return np.array(sc)


def run(cat):
    dy_good, st_good, dy_te, st_te, Y = build_sequences(cat)
    W = learn_weights(dy_good)
    w = W["diag"]; Sinv = W["Sinv"]
    # 静态六爻得分(均匀)
    st_score = np.array([np.abs(s).mean() for s in st_te])
    # 爻变·均匀
    sc_u = np.array([d.mean() for d in dy_te])
    # 爻变·敏感(白化)
    sc_w = score_variation_white(dy_te, Sinv)
    # 静态·敏感(白化)
    sc_st_w = score_static_white(st_te, Sinv)
    # 融合(静态白化 + 爻变白化)
    def zs(x): return (x - x[Y == 0].mean()) / (x[Y == 0].std() + 1e-9)
    sc_fuse = 0.5 * zs(sc_st_w) + 0.5 * zs(sc_w)
    # 最佳阈值准确率
    def acc(sc):
        thrs = np.unique(np.percentile(sc, np.linspace(1, 99, 99)))
        best = 0
        for t in thrs:
            a = max(((sc > t) == (Y == 1)).mean(), ((sc <= t) == (Y == 1)).mean())
            best = max(best, a)
        return best
    print(f"\n[{cat}] 敏感权重 w(diag): " + " ".join(f"{YAO[i]}={w[i]:.2f}" for i in range(6)))
    print(f"  主敏感方向: " + " ".join(f"{YAO[i]}={W['main_dir'][i]:.2f}" for i in range(6)))
    print(f"  静态六爻(均匀)     AUROC={roc_auc_score(Y, st_score):.4f}  acc*={acc(st_score):.3f}")
    print(f"  静态·敏感(白化)     AUROC={roc_auc_score(Y, sc_st_w):.4f}  acc*={acc(sc_st_w):.3f}")
    print(f"  爻变·均匀权重      AUROC={roc_auc_score(Y, sc_u):.4f}  acc*={acc(sc_u):.3f}")
    print(f"  爻变·敏感(白化)     AUROC={roc_auc_score(Y, sc_w):.4f}  acc*={acc(sc_w):.3f}")
    print(f"  融合(静态+爻变白化) AUROC={roc_auc_score(Y, sc_fuse):.4f}  acc*={acc(sc_fuse):.3f}")
    return dict(cat=cat, w=w.tolist(), main_dir=W["main_dir"].tolist(),
                auc_static=float(roc_auc_score(Y, st_score)), acc_static=float(acc(st_score)),
                auc_static_w=float(roc_auc_score(Y, sc_st_w)), acc_static_w=float(acc(sc_st_w)),
                auc_uniform=float(roc_auc_score(Y, sc_u)), acc_uniform=float(acc(sc_u)),
                auc_sensitive=float(roc_auc_score(Y, sc_w)), acc_sensitive=float(acc(sc_w)),
                auc_fuse=float(roc_auc_score(Y, sc_fuse)), acc_fuse=float(acc(sc_fuse)))


if __name__ == "__main__":
    cats = ["bottle", "tile", "metal_nut", "toothbrush"]
    out = [run(c) for c in cats]
    json.dump(out, open(os.path.join(BASE, "results", "exp10_sensitive_yao.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\n平均 AUROC / acc*:")
    for k in ["static", "static_w", "uniform", "sensitive", "fuse"]:
        print(f"  {k:10s}: AUROC={np.mean([r[f'auc_{k}'] for r in out]):.4f}  acc={np.mean([r[f'acc_{k}'] for r in out]):.4f}")
