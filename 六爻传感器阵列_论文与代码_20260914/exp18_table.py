#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp18: 我们方法的最终对比表 (三条路线 vs SOTA)
================================================================================
汇总 A(手工六爻) / B(预训练六爻全局) / 融合 / C(patch级kNN局部峰值)
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")

# 已跑出的结果
A = {  # 全量, 手工六爻
    "bottle": 0.9825, "tile": 0.8510, "metal_nut": 0.7537, "toothbrush": 0.8278}
B = {  # 全量, 预训练六爻(全局)
    "bottle": 1.0000, "tile": 0.8885, "metal_nut": 0.8074, "toothbrush": 0.8444}
F = {  # 全量, 融合
    "bottle": 1.0000, "tile": 0.9226, "metal_nut": 0.8099, "toothbrush": 0.8611}
C = {  # patch级kNN(局部峰值)
    "bottle": 1.0000, "tile": 0.9340, "metal_nut": 0.9814, "toothbrush": 0.9417}
SOTA_PaDiM = {"bottle": 0.98, "tile": 0.94, "metal_nut": 0.97, "toothbrush": 0.93}
SOTA_PatchCore = {"bottle": 1.00, "tile": 0.99, "metal_nut": 1.00, "toothbrush": 1.00}

cats = ["bottle", "tile", "metal_nut", "toothbrush"]
print(f"{'方法':28s} " + " ".join(f"{c:>10s}" for c in cats) + f" {'平均':>8s}")
for name, d in [("A 手工六爻(全局)", A), ("B 预训练六爻(全局)", B),
                ("A⊕B 融合", F), ("C patch级kNN(局部)", C),
                ("PaDiM (SOTA)", SOTA_PaDiM), ("PatchCore (SOTA)", SOTA_PatchCore)]:
    vals = [d[c] for c in cats]
    print(f"{name:28s} " + " ".join(f"{v:10.4f}" for v in vals) + f" {np.mean(vals):8.4f}")

json.dump(dict(A=A, B=B, F=F, C=C, PaDiM=SOTA_PaDiM, PatchCore=SOTA_PatchCore),
          open(os.path.join(RES, "exp18_final_table.json"), "w"), ensure_ascii=False, indent=2)
