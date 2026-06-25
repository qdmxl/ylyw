# 
# 追加物体（Phase 3 扩展到 50 个物体）
# 每类从 2-3 个扩展到 6-7 个
#

_EXTENDED_PRESETS = {
    # ========== 球体扩展 ==========
    "rubber_ball": {
        "name": "橡胶球",
        "type": "sphere",
        "features": {
            'stability': 0.22, 'roll_tendency': 0.93, 'strength_needed': 0.18,
            'fragility': 0.15, 'reachability': 0.88, 'grasp_surface_quality': 0.65,
            'support_area': 0.08, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.12, 'visibility': 0.95,
            'deformability': 0.45,
        },
    },
    "marble": {
        "name": "玻璃弹珠",
        "type": "sphere",
        "features": {
            'stability': 0.18, 'roll_tendency': 0.99, 'strength_needed': 0.10,
            'fragility': 0.55, 'reachability': 0.90, 'grasp_surface_quality': 0.15,
            'support_area': 0.03, 'occlusion': 0.02, 'obstacle_density': 0.05,
            'task_priority': 0.50, 'weight_ratio': 0.05, 'visibility': 0.98,
            'deformability': 0.02,
        },
    },
    "steel_ball": {
        "name": "钢球",
        "type": "sphere",
        "features": {
            'stability': 0.22, 'roll_tendency': 0.95, 'strength_needed': 0.55,
            'fragility': 0.02, 'reachability': 0.85, 'grasp_surface_quality': 0.10,
            'support_area': 0.08, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.45, 'visibility': 0.95,
            'deformability': 0.01,
        },
    },
    "foam_ball": {
        "name": "泡沫球",
        "type": "sphere",
        "features": {
            'stability': 0.30, 'roll_tendency': 0.85, 'strength_needed': 0.05,
            'fragility': 0.92, 'reachability': 0.82, 'grasp_surface_quality': 0.50,
            'support_area': 0.12, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.02, 'visibility': 0.95,
            'deformability': 0.90,
        },
    },
    "beach_ball": {
        "name": "沙滩球",
        "type": "sphere",
        "features": {
            'stability': 0.10, 'roll_tendency': 0.99, 'strength_needed': 0.02,
            'fragility': 0.10, 'reachability': 0.92, 'grasp_surface_quality': 0.80,
            'support_area': 0.02, 'occlusion': 0.02, 'obstacle_density': 0.05,
            'task_priority': 0.50, 'weight_ratio': 0.01, 'visibility': 0.99,
            'deformability': 0.95,
        },
    },

    # ========== 立方体扩展 ==========
    "plastic_block": {
        "name": "塑料积木",
        "type": "cube",
        "features": {
            'stability': 0.88, 'roll_tendency': 0.04, 'strength_needed': 0.20,
            'fragility': 0.22, 'reachability': 0.82, 'grasp_surface_quality': 0.55,
            'support_area': 0.72, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.15, 'visibility': 0.92,
            'deformability': 0.20,
        },
    },
    "rubber_cube": {
        "name": "橡皮块",
        "type": "cube",
        "features": {
            'stability': 0.82, 'roll_tendency': 0.06, 'strength_needed': 0.25,
            'fragility': 0.18, 'reachability': 0.80, 'grasp_surface_quality': 0.72,
            'support_area': 0.68, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.18, 'visibility': 0.92,
            'deformability': 0.35,
        },
    },
    "foam_cube": {
        "name": "泡沫块",
        "type": "cube",
        "features": {
            'stability': 0.85, 'roll_tendency': 0.03, 'strength_needed': 0.08,
            'fragility': 0.88, 'reachability': 0.82, 'grasp_surface_quality': 0.55,
            'support_area': 0.75, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.04, 'visibility': 0.92,
            'deformability': 0.88,
        },
    },
    "hardwood_block": {
        "name": "硬木块",
        "type": "cube",
        "features": {
            'stability': 0.90, 'roll_tendency': 0.04, 'strength_needed': 0.45,
            'fragility': 0.10, 'reachability': 0.80, 'grasp_surface_quality': 0.65,
            'support_area': 0.75, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.35, 'visibility': 0.90,
            'deformability': 0.04,
        },
    },

    # ========== 圆柱体扩展 ==========
    "coffee_can": {
        "name": "咖啡罐",
        "type": "cylinder",
        "features": {
            'stability': 0.58, 'roll_tendency': 0.68, 'strength_needed': 0.30,
            'fragility': 0.25, 'reachability': 0.75, 'grasp_surface_quality': 0.55,
            'support_area': 0.32, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.25, 'visibility': 0.92,
            'deformability': 0.40,
        },
    },
    "spray_can": {
        "name": "喷雾罐",
        "type": "cylinder",
        "features": {
            'stability': 0.52, 'roll_tendency': 0.72, 'strength_needed': 0.22,
            'fragility': 0.28, 'reachability': 0.72, 'grasp_surface_quality': 0.35,
            'support_area': 0.28, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.18, 'visibility': 0.92,
            'deformability': 0.45,
        },
    },
    "candle": {
        "name": "蜡烛",
        "type": "cylinder",
        "features": {
            'stability': 0.38, 'roll_tendency': 0.70, 'strength_needed': 0.12,
            'fragility': 0.70, 'reachability': 0.78, 'grasp_surface_quality': 0.30,
            'support_area': 0.22, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.08, 'visibility': 0.94,
            'deformability': 0.65,
        },
    },
    "glass_jar": {
        "name": "玻璃罐",
        "type": "cylinder",
        "features": {
            'stability': 0.55, 'roll_tendency': 0.65, 'strength_needed': 0.38,
            'fragility': 0.80, 'reachability': 0.70, 'grasp_surface_quality': 0.20,
            'support_area': 0.30, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.32, 'visibility': 0.90,
            'deformability': 0.02,
        },
    },

    # ========== 碗扩展 ==========
    "metal_bowl": {
        "name": "金属碗",
        "type": "bowl",
        "features": {
            'stability': 0.72, 'roll_tendency': 0.12, 'strength_needed': 0.28,
            'fragility': 0.10, 'reachability': 0.70, 'grasp_surface_quality': 0.30,
            'support_area': 0.58, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.20, 'visibility': 0.95,
            'deformability': 0.10,
        },
    },
    "glass_bowl": {
        "name": "玻璃碗",
        "type": "bowl",
        "features": {
            'stability': 0.68, 'roll_tendency': 0.14, 'strength_needed': 0.32,
            'fragility': 0.82, 'reachability': 0.68, 'grasp_surface_quality': 0.18,
            'support_area': 0.55, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.26, 'visibility': 0.95,
            'deformability': 0.02,
        },
    },
    "wooden_bowl": {
        "name": "木碗",
        "type": "bowl",
        "features": {
            'stability': 0.74, 'roll_tendency': 0.10, 'strength_needed': 0.22,
            'fragility': 0.20, 'reachability': 0.72, 'grasp_surface_quality': 0.62,
            'support_area': 0.60, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.15, 'visibility': 0.95,
            'deformability': 0.08,
        },
    },
    "ceramic_soup_bowl": {
        "name": "陶瓷汤碗",
        "type": "bowl",
        "features": {
            'stability': 0.68, 'roll_tendency': 0.12, 'strength_needed': 0.35,
            'fragility': 0.75, 'reachability': 0.70, 'grasp_surface_quality': 0.22,
            'support_area': 0.56, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.28, 'visibility': 0.95,
            'deformability': 0.03,
        },
    },

    # ========== 瓶子扩展 ==========
    "wine_bottle": {
        "name": "酒瓶",
        "type": "bottle",
        "features": {
            'stability': 0.48, 'roll_tendency': 0.60, 'strength_needed': 0.45,
            'fragility': 0.75, 'reachability': 0.68, 'grasp_surface_quality': 0.22,
            'support_area': 0.18, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.38, 'visibility': 0.90,
            'deformability': 0.02,
        },
    },
    "pill_bottle": {
        "name": "药瓶",
        "type": "bottle",
        "features": {
            'stability': 0.52, 'roll_tendency': 0.55, 'strength_needed': 0.15,
            'fragility': 0.35, 'reachability': 0.78, 'grasp_surface_quality': 0.45,
            'support_area': 0.25, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.10, 'visibility': 0.94,
            'deformability': 0.30,
        },
    },
    "perfume_bottle": {
        "name": "香水瓶",
        "type": "bottle",
        "features": {
            'stability': 0.42, 'roll_tendency': 0.58, 'strength_needed': 0.20,
            'fragility': 0.88, 'reachability': 0.72, 'grasp_surface_quality': 0.18,
            'support_area': 0.20, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.15, 'visibility': 0.92,
            'deformability': 0.02,
        },
    },
    "thermos": {
        "name": "保温瓶",
        "type": "bottle",
        "features": {
            'stability': 0.50, 'roll_tendency': 0.52, 'strength_needed': 0.42,
            'fragility': 0.25, 'reachability': 0.70, 'grasp_surface_quality': 0.40,
            'support_area': 0.28, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.35, 'visibility': 0.90,
            'deformability': 0.15,
        },
    },

    # ========== 盘子扩展 ==========
    "paper_plate": {
        "name": "纸盘",
        "type": "plate",
        "features": {
            'stability': 0.78, 'roll_tendency': 0.05, 'strength_needed': 0.08,
            'fragility': 0.40, 'reachability': 0.80, 'grasp_surface_quality': 0.55,
            'support_area': 0.88, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.03, 'visibility': 0.96,
            'deformability': 0.50,
        },
    },
    "metal_plate": {
        "name": "金属盘",
        "type": "plate",
        "features": {
            'stability': 0.85, 'roll_tendency': 0.03, 'strength_needed': 0.30,
            'fragility': 0.12, 'reachability': 0.75, 'grasp_surface_quality': 0.25,
            'support_area': 0.85, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.22, 'visibility': 0.95,
            'deformability': 0.04,
        },
    },
    "wooden_plate": {
        "name": "木盘",
        "type": "plate",
        "features": {
            'stability': 0.84, 'roll_tendency': 0.04, 'strength_needed': 0.18,
            'fragility': 0.18, 'reachability': 0.76, 'grasp_surface_quality': 0.58,
            'support_area': 0.86, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.12, 'visibility': 0.95,
            'deformability': 0.06,
        },
    },
    "glass_plate": {
        "name": "玻璃盘",
        "type": "plate",
        "features": {
            'stability': 0.82, 'roll_tendency': 0.04, 'strength_needed': 0.26,
            'fragility': 0.82, 'reachability': 0.74, 'grasp_surface_quality': 0.12,
            'support_area': 0.86, 'occlusion': 0.05, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.18, 'visibility': 0.95,
            'deformability': 0.02,
        },
    },

    # ========== 石块扩展 ==========
    "brick_fragment": {
        "name": "砖块碎片",
        "type": "rock",
        "features": {
            'stability': 0.60, 'roll_tendency': 0.35, 'strength_needed': 0.55,
            'fragility': 0.08, 'reachability': 0.68, 'grasp_surface_quality': 0.72,
            'support_area': 0.40, 'occlusion': 0.12, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.48, 'visibility': 0.88,
            'deformability': 0.02,
        },
    },
    "pumice": {
        "name": "浮石",
        "type": "rock",
        "features": {
            'stability': 0.48, 'roll_tendency': 0.42, 'strength_needed': 0.25,
            'fragility': 0.30, 'reachability': 0.70, 'grasp_surface_quality': 0.68,
            'support_area': 0.32, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.18, 'visibility': 0.90,
            'deformability': 0.15,
        },
    },
    "gravel": {
        "name": "碎石块",
        "type": "rock",
        "features": {
            'stability': 0.42, 'roll_tendency': 0.55, 'strength_needed': 0.40,
            'fragility': 0.05, 'reachability': 0.72, 'grasp_surface_quality': 0.75,
            'support_area': 0.28, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.30, 'visibility': 0.90,
            'deformability': 0.02,
        },
    },
    "quartz": {
        "name": "石英块",
        "type": "rock",
        "features": {
            'stability': 0.52, 'roll_tendency': 0.38, 'strength_needed': 0.48,
            'fragility': 0.06, 'reachability': 0.68, 'grasp_surface_quality': 0.20,
            'support_area': 0.35, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.40, 'visibility': 0.88,
            'deformability': 0.01,
        },
    },

    # ========== 花瓶扩展 ==========
    "porcelain_vase": {
        "name": "瓷花瓶",
        "type": "vase",
        "features": {
            'stability': 0.52, 'roll_tendency': 0.42, 'strength_needed': 0.28,
            'fragility': 0.88, 'reachability': 0.65, 'grasp_surface_quality': 0.25,
            'support_area': 0.26, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.22, 'visibility': 0.92,
            'deformability': 0.02,
        },
    },
    "clay_vase": {
        "name": "陶土花瓶",
        "type": "vase",
        "features": {
            'stability': 0.54, 'roll_tendency': 0.40, 'strength_needed': 0.32,
            'fragility': 0.72, 'reachability': 0.64, 'grasp_surface_quality': 0.42,
            'support_area': 0.30, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.28, 'visibility': 0.92,
            'deformability': 0.05,
        },
    },
    "metal_vase": {
        "name": "金属花瓶",
        "type": "vase",
        "features": {
            'stability': 0.56, 'roll_tendency': 0.38, 'strength_needed': 0.38,
            'fragility': 0.10, 'reachability': 0.66, 'grasp_surface_quality': 0.30,
            'support_area': 0.28, 'occlusion': 0.08, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.30, 'visibility': 0.92,
            'deformability': 0.04,
        },
    },
    "crystal_vase": {
        "name": "水晶花瓶",
        "type": "vase",
        "features": {
            'stability': 0.48, 'roll_tendency': 0.46, 'strength_needed': 0.34,
            'fragility': 0.85, 'reachability': 0.62, 'grasp_surface_quality': 0.12,
            'support_area': 0.24, 'occlusion': 0.10, 'obstacle_density': 0.10,
            'task_priority': 0.50, 'weight_ratio': 0.26, 'visibility': 0.90,
            'deformability': 0.01,
        },
    },
}

from scripts.object_presets import OBJECT_PRESETS

OBJECT_PRESETS.update(_EXTENDED_PRESETS)
