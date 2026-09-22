#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爻变自动敏感特征发现 (exp8)
================================================================================
理念: "针对不同物品, 最敏感的特征应该不一样"。爻变能否【自动捕获】该敏感特征?

方法: 对物品 c, 用其【正常样本的爻变协方差】Σ_c = cov(dy) 做马氏距离检测:
      S = dy^T Σ_c^{-1} dy
  - Σ_c 的【大方差方向】(该物品天然波动大) 被 Σ_c^{-1} 抑制
  - Σ_c 的【协同方向】(多爻共同响应缺陷) 被放大
  => 检测权重自动偏向该物品的"敏感爻/敏感协同", 无需手调。

验证:
  1) 每物品学 Σ_c, 报告 Σ_c^{-1} 各爻权重 -> "敏感爻"是否因物品而异?
  2) 马氏距离检测 AUROC vs 均匀权重(基线)。
  3) 用【别的物品】的 Σ 来检测 -> 掉多少? (证明 Σ 是物品特异的)
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yao_variation import load_gray, load_rgb, load_split, build_templates, yao_from_img, YAO
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))


def yao_series(cat, n_good=40, T=16, seed=0):
    """为 train/*(正常)与 test/* 每张图, 构造 good->img 的爻变序列, 返回 (dy列表, 标签)。"""
    train = [p for p, d in load_split(cat, "train")]
    T0, S0, TC0, SC0, F0 = build_templates(train, n_good)
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    def ny(f): return (f - mu) / sd
    g_imgs = [(load_gray(p), load_rgb(p)) for p in train[:n_good]]
    rng = np.random.default_rng(seed)

    def dy_of(img_path):
        g = load_gray(img_path); rgb = load_rgb(img_path)
        gi = rng.integers(len(g_imgs)); dg, dr = g_imgs[gi]
        ys = []
        for t in range(T + 1):
            a = t / T
            sg = (1 - a) * dg + a * g; srgb = (1 - a) * dr + a * rgb
            ys.append(ny(yao_from_img(sg, srgb, T0, S0, TC0, SC0)))
        ys = np.array(ys)
        return np.abs(np.diff(ys, axis=0))          # (T,6)

    # 正常: 用 train 图(除模板)自比
    dy_good = [dy_of(p) for p in train[n_good:n_good + 30]] if len(train) > n_good + 5 else [dy_of(p) for p in train[:10]]
    dy_test, Y = [], []
    for p, d in load_split(cat, "test"):
        dy_test.append(dy_of(p)); Y.append(0 if d == "good" else 1)
    return dy_good, dy_test, np.array(Y)


def yao_cov(dy_list):
    """物品正常爻变协方差 Σ_c (6x6): 用每步 dy 的样本。"""
    X = np.vstack([d for d in dy_list])             # (n,6) 步骤级
    return np.cov(X.T) + 1e-4 * np.eye(6)


def mahalanobis_score(dy_seq, Sig_inv):
    """序列级马氏距离: 取该序列各步马氏距离的中位/均值。"""
    scores = []
    for dy in dy_seq:
        s = np.einsum("ij,jk,ik->i", dy, Sig_inv, dy)
        scores.append(np.median(s))
    return np.array(scores)


def run(cat):
    dy_good, dy_test, Y = yao_series(cat)
    S = yao_cov(dy_good)
    Sinv = np.linalg.inv(S)
    # 各爻"敏感权重": Sinv 的对角(自身方差校正) + 行和(协同)
    diag_w = np.diag(Sinv)
    off_w = np.abs(Sinv).sum(1) - np.abs(diag_w)
    print(f"\n[{cat}] 物品正常爻变协方差 Σ_c 的逆 Sinv")
    print("  各爻敏感权重(越大越敏感):")
    order = np.argsort(-diag_w)
    for i in order:
        print(f"    {YAO[i]:8s}: 自身校正={diag_w[i]:8.3f}  协同={off_w[i]:8.3f}")
    # 检测
    sc = mahalanobis_score(dy_test, Sinv)
    # 均匀权重基线
    I = np.eye(6) * (1.0 / np.mean(np.diag(S)))
    sc_u = mahalanobis_score(dy_test, I)
    print(f"  马氏距离(自动学Σ) AUROC = {roc_auc_score(Y, sc):.4f}")
    print(f"  均匀权重(不计协方差) AUROC = {roc_auc_score(Y, sc_u):.4f}")
    # 相关性矩阵可解释
    D = np.sqrt(np.diag(S))
    C = S / np.outer(D, D)
    iu = np.triu_indices(6, 1)
    top = sorted(zip(iu[0], iu[1], C[iu]), key=lambda x: -abs(x[2]))[:3]
    print("  最强关联对:", ", ".join(f"{YAO[i]}-{YAO[j]}({c:.2f})" for i, j, c in top))
    return dict(cat=cat, auc_maha=float(roc_auc_score(Y, sc)),
                auc_uniform=float(roc_auc_score(Y, sc_u)),
                diag_w=diag_w.tolist())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", nargs="+", default=["bottle", "tile", "metal_nut", "toothbrush"])
    a = ap.parse_args()
    out = [run(c) for c in a.cats]
    json.dump(out, open(os.path.join(BASE, "results", "exp8_auto_sensitive.json"), "w"),
              ensure_ascii=False, indent=2)
    print("\n保存 results/exp8_auto_sensitive.json")
