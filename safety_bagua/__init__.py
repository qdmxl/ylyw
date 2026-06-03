"""
安全八卦 (Safety Bagua) — YLYW Phase 2: Physical Constraint Layer

双层八卦架构:
  策略八卦 (prior_manual) → 决定"抓什么怎么抓"
  安全八卦 (safety_bagua)  → 验证"能否安全执行"

两层共享相同的三层架构 (L1八卦→L2六爻→L3六十四卦)，
均采用零样本符号推理，无需训练数据。
"""

from ylyw.safety_bagua.safety_yao_encoder import SafetyYaoEncoder, SafetyYaoVector
from ylyw.safety_bagua.safety_hexagram_rules import (
    SafetyHexagramRules, SafetyLevel, SafetyAction
)
from ylyw.safety_bagua.dual_bagua_arbiter import (
    DualBaguaArbiter, SafeStrategyOutput, SafePriorManual
)

__all__ = [
    'SafetyYaoEncoder', 'SafetyYaoVector',
    'SafetyHexagramRules', 'SafetyLevel', 'SafetyAction',
    'DualBaguaArbiter', 'SafeStrategyOutput', 'SafePriorManual',
]
