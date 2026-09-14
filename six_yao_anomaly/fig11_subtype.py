#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig11_subtype.py  --  Fig.11 各缺陷子类 AUROC 分解 (C 路线)
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

d = json.load(open(os.path.join(RES, "exp28_subtype.json")))
cat_zh = {"bottle": "bottle", "tile": "tile", "metal_nut": "metal_nut", "toothbrush": "toothbrush"}

labels, vals, colors_c = [], [], []
palette = {"bottle": "#1565c0", "tile": "#2e7d32", "metal_nut": "#c62828", "toothbrush": "#ef6c00"}
for cat in ["bottle", "tile", "metal_nut", "toothbrush"]:
    for sub, v in d[cat].items():
        labels.append(f"{cat}\n{sub}")
        vals.append(v)
        colors_c.append(palette[cat])

fig, ax = plt.subplots(figsize=(10.5, 4.6))
bars = ax.bar(range(len(labels)), vals, color=colors_c, edgecolor="black", lw=0.6, width=0.7)
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.008, f"{v:.3f}", ha="center", fontsize=8, rotation=90)

ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=7.8)
ax.set_ylabel("AUROC (vs good)", fontsize=11)
ax.set_title("各缺陷子类分解（C 路线 patch-kNN）：仅 gray_stroke / scratch / defective 是短板",
             fontsize=11.5, fontweight="bold")
ax.set_ylim(0.6, 1.05); ax.grid(axis="y", ls=":", alpha=0.4)

plt.tight_layout()
p = os.path.join(OUT, "fig11_subtype.png")
plt.savefig(p, dpi=200)
print("saved:", p)
