#!/usr/bin/env python3
"""第4章 知己学习配图：知几知耻双环图 + 与RL对比图"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties
import numpy as np

fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fp_bold = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
zh = FontProperties(fname=fp, size=10)
zh_sm = FontProperties(fname=fp, size=8)
zh_title = FontProperties(fname=fp_bold, size=14)
zh_bold = FontProperties(fname=fp_bold, size=10)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8.5))

# ======== 左图：知几知耻双环图 ========
ax1.set_xlim(0, 12)
ax1.set_ylim(0, 12)
ax1.axis('off')
ax1.set_title('知己学习双环架构：知几 + 知耻', fontproperties=zh_title, pad=18, color='#1a237e')

# 核心圆
circle = plt.Circle((5.5, 6), 1.2, facecolor='#FFF3E0', edgecolor='#E65100', linewidth=2.5, zorder=3)
ax1.add_patch(circle)
ax1.text(5.5, 6, '知己学习', ha='center', va='center', fontproperties=zh_bold, color='#E65100', zorder=4)

# 知几环（左）
box_zhiji = FancyBboxPatch((1.5, 8.5), 4.5, 2.0, boxstyle="round,pad=0.15",
                          facecolor='#E3F2FD', edgecolor='#1565C0', linewidth=2, zorder=1)
ax1.add_patch(box_zhiji)
ax1.text(3.75, 9.7, '知几（Zhi-Ji）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#1565C0', zorder=2)
items_zhiji = ['事先征兆辨识', '几者动之微，吉之先见者也', '物极必反预判', 'Top-3卦象变卦预警', '四爻脆弱性早期识别']
for idx, item in enumerate(items_zhiji):
    ax1.text(3.75, 8.9 - idx*0.33, f'•  {item}', ha='center', va='center', fontproperties=zh_sm, color='#37474F', zorder=2)

# 知耻环（右）
box_zhichi = FancyBboxPatch((6.0, 3.5), 4.5, 2.0, boxstyle="round,pad=0.15",
                          facecolor='#E8F5E9', edgecolor='#2E7D32', linewidth=2, zorder=1)
ax1.add_patch(box_zhichi)
ax1.text(8.25, 4.7, '知耻（Zhi-Chi）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#2E7D32', zorder=2)
items_zhichi = ['事后失败修正', '知耻近乎勇', '推理链回放诊断', '定位责任层修正', '仅1-5个参数/次']
for idx, item in enumerate(items_zhichi):
    ax1.text(8.25, 4.0 - idx*0.33, f'•  {item}', ha='center', va='center', fontproperties=zh_sm, color='#37474F', zorder=2)

# 连接箭头
ax1.annotate('', xy=(4.0, 8.5), xytext=(4.5, 7.2),
            arrowprops=dict(arrowstyle='->', color='#546E7A', lw=2.5, connectionstyle='arc3,rad=0.3'), zorder=5)
ax1.annotate('', xy=(7.0, 5.5), xytext=(6.5, 4.2),
            arrowprops=dict(arrowstyle='->', color='#546E7A', lw=2.5, connectionstyle='arc3,rad=0.3'), zorder=5)

# 标注
ax1.text(4.5, 10.8, '事前预防', ha='center', va='center', fontproperties=zh_bold, color='#1565C0')
ax1.text(8.25, 6.3, '事后修正', ha='center', va='center', fontproperties=zh_bold, color='#2E7D32')

# 底部说明
ax1.text(5.5, 1.3, '知几：物极必反预判 & 变卦提前预警\n知耻：失败推理链诊断 → 定向参数修正',
         ha='center', va='center', fontproperties=FontProperties(fname=fp, size=9), color='#37474F',
         bbox=dict(boxstyle='round', facecolor='#ECEFF1', edgecolor='#B0BEC5', alpha=0.8))
# 数据标注
ax1.text(5.5, 0.4, f'零样本 92.7% | 443 参数 | 3步收敛 | 四个实验验证', ha='center', va='center',
         fontproperties=zh_sm, color='#78909C')

# ======== 右图：知己学习 vs RL 对比 ========
ax2.set_xlim(0, 10)
ax2.set_ylim(0, 12)
ax2.axis('off')
ax2.set_title('知己学习 vs 强化学习：六个维度对比', fontproperties=zh_title, pad=18, color='#1a237e')

# 三列标题
labels = ['维度', '强化学习 (RL)', '知己学习 (ZJ)']
colors_bg = ['#ECEFF1', '#FFEBEE', '#E3F2FD']
for x, label, bg in zip([0.5, 3.7, 7.3], labels, colors_bg):
    rect = FancyBboxPatch((x-0.5, 11), 2.5, 1.0, boxstyle="round,pad=0.08",
                          facecolor=bg, edgecolor='#455A64', linewidth=1, zorder=2)
    ax2.add_patch(rect)
    fp_use = zh_title if label == '维度' else zh_bold
    ax2.text(x+0.75, 11.5, label, ha='center', va='center', fontproperties=zh_bold, color='#1a237e', zorder=3)

rows = [
    ('时间性', '事后奖惩驱动', '事先征兆辨识'),
    ('知识起点', '白板（tabula rasa）', '内建先验 Ω'),
    ('学习本质', '建立因果关联', '校准关键阈值'),
    ('探索方式', '全局盲目试错', '局部合规校准'),
    ('可解释性', '黑箱（百万权重）', '透明（推理链可读）'),
    ('安全性', '数据"喂"出来', '结构"建"出来'),
]

for idx, (dim, rl, zj) in enumerate(rows):
    y = 10.0 - idx * 1.3
    bg_r = '#F5F5F5' if idx % 2 == 0 else '#FAFAFA'
    rect = plt.Rectangle((0, y-0.45), 2.5, 0.9, facecolor=bg_r, edgecolor='#E0E0E0', lw=0.5, zorder=0)
    ax2.add_patch(rect)
    ax2.text(1.25, y, dim, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=9),
             color='#37474F', fontweight='bold', zorder=3)
    ax2.text(4.0, y, rl, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=8.5),
             color='#C62828', zorder=3)
    ax2.text(7.3, y, zj, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=8.5),
             color='#1565C0', zorder=3)

# 底部 K=f(D) vs K=Ω⊕f_calibrate(D)
ax2.text(0, 0.5, 'K = f(D)', ha='left', va='center', fontproperties=FontProperties(fname=fp_bold, size=11),
         color='#C62828')
ax2.text(5, 0.5, 'K = Ω ⊕ f_calibrate(D)', ha='left', va='center', fontproperties=FontProperties(fname=fp_bold, size=11),
         color='#1565C0')
ax2.text(5, 0.0, '(先验Ω  +  校准)', ha='left', va='center', fontproperties=zh_sm, color='#546E7A')

# 分界线
ax2.axvline(x=2.8, ymin=0.1, ymax=0.88, color='#B0BEC5', lw=1, linestyle=':')
ax2.axvline(x=6.2, ymin=0.1, ymax=0.88, color='#B0BEC5', lw=1, linestyle=':')

plt.tight_layout()
path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig4_1_zhiji_learning.png'
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
