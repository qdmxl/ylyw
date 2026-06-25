#!/usr/bin/env python3
"""第7章配图：层次化嵌套三层架构图 + 全息自相似示意图 + 卦象意图通讯协议"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
from matplotlib.font_manager import FontProperties
import numpy as np

fp = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
fp_bold = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
zh = FontProperties(fname=fp, size=9)
zh_sm = FontProperties(fname=fp, size=7.5)
zh_title = FontProperties(fname=fp_bold, size=13)
zh_bold = FontProperties(fname=fp_bold, size=9)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8.5))

# ======== 左图：三层嵌套架构 ========
ax1.set_xlim(0, 12)
ax1.set_ylim(0, 12)
ax1.axis('off')
ax1.set_title('YLYW 层次化三层嵌套架构', fontproperties=zh_title, pad=15, color='#1a237e')

# 宏观层
macro_box = FancyBboxPatch((0.8, 8.5), 10.4, 2.0, boxstyle="round,pad=0.15",
                            facecolor='#E3F2FD', edgecolor='#1565C0', linewidth=2.5, zorder=1)
ax1.add_patch(macro_box)
ax1.text(6.0, 10.0, '宏观层（道/太极）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#1565C0')
macro_items = ['输入：人类指令 + 全局环境状态', '推理：64卦价值空间中映射为最优卦象意图', '输出：向各中观子系统广播卦象意图', '时间尺度：秒~分钟级别']
for idx, item in enumerate(macro_items):
    ax1.text(1.5, 9.1 - idx*0.32, f'•  {item}', ha='left', va='center', fontproperties=zh_sm, color='#37474F')

# 中观层
mid_box = FancyBboxPatch((0.8, 4.8), 10.4, 2.8, boxstyle="round,pad=0.15",
                           facecolor='#E8F5E9', edgecolor='#2E7D32', linewidth=2.5, zorder=1)
ax1.add_patch(mid_box)
ax1.text(6.0, 7.0, '中观层（卦/系统）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#2E7D32')

# 中观层内部的三个子元胞
for idx, (name, role, x) in enumerate([('双臂元胞', '取物+传递', 1.5), ('双腿元胞', '行走+平衡', 5.0), ('躯干元胞', '姿态+协调', 8.5)]):
    rect = FancyBboxPatch((x, 5.1), 2.8, 1.2, boxstyle="round,pad=0.08",
                          facecolor='#C8E6C9', edgecolor='#388E3C', linewidth=1.5, zorder=2)
    ax1.add_patch(rect)
    ax1.text(x+1.4, 5.8, f'{name}\n{role}', ha='center', va='center', fontproperties=zh_sm, color='#1B5E20', zorder=3)
    # 箭头连接
    if idx < 2:
        ax1.annotate('', xy=(x+2.9, 5.7), xytext=(x+2.9, 5.7),
                     arrowprops=dict(arrowstyle='<->', color='#388E3C', lw=1, connectionstyle='arc3,rad=0.3'))

# 微观层
micro_box = FancyBboxPatch((0.8, 1.5), 10.4, 2.2, boxstyle="round,pad=0.15",
                            facecolor='#FFF3E0', edgecolor='#E65100', linewidth=2.5, zorder=1)
ax1.add_patch(micro_box)
ax1.text(6.0, 3.0, '微观层（爻/组件）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=13), color='#E65100')

# 微观层的关节级元胞
joints = [('肩关节\nfull YLYW', 1.5), ('肘关节\nfull YLYW', 3.5), ('腕关节\nfull YLYW', 5.5), ('髋关节\nfull YLYW', 7.5), ('膝关节\nfull YLYW', 9.5)]
for name, x in joints:
    rect = FancyBboxPatch((x, 1.8), 1.8, 0.9, boxstyle="round,pad=0.05",
                          facecolor='#FFE0B2', edgecolor='#EF6C00', linewidth=1.2, zorder=2)
    ax1.add_patch(rect)
    ax1.text(x+0.9, 2.25, name, ha='center', va='center', fontproperties=FontProperties(fname=fp, size=7.5), color='#BF360C', zorder=3)

# 层级间的卦象意图通讯箭头
ax1.annotate('', xy=(6.0, 8.4), xytext=(6.0, 7.6),
            arrowprops=dict(arrowstyle='->', color='#1565C0', lw=3), zorder=5)
ax1.annotate('', xy=(6.0, 4.6), xytext=(6.0, 3.8),
            arrowprops=dict(arrowstyle='->', color='#2E7D32', lw=3), zorder=5)

# 通信协议标注
ax1.text(7.5, 8.0, '卦象意图', ha='center', va='center', fontproperties=zh_bold, color='#1565C0')
ax1.text(7.5, 7.5, '{卦名} {卦象}\n[紧急度] [约束]', ha='center', va='center', fontproperties=zh_sm, color='#1565C0')
ax1.text(7.5, 4.2, '变卦预警', ha='center', va='center', fontproperties=zh_bold, color='#E65100')
ax1.text(7.5, 3.7, '"三爻逼近老阳(0.92)"', ha='center', va='center', fontproperties=zh_sm, color='#E65100')

# 时间尺度标注
ax1.text(0.1, 10.5, '时间尺度', ha='left', va='center', fontproperties=zh_bold, color='#37474F', fontsize=9)
ax1.text(0.8, 10.5, '  秒~分钟', ha='left', va='center', fontproperties=zh_sm, color='#1565C0')
ax1.text(0.8, 7.5, '  0.1~1秒', ha='left', va='center', fontproperties=zh_sm, color='#2E7D32')
ax1.text(0.8, 4.5, '  毫秒~0.1秒', ha='left', va='center', fontproperties=zh_sm, color='#E65100')

# 核心原则标注
ax1.text(6.0, 0.8, '核心原则：每层运行结构完全相同的YLYW模型', ha='center', va='center',
         fontproperties=FontProperties(fname=fp_bold, size=10), color='#1a237e')

# ======== 右图：全息自相似 + 元胞分裂 ========
ax2.set_xlim(0, 12)
ax2.set_ylim(0, 12)
ax2.axis('off')
ax2.set_title('全息自相似与元胞分裂', fontproperties=zh_title, pad=15, color='#1a237e')

# 左侧：全息自相似——同一架构在不同粒度
ax2.text(2.5, 10.5, '全息自相似', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=12), color='#1565C0')

sizes = ['宏观', '中观', '微观']
for idx, (size, x, y, scale) in enumerate([('宏观', 2.5, 8.0, 1.0), ('中观', 2.5, 5.0, 0.6), ('微观', 2.5, 2.5, 0.35)]):
    # 分形YLYW元胞示意
    r = Circle((x, y), scale*1.2, facecolor='none', edgecolor='#1565C0', linewidth=2, zorder=2)
    ax2.add_patch(r)
    ax2.text(x, y+0.1, 'YLYW\n元胞', ha='center', va='center', fontproperties=FontProperties(fname=fp, size=8*scale+3), color='#1565C0', zorder=3)
    ax2.text(x, y-1.0, size, ha='center', va='center', fontproperties=zh_sm, color='#37474F')

# 箭头指向右侧
ax2.annotate('', xy=(4.0, 5.5), xytext=(4.0, 6.5),
            arrowprops=dict(arrowstyle='->', color='#546E7A', lw=2), zorder=5)
ax2.annotate('', xy=(2.5, 3.5), xytext=(2.5, 4.8),
            arrowprops=dict(arrowstyle='->', color='#546E7A', lw=2), zorder=5)

# 右侧：元胞分裂
ax2.text(8.5, 10.5, '元胞自分裂（自进化）', ha='center', va='center', fontproperties=FontProperties(fname=fp_bold, size=12), color='#E65100')

# 分裂前（单个元胞）
rect_before = FancyBboxPatch((7.0, 8.5), 3.0, 1.2, boxstyle="round,pad=0.1",
                              facecolor='#FFE0B2', edgecolor='#EF6C00', linewidth=2, zorder=2)
ax2.add_patch(rect_before)
ax2.text(8.5, 9.1, '单个元胞\n处理整个任务', ha='center', va='center', fontproperties=zh_sm, color='#BF360C', zorder=3)

# 分裂箭头
ax2.annotate('', xy=(8.5, 8.3), xytext=(8.5, 8.0),
            arrowprops=dict(arrowstyle='->', color='#E65100', lw=2.5), zorder=5)

# 分裂后（两个子元胞）
rect1 = FancyBboxPatch((6.5, 5.5), 2.0, 1.2, boxstyle="round,pad=0.1",
                        facecolor='#C8E6C9', edgecolor='#388E3C', linewidth=2, zorder=2)
ax2.add_patch(rect1)
ax2.text(7.5, 6.1, '子元胞A\n负责宏观', ha='center', va='center', fontproperties=zh_sm, color='#1B5E20', zorder=3)

rect2 = FancyBboxPatch((9.5, 5.5), 2.0, 1.2, boxstyle="round,pad=0.1",
                        facecolor='#C8E6C9', edgecolor='#388E3C', linewidth=2, zorder=2)
ax2.add_patch(rect2)
ax2.text(10.5, 6.1, '子元胞B\n负责微观', ha='center', va='center', fontproperties=zh_sm, color='#1B5E20', zorder=3)

ax2.annotate('', xy=(8.5, 7.3), xytext=(7.5, 6.7), arrowprops=dict(arrowstyle='->', color='#388E3C', lw=1.5))
ax2.annotate('', xy=(8.5, 7.3), xytext=(9.5, 6.7), arrowprops=dict(arrowstyle='->', color='#388E3C', lw=1.5))

# 分裂条件
ax2.text(8.5, 4.5, '分裂条件：卦象熵 H > 阈值', ha='center', va='center', fontproperties=zh_bold, color='#E65100')
ax2.text(8.5, 3.8, '单个元胞无法处理当前任务复杂度', ha='center', va='center', fontproperties=zh_sm, color='#37474F')

# 底部标注
ax2.text(8.5, 2.0, f'卦象熵: H = -Σ p(i) × log₂(p(i))\n当 H≈3 → 最大复杂度 → 触发分裂\n当 H≈0 → 最小复杂度 → 完全确定', ha='center', va='center',
         fontproperties=FontProperties(fname=fp, size=7.5), color='#37474F',
         bbox=dict(boxstyle='round', facecolor='#ECEFF1', edgecolor='#B0BEC5', alpha=0.8))

plt.tight_layout()
path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig7_architecture.png'
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
