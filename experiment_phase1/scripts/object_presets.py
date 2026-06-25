#!/usr/bin/env python3
"""
YLYW 灵犀X2 灵巧手抓取实物验证 — 物体预设特征值

8类物体 × 每类2-3个实例的13维物理特征。
这些值基于实验方案文档中的物体规格定义，
由仿真物体生成器产生典型特征值。

Phase 1（无摄像头）使用这些预设值直接输入 YLYW 推理引擎。
后续 Phase 2 接入深度相机后替换为实时视觉提取。

特征维度说明:
  0: stability         稳定性 (越大越稳)
  1: roll_tendency     滚动倾向 (越大越容易滚)
  2: strength_needed   所需抓取力 (越大需要越大力)
  3: fragility         脆弱性 (越大越脆)
  4: reachability      可达性 (越大越容易够到)
  5: grasp_surface_quality  抓取表面质量 (越大越粗糙/容易抓)
  6: support_area      支撑面积 (越大底面越大)
  7: occlusion         遮挡程度 (越大遮挡越严重)
  8: obstacle_density  障碍密度
  9: task_priority     任务优先级
  10: weight_ratio     重量比
  11: visibility       可见性
  12: deformability    变形能力
"""

# ============================================================
# 物体预设特征值
# ============================================================
OBJECT_PRESETS = {
    # ========== 球体 ==========
    "tennis_ball": {
        "name": "网球",
        "type": "sphere",
        "features": {
            'stability': 0.25,
            'roll_tendency': 0.95,
            'strength_needed': 0.15,
            'fragility': 0.20,
            'reachability': 0.85,
            'grasp_surface_quality': 0.75,
            'support_area': 0.10,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.10,
            'visibility': 0.95,
            'deformability': 0.40,
        },
    },
    "pingpong_ball": {
        "name": "乒乓球",
        "type": "sphere",
        "features": {
            'stability': 0.20,
            'roll_tendency': 0.98,
            'strength_needed': 0.08,
            'fragility': 0.70,
            'reachability': 0.82,
            'grasp_surface_quality': 0.35,
            'support_area': 0.05,
            'occlusion': 0.02,
            'obstacle_density': 0.05,
            'task_priority': 0.50,
            'weight_ratio': 0.03,
            'visibility': 0.98,
            'deformability': 0.30,
        },
    },
    "golf_ball": {
        "name": "高尔夫球",
        "type": "sphere",
        "features": {
            'stability': 0.28,
            'roll_tendency': 0.90,
            'strength_needed': 0.20,
            'fragility': 0.15,
            'reachability': 0.88,
            'grasp_surface_quality': 0.60,
            'support_area': 0.08,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.12,
            'visibility': 0.95,
            'deformability': 0.10,
        },
    },

    # ========== 立方体 ==========
    "wooden_block": {
        "name": "木块",
        "type": "cube",
        "features": {
            'stability': 0.85,
            'roll_tendency': 0.05,
            'strength_needed': 0.40,
            'fragility': 0.15,
            'reachability': 0.80,
            'grasp_surface_quality': 0.70,
            'support_area': 0.70,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.30,
            'visibility': 0.90,
            'deformability': 0.05,
        },
    },
    "metal_cube": {
        "name": "金属方块",
        "type": "cube",
        "features": {
            'stability': 0.90,
            'roll_tendency': 0.03,
            'strength_needed': 0.70,
            'fragility': 0.05,
            'reachability': 0.78,
            'grasp_surface_quality': 0.45,
            'support_area': 0.75,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.60,
            'visibility': 0.90,
            'deformability': 0.02,
        },
    },

    # ========== 圆柱体 ==========
    "soda_can": {
        "name": "易拉罐",
        "type": "cylinder",
        "features": {
            'stability': 0.55,
            'roll_tendency': 0.70,
            'strength_needed': 0.25,
            'fragility': 0.35,
            'reachability': 0.75,
            'grasp_surface_quality': 0.50,
            'support_area': 0.30,
            'occlusion': 0.08,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.18,
            'visibility': 0.92,
            'deformability': 0.55,
        },
    },
    "water_bottle": {
        "name": "矿泉水瓶",
        "type": "cylinder",
        "features": {
            'stability': 0.40,
            'roll_tendency': 0.75,
            'strength_needed': 0.30,
            'fragility': 0.40,
            'reachability': 0.72,
            'grasp_surface_quality': 0.40,
            'support_area': 0.25,
            'occlusion': 0.08,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.22,
            'visibility': 0.92,
            'deformability': 0.60,
        },
    },

    # ========== 碗 ==========
    "plastic_bowl": {
        "name": "塑料碗",
        "type": "bowl",
        "features": {
            'stability': 0.65,
            'roll_tendency': 0.15,
            'strength_needed': 0.15,
            'fragility': 0.30,
            'reachability': 0.70,
            'grasp_surface_quality': 0.55,
            'support_area': 0.60,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.12,
            'visibility': 0.95,
            'deformability': 0.25,
        },
    },
    "ceramic_bowl": {
        "name": "陶瓷碗",
        "type": "bowl",
        "features": {
            'stability': 0.70,
            'roll_tendency': 0.10,
            'strength_needed': 0.35,
            'fragility': 0.75,
            'reachability': 0.68,
            'grasp_surface_quality': 0.35,
            'support_area': 0.55,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.28,
            'visibility': 0.95,
            'deformability': 0.05,
        },
    },

    # ========== 瓶子 ==========
    "glass_bottle": {
        "name": "玻璃瓶",
        "type": "bottle",
        "features": {
            'stability': 0.45,
            'roll_tendency': 0.65,
            'strength_needed': 0.35,
            'fragility': 0.85,
            'reachability': 0.70,
            'grasp_surface_quality': 0.25,
            'support_area': 0.20,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.30,
            'visibility': 0.90,
            'deformability': 0.02,
        },
    },
    "plastic_bottle": {
        "name": "塑料瓶",
        "type": "bottle",
        "features": {
            'stability': 0.42,
            'roll_tendency': 0.68,
            'strength_needed': 0.20,
            'fragility': 0.40,
            'reachability': 0.72,
            'grasp_surface_quality': 0.45,
            'support_area': 0.22,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.15,
            'visibility': 0.90,
            'deformability': 0.55,
        },
    },

    # ========== 盘子 ==========
    "ceramic_plate": {
        "name": "瓷盘",
        "type": "plate",
        "features": {
            'stability': 0.80,
            'roll_tendency': 0.05,
            'strength_needed': 0.25,
            'fragility': 0.70,
            'reachability': 0.75,
            'grasp_surface_quality': 0.30,
            'support_area': 0.85,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.20,
            'visibility': 0.95,
            'deformability': 0.02,
        },
    },
    "plastic_plate": {
        "name": "塑料盘",
        "type": "plate",
        "features": {
            'stability': 0.82,
            'roll_tendency': 0.04,
            'strength_needed': 0.12,
            'fragility': 0.25,
            'reachability': 0.78,
            'grasp_surface_quality': 0.50,
            'support_area': 0.88,
            'occlusion': 0.05,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.08,
            'visibility': 0.95,
            'deformability': 0.30,
        },
    },

    # ========== 石块 ==========
    "irregular_rock": {
        "name": "不规则石块",
        "type": "rock",
        "features": {
            'stability': 0.55,
            'roll_tendency': 0.40,
            'strength_needed': 0.65,
            'fragility': 0.05,
            'reachability': 0.65,
            'grasp_surface_quality': 0.80,
            'support_area': 0.35,
            'occlusion': 0.15,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.55,
            'visibility': 0.85,
            'deformability': 0.02,
        },
    },
    "smooth_stone": {
        "name": "光滑卵石",
        "type": "rock",
        "features": {
            'stability': 0.45,
            'roll_tendency': 0.55,
            'strength_needed': 0.50,
            'fragility': 0.08,
            'reachability': 0.68,
            'grasp_surface_quality': 0.25,
            'support_area': 0.25,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.42,
            'visibility': 0.88,
            'deformability': 0.02,
        },
    },

    # ========== 花瓶 ==========
    "ceramic_vase": {
        "name": "陶瓷花瓶",
        "type": "vase",
        "features": {
            'stability': 0.50,
            'roll_tendency': 0.45,
            'strength_needed': 0.30,
            'fragility': 0.90,
            'reachability': 0.65,
            'grasp_surface_quality': 0.30,
            'support_area': 0.28,
            'occlusion': 0.08,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.25,
            'visibility': 0.92,
            'deformability': 0.02,
        },
    },
    "glass_vase": {
        "name": "玻璃花瓶",
        "type": "vase",
        "features": {
            'stability': 0.48,
            'roll_tendency': 0.48,
            'strength_needed': 0.28,
            'fragility': 0.95,
            'reachability': 0.62,
            'grasp_surface_quality': 0.20,
            'support_area': 0.25,
            'occlusion': 0.10,
            'obstacle_density': 0.10,
            'task_priority': 0.50,
            'weight_ratio': 0.22,
            'visibility': 0.90,
            'deformability': 0.01,
        },
    },
}

