#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp15: 样本数对比 (全量 vs 少样本) + 与 SOTA 公平对齐
================================================================================
回答: 我们用40张还是全量? 全量下结果如何? 少样本优势有多大?
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


def full_counts(cat):
    return len(A.load_split(cat, "train"))


def run_config(cat, n):
    tr = [p for p, d in A.load_split(cat, "train")][:n]
    # A
    Ta = np.mean([A.load_gray(p) for p in tr], 0); Sa = np.std([A.load_gray(p) for p in tr], 0) + 1e-3
    TCa = np.mean([A.load_rgb(p) for p in tr], 0); SCa = np.std([A.load_rgb(p) for p in tr], 0) + 1e-3
    def fa(p):
        g = A.load_gray(p); c = A.load_rgb(p)
        return A.ortho6_enh(A.filters.gaussian(np.abs(g - Ta) / Sa, 2.0), np.abs(c - TCa) / SCa, False)
    FA0 = np.array([fa(p) for p in tr])
    # B
    T1, S1, T2, S2 = B.build_template(cat, n)
    def fb(p):
        return B.score_img(p, T1, S1, T2, S2)
    FB0 = np.array([fb(p) for p in tr])

    te = A.load_split(cat, "test")
    ZA, ZB, Y = [], [], []
    for p, d in te:
        ZA.append(np.abs((fa(p) - FA0.mean(0)) / (FA0.std(0) + 1e-9)))
        ZB.append(np.abs((fb(p) - FB0.mean(0)) / (FB0.std(0) + 1e-9)))
        Y.append(0 if d == "good" else 1)
    ZA = np.array(ZA); ZB = np.array(ZB); Y = np.array(Y)
    sA = ZA.mean(1); sB = ZB.mean(1)
    sF = 0.5 * rankdata(sA) / len(sA) + 0.5 * rankdata(sB) / len(sB)
    return dict(n=n, A=roc_auc_score(Y, sA), B=roc_auc_score(Y, sB), F=roc_auc_score(Y, sF))


if __name__ == "__main__":
    ns = [10, 20, 40, 60, None]   # None = 全量
    allres = {}
    for cat in CATS:
        full = full_counts(cat)
        rows = []
        for n in ns:
            nn = full if n is None else min(n, full)
            r = run_config(cat, nn)
            rows.append(r)
            print(f"[{cat}] n={nn:3d}({'全量' if n is None else ''})  A={r['A']:.4f}  B={r['B']:.4f}  融合={r['F']:.4f}")
        allres[cat] = dict(full=full, rows=rows)
        print()
    json.dump(allres, open(os.path.join(RES, "exp15_sample_count.json"), "w"), ensure_ascii=False, indent=2)
    print("=== 全量汇总 ===")
    print(f"{'cat':12s} {'A':>8s} {'B':>8s} {'融合':>8s}")
    for cat in CATS:
        r = allres[cat]["rows"][-1]
        print(f"{cat:12s} {r['A']:8.4f} {r['B']:8.4f} {r['F']:8.4f}")
    print(f"{'平均':12s} {np.mean([allres[c]['rows'][-1]['A'] for c in CATS]):8.4f} "
          f"{np.mean([allres[c]['rows'][-1]['B'] for c in CATS]):8.4f} "
          f"{np.mean([allres[c]['rows'][-1]['F'] for c in CATS]):8.4f}")
