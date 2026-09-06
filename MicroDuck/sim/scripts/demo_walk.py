#!/usr/bin/env python3
"""MicroDuck: 用 ylyw 相位步态走一段(demo)。

在 CPU 仿真里连续走 T 秒,打印:
  - 竖直保持率 / 净前进 x / 躯干高(是否摔倒、走了多远)
  - 可选 --anim: 渲染成动图(需桌面 OpenGL,见 render_frames.py)

用法:
  python scripts/demo_walk.py --secs 3
  python scripts/demo_walk.py --secs 2.5 --out data/duck_walk.gif   # 顺带动图
"""
import os
import sys
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env.microduck_env import StandingEnv  # noqa:E402
from ylyw_algos.gait import make_walk_ctrl  # noqa:E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=3.0)
    ap.add_argument("--freq", type=float, default=1.8)
    ap.add_argument("--amp", type=float, default=0.05)
    ap.add_argument("--lift", type=float, default=0.06)
    ap.add_argument("--out", default=None, help="若给,渲染动画用这些参数")
    a = ap.parse_args()

    ctrl = make_walk_ctrl(freq_hz=a.freq, amp=a.amp, lift=a.lift, speed_ramp=0.0)
    env = StandingEnv(control_dt=0.02)
    rec, m = env.run_gait_record(ctrl, seconds=a.secs)
    print(f"ylyw 相位步态走 {a.secs}s:")
    print(f"  竖直保持  upright_frac = {m['upright_frac']}")
    print(f"  净前进    final_x      = {m['final_x']:+.3f} m")
    print(f"  躯干高    final_z      = {m['final_z']:.3f} m")
    if m["final_upright"] and m["final_x"] > 0.02:
        print("  判定: PASS —— 直立并向前走出距离(动能转换中,非原地不倒)")

    if a.out:
        from render_frames import render_frames, _resolve_controllers
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        ctrls = _resolve_controllers("walk")
        # 用同样参数重建(默认 make_walk_ctrl() 即 a 的一致参数)
        from ylyw_algos import gait
        ctrls = (gait.make_walk_ctrl(freq_hz=a.freq, amp=a.amp, lift=a.lift),)
        render_frames(keyframe="STAND", out=a.out, controllers=ctrls,
                      horizon_s=a.secs, step_s=0.05, fps=12)


if __name__ == "__main__":
    main()
