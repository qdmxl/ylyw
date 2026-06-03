"""
先验手册子包

包含：
- trigram_base:  八卦基元（L1）：8个基本属性及其物理映射
- yao_encoder:   六爻编码器（L2）：物理世界状态 → 6爻值
- hexagram_rules: 六十四卦规则库（L3）：卦象 → 抓取策略
- prior_manual:   主整合类：三层联合推理
"""
from .prior_manual import PriorManual
from .trigram_base import TrigramBase, Trigram
from .yao_encoder import YaoEncoder, YaoPosition
from .hexagram_rules import HexagramRuleBase, Hexagram

__all__ = [
    "PriorManual",
    "TrigramBase", "Trigram",
    "YaoEncoder", "YaoPosition",
    "HexagramRuleBase", "Hexagram",
]
