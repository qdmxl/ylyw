#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig7_layer_heatmap.py  --  Fig.7 层贡献热图 (15 类全量)
数据: results/exp31_full15_L{1,2,3}.json
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

def load(tag):
    d = json.load(open(os.path.join(RES, f"exp31_full15_{tag}.json")))
    return {x["cat"]: x["auc"] for x in d}

L1, L2, L3 = load("L1"), load("L2"), load("L3")
cats = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
        "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
        "wood", "zipper"]
M = np.array([[L1[c], L2[c], L3[c]] for c in cats])   # (15,3)

fig, ax = plt.subplots(figsize=(4.5, 8.2))
im = ax.imshow(M, cmap="RdYlGn", vmin=0.4, vmax=1.0, aspect="auto")
ax.set_xticks(range(3)); ax.set_xticklabels(["L1", "L2", "L3"], fontsize=11)
ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats, fontsize=9)
for i in range(len(cats)):
    for j in range(3):
        ax.text(j, i, f"{M[i,j]:.3f}", ha="center", va="center", fontsize=7.5,
                color="black")
ax.set_title("层贡献热图（15 类 图像级 AUROC）", fontsize=12, fontweight="bold", pad=10)
cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("AUROC", fontsize=10)

plt.tight_layout()
p = os.path.join(OUT, "fig7_layer_heatmap.png")
plt.savefig(p, dpi=200)
print("saved:", p)
print("平均: L1=%.4f L2=%.4f L3=%.4f" % (M[:,0].mean(), M[:,1].mean(), M[:,2].mean()))
