#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.7 架构重构V2：从8卦基底到64卦全空间 + 六大模块"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 2, figsize=(14, 5.6),
                         gridspec_kw={'width_ratios': [1, 1.25]})

# 左：8顶点 vs 64全空间
ax = axes[0]
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')
ax.set_title('(a) 8卦基底 → 64卦全空间', fontsize=12, fontweight='bold')

ax.add_patch(FancyBboxPatch((0.5, 6.2), 9.0, 2.6,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#bbb', alpha=0.18, ec='#888', lw=1.6))
ax.text(5, 8.35, '旧：名义64维，实用8顶点', ha='center', fontsize=10.5,
        fontweight='bold', color='#555')
# 8个点 + 均匀尾巴示意
for i, x in enumerate(np.linspace(1.2, 3.0, 8)):
    ax.plot(x, 7.2, 'o', color='#888', ms=7)
ax.text(2.1, 6.65, '8经卦顶点', ha='center', fontsize=8.3, color='#666')
ax.plot([3.6, 8.9], [7.2, 7.2], ':', color='#aaa', lw=2)
ax.text(6.25, 6.65, '56维无名均匀尾巴（未用）', ha='center', fontsize=8.3, color='#999')

ax.add_patch(FancyBboxPatch((0.5, 2.4), 9.0, 2.9,
             boxstyle="round,pad=0.1,rounding_size=0.12",
             fc='#1f6f8b', alpha=0.13, ec='#1f6f8b', lw=1.8))
ax.text(5, 4.9, 'V2：真正64维全空间（6-qubit）', ha='center', fontsize=10.5,
        fontweight='bold', color='#17496b')
# 随机密布的点表示64
rng = np.random.default_rng(3)
xs = 1.1 + rng.random(64) * 7.8
ys = 3.0 + rng.random(64) * 1.4
ax.scatter(xs, ys, s=16, color='#1f6f8b', alpha=0.6)
ax.text(5, 2.7, '64卦=64个自足语义基矢；量子叠加=多义', ha='center',
        fontsize=8.6, color='#333')

ax.annotate('', xy=(5, 5.6), xytext=(5, 6.15),
            arrowprops=dict(arrowstyle='->', lw=2.2, color='#c0392b'))
ax.text(5, 5.9, '架构重构', ha='center', fontsize=8.5, color='#c0392b')

# 右：六大模块
ax = axes[1]
ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis('off')
ax.set_title('(b) 架构重构V2的六大模块', fontsize=12, fontweight='bold')
mods = [
    ('① 8卦→64卦', '分辨率提升', '#1f6f8b'),
    ('② 字典先验内化', '8624字先天种子', '#2e8b57'),
    ('③ 量子主管线', 'engine64q（6-qubit叠加）', '#b7791f'),
    ('④ 多义择义', '局部窗口+义项保护', '#c0392b'),
    ('⑤ 防弥散/先验衰减', '提纯锚base', '#6a4c93'),
    ('⑥ 坐标系统一', '引擎二进制index', '#0e7c86'),
]
for k, (t, s, c) in enumerate(mods):
    row, col = divmod(k, 2)
    x = 0.4 + col * 5.9
    y = 7.4 - row * 2.35
    ax.add_patch(FancyBboxPatch((x, y), 5.3, 1.85,
                 boxstyle="round,pad=0.1,rounding_size=0.12",
                 fc=c, alpha=0.13, ec=c, lw=1.7))
    ax.text(x+0.35, y+1.2, t, ha='left', fontsize=10.3, fontweight='bold', color=c)
    ax.text(x+0.35, y+0.5, s, ha='left', fontsize=8.6, color='#333')

fig.suptitle('图10.7  架构重构V2：从8卦基底到64卦全空间', fontsize=13.5,
             fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.94])
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_7_v2.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_7')
