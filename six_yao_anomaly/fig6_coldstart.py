#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig6_coldstart.py -- Fig.6 冷启动污染鲁棒性 (exp30 数据)
"""
import os, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results"); OUT = os.path.join(BASE, "figures_paper")
os.makedirs(OUT, exist_ok=True)
for fp in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

d = json.load(open(os.path.join(RES, "exp30_coldstart.json")))
ks = [0, 1, 2, 3, 5]
colors = {"bottle": "#1565c0", "tile": "#2e7d32", "metal_nut": "#c62828", "toothbrush": "#ef6c00"}

fig, ax = plt.subplots(figsize=(7.5, 4.8))
for cat, col in colors.items():
    ys = [d[cat][str(k)] for k in ks]
    ax.plot(ks, ys, "o-", color=col, lw=2, ms=6, label=cat)

ax.set_xlabel("冷启动注入的缺陷样本数 k（放在正常流最前）", fontsize=11)
ax.set_ylabel("最终 AUROC（全部正常样本学习后）", fontsize=11)
ax.set_title("冷启动污染鲁棒性：注入缺陷后最终精度几乎不变\n（Welford 1/n 遗忘使早期污染被稀释）",
             fontsize=12, fontweight="bold")
ax.set_xticks(ks); ax.grid(ls=":", alpha=0.4); ax.legend(fontsize=10)
ax.set_ylim(0.68, 1.0)

# 标注 bottle 几乎平坦
ax.annotate("bottle: 0.975→0.969", xy=(5, d["bottle"]["5"]), xytext=(3.2, 0.95),
            fontsize=9, color="#1565c0",
            arrowprops=dict(arrowstyle="->", color="#1565c0", lw=1))

plt.tight_layout()
p = os.path.join(OUT, "fig6_coldstart.png")
plt.savefig(p, dpi=200)
print("saved:", p)
