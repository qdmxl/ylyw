#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig9_sensitive_radar.py -- Fig.9 各物品敏感爻指纹 (radar, exp8 数据)
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

data = json.load(open(os.path.join(RES, "exp8_auto_sensitive.json")))
yao_zh = ["初点", "二频", "三梯", "四分布", "五色", "六形"]
cats = [d["cat"] for d in data]
labels = [{"bottle": "bottle", "tile": "tile", "metal_nut": "metal_nut",
           "toothbrush": "toothbrush"}[c] for c in cats]

N = 6
angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
angles += angles[:1]
colors = ["#1565c0", "#2e7d32", "#c62828", "#ef6c00"]

fig, axes = plt.subplots(1, 4, figsize=(16, 4.4), subplot_kw=dict(polar=True))
for ax, d, lab, col in zip(axes, data, labels, colors):
    w = np.array(d["diag_w"], dtype=float)
    w = w / w.max()
    vals = w.tolist() + [w[0]]
    ax.plot(angles, vals, color=col, lw=2)
    ax.fill(angles, vals, color=col, alpha=0.25)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(yao_zh, fontsize=11)
    ax.set_ylim(0, 1.05); ax.set_yticks([0.5, 1.0]); ax.set_yticklabels([])
    top = np.argsort(-w)[:2]
    ax.set_title(f"{lab}\n敏感: {yao_zh[top[0]]} > {yao_zh[top[1]]}", fontsize=11.5, fontweight="bold")

fig.suptitle("各物品敏感爻指纹（零手调自动学出，Σ 对角权重归一）", fontsize=13.5, fontweight="bold")
plt.tight_layout()
p = os.path.join(OUT, "fig9_sensitive_radar.png")
plt.savefig(p, dpi=200)
print("saved:", p)
