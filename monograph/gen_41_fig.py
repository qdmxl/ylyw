#!/usr/bin/env python3
"""第4章配图：参数空间图 + 学习收敛曲线"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fp_bold = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
zh = FontProperties(fname=fp, size=10)
zh_sm = FontProperties(fname=fp, size=8.5)
zh_title = FontProperties(fname=fp_bold, size=14)
zh_note = FontProperties(fname=fp, size=7)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

# ======== 左图：443参数空间分布 ========
ax1.set_xlim(0, 10)
ax1.set_ylim(0, 10)
ax1.axis('off')
ax1.set_title('YLYW 参数空间构成（443个可调参数）', fontproperties=zh_title, pad=18, color='#1a237e')

layers = [
    ('L1 八卦原型\n8卦 × 6维 = 48', 48, '#1565C0'),
    ('L2 六爻阈值\n6个维度 = 6', 6, '#2E7D32'),
    ('L3 六十四卦模板\n64卦 × 6维 = 384', 384, '#E65100'),
    ('L3+ 爻位权重\n5个权重 = 5', 5, '#6A1B9A'),
]
total = sum(v for _, v, _ in layers)

for idx, (label, val, color) in enumerate(layers):
    y = 8 - idx * 2
    x_start = 1.5
    bar_w = val / total * 6.5
    rect = plt.Rectangle((x_start, y-0.55), bar_w, 1.1, facecolor=color, alpha=0.75,
                          edgecolor=color, linewidth=2, zorder=2)
    ax1.add_patch(rect)
    ax1.text(x_start + bar_w + 0.15, y, f'{label}\n({val}, {val/total*100:.1f}%)',
             ha='left', va='center', fontproperties=FontProperties(fname=fp, size=9), color=color, zorder=3)

# 对标
ax1.text(5, 1.5, f'总计: {total} 个参数', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#1a237e')
ax1.text(5, 0.7, '对比: DRL 典型 ~10⁶-10⁷ 参数, YLYW 仅 ~443 (约 10⁴ 倍效率)',
         ha='center', va='center', fontproperties=zh_note, color='#78909C')

# ======== 右图：学习收敛曲线 + 对比 ========
ax2.set_xlim(-0.5, 12)
ax2.set_ylim(0, 105)
ax2.set_title('自适应学习收敛性能', fontproperties=zh_title, pad=18, color='#1a237e')
ax2.set_xlabel('交互轮数 / 失败次数', fontproperties=zh)
ax2.set_ylabel('成功率 / 收敛指标 (%)', fontproperties=zh)

# YLYW 抓取自适应
rounds = [0, 1, 2, 3, 5, 7, 9]
succ = [58, 62, 60, 66, 64, 64, 64]
ax2.plot(rounds, succ, 'o-', color='#1565C0', lw=2.5, markersize=8, label='YLYW物理抓取自适应 (50物体)')
ax2.axhline(y=66, xmin=0, xmax=0.75, color='#1565C0', lw=1, linestyle='--', alpha=0.5)
ax2.text(3.5, 66, '收敛至66%', fontproperties=zh_note, color='#1565C0')

# 冰面步态
steps = [0, 1, 2, 3, 10, 15]
speed = [2.0, 0.9, 0.6, 0.6, 0.6, 0.6]
ax2.plot(steps, [s*30 for s in speed], 's-', color='#2E7D32', lw=2.5, markersize=8, label='YLYW冰面步态收敛 (m/s×30)')

# DRL 对比线
drl_r = list(range(12))
drl_v = [0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.5, 3, 6, 12, 25, 50]
ax2.plot(drl_r, drl_v, 'x--', color='#C62828', lw=1.5, markersize=5, alpha=0.6, label='典型DRL收敛曲线 (示意)')

ax2.legend(loc='lower right', prop=FontProperties(fname=fp, size=9))
ax2.grid(axis='y', alpha=0.3)
ax2.set_xticks(list(range(12)))
ax2.text(5, 85, 'YLYW: 3轮 / 3步内收敛\nDRL: 数万步交互\n效率提升 ~10³-10⁴ 倍',
         fontproperties=FontProperties(fname=fp, size=9), color='#1a237e',
         bbox=dict(boxstyle='round', facecolor='#E3F2FD', edgecolor='#1565C0', alpha=0.8))

plt.tight_layout()
path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig4_1_learning.png'
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
