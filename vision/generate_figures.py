#!/usr/bin/env python3
"""Generate all figures for YLYW Vision paper"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

outdir = os.path.dirname(os.path.abspath(__file__))

# Chinese font
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# Figure 1: Architecture Diagram
# ============================================================
fig, ax = plt.subplots(1, 1, figsize=(10, 4))
ax.set_xlim(0, 10)
ax.set_ylim(0, 4)
ax.axis('off')

# Boxes
boxes = [
    (0.5, 2.5, 1.8, 1.0, 'Image\n96x96', '#E8F5E9'),
    (3.0, 2.5, 1.8, 1.0, '8 Specialized\nDetectors\n(one per trigram)', '#FFF3E0'),
    (5.5, 2.5, 1.8, 1.0, '8D Feature\nVector', '#E3F2FD'),
    (8.0, 2.5, 1.5, 1.0, 'Nearest\nPrototype\n→ Class', '#F3E5F5'),
]
for x, y, w, h, text, color in boxes:
    rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.1',
                                     facecolor=color, edgecolor='#333', linewidth=1.5)
    ax.add_patch(rect)
    ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=8, fontweight='bold')

# Arrows
for x1, x2 in [(0.5+1.8, 3.0), (3.0+1.8, 5.5), (5.5+1.8, 8.0)]:
    ax.annotate('', xy=(x2, 3.0), xytext=(x1, 3.0),
                arrowprops=dict(arrowstyle='->', color='#555', lw=1.5))

# Layer labels
ax.text(1.4, 1.6, 'L1: Trigram Prototypes', ha='center', fontsize=7, style='italic', color='#666')
ax.text(3.9, 1.6, 'L1 (specialized)', ha='center', fontsize=7, style='italic', color='#666')
ax.text(6.4, 1.6, 'L2 skipped', ha='center', fontsize=7, style='italic', color='#999')
ax.text(8.75, 1.6, 'L3: Classification', ha='center', fontsize=7, style='italic', color='#666')

# Trigram symbols
trigrams = ['Qian ☰', 'Kun ☷', 'Zhen ☳', 'Xun ☴', 'Kan ☵', 'Li ☲', 'Gen ☶', 'Dui ☱']
for i, t in enumerate(trigrams):
    ax.text(3.9, 3.65 - i*0.15, t, ha='center', fontsize=5.5, color='#888')

ax.set_title('YLYW Vision Classifier Architecture', fontsize=11, fontweight='bold', pad=12)

plt.tight_layout()
fig.savefig(os.path.join(outdir, 'fig_architecture.png'), dpi=150, bbox_inches='tight')
plt.close()
print('fig_architecture.png done')

# ============================================================
# Figure 2: Per-class Accuracy (STL-10)
# ============================================================
classes = ['Qian\n(airplane)', 'Dui\n(cat)', 'Li\n(car)', 'Zhen\n(horse)',
           'Xun\n(bird)', 'Kan\n(deer)', 'Gen\n(truck)', 'Kun\n(ship)']
top1 = [51.5, 24.0, 53.0, 57.9, 15.5, 40.0, 25.4, 29.0]
top3 = [71.9, 82.2, 75.1, 76.6, 83.9, 63.0, 75.5, 71.6]

x = np.arange(len(classes))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 4.5))
bars1 = ax.bar(x - width/2, top1, width, label='Top-1', color='#1A5276', edgecolor='white')
bars3 = ax.bar(x + width/2, top3, width, label='Top-3', color='#27AE60', edgecolor='white')

ax.axhline(y=12.5, color='red', linestyle='--', linewidth=1, alpha=0.7, label='Random (12.5%)')
ax.axhline(y=37.5, color='orange', linestyle='--', linewidth=1, alpha=0.7, label='Random Top-3 (37.5%)')

for bar in bars1:
    h = bar.get_height()
    ax.text(bar.get_x()+bar.get_width()/2, h+0.5, f'{h:.1f}%', ha='center', fontsize=7, fontweight='bold')
for bar in bars3:
    h = bar.get_height()
    ax.text(bar.get_x()+bar.get_width()/2, h+0.5, f'{h:.1f}%', ha='center', fontsize=7)

ax.set_xticks(x)
ax.set_xticklabels(classes, fontsize=8)
ax.set_ylabel('Accuracy (%)', fontsize=10)
ax.set_title('STL-10 Zero-Shot Classification Accuracy by Class', fontsize=11, fontweight='bold')
ax.legend(fontsize=8, loc='upper right')
ax.set_ylim(0, 100)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(outdir, 'fig_stl10_accuracy.png'), dpi=150, bbox_inches='tight')
plt.close()
print('fig_stl10_accuracy.png done')

# ============================================================
# Figure 3: Confusion Matrix
# ============================================================
confusion = np.array([
    [412, 19, 60, 49, 43, 76, 25, 116],
    [18, 192, 4, 274, 81, 208, 12, 11],
    [20, 15, 424, 110, 14, 13, 138, 66],
    [14, 111, 17, 463, 78, 73, 31, 13],
    [63, 121, 4, 238, 124, 194, 19, 37],
    [30, 111, 2, 244, 80, 320, 8, 5],
    [36, 36, 251, 138, 24, 14, 203, 98],
    [196, 26, 112, 66, 45, 50, 73, 232],
])

# Normalize by row
conf_norm = confusion / confusion.sum(axis=1, keepdims=True)

fig, ax = plt.subplots(figsize=(8, 6.5))
im = ax.imshow(conf_norm, cmap='YlOrRd', vmin=0, vmax=0.65)

class_labels = ['Qian', 'Dui', 'Li', 'Zhen', 'Xun', 'Kan', 'Gen', 'Kun']
stl_labels = ['airplane', 'cat', 'car', 'horse', 'bird', 'deer', 'truck', 'ship']

ax.set_xticks(range(8))
ax.set_yticks(range(8))
ax.set_xticklabels([f'{c}' for c in class_labels], fontsize=8)
ax.set_yticklabels([f'{c}\n({s})' for c, s in zip(class_labels, stl_labels)], fontsize=8)

for i in range(8):
    for j in range(8):
        val = confusion[i, j]
        color = 'white' if conf_norm[i, j] > 0.3 else 'black'
        ax.text(j, i, str(val), ha='center', va='center', fontsize=7, color=color, fontweight='bold')

ax.set_xlabel('Predicted Trigram', fontsize=10)
ax.set_ylabel('True Class (STL-10)', fontsize=10)
ax.set_title('STL-10 Confusion Matrix', fontsize=11, fontweight='bold')
plt.colorbar(im, ax=ax, label='Fraction', shrink=0.8)

plt.tight_layout()
fig.savefig(os.path.join(outdir, 'fig_confusion.png'), dpi=150, bbox_inches='tight')
plt.close()
print('fig_confusion.png done')

# ============================================================
# Figure 4: Cross-Dataset Comparison
# ============================================================
datasets = ['Synthetic\nTextures', 'Synthetic\nObjects', 'STL-10\n(Real)', 'Brodatz\n(Real)']
top1_vals = [100, 89.6, 37.0, 14.0]
top3_vals = [100, 99.3, 75.0, 55.2]
colors_t1 = ['#1A5276', '#1A5276', '#E74C3C', '#E74C3C']
colors_t3 = ['#85C1E9', '#85C1E9', '#F1948A', '#F1948A']

x = np.arange(len(datasets))
width = 0.3

fig, ax = plt.subplots(figsize=(7, 4))
b1 = ax.bar(x - width/2, top1_vals, width, label='Top-1', color=colors_t1, edgecolor='white')
b3 = ax.bar(x + width/2, top3_vals, width, label='Top-3', color=colors_t3, edgecolor='white')

for bar, val in zip(b1, top1_vals):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1, f'{val}%', ha='center', fontsize=9, fontweight='bold')
for bar, val in zip(b3, top3_vals):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1, f'{val}%', ha='center', fontsize=8)

ax.set_xticks(x)
ax.set_xticklabels(datasets, fontsize=9)
ax.set_ylabel('Accuracy (%)', fontsize=10)
ax.set_title('Cross-Dataset Zero-Shot Classification Performance', fontsize=11, fontweight='bold')
ax.legend(fontsize=9)
ax.set_ylim(0, 115)
ax.grid(axis='y', alpha=0.3)

# Add type labels
ax.text(0.5, 110, 'Synthetic', ha='center', fontsize=8, color='#1A5276', fontweight='bold',
        bbox=dict(boxstyle='round', facecolor='#E3F2FD', alpha=0.5))
ax.text(2.5, 110, 'Real', ha='center', fontsize=8, color='#E74C3C', fontweight='bold',
        bbox=dict(boxstyle='round', facecolor='#FDEDEC', alpha=0.5))

plt.tight_layout()
fig.savefig(os.path.join(outdir, 'fig_comparison.png'), dpi=150, bbox_inches='tight')
plt.close()
print('fig_comparison.png done')

print('\nAll figures generated.')
