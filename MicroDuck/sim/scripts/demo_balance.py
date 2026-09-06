#!/usr/bin/env python3
"""MicroDuck 抗扰(站立保持)演示 —— 给 ylyw 提供“能落地的控制评估基准”。

流程: STAND 起始 → 施加一个前向速度冲量 → 让控制器(= 保持 STAND 目标)自行恢复,
统计 竖直时间占比/是否倒地。

用法:
    python scripts/demo_balance.py [--push 0.5] [--horizon 3.0]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from env.microduck_env import StandingEnv, ensure_control_model, SERVO_JOINTS, _HOME

H = np.array([_HOME[j] for j in SERVO_JOINTS])


def hold_stand_controller(env, obs, t):
    # “零策略”: 一直把 14 关节拉回 HOME(唯一可以稳定站立的静态目标)。
    return H


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", type=float, default=0.5)
    ap.add_argument("--horizon", type=float, default=3.0)
    a = ap.parse_args()

    ensure_control_model()
    env = StandingEnv(control_dt=0.02)
    env.reset("STAND")

    # 施加冲量
    env.apply_push((a.push, 0.0, 0.0))
    print(f"已施加前向冲量 vx=+{a.push} m/s;后续由 hold-stand 控制器接管\n")

    records, summary = env.run_gait_record(hold_stand_controller, a.horizon)
    # 打印阶段摘要(只输出 /5 避免刷屏)
    print("t(s)   x     躯干z   pitch°   足L 足R  竖直?")
    for r in records[:: len(records) // 10 + 1]:
        print(f"{r['t']:5.2f} {r['x']:+7.3f} {r['z']:7.3f} "
              f"{r['pitch_deg']:6.1f}  {'O' if r['foot_l'] else '.'}  "
              f"{'O' if r['foot_r'] else '.'}   {'y' if r['upright'] else 'n'}")
    print("\n=== 汇总 ===")
    for k, v in summary.items():
        print(f"  {k:14s}: {v}")
    ok = summary["final_upright"] and summary["upright_frac"] > 0.7
    print("\n判定:", "PASS —— 扰动后可自行恢复稳定" if ok else
          "FAIL —— 纯静态目标无法抗此扰(ylyw 需要主动平衡控制)")


if __name__ == "__main__":
    main()
