#!/usr/bin/env python3
"""MicroDuck 实时查看器 —— 在桌面(Wayland :0)开 MuJoCo 交互窗口,看鸭子实时跑。

可按 --algo 选控制器,并在窗口/回车后打印正在跑的卦与自知力系数(走 ylyw v2 时)。

用法:
  python scripts/live_viewer.py                        # hold-stand 站立
  python scripts/live_viewer.py --algo ylyw2          # ylyw 卦相位步态(向前走)
  python scripts/live_viewer.py --algo ylyw2 --tilt   # + 每 1.5s 推一下,看自知收力+恢复
  python scripts/live_viewer.py --algo walk           # gait.make_walk_ctrl
  python scripts/live_viewer.py --sit                 # 换个起始姿态(SIT)
按右上角/标题栏×关闭窗口;最后一行回显位移与是否直立。
"""
import os
import sys
import time
import argparse

import numpy as np
import mujoco

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (BASE, os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

import mujoco.viewer as viewer  # noqa:E402
from gl_env import configure_opengl_env  # noqa:E402
from env.microduck_env import (
    StandingEnv, ensure_control_model, SERVO_JOINTS, _HOME, )  # noqa:E402


def build_controller(algo, args_cmd=None):
    """返回 controller(env, obs, t)->target14 与一个 HUD 读取器(或 None)。"""
    if algo in ("hold", "none") or algo is None:
        HOME = np.array([_HOME[j] for j in SERVO_JOINTS], float)
        def ctrl(env, obs, t):
            return HOME.copy()
        return ctrl, None
    if algo == "ylyw2":
        from ylyw_algos.ylyw_gait_v2 import YLYWMicroDuckGait
        c = YLYWMicroDuckGait(intent="walk", lean=0.012)
        return c, lambda: getattr(c, "_state", None)
    if algo in ("waddle", "ylyww", "duck"):
        from ylyw_algos.ylyw_gait_v2 import YLYWMicroDuckGait
        c = YLYWMicroDuckGait(intent="waddle")
        return c, lambda: getattr(c, "_state", None)
    if algo == "walk":
        from ylyw_algos.gait import make_walk_ctrl
        from ylyw_algos.gait import SERVO_JOINTS as _  # noqa:F401  (确保存在)
        c = make_walk_ctrl(speed_ramp=0.0)
        return c, None
    raise SystemExit(f"未知 --algo {algo}(可选 hold / ylyw2 / walk)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="STAND")
    ap.add_argument("--algo", default="hold")
    ap.add_argument("--tilt", action="store_true", help="周期加小推力看自知收力/恢复")
    ap.add_argument("--tilt-gap", type=float, default=1.5, help="两次推的间隔s")
    ap.add_argument("--force", type=float, default=0.45, help="推力幅度 m/s")
    ap.add_argument("--fps", type=float, default=200.0)
    a = ap.parse_args()

    configure_opengl_env()
    xml = ensure_control_model()
    env = StandingEnv(xml_path=xml, control_dt=0.02)
    env.reset(a.key if a.key else "STAND")

    ctrl, hud = build_controller(a.algo)
    m, d = env.model, env.data

    # 让控制器看一眼初始状态,打印 ylyw 推出的卦(若 HUD)
    try:
        ctrl(env, env.observe(), 0.0)
    except Exception as e:
        print("[warn] 控制器首次调用失败:", e)

    print(f"algo={a.algo} 起点={a.key or 'STAND'} 控制率={env.control_dt:.2f}s"
          f"  物理dt={env.dt:.4f}s")
    if hud:
        print("HUD: 每2s打印一次 ylyw 状态(卦, 自知力系数)")
    print("关闭窗口(=标题栏✕/右上角×/按 Esc 若绑定)结束; Ctrl-C 亦可。")
    v = viewer.launch_passive(m, d)
    t_last_push = time.time()
    sim_t = 0.0
    n_sub = max(1, round(env.control_dt / env.dt))
    this_control = env.control_dt
    hud_next = 2.0
    start_wall = time.time()
    try:
        while v.is_running():
            tick = time.time()
            # --- 控制周期: 求 14 关节目标,下发给当前 env.data ---
            acts = None
            try:
                acts = ctrl(env, env.observe(), sim_t)
            except Exception:
                acts = None
            if acts is not None:
                env.set_target(np.asarray(acts, float))
            # 物理推进一个控制周期(与 run_gait_record 同)
            for _ in range(n_sub):
                if a.tilt and time.time() - t_last_push > a.tilt_gap:
                    d.qvel[0] += a.force
                    t_last_push = time.time()
                mujoco.mj_step(m, d)
            sim_t += this_control
            if hud:
                st = hud()
                if st is not None and sim_t >= hud_next:
                    print(f"  [卦={st[0]} 自知力系数={st[1]:.2f}]  x={d.qpos[0]:+.3f} z={d.qpos[2]:.3f}")
                    hud_next = sim_t + 2.0
            v.sync()
            dt = time.time() - tick
            if dt < 1.0 / a.fps:
                time.sleep(max(0.0, 1.0 / a.fps - dt))
    except KeyboardInterrupt:
        pass
    finally:
        v.close()
    up = bool(env.is_upright())
    print(f"\n结束: x位移={d.qpos[0]:+.3f} m  躯干z={d.qpos[2]:.3f}  直立={up}  "
          f"墙钟={time.time()-start_wall:.1f}s")


if __name__ == "__main__":
    main()
