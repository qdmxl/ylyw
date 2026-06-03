"""
安全八卦 — 六十四卦安全规则库 (Safety Hexagram Rules)

L3层: 6维安全爻向量 → 64卦匹配 → 安全等级 + 修正动作

64个卦覆盖从"全合规(乾为天)"到"极度危险(火水未济)"的安全状态空间。
每个卦关联: 安全等级、修正动作、风险描述。
"""

import numpy as np
from enum import Enum
from typing import Dict, Tuple, List, Optional, NamedTuple
from dataclasses import dataclass


# ============================================================
# 安全等级
# ============================================================
class SafetyLevel(Enum):
    SAFE = "SAFE"           # 全合规，直接放行
    CAUTION = "CAUTION"     # 轻微风险，降速
    WARNING = "WARNING"     # 中度风险，调整力参数
    DANGER = "DANGER"       # 高风险，大幅降力
    CRITICAL = "CRITICAL"   # 极度危险，终止/换策略


# ============================================================
# 安全修正动作
# ============================================================
@dataclass
class SafetyAction:
    """安全修正动作"""
    level: SafetyLevel
    force_modifier: float         # 力修正系数 (0=取消, 1=不变)
    speed_override: Optional[str] # 强制速度等级
    angle_override: Optional[float]  # 强制接近角度
    strategy_override: Optional[str] # 强制切换策略
    description: str              # 可解释描述
    risk_tags: List[str]          # 风险标签


# ============================================================
# 64卦 → 安全规则映射
# ============================================================

