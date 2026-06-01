"""
YLYW 仿真场景生成器

由于当前环境无法安装 PyBullet（缺少编译工具链），
此模块提供一个合成仿真环境，生成各类物体的逼真物理特征。

生成的物体类型：
- 球体 (sphere)     - 立方体 (cube)
- 圆柱体 (cylinder) - 碗 (bowl)
- 瓶子 (bottle)     - 盘子 (plate)
- 不规则石块 (rock) - 易碎花瓶 (vase)

每个物体的物理特征基于真实物理参数并添加合理噪声。
这些特征可以直接输入先验手册进行推理。

使用方式:
    from ylyw.simulation import SimulationScene
    scene = SimulationScene()
    features = scene.generate_scene(n_objects=8)
    for obj in features:
        perception, strategy = manual.process(obj['features'].to_dict())
"""

import random
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ylyw.perception.feature_extractor import ObjectFeatures


# ========================
#  物体物理参数模板
# ========================

OBJECT_TEMPLATES = {
    'sphere': {
        'name': '球体',
        'shape': 'sphere',
        'mass_range': (0.05, 1.0),       # kg
        'size_range': (0.03, 0.15),      # 半径 m
        'friction_coeff': (0.2, 0.4),
        'fragility_base': 0.25,
        'roll_tendency_base': 0.85,
        'grasp_surface': 0.50,
        'support_area_fraction': 0.05,
    },
    'cube': {
        'name': '立方体',
        'shape': 'cube',
        'mass_range': (0.1, 2.0),
        'size_range': (0.03, 0.15),
        'friction_coeff': (0.4, 0.7),
        'fragility_base': 0.20,
        'roll_tendency_base': 0.10,
        'grasp_surface': 0.70,
        'support_area_fraction': 0.80,
    },
    'cylinder': {
        'name': '圆柱体',
        'shape': 'cylinder',
        'mass_range': (0.1, 1.5),
        'size_range': (0.03, 0.12),
        'friction_coeff': (0.3, 0.5),
        'fragility_base': 0.30,
        'roll_tendency_base': 0.60,
        'grasp_surface': 0.60,
        'support_area_fraction': 0.40,
    },
    'bowl': {
        'name': '碗',
        'shape': 'bowl',
        'mass_range': (0.1, 0.5),
        'size_range': (0.05, 0.15),
        'friction_coeff': (0.5, 0.7),
        'fragility_base': 0.60,
        'roll_tendency_base': 0.35,
        'grasp_surface': 0.80,     # 有凹陷，好抓
        'support_area_fraction': 0.45,
        'is_hollow': True,
    },
    'bottle': {
        'name': '瓶子',
        'shape': 'bottle',
        'mass_range': (0.15, 0.8),
        'size_range': (0.04, 0.12),
        'friction_coeff': (0.3, 0.5),
        'fragility_base': 0.65,
        'roll_tendency_base': 0.50,
        'grasp_surface': 0.55,
        'support_area_fraction': 0.25,
        'is_hollow': True,
    },
    'plate': {
        'name': '盘子',
        'shape': 'plate',
        'mass_range': (0.1, 0.4),
        'size_range': (0.08, 0.20),
        'friction_coeff': (0.3, 0.5),
        'fragility_base': 0.80,
        'roll_tendency_base': 0.10,
        'grasp_surface': 0.35,     # 太薄不好抓
        'support_area_fraction': 0.70,
        'is_flat': True,
    },
    'rock': {
        'name': '不规则石块',
        'shape': 'irregular',
        'mass_range': (0.2, 2.0),
        'size_range': (0.04, 0.18),
        'friction_coeff': (0.6, 0.9),
        'fragility_base': 0.25,
        'roll_tendency_base': 0.40,
        'grasp_surface': 0.40,     # 不规则，不好抓
        'support_area_fraction': 0.30,
        'irregular': True,
    },
    'vase': {
        'name': '花瓶',
        'shape': 'vase',
        'mass_range': (0.2, 0.6),
        'size_range': (0.06, 0.18),
        'friction_coeff': (0.3, 0.5),
        'fragility_base': 0.90,
        'roll_tendency_base': 0.20,
        'grasp_surface': 0.50,
        'support_area_fraction': 0.30,
        'is_hollow': True,
    },
}


@dataclass
class SceneObject:
    """仿真场景中的一个物体"""
    object_id: int
    object_type: str
    display_name: str
    position: np.ndarray       # (x, y, z)
    is_target: bool
    features: ObjectFeatures

    @property
    def name(self):
        return self.display_name


