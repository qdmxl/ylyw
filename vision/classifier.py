"""
YLYW 视觉分类器 (Vision Classifier) — 主管线 v3

完整推理链路:
    图像 → VisualFeatureExtractor → 6维视觉特征
         → VisualTrigramBase → L1 8卦隶属度
         → VisualYaoEncoder → L2 六爻向量
         → (上卦=主导卦, 下卦=次主导卦) → 六十四卦索引
         → 上卦决定视觉类别
         → YaoRelations → L3+ 爻位关系 → 置信度修正

核心设计:
    - 上卦: 隶属度最高的卦 → 决定视觉类别（外观）
    - 下卦: 隶属度次高的卦 → 提供互补信息（内质）
    - Top-K: 用主导卦固定上卦, 变化下卦来生成备选
"""

import sys
import os
import numpy as np

from .feature_extractor_vision import VisualFeatureExtractor
from .trigram_base_vision import VisualTrigramBase, Trigram, FEATURE_NAMES
from .yao_encoder_vision import VisualYaoEncoder

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'experiment_phase1'))
from ylyw_core.yao_relations import YaoRelations


class VisionClassifier:
    """YLYW 视觉分类器 v3 — 主导卦驱动"""

    def __init__(self, sensitivity: float = 0.8):
        self.trigram_base = VisualTrigramBase(sensitivity=sensitivity)
        self.feature_extractor = VisualFeatureExtractor()
        self.yao_encoder = VisualYaoEncoder()
        self.yao_relations = YaoRelations()

        # 构建 (上卦,下卦) → hexagram_index 映射
        self._build_hexagram_index()
        self._verbose = False

    def _build_hexagram_index(self):
        """从物理域构建 trigram pair → hexagram 映射

        注意: 视觉域和物理域使用不同的八卦编号!
            视觉域 Trigram 枚举: 乾0 坤1 震2 巽3 坎4 离5 艮6 兑7
            物理域 trigram编号: 乾0 兑1 离2 震3 巽4 坎5 艮6 坤7
            需要做编号转换。
        """
        from ylyw_core.hexagram_rules import HexagramRuleBase

        engine = HexagramRuleBase()
        # 物理域编号: 乾兑离震巽坎艮坤
        sym_to_phys = {
            '☰': 0, '☱': 1, '☲': 2, '☳': 3,
            '☴': 4, '☵': 5, '☶': 6, '☷': 7,
        }
        # 视觉域 → 物理域 编号转换
        # 视觉: 乾0 坤1 震2 巽3 坎4 离5 艮6 兑7
        # 物理: 乾0 兑1 离2 震3 巽4 坎5 艮6 坤7
        self._vis_to_phys = {0:0, 1:7, 2:3, 3:4, 4:5, 5:2, 6:6, 7:1}
        self._phys_to_vis = {v:k for k,v in self._vis_to_phys.items()}

        self._pair_to_hex = {}
        self._hex_name = {}
        for hx, rule in engine.rules.items():
            u_sym, l_sym = rule['upper_lower']
            u_phys = sym_to_phys[u_sym]
            l_phys = sym_to_phys[l_sym]
            # 存储时使用视觉编号
            u_vis = self._phys_to_vis[u_phys]
            l_vis = self._phys_to_vis[l_phys]
            self._pair_to_hex[(u_vis, l_vis)] = hx.value
            self._hex_name[hx.value] = rule['name']

        # 视觉类别名（按视觉域 Trigram 枚举编号）
        # 视觉: 乾0 坤1 震2 巽3 坎4 离5 艮6 兑7
        self.class_names = {
            0: '乾类·结构/几何',
            1: '坤类·平滑/均匀',
            2: '震类·高对比方向',
            3: '巽类·细纹理',
            4: '坎类·曲线/流动',
            5: '离类·亮/辐射',
            6: '艮类·块状/厚重',
            7: '兑类·反射/高光',
        }

    def classify(self, image: np.ndarray, top_k: int = 3) -> dict:
        """对图像进行完整分类推理"""
        # Step 1-2: 视觉特征 → 八卦隶属度
        visual_features = self.feature_extractor.extract(image)
        memberships = self.trigram_base.get_all_memberships(visual_features)

        # 按隶属度排序
        ranked = sorted(enumerate(memberships), key=lambda x: x[1], reverse=True)

        # 主导卦 = 上卦, 次主导 = 下卦
        upper = ranked[0][0]
        upper_score = ranked[0][1]
        lower = ranked[1][0]
        lower_score = ranked[1][1]

        # Step 3: 六爻编码
        yao_vector = self.yao_encoder.encode(visual_features)

        # Step 4: 爻位关系 → 置信度修正
        yao_rel = self.yao_relations.analyze(yao_vector)
        conf_mod = yao_rel.strategy_modifier

        if self._verbose:
            print(f"\n[视觉特征] {' '.join(f'{n}={visual_features[n]:.3f}' for n in FEATURE_NAMES)}")
            print(f"[六爻] {self._fmt_yao(yao_vector)}")
            print(f"[主导卦] {self.trigram_base.get_trigram_info(Trigram(upper))['name']} "
                  f"({upper_score:.3f})")
            print(f"[次主导] {self.trigram_base.get_trigram_info(Trigram(lower))['name']} "
                  f"({lower_score:.3f})")

        # Step 5: 生成 Top-K 结果
        # 主结果: (上卦=主导卦, 下卦=次主导卦)
        # 备选: 固定上卦, 变化下卦(按隶属度序)
        top_results = []
        seen_classes = set()

        # 尝试多种下卦组合
        lower_candidates = [i for i, _ in ranked[1:]]  # 排除主导卦本身

        for l_cand in lower_candidates:
            hex_idx = self._pair_to_hex.get((upper, l_cand))
            if hex_idx is None:
                continue

            class_id = upper  # 上卦固定 → 类别固定
            if class_id in seen_classes:
                continue

            pair_confidence = lower_score * memberships[l_cand] if l_cand == lower else \
                              upper_score * memberships[l_cand]
            confidence = round(pair_confidence * conf_mod, 4)

            top_results.append({
                'hexagram_index': hex_idx,
                'hexagram_name': self._hex_name[hex_idx],
                'upper_trigram': upper,
                'lower_trigram': l_cand,
                'class_id': class_id,
                'class_name': self.class_names[class_id],
                'pair_score': round(pair_confidence, 4),
                'confidence': confidence,
            })
            seen_classes.add(class_id)

            if len(top_results) >= 1:
                break  # 上卦固定 → 类别只有一个, 一条就够了

        # 如果主导卦的下卦组合找不到, 用本位卦兜底
        if not top_results:
            hex_idx = self._pair_to_hex.get((upper, upper))
            if hex_idx is not None:
                confidence = round(float(upper_score ** 2) * conf_mod, 4)
                top_results.append({
                    'hexagram_index': hex_idx,
                    'hexagram_name': self._hex_name[hex_idx],
                    'upper_trigram': upper,
                    'lower_trigram': upper,
                    'class_id': upper,
                    'class_name': self.class_names[upper],
                    'pair_score': round(float(upper_score ** 2), 4),
                    'confidence': confidence,
                })

        # Top-K: 除了主导卦类别, 还要展示 2-3 个次优类别（用备用上卦）
        # 这些是 "也可能的类别"——用次主导卦作上卦
        for alt_upper_i, alt_upper_score in ranked[1:min(1 + top_k, len(ranked))]:
            alt_upper = alt_upper_i
            if alt_upper in seen_classes:
                continue

            hex_idx = self._pair_to_hex.get((alt_upper, alt_upper))
            if hex_idx is None:
                continue

            confidence = round(float(alt_upper_score ** 2) * conf_mod, 4)
            top_results.append({
                'hexagram_index': hex_idx,
                'hexagram_name': self._hex_name[hex_idx],
                'upper_trigram': alt_upper,
                'lower_trigram': alt_upper,
                'class_id': alt_upper,
                'class_name': self.class_names[alt_upper],
                'pair_score': round(float(alt_upper_score ** 2), 4),
                'confidence': confidence,
            })
            seen_classes.add(alt_upper)

            if len(top_results) >= top_k:
                break

        return {
            'top_results': top_results,
            'trigram_memberships': {
                self.trigram_base.get_trigram_info(Trigram(i))['name']: round(float(m), 4)
                for i, m in enumerate(memberships)
            },
            'dominant_trigram': {
                'name': self.trigram_base.get_trigram_info(Trigram(upper))['name'],
                'visual_type': self.trigram_base.get_trigram_info(Trigram(upper))['visual_type'],
                'score': round(upper_score, 4),
            },
            'yao_vector': yao_vector.tolist(),
            'yao_relations': {
                'score_overall': yao_rel.score_overall,
                'dangwei': yao_rel.score_dangwei,
                'dezhong': yao_rel.score_dezhong,
                'cheng_cheng': yao_rel.score_cheng_cheng,
                'bi': yao_rel.score_bi,
                'ying': yao_rel.score_ying,
                'modifier': round(conf_mod, 3),
                'caution': yao_rel.caution_level,
            },
            'visual_features': visual_features,
        }

    def classify_batch(self, images, top_k=3):
        return [self.classify(img, top_k=top_k) for img in images]

    def set_verbose(self, v=True):
        self._verbose = v

    def _fmt_yao(self, yao):
        syms = ['初', '二', '三', '四', '五', '上']
        return ' '.join(f"{syms[i]}{'—' if yao[i] >= 0.5 else '--'}" for i in range(6))

    def __repr__(self):
        return f"VisionClassifier(sensitivity={self.trigram_base.sensitivity})"
