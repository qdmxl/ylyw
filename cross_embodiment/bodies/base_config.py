#!/usr/bin/env python3
"""
本体配置基类 — 跨本体泛化的核心抽象

每个本体实现一个 BodyConfig 子类，定义：
  1. 本体名称和基本信息
  2. 六爻编码函数 (L2): 传感器状态 → 6维爻向量
  3. 动作解码函数: 策略参数 → 关节控制信号
  4. 本体特定的运动学参数

核心原则:
  - L1八卦 和 L3 64卦规则 是跨本体共享的
  - L2六爻编码 和 动作解码 是本体特异的
"""

import numpy as np
from typing import Dict, Any, Callable
from abc import ABC, abstractmethod


class BodyConfig(ABC):
    """本体配置抽象基类"""

    def __init__(self):
        self.name = "base"
        self.n_dof = 0               # 自由度数量
        self.n_ctrl = 0              # 控制信号数量
        self.end_effector = ""       # 末端执行器类型
        self.description = ""        # 描述

    @abstractmethod
    def encode_yao(self, bagua: np.ndarray, obs: dict) -> np.ndarray:
        """
        六爻编码: 八卦隶属度(8维) + 传感器观测 → 六爻向量(6维)

        Args:
            bagua: L1输出的8维八卦隶属度向量
            obs:   环境观测字典（joint位置、接触信息、物体位置等）

        Returns:
            6维六爻向量, 每个元素 ∈ [0, 1]
        """
        pass

    @abstractmethod
    def decode_action(self, strategy: dict, obs: dict) -> np.ndarray:
        """
        动作解码: L3策略参数 → 本体关节控制信号

        Args:
            strategy: L3输出的策略字典
                { "gua": 卦名, "strategy": 策略类型,
                  "params": {"speed": float, "force": float, "precision": str} }
            obs: 当前观测

        Returns:
            控制信号向量 (长度 = n_ctrl)
        """
        pass

    def apply_zhiji_gains(self, strategy_type: str, ctrl: np.ndarray,
                          zhiji_gains: dict) -> np.ndarray:
        """
        将知几学习到的解码器增益叠加到控制信号上。

        Args:
            strategy_type: 当前策略名
            ctrl: 基类解码器生成的原始控制信号
            zhiji_gains: get_decoder_gains() 返回的增益字典
                {ctrl_idx: gain_value}

        Returns:
            叠加增益后的控制信号
        """
        if not zhiji_gains:
            return ctrl

        result = ctrl.copy()
        for idx_str, gain in zhiji_gains.items():
            try:
                idx = int(idx_str)
                if 0 <= idx < len(result):
                    # 策略级增益：如果该关节有已知增益，用它替代硬编码值
                    result[idx] = gain
            except (ValueError, IndexError):
                pass

        return result

    def apply_zhiji_thresholds(self, yao: np.ndarray, strategy_type: str,
                               zhiji_thresholds: dict) -> np.ndarray:
        """
        将知几学习到的编码器阈值叠加到六爻编码上。

        Args:
            yao: encode_yao 的原始输出
            strategy_type: 当前策略名
            zhiji_thresholds: get_encoder_thresholds() 返回的阈值字典
                {yao_index: {center: float, sigma: float}}

        Returns:
            调整后的六爻向量
        """
        if not zhiji_thresholds:
            return yao

        result = yao.copy()
        for idx_str, th in zhiji_thresholds.items():
            try:
                idx = int(idx_str)
                if 0 <= idx < len(result):
                    center = th.get('center', 0.5)
                    sigma = th.get('sigma', 0.2)
                    # 知几调整：中心漂移 + 敏感度调整
                    if sigma > 0:
                        result[idx] = np.exp(-0.5 * ((result[idx] - center) / sigma) ** 2)
            except (ValueError, IndexError):
                pass

        return result

    def get_info(self) -> dict:
        """本体基本信息"""
        return {
            'name': self.name,
            'n_dof': self.n_dof,
            'n_ctrl': self.n_ctrl,
            'end_effector': self.end_effector,
            'description': self.description,
        }


class YaoThresholds:
    """六爻阈值的便捷工具类"""

    def __init__(self):
        pass

    @staticmethod
    def binary(value: float, threshold: float = 0.5) -> float:
        """二值化"""
        return 1.0 if value > threshold else 0.0

    @staticmethod
    def continuous(value: float, low: float = 0.0, high: float = 1.0,
                   vmin: float = 0.0, vmax: float = 1.0) -> float:
        """连续值映射到 [0,1]"""
        clamped = np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0)
        return float(clamped)

    @staticmethod
    def inverse(value: float, low: float = 0.0, high: float = 1.0) -> float:
        """反向映射（越小越接近1）"""
        return 1.0 - np.clip((value - low) / (high - low), 0.0, 1.0)

    @staticmethod
    def gaussian(value: float, center: float = 0.5, sigma: float = 0.2) -> float:
        """高斯型隶属度"""
        return float(np.exp(-0.5 * ((value - center) / sigma) ** 2))
