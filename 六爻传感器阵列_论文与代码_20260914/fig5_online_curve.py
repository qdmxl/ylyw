#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig5_online_curve.py  --  Fig.5 在线学习曲线 (AUROC vs 样本数)
================================================================================
数据: results/expA_ortho_online.json (bottle 等, S1 peak vs S2 ortho)
"""
import os, json, glob
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

d = json.load(open(os.path.join(RES, "expA_ortho_online.json")))
fig, ax = plt.subplots(figsize=(7.6, 4.8))
colors = {"bottle": "#1565c0", "tile": "#2e7d32", "metal_nut": "#c62828", "toothbrush": "#ef6c00"}

for cat, recs in d.items():
    ns = [r["n_train"] for r in recs]
    s1 = [r["s1_peak"] for r in recs]
    s2 = [r.get("s2_ortho") for r in recs]
    c = colors.get(cat, "gray")
    ax.plot(ns, s1, "-o", ms=3, lw=1.8, color=c, label=f"{cat} (峰值判据)")
    if s2 and s2[0] is not None:
        ax.plot(ns, s2, "--s", ms=3, lw=1.3, color=c, alpha=0.55,
                label=f"{cat} (正交判据)")

ax.set_xlabel("在线累计正常样本数 n", fontsize=11)
ax.set_ylabel("AUROC", fontsize=11)
ax.set_title("在线学习曲线：随样本数增长而提升（峰值判据 > 正交判据）",
             fontsize=12, fontweight="bold")
ax.grid(ls=":", alpha=0.4)
ax.legend(fontsize=8, ncol=2, loc="lower right")
ax.set_ylim(0.55, 1.02)

plt.tight_layout()
p = os.path.join(OUT, "fig5_online_curve.png")
plt.savefig(p, dpi=200)
print("saved:", p)
