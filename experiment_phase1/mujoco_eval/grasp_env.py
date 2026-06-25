#!/usr/bin/env python3
"""
MuJoCo 抓取仿真环境 v3
核心思想：力控夹爪 (force-controlled gripper)

力控夹爪用 motor actuator 而非 position actuator——
施加固定力矩来闭合而非强推到目标位置，
这样接触物体后力是有限的，仿真稳定。

评估指标（纯物理，不依赖策略标签）：
  - grasp_success:  提升后物体是否跟随
  - shake_success:  晃动后物体不掉
  - peak_force:     抓取峰值力
  - actual_lift:    实际提升高度
"""

import os
import math
import numpy as np

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')
os.environ.setdefault('EGL_PLATFORM', 'x11')
os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')

try:
    import mujoco
    from mujoco import viewer
    HAS_MUJOCO = True
except ImportError:
    HAS_MUJOCO = False


def _obj_geom_xml(obj_type, obj_size, obj_mass, obj_friction, obj_rgba):
    if obj_type == 'sphere':
        obj_z = 0.73 + obj_size
        return f'<geom name="obj" type="sphere" size="{obj_size}" mass="{obj_mass}" rgba="{obj_rgba}" friction="{obj_friction} 0.005 0.0001" condim="4"/>', obj_z
    elif obj_type == 'cube':
        half = obj_size * 0.7
        obj_z = 0.73 + half
        return f'<geom name="obj" type="box" size="{half} {half} {half}" mass="{obj_mass}" rgba="{obj_rgba}" friction="{obj_friction} 0.005 0.0001" condim="4"/>', obj_z
    elif obj_type == 'cylinder':
        h = obj_size * 2
        obj_z = 0.73 + h
        return f'<geom name="obj" type="cylinder" size="{obj_size} {h}" mass="{obj_mass}" rgba="{obj_rgba}" friction="{obj_friction} 0.005 0.0001" condim="4"/>', obj_z
    else:
        obj_z = 0.73 + obj_size
        return f'<geom name="obj" type="sphere" size="{obj_size}" mass="{obj_mass}" rgba="{obj_rgba}" friction="{obj_friction} 0.005 0.0001" condim="4"/>', obj_z


def _make_scene_xml(obj_type='sphere', obj_size=0.04, obj_mass=0.1,
                    obj_friction=0.5, obj_rgba='0.8 0.5 0.2 1'):
    """力控夹爪场景: 桌面 + 物体 + Z升降 + 力控铰链手指"""
    obj_geom, obj_z = _obj_geom_xml(obj_type, obj_size, obj_mass,
                                     obj_friction, obj_rgba)
    return f'''<?xml version="1.0"?>
<mujoco>
  <option timestep="0.002" gravity="0 0 -9.81">
    <flag contact="enable"/>
  </option>
  <asset>
    <material name="desk" rgba="0.4 0.35 0.3 1"/>
    <material name="jaw" rgba="0.5 0.5 0.55 1"/>
  </asset>
  <worldbody>
    <light pos="2 2 3" dir="-1 -1 -2" diffuse="0.8 0.8 0.8"/>
    <light pos="-2 2 2" dir="1 -1 -1" diffuse="0.3 0.3 0.3"/>
    <geom name="table" type="box" size="0.4 0.4 0.02" pos="0 0 0.72" material="desk"/>
    <geom name="floor" type="plane" size="2 2 0.01" pos="0 0 0"/>

    <body name="target_object" pos="0.05 0.0 {obj_z}">
      <freejoint name="obj_fj"/>
      {obj_geom}
    </body>

    <!-- Z 升降导轨 -->
    <body name="elevator" pos="0 0 1.10">
      <joint name="elev_z" type="slide" axis="0 0 1" range="-0.45 0.10"/>
      <geom name="elev_body" type="box" size="0.02 0.02 0.02" material="jaw"/>

      <!-- 左手指: slide沿Y, 初始宽开 -->
      <body name="finger_left" pos="0 0.06 -0.06">
        <joint name="fl_j" type="slide" axis="0 -1 0" range="-0.10 0.10"
               damping="1.0" armature="0.001"/>
        <geom name="fl_geom" type="box" size="0.005 0.008 0.055" material="jaw"/>
      </body>

      <!-- 右手指: slide沿Y -->
      <body name="finger_right" pos="0 -0.06 -0.06">
        <joint name="fr_j" type="slide" axis="0 1 0" range="-0.10 0.10"
               damping="1.0" armature="0.001"/>
        <geom name="fr_geom" type="box" size="0.005 0.008 0.055" material="jaw"/>
      </body>
    </body>
  </worldbody>

  <actuator>
    <position name="ez_act" joint="elev_z" kp="500" kv="60"/>
    <motor    name="fl_motor" joint="fl_j" gear="1"/>
    <motor    name="fr_motor" joint="fr_j" gear="1"/>
  </actuator>
</mujoco>'''


