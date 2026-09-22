#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.5 消融式理解测试示意与结果"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0),
                         gridspec_kw={'width_ratios': [1.15, 1]})

# 左：测试逻辑示意
ax = axes[0]
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
ax.set_title('(a) 消融式理解测试逻辑', fontsize=12, fontweight='bold')
ax.add_patch(FancyBboxPatch((0.3, 7.3), 9.4, 1.6,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#1f6f8b', alpha=0.12, ec='#1f6f8b', lw=1.6))
ax.text(5, 8.45, '原句（含目标类词）', ha='center', fontsize=10.5,
        fontweight='bold', color='#17496b')
ax.text(5, 7.75, '⇩ 句胞语义对目标类原型的偏移量 Δ', ha='center',
        fontsize=9, color='#555')
ax.add_patch(FancyBboxPatch((0.3, 5.3), 9.4, 1.6,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#c0392b', alpha=0.12, ec='#c0392b', lw=1.6))
ax.text(5, 6.45, '消融句（挖掉目标类词）', ha='center', fontsize=10.5,
        fontweight='bold', color='#8c2a1e')
ax.text(5, 5.72, '⇩ 与中性基线对照', ha='center', fontsize=9, color='#555')
ax.add_patch(FancyBboxPatch((0.3, 3.0), 9.4, 1.7,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#2e8b57', alpha=0.12, ec='#2e8b57', lw=1.6))
ax.text(5, 4.2, '若 Δ 显著为正 → 真理解', ha='center', fontsize=10.5,
        fontweight='bold', color='#1f5c25')
ax.text(5, 3.45, '（中性基线是固定偏差，解释不了结构性变化）', ha='center',
        fontsize=8.6, color='#555')
ax.text(5, 2.0, '结论：移除特定词 → 该类语义方向明确变化\n= 句胞层"以句为主"的语义理解',
        ha='center', fontsize=9.3, color='#333',
        bbox=dict(boxstyle='round,pad=0.4', fc='#888', alpha=0.08, ec='#aaa'))

# 右：结果条形图
ax = axes[1]
labels = ['水类', '火类', '木类']
vals = [0.566, 0.647, 0.228]
bars = ax.bar(labels, vals, color=['#1f6f8b', '#c0392b', '#2e8b57'],
              alpha=0.8, width=0.5)
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.015, f'+{v}', ha='center',
            fontsize=11, fontweight='bold')
ax.axhline(0, color='#888', lw=1)
ax.set_ylabel('句胞语义偏移量 Δ', fontsize=11)
ax.set_ylim(0, 0.78)
ax.set_title('(b) 三类偏移量（均显著为正）', fontsize=12, fontweight='bold')
ax.grid(alpha=0.3, axis='y')
ax.text(1.0, 0.70, '全部显著为正，排除中性基线污染', ha='center',
        fontsize=9, color='#c0392b', style='italic')

fig.suptitle('图10.5  消融式理解测试：真理解 vs 聚类记忆的判别', fontsize=13.5,
             fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_5_ablation.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_5')
