"""
双八卦仲裁层 (Dual Bagua Arbiter)

将策略八卦的输出与安全八卦的输出合并，产生最终的安全抓取指令。

核心逻辑:
  - SAFE → 策略八卦输出原样放行
  - CAUTION → 降速 + 策略八卦输出
  - WARNING → 降力20% + 爻位修正
  - DANGER → 降力40% + 切换谨慎策略族
  - CRITICAL → 大幅降力或触发变卦重新选策略
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from ylyw.safety_bagua.safety_yao_encoder import SafetyYaoEncoder, SafetyYaoVector
from ylyw.safety_bagua.safety_hexagram_rules import (
    SafetyHexagramRules, SafetyLevel, SafetyAction
)


# ============================================================
# 最终输出数据结构
# ============================================================
@dataclass
class SafeStrategyOutput:
    """双层八卦仲裁后的最终抓取策略"""
    
    # 原始策略八卦输出
    strategy_type: str
    original_force: float
    original_angle: float
    original_speed: str
    
    # 安全八卦修正
    safety_level: SafetyLevel
    safety_hexagram: str
    safety_similarity: float
    safety_yao: SafetyYaoVector
    
    # 最终输出
    final_force: float
    final_speed: str
    final_angle: float
    force_modifier_total: float      # 总的力修正系数
    
    # 可解释性
    reasoning_trace: List[str] = field(default_factory=list)
    risk_tags: List[str] = field(default_factory=list)
    
    # 是否需要变卦
    needs_hexagram_change: bool = False
    suggested_hexagram: str = ''


# ============================================================
# 双八卦仲裁器
# ============================================================
class DualBaguaArbiter:
    """
    双八卦仲裁器
    
    结合策略八卦和物理八卦（安全八卦）的输出，
    进行安全仲裁，产生最终的可执行指令。
    """
    
    def __init__(self, robot_tau_max: float = 5.0):
        self.safety_encoder = SafetyYaoEncoder(robot_tau_max)
        self.safety_rules = SafetyHexagramRules()
    
    def arbitrate(self, 
                  features: Dict[str, float],
                  strategy_output: Dict,
                  perception: Dict) -> SafeStrategyOutput:
        """
        双八卦仲裁
        
        Args:
            features: 13维物体特征
            strategy_output: 策略八卦输出 {type, force, approach_angle, speed, hexagram, ...}
            perception: 策略八卦感知结果 {yao_vector, trigram_memberships, best_hexagram, ...}
        
        Returns:
            SafeStrategyOutput: 安全仲裁后的最终策略
        """
        trace = []
        
        # === 步骤1: 安全八卦推理 ===
        trace.append("【步骤1】安全八卦推理")
        
        safety_yao = self.safety_encoder.encode(features, strategy_output)
        safety_action, safety_idx, safety_sim = \
            self.safety_rules.get_safety_action(safety_yao.yao)
        
        safety_name = self.safety_rules.get_hexagram_name(safety_idx)
        
        trace.append(self.safety_encoder.explain(safety_yao, features, strategy_output))
        trace.append(self.safety_rules.explain_match(
            safety_yao.yao, safety_idx, safety_sim, safety_action
        ))
        
        # === 步骤2: 安全仲裁 ===
        trace.append(f"\n【步骤2】安全仲裁: {safety_action.level.value}")
        
        orig_force = strategy_output.get('force', 0.5)
        orig_angle = strategy_output.get('approach_angle', 0)
        orig_speed = strategy_output.get('speed', 'medium')
        orig_type = strategy_output.get('type', 'generic')
        
        final_force = orig_force
        final_speed = orig_speed
        final_angle = orig_angle
        needs_change = False
        suggested_hex = ''
        
        if safety_action.level == SafetyLevel.SAFE:
            trace.append("  全合规: 策略八卦输出原样放行")
            force_mod_total = 1.0
            
        elif safety_action.level == SafetyLevel.CAUTION:
            trace.append(f"  轻微风险: 降速到 {safety_action.speed_override}")
            final_speed = safety_action.speed_override or final_speed
            force_mod_total = safety_action.force_modifier
            final_force = orig_force * force_mod_total
            
        elif safety_action.level == SafetyLevel.WARNING:
            trace.append(f"  中度风险: 降力到 {safety_action.force_modifier:.0%}")
            final_force = orig_force * safety_action.force_modifier
            final_speed = safety_action.speed_override or final_speed
            force_mod_total = safety_action.force_modifier
            
        elif safety_action.level == SafetyLevel.DANGER:
            trace.append(f"  高风险: 降力到 {safety_action.force_modifier:.0%}，切换谨慎模式")
            final_force = orig_force * safety_action.force_modifier
            final_speed = 'slow'
            # 策略覆盖: 切换到谨慎策略族
            if safety_action.strategy_override == 'cautious':
                if 'vigorous' in orig_type or 'forceful' in orig_type:
                    needs_change = True
                    # 变卦: 寻找谨慎的替代卦
                    trace.append("  触发变卦: 暴力策略在物理高风险场景下不安全")
                    
            force_mod_total = safety_action.force_modifier
            
        elif safety_action.level == SafetyLevel.CRITICAL:
            trace.append(f"  极度危险: 大幅降力到 {safety_action.force_modifier:.0%}")
            final_force = orig_force * safety_action.force_modifier
            final_speed = 'slow'
            needs_change = True
            trace.append("  触发变卦: 当前策略在物理上不可执行")
            force_mod_total = safety_action.force_modifier
        
        # 同时应用爻位关系修正（来自策略八卦的 L3+ 修正）
        yao_modifier = strategy_output.get('force_modifier', 1.0)
        final_force *= yao_modifier
        force_mod_total *= yao_modifier
        
        # 裁剪
        final_force = max(0.05, min(1.0, final_force))
        
        trace.append(f"\n【步骤3】最终输出")
        trace.append(f"  力: {orig_force:.2f} × {force_mod_total:.2f} = {final_force:.2f}")
        trace.append(f"  速度: {final_speed}")
        trace.append(f"  角度: {final_angle}°")
        trace.append(f"  安全等级: {safety_action.level.value}")
        if needs_change:
            trace.append(f"  ⚠️ 建议变卦: 物理约束层判定当前卦象不安全")
        
        return SafeStrategyOutput(
            strategy_type=orig_type,
            original_force=orig_force,
            original_angle=orig_angle,
            original_speed=orig_speed,
            safety_level=safety_action.level,
            safety_hexagram=safety_name,
            safety_similarity=float(safety_sim),
            safety_yao=safety_yao,
            final_force=final_force,
            final_speed=final_speed,
            final_angle=final_angle,
            force_modifier_total=force_mod_total,
            reasoning_trace=trace,
            risk_tags=safety_action.risk_tags,
            needs_hexagram_change=needs_change,
            suggested_hexagram=suggested_hex,
        )


# ============================================================
# 集成到 PriorManual
# ============================================================

class SafePriorManual:
    """
    带安全八卦的增强版 PriorManual
    
    在原有推理链上附加安全仲裁层。
    """
    
    def __init__(self, verbose: bool = False):
        from ylyw.prior_manual.prior_manual import PriorManual
        self.strategy_manual = PriorManual(verbose=verbose)
        self.arbiter = DualBaguaArbiter()
        self.verbose = verbose
    
    def process_safe(self, object_features: Dict[str, float]) -> SafeStrategyOutput:
        """
        完整推理 + 安全仲裁
        
        Args:
            object_features: 13维物体特征
        
        Returns:
            SafeStrategyOutput: 安全仲裁后的最终策略
        """
        # 策略八卦推理
        perception, strategy = self.strategy_manual.process(object_features)
        
        # 双八卦安全仲裁
        safe_output = self.arbiter.arbitrate(
            features=object_features,
            strategy_output=strategy,
            perception=perception,
        )
        
        if self.verbose:
            for line in safe_output.reasoning_trace:
                print(line)
        
        return safe_output
