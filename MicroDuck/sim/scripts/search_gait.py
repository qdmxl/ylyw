#!/usr/bin/env python3
"""ylyw 相位步态 —— 搜索一组能真走、且不摔的参数。

策略(易理/相位框架):
  φ(t) 相位驱动髋俯仰交替;叠加少量“髋补偿”维持竖直;整组参数在 CPU 仿真里
  用 run_gait_record 的竖直保持率 + 净位移自动搜。仿真比实时快约 40x,可扫。

输出: 最优参数 + 竖直到末 / 净前进位移;并可回调导出轨迹供渲染动图。
"""
import os
import sys
import time
import argparse
import itertools

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env.microduck_env import StandingEnv, SERVO_JOINTS, _HOME  # noqa:E402

HOME = np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)
# 轴向索引
HPL = 2; KNL = 3; ANL = 4
HPR = 11; KNR = 12; ANR = 13


def build_controller(amp_hp=0.10, freq=1.5, lift=0.08, prop=0.10, lean=0.0,
                     bal_kp=0.0):
    """ylyw 相位步态。返回 controller(env,obs,t)->target14。

    动作原语(以相位 gating 组合):
      髋俯仰交替摆 (amp_hp)
      支撑相髋向后蹬推进 (prop, 假设触地足向后伸展推动躯干前移)
      摆动相抬腿离地 (lift)
      躯干前倾 lean(简单设髋 pitch 偏置)推动前进趋势
      平衡反馈 bal_kp: 躯干前/后倾 -> 双髋同向修正防摔
    """
    def ctrl(env, obs, t):
        tgt = HOME.copy()
        ph = 2 * np.pi * freq * t
        sh = np.sin(ph)
        # 摆动/支撑判别(相位门): 腿i摆动约前半程
        swL = max(0.0, sh)       # L 摆动门 ∈[0,1]  (sh>0 视为 L 摆动)
        swR = max(0.0, -sh)      # R 摆动门
        # 1) 髋对称交替摆
        tgt[HPL] = HOME[HPL] + amp_hp * sh
        tgt[HPR] = HOME[HPR] - amp_hp * sh
        # 2) 推进: 接触地被压向后/被摆髋前移 -> 简化: 摆动结束前足下压后蹬由髋扩展承担
        tgt[HPL] -= prop * swL * 0.5      # L 摆动时髋更向前(抬足前摆)
        tgt[HPR] += prop * swR * 0.5
        # 3) 抬腿(摆动腿屈膝)
        tgt[KNL] = HOME[KNL] - lift * swL
        tgt[KNR] = HOME[KNR] - lift * swR
        # 踝保持脚面水平
        tgt[ANL] = HOME[ANL] - (tgt[HPL] - HOME[HPL]) - 0.15*swL
        tgt[ANR] = HOME[ANR] + (tgt[HPR] - HOME[HPR]) - 0.15*swR
        # 躯干前倾偏置
        if lean:
            tgt[HPL] += lean
            tgt[HPR] += lean
        # 平衡(躯干俯仰闭环)
        if bal_kp:
            q = env.data.qpos[3:7]; w, x, y, z = q
            R00 = 1 - 2*(y*y + z*z); R10 = 2*(x*y + w*z)
            pitch = np.arctan2(-R10, R00)
            tgt[HPL] += bal_kp * pitch
            tgt[HPR] += bal_kp * pitch
        return tgt
    return ctrl


def score(ctrl, secs=3.0):
    env = StandingEnv(control_dt=0.02)
    rec, m = env.run_gait_record(ctrl, seconds=secs)
    # 非直立惩罚大
    pan = 3.0 * (1 - m["upright_frac"])
    xf = m["final_x"]
    return (xf - pan), m


def score_steps(ctrl, secs=3.0):
    """更严格的步态度量:除前进外,惩罚双足同时离地的‘跳’成分,
    鼓励真正的单支撑交替迈步。"""
    env = StandingEnv(control_dt=0.02)
    n = int(secs / env.control_dt)
    env.reset("STAND")
    hop = flight = single = 0
    dt = 0.02
    for i in range(n):
        obs = env.observe()
        act = ctrl(env, obs, i * dt)
        env.step(act if act is not None else None)
        c = env.get_contacts()
        on = int(c["left_on"]) + int(c["right_on"])
        if on == 0:
            flight += 1      # 双离地=不可控跳
        elif on == 1:
            single += 1      # 单足 = 阶段分明,健康
        # else ok (双足支撑不惩罚)
    tot = max(1, n)
    xf = env.data.qpos[0]
    up = float(env.is_upright())
    m = {"final_x": xf, "final_upright": up,
         "flight_frac": flight / tot, "single_frac": single / tot,
         "z": env.data.qpos[2]}
    metric = xf - 2.0 * m["flight_frac"] - (3.0 if not up else 0.0)
    return metric, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--best", type=int, default=1)
    ap.add_argument("--secs", type=float, default=3.0)
    ap.add_argument("--no-scan", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--amp", type=float)
    ap.add_argument("--freq", type=float)
    ap.add_argument("--lift", type=float)
    ap.add_argument("--bal", type=float)
    a = ap.parse_args()

    if a.no_scan:
        cfg = dict(amp_hp=a.amp or 0.10, freq=a.freq or 1.5,
                   lift=a.lift or 0.06, bal_kp=a.bal or 0.0)
        s, m = score(build_controller(**cfg), a.secs)
        print("单点:", cfg, "score=%.3f"%s, m)
        return

    best = []
    # 粗->细 参数网格
    grid = dict(
        amp_hp=[0.05, 0.10, 0.16],
        freq=[0.9, 1.3, 1.8],
        lift=[0.0, 0.06, 0.12],
        prop=[0.0, 0.08, 0.15],
        lean=[0.0, 0.05],
        bal_kp=[0.1, 0.3],
    )
    keys = list(grid)
    cand_keys = list(itertools.product(*(grid.values())))
    scorer = score_steps if a.strict else score
    print(f"候选参数数: {len(cand_keys)} 模式={'strict(惩罚双离地)' if a.strict else '简单'}")
    t0 = time.time()
    for comb in cand_keys:
        cfg = dict(zip(keys, comb))
        sc, m = scorer(build_controller(**cfg), a.secs)
        best.append((sc, cfg, m))
    best.sort(key=lambda x: -x[0])
    dt = time.time() - t0
    print(f"扫描 {len(best)} 组耗时 {dt:.1f}s")
    for sc, cfg, m in best[:a.best]:
        print("top: score=%.3f" % sc, cfg)
        print("     ", {k: (round(v, 3) if isinstance(v, float) else v)
                         for k, v in m.items()})


if __name__ == "__main__":
    main()
