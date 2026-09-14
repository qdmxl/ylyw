#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻传感器阵列 —— 结果汇总(全量) 与对比
================================================================================
最优配置: L1+L3 多层六爻传感器融合 (无 kNN / 无 memory bank)
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")

# 全量结果
single = {"bottle": {"L1": 0.9913, "L2": 0.9976, "L3": 0.9976},
          "tile": {"L1": 0.6970, "L2": 0.8842, "L3": 0.9239},
          "metal_nut": {"L1": 0.8138, "L2": 0.8055, "L3": 0.9018},
          "toothbrush": {"L1": 0.9889, "L2": 0.8417, "L3": 0.8778}}
fuse = {"bottle": {"L1+L3": 0.9992, "L2+L3": 1.0000, "L1+L2+L3": 1.0000},
        "tile": {"L1+L3": 0.9260, "L2+L3": 0.9163, "L1+L2+L3": 0.9152},
        "metal_nut": {"L1+L3": 0.8778, "L2+L3": 0.8651, "L1+L2+L3": 0.8729},
        "toothbrush": {"L1+L3": 0.9833, "L2+L3": 0.8667, "L1+L2+L3": 0.9556}}

cats = ["bottle", "tile", "metal_nut", "toothbrush"]
print("=== 六爻传感器阵列 (全量, 无 kNN) ===")
print(f"{'配置':12s} " + " ".join(f"{c:>10s}" for c in cats) + f" {'平均':>8s}")
for L in ["L1", "L2", "L3"]:
    vals = [single[c][L] for c in cats]
    print(f"{'单层 '+L:12s} " + " ".join(f"{v:10.4f}" for v in vals) + f" {np.mean(vals):8.4f}")
for L in ["L1+L3", "L2+L3", "L1+L2+L3"]:
    vals = [fuse[c][L] for c in cats]
    print(f"{L:12s} " + " ".join(f"{v:10.4f}" for v in vals) + f" {np.mean(vals):8.4f}")
print()
print("=== 最终对比 (全量) ===")
final = {
    "Path A 原版(六爻在线)": [0.983, 0.833, 0.722, 0.886, "—"],
    "A 手工六爻(像素)": [0.983, 0.851, 0.754, 0.828, "✗"],
    "B 全局预训练六爻": [1.000, 0.889, 0.807, 0.844, "✗"],
    "六爻传感器 L3单层": [0.998, 0.924, 0.902, 0.878, "✗"],
    "六爻传感器 L1+L3": [0.999, 0.926, 0.878, 0.983, "✗"],
    "C patch级kNN": [1.000, 0.925, 0.984, 0.956, "✓"],
    "PaDiM (SOTA)": [0.980, 0.940, 0.970, 0.930, "✓"],
    "PatchCore (SOTA)": [1.000, 0.990, 1.000, 1.000, "✓"],
}
print(f"{'方法':22s} " + " ".join(f"{c:>10s}" for c in cats) + f" {'平均':>8s}  kNN")
for name, v in final.items():
    print(f"{name:22s} " + " ".join(f"{x:10.3f}" if isinstance(x, float) else f"{x:>10s}" for x in v[:4]) + f" {np.mean(v[:4]):8.4f}  {v[4]}")
