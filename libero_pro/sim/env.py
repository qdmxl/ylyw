#!/usr/bin/env python3
"""
轻量平面抓取 MuJoCo 环境（本机阶段一）

不依赖 robosuite。用程序化 XML 建一个桌面 + 6DOF 浮动末端 + 目标物体，
末端受 PD 控制跟随 YLYW 给出的笛卡尔速度指令。

注意：这是"推理层验证"用的简化载体，不是 LIBERO 的复刻。
目的是在无 GPU / 无 robosuite 的条件下，量化 YLYW 在扰动下的行为。
"""

import os
import numpy as np

# 阶段一为纯物理仿真（无渲染），用 "disable" 跳过 GL 后端初始化。
# 若后续要渲染图像（阶段二视觉特征），改为 "osmesa"/"egl" 并装好 GL 栈。
os.environ.setdefault("MUJOCO_GL", "disable")

import mujoco  # noqa: E402


SCENE_TMPL = """
<mujoco model="ylyw_libero_pro_lite">
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1"/>
    <geom name="table" type="plane" size="0.5 0.5 0.01" rgba="0.5 0.5 0.6 1"/>
    <!-- 6DOF 浮动末端（笛卡尔受控） -->
    <body name="ee" pos="{ee_x} {ee_y} {ee_z}">
      <geom name="ee_geom" type="sphere" size="0.015" rgba="0.2 0.8 0.2 1"/>
      <freejoint name="ee_free"/>
    </body>
    <!-- 目标物体 -->
    <body name="object" pos="{obj_x} {obj_y} {obj_z}">
      <geom name="obj_geom" type="{obj_geom}" size="{obj_size}" rgba="0.9 0.3 0.3 1"
            mass="{obj_mass}"/>
      <freejoint name="obj_free"/>
    </body>
    <!-- 目标容器（放置点） -->
    <body name="target" pos="{tgt_x} {tgt_y} 0.01">
      <geom name="tgt_geom" type="cylinder" size="0.04 0.005" rgba="0.3 0.4 0.9 0.6"
            contype="0" conaffinity="0"/>
    </body>
  </worldbody>
</mujoco>
"""

OBJ_GEOM = {
    "sphere": "sphere", "box": "box", "cylinder": "cylinder", "rod": "capsule",
}


class LiteGraspEnv:
    """平面抓取环境：末端移动到物体 → 抓取 → 移到目标点。"""

    def __init__(self, obj: dict, target_pos=None, ee_start=(0.0, 0.0, 0.15)):
        self.obj = obj
        self.target_pos = np.array([0.3, 0.0, 0.02] if target_pos is None else target_pos,
                                   dtype=float)
        half = obj["size"] * 0.5 if obj["shape"] == "box" else obj["size"]
        xml = SCENE_TMPL.format(
            ee_x=ee_start[0], ee_y=ee_start[1], ee_z=ee_start[2],
            obj_x=obj["pos"][0], obj_y=obj["pos"][1], obj_z=obj["pos"][2],
            obj_geom=OBJ_GEOM.get(obj["shape"], "box"),
            obj_size=half, obj_mass=obj.get("mass", 0.03),
            tgt_x=self.target_pos[0], tgt_y=self.target_pos[1],
        )
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.ee_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "ee")
        self.obj_body = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "object")
        self.grasped = False
        self._grasp_offset = np.zeros(3)

    def try_grasp(self, tol: float = 0.035) -> bool:
        """当末端靠近物体时建立“抓取”约束（简化：记相对偏移，后续强制跟随）。
        不依赖真实摩擦/接触，聚焦推理层验证。"""
        if self.grasped:
            return True
        ee = self.get_ee_pos()
        op = self.get_obj_pos()
        if float(np.linalg.norm(ee - op)) < tol:
            self.grasped = True
            self._grasp_offset = op - ee
            return True
        return False

    def _follow_grasp(self):
        """若已抓取，把物体位姿锁定到末端（保留抓取时的相对偏移）。"""
        if not self.grasped:
            return
        ee = self.get_ee_pos()
        target = ee + self._grasp_offset
        qadr = self.model.body_jntadr[self.obj_body]  # freejoint qpos 起始
        jadr = self.model.jnt_qposadr[self.model.body_jntadr[self.obj_body]]
        self.data.qpos[jadr:jadr + 3] = target
        self.data.qvel[jadr:jadr + 6] = 0.0

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)

    def get_ee_pos(self):
        return self.data.xpos[self.ee_body].copy()

    def get_obj_pos(self):
        return self.data.xpos[self.obj_body].copy()

    def apply_ee_velocity(self, delta_pos, max_vel: float = 2.0):
        """把末端推向 delta_pos：delta_pos 是期望的“本步位移”，
        换算为世界系线速度写入 freejoint 的 qvel。"""
        dt = self.model.opt.timestep
        vel = np.asarray(delta_pos, dtype=float) / dt
        n = float(np.linalg.norm(vel))
        if n > max_vel:
            vel = vel / n * max_vel
        qadr = self.model.body_dofadr[self.ee_body]
        self.data.qvel[qadr:qadr + 3] = vel
        self.data.qvel[qadr + 3:qadr + 6] *= 0.5  # 角速度阻尼

    def step(self, n_sub: int = 1):
        """推进仿真。n_sub 为子步数（提高控制频率等效性）。"""
        for _ in range(n_sub):
            self._follow_grasp()
            mujoco.mj_step(self.model, self.data)


if __name__ == "__main__":
    env = LiteGraspEnv({"pos": [0.3, 0.1, 0.05], "size": 0.05, "shape": "sphere", "mass": 0.03})
    env.reset()
    print("ee:", env.get_ee_pos(), "obj:", env.get_obj_pos())
    for _ in range(50):
        env.apply_ee_velocity(np.array([0.001, 0.001, 0.0]))
        env.step()
    print("after: ee:", env.get_ee_pos())
