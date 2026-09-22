#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第7章 图7.2 量子运算与易理规则的四层同构映射图"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.font_manager as fm
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(13, 7.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')

rows = [
    ('6量子比特 Hilbert 空间', '六十四卦完备状态空间',
     '维数等同（64维）', '经典：人为编码\n量子：物理等同', '#1f6f8b'),
    ('CNOT 门（受控非门）', '爻际关系"应"',
     '非定域关联', '初-四 / 二-五 / 三-上\n远距呼应', '#2e8b57'),
    ('酉变换  U=e^{-iHτ}', '"乘承比应当位得中"',
     '一次并行变换', '5条规则×64卦\n一个时钟周期完成', '#b7791f'),
    ('Grover 振幅放大', '决策的"涌现"',
     '"寂然不动，感而遂通"', '不逐个搜索\n让答案自然浮现', '#c0392b'),
]

y0 = 8.4; dy = 1.85
for k, (q, y, rel, note, color) in enumerate(rows):
    yc = y0 - k*dy
    # 左侧：量子运算
    b1 = FancyBboxPatch((0.3, yc-0.55), 2.7, 1.1,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc=color, alpha=0.16, ec=color, lw=1.6)
    ax.add_patch(b1)
    ax.text(1.65, yc+0.14, q, ha='center', va='center', fontsize=10.5,
            fontweight='bold', color=color)
    ax.text(1.65, yc-0.28, note.split('\n')[0] if '\n' in note else '', ha='center',
            va='center', fontsize=8, color='#444')
    # 中间：等价符号 & 关系
    ax.text(3.55, yc, '⇔', ha='center', va='center', fontsize=17, color='#666')
    # 右侧：易理规则
    b2 = FancyBboxPatch((4.2, yc-0.55), 3.0, 1.1,
                        boxstyle="round,pad=0.05,rounding_size=0.1",
                        fc='#8B4513', alpha=0.13, ec='#8B4513', lw=1.6)
    ax.add_patch(b2)
    ax.text(5.7, yc+0.14, y, ha='center', va='center', fontsize=10.5,
            fontweight='bold', color='#6b3410')
    ax.text(5.7, yc-0.28, note.replace('\n', ' / '), ha='center', va='center',
            fontsize=7.6, color='#444')
    # 最右：关系标签
    ax.text(7.7, yc, rel, ha='left', va='center', fontsize=9.5,
            color=color, fontweight='bold')

ax.text(5, 9.7, '图7.2  量子运算与易理规则的四层工程同构',
        ha='center', fontsize=14, fontweight='bold')
ax.text(1.65, 9.15, '量子运算', ha='center', fontsize=11, color='#333', fontweight='bold')
ax.text(5.7, 9.15, '易理规则', ha='center', fontsize=11, color='#333', fontweight='bold')
ax.text(7.7, 9.15, '同构性质', ha='left', fontsize=11, color='#333', fontweight='bold')
ax.plot([0.3, 9.7], [8.95, 8.95], color='#999', lw=1)

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第7章_量子易理/fig7_2_isomorphism.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig7_2')
