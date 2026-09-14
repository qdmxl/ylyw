#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B+ 路线 (exp14): 手工六爻 (A) ⊕ 预训练六爻 (B) 融合
================================================================================
动机: metal_nut/bottle 靠预训练特征大幅提升, tile 靠手工纹理特征更好。
      两者互补 -> 融合应超过各自。
"""
import os, sys, json, argparse
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")

# A 路线
import exp12_discrim as A
# B 路线
import exp13_pretrained as B
from sklearn.metrics import roc_auc_score


def zstats(F0, F):
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    return np.abs((F - mu) / sd)


def run(cat, n_train=40):
    tr = [p for p, d in A.load_split(cat, "train")][:n_train]
    # ---- A: 手工六爻 ----
    Ta = np.mean([A.load_gray(p) for p in tr], 0); Sa = np.std([A.load_gray(p) for p in tr], 0) + 1e-3
    TCa = np.mean([A.load_rgb(p) for p in tr], 0); SCa = np.std([A.load_rgb(p) for p in tr], 0) + 1e-3
    def fa(p):
        g = A.load_gray(p); c = A.load_rgb(p)
        R = np.abs(g - Ta) / Sa; Rc = np.abs(c - TCa) / SCa
        return A.ortho6_enh(A.filters.gaussian(R, 2.0), Rc, use_lcn=False)
    FA0 = np.array([fa(p) for p in tr])
    # ---- B: 预训练六爻 ----
    T1, S1, T2, S2 = B.build_template(cat, n_train)
    def fb(p):
        return B.score_img(p, T1, S1, T2, S2)
    FB0 = np.array([fb(p) for p in tr])

    te = A.load_split(cat, "test")
    ZA, ZB, Y = [], [], []
    for p, d in te:
        ZA.append(zstats(FA0, fa(p))); ZB.append(zstats(FB0, fb(p))); Y.append(0 if d == "good" else 1)
    ZA = np.array(ZA); ZB = np.array(ZB); Y = np.array(Y)
    sA = ZA.mean(1); sB = ZB.mean(1)
    aucA = roc_auc_score(Y, sA); aucB = roc_auc_score(Y, sB)
    # 融合: 分数 rank 归一化后平均
    from scipy.stats import rankdata
    rA = rankdata(sA) / len(sA); rB = rankdata(sB) / len(sB)
    sF = 0.5 * rA + 0.5 * rB
    aucF = roc_auc_score(Y, sF)
    # 融合(特征级): 拼接 A/B 的 z 分数向量
    ZAB = np.concatenate([ZA, ZB], 1)
    aucCat = roc_auc_score(Y, ZAB.mean(1))
    print(f"[{cat}] A(手工)={aucA:.4f}  B(预训练)={aucB:.4f}  融合(rank)={aucF:.4f}  融合(拼接)={aucCat:.4f}")
    return dict(cat=cat, A=float(aucA), B=float(aucB), fusion_rank=float(aucF), fusion_cat=float(aucCat))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cat", nargs="?", default="all"); ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    cats = ["bottle", "tile", "metal_nut", "toothbrush"] if a.cat == "all" else [a.cat]
    out = [run(c, a.n) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp14_fusion.json"), "w"), ensure_ascii=False, indent=2)
    print("\n平均:")
    for k in ["A", "B", "fusion_rank", "fusion_cat"]:
        print(f"  {k:12s}: {np.mean([r[k] for r in out]):.4f}")
