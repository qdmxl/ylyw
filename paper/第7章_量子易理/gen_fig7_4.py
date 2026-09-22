#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第7章 图7.4 八卦相荡=酉变换干涉动力学示意"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))

# 左图：三阶段动力学（初始态 → 酉变换 → 干涉后）
ax = axes[0]
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
stages = [
    (1.4, '初始叠加态\n|psi0> = Σ alpha_i |i>', '所有卦象\n等幅叠加', '#1f6f8b'),
    (4.6, '酉变换\nU_摩 = e^{-iHτ}', '相位按H\n谱结构旋转', '#b7791f'),
    (8.0, '干涉后态\n|psi'> = U|psi0>', '好卦相长增强\n坏卦相消衰减', '#c0392b'),
]
for x, title, note, color in stages:
    ax.add_patch(FancyBboxPatch((x-1.25, 4.2), 2.5, 2.3,
                 boxstyle="round,pad=0.1,rounding_size=0.15",
                 fc=color, alpha=0.12, ec=color, lw=1.8))
    ax.text(x, 6.1, title, ha='center', va='center', fontsize=10.5,
            fontweight='bold', color=color, linespacing=1.5)
    ax.text(x, 4.9, note, ha='center', va='center', fontsize=8.5, color='#333', linespacing=1.4)
for x0 in (2.85, 6.05):
    ax.annotate('', xy=(x0+0.5, 5.35), xytext=(x0-0.05, 5.35),
                arrowprops=dict(arrowstyle='->', lw=2.2, color='#666'))
# 底部柱状示意
bars0 = [0.5]*8
bars1 = [0.08,0.15,0.15,0.30,0.50,0.65,0.90,1.0]
xbase = np.linspace(0.6, 2.2, 8)
for k,b in enumerate(bars0):
    ax.add_patch(plt.Rectangle((xbase[k]-0.09, 2.6), 0.16, b*1.0, fc='#1f6f8b', alpha=0.5))
ax.text(1.4, 2.2, '概率均匀', ha='center', fontsize=8, color='#14506b')
xbase2 = np.linspace(7.1, 8.9, 8)
for k,b in enumerate(bars1):
    col = '#c0392b' if b>0.4 else '#999'
    ax.add_patch(plt.Rectangle((xbase2[k]-0.09, 2.6), 0.16, b*1.0, fc=col, alpha=0.7))
ax.text(8.0, 2.2, '好卦增强/坏卦抑制', ha='center', fontsize=8, color='#c0392b')
ax.text(5, 9.5, '(a) 干涉动力学三阶段', ha='center', fontsize=11.5, fontweight='bold')

# 右图：增益因子与易理评分的单调映射
ax = axes[1]
scores = np.array([-4,-3,-2,-1,0,1,2,3,4])
gains = np.array([0.08,0.20,0.34,0.55,0.80,1.10,1.50,2.10,3.55])
colors = ['#c0392b' if s<0 else '#2e8b57' for s in scores]
bars = ax.bar(scores, gains, color=colors, alpha=0.7, edgecolor='white')
ax.plot(scores, gains, 'o-', color='#333', lw=1.5, ms=5, zorder=5)
ax.axhline(1.0, color='#999', ls='--', lw=1)
ax.set_xlabel('易理评分 S(h)', fontsize=11)
ax.set_ylabel('增益因子', fontsize=11)
ax.set_title('(b) 增益因子与易理评分的单调映射', fontsize=11.5, fontweight='bold')
ax.grid(alpha=0.25, axis='y')
ax.text(0, 3.2, '好卦\n增强', ha='center', fontsize=9, color='#2e8b57', fontweight='bold')
ax.text(-2.8, 1.6, '坏卦\n抑制', ha='center', fontsize=9, color='#c0392b', fontweight='bold')

plt.suptitle('图7.4  "八卦相荡"=酉变换干涉：好卦相长增强、坏卦相消衰减',
             fontsize=13.5, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第7章_量子易理/fig7_4_interference.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig7_4')
