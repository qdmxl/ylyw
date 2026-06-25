#!/usr/bin/env python3
"""YLYW书法论文图表生成"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from pathlib import Path
import os

# 直接指定中文字体
zh_font_path = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
if os.path.exists(zh_font_path):
    fm.fontManager.addfont(zh_font_path)
    prop = fm.FontProperties(fname=zh_font_path)
    font_name = prop.get_name()
    plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
    print(f"Font: {font_name} from {zh_font_path}")
else:
    print(f"Font not found: {zh_font_path}")
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

outdir = Path('/home/lijinhan/MXL/科研/ylyw/calligraphy/output/figures')
outdir.mkdir(parents=True, exist_ok=True)

# ===== 图1: 学习曲线 =====
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# 左图：卦象距离学习曲线
iterations = np.arange(1, 9)
distances = np.array([0.324, 0.300, 0.307, 0.199, 0.159, 0.134, 0.124, 0.087])
grades = ['中', '中', '中', '良', '良', '良', '良', '优']
grade_colors = {'中': '#e74c3c', '良': '#f39c12', '优': '#27ae60'}

colors = [grade_colors[g] for g in grades]
ax1.plot(iterations, distances, 'o-', color='#2c3e50', linewidth=2.5, markersize=10, zorder=2)
for i, (it, d, col) in enumerate(zip(iterations, distances, colors)):
    ax1.plot(it, d, 'o', color=col, markersize=14, markeredgewidth=2, markeredgecolor='white', zorder=3)
    label = f'{grades[i]}\n{d:.3f}'
    ax1.annotate(label, (it, d), textcoords="offset points", xytext=(0, 15),
                ha='center', fontsize=9, fontweight='bold', color=col)

ax1.fill_between(iterations, distances, alpha=0.15, color='#3498db')
ax1.axhline(y=0.1, color='#27ae60', linestyle='--', linewidth=1, alpha=0.6, label='优秀阈值')
ax1.set_xlabel('迭代次数', fontsize=13)
ax1.set_ylabel('卦象距离', fontsize=13)
ax1.set_title('「大」字学习曲线\n(卦象距离: 0.324→0.087,改善73.2%)', fontsize=14, fontweight='bold')
ax1.set_xticks(iterations)
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=10)
ax1.set_ylim(0, 0.4)

# 标注关键事件
ax1.annotate('第6轮\n卦象回归', xy=(6, 0.134), xytext=(4.5, 0.24),
            arrowprops=dict(arrowstyle='->', color='#2980b9', lw=2),
            fontsize=9, color='#2980b9', fontweight='bold')

# 右图：改善率瀑布图
improvements = [0]
for i in range(1, len(distances)):
    improvements.append(distances[i-1] - distances[i])

colors_bar = ['#2ecc71' if imp >= 0 else '#e74c3c' for imp in improvements]
bars = ax2.bar(iterations, improvements, color=colors_bar, edgecolor='white', linewidth=1.2)
ax2.axhline(y=0, color='black', linewidth=0.8)
ax2.set_xlabel('迭代次数', fontsize=13)
ax2.set_ylabel('改善量', fontsize=13)
ax2.set_title('每次迭代的改善量', fontsize=14, fontweight='bold')
ax2.set_xticks(iterations)

for bar, imp in zip(bars, improvements):
    if imp != 0:
        y_pos = bar.get_height() + (0.005 if imp > 0 else -0.015)
        ax2.text(bar.get_x() + bar.get_width()/2, y_pos, f'{imp:+.3f}',
                ha='center', fontsize=9, fontweight='bold')

fig.suptitle('YLYW知几学习：8轮迭代学习曲线', fontsize=16, fontweight='bold', y=1.02)
fig.tight_layout()
fig.savefig(outdir / 'fig1_learning_curve.png', dpi=300)
plt.close()
print("Fig1 saved")

# ===== 图2: 爻位收敛 =====
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

yao_names = ['初爻(方向)', '二爻(粗细)', '三爻(曲直)', '四爻(规整)', '五爻(重心x)', '上爻(重心y)']
yao_initial = [0.267, 0.158, 0.073, 0.000, 0.056, 0.012]
yao_final   = [0.014, 0.064, 0.045, 0.000, 0.031, 0.018]
yao_change  = [abs(yao_initial[i]) - abs(yao_final[i]) for i in range(6)]

# 左：堆叠条
x_pos = np.arange(len(yao_names))
width = 0.35
bars1 = ax1.bar(x_pos - width/2, [abs(v) for v in yao_initial], width, 
                label='初始偏差', color='#e74c3c', alpha=0.85, edgecolor='white')
bars2 = ax1.bar(x_pos + width/2, [abs(v) for v in yao_final], width,
                label='最终偏差', color='#2ecc71', alpha=0.85, edgecolor='white')
ax1.set_xticks(x_pos)
ax1.set_xticklabels(yao_names, rotation=20, ha='right', fontsize=10)
ax1.set_ylabel('绝对偏差', fontsize=13)
ax1.set_title('爻位偏差：初始 vs 最终', fontsize=14, fontweight='bold')
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3, axis='y')

for bar, val in zip(bars1, [abs(v) for v in yao_initial]):
    if val > 0.005:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f'{val:.3f}', ha='center', fontsize=8, fontweight='bold', color='#c0392b')
for bar, val in zip(bars2, [abs(v) for v in yao_final]):
    if val > 0.005:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                f'{val:.3f}', ha='center', fontsize=8, fontweight='bold', color='#27ae60')

# 右：改善量
colors_yao = ['#2ecc71' if c > 0.005 else ('#e74c3c' if c < -0.005 else '#95a5a6') for c in yao_change]
ax2.barh(yao_names, yao_change, color=colors_yao, edgecolor='white', height=0.6)
ax2.axvline(x=0, color='black', linewidth=0.8)
ax2.set_xlabel('改善量 (|初始|−|最终|)', fontsize=13)
ax2.set_title('爻位收敛效果', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='x')

for i, (name, chg) in enumerate(zip(yao_names, yao_change)):
    direction = '✓ 改善' if chg > 0.005 else ('✗ 恶化' if chg < -0.005 else '− 不变')
    offset = 0.012 if chg >= 0 else -0.025
    ax2.text(chg + offset, i, f'{chg:+.3f} {direction}', va='center', fontsize=10, fontweight='bold')

fig.suptitle('爻位收敛分析：从初爻大偏差到全局收敛', fontsize=16, fontweight='bold', y=1.02)
fig.tight_layout()
fig.savefig(outdir / 'fig2_yao_convergence.png', dpi=300)
plt.close()
print("Fig2 saved")

# ===== 图3: YLYW vs DRL 雷达图 =====
categories = ['初始性能', '样本效率', '可解释性', '学习迁移', '安全']
ylyw = [5, 5, 5, 4, 5]
drl  = [1, 1, 1, 2, 2]

N = len(categories)
angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
angles += angles[:1]

ylyw_vals = ylyw + ylyw[:1]
drl_vals = drl + drl[:1]

fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
ax.fill(angles, ylyw_vals, color='#3498db', alpha=0.3, label='YLYW知几学习')
ax.plot(angles, ylyw_vals, color='#2980b9', linewidth=3, marker='o', markersize=10)
ax.fill(angles, drl_vals, color='#e74c3c', alpha=0.2, label='深度强化学习(DRL)')
ax.plot(angles, drl_vals, color='#c0392b', linewidth=3, marker='s', markersize=10)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=13, fontweight='bold')
ax.set_ylim(0, 5.5)
ax.set_yticks([1, 2, 3, 4, 5])
ax.set_yticklabels(['1', '2', '3', '4', '5'], fontsize=10)

for i, (cat, y, d) in enumerate(zip(categories, ylyw, drl)):
    ax.annotate(f'Y:{y}', (angles[i], y), textcoords="offset points",
               xytext=(8, 8), fontsize=9, color='#2980b9', fontweight='bold')
    ax.annotate(f'D:{d}', (angles[i], d), textcoords="offset points",
               xytext=(8, -12), fontsize=9, color='#c0392b', fontweight='bold')

ax.set_title('YLYW知几学习 vs 深度强化学习\n5维对比', fontsize=16, fontweight='bold', pad=25)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
fig.tight_layout()
fig.savefig(outdir / 'fig3_ylyw_vs_drl.png', dpi=300)
plt.close()
print("Fig3 saved")

# ===== 图4: 系统架构图 =====
fig, ax = plt.subplots(figsize=(14, 9))
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.axis('off')

def draw_box(ax, x, y, w, h, text, color, title=None, fontsize=9, alpha=0.9):
    rect = plt.Rectangle((x-w/2, y-h/2), w, h, facecolor=color, edgecolor='#2c3e50',
                         linewidth=2, alpha=alpha, zorder=2)
    ax.add_patch(rect)
    if title:
        ax.text(x, y+h/2-0.25, title, ha='center', va='top', fontsize=fontsize+1,
               fontweight='bold', color='#2c3e50', zorder=3)
    ax.text(x, y, text, ha='center', va='center', fontsize=fontsize, color='white',
           fontweight='bold', zorder=3, linespacing=1.3)

def draw_arrow(ax, x1, y1, x2, y2, text='', color='#34495e', lw=2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
               arrowprops=dict(arrowstyle='->', color=color, lw=lw, connectionstyle='arc3,rad=0'))
    if text:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my+0.15, text, ha='center', va='bottom', fontsize=8, color=color, fontweight='bold')

# 顶层：输入
draw_box(ax, 2.5, 8.2, 3.5, 1, '字帖图像\n目标笔画结构', '#8e44ad', '输入层')
draw_box(ax, 7, 8.2, 3.5, 1, '八卦基元知识库\n笔法-卦象映射', '#8e44ad', '先验知识')

# 中层：视觉YLYW
draw_box(ax, 2.5, 6.2, 3.5, 1.3, '视觉YLYW\n笔画骨架→12D特征\n八卦隶属度→结构卦象', '#2980b9', '观帖（读帖）')
draw_box(ax, 7, 6.2, 3.5, 1.3, '书写YLYW\n卦象→笔法选择\n六爻→轨迹参数', '#27ae60', '临摹（以卦驭笔）')

# 底层：执行
draw_box(ax, 7, 4.2, 3.5, 1, 'MuJoCo书写环境\n机械臂轨迹+压力\n笔触渲染输出', '#e67e22', '执行层')

# 反馈回路
draw_box(ax, 2.5, 4.2, 3.5, 1, '视觉YLYW\n书写结果→结果卦象', '#2980b9', '感知（观我）')
draw_box(ax, 2.5, 2.2, 3.5, 1.3, '卦象差异分析\n爻位诊断→参数修正\n几何+压力参数更新', '#c0392b', '知几学习（自省+精进）')

# 箭头
draw_arrow(ax, 2.5, 7.55, 2.5, 6.85, '分析', '#2980b9')
draw_arrow(ax, 7, 7.55, 7, 6.85, '生成', '#27ae60')
draw_arrow(ax, 4.25, 6.2, 5.25, 6.2, '结构卦象', '#34495e', 2)
draw_arrow(ax, 7, 5.55, 7, 4.85, '轨迹执行', '#e67e22')
draw_arrow(ax, 5.25, 4.2, 3.5, 4.2, '结果渲染', '#34495e', 2)
draw_arrow(ax, 2.5, 3.55, 2.5, 2.85, '差异分析', '#c0392b')

# 反馈大箭头
ax.annotate('知几闭环', xy=(1.2, 2.2), xytext=(1.2, 6.2),
           arrowprops=dict(arrowstyle='->', color='#e74c3c', lw=3,
                          connectionstyle='arc3,rad=-0.3'),
           fontsize=11, color='#e74c3c', fontweight='bold', rotation=90, va='center')

# 安全八卦
draw_box(ax, 11.5, 5.2, 2.5, 3, '安全八卦\n笔尖压力保护\n纸面损坏预警\n墨量约束', '#1abc9c', '安全层', alpha=0.7)
draw_arrow(ax, 9.75, 5.2, 10.25, 5.2, '', '#1abc9c', 1.5)

# 焊接映射提示
ax.text(7, 0.8, '← 同一架构可迁移至焊接：视觉YLYW→焊缝结构 | 书写YLYW→焊接工艺 | 安全八卦→空间约束',
       ha='center', fontsize=9, color='#7f8c8d', style='italic',
       bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8))

ax.set_title('YLYW书法学习系统架构：观物取象，以卦驭笔', fontsize=17, fontweight='bold', pad=15)
fig.tight_layout()
fig.savefig(outdir / 'fig4_architecture.png', dpi=300)
plt.close()
print("Fig4 saved")

# ===== 图5: 书法↔焊接同构 =====
fig, ax = plt.subplots(figsize=(14, 7))
ax.set_xlim(0, 14)
ax.set_ylim(0, 7)
ax.axis('off')

ax.set_title('YLYW跨域泛化：书法 → 焊接 结构同构', fontsize=16, fontweight='bold', pad=10)

# 左边：书法
ax.text(3.5, 6.5, '🖌️ 书法域', ha='center', fontsize=15, fontweight='bold', color='#8e44ad')
# 右边：焊接
ax.text(10.5, 6.5, '🔧 焊接域', ha='center', fontsize=15, fontweight='bold', color='#c0392b')

rows = [
    ('字帖图像', '焊缝图像', 'L1 视觉感知'),
    ('笔画骨架', '焊道骨架', '结构提取'),
    ('笔画分解(横/竖/撇/捺)', '焊道分段(打底/填充/盖面)', '任务分解'),
    ('卦象驱动笔画排序', '卦象驱动焊接排序', 'L3 顺序推理'),
    ('笔法→机械臂轨迹', '工艺→焊枪轨迹', '轨迹生成'),
    ('安全八卦→纸面保护', '安全八卦→碰撞避免', '安全约束'),
    ('书写结果→卦象对比', '焊缝检测→卦象对比', '知几闭环'),
]

for i, (calli, weld, layer) in enumerate(rows):
    y = 5.7 - i * 0.8
    
    # 书法框
    rect_l = plt.Rectangle((0.8, y-0.3), 5.4, 0.6, facecolor='#d5f5e3', edgecolor='#27ae60', linewidth=1.5, alpha=0.7)
    ax.add_patch(rect_l)
    ax.text(3.5, y, calli, ha='center', va='center', fontsize=10, fontweight='bold', color='#1e8449')
    
    # 焊接框
    rect_r = plt.Rectangle((7.8, y-0.3), 5.4, 0.6, facecolor='#fadbd8', edgecolor='#e74c3c', linewidth=1.5, alpha=0.7)
    ax.add_patch(rect_r)
    ax.text(10.5, y, weld, ha='center', va='center', fontsize=10, fontweight='bold', color='#922b21')
    
    # 中心层标签
    ax.text(7, y, layer, ha='center', va='center', fontsize=7, color='#7f8c8d', fontstyle='italic')
    
    # 等同线
    ax.plot([6.2, 7.8], [y, y], '--', color='#bdc3c7', linewidth=1, alpha=0.8)
    ax.plot(6.2, y, '>', color='#bdc3c7', markersize=5)
    ax.plot(7.8, y, '<', color='#bdc3c7', markersize=5)

# 底部：同构总结
ax.text(7, 0.3, '✅ 同一套YLYW三层架构 | ✅ 同一套爻位关系推理 | ✅ 同一套知几学习闭环 | ✅ 仅需替换领域语义映射',
       ha='center', fontsize=9, color='#2c3e50', fontweight='bold',
       bbox=dict(boxstyle='round', facecolor='#ebf5fb', edgecolor='#2980b9', alpha=0.9))

fig.tight_layout()
fig.savefig(outdir / 'fig5_welding_isomorphism.png', dpi=300)
plt.close()
print("Fig5 saved")

print(f"\n✅ All figures saved to {outdir}")
