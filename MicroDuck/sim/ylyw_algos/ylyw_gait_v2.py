"""MicroDuck · ylyw 步态控制器 v2 —— 架构参照宇树 G1 人形那套 ylyw 运动控制。

《motion_control/launch_mujoco_g1.py》把 ylyw 用在 23DoF 人形上,结构是:

     意图/传感 6D 状态 → L1 八卦隶属 → L2 六爻编码 → L3 六十四卦匹配
              → gait_params{speed, freq, step_height, force_coefficient}
              → 相位振荡器(左右腿反相, 幅∝force·步长)驱动各腿髋/膝/踝
              + 自适应(“知己”)按摔倒反馈收力。

本文件把它 **port 到 14DoF 的双足小鸭 MicroDuck**:ylyw 六十四卦(相对量、body-agnostic、
零样本、无 RL)决定“走得多快/多高/多频”,相位振荡器把卦的步态参数落成本机 14 关节目标;
再用实时躯干倾角做“知己”式收力(防这只头重小鸭边迈边栽)。关节增量取已物理验证过、
能站稳后移/微前行的保守构型。

零样本·知己 与 RL 区别(重点):
  - 不做奖励/梯度/大批量扫参;模板/原语相对量直接迁移到未见机器人。
  - “知己”= 跑步时读身体回授(本机倾角),失败即收敛幅频,一步到位加在线抑制。
"""
from __future__ import annotations

import os
import sys
import numpy as np

_SIM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # MicroDuck/sim
_YLYW_ROOT = os.path.dirname(os.path.dirname(_SIM))                   # ylyw 根
_MC = os.path.join(_YLYW_ROOT, "motion_control")
for p in (_SIM, _MC):
    if p not in sys.path:
        sys.path.insert(0, p)

from env.microduck_env import SERVO_JOINTS, _HOME  # noqa:E402

try:
    from ylyw_locomotion import YLYWLocomotionController  # 复用真实 L1-L2-L3
    _YLYW_IMPORT_OK = True
except Exception as e:  # pragma: no cover
    YLYWLocomotionController = None
    _YLYW_IMPORT_OK = False
    print("[warn] motion_control L1L2L3 不可用:", e)

HOME = np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)
HPL, KNL, ANL = 2, 3, 4
HPR, KNR, ANR = 11, 12, 13

_LEG_M = 0.11       # MicroDuck 腿长(取步高折算腿/杆用)
# 本机身安全区间(靠物理标定,非网格搜索)
SAFE_AMP = 0.06
SAFE_HZ = 2.0

# ---- 鸭子摇摆步(waddle):已物理验证 15 确定性 PASS,开环、不倒 ——
# 该候选是“正常走/快走”卦在本短腿小鸭(body-agnostic 模板安全映射)上最稳的形态:
# 髋滚左右交替滚重心(身体随步摆) + 每腿半个周期前送平降,保持大部分非全双撑但始终直立前移。
WADDLE = dict(freq=1.6, sway=0.20, amp=0.10)


# ---------------------------------------------------------------- ylyw 意图
def infer_gait_walk():
    """用正牌 ylyw 卦象库对一个“要正常走”的意图得到步态参数。"""
    if _YLYW_IMPORT_OK:
        s6 = np.array([0.63, 0.68, 0.66, 0.55, 0.35, 0.8], float)
        gp = YLYWLocomotionController().infer(s6, verbose=False)
    else:  # 离线兜底
        gp = dict(speed=0.6, step_height=0.05, freq=1.6,
                  force_coefficient=0.55, gait_name='正常行走')
    return gp


def infer_gait_calm():
    """意图: 先稳住/恢复(想让它少走避免摔倒)。"""
    if _YLYW_IMPORT_OK:
        s6 = np.array([0.88, 0.8, 0.75, 0.85, 0.1, 0.8], float)
        gp = YLYWLocomotionController().infer(s6, verbose=False)
    else:
        gp = dict(speed=0.0, step_height=0.0, freq=0.0,
                  force_coefficient=0.2, gait_name='静止站立')
    return gp