# ============================================================
# 策略→手指参数映射
# ============================================================
STRATEGY_FINGER_PARAMS = {
    "power_grasp": {
        "description": "全掌包覆抓取 (乾)",
        "position": 0.0, "velocity": 1.0, "effort": 0.85,
    },
    "precise_pick": {
        "description": "指尖精确捏取 (坤)",
        "position": 0.0, "velocity": 0.3, "effort": 0.25,
    },
    "dynamic_grasp": {
        "description": "快速动态抓取 (震)",
        "position": 0.0, "velocity": 1.0, "effort": 0.70,
    },
    "cautious_grasp": {
        "description": "谨慎缓慢抓取 (履)",
        "position": 0.0, "velocity": 0.2, "effort": 0.30,
    },
    "adaptive_grasp": {
        "description": "异形自适应抓取 (睽)",
        "position": 0.0, "velocity": 0.5, "effort": 0.50,
    },
    "wrap_grasp": {
        "description": "环绕包络抓取 (随)",
        "position": 0.0, "velocity": 0.8, "effort": 0.60,
    },
    "incremental_grasp": {
        "description": "渐进夹紧抓取 (渐)",
        "position": 0.0, "velocity": 0.3, "effort": 0.40,
    },
    "conditional_grasp": {
        "description": "条件判断抓取 (需)",
        "position": 0.0, "velocity": 0.5, "effort": 0.50,
    },
    # 扩展策略
    "gentle_grasp": {
        "description": "轻柔抓取",
        "position": 0.0, "velocity": 0.15, "effort": 0.20,
    },
    "forceful_grasp": {
        "description": "强力抓取",
        "position": 0.0, "velocity": 1.0, "effort": 0.95,
    },
    "non_conflict_grasp": {
        "description": "无冲突抓取",
        "position": 0.0, "velocity": 0.5, "effort": 0.50,
    },
    "following_grasp": {
        "description": "跟随抓取",
        "position": 0.0, "velocity": 0.6, "effort": 0.55,
    },
    "direct_grasp": {
        "description": "直接抓取",
        "position": 0.0, "velocity": 0.7, "effort": 0.65,
    },
}


