#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第7章 图7.9 全栈量子化数据流图"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(12.5, 4.6))
ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis('off')

stages = [
    ('物体特征', '13维物理特征\n(硬度/重量/纹理...)', '#5b4b8a'),
    ('L0 量子态编码', 'FeatureEncoder\nC^64 归一化态矢量', '#1f6f8b'),
    ('L3 酉变换', 'YiliOracle\nU = e^{-iHτ}', '#b7791f'),
    ('L4 涌现', 'Grover / 干涉\nP(k)=|<k|Ψ>|²', '#c0392b'),
    ('决策输出', '64维概率分布\n→ 策略参数', '#2e8b57'),
]
x0, dx = 1.3, 2.35
for k, (title, note, color) in enumerate(stages):
    x = x0 + k*dx
    ax.add_patch(FancyBboxPatch((x-0.95, 3.6), 1.9, 2.7,
                 boxstyle="round,pad=0.1,rounding_size=0.15",
                 fc=color, alpha=0.13, ec=color, lw=1.8))
    ax.text(x, 5.6, title, ha='center', va='center', fontsize=10.5,
            fontweight='bold', color=color)
    ax.text(x, 4.5, note, ha='center', va='center', fontsize=8.3,
            color='#333', linespacing=1.5)
    if k < len(stages)-1:
        ax.annotate('', xy=(x+dx-1.05, 4.95), xytext=(x+0.95, 4.95),
                    arrowprops=dict(arrowstyle='->', lw=2.2, color='#666'))

ax.text(6, 8.3, '图7.9  全栈量子化数据流：从物理特征到决策涌现',
        ha='center', fontsize=13.5, fontweight='bold')
ax.text(6, 7.4, '经典四层串行计算 → 量子一次并行变换',
        ha='center', fontsize=10, color='#666', style='italic')
# 量子并行性标注
ax.annotate('', xy=(2.95, 2.9), xytext=(2.95, 3.55),
            arrowprops=dict(arrowstyle='-', lw=1, color='#999'))
ax.text(6, 2.3, '量子并行性：一次变换同时作用于全部 64 个基态',
        ha='center', fontsize=9.5, color='#c0392b',
        bbox=dict(boxstyle='round,pad=0.4', fc='#c0392b', alpha=0.08, ec='#c0392b'))

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第7章_量子易理/fig7_9_dataflow.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig7_9')
