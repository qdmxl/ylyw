"""
YLYW 视觉分类器 v4 — 专用检测器驱动 (跳过六爻编码)

完整链路:
    图像 → SpecializedDetectors(8个专用算子) → 8D隶属度向量
         → argmax → 主导卦 → 视觉类别

跳过层:
    - L2 六爻编码 (6D共享特征→6爻)
    - L3 六十四卦匹配 (爻向量→卦象模板余弦匹配)
    - L3+ 爻位关系运算

核心理念:
    每个卦象有自己专属的视觉检测器, 直接从图像计算隶属度。
    无需共享特征, 无需压缩编码, 无需卦象匹配。
"""

import numpy as np
from .specialized_detectors_v2 import SpecializedDetectorsV2, Trigram


class VisionClassifierV4:
    """YLYW 视觉分类器 v4 — 跳过六爻, 直达卦象"""

    # 视觉类别名
    CLASS_NAMES = {
        0: '乾类·结构/几何',
        1: '坤类·平滑/均匀',
        2: '震类·高对比方向',
        3: '巽类·细纹理',
        4: '坎类·曲线/流动',
        5: '离类·亮/辐射',
        6: '艮类·块状/厚重',
        7: '兑类·反射/高光',
    }

    TRIGRAM_NAMES = {
        0: '乾 ☰ 天',
        1: '坤 ☷ 地',
        2: '震 ☳ 雷',
        3: '巽 ☴ 风',
        4: '坎 ☵ 水',
        5: '离 ☲ 火',
        6: '艮 ☶ 山',
        7: '兑 ☱ 泽',
    }

    def __init__(self):
        self.detectors = SpecializedDetectorsV2()
        self._verbose = False

    def classify(self, image: np.ndarray, top_k: int = 3) -> dict:
        """
        对图像进行分类

        Args:
            image: (H,W) 灰度 或 (H,W,3) RGB
            top_k: 返回前k个结果

        Returns:
            dict with top_results, memberships, ...
        """
        if image.ndim == 3:
            import cv2
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)

        # 8个专用检测器 → 8D隶属度
        memberships = self.detectors.detect_all(gray)

        # 排序
        ranked = sorted(enumerate(memberships), key=lambda x: x[1], reverse=True)

        # 主导卦 → 类别
        top_results = []
        for i in range(min(top_k, 8)):
            tri_idx, score = ranked[i]
            top_results.append({
                'class_id': tri_idx,
                'class_name': self.CLASS_NAMES[tri_idx],
                'trigram_name': self.TRIGRAM_NAMES[tri_idx],
                'score': round(float(score), 4),
            })

        if self._verbose:
            print(f"[隶属度] {' | '.join(f'{self.TRIGRAM_NAMES[i]}:{memberships[i]:.3f}' for i in range(8))}")
            print(f"[主导] {self.TRIGRAM_NAMES[ranked[0][0]]} → {self.CLASS_NAMES[ranked[0][0]]}")

        return {
            'top_results': top_results,
            'memberships': {
                self.TRIGRAM_NAMES[i]: round(float(m), 4)
                for i, m in enumerate(memberships)
            },
            'dominant_trigram': {
                'name': self.TRIGRAM_NAMES[ranked[0][0]],
                'class': self.CLASS_NAMES[ranked[0][0]],
                'score': round(float(ranked[0][1]), 4),
            },
        }

    def classify_batch(self, images, top_k=3):
        return [self.classify(img, top_k=top_k) for img in images]

    def set_verbose(self, v=True):
        self._verbose = v

    def __repr__(self):
        return "VisionClassifierV4(8 specialized detectors)"
