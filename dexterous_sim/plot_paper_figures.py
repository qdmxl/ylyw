#!/usr/bin/env python3
"""
YLYW 灵巧手仿真 — 论文用可视化图

从 benchmark_screenshot.py 的运行结果生成：
  1. 物体×策略 提升热力图
  2. 每种物体的最佳策略条形图
  3. 接触手指数与提升的散点图
"""

import os, json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# 字体设置
plt.rcParams['font.family'] = ['DejaVu Sans']
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 300

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'paper_figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── 实验数据 ───
RESULTS = [
    # (物体, 策略, 力, 接触, 提升mm, 成功)
    ('Sphere', 'soft_grasp', 0.6, 5, 15.8, 1),
    ('Sphere', 'soft_grasp', 1.0, 5, 15.8, 1),
    ('Sphere', 'wrap_grasp', 0.6, 5, 15.8, 1),
    ('Sphere', 'wrap_grasp', 1.0, 5, 8.5, 1),
    ('Sphere', 'firm_grasp', 0.6, 5, 15.8, 1),
    ('Sphere', 'firm_grasp', 1.0, 5, -65.0, 0),
    ('Sphere', 'adaptive_grasp', 0.6, 5, 15.8, 1),
    ('Sphere', 'adaptive_grasp', 1.0, 5, 15.8, 1),
    ('Box', 'power_grasp', 0.6, 5, 12.9, 1),
    ('Box', 'power_grasp', 1.0, 5, 12.9, 1),
    ('Box', 'precision_grasp', 0.6, 5, 12.9, 1),
    ('Box', 'precision_grasp', 1.0, 5, 12.9, 1),
    ('Box', 'wrap_grasp', 0.6, 5, 12.9, 1),
    ('Box', 'wrap_grasp', 1.0, 5, 12.9, 1),
    ('Box', 'firm_grasp', 0.6, 5, 12.9, 1),
    ('Box', 'firm_grasp', 1.0, 5, 12.9, 1),
    ('Cylinder', 'wrap_grasp', 0.6, 5, 21.4, 1),
    ('Cylinder', 'wrap_grasp', 1.0, 5, 17.4, 1),
    ('Cylinder', 'firm_grasp', 0.6, 5, 17.4, 1),
    ('Cylinder', 'firm_grasp', 1.0, 5, 22.4, 1),
    ('Cylinder', 'adaptive_grasp', 0.6, 5, 17.4, 1),
    ('Cylinder', 'adaptive_grasp', 1.0, 5, 17.4, 1),
    ('Cylinder', 'cautious_grasp', 0.6, 5, 17.4, 1),
    ('Cylinder', 'cautious_grasp', 1.0, 5, 17.4, 1),
    ('Rod', 'precision_grasp', 0.6, 5, -4.4, 0),
    ('Rod', 'precision_grasp', 1.0, 5, -4.4, 0),
    ('Rod', 'cautious_grasp', 0.6, 5, -4.4, 0),
    ('Rod', 'cautious_grasp', 1.0, 5, -4.4, 0),
    ('Rod', 'soft_grasp', 0.6, 5, -4.4, 0),
    ('Rod', 'soft_grasp', 1.0, 5, -4.4, 0),
    ('Rod', 'adaptive_grasp', 0.6, 5, -4.4, 0),
    ('Rod', 'adaptive_grasp', 1.0, 5, -4.4, 0),
    ('Mushroom', 'wrap_grasp', 0.6, 5, -1.6, 0),
    ('Mushroom', 'wrap_grasp', 1.0, 5, -1.6, 0),
    ('Mushroom', 'soft_grasp', 0.6, 5, -1.6, 0),
    ('Mushroom', 'soft_grasp', 1.0, 5, -1.6, 0),
    ('Mushroom', 'cautious_grasp', 0.6, 5, -1.6, 0),
    ('Mushroom', 'cautious_grasp', 1.0, 5, -1.6, 0),
    ('Mushroom', 'adaptive_grasp', 0.6, 5, -1.6, 0),
    ('Mushroom', 'adaptive_grasp', 1.0, 5, -1.6, 0),
    ('Dumbbell', 'power_grasp', 0.6, 5, 2.6, 0),
    ('Dumbbell', 'power_grasp', 1.0, 5, 2.6, 0),
    ('Dumbbell', 'wrap_grasp', 0.6, 5, 2.5, 0),
    ('Dumbbell', 'wrap_grasp', 1.0, 5, 2.6, 0),
    ('Dumbbell', 'adaptive_grasp', 0.6, 5, -3.9, 0),
    ('Dumbbell', 'adaptive_grasp', 1.0, 5, 2.1, 0),
    ('Dumbbell', 'firm_grasp', 0.6, 5, 2.6, 0),
    ('Dumbbell', 'firm_grasp', 1.0, 5, 2.6, 0),
    ('Disc', 'soft_grasp', 0.6, 5, -25.8, 0),
    ('Disc', 'soft_grasp', 1.0, 5, -19.6, 0),
    ('Disc', 'wrap_grasp', 0.6, 5, -25.1, 0),
    ('Disc', 'wrap_grasp', 1.0, 5, -23.1, 0),
    ('Disc', 'cautious_grasp', 0.6, 5, -7.9, 0),
    ('Disc', 'cautious_grasp', 1.0, 5, -19.2, 0),
    ('Disc', 'firm_grasp', 0.6, 5, 4.2, 1),
    ('Disc', 'firm_grasp', 1.0, 5, -17.4, 0),
]

