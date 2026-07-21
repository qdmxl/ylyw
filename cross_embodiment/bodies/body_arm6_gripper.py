#!/usr/bin/env python3
"""
6轴协作机械臂 + 力控夹爪 — 本体配置 (YLYW 直接控制版)

与 arm6_hand 共享同一套6轴关节控制逻辑，
末端换为力控夹爪。

YLYW 卦象策略直接决定6个关节的目标角度
和夹爪的力矩大小。
"""

import numpy as np, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_config import BodyConfig, YaoThresholds
from body_arm6_hand import Q_HOME, FINGER_ACT


class Arm6GripperConfig(BodyConfig):
    """6轴臂 + 力控夹爪 — YLYW 直接控制"""

    def __init__(self):
        super().__init__()
        self.name = "arm6_gripper"
        self.n_dof = 8
        self.n_ctrl = 8
        self.end_effector = "2-finger gripper on 6-DOF arm"
        self.description = "UR5-style 6-DOF arm + parallel gripper, YLYW direct control"

        self.xy_align_thresh = 0.025
        self.z_approach_thresh = 0.05
        self.lift_threshold = 0.03

        self.joint_ranges = [
            (-3.14, 3.14), (-2.5, 2.5), (-2.5, 2.5),
            (-3.14, 3.14), (-2.0, 2.0), (-3.14, 3.14),
        ]

    def encode_yao(self, bagua, obs):
        yao = np.zeros(6)
        joints = obs.get('joints', {})
        contacts = obs.get('contact', [])
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.26]))
        lift_h = obs.get('lift_height', 0.0)

        dx = palm_pos[0] - obj_pos[0]
        dy = palm_pos[1] - obj_pos[1]
        xy_dist = math.sqrt(dx*dx + dy*dy)
        z_dist = palm_pos[2] - obj_pos[2]

        n_contacts = 0
        for c in contacts:
            g1, g2 = c.get('geom1',''), c.get('geom2','')
            if ('fl_' in g1 or 'fr_' in g1) and 'obj' in g2: n_contacts += 1
            if ('fl_' in g2 or 'fr_' in g2) and 'obj' in g1: n_contacts += 1

        fl = joints.get('fl_j', 0)
        fr = joints.get('fr_j', 0)
        grip_close = 0.07 - fl - fr
        lift = max(0, lift_h)

        yao[0] = YaoThresholds.gaussian(xy_dist, center=0, sigma=self.xy_align_thresh)
        yao[1] = YaoThresholds.gaussian(z_dist, center=0.03, sigma=0.04)
        yao[2] = np.clip(n_contacts / 2.0, 0, 1)
        yao[3] = np.clip(1.0 - grip_close / 0.06, 0, 1)
        yao[4] = np.clip(lift / self.lift_threshold, 0, 1)
        yao[5] = 0.1 if (lift > 0.01 and n_contacts < 1) else (0.9 if lift > 0 else 1.0)
        return yao

    def decode_action(self, strategy, obs, current_ctrl=None):
        ctrl = np.zeros(self.n_ctrl)
        if current_ctrl is not None:
            ctrl[:] = current_ctrl

        stype = strategy.get('strategy_type', 'standard_grasp')
        params = strategy.get('params', {})
        speed = params.get('speed', 0.5)
        force = params.get('force', 0.5)

        joints = obs.get('joints', {})
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.26]))

        q_current = np.array([joints.get(f'j{i}', Q_HOME[i-1]) for i in range(1, 7)])

        dx = obj_pos[0] - palm_pos[0]
        dy = obj_pos[1] - palm_pos[1]
        dz = obj_pos[2] - palm_pos[2]

        if stype in ("全力抓取/执行", "power_grasp"):
            j1_target = math.atan2(dy, dx) if abs(dx)+abs(dy) > 0.001 else q_current[0]
            q_target = np.array([
                j1_target,
                -0.3 + dz * 0.3,
                1.0 - dz * 0.5,
                0.0,
                -0.5 - dz * 0.3,
                0.0,
            ])
            for i in range(6):
                lo, hi = self.joint_ranges[i]
                q_target[i] = np.clip(q_target[i], lo, hi)
            alpha = min(1.0, speed * 0.15)
            ctrl[:6] = q_current * (1-alpha) + q_target * alpha
            gf = 0.3 + force * 0.5
            ctrl[6] = gf
            ctrl[7] = gf

        elif stype in ("任务完成/确认", "balanced_grasp"):
            q_target = q_current.copy()
            q_target[1] += 0.1
            q_target[2] += 0.05
            for i in range(6):
                lo, hi = self.joint_ranges[i]
                q_target[i] = np.clip(q_target[i], lo, hi)
            ctrl[:6] = q_target
            ctrl[6] = 0.4
            ctrl[7] = 0.4

        elif stype in ("待机/准备",):
            alpha = min(1.0, speed * 0.1)
            ctrl[:6] = q_current * (1-alpha) + Q_HOME * alpha
            ctrl[6] = -0.2
            ctrl[7] = -0.2

        elif stype == "缓慢接近/精确对准":
            j1_target = math.atan2(dy, dx) if abs(dx)+abs(dy) > 0.001 else q_current[0]
            q_target = np.array([
                j1_target * 0.3 + q_current[0] * 0.7,
                q_current[1] + dz * 0.15,
                q_current[2] - dz * 0.2,
                0.0,
                q_current[4] - dz * 0.1,
                0.0,
            ])
            for i in range(6):
                lo, hi = self.joint_ranges[i]
                q_target[i] = np.clip(q_target[i], lo, hi)
            alpha = min(1.0, speed * 0.08)
            ctrl[:6] = q_current * (1-alpha) + q_target * alpha
            ctrl[6] = 0.1
            ctrl[7] = 0.1

        elif stype in ("任务未完成/继续尝试",):
            q_target = q_current.copy()
            q_target[1] -= 0.05
            q_target[2] += 0.05
            for i in range(6):
                lo, hi = self.joint_ranges[i]
                q_target[i] = np.clip(q_target[i], lo, hi)
            ctrl[:6] = q_target
            ctrl[6] = min(1.0, 0.5 + force * 0.6)
            ctrl[7] = min(1.0, 0.5 + force * 0.6)

        else:
            j1_target = math.atan2(dy, dx) if abs(dx)+abs(dy) > 0.001 else q_current[0]
            ctrl[:6] = [j1_target, q_current[1], q_current[2]*0.9, 0, q_current[4], 0]
            ctrl[6] = 0.2
            ctrl[7] = 0.2

        return ctrl