def get_all_objects():
    """获取所有物体预设"""
    return list(OBJECT_PRESETS.items())


def get_objects_by_type(obj_type: str):
    """按类型获取物体"""
    return [(k, v) for k, v in OBJECT_PRESETS.items() if v['type'] == obj_type]


def list_object_types():
    """列出所有物体类型及实例"""
    types = {}
    for key, obj in OBJECT_PRESETS.items():
        t = obj['type']
        if t not in types:
            types[t] = []
        types[t].append(f"{key} ({obj['name']})")

    print("=" * 60)
    print("  YLYW 抓取实验 — 物体预设库")
    print("=" * 60)
    for t, items in sorted(types.items()):
        print(f"\n  [{t}] ({len(items)}个实例)")
        for item in items:
            print(f"    • {item}")
    print(f"\n  总计: {len(OBJECT_PRESETS)} 个物体实例, {len(types)} 种类型")


def get_feature_dict(obj_key: str) -> dict:
    """获取某物体的13维特征dict"""
    if obj_key not in OBJECT_PRESETS:
        raise KeyError(f"未知物体: {obj_key}. 可用: {list(OBJECT_PRESETS.keys())}")
    return OBJECT_PRESETS[obj_key]['features'].copy()


if __name__ == '__main__':
    list_object_types()
