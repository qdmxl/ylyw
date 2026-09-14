#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig8_fewshot.py  --  Fig.8 少样本曲线
================================================================================
数据: exp16 (A/B/Fusion), exp19 (C-route kNN)
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

A = json.load(open(os.path.join(RES, "exp16_fewshot_curve.json")))
C = json.load(open(os.path.join(RES, "exp19_C_fewshot.json")))

def avg_over(d, key):
    cats = list(d.keys())
    ns = [r["n"] for r in d[cats[0]]]
    mean = []
    for i in range(len(ns)):
        mean.append(np.mean([d[c][i][key] for c in cats]))
    return ns, mean

fig, ax = plt.subplots(figsize=(7.6, 4.9))

# A 手工 / B 预训练 / F 融合
nsA, mA = avg_over(A, "A"); nsB, mB = avg_over(A, "B"); nsF, mF = avg_over(A, "F")
ax.plot(nsA, mA, "-o", color="#42a5f5", label="A 手工六爻", lw=2, ms=4)
ax.plot(nsB, mB, "-s", color="#66bb6a", label="B 预训练六爻", lw=2, ms=4)
ax.plot(nsF, mF, "-^", color="#ab47bc", label="A⊕B 融合", lw=2, ms=4)
# C 路线 kNN
nsC, mC = avg_over(C, "auc")
ax.plot(nsC, mC, "-D", color="#ef5350", label="C patch级kNN", lw=2, ms=4)

ax.set_xlabel("正常训练样本数 n", fontsize=11)
ax.set_ylabel("平均 AUROC (4 类)", fontsize=11)
ax.set_title("少样本曲线：C 路线（kNN）数据效率最高，n=10 即达 0.956",
             fontsize=12, fontweight="bold")
ax.grid(ls=":", alpha=0.4)
ax.legend(fontsize=9.5, loc="lower right")
ax.set_ylim(0.70, 1.02)

# 标注
ax.axvline(10, ls=":", color="gray", alpha=0.6)
ax.text(10.5, 0.73, "n=10", color="gray", fontsize=8.5)

plt.tight_layout()
p = os.path.join(OUT, "fig8_fewshot.png")
plt.savefig(p, dpi=200)
print("saved:", p)
print("A:", [round(x,3) for x in mA])
print("B:", [round(x,3) for x in mB])
print("C:", [round(x,3) for x in mC])
print("F:", [round(x,3) for x in mF])
