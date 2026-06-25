#!/usr/bin/env python3
"""生成 3.3 节配图：卦象→策略映射示意 + 策略类型分布"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import numpy as np

fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fp_bold = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
zh = FontProperties(fname=fp, size=10)
zh_sm = FontProperties(fname=fp, size=8)
zh_title = FontProperties(fname=fp_bold, size=14)

# ============ 图 3.2: 10个核心卦象→策略映射示例 ============
hex_names = [
    '乾为天\n(01)', '坤为地\n(02)', '山水蒙\n(04)', '天泽履\n(10)', '天地否\n(12)',
    '风山渐\n(53)', '震为雷\n(51)', '艮为山\n(52)', '水火既济\n(63)', '火水未济\n(64)'
]
strategies = [
    '强力抓取\npower_grasp', '精确轻抓\nprecision_grasp', '自适应抓取\nadaptive_grasp',
    '谨慎抓取\ncautious_grasp', '回避重试\navoid_or_retry',
    '渐进抓取\nprogressive_grasp', '动态抓取\ndynamic_grasp', '稳定抓取\nstable_grasp',
    '协调抓取\ncoordinated_grasp', '放弃重试\nabort_or_retry'
]
forces = [0.85, 0.25, 0.50, 0.35, 0.30, 0.45, 0.50, 0.40, 0.55, 0.40]
dictums = [
    '健行不息\n刚健中正', '柔顺包容\n顺势而为', '蒙昧待启\n循序渐进', '如履薄冰\n小心翼翼',
    '闭塞不通\n否极泰来', '渐进不躁\n如风徐入', '震动不安\n动态变化', '静止如山\n不动如山',
    '事已成也\n完美收束', '事未成也\n重新开始'
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))

# --- 左图：卦→策略 流程图 ---
ax1.set_xlim(0, 10)
ax1.set_ylim(0, 12)
ax1.axis('off')
ax1.set_title('六十四卦→抓取策略 工程转译示例', fontproperties=zh_title, pad=20, color='#1a237e')

for i, (hn, st, dt, f) in enumerate(zip(hex_names, strategies, dictums, forces)):
    y = 11 - i * 1.15
    # 卦名框
    rect1 = plt.Rectangle((0.2, y-0.35), 1.6, 0.7, facecolor='#E3F2FD', edgecolor='#455A64',
                           linewidth=1.2, zorder=2)
    ax1.add_patch(rect1)
    ax1.text(1.0, y, hn, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=8),
             color='#1a237e', zorder=3)
    # 箭头
    ax1.annotate('', xy=(2.4, y), xytext=(1.8, y), zorder=1,
                arrowprops=dict(arrowstyle='->', color='#546E7A', lw=1.5))
    # 策略框
    rect2 = plt.Rectangle((2.4, y-0.35), 2.0, 0.7, facecolor='#F3E5F5', edgecolor='#455A64',
                           linewidth=1.2, zorder=2)
    ax1.add_patch(rect2)
    ax1.text(3.4, y, st, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=8),
             color='#4A148C', zorder=3, fontweight='bold')
    # 箭头
    ax1.annotate('', xy=(5.0, y), xytext=(4.4, y), zorder=1,
                arrowprops=dict(arrowstyle='->', color='#546E7A', lw=1.5))
    # 卦辞框
    rect3 = plt.Rectangle((5.0, y-0.35), 1.8, 0.7, facecolor='#FFF3E0', edgecolor='#455A64',
                           linewidth=1, zorder=2)
    ax1.add_patch(rect3)
    ax1.text(5.9, y, dt, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=7.5),
             color='#E65100', zorder=3, style='italic')
    # 力预设标注
    ax1.text(7.1, y, f'力: {f:.2f}', ha='center', va='center',
             fontproperties=FontProperties(fname=fp, size=8), color='#2E7D32')

# 列标题
for x, y, label in [(1.0, 11.5, '卦名/卦象'), (3.4, 11.5, '策略类型'), (5.9, 11.5, '卦辞核心'), (7.1, 11.5, '力预设')]:
    ax1.text(x, y, label, ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=9), color='#37474F')

# --- 右图：策略类型分布饼图 ---
strategy_groups = {
    '强力型\n(power/stable)': 8,
    '精细型\n(precision/delicate)': 7,
    '动态型\n(dynamic/following)': 5,
    '谨慎型\n(cautious/careful)': 6,
    '渐进型\n(progressive/adaptive)': 5,
    '特殊型\n(irregular/abort/other)': 8,
}
labels = list(strategy_groups.keys())
sizes = list(strategy_groups.values())
colors = ['#1565C0', '#2E7D32', '#E65100', '#6A1B9A', '#00838F', '#BF360C']
wedges, texts = ax2.pie(sizes, labels=labels, colors=colors, startangle=90,
                         textprops={'fontproperties': zh_sm, 'color': '#263238'})
ax2.set_title('64卦→39种策略类型分布', fontproperties=zh_title, pad=15, color='#1a237e')
# 中心标注
ax2.text(0, 0, f'共39种\n策略类型', ha='center', va='center',
         fontproperties=FontProperties(fname=fp_bold, size=12), color='#1a237e')

plt.tight_layout()
path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig3_2_hex_strategy.png'
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
