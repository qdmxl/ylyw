#!/usr/bin/env python3
"""
YLYW 增强仿真场景生成器 (Simulation Scene)

基于原有 simulation/__init__.py，增强以下功能：
  - 批量生成可复现随机物体（指定 seed）
  - 物理特征噪声注入（模拟真实传感器误差）
  - 场景难度调节（easy/medium/hard）
  - 遮挡/堆叠模拟
  - 直接输出 13 维 numpy 特征向量

这是 experiment.py 的仿真后端，替代 PyBullet 提供快速推理验证。

用法:
    from simulation_scene import EnhancedSimulationScene
    scene = EnhancedSimulationScene(seed=42, difficulty="medium")
    features, meta = scene.generate_batch(objects_per_type=5)
"""

import random
import math
import numpy as np
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# ============================================================
# 物体物理参数模板（8类 × 2-3变体）
# ============================================================
OBJECT_TEMPLATES = {
    "sphere": {
        "name": "球体",
        "shape": "sphere",
        "mass_range": (0.02, 0.60),
        "size_range": (0.02, 0.12),
        "friction_range": (0.1, 0.40),
        "fragility_base": 0.20,
        "roll_tendency_base": 0.90,
        "grasp_surface": 0.45,
        "support_area_fraction": 0.05,
        "variants": ["网球", "乒乓球", "高尔夫球", "弹力球", "玻璃珠"],
    },
    "cube": {
        "name": "立方体",
        "shape": "cube",
        "mass_range": (0.10, 1.50),
        "size_range": (0.03, 0.12),
        "friction_range": (0.35, 0.70),
        "fragility_base": 0.18,
        "roll_tendency_base": 0.08,
        "grasp_surface": 0.65,
        "support_area_fraction": 0.75,
        "variants": ["木块", "金属方块", "塑料积木", "橡皮块"],
    },
    "cylinder": {
        "name": "圆柱体",
        "shape": "cylinder",
        "mass_range": (0.08, 1.00),
        "size_range": (0.03, 0.10),
        "friction_range": (0.20, 0.50),
        "fragility_base": 0.30,
        "roll_tendency_base": 0.65,
        "grasp_surface": 0.55,
        "support_area_fraction": 0.35,
        "variants": ["易拉罐", "矿泉水瓶", "笔筒", "电池"],
    },
    "bowl": {
        "name": "碗",
        "shape": "bowl",
        "mass_range": (0.10, 0.50),
        "size_range": (0.05, 0.15),
        "friction_range": (0.40, 0.70),
        "fragility_base": 0.55,
        "roll_tendency_base": 0.30,
        "grasp_surface": 0.70,
        "support_area_fraction": 0.45,
        "is_hollow": True,
        "variants": ["塑料碗", "陶瓷碗", "不锈钢碗"],
    },
    "bottle": {
        "name": "瓶子",
        "shape": "bottle",
        "mass_range": (0.12, 0.80),
        "size_range": (0.04, 0.12),
        "friction_range": (0.15, 0.45),
        "fragility_base": 0.70,
        "roll_tendency_base": 0.50,
        "grasp_surface": 0.45,
        "support_area_fraction": 0.22,
        "is_hollow": True,
        "variants": ["玻璃瓶", "塑料瓶", "药瓶"],
    },
    "plate": {
        "name": "盘子",
        "shape": "plate",
        "mass_range": (0.10, 0.40),
        "size_range": (0.08, 0.20),
        "friction_range": (0.20, 0.45),
        "fragility_base": 0.75,
        "roll_tendency_base": 0.08,
        "grasp_surface": 0.35,
        "support_area_fraction": 0.70,
        "is_flat": True,
        "variants": ["瓷盘", "塑料盘", "纸盘"],
    },
    "rock": {
        "name": "石块",
        "shape": "irregular",
        "mass_range": (0.20, 2.00),
        "size_range": (0.04, 0.15),
        "friction_range": (0.55, 0.90),
        "fragility_base": 0.22,
        "roll_tendency_base": 0.45,
        "grasp_surface": 0.35,
        "support_area_fraction": 0.30,
        "irregular": True,
        "variants": ["不规则石块", "光滑卵石", "矿石"],
    },
    "vase": {
        "name": "花瓶",
        "shape": "vase",
        "mass_range": (0.18, 0.55),
        "size_range": (0.06, 0.18),
        "friction_range": (0.20, 0.45),
        "fragility_base": 0.85,
        "roll_tendency_base": 0.20,
        "grasp_surface": 0.40,
        "support_area_fraction": 0.28,
        "is_hollow": True,
        "variants": ["陶瓷花瓶", "玻璃花瓶"],
    },
}


