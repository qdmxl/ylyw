#!/usr/bin/env python3
"""
L2 六爻状态编码 (Yao Encoder for Motion Control)
将机器人运动状态编码为6爻向量
"""
import numpy as np

class MotionYaoEncoder:
    """
    六爻编码层：6维状态 → 6爻值向量 [0,1]
    
    六爻映射:
      初爻: 躯干姿态稳定性 (俯仰/横滚)
      二爻: 质心高度
      三爻: 足端力分布均匀性
      四爻: ZMP稳定裕度
      五爻: 扰动/能耗
      上爻: 地形环境
    """
    
    def __init__(self):
        # 阴阳判定阈值（可在线调参）
        # 每个爻值 >= threshold 即判为阳爻
        self.thresholds = np.array([0.50, 0.50, 0.50, 0.50, 0.50, 0.50])
        
        # 编码权重（可用于微调）
        self.weights = {
            'yao1': {'posture': 1.0},
            'yao2': {'com_height': 1.0},
            'yao3': {'force_dist': 1.0},
            'yao4': {'zmp_margin': 1.0},
            'yao5': {'disturbance': 0.6, 'energy': 0.4},
            'yao6': {'terrain': 1.0},
        }
    
    def encode(self, state):
        """
        将状态向量编码为六爻
        
        Args:
            state: dict or array with keys/indices:
                posture: 躯干姿态稳定性 [0,1], 1=稳定
                com_height: 质心高度归一化 [0,1]
                force_dist: 足端力分布均匀性 [0,1], 1=均匀
                zmp_margin: ZMP裕度 [0,1], 1=安全
                disturbance: 扰动量 [0,1], 0=无扰动
                energy: 能耗水平 [0,1], 0=低能耗
                terrain: 地形通过性 [0,1], 1=平坦
        
        Returns:
            yao_vector: 6维爻值 [初爻..上爻]
            yao_yin_yang: 阴阳判断 ['—' or '--'] × 6
            yao_descriptions: 语义描述
        """
        if isinstance(state, dict):
            s = state
        else:
            s = {
                'posture': state[0], 'com_height': state[1],
                'force_dist': state[2], 'zmp_margin': state[3],
                'disturbance': state[4], 'terrain': state[5]
            }
        
        y1 = s['posture']
        y2 = s['com_height']
        y3 = s['force_dist']
        y4 = s['zmp_margin']
        y5 = self.weights['yao5']['disturbance'] * (1 - s.get('disturbance', s.get('disturbance', 0.5))) + \
             self.weights['yao5']['energy'] * (1 - s.get('energy', 0.5))
        y6 = s['terrain']
        
        yao = np.array([y1, y2, y3, y4, y5, y6])
        yao = np.clip(yao, 0.0, 1.0)
        
        yin_yang = ['—' if v >= self.thresholds[i] else '--' for i, v in enumerate(yao)]
        
        t = self.thresholds
        descriptions = [
            f"初爻(姿态): {'阳—稳定' if y1 >= t[0] else '阴--不稳'} ({y1:.2f})",
            f"二爻(质心): {'阳—正常' if y2 >= t[1] else '阴--偏低'} ({y2:.2f})",
            f"三爻(力分布): {'阳—均匀' if y3 >= t[2] else '阴--不均'} ({y3:.2f})",
            f"四爻(ZMP): {'阳—安全' if y4 >= t[3] else '阴--危险'} ({y4:.2f})",
            f"五爻(扰动): {'阳—平稳' if y5 >= t[4] else '阴—扰动'} ({y5:.2f})",
            f"上爻(地形): {'阳—平坦' if y6 >= t[5] else '阴—崎岖'} ({y6:.2f})",
        ]
        
        return yao, yin_yang, descriptions


if __name__ == '__main__':
    encoder = MotionYaoEncoder()
    
    # Test 1: Stable standing
    print("=== 稳定站立 ===")
    yao, yy, desc = encoder.encode({
        'posture': 0.92, 'com_height': 0.85, 'force_dist': 0.80,
        'zmp_margin': 0.90, 'disturbance': 0.05, 'energy': 0.1,
        'terrain': 0.80
    })
    print(f"爻向量: {np.round(yao, 2)}")
    print(f"阴阳:   {''.join(yy)}")
    for d in desc:
        print(f"  {d}")
    
    # Test 2: Disturbed
    print("\n=== 受扰动 ===")
    yao, yy, desc = encoder.encode({
        'posture': 0.25, 'com_height': 0.40, 'force_dist': 0.35,
        'zmp_margin': 0.15, 'disturbance': 0.80, 'energy': 0.7,
        'terrain': 0.45
    })
    print(f"爻向量: {np.round(yao, 2)}")
    print(f"阴阳:   {''.join(yy)}")
    for d in desc:
        print(f"  {d}")
