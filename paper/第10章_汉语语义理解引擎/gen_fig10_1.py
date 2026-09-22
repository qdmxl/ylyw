#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.1 易卦生成逻辑与汉字生成逻辑的同构对应"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(12.5, 7.4))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')

ax.text(5, 9.65, '图10.1  易卦生成逻辑与汉字生成逻辑的同构对应',
        ha='center', fontsize=14.5, fontweight='bold')

# 三列标题
ax.text(1.9, 9.02, '易卦生成链', ha='center', fontsize=12, color='#1f5f8b', fontweight='bold')
ax.text(5.0, 9.02, '共享认知操作', ha='center', fontsize=12, color='#7a3b0e', fontweight='bold')
ax.text(8.1, 9.02, '汉字生成链', ha='center', fontsize=12, color='#2e7d32', fontweight='bold')
ax.plot([0.35, 9.65], [8.82, 8.82], color='#aaa', lw=1)

rows = [
    ('阴阳爻（阴/阳）', '观物取象', '笔画（横竖撇捺）'),
    ('八　卦（八经卦）', '立象尽意', '部　件（氵木人口…）'),
    ('六十四卦（重卦）', '相重组合', '整　字（会意/形声）'),
    ('卦变·引申·万事之理', '类比延伸', '引申·转注·假借之义'),
]

y0 = 7.9; dy = 1.72
for k, (q, mid, y) in enumerate(rows):
    yc = y0 - k*dy
    # 左：易卦
    b1 = FancyBboxPatch((0.35, yc-0.46), 3.1, 0.92,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc='#1f5f8b', alpha=0.14, ec='#1f5f8b', lw=1.6)
    ax.add_patch(b1)
    ax.text(1.9, yc, q, ha='center', va='center', fontsize=10.6,
            fontweight='bold', color='#17496b')
    # 中：认知操作
    b2 = FancyBboxPatch((3.75, yc-0.46), 2.5, 0.92,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc='#7a3b0e', alpha=0.13, ec='#7a3b0e', lw=1.6)
    ax.add_patch(b2)
    ax.text(5.0, yc, mid, ha='center', va='center', fontsize=11,
            fontweight='bold', color='#5e2c08')
    # 右：汉字
    b3 = FancyBboxPatch((6.55, yc-0.46), 3.1, 0.92,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc='#2e7d32', alpha=0.14, ec='#2e7d32', lw=1.6)
    ax.add_patch(b3)
    ax.text(8.1, yc, y, ha='center', va='center', fontsize=10.6,
            fontweight='bold', color='#1f5c25')
    # 箭头：左→中→右
    ax.add_patch(FancyArrowPatch((3.5, yc), (3.72, yc), arrowstyle='-|>',
                 mutation_scale=13, color='#888', lw=1.2))
    ax.add_patch(FancyArrowPatch((6.3, yc), (6.52, yc), arrowstyle='-|>',
                 mutation_scale=13, color='#888', lw=1.2))

ax.text(5, 0.55, '同一种认知操作，在两种符号系统中的两次实现：观物取象，立象尽意',
        ha='center', fontsize=10.5, style='italic', color='#555')

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_1_isomorphism.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_1')
