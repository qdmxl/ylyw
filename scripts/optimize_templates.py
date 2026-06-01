#!/usr/bin/env python3
"""
爻模板系统性优化

策略：
1. 采集8类物体的爻向量质心（已采集）
2. 定义每卦"该服务"的物体类型
3. 将模板值设为对应质心的加权组合
4. 同类策略的多个卦通过微小扰动区分
"""

import numpy as np

# ============================================================
# 8类物体爻向量质心 (从50+样本统计)
# ============================================================
CENTROIDS = {
    'sphere':   np.array([0.087, 0.620, 0.340, 0.728, 0.480, 0.656]),
    'cube':     np.array([0.753, 0.588, 0.594, 0.755, 0.435, 0.657]),
    'cylinder': np.array([0.365, 0.593, 0.479, 0.654, 0.480, 0.787]),
    'bowl':     np.array([0.440, 0.637, 0.251, 0.382, 0.348, 0.625]),
    'bottle':   np.array([0.258, 0.575, 0.329, 0.350, 0.336, 0.491]),
    'plate':    np.array([0.764, 0.544, 0.237, 0.194, 0.309, 0.457]),
    'rock':     np.array([0.337, 0.539, 0.586, 0.693, 0.421, 0.605]),
    'vase':     np.array([0.389, 0.557, 0.339, 0.072, 0.361, 0.706]),
}

# 未济卦专用：极端"事未成"状态
WEIJI_EXTREME = np.array([0.08, 0.88, 0.12, 0.10, 0.08, 0.12])
# 既济卦专用：极端"已完成"状态
JIJI_EXTREME = np.array([0.90, 0.85, 0.90, 0.88, 0.92, 0.85])

# ============================================================
# 卦象 → 目标物体类型映射
# ============================================================
HEX_TO_TARGETS = {
    # --- 动态/球体/圆柱体类 ---
    'ZHEN_GUA':  ['sphere', 'cylinder'],     # 震为雷 → dynamic_grasp
    'SUI':       ['sphere', 'cylinder'],     # 泽雷随 → following_grasp
    'YU':        ['sphere', 'cylinder'],     # 雷地豫 → predictive_grasp
    'HENG':      ['cylinder'],               # 雷风恒 → endurance_grasp (圆柱长时)

    # --- 强力/立方体类 ---
    'QIAN':      ['cube'],                   # 乾为天 → power_grasp
    'WUWANG':    ['cube'],                   # 天雷无妄 → direct_grasp
    'DAZHUANG':  ['cube', 'rock'],           # 雷天大壮 → robust_power
    'DACHU':     ['cube'],                   # 山天大畜 → power_accumulating
    'TAI':       ['cube'],                   # 地天泰 → standard_grasp
    'DAGUO':     ['cube', 'rock'],           # 泽风大过 → forceful_grasp

    # --- 精密/软性/碗瓶类 ---
    'KUN':       ['bowl', 'bottle', 'vase'], # 坤为地 → precision_grasp
    'LIN':       ['bowl'],                   # 地泽临 → top_down_grasp
    'FU':        ['bowl', 'vase'],           # 地雷复 → iterative_grasp
    'SUN':       ['bowl', 'plate', 'vase'],  # 山泽损 → reduced_force_grasp
    'XIAOXU':    ['bowl'],                   # 风天小畜 → progressive_grasp
    'JIN':       ['bowl', 'vase'],           # 火地晋 → progressive_grasp
    'GUAN':      ['bowl', 'vase', 'plate'],  # 风地观 → observational_grasp

    # --- 谨慎/瓶瓶罐罐类 ---
    'LU':        ['bottle', 'vase'],         # 天泽履 → cautious_grasp
    'KAN_GUA':   ['bottle'],                 # 坎为水 → cautious_grasp
    'JIAREN':    ['bottle', 'vase'],         # 风火家人 → coordinated_grasp
    'SHIHE':     ['bottle', 'rock'],         # 火雷噬嗑 → interlocking_grasp
    'BI':        ['bottle'],                 # 水地比 → close_proximity

    # --- 盘子/扁平类 ---
    'BO':        ['plate'],                  # 山地剥 → peeling_grasp
    'MINGYI':    ['plate', 'vase'],          # 地火明夷 → low_visibility_grasp
    'DUI_GUA':   ['plate', 'bowl'],          # 兑为泽 → soft_grasp
    'LI_GUA':    ['plate'],                  # 离为火 → adhesion_grasp

    # --- 石块/不规则类 ---
    'KUI':       ['rock'],                   # 火泽睽 → adaptive_irregular_grasp
    'JIAN':      ['rock'],                   # 水山蹇 → difficult_grasp
    'XIE':       ['rock'],                   # 雷水解 → extrication_grasp
    'XUN_GUA':   ['rock'],                   # 巽为风 → compliant_grasp

    # --- 通用/混合场景 ---
    'ZHUN':      ['bottle', 'rock'],         # 水雷屯 → cautious_grasp
    'MENG':      ['rock', 'sphere'],         # 山水蒙 → adaptive_grasp
    'XU':        ['cylinder', 'sphere'],     # 水天需 → conditional_grasp
    'XIAN':      ['vase', 'bottle'],         # 泽山咸 → tactile_feedback
    'GU':        ['rock', 'cylinder'],       # 山风蛊 → corrective_grasp

    # --- 特殊卦（远离所有质心） ---
    'SONG':      None,                       # 天水讼 → 争讼，非常态
    'SHI':       None,                       # 地水师 → 有序，非常态
    'PI':        None,                       # 天地否 → 闭塞，远离正常
    'DUN':       None,                       # 天山遁 → 退避，非常态
    'GEN_GUA':   None,                       # 艮为山 → stable_grasp，独立状态
    'WEIJI':     None,                       # 火水未济 → 极端"未完成"
    'JIJI':      None,                       # 水火既济 → 极端"已完成"
}


