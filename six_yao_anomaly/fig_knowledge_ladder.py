#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig_knowledge_ladder.py  --  Fig.4 知识载体阶梯图 (信号无关性核心证据)
================================================================================
数据来源: results/exp27_pretrain_ablation.json (4类全量)
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

# 中文字体
for fp in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

d = json.load(open(os.path.join(RES, "exp27_pretrain_ablation.json")))
cats = ["bottle", "tile", "metal_nut", "toothbrush"]
cat_zh = {"bottle": "bottle", "tile": "tile", "metal_nut": "metal_nut", "toothbrush": "toothbrush"}

# 四级: 随机卷积 / 手工固定卷积 / 手工六爻(路径A像素版) / 预训练ResNet
# 路径A 手工六爻全量: bottle 0.983, tile 0.851, metal_nut 0.754, toothbrush 0.828
pathA = {"bottle": 0.983, "tile": 0.851, "metal_nut": 0.754, "toothbrush": 0.828}

levels = [
    ("随机初始化\n卷积 (无知识)", "random", "#9e9e9e"),
    ("手工固定\n卷积核", "handmade", "#ff9800"),
    ("手工六爻\n信号 (路径A)", "pathA", "#2196f3"),
    ("ImageNet\n预训练 ResNet", "pretrained", "#4caf50"),
]

avg = {}
for name, key, _ in levels:
    if key == "pathA":
        avg[name] = np.mean([pathA[c] for c in cats])
    else:
        avg[name] = np.mean([d[key][c] for c in cats])

fig, ax = plt.subplots(figsize=(7.2, 4.4))
names = [n for n, _, _ in levels]
vals = [avg[n] for n in names]
colors = [c for _, _, c in levels]
bars = ax.bar(names, vals, color=colors, edgecolor="black", linewidth=0.8, width=0.62)

for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, v + 0.012, f"{v:.3f}",
            ha="center", va="bottom", fontsize=11, fontweight="bold")

ax.axhline(vals[-1], ls="--", color="#4caf50", alpha=0.5, lw=1)
ax.set_ylabel("平均 AUROC (4 类, 全量)", fontsize=11)
ax.set_title("知识在信号里，不在框架里：六爻框架的信号无关性", fontsize=12.5, fontweight="bold")
ax.set_ylim(0.6, 1.0)
ax.grid(axis="y", ls=":", alpha=0.4)
ax.tick_params(axis="x", labelsize=9.5)

# 箭头标注趋势
ax.annotate("", xy=(3, vals[3]+0.03), xytext=(0, vals[0]+0.03),
            arrowprops=dict(arrowstyle="->", color="crimson", lw=1.8, alpha=0.6))
ax.text(1.5, 0.985, "知识含量递增 →", color="crimson", fontsize=10, ha="center", style="italic")

plt.tight_layout()
p = os.path.join(OUT, "fig4_knowledge_ladder.png")
plt.savefig(p, dpi=200)
print("saved:", p)
for n in names:
    print(f"  {n.replace(chr(10),' ')}: {avg[n]:.4f}")
