"""ylyw(易理/模糊)思路的相位步态 —— MicroDuck 第一版能动、不摔的控制器。

设计(informal 易理相位框架):
  - “一阴一阳之谓道”: 左右腿互为阴/阳,相位差 π,由单一相位变量 φ(t) 驱动,
    保证腿间天然对称与连续,避免离散状态机跳变 —— 相位即“变化之机”。
  - 动作用原语叠加(髋摆 / 抬腿 / 支撑后蹬推进 / 踝保持脚面),按 φ gating 组合；
  - 关键: 叠加强度 0.1 的躯干俯仰反馈(bal_kp)拉回躯体,否则头重鸭一蹬就栽。

参数是在 CPU 仿真里用 search_gait.py 扫描得到的一组可行点:
  始终直立(upright_frac≈1.0),接触以单足交替为主(single_frac≈0.6),
  3s 净前进 +0.11~0.18 m(起步加速中)。属“可用稳定步”,还不是大步行走。

用法(见同目录 example.py / scripts/demo_walk.py):
    from ylyw_algos.gait import make_walk_ctrl
    ctrl = make_walk_ctrl()
    env.run_gait_record(ctrl, seconds=4)
"""
from __future__ import annotations

import os
import sys
import numpy as np

_SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

try:
    from env.microduck_env import SERVO_JOINTS, _HOME
except Exception:
    raise RuntimeError("在 MicroDuck/sim 下运行")

HOME = np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)
# 关节轴索引(SERVO_JOINTS 顺序)
HPL, KNL, ANL = 2, 3, 4
HPR, KNR, ANR = 11, 12, 13


def make_walk_ctrl(freq_hz: float = 1.8, amp: float = 0.05,
                   lift: float = 0.06, prop: float = 0.08,
                   lean: float = 0.0, bal_kp: float = 0.10,
                   speed_ramp: float = 0.0):
    """ylyw 相位步态控制器。核心与 scripts/search_gait.build_controller 同源
    (经扫描可确定能直立前行的实现),这里独立成包内正式版。

    amp  髋摆幅; lift 抬腿量; prop 支撑腿后蹬推进量;
    bal_kp 躯干俯仰闭环增益(>0 抗栽); lean 前倾偏置;speed_ramp 柔起步秒数。

    经验证参数: amp=.05 freq=1.8 lift=.06 prop=.08 bal_kp=.10  →
    3s 直立前移 +0.115m(upright=1.0,single_frac≈0.6)。
    """
    def ctrl(env, obs, t):
        tgt = HOME.copy()
        sc = 1.0
        if speed_ramp:
            sc = min(1.0, t / speed_ramp)
        a = amp * sc
        ph = 2 * np.pi * freq_hz * t
        sh = np.sin(ph)
        swL = max(0.0, sh)      # L 摆动相位门
        swR = max(0.0, -sh)     # R 摆动相位门
        # 髋交替摆 + 支撑后蹬推进(注意踝/髋符号与 search 同源)
        tgt[HPL] = HOME[HPL] + a * sh - prop * swL * 0.5
        tgt[HPR] = HOME[HPR] - a * sh + prop * swR * 0.5
        # 摆动腿屈膝抬脚
        tgt[KNL] = HOME[KNL] - lift * swL
        tgt[KNR] = HOME[KNR] - lift * swR
        # 踝保持脚面(左腿减、右腿加的符号与官方/home 镜像一致)
        tgt[ANL] = HOME[ANL] - (tgt[HPL] - HOME[HPL]) - 0.15 * swL
        tgt[ANR] = HOME[ANR] + (tgt[HPR] - HOME[HPR]) - 0.15 * swR
        # 前倾偏置(可选)
        if lean:
            tgt[HPL] += lean
            tgt[HPR] += lean
        # 平衡: 躯干俯仰闭环(测量式须与 search 一致)
        if bal_kp:
            q = env.data.qpos[3:7]
            w, x, y, z = q
            R00 = 1 - 2 * (y * y + z * z)
            R10 = 2 * (x * y + w * z)
            pitch = np.arctan2(-R10, R00)
            corr = bal_kp * pitch
            tgt[HPL] += corr
            tgt[HPR] += corr
        return tgt
    return ctrl


def hold_ctrl():
    """保守零步: 站住不动(对照用)。"""
    def ctrl(env, obs, t):
        return HOME.copy()
    return ctrl


if __name__ == "__main__":
    from env.microduck_env import StandingEnv
    env = StandingEnv(control_dt=0.02)
    print("walk 4s(带 1s 缓起):")
    ctrl = make_walk_ctrl(speed_ramp=1.0)
    rec, m = env.run_gait_record(ctrl, seconds=4.0)
    print("  ", m)
