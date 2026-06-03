"""
安全八卦 — 六爻编码层 (Safety Yao Encoder)

将6条物理解析式编码为6维阴阳爻向量。
每条爻 ∈ [0,1], ≥0.5=阳(合规), <0.5=阴(违规)

这是整个安全八卦系统中唯一使用物理公式的地方。
进入L2之后的所有推理都在符号空间进行。
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, Tuple, Optional


# ============================================================
# 物性参数估算（从13维特征中推算质量/摩擦/强度等）
# ============================================================

def estimate_mass(features: Dict[str, float]) -> float:
    """从特征估算物体质量 (kg)"""
    st = features.get('strength_needed', 0.5)
    wr = features.get('weight_ratio', 0.5)
    vol_factor = features.get('support_area', 0.5) * 0.8 + 0.2
    return 0.05 + st * wr * vol_factor * 1.5


def estimate_friction_coeff(features: Dict[str, float]) -> float:
    """估算等效摩擦系数"""
    gq = features.get('grasp_surface_quality', 0.5)
    return 0.1 + gq * 0.7


def estimate_breaking_force(features: Dict[str, float]) -> float:
    """估算物体破坏力阈值 (N)"""
    fragility = features.get('fragility', 0.5)
    # 脆弱物体: 破坏力低 (3N 量级，如薄玻璃杯)
    # 坚固物体: 破坏力高 (80N 量级，如金属块)
    return 3.0 + (1.0 - fragility) * 77.0


def estimate_contact_area(features: Dict[str, float]) -> float:
    """估算接触面积 (m²)"""
    sa = features.get('support_area', 0.5)
    return 1e-5 + sa * 1e-3  # 0.01 to 1 cm²


def estimate_grasp_distance(features: Dict[str, float]) -> float:
    """估算抓取力臂 (m)，产生力矩的力臂"""
    sa = features.get('support_area', 0.5)
    return 0.01 + sa * 0.08  # 1-9 cm


# ============================================================
# 六爻编码公式
# ============================================================

def yao1_force_adequacy(F_grasp: float, mass: float, mu: float, g: float = 9.81) -> float:
    """
    初爻：抓取力充足性
    
    阳(合规): F ≥ mg/(2μ)  摩擦力足够防止滑脱
    阴(违规): F < 临界值    存在滑脱风险
    
    用 sigmoid 做连续化，避免硬二值化。
    """
    F_critical = mass * g / (2.0 * mu + 1e-6)
    ratio = F_grasp / max(F_critical, 0.01)
    # sigmoid 中心在 ratio=1.0 (刚好够力处为0.5)
    return 1.0 / (1.0 + np.exp(-5.0 * (ratio - 1.0)))


def yao2_force_safety(F_grasp: float, F_break: float) -> float:
    """
    二爻：抓取力安全裕度
    
    阳(合规): F ≤ 0.7 × F_break  不会破坏物体
    阴(违规): F 过高              存在破坏风险
    
    对脆弱物体特别敏感: 采用更陡的 sigmoid + 更早触发
    """
    # 对脆弱物体使用更保守的阈值
    safe_limit = F_break * 0.5  # 脆性材料安全系数更大
    ratio = F_grasp / max(safe_limit, 0.01)
    # 陡峭 sigmoid: 力超过安全限值50%即判定为明显违规
    return 1.0 / (1.0 + np.exp(8.0 * (ratio - 1.0)))


def yao3_friction_cone(mu: float, approach_angle: float) -> float:
    """
    三爻：摩擦锥约束
    
    阳(合规): 接触点位于摩擦锥内 (tan(angle) ≤ μ)
    阴(违规): 超出摩擦锥，可能滑移
    
    approach_angle 为度，转为弧度
    """
    angle_rad = np.radians(abs(approach_angle))
    friction_angle = np.arctan(mu)
    ratio = angle_rad / max(friction_angle, 0.01)
    return 1.0 / (1.0 + np.exp(5.0 * (ratio - 1.0)))


def yao4_joint_torque(F_grasp: float, d: float, tau_max: float = 5.0) -> float:
    """
    四爻：关节力矩约束
    
    阳(合规): τ = F × d ≤ τ_max
    阴(违规): 力矩超限
    """
    tau = F_grasp * d
    ratio = tau / max(tau_max, 0.1)
    return 1.0 / (1.0 + np.exp(5.0 * (ratio - 1.0)))


def yao5_stability_margin(F_grasp: float, mass: float, support_area: float, 
                           mu: float, g: float = 9.81) -> float:
    """
    五爻：稳定裕度（力封闭条件）
    
    简化力封闭判断：摩擦力 + 支撑力 > 重力扰动
    
    阳(合规): 力封闭成立，物体不会脱落
    阴(违规): 力封闭不满足
    """
    # 法向力 ≈ F_grasp (简化假设)
    normal_force = F_grasp
    friction_force = mu * normal_force
    
    # 需要抵抗的扰动力（重力 + 不确定性）
    disturbance = mass * g * (1.0 - support_area * 0.5)  # 支撑面积大→扰动小
    
    ratio = disturbance / max(friction_force, 0.01)
    return 1.0 / (1.0 + np.exp(5.0 * (ratio - 1.0)))


def yao6_penetration(approach_angle: float, fragility: float) -> float:
    """
    上爻：穿透风险评估
    
    阳(合规): 指尖力方向 + 接近角度不会穿透表面
    阴(违规): 存在穿透风险（特别是尖锐角度+脆弱物体）
    
    穿透风险 ∝ 接近角度 × 脆弱性
    """
    risk = (abs(approach_angle) / 90.0) * fragility
    return 1.0 / (1.0 + np.exp(5.0 * (risk - 0.5)))


# ============================================================
# 安全六爻编码器
# ============================================================

@dataclass
class SafetyYaoVector:
    """安全六爻向量及元信息"""
    yao: np.ndarray          # 6维爻向量 [0,1]⁶
    yin_yang: str            # 阴阳序列如 "阳-阴-阳-阳-..."
    violation_count: int     # 违规爻数（阴爻数）
    primary_risk: str        # 主要风险类型
    
    @property
    def is_all_yang(self) -> bool:
        return self.violation_count == 0
    
    def to_dict(self) -> dict:
        return {
            'yao': self.yao.tolist(),
            'yin_yang': self.yin_yang,
            'violation_count': self.violation_count,
            'primary_risk': self.primary_risk,
        }


class SafetyYaoEncoder:
    """
    安全六爻编码器
    
    输入: 抓取参数 + 物体特征 → 输出: 6维安全爻向量
    
    这是安全八卦的 L2 层——唯一涉及物理公式的地方。
    """
    
    def __init__(self, robot_tau_max: float = 5.0):
        self.tau_max = robot_tau_max
    
    def encode(self, features: Dict[str, float],
               strategy: Dict) -> SafetyYaoVector:
        """
        编码安全六爻
        
        Args:
            features: 13维物体特征 dict
            strategy: YLYW 策略输出 dict
                {type, force, approach_angle, speed, ...}
        
        Returns:
            SafetyYaoVector
        """
        # 步骤1: 从特征中估算物理量
        mass = estimate_mass(features)
        mu = estimate_friction_coeff(features)
        F_break = estimate_breaking_force(features)
        contact_area = estimate_contact_area(features)
        grasp_d = estimate_grasp_distance(features)
        
        # 步骤2: 从策略中获取抓取参数
        F_grasp = strategy.get('force', 0.5) * 50.0  # 归一化力→N (最大50N)
        approach_angle = strategy.get('approach_angle', 0)
        support_area = features.get('support_area', 0.5)
        fragility = features.get('fragility', 0.5)
        
        # 步骤3: 计算六爻
        y1 = yao1_force_adequacy(F_grasp, mass, mu)
        y2 = yao2_force_safety(F_grasp, F_break)
        y3 = yao3_friction_cone(mu, approach_angle)
        y4 = yao4_joint_torque(F_grasp, grasp_d, self.tau_max)
        y5 = yao5_stability_margin(F_grasp, mass, support_area, mu)
        y6 = yao6_penetration(approach_angle, fragility)
        
        yao = np.array([y1, y2, y3, y4, y5, y6])
        
        # 阴阳判定
        yin_yang = '-'.join('阳' if v >= 0.5 else '阴' for v in yao)
        violation_count = sum(1 for v in yao if v < 0.5)
        
        # 主要风险
        risk_types = ['力不足', '破坏风险', '滑移风险', '力矩超限', '不稳定', '穿透风险']
        if violation_count > 0:
            worst_idx = int(np.argmin(yao))
            primary_risk = risk_types[worst_idx]
        else:
            primary_risk = '无风险'
        
        return SafetyYaoVector(
            yao=yao,
            yin_yang=yin_yang,
            violation_count=violation_count,
            primary_risk=primary_risk,
        )
    
    def explain(self, safety_vec: SafetyYaoVector,
                features: Dict[str, float],
                strategy: Dict) -> str:
        """生成可解释报告"""
        lines = []
        yao_names = ['初爻(力足)', '二爻(力安)', '三爻(摩擦)', 
                     '四爻(力矩)', '五爻(稳定)', '上爻(穿透)']
        risk_details = [
            f'抓取力 {strategy.get("force",0)*50:.1f}N vs 临界力',
            f'抓取力 vs 破坏力阈值',
            f'接近角 {strategy.get("approach_angle",0)}° vs 摩擦锥',
            f'力矩 vs 关节极限 {self.tau_max}Nm',
            f'力封闭 vs 重力扰动',
            f'穿透风险: 角度×脆弱性',
        ]
        
        for i, (name, val) in enumerate(zip(yao_names, safety_vec.yao)):
            status = '✅阳' if val >= 0.5 else '❌阴'
            lines.append(f'  {name}: {val:.3f} ({status}) — {risk_details[i]}')
        
        lines.append(f'\n  综合: {safety_vec.violation_count}/6处违规 ({safety_vec.yin_yang})')
        lines.append(f'  主要风险: {safety_vec.primary_risk}')
        
        return '\n'.join(lines)
