#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在线无监督引擎 - 结果汇总与出图 (exp11)
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(BASE, "results"); FIG = os.path.join(BASE, "figures", "online_gen")
cats = ["bottle", "tile", "metal_nut", "toothbrush"]
data = {}
for c in cats:
    p = os.path.join(RES, f"online_gen_{c}.json")
    if os.path.exists(p):
        data[c] = json.load(open(p))

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
colors = {"bottle": "#d62728", "tile": "#1f77b4", "metal_nut": "#2ca02c", "toothbrush": "#9467bd"}
# (a) 准确率随使用次数(越用越准)
for c, d in data.items():
    rows = d["rows"]
    xs = [r["i"] for r in rows if r["acc"] is not None]
    ys = [r["acc"] for r in rows if r["acc"] is not None]
    # 平滑
    if len(ys) > 10:
        k = 10; ys_s = np.convolve(ys, np.ones(k) / k, mode="valid"); xs_s = xs[k - 1:]
    else:
        ys_s, xs_s = ys, xs
    axes[0].plot(xs_s, ys_s, "-", color=colors[c], label=f"{c} (final={ys[-1]:.3f})")
axes[0].set_xlabel("usage count (image index)"); axes[0].set_ylabel("cumulative accuracy (smoothed)")
axes[0].set_title("(a) Online unsupervised learning: accuracy vs usage")
axes[0].legend(fontsize=9); axes[0].grid(alpha=0.3); axes[0].set_ylim(0, 1.05)
# (b) 自适应阈值随时间
for c, d in data.items():
    rows = d["rows"]
    axes[1].plot([r["i"] for r in rows], [r["thr"] for r in rows], "-", color=colors[c], label=c)
axes[1].set_xlabel("usage count"); axes[1].set_ylabel("auto-adaptive threshold")
axes[1].set_title("(b) Threshold auto-adaptation (no manual params)")
axes[1].legend(fontsize=9); axes[1].grid(alpha=0.3)
plt.suptitle("Truly online, unsupervised, category-agnostic engine (zero hand-tuned params)")
plt.tight_layout()
out = os.path.join(FIG, "online_gen_all.png")
fig.savefig(out, dpi=150); print("saved", out)

# 汇总表
print("\n汇总(评价段):")
print(f"{'类别':10s} {'准确率':>8s} {'召回':>8s}")
accs = []
for c, d in data.items():
    accs.append(d["acc"])
    print(f"{c:10s} {d['acc']:8.4f} {d['recall']:8.4f}")
print(f"{'平均':10s} {np.mean(accs):8.4f}")
