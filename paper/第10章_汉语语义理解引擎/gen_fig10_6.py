#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.6 跨域试金石：中医辨证与红楼梦理解"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 2, figsize=(14, 5.4),
                         gridspec_kw={'width_ratios': [1, 1]})

# 左：中医辨证双通道
ax = axes[0]
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
ax.set_title('(a) 中医辨证：双通道多维度', fontsize=12, fontweight='bold')
ax.add_patch(FancyBboxPatch((0.4, 7.5), 9.2, 1.4,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#444', alpha=0.1, ec='#444', lw=1.5))
ax.text(5, 8.2, '症状输入（古籍文言 / 现代辨证式）', ha='center',
        fontsize=9.8, color='#333')
# 病位通道
ax.add_patch(FancyBboxPatch((0.6, 4.9), 4.3, 2.1,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#2e7d32', alpha=0.13, ec='#2e7d32', lw=1.7))
ax.text(2.75, 6.5, '病位通道（可涌现）', ha='center', fontsize=10,
        fontweight='bold', color='#1f5c25')
ax.text(2.75, 5.6, '词级PMI + 含脏证候词\n→ 跨典籍零样本 10/10', ha='center',
        fontsize=8.6, color='#333', linespacing=1.4)
# 八纲通道
ax.add_patch(FancyBboxPatch((5.1, 4.9), 4.3, 2.1,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#b7791f', alpha=0.13, ec='#b7791f', lw=1.7))
ax.text(7.25, 6.5, '八纲/气血通道（采集）', ha='center', fontsize=10,
        fontweight='bold', color='#7a4f08')
ax.text(7.25, 5.6, '成说模板匹配\n（义项不可分布涌现）', ha='center',
        fontsize=8.6, color='#333', linespacing=1.4)
ax.annotate('', xy=(2.75, 7.45), xytext=(2.75, 7.05),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#2e7d32'))
ax.annotate('', xy=(7.25, 7.45), xytext=(7.25, 7.05),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#b7791f'))
ax.add_patch(FancyBboxPatch((1.4, 2.4), 7.2, 1.6,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#c0392b', alpha=0.13, ec='#c0392b', lw=1.7))
ax.text(5, 3.2, '可问答辨证：病位 + 八纲 + 气血 + 病名诊断', ha='center',
        fontsize=9.5, fontweight='bold', color='#8c2a1e')
ax.annotate('', xy=(5, 2.35), xytext=(5, 4.85),
            arrowprops=dict(arrowstyle='->', lw=1.8, color='#666'))
ax.text(5, 1.2, '可生长：喂新书→重训（9.4s）→能力自动增强', ha='center',
        fontsize=9, color='#555',
        bbox=dict(boxstyle='round,pad=0.35', fc='#888', alpha=0.08, ec='#aaa'))

# 右：版本演进柱状图
ax = axes[1]
versions = ['v1', 'v2', 'v4', 'v5', 'v6']
scores = [0, 55.6, 38.9, 100, 100]
colors = ['#bbb', '#999', '#999', '#2e8b57', '#1f6f8b']
bars = ax.bar(versions, scores, color=colors, alpha=0.85, width=0.6)
for b, v in zip(bars, scores):
    ax.text(b.get_x()+b.get_width()/2, v+2, f'{v:.0f}%' if v else '失败',
            ha='center', fontsize=9.5, fontweight='bold')
ax.set_ylabel('归脏准确率 (%)', fontsize=11)
ax.set_ylim(0, 115)
ax.set_xlabel('判别器版本', fontsize=11)
ax.set_title('(b) 症状→脏腑判别器演进', fontsize=12, fontweight='bold')
ax.grid(alpha=0.3, axis='y')
ax.text(3.0, 60, 'v5/v6 零样本\n跨典籍 10/10', ha='center', fontsize=9.5,
        color='#1f5c25', style='italic')

fig.suptitle('图10.6  跨域试金石：中医辨证与《红楼梦》语义泛化', fontsize=13.5,
             fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_6_crossdomain.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_6')
