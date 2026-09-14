#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig12_lightweight.py -- Fig.12 轻量化对比图 (存储 / 推理时延)
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

ours = json.load(open(os.path.join(RES, "exp29_ours.json")))
knn = json.load(open(os.path.join(RES, "exp29_knn.json")))
try:
    padim = json.load(open(os.path.join(RES, "exp29_padim.json")))
except: padim = None

methods = ["六爻阵列\n(本文)", "patch-kNN\n(PatchCore风格)", "PaDiM风格\n(逐patch对角)"]
store = [ours["store_MB"], knn["store_MB"], padim["store_MB"] if padim else 0]
infer = [ours["infer_ms"], knn["infer_ms"], padim["infer_ms"] if padim else 0]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.4))
colors = ["#1565c0", "#ef5350", "#ff9800"]

b1 = ax1.bar(methods, store, color=colors, edgecolor="black", lw=0.6)
for b, v in zip(b1, store):
    ax1.text(b.get_x()+b.get_width()/2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax1.set_ylabel("需存储的正常参考数据 (MB)", fontsize=10.5)
ax1.set_title("存储需求：六爻阵列省 50×+", fontsize=12, fontweight="bold")
ax1.grid(axis="y", ls=":", alpha=0.4); ax1.tick_params(axis="x", labelsize=9)

b2 = ax2.bar(methods, infer, color=colors, edgecolor="black", lw=0.6)
for b, v in zip(b2, infer):
    ax2.text(b.get_x()+b.get_width()/2, v, f"{v:.0f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax2.set_ylabel("单张推理时延 (ms)", fontsize=10.5)
ax2.set_title("推理速度：六爻阵列快 50×+", fontsize=12, fontweight="bold")
ax2.grid(axis="y", ls=":", alpha=0.4); ax2.tick_params(axis="x", labelsize=9)

fig.suptitle("轻量化优势：无记忆库，仅存模板 (MVTec bottle, CPU)", fontsize=13, fontweight="bold")
plt.tight_layout()
p = os.path.join(OUT, "fig12_lightweight.png")
plt.savefig(p, dpi=200)
print("saved:", p)
print(f"存储: 本文 {store[0]:.1f}MB vs kNN {store[1]:.1f}MB (省 {store[1]/store[0]:.0f}×)")
print(f"时延: 本文 {infer[0]:.0f}ms vs kNN {infer[1]:.0f}ms (快 {infer[1]/infer[0]:.0f}×)")
