"""
视觉八卦原型 (Visual Trigram Base) — L1 层

将八卦的8种原型映射为6维视觉特征空间的质心向量。
每个卦象对应一种典型的视觉模式。

原型设计:
    基于合成图像特征分布标定，保留视觉概念语义:
    - 乾: 高边缘+高对比+高规整 → 结构几何
    - 坤: 高纹理均匀+低边缘+低对比 → 平滑均匀
    - 震: 极高边缘+高对比+低规整 → 定向条纹
    - 巽: 中等各项 → 细密纹理
    - 坎: 中等纹理+低边缘+低规整 → 曲线流动
    - 离: 高对比+中高显著性 → 亮辐射
    - 艮: 低边缘+高规整 → 块状厚重
    - 兑: 高纹理+低边缘+高规整 → 反射高光

用法:
    >>> vt = VisualTrigramBase()
    >>> memberships = vt.get_all_memberships(visual_features)
    >>> dominant, score = vt.get_dominant_trigram(visual_features)
"""

import numpy as np
from enum import Enum


class Trigram(Enum):
    """八卦枚举"""
    QIAN = 0   # 乾 ☰ 天 — 结构/几何
    KUN = 1    # 坤 ☷ 地 — 平滑/均匀
    ZHEN = 2   # 震 ☳ 雷 — 高对比方向
    XUN = 3    # 巽 ☴ 风 — 细纹理
    KAN = 4    # 坎 ☵ 水 — 曲线/流动
    LI = 5     # 离 ☲ 火 — 亮/辐射
    GEN = 6    # 艮 ☶ 山 — 块状/厚重
    DUI = 7    # 兑 ☱ 泽 — 反射/高光


# 特征维度索引
FEATURE_NAMES = [
    'texture_uniformity',       # 初爻: 纹理均匀度
    'edge_clarity',             # 二爻: 边缘清晰度
    'local_contrast',           # 三爻: 局部对比度
    'shape_regularity',         # 四爻: 形状规整度
    'saliency',                 # 五爻: 显著性
    'background_complexity',    # 上爻: 背景复杂度
]


class VisualTrigramBase:
    """
    视觉八卦基元

    8个原型向量定义在6维视觉特征空间中。
    原型标定基于合成图像的特征分布 + 视觉语义概念。
    隶属度采用欧氏距离 + 高斯核。
    """

    def __init__(self, sensitivity: float = 0.8):
        """
        Args:
            sensitivity: 高斯核敏感度 (默认0.8, 适配当前特征值范围)
        """
        self.sensitivity = sensitivity

        # [texture_uniformity, edge_clarity, local_contrast,
        #  shape_regularity, saliency, background_complexity]
        #
        # background_complexity 设为0.50基准值:
        #   合成图像全幅填充→实际值1.0; 真实图像的物体+背景→会低很多
        #   此处取中位值以兼容两端, 避免该特征主导距离
        self.trigram_prototypes: dict[Trigram, dict] = {
            Trigram.QIAN: {
                'name': '乾 ☰ 天',
                'visual_type': '结构/几何',
                'description': '锐利边缘+高对比+高规整: 棋盘格、建筑立面、二维码',
                'prototype': np.array([0.05, 0.65, 0.95, 0.82, 0.22, 0.50],
                                      dtype=np.float32),
            },
            Trigram.KUN: {
                'name': '坤 ☷ 地',
                'visual_type': '平滑/均匀',
                'description': '高纹理均匀+极低对比: 天空、纯色、毛玻璃、渐变',
                'prototype': np.array([0.92, 0.05, 0.10, 0.52, 0.20, 0.50],
                                      dtype=np.float32),
            },
            Trigram.ZHEN: {
                'name': '震 ☳ 雷',
                'visual_type': '高对比方向',
                'description': '极高边缘+高对比+低规整: 栅栏、条纹、木纹',
                'prototype': np.array([0.05, 0.95, 0.95, 0.15, 0.18, 0.50],
                                      dtype=np.float32),
            },
            Trigram.XUN: {
                'name': '巽 ☴ 风',
                'visual_type': '细纹理',
                'description': '中等各项、细密均匀: 织物、草地、砂纸、毛发',
                'prototype': np.array([0.15, 0.45, 0.30, 0.55, 0.12, 0.50],
                                      dtype=np.float32),
            },
            Trigram.KAN: {
                'name': '坎 ☵ 水',
                'visual_type': '曲线/流动',
                'description': '中等纹理+低边缘+低规整: 水流、云朵、烟雾、墨迹',
                'prototype': np.array([0.50, 0.08, 0.38, 0.48, 0.22, 0.50],
                                      dtype=np.float32),
            },
            Trigram.LI: {
                'name': '离 ☲ 火',
                'visual_type': '亮/辐射',
                'description': '高对比+中高显著性+中低规整: 灯光、火焰、光斑',
                'prototype': np.array([0.05, 0.55, 0.95, 0.38, 0.35, 0.50],
                                      dtype=np.float32),
            },
            Trigram.GEN: {
                'name': '艮 ☶ 山',
                'visual_type': '块状/厚重',
                'description': '低边缘+高规整+中等对比: 砖墙、岩石、文字块',
                'prototype': np.array([0.05, 0.20, 0.48, 0.70, 0.38, 0.50],
                                      dtype=np.float32),
            },
            Trigram.DUI: {
                'name': '兑 ☱ 泽',
                'visual_type': '反射/高光',
                'description': '高纹理均匀+低边缘+高规整: 金属、玻璃、水面倒影',
                'prototype': np.array([0.68, 0.05, 0.28, 0.72, 0.25, 0.50],
                                      dtype=np.float32),
            },
        }

    def compute_membership(self, visual_features: dict, trigram: Trigram) -> float:
        """
        计算图像在指定卦象下的模糊隶属度

        μ(x) = exp(-sensitivity × ||x - prototype||²)

        Args:
            visual_features: 6维视觉特征字典
            trigram: 目标卦象

        Returns:
            float ∈ [0, 1]: 隶属度
        """
        feature_vector = np.array([
            visual_features[name] for name in FEATURE_NAMES
        ], dtype=np.float32)

        prototype = self.trigram_prototypes[trigram]['prototype']
        squared_dist = np.sum((feature_vector - prototype) ** 2)
        membership = np.exp(-self.sensitivity * squared_dist)
        return float(np.clip(membership, 0.0, 1.0))

    def get_dominant_trigram(self, visual_features: dict) -> tuple[Trigram, float]:
        """获取主导卦象及隶属度"""
        best_trigram = None
        best_score = -1.0
        for trigram in Trigram:
            score = self.compute_membership(visual_features, trigram)
            if score > best_score:
                best_score = score
                best_trigram = trigram
        return best_trigram, best_score

    def get_all_memberships(self, visual_features: dict) -> np.ndarray:
        """获取8卦隶属度向量, shape (8,)"""
        memberships = np.zeros(8, dtype=np.float32)
        for trigram in Trigram:
            memberships[trigram.value] = self.compute_membership(visual_features, trigram)
        return memberships

    def get_trigram_info(self, trigram: Trigram) -> dict:
        return self.trigram_prototypes.get(trigram, {})

    def __repr__(self):
        return (f"VisualTrigramBase(8 prototypes, "
                f"sensitivity={self.sensitivity})")
