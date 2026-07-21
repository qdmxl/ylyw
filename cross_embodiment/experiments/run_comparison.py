#!/usr/bin/env python3
"""
YCB 标准物体 × 跨本体 × 多基线 对比实验

同时运行 Random / Open-loop / YLYW 在同一场景下对比。
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
from bodies.body_arm6_hand import Arm6HandConfig
from bodies.body_arm6_gripper import Arm6GripperConfig
from baselines.baseline_methods import run_random, run_openloop

YCB_SCRIPTS = os.path.expanduser('~/MXL/科研/ylyw/experiment_phase1/scripts')
sys.path.insert(0, YCB_SCRIPTS)
sys.path.insert(0, os.path.dirname(YCB_SCRIPTS))
sys.path.insert(0, os.path.expanduser('~/MXL/科研/ylyw'))
try:
    from object_presets import OBJECT_PRESETS
except ImportError:
    OBJECT_PRESETS = {}
try:
    from object_presets_extended import _EXTENDED_PRESETS
except ImportError:
    _EXTENDED_PRESETS = {}

YCB_OBJECTS = dict(OBJECT_PRESETS)
YCB_OBJECTS.update(_EXTENDED_PRESETS)

YCB_TO_MJ_GEO = {
    'sphere': 'sphere', 'cube': 'box', 'cylinder': 'cylinder',
    'bowl': 'sphere', 'bottle': 'cylinder', 'plate': 'cylinder',
    'rock': 'sphere', 'vase': 'cylinder',
}

BODIES = {
    'shadow_hand_3axis': {'config_class': ShadowHand3AxisConfig, 'label': '灵巧手+3轴臂'},
    'force_gripper_3axis': {'config_class': Gripper3AxisConfig, 'label': '力控夹爪+3轴臂'},
    'arm6_hand': {'config_class': Arm6HandConfig, 'label': '6轴臂+灵巧手'},
    'arm6_gripper': {'config_class': Arm6GripperConfig, 'label': '6轴臂+夹爪'},
}

RESULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')


def get_ycb_objects(n: int = 17):
    keys = list(YCB_OBJECTS.keys())[:n]
    return [(k, YCB_OBJECTS[k].get('type', 'sphere'), YCB_OBJECTS[k].get('features', {})) for k in keys]


def _run_one(method, env, body_type, config, use_zhiji, zhiji_engine,
             obj_id, obj_type, features, trial, max_steps=400):
    import mujoco
    np.random.seed(trial * 100 + hash(obj_id) % 10000)
    ox, oy = np.random.uniform(-0.10, 0.10, 2)
    mj_key = YCB_TO_MJ_GEO.get(obj_type, 'sphere')
    env.reset(object_key=mj_key, object_offset=(ox, oy))

    if method == 'random':
        return run_random(env, body_type, max_steps=max_steps)
    if method == 'openloop':
        return run_openloop(env, body_type, max_steps=max_steps)

    # ylyw
    if use_zhiji:
        engine = ZhijiInfer(config, body_type=body_type, zhiji=zhiji_engine)
        engine.start_trajectory(object_key=obj_id, object_offset=(ox, oy))
    else:
        from core.cross_body_infer import CrossBodyInfer
        engine = CrossBodyInfer(config)

    peak_lift = 0
    hold = 0
    for step in range(max_steps):
        strategy = engine.infer(env.get_observation(), task_desc='grasp',
                                object_key=obj_id, object_offset=(ox, oy))
        ctrl = engine.decode_action(strategy, env.get_observation())
        env.data.ctrl[:] = ctrl
        mujoco.mj_step(env.model, env.data)
        if use_zhiji:
            engine.record_step(env.get_observation(), strategy, ctrl)
        lift = env.get_obj_lift_mm()
        peak_lift = max(peak_lift, lift)
        if lift > 30:
            hold += 1
            if hold >= 30:
                break
        else:
            hold = 0

    fl = env.get_obj_lift_mm()
    ok = fl > 30
    if use_zhiji:
        engine.finish_trajectory(ok, fl)
    return {'success': ok, 'lift_mm': float(fl), 'peak_lift_mm': float(peak_lift), 'steps': step + 1}


def run_comparison(body_type, methods, n_objects=17, n_repeats=5):
    label = BODIES[body_type]['label']
    config = BODIES[body_type]['config_class']()
    env = CrossBodyEnv(body_type=body_type, headless=True)
    zhiji = ZhijiLearning(verbose=False)
    zhiji.load()
    objects = get_ycb_objects(n_objects)
    total = len(objects) * n_repeats * len(methods)

    print(f"\n{'='*65}")
    print(f"本体: {label}")
    print(f"方法: {methods}")
    print(f"物体: {len(objects)}个YCB × {n_repeats}次 × {len(methods)}种方法 = {total}次试验")
    print(f"{'='*65}")

    stats = defaultdict(lambda: defaultdict(lambda: {'ok': 0, 'n': 0, 'lifts': []}))

    for method in methods:
        for obj_id, obj_type, features in objects:
            for trial in range(n_repeats):
                sys.stdout.write(f"\r  {method:12s} {obj_id:20s} {trial+1}/{n_repeats}")
                sys.stdout.flush()
                r = _run_one(method, env, body_type, config,
                             use_zhiji=(method == 'ylyw'),
                             zhiji_engine=zhiji if method == 'ylyw' else None,
                             obj_id=obj_id, obj_type=obj_type,
                             features=features, trial=trial)
                s = stats[method][obj_type]
                s['n'] += 1
                s['lifts'].append(r['lift_mm'])
                if r['success']:
                    s['ok'] += 1

            st = stats[method][obj_type]
            sr = f"{st['ok']}/{st['n']} = {st['ok']/st['n']*100:.0f}%"
            avg_l = np.mean(st['lifts'])
            print(f"\r  {method:12s} {obj_id:20s}: {sr:>14s}  lift={avg_l:+.1f}mm")

    env = None

    # save
    serializable = {}
    for m in stats:
        serializable[m] = {}
        for t in stats[m]:
            serializable[m][t] = {
                'ok': stats[m][t]['ok'], 'n': stats[m][t]['n'],
                'avg_lift': round(np.mean(stats[m][t]['lifts']), 1),
            }
    rf = os.path.join(RESULT_DIR, f"comparison_{body_type}.json")
    with open(rf, 'w') as f:
        json.dump(serializable, f, indent=2)

    return stats


def print_results(all_stats):
    print(f"\n\n{'='*70}")
    print("YCB 标准物体 × 跨本体 × 多基线 对比结果")
    print(f"{'='*70}")

    for body_type, stats in sorted(all_stats.items()):
        label = BODIES[body_type]['label']
        methods = sorted(stats.keys())
        types = sorted(set(t for m in stats for t in stats[m]))

        print(f"\n{label}:")
        print(f"{'类型':15s} " + " ".join(f"{m:>10s}" for m in methods))
        print(f"{'─'*15} {'─'*10*len(methods)}")

        for t in types:
            row = f"{t:15s}"
            for m in methods:
                s = stats[m].get(t, {'ok': 0, 'n': 0})
                sr = s['ok'] / max(1, s['n']) * 100
                row += f" {sr:5.1f}%    "
            print(row)

        row = f"{'总计':15s}"
        for m in methods:
            total_ok = sum(stats[m][t]['ok'] for t in types if t in stats[m])
            total_n = sum(stats[m][t]['n'] for t in types if t in stats[m])
            row += f" {total_ok/max(1,total_n)*100:5.1f}%    "
        print(f"{'─'*15} {'─'*10*len(methods)}")
        print(row)


def main():
    parser = argparse.ArgumentParser(description='YCB 跨本体对比实验')
    parser.add_argument('--bodies', nargs='+', choices=list(BODIES.keys())+['all'],
                       default=['all'])
    parser.add_argument('--methods', nargs='+', choices=['random','openloop','ylyw'],
                       default=['random','openloop','ylyw'])
    parser.add_argument('--n-objects', type=int, default=17)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()

    if args.quick:
        args.n_objects = 3
        args.repeats = 3

    bodies = list(BODIES.keys()) if 'all' in args.bodies else args.bodies
    all_stats = {}
    for body_type in bodies:
        s = run_comparison(body_type, args.methods, args.n_objects, args.repeats)
        all_stats[body_type] = s

    print_results(all_stats)
    print("\n✅ 对比实验完成")


if __name__ == '__main__':
    main()