class SafetyHexagramRules:
    """
    安全六十四卦规则库
    
    6条爻的阴阳组合 → 2⁶=64种安全状态 → 安全等级 + 修正动作
    """
    
    def __init__(self):
        self._rules = self._build_rules()
        self._ideal_templates = self._build_ideal_templates()
    
    def _build_ideal_templates(self) -> Dict[str, np.ndarray]:
        """
        构建64卦的理想爻模板（用于余弦相似度匹配）
        
        每个卦的理想模板是6维向量，阴阳对应:
          阳(合规): 0.85±0.05
          阴(违规): 0.15±0.05
        
        六十四卦的阴阳组合:
          000000 (纯阴-坤) → 111111 (纯阳-乾)
        """
        # 64卦的6爻阴阳序列（从初爻到上爻）
        # 0=阴, 1=阳
        hexagram_lines = {}
        for i in range(64):
            # i 的6位二进制表示 = 六爻序列
            lines = [(i >> j) & 1 for j in range(6)]  # [初爻, ..., 上爻]
            hexagram_lines[i] = lines
        
        templates = {}
        for i in range(64):
            lines = hexagram_lines[i]
            # 阳爻 ≈ 0.85, 阴爻 ≈ 0.15
            template = np.array([0.85 if l else 0.15 for l in lines])
            templates[str(i)] = template
        
        return templates
    
    def _build_rules(self) -> Dict[int, SafetyAction]:
        """
        构建64卦安全规则
        
        规则基于违规爻数和违规爻位的重要性:
        - 0处违规 (111111): SAFE
        - 1处违规: CAUTION (轻微)
        - 2处违规: WARNING (中等)
        - 3处违规: DANGER (严重)
        - 4+处违规: CRITICAL
        
        特定爻位有更高权重:
        - 二爻(破坏风险) 和 上爻(穿透) 权重 2x
        - 初爻(力不足) 和 四爻(力矩) 权重 1.5x
        """
        rules = {}
        
        for i in range(64):
            lines = [(i >> j) & 1 for j in range(6)]
            violation_count = sum(1 for l in lines if l == 0)
            
            # 加权违规数: 考虑爻位重要性
            weighted = 0
            for j, l in enumerate(lines):
                if l == 0:  # 阴 = 违规
                    if j == 1 or j == 5:    # 二爻或上爻
                        weighted += 2
                    elif j == 0 or j == 3:  # 初爻或四爻
                        weighted += 1.5
                    else:
                        weighted += 1
            
            # 识别具体风险
            risks = []
            if lines[0] == 0: risks.append('force_insufficient')
            if lines[1] == 0: risks.append('fragility_risk')
            if lines[2] == 0: risks.append('slip_risk')
            if lines[3] == 0: risks.append('torque_overload')
            if lines[4] == 0: risks.append('stability_loss')
            if lines[5] == 0: risks.append('penetration_risk')
            
            # 安全等级 + 修正动作
            if weighted == 0:
                level = SafetyLevel.SAFE
                force_mod = 1.0
                speed_ov = None
                strategy_ov = None
                desc = "全合规，直接执行"
            elif weighted <= 1.5:
                level = SafetyLevel.CAUTION
                force_mod = 0.95
                speed_ov = 'slow'
                strategy_ov = None
                desc = f"轻微风险: {', '.join(risks)}，降速处理"
            elif weighted <= 3:
                level = SafetyLevel.WARNING
                force_mod = 0.80
                speed_ov = 'slow'
                strategy_ov = None
                desc = f"中度风险: {', '.join(risks)}，降力20%"
            elif weighted <= 5:
                level = SafetyLevel.DANGER
                force_mod = 0.60
                speed_ov = 'slow'
                strategy_ov = 'cautious'  # 切换到谨慎策略族
                desc = f"高风险: {', '.join(risks)}，降力40%并切换谨慎模式"
            else:
                level = SafetyLevel.CRITICAL
                force_mod = 0.30
                speed_ov = 'slow'
                strategy_ov = 'abort'  # 终止
                desc = f"极度危险: {', '.join(risks)}，大幅降力或终止"
            
            rules[i] = SafetyAction(
                level=level,
                force_modifier=force_mod,
                speed_override=speed_ov,
                angle_override=0.0,  # 风险场景用垂直下抓
                strategy_override=strategy_ov,
                description=desc,
                risk_tags=risks,
            )
        
        return rules
    
    def get_rule(self, hexagram_index: int) -> SafetyAction:
        """获取卦对应的安全规则"""
        return self._rules.get(hexagram_index, 
            SafetyAction(SafetyLevel.CRITICAL, 0.3, 'slow', 0.0, 'abort', 
                        '未知安全状态，默认终止', ['unknown']))
    
    def match(self, yao_vector: np.ndarray) -> Tuple[int, float, List[Tuple[int, float]]]:
        """
        余弦相似度匹配最佳安全卦
        
        Args:
            yao_vector: 6维安全爻向量 [0,1]⁶
        
        Returns:
            (best_hexagram_index, similarity, top3_list)
        """
        best_idx = 0
        best_sim = -1.0
        sims = []
        
        for idx, template in self._ideal_templates.items():
            idx_int = int(idx)
            sim = np.dot(yao_vector, template) / (
                np.linalg.norm(yao_vector) * np.linalg.norm(template) + 1e-8
            )
            sims.append((idx_int, sim))
        
        sims.sort(key=lambda x: -x[1])
        best_idx, best_sim = sims[0]
        top3 = sims[:3]
        
        return best_idx, best_sim, top3
    
    def get_safety_action(self, yao_vector: np.ndarray) -> Tuple[SafetyAction, int, float]:
        """
        完整流程: 匹配安全卦 → 返回安全动作
        
        Returns:
            (SafetyAction, hexagram_index, similarity)
        """
        idx, sim, top3 = self.match(yao_vector)
        action = self.get_rule(idx)
        return action, idx, sim
    
    def get_hexagram_name(self, idx: int) -> str:
        """获取卦索引 → 卦名（使用64卦标准序号 + 阴阳序列）"""
        lines = [(idx >> j) & 1 for j in range(6)]
        yin_yang = ''.join('—' if l else '--' for l in lines)
        
        # 64卦标准名映射（基于上下卦）
        upper = (lines[3] << 2) | (lines[4] << 1) | lines[5]
        lower = (lines[0] << 2) | (lines[1] << 1) | lines[2]
        
        trigram_names = ['坤', '震', '坎', '兑', '艮', '离', '巽', '乾']
        upper_name = trigram_names[upper]
        lower_name = trigram_names[lower]
        
        # 特殊卦名
        hex_names = {
            (7, 7): '乾为天', (0, 0): '坤为地', (4, 7): '山天大畜',
            (6, 0): '风地观', (3, 0): '泽地萃', (1, 0): '雷地豫',
            (7, 3): '天泽履', (7, 1): '天雷无妄', (7, 2): '天水讼',
            (7, 4): '天山遁', (7, 5): '天火同人', (7, 6): '天风姤',
            (0, 1): '地雷复', (0, 3): '地泽临', (0, 7): '地天泰',
            (5, 7): '火天大有', (2, 7): '水天需', (1, 7): '雷天大壮',
            (1, 1): '震为雷', (3, 3): '兑为泽', (5, 5): '离为火',
            (2, 2): '坎为水', (4, 4): '艮为山', (6, 6): '巽为风',
            (2, 5): '水火既济', (5, 2): '火水未济',
        }
        
        key = (upper, lower)
        if key in hex_names:
            return hex_names[key]
        else:
            return f'{upper_name}{lower_name}(卦{idx})'
    
    def explain_match(self, yao_vector: np.ndarray, idx: int, sim: float,
                      action: SafetyAction) -> str:
        """生成可解释匹配报告"""
        lines = []
        lines.append(f'安全卦: {self.get_hexagram_name(idx)} (相似度={sim:.4f})')
        lines.append(f'安全等级: {action.level.value}')
        lines.append(f'力修正: ×{action.force_modifier:.2f}')
        lines.append(f'速度: {action.speed_override or "不变"}')
        if action.strategy_override:
            lines.append(f'策略覆盖: {action.strategy_override}')
        lines.append(f'风险: {", ".join(action.risk_tags) if action.risk_tags else "无"}')
        lines.append(f'描述: {action.description}')
        return '\n'.join(lines)
