#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验 (b): 收缩协方差改进爻变检测
问题: 直接求 Σ^{-1} 在高维/小样本/噪声下不稳 (tile/toothbrush 马氏距离输给均匀权重)。
方案: Ledoit-Wolf 收缩 Σ_shrunk = (1-a)·S + a·μ·I, 提稳定量。
对照: 均匀权重 / 原始逆 / Ledoit-Wolf 收缩 / OAS 收缩。
"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exp8_auto_sensitive import yao_series, yao_cov, mahalanobis_score
from sklearn.metrics import roc_auc_score
from sklearn.covariance import LedoitWolf, OAS

BASE = os.path.dirname(os.path.abspath(__file__))


def run(cat):
    dy_good, dy_test, Y = yao_series(cat)
    X = np.vstack(dy_good)                 # (n,6)
    S = yao_cov(dy_good)
    Sinv = np.linalg.inv(S)
    sc_raw = mahalanobis_score(dy_test, Sinv)
    # 均匀
    I = np.eye(6) / np.mean(np.diag(S))
    sc_u = mahalanobis_score(dy_test, I)
    # Ledoit-Wolf
    lw = LedoitWolf().fit(X)
    sc_lw = mahalanobis_score(dy_test, np.linalg.inv(lw.covariance_))
    # OAS
    oas = OAS().fit(X)
    sc_oas = mahalanobis_score(dy_test, np.linalg.inv(oas.covariance_))
    res = dict(cat=cat,
               uniform=float(roc_auc_score(Y, sc_u)),
               raw=float(roc_auc_score(Y, sc_raw)),
               ledoit=float(roc_auc_score(Y, sc_lw)),
               oas=float(roc_auc_score(Y, sc_oas)),
               lw_shrinkage=float(lw.shrinkage_))
    print(f"\n[{cat}] 收缩系数={lw.shrinkage_:.3f}")
    print(f"  均匀权重      AUROC={res['uniform']:.4f}")
    print(f"  原始逆Σ       AUROC={res['raw']:.4f}")
    print(f"  Ledoit-Wolf   AUROC={res['ledoit']:.4f}")
    print(f"  OAS           AUROC={res['oas']:.4f}")
    return res


if __name__ == "__main__":
    cats = ["bottle", "tile", "metal_nut", "toothbrush"]
    out = [run(c) for c in cats]
    json.dump(out, open(os.path.join(BASE, "results", "exp9_shrinkage.json"), "w"),
              ensure_ascii=False, indent=2)
    import numpy as np
    print("\n平均:")
    for k in ["uniform", "raw", "ledoit", "oas"]:
        print(f"  {k:8s}: {np.mean([r[k] for r in out]):.4f}")
