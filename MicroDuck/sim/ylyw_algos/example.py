"""ylyw 算法接入点示例/脚手架(由你填充真实策略)。

ylyw 思路(示意):
  1. 易理/64卦 把“行走目标”(如速度、转向)编码为步态相位 φ ∈ [0, 2π) 或相位矢量,
  2. 把相位映射到腿部动作原语(髋俯仰摆 / 膝屈 / 踝补偿 / 抬腿),
  3. 在 Physics(本环境)里逐步验证,依据竖起保持率等指标迭代。

`make_gait` 返回一个 controller(env, obs, t) -> 14 关节目标角,
可直接喂给 env.run_gait_record(controller, seconds=...) 评估。
"""
from __future__ import annotations

import os
import sys
import numpy as np

# 兼容“直接在仓库里跑脚本”与“作为包使用”两种入口
_SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SIM not in sys.path:
    sys.path.insert(0, _SIM)

try:
    from env.microduck_env import SERVO_JOINTS, _HOME
except Exception:  # 包相对导入
    try:
        from ..env.microduck_env import SERVO_JOINTS, _HOME
    except Exception:
        raise RuntimeError("无法定位 env.microduck_env —— 请在 MicroDuck/sim 下运行")

HOME = np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)


def hold_stand():
    """零策略:始终把 14 关节拉回站立姿态。整只鸭子能站住,但不前进。"""
    return lambda env, obs, t: HOME.copy()


def make_gait(freq_hz: float = 1.6, swing: float = 0.18, lift: float = 0.10):
    """简单的开环对称摆腿控制器(示例,未必走得稳 —— 用它体会为何要主动平衡)。

    关节轴索引见 SERVO_JOINTS: left_hip_pitch=2, left_knee=3, left_ankle=4,
    right_hip_pitch=11, right_knee=12, right_ankle=13, hip_roll L=1 R=10。
    """
    def ctrl(env, obs, t):
        target = HOME.copy()
        ph = 2 * np.pi * freq_hz * t
        # 前后摆髋(左右反相)
        target[2]  = HOME[2]  + swing * np.sin(ph)          # 左髋前摆
        target[11] = HOME[11] - swing * np.sin(ph)          # 右髋后摆(反相)
        # 抬腿: 髋俯仰相位前段屈膝(简单近似: 用 sin 的符号使腿交替微抬)
        target[3]  = HOME[3]  - lift * max(0.0, np.sin(ph))          # 左膝
        target[12] = HOME[12] - lift * max(0.0, -np.sin(ph))         # 右膝
        # 踝补偿保持脚面: 脚踝目标相对髋尽量维持脚面大致水平
        target[4]  = HOME[4]  - (target[2] - HOME[2])
        target[13] = HOME[13] - (target[11] - HOME[11])
        return target
    return ctrl


if __name__ == "__main__":
    from env.microduck_env import StandingEnv
    env = StandingEnv(control_dt=0.02)
    print("hold_stand 评估(3s):")
    _, s = env.run_gait_record(hold_stand(), seconds=3.0)
    print("  ", s)
    print("\n开环摆腿 gait 评估(3s):")
    rec, s2 = env.run_gait_record(make_gait(), seconds=3.0)
    print("  ", s2)
