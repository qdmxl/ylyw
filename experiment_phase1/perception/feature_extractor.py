"""
特征提取模块 (Feature Extractor)

从 PyBullet 仿真环境中提取物体的物理特征。
这些特征将作为先验手册的输入。

提取的特征分为六组（对应六爻）:
    1. 基础稳定性  → stability, roll_tendency, support_area
    2. 抓取可达性  → reachability, occlusion, grasp_surface_quality
    3. 抓取力需求  → strength_needed, weight_ratio
    4. 物体脆弱性  → fragility, deformability
    5. 任务优先级  → task_priority
    6. 环境约束    → obstacle_density
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
import math


@dataclass
class ObjectFeatures:
    """
    物体的特征向量，与先验手册的输入格式对齐

    每个特征值 ∈ [0, 1]，越高表示该属性越强。
    """

    # === 基础物理属性 ===
    stability: float = 0.5           # 稳定性，越高越稳定、不易倾倒
    roll_tendency: float = 0.5      # 滚动倾向，越高越容易滚动
    strength_needed: float = 0.5    # 抓取所需力量，越高需要越大力
    fragility: float = 0.5          # 脆弱性，越高越易碎

    # === 抓取相关 ===
    reachability: float = 0.5       # 可达性，夹爪能否无碰撞到达
    grasp_surface_quality: float = 0.5  # 抓取表面质量，越高越容易抓
    support_area: float = 0.5       # 支撑面积（归一化）

    # === 环境与任务 ===
    occlusion: float = 0.0          # 遮挡程度
    obstacle_density: float = 0.0   # 周围障碍物密度
    task_priority: float = 0.5      # 任务优先级（目标物体=高，障碍物=低）
    weight_ratio: float = 0.5       # 重量比（物体重量 / 机械臂负载）

    # === 额外属性（用于八卦映射） ===
    visibility: float = 0.5         # 可见性（颜色、大小等）
    deformability: float = 0.5      # 变形能力，越高越容易变形

    def to_dict(self) -> dict:
        """转换为字典格式（供先验手册输入）"""
        return {
            'stability': self.stability,
            'roll_tendency': self.roll_tendency,
            'strength_needed': self.strength_needed,
            'fragility': self.fragility,
            'reachability': self.reachability,
            'grasp_surface_quality': self.grasp_surface_quality,
            'support_area': self.support_area,
            'occlusion': self.occlusion,
            'obstacle_density': self.obstacle_density,
            'task_priority': self.task_priority,
            'weight_ratio': self.weight_ratio,
            'visibility': self.visibility,
            'deformability': self.deformability,
        }


class FeatureExtractor:
    """
    从 PyBullet 仿真中提取物体的物理特征

    使用方式:
        >>> extractor = FeatureExtractor(robot_id, gripper_id)
        >>> features = extractor.extract_all_features(object_id)
        >>> features_dict = features.to_dict()
    """

    # 材质属性先验知识库
    # 格式: {物体类型: [密度(kg/m³), 弹性系数, 摩擦系数, 易碎阈值]}
    MATERIAL_PROPERTIES = {
        'cube':     [500, 0.8, 0.5, 0.3],
        'sphere':   [400, 0.9, 0.2, 0.2],
        'cylinder': [450, 0.7, 0.4, 0.3],
        'bowl':     [300, 0.5, 0.6, 0.6],
        'bottle':   [350, 0.6, 0.4, 0.5],
        'plate':    [400, 0.7, 0.3, 0.7],
        'default':  [500, 0.5, 0.5, 0.4],
    }

    def __init__(self, robot_id: int = -1, gripper_id: int = -1,
                 client_id: int = 0, max_payload: float = 2.0):
        """
        Args:
            robot_id: 机械臂的 PyBullet body unique id
            gripper_id: 夹爪的 PyBullet body unique id
            client_id: PyBullet 客户端 ID
            max_payload: 机械臂最大负载 (kg)，默认 UR5e = 2.0 kg
        """
        self.robot_id = robot_id
        self.gripper_id = gripper_id
        self.client_id = client_id
        self.max_payload = max_payload

    def extract_all_features(self, object_id: int,
                             target_position: Optional[List[float]] = None,
                             obstacles_ids: Optional[List[int]] = None) -> ObjectFeatures:
        """
        提取物体的所有特征（一站式调用）

        Args:
            object_id: 物体的 PyBullet body unique id
            target_position: 目标位置（若是目标物体，传入其位置）
            obstacles_ids: 周围障碍物的 id 列表

        Returns:
            ObjectFeatures: 完整的特征向量
        """
        import pybullet as p

        # 获取基本状态
        position, orientation = p.getBasePositionAndOrientation(object_id, self.client_id)

        # 获取几何信息
        aabb_min, aabb_max = p.getAABB(object_id, -1, self.client_id)
        dimensions = np.array(aabb_max) - np.array(aabb_min)

        # 获取质量
        mass = self._get_object_mass(object_id)

        # 获取物体类型
        object_type = self._get_object_type(object_id)

        # === 逐一提取各维度特征 ===
        stability = self._compute_stability(dimensions)
        roll_tendency = self._compute_roll_tendency(object_type, dimensions, orientation)
        strength_needed = self._compute_strength_needed(mass, object_type)
        fragility = self._compute_fragility(object_type, mass)
        deformability = self._compute_deformability(object_type)

        reachability = self._compute_reachability(object_id, position, target_position)
        grasp_surface_quality = self._compute_grasp_surface_quality(object_type)
        support_area = self._compute_support_area(dimensions)

        occlusion = self._compute_occlusion(object_id, position)
        obstacle_density = self._compute_obstacle_density(position, obstacles_ids)
        weight_ratio = min(1.0, mass / self.max_payload if self.max_payload > 0 else 0.5)

        visibility = self._compute_visibility(object_type)

        # 任务优先级
        task_priority = 0.9 if target_position is not None else 0.3

        return ObjectFeatures(
            stability=stability,
            roll_tendency=roll_tendency,
            strength_needed=strength_needed,
            fragility=fragility,
            reachability=reachability,
            grasp_surface_quality=grasp_surface_quality,
            support_area=support_area,
            occlusion=occlusion,
            obstacle_density=obstacle_density,
            task_priority=task_priority,
            weight_ratio=weight_ratio,
            visibility=visibility,
            deformability=deformability,
        )

    # ========================
    #  内部特征计算方法
    # ========================

    def _get_object_mass(self, object_id: int) -> float:
        """获取物体质量 (kg)"""
        try:
            import pybullet as p
            dynamics_info = p.getDynamicsInfo(object_id, -1, self.client_id)
            return dynamics_info[0] if dynamics_info else 0.5
        except Exception:
            return 0.5

    def _get_object_type(self, object_id: int) -> str:
        """从 URDF 文件名或自定义属性推断物体类型"""
        # 检查是否有自定义属性
        if hasattr(object_id, 'object_type'):
            return object_id.object_type
        # 尝试从 body info 中获取名称
        try:
            import pybullet as p
            info = p.getBodyInfo(object_id, self.client_id)
            name = info[0].decode() if isinstance(info[0], bytes) else str(info[0])
            for obj_type in self.MATERIAL_PROPERTIES:
                if obj_type in name.lower():
                    return obj_type
        except Exception:
            pass
        return 'default'

    def _compute_stability(self, dimensions: np.ndarray) -> float:
        """
        计算稳定性

        基于支撑面积与重心高度的比值。
        公式: stability = clamp(support_area / (cog_height + eps))
        """
        # 底部面积 = 长 × 宽（假设 z 轴为高度方向）
        bottom_area = dimensions[0] * dimensions[1]
        max_reference_area = 0.25  # 0.5m × 0.5m
        norm_area = min(1.0, bottom_area / max_reference_area)

        # 重心高度（假设几何中心）
        cog_height = dimensions[2] / 2.0
        norm_height = min(1.0, cog_height / 0.3)

        stability = norm_area / (norm_height + 0.1)
        return min(1.0, max(0.0, stability))

    def _compute_roll_tendency(self, object_type: str,
                                dimensions: np.ndarray,
                                orientation: Tuple[float, ...]) -> float:
        """
        计算滚动倾向

        基于形状类型（球 > 圆柱 > 立方）和当前朝向。
        """
        # 基础滚动倾向
        base_tendency_map = {
            'sphere': 0.9,
            'cylinder': 0.6,
            'cube': 0.1,
            'bowl': 0.4,
            'bottle': 0.5,
            'plate': 0.3,
            'default': 0.3,
        }
        base = base_tendency_map.get(object_type, 0.3)

        # 圆柱体：侧放时滚动倾向显著提高
        if object_type == 'cylinder':
            roll, pitch, _ = self._quat_to_euler(orientation)
            if abs(roll) > 0.7 or abs(pitch) > 0.7:
                base = 0.85

        # 长宽比修正
        min_hw = min(dimensions[0], dimensions[1])
        aspect = max(dimensions[0], dimensions[1]) / (min_hw + 0.001)
        shape_bonus = min(0.3, max(0, (aspect - 1.0) * 0.15))

        return min(1.0, base + shape_bonus)

    def _compute_strength_needed(self, mass: float, object_type: str) -> float:
        """
        计算所需抓取力

        质量越大、表面越光滑 → 需要更大的力。
        """
        mass_factor = min(1.0, mass / self.max_payload) if self.max_payload > 0 else 0.5

        # 表面修正：光滑表面更费力
        surface_bonus = {
            'sphere': 0.25,      # 球面——最小接触面积
            'cylinder': 0.15,
            'cube': 0.05,        # 平面——容易抓
            'bowl': -0.05,       # 有凹陷——容易抓
            'bottle': 0.10,
            'plate': 0.15,
            'default': 0.10,
        }.get(object_type, 0.10)

        return min(1.0, max(0.0, mass_factor + surface_bonus))

    def _compute_fragility(self, object_type: str, mass: float) -> float:
        """计算脆弱性（基于类型先验 + 质量修正）"""
        base_fragility = {
            'cube': 0.20,
            'sphere': 0.25,
            'cylinder': 0.30,
            'bowl': 0.60,
            'bottle': 0.70,
            'plate': 0.80,
            'default': 0.40,
        }.get(object_type, 0.40)

        mass_bonus = min(0.2, mass / self.max_payload * 0.2) if self.max_payload > 0 else 0
        return min(1.0, base_fragility + mass_bonus)

    def _compute_reachability(self, object_id: int,
                               position: Tuple[float, ...],
                               target_position: Optional[List[float]]) -> float:
        """计算可达性（基于距离 + 路径碰撞检测）"""
        if target_position is None:
            return 0.8

        distance = np.linalg.norm(np.array(position[:2]) - np.array(target_position[:2]))
        max_dist = 0.5
        distance_factor = max(0.0, 1.0 - distance / max_dist) if distance < max_dist else 0.0

        # TODO: 在完整仿真环境中用 rayTest 做碰撞检测
        return min(1.0, distance_factor + 0.2)

    def _compute_grasp_surface_quality(self, object_type: str) -> float:
        """计算抓取表面质量"""
        return {
            'cube': 0.70,
            'sphere': 0.50,
            'cylinder': 0.60,
            'bowl': 0.80,
            'bottle': 0.55,
            'plate': 0.40,
            'default': 0.50,
        }.get(object_type, 0.50)

    def _compute_support_area(self, dimensions: np.ndarray) -> float:
        """计算支撑面积（归一化）"""
        bottom_area = dimensions[0] * dimensions[1]
        return min(1.0, bottom_area / 0.25)

    def _compute_occlusion(self, object_id: int,
                            position: Tuple[float, ...]) -> float:
        """计算遮挡程度（简化为射线检测）"""
        try:
            import pybullet as p
            camera_pos = [0.5, 0.0, 1.0]
            ray = p.rayTest(camera_pos, position, self.client_id)
            if ray and ray[0][0] not in (-1, object_id):
                return 0.7  # 有遮挡
        except Exception:
            pass
        return 0.1  # 无遮挡

    def _compute_obstacle_density(self, position: Tuple[float, ...],
                                   obstacles_ids: Optional[List[int]]) -> float:
        """计算周围障碍物密度"""
        if not obstacles_ids:
            return 0.0

        import pybullet as p
        density = 0.0
        radius = 0.3
        for obs_id in obstacles_ids:
            try:
                obs_pos, _ = p.getBasePositionAndOrientation(obs_id, self.client_id)
                dist = np.linalg.norm(np.array(position[:2]) - np.array(obs_pos[:2]))
                if dist < radius:
                    density += (1.0 - dist / radius)
            except Exception:
                continue

        return min(1.0, density / 3.0)

    def _compute_visibility(self, object_type: str) -> float:
        """计算可见性（基于物体类型先验）"""
        return {
            'cube': 0.70,
            'sphere': 0.65,
            'cylinder': 0.60,
            'bowl': 0.50,
            'bottle': 0.50,
            'plate': 0.40,
            'default': 0.50,
        }.get(object_type, 0.50)

    def _compute_deformability(self, object_type: str) -> float:
        """计算变形能力"""
        return {
            'cube': 0.10,
            'sphere': 0.10,
            'cylinder': 0.15,
            'bowl': 0.20,
            'bottle': 0.30,
            'plate': 0.15,
            'default': 0.20,
        }.get(object_type, 0.20)

    @staticmethod
    def _quat_to_euler(orientation: Tuple[float, ...]) -> Tuple[float, float, float]:
        """四元数转欧拉角 (roll, pitch, yaw)"""
        x, y, z, w = orientation
        roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        pitch = math.asin(2 * (w * y - z * x))
        yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        return roll, pitch, yaw
