#!/usr/bin/env python3
"""生成专著版 YLYW 三层架构图 —— 中文版，使用 Noto Sans CJK 字体"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.font_manager import FontProperties
import numpy as np

# 注册 Noto Sans CJK 字体
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
bold_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

zh = FontProperties(fname=font_path, size=10)
zh_sm = FontProperties(fname=font_path, size=8)
zh_lg = FontProperties(fname=font_path, size=13)
zh_bold = FontProperties(fname=bold_path, size=10)
zh_bold_lg = FontProperties(fname=bold_path, size=13)
zh_title = FontProperties(fname=bold_path, size=18)
zh_note = FontProperties(fname=font_path, size=7)

fig, ax = plt.subplots(1, 1, figsize=(18, 10))
ax.set_xlim(0, 18)
ax.set_ylim(0, 10)
ax.axis('off')

L1_C = '#E3F2FD'
L2_C = '#E8F5E9'
L3_C = '#F3E5F5'
L3P_C = '#FCE4EC'
SAFE_C = '#FFEBEE'
OUT_C = '#E0F7FA'
SENS_C = '#FFF3E0'

def box(x, y, w, h, text, color, edge='#455A64', fs=9, bold=False):
    fbb = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                         facecolor=color, edgecolor=edge, linewidth=1.2, zorder=2)
    ax.add_patch(fbb)
    fp = zh_bold if bold else zh
    if fs <= 7: fp = zh_sm
    elif fs >= 13: fp = zh_bold_lg if bold else zh_lg
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontproperties=fp, color='#1a237e', zorder=3)

def arrow(x1, y1, x2, y2, color='#37474F', lw=1.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), zorder=1,
                arrowprops=dict(arrowstyle='->', color=color, lw=lw))

def dashed_arrow(x1, y1, x2, y2, color='#78909C', lw=1.2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1), zorder=1,
                arrowprops=dict(arrowstyle='->', color=color, lw=lw, linestyle='dashed'))

# ======== 标题 ========
ax.text(9, 9.7, 'YLYW 联邦式神经符号三层架构',
        ha='center', va='center', fontproperties=zh_title, color='#0D47A1')

# ======== 传感器 ========
box(0.3, 7.5, 2.6, 1.5,
    '传感器数据\n13维物理特征\n(稳定性、滚动、力需求……)',
    SENS_C, fs=9)

# ======== L1 ========
box(3.6, 7.5, 3.5, 1.5,
    'L1  八卦隶属度层\n8个八卦原型 × 高斯核映射\n→ 8维连续隶属度向量',
    L1_C, bold=True, fs=9)

# ======== L2 ========
box(7.8, 7.5, 3.5, 1.5,
    'L2  六爻编码层\n6条加权聚合公式\n→ 6维爻值向量 + 阴阳判定',
    L2_C, bold=True, fs=9)

# ======== L3 ========
box(3.6, 5.2, 10.7, 1.6,
    'L3  六十四卦匹配层\n余弦相似度  sim(y,t) = (y·t)/(||y||·||t||)\n64卦爻模板中搜索最佳匹配 → Top-1 卦象 + Top-3 备选',
    L3_C, bold=True, fs=10)

# ======== L3+ ========
box(3.6, 3.5, 5.8, 1.3,
    'L3+  爻位关系运算层\n当位 · 得中 · 乘承 · 亲比 · 呼应\n→ 爻位质量评分 S_yao + 力修正系数',
    L3P_C, bold=True, fs=9)

# ======== 安全八卦 ========
box(10.2, 3.5, 4.1, 1.3,
    '安全八卦（并行运行）\n安全六爻编码\n→ 5级安全等级 + 力修正',
    SAFE_C, bold=True, fs=9)

# ======== 策略输出 ========
box(6.5, 1.6, 4.8, 1.2,
    '策略输出\n策略类型 | 力预设 | 速度等级\n接近角度 | 安全等级 | 注意事项',
    OUT_C, bold=True, fs=9)

# ======== 箭头 ========
arrow(2.9, 8.25, 3.6, 8.25)
arrow(7.1, 8.25, 7.8, 8.25)
arrow(9.55, 7.5, 7.0, 6.8)
dashed_arrow(11.3, 7.5, 12.2, 4.8)
arrow(6.5, 5.2, 6.5, 4.8)
arrow(6.5, 3.5, 8.9, 2.8)
dashed_arrow(12.2, 3.5, 10.0, 2.8)

# ======== 参数标注 ========
ax.text(0.3, 6.3, '48个参数\n(8卦×6维原型)', fontproperties=zh_note, color='#78909C', ha='center')
ax.text(7.8, 6.6, '6个阈值参数', fontproperties=zh_note, color='#78909C', ha='center')
ax.text(3.6, 4.6, '384个模板参数\n(64卦×6维)', fontproperties=zh_note, color='#78909C', ha='center')
ax.text(8.9, 3.1, '总参数量: 443\n推理延迟: ~1.7ms (CPU)', fontproperties=zh_note, color='#0D47A1', ha='center')

# 分隔线
for ypos in [7.2, 4.9]:
    ax.axhline(y=ypos, xmin=0.02, xmax=0.98, color='#B0BEC5', lw=0.6, linestyle=':')

# 右侧注释
notes = [
    (15.2, 7.6, '物理世界\n→ 符号基元', 8),
    (15.2, 6.2, '符号基元\n→ 结构化编码', 8),
    (15.2, 4.2, '64卦模板库\n余弦相似度匹配\nTop-3 变卦备选', 8),
]
for x, y, t, fs in notes:
    fp = FontProperties(fname=font_path, size=fs)
    ax.text(x, y, t, ha='left', va='center', fontproperties=fp, color='#546E7A', style='italic')

path = '/home/lijinhan/MXL/科研/ylyw/monograph/fig3_1_architecture.png'
plt.tight_layout()
plt.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Done: {path}')
