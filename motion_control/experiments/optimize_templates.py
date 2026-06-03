#!/usr/bin/env python3
"""
爻模板优化：基于步态质心的系统性模板优化（三步法）
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ylyw_locomotion import YLYWLocomotionController
from hexagram_gait_rules import HexagramGaitRules


def step1_collect_centroids(n_samples=50):
    """
    步骤一：采集各步态类型的六爻质心
    对每种步态生成大量状态样本，经L1→L2推理输出六爻向量，取均值
    """
    controller = YLYWLocomotionController()
    
    # 步态类型的典型状态中心（6维: posture, com_h, force_dist, zmp, disturbance, terrain）
    gait_centers = {
        'stand':        [0.92, 0.85, 0.78, 0.92, 0.03, 0.78],
        'crawl':        [0.50, 0.30, 0.35, 0.55, 0.10, 0.55],
        'slow_walk':    [0.72, 0.72, 0.68, 0.68, 0.18, 0.78],
        'walk':         [0.65, 0.70, 0.65, 0.62, 0.28, 0.75],
        'fast_walk':    [0.58, 0.72, 0.70, 0.52, 0.42, 0.78],
        'trot':         [0.55, 0.72, 0.72, 0.48, 0.52, 0.75],
        'run':          [0.48, 0.75, 0.78, 0.42, 0.62, 0.78],
        'caution_walk': [0.42, 0.48, 0.42, 0.32, 0.42, 0.38],
        'recovery':     [0.20, 0.28, 0.22, 0.14, 0.78, 0.52],
        'transition':   [0.55, 0.55, 0.52, 0.48, 0.40, 0.55],
        'turn':         [0.52, 0.60, 0.55, 0.45, 0.42, 0.62],
        'climb':        [0.48, 0.42, 0.52, 0.32, 0.45, 0.18],
        'descend':      [0.50, 0.35, 0.45, 0.35, 0.40, 0.28],
        'adaptive':     [0.48, 0.50, 0.48, 0.42, 0.42, 0.35],
    }
    
    # 每种步态的噪声幅度（反映该步态的天然变异度）
    noise_levels = {
        'stand': 0.03, 'crawl': 0.05, 'slow_walk': 0.06, 'walk': 0.06,
        'fast_walk': 0.08, 'trot': 0.08, 'run': 0.10,
        'caution_walk': 0.05, 'recovery': 0.08, 'transition': 0.06,
        'turn': 0.06, 'climb': 0.05, 'descend': 0.05, 'adaptive': 0.06,
    }
    
    centroids = {}
    np.random.seed(12345)
    
    print("步骤一：采集六爻质心...")
    for gait_name, center in gait_centers.items():
        yao_samples = []
        noise = noise_levels.get(gait_name, 0.05)
        
        for _ in range(n_samples):
            # 在中心周围采样
            state = np.clip(np.array(center) + np.random.normal(0, noise, 6), 0.0, 1.0)
            # 只通过L2编码（不完整的L1→L2链，直接用状态编码）
            state_dict = {
                'posture': state[0], 'com_height': state[1],
                'force_dist': state[2], 'zmp_margin': state[3],
                'disturbance': state[4], 'terrain': state[5],
                'energy': 0.5,
            }
            yao, _, _ = controller.yao_encoder.encode(state_dict)
            yao_samples.append(yao)
        
        centroid = np.mean(yao_samples, axis=0)
        std = np.std(yao_samples, axis=0)
        centroids[gait_name] = {'centroid': centroid, 'std': std}
        
        yin_yang = ''.join(['—' if v >= 0.5 else '--' for v in centroid])
        print(f"  {gait_name:<14} → {yin_yang}  ({', '.join(f'{c:.3f}' for c in centroid)})")
    
    return centroids


def step2_map_hexagrams_to_gaits():
    """
    步骤二：卦象-步态类型映射
    将64卦根据其语义和策略类型映射到目标步态类型
    """
    hgr = HexagramGaitRules()
    
    # 步态类型→卦象列表
    gait_to_hexagrams = {gait: [] for gait in HexagramGaitRules.GAIT_TYPES}
    
    for hid in range(1, 65):
        rule = hgr.HEXAGRAM_GAIT_RULES[hid]
        gait_type = rule[3]
        if gait_type in gait_to_hexagrams:
            gait_to_hexagrams[gait_type].append(hid)
    
    print("\n步骤二：卦象-步态映射")
    for gait, hids in sorted(gait_to_hexagrams.items()):
        names = [hgr.HEXAGRAM_GAIT_RULES[hid][0] for hid in hids]
        print(f"  {gait:<14} ({len(hids):>2}卦): {', '.join(names[:5])}{'...' if len(names)>5 else ''}")
    
    return gait_to_hexagrams


def temp_hash_perturbation(hexagram_id, dim=6, scale=0.02):
    """基于卦名哈希的确定性微小扰动"""
    h = hashlib.md5(str(hexagram_id).encode()).digest()
    # 使用哈希字节生成扰动
    return np.array([(h[i % len(h)] / 255.0 - 0.5) * 2 * scale for i in range(dim)])


def step3_recalculate_templates(centroids, gait_to_hexagrams):
    """
    步骤三：模板重算
    对每个卦：新模板 = 质心平均 + 哈希扰动
    同时识别和修复问题卦
    """
    hgr = HexagramGaitRules()
    
    new_templates = {}
    problem_hexagrams = []
    
    for gait_type, hex_ids in gait_to_hexagrams.items():
        if gait_type not in centroids:
            continue
        
        centroid = centroids[gait_type]['centroid']
        
        for hid in hex_ids:
            # 质心 + 哈希扰动
            perturbation = temp_hash_perturbation(hid, scale=0.015)
            template = centroid + perturbation
            template = np.clip(template, 0.02, 0.98)
            new_templates[hid] = template
    
    print(f"\n步骤三：模板重算完成，{len(new_templates)}个模板")
    
    # 识别问题卦：模板过于"中性"（各维标准差 < 0.12 且均值在0.4-0.6之间）
    for hid, template in new_templates.items():
        t = np.array(template)
        mean_val = np.mean(t)
        std_val = np.std(t)
        if 0.35 < mean_val < 0.60 and std_val < 0.10:
            problem_hexagrams.append((hid, mean_val, std_val))
    
    if problem_hexagrams:
        print(f"\n识别到{len(problem_hexagrams)}个问题卦（中性catch-all）：")
        for hid, mv, sv in problem_hexagrams:
            rule = hgr.HEXAGRAM_GAIT_RULES[hid]
            print(f"  {hid}: {rule[0]} mean={mv:.3f} std={sv:.3f}")
        
        # 修复：极端化
        print("\n修复问题卦（极端化处理）...")
        for hid, _, _ in problem_hexagrams:
            rule = hgr.HEXAGRAM_GAIT_RULES[hid]
            gait_type = rule[3]
            # 向极端方向拉伸
            current = new_templates[hid]
            # 极值拉伸：将各维度向0或1方向推
            extreme = np.where(current > 0.5, 
                              np.minimum(current * 1.35, 0.98),
                              np.maximum(current * 0.65, 0.02))
            new_templates[hid] = extreme
            print(f"  {hid} {rule[0]}: {[f'{v:.3f}' for v in current[:3]]}...→{[f'{v:.3f}' for v in extreme[:3]]}...")
    
    return new_templates


def apply_and_test(new_templates):
    """应用新模板并测试"""
    hgr = HexagramGaitRules()
    
    # 替换模板
    hgr.HEXAGRAM_YAO_TEMPLATES = {int(k): v.tolist() if hasattr(v, 'tolist') else v 
                                   for k, v in new_templates.items()}
    
    # 运行快速测试
    from experiments.exp_a_zero_shot import generate_test_scenarios, evaluate_gait_reasonableness
    
    controller = YLYWLocomotionController()
    controller.hexagram_rules.HEXAGRAM_YAO_TEMPLATES = hgr.HEXAGRAM_YAO_TEMPLATES
    
    scenarios = generate_test_scenarios()
    
    exact = 0
    reasonable = 0
    acceptable = 0
    total = len(scenarios)
    
    for sc in scenarios:
        state = np.array(sc['state'])
        # Build state dict properly
        state_dict = {
            'posture': state[0], 'com_height': state[1],
            'force_dist': state[2], 'zmp_margin': state[3],
            'disturbance': state[4], 'terrain': state[5],
            'energy': 0.5,
        }
        gp = controller.infer(state, verbose=False)
        r = evaluate_gait_reasonableness(gp['gait_type'], sc['expected_gait'], gp['speed'])
        if r == 'exact': exact += 1
        if r in ('exact', 'reasonable'): reasonable += 1
        if r in ('exact', 'reasonable', 'acceptable'): acceptable += 1
    
    print(f"\n{'='*60}")
    print(f"优化后结果:")
    print(f"  精确匹配:     {exact:>3}/{total} ({exact/total*100:5.1f}%)")
    print(f"  合理(含精确):  {reasonable:>3}/{total} ({reasonable/total*100:5.1f}%)")
    print(f"  可接受(全部):  {acceptable:>3}/{total} ({acceptable/total*100:5.1f}%)")
    print(f"  不合理:        {total-acceptable:>3}/{total} ({(total-acceptable)/total*100:5.1f}%)")
    
    return exact, reasonable, acceptable


if __name__ == '__main__':
    print("=" * 60)
    print("YLYW 步态爻模板优化（三步法）")
    print("=" * 60)
    
    # 步骤一
    centroids = step1_collect_centroids()
    
    # 步骤二
    gait_to_hexagrams = step2_map_hexagrams_to_gaits()
    
    # 步骤三
    new_templates = step3_recalculate_templates(centroids, gait_to_hexagrams)
    
    # 测试
    apply_and_test(new_templates)
    
    # 保存优化后的模板
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, 'optimized_templates.json')
    
    serializable = {str(k): (v.tolist() if hasattr(v, 'tolist') else v) 
                    for k, v in new_templates.items()}
    with open(out_path, 'w') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\n优化后模板已保存: {out_path}")
