#!/usr/bin/env python3
"""
YLYW 自适应学习实验 (Adaptive Learning from Feedback)

从真正的零样本开始 (force_scale=1.0, 无任何调参)，
每轮根据物理评估失败案例自动调整 YLYW 参数，
记录成功率收敛曲线。

学习策略:
  - 全局调整: force_scale (所有卦的 force 统一缩放)
  - 逐类调整: 针对失败率高的物体类型，提高对应主导卦的 force

用法:
  python3 adaptive_learning.py --rounds 10
"""

import sys
import os
import json
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).parent
EXP_DIR = SCRIPT_DIR.parent  # mujoco_eval/ → experiment_phase1/
YLYW_ROOT = EXP_DIR.parent   # ylyw/
sys.path.insert(0, str(EXP_DIR))
sys.path.insert(0, str(YLYW_ROOT))

from ylyw_core.prior_manual import PriorManual
from scripts.object_presets import OBJECT_PRESETS
import scripts.object_presets_extended  # 50物体

from mujoco_eval.physics_evaluator import PhysicsEvaluator, OBJECT_PARAMS

# ─────────────────────────────────────────────────────────
# YLYW 适配器（可调整 force_scale）
# ─────────────────────────────────────────────────────────

class AdaptiveYLYW:
    """可动态调整参数的 YLYW"""

    def __init__(self, force_scale=1.0, per_category_scales=None):
        self.force_scale = force_scale
        self.per_category_scales = per_category_scales or {}
        self._rebuild()

    def _rebuild(self):
        self.ylyw = PriorManual(verbose=False, force_scale=self.force_scale)
        self.hex_rules = self.ylyw.hexagram_rules

    def set_force_scale(self, scale):
        self.force_scale = scale
        self._rebuild()

    def infer_from_preset(self, obj_key):
        if obj_key not in OBJECT_PRESETS:
            raise KeyError(f"未知物体: {obj_key}")
        features = OBJECT_PRESETS[obj_key]['features'].copy()
        t0 = time.perf_counter()
        perception, strategy = self.ylyw.process(features)
        t_ms = (time.perf_counter() - t0) * 1000
        return {
            'perception': perception,
            'strategy': strategy,
            'inference_ms': round(t_ms, 2),
        }

    def get_hexagram_preset(self, hexagram_enum):
        """获取某卦的 force 预设值"""
        from ylyw_core.hexagram_rules import Hexagram
        if isinstance(hexagram_enum, Hexagram):
            rule = self.hex_rules.get_rule(hexagram_enum)
            return rule['grasp_strategy']['force']
        return None

    def boost_hexagram_force(self, hexagram_enum, factor):
        """直接修改某卦的 force 值"""
        from ylyw_core.hexagram_rules import Hexagram
        if isinstance(hexagram_enum, Hexagram):
            rule = self.hex_rules.get_rule(hexagram_enum)
            old = rule['grasp_strategy']['force']
            new = round(min(0.98, old * factor), 2)
            rule['grasp_strategy']['force'] = new
            return old, new
        return None, None


# ─────────────────────────────────────────────────────────
# 自适应学习循环
# ─────────────────────────────────────────────────────────

