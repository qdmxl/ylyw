#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.3 YLYW双通道融合语义系统架构"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(12.5, 6.6))
ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis('off')
ax.text(6, 9.6, '图10.3  YLYW双通道融合语义系统架构',
        ha='center', fontsize=14, fontweight='bold')

# 两条上游通道
ax.add_patch(FancyBboxPatch((0.6, 6.6), 4.6, 2.0,
             boxstyle="round,pad=0.1,rounding_size=0.15",
             fc='#1f6f8b', alpha=0.13, ec='#1f6f8b', lw=1.8))
ax.text(2.9, 8.15, '先天字形通道（观物取象）', ha='center', fontsize=11,
        fontweight='bold', color='#17496b')
ax.text(2.9, 7.35, '偏旁部首 → 八卦六爻（8维）\n提供粗糙的自然范畴先验', ha='center',
        fontsize=9, color='#333', linespacing=1.5)

ax.add_patch(FancyBboxPatch((6.8, 6.6), 4.6, 2.0,
             boxstyle="round,pad=0.1,rounding_size=0.15",
             fc='#2e7d32', alpha=0.13, ec='#2e7d32', lw=1.8))
ax.text(9.1, 8.15, '后天语料通道（观其伴知其义）', ha='center', fontsize=11,
        fontweight='bold', color='#1f5c25')
ax.text(9.1, 7.35, 'PMI 共现指纹 → 语义类质心\n提供精确的语义证据', ha='center',
        fontsize=9, color='#333', linespacing=1.5)

# 统一评分核心
ax.add_patch(FancyBboxPatch((3.3, 3.4), 5.4, 2.2,
             boxstyle="round,pad=0.12,rounding_size=0.18",
             fc='#b7791f', alpha=0.15, ec='#b7791f', lw=2.0))
ax.text(6.0, 5.15, '统一双通道评分', ha='center', fontsize=12,
        fontweight='bold', color='#7a4f08')
ax.text(6.0, 4.15, r'$\mathrm{score}(c)=\lambda\cdot G(\mathbf{y}_c)+(1-\lambda)\cdot\cos(\mathbf{t}_x,\mathbf{q}_c)+b_c$'
        .replace(r'\mathbf', r'\mathbf'), ha='center', fontsize=11, color='#333')

# 知几校准（粘合剂）
ax.add_patch(FancyBboxPatch((8.9, 3.6), 2.6, 1.8,
             boxstyle="round,pad=0.1,rounding_size=0.15",
             fc='#6a4c93', alpha=0.14, ec='#6a4c93', lw=1.8))
ax.text(10.2, 4.8, '知几校准 $b_c$', ha='center', fontsize=10,
        fontweight='bold', color='#4c3575')
ax.text(10.2, 4.05, '随经验修正\n两通道偏差', ha='center', fontsize=8.5,
        color='#333', linespacing=1.4)

# 箭头
ax.annotate('', xy=(5.0, 5.6), xytext=(2.9, 6.55),
            arrowprops=dict(arrowstyle='->', lw=2, color='#1f6f8b'))
ax.annotate('', xy=(7.0, 5.6), xytext=(9.1, 6.55),
            arrowprops=dict(arrowstyle='->', lw=2, color='#2e7d32'))
ax.annotate('', xy=(8.85, 4.5), xytext=(8.75, 4.5),
            arrowprops=dict(arrowstyle='->', lw=2, color='#6a4c93'))

# 输出
ax.annotate('', xy=(6.0, 2.0), xytext=(6.0, 3.35),
            arrowprops=dict(arrowstyle='->', lw=2.2, color='#666'))
ax.add_patch(FancyBboxPatch((3.3, 0.7), 5.4, 1.25,
             boxstyle="round,pad=0.1,rounding_size=0.15",
             fc='#444', alpha=0.12, ec='#444', lw=1.6))
ax.text(6.0, 1.32, '语义类判定  →  随阅读四维成长（覆盖面 / 复杂度 / 语义收敛 / 准确率）',
        ha='center', va='center', fontsize=9.6, color='#333')

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_3_dual_channel.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_3')
