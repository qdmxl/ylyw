"""
八卦基元模块 (L1: Trigram Base)

定义8个基本卦象及其物理世界映射。
每个卦对应一组"理想物理特征"，这些是先验知识——不可学习。

八卦映射：
    乾 ☰ → 健（刚性、强力）
    坤 ☷ → 顺（柔性、包容）
    震 ☳ → 动（动态、易变）
    艮 ☶ → 止（稳固、静止）
    离 ☲ → 明/附丽（轻质、依赖附着）
    坎 ☵ → 陷/险（凹陷、高风险）
    兑 ☱ → 悦（柔软、愉悦）
    巽 ☴ → 入（渗透、适应）
"""

import numpy as np
from enum import Enum


class Trigram(Enum):
    """八卦枚举"""
    QIAN = 0   # 乾 ☰  天，健也
    KUN = 1    # 坤 ☷  地，顺也
    ZHEN = 2   # 震 ☳  雷，动也
    GEN = 3    # 艮 ☶  山，止也
    LI = 4     # 离 ☲  火，明也、附丽也
    KAN = 5    # 坎 ☵  水，陷也、险也
    DUI = 6    # 兑 ☱  泽，悦也
    XUN = 7    # 巽 ☴  风，入也


class TrigramBase:
    """
    八卦基元：预定义的物理世界建模知识

    这是"圣人仰观俯察"得出的先验符号模型，
    每个卦定义了一组物理特征的理想值（prototype）。
    """

    def __init__(self):
        # 定义每个卦的"理想物理特征"
        # 这些是上古圣人"仰观俯察"得出的先验知识
        self.trigram_prototypes = {
            Trigram.QIAN: {
                'name': '乾',
                'symbol': '☰',
                'meaning': '健',
                'natural': '天',
                'physical_attrs': {
                    'strength_needed': 0.9,      # 需要强力
                    'stability': 0.8,            # 稳定
                    'deformability': 0.1,         # 不易变形
                    'roll_tendency': 0.2,         # 不易滚动
                    'visibility': 0.7,            # 可见
                    'fragility': 0.2              # 不易碎
                }
            },
            Trigram.KUN: {
                'name': '坤',
                'symbol': '☷',
                'meaning': '顺',
                'natural': '地',
                'physical_attrs': {
                    'strength_needed': 0.3,
                    'stability': 0.6,
                    'deformability': 0.8,
                    'roll_tendency': 0.3,
                    'visibility': 0.5,
                    'fragility': 0.3
                }
            },
            Trigram.ZHEN: {
                'name': '震',
                'symbol': '☳',
                'meaning': '动',
                'natural': '雷',
                'physical_attrs': {
                    'strength_needed': 0.5,
                    'stability': 0.2,
                    'deformability': 0.4,
                    'roll_tendency': 0.9,         # 极易滚动
                    'visibility': 0.6,
                    'fragility': 0.6
                }
            },
            Trigram.GEN: {
                'name': '艮',
                'symbol': '☶',
                'meaning': '止',
                'natural': '山',
                'physical_attrs': {
                    'strength_needed': 0.4,
                    'stability': 0.9,             # 非常稳定
                    'deformability': 0.2,
                    'roll_tendency': 0.1,         # 几乎不滚动
                    'visibility': 0.5,
                    'fragility': 0.4
                }
            },
            Trigram.LI: {
                'name': '离',
                'symbol': '☲',
                'meaning': '明、附丽',
                'natural': '火',
                'physical_attrs': {
                    'strength_needed': 0.4,
                    'stability': 0.5,
                    'deformability': 0.4,
                    'roll_tendency': 0.4,
                    'visibility': 0.9,             # 非常醒目
                    'fragility': 0.5
                }
            },
            Trigram.KAN: {
                'name': '坎',
                'symbol': '☵',
                'meaning': '陷、险',
                'natural': '水',
                'physical_attrs': {
                    'strength_needed': 0.6,
                    'stability': 0.3,
                    'deformability': 0.5,
                    'roll_tendency': 0.5,
                    'visibility': 0.4,
                    'fragility': 0.7               # 较脆弱
                }
            },
            Trigram.DUI: {
                'name': '兑',
                'symbol': '☱',
                'meaning': '悦',
                'natural': '泽',
                'physical_attrs': {
                    'strength_needed': 0.3,
                    'stability': 0.5,
                    'deformability': 0.6,
                    'roll_tendency': 0.3,
                    'visibility': 0.6,
                    'fragility': 0.4
                }
            },
            Trigram.XUN: {
                'name': '巽',
                'symbol': '☴',
                'meaning': '入',
                'natural': '风',
                'physical_attrs': {
                    'strength_needed': 0.4,
                    'stability': 0.4,
                    'deformability': 0.5,
                    'roll_tendency': 0.4,
                    'visibility': 0.5,
                    'fragility': 0.5
                }
            }
        }

    def compute_membership(self, object_features, trigram):
        """
        计算一个物体对某个卦的隶属度

        使用高斯核计算object_features与卦象prototype之间的相似度。
        这类似于模糊数学中的"隶属度函数"——差异越小，隶属度越高。

        Args:
            object_features: dict, 包含 physical_attrs 中的键值
            trigram: Trigram枚举

        Returns:
            float: 隶属度 ∈ [0, 1]
        """
        prototype = self.trigram_prototypes[trigram]['physical_attrs']

        similarity = 0.0
        weight_sum = 0.0

        for attr, proto_val in prototype.items():
            if attr in object_features:
                actual_val = object_features[attr]
                # 计算差异（绝对差）
                diff = abs(actual_val - proto_val)
                # 转换为隶属度：差异越小，隶属度越高
                # 1.5 是敏感度系数（先验知识）
                membership = max(0.0, 1.0 - diff * 1.5)
                similarity += membership
                weight_sum += 1.0

        if weight_sum > 0:
            return similarity / weight_sum
        return 0.0

    def get_dominant_trigram(self, object_features):
        """
        获取一个物体最主要的卦象（隶属度最高）

        Returns:
            (Trigram, membership_score)
        """
        best_trigram = None
        best_score = -1.0

        for trigram in Trigram:
            score = self.compute_membership(object_features, trigram)
            if score > best_score:
                best_score = score
                best_trigram = trigram

        return best_trigram, best_score

    def get_all_memberships(self, object_features):
        """
        返回物体对8个卦的隶属度向量

        可用于可视化或进一步分析

        Returns:
            np.ndarray: 形状(8,)，每个卦的隶属度
        """
        memberships = []
        for trigram in Trigram:
            memberships.append(self.compute_membership(object_features, trigram))
        return np.array(memberships, dtype=np.float32)

    def get_trigram_info(self, trigram):
        """获取某个卦的元信息"""
        return self.trigram_prototypes.get(trigram, {})

    def __repr__(self):
        return f"TrigramBase(8 trigrams, {len(self.trigram_prototypes[Trigram.QIAN]['physical_attrs'])} attributes each)"