def perturb(template, seed, scale=0.03):
    """对模板做微小扰动，避免同策略卦完全重叠"""
    rng = np.random.RandomState(seed)
    noise = rng.uniform(-scale, scale, size=6)
    return np.clip(template + noise, 0.02, 0.98)


def compute_new_templates():
    """计算所有优化后的爻模板"""
    new_templates = {}
    
    for hex_name, targets in HEX_TO_TARGETS.items():
        if targets is None:
            # 特殊卦：手动定义极端模板
            continue
        elif len(targets) == 0:
            continue
        
        # 计算目标质心的平均值
        target_centroids = [CENTROIDS[t] for t in targets]
        mean_centroid = np.mean(target_centroids, axis=0)
        
        # 向质心方向收缩（不完全等于质心，保留模板的"理想化"特征）
        # 模板 = 质心 * 0.75 + 当前模板理想值 * 0.25
        # (这步需要知道当前模板，但我直接在下一步手动调)
        new_templates[hex_name] = mean_centroid
    
    # 设置特殊卦的极端值
    new_templates['WEIJI'] = WEIJI_EXTREME
    new_templates['JIJI'] = JIJI_EXTREME
    
    return new_templates


if __name__ == '__main__':
    templates = compute_new_templates()
    
    # 生成Python代码格式的输出
    print("# 优化后的爻模板 (基于物体质心)")
    for hex_name in sorted(templates.keys()):
        arr = templates[hex_name]
        # 加扰动（基于hash值）
        seed = hash(hex_name) % 10000
        arr_perturbed = perturb(arr, seed)
        
        vals = ', '.join(f'{v:.2f}' for v in arr_perturbed)
        print(f"            Hexagram.{hex_name}: np.array([{vals}]),")
    
    print(f"\n# 共 {len(templates)} 个模板")
    
    # 验证：计算各质心与最近模板的距离
    print("\n# === 物体质心 → 最近模板匹配 ===")
    for otype, centroid in CENTROIDS.items():
        best_dist = float('inf')
        best_hex = None
        for hex_name, tmpl in templates.items():
            dist = np.linalg.norm(centroid - tmpl)
            if dist < best_dist:
                best_dist = dist
                best_hex = hex_name
        print(f"  {otype:<10} → {best_hex:<15} dist={best_dist:.3f}")
