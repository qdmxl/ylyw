#!/usr/bin/env python3
"""
YLYW 策略映射模块 (Strategy Mapping)

将 YLYW 推理引擎的 64 卦策略映射为：
  1. 灵巧手关节参数（NIMBLE_HANDS 10指 + Gripper 模式）
  2. 抓取质量评分规则
  3. 物体类型→推荐策略白名单

这是"卦象→物理动作"的最后一公里。
每一卦象都有一个预定义的"最佳手指姿态"，源自易经的工程化转译。

用法:
    from strategy_mapping import StrategyMapper
    mapper = StrategyMapper()
    finger_params = mapper.get_finger_params("dynamic_grasp", force=0.65)
"""

import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================
# 灵巧手关节策略参数
# ============================================================
# NIMBLE_HANDS: 每只手10个自由度
# thumb(3电机), index(2电机), middle(2电机), ring(2电机), pinky(1电机)
# 另有对掌/侧摆自由度，简化表示

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]
FINGER_JOINT_COUNT = {"thumb": 3, "index": 2, "middle": 2, "ring": 2, "pinky": 1}


@dataclass
class FingerParams:
    """单指控制参数"""
    position: float = 0.0   # 闭合程度 [0=全闭, 1=全开]
    velocity: float = 0.5   # 闭合速度 [0, 1]
    effort: float = 0.5     # 力矩限制 [0, 1]


@dataclass
class HandStrategy:
    """完整灵巧手策略"""
    name: str
    description: str
    hexagram_source: str       # 来源卦象
    fingers: Dict[str, FingerParams] = field(default_factory=dict)
    approach_angle: float = 0  # 手腕接近角度 (deg)
    approach_speed: str = "medium"  # slow/medium/fast
    pre_grasp_open: float = 1.0    # 预张开程度
    cautions: List[str] = field(default_factory=list)