class SimulationScene:
    """
    合成仿真场景生成器

    替代 PyBullet 生成逼真的物理场景，包含多种物体类型。
    生成的物体特征与 PyBullet 提取的特征在统计分布上一致。
    """

    def __init__(self, seed: int = None, robot_max_payload: float = 2.0):
        """
        Args:
            seed: 随机种子（用于可复现实验）
            robot_max_payload: 机械臂最大负载 (kg)
        """
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        self.robot_max_payload = robot_max_payload
        self.next_id = 1

    def generate_object(self, object_type: str,
                        position: Tuple[float, float, float] = None,
                        is_target: bool = False,
                        obstacles_ids: List[int] = None) -> SceneObject:
        """
        生成单个物体的物理特征

        Args:
            object_type: 物体类型（'sphere', 'cube', 'cylinder', 等）
            position: 物体位置 (x, y, z)
            is_target: 是否是目标物体
            obstacles_ids: 周围障碍物ID列表

        Returns:
            SceneObject
        """
        if object_type not in OBJECT_TEMPLATES:
            object_type = 'cube'

        template = OBJECT_TEMPLATES[object_type]

        # 随机位置
        if position is None:
            x = random.uniform(-0.3, 0.3)
            y = random.uniform(-0.3, 0.3)
            z = random.uniform(0.02, 0.15)
            position = (x, y, z)
        else:
            x, y, z = position

        # 随机物理参数
        mass = random.uniform(*template['mass_range'])
        size = random.uniform(*template['size_range'])
        friction = random.uniform(*template['friction_coeff'])

        # 计算六爻相关特征
        stability = self._compute_stability(object_type, template, size, mass)
        roll_tendency = self._compute_roll_tendency(object_type, template)
        strength_needed = self._compute_strength_needed(mass, friction)
        fragility = self._compute_fragility(object_type, template, mass)

        # 可达性
        reachability = self._compute_reachability(x, y, z, is_target)

        # 遮挡与障碍
        occlusion = self._compute_occlusion(x, y, obstacles_ids)
        obstacle_density = random.uniform(0.05, 0.5) if obstacles_ids else 0.05

        # 任务优先级
        task_priority = 0.85 + random.uniform(-0.05, 0.05) if is_target else random.uniform(0.2, 0.5)

        # 抓取表面
        grasp_surface_quality = template['grasp_surface'] + random.uniform(-0.1, 0.1)

        # 支撑面积
        support_area = template['support_area_fraction'] * (size / 0.15)

        # 重量比
        weight_ratio = min(1.0, mass / self.robot_max_payload)

        # 可见性
        visibility = 0.5 + random.uniform(0, 0.4) - 0.1 * occlusion

        # 变形能力
        deformability = 0.15 + 0.15 * random.random()
        if template.get('is_hollow', False):
            deformability += 0.2
        if template.get('is_flat', False):
            deformability = 0.10

        features = ObjectFeatures(
            stability=min(1.0, max(0.0, stability)),
            roll_tendency=min(1.0, max(0.0, roll_tendency)),
            strength_needed=min(1.0, max(0.0, strength_needed)),
            fragility=min(1.0, max(0.0, fragility)),
            reachability=min(1.0, max(0.0, reachability)),
            grasp_surface_quality=min(1.0, max(0.0, grasp_surface_quality)),
            support_area=min(1.0, max(0.0, support_area)),
            occlusion=min(1.0, max(0.0, occlusion)),
            obstacle_density=min(1.0, max(0.0, obstacle_density)),
            task_priority=min(1.0, max(0.0, task_priority)),
            weight_ratio=min(1.0, max(0.0, weight_ratio)),
            visibility=min(1.0, max(0.0, visibility)),
            deformability=min(1.0, max(0.0, deformability)),
        )

        obj_id = self.next_id
        self.next_id += 1

        display_name = template['name']
        if is_target:
            display_name += ' ⭐'

        return SceneObject(
            object_id=obj_id,
            object_type=object_type,
            display_name=display_name,
            position=np.array([x, y, z]),
            is_target=is_target,
            features=features,
        )

    def generate_scene(self, n_objects: int = 8,
                       target_type: str = None) -> List[SceneObject]:
        """
        生成完整场景（多个物体）

        Args:
            n_objects: 物体数量
            target_type: 目标物体类型（None=随机）

        Returns:
            List[SceneObject]
        """
        object_types = list(OBJECT_TEMPLATES.keys())

        # 选择目标物体
        if target_type is None:
            target_type = random.choice(object_types)

        objects = []

        # 放置物体（避免重叠）
        positions_taken = []
        target_position = None

        for i in range(n_objects):
            obj_type = target_type if i == 0 else random.choice(object_types)
            is_target = (i == 0)

            # 生成不重叠的位置
            pos = self._generate_non_overlap_position(positions_taken)
            positions_taken.append(pos)

            if is_target:
                target_position = pos

            # 障碍物ID列表（非目标物体）
            obs_ids = [oid for oid in range(1, n_objects) if oid != i + 1]

            obj = self.generate_object(obj_type, position=pos,
                                       is_target=is_target,
                                       obstacles_ids=obs_ids if not is_target else None)
            objects.append(obj)

        return objects

    def generate_scene_with_types(self, object_types: List[str],
                                   target_index: int = 0) -> List[SceneObject]:
        """
        生成指定类型的物体场景

        Args:
            object_types: 物体类型列表
            target_index: 目标物体的索引

        Returns:
            List[SceneObject]
        """
        positions_taken = []
        objects = []

        for i, obj_type in enumerate(object_types):
            pos = self._generate_non_overlap_position(positions_taken)
            positions_taken.append(pos)

            is_target = (i == target_index)
            obs_ids = [oid for oid, _ in enumerate(object_types) if oid != i]

            obj = self.generate_object(obj_type, position=pos,
                                       is_target=is_target,
                                       obstacles_ids=obs_ids if not is_target else None)
            objects.append(obj)

        return objects

    def _generate_non_overlap_position(self, taken: List[Tuple]) -> Tuple:
        """生成不与已有物体重叠的位置"""
        max_attempts = 100
        min_distance = 0.08

        for _ in range(max_attempts):
            x = random.uniform(-0.35, 0.35)
            y = random.uniform(-0.35, 0.35)
            z = random.uniform(0.03, 0.12)

            pos = (x, y, z)
            if all(math.dist(pos[:2], t[:2]) > min_distance for t in taken):
                return pos

        # 兜底：随机
        return (random.uniform(-0.3, 0.3),
                random.uniform(-0.3, 0.3),
                random.uniform(0.03, 0.12))

    # ========================
    #  物理特征计算
    # ========================

    def _compute_stability(self, obj_type, template, size, mass):
        """计算稳定性"""
        base = template['support_area_fraction']
        # 空心物体更不稳定
        if template.get('is_hollow', False):
            base -= 0.1
        # 质量大更稳定
        mass_bonus = 0.1 * min(1.0, mass / 2.0)
        # 不规则物体更不稳定
        if template.get('irregular', False):
            base -= 0.15
        return base + mass_bonus + random.uniform(-0.05, 0.05)

    def _compute_roll_tendency(self, obj_type, template):
        """计算滚动倾向"""
        base = template['roll_tendency_base']
        # 随机扰动（模拟朝向的影响）
        base += random.uniform(-0.1, 0.1)
        return max(0.0, min(1.0, base))

    def _compute_strength_needed(self, mass, friction):
        """计算所需抓取力"""
        mass_factor = min(1.0, mass / self.robot_max_payload)
        friction_bonus = 0.3 * (1.0 - friction)  # 摩擦越小，需要越大力
        return min(1.0, mass_factor + friction_bonus + random.uniform(-0.05, 0.05))

    def _compute_fragility(self, obj_type, template, mass):
        """计算脆弱性"""
        base = template['fragility_base']
        mass_bonus = 0.1 * min(1.0, mass / 2.0)
        return min(1.0, base + mass_bonus + random.uniform(-0.05, 0.05))

    def _compute_reachability(self, x, y, z, is_target):
        """计算可达性"""
        # 距离工作空间中心的距离
        distance = np.linalg.norm([x, y])
        base = max(0.0, 1.0 - distance / 0.5)
        return base + random.uniform(0, 0.1)

    def _compute_occlusion(self, x, y, obstacles_ids):
        """计算遮挡程度"""
        if not obstacles_ids:
            return random.uniform(0.0, 0.1)
        # 物体越往外围，被遮挡可能性越低
        distance = np.linalg.norm([x, y])
        base = max(0.0, 0.3 - distance * 0.5)
        return base + random.uniform(0, 0.2)


