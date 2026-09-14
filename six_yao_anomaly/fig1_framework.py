#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig1_framework.py  --  Fig.1 六爻框架总览图
================================================================================
图像/特征 → 残差场 → 六爻传感器阵列 → 爻变判据 → 异常分数 → 自适应阈值判决
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib import font_manager

BASE = os.path.dirname(os.path.abspath(__file__))
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

fig, ax = plt.subplots(figsize=(12, 5.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 5.2); ax.axis("off")

def box(x, y, w, h, text, fc, ec="black", fs=10.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                                fc=fc, ec=ec, lw=1.3))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal", wrap=True)

def arrow(x1, y1, x2, y2, color="#333"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=16, lw=1.6, color=color))

# ---- 阶段1: 输入信号 ----
box(0.15, 3.5, 1.8, 1.2, "输入信号\n(图像 / 特征场 F)", "#e3f2fd", fs=10)
box(0.15, 1.6, 1.8, 1.2, "在线模板 T\n+ 尺度 SD\n(Welford 增量)", "#fff3e0", fs=9.5)

# ---- 阶段2: 残差场 ----
box(2.4, 2.55, 1.7, 1.1, "残差场\nR = |F−T| / SD", "#f3e5f5", fs=11, bold=True)

# ---- 阶段3: 六爻传感器阵列 ----
box(4.5, 3.7, 2.6, 1.25, "六爻传感器阵列\n(6 个可解释读数)", "#e8f5e9", fs=11, bold=True)
yao_labels = ["初 残差峰值", "二 高频比", "三 结构各向异性",
              "四 非高斯残差", "五 颜色残差", "六 连通域密度"]
for i, t in enumerate(yao_labels):
    ax.text(4.62, 3.62 - i*0.185, "• " + t, fontsize=8.2, va="top")

# ---- 阶段4: 爻变判据 ----
box(4.5, 1.35, 2.6, 1.15, "爻变判据\n读数偏离 + 关联结构变化\n(非正交)", "#fce4ec", fs=10, bold=True)

# ---- 阶段5: 分数与判决 ----
box(7.6, 2.55, 1.9, 1.1, "异常分数\nmax(z_i) × ΔC", "#e0f7fa", fs=10.5, bold=True)
box(10.0, 2.55, 1.85, 1.1, "自适应阈值\nq = 75 分位\n→ 正常 / 缺陷", "#fff9c4", fs=10, bold=True)

# ---- 箭头 ----
arrow(1.95, 4.1, 2.4, 3.3)          # 信号 → 残差场
arrow(1.95, 2.2, 2.4, 2.9)          # 模板 → 残差场
arrow(4.1, 3.1, 4.5, 4.0)           # 残差场 → 六爻阵列
arrow(4.1, 3.1, 4.5, 2.1)           # 残差场 → 爻变判据
arrow(7.1, 3.9, 7.6, 3.3)           # 六爻阵列 → 分数
arrow(7.1, 1.9, 7.6, 2.7)           # 爻变判据 → 分数
arrow(9.5, 3.1, 10.0, 3.1)          # 分数 → 阈值

# 在线更新回环
ax.add_patch(FancyArrowPatch((10.9, 2.5), (1.05, 1.55), arrowstyle="-|>",
             mutation_scale=15, lw=1.5, color="#d32f2f", linestyle="--",
             connectionstyle="arc3,rad=-0.25"))
ax.text(5.8, 0.72, "在线更新 (自首样本起增量学习，天然遗忘)", color="#d32f2f",
        fontsize=9.5, ha="center", style="italic")

ax.text(6.0, 5.02, "六爻传感器阵列框架总览", ha="center", fontsize=14, fontweight="bold")

plt.tight_layout()
p = os.path.join(OUT, "fig1_framework.png")
plt.savefig(p, dpi=200, bbox_inches="tight")
print("saved:", p)
