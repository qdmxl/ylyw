"""
先验手册主类 (Prior Manual)

整合三层先验知识，提供统一的感知-推理-决策接口：

    L1 八卦基元  → 物理属性分类
    L2 六爻编码  → 状态向量化
    L3 六十四卦  → 策略匹配

这是整个 YLYW 系统的"灵魂"。
所有推理规则都硬编码在这里——不需要任何数据训练，
纯粹靠预定义的易理知识工作。

使用方式:
    >>> from ylyw.prior_manual import PriorManual
    >>> manual = PriorManual()
    >>> features = {'stability': 0.2, 'roll_tendency': 0.9, ...}
    >>> result = manual.perceive_and_encode(features)
    >>> strategy = manual.get_grasp_strategy(result)
    >>> print(manual.explain_reasoning(result))
"""

import numpy as np
from .trigram_base import TrigramBase, Trigram
from .yao_encoder import YaoEncoder, YaoPosition
from .hexagram_rules import HexagramRuleBase, Hexagram


class PriorManual:
    """
    先验手册：将《易经》的符号化知识封装为可调用接口

    工作流程:
        1. 感知: 接收物体物理特征 → 计算八卦隶属度
        2. 编码: 物理特征 → 六爻向量
        3. 推理: 六爻向量 → 匹配最佳卦象
        4. 决策: 卦象 → 抓取策略
        5. 解释: 输出可读的推理链

    Attributes:
        trigram_base: 八卦基元（L1）
        yao_encoder: 六爻编码器（L2）
        hexagram_rules: 六十四卦规则库（L3）
        verbose: 是否打印详细推理日志
    """

    def __init__(self, verbose=False):
        """
        初始化先验手册

        Args:
            verbose: 是否开启详细日志输出
        """
        self.trigram_base = TrigramBase()
        self.yao_encoder = YaoEncoder()
        self.hexagram_rules = HexagramRuleBase()

        self.verbose = verbose
        if verbose:
            self.yao_encoder.enable_logging()

    def perceive_and_encode(self, object_features):
        """
        感知一个物体，输出完整的推理结果

        这是先验手册的核心推理链路：
        L1 → L2 → L3

        Args:
            object_features: dict, 包含物体的物理特征
                必需字段:
                - stability: 稳定性 [0,1]
                - roll_tendency: 滚动倾向 [0,1]
                - strength_needed: 所需抓取力 [0,1]
                - fragility: 脆弱性 [0,1]
                - task_priority: 任务优先级 [0,1]
                - reachability: 可达性 [0,1]

                可选字段:
                - support_area: 支撑面积 [0,1]
                - occlusion: 遮挡程度 [0,1]
                - obstacle_density: 周围障碍密度 [0,1]
                - grasp_surface_quality: 抓取表面质量 [0,1]
                - weight_ratio: 重量比 [0,1]
                - visibility: 可见性 [0,1]
                - deformability: 变形能力 [0,1]

        Returns:
            dict: {
                'yao_vector': np.ndarray(6,),
                'trigram_memberships': np.ndarray(8,),
                'dominant_trigram': Trigram,
                'dominant_trigram_score': float,
                'best_hexagram': Hexagram or None,
                'hexagram_match_score': float,
                'top_k_hexagrams': [(Hexagram, float), ...],
            }
        """
        if self.verbose:
            print("\n" + "=" * 60)
            print("[先验手册] 开始感知与编码")
            print("=" * 60)

        # === L1: 八卦基元——计算8卦隶属度 ===
        trigram_memberships = self.trigram_base.get_all_memberships(object_features)
        dominant_trigram, dominant_score = self.trigram_base.get_dominant_trigram(object_features)

        if self.verbose:
            tri_info = self.trigram_base.get_trigram_info(dominant_trigram)
            print(f"\n[L1 八卦映射]")
            print(f"  主导卦象: {dominant_trigram.name} {tri_info.get('symbol', '?')} "
                  f"「{tri_info.get('name', '?')}」— {tri_info.get('meaning', '?')}")
            print(f"  隶属度: {dominant_score:.3f}")

        # === L2: 六爻编码——物理特征 → 6维向量 ===
        yao_vector = self.yao_encoder.encode(object_features)

        if self.verbose:
            self._print_yao_analysis(yao_vector)

        # === L3: 六十四卦规则——爻向量 → 最佳卦象 ===
        best_hexagram, match_score = self.hexagram_rules.get_best_hexagram(yao_vector)
        top_k = self.hexagram_rules.get_top_k_hexagrams(yao_vector, k=3)

        if self.verbose and best_hexagram:
            rule = self.hexagram_rules.get_rule(best_hexagram)
            print(f"\n[L3 卦象匹配]")
            print(f"  最佳卦象: {best_hexagram.name}「{rule['name']}」"
                  f" {rule['upper_lower'][0]}{rule['upper_lower'][1]}")
            print(f"  相似度: {match_score:.4f}")
            print(f"  卦辞: {rule['description']}")
            print(f"  Top-3: {[(h.name, f'{s:.4f}') for h, s in top_k]}")

        return {
            'yao_vector': yao_vector,
            'trigram_memberships': trigram_memberships,
            'dominant_trigram': dominant_trigram,
            'dominant_trigram_score': dominant_score,
            'best_hexagram': best_hexagram,
            'hexagram_match_score': match_score,
            'top_k_hexagrams': top_k,
        }

    def get_grasp_strategy(self, perception_result):
        """
        根据感知结果输出抓取策略

        Args:
            perception_result: perceive_and_encode() 的返回值

        Returns:
            dict: {
                'type': str,       # 抓取类型
                'force': float,    # 力预设 [0,1]
                'approach_angle': float,  # 接近角度
                'speed': str,      # 接近速度
                'cautions': [str], # 注意事项
                'hexagram': str,   # 来源卦象名
            }
        """
        best_hexagram = perception_result.get('best_hexagram')

        if best_hexagram is None:
            rule = self.hexagram_rules.default_rule
        else:
            rule = self.hexagram_rules.get_rule(best_hexagram)

        strategy = rule['grasp_strategy'].copy()
        strategy['hexagram'] = rule['name']

        if self.verbose:
            print(f"\n[决策输出]")
            print(f"  抓取类型: {strategy['type']}")
            print(f"  力预设: {strategy['force']:.2f}")
            print(f"  接近速度: {strategy['speed']}")
            print(f"  来源卦象: {strategy['hexagram']}")
            if strategy['cautions']:
                print(f"  注意事项: {'; '.join(strategy['cautions'])}")

        return strategy

    def process(self, object_features):
        """
        一站式处理：感知 + 决策

        先验手册的最高层接口，输入物体特征，直接输出动作策略。

        Args:
            object_features: dict, 物体物理特征

        Returns:
            (perception_result, grasp_strategy)
        """
        perception = self.perceive_and_encode(object_features)
        strategy = self.get_grasp_strategy(perception)
        return perception, strategy

    def explain_reasoning(self, perception_result):
        """
        输出可解释的推理链

        这是 YLYW 相对于黑箱深度学习模型的核心优势——
        每一步推理都有明确的语义，完全可追溯、可审计。

        Args:
            perception_result: perceive_and_encode() 的返回值

        Returns:
            str: 格式化的推理链文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append("【YLYW 先验推理链】" + " " * 20)
        lines.append("=" * 60)

        # --- L1 ---
        dt = perception_result['dominant_trigram']
        dt_score = perception_result['dominant_trigram_score']
        tri_info = self.trigram_base.get_trigram_info(dt)
        lines.append(f"\n▎L1 八卦基元映射")
        lines.append(f"  物体呈现「{tri_info.get('name', '?')}」卦（{tri_info.get('meaning', '?')}）特性")
        lines.append(f"  隶属度: {dt_score:.2f}")

        # --- L2 ---
        yao = perception_result['yao_vector']
        pos_names = ['初爻(基础稳定性)', '二爻(可达性)', '三爻(力需求)',
                     '四爻(脆弱性)', '五爻(任务优先级)', '上爻(环境约束)']
        lines.append(f"\n▎L2 六爻状态分析")
        for i, (name, val) in enumerate(zip(pos_names, yao)):
            yin_yang = "阳爻（— 强/利）" if val >= 0.5 else "阴爻（-- 弱/不利）"
            bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
            lines.append(f"  {name:<20s} [{bar}] {val:.3f} → {yin_yang}")

        # --- L3 ---
        hexagram = perception_result['best_hexagram']
        if hexagram:
            rule = self.hexagram_rules.get_rule(hexagram)
            lines.append(f"\n▎L3 卦象综合判断")
            lines.append(f"  卦象: 「{rule['name']}」 {rule['upper_lower'][0]}{rule['upper_lower'][1]}")
            lines.append(f"  卦辞: {rule['description']}")
            lines.append(f"  匹配度: {perception_result['hexagram_match_score']:.4f}")

            # Top-k 备选
            top_k = perception_result.get('top_k_hexagrams', [])
            if len(top_k) > 1:
                alt_names = []
                for h, s in top_k[1:]:
                    r = self.hexagram_rules.get_rule(h)
                    n = r.get('name', '?')
                    alt_names.append(f'「{n}」({s:.3f})')
                lines.append(f"  备选卦象: {', '.join(alt_names)}")

        # --- Decision ---
        strategy = self.get_grasp_strategy(perception_result)
        lines.append(f"\n▎决策输出")
        lines.append(f"  抓取类型: {strategy['type']}")
        lines.append(f"  力预设: {strategy['force']:.2f}  |  接近角: {strategy['approach_angle']}°")
        lines.append(f"  速度: {strategy['speed']}")
        if strategy['cautions']:
            lines.append(f"  注意事项: {'; '.join(strategy['cautions'])}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def _print_yao_analysis(self, yao_vector):
        """打印六爻分析（verbose模式）"""
        print(f"\n[L2 六爻编码]")
        positions = ['初爻(稳定性)', '二爻(可达性)', '三爻(力需求)',
                     '四爻(脆弱性)', '五爻(优先级)', '上爻(环境)']
        for name, val in zip(positions, yao_vector):
            yin_yang = "阳 —" if val >= 0.5 else "阴 --"
            bar = "▌" * int(val * 8)
            print(f"  {name}: {val:.3f} [{bar}] {yin_yang}")

    def set_verbose(self, verbose):
        """设置详细日志开关"""
        self.verbose = verbose
        if verbose:
            self.yao_encoder.enable_logging()
        else:
            self.yao_encoder.disable_logging()

    def __repr__(self):
        return (f"PriorManual(\n"
                f"  L1: {self.trigram_base}\n"
                f"  L2: {self.yao_encoder}\n"
                f"  L3: {self.hexagram_rules}\n"
                f"  verbose: {self.verbose}\n"
                f")")