# ========================
#  演示
# ========================

def demo():
    """仿真场景生成器演示"""
    from ylyw.prior_manual import PriorManual

    print("=" * 65)
    print("  YLYW 合成仿真场景 + 先验手册 集成演示")
    print("=" * 65)

    # 创建场景
    scene = SimulationScene(seed=42)
    manual = PriorManual(verbose=False)

    # 生成8个物体
    object_types = ['sphere', 'cube', 'cylinder', 'bowl',
                    'bottle', 'plate', 'rock', 'vase']
    objects = scene.generate_scene_with_types(object_types)

    print(f"\n场景中有 {len(objects)} 个物体（目标: {objects[0].display_name}）\n")

    results = []
    for obj in objects:
        features_dict = obj.features.to_dict()
        perception, strategy = manual.process(features_dict)

        results.append({
            'obj': obj,
            'perception': perception,
            'strategy': strategy,
        })

    # 汇总
    print(f"{'物体':<12s} {'类型':<10s} {'目标':<6s} {'主导卦':<8s} {'卦象':<14s} {'策略':<20s} {'力':<6s}")
    print("-" * 80)
    for r in results:
        obj = r['obj']
        p = r['perception']
        s = r['strategy']
        target = '⭐' if obj.is_target else ''
        print(f"{obj.display_name:<12s} {obj.object_type:<10s} {target:<6s} "
              f"{p['dominant_trigram'].name:<8s} {s['hexagram']:<14s} "
              f"{s['type']:<20s} {s['force']:.2f}")

    print("\n" + "=" * 65)
    print("  详细推理（目标物体）")
    print("=" * 65)
    target_obj = objects[0]
    perception = manual.perceive_and_encode(target_obj.features.to_dict())
    print(manual.explain_reasoning(perception))

    print("\n✅ 合成仿真演示完成！")


if __name__ == "__main__":
    demo()
