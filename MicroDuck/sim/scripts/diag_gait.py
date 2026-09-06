#!/usr/bin/env python3
"""诊断一段步态:打印随时间 x位移、左右足触地、髋俯仰,判断是真迈步还是滑擦。"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env.microduck_env import StandingEnv, SERVO_JOINTS, _HOME
import search_gait as sg
sys.path.insert(0,'scripts')

env = StandingEnv(control_dt=0.02)
cfg = dict(amp_hp=0.05, freq=1.2, lift=0.05, bal_kp=0.0)
ctrl = sg.build_controller(**cfg)
env.reset("STAND")
dt = env.control_dt
prev_foot = None
for i in range(int(3.0/dt)):
    obs = env.observe()
    act = ctrl(env, obs, i*dt)
    env.step(act if act is not None else None)
    if i % 10 == 0:  # every 0.2s
        cont = env.get_contacts()
        fp = (env.get_joint_pos()[2], env.get_joint_pos()[11])  # 髋pitch L/R
        toep = (env.get_joint_pos()[4], env.get_joint_pos()[13])
        print(f"t={i*dt:.2f} x={env.data.qpos[0]:+.3f} fl={int(cont['left_on'])} "
              f"fr={int(cont['right_on'])} hipL={fp[0]:+.3f} hipR={fp[1]:+.3f} "
              f"ankL={toep[0]:+.3f} ankR={toep[1]:+.3f} z={env.data.qpos[2]:.3f}")
