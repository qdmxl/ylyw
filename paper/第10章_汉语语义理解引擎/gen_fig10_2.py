#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.2 YLYW四层嵌套语言处理架构数据流"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(13, 6.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis('off')

ax.text(6, 9.55, '图10.2  YLYW四层嵌套语言处理架构数据流',
        ha='center', fontsize=14, fontweight='bold')
ax.text(6, 8.95, '输入经文 → 字形层 → 字义层 → 词句层 → 篇章层 → 带推理链的语义解析',
        ha='center', fontsize=9.8, color='#666', style='italic')

layers = [
    ('L1 字形层', '爻', '偏旁部首\n→ 模糊隶属度', '#1f6f8b'),
    ('L2 字义层', '卦', '乘承比应\n会意字知识库', '#2e8b57'),
    ('L3 词句层', '别卦', '虚词驱动分词\n三通道判定', '#b7791f'),
    ('L4 篇章层', '复卦', '多句起承转合\n变卦序列', '#c0392b'),
]
x0, dx = 1.8, 2.55
for k, (title, gua, note, color) in enumerate(layers):
    x = x0 + k*dx
    ax.add_patch(FancyBboxPatch((x-1.0, 3.9), 2.0, 2.9,
                 boxstyle="round,pad=0.1,rounding_size=0.15",
                 fc=color, alpha=0.13, ec=color, lw=1.8))
    ax.text(x, 6.4, title, ha='center', va='center', fontsize=11,
            fontweight='bold', color=color)
    ax.text(x, 5.75, '【' + gua + '】', ha='center', va='center',
            fontsize=9.5, color=color)
    ax.text(x, 4.8, note, ha='center', va='center', fontsize=8.6,
            color='#333', linespacing=1.5)
    if k < len(layers)-1:
        ax.annotate('', xy=(x+dx-1.08, 5.35), xytext=(x+1.0, 5.35),
                    arrowprops=dict(arrowstyle='->', lw=2.2, color='#666'))

# 输入/输出
ax.add_patch(FancyBboxPatch((0.15, 4.75), 0.75, 1.2,
             boxstyle="round,pad=0.06,rounding_size=0.1",
             fc='#444', alpha=0.12, ec='#444', lw=1.5))
ax.text(0.52, 5.35, '输入\n经文', ha='center', va='center', fontsize=8.5, color='#333')
ax.annotate('', xy=(0.78, 5.35), xytext=(0.92, 5.35),
            arrowprops=dict(arrowstyle='->', lw=2, color='#666'))
ax.add_patch(FancyBboxPatch((10.15, 4.75), 1.7, 1.2,
             boxstyle="round,pad=0.06,rounding_size=0.1",
             fc='#444', alpha=0.12, ec='#444', lw=1.5))
ax.text(11.0, 5.35, '语义解析\n+推理链', ha='center', va='center', fontsize=8.5, color='#333')
ax.annotate('', xy=(10.15, 5.35), xytext=(9.85, 5.35),
            arrowprops=dict(arrowstyle='->', lw=2, color='#666'))

# 认知同构标注
ax.annotate('', xy=(1.8, 3.85), xytext=(9.45, 3.85),
            arrowprops=dict(arrowstyle='<->', lw=1.3, color='#888', ls='--'))
ax.text(6, 3.35, '认知同构：爻→八卦→六十四卦的生成链，逐层映射为字→词→句→篇的嵌套链',
        ha='center', fontsize=9.2, color='#555',
        bbox=dict(boxstyle='round,pad=0.35', fc='#888', alpha=0.08, ec='#aaa'))

# 底座：知几校准 + 自适应成长
ax.add_patch(FancyBboxPatch((1.2, 1.4), 9.6, 1.15,
             boxstyle="round,pad=0.1,rounding_size=0.15",
             fc='#6a4c93', alpha=0.13, ec='#6a4c93', lw=1.8))
ax.text(6, 1.97, '知几跨句校准  +  自适应成长底座（先天字形 + 后天语料，越读越懂）',
        ha='center', va='center', fontsize=10, fontweight='bold', color='#4c3575')
for x in (1.8, 4.35, 6.9, 9.45):
    ax.annotate('', xy=(x, 3.9), xytext=(x, 2.55),
                arrowprops=dict(arrowstyle='->', lw=1.3, color='#6a4c93', ls=':'))

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_2_arch.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_2')
