#!/usr/bin/env python3
"""
YLYW 推理层适配器

把 YLYW（PriorManual）接到 LIBERO-PRO 评测流程里。
职责：
  1. 从仿真/视觉观测生成 YLYW 需要的 13 维物理特征（见 features.py）
  2. 调用 PriorManual 得到卦象 + 抓取策略（符号层）
  3. 把符号策略翻译为连续动作指令（笛卡尔速度/夹爪开合）

这一层是"易理模型 vs VLA"对比的关键：VLA 端到端出动作，
YLYW 中间有可解释的卦象推理链，每次决策都可归因。
"""

import os
import sys
import numpy as np

# YLYW 核心（复用 experiment_phase1 的 PriorManual）
_YLYW_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _YLYW_ROOT)

from experiment_phase1.ylyw_core.prior_manual import PriorManual  # noqa: E402


# 策略关键词 → 归一化速度指令的映射
_STRATEGY_TO_SPEED = {
    "soft": 0.3, "medium": 0.6, "fast": 1.0, "slow": 0.25,
}


class YLYWInference:
    """YLYW 推理层：特征 → 卦象 → 动作。"""

    def __init__(self, force_scale: float = 1.25):
        self.manual = PriorManual(force_scale=force_scale)
        self.last_reasoning: dict = {}

    # ------------------------------------------------------------------ #
    def infer(self, features: dict) -> dict:
        """核心推理：13 维物理特征 → 抓取策略。

        Args:
            features: 见 features.py 的 required 字段
        Returns:
            dict: {hexagram, strategy_type, force, speed, angle, cautions,
                   yao_quality, reasoning_chain}
        """
        perception = self.manual.perceive_and_encode(features)
        strategy = self.manual.get_grasp_strategy(perception)
        reasoning = self.manual.explain_reasoning(perception)

        self.last_reasoning = {
            "features": features,
            "hexagram": strategy.get("hexagram"),
            "strategy_type": strategy.get("type"),
            "match_score": perception.get("hexagram_match_score"),
            "yao_quality": strategy.get("yao_quality"),
            "top_k": perception.get("top_k_hexagrams"),
        }

        return {
            "hexagram": strategy.get("hexagram"),
            "strategy_type": strategy.get("type"),
            "force": strategy.get("force"),
            "speed": strategy.get("speed"),
            "approach_angle": strategy.get("approach_angle"),
            "cautions": strategy.get("cautions", []),
            "yao_quality": strategy.get("yao_quality"),
            "reasoning_chain": reasoning,
        }

    # ------------------------------------------------------------------ #
    def strategy_to_action(self, result: dict, ee_pos: np.ndarray,
                           target_pos: np.ndarray, gripper_open: float,
                           step_scale: float = 0.05) -> dict:
        """符号策略 → 连续动作指令。

        简单闭环控制器：朝目标位置移动，速度/力由卦象策略调制。
        真·LIBERO-PRO 阶段可替换为 IK + 力控。

        Returns:
            {'delta_pos': (3,), 'gripper': float, 'phase': str}
        """
        direction = target_pos - ee_pos
        dist = float(np.linalg.norm(direction))
        if dist > 1e-6:
            direction = direction / dist

        # 速度调制：卦象策略的 speed 字段
        speed_key = result.get("speed", "medium")
        v = _STRATEGY_TO_SPEED.get(speed_key, 0.6)

        # 力/谨慎度调制：接近时减速（爻位质量低 → 更谨慎）
        yao_q = result.get("yao_quality", 0.5) or 0.5
        caution = 0.5 + 0.5 * (1.0 - min(max(yao_q, 0.0), 1.0))

        step = min(dist, step_scale * v * (1.2 - 0.4 * caution))
        delta_pos = direction * step

        # 到达即闭合夹爪
        phase = "approach"
        grip = gripper_open
        if dist < 0.03:
            phase = "grasp"
            grip = 0.0

        return {"delta_pos": delta_pos, "gripper": grip, "phase": phase, "dist": dist}

    # ------------------------------------------------------------------ #
    def describe_decision(self, result: dict) -> str:
        """人类可读的决策归因链（论文用）。"""
        return (
            f"特征→卦象【{result.get('hexagram')}】"
            f"(匹配度 {result.get('match_score', 0):.2f}, 爻位质量 {result.get('yao_quality', 0):.2f}) "
            f"→ 策略[{result.get('strategy_type')}] "
            f"力={result.get('force')}, 速度={result.get('speed')}, 角度={result.get('approach_angle')}°"
        )


if __name__ == "__main__":
    # 冒烟测试
    inf = YLYWInference()
    demo = {
        "stability": 0.2, "roll_tendency": 0.9, "strength_needed": 0.3,
        "fragility": 0.1, "task_priority": 0.8, "reachability": 0.7,
    }
    r = inf.infer(demo)
    print(inf.describe_decision(r))
