#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第10章 图10.4 YLYW语义底座四维成长曲线"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.6))

# G1/G2: 元胞成长
sent = [376, 752, 1505, 3010, 5267, 7525]
chars = [580, 787, 966, 1169, 1339, 1464]
words = [1709, 3240, 5891, 9686, 14848, 19483]
ax = axes[0]
ax.plot(sent, chars, 'o-', color='#1f6f8b', lw=2, label='字元胞 (G1)')
ax.plot(sent, words, 's-', color='#2e8b57', lw=2, label='词元胞 (G2)')
ax.set_xlabel('累计阅读句数', fontsize=10)
ax.set_ylabel('元胞数量', fontsize=10)
ax.set_title('(a) 覆盖面与复杂度成长', fontsize=11, fontweight='bold')
ax.legend(fontsize=9); ax.grid(alpha=0.3)

# G3: 语义收敛
ratio = [5, 12, 25, 50, 75, 100]
stab = [None, 22, 28, 33, 40, 56]
ax = axes[1]
xs = ratio[1:]; ys = stab[1:]
ax.plot(xs, ys, 'D-', color='#b7791f', lw=2)
for x, y in zip(xs, ys):
    ax.annotate(str(y)+'%', (x, y), textcoords='offset points',
                xytext=(0, 7), ha='center', fontsize=8.5, color='#7a4f08')
ax.set_xlabel('累计阅读比例 (%)', fontsize=10)
ax.set_ylabel('相邻阶段语义划分稳定率 (%)', fontsize=10)
ax.set_ylim(15, 65)
ax.set_title('(b) 语义收敛（理解巩固）', fontsize=11, fontweight='bold')
ax.grid(alpha=0.3)

# G4: 判别准确率
ax = axes[2]
labels = ['纯语料\n通道', '统一\n双通道']
vals = [95.8, 97.7]
bars = ax.bar(labels, vals, color=['#2e8b57', '#c0392b'], alpha=0.8, width=0.55)
for b, v in zip(bars, vals):
    ax.text(b.get_x()+b.get_width()/2, v+0.2, f'{v}%', ha='center',
            fontsize=10.5, fontweight='bold')
ax.set_ylim(90, 100)
ax.set_ylabel('判别准确率 (%)', fontsize=10)
ax.set_title('(c) 统一判别准确率 (G4)', fontsize=11, fontweight='bold')
ax.grid(alpha=0.3, axis='y')

fig.suptitle('图10.4  YLYW语义底座的四维成长曲线：越读越懂',
             fontsize=13.5, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.savefig('/home/lijinhan/MXL/科研/ylyw/paper/第10章_汉语语义理解引擎/fig10_4_growth.png',
            dpi=180, bbox_inches='tight', facecolor='white')
print('OK fig10_4')
