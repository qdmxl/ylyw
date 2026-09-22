#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp19: C 路线 (patch级kNN) 的少样本曲线 —— 差异化优势
================================================================================
SOTA (PatchCore) 需要全量正常样本建 memory bank; 我们测它在少量样本下的表现,
并与我们 A/B/融合 路线对比, 展示"数据效率"优势。
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp17_patchknn as P
from sklearn.metrics import roc_auc_score

CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
NS = [5, 10, 20, 40, None]
R = 3


if __name__ == "__main__":
    res = {}
    for cat in CATS:
        tr_all = [p for p, d in P.load_split(cat, "train")]
        te = P.load_split(cat, "test")
        nfull = len(tr_all)
        # 预提取 test 特征(一次)
        teF = [P.features(p) for p, d in te]
        Y = np.array([0 if d == "good" else 1 for _, d in te])
        rows = []
        for n in NS:
            nn = nfull if n is None else min(n, nfull)
            reps = 1 if nn == nfull else R
            aucs = []
            for r in range(reps):
                rng = np.random.default_rng(1000 + r)
                idx = rng.choice(nfull, nn, replace=False)
                tr = [tr_all[i] for i in idx]
                bank = P.patch_bank(tr, max_patches=min(20000, nn * 1024), seed=r)
                S = [P.knn_score(F, bank).max() for F in teF]
                aucs.append(roc_auc_score(Y, np.array(S)))
            rows.append(dict(n=nn, auc=float(np.mean(aucs)), std=float(np.std(aucs))))
            print(f"[{cat}] C路线 n={nn:3d}: AUROC={np.mean(aucs):.4f}±{np.std(aucs):.3f}", flush=True)
        res[cat] = rows
        print(flush=True)
    json.dump(res, open(os.path.join(RES, "exp19_C_fewshot.json"), "w"), ensure_ascii=False, indent=2)
    print("=== C路线 少样本汇总 ===")
    for n in NS:
        vals = []
        for cat in CATS:
            nn = len([p for p, d in P.load_split(cat, "train")]) if n is None else n
            row = [r for r in res[cat] if r["n"] == min(nn, len([p for p, d in P.load_split(cat, "train")]))]
            if row: vals.append(row[0]["auc"])
        print(f"  n={str(n):5s}: 平均={np.mean(vals):.4f}")
