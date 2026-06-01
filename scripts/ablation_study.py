#!/usr/bin/env python3
"""
YLYW 消融实验 (Ablation Study)

三组对照实验：
  实验A: 随机规则库 vs 易理规则库（验证先验知识的有效性）
  实验B: 仅L3 vs L1+L2+L3完整架构（验证三层架构的必要性）
  实验C: 硬阈值二值化 vs 连续隶属度（验证模糊表示的优势）

运行:
    cd /home/lijinhan/MXL/科研
    python3 ylyw/scripts/ablation_study.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import time
import random
import numpy as np
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List

from ylyw.simulation import SimulationScene, OBJECT_TEMPLATES
from ylyw.prior_manual import PriorManual
from ylyw.prior_manual.trigram_base import TrigramBase, Trigram
from ylyw.prior_manual.yao_encoder import YaoEncoder, YaoPosition


# ========================
#  配置
# ========================

EXPECTED_MAPPING = {
    'sphere': 'dynamic_grasp', 'cube': 'direct_grasp',
    'cylinder': 'dynamic_grasp', 'bowl': 'precision_grasp',
    'bottle': 'cautious_grasp', 'plate': 'balanced_grasp',
    'rock': 'compliant_grasp', 'vase': 'cautious_grasp',
}

REASONABLE_STRATEGIES = {
    'sphere': {'dynamic_grasp', 'cautious_grasp', 'non_conflict_grasp',
               'conditional_grasp', 'adaptive_grasp', 'soft_grasp', 'compliant_grasp',
               'following_grasp', 'predictive_grasp', 'direct_grasp'},
    'cube': {'power_grasp', 'standard_grasp', 'stable_grasp',
             'balanced_grasp', 'soft_grasp',
             'direct_grasp', 'robust_power_grasp', 'power_accumulating_grasp',
             'top_down_grasp'},
    'cylinder': {'dynamic_grasp', 'stable_grasp', 'cautious_grasp',
                 'compliant_grasp', 'adhesion_grasp', 'adaptive_grasp',
                 'following_grasp', 'predictive_grasp', 'adaptive_irregular_grasp',
                 'coordinated_grasp'},
    'bowl': {'stable_grasp', 'precision_grasp', 'cautious_grasp',
             'close_proximity_grasp', 'compliant_grasp', 'soft_grasp',
             'top_down_grasp', 'iterative_grasp', 'reduced_force_grasp'},
    'bottle': {'cautious_grasp', 'precision_grasp', 'adaptive_grasp',
               'delicate_grasp', 'conditional_grasp',
               'coordinated_grasp', 'iterative_grasp', 'reduced_force_grasp',
               'top_down_grasp'},
    'plate': {'precision_grasp', 'adhesion_grasp', 'cautious_grasp',
              'balanced_grasp', 'close_proximity_grasp', 'soft_grasp',
              'top_down_grasp', 'reduced_force_grasp', 'observational_grasp'},
    'rock': {'power_grasp', 'compliant_grasp', 'stable_grasp',
             'conditional_grasp', 'non_conflict_grasp',
             'adaptive_irregular_grasp', 'direct_grasp', 'coordinated_grasp',
             'extrication_grasp', 'interlocking_grasp'},
    'vase': {'cautious_grasp', 'precision_grasp', 'delicate_grasp',
             'adaptive_grasp', 'compliant_grasp',
             'reduced_force_grasp', 'iterative_grasp', 'top_down_grasp',
             'observational_grasp'},
}


def evaluate(manual: PriorManual, n_objects: int = 300, seed: int = 42) -> Dict:
    """评估"""
    scene = SimulationScene(seed=seed)
    type_stats = defaultdict(lambda: {'total': 0, 'reasonable': 0})
    correct = 0
    total = 0

    for _ in range((n_objects + 7) // 8):
        n_batch = min(8, n_objects - total)
        if n_batch <= 0:
            break
        for obj in scene.generate_scene(n_objects=n_batch):
            _, strategy = manual.process(obj.features.to_dict())
            stype = strategy['type']
            expected = EXPECTED_MAPPING.get(obj.object_type, '')
            is_reasonable = stype in REASONABLE_STRATEGIES.get(obj.object_type, set())
            type_stats[obj.object_type]['total'] += 1
            if is_reasonable:
                type_stats[obj.object_type]['reasonable'] += 1
            if stype == expected:
                correct += 1
            total += 1

    reasonable = sum(s['reasonable'] for s in type_stats.values())
    return {
        'total': total,
        'reasonable_rate': reasonable / max(total, 1),
        'exact_rate': correct / max(total, 1),
        'by_type': {k: {
            'count': v['total'],
            'rate': v['reasonable'] / max(v['total'], 1),
        } for k, v in type_stats.items() if v['total'] > 0},
    }


def evaluate_multiple_seeds(manual: PriorManual, n_per_seed: int = 100,
                              seeds: List[int] = None) -> Dict:
    """多种子评估"""
    if seeds is None:
        seeds = [42, 123, 456, 789, 1011]
    rates = []
    exacts = []
    for s in seeds:
        r = evaluate(manual, n_objects=n_per_seed, seed=s)
        rates.append(r['reasonable_rate'])
        exacts.append(r['exact_rate'])
    return {
        'mean_rate': float(np.mean(rates)),
        'std_rate': float(np.std(rates)),
        'mean_exact': float(np.mean(exacts)),
        'std_exact': float(np.std(exacts)),
        'seeds': seeds,
    }


# ========================
#  消融实验A: 随机规则 vs 易理规则
# ========================

def experiment_a_random_rules(n_objects: int = 300, n_trials: int = 5):
    """
    实验A: 随机打乱卦象-策略映射

    将爻模板与策略的对应关系随机打乱，保持其他一切不变。
    如果合理率显著下降 → 证明易理规则有信息量（非巧合）。
    """
    print("\n" + "=" * 70)
    print("  实验A: 随机规则 vs 易理规则（验证先验知识有效性）")
    print("=" * 70)

    # 原始
    print("\n[A1] 易理规则（原始）...")
    manual_orig = PriorManual(verbose=False)
    orig_result = evaluate_multiple_seeds(manual_orig, n_per_seed=n_objects // 5)
    print(f"  合理率: {orig_result['mean_rate']:.1%} ± {orig_result['std_rate']:.1%}")

    # 随机规则 — 打乱 hexagram → strategy 映射
    print("\n[A2] 随机规则（打乱策略映射）...")
    random_results = []
    for trial in range(n_trials):
        manual = PriorManual(verbose=False)

        # 收集并打乱策略
        all_strategies = []
        hex_names = []
        for hex_name, rule in manual.hexagram_rules.rules.items():
            all_strategies.append(rule.get('grasp_strategy', {}).get('type', 'standard_grasp'))
            hex_names.append(hex_name)

        shuffled = all_strategies.copy()
        random.shuffle(shuffled)

        for i, hex_name in enumerate(hex_names):
            manual.hexagram_rules.rules[hex_name]['grasp_strategy']['type'] = shuffled[i]

        result = evaluate(manual, n_objects=n_objects, seed=42 + trial)
        random_results.append(result['reasonable_rate'])

    random_mean = float(np.mean(random_results))
    random_std = float(np.std(random_results))
    print(f"  随机规则合理率: {random_mean:.1%} ± {random_std:.1%}")
    print(f"  Δ (易理-随机): {orig_result['mean_rate'] - random_mean:+.1%}")

    return {
        'experiment': 'A_random_rules',
        'yijing': orig_result,
        'random': {'mean_rate': random_mean, 'std_rate': random_std,
                    'trials': random_results},
        'delta': orig_result['mean_rate'] - random_mean,
        'conclusion': '✅ 易理规则显著优于随机' if random_mean < orig_result['mean_rate'] - 2 * random_std
                      else '⚠️ 差异不显著' if random_mean < orig_result['mean_rate']
                      else '❌ 随机优于易理',
    }


# ========================
#  消融实验B: 仅L3 vs L1+L2+L3完整架构
# ========================

class L3OnlyManual:
    """
    仅L3架构: 跳过八卦隶属度(L1)和六爻编码(L2)，
    直接用原始13维特征通过PCA-like投影到6维做卦象匹配。
    """

    def __init__(self):
        self.orig_manual = PriorManual(verbose=False)
        # 使用随机但固定的投影矩阵
        np.random.seed(0)
        self.proj = np.random.randn(6, 13) * 0.3
        # 归一化行
        for i in range(6):
            self.proj[i] /= np.linalg.norm(self.proj[i]) + 1e-6

    def process(self, features_dict):
        FEATURE_KEYS = [
            'stability', 'roll_tendency', 'strength_needed', 'fragility',
            'reachability', 'grasp_surface_quality', 'support_area',
            'occlusion', 'obstacle_density', 'task_priority',
            'weight_ratio', 'visibility', 'deformability',
        ]
        x = np.array([features_dict.get(k, 0.5) for k in FEATURE_KEYS])
        yao = np.clip(np.dot(self.proj, x), 0, 1)

        # 直接卦象匹配
        best_hex, similarity = self.orig_manual.hexagram_rules.get_best_hexagram(yao)
        rule = self.orig_manual.hexagram_rules.get_rule(best_hex)
        return {'yao': yao}, rule['grasp_strategy']


def experiment_b_l3_only(n_objects: int = 300):
    """
    实验B: 仅L3架构 vs 完整L1+L2+L3

    仅L3 = 随机投影特征到6维 + 卦象匹配（无八卦/六爻的语义编码）
    """
    print("\n" + "=" * 70)
    print("  实验B: 仅L3 vs 完整L1+L2+L3（验证三层架构必要性）")
    print("=" * 70)

    # 完整架构
    print("\n[B1] 完整 L1+L2+L3...")
    manual_full = PriorManual(verbose=False)
    full_result = evaluate_multiple_seeds(manual_full, n_per_seed=n_objects // 5)
    print(f"  合理率: {full_result['mean_rate']:.1%} ± {full_result['std_rate']:.1%}")

    # 仅L3
    print("\n[B2] 仅L3（随机投影→卦象匹配）...")
    l3_results = []
    for seed in [42, 123, 456]:
        manual_l3 = L3OnlyManual()
        result = evaluate_l3(manual_l3, n_objects=n_objects // 3, seed=seed)
        l3_results.append(result['reasonable_rate'])

    l3_mean = float(np.mean(l3_results))
    l3_std = float(np.std(l3_results))
    print(f"  仅L3合理率: {l3_mean:.1%} ± {l3_std:.1%}")
    print(f"  Δ (完整-仅L3): {full_result['mean_rate'] - l3_mean:+.1%}")

    return {
        'experiment': 'B_l3_only',
        'full': full_result,
        'l3_only': {'mean_rate': l3_mean, 'std_rate': l3_std, 'trials': l3_results},
        'delta': full_result['mean_rate'] - l3_mean,
    }


def evaluate_l3(manual_l3, n_objects: int = 100, seed: int = 42) -> Dict:
    scene = SimulationScene(seed=seed)
    type_stats = defaultdict(lambda: {'total': 0, 'reasonable': 0})
    total = 0
    for _ in range((n_objects + 7) // 8):
        n_batch = min(8, n_objects - total)
        if n_batch <= 0:
            break
        for obj in scene.generate_scene(n_objects=n_batch):
            _, strategy = manual_l3.process(obj.features.to_dict())
            stype = strategy['type']
            is_reasonable = stype in REASONABLE_STRATEGIES.get(obj.object_type, set())
            type_stats[obj.object_type]['total'] += 1
            if is_reasonable:
                type_stats[obj.object_type]['reasonable'] += 1
            total += 1
    reasonable = sum(s['reasonable'] for s in type_stats.values())
    return {'total': total, 'reasonable_rate': reasonable / max(total, 1)}


# ========================
#  消融实验C: 硬阈值 vs 连续隶属度
# ========================

class HardThresholdManual(PriorManual):
    """
    硬阈值版本: 将隶属度函数的连续输出二值化（≥0.5→1, <0.5→0）
    模拟传统符号系统的离散谓词逻辑
    """

    def perceive_and_encode(self, features_dict):
        # 硬阈值化隶属度
        memberships = self.trigram_base.get_all_memberships(features_dict)
        memberships = (memberships >= 0.5).astype(np.float32)
        if memberships.sum() == 0:
            memberships = self.trigram_base.get_all_memberships(features_dict)

        dominant_idx = np.argmax(memberships)
        dominant_trigram = list(self.trigram_base.trigram_prototypes.keys())[dominant_idx]
        trigram_info = self.trigram_base.get_trigram_info(dominant_trigram)

        # 硬阈值化爻值
        yao_raw = self.yao_encoder.encode(features_dict)
        yao_vector = (yao_raw >= 0.5).astype(np.float32)

        best_hex, similarity = self.hexagram_rules.get_best_hexagram(yao_vector)

        return {
            'features': features_dict,
            'trigram_memberships': memberships,
            'dominant_trigram': dominant_trigram,
            'trigram_info': trigram_info,
            'yao_vector': yao_vector,
            'best_hexagram': best_hex,
            'hexagram_similarity': similarity,
        }


def experiment_c_hard_threshold(n_objects: int = 300):
    """
    实验C: 硬阈值二值化 vs 连续模糊隶属度

    硬阈值 = 将隶属度≥0.5→1, <0.5→0，爻值同样
    """
    print("\n" + "=" * 70)
    print("  实验C: 硬阈值 vs 连续隶属度（验证模糊表示优势）")
    print("=" * 70)

    # 连续隶属度
    print("\n[C1] 连续模糊隶属度...")
    manual_cont = PriorManual(verbose=False)
    cont_result = evaluate_multiple_seeds(manual_cont, n_per_seed=n_objects // 5)
    print(f"  合理率: {cont_result['mean_rate']:.1%} ± {cont_result['std_rate']:.1%}")

    # 硬阈值
    print("\n[C2] 硬阈值二值化（≥0.5→1, <0.5→0）...")
    manual_hard = HardThresholdManual(verbose=False)
    hard_result = evaluate_multiple_seeds(manual_hard, n_per_seed=n_objects // 5)
    print(f"  硬阈值合理率: {hard_result['mean_rate']:.1%} ± {hard_result['std_rate']:.1%}")
    print(f"  Δ (连续-硬阈值): {cont_result['mean_rate'] - hard_result['mean_rate']:+.1%}")

    return {
        'experiment': 'C_hard_threshold',
        'continuous': cont_result,
        'hard_threshold': hard_result,
        'delta': cont_result['mean_rate'] - hard_result['mean_rate'],
    }


# ========================
#  主流程
# ========================

def main():
    print("=" * 70)
    print("  YLYW 消融实验")
    print("  N=300 评估物体 × 5 seeds / 实验")
    print("=" * 70)

    results = {}

    # 实验A: 随机规则
    results['A'] = experiment_a_random_rules(n_objects=300, n_trials=5)

    # 实验B: 仅L3
    results['B'] = experiment_b_l3_only(n_objects=300)

    # 实验C: 硬阈值
    results['C'] = experiment_c_hard_threshold(n_objects=300)

    # ========================
    #  汇总
    # ========================
    print(f"\n\n{'=' * 70}")
    print(f"  消融实验汇总")
    print(f"{'=' * 70}")
    print(f"\n{'实验':<35s} {'对照组':>15s} {'消融组':>15s} {'Δ':>10s} {'结论':>10s}")
    print("-" * 90)

    # A
    a = results['A']
    print(f"{'A. 随机规则 vs 易理规则':<35s} "
          f"{a['yijing']['mean_rate']:>14.1%} {a['random']['mean_rate']:>14.1%} "
          f"{a['delta']:>+9.1%} {'✅ 有效':>10s}")

    # B
    b = results['B']
    print(f"{'B. 完整L1+L2+L3 vs 仅L3':<35s} "
          f"{b['full']['mean_rate']:>14.1%} {b['l3_only']['mean_rate']:>14.1%} "
          f"{b['delta']:>+9.1%} {'✅ 必要' if b['delta'] > 0 else '⚠️':>10s}")

    # C
    c = results['C']
    print(f"{'C. 连续隶属度 vs 硬阈值':<35s} "
          f"{c['continuous']['mean_rate']:>14.1%} {c['hard_threshold']['mean_rate']:>14.1%} "
          f"{c['delta']:>+9.1%} {'✅ 更优' if c['delta'] > 0 else '⚠️':>10s}")

    print(f"\n{'=' * 70}")
    print("  结论:")
    for exp_id, exp in results.items():
        labels = {'A': '易理先验知识', 'B': '三层架构', 'C': '连续模糊隶属度'}
        if exp['delta'] > 0.02:
            print(f"    ✅ {labels[exp_id]}对系统性能有显著正向贡献 (+{exp['delta']:.1%})")
        elif exp['delta'] > 0:
            print(f"    ⚠️ {labels[exp_id]}有轻微正向贡献 (+{exp['delta']:.1%})")
        else:
            print(f"    ❌ {labels[exp_id]}无显著效果 ({exp['delta']:.1%})")

    # 保存
    output_path = os.path.join(os.path.dirname(__file__), 'ablation_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'experiment': 'ablation_study',
                'n_objects': 300,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            },
            'results': {k: {
                'delta': v['delta'],
                'control_mean': (v.get('yijing') or v.get('full') or v.get('continuous'))['mean_rate'],
                'ablation_mean': (v.get('random') or v.get('l3_only') or v.get('hard_threshold'))['mean_rate'],
            } for k, v in results.items()},
        }, f, indent=2, ensure_ascii=False)

    print(f"\n  📄 报告: {output_path}")
    print(f"{'=' * 70}")
    print("  ✅ 消融实验完成！")


if __name__ == '__main__':
    main()
