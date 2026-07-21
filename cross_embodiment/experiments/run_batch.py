#!/usr/bin/env python3
"""
批量跨本体抓取实验

运行所有本体 × 所有物体的抓取测试，
记录成功率和提升高度，生成对比报告。

用法:
    python3 experiments/run_batch.py                    # 全量实验
    python3 experiments/run_batch.py --bodies hand     # 仅灵巧手
    python3 experiments/run_batch.py --bodies gripper  # 仅夹爪
    python3 experiments/run_batch.py --no-zhiji        # 禁用知几学习(对比)
"""

import os, sys, time, json, argparse
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mujoco_env import CrossBodyEnv
from core.zhiji_infer import ZhijiInfer
from core.zhiji_learning import ZhijiLearning

from bodies.body_shadow_hand import ShadowHand3AxisConfig
from bodies.body_gripper import Gripper3AxisConfig

# ====== 配置 ======

OBJECTS = ['sphere', 'box', 'cylinder', 'long_rod', 'mushroom', 'dumbbell', 'disc']
OFFSETS = [(0.0, 0.0), (0.02, 0.02)]  # 无偏移 + 偏移
N_REPEATS = 3         # 每个条件重复次数（统计稳定性）
MAX_STEPS = 300       # 每次实验最大步数
LIFT_THRESHOLD = 3.0  # 成功判定阈值 (mm)

BODIES = {
    'shadow_hand_3axis': {
        'config_class': ShadowHand3AxisConfig,
        'label': '灵巧手+3轴臂',
    },
    'force_gripper_3axis': {
        'config_class': Gripper3AxisConfig,
        'label': '力控夹爪+3轴臂',
    },
}


def run_single(env, body_type, body_config, object_key, offset,
               use_zhiji=True, zhiji_engine=None, task_desc='grasp'):
    """
    执行一次抓取实验

    Returns:
        (success: bool, lift_mm: float, steps: int, strategy_chain: list)
    """
    obs = env.reset(object_key=object_key, object_offset=offset)

    if use_zhiji:
        engine = ZhijiInfer(body_config, body_type=body_type, zhiji=zhiji_engine)
        engine.start_trajectory(object_key=object_key, object_offset=offset)
    else:
        from core.cross_body_infer import CrossBodyInfer
        engine = CrossBodyInfer(body_config)

    strategy_chain = []

    for step in range(MAX_STEPS):
        strategy = engine.infer(obs, task_desc=task_desc,
                                object_key=object_key, object_offset=offset)
        ctrl = engine.decode_action(strategy, obs)
        obs, _, _, _ = env.step(ctrl)

        if use_zhiji:
            engine.record_step(obs, strategy, ctrl)

        lift_mm = env.get_obj_lift_mm()

        if step % 50 == 0:
            strategy_chain.append({
                'step': step,
                'hexagram': strategy.get('hexagram_name', ''),
                'strategy': strategy.get('strategy_type', ''),
                'lift_mm': lift_mm,
            })

        # 提前结束：提升成功或超过最大提升
        if lift_mm > LIFT_THRESHOLD and step > 50:
            # 保持几帧确认
            if env.get_obj_lift_mm() > LIFT_THRESHOLD:
                break

    lift_mm = env.get_obj_lift_mm()
    success = lift_mm > LIFT_THRESHOLD

    if use_zhiji:
        engine.finish_trajectory(success, lift_mm)
        final_params = engine.get_params()
    else:
        final_params = {}

    return {
        'success': success,
        'lift_mm': float(round(lift_mm, 1)),
        'steps': step + 1,
        'strategy_chain': strategy_chain,
        'final_params': final_params,
    }


