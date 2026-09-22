#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig10_main_results.py  --  Fig.10 主结果对比 (15 类全量)
================================================================================
数据: 手工(handmade) / 预训练六爻 L1 / L2 / L3 / PaDiM(参照) / PatchCore(参照)
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results")
OUT = os.path.join(BASE, "figures_paper")
os.makedirs(OUT, exist_ok=True)

for fp in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

def load(fn):
    return {x["cat"]: x["auc"] for x in json.load(open(os.path.join(RES, fn)))}

cats = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
        "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
        "wood", "zipper"]
H = load("exp32_ladder15_handmade.json")
L1, L2, L3 = load("exp31_full15_L1.json"), load("exp31_full15_L2.json"), load("exp31_full15_L3.json")

# PaDiM / PatchCore 文献报告值 (15 类, 官方 image-level AUROC)
PADIM = [0.979,0.886,0.968,0.991,0.945,0.989,0.994,0.952,0.947,0.752,0.975,0.970,0.970,0.987,0.919]
PATCH = [1.000,0.993,0.981,0.997,0.997,1.000,1.000,1.000,0.988,0.982,1.000,0.997,1.000,0.993,0.996]

methods = [
    ("手工(无预训练)", [H[c] for c in cats], "#90caf9"),
    ("六爻 L1", [L1[c] for c in cats], "#64b5f6"),
    ("六爻 L2", [L2[c] for c in cats], "#1e88e5"),
    ("六爻 L3(本文)", [L3[c] for c in cats], "#0d47a1"),
]

x = np.arange(len(cats)); w = 0.20
fig, ax = plt.subplots(figsize=(14, 5.5))
for i, (name, vals, col) in enumerate(methods):
    off = (i - len(methods)/2 + 0.5) * w
    ax.bar(x + off, vals, w, label=name, color=col, edgecolor="black", linewidth=0.4)

means = {name: np.mean(vals) for name, vals, _ in methods}
# 参照均值线 (文献报告: PaDiM 0.975 / PatchCore 0.992)
ax.axhline(0.975, ls="--", lw=1.2, color="#a1887f", label="PaDiM 平均(0.975)")
ax.axhline(0.992, ls="--", lw=1.2, color="#616161", label="PatchCore 平均(0.992)")
ax.set_xticks(x); ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=9)
ax.set_ylabel("图像级 AUROC", fontsize=11)
ax.set_title("MVTec AD 主结果对比（15 类，图像级 AUROC）", fontsize=13, fontweight="bold")
ax.set_ylim(0.35, 1.06)
ax.legend(ncol=6, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.34), framealpha=0.9)
ax.grid(axis="y", ls=":", alpha=0.4)
txt = "  平均:  " + "   ".join(f"{n}={means[n]:.3f}" for n,_,_ in methods)
ax.text(0.5, 1.02, txt, transform=ax.transAxes, ha="center", fontsize=8.5, color="#333")

plt.tight_layout()
p = os.path.join(OUT, "fig10_main_results.png")
plt.savefig(p, dpi=180, bbox_inches="tight")
print("saved:", p)
for n, v, _ in methods:
    print(f"  {n}: {np.mean(v):.4f}")
