#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp16 (优化版): 稳定少样本曲线, 特征预提取+缓存, 随机采样×多次重复。
================================================================================
A 特征: 手工六爻 (依赖模板 -> 需按子集重算, 但快)
B 特征: 预训练 ResNet (与模板无关, 预提取一次即可)
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp12_discrim as A
import exp13_pretrained as B
from sklearn.metrics import roc_auc_score
from scipy.stats import rankdata

CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
NS = [5, 10, 20, 40, 80, None]
R = 5


def b_feat(path):
    f1, f2 = B.extract(path)
    return f1, f2


def run_once(cat, tr, te, trB, teB):
    # ---- A: 手工六爻 (模板依赖, 需重算) ----
    Ta = np.mean([A.load_gray(p) for p in tr], 0); Sa = np.std([A.load_gray(p) for p in tr], 0) + 1e-3
    TCa = np.mean([A.load_rgb(p) for p in tr], 0); SCa = np.std([A.load_rgb(p) for p in tr], 0) + 1e-3
    def fa(p):
        g = A.load_gray(p); c = A.load_rgb(p)
        return A.ortho6_enh(A.filters.gaussian(np.abs(g - Ta) / Sa, 2.0), np.abs(c - TCa) / SCa, False)
    FA0 = np.array([fa(p) for p in tr])
    # ---- B: 预训练特征 (已缓存) ----
    F1 = [b[0] for b in trB]; F2 = [b[1] for b in trB]
    T1 = np.mean(F1, 0); S1 = np.std(F1, 0) + 1e-3; T2 = np.mean(F2, 0); S2 = np.std(F2, 0) + 1e-3
    def fb_from(b):
        f1, f2 = b
        return B.six_yao_feat(np.abs(f2 - T2) / S2, np.abs(f1 - T1) / S1)
    FB0 = np.array([fb_from(b) for b in trB])

    ZA, ZB, Y = [], [], []
    for (p, d), b in zip(te, teB):
        ZA.append(np.abs((fa(p) - FA0.mean(0)) / (FA0.std(0) + 1e-9)))
        ZB.append(np.abs((fb_from(b) - FB0.mean(0)) / (FB0.std(0) + 1e-9)))
        Y.append(0 if d == "good" else 1)
    ZA = np.array(ZA); ZB = np.array(ZB); Y = np.array(Y)
    sA = ZA.mean(1); sB = ZB.mean(1)
    sF = 0.5 * rankdata(sA) / len(sA) + 0.5 * rankdata(sB) / len(sB)
    return roc_auc_score(Y, sA), roc_auc_score(Y, sB), roc_auc_score(Y, sF)


if __name__ == "__main__":
    res = {}
    for cat in CATS:
        train_paths = [p for p, d in A.load_split(cat, "train")]
        te = A.load_split(cat, "test")
        nfull = len(train_paths)
        print(f"[{cat}] 预提取 B 特征 ({nfull} train + {len(te)} test)...", flush=True)
        trB_all = [b_feat(p) for p in train_paths]
        teB = [b_feat(p) for p, d in te]
        rows = []
        for n in NS:
            nn = nfull if n is None else min(n, nfull)
            reps = 1 if nn == nfull else R
            Aa, Bb, Ff = [], [], []
            for r in range(reps):
                rng = np.random.default_rng(1000 + r)
                idx = rng.choice(nfull, nn, replace=False)
                tr = [train_paths[i] for i in idx]
                trB = [trB_all[i] for i in idx]
                a, b, f = run_once(cat, tr, te, trB, teB)
                Aa.append(a); Bb.append(b); Ff.append(f)
            row = dict(n=nn, A=float(np.mean(Aa)), A_std=float(np.std(Aa)),
                       B=float(np.mean(Bb)), B_std=float(np.std(Bb)),
                       F=float(np.mean(Ff)), F_std=float(np.std(Ff)))
            rows.append(row)
            print(f"[{cat}] n={nn:3d}: A={row['A']:.4f}±{row['A_std']:.3f}  B={row['B']:.4f}±{row['B_std']:.3f}  融合={row['F']:.4f}±{row['F_std']:.3f}", flush=True)
        res[cat] = rows
        print(flush=True)
    json.dump(res, open(os.path.join(RES, "exp16_fewshot_curve.json"), "w"), ensure_ascii=False, indent=2)
    print("=== 全量汇总 ===")
    for cat in CATS:
        r = res[cat][-1]
        print(f"{cat:12s} A={r['A']:.4f}  B={r['B']:.4f}  融合={r['F']:.4f}")
    print(f"{'平均':12s} A={np.mean([res[c][-1]['A'] for c in CATS]):.4f}  "
          f"B={np.mean([res[c][-1]['B'] for c in CATS]):.4f}  融合={np.mean([res[c][-1]['F'] for c in CATS]):.4f}")
