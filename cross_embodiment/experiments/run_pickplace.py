#!/usr/bin/env python3
"""
YCB 精准放置 (Pick-and-Place) 实验 — v2

统一使用 PickPlaceInfer 管理"接近→抓取→移动→释放"阶段的只有 YLYW。
Random 和 Open-loop 的放置任务用直接控制实现公平对比。

三种方法在完全相同的环境设置下运行。
"""

import os, sys, time, json, argparse, math
import numpy as np
from typing import Dict, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mujoco_env import CrossBodyEnv
from core.zhiji_learning import ZhijiLearning
from core.pickplace_infer import PickPlaceInfer
from bodies.body_shadow_hand import ShadowHand3AxisConfig
from bodies.body_gripper import Gripper3AxisConfig
from bodies.body_arm6_hand import Arm6HandConfig
from bodies.body_arm6_gripper import Arm6GripperConfig

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


def get_ycb_objects(n=17):
    keys = list(YCB_OBJECTS.keys())[:n]
    return [(k, YCB_OBJECTS[k].get('type', 'sphere'), YCB_OBJECTS[k].get('features', {})) for k in keys]


def _run_trial(method, body_type, config, env, obj_id, obj_type, trial):
    """运行单次试验，返回结果"""
    import mujoco
    np.random.seed(trial * 100 + hash(obj_id) % 10000)
    ox, oy = np.random.uniform(-0.10, 0.10, 2)
    mj_key = YCB_TO_MJ_GEO.get(obj_type, 'sphere')
    env.reset(object_key=mj_key, object_offset=(ox, oy))

    max_steps = 300
    nu = env.model.nu

    if method == 'ylyw':
        zhiji = ZhijiLearning(verbose=False)
        zhiji.load()
        engine = PickPlaceInfer(config, body_type=body_type, zhiji=zhiji)
        engine.start_trajectory(obj_id, (ox, oy))

        for step in range(max_steps):
            strategy = engine.infer(env.get_observation(), task_desc=None,
                                    object_key=obj_id, object_offset=(ox, oy))
            ctrl = engine.decode_action(strategy, env.get_observation())
            env.data.ctrl[:] = ctrl
            mujoco.mj_step(env.model, env.data)
            engine.record_step(env.get_observation(), strategy, ctrl)
            if engine.task_completed:  # DONE
                break

        fl = env.get_obj_lift_mm()
        obj_pos = env.get_observation()['object_pos']
        dist = math.sqrt(obj_pos[0]**2 + obj_pos[1]**2)
        # 真正的放置成功：物体已放回桌面（提升<15mm）+ 在目标区域（距离中心<5cm）
        placed = fl < 15 and dist < 0.05
        # 抓取阶段评估作为辅助指标
        grasped = fl > 30
        engine.finish_trajectory(placed, fl)
        return {'success': placed, 'lift_mm': float(fl), 'peak_lift': float(engine.peak_lift),
                'grasped': bool(grasped), 'place_error_mm': float(dist*1000), 'steps': step+1}

    # === Random ===
    if body_type == 'shadow_hand_3axis':
        # 前150步随机搜索+抓取，后150步随机移动+释放
        ranges_grasp = [(-0.04, 0.04)]*2 + [(-0.30, 0.08)] + [(-0.3,0.3)]*2 + [(0,0.03)] + [(0,0.6)]*10
        ranges_move  = [(-0.04, 0.04)]*2 + [(0.05, 0.12)]  + [(-0.3,0.3)]*2 + [(0,0.03)] + [(0.2,0.5)]*10
    elif body_type == 'force_gripper_3axis':
        ranges_grasp = [(-0.04,0.04)]*2 + [(-0.30,0.08)] + [(0,0.6)]*2
        ranges_move  = [(-0.04,0.04)]*2 + [(0.05,0.12)]  + [(0,0.4)]*2
    elif 'arm6' in body_type:
        ranges_grasp = [(-0.3,0.3)]*6 + [(0,0.4)]*(nu-6)
        ranges_move  = [(-0.2,0.2)]*6 + [(0,0.3)]*(nu-6)
    else:
        ranges_grasp = ranges_move = [(0,0)]*nu

    peak_lift = 0
    for step in range(max_steps):
        r = ranges_grasp if step < 150 else ranges_move
        ctrl = np.array([np.random.uniform(l,h) for l,h in r])
        env.data.ctrl[:] = ctrl
        mujoco.mj_step(env.model, env.data)
        peak_lift = max(peak_lift, env.get_obj_lift_mm())

    fl = env.get_obj_lift_mm()
    obj_pos = env.get_observation()['object_pos']
    dist = math.sqrt(obj_pos[0]**2 + obj_pos[1]**2)
    return {'success': fl < 15 and dist < 0.05, 'lift_mm': float(fl),
            'peak_lift': float(peak_lift), 'grasped': bool(peak_lift>30),
            'place_error_mm': float(dist*1000), 'steps': max_steps}

    # === Open-loop ===
    # （Open-loop 对放置任务天然不利，因为不知道何时释放）
    if body_type == 'shadow_hand_3axis':
        p_grasp = np.array([0,0,-0.25,0.1,0,0.03] + [0.4]*10)
        p_lift   = np.array([0,0,0.10,0.1,0,0.03] + [0.3]*10)
        p_release= np.array([0,0,0.05,0,0,0] + [0]*10)
    elif body_type == 'force_gripper_3axis':
        p_grasp = np.array([0,0,-0.28,0.5,0.5])
        p_lift   = np.array([0,0,0.08,0.4,0.4])
        p_release= np.array([0,0,0.05,-0.2,-0.2])
    elif 'arm6' in body_type:
        if 'hand' in body_type:
            p_grasp = np.array([0,-0.5,1.2,0,-0.5,0] + [0.4]*10)
            p_lift   = np.array([0,-0.3,1.0,0,-0.3,0] + [0.3]*10)
            p_release= np.array([0,-0.3,1.0,0,-0.3,0] + [0]*10)
        else:
            p_grasp = np.array([0,-0.5,1.2,0,-0.5,0,0.5,0.5])
            p_lift   = np.array([0,-0.3,1.0,0,-0.3,0,0.4,0.4])
            p_release= np.array([0,-0.3,1.0,0,-0.3,0,-0.3,-0.3])
    else:
        return {'success': False, 'lift_mm': 0, 'peak_lift': 0, 'place_error_mm': 999, 'steps': 0}

    peak_lift = 0
    phases = [(p_grasp, 120), (p_lift, 60), (p_release, 80)]
    step = 0
    for ctrl, n in phases:
        for _ in range(n):
            env.data.ctrl[:] = ctrl
            mujoco.mj_step(env.model, env.data)
            step += 1
            peak_lift = max(peak_lift, env.get_obj_lift_mm())

    fl = env.get_obj_lift_mm()
    obj_pos = env.get_observation()['object_pos']
    dist = math.sqrt(obj_pos[0]**2 + obj_pos[1]**2)
    placed = fl < 15 and dist < 0.05
    return {'success': placed, 'lift_mm': float(fl),
            'peak_lift': float(peak_lift), 'grasped': bool(peak_lift>30),
            'place_error_mm': float(dist*1000), 'steps': step}


