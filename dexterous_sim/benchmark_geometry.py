#!/usr/bin/env python3
"""
YLYW 灵巧手仿真 — YLYW 几何推理 vs 基线 (手腕+前伸)
"""

import os, sys, math, time, numpy as np
os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
import mujoco

from grasp_env import STRATEGY_TO_POSITION, FINGER_NAMES
from benchmark_screenshot import load_model
from geometric_ylyw import GeometricYLYW


def run_trial_force(m, d, finger_angles, force_scale=1.0, torque_mod=None, wrist=None):
    # ctrl: 0=lift_z, 1=pitch, 2=yaw, 3=reach, 4-13=fingers
    act_map = {'thumb': (4,5), 'index': (6,7), 'middle': (8,9), 'ring': (10,11), 'pinky': (12,13)}
    max_t = {'thumb': 2.5, 'index': 2.0, 'middle': 2.0, 'ring': 1.8, 'pinky': 1.5}
    if torque_mod is None: torque_mod = {f: 1.0 for f in FINGER_NAMES}
    wrist = wrist or (0.0, 0.0, 0.0)

    def _apply_torque(tighten=1.0):
        for f, (a1, a2) in act_map.items():
            if f in finger_angles:
                j1, j2 = finger_angles[f]
                mt = max_t.get(f, 0.5)
                mod = torque_mod.get(f, 1.0)
                d.ctrl[a1] = j1 * mt / 1.2 * tighten * force_scale * mod
                d.ctrl[a2] = j2 * mt / 1.2 * tighten * force_scale * mod

    # 1. 手腕姿态 + 前伸 + 降臂
    d.ctrl[1] = wrist[0]; d.ctrl[2] = wrist[1]; d.ctrl[3] = wrist[2]
    d.ctrl[0] = -0.20  # 大幅降臂
    for i in range(4, len(d.ctrl)): d.ctrl[i] = 0.0
    for _ in range(200): mujoco.mj_step(m, d)  # 更多步数，让手到位

    init_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]

    # 2. 闭合
    _apply_torque(tighten=1.0)
    for _ in range(150): mujoco.mj_step(m, d)

    # 3. 抬臂
    d.ctrl[0] = 0.12
    for _ in range(300):
        _apply_torque(tighten=1.3)
        mujoco.mj_step(m, d)

    final_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]
    lift_mm = (final_obj_z - init_obj_z) * 1000
    success = lift_mm > 3.0

    contacts = {f: False for f in FINGER_NAMES}
    for i in range(d.ncon):
        g1 = m.geom(d.contact[i].geom1).name
        g2 = m.geom(d.contact[i].geom2).name
        for f in FINGER_NAMES:
            if f in g1 or f in g2: contacts[f] = True
    n_fingers = sum(1 for v in contacts.values() if v)
    return {'success': success, 'lift_mm': lift_mm, 'n_fingers': n_fingers}


def get_default_strategy_angles(strat_name):
    pos = STRATEGY_TO_POSITION.get(strat_name, {f: (0,0) for f in FINGER_NAMES})
    return pos, (0.0, 0.0, 0.0)


if __name__ == '__main__':
    print("=" * 70)
    print("YLYW 灵巧手仿真 — 手腕+前伸")
    print("=" * 70)
    strategies = ['soft_grasp', 'cautious_grasp', 'power_grasp', 'precision_grasp',
                  'wrap_grasp', 'firm_grasp', 'dynamic_grasp', 'adaptive_grasp']
    fs_list = [0.6, 1.0]; objects = ['sphere','box','cylinder','long_rod','mushroom','dumbbell','disc']

    print(f"\n{'─'*70}")
    print("【基线】")
    base_r = []
    for obj in objects:
        for s in strategies:
            for fs in fs_list:
                m = load_model(obj); d = mujoco.MjData(m)
                pos, wr = get_default_strategy_angles(s)
                base_r.append((obj, s, fs, run_trial_force(m,d,pos,fs,wrist=wr)))
    n = sum(1 for _,_,_,r in base_r if r['success'])
    print(f"  总计: {n}/{len(base_r)} ({n/len(base_r)*100:.0f}%)")

    print(f"\n{'─'*70}")
    print("【YLYW】几何+八卦+六爻→手指+手腕+前伸+爻位力矩修正")
    gylyw = GeometricYLYW()
    ylyw_r = []
    for obj in objects:
        for s in strategies:
            for fs in fs_list:
                m = load_model(obj); d = mujoco.MjData(m)
                angles = gylyw.infer_finger_angles(obj)
                r = run_trial_force(m, d, angles, fs,
                    torque_mod=gylyw._torque_mod, wrist=gylyw._wrist)
                ylyw_r.append((obj, s, fs, r))
    n = sum(1 for _,_,_,r in ylyw_r if r['success'])
    print(f"  总计: {n}/{len(ylyw_r)} ({n/len(ylyw_r)*100:.0f}%)")

    print(f"\n{'─'*70}")
    print(f"{'物体':12s} {'基线':16s} {'YLYW+手':18s} {'增量':10s}")
    print(f"{'─'*60}")
    tb = ty = 0
    for obj in objects:
        bo = sum(1 for o,_,_,r in base_r if o==obj and r['success'])
        yo = sum(1 for o,_,_,r in ylyw_r if o==obj and r['success'])
        tb += bo; ty += yo
        t = sum(1 for o,_,_,_ in base_r if o==obj)
        d = yo - bo
        print(f"{obj:12s} {bo:3d}/{t:2d} ({bo/t*100:3.0f}%)  "
              f"{yo:3d}/{t:2d} ({yo/t*100:3.0f}%)  {'+'+str(d) if d>0 else str(d)}")
    print(f"{'─'*60}")
    print(f"{'总计':12s} {tb:3d}/{len(base_r):2d} ({tb/len(base_r)*100:3.0f}%)  "
          f"{ty:3d}/{len(ylyw_r):2d} ({ty/len(ylyw_r)*100:3.0f}%)  +{ty-tb}")

    print(f"\n{'─'*70}")
    print("YLYW详细:")
    print(f"{'物体':12s} {'手腕+前伸':20s} {'力':5s} {'提升':8s}")
    gylyw2 = GeometricYLYW()
    for obj in objects:
        gylyw2.infer_finger_angles(obj)
        for fs in fs_list:
            r = next(rr for o,_,f,rr in ylyw_r if o==obj and f==fs)
            wr = gylyw2._wrist
            print(f"  {obj:12s} p{wr[0]:+.2f} y{wr[1]:+.2f} r{wr[2]:+.3f}  {fs:.1f}  {r['lift_mm']:+.1f}mm  "
                  f"{'✅' if r['success'] else '❌'}")
