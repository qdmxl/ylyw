#!/usr/bin/env python3
"""
实验结果可视化

生成:
  1. 热力图: 物体×本体 的成功率和提升高度
  2. 柱状图: 跨本体对比
  3. 知几学习曲线: 参数校准趋势
  4. 推理链示例: 卦象→策略的映射
"""

import os, sys, json, glob
import numpy as np
from typing import Dict, List
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("matplotlib not installed, using text-only output")

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'results')
FIGURES_DIR = os.path.join(RESULTS_DIR, 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)

OBJECTS = ['sphere', 'box', 'cylinder', 'long_rod', 'mushroom', 'dumbbell', 'disc']
OBJECT_LABELS = ['球体', '方块', '圆柱', '长杆', '蘑菇', '哑铃', '圆盘']

BODY_LABELS = {
    'shadow_hand_3axis': '灵巧手+3轴臂',
    'force_gripper_3axis': '力控夹爪+3轴臂',
}


def load_results(results_dir: str = RESULTS_DIR) -> Dict:
    """加载所有结果文件"""
    all_data = {}
    for f in glob.glob(os.path.join(results_dir, 'results_*.json')):
        with open(f) as fh:
            data = json.load(fh)
        body = data.get('body_type', os.path.basename(f))
        all_data[body] = data
    return all_data


def print_text_report(all_data: Dict):
    """纯文本报告（无 matplotlib 时使用）"""
    print("\n" + "=" * 80)
    print("            跨本体泛化实验结果报告")
    print("=" * 80)

    for body_type, data in sorted(all_data.items()):
        label = BODY_LABELS.get(body_type, body_type)
        print(f"\n{label} ({body_type})")
        print(f"  知几学习: {'启用' if data.get('use_zhiji', True) else '禁用'}")
        print(f"  {'物体':12s} {'居中成功率':12s} {'居中提升':10s} "
              f"{'偏移成功率':12s} {'偏移提升':10s} {'平均步数':8s}")

        for obj in OBJECTS:
            c_key = f"{obj}_(0mm, 0mm)"
            o_key = f"{obj}_(20mm, 20mm)"
            r = data.get('results', {})
            c_sr = r.get(c_key, {}).get('sr', 0)
            c_lift = r.get(c_key, {}).get('avg_lift', 0)
            o_sr = r.get(o_key, {}).get('sr', 0)
            o_lift = r.get(o_key, {}).get('avg_lift', 0)
            steps = int(np.mean([
                r.get(c_key, {}).get('avg_steps', 0),
                r.get(o_key, {}).get('avg_steps', 0),
            ]))
            print(f"  {obj:12s} {c_sr:6.0f}%      {c_lift:+6.1f}mm   "
                  f"{o_sr:6.0f}%      {o_lift:+6.1f}mm   {steps:4d}")

        # 汇总
        srs = [v.get('sr', 0) for v in data.get('results', {}).values()]
        lifts = [v.get('avg_lift', 0) for v in data.get('results', {}).values()]
        print(f"  {'─'*70}")
        print(f"  平均成功率: {np.mean(srs):.0f}%  "
              f"平均提升: {np.mean(lifts):+.1f}mm")