@dataclass
class SceneObject:
    """场景中的物体"""
    object_id: int
    object_type: str  # sphere, cube, cylinder, etc.
    variant_name: str  # "网球", "木块", etc.
    position: np.ndarray  # (x, y, z)
    features: np.ndarray  # (13,) 归一化特征向量
    is_occluded: bool
    difficulty: str  # easy, medium, hard

    @property
    def feature_dict(self) -> dict:
        """返回特征字典（兼容PriorManual）"""
        return {
            "stability": float(self.features[0]),
            "roll_tendency": float(self.features[1]),
            "strength_needed": float(self.features[2]),
            "fragility": float(self.features[3]),
            "reachability": float(self.features[4]),
            "grasp_surface_quality": float(self.features[5]),
            "support_area": float(self.features[6]),
            "occlusion": float(self.features[7]),
            "obstacle_density": float(self.features[8]),
            "task_priority": float(self.features[9]),
            "weight_ratio": float(self.features[10]),
            "visibility": float(self.features[11]),
            "deformability": float(self.features[12]),
        }


# ============================================================
# 增强仿真场景生成器
# ============================================================
class EnhancedSimulationScene:
    """增强版仿真场景生成器"""

    FEATURE_NAMES = [
        "stability", "roll_tendency", "strength_needed", "fragility",
        "reachability", "grasp_surface_quality", "support_area",
        "occlusion", "obstacle_density", "task_priority",
        "weight_ratio", "visibility", "deformability",
    ]

    def __init__(self, seed: int = None, difficulty: str = "medium",
                 robot_max_payload: float = 2.0,
                 noise_level: float = 0.05,
                 enabled_types: List[str] = None):
        """
        Args:
            seed: 随机种子
            difficulty: 场景难度 (easy/medium/hard)
            robot_max_payload: 机械臂最大负载 (kg)
            noise_level: 特征噪声水平 [0, 1]
            enabled_types: 允许的物体类型（None=全部8种）
        """
        self.seed = seed
        self.difficulty = difficulty
        self.robot_max_payload = robot_max_payload
        self.noise_level = noise_level
        self.enabled_types = enabled_types or list(OBJECT_TEMPLATES.keys())

        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self._next_id = 0

        # 难度参数
        difficulty_params = {
            "easy": {
                "occlusion_prob": 0.05,
                "occlusion_max": 0.15,
                "obstacle_density_max": 0.20,
                "noise_scale": 0.02,
            },
            "medium": {
                "occlusion_prob": 0.15,
                "occlusion_max": 0.40,
                "obstacle_density_max": 0.45,
                "noise_scale": 0.05,
            },
            "hard": {
                "occlusion_prob": 0.30,
                "occlusion_max": 0.70,
                "obstacle_density_max": 0.70,
                "noise_scale": 0.10,
            },
        }
        self.diff = difficulty_params.get(difficulty, difficulty_params["medium"])

    def reset(self, seed: int = None):
        """重置生成器（新 seed）"""
        if seed is not None:
            self.seed = seed
            random.seed(seed)
            np.random.seed(seed)
        self._next_id = 0

    def generate_object(self, object_type: str,
                        occluded: bool = None) -> SceneObject:
        """生成单个物体"""
        if object_type not in OBJECT_TEMPLATES:
            object_type = random.choice(self.enabled_types)

        template = OBJECT_TEMPLATES[object_type]

        # 随机物理参数
        mass = random.uniform(*template["mass_range"])
        size = random.uniform(*template["size_range"])
        friction = random.uniform(*template["friction_range"])

        # 随机位置
        x = random.uniform(-0.35, 0.35)
        y = random.uniform(-0.35, 0.35)
        z = random.uniform(0.02, 0.15)

        # 遮挡
        if occluded is None:
            occluded = random.random() < self.diff["occlusion_prob"]
        occlusion = (random.uniform(0.05, self.diff["occlusion_max"])
                     if occluded else random.uniform(0.0, 0.08))

        # 计算 13 维特征
        features = self._compute_features(object_type, template, mass, size,
                                          friction, occlusion, x, y, z)
        # 注入噪声
        features = self._add_noise(features)

        self._next_id += 1
        variant = random.choice(template["variants"])

        return SceneObject(
            object_id=self._next_id,
            object_type=object_type,
            variant_name=variant,
            position=np.array([x, y, z]),
            features=features,
            is_occluded=occluded,
            difficulty=self.difficulty,
        )

    def generate_batch(self, objects_per_type: int = 5,
                       types: List[str] = None) -> Tuple[List[np.ndarray], List[dict]]:
        """
        批量生成物体（每类均匀分布）

        Args:
            objects_per_type: 每类物体数量
            types: 物体类型列表（None=全部）

        Returns:
            (features_list, meta_list)
            features_list: [np.ndarray(13,), ...]
            meta_list: [{"type": str, "variant": str, "occluded": bool}, ...]
        """
        use_types = types or self.enabled_types
        features_list = []
        meta_list = []

        for t in use_types:
            for _ in range(objects_per_type):
                obj = self.generate_object(t)
                features_list.append(obj.features)
                meta_list.append({
                    "type": obj.object_type,
                    "variant": obj.variant_name,
                    "occluded": obj.is_occluded,
                    "difficulty": obj.difficulty,
                })

        return features_list, meta_list

    def generate_varied_batch(self, per_type_range: Tuple[int, int] = (2, 8),
                              types: List[str] = None) -> Tuple[List[np.ndarray], List[dict]]:
        """
        每类数量不一的生成（模拟真实分布不均）
        """
        use_types = types or self.enabled_types
        features_list = []
        meta_list = []

        for t in use_types:
            n = random.randint(*per_type_range)
            for _ in range(n):
                obj = self.generate_object(t)
                features_list.append(obj.features)
                meta_list.append({
                    "type": obj.object_type,
                    "variant": obj.variant_name,
                    "occluded": obj.is_occluded,
                    "difficulty": obj.difficulty,
                })

        return features_list, meta_list

    # ========================
    #  特征计算
    # ========================
    def _compute_features(self, obj_type, template, mass, size,
                          friction, occlusion, x, y, z) -> np.ndarray:
        """计算13维物理特征"""
        t = template

        # 1. stability (稳定性)
        base_stability = t["support_area_fraction"]
        if t.get("is_hollow"):
            base_stability -= 0.12
        if t.get("irregular"):
            base_stability -= 0.15
        stability = base_stability + 0.10 * min(1.0, mass / 1.5)

        # 2. roll_tendency (滚动倾向)
        roll_tendency = t["roll_tendency_base"]

        # 3. strength_needed (力需求)
        mass_factor = min(1.0, mass / self.robot_max_payload)
        friction_bonus = 0.3 * (1.0 - friction)
        strength_needed = mass_factor + friction_bonus

        # 4. fragility (脆弱性)
        fragility = t["fragility_base"] + 0.08 * min(1.0, mass / 1.5)

        # 5. reachability (可达性)
        distance = math.sqrt(x*x + y*y)
        reachability = max(0.0, 1.0 - distance / 0.5)

        # 6. grasp_surface_quality (抓取表面质量)
        gsq = t["grasp_surface"]

        # 7. support_area (支撑面积)
        support_area = t["support_area_fraction"] * (size / 0.15)

        # 8. occlusion (遮挡)
        obs_density = min(1.0, occlusion * 2.5)

        # 9. obstacle_density (障碍密度)
        obstacle_density = random.uniform(0.0, self.diff["obstacle_density_max"])

        # 10. task_priority (任务优先级)
        task_priority = random.uniform(0.3, 0.9)

        # 11. weight_ratio (重量比)
        weight_ratio = min(1.0, mass / self.robot_max_payload)

        # 12. visibility (可见性)
        visibility = 0.7 + random.uniform(-0.2, 0.2) - occlusion * 0.5

        # 13. deformability (变形能力)
        deformability = 0.12 + random.uniform(0, 0.15)
        if t.get("is_hollow"):
            deformability += 0.20
        if t.get("is_flat"):
            deformability = 0.08
        if obj_type in ("rock", "cube"):
            deformability = max(0.02, deformability - 0.10)

        features = np.array([
            stability, roll_tendency, strength_needed, fragility,
            reachability, gsq, support_area, occlusion,
            obstacle_density, task_priority, weight_ratio,
            visibility, deformability,
        ])
        return np.clip(features, 0.0, 1.0)

    def _add_noise(self, features: np.ndarray) -> np.ndarray:
        """注入高斯噪声"""
        noise = np.random.normal(0, self.diff["noise_scale"], size=features.shape)
        return np.clip(features + noise, 0.0, 1.0)

    # ========================
    #  工具
    # ========================
    def get_type_stats(self) -> dict:
        """获取物体类型元信息"""
        result = {}
        for key, t in OBJECT_TEMPLATES.items():
            result[key] = {
                "name": t["name"],
                "shape": t["shape"],
                "variants": t["variants"],
                "mass_range": t["mass_range"],
                "roll_tendency": t["roll_tendency_base"],
                "fragility": t["fragility_base"],
            }
        return result

    def print_stats(self):
        """打印物体类型统计"""
        print("\n" + "=" * 60)
        print(f"  Enhanced Simulation Scene — {self.difficulty.upper()} mode")
        print("=" * 60)
        for key, info in self.get_type_stats().items():
            print(f"  {key:10s} {info['name']:8s} "
                  f"roll={info['roll_tendency']:.2f} "
                  f"frag={info['fragility']:.2f} "
                  f"mass={info['mass_range']}")
            print(f"             variants: {', '.join(info['variants'])}")
        print("=" * 60)


# ============================================================
# 演示
# ============================================================
def demo():
    """仿真场景演示"""
    print("=" * 60)
    print("  YLYW Enhanced Simulation Scene — Demo")
    print("=" * 60)

    for diff in ["easy", "medium", "hard"]:
        scene = EnhancedSimulationScene(seed=42, difficulty=diff)
        features, meta = scene.generate_batch(objects_per_type=1)
        print(f"\n  [{diff.upper()}] {len(features)} objects generated")
        for i, (f, m) in enumerate(zip(features, meta)):
            print(f"    {m['type']:8s} ({m['variant']:8s}) "
                  f"stab={f[0]:.2f} roll={f[1]:.2f} "
                  f"force={f[2]:.2f} frag={f[3]:.2f} "
                  f"occ={f[7]:.2f}")

    print("\n  ✅ Demo complete!")


if __name__ == "__main__":
    demo()
