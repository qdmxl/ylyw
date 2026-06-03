#!/usr/bin/env python3
"""
YLYW 运动控制器 (YLYW Locomotion Controller)
集成 L1 → L2 → L3 → L3+ → 动作输出
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from trigram_base_motion import TrigramMotionBase
from yao_encoder_motion import MotionYaoEncoder
from hexagram_gait_rules import HexagramGaitRules


class YLYWLocomotionController:
    """
    YLYW运动控制器
    
    数据流:
        传感器状态 → L1八卦隶属度 → L2六爻编码 → L3卦象匹配 → 步态参数
    """
    
    def __init__(self):
        self.trigram_base = TrigramMotionBase(sensitivity=1.5)
        self.yao_encoder = MotionYaoEncoder()
        self.hexagram_rules = HexagramGaitRules()
        
        # 统计
        self.step_count = 0
        self.hexagram_history = []
    
    def infer(self, state_vector, verbose=False):
        """
        完整推理链: 状态 → 步态参数
        
        Args:
            state_vector: 6维状态 [posture, com_h, force_dist, zmp, dist, terrain]
            verbose: 是否打印推理链
        
        Returns:
            gait_params: dict {speed, step_height, freq, force_coefficient, gait_name, ...}
        """
        self.step_count += 1
        
        # L1: 八卦隶属度
        memberships, dominant = self.trigram_base.compute_membership(state_vector)
        
        # L2: 六爻编码
        state_stub = {
            'posture': state_vector[0],
            'com_height': state_vector[1],
            'force_dist': state_vector[2],
            'zmp_margin': state_vector[3],
            'disturbance': state_vector[4],
            'terrain': state_vector[5],
            'energy': 0.5,  # default
        }
        yao, yin_yang, descriptions = self.yao_encoder.encode(state_stub)
        
        # L3: 卦象匹配
        hex_id, hex_name, sim, gait, top3 = self.hexagram_rules.match_hexagram(yao)
        self.hexagram_history.append(hex_id)
        
        # 构建步态参数
        gait_params = {
            'speed': gait['speed'],
            'step_height': gait['step_height'],
            'freq': gait['freq'],
            'force_coefficient': gait['force_coefficient'],
            'gait_name': gait['name'],
            'gait_type': next(k for k,v in HexagramGaitRules.GAIT_TYPES.items() if v['name']==gait['name']),
            'hexagram_id': hex_id,
            'hexagram_name': hex_name,
            'similarity': sim,
            'dominant_trigram': dominant,
            'dominant_trigram_name': self.trigram_base.TRIGRAM_PROTOTYPES[dominant]['name'],
            'yao_vector': yao,
            'yin_yang': ''.join(yin_yang),
            'top3_hexagrams': [(hid, hname, s) for hid, hname, s in top3],
        }
        
        if verbose:
            self._print_chain(gait_params, descriptions)
        
        return gait_params
    
    def _print_chain(self, gp, descriptions):
        """打印推理链"""
        print(f"\n{'='*60}")
        print(f"Step {self.step_count}: {gp['hexagram_name']} ({gp['similarity']:.3f})")
        print(f"  六爻: {gp['yin_yang']} | 主导卦: {gp['dominant_trigram_name']}")
        print(f"  步态: {gp['gait_name']}({gp['gait_type']})")
        print(f"  速度: {gp['speed']:.2f} m/s | 步高: {gp['step_height']:.2f} m | 力系数: {gp['force_coefficient']:.2f}")
        print(f"  Top3: {[(n, f'{s:.3f}') for _,n,s in gp['top3_hexagrams'][:3]]}")
    
    def get_stats(self):
        """获取统计信息"""
        if not self.hexagram_history:
            return {}
        unique = len(set(self.hexagram_history))
        return {
            'total_steps': self.step_count,
            'unique_hexagrams': unique,
            'hexagram_diversity': unique / max(1, self.step_count),
        }


def run_demo():
    """演示：不同运动状态下的YLYW推理"""
    controller = YLYWLocomotionController()
    
    # 预定义场景
    scenarios = [
        ("稳定站立",      [0.92, 0.85, 0.80, 0.90, 0.05, 0.80]),
        ("正常行走",      [0.65, 0.70, 0.65, 0.60, 0.30, 0.75]),
        ("高速奔跑",      [0.55, 0.75, 0.70, 0.45, 0.60, 0.80]),
        ("受推搡扰动",    [0.20, 0.35, 0.30, 0.15, 0.80, 0.60]),
        ("上坡爬行",      [0.45, 0.40, 0.50, 0.30, 0.45, 0.20]),
        ("下坡慢行",      [0.50, 0.35, 0.45, 0.35, 0.40, 0.30]),
        ("崎岖地形",      [0.40, 0.45, 0.35, 0.30, 0.50, 0.15]),
        ("恢复站立",      [0.60, 0.30, 0.40, 0.35, 0.35, 0.50]),
    ]
    
    print("=" * 60)
    print("YLYW 运动控制推理演示")
    print("=" * 60)
    
    results = []
    for name, state in scenarios:
        print(f"\n{'─'*60}")
        print(f"场景: {name}")
        print(f"状态: posture={state[0]:.2f} com_h={state[1]:.2f} force={state[2]:.2f} zmp={state[3]:.2f} dist={state[4]:.2f} terrain={state[5]:.2f}")
        gp = controller.infer(state, verbose=True)
        results.append((name, gp))
    
    # 汇总
    print(f"\n{'='*60}")
    print("场景汇总")
    print(f"{'场景':<12} {'卦象':<10} {'步态':<10} {'速度':>6} {'力系数':>6}")
    print('-' * 50)
    for name, gp in results:
        print(f"{name:<12} {gp['hexagram_name']:<10} {gp['gait_name']:<10} {gp['speed']:>5.2f}m/s {gp['force_coefficient']:>5.2f}")
    
    stats = controller.get_stats()
    print(f"\n统计: {stats['total_steps']}步, {stats['unique_hexagrams']}个不同卦象")


if __name__ == '__main__':
    run_demo()
