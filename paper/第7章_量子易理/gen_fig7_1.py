#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成第7章插图：图7.1 量子-易理思想交汇时间轴"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.font_manager as fm

# 中文字体
for _f in ['Noto Sans CJK JP', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei']:
    try:
        fm.findfont(_f, fallback_to_default=False)
        plt.rcParams['font.sans-serif'] = [_f]
        break
    except Exception:
        continue
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(12, 6.2))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# 时间轴主线
ax.plot([0.8, 9.2], [5, 5], color='#7a5230', lw=3, zorder=1)

events = [
    (1.4, '约公元前11世纪', '《易经》成书', '阴阳→八卦→\n六十四卦符号体系', '#8B4513', 1),
    (3.0, '1937年', '玻尔访华', '太极徽章·互补原理\n"Contraria sunt complementa"', '#1f6f8b', -1),
    (4.6, '1975年', '卡普拉《物理学之道》', '量子力学\n与东方哲学比较', '#2e8b57', 1),
    (6.2, '2009-2012年', '量子认知理论', 'Aerts / Busemeyer\n量子概率决策模型', '#5b4b8a', -1),
    (7.7, '2017年', 'Petoukhov 张量积', 'Kronecker积\n64卦↔遗传密码', '#a0522d', 1),
    (9.0, '2026年', 'QYUF 全栈量子化', '本章工作：\n酉变换+张量积+具身验证', '#c0392b', -1),
]

for x, date, title, desc, color, side in events:
    y_main = 5
    y_box = 5 + side * 2.6
    # 连接线
    ax.plot([x, x], [y_main, y_box - side*0.1], color=color, lw=1.6, ls='--', zorder=2)
    # 圆点
    ax.scatter([x], [y_main], s=140, color=color, zorder=4, edgecolor='white', linewidth=1.5)
    # 日期
    ax.text(x, y_main + side*0.55, date, ha='center',
            va='bottom' if side > 0 else 'top', fontsize=9.5, color=color, fontweight='bold')
    # 内容框
    box = FancyBboxPatch((x-0.92, y_box-0.95 if side > 0 else y_box-0.05),
                        1.84, 1.0, boxstyle="round,pad=0.08,rounding_size=0.12",
                        fc=color, alpha=0.12, ec=color, lw=1.5, zorder=3)
    ax.add_patch(box)
    ax.text(x, y_box+0.42 if side > 0 else y_box+0.42, title,
            ha='center', va='center', fontsize=10, fontweight='bold', color=color, zorder=5)
    ax.text(x, y_box-0.28 if side > 0 else y_box-0.28, desc,
            ha='center', va='center', fontsize=8.2, color='#333333', zorder=5, linespacing=1.4)

ax.text(5, 9.4, '图7.1  量子力学与易理思想交汇的时间轴',
        ha='center', fontsize=14, fontweight='bold', color='#1a1a1a')

plt.tight_layout()
plt.savefig('/home/lijinhan/.openclaw/workspace-quantum/ylyw_ch7/fig7_1_timeline.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig7_1')