# 统一用英文——适合论文投稿
OBJECTS = ['Sphere', 'Box', 'Cylinder', 'Rod', 'Mushroom', 'Dumbbell', 'Disc']
STRATEGIES = ['soft_grasp', 'wrap_grasp', 'firm_grasp', 'cautious_grasp',
              'power_grasp', 'precision_grasp', 'adaptive_grasp']

# ─── 图1：提升高度热力图 ───
def plot_heatmap():
    """物体 × 策略 的提升高度热力图（取力0.6的结果）"""
    data = np.zeros((len(OBJECTS), len(STRATEGIES)))
    for obj_i, obj in enumerate(OBJECTS):
        for strat_j, strat in enumerate(STRATEGIES):
            vals = [r[4] for r in RESULTS if r[0]==obj and r[1]==strat and r[2]==0.6]
            data[obj_i, strat_j] = vals[0] if vals else -50

    fig, ax = plt.subplots(figsize=(10, 5.5))
    cmap = plt.cm.RdYlGn
    cmap.set_under('darkred')
    vmin, vmax = -15, 25
    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')

    ax.set_xticks(range(len(STRATEGIES)))
    ax.set_xticklabels(STRATEGIES, rotation=30, ha='right', fontsize=9)
    ax.set_yticks(range(len(OBJECTS)))
    ax.set_yticklabels(OBJECTS, fontsize=10)
    ax.set_xlabel('Grasp Strategy', fontsize=11)
    ax.set_ylabel('Object', fontsize=11)

    # 填入数值
    for i in range(len(OBJECTS)):
        for j in range(len(STRATEGIES)):
            v = data[i, j]
            if v >= 3:
                text_clr = 'white' if v < 8 else 'white'
            else:
                text_clr = 'white' if v < -5 else 'black'
            label = f'{v:.0f}'
            ax.text(j, i, label, ha='center', va='center', fontsize=8,
                    color=text_clr, fontweight='bold')

    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label('Lift Height (mm)', fontsize=10)

    ax.set_title('YLYW Dexterous Hand Zero-Shot Grasping — Lift Height (mm)', fontsize=13, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig1_heatmap.png'), bbox_inches='tight')
    plt.close()
    print(f'✅ 图1: heatmap saved')


# ─── 图2：每种物体的最佳策略条形图 ───
def plot_best_strategies():
    """7种物体×8策略的力0.6时提升高度（分组条形图）"""
    strat_short = {
        'soft_grasp': 'SOFT', 'wrap_grasp': 'WRAP', 'firm_grasp': 'FIRM',
        'cautious_grasp': 'CAUT', 'power_grasp': 'POWR',
        'precision_grasp': 'PREC', 'adaptive_grasp': 'ADPT',
    }
    n_groups = len(OBJECTS)
    n_bars = len(STRATEGIES)
    bar_width = 0.10
    x = np.arange(n_groups)

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = plt.cm.tab10(np.linspace(0, 1, n_bars))

    for j, strat in enumerate(STRATEGIES):
        vals = []
        for obj in OBJECTS:
            v = [r[4] for r in RESULTS if r[0]==obj and r[1]==strat and r[2]==0.6]
            vals.append(v[0] if v else 0)
        ax.bar(x + j*bar_width, vals, bar_width,
               label=strat_short.get(strat, strat), color=colors[j])

    ax.set_xlabel('Object', fontsize=11)
    ax.set_ylabel('Lift Height (mm)', fontsize=11)
    ax.set_title('YLYW Strategy × Object — Zero-Shot Grasp (force=0.6)', fontsize=12, fontweight='bold')
    ax.set_xticks(x + bar_width * (n_bars-1) / 2)
    ax.set_xticklabels(OBJECTS, fontsize=10)
    ax.axhline(y=3, color='gray', linestyle='--', linewidth=0.8, label='Success threshold (3mm)')
    ax.legend(fontsize=7, ncol=7, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig2_bar.png'), bbox_inches='tight')
    plt.close()
    print(f'✅ 图2: bar chart saved')


# ─── 图3：力缩放对提升的影响 ───
def plot_force_comparison():
    """力0.6 vs 力1.0对提升的影响（只选成功物体）"""
    fig, axes = plt.subplots(2, 4, figsize=(14, 6), sharey=True)
    axes = axes.flatten()
    colors = {'0.6': '#2E86AB', '1.0': '#DB5461'}
    
    valid_objects = ['球体', '立方体', '圆柱体', '盘状体']
    for idx, obj in enumerate(valid_objects):
        ax = axes[idx]
        strat_set = sorted(set(r[1] for r in RESULTS if r[0]==obj and r[2]==0.6))
        x = np.arange(len(strat_set))
        w = 0.30
        for fi, scale in enumerate([0.6, 1.0]):
            vals = []
            for s in strat_set:
                v = [r[4] for r in RESULTS if r[0]==obj and r[1]==s and r[2]==scale]
                vals.append(v[0] if v else -50)
            ax.bar(x + (fi-0.5)*w, vals, w, label=f'force={scale}',
                   color=colors[str(scale)], alpha=0.85)
        ax.axhline(y=3, color='gray', linestyle='--', linewidth=0.6)
        ax.set_title(obj, fontsize=10, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([s[:4] for s in strat_set], rotation=20, fontsize=7)
        ax.grid(axis='y', alpha=0.3)
        if idx == 0:
            ax.legend(fontsize=7)
        ax.set_ylabel('提升 (mm)' if idx%4==0 else '')

    axes[-1].axis('off')
    fig.suptitle('Effect of Force Scaling on YLYW Dexterous Grasp Lift', fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig3_force_comparison.png'), bbox_inches='tight')
    plt.close()
    print(f'✅ 图3: force comparison saved')


# ─── 图4：成功/失败表格 ───
def plot_summary_table():
    """绘制结果汇总表格"""
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.axis('off')

    # 表头
    header = ['Object', 'Best Strategy', 'Best Lift', 'Success Rate', 'Force-Sensitive']
    cell_text = []
    for obj in OBJECTS:
        obj_results = [r for r in RESULTS if r[0]==obj]
        successes = [r for r in obj_results if r[5]==1]
        best = max(obj_results, key=lambda r: r[4])
        rate = f"{len(successes)}/{len(obj_results)} ({len(successes)/len(obj_results)*100:.0f}%)"
        
        # 检测是否力敏感（力0.6成功但1.0失败）
        force_sensitive = False
        strat_set = set(r[1] for r in obj_results)
        for s in strat_set:
            v06 = [r[4] for r in obj_results if r[1]==s and r[2]==0.6]
            v10 = [r[4] for r in obj_results if r[1]==s and r[2]==1.0]
            if v06 and v10 and v06[0] > 3 and v10[0] < -3:
                force_sensitive = True
                break
        
        cell_text.append([
            obj,
            best[1],
            f'{best[4]:+.1f}mm',
            rate,
            '是' if force_sensitive else 'No',
        ])

    table = ax.table(cellText=cell_text, colLabels=header,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.6)

    # 着色
    for i in range(len(OBJECTS)):
        for j in range(len(header)):
            cell = table[i+1, j]
            if j == 3:  # 成功率列
                success_frac = float(cell_text[i][3].split('/')[0])
                total = float(cell_text[i][3].split('/')[1].split()[0])
                ratio = success_frac / total if total > 0 else 0
                if ratio >= 0.75:
                    cell.set_facecolor('#90EE90')
                elif ratio >= 0.25:
                    cell.set_facecolor('#FFD700')
                else:
                    cell.set_facecolor('#FFB6C1')

    ax.set_title('Summary — YLYW Dexterous Hand Experiment', fontsize=13, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'fig4_summary.png'), bbox_inches='tight')
    plt.close()
    print(f'✅ 图4: summary table saved')


if __name__ == '__main__':
    print("=" * 50)
    print("YLYW 灵巧手仿真 — 论文可视化图")
    print("=" * 50)

    plot_heatmap()
    plot_best_strategies()
    plot_force_comparison()
    plot_summary_table()

    print(f"\n{'='*50}")
    print(f"✅ 所有图片生成完毕!")
    print(f"   输出目录: {OUTPUT_DIR}")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        sz = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"   {f:40s} {sz//1024} KB")
    print(f"{'='*50}")