def plot_heatmaps(all_data: Dict, save: bool = True):
    """绘制热力图"""
    if not HAS_MPL:
        return

    n_bodies = len(all_data)
    fig, axes = plt.subplots(2, n_bodies, figsize=(5*n_bodies, 8))

    if n_bodies == 1:
        axes = axes.reshape(2, 1)

    for i, (body_type, data) in enumerate(sorted(all_data.items())):
        label = BODY_LABELS.get(body_type, body_type)
        r = data.get('results', {})

        # 成功率热力图 (居中)
        sr_matrix = np.zeros((len(OBJECTS), 2))  # col0=居中, col1=偏移
        lift_matrix = np.zeros((len(OBJECTS), 2))

        for j, obj in enumerate(OBJECTS):
            c_key = f"{obj}_(0mm, 0mm)"
            o_key = f"{obj}_(20mm, 20mm)"
            sr_matrix[j, 0] = r.get(c_key, {}).get('sr', 0) / 100
            sr_matrix[j, 1] = r.get(o_key, {}).get('sr', 0) / 100
            lift_matrix[j, 0] = r.get(c_key, {}).get('avg_lift', 0)
            lift_matrix[j, 1] = r.get(o_key, {}).get('avg_lift', 0)

        # 成功率
        ax = axes[0, i]
        im = ax.imshow(sr_matrix, cmap='RdYlGn', vmin=0, vmax=1, aspect='auto')
        ax.set_xticks(range(2))
        ax.set_xticklabels(['居中', '偏移20mm'])
        ax.set_yticks(range(len(OBJECTS)))
        ax.set_yticklabels(OBJECT_LABELS)
        ax.set_title(f'{label}\n成功率', fontsize=11)

        for j in range(len(OBJECTS)):
            for k in range(2):
                val = sr_matrix[j, k]
                color = 'white' if val < 0.4 else 'black'
                ax.text(k, j, f'{val*100:.0f}%', ha='center', va='center',
                       color=color, fontsize=9, fontweight='bold')

        # 提升高度
        ax2 = axes[1, i]
        vmin_lift = min(0, np.min(lift_matrix))
        vmax_lift = max(20, np.max(lift_matrix))
        im2 = ax2.imshow(lift_matrix, cmap='RdYlGn', vmin=vmin_lift, vmax=vmax_lift,
                         aspect='auto')
        ax2.set_xticks(range(2))
        ax2.set_xticklabels(['居中', '偏移20mm'])
        ax2.set_yticks(range(len(OBJECTS)))
        ax2.set_yticklabels(OBJECT_LABELS)
        ax2.set_title(f'{label}\n提升高度 (mm)', fontsize=11)

        for j in range(len(OBJECTS)):
            for k in range(2):
                val = lift_matrix[j, k]
                color = 'white' if val < 5 else 'black'
                ax2.text(k, j, f'{val:+.0f}', ha='center', va='center',
                        color=color, fontsize=9, fontweight='bold')

    plt.suptitle('跨本体泛化实验结果', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    if save:
        path = os.path.join(FIGURES_DIR, 'cross_embodiment_heatmap.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        print(f"热力图保存至: {path}")
    plt.close()


def plot_comparison_bars(all_data: Dict, save: bool = True):
    """跨本体对比柱状图"""
    if not HAS_MPL or len(all_data) < 2:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 成功率对比
    ax = axes[0]
    x = np.arange(len(OBJECTS))
    width = 0.35
    colors = plt.cm.Set2(np.linspace(0, 1, len(all_data)))

    for i, (body_type, data) in enumerate(sorted(all_data.items())):
        label = BODY_LABELS.get(body_type, body_type)
        r = data.get('results', {})
        srs = [np.mean([r.get(f"{obj}_(0mm, 0mm)", {}).get('sr', 0),
                        r.get(f"{obj}_(20mm, 20mm)", {}).get('sr', 0)]) / 100
               for obj in OBJECTS]
        bars = ax.bar(x + i*width, srs, width, label=label, color=colors[i], alpha=0.8)
        for bar, val in zip(bars, srs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                   f'{val*100:.0f}%', ha='center', va='bottom', fontsize=8)

    ax.set_xticks(x + width * (len(all_data)-1) / 2)
    ax.set_xticklabels(OBJECT_LABELS, fontsize=10)
    ax.set_ylabel('成功率', fontsize=11)
    ax.set_title('跨本体成功率对比', fontsize=12)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.axhline(y=0.8, color='gray', linestyle='--', alpha=0.5, label='80%基准')

    # 提升高度对比
    ax2 = axes[1]
    for i, (body_type, data) in enumerate(sorted(all_data.items())):
        label = BODY_LABELS.get(body_type, body_type)
        r = data.get('results', {})
        lifts = [np.mean([r.get(f"{obj}_(0mm, 0mm)", {}).get('avg_lift', 0),
                          r.get(f"{obj}_(20mm, 20mm)", {}).get('avg_lift', 0)])
                 for obj in OBJECTS]
        bars = ax2.bar(x + i*width, lifts, width, label=label, color=colors[i], alpha=0.8)
        for bar, val in zip(bars, lifts):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{val:+.0f}', ha='center', va='bottom', fontsize=8)

    ax2.set_xticks(x + width * (len(all_data)-1) / 2)
    ax2.set_xticklabels(OBJECT_LABELS, fontsize=10)
    ax2.set_ylabel('提升高度 (mm)', fontsize=11)
    ax2.set_title('跨本体提升高度对比', fontsize=12)
    ax2.legend(fontsize=10)
    ax2.axhline(y=3, color='gray', linestyle='--', alpha=0.5, label='成功阈值')

    plt.suptitle('YLYW 跨本体泛化 — 灵巧手 vs 力控夹爪', fontsize=14, fontweight='bold')
    plt.tight_layout()
    if save:
        path = os.path.join(FIGURES_DIR, 'cross_embodiment_comparison.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        print(f"对比图保存至: {path}")
    plt.close()


def main():
    all_data = load_results()

    if not all_data:
        print("未找到实验结果，请先运行 experiments/run_batch.py")
        return

    print(f"找到 {len(all_data)} 个结果文件:")
    for k in all_data:
        print(f"  - {k}")

    print_text_report(all_data)

    if HAS_MPL:
        plot_heatmaps(all_data)
        plot_comparison_bars(all_data)
        print(f"\n图片已保存至: {FIGURES_DIR}/")
    else:
        print("\n提示: 安装 matplotlib 可生成图表: pip install matplotlib")


if __name__ == '__main__':
    main()
