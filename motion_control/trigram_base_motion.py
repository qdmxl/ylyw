#!/usr/bin/env python3
"""
L1 八卦运动基元 (Trigram Base for Motion Control)
将躯干/步态状态映射为8个卦的连续模糊隶属度
"""
import numpy as np

class TrigramMotionBase:
    """八卦运动基元层：连续模糊隶属度"""
    
    # 八卦-运动原型映射 (6维: 姿态稳定, 质心高度, 力分布, ZMP裕度, 扰动, 地形)
    TRIGRAM_PROTOTYPES = {
        'qian': {  # 乾 - 驱动力基元 (健)
            'name': '乾', 'symbol': '☰', 'virtue': '健',
            'posture': 0.85, 'com_height': 0.80, 'force_dist': 0.90,
            'zmp_margin': 0.80, 'disturbance': 0.15, 'terrain': 0.70
        },
        'kun': {  # 坤 - 柔顺性基元 (顺)
            'name': '坤', 'symbol': '☷', 'virtue': '顺',
            'posture': 0.70, 'com_height': 0.40, 'force_dist': 0.30,
            'zmp_margin': 0.60, 'disturbance': 0.40, 'terrain': 0.50
        },
        'zhen': {  # 震 - 速度基元 (动)
            'name': '震', 'symbol': '☳', 'virtue': '动',
            'posture': 0.30, 'com_height': 0.55, 'force_dist': 0.55,
            'zmp_margin': 0.25, 'disturbance': 0.85, 'terrain': 0.60
        },
        'gen': {  # 艮 - 稳定性基元 (止)
            'name': '艮', 'symbol': '☶', 'virtue': '止',
            'posture': 0.95, 'com_height': 0.65, 'force_dist': 0.75,
            'zmp_margin': 0.95, 'disturbance': 0.05, 'terrain': 0.50
        },
        'li': {  # 离 - 感知基元 (明/附丽)
            'name': '离', 'symbol': '☲', 'virtue': '明',
            'posture': 0.55, 'com_height': 0.60, 'force_dist': 0.50,
            'zmp_margin': 0.50, 'disturbance': 0.40, 'terrain': 0.90
        },
        'kan': {  # 坎 - 恢复基元 (陷/险)
            'name': '坎', 'symbol': '☵', 'virtue': '险',
            'posture': 0.25, 'com_height': 0.35, 'force_dist': 0.40,
            'zmp_margin': 0.20, 'disturbance': 0.70, 'terrain': 0.40
        },
        'dui': {  # 兑 - 协调基元 (悦)
            'name': '兑', 'symbol': '☱', 'virtue': '悦',
            'posture': 0.65, 'com_height': 0.70, 'force_dist': 0.60,
            'zmp_margin': 0.65, 'disturbance': 0.30, 'terrain': 0.55
        },
        'xun': {  # 巽 - 适应基元 (入)
            'name': '巽', 'symbol': '☴', 'virtue': '入',
            'posture': 0.50, 'com_height': 0.50, 'force_dist': 0.45,
            'zmp_margin': 0.50, 'disturbance': 0.45, 'terrain': 0.55
        },
    }
    
    FEATURE_KEYS = ['posture', 'com_height', 'force_dist', 'zmp_margin', 'disturbance', 'terrain']
    
    def __init__(self, sensitivity=1.5):
        self.sensitivity = sensitivity
        
    def compute_membership(self, state_vector):
        """
        计算8维八卦隶属度向量
        
        Args:
            state_vector: 6维状态 [姿态, 质心高度, 力分布, ZMP裕度, 扰动, 地形]
                         全部归一化到[0,1]
        
        Returns:
            membership: dict {卦名: 隶属度}
            dominant: 主导卦名
        """
        f = np.array(state_vector)
        memberships = {}
        
        for key, proto in self.TRIGRAM_PROTOTYPES.items():
            p = np.array([proto[k] for k in self.FEATURE_KEYS])
            # 高斯核：max(0, 1 - |diff| * sensitivity)
            diff = np.abs(f - p)
            mu = np.mean(np.maximum(0, 1.0 - diff * self.sensitivity))
            memberships[key] = mu
        
        dominant = max(memberships, key=memberships.get)
        return memberships, dominant
    
    def get_prototype(self, trigram_key):
        """获取卦象原型向量"""
        proto = self.TRIGRAM_PROTOTYPES[trigram_key]
        return np.array([proto[k] for k in self.FEATURE_KEYS])
    
    def get_all_prototypes(self):
        """获取所有卦象原型矩阵 (8×6)"""
        return np.array([[self.TRIGRAM_PROTOTYPES[k][fk] 
                         for fk in self.FEATURE_KEYS] 
                        for k in self.TRIGRAM_PROTOTYPES])


if __name__ == '__main__':
    # Quick test
    tmb = TrigramMotionBase()
    
    # Test: stable standing state
    stable = [0.9, 0.8, 0.7, 0.9, 0.1, 0.5]
    mem, dom = tmb.compute_membership(stable)
    print("=== 稳定站立 ===")
    print(f"State: {stable}")
    print(f"Dominant: {dom} ({tmb.TRIGRAM_PROTOTYPES[dom]['name']})")
    for k, v in sorted(mem.items(), key=lambda x: -x[1])[:3]:
        print(f"  {k} ({tmb.TRIGRAM_PROTOTYPES[k]['name']}): {v:.3f}")
    
    # Test: disturbed state
    disturbed = [0.2, 0.3, 0.4, 0.15, 0.85, 0.4]
    mem, dom = tmb.compute_membership(disturbed)
    print("\n=== 受扰动状态 ===")
    print(f"State: {disturbed}")
    print(f"Dominant: {dom} ({tmb.TRIGRAM_PROTOTYPES[dom]['name']})")
    for k, v in sorted(mem.items(), key=lambda x: -x[1])[:3]:
        print(f"  {k} ({tmb.TRIGRAM_PROTOTYPES[k]['name']}): {v:.3f}")
