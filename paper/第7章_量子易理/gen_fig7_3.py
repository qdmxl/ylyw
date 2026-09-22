#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第7章 图7.3 两卦相重=张量积（8⊗8→64）结构示意"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.font_manager as fm
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(12.5, 7))
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')

# 左：上卦 8维空间
ax.text(1.5, 9.0, '上卦（外卦）', ha='center', fontsize=12, fontweight='bold', color='#1f6f8b')
ax.text(1.5, 8.55, '$\\mathcal{H}_3=\\mathbb{C}^8$', ha='center', fontsize=10, color='#1f6f8b')
# 八卦爻符（自下而下：初→三）
YAO = {
 '乾': [1,1,1], '坤': [0,0,0], '震': [1,0,0], '巽': [0,1,1],
 '坎': [0,1,0], '离': [1,0,1], '艮': [0,0,1], '兑': [1,1,0],
}
name_order = ['乾','坤','震','巽','坎','离','艮','兑']

def draw_trigram(cx, cy, yao, color, s=0.16):
    # yao[0]=初爻(最下), yao[2]=三爻(最上)
    for k in range(3):
        yy = cy - s + k*s*0.85
        v = yao[k]
        if v == 1:
            ax.plot([cx-0.22, cx+0.22], [yy, yy], color=color, lw=2.2, solid_capstyle='butt')
        else:
            ax.plot([cx-0.22, cx-0.04], [yy, yy], color=color, lw=2.2, solid_capstyle='butt')
            ax.plot([cx+0.04, cx+0.22], [yy, yy], color=color, lw=2.2, solid_capstyle='butt')

for i, g in enumerate(name_order):
    y = 7.6 - i*0.85
    ax.add_patch(FancyBboxPatch((0.8, y-0.32), 1.4, 0.62,
                 boxstyle="round,pad=0.03,rounding_size=0.08",
                 fc='#1f6f8b', alpha=0.13, ec='#1f6f8b', lw=1.1))
    draw_trigram(1.15, y, YAO[g], '#14506b')
    ax.text(1.72, y, g, ha='center', va='center', fontsize=10, color='#14506b')

# 中：张量积符号
ax.text(3.5, 5.0, 'X', ha='center', va='center', fontsize=30, color='#8B4513')
ax.add_patch(plt.Circle((3.5, 5.0), 0.42, fill=False, ec='#8B4513', lw=2.4))
ax.annotate('两卦相重\n（张量积）', xy=(3.5, 6.2), fontsize=11, ha='center',
            color='#8B4513', fontweight='bold')

# 右：下卦 8维空间
ax.text(5.5, 9.0, '下卦（内卦）', ha='center', fontsize=12, fontweight='bold', color='#2e8b57')
ax.text(5.5, 8.55, '$\\mathcal{H}_3=\\mathbb{C}^8$', ha='center', fontsize=10, color='#2e8b57')
for i, g in enumerate(name_order):
    y = 7.6 - i*0.85
    ax.add_patch(FancyBboxPatch((4.8, y-0.32), 1.4, 0.62,
                 boxstyle="round,pad=0.03,rounding_size=0.08",
                 fc='#2e8b57', alpha=0.13, ec='#2e8b57', lw=1.1))
    draw_trigram(5.15, y, YAO[g], '#1c5e39')
    ax.text(5.72, y, g, ha='center', va='center', fontsize=10, color='#1c5e39')

# 箭头到结果空间
ax.annotate('', xy=(7.6, 5.0), xytext=(6.4, 5.0),
            arrowprops=dict(arrowstyle='->', lw=2.5, color='#c0392b'))

# 结果：64维空间
ax.add_patch(FancyBboxPatch((7.7, 1.2), 2.0, 7.4,
             boxstyle="round,pad=0.08,rounding_size=0.15",
             fc='#c0392b', alpha=0.10, ec='#c0392b', lw=1.8))
ax.text(8.7, 8.35, '六十四卦', ha='center', fontsize=12, fontweight='bold', color='#c0392b')
ax.text(8.7, 7.95, '$\\mathcal{H}_6=\\mathbb{C}^{64}$', ha='center', fontsize=10, color='#c0392b')
ax.text(8.7, 7.5, '维数 8×8=64', ha='center', fontsize=9.5, color='#c0392b')
# 网格示意
for r in range(4):
    for c in range(4):
        ax.add_patch(Rectangle((7.9+c*0.42, 5.6-r*0.42), 0.34, 0.34,
                     fc='#c0392b', alpha=0.15, ec='#c0392b', lw=0.5))
ax.text(8.7, 2.4, '任一纯态可唯一\n分解为 |u>|l>\n（可逆、可分离）',
        ha='center', fontsize=8.5, color='#7a1f1f', linespacing=1.5)
ax.text(8.7, 1.7, 'Concurrence C = 0', ha='center', fontsize=9.5,
        color='#c0392b', fontweight='bold')

ax.text(5, 9.8, '图7.3  "两卦相重" = 张量积：从两个8维空间到64维空间的映射',
        ha='center', fontsize=13.5, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第7章_量子易理/fig7_3_tensor.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig7_3')
