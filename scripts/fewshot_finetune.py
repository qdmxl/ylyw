#!/usr/bin/env python3
"""
YLYW 小样本微调 v4 — 爻权重学习 (Yao Weight Learning)

核心方法:
    先验手册的六爻编码器使用硬编码权重将特征聚合为爻值。
    本模块通过少量演示样本学习最优的爻聚合权重。

    每个爻的计算公式为:
        yao_i = Σ w_ij * feature_j     (加权求和)
        
    初始权重 w_ij 来自原硬编码公式。
    微调后权重保留了可解释性——可以分析哪些特征对每个爻最重要。

运行:
    cd /home/lijinhan/MXL/科研
    python3 ylyw/scripts/fewshot_finetune.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import time
import math
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize

from ylyw.simulation import SimulationScene, OBJECT_TEMPLATES
from ylyw.prior_manual import PriorManual


# ========================
#  配置
# ========================

EXPECTED_MAPPING = {
    'sphere':   'dynamic_grasp',
    'cube':     'power_grasp',
    'cylinder': 'dynamic_grasp',
    'bowl':     'precision_grasp',
    'bottle':   'cautious_grasp',
    'plate':    'balanced_grasp',
    'rock':     'compliant_grasp',
    'vase':     'cautious_grasp',
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

FEATURE_KEYS = [
    'stability', 'roll_tendency', 'strength_needed', 'fragility',
    'reachability', 'grasp_surface_quality', 'support_area',
    'occlusion', 'obstacle_density', 'task_priority',
    'weight_ratio', 'visibility', 'deformability',
]

YAO_NAMES = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth']


# ========================
#  可学习的爻编码器
# ========================

class LearnableYaoEncoder:
    """
    爻编码器，其聚合权重可学习。

    初始权重来自原 hard-coded 公式。
    每个爻 yao_i = Σ_j w_ij * feature_j

    权重被归一化以确保: Σ_j |w_ij| = 1
    """

    def __init__(self):
        n_features = len(FEATURE_KEYS)
        n_yao = 6

        # 初始化权重: 从原硬编码公式中提取
        self.W = np.zeros((n_yao, n_features))

        # 初爻 (FIRST): stability + roll_tendency + support_area
        self.W[0, FEATURE_KEYS.index('stability')] = 0.4
        self.W[0, FEATURE_KEYS.index('roll_tendency')] = -0.3  # 1 - roll
        self.W[0, FEATURE_KEYS.index('support_area')] = 0.3

        # 二爻 (SECOND): reachability + occlusion + grasp
        self.W[1, FEATURE_KEYS.index('reachability')] = 0.5
        self.W[1, FEATURE_KEYS.index('occlusion')] = -0.3
        self.W[1, FEATURE_KEYS.index('grasp_surface_quality')] = 0.2

        # 三爻 (THIRD): strength_needed + weight_ratio
        self.W[2, FEATURE_KEYS.index('strength_needed')] = 0.6
        self.W[2, FEATURE_KEYS.index('weight_ratio')] = 0.4

        # 四爻 (FOURTH): fragility (反编码: 1-fragility)
        self.W[3, FEATURE_KEYS.index('fragility')] = -1.0

        # 五爻 (FIFTH): task_priority
        self.W[4, FEATURE_KEYS.index('task_priority')] = 1.0

        # 上爻 (SIXTH): obstacle_density (反编码)
        self.W[5, FEATURE_KEYS.index('obstacle_density')] = -1.0

        # 保存原始权重
        self.W_original = self.W.copy()

        # 每个爻的偏置（原公式中有隐含的常量）
        self.b = np.array([0.3, 0.0, 0.0, 1.0, 0.0, 1.0])

    def encode(self, features_dict: Dict[str, float]) -> np.ndarray:
        """编码为六爻向量"""
        x = np.array([features_dict.get(k, 0.5) for k in FEATURE_KEYS])
        raw = np.dot(self.W, x) + self.b
        # 裁剪到 [0, 1]
        return np.clip(raw, 0.0, 1.0)

    def set_params(self, flat_params: np.ndarray):
        """设置权重和偏置"""
        n_f = len(FEATURE_KEYS)
        self.W = flat_params[:6 * n_f].reshape(6, n_f)
        self.b = flat_params[6 * n_f:]

    def get_params(self) -> np.ndarray:
        """获取平坦参数"""
        return np.concatenate([self.W.flatten(), self.b])

    def get_n_params(self) -> int:
        return 6 * len(FEATURE_KEYS) + 6  # 78 + 6 = 84


# ========================
#  训练与评估
# ========================

class ManualWithLearnableYao(PriorManual):
    """使用可学习爻编码器的先验手册"""

    def __init__(self, yao_encoder: LearnableYaoEncoder, verbose=False):
        super().__init__(verbose=verbose)
        self._yao_encoder = yao_encoder

    def perceive_and_encode(self, features_dict):
        """重写: 使用可学习的爻编码器"""
        # 卦象隶属度
        memberships = self.trigram_base.get_all_memberships(features_dict)
        dominant_idx = np.argmax(memberships)
        dominant_trigram = list(self.trigram_base.trigram_prototypes.keys())[dominant_idx]
        trigram_info = self.trigram_base.get_trigram_info(dominant_trigram)

        # 使用可学习的爻编码器
        yao_vector = self._yao_encoder.encode(features_dict)

        # 匹配卦象
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

    def get_grasp_strategy(self, perception: Dict) -> Dict:
        """使用父类的策略获取逻辑"""
        return super().get_grasp_strategy(perception)

    def process(self, features_dict):
        """完整推理流程"""
        perception = self.perceive_and_encode(features_dict)
        strategy = self.get_grasp_strategy(perception)
        return perception, strategy


def predict_strategy(features_dict: Dict, manual: ManualWithLearnableYao) -> str:
    """预测抓取策略"""
    _, strategy = manual.process(features_dict)
    return strategy['type']


def compute_loss(params: np.ndarray, encoder: LearnableYaoEncoder,
                 demos: List[Dict]) -> float:
    """
    损失函数: 用演示样本评估预测策略的合理性

    loss = Σ (如果预测不reasonable: 1, 如果合理但不精确: 0.3, 如果精确: 0)
         + λ * ||W - W_original||²  (L2正则)
    """
    encoder.set_params(params)
    manual = ManualWithLearnableYao(encoder, verbose=False)

    loss = 0.0

    for demo in demos:
        pred = predict_strategy(demo['features'], manual)
        expected = demo['expected_strategy']
        obj_type = demo['object_type']

        if pred == expected:
            loss += 0.0  # 精确匹配: 无惩罚
        elif pred in REASONABLE_STRATEGIES.get(obj_type, set()):
            loss += 0.3  # 合理: 小惩罚
        else:
            loss += 1.0  # 不合理: 大惩罚

    # L2正则: 偏向保持接近原始权重
    reg = 0.05 * np.sum((encoder.W - encoder.W_original) ** 2)
    reg += 0.05 * np.sum((encoder.b - np.array([0.3, 0.0, 0.0, 1.0, 0.0, 1.0])) ** 2)

    return loss + reg


def train_yao_weights(demos: List[Dict], encoder: LearnableYaoEncoder,
                      n_restarts: int = 10, max_iter: int = 100):
    """
    训练爻聚合权重

    多起点 + L-BFGS-B 局部优化
    """
    n_params = encoder.get_n_params()

    best_loss = float('inf')
    best_params = encoder.get_params()

    print(f"  训练中... ({n_restarts} restarts)")

    for restart in range(n_restarts):
        # 在原始权重附近随机初始化
        init_params = encoder.get_params().copy()
        init_params += np.random.normal(0, 0.15, n_params)

        result = minimize(
            compute_loss,
            init_params,
            args=(encoder, demos),
            method='L-BFGS-B',
            options={'maxiter': max_iter, 'maxfun': max_iter * 5},
            bounds=[(-3.0, 3.0)] * n_params,
        )

        if result.fun < best_loss:
            best_loss = result.fun
            best_params = result.x

        print(f"    restart {restart}: loss={result.fun:.3f}  ({result.nit} iters)")
        sys.stdout.flush()

    encoder.set_params(best_params)
    print(f"  最佳 loss: {best_loss:.3f}")

    # 打印显著的权重变化
    print("\n  [爻权重变化 (|Δ| > 0.1)]")
    for i, name in enumerate(YAO_NAMES):
        changes = []
        for j, feat in enumerate(FEATURE_KEYS):
            delta = encoder.W[i, j] - encoder.W_original[i, j]
            if abs(delta) > 0.1:
                changes.append(f"{feat}: {encoder.W_original[i,j]:.2f}→{encoder.W[i,j]:.2f}")
        if changes:
            print(f"    {name}爻: {'; '.join(changes)}")

    return encoder


# ========================
#  评估
# ========================

def evaluate(encoder: LearnableYaoEncoder, n_objects: int = 200,
             seed: int = 42) -> Dict:
    """评估系统表现"""
    manual = ManualWithLearnableYao(encoder, verbose=False)
    scene = SimulationScene(seed=seed)

    type_stats = defaultdict(lambda: {'total': 0, 'reasonable': 0})
    correct = 0
    total = 0
    all_preds = []

    for _ in range((n_objects + 7) // 8):
        n_batch = min(8, n_objects - total)
        if n_batch <= 0:
            break

        for obj in scene.generate_scene(n_objects=n_batch):
            pred = predict_strategy(obj.features.to_dict(), manual)
            expected = EXPECTED_MAPPING.get(obj.object_type, '')
            is_reasonable = pred in REASONABLE_STRATEGIES.get(obj.object_type, set())

            type_stats[obj.object_type]['total'] += 1
            if is_reasonable:
                type_stats[obj.object_type]['reasonable'] += 1
            if pred == expected:
                correct += 1
            total += 1
            all_preds.append(pred)

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


# ========================
#  主实验
# ========================

def run_experiment(n_demos_per_type: int = 3, n_eval: int = 200):
    """完整实验"""

    print("=" * 70)
    print(f"  YLYW 小样本微调实验 v4 — 爻权重学习")
    print(f"  {n_demos_per_type} × 8 = {n_demos_per_type * 8} 演示，{n_eval} 评估")
    print("=" * 70)

    encoder = LearnableYaoEncoder()
    manual = ManualWithLearnableYao(encoder, verbose=False)

    # ---- 1. 零样本基线 ----
    print(f"\n[1/5] 零样本基线 (N={n_eval})...")
    baseline = evaluate(encoder, n_objects=n_eval, seed=42)
    print(f"  合理率: {baseline['reasonable_rate']:.1%}  "
          f"精确率: {baseline['exact_rate']:.1%}")

    # ---- 2. 生成演示 ----
    print(f"\n[2/5] 生成 {n_demos_per_type * 8} 个演示...")
    scene = SimulationScene(seed=100)
    demos = []
    for obj_type in EXPECTED_MAPPING:
        for _ in range(n_demos_per_type):
            obj = scene.generate_object(obj_type, is_target=True)
            demos.append({
                'features': obj.features.to_dict(),
                'object_type': obj_type,
                'expected_strategy': EXPECTED_MAPPING[obj_type],
            })
    print(f"  {len(demos)} 个演示就绪")

    # ---- 3. 训练 ----
    print(f"\n[3/5] 训练爻聚合权重...")
    encoder = train_yao_weights(demos, encoder, n_restarts=10, max_iter=100)

    # ---- 4. 评估 ----
    print(f"\n[4/5] 微调后评估 (N={n_eval})...")
    after = evaluate(encoder, n_objects=n_eval, seed=42)

    # ---- 5. 交叉验证 ----
    print(f"\n[5/5] 交叉验证 (3 seeds × 100)...")
    cv_rates = []
    for cv_seed in [7, 77, 777]:
        cv = evaluate(encoder, n_objects=100, seed=cv_seed)
        cv_rates.append(cv['reasonable_rate'])
    cv_mean = np.mean(cv_rates)
    cv_std = np.std(cv_rates)
    print(f"  CV: {cv_mean:.1%} ± {cv_std:.1%}")

    # ---- 结果 ----
    print(f"\n{'=' * 70}")
    print(f"  实验结果")
    print(f"{'=' * 70}")
    print(f"\n{'指标':<20s} {'零样本':>10s} {'微调后':>10s} {'提升':>10s}")
    print("-" * 54)
    delta_r = after['reasonable_rate'] - baseline['reasonable_rate']
    delta_e = after['exact_rate'] - baseline['exact_rate']
    print(f"{'合理率':<20s} {baseline['reasonable_rate']:>9.1%} "
          f"{after['reasonable_rate']:>9.1%} {delta_r:>+9.1%}")
    print(f"{'精确率':<20s} {baseline['exact_rate']:>9.1%} "
          f"{after['exact_rate']:>9.1%} {delta_e:>+9.1%}")
    print(f"{'CV 平均':<20s} {'—':>10s} {cv_mean:>9.1%} "
          f"{'±' + f'{cv_std:.1%}':>10s}")

    print(f"\n{'类型':<12s} {'零样本':>8s} {'微调后':>8s} {'提升':>8s} {'状态':>6s}")
    print("-" * 48)
    for obj_type in EXPECTED_MAPPING:
        br = baseline['by_type'].get(obj_type, {}).get('rate', 0)
        ar = after['by_type'].get(obj_type, {}).get('rate', 0)
        d = ar - br
        status = '✅' if ar >= 0.6 else '⚠️' if ar >= 0.3 else '❌'
        print(f"{obj_type:<12s} {br:>7.1%} {ar:>7.1%} {d:>+7.1%} {status:>6s}")

    avg_d = np.mean([
        after['by_type'].get(t, {}).get('rate', 0) -
        baseline['by_type'].get(t, {}).get('rate', 0)
        for t in EXPECTED_MAPPING
    ])
    print(f"\n  平均提升: {avg_d:+.1%}")

    # ---- 保存 ----
    output_path = os.path.join(os.path.dirname(__file__),
                               'fewshot_v4_report.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'version': 'v4_yao_weights',
                'n_demos': len(demos),
                'n_eval': n_eval,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            },
            'baseline': baseline,
            'after': after,
            'cv': {'mean': float(cv_mean), 'std': float(cv_std)},
            'improvement': {
                'reasonable_delta': float(delta_r),
                'exact_delta': float(delta_e),
                'avg_per_type_delta': float(avg_d),
            },
            'learned_weights': {
                'W': [[float(v) for v in row] for row in encoder.W],
                'b': [float(v) for v in encoder.b],
            },
        }, f, indent=2, ensure_ascii=False)

    print(f"\n  📄 报告: {output_path}")
    print(f"{'=' * 70}")
    print("  ✅ 完成！")

    return baseline, after


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--demos', type=int, default=3)
    parser.add_argument('--eval', type=int, default=200)
    args = parser.parse_args()
    run_experiment(n_demos_per_type=args.demos, n_eval=args.eval)
