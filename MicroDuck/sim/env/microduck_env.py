"""MicroDuck MuJoCo CPU 仿真环境核心类(ylyw 算法验证基座)。

设计目标
--------
在 **CPU、无 GPU** 环境下,提供一只可在 MuJoCo 3 中稳定站立/行走的双足鸭形机器人
(MicroDuck),让 ylyw 的上层算法(如 64 卦步态相位映射、关节目标角序列、时序决策)
能以“给定 14 维关节目标角 → 读取物理反馈”的标准 RL/控制接口工作。

为什么需要“控制友好执行器”
--------------------------
官方 microduck_rl 用 MuJoCo Warp(GPU)+ BAM 电压控制执行器训练,仓库自带的
robot_*.xml 里的 XML 位置执行器(kp≈0.55, forcerange±0.96)是 EOL 的弱 PD 残留,
不足以让鸭子站住。我们不改动几何/质量/关节/自由度(仍是同一物理本体),
仅重写执行器增益到可跟踪关节目标的量级,得到可平衡的 CPU 版本。
这用于 **验证 ylyw 控制算法结构与步态逻辑**;若要真机 sim2real 再引官方 BAM。

关节顺序(与官方 microduck_rl 动作空间一致, 14 维)
--------------------------------------------------
 0 left_hip_yaw   1 left_hip_roll  2 left_hip_pitch  3 left_knee  4 left_ankle
 5 neck_pitch     6 head_pitch     7 head_yaw        8 head_roll
 9 right_hip_yaw 10 right_hip_roll 11 right_hip_pitch 12 right_knee 13 right_ankle
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import mujoco

try:
    from lxml import etree
    _HAS_LXML = True
except Exception:  # pragma: no cover
    _HAS_LXML = False

# ---------------------------------------------------------------------------
# 路径约定
# ---------------------------------------------------------------------------
_ENV_DIR = os.path.dirname(os.path.abspath(__file__))
_SIM_DIR = os.path.dirname(_ENV_DIR)                      # .../sim
_MODEL_DIR = os.path.join(_SIM_DIR, "models", "microduck")
_RAW_ROBOT_XML = os.path.join(_MODEL_DIR, "robot_walk.xml")
_RAW_SCENE_XML = os.path.join(_MODEL_DIR, "scene_walk.xml")
# 生成的控制友好模型(相对 scene)：由 ensure_control_model() 创建
_CTRL_SCENE_XML = os.path.join(_MODEL_DIR, "_ylyw_control_scene.xml")

# 推荐的平衡执行器参数
_CTRL_KP = 60.0      # 位置增益(可跟踪 STEP 目标,且身体能站住)
_CTRL_KV = 4.0       # 速度阻尼增益(注意:MuJoCo position 的 kv,需去掉 dampratio 冲突)
_CTRL_FR = 3.0       # forcerange(牛顿·米 上限)
_CTRL_DAMPING = 0.1  # 关节被动阻尼
_CTRL_FRICTION = 0.02
_CTRL_ARMATURE = 0.002

# 官方姿态标签(HOME_FRAME / scene keyframe STAND)
_HOME = {
    "left_hip_yaw": 0.0, "left_hip_roll": -0.0873, "left_hip_pitch": -0.4579,
    "left_knee": -0.0049, "left_ankle": 0.4530,
    "neck_pitch": 0.3491, "head_pitch": 0.3491, "head_yaw": 0.0, "head_roll": 0.0,
    "right_hip_yaw": 0.0, "right_hip_roll": 0.0873, "right_hip_pitch": 0.4579,
    "right_knee": 0.0049, "right_ankle": -0.4530,
}
_HOME_TRUNK_Z = 0.12

SERVO_JOINTS = [  # 与 XML keyframe/home 一致的 14 关节顺序
    "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee", "left_ankle",
    "neck_pitch", "head_pitch", "head_yaw", "head_roll",
    "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee", "right_ankle",
]


# ---------------------------------------------------------------------------
# XML 复制工具
# ---------------------------------------------------------------------------
def _rewrite_actuators(robot_path: str, out_path: str,
                       kp: float, kv: float, fr: float,
                       damping: float, friction: float, armature: float) -> str:
    """把 robot XML 里 chosen_actuator 默认类重写成可平衡的位置执行器。"""
    if not _HAS_LXML:
        raise RuntimeError("需要 lxml: pip install lxml 才能生成控制友好模型")
    tree = etree.parse(robot_path)
    root = tree.getroot()
    patched = 0
    for el in root.iter():
        if el.tag != "default":
            continue
        for sub in el:
            if isinstance(sub.tag, str) and sub.tag == "default" and sub.get("class") == "chosen_actuator":
                j = sub.find("joint")
                if j is not None:
                    j.set("damping", str(damping))
                    j.set("frictionloss", str(friction))
                    j.set("armature", str(armature))
                p = sub.find("position")
                if p is not None:
                    ignored = [a for a in ("kv", "dampratio") if a in p.attrib]
                    for a in ignored:
                        del p.attrib[a]
                    p.set("kp", str(kp))
                    p.set("kv", str(kv))
                    p.set("forcerange", "-%.4f %.4f" % (fr, fr))
                    p.set("ctrlrange", "-10 10")
                patched += 1
    if patched == 0:
        raise RuntimeError("未在 XML 中找到 chosen_actuator 默认类,无法生成控制友好模型")
    tree.write(out_path)
    return out_path


def ensure_control_model(force: bool = False,
                         kp: float = _CTRL_KP, kv: float = _CTRL_KV,
                         fr: float = _CTRL_FR) -> str:
    """返回控制友好 scene XML;必要时把默认执行器重写并生成。

    生成两个文件存于 models/microduck:
      _ylyw_control_robot.xml  (重写执行器后的 robot)
      _ylyw_control_scene.xml  (include 上述 robot 的 scene wrapper)
    """
    if os.path.exists(_CTRL_SCENE_XML) and not force:
        return _CTRL_SCENE_XML
    robot_out = os.path.join(_MODEL_DIR, "_ylyw_control_robot.xml")
    scene_out = _CTRL_SCENE_XML
    _rewrite_actuators(_RAW_ROBOT_XML, robot_out,
                       kp=kp, kv=kv, fr=fr,
                       damping=_CTRL_DAMPING, friction=_CTRL_FRICTION,
                       armature=_CTRL_ARMATURE)
    # scene: 复制 scene_walk.xml 但 include 指向 _ylyw_control_robot.xml
    if not _HAS_LXML:
        # 退路:直接读文本替换 include 目标
        with open(_RAW_SCENE_XML, "r", encoding="utf-8") as f:
            s = f.read().replace('robot_walk.xml', '_ylyw_control_robot.xml')
    else:
        st = etree.parse(_RAW_SCENE_XML)
        r = st.getroot()
        for inc in r.iter("include"):
            inc.set("file", "_ylyw_control_robot.xml")
        import io
        buf = io.BytesIO()
        st.write(buf, encoding="utf-8", xml_declaration=True)
        s = buf.getvalue().decode("utf-8")
    os.makedirs(os.path.dirname(scene_out), exist_ok=True)
    with open(scene_out, "w", encoding="utf-8") as f:
        f.write(s)
    return scene_out


# ---------------------------------------------------------------------------
# 环境类
# ---------------------------------------------------------------------------
@dataclass
class EnvState:
    """紧凑的物理状态快照,供 ylyw 上层解析。"""
    # 浮动基座:位置/姿态
    base_pos: np.ndarray      # (3,) 地面系位置
    base_quat: np.ndarray     # (4,)
    base_lin_vel: np.ndarray  # (3,)
    base_ang_vel: np.ndarray  # (3,)
    # 关节
    joint_qpos: np.ndarray    # (14,) 当前关节角(弧度)
    joint_qvel: np.ndarray    # (14,) 关节角速度
    joint_target: np.ndarray  # (14,) 当前控制目标
    # 触地量(每足接触点法向力总和,归一化指示是否着地)
    foot_force_l: float
    foot_force_r: float
    # 汇总向量(轻量观测):[3pos,4quat,3lin,3ang,14qpos,14qvel] = 41
    raw: np.ndarray


class MicroDuckEnv:
    """在给定 MuJoCo 模型上做 reset/step/observe 的最小包装。

    参数:
      xml_path: MuJoCo 模型完整 xml(应含 floor + robot + keyframes)
      dt:       每步物理步长(秒)。控制频率由 targ_dt 决定。
      targ_dt:  上层调用一次 step() 对应的“控制周期”。内部做多次 mj_step。
      control_mode: 'position'(默认, ctrl 为关节目标角) 或 'none'(不驱动)
    """

    def __init__(self, xml_path: Optional[str] = None, dt: float = 0.002,
                 control_dt: float = 0.02):
        self._xml = xml_path or ensure_control_model()
        self.model = mujoco.MjModel.from_xml_path(self._xml)
        self.data = mujoco.MjData(self.model)
        self.dt = self.model.opt.timestep          # 物理 dt(读取模型)
        self.control_dt = float(control_dt)
        self._substeps = max(1, int(round(self.control_dt / self.dt)))

        # 关节索引映射 (名称 -> (qpos_adr, qvel_adr))
        self._jmap: dict = {}
        joint_names = [
            mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, j)
            for j in range(self.model.njnt)
        ]
        self._jpos_adr = {n: self.model.jnt_qposadr[i]
                          for i, n in enumerate(joint_names)}
        self._jvel_adr = {n: self.model.jnt_dofadr[i]
                          for i, n in enumerate(joint_names)}
        self.active_joints = SERVO_JOINTS
        self.free_adr = 0  # trunk_base_freejoint 的 qpos 起始(第0个关节是free)

        # 建立 SERVO_JOINTS -> actuator id。MuJoCo 中 actuator.jntid / trnid[0]
        # 给出其驱动关节的 joint id,据此把“关节名”映射到“actuator 索引”。
        self._servo_act_idx: dict = {}
        self._act_names = []
        for a in range(self.model.nu):
            jid = self.model.actuator(a).trnid[0]
            if jid == -1:
                continue
            jnm = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, jid)
            self._act_names.append(jnm)
        for cn, nm in enumerate(self._act_names):
            if nm in SERVO_JOINTS:
                self._servo_act_idx[nm] = cn
        self.action_size = len(SERVO_JOINTS)  # = 14

        # foot geoms
        self._foot_l = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "left_foot_collision")
        self._foot_r = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "right_foot_collision")

        self._default_pos = np.array([_HOME[jn] for jn in SERVO_JOINTS])

    # ---------------- 基础操作 ----------------
    def reset(self, pose: str = "STAND", randomize: bool = False):
        """复位到官方姿态。
          pose: 'STAND'(HOME) / 'INIT' / 'SIT' / 'FOLD' (scene keyframes)
        """
        mujoco.mj_resetData(self.model, self.data)
        kf_adr = None
        for k in range(self.model.nkey):
            if mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_KEY, k) == pose:
                kf_adr = k
                break
        if kf_adr is not None:
            mujoco.mj_resetDataKeyframe(self.model, self.data, kf_adr)
        else:  # 直接写 HOME 到 servo qpos
            self.set_joint_pos(self._default_pos, velocities=np.zeros(14))
            self.data.qpos[2] = _HOME_TRUNK_Z      # free pos z
            self.data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]  # free quat 单位四元数
        mujoco.mj_forward(self.model, self.data)
        # 让执行器目标=当前关节,避免首步跳变
        self.set_target(self.get_joint_pos())
        return self.observe()

    def set_joint_pos(self, angles: np.ndarray, velocities: Optional[np.ndarray]):
        """直接把 14 关节 qpos 写入(用于初始化)。angles 长度须为 14。"""
        assert len(angles) == 14
        for jn, val in zip(SERVO_JOINTS, angles):
            self.data.qpos[self._jpos_adr[jn]] = val
            if velocities is not None:
                self.data.qvel[self._jvel_adr[jn]] = velocities  # placeholder
        if velocities is not None:
            for jn, v in zip(SERVO_JOINTS, velocities):
                self.data.qvel[self._jvel_adr[jn]] = v

    def set_target(self, target: np.ndarray):
        """设置执行器目标(关节角,弧度),长度 14,顺序同 SERVO_JOINTS。"""
        assert target.shape == (14,), target.shape
        # ctrl 顺序是 nu = actuator 顺序 = SERVO_JOINTS 顺序(mj_model actuator block)
        # 但我们不能假设 XML actuator 顺序= SERVO;以名对齐更稳
        for jn, val in zip(SERVO_JOINTS, target):
            a = self._servo_act_idx.get(jn)
            if a is not None:
                self.data.ctrl[a] = float(val)

    def step(self, acts: Optional[np.ndarray] = None):
        """推进一个控制周期;acts 若给出则作为关节目标角(14,)。返回观测。"""
        if acts is not None:
            self.set_target(np.asarray(acts, dtype=float))
        for _ in range(self._substeps):
            mujoco.mj_step(self.model, self.data)
        return self.observe()

    # ---------------- 状态读取 ----------------
    def get_joint_pos(self) -> np.ndarray:
        return np.array([self.data.qpos[self._jpos_adr[jn]] for jn in SERVO_JOINTS])

    def get_joint_vel(self) -> np.ndarray:
        return np.array([self.data.qvel[self._jvel_adr[jn]] for jn in SERVO_JOINTS])

    def get_contacts(self):
        """两足是否有着地接触。返回 {"left_on":bool,"right_on":bool}。
        通过 ncon 时接触是否涉及对应 sole geom 判断(轻量、无需装配约束力)。
        """
        left_on = right_on = False
        for c in range(self.data.ncon):
            g1 = self.data.contact[c].geom1
            g2 = self.data.contact[c].geom2
            if g1 == self._foot_l or g2 == self._foot_l:
                left_on = True
            if g1 == self._foot_r or g2 == self._foot_r:
                right_on = True
        return {"left": 1.0 if left_on else 0.0,
                "right": 1.0 if right_on else 0.0,
                "left_on": left_on, "right_on": right_on}

    def observe(self) -> np.ndarray:
        """紧凑观测向量,顺序:
           [base_pos(3), base_quat(4), lin_vel(3), ang_vel(3),
            joint_qpos(14), joint_qvel(14), 足触地(2)] -> 43 维
        """
        d = self.data
        pos = d.qpos[0:3].copy()
        quat = d.qpos[3:7].copy()
        lin = d.qvel[0:3].copy()
        ang = d.qvel[3:6].copy()
        jp = self.get_joint_pos()
        jv = self.get_joint_vel()
        cont = self.get_contacts()
        touch = np.array([1.0 if cont["left_on"] else 0.0,
                          1.0 if cont["right_on"] else 0.0], dtype=float)
        return np.concatenate([pos, quat, lin, ang, jp, jv, touch])

    # ------------- 便利度量 -------------
    def is_upright(self, tilt_thresh_deg: float = 35.0) -> bool:
        # trunk 是否大致竖直:R[2,2]
        q = self.data.qpos[3:7]
        w, x, y, z = q
        R22 = 1 - 2 * (x * x + y * y)
        return R22 > np.cos(np.deg2rad(tilt_thresh_deg))

    def trunk_height(self) -> float:
        return float(self.data.qpos[2])

    def horizontal_drift(self) -> float:
        return float(np.hypot(self.data.qpos[0], self.data.qpos[1]))

    @property
    def base_pose(self):
        return {"pos": self.data.qpos[0:3].copy(), "quat": self.data.qpos[3:7].copy()}


    # ------------- 外力扰动(抗扰/恢复验证用) -------------
    def apply_push(self, impulse=(0.5, 0.0, 0.0)):
        """给浮动躯干一个瞬时线速度冲量(单位 m/s),用于抗扰/恢复实验。"""
        for k in range(3):
            self.data.qvel[k] += impulse[k]
        mujoco.mj_forward(self.model, self.data)
        return self.observe()

    def run_gait_record(self, controller, seconds: float, record_hz: float = 50.0):
        """通用步态/控制回放 harness。

        每个控制周期调 controller(self, obs(43,), t) -> target(14,) 或 None。
        返回 (records, summary):
          records[i] = {t,x,y,z,pitch_deg,upright,foot_l,foot_r,velx}
          summary     = 竖直保持率、终态 x/z、是否仍竖直
        """
        self.reset("STAND")
        dt = self.control_dt
        records = []
        step_call = max(1, int(round(1.0 / record_hz / dt)))
        for i in range(int(seconds / dt)):
            obs = self.observe()
            act = controller(self, obs, i * dt) if controller else None
            if act is not None:
                self.step(np.asarray(act, dtype=float))
            else:
                self.step()
            if i % step_call == 0:
                q = self.data.qpos[3:7]
                w, x, y, z = q
                c = 1 - 2 * (x * x + y * y)
                tilt = float(np.degrees(np.arccos(np.clip(min(max(c, -1.0), 1.0), -1, 1))))
                cont = self.get_contacts()
                records.append(dict(
                    t=i * dt, x=float(self.data.qpos[0]), y=float(self.data.qpos[1]),
                    z=float(self.data.qpos[2]), pitch_deg=tilt,
                    upright=bool(tilt < 35),
                    foot_l=bool(cont["left_on"]), foot_r=bool(cont["right_on"]),
                    velx=float(self.data.qvel[0])))
        up = sum(1 for r in records if r["upright"])
        summary = {
            "seconds": int(seconds),
            "upright_frac": round(up / len(records), 3) if records else 0.0,
            "final_x": float(self.data.qpos[0]),
            "final_z": float(self.data.qpos[2]),
            "final_upright": bool(self.is_upright()),
        }
        return records, summary


class StandingEnv(MicroDuckEnv):
    """开箱即用的“站立保持”验证:reset 到 STAND 后空转,检测是否站稳。"""

    def run_hold(self, seconds: float) -> dict:
        self.reset("STAND")
        z0 = self.trunk_height()
        steps = int(seconds / self.control_dt)
        max_tilt = 0.0
        for _ in range(steps):
            self.step()
            if self.is_upright():
                pass
            # 角度度量
            q = self.data.qpos[3:7]
            c = 1 - 2 * (q[1] ** 2 + q[2] ** 2)
            tilt = np.degrees(np.arccos(np.clip(c, -1, 1)))
            max_tilt = max(max_tilt, tilt)
        return {
            "seconds": seconds,
            "trunk0": float(z0),
            "trunk_final": self.trunk_height(),
            "drift": self.horizontal_drift(),
            "max_tilt_deg": float(max_tilt),
            "upright_final": self.is_upright(),
            "stable": 0.05 < self.trunk_height() < 0.30
                      and self.horizontal_drift() < 2.0
                      and self.is_upright(),
        }