def run_experiment(body_type: str, use_zhiji: bool = True,
                   results_file: str = None,
                   n_repeats: int = 3) -> Dict:
    """运行单个本体的所有实验"""
    body_cfg = BODIES[body_type]
    config = body_cfg['config_class']()
    label = body_cfg['label']

    env = CrossBodyEnv(body_type=body_type, headless=True)
    zhiji = ZhijiLearning(save_dir=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results'),
        verbose=False)

    if use_zhiji:
        zhiji.load()

    print(f"\n{'='*60}")
    print(f"本体: {label} ({body_type})")
    print(f"{'='*60}")

    all_results = {}
    summary = []

    for obj in OBJECTS:
        for offset in OFFSETS:
            offset_label = f"({offset[0]*1000:.0f}mm, {offset[1]*1000:.0f}mm)"
            results_for_condition = []

            for rep in range(n_repeats):
                sys.stdout.write(f"\r  {obj:12s} 偏移{offset_label}: {rep+1}/{n_repeats}")
                sys.stdout.flush()

                result = run_single(env, body_type, config, obj, offset,
                                    use_zhiji=use_zhiji, zhiji_engine=zhiji)
                results_for_condition.append(result)

            # 统计分析
            successes = [r['success'] for r in results_for_condition]
            lifts = [r['lift_mm'] for r in results_for_condition]
            steps = [r['steps'] for r in results_for_condition]
            sr = sum(successes) / len(successes) * 100

            print(f"\r  {obj:12s} 偏移{offset_label}: "
                  f"{sum(successes)}/{n_repeats} = {sr:.0f}%  "
                  f"lift={np.mean(lifts):+.1f}mm  "
                  f"steps={int(np.mean(steps))}")

            all_results[f"{obj}_{offset_label}"] = {
                'sr': sr,
                'avg_lift': round(np.mean(lifts), 1),
                'std_lift': round(np.std(lifts), 1),
                'avg_steps': int(np.mean(steps)),
                'details': results_for_condition,
            }

            summary.append({
                'body': body_type,
                'object': obj,
                'offset': offset_label,
                'sr': sr,
                'avg_lift': round(np.mean(lifts), 1),
                'avg_steps': int(np.mean(steps)),
            })

    env = None

    # 汇总
    total_all = sum(len(r['details']) for r in all_results.values())
    total_ok = sum(
        sum(1 for d in r['details'] if d['success'])
        for r in all_results.values()
    )
    print(f"\n  {'─'*50}")
    print(f"  总 {total_all} 次实验, 成功 {total_ok} 次 "
          f"({total_ok/total_all*100:.0f}%)")

    # 保存结果
    if results_file:
        data = {
            'body_type': body_type,
            'label': label,
            'use_zhiji': use_zhiji,
            'results': {k: {
                'sr': v['sr'],
                'avg_lift': v['avg_lift'],
                'std_lift': v['std_lift'],
                'avg_steps': v['avg_steps'],
            } for k, v in all_results.items()},
            'summary': summary,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        with open(results_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  结果保存至: {results_file}")

    return {'all_results': all_results, 'summary': summary, 'zhiji': zhiji}


def print_comparison(all_body_results: dict):
    """打印跨本体对比表"""
    print("\n" + "=" * 70)
    print("跨本体泛化对比结果")
    print("=" * 70)

    # 表头
    header = f"{'物体':12s}"
    for body_type, body_cfg in BODIES.items():
        header += f" {body_cfg['label']:20s}"
    print(header)
    print(f"{'─'*12} {'─'*20} {'─'*20}")

    for obj in OBJECTS:
        row = f"{obj:12s}"
        for body_type in BODIES:
            sr_list = []
            lift_list = []
            for offset in OFFSETS:
                offset_label = f"({offset[0]*1000:.0f}mm, {offset[1]*1000:.0f}mm)"
                key = f"{obj}_{offset_label}"
                if body_type in all_body_results and key in all_body_results[body_type]['all_results']:
                    r = all_body_results[body_type]['all_results'][key]
                    sr_list.append(r['sr'])
                    lift_list.append(r['avg_lift'])
            if sr_list:
                avg_sr = np.mean(sr_list)
                avg_lift = np.mean(lift_list)
                row += f" {avg_sr:5.0f}%/{avg_lift:+.1f}mm  "
            else:
                row += f" {'N/A':>18s}"
        print(row)

    print(f"\n{'─'*70}")
    print("Transfer Gap (偏移 vs 居中 的性能差距):")
    for body_type in BODIES:
        label = BODIES[body_type]['label']
        gaps = []
        for obj in OBJECTS:
            centered_key = f"{obj}_(0mm, 0mm)"
            offset_key = f"{obj}_(20mm, 20mm)"
            br = all_body_results.get(body_type, {}).get('all_results', {})
            if centered_key in br and offset_key in br:
                c_sr = br[centered_key]['sr']
                o_sr = br[offset_key]['sr']
                gaps.append(c_sr - o_sr)
        if gaps:
            print(f"  {label:20s}: 平均TGT={np.mean(gaps):+.1f}%")


def main():
    parser = argparse.ArgumentParser(description='跨本体批量实验')
    parser.add_argument('--bodies', nargs='+', choices=list(BODIES.keys()) + ['all'],
                       default=['all'], help='本体类型')
    parser.add_argument('--no-zhiji', action='store_true', help='禁用知几学习')
    parser.add_argument('--repeats', type=int, default=N_REPEATS)
    args = parser.parse_args()

    n_repeats = args.repeats

    bodies_to_run = list(BODIES.keys()) if 'all' in args.bodies else args.bodies
    use_zhiji = not args.no_zhiji

    all_results = {}
    for body_type in bodies_to_run:
        results_file = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'results',
            f"results_{body_type}_{'zhiji' if use_zhiji else 'nocalib'}.json")
        result = run_experiment(body_type, use_zhiji=use_zhiji,
                                results_file=results_file,
                                n_repeats=n_repeats)
        all_results[body_type] = result

    if len(bodies_to_run) > 1:
        print_comparison(all_results)

    print("\n✅ 批量实验完成")


if __name__ == '__main__':
    main()
