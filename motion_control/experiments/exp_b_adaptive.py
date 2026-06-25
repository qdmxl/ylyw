#!/usr/bin/env python3
"""
实验B: YLYW 运动控制在线自适应对比实验 (v4)

测试1 - 步态族污染与恢复：
  污染同一gait家族的所有卦模板 → 强制跨家族匹配 → ground truth纠正
  
测试2 - 异常场景鲁棒性对比
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ylyw_locomotion import YLYWLocomotionController
from ylyw_adaptive import YLYWAdaptiveController
from hexagram_gait_rules import HexagramGaitRules


def simulate_feedback(state, gait_result, ground_truth_gait='walk'):
    gt = HexagramGaitRules.GAIT_TYPES.get(ground_truth_gait, {'speed':0.5})
    gt_speed = gt.get('speed', 0.5)
    actual_speed = gait_result.get('speed', 0.5)
    actual_force = gait_result.get('force_coefficient', 0.5)
    
    speed_ratio = actual_speed / max(0.05, gt_speed)
    fell = speed_ratio > 3.0 or (state[0] < 0.10 and speed_ratio > 1.5)
    
    force_mismatch = abs(actual_force - 0.5)
    com_dev = force_mismatch * 0.3 + max(0, 0.85 - state[0]) * 0.3
    zmp_margin = state[3] * (1.0 - force_mismatch * 0.5)
    energy = actual_speed * 0.4 + actual_force * 0.3 + state[4] * 0.3
    
    return {
        'fell': fell,
        'com_deviation': round(min(1.0, com_dev), 3),
        'zmp_margin': round(max(0.01, zmp_margin), 3),
        'speed_error': round(max(0, speed_ratio - 1.0) * 0.5, 3),
        'energy_cost': round(min(1.0, energy), 3),
        'expected_gait': ground_truth_gait,
    }


def quality_score(gait_result, feedback):
    if feedback['fell']: return 0.0
    return round(
        0.25 * max(0, 1 - feedback['com_deviation'] * 2.5) +
        0.30 * min(1, feedback['zmp_margin'] * 1.3) +
        0.25 * max(0, 1 - feedback['speed_error'] * 3) +
        0.20 * max(0, 1 - feedback['energy_cost']), 3)


def corrupt_templates_for_gait_family(adaptive, gait_type, corruption_strength=0.35):
    """
    污染同一gait类型的所有卦模板，使它们偏离原始值
    
    策略：跑动卦→降低速度维度（姿态/扰动）→ 使模板看起来像行走卦
          站立卦→降低稳定性 → 使模板看起来不像站立
    """
    hgr = HexagramGaitRules()
    affected = []
    
    for hid in range(1, 65):
        rule = hgr.HEXAGRAM_GAIT_RULES[hid]
        if rule[3] == gait_type:
            orig = adaptive.controller.hexagram_rules.get_template(hid).copy()
            
            if gait_type in ('run', 'fast_walk', 'trot'):
                # 高速卦 → 降低速度维度
                orig[0] = np.clip(orig[0] + corruption_strength, 0, 0.98)  # 姿态↑
                orig[4] = np.clip(orig[4] - corruption_strength, 0.02, 0.98)  # 扰动↓
            elif gait_type in ('stand', 'crawl'):
                # 静止/极慢 → 升高扰动
                orig[4] = np.clip(orig[4] + corruption_strength, 0, 0.98)
                orig[0] = np.clip(orig[0] - corruption_strength, 0.02, 0.98)
            else:
                # 通用：随机偏移
                orig += np.random.normal(0, corruption_strength, 6)
                orig = np.clip(orig, 0.02, 0.98)
            
            adaptive.controller.hexagram_rules.update_template(hid, orig)
            affected.append(hid)
    
    return affected


def test_gait_family_recovery():
    """
    污染所有'run'卦(3个) → 跑动状态匹配到行走卦 → GT='run'触发修正
    """
    print(f"\n{'='*70}")
    print(f"测试1: 步态族污染恢复（污染全部3个run卦）")
    print(f"{'='*70}")
    
    np.random.seed(42)
    hgr = HexagramGaitRules()
    
    # 记录原始模板
    run_hex_ids = [hid for hid in range(1, 65) if hgr.HEXAGRAM_GAIT_RULES[hid][3] == 'run']
    print(f"Run卦: {[(hid, hgr.HEXAGRAM_GAIT_RULES[hid][0]) for hid in run_hex_ids]}")
    
    orig_templates = {hid: hgr.get_template(hid).copy() for hid in run_hex_ids}
    
    # 创建自适应控制器并污染
    adaptive = YLYWAdaptiveController(learning_rate=0.10, momentum=0.4)
    affected = corrupt_templates_for_gait_family(adaptive, 'run', corruption_strength=0.35)
    
    # 验证污染效果
    run_state = np.array([0.48, 0.75, 0.78, 0.42, 0.65, 0.78])
    before = adaptive.controller.infer(run_state, verbose=False)
    print(f"\n污染前(静态ctrl): 34 雷天大壮 → run spd=2.00")
    print(f"污染后: {before['hexagram_name']}({before['hexagram_id']}) → "
          f"{before['gait_type']} spd={before['speed']:.2f}")
    
    # 初始偏差
    init_dists = {hid: np.linalg.norm(adaptive.controller.hexagram_rules.get_template(hid) - orig_templates[hid]) 
                  for hid in run_hex_ids}
    print(f"初始模板偏差: {[(hid, f'{d:.3f}') for hid, d in init_dists.items()]}")
    
    # 在线恢复
    n_steps = 60
    feedback = None
    gait_history = []
    dist_history = []
    
    for step in range(n_steps):
        noise = np.random.normal(0, 0.03, 6)
        state = np.clip(run_state + noise, 0.0, 0.99)
        
        result = adaptive.step(state, feedback=feedback)
        feedback = simulate_feedback(state, result, ground_truth_gait='run')
        adaptive.give_feedback(feedback)
        
        gait_history.append(result.get('gait_type', '?'))
        
        if step % 5 == 0:
            dists = {hid: np.linalg.norm(adaptive.controller.hexagram_rules.get_template(hid) - orig_templates[hid])
                     for hid in run_hex_ids}
            dist_history.append({'step': step, 'mean_dist': round(np.mean(list(dists.values())), 3)})
    
    # 结果
    final_dists = {hid: np.linalg.norm(adaptive.controller.hexagram_rules.get_template(hid) - orig_templates[hid])
                   for hid in run_hex_ids}
    
    init_mean = np.mean(list(init_dists.values()))
    final_mean = np.mean(list(final_dists.values()))
    
    run_correct = sum(1 for g in gait_history if g == 'run')
    late_correct = sum(1 for g in gait_history[30:] if g == 'run')
    
    print(f"\n恢复结果 ({n_steps}步, {adaptive.total_adaptations}次修正):")
    print(f"  平均模板偏差: {init_mean:.3f} → {final_mean:.3f} (改善 {init_mean-final_mean:+.3f})")
    for hid in run_hex_ids:
        name = hgr.HEXAGRAM_GAIT_RULES[hid][0]
        print(f"    卦{hid} {name:<8}: {init_dists[hid]:.3f} → {final_dists[hid]:.3f}")
    print(f"  步态正确率: {run_correct}/{n_steps} ({run_correct/n_steps*100:.0f}%), "
          f"后半: {late_correct}/{n_steps-30} ({late_correct/(n_steps-30)*100:.0f}%)")
    print(f"  最终L2阈值: {np.round(adaptive.controller.yao_encoder.thresholds, 3)}")
    
    return {
        'test': 'gait_family_recovery',
        'init_mean_dist': round(init_mean, 3),
        'final_mean_dist': round(final_mean, 3),
        'improvement': round(init_mean - final_mean, 3),
        'corrections': adaptive.total_adaptations,
        'run_correct_rate': round(run_correct / n_steps, 3),
        'late_correct_rate': round(late_correct / (n_steps - 30), 3),
    }


def test_anomaly_scenarios():
    print(f"\n{'='*70}")
    print(f"测试2: 异常场景鲁棒性对比")
    print(f"{'='*70}")
    
    np.random.seed(123)
    
    scenarios = [
        ("COM渐变偏移", lambda t: np.clip([
            0.85 - t*0.03, 0.78 - t*0.025, 0.75 - t*0.035,
            0.82 - t*0.04, 0.05 + t*0.035, 0.78,
        ], 0.03, 0.99), 'walk'),
        ("电机老化衰减", lambda t: np.clip([
            0.70 - t*0.012, 0.72 - t*0.01, 0.55 - t*0.02,
            0.65 - t*0.018, 0.20 + t*0.025, 0.78,
        ], 0.05, 0.99), 'walk'),
        ("间歇外力推搡", lambda t: np.clip([
            0.15 if t%4==2 else 0.70, 0.35 if t%4==2 else 0.72,
            0.22 if t%4==2 else 0.65, 0.12 if t%4==2 else 0.65,
            0.88 if t%4==2 else 0.25, 0.75,
        ], 0.01, 0.99), 'walk'),
        ("传感器零点漂移", lambda t: np.clip([
            0.85 - t*0.01, 0.78 - t*0.007, 0.75 - t*0.008,
            0.80 - t*0.01, 0.05 + t*0.006, 0.82,
        ], 0.15, 0.99), 'walk'),
    ]
    
    results = []
    for name, state_fn, gt_gait in scenarios:
        n_steps = 50
        
        # 静态
        sc = YLYWLocomotionController()
        sq, sf = [], 0
        for t in range(n_steps):
            s = state_fn(t)
            g = sc.infer(s, verbose=False)
            f = simulate_feedback(s, g, gt_gait)
            sq.append(quality_score(g, f))
            if f['fell']: sf += 1
        
        # 自适应
        ac = YLYWAdaptiveController(learning_rate=0.06, momentum=0.6)
        aq, af = [], 0
        fb = None
        for t in range(n_steps):
            s = state_fn(t)
            g = ac.step(s, feedback=fb)
            f = simulate_feedback(s, g, gt_gait)
            ac.give_feedback(f)
            aq.append(quality_score(g, f))
            if f['fell']: af += 1
            fb = f
        
        mid = n_steps // 2
        r = {
            'name': name, 'static_avg': round(np.mean(sq), 3),
            'adaptive_avg': round(np.mean(aq), 3),
            'improvement': round(np.mean(aq) - np.mean(sq), 3),
            'static_late': round(np.mean(sq[mid:]), 3),
            'adaptive_late': round(np.mean(aq[mid:]), 3),
            'late_improvement': round(np.mean(aq[mid:]) - np.mean(sq[mid:]), 3),
            'static_fells': sf, 'adaptive_fells': af,
            'adaptations': ac.total_adaptations,
        }
        results.append(r)
        
        # 步态差异统计
        gait_diffs = 0
        for t in range(n_steps):
            sg = sc.infer(state_fn(t), verbose=False)
            ag = ac.controller.infer(state_fn(t), verbose=False)
            if sg['gait_type'] != ag['gait_type']:
                gait_diffs += 1
        
        print(f"  {name:<14} | static={r['static_avg']:.3f} adp={r['adaptive_avg']:.3f} "
              f"Δ={r['improvement']:+.3f} lateΔ={r['late_improvement']:+.3f} "
              f"fells={sf}/{af} corr={ac.total_adaptations} gaitDiff={gait_diffs}")
    
    # 汇总
    print(f"\n{'场景':<16} {'静态':>7} {'自适应':>7} {'Δ全部':>7} {'Δ后半':>7} {'摔静':>5} {'摔自':>5} {'修正':>5}")
    print('-' * 62)
    for r in results:
        print(f"{r['name']:<16} {r['static_avg']:>7.3f} {r['adaptive_avg']:>7.3f} "
              f"{r['improvement']:>+7.3f} {r['late_improvement']:>+7.3f} "
              f"{r['static_fells']:>5} {r['adaptive_fells']:>5} {r['adaptations']:>5}")
    avg_imp = np.mean([r['improvement'] for r in results])
    avg_late = np.mean([r['late_improvement'] for r in results])
    print(f"{'平均':<16} {'':>7} {'':>7} {avg_imp:>+7.3f} {avg_late:>+7.3f}")
    
    return results


def main():
    print("=" * 70)
    print("实验B: YLYW 运动控制在线自适应对比实验 (v4)")
    print("=" * 70)
    
    recovery = test_gait_family_recovery()
    anomaly = test_anomaly_scenarios()
    
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, 'exp_b_adaptive_results.json')
    
    output = {
        'experiment': 'B - Online Adaptive Locomotion Control (v4)',
        'gait_family_recovery': recovery,
        'anomaly_scenarios': anomaly,
    }
    with open(out_path, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存: {out_path}")


if __name__ == '__main__':
    main()
