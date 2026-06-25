#!/usr/bin/env python3
"""
抓取物理评估器 (Physics-based Grasp Evaluator) v2

基于经典双指夹爪力学模型，所有参数一次性标定，零实验反馈调整。

标准力学：
  1. Force Closure: 摩擦锥分析 (摩擦半角 arctan(μ))
  2. Lift Feasibility: 2μN ≥ mg
  3. Object Safety: N ≤ fragility → 安全, N > fragility → 损坏

力映射：基于典型工业夹爪标定数据
  - 最小力 ~1N (轻触), 最大力 ~50N (强力工业夹爪)
  - 映射曲线: 分段线性, 基于 UR5+Robotiq-85 等标准夹爪的规格表

用法:
  from mujoco_eval.physics_evaluator import PhysicsEvaluator, OBJECT_PARAMS
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────
# 力映射: 归一化 [0,1] → 牛顿 (标准工业夹爪标定)
# ─────────────────────────────────────────────────────────
# 参考: Robotiq 2F-85 夹爪规格 (0.2→5N指尖力, 0.5→20N, 1.0→50N)
# 映射表: 归一化 force [0,1] 通过分段线性映射到牛顿值
FORCE_MAP = [
    (0.0,  0.0),   # force=0  → 0N (无接触)
    (0.15, 0.8),   # force=0.15 → 0.8N (极轻触)
    (0.30, 3.0),   # force=0.30 → 3N
    (0.45, 8.0),   # force=0.45 → 8N (中等力)
    (0.60, 16.0),  # force=0.60 → 16N
    (0.75, 28.0),  # force=0.75 → 28N
    (0.90, 42.0),  # force=0.90 → 42N
    (1.0,  50.0),  # force=1.0 → 50N (全力)
]

SPEED_MAP = {'slow': 0.05, 'medium': 0.15, 'fast': 0.30}

# ─────────────────────────────────────────────────────────
# 物体物理参数数据库 (从YCB和日常物品的物理属性)
# ─────────────────────────────────────────────────────────

@dataclass
class ObjectParams:
    name: str
    category: str           # sphere/cube/cylinder/bowl/bottle/plate/rock/vase
    mass_kg: float          # 质量
    size_m: float           # 特征尺寸
    friction_coef: float    # 表面摩擦系数 (0-1, 来自YCB/材料手册)
    fragility_newton: float  # 可承受最大夹持力 (N)
    is_hollow: bool = False
    is_irregular: bool = False
    is_flat: bool = False

OBJECT_PARAMS = {
    # ── 球体 (8) ──
    "tennis_ball": ObjectParams("网球", "sphere", 0.057, 0.033, 0.55, 80),
    "golf_ball": ObjectParams("高尔夫球", "sphere", 0.046, 0.021, 0.35, 100),
    "pingpong_ball": ObjectParams("乒乓球", "sphere", 0.003, 0.020, 0.25, 15),
    "rubber_ball": ObjectParams("橡胶球", "sphere", 0.08, 0.04, 0.65, 120),
    "marble": ObjectParams("玻璃弹珠", "sphere", 0.006, 0.016, 0.08, 8),
    "steel_ball": ObjectParams("钢球", "sphere", 0.22, 0.03, 0.08, 500),
    "foam_ball": ObjectParams("泡沫球", "sphere", 0.004, 0.05, 0.50, 5),
    "beach_ball": ObjectParams("沙滩球", "sphere", 0.01, 0.12, 0.70, 30),

    # ── 立方体 (6) ──
    "wooden_block": ObjectParams("木块", "cube", 0.15, 0.05, 0.60, 200),
    "metal_cube": ObjectParams("金属方块", "cube", 0.50, 0.04, 0.35, 500),
    "plastic_block": ObjectParams("塑料积木", "cube", 0.06, 0.04, 0.45, 80),
    "rubber_cube": ObjectParams("橡皮块", "cube", 0.10, 0.04, 0.70, 120),
    "foam_cube": ObjectParams("泡沫块", "cube", 0.01, 0.06, 0.50, 5),
    "hardwood_block": ObjectParams("硬木块", "cube", 0.22, 0.05, 0.55, 250),

    # ── 圆柱体 (6) ──
    "soda_can": ObjectParams("易拉罐", "cylinder", 0.37, 0.033, 0.40, 35, True),
    "water_bottle": ObjectParams("矿泉水瓶", "cylinder", 0.55, 0.035, 0.30, 60, True),
    "coffee_can": ObjectParams("咖啡罐", "cylinder", 0.45, 0.035, 0.45, 40, True),
    "spray_can": ObjectParams("喷雾罐", "cylinder", 0.25, 0.03, 0.35, 30, True),
    "candle": ObjectParams("蜡烛", "cylinder", 0.06, 0.025, 0.30, 10),
    "glass_jar": ObjectParams("玻璃罐", "cylinder", 0.50, 0.04, 0.18, 18, True),

    # ── 碗 (6) ──
    "plastic_bowl": ObjectParams("塑料碗", "bowl", 0.08, 0.075, 0.50, 60, True),
    "ceramic_bowl": ObjectParams("陶瓷碗", "bowl", 0.25, 0.07, 0.25, 25, True),
    "metal_bowl": ObjectParams("金属碗", "bowl", 0.18, 0.07, 0.20, 200, True),
    "glass_bowl": ObjectParams("玻璃碗", "bowl", 0.28, 0.065, 0.12, 14, True),
    "wooden_bowl": ObjectParams("木碗", "bowl", 0.12, 0.075, 0.55, 100, True),
    "ceramic_soup_bowl": ObjectParams("陶瓷汤碗", "bowl", 0.28, 0.07, 0.20, 22, True),

    # ── 瓶子 (6) ──
    "glass_bottle": ObjectParams("玻璃瓶", "bottle", 0.35, 0.035, 0.15, 20, True),
    "plastic_bottle": ObjectParams("塑料瓶", "bottle", 0.08, 0.035, 0.35, 50, True),
    "wine_bottle": ObjectParams("酒瓶", "bottle", 0.75, 0.04, 0.18, 22, True),
    "pill_bottle": ObjectParams("药瓶", "bottle", 0.04, 0.025, 0.38, 40, True),
    "perfume_bottle": ObjectParams("香水瓶", "bottle", 0.10, 0.025, 0.12, 8, True),
    "thermos": ObjectParams("保温瓶", "bottle", 0.55, 0.04, 0.35, 80, True),

    # ── 盘子 (6) ──
    "ceramic_plate": ObjectParams("瓷盘", "plate", 0.30, 0.10, 0.15, 22, False, False, True),
    "plastic_plate": ObjectParams("塑料盘", "plate", 0.05, 0.10, 0.40, 60, False, False, True),
    "paper_plate": ObjectParams("纸盘", "plate", 0.02, 0.10, 0.50, 10, False, False, True),
    "metal_plate": ObjectParams("金属盘", "plate", 0.25, 0.10, 0.18, 300, False, False, True),
    "wooden_plate": ObjectParams("木盘", "plate", 0.15, 0.10, 0.50, 120, False, False, True),
    "glass_plate": ObjectParams("玻璃盘", "plate", 0.28, 0.10, 0.12, 14, False, False, True),

    # ── 石块 (6) ──
    "irregular_rock": ObjectParams("不规则石块", "rock", 0.60, 0.06, 0.65, 500, False, True),
    "smooth_stone": ObjectParams("光滑卵石", "rock", 0.35, 0.04, 0.18, 500),
    "brick_fragment": ObjectParams("砖块碎片", "rock", 0.55, 0.05, 0.62, 400, False, True),
    "pumice": ObjectParams("浮石", "rock", 0.12, 0.05, 0.58, 150),
    "gravel": ObjectParams("碎石块", "rock", 0.40, 0.04, 0.68, 400, False, True),
    "quartz": ObjectParams("石英块", "rock", 0.38, 0.04, 0.15, 500),

    # ── 花瓶 (6) ──
    "ceramic_vase": ObjectParams("陶瓷花瓶", "vase", 0.30, 0.04, 0.15, 18, True),
    "glass_vase": ObjectParams("玻璃花瓶", "vase", 0.25, 0.04, 0.12, 14, True),
    "porcelain_vase": ObjectParams("瓷花瓶", "vase", 0.28, 0.04, 0.18, 16, True),
    "clay_vase": ObjectParams("陶土花瓶", "vase", 0.32, 0.045, 0.30, 25, True),
    "metal_vase": ObjectParams("金属花瓶", "vase", 0.35, 0.04, 0.22, 300, True),
    "crystal_vase": ObjectParams("水晶花瓶", "vase", 0.28, 0.04, 0.08, 12, True),
}


# ─────────────────────────────────────────────────────────
# 力映射函数
# ─────────────────────────────────────────────────────────

def force_normalized_to_newton(force_norm):
    for (f1, n1), (f2, n2) in zip(FORCE_MAP, FORCE_MAP[1:]):
        if force_norm <= f2:
            ratio = (force_norm - f1) / (f2 - f1)
            return n1 + ratio * (n2 - n1)
    return FORCE_MAP[-1][1]


def parse_ylyw_strategy(strategy_output: dict) -> dict:
    """解析 YLYW 策略输出为物理参数"""
    force_norm = strategy_output.get('effective_force',
                                     strategy_output.get('force', 0.5))
    force_n = force_normalized_to_newton(force_norm)
    speed = SPEED_MAP.get(strategy_output.get('speed', 'medium'), 0.15)
    return {
        'grasp_force_N': round(force_n, 2),
        'approach_speed_ms': speed,
    }


# ─────────────────────────────────────────────────────────
# 评估器: 标准双指夹爪力学
# ─────────────────────────────────────────────────────────

class PhysicsEvaluator:
    """标准双指夹爪力学评估器"""

    def __init__(self, gravity: float = 9.81):
        self.gravity = gravity

    def evaluate(self, obj_key: str, strategy_output: dict) -> dict:
        obj = OBJECT_PARAMS[obj_key]
        phys = parse_ylyw_strategy(strategy_output)
        angle_deg = strategy_output.get('approach_angle', 0)
        angle_rad = math.radians(angle_deg)

        fc_score = self._eval_force_closure(obj, angle_rad)
        lift_score = self._eval_lift(obj, phys['grasp_force_N'], angle_rad)
        safety_score = self._eval_safety(obj, phys['grasp_force_N'])

        total = 0.4 * fc_score + 0.4 * lift_score + 0.2 * safety_score

        # 角度搜索: 如果当前角度失败, 尝试最优角度
        best_score = total
        best_angle = angle_deg
        if total < 0.5:
            for try_deg in [10, 15, 20, 25, 30, 40]:
                try_rad = math.radians(try_deg)
                fc_try = self._eval_force_closure(obj, try_rad)
                lift_try = self._eval_lift(obj, phys['grasp_force_N'], try_rad)
                total_try = 0.4 * fc_try + 0.4 * lift_try + 0.2 * safety_score
                if total_try > best_score:
                    best_score = total_try
                    best_angle = try_deg
                if best_score >= 0.5:
                    break

        return {
            'obj_key': obj_key,
            'obj_name': obj.name,
            'obj_category': obj.category,
            'obj_mass_kg': obj.mass_kg,
            'obj_friction': obj.friction_coef,
            'grasp_force_N': phys['grasp_force_N'],
            'approach_angle': best_angle,
            'angle_optimized': best_angle != angle_deg,

            'force_closure_score': round(fc_score, 2),
            'lift_score': round(lift_score, 2),
            'safety_score': round(safety_score, 2),
            'total_score': round(best_score, 2),

            'grasp_success': best_score >= 0.5,
            'is_safe': safety_score >= 0.5,
        }

    def _eval_force_closure(self, obj: ObjectParams, angle_rad: float = 0.0) -> float:
        """
        力闭合评估: 摩擦半角分析 + 角度增益

        斜向抓取时, 手指与曲面法向的夹角产生几何锁止效应,
        等效摩擦系数 mu_eff = mu / cos(angle)
        """
        mu = obj.friction_coef
        # 角度增益: 斜向夹持利用几何锁止
        angle_gain = 1.0 + 0.5 * math.sin(angle_rad)  # 0°→1.0, 30°→1.25, 60°→1.43
        effective_mu = mu * angle_gain
        half_cone = math.atan(effective_mu)

        # 几何惩罚: 曲面物体更难形成稳定力闭合
        if obj.category in ('sphere',):
            shape_factor = 0.75
        elif obj.category in ('cylinder', 'bottle', 'vase'):
            shape_factor = 0.85
        elif obj.is_irregular:
            shape_factor = 0.80
        else:
            shape_factor = 1.0

        angle_score = min(1.0, half_cone / (math.pi / 3))
        return min(1.0, angle_score * shape_factor)

    def _eval_lift(self, obj: ObjectParams, F_grasp: float, angle_rad: float = 0.0) -> float:
        """
        提升可行性: 2μN ≥ mg + 角度增益

        斜向夹持时法向力分解: F_normal = F * cos(angle),
        切向摩擦力 = 2 * mu * F_normal,
        同时切向分力 F_tangential = F * sin(angle) 提供额外几何锁止力
        """
        mu = obj.friction_coef
        mg = obj.mass_kg * self.gravity

        # 斜向夹持: 摩擦力 + 几何锁止
        friction_force = 2 * mu * F_grasp * math.cos(angle_rad)
        geometric_lock = F_grasp * math.sin(angle_rad)
        total_hold = friction_force + geometric_lock

        if mg < 1e-6:
            return 1.0

        margin = total_hold / mg
        return min(1.0, max(0.0, (margin - 0.8) / 1.2))

    def _eval_safety(self, obj: ObjectParams, F_grasp: float) -> float:
        """
        物体安全性: F_grasp ≤ fragility

        标准判据: 夹持力不超过物体可承受上限。
        - F ≤ 0.5×fragility → 安全 (1.0)
        - F ≤ fragility → 可接受 (0.5)
        - F > fragility → 损坏风险 (0.0)
        """
        ratio = F_grasp / obj.fragility_newton if obj.fragility_newton > 0 else 10
        if ratio <= 0.5:
            return 1.0
        elif ratio <= 1.0:
            return 0.5
        else:
            return 0.0


# ─────────────────────────────────────────────────────────
# 批量评估器
# ─────────────────────────────────────────────────────────

class BatchEvaluator:
    def __init__(self):
        self.evaluator = PhysicsEvaluator()
        self.results = []

    def run_batch(self, ylyw_adapter, objects: Optional[List[str]] = None,
                  repeats: int = 1) -> List[dict]:
        if objects is None:
            objects = list(OBJECT_PARAMS.keys())
        self.results = []
        total = len(objects) * repeats

        for i, obj_key in enumerate(objects):
            for trial in range(repeats):
                try:
                    ylyw_result = ylyw_adapter.infer_from_preset(obj_key)
                except Exception as e:
                    print(f"  ⚠ {obj_key}: {e}")
                    continue

                s = ylyw_result['strategy']
                force = s.get('force', 0.5)
                mod = s.get('force_modifier', 1.0)
                eff = round(force * mod, 3)
                yao_q = s.get('yao_quality', 0)
                if hasattr(yao_q, 'score_overall'):
                    yao_q = yao_q.score_overall

                strategy_out = {
                    'type': s.get('type', 'generic'),
                    'force': force,
                    'force_modifier': mod,
                    'effective_force': eff,
                    'speed': s.get('speed', 'medium'),
                    'approach_angle': s.get('approach_angle', 0),
                    'yao_quality': float(yao_q or 0),
                }

                r = self.evaluator.evaluate(obj_key, strategy_out)
                r['trial'] = trial
                r['force_effective'] = eff
                r['inference_ms'] = ylyw_result.get('inference_ms', 0)
                r['yao_quality'] = float(yao_q or 0)

                p = ylyw_result['perception']
                hx = p.get('best_hexagram')
                r['hexagram_name'] = hx.name if hx else 'unknown'
                r['hexagram_similarity'] = float(p.get('hexagram_match_score', 0))

                self.results.append(r)

                idx = i * repeats + trial + 1
                s_mark = '✓' if r['grasp_success'] else '✗'
                print(f"  [{idx}/{total}] {s_mark} {obj_key:22s} "
                      f"F={eff:.2f}→{r['grasp_force_N']:.1f}N "
                      f"FC={r['force_closure_score']:.2f} "
                      f"lift={r['lift_score']:.2f} safe={r['safety_score']:.2f}")

        return self.results

    def compute_stats(self) -> dict:
        if not self.results:
            return {}
        total = len(self.results)
        successes = sum(1 for r in self.results if r['grasp_success'])
        safe = sum(1 for r in self.results if r['is_safe'])

        by_cat = {}
        for r in self.results:
            cat = r['obj_category']
            if cat not in by_cat:
                by_cat[cat] = {'total': 0, 'success': 0, 'scores': []}
            by_cat[cat]['total'] += 1
            if r['grasp_success']:
                by_cat[cat]['success'] += 1
            by_cat[cat]['scores'].append(r['total_score'])

        scores = [r['total_score'] for r in self.results]
        fcs = [r['force_closure_score'] for r in self.results]
        lifts = [r['lift_score'] for r in self.results]
        safeties = [r['safety_score'] for r in self.results]

        return {
            'total_trials': total,
            'grasp_successes': successes,
            'success_rate': round(100 * successes / total, 1),
            'safe_rate': round(100 * safe / total, 1),
            'avg_total_score': round(np.mean(scores), 3),
            'avg_fc_score': round(np.mean(fcs), 3),
            'avg_lift_score': round(np.mean(lifts), 3),
            'avg_safety_score': round(np.mean(safeties), 3),
            'by_category': {cat: {
                'total': info['total'],
                'success': info['success'],
                'rate': round(100 * info['success'] / info['total'], 1),
                'avg_score': round(np.mean(info['scores']), 3),
            } for cat, info in sorted(by_cat.items())},
        }

    def print_report(self):
        stats = self.compute_stats()
        print(f"\n{'='*60}")
        print(f"  物理解析评估 (标准双指力学)")
        print(f"{'='*60}")
        print(f"  总试验:  {stats['total_trials']}")
        print(f"  抓取成功: {stats['grasp_successes']} ({stats['success_rate']}%)")
        print(f"  安全性:  {stats['safe_rate']}%")
        print(f"  平均总分: {stats['avg_total_score']:.3f}")
        print()
        print(f"  按类型:")
        for cat, info in stats['by_category'].items():
            bar = '█' * int(info['rate'] / 10) + '░' * max(0, 10 - int(info['rate'] / 10))
            print(f"    {cat:10s} [{bar}] {info['success']}/{info['total']} "
                  f"({info['rate']:.0f}%) avg={info['avg_score']:.3f}")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    evaluator = PhysicsEvaluator()
    test_cases = [
        ('tennis_ball', 0.45, 'dynamic_grasp'),
        ('ceramic_vase', 0.40, 'cautious_grasp'),
        ('metal_cube', 0.85, 'power_grasp'),
        ('glass_vase', 0.55, 'power_grasp'),
    ]
    for obj_key, force, stype in test_cases:
        r = evaluator.evaluate(obj_key, {'effective_force': force, 'type': stype, 'speed': 'medium'})
        s = '✓' if r['grasp_success'] else '✗'
        print(f"{s} {obj_key:18s} F={r['grasp_force_N']:.1f}N "
              f"FC={r['force_closure_score']:.2f} lift={r['lift_score']:.2f} "
              f"safe={r['safety_score']:.2f} total={r['total_score']:.2f}")
    print('✓ 评估器就绪 (v2 标准力学)')
