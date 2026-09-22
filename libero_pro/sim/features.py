#!/usr/bin/env python3
"""
仿真观测 → YLYW 13 维物理特征

真·LIBERO-PRO 阶段这本应由视觉模型估计；本机阶段一直接从 MuJoCo 真值推导，
聚焦"推理层"验证（隔离视觉估计噪声这一变量）。

PriorManual 特征 schema：
  必需 6 项：stability, roll_tendency, strength_needed, fragility,
             task_priority, reachability
  可选 7 项：support_area, occlusion, obstacle_density,
             grasp_surface_quality, weight_ratio, visibility, deformability
"""

import numpy as np

REQUIRED = ["stability", "roll_tendency", "strength_needed",
            "fragility", "task_priority", "reachability"]
OPTIONAL = ["support_area", "occlusion", "obstacle_density",
            "grasp_surface_quality", "weight_ratio", "visibility", "deformability"]


def _clip(x, lo=0.0, hi=1.0):
    return float(min(max(x, lo), hi))


def extract_features(state: dict) -> dict:
    """从仿真状态字典提取 YLYW 13 维特征。

    Args:
        state: {
            'obj_pos': (3,), 'obj_size': float, 'obj_mass': float,
            'obj_shape': str,           # sphere/box/cylinder/rod
            'ee_pos': (3,), 'target_pos': (3,),
            'n_obstacles': int, 'gripper_open': float,
            'task_priority': float,     # 由任务语义给
            'occlusion': float, 'visibility': float,   # 由视觉层给（阶段一给真值）
        }
    """
    obj_pos = np.asarray(state["obj_pos"], dtype=float)
    ee_pos = np.asarray(state["ee_pos"], dtype=float)
    target_pos = np.asarray(state["target_pos"], dtype=float)
    size = float(state["obj_size"])
    mass = float(state["obj_mass"])
    shape = state.get("obj_shape", "box")

    # 稳定性：支撑面越大 / 重心越低 越稳
    base_stability = {"sphere": 0.25, "cylinder": 0.6, "rod": 0.15,
                      "box": 0.85}.get(shape, 0.5)
    stability = _clip(base_stability - 0.3 * (size - 0.05))

    # 滚动倾向：球形/柱形高，方块低
    roll = {"sphere": 0.9, "cylinder": 0.7, "rod": 0.8, "box": 0.05}.get(shape, 0.5)
    roll_tendency = _clip(roll + 0.2 * (1.0 - stability))

    # 所需抓取力：质量越大越需力
    strength_needed = _clip(mass / 0.1)

    # 脆弱性：小尺寸 / 薄件 更脆
    fragility = _clip(1.0 - size / 0.08)

    # 可达性：末端到物体距离越近越高
    dist = float(np.linalg.norm(obj_pos - ee_pos))
    reachability = _clip(1.0 - dist / 0.5)

    # 任务优先级：外部给定（语义扰动会改）
    task_priority = _clip(state.get("task_priority", 0.5))

    # 可选 7 项
    support_area = stability
    occlusion = _clip(state.get("occlusion", 0.1))
    obstacle_density = _clip(state.get("n_obstacles", 0) / 5.0)
    grasp_surface_quality = _clip(0.4 + 0.5 * (1.0 - fragility))
    weight_ratio = _clip(mass / 0.2)
    visibility = _clip(state.get("visibility", 0.95))
    deformability = 0.0  # 阶段一物体均为刚体

    feats = {
        "stability": stability,
        "roll_tendency": roll_tendency,
        "strength_needed": strength_needed,
        "fragility": fragility,
        "task_priority": task_priority,
        "reachability": reachability,
        "support_area": support_area,
        "occlusion": occlusion,
        "obstacle_density": obstacle_density,
        "grasp_surface_quality": grasp_surface_quality,
        "weight_ratio": weight_ratio,
        "visibility": visibility,
        "deformability": deformability,
    }
    assert all(0.0 <= feats[k] <= 1.0 for k in REQUIRED), feats
    return feats


if __name__ == "__main__":
    demo = {
        "obj_pos": [0.3, 0.1, 0.05], "obj_size": 0.05, "obj_mass": 0.03,
        "obj_shape": "sphere", "ee_pos": [0.2, 0.0, 0.1],
        "target_pos": [0.3, 0.1, 0.05], "n_obstacles": 1,
        "gripper_open": 1.0, "task_priority": 0.8,
    }
    f = extract_features(demo)
    for k, v in f.items():
        print(f"  {k:24s} {v:.3f}")
