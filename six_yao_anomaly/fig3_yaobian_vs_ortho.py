#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig3_yaobian_vs_ortho.py  --  Fig.3 爻变判据 vs 正交判据
================================================================================
数据: results/exp6_yaobian_compare.json
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

d = json.load(open(os.path.join(RES, "exp6_yaobian_compare.json")))
cats = [r["cat"] for r in d]
raw = [r["auc_raw"] for r in d]
orth = [r["auc_orth"] for r in d]
var = [r["auc_var"] for r in d]
varl = [r["auc_var_lite"] for r in d]

x = np.arange(len(cats)); w = 0.2
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.bar(x-1.5*w, raw, w, label="原始六爻(残差)", color="#90caf9", edgecolor="black", lw=0.5)
ax.bar(x-0.5*w, orth, w, label="正交化 (PCA)", color="#ef9a9a", edgecolor="black", lw=0.5)
ax.bar(x+0.5*w, var, w, label="完全爻变", color="#a5d6a7", edgecolor="black", lw=0.5)
ax.bar(x+1.5*w, varl, w, label="爻变(轻量)", color="#66bb6a", edgecolor="black", lw=0.5)

ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=10.5)
ax.set_ylabel("AUROC", fontsize=11)
ax.set_title("爻变判据 vs 正交判据：相关性是信息，不应被正交化消除",
             fontsize=12, fontweight="bold")
ax.set_ylim(0.45, 1.05)
ax.legend(fontsize=9, ncol=4, loc="upper center")
ax.grid(axis="y", ls=":", alpha=0.4)

# 平均标注
avgs = {"原始": np.mean(raw), "正交": np.mean(orth), "完全爻变": np.mean(var), "轻量爻变": np.mean(varl)}
txt = "  平均:  " + "  |  ".join(f"{k} {v:.3f}" for k, v in avgs.items())
ax.text(0.5, -0.19, txt, transform=ax.transAxes, ha="center", fontsize=9.5)

plt.tight_layout()
p = os.path.join(OUT, "fig3_yaobian_vs_ortho.png")
plt.savefig(p, dpi=200, bbox_inches="tight")
print("saved:", p)
for k, v in avgs.items():
    print(f"  {k}: {v:.4f}")