# ============================================================
# 64卦 → 灵巧手策略参数映射
# ============================================================
STRATEGY_HAND_MAP: Dict[str, HandStrategy] = {
    # ──────────── 乾坤系（强力/精确）────────────
    "power_grasp": HandStrategy(
        name="power_grasp",
        description="全掌包覆强力抓取（乾为天）",
        hexagram_source="乾为天 ☰☰",
        fingers={
            "thumb":  FingerParams(0.0, 1.0, 0.85),
            "index":  FingerParams(0.0, 1.0, 0.85),
            "middle": FingerParams(0.0, 1.0, 0.85),
            "ring":   FingerParams(0.0, 1.0, 0.85),
            "pinky":  FingerParams(0.0, 1.0, 0.85),
        },
        approach_speed="fast",
        cautions=["确保抓取稳定", "监控力矩不超限"],
    ),
    "robust_power_grasp": HandStrategy(
        name="robust_power_grasp",
        description="强力稳健抓取（雷天大壮）",
        hexagram_source="雷天大壮 ☳☰",
        fingers={
            "thumb":  FingerParams(0.0, 0.9, 0.80),
            "index":  FingerParams(0.0, 0.9, 0.80),
            "middle": FingerParams(0.0, 0.9, 0.80),
            "ring":   FingerParams(0.0, 0.9, 0.80),
            "pinky":  FingerParams(0.0, 0.9, 0.75),
        },
        approach_speed="medium",
        cautions=["确认物体坚固", "防止力度过冲"],
    ),
    "power_accumulating_grasp": HandStrategy(
        name="power_accumulating_grasp",
        description="蓄力抓取（山天大畜）",
        hexagram_source="山天大畜 ☶☰",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.75),
            "index":  FingerParams(0.0, 0.5, 0.75),
            "middle": FingerParams(0.0, 0.5, 0.75),
            "ring":   FingerParams(0.0, 0.5, 0.70),
            "pinky":  FingerParams(0.0, 0.5, 0.70),
        },
        approach_speed="slow",
        cautions=["从轻到重逐步施力", "达到稳定即停止"],
    ),
    "forceful_grasp": HandStrategy(
        name="forceful_grasp",
        description="强力突破抓取（泽风大过）",
        hexagram_source="泽风大过 ☱☴",
        fingers={
            "thumb":  FingerParams(0.0, 1.0, 0.90),
            "index":  FingerParams(0.0, 1.0, 0.90),
            "middle": FingerParams(0.0, 1.0, 0.90),
            "ring":   FingerParams(0.0, 1.0, 0.90),
            "pinky":  FingerParams(0.0, 1.0, 0.90),
        },
        approach_speed="medium",
        cautions=["确认物体能承受大力", "防止过冲损坏"],
    ),

    # ──────────── 坤系（轻柔/精密）────────────
    "precision_grasp": HandStrategy(
        name="precision_grasp",
        description="指尖精确捏取（坤为地）",
        hexagram_source="坤为地 ☷☷",
        fingers={
            "thumb":  FingerParams(0.0, 0.3, 0.25),
            "index":  FingerParams(0.0, 0.3, 0.25),
            "middle": FingerParams(0.8, 0.3, 0.05),
            "ring":   FingerParams(0.8, 0.3, 0.05),
            "pinky":  FingerParams(0.8, 0.3, 0.05),
        },
        approach_speed="slow",
        cautions=["轻接触", "避免物体变形"],
    ),
    "soft_grasp": HandStrategy(
        name="soft_grasp",
        description="柔性抓取（兑为泽）",
        hexagram_source="兑为泽 ☱☱",
        fingers={
            "thumb":  FingerParams(0.0, 0.4, 0.30),
            "index":  FingerParams(0.0, 0.4, 0.30),
            "middle": FingerParams(0.0, 0.4, 0.30),
            "ring":   FingerParams(0.2, 0.4, 0.25),
            "pinky":  FingerParams(0.2, 0.4, 0.25),
        },
        approach_speed="slow",
        cautions=["最小力抓取", "保持柔性接触"],
    ),
    "reduced_force_grasp": HandStrategy(
        name="reduced_force_grasp",
        description="减力抓取（山泽损/地山谦）",
        hexagram_source="山泽损 ☶☱",
        fingers={
            "thumb":  FingerParams(0.0, 0.25, 0.20),
            "index":  FingerParams(0.0, 0.25, 0.20),
            "middle": FingerParams(0.0, 0.25, 0.20),
            "ring":   FingerParams(0.5, 0.25, 0.15),
            "pinky":  FingerParams(0.5, 0.25, 0.15),
        },
        approach_speed="slow",
        cautions=["最小力抓取", "持续监控"],
    ),
    "gentle_grasp": HandStrategy(
        name="gentle_grasp",
        description="轻柔抓取（通用柔弱物体）",
        hexagram_source="多卦综合",
        fingers={
            "thumb":  FingerParams(0.0, 0.2, 0.20),
            "index":  FingerParams(0.0, 0.2, 0.20),
            "middle": FingerParams(0.3, 0.2, 0.15),
            "ring":   FingerParams(0.5, 0.2, 0.10),
            "pinky":  FingerParams(0.5, 0.2, 0.10),
        },
        approach_speed="slow",
        cautions=["极度轻柔", "传感器全程监控"],
    ),

    # ──────────── 震系（动态/快速）────────────
    "dynamic_grasp": HandStrategy(
        name="dynamic_grasp",
        description="快速动态抓取（震为雷）",
        hexagram_source="震为雷 ☳☳",
        fingers={
            "thumb":  FingerParams(0.0, 1.0, 0.60),
            "index":  FingerParams(0.0, 1.0, 0.60),
            "middle": FingerParams(0.0, 1.0, 0.60),
            "ring":   FingerParams(0.0, 1.0, 0.55),
            "pinky":  FingerParams(0.0, 1.0, 0.55),
        },
        approach_speed="fast",
        cautions=["快速响应", "跟踪运动物体"],
    ),
    "predictive_grasp": HandStrategy(
        name="predictive_grasp",
        description="预判拦截抓取（雷地豫）",
        hexagram_source="雷地豫 ☳☷",
        fingers={
            "thumb":  FingerParams(0.0, 0.8, 0.45),
            "index":  FingerParams(0.0, 0.8, 0.45),
            "middle": FingerParams(0.0, 0.8, 0.45),
            "ring":   FingerParams(0.0, 0.8, 0.40),
            "pinky":  FingerParams(0.0, 0.8, 0.40),
        },
        approach_speed="fast",
        cautions=["预判物体轨迹", "提前到达拦截点"],
    ),
    "following_grasp": HandStrategy(
        name="following_grasp",
        description="跟随运动抓取（泽雷随）",
        hexagram_source="泽雷随 ☱☳",
        fingers={
            "thumb":  FingerParams(0.0, 0.7, 0.50),
            "index":  FingerParams(0.0, 0.7, 0.50),
            "middle": FingerParams(0.0, 0.7, 0.45),
            "ring":   FingerParams(0.0, 0.7, 0.45),
            "pinky":  FingerParams(0.0, 0.7, 0.45),
        },
        approach_speed="medium",
        cautions=["匹配物体速度", "顺势抓取"],
    ),

    # ──────────── 艮系（稳定/慢速）────────────
    "stable_grasp": HandStrategy(
        name="stable_grasp",
        description="稳定静态抓取（艮为山）",
        hexagram_source="艮为山 ☶☶",
        fingers={
            "thumb":  FingerParams(0.0, 0.4, 0.40),
            "index":  FingerParams(0.0, 0.4, 0.40),
            "middle": FingerParams(0.0, 0.4, 0.40),
            "ring":   FingerParams(0.0, 0.4, 0.40),
            "pinky":  FingerParams(0.0, 0.4, 0.35),
        },
        approach_speed="slow",
        cautions=["先固定位置", "确认稳定后提升"],
    ),
    "endurance_grasp": HandStrategy(
        name="endurance_grasp",
        description="持久恒定抓取（雷风恒/山雷颐）",
        hexagram_source="雷风恒 ☳☴",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.50),
            "middle": FingerParams(0.0, 0.5, 0.45),
            "ring":   FingerParams(0.0, 0.5, 0.45),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="medium",
        cautions=["恒定力输出", "定期检查状态"],
    ),

    # ──────────── 坎系（谨慎/试探）────────────
    "cautious_grasp": HandStrategy(
        name="cautious_grasp",
        description="谨慎试探抓取（天泽履/坎为水）",
        hexagram_source="天泽履 ☰☱",
        fingers={
            "thumb":  FingerParams(0.0, 0.2, 0.30),
            "index":  FingerParams(0.0, 0.2, 0.30),
            "middle": FingerParams(0.0, 0.2, 0.30),
            "ring":   FingerParams(0.0, 0.2, 0.25),
            "pinky":  FingerParams(0.0, 0.2, 0.25),
        },
        approach_speed="slow",
        cautions=["极慢接近", "发现异常立即撤回"],
    ),
    "conditional_grasp": HandStrategy(
        name="conditional_grasp",
        description="条件判断抓取（水天需/火山旅）",
        hexagram_source="水天需 ☵☰",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.50),
            "middle": FingerParams(0.0, 0.5, 0.45),
            "ring":   FingerParams(0.0, 0.5, 0.45),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="medium",
        cautions=["检查条件满足后再执行", "时机不对则放弃"],
    ),

    # ──────────── 离系（附着/协同）────────────
    "adhesion_grasp": HandStrategy(
        name="adhesion_grasp",
        description="吸附附着抓取（离为火/火天大有）",
        hexagram_source="离为火 ☲☲",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.40),
            "index":  FingerParams(0.0, 0.5, 0.40),
            "middle": FingerParams(0.0, 0.5, 0.35),
            "ring":   FingerParams(0.0, 0.5, 0.35),
            "pinky":  FingerParams(0.0, 0.5, 0.30),
        },
        approach_speed="medium",
        cautions=["检查表面适合吸附", "保持接触面积"],
    ),
    "coordinated_grasp": HandStrategy(
        name="coordinated_grasp",
        description="多指协同抓取（风火家人/天火同人）",
        hexagram_source="风火家人 ☴☲",
        fingers={
            "thumb":  FingerParams(0.0, 0.6, 0.50),
            "index":  FingerParams(0.0, 0.6, 0.40),
            "middle": FingerParams(0.0, 0.6, 0.50),
            "ring":   FingerParams(0.0, 0.6, 0.40),
            "pinky":  FingerParams(0.0, 0.6, 0.50),
        },
        approach_speed="medium",
        cautions=["多指协调用力", "力分布均匀"],
    ),

    # ──────────── 巽系（柔顺/适应）────────────
    "compliant_grasp": HandStrategy(
        name="compliant_grasp",
        description="顺应姿态抓取（巽为风/雷泽归妹）",
        hexagram_source="巽为风 ☴☴",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.35),
            "index":  FingerParams(0.0, 0.5, 0.35),
            "middle": FingerParams(0.0, 0.5, 0.30),
            "ring":   FingerParams(0.0, 0.5, 0.30),
            "pinky":  FingerParams(0.0, 0.5, 0.30),
        },
        approach_angle=12,
        approach_speed="medium",
        cautions=["顺应物体姿态", "不强行改变朝向"],
    ),
    "adaptive_grasp": HandStrategy(
        name="adaptive_grasp",
        description="异形自适应抓取（山水蒙/天风姤/火泽睽）",
        hexagram_source="山水蒙 ☶☵",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.20),
            "middle": FingerParams(0.0, 0.5, 0.50),
            "ring":   FingerParams(0.0, 0.5, 0.20),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="slow",
        cautions=["适应不规则形状", "根据局部几何调整指位"],
    ),

    # ──────────── 兑系（其他）────────────
    "direct_grasp": HandStrategy(
        name="direct_grasp",
        description="直接果断抓取（天雷无妄/泽天夬）",
        hexagram_source="天雷无妄 ☰☳",
        fingers={
            "thumb":  FingerParams(0.0, 0.7, 0.55),
            "index":  FingerParams(0.0, 0.7, 0.55),
            "middle": FingerParams(0.0, 0.7, 0.50),
            "ring":   FingerParams(0.0, 0.7, 0.50),
            "pinky":  FingerParams(0.0, 0.7, 0.45),
        },
        approach_speed="fast",
        cautions=["确认条件后果断执行"],
    ),
    "standard_grasp": HandStrategy(
        name="standard_grasp",
        description="标准中庸抓取（地天泰/水火既济）",
        hexagram_source="地天泰 ☷☰",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.50),
            "middle": FingerParams(0.0, 0.5, 0.45),
            "ring":   FingerParams(0.0, 0.5, 0.45),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="medium",
        cautions=["正常标准操作"],
    ),
    "balanced_grasp": HandStrategy(
        name="balanced_grasp",
        description="平衡抓取（火风鼎）",
        hexagram_source="火风鼎 ☲☴",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.45),
            "middle": FingerParams(0.0, 0.5, 0.45),
            "ring":   FingerParams(0.0, 0.5, 0.45),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="medium",
        cautions=["全程监控", "保持力平衡"],
    ),
    "non_conflict_grasp": HandStrategy(
        name="non_conflict_grasp",
        description="避让无冲突抓取（天水讼）",
        hexagram_source="天水讼 ☰☵",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.35),
            "index":  FingerParams(0.0, 0.5, 0.35),
            "middle": FingerParams(0.0, 0.5, 0.35),
            "ring":   FingerParams(0.5, 0.5, 0.20),
            "pinky":  FingerParams(0.5, 0.5, 0.20),
        },
        approach_angle=20,
        approach_speed="medium",
        cautions=["从开阔侧接近", "避免碰撞"],
    ),
    "top_down_grasp": HandStrategy(
        name="top_down_grasp",
        description="自上而下抓取（地泽临/地风升）",
        hexagram_source="地泽临 ☷☱",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.45),
            "index":  FingerParams(0.0, 0.5, 0.45),
            "middle": FingerParams(0.0, 0.5, 0.40),
            "ring":   FingerParams(0.0, 0.5, 0.40),
            "pinky":  FingerParams(0.0, 0.5, 0.35),
        },
        approach_speed="medium",
        cautions=["从正上方垂直接近", "利用重力辅助"],
    ),
    "progressive_grasp": HandStrategy(
        name="progressive_grasp",
        description="渐进加力抓取（风天小畜/火地晋/风山渐）",
        hexagram_source="风天小畜 ☴☰",
        fingers={
            "thumb":  FingerParams(0.0, 0.3, 0.40),
            "index":  FingerParams(0.0, 0.3, 0.40),
            "middle": FingerParams(0.0, 0.3, 0.35),
            "ring":   FingerParams(0.0, 0.3, 0.35),
            "pinky":  FingerParams(0.0, 0.3, 0.30),
        },
        approach_speed="slow",
        cautions=["从弱到强逐步加力", "每阶段评估"],
    ),
    "tactile_feedback_grasp": HandStrategy(
        name="tactile_feedback_grasp",
        description="触觉反馈抓取（泽山咸/风泽中孚）",
        hexagram_source="泽山咸 ☱☶",
        fingers={
            "thumb":  FingerParams(0.0, 0.3, 0.40),
            "index":  FingerParams(0.0, 0.3, 0.40),
            "middle": FingerParams(0.0, 0.3, 0.35),
            "ring":   FingerParams(0.0, 0.3, 0.35),
            "pinky":  FingerParams(0.0, 0.3, 0.35),
        },
        approach_speed="slow",
        cautions=["依赖触觉反馈", "实时调整力"],
    ),
    "iterative_grasp": HandStrategy(
        name="iterative_grasp",
        description="迭代试探抓取（地雷复）",
        hexagram_source="地雷复 ☷☳",
        fingers={
            "thumb":  FingerParams(0.0, 0.25, 0.35),
            "index":  FingerParams(0.0, 0.25, 0.35),
            "middle": FingerParams(0.0, 0.25, 0.30),
            "ring":   FingerParams(0.0, 0.25, 0.30),
            "pinky":  FingerParams(0.0, 0.25, 0.25),
        },
        approach_speed="slow",
        cautions=["渐增力试探", "每次评估后决定下一轮"],
    ),
    "observational_grasp": HandStrategy(
        name="observational_grasp",
        description="观察优先抓取（风地观/山火贲）",
        hexagram_source="风地观 ☴☷",
        fingers={
            "thumb":  FingerParams(0.0, 0.4, 0.40),
            "index":  FingerParams(0.0, 0.4, 0.40),
            "middle": FingerParams(0.0, 0.4, 0.35),
            "ring":   FingerParams(0.0, 0.4, 0.35),
            "pinky":  FingerParams(0.0, 0.4, 0.30),
        },
        approach_speed="slow",
        cautions=["先观察后动手", "评估所有抓取点"],
    ),

    # 特殊/消极策略
    "avoid_or_retry": HandStrategy(
        name="avoid_or_retry",
        description="放弃或重试（天地否）",
        hexagram_source="天地否 ☰☷",
        fingers={},
        approach_speed="slow",
        cautions=["不可抓则放弃", "换角度重试"],
    ),
    "withdraw_grasp": HandStrategy(
        name="withdraw_grasp",
        description="主动退避（天山遁）",
        hexagram_source="天山遁 ☰☶",
        fingers={},
        approach_speed="slow",
        cautions=["果断放弃", "记录原因"],
    ),
    "abort_or_retry": HandStrategy(
        name="abort_or_retry",
        description="暂缓重试（风水涣/火水未济）",
        hexagram_source="火水未济 ☲☵",
        fingers={},
        approach_speed="slow",
        cautions=["确认条件", "不满足则暂缓"],
    ),
    "low_visibility_grasp": HandStrategy(
        name="low_visibility_grasp",
        description="低可见性抓取（地火明夷）",
        hexagram_source="地火明夷 ☷☲",
        fingers={
            "thumb":  FingerParams(0.0, 0.2, 0.35),
            "index":  FingerParams(0.0, 0.2, 0.35),
            "middle": FingerParams(0.0, 0.2, 0.30),
            "ring":   FingerParams(0.0, 0.2, 0.30),
            "pinky":  FingerParams(0.0, 0.2, 0.25),
        },
        approach_speed="slow",
        cautions=["依赖触觉而非视觉", "降低速度"],
    ),

    # 兜底策略
    "generic_grasp": HandStrategy(
        name="generic_grasp",
        description="通用抓取（降级兜底）",
        hexagram_source="默认",
        fingers={
            "thumb":  FingerParams(0.0, 0.5, 0.50),
            "index":  FingerParams(0.0, 0.5, 0.50),
            "middle": FingerParams(0.0, 0.5, 0.45),
            "ring":   FingerParams(0.0, 0.5, 0.45),
            "pinky":  FingerParams(0.0, 0.5, 0.40),
        },
        approach_speed="medium",
        cautions=["降级策略", "监控执行"],
    ),
}


