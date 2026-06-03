#!/usr/bin/env python3
"""
实验A: 零样本步态识别基线测试
验证YLYW在零样本条件下对多种运动状态推理的合理性和一致性
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from ylyw_locomotion import YLYWLocomotionController


def generate_test_scenarios():
    """
    生成测试场景：覆盖11种步态模式 × 10种初始条件 = 110个测试点
    每种模式在6维空间中采样变体
    """
    np.random.seed(42)
    
    # 场景模板: (名称, 期望步态类型, 6维状态中心, 噪声方差)
    templates = [
        # 静止类
        ("稳定站立",     "stand",        [0.92, 0.85, 0.80, 0.90, 0.03, 0.80], [0.05]*6),
        ("斜面站立",     "stand",        [0.75, 0.70, 0.65, 0.75, 0.08, 0.55], [0.05]*6),
        
        # 行走类
        ("平地慢走",     "slow_walk",    [0.70, 0.72, 0.68, 0.65, 0.20, 0.78], [0.05]*6),
        ("正常行走",     "walk",         [0.65, 0.70, 0.65, 0.60, 0.30, 0.75], [0.05]*6),
        ("快速行走",     "fast_walk",    [0.60, 0.72, 0.70, 0.52, 0.45, 0.78], [0.05]*6),
        
        # 跑动类
        ("小跑步态",     "trot",         [0.55, 0.72, 0.72, 0.48, 0.55, 0.75], [0.05]*6),
        ("高速奔跑",     "run",          [0.50, 0.75, 0.75, 0.42, 0.65, 0.78], [0.05]*6),
        
        # 特殊类
        ("受扰动恢复",   "recovery",     [0.22, 0.32, 0.28, 0.15, 0.78, 0.55], [0.05]*6),
        ("上坡爬行",     "climb",        [0.48, 0.42, 0.52, 0.32, 0.45, 0.18], [0.05]*6),
        ("下坡慢行",     "descend",      [0.50, 0.35, 0.45, 0.35, 0.40, 0.28], [0.05]*6),
        ("崎岖地形",     "caution_walk", [0.42, 0.45, 0.38, 0.32, 0.48, 0.15], [0.05]*6),
    ]
    
    scenarios = []
    for name, expected_gait, center, noise in templates:
        for i in range(10):
            state = np.clip(np.array(center) + np.random.normal(0, noise), 0.0, 1.0)
            scenarios.append({
                'id': f"{name}_{i+1}",
                'name': name,
                'expected_gait': expected_gait,
                'state': state.tolist(),
            })
    
    return scenarios


def evaluate_gait_reasonableness(gait_type, expected_gait, speed):
    """
    评估步态合理性
    
    Returns:
        'reasonable': 步态类型合理
        'acceptable': 步态类型可以接受（偏保守但安全）
        'unreasonable': 步态类型明显不合理
    """
    # 步态速度等级映射
    speed_levels = {
        'stand': 0, 'crawl': 1, 'recovery': 1,
        'caution_walk': 2, 'slow_walk': 2, 'descend': 2,
        'walk': 3, 'transition': 3, 'adaptive': 3,
        'turn': 3, 'climb': 3,
        'fast_walk': 4,
        'trot': 5,
        'run': 6,
    }
    
    expected_level = speed_levels.get(expected_gait, 3)
    actual_level = speed_levels.get(gait_type, 3)
    
    diff = abs(actual_level - expected_level)
    
    if diff == 0:
        return 'exact'
    elif diff <= 1:
        return 'reasonable'
    elif diff <= 2:
        return 'acceptable'
    else:
        return 'unreasonable'


def run_experiment_a():
    """运行实验A：零样本步态识别"""
    controller = YLYWLocomotionController()
    scenarios = generate_test_scenarios()
    
    print("=" * 70)
    print("实验A: 零样本步态识别基线测试")
    print(f"场景数: {len(scenarios)} (11种步态 × 10变体)")
    print("=" * 70)
    
    results = []
    start_time = time.time()
    
    for sc in scenarios:
        state = np.array(sc['state'])
        gp = controller.infer(state, verbose=False)
        
        reasonableness = evaluate_gait_reasonableness(
            gp['gait_type'], sc['expected_gait'], gp['speed']
        )
        
        results.append({
            'id': sc['id'],
            'name': sc['name'],
            'expected': sc['expected_gait'],
            'actual': gp['gait_type'],
            'actual_name': gp['gait_name'],
            'hexagram': gp['hexagram_name'],
            'similarity': gp['similarity'],
            'reasonableness': reasonableness,
            'speed': gp['speed'],
            'yin_yang': gp['yin_yang'],
        })
    
    elapsed = time.time() - start_time
    avg_inference = elapsed / len(scenarios) * 1000
    
    # 统计
    exact = sum(1 for r in results if r['reasonableness'] == 'exact')
    reasonable = sum(1 for r in results if r['reasonableness'] in ('exact', 'reasonable'))
    acceptable = sum(1 for r in results if r['reasonableness'] in ('exact', 'reasonable', 'acceptable'))
    unreasonable = sum(1 for r in results if r['reasonableness'] == 'unreasonable')
    
    # 按期望步态分组
    by_gait = {}
    for r in results:
        eg = r['expected']
        if eg not in by_gait:
            by_gait[eg] = {'total': 0, 'exact': 0, 'reasonable': 0, 'acceptable': 0}
        by_gait[eg]['total'] += 1
        if r['reasonableness'] == 'exact':
            by_gait[eg]['exact'] += 1
        if r['reasonableness'] in ('exact', 'reasonable'):
            by_gait[eg]['reasonable'] += 1
        if r['reasonableness'] in ('exact', 'reasonable', 'acceptable'):
            by_gait[eg]['acceptable'] += 1
    
    # 打印结果
    print(f"\n{'='*70}")
    print(f"总体结果")
    print(f"{'='*70}")
    print(f"精确匹配:     {exact:>3}/{len(results)} ({exact/len(results)*100:5.1f}%)")
    print(f"合理(含精确):  {reasonable:>3}/{len(results)} ({reasonable/len(results)*100:5.1f}%)")
    print(f"可接受(全部):  {acceptable:>3}/{len(results)} ({acceptable/len(results)*100:5.1f}%)")
    print(f"不合理:        {unreasonable:>3}/{len(results)} ({unreasonable/len(results)*100:5.1f}%)")
    print(f"平均推理时间:  {avg_inference:.2f} ms")
    
    print(f"\n按步态类型:")
    print(f"{'期望步态':<14} {'精确':>4} {'合理':>4} {'可接受':>4} {'不合理':>4} {'精确率':>7}")
    print('-' * 50)
    for gait_name in sorted(by_gait.keys()):
        g = by_gait[gait_name]
        exact_pct = g['exact'] / g['total'] * 100
        print(f"{gait_name:<14} {g['exact']:>3}/{g['total']:<5} {g['reasonable']:>3} {g['acceptable']:>3} {g['total']-g['acceptable']:>3} {exact_pct:>6.1f}%")
    
    # 打印部分推理链示例
    print(f"\n{'='*70}")
    print("推理链示例（每种步态取1例）")
    print(f"{'='*70}")
    
    shown = set()
    for r in results:
        if r['expected'] not in shown:
            shown.add(r['expected'])
            print(f"\n场景: {r['name']} ({r['id']})")
            print(f"  期望: {r['expected']} → 实际: {r['actual_name']}({r['actual']})")
            print(f"  卦象: {r['hexagram']} (sim={r['similarity']:.3f})")
            print(f"  速度: {r['speed']:.2f} m/s | 六爻: {r['yin_yang']} | 评价: {r['reasonableness']}")
    
    # 保存结果
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(out_dir, '..', 'experiment_phase1', 'data', 'motion_exp_a_results.json')
    
    summary = {
        'experiment': 'A - Zero-shot Gait Recognition',
        'total_scenarios': len(scenarios),
        'exact': exact,
        'reasonable': reasonable,
        'acceptable': acceptable,
        'unreasonable': unreasonable,
        'exact_rate': exact / len(scenarios),
        'reasonable_rate': reasonable / len(scenarios),
        'acceptable_rate': acceptable / len(scenarios),
        'avg_inference_ms': avg_inference,
        'by_gait': by_gait,
        'results': results,
    }
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存: {out_path}")
    
    return summary


if __name__ == '__main__':
    run_experiment_a()
