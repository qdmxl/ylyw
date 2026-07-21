#!/usr/bin/env python3
"""
六十四卦规则层 — 跨本体共享

这是 YLYW 最核心的先验知识库：
从六爻二进制模式到策略类型的映射，
所有机器人共享同一套规则。

每条规则:
  key: 6位二进制tuple
  value: { "gua": 卦名, "strategy": 策略类型, "params": 参数模板 }
"""

import numpy as np
from typing import Tuple, Dict


class HexagramRules:
    """
    六十四卦规则引擎

    从六爻模式匹配到抓取策略和参数模板。
    跨本体共享——所有机器人用同一套规则。
    """

    # 核心策略类型（所有的策略选项）
    STRATEGY_TYPES = [
        "全力抓取/执行",   # 各方面条件都满足，全力执行
        "待机/准备",        # 还没准备好，需要准备
        "任务完成/确认",    # 已完成，确认保持
        "任务未完成/继续尝试",  # 还差一点，调整策略
        "缓慢接近/精确对准",  # 需要小心对准
        "保持接触/轻微调整",  # 已接触但不够，微调
        "松开/释放",         # 需要释放物体
        "紧急停止/安全保护",  # 出现异常
    ]

    # ===== 完整64卦规则表 =====
    # key: (上爻,五爻,四爻,三爻,二爻,初爻) — 从高到低
    # 使用整数二进制编码便于匹配
    RULES = {
        # ── 纯阳/纯阴 (2) ──
        (1, 1, 1, 1, 1, 1): {
            "gua": "䷀ 乾为天",
            "strategy": "全力抓取/执行",
            "params": {"speed": 1.0, "force": 1.0, "precision": "low"}
        },
        (0, 0, 0, 0, 0, 0): {
            "gua": "䷁ 坤为地",
            "strategy": "待机/准备",
            "params": {"speed": 0.0, "force": 0.0, "precision": "none"}
        },

        # ── 既济/未济 (2) ──
        (1, 0, 1, 0, 1, 0): {
            "gua": "䷾ 既济",
            "strategy": "任务完成/确认",
            "params": {"speed": 0.3, "force": 0.6, "precision": "high"}
        },
        (0, 1, 0, 1, 0, 1): {
            "gua": "䷿ 未济",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.6, "force": 0.7, "precision": "medium"}
        },

        # ── 四阳二阴 (15) ──
        (1, 1, 1, 1, 1, 0): {
            "gua": "䷫ 天风姤",
            "strategy": "全力抓取/执行",
            "params": {"speed": 0.9, "force": 0.9, "precision": "low"}
        },
        (1, 1, 1, 1, 0, 1): {
            "gua": "䷉ 天泽履",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.4, "force": 0.5, "precision": "high"}
        },
        (1, 1, 1, 0, 1, 1): {
            "gua": "䷠ 天山遁",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.6, "precision": "high"}
        },
        (1, 1, 0, 1, 1, 1): {
            "gua": "䷋ 天地否",
            "strategy": "待机/准备",
            "params": {"speed": 0.0, "force": 0.3, "precision": "low"}
        },
        (1, 0, 1, 1, 1, 1): {
            "gua": "䷌ 天火同人",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.4, "force": 0.7, "precision": "high"}
        },
        (0, 1, 1, 1, 1, 1): {
            "gua": "䷘ 天雷无妄",
            "strategy": "全力抓取/执行",
            "params": {"speed": 0.8, "force": 0.8, "precision": "medium"}
        },
        (1, 1, 1, 1, 0, 0): {
            "gua": "䷹ 兑为泽",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.5, "precision": "high"}
        },
        (1, 1, 0, 0, 1, 1): {
            "gua": "䷴ 风山渐",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },
        (0, 0, 1, 1, 1, 1): {
            "gua": "䷡ 雷天大壮",
            "strategy": "全力抓取/执行",
            "params": {"speed": 0.9, "force": 0.9, "precision": "low"}
        },
        (1, 1, 0, 1, 1, 0): {
            "gua": "䷦ 水山蹇",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.5, "force": 0.8, "precision": "medium"}
        },
        (1, 0, 1, 1, 0, 1): {
            "gua": "䷿ 火水未济",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.6, "force": 0.6, "precision": "medium"}
        },

        # ── 三阳三阴 (20) — 最常见情境 ──
        (1, 0, 1, 0, 0, 1): {
            "gua": "䷔ 火雷噬嗑",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.3, "force": 0.4, "precision": "high"}
        },
        (0, 1, 0, 1, 1, 0): {
            "gua": "䷮ 水地比",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.4, "force": 0.5, "precision": "high"}
        },
        (1, 1, 0, 1, 0, 1): {
            "gua": "䷽ 雷山小过",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.4, "precision": "high"}
        },
        (1, 0, 1, 1, 0, 0): {
            "gua": "䷔ 火山旅",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.5, "precision": "high"}
        },
        (0, 1, 1, 1, 0, 1): {
            "gua": "䷾ 水风井",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.5, "force": 0.6, "precision": "medium"}
        },
        (0, 0, 1, 0, 1, 1): {
            "gua": "䷣ 地火明夷",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },
        (1, 1, 0, 0, 1, 0): {
            "gua": "䷳ 泽山咸",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.4, "precision": "high"}
        },
        (0, 1, 0, 0, 1, 1): {
            "gua": "䷎ 水地晋",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },

        # ── 二阳四阴 (15) ──
        (0, 0, 0, 0, 0, 1): {
            "gua": "䷗ 地雷复",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.1, "force": 0.2, "precision": "high"}
        },
        (0, 0, 0, 0, 1, 0): {
            "gua": "䷖ 山地剥",
            "strategy": "待机/准备",
            "params": {"speed": 0.0, "force": 0.1, "precision": "low"}
        },
        (0, 0, 0, 1, 0, 0): {
            "gua": "䷧ 水泽节",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.5, "precision": "high"}
        },
        (0, 0, 1, 0, 0, 0): {
            "gua": "䷨ 风雷益",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },
        (0, 1, 0, 0, 0, 0): {
            "gua": "䷲ 震为雷",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.7, "force": 0.7, "precision": "low"}
        },
        (1, 0, 0, 0, 0, 0): {
            "gua": "䷳ 艮为山",
            "strategy": "待机/准备",
            "params": {"speed": 0.0, "force": 0.2, "precision": "low"}
        },
        (0, 0, 0, 1, 1, 0): {
            "gua": "䷮ 水泽履",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },
        (0, 0, 1, 1, 0, 0): {
            "gua": "䷟ 风火家人",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.4, "force": 0.5, "precision": "high"}
        },
        (0, 1, 1, 0, 0, 0): {
            "gua": "䷶ 火雷丰",
            "strategy": "全力抓取/执行",
            "params": {"speed": 0.8, "force": 0.7, "precision": "medium"}
        },
        (1, 1, 0, 0, 0, 0): {
            "gua": "䷸ 巽为风",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.3, "force": 0.4, "precision": "high"}
        },

        # ── 一阳五阴 / 一阴五阳 + 其他 (10) ──
        (0, 0, 0, 0, 0, 1): {
            "gua": "䷗ 复卦",
            "strategy": "缓慢接近/精确对准",
            "params": {"speed": 0.2, "force": 0.3, "precision": "high"}
        },
        (1, 1, 1, 1, 1, 0): {
            "gua": "䷪ 夬卦",
            "strategy": "任务完成/确认",
            "params": {"speed": 0.4, "force": 0.3, "precision": "low"}
        },
        (0, 0, 1, 1, 1, 1): {
            "gua": "䷡ 大壮",
            "strategy": "全力抓取/执行",
            "params": {"speed": 0.9, "force": 0.8, "precision": "low"}
        },
        (1, 1, 1, 1, 0, 0): {
            "gua": "䷹ 兑卦",
            "strategy": "保持接触/轻微调整",
            "params": {"speed": 0.3, "force": 0.4, "precision": "high"}
        },
    }

    def __init__(self):
        # 构建所有 64 种情况的默认规则
        self._build_defaults()

    def _build_defaults(self):
        """补齐64卦中未显式定义的规则（使用最近邻策略）"""
        self._all_rules = dict(self.RULES)

        # 遍历所有 64 种二元组合
        for bits in self._all_binary_patterns():
            if bits not in self._all_rules:
                # 找 Hamming 距离最近的已知规则
                self._all_rules[bits] = self._nearest_rule(bits)

    @staticmethod
    def _all_binary_patterns():
        """生成64种6位二进制组合"""
        for i in range(64):
            yield tuple((i >> (5 - j)) & 1 for j in range(6))

    def _nearest_rule(self, bits: tuple) -> dict:
        """找 Hamming 距离最近的已知规则"""
        best_dist = 7
        best_rule = self.RULES[(0, 0, 0, 0, 0, 0)]  # 默认坤卦

        for known_bits, rule in self.RULES.items():
            dist = sum(1 for a, b in zip(bits, known_bits) if a != b)
            if dist < best_dist:
                best_dist = dist
                best_rule = rule

        # 给一个合理的名字
        n_ones = sum(bits)
        # 参数处理：precision 是字符串，不能乘浮点数
        raw_params = best_rule.get("params", {})
        if isinstance(raw_params, dict):
            params = {}
            for k, v in raw_params.items():
                if isinstance(v, (int, float)):
                    params[k] = v * (n_ones / 3.0)
                else:
                    params[k] = v
        else:
            params = raw_params
        return {
            "gua": f"䷀~䷁ (混合, {n_ones}阳{6-n_ones}阴)",
            "strategy": best_rule.get("strategy", "待机/准备"),
            "params": params
        }

    def match(self, yao_vector: np.ndarray) -> dict:
        """
        六爻向量 → 匹配最合适的卦象规则

        Args:
            yao_vector: 6维连续向量, 每维 ∈ [0,1]

        Returns:
            { "gua": 卦名, "strategy": 策略, "params": 参数 }
        """
        # 二值化（≥0.5 为阳爻 1, <0.5 为阴爻 0）
        binary = tuple(int(v >= 0.5) for v in yao_vector)
        return dict(self._all_rules[binary])

    def get_rule_by_binary(self, bits: tuple) -> dict:
        """根据二进制模式获取规则"""
        return dict(self._all_rules.get(bits, self._all_rules[(0, 0, 0, 0, 0, 0)]))


if __name__ == '__main__':
    rules = HexagramRules()
    print(f"Total rules: {len(rules._all_rules)}")

    # 测试几种情况
    tests = [
        "001010",  # 接近中
        "111111",  # 全力
        "101010",  # 完成
        "010101",  # 未完成
        "000000",  # 待机
        "110011",  # 慢慢接近
    ]
    for t in tests:
        yao = np.array([float(c) for c in t])
        result = rules.match(yao)
        print(f"  {t} → {result['gua']:20s} | {result['strategy']:20s} | {result['params']}")

    print("\n✅ HexagramRules OK")