# ============================================================
# 策略映射器
# ============================================================
class StrategyMapper:
    """YLYW 卦象策略 → 灵巧手物理参数"""

    def __init__(self):
        self._strategy_map = STRATEGY_HAND_MAP

        # 策略别名映射（处理不同命名风格）
        self._aliases = {
            "precise_pick": "precision_grasp",
            "wrap_grasp": "following_grasp",
            "incremental_grasp": "progressive_grasp",
            "peeling_grasp": "progressive_grasp",
            "close_proximity_grasp": "top_down_grasp",
            "sequential_grasp": "standard_grasp",
            "interlocking_grasp": "power_grasp",
            "extrication_grasp": "adaptive_grasp",
            "difficult_grasp": "cautious_grasp",
            "adaptive_irregular_grasp": "adaptive_grasp",
            "corrective_grasp": "iterative_grasp",
        }

    def resolve_strategy(self, strategy_type: str) -> str:
        """解析策略名（处理别名）"""
        if strategy_type in self._strategy_map:
            return strategy_type
        return self._aliases.get(strategy_type, "generic_grasp")

    def get_finger_params(self, strategy_type: str,
                          force_scale: float = 1.0) -> dict:
        """
        获取指定策略的手指参数

        Args:
            strategy_type: YLYW 策略名
            force_scale: 力缩放系数（来自YLYW的force_preset × modifier）

        Returns:
            dict: {"thumb": {position, velocity, effort}, ...}
        """
        resolved = self.resolve_strategy(strategy_type)
        strat = self._strategy_map.get(resolved,
                                       self._strategy_map["generic_grasp"])

        result = {
            "strategy_name": strat.name,
            "description": strat.description,
            "approach_angle": strat.approach_angle,
            "approach_speed": strat.approach_speed,
            "pre_grasp_open": strat.pre_grasp_open,
            "cautions": strat.cautions,
            "fingers": {},
        }

        for finger, params in strat.fingers.items():
            result["fingers"][finger] = {
                "position": params.position,
                "velocity": params.velocity,
                "effort": round(min(1.0, max(0.05,
                                           params.effort * force_scale)), 2),
            }

        return result

    def get_gripper_params(self, strategy_type: str,
                           force_scale: float = 1.0) -> dict:
        """
        获取简易夹爪模式参数（非NIMBLE_HANDS）
        适用于两指/三指简易夹爪
        """
        finger_params = self.get_finger_params(strategy_type, force_scale)
        avg_pos = np.mean([p["position"]
                          for p in finger_params["fingers"].values()])
        avg_vel = np.mean([p["velocity"]
                          for p in finger_params["fingers"].values()])
        avg_eff = np.mean([p["effort"]
                          for p in finger_params["fingers"].values()])

        return {
            "strategy_name": finger_params["strategy_name"],
            "description": finger_params["description"],
            "position": round(float(avg_pos), 2),
            "velocity": round(float(avg_vel), 2),
            "effort": round(float(avg_eff), 2),
            "approach_speed": finger_params["approach_speed"],
            "cautions": finger_params["cautions"],
        }

    def list_strategies(self) -> List[dict]:
        """列出所有可用策略"""
        result = []
        for name, strat in self._strategy_map.items():
            result.append({
                "name": name,
                "description": strat.description,
                "hexagram": strat.hexagram_source,
                "fingers_count": len(strat.fingers),
            })
        return result

    def print_strategies(self):
        """打印所有策略"""
        print(f"\n{'='*70}")
        print(f"  YLYW → OmniHand Strategy Mapping ({len(self._strategy_map)} strategies)")
        print(f"{'='*70}")
        for name, strat in sorted(self._strategy_map.items()):
            print(f"  {name:32s} {strat.description}")
            print(f"    {'':32s} ← {strat.hexagram_source}")
        print(f"{'='*70}\n")


# ============================================================
# 快捷函数
# ============================================================
_mapper = None

def get_strategy_params(strategy_type: str, force_scale: float = 1.0) -> dict:
    """全局快捷调用"""
    global _mapper
    if _mapper is None:
        _mapper = StrategyMapper()
    return _mapper.get_finger_params(strategy_type, force_scale)


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    mapper = StrategyMapper()
    mapper.print_strategies()

    # 测试几个策略
    for s in ["dynamic_grasp", "precision_grasp", "power_grasp", "cautious_grasp"]:
        params = mapper.get_gripper_params(s, force_scale=0.8)
        print(f"  {s}: pos={params['position']:.2f} vel={params['velocity']:.2f} "
              f"eff={params['effort']:.2f}  speed={params['approach_speed']}")