class AdaptiveLearner:
    """
    自适应学习：
      每轮评估全部物体 → 分析失败案例 →
      调整 YLYW 参数 → 下一轮
    """

    def __init__(self, objects=None):
        self.objects = objects or sorted(OBJECT_PRESETS.keys())
        self.evaluator = PhysicsEvaluator()
        self.ylyw = AdaptiveYLYW(force_scale=1.0)
        self.history = []  # 每轮: {round, force_scale, success_rate, ...}

    def evaluate_round(self, repeats=3, quiet=False):
        """单轮评估"""
        results = []
        for obj_key in self.objects:
            for trial in range(repeats):
                ylyw_out = self.ylyw.infer_from_preset(obj_key)
                s = ylyw_out['strategy']
                eff = round(s['force'] * s.get('force_modifier', 1.0), 3)
                strategy_out = {
                    'type': s.get('type', 'generic'),
                    'effective_force': eff,
                    'force': s['force'],
                    'force_modifier': s.get('force_modifier', 1.0),
                    'speed': s.get('speed', 'medium'),
                    'approach_angle': s.get('approach_angle', 0),
                    'yao_quality': float(s.get('yao_quality', 0) or 0),
                }
                r = self.evaluator.evaluate(obj_key, strategy_out)
                r['obj_key'] = obj_key
                r['trial'] = trial
                r['force_effective'] = eff
                # 卦象信息
                p = ylyw_out['perception']
                hx = p.get('best_hexagram')
                r['hexagram'] = hx.name if hx else 'unknown'
                results.append(r)

        # 汇总
        total = len(results)
        successes = sum(1 for r in results if r['grasp_success'])
        safe = sum(1 for r in results if r['is_safe'])
        success_rate = successes / total if total else 0

        # 按类型
        by_type = {}
        for r in results:
            t = r['obj_category']
            if t not in by_type:
                by_type[t] = {'total': 0, 'success': 0, 'failures': []}
            by_type[t]['total'] += 1
            if r['grasp_success']:
                by_type[t]['success'] += 1
            else:
                by_type[t]['failures'].append(r)

        if not quiet:
            print(f"  success={success_rate:.1%} ({successes}/{total}) "
                  f"safe={safe/total:.1%} fs={self.ylyw.force_scale:.2f}")

        return {
            'total': total,
            'successes': successes,
            'success_rate': success_rate,
            'safe': safe,
            'safe_rate': safe / total,
            'by_type': by_type,
            'results': results,
        }

    def adjust(self, round_stats, round_num):
        """
        根据失败反馈调整参数

        策略:
          round 0-2:  调整全局 force_scale (粗调)
          round 3+:   调整失败率最高类型的对应卦 force (细调)
        """
        changes = []

        # ── 全局 scale 调整 ──
        sr = round_stats['success_rate']
        fs = self.ylyw.force_scale

        if round_num < 3:
            if sr < 0.3:
                fs += 0.30
            elif sr < 0.5:
                fs += 0.15
            elif sr < 0.65:
                fs += 0.08
            elif sr < 0.75:
                fs += 0.04
            elif sr < 0.85:
                fs += 0.02
            else:
                fs += 0.01  # 微调

            fs = min(fs, 2.0)
            if fs != self.ylyw.force_scale:
                self.ylyw.set_force_scale(fs)
                changes.append(f"force_scale → {fs:.2f}")

        # ── 逐类型调整 ──
        by_type = round_stats['by_type']
        # 找出失败率最高且样本数>=6的类型
        worst_types = sorted(
            [(t, info['success'] / info['total'])
             for t, info in by_type.items()
             if info['total'] >= 5],
            key=lambda x: x[1]
        )[:2]  # 最差的2个类型

        if round_num >= 1 and worst_types and worst_types[0][1] < 0.7:
            for cat, rate in worst_types:
                if rate < 0.7:
                    # 收集该类型物体的失败案例所对应的卦
                    hexes_for_cat = {}
                    for r in by_type[cat]['failures']:
                        hx = r.get('hexagram', 'unknown')
                        hexes_for_cat[hx] = hexes_for_cat.get(hx, 0) + 1

                    # 对失败最多的卦 boost force
                    top_hexes = sorted(hexes_for_cat.items(),
                                       key=lambda x: -x[1])[:2]
                    for hx_name, count in top_hexes:
                        from ylyw_core.hexagram_rules import Hexagram
                        try:
                            hx_enum = getattr(Hexagram, hx_name, None)
                        except:
                            hx_enum = None
                        if hx_enum:
                            old, new = self.ylyw.boost_hexagram_force(hx_enum, 1.08)
                            if old and new and new != old:
                                changes.append(
                                    f"↑ {hx_name} force {old:.2f}→{new:.2f} "
                                    f"(for {cat}, {count} failures)")

        return changes

    def run(self, rounds=10, repeats=3) -> List[dict]:
        """运行完整学习循环"""
        print(f"\n{'='*65}")
        print(f"  YLYW 自适应学习实验 (Adaptive from Zero-Shot)")
        print(f"{'='*65}")
        print(f"  物体: {len(self.objects)}  |  重复: {repeats}次/轮")
        print(f"  初始参数: force_scale=1.0 (纯零样本)")
        print(f"  学习方式: 失败反馈 → 自动调参 → 复测")
        print(f"{'='*65}\n")

        for rnd in range(rounds):
            print(f"  Round {rnd}:", end=" ")
            stats = self.evaluate_round(repeats=repeats, quiet=False)
            changes = self.adjust(stats, rnd)

            record = {
                'round': rnd,
                'force_scale': self.ylyw.force_scale,
                'success_rate': stats['success_rate'],
                'safe_rate': stats['safe_rate'],
                'successes': stats['successes'],
                'total': stats['total'],
                'changes': changes,
                'by_type_rates': {
                    t: info['success'] / info['total']
                    for t, info in stats['by_type'].items()
                }
            }
            self.history.append(record)

            if changes:
                print(f"         Δ: {' | '.join(changes)}")

            # 收敛判定
            if stats['success_rate'] >= 0.90:
                print(f"\n  ✓ 收敛于 round {rnd} ({stats['success_rate']:.1%})")
                break

        return self.history

    def print_curve(self):
        """打印学习曲线"""
        print(f"\n{'='*65}")
        print(f"  学习曲线")
        print(f"{'='*65}")
        print(f"  {'Round':6s} {'fs':5s} {'success':8s} {'safe':6s}")
        print(f"  {'-'*35}")
        for h in self.history:
            print(f"  {h['round']:<6d} {h['force_scale']:<5.2f} "
                  f"{h['success_rate']:.1%}      {h['safe_rate']:.1%}")

        print(f"\n  按类型最终成功率:")
        final = self.history[-1]['by_type_rates']
        for t, rate in sorted(final.items()):
            bar = '█' * int(rate * 10) + '░' * max(0, 10 - int(rate * 10))
            print(f"    {t:10s} [{bar}] {rate:.0%}")

        # 跟踪每个类型的变化
        if len(self.history) >= 2:
            print(f"\n  各轮按类型趋势:")
            header = f"    {'Round':>5s}"
            types = list(self.history[0]['by_type_rates'].keys())
            for t in types:
                header += f"  {t:>8s}"
            print(header)
            for h in self.history:
                line = f"    {h['round']:>5d}"
                for t in types:
                    line += f"  {h['by_type_rates'].get(t, 0):.0%}"
                print(line)

        print(f"{'='*65}\n")

    def save(self, path):
        """保存学习记录"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'num_objects': len(self.objects),
            'history': self.history,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📁 学习曲线已保存: {path}")


# ─────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='YLYW Adaptive Learning')
    parser.add_argument('--rounds', type=int, default=10, help='最大轮数')
    parser.add_argument('--repeats', type=int, default=3, help='每轮每物体重复')
    parser.add_argument('--objects', type=int, default=50, help='物体数量')
    parser.add_argument('--json', type=str, default=None, help='输出JSON')
    args = parser.parse_args()

    all_objects = list(OBJECT_PRESETS.keys())
    objects = all_objects[:min(args.objects, len(all_objects))]

    learner = AdaptiveLearner(objects=objects)
    history = learner.run(rounds=args.rounds, repeats=args.repeats)
    learner.print_curve()

    if args.json:
        learner.save(args.json)