class GraspSimEnv:
    """MuJoCo 力控夹爪抓取仿真"""

    def __init__(self, render=False):
        if not HAS_MUJOCO:
            raise RuntimeError("MuJoCo 未安装")
        self.render = render
        self.model = None
        self.data = None
        self.viewer = None

    def _load_scene(self, obj_type='sphere', obj_size=0.04, obj_mass=0.1,
                    obj_friction=0.5, obj_rgba='0.8 0.5 0.2 1'):
        xml = _make_scene_xml(obj_type=obj_type, obj_size=obj_size,
                              obj_mass=obj_mass, obj_friction=obj_friction,
                              obj_rgba=obj_rgba)
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        if self.render:
            self.viewer = viewer.launch_passive(self.model, self.data)

    def _obj_z(self):
        bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'target_object')
        return self.data.xpos[bid][2]

    def run_trial(self, grasp_force=0.5, approach_speed='medium',
                  obj_type='sphere', obj_size=0.04, obj_mass=0.1,
                  obj_friction=0.5, obj_rgba=None, max_trials=3) -> dict:
        """
        夹爪下降→力控闭合→提升→晃动→判定

        grasp_force [0,1] 映射为手指电机的力矩,
        接触物体后力矩用于维持夹持,不产生爆炸力。
        """
        if obj_rgba is None:
            obj_rgba = '0.8 0.5 0.2 1'

        # grasp_force → motor force
        # slide joint: 正力=向物体方向(Y=0)推
        force_close = 2.0 + 6.0 * grasp_force   # [2.6, 8.0] N
        force_open = -2.0  # 张开

        sf = {'slow': 0.4, 'medium': 0.65, 'fast': 1.0}.get(approach_speed, 0.65)
        table_z = 0.74

        self._load_scene(obj_type=obj_type, obj_size=obj_size,
                         obj_mass=obj_mass, obj_friction=obj_friction,
                         obj_rgba=obj_rgba)
        m = self.model; d = self.data
        ez = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, 'ez_act')
        fl_m = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, 'fl_motor')
        fr_m = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, 'fr_motor')

        all_results = []

        for trial in range(max_trials):
            mujoco.mj_resetData(m, d)

            # 初始: 高位+手指张开
            d.ctrl[ez] = 0.05
            d.ctrl[fl_m] = force_open
            d.ctrl[fr_m] = force_open
            for _ in range(40):
                mujoco.mj_step(m, d)

            # 下降
            d.ctrl[ez] = -0.33
            for _ in range(int(160*sf)):
                mujoco.mj_step(m, d)

            # 闭合(施力夹紧)
            d.ctrl[fl_m] = force_close
            d.ctrl[fr_m] = force_close
            for _ in range(int(250*sf)):
                mujoco.mj_step(m, d)

            z0 = self._obj_z()
            peak_z = z0

            # 提升
            d.ctrl[ez] = 0.10
            for _ in range(int(300*sf)):
                mujoco.mj_step(m, d)
                peak_z = max(peak_z, self._obj_z())

            lift = peak_z - z0
            grasped = lift > 0.015

            # 晃动
            shook = False
            if grasped:
                for i in range(200):
                    t = i * m.opt.timestep
                    d.ctrl[ez] = 0.07 + 0.015 * math.sin(t * 14)
                    d.ctrl[fl_m] = force_close + 0.3 * math.sin(t * 20)
                    d.ctrl[fr_m] = force_close + 0.3 * math.sin(t * 20 + 0.3)
                    mujoco.mj_step(m, d)
                shook = self._obj_z() > (table_z + 0.04)

            success = grasped and shook

            all_results.append({
                'success': success, 'grasped': grasped, 'shake_survived': shook,
                'actual_lift_m': round(lift, 4),
                'peak_z': round(peak_z, 4),
                'z_before_lift': round(z0, 4),
                'trial': trial + 1,
            })
            if success:
                break

        if self.viewer:
            self.viewer.close(); self.viewer = None

        best = max(all_results, key=lambda r: (r['success'], r['actual_lift_m']))
        best['total_trials'] = len(all_results)
        best['all_trials'] = all_results
        return best

    def close(self):
        if self.viewer:
            self.viewer.close(); self.viewer = None


if __name__ == '__main__':
    env = GraspSimEnv(render=False)
    for f in [0.9, 0.6, 0.3]:
        r = env.run_trial(grasp_force=f, obj_type='sphere', obj_size=0.04, obj_mass=0.05)
        s = '✓' if r['success'] else '✗'
        print(f"{s} force={f:.1f} lift={r['actual_lift_m']*100:.1f}cm peakZ={r['peak_z']:.3f}")
    env.close()
    print('✓ OK')
