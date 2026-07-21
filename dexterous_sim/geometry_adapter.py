#!/usr/bin/env python3
"""
YLYW 灵巧手策略角度几何适配器

核心思想：
  当前 STRATEGY_TO_POSITION 的关节角度是固定的硬编码值，对于不同尺寸/形状的物体不通用。
  几何适配器根据物体的关键尺寸和形状特征，对基础策略角度做缩放和偏移。

物体特征提取：
  - obj_width: 物体X方向最大尺寸
  - obj_height: Z方向高度
  - obj_diameter: 物体的等效直径
  - shape_type: 'sphere' / 'box' / 'cylinder' / 'rod' / 'mushroom' / 'dumbbell' / 'disc'

对策略角度的修正：
  1. 拇指对掌角 (THJ1): 与物体宽度成正比
  2. 手指弯曲角 (FFJ1/MFJ1/RFJ1/LFJ1): 与物体直径成反比（细物弯更多）
  3. 末端弯曲角 (FFJ2/MFJ2/...): 与物体高度成正比
"""

import math
import numpy as np

# 物体几何参数
OBJECT_GEOMETRY = {
    'sphere': {
        'width': 0.056, 'height': 0.056, 'diameter': 0.056,
        'shape': 'sphere',
        'finger_offset': 0.0,     # 手指需要偏移的距离
        'thumb_spread': 1.0,      # 拇指张开度缩放
    },
    'box': {
        'width': 0.050, 'height': 0.050, 'diameter': 0.050,
        'shape': 'box',
        'finger_offset': 0.0,
        'thumb_spread': 1.0,
    },
    'cylinder': {
        'width': 0.050, 'height': 0.060, 'diameter': 0.050,
        'shape': 'cylinder',
        'finger_offset': 0.0,
        'thumb_spread': 1.0,
    },
    'long_rod': {
        'width': 0.016, 'height': 0.090, 'diameter': 0.016,
        'shape': 'rod',
        'finger_offset': 0.0,
        'thumb_spread': 1.3,      # 细长物需要拇指更大对掌
    },
    'mushroom': {
        'width': 0.070, 'height': 0.070, 'diameter': 0.070,
        'shape': 'mushroom',
        'finger_offset': 0.01,    # 需要手指上移抓蘑菇头
        'thumb_spread': 1.2,
    },
    'dumbbell': {
        'width': 0.090, 'height': 0.040, 'diameter': 0.012,
        'shape': 'dumbbell',
        'finger_offset': 0.0,
        'thumb_spread': 1.4,      # 哑铃需要更大张开
    },
    'disc': {
        'width': 0.070, 'height': 0.016, 'diameter': 0.070,
        'shape': 'disc',
        'finger_offset': 0.0,
        'thumb_spread': 1.2,
    },
}

# 参考物体尺寸（球体，直径0.056作为参考）
REF_WIDTH = 0.056
REF_HEIGHT = 0.056
REF_DIAMETER = 0.056


def default_strategy_positions():
    """返回原始硬编码的策略角度"""
    from grasp_env import STRATEGY_TO_POSITION
    return STRATEGY_TO_POSITION


def adjust_for_object(strategy_name: str, obj_key: str,
                      base_force: float = 1.0) -> dict:
    """
    根据物体几何调整指定策略的角度。

    obj_key: 物体名 ('sphere', 'box', 'cylinder', 'long_rod', 'mushroom', 'dumbbell', 'disc')

    返回: {'thumb': (J1, J2), 'index': (J1, J2), ...}
    """
    geo = OBJECT_GEOMETRY.get(obj_key, OBJECT_GEOMETRY['sphere'])
    from grasp_env import STRATEGY_TO_POSITION

    if strategy_name not in STRATEGY_TO_POSITION:
        # 找不到就返回开放
        from grasp_env import FINGER_NAMES
        return {f: (0, 0) for f in FINGER_NAMES}

    base = STRATEGY_TO_POSITION[strategy_name]

    # 计算缩放系数
    w_scale = geo['width'] / REF_WIDTH       # 宽度缩放
    h_scale = geo['height'] / REF_HEIGHT     # 高度缩放
    d_scale = geo['diameter'] / REF_DIAMETER # 直径缩放

    # 拇指：J1=对掌(与宽度正比), J2=弯曲(与高度正比)
    # 对细长物体(rod/dumbbell)，拇指需要更大对掌来包住
    # 对扁宽物体(disc)，拇指需要稍微张开
    thumb_j1, thumb_j2 = base['thumb']
    # 拇指J1: 宽物需要更大对掌
    thumb_j1_adj = thumb_j1 * min(w_scale * 1.5, 2.0) * geo['thumb_spread']
    # 拇指J2: 高物需要更大弯曲
    thumb_j2_adj = thumb_j2 * min(h_scale * 1.3, 1.8)

    # 四指：J1=基部弯曲, J2=末端弯曲
    # 细物(diameter小)→手指弯更多来包紧
    # 高物→末端多弯
    def adjust_finger(finger_name):
        if finger_name not in base:
            return (0, 0)
        j1, j2 = base[finger_name]
        # 细长物 → 弯更多（补偿接触面积小）
        j1_adj = j1 * min(1.0 / max(d_scale, 0.3), 2.5)
        # 高物 → 末端多弯抓高度
        j2_adj = j2 * min(h_scale * 1.2, 2.0)
        return (j1_adj, j2_adj)

    result = {
        'thumb': (min(thumb_j1_adj, 1.2), min(thumb_j2_adj, 1.2)),
        'index': adjust_finger('index'),
        'middle': adjust_finger('middle'),
        'ring': adjust_finger('ring'),
        'pinky': adjust_finger('pinky'),
    }
    return result


def test_all_strategies():
    """打印所有物体×策略的适配后角度"""
    FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']
    print(f"{'物体':12s} {'策略':20s}  {'拇指':14s} {'食指':14s} {'中指':14s} {'无名':14s} {'小指':14s}")
    print("-" * 100)
    from grasp_env import STRATEGY_TO_POSITION
    for obj_key in OBJECT_GEOMETRY:
        for strat in ['soft_grasp', 'firm_grasp', 'wrap_grasp']:
            adj = adjust_for_object(strat, obj_key)
            vals = '  '.join(
                f'({adj[f][0]:.2f},{adj[f][1]:.2f})' for f in FINGER_NAMES
            )
            print(f"{obj_key:12s} {strat:20s}  {vals}")
        print()


if __name__ == '__main__':
    test_all_strategies()