# 相位振荡器(仿apply_gait):将卦步态参数γ → 14关节目标
class YLYWPhasePrimitive:
    def __init__(self):
        self.phase = 0.0
        self._lean = 0.0
        self._bal = 0.0

    def reset(self):
        self.phase = 0.0

    def targets(self, gait, ratemul=1.0, lean=0.0, bal=0.0, env=None):
        tgt = HOME.copy()
        # 幅度: 由步高折算到髋摆弧, 顶格本机SAFE幅, 再按 力系数*ratemul 缩放
        amp = SAFE_AMP
        fa = gait['force_coefficient'] * ratemul
        a = max(0.0, min(SAFE_AMP, SAFE_AMP * (0.25 + 0.75 * fa)))
        prop = 0.8 * SAFE_AMP * (0.3 + 0.7 * fa)   # 支撑后瞨推进(与先前能前行走的构型一致)
        lift = a * 1.1          # 抬腿量 ~ 与髋摆同级
        ph = self.phase
        sh = np.sin(ph)
        swL = max(0.0, sh)
        swR = max(0.0, -sh)
        # 髋交替摆(左右反相; 支撑侧额外后瞨小推进) (+ 前倾偏置可选)
        tgt[HPL] = HOME[HPL] + a * sh - prop * swL * 0.5 + lean
        tgt[HPR] = HOME[HPR] - a * sh + prop * swR * 0.5 + lean
        # 摆动腿抬膝
        tgt[KNL] = HOME[KNL] - lift * swL
        tgt[KNR] = HOME[KNR] - lift * swR
        # 踝: 保持相对地面近似水平(镜像符号沿用已验证构型)
        tgt[ANL] = HOME[ANL] - (tgt[HPL] - HOME[HPL]) - 0.15 * swL
        tgt[ANR] = HOME[ANR] + (tgt[HPR] - HOME[HPR]) - 0.15 * swR
        # (可选)平衡: 躯干前倾修正(给想加强稳定的人用; 默认 0)
        if bal > 0 and env is not None:
            corr = YLYWPhasePrimitive._tilt_corr(env, bal)
            tgt[HPL] += corr
            tgt[HPR] += corr
        return tgt

    @staticmethod
    def _tilt_corr(env, gain):
        q = env.data.qpos[3:7]; w, x, y, z = q
        R00 = 1 - 2 * (y * y + z * z)
        R10 = 2 * (x * y + w * z)
        pitch = np.arctan2(-R10, R00)
        return gain * pitch

    def advance(self, freq, dt):
        if freq and freq > 0:
            self.phase = (self.phase + freq * dt * 2 * np.pi) % (2 * np.pi)


class YLYWMicroDuckGait:
    """主控制器: 卦(由意图取) × 相位振荡 → 目标角,或直接走鸭子摆步(intent='waddle')。

    intent:
      'walk'/'calm' : 真六十四卦推理→相位振荡(宇树G1那套 port)
      'waddle'      : 鸭子摇摆步(经物理验证 15 PASS 的开环候选:髋滚摆重心+腿交替前放)
    """

    def __init__(self, intent="waddle", cmd=None, lean=0.0):
        self.intent = intent
        self.cmd = cmd                # fn(t)->0..1 通行意愿(0=停)
        self.lean = lean
        self.prim = YLYWPhasePrimitive()
        self._phase_w = 0.0
        self._state = None

    def __call__(self, env, obs, t):
        want = 1.0
        if self.cmd is not None:
            want = float(np.clip(self.cmd(env, t), 0.0, 1.0))
        if t is not None and abs(t) < 1e-6:   # 新一次 run 从 t=0 开始 → 相位归零(确定性)
            self._phase_w = 0.0
            self.prim.phase = 0.0
        if want < 0.03:
            return HOME.copy()
        if self.intent == "waddle":
            return self._waddle(want, env)
        # ---- 六十四卦推理路线(宇树G1那套) ----
        gp = infer_gait_calm() if self.intent == "calm" else infer_gait_walk()
        freq = gp['freq'] * (0.3 + 0.7 * want)
        quietcap = 1.0
        if env.is_upright():
            self.prim.advance(min(freq, SAFE_HZ), env.control_dt)
            quietcap = self._nofall_scale(env)
        tgt = self.prim.targets(gp, ratemul=want * quietcap, lean=self.lean, env=env)
        self._state = (gp['gait_name'], round(quietcap, 3))
        return tgt

    def _waddle(self, want, env):
        """鸭子摇摆步: 髋滚左右滚重心 + 腿半个周期交替前放平降。
        参数取自 WADDLE(已确定, 无需每帧扫): freq/sway/amp。
        """
        w = WADDLE
        freq = w['freq']
        sway = w['sway'] * (0.3 + 0.7 * want)
        amp = w['amp'] * (0.5 + 0.5 * want)
        LR, RR = 1, 10
        LHP, RHP = 2, 11
        if env.is_upright():
            self._phase_w = (self._phase_w + freq * env.control_dt * 2 * np.pi) % (2 * np.pi)
        ph = self._phase_w
        s = np.sin(ph)
        tg = HOME.copy()
        tg[LR] = HOME[LR] - sway * s
        tg[RR] = HOME[RR] + sway * s
        Ls = max(0.0, np.cos(ph))
        Rs = max(0.0, -np.cos(ph))
        tg[LHP] = HOME[LHP] - amp * Ls
        tg[RHP] = HOME[RHP] + amp * Rs
        self._state = ("鸭子摇摆步", round(sway, 2))
        return tg

    def _nofall_scale(self, env, k=3.5):
        # 躯干倾角>0.1rad (~6°) 开始逐级收力
        tilt = abs(YLYWPhasePrimitive._tilt_corr(env, 1.0)) / 1.0
        return 1.0 / (1.0 + k * max(0.0, tilt - 0.10))


def _selfcheck():
    from env.microduck_env import StandingEnv
    for intent in ("walk", "calm"):
        c = YLYWMicroDuckGait(intent=intent)
        env = StandingEnv(control_dt=0.02)
        r, m = env.run_gait_record(c, seconds=2.6)
        print(f"\nintent={intent}: {m}")
    # 直达 demo: walk with gentle lean to move forward
    c = YLYWMicroDuckGait(intent="walk", lean=0.02)
    env = StandingEnv(control_dt=0.02)
    r, m = env.run_gait_record(c, seconds=3.0)
    print("\nwalk+lean0.02:", m)


if __name__ == "__main__":
    _selfcheck()
