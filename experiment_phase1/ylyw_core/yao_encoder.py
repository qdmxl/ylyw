"""
六爻编码器模块 (L2: Yao Encoder)

将物理世界状态编码为6个爻值。
每个爻对应一个关键的物理/语义维度。

六爻位置（从下往上）：
    初爻（初九/初六）：基础稳定性
    二爻（九二/六二）：抓取点可达性
    三爻（九三/六三）：抓取力需求
    四爻（九四/六四）：物体脆弱性
    五爻（九五/六五）：任务优先级
    上爻（上九/上六）：环境约束

爻值规则：
    - 接近1 → 阳爻（—），表示强、积极、有利
    - 接近0 → 阴爻（--），表示弱、消极、不利
"""

import numpy as np
from enum import Enum


class YaoPosition(Enum):
    """六爻位置定义（从下往上，符合《周易》传统）"""
    FIRST = 0   # 初爻：基础稳定性
    SECOND = 1  # 二爻：抓取点可达性
    THIRD = 2   # 三爻：抓取力需求
    FOURTH = 3  # 四爻：物体脆弱性
    FIFTH = 4   # 五爻：任务优先级
    SIXTH = 5   # 上爻：环境约束


class YaoEncoder:
    """
    六爻编码器：将物体特征和环境状态映射到六爻值

    这是将"现实世界的物理状态"编码为"易经符号系统"的核心桥梁。
    每个爻都有预定义的编码公式（先验知识）。

    使用示例:
        >>> encoder = YaoEncoder()
        >>> features = {'stability': 0.8, 'reachability': 0.9, ...}
        >>> yao_vector = encoder.encode(features)
        >>> print(yao_vector)  # tensor([0.85, 0.72, 0.45, 0.60, 0.80, 0.70])
    """

    def __init__(self):
        # 预定义每个爻的计算规则（先验知识，硬编码）
        self.encoding_rules = {
            YaoPosition.FIRST: {
                'name': '基础稳定性',
                'description': '物体的支撑基础是否稳定，是否容易倾倒',
                'formula': lambda f: (
                    0.4 * f.get('stability', 0.5) +
                    0.3 * (1.0 - f.get('roll_tendency', 0.5)) +
                    0.3 * f.get('support_area', 0.5)
                )
            },
            YaoPosition.SECOND: {
                'name': '抓取点可达性',
                'description': '夹爪能否无碰撞地到达最佳抓取点',
                'formula': lambda f: (
                    0.5 * f.get('reachability', 0.5) +
                    0.3 * (1.0 - f.get('occlusion', 0.5)) +
                    0.2 * f.get('grasp_surface_quality', 0.5)
                )
            },
            YaoPosition.THIRD: {
                'name': '抓取力需求',
                'description': '稳定抓取所需的握力大小，重物/平滑物需要更大的力',
                'formula': lambda f: (
                    0.6 * f.get('strength_needed', 0.5) +
                    0.4 * f.get('weight_ratio', 0.5)
                )
            },
            YaoPosition.FOURTH: {
                'name': '物体脆弱性',
                'description': '物体是否易碎、易变形。爻值高=不易碎（阳），爻值低=易碎（阴）',
                # 注意：脆弱性反向编码——越脆弱，爻值越低（阴爻，不利）
                'formula': lambda f: 1.0 - f.get('fragility', 0.5)
            },
            YaoPosition.FIFTH: {
                'name': '任务优先级',
                'description': '当前物体在任务序列中的重要性',
                'formula': lambda f: f.get('task_priority', 0.5)
            },
            YaoPosition.SIXTH: {
                'name': '环境约束',
                'description': '周围障碍物的密集程度、操作空间的限制。爻值高=空间宽敞（阳），低=拥挤（阴）',
                'formula': lambda f: 1.0 - min(1.0, f.get('obstacle_density', 0.0) * 1.5)
            }
        }

        # 日志开关
        self._logger_enabled = False

    def encode(self, object_features):
        """
        将物体特征编码为六爻向量

        Args:
            object_features: dict, 包含所有需要的特征：
                - stability, roll_tendency, support_area (初爻)
                - reachability, occlusion, grasp_surface_quality (二爻)
                - strength_needed, weight_ratio (三爻)
                - fragility (四爻)
                - task_priority (五爻)
                - obstacle_density (上爻)

        Returns:
            np.ndarray: 形状(6,)，每个元素 ∈ [0, 1]
        """
        yao_vector = []

        for position in YaoPosition:
            rule = self.encoding_rules[position]
            # 应用预定义公式
            value = rule['formula'](object_features)
            # 裁剪到 [0, 1]
            value = max(0.0, min(1.0, value))
            yao_vector.append(value)

        if self._logger_enabled:
            self._log_encoding(yao_vector)

        return np.array(yao_vector, dtype=np.float32)

    def encode_batch(self, features_list):
        """
        批量编码多个物体

        Args:
            features_list: List[dict], 多个物体的特征字典

        Returns:
            np.ndarray: 形状(N, 6)
        """
        results = []
        for features in features_list:
            yao = self.encode(features)
            results.append(yao)
        return np.stack(results)

    def get_yao_interpretation(self, yao_vector):
        """
        将六爻向量解释为人类可读的格式

        Args:
            yao_vector: np.ndarray, 形状(6,)

        Returns:
            list of dict: 每个爻的详细解释
        """
        interpretations = []
        for i, pos in enumerate(YaoPosition):
            rule = self.encoding_rules[pos]
            val = float(yao_vector[i])
            yin_yang = "阳爻（—，强/利）" if val >= 0.5 else "阴爻（--，弱/不利）"
            interpretations.append({
                'position': pos.name,
                'name': rule['name'],
                'value': round(val, 3),
                'nature': yin_yang,
                'description': rule['description']
            })
        return interpretations

    def _log_encoding(self, yao_vector):
        """记录六爻编码过程（可解释性）"""
        print("\n[六爻编码]")
        for i, pos in enumerate(YaoPosition):
            rule = self.encoding_rules[pos]
            yin_yang = "阳 —" if yao_vector[i] >= 0.5 else "阴 --"
            print(f"  {pos.name}({rule['name']}): {yao_vector[i]:.3f} ({yin_yang})")

    def enable_logging(self):
        """开启编码日志"""
        self._logger_enabled = True

    def disable_logging(self):
        """关闭编码日志"""
        self._logger_enabled = False

    def __repr__(self):
        return f"YaoEncoder(6 positions, {'logging: ON' if self._logger_enabled else 'logging: OFF'})"
