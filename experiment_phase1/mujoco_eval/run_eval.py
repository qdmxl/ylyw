#!/usr/bin/env python3
"""
YLYW 抓取策略物理评估 — 主实验脚本 (Phase 3)

流程:
  1. 加载 YLYW 推理引擎 + 物体预设
  2. 对每个物体运行 YLYW 推理
  3. 用物理解析评估器独立评分
  4. 输出论文级统计报告

评估是完全独立于 YLYW 的——评估器只知道：
  - 物体的质量、摩擦、几何、可承受力
  - YLYW 输出的抓取力、速度、抓取风格
  - 不接触、不依赖 YLYW 的卦象/爻位内部机制

用法:
  python3 run_eval.py --objects 18 --repeats 1        # 全量评估
  python3 run_eval.py --demo                           # 快速演示
  python3 run_eval.py --objects 40 --repeats 3 --json  # 完整实验+输出JSON
"""

import sys
import os
import json
import time
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# 路径设置
SCRIPT_DIR = Path(__file__).parent
PROJ_DIR = SCRIPT_DIR.parent         # mujoco_eval/
EXP_DIR = PROJ_DIR.parent            # experiment_phase1/
YLYW_ROOT = EXP_DIR.parent           # ylyw/

sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(YLYW_ROOT))

from mujoco_eval.physics_evaluator import (
    PhysicsEvaluator, BatchEvaluator,
    OBJECT_PARAMS, parse_ylyw_strategy
)

from ylyw_core.prior_manual import PriorManual
from scripts.object_presets import OBJECT_PRESETS, get_feature_dict
import scripts.object_presets_extended  # 加载追加的33个物体


# ─────────────────────────────────────────────────────────
# YLYW 推理适配器
# ─────────────────────────────────────────────────────────

class YLYWAdapter:
    """将 experiment_phase1 的 YLYW 引擎适配到评估器接口"""

    def __init__(self, verbose=False, force_scale=1.25):
        self.ylyw = PriorManual(verbose=verbose, force_scale=force_scale)

    def infer_from_preset(self, obj_key: str) -> dict:
        """从物体预设键名推理"""
        if obj_key not in OBJECT_PRESETS:
            raise KeyError(f"未知物体: {obj_key}")

        features = get_feature_dict(obj_key)
        t0 = time.perf_counter()
        perception, strategy = self.ylyw.process(features)
        t_ms = (time.perf_counter() - t0) * 1000

        return {
            'perception': perception,
            'strategy': strategy,
            'inference_ms': round(t_ms, 2),
        }


# ─────────────────────────────────────────────────────────
# 主实验
# ─────────────────────────────────────────────────────────

def run_experiment(objects: List[str], repeats: int = 1,
                   verbose: bool = True, output_json: str = None):
    """执行完整实验"""
    print(f"\n{'='*60}")
    print(f"  YLYW 抓取策略物理评估实验 (Phase 3)")
    print(f"{'='*60}")
    print(f"  物体数: {len(objects)}  |  重复: {repeats}次")
    print(f"  总试验: {len(objects) * repeats}")
    print(f"  评估方式: 物理解析（力闭合+提升+安全性）")
    print(f"{'='*60}\n")

    adapter = YLYWAdapter(verbose=False, force_scale=1.25)
    batch = BatchEvaluator()

    t0 = time.time()
    results = batch.run_batch(adapter, objects=objects, repeats=repeats)
    elapsed = time.time() - t0

    # 报告
    batch.print_report()
    stats = batch.compute_stats()

    print(f"  ⏱ 耗时: {elapsed:.1f}s  ({len(results)/elapsed:.1f} trials/s)\n")

    # 按 force 区间分析
    print(f"  Force 区间分析:")
    force_bins = {'low (<5N)': [], 'medium (5-15N)': [], 'high (>15N)': []}
    for r in results:
        f = r['grasp_force_N']
        if f < 5:
            force_bins['low (<5N)'].append(r)
        elif f < 15:
            force_bins['medium (5-15N)'].append(r)
        else:
            force_bins['high (>15N)'].append(r)

    for label, items in force_bins.items():
        if items:
            sr = sum(1 for r in items if r['grasp_success']) / len(items) * 100
            safe = sum(1 for r in items if r['is_safe']) / len(items) * 100
            print(f"    {label:18s}: n={len(items):2d}  success={sr:5.1f}%  safe={safe:5.1f}%")

    # JSON 输出
    if output_json:
        output = {
            'experiment': 'phase3_physics_eval',
            'timestamp': datetime.now().isoformat(),
            'num_objects': len(objects),
            'repeats': repeats,
            'total_trials': len(results),
            'elapsed_seconds': round(elapsed, 2),
            'stats': stats,
            'results': results,
        }
        out_path = Path(output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📁 结果保存: {out_path}")

    return results, stats


def demo():
    """快速演示"""
    demo_objects = ['tennis_ball', 'ceramic_vase', 'metal_cube',
                    'glass_vase', 'pingpong_ball', 'wooden_block',
                    'ceramic_bowl', 'smooth_stone']
    return run_experiment(demo_objects, repeats=1, verbose=True)


def full_experiment():
    """完整实验（所有物体）"""
    all_objects = list(OBJECT_PRESETS.keys())
    return run_experiment(all_objects, repeats=3,
                          output_json=f'output/eval_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='YLYW Phase 3: Physics-based Grasp Evaluation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 run_eval.py --demo                     # 快速演示
  python3 run_eval.py --objects 18 --repeats 1   # 全量评估
  python3 run_eval.py --objects 40 --repeats 3   # 大规模实验
  python3 run_eval.py --object tennis_ball       # 单物体分析
        """
    )
    parser.add_argument('--demo', action='store_true', help='快速演示')
    parser.add_argument('--full', action='store_true', help='完整实验')
    parser.add_argument('--objects', type=int, default=18, help='物体数量')
    parser.add_argument('--repeats', type=int, default=1, help='每物体重复')
    parser.add_argument('--object', type=str, help='单物体分析')
    parser.add_argument('--json', type=str, default=None, help='JSON输出路径')
    parser.add_argument('--quiet', action='store_true', help='安静模式')

    args = parser.parse_args()

    if args.demo:
        return demo()
    elif args.full:
        return full_experiment()
    elif args.object:
        result = run_experiment([args.object], repeats=1,
                                output_json=args.json)
        return result
    else:
        all_objects = list(OBJECT_PRESETS.keys())
        objects = all_objects[:min(args.objects, len(all_objects))]
        json_path = args.json or f'output/eval_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        return run_experiment(objects, repeats=args.repeats,
                              output_json=json_path, verbose=not args.quiet)


if __name__ == '__main__':
    main()
