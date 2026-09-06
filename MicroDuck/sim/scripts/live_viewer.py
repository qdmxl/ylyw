#!/usr/bin/env python3
"""MicroDuck 实时查看器 —— 在桌面(Wayland :0)开 MuJoCo 交互窗口看鸭子动。

用法:
  python scripts/live_viewer.py                 # 默认: 从 STAND 起让 hold-stand 盯着
  python scripts/live_viewer.py --tilt          # 每 1.2s 施加一个小推力看恢复
  python scripts/live_viewer.py --sit           # 起点用 SIT
按 Esc/右上角关闭窗口结束。
"""
import os
import sys
import time
import argparse

import numpy as np
import mujoco

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mujoco.viewer as viewer  # noqa:E402
from gl_env import configure_opengl_env  # noqa:E402
from env.microduck_env import ensure_control_model, SERVO_JOINTS, _HOME  # noqa:E402

HOME = np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="STAND")
    ap.add_argument("--tilt", action="store_true", help="周期加小推力观察恢复")
    ap.add_argument("--fps", type=float, default=200.0, help="可实时调倍速")
    a = ap.parse_args()

    configure_opengl_env()
    xml = ensure_control_model()
    m = mujoco.MjModel.from_xml_path(xml)
    d = mujoco.MjData(m)
    if a.key:
        for k in range(m.nkey):
            if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_KEY, k) == a.key:
                mujoco.mj_resetDataKeyframe(m, d, k)
                break
    mujoco.mj_forward(m, d)
    # 初始执行器目标 = 当前关节,避免跳变
    for jn, v in zip(SERVO_JOINTS, HOME):
        for ai in range(m.nu):
            if m.actuator(ai).name and m.actuator(ai).name == jn:
                d.ctrl[ai] = v

    print("按标题栏/右上角 关闭窗口结束;鸭子默认靠 hold-stand 站立。")
    v = viewer.launch_passive(m, d)
    t0 = time.time()
    last_push = t0
    try:
        while v.is_running():
            step_start = time.time()
            # hold-stand 盯住目标
            for ai in range(m.nu):
                d.ctrl[ai] = 0.0  # 复位
            for jn, val in zip(SERVO_JOINTS, HOME):
                for ai in range(m.nu):
                    if m.actuator(ai).name == jn:
                        d.ctrl[ai] = val
            # 可选推一把
            if a.tilt and time.time() - last_push > 1.5:
                d.qvel[0] += 0.4
                last_push = time.time()
            # 固定实时率
            mujoco.mj_step(m, d)
            v.sync()
            dt = time.time() - step_start
            if dt < 1.0 / a.fps:
                time.sleep(max(0.0, 1.0 / a.fps - dt))
    finally:
        v.close()
    # 结束后回显躯干高作为简单指标
    print(f"结束: trunk_z={float(d.qpos[2]):.3f}  位移x={float(d.qpos[0]):.3f}")


if __name__ == "__main__":
    main()