def run_comparison(body_type, methods, n_objects=5, n_repeats=5):
    label = BODIES[body_type]['label']
    config = BODIES[body_type]['config_class']()
    env = CrossBodyEnv(body_type=body_type, headless=True)
    objects = get_ycb_objects(n_objects)
    total = len(objects) * n_repeats * len(methods)

    print(f"\n{'='*65}")
    print(f"[Pick-and-Place v2] 本体: {label}")
    print(f"方法: {methods}")
    print(f"物体: {len(objects)}个YCB × {n_repeats}次 × {len(methods)}种方法 = {total}次试验")
    print(f"{'='*65}")

    stats = defaultdict(lambda: defaultdict(lambda: {'ok': 0, 'n': 0, 'grasped': 0, 'lifts': [], 'errors': []}))

    for method in methods:
        for obj_id, obj_type, features in objects:
            for trial in range(n_repeats):
                sys.stdout.write(f"\r  {method:12s} {obj_id:20s} {trial+1}/{n_repeats}")
                sys.stdout.flush()
                r = _run_trial(method, body_type, config, env, obj_id, obj_type, trial)
                s = stats[method][obj_type]
                s['n'] += 1
                s['lifts'].append(r['lift_mm'])
                s['errors'].append(r.get('place_error_mm', 999))
                if r['success']:
                    s['ok'] += 1
                if r.get('grasped', False):
                    s['grasped'] += 1

            st = stats[method][obj_type]
            sr = f"{st['ok']}/{st['n']} = {st['ok']/st['n']*100:.0f}%"
            avg_e = np.mean(st['errors'])
            gr = f"抓成{st['grasped']}/{st['n']}" if method == 'ylyw' else ''
            print(f"\r  {method:12s} {obj_id:20s}: {sr:>14s}  err={avg_e:.0f}mm {gr}")

    env = None
    return stats


def print_results(all_stats):
    print(f"\n\n{'='*70}")
    print("YCB Pick-and-Place v2 对比结果")
    print(f"{'='*70}")
    for body_type, stats in sorted(all_stats.items()):
        label = BODIES[body_type]['label']
        methods = sorted(stats.keys())
        types = sorted(set(t for m in stats for t in stats[m]))
        print(f"\n{label}:")
        h = f"{'类型':15s}"
        for m in methods: h += f" {m:>12s}"
        print(h)
        print(f"{'─'*15} {'─'*12*len(methods)}")
        for t in types:
            r = f"{t:15s}"
            for m in methods:
                s = stats[m].get(t, {'ok':0,'n':0})
                r += f" {s['ok']/max(1,s['n'])*100:5.1f}%     "
            print(r)
        row = f"{'总计':15s}"
        for m in methods:
            to = sum(stats[m][t]['ok'] for t in types if t in stats[m])
            tn = sum(stats[m][t]['n'] for t in types if t in stats[m])
            row += f" {to/max(1,tn)*100:5.1f}%     "
        print(f"{'─'*15} {'─'*12*len(methods)}")
        print(row)


def main():
    parser = argparse.ArgumentParser(description='YCB Pick-and-Place v2')
    parser.add_argument('--bodies', nargs='+', choices=list(BODIES.keys())+['all'], default=['all'])
    parser.add_argument('--methods', nargs='+', choices=['random','openloop','ylyw'], default=['random','openloop','ylyw'])
    parser.add_argument('--n-objects', type=int, default=5)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    if args.quick:
        args.n_objects = 3; args.repeats = 3

    bodies = list(BODIES.keys()) if 'all' in args.bodies else args.bodies
    all_stats = {}
    for body_type in bodies:
        s = run_comparison(body_type, args.methods, args.n_objects, args.repeats)
        all_stats[body_type] = s
    print_results(all_stats)
    print("\n✅ Pick-and-Place v2 完成")


if __name__ == '__main__':
    main()
