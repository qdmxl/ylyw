#!/usr/bin/env python3
"""生成3.4节配图：五种爻位关系示意图 + 爻位质量分布"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
from matplotlib.font_manager import FontProperties
import numpy as np

fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fp_bold = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
zh = FontProperties(fname=fp, size=10)
zh_sm = FontProperties(fname=fp, size=8.5)
zh_title = FontProperties(fname=fp_bold, size=14)
zh_box = FontProperties(fname=fp_bold, size=9)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8.5))

# ======== 左图：五条爻位关系示意图 ========
ax1.set_xlim(0, 12)
ax1.set_ylim(0, 12)
ax1.axis('off')
ax1.set_title('五种爻位关系运算示意', fontproperties=zh_title, pad=18, color='#1a237e')

relations = [
    ('当位 (0.40)', '阳爻居阳位(1/3/5)\n阴爻居阴位(2/4/6)\n→ 内在稳定性', '#1565C0',
     [('初(阳位)', 1), ('二(阴位)', 2), ('三(阳位)', 3), ('四(阴位)', 4), ('五(阳位)', 5), ('上(阴位)', 6)]),
    ('得中 (0.20)', '二爻宜阴(六二)\n五爻宜阳(九五)\n→ 中正平衡', '#2E7D32',
     [('二爻·中', 2), ('五爻·中', 5)]),
    ('乘承 (0.15)', '阴在阳上=乘(逆)\n阴在阳下=承(顺)\n→ 助力与阻力', '#E65100',
     [('乘', 1.7), ('承', 1.3)]),
    ('亲比 (0.10)', '相邻两爻同性\n→ 动作连贯性', '#6A1B9A',
     [('初-二', 0.5), ('二-三', 0.5), ('三-四', 0.5), ('四-五', 0.5), ('五-上', 0.5)]),
    ('呼应 (0.15)', '初↔四  二↔五  三↔上\n阴阳相反=呼应\n→ 上下协调', '#BF360C',
     [('初↔四', 1), ('二↔五', 2), ('三↔上', 3)]),
]

for idx, (title, desc, color, details) in enumerate(relations):
    x_base = 0.3 + idx * 2.35
    y_top = 10.5

    # 标题框
    rect = FancyBboxPatch((x_base, y_top-0.8), 2.1, 0.7, boxstyle="round,pad=0.1",
                          facecolor=color, alpha=0.15, edgecolor=color, linewidth=1.5, zorder=2)
    ax1.add_patch(rect)
    ax1.text(x_base+1.05, y_top-0.45, title, ha='center', va='center',
             fontproperties=zh_box, color=color, zorder=3)

    # 描述文字
    ax1.text(x_base+1.05, y_top-1.5, desc, ha='center', va='top',
             fontproperties=FontProperties(fname=fp, size=7.5), color='#37474F', zorder=3)

    # 六爻可视化列
    for j in range(6):
        y = 9.0 - j * 0.9
        yao_val = 0
        if idx == 0:  # 当位：交替
            yao_val = 1 if j % 2 == 0 else 0
        elif idx == 1:  # 得中：二五为阳
            yao_val = 1 if j in [1, 4] else 0
        elif idx == 2:  # 乘承
            yao_val = 1 if j % 2 == 0 else 0
        elif idx == 3:  # 亲比：全阳
            yao_val = 1
        elif idx == 4:  # 呼应：交替
            yao_val = 1 if j % 2 == 0 else 0

        # 爻线
        lw = 4
        if yao_val >= 0.5:
            ax1.plot([x_base+0.4, x_base+1.7], [y, y], '-', color='#1a237e', lw=lw, zorder=2, solid_capstyle='round')
        else:
            ax1.plot([x_base+0.4, x_base+1.05], [y, y], '-', color='#c62828', lw=lw, zorder=2, solid_capstyle='round')
            ax1.plot([x_base+1.05, x_base+1.7], [y, y], '-', color='#c62828', lw=lw, zorder=2, solid_capstyle='round')

        # 爻位序号
        ax1.text(x_base+0.1, y, str(j+1), ha='center', va='center',
                 fontproperties=FontProperties(fname=fp, size=7), color='#78909C', zorder=3)

    # 关系连线（呼应）
    if idx == 4:
        for pair_y1, pair_y2 in [(9.0, 6.3), (8.1, 5.4), (7.2, 4.5)]:
            ax1.annotate('', xy=(x_base+2.0, pair_y2), xytext=(x_base+2.0, pair_y1),
                        arrowprops=dict(arrowstyle='<->', color='#BF360C', lw=1.5))
    # 关系连线（乘承）
    if idx == 2:
        for j in range(5):
            y1 = 9.0 - j * 0.9
            y2 = 9.0 - (j+1) * 0.9
            mid = (y1 + y2) / 2
            ax1.annotate('', xy=(x_base+2.0, y2), xytext=(x_base+2.0, y1),
                        arrowprops=dict(arrowstyle='->', color='#E65100', lw=1.0, linestyle='dashed'))
            ax1.text(x_base+2.2, mid, '乘' if j % 2 == 0 else '承', ha='left', va='center',
                     fontproperties=FontProperties(fname=fp, size=6), color='#E65100')

# ======== 右图：爻位质量→修正系数映射 + 分布 ========
ax2.set_xlim(-0.5, 1.5)
ax2.set_ylim(0, 12)
ax2.axis('off')
ax2.set_title('爻位质量→力修正映射', fontproperties=zh_title, pad=18, color='#1a237e')

# 四个谨慎级别区域
levels = [
    (0, 0.30, '< 0.30\nvery_cautious\n修正: 0.75-0.85', '#C62828'),
    (0.30, 0.50, '[0.30, 0.50)\ncautious\n修正: 0.85-0.95', '#F57C00'),
    (0.50, 0.70, '[0.50, 0.70)\nnormal\n修正: 0.95-1.00', '#1565C0'),
    (0.70, 1.0, '≥ 0.70\nrelaxed\n修正: 1.00-1.05', '#2E7D32'),
]
for low, high, label, color in levels:
    y_low = 1.5 + low * 8.5
    y_high = 1.5 + high * 8.5
    rect = FancyBboxPatch((0.0, y_low), 1.0, y_high - y_low,
                          boxstyle="round,pad=0.05", facecolor=color, alpha=0.12,
                          edgecolor=color, linewidth=1.5, zorder=2)
    ax2.add_patch(rect)
    mid = (y_low + y_high) / 2
    ax2.text(0.5, mid, label, ha='center', va='center',
             fontproperties=FontProperties(fname=fp, size=8), color=color, zorder=3)

    # 修正系数标注
    ax2.text(1.15, mid, f'{low:.2f}→{high:.2f}', ha='center', va='center',
             fontproperties=FontProperties(fname=fp, size=7), color='#546E7A')

# 轴标注
ax2.text(-0.25, 10, '爻位\n质量\nS_yao', ha='center', va='center',
         fontproperties=FontProperties(fname=fp_bold, size=9), color='#37474F')
ax2.text(-0.25, 1.2, '1.0', ha='center', va='center', fontproperties=zh_sm, color='#78909C')
ax2.text(-0.25, 1.5, '0.0', ha='center', va='center', fontproperties=zh_sm, color='#78909C')

# 全局统计
stats_text = ('全局统计 (300物体基线):\n'
              '  力修正均值: 0.94\n'
              '  爻位质量均值: 0.50\n'
              '  cautious占比: 52%\n'
              '  relaxed占比: 1%')
ax2.text(0.5, 11.0, stats_text, ha='center', va='top',
         fontproperties=FontProperties(fname=fp, size=8), color='#37474F',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#ECEFF1', edgecolor='#B0BEC5', alpha=0.8))

# 典型案例
cases = [
    (0.85, '石块: 0/6当位 + 2乘 → 0.85'),
    (0.95, '立方体: 4/6当位 → 0.95'),
    (0.90, '花瓶: 2/6当位 + 易碎 → 0.90'),
]
for mod, label in cases:
    y = 1.5 + mod * 8.5
    ax2.axhline(y=y, xmin=0.55, xmax=1.0, color='#1a237e', lw=1.5, linestyle='--', zorder=4)
    ax2.plot([0.5, 1.0], [y, y], 'o', color='#1a237e', markersize=5, zorder=4)
    ax2.text(1.15, y, label, ha='left', va='center', fontproperties=FontProperties(fname=fp, size=7),
             color='#1a237e')

plt.tight_layout()
path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig3_3_yao_relations.png'
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
