#!/usr/bin/env python3
"""
基线方法 — Random 策略 & Open-loop 策略 (难度增强版)

增加任务难度使基线有区分度：
  1. Random: 控制范围缩小（不能直接闭合手指，必须先下降）
  2. Open-loop: 固定的简单动作，不对大偏移物体有效
  3. 减少步数上限，减少试错空间
"""

import os, sys, numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.mujoco_env import CrossBodyEnv


def _get_nu_ranges(body_type, nu):
    """根据本体类型获取每个控制维度的随机范围（难度调参）"""
    if body_type == 'shadow_hand_3axis':
        # 滑台范围缩小到±4cm，手指不能全开
        return [
            (-0.04, 0.04), (-0.04, 0.04), (-0.30, 0.05),  # slide_x/y, lift_z
            (-0.3, 0.3), (-0.3, 0.3), (0.0, 0.05),         # wrist
            (0.0, 0.6), (0.0, 0.6), (0.0, 0.6), (0.0, 0.6),  # 手指半开
            (0.0, 0.6), (0.0, 0.6), (0.0, 0.6), (0.0, 0.6),
            (0.0, 0.6), (0.0, 0.6),
        ]
    elif body_type == 'force_gripper_3axis':
        return [
            (-0.04, 0.04), (-0.04, 0.04), (-0.30, 0.05),
            (0.0, 0.6), (0.0, 0.6),
        ]
    elif 'arm6' in body_type:
        # 6轴臂：关节角小幅随机变动
        base = [(-0.3, 0.3)] * 6  # 每个关节±0.3 rad
        if 'hand' in body_type:
            base += [(0.0, 0.4)] * 10  # 手指微动
        else:
            base += [(0.0, 0.3)] * 2   # 夹爪微动
        return base
    return [(0, 0)] * nu


def run_random(env, body_type, max_steps=200, success_threshold_mm=30):
    """随机策略：有限随机动作"""
    import mujoco
    nu = env.model.nu
    ranges = _get_nu_ranges(body_type, nu)
    assert len(ranges) == nu, f'{body_type}: nu={nu}, ranges={len(ranges)}'

    peak_lift = 0.0
    hold = 0
    for step in range(max_steps):
        ctrl = np.array([np.random.uniform(l, h) for l, h in ranges])
        env.data.ctrl[:] = ctrl
        mujoco.mj_step(env.model, env.data)
        lift = env.get_obj_lift_mm()
        peak_lift = max(peak_lift, lift)
        if lift > success_threshold_mm:
            hold += 1
            if hold >= 30:
                return {'success': True, 'lift_mm': float(lift),
                        'peak_lift_mm': float(peak_lift), 'steps': step+1}
        else:
            hold = 0
    fl = env.get_obj_lift_mm()
    return {'success': bool(fl > success_threshold_mm), 'lift_mm': float(fl),
            'peak_lift_mm': float(peak_lift), 'steps': max_steps}


def run_openloop(env, body_type, max_steps=200, success_threshold_mm=30):
    """开环策略：固定简单的动作序列，不做感知反馈"""
    import mujoco
    nu = env.model.nu

    if body_type == 'shadow_hand_3axis':
        # 简单下降+抓取（不追踪偏移）
        c1 = np.array([0.0, 0.0, -0.25, 0.1, 0.0, 0.02,
                      0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # 仅下降
        c2 = np.array([0.0, 0.0, -0.25, 0.1, 0.0, 0.02,
                      0.4, 0.3, 0.4, 0.3, 0.4, 0.3, 0.4, 0.3, 0.3, 0.2])  # 闭合
        c3 = np.array([0.0, 0.0, 0.08, 0.1, 0.0, 0.02,
                      0.3, 0.2, 0.3, 0.2, 0.3, 0.2, 0.3, 0.2, 0.2, 0.1])  # 提升
    elif body_type == 'force_gripper_3axis':
        c1 = np.array([0.0, 0.0, -0.28, 0.1, 0.1])
        c2 = np.array([0.0, 0.0, -0.28, 0.4, 0.4])
        c3 = np.array([0.0, 0.0, 0.06, 0.3, 0.3])
    elif 'arm6' in body_type:
        if 'hand' in body_type:
            c1 = np.array([0, -0.8, 1.6, 0, -0.8, 0] + [0.0]*10)   # 待机
            c2 = np.array([0, -0.5, 1.2, 0, -0.5, 0] + [0.4]*10)   # 下降
            c3 = np.array([0, -0.3, 1.0, 0, -0.3, 0] + [0.3]*10)   # 提升
        else:
            c1 = np.array([0, -0.8, 1.6, 0, -0.8, 0, 0.0, 0.0])
            c2 = np.array([0, -0.5, 1.2, 0, -0.5, 0, 0.4, 0.4])
            c3 = np.array([0, -0.3, 1.0, 0, -0.3, 0, 0.3, 0.3])
    else:
        c1 = c2 = c3 = np.zeros(nu)

    assert len(c1) == nu
    n1 = min(100, max_steps // 2)
    n2 = min(60, max_steps // 3)
    n3 = max_steps - n1 - n2
    peak_lift = 0
    hold = 0
    step = 0

    for ctrl, n in [(c1, n1), (c2, n2), (c3, n3)]:
        for _ in range(n):
            env.data.ctrl[:] = ctrl
            mujoco.mj_step(env.model, env.data)
            step += 1
            lift = env.get_obj_lift_mm()
            peak_lift = max(peak_lift, lift)
            if lift > success_threshold_mm:
                hold += 1
                if hold >= 30:
                    return {'success': True, 'lift_mm': float(lift),
                            'peak_lift_mm': float(peak_lift), 'steps': step}
            else:
                hold = 0

    fl = env.get_obj_lift_mm()
    return {'success': bool(fl > success_threshold_mm), 'lift_mm': float(fl),
            'peak_lift_mm': float(peak_lift), 'steps': step}
