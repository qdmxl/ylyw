"""
视觉六爻编码器 (Visual Yao Encoder) — L2 层

将6维视觉特征向量编码为六爻值。
每个爻对应一个关键的视觉维度（与物理域的语义一一对应）。

六爻位置（从下往上）：
    初爻: 纹理均匀度 — 纹理是否均匀平滑
    二爻: 边缘清晰度 — 边缘是否锐利分明
    三爻: 局部对比度 — 明暗变化是否剧烈
    四爻: 形状规整度 — 形状是否规则几何
    五爻: 显著性 — 画面是否有突出区域
    上爻: 背景复杂度 — 周围环境是否杂乱

爻值规则:
    - 接近1 → 阳爻（—），表示该视觉特征强/显著
    - 接近0 → 阴爻（--），表示该视觉特征弱/不显著

用法:
    >>> encoder = VisualYaoEncoder()
    >>> yao_vector = encoder.encode(visual_features)
    >>> print(yao_vector)  # [0.85, 0.72, 0.45, 0.60, 0.80, 0.30]
"""

import numpy as np
from enum import Enum


class YaoPosition(Enum):
    """六爻位置（从下往上）"""
    FIRST = 0    # 初爻: 纹理均匀度
    SECOND = 1   # 二爻: 边缘清晰度
    THIRD = 2    # 三爻: 局部对比度
    FOURTH = 3   # 四爻: 形状规整度
    FIFTH = 4    # 五爻: 显著性
    SIXTH = 5    # 上爻: 背景复杂度


class VisualYaoEncoder:
    """
    视觉六爻编码器

    将6维视觉特征直接映射为六爻值。
    与物理域六爻编码器不同的是，视觉特征已经在
    VisualFeatureExtractor 中归一化到 [0,1]，
    因此编码公式可以更简洁。
    """

    def __init__(self):
        # 各爻的编码规则（从视觉特征到爻值的直接映射）
        self.encoding_rules = {
            YaoPosition.FIRST: {
                'name': '纹理均匀度',
                'description': '纹理是否均匀平滑。高值=均匀(阳)，低值=杂乱(阴)',
                'formula': lambda f: f.get('texture_uniformity', 0.5),
            },
            YaoPosition.SECOND: {
                'name': '边缘清晰度',
                'description': '边缘是否锐利分明。高值=锐利(阳)，低值=模糊(阴)',
                'formula': lambda f: f.get('edge_clarity', 0.5),
            },
            YaoPosition.THIRD: {
                'name': '局部对比度',
                'description': '明暗变化是否剧烈。高值=强对比(阳)，低值=平淡(阴)',
                'formula': lambda f: f.get('local_contrast', 0.5),
            },
            YaoPosition.FOURTH: {
                'name': '形状规整度',
                'description': '形状是否规则几何。高值=规则(阳)，低值=不规则(阴)',
                'formula': lambda f: f.get('shape_regularity', 0.5),
            },
            YaoPosition.FIFTH: {
                'name': '显著性',
                'description': '画面是否有突出显著区域。高值=显著(阳)，低值=平淡(阴)',
                'formula': lambda f: f.get('saliency', 0.5),
            },
            YaoPosition.SIXTH: {
                'name': '背景复杂度',
                'description': '背景环境是否杂乱。高值=复杂(阳)，低值=纯净(阴)',
                'formula': lambda f: f.get('background_complexity', 0.5),
            },
        }

        self._logger_enabled = False

    def encode(self, visual_features: dict) -> np.ndarray:
        """
        将视觉特征编码为六爻向量

        Args:
            visual_features: dict, 包含6个视觉特征:
                texture_uniformity, edge_clarity, local_contrast,
                shape_regularity, saliency, background_complexity

        Returns:
            np.ndarray: shape (6,), 每个元素 ∈ [0, 1]
        """
        yao_vector = []

        for position in YaoPosition:
            rule = self.encoding_rules[position]
            value = rule['formula'](visual_features)
            value = max(0.0, min(1.0, value))
            yao_vector.append(value)

        if self._logger_enabled:
            self._log_encoding(yao_vector)

        return np.array(yao_vector, dtype=np.float32)

    def encode_batch(self, features_list: list[dict]) -> np.ndarray:
        """批量编码"""
        return np.stack([self.encode(f) for f in features_list])

    def get_yao_interpretation(self, yao_vector: np.ndarray) -> list[dict]:
        """将六爻向量解释为人类可读格式"""
        interpretations = []
        for i, pos in enumerate(YaoPosition):
            rule = self.encoding_rules[pos]
            val = float(yao_vector[i])
            yin_yang = "阳爻（—）" if val >= 0.5 else "阴爻（--）"
            interpretations.append({
                'position': pos.name,
                'name': rule['name'],
                'value': round(val, 3),
                'nature': yin_yang,
                'description': rule['description'],
            })
        return interpretations

    def _log_encoding(self, yao_vector):
        """编码日志"""
        print("\n[视觉六爻编码]")
        for i, pos in enumerate(YaoPosition):
            rule = self.encoding_rules[pos]
            yy = "阳 —" if yao_vector[i] >= 0.5 else "阴 --"
            print(f"  {pos.name}({rule['name']}): {yao_vector[i]:.3f} ({yy})")

    def enable_logging(self): self._logger_enabled = True
    def disable_logging(self): self._logger_enabled = False

    def __repr__(self):
        return f"VisualYaoEncoder(6 positions)"
