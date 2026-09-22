#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验 (a): 敏感爻雷达图
出生每个物品"最敏感爻"的自动学出结果 (Sinv 对角权重) 可视化。
"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
YAO_EN = ["Y1 point", "Y2 freq", "Y3 grad", "Y4 dist", "Y5 color", "Y6 morph"]
YAO_CN = ["初(点)", "二(频)", "三(梯)", "四(分布)", "五(色)", "六(形)"]

data = json.load(open(os.path.join(BASE, "results", "exp8_auto_sensitive.json")))
cats = [d["cat"] for d in data]

# 雷达图
N = 6
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]
fig, axes = plt.subplots(2, 2, figsize=(13, 11), subplot_kw=dict(polar=True))
colors = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd"]
for ax, d, col in zip(axes.ravel(), data, colors):
    w = np.array(d["diag_w"], float)
    w = w / w.max()                     # 归一化到最大=1
    vals = w.tolist() + [w[0]]
    ax.plot(angles, vals, "-o", color=col, lw=2)
    ax.fill(angles, vals, color=col, alpha=0.25)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(YAO_CN, fontsize=10)
    ax.set_ylim(0, 1.05)
    ax.set_title(f"{d['cat']}  (AUROC maha={d['auc_maha']:.3f})", fontsize=12, pad=15)
plt.suptitle("Auto-discovered 'sensitive yao' per category (from normal yao-change covariance)",
             fontsize=13)
plt.tight_layout()
out = os.path.join(BASE, "figures", "exp8_sensitive_radar.png")
plt.savefig(out, dpi=150); print("saved", out)

# 热力图: 四物品 x 六爻 的敏感权重
M = np.array([np.array(d["diag_w"]) / np.max(d["diag_w"]) for d in data])
fig, ax = plt.subplots(figsize=(8, 4.2))
im = ax.imshow(M, cmap="YlOrRd", aspect="auto")
ax.set_xticks(range(6)); ax.set_xticklabels(YAO_CN)
ax.set_yticks(range(len(cats))); ax.set_yticklabels(cats)
for i in range(len(cats)):
    for j in range(6):
        ax.text(j, i, f"{M[i,j]:.2f}", ha="center", va="center",
                color="black" if M[i, j] < 0.6 else "white", fontsize=10)
ax.set_title("Sensitive-yao weight (normalized) per category  -- auto-learned")
plt.colorbar(im, label="relative sensitivity")
plt.tight_layout()
out2 = os.path.join(BASE, "figures", "exp8_sensitive_heatmap.png")
plt.savefig(out2, dpi=150); print("saved", out2)

# 打印排序摘要
print("\n各物品敏感爻排序:")
for d in data:
    w = np.array(d["diag_w"])
    order = np.argsort(-w)
    print(f"  {d['cat']:10s}: " + " > ".join(YAO_CN[i] for i in order))
