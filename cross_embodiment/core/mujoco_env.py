#!/usr/bin/env python3
"""
跨本体 MuJoCo 环境基类

管理仿真场景、机器人加载、任务物体、YLYW 推理引擎对接。
所有本体共用一个环境接口，通过 BodyConfig 插件化区分。

用法:
    env = CrossBodyEnv(body_type="shadow_hand_3axis", headless=True)
    obs = env.reset(object_key="sphere")
    done = env.step(ylyw_action)
"""

import os, sys, math, time, json, numpy as np
from typing import Optional, Dict, Any, Tuple

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')

import mujoco

# YLYW 核心路径
YLYW_CORE = os.path.expanduser('~/MXL/科研/ylyw/api_docs/ylyw_core')
sys.path.insert(0, YLYW_CORE)

# 本体和场景路径
CROSS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES_DIR = os.path.join(CROSS_DIR, 'scenes')
BODIES_DIR = os.path.join(CROSS_DIR, 'bodies')
DECODERS_DIR = os.path.join(CROSS_DIR, 'decoders')

# 物体几何参数（与 dexterous_sim 保持一致）
OBJECT_GEOMETRY = {
    'sphere':    {'width': 0.056, 'height': 0.056, 'diameter': 0.056, 'shape': 'sphere', 'mass': 0.03},
    'box':       {'width': 0.050, 'height': 0.050, 'diameter': 0.050, 'shape': 'box', 'mass': 0.03},
    'cylinder':  {'width': 0.050, 'height': 0.060, 'diameter': 0.050, 'shape': 'cylinder', 'mass': 0.03},
    'long_rod':  {'width': 0.016, 'height': 0.090, 'diameter': 0.016, 'shape': 'rod', 'mass': 0.02},
    'mushroom':  {'width': 0.070, 'height': 0.070, 'diameter': 0.070, 'shape': 'mushroom', 'mass': 0.03},
    'dumbbell':  {'width': 0.090, 'height': 0.040, 'diameter': 0.012, 'shape': 'dumbbell', 'mass': 0.04},
    'disc':      {'width': 0.070, 'height': 0.016, 'diameter': 0.070, 'shape': 'disc', 'mass': 0.02},
}

# 物体 MuJoCo geom 类型映射
SHAPE_TO_MJGEOM = {
    'sphere': 'sphere',
    'box': 'box',
    'cylinder': 'cylinder',
    'rod': 'cylinder',
    'mushroom': 'box',
    'dumbbell': 'box',
    'disc': 'cylinder',
}


class CrossBodyEnv:
    """
    跨本体 MuJoCo 环境

    Args:
        body_type: 本体类型标识，如 "shadow_hand_3axis"
        scene_xml: 场景 XML 路径 (None 则自动根据 body_type 查找)
        headless: 是否无头模式
        timestep: 仿真步长
    """

    # 本体→场景XML映射
    BODY_SCENE_MAP = {
        'shadow_hand_3axis': 'hand_scene_3axis.xml',
        'force_gripper_3axis': 'gripper_scene_3axis.xml',
        'arm6_hand': 'arm6_hand_scene.xml',
        'arm6_gripper': 'arm6_gripper_scene.xml',
    }

    def __init__(self, body_type: str = 'shadow_hand_3axis',
                 scene_xml: Optional[str] = None,
                 headless: bool = True,
                 timestep: float = 0.002):

        self.body_type = body_type
        self.headless = headless

        # 加载场景 XML
        if scene_xml is None:
            xml_name = self.BODY_SCENE_MAP.get(body_type)
            if xml_name is None:
                raise ValueError(f"Unknown body_type: {body_type}")
            scene_xml = os.path.join(SCENES_DIR, xml_name)

        self.scene_xml = scene_xml
        self.model = mujoco.MjModel.from_xml_path(scene_xml)

        # 设置时间步长
        self.model.opt.timestep = timestep

        # 创建 data
        self.data = mujoco.MjData(self.model)

        # 关节/执行器名称索引
        self._build_name_map()

        # YLYW 推理引擎（懒加载）
        self._ylyw_engine = None

        # 本体配置和动作解码器
        self.body_config = None
        self.decoder = None

        # 物体位置偏移（用于测试XY对齐）
        self._obj_offset = np.array([0.0, 0.0, 0.0])

        # 状态缓存
        self._state = {}

        print(f"[CrossBodyEnv] initialized: body={body_type}, scene={os.path.basename(scene_xml)}, "
              f"nq={self.model.nq}, nu={self.model.nu}")

    def _build_name_map(self):
        """构建名称→索引映射"""
        self.joint_ids = {}
        self.actuator_ids = {}
        self.body_ids = {}
        self.geom_ids = {}

        for i in range(self.model.njnt):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_JOINT, i)
            if name:
                self.joint_ids[name] = i

        for i in range(self.model.nu):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            if name:
                self.actuator_ids[name] = i

        for i in range(self.model.nbody):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY, i)
            if name:
                self.body_ids[name] = i

        for i in range(self.model.ngeom):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_GEOM, i)
            if name:
                self.geom_ids[name] = i

    def get_joint_qposadr(self, joint_name: str) -> int:
        """获取关节在 qpos 中的起始索引"""
        jid = self.joint_ids.get(joint_name)
        if jid is None:
            raise KeyError(f"Joint '{joint_name}' not found")
        return self.model.jnt_qposadr[jid]

    def set_joint_qpos(self, joint_name: str, value: float):
        """设置关节位置"""
        adr = self.get_joint_qposadr(joint_name)
        self.data.qpos[adr] = value

    def get_joint_qpos(self, joint_name: str) -> float:
        """读取关节位置"""
        adr = self.get_joint_qposadr(joint_name)
        return float(self.data.qpos[adr])

    def set_ctrl(self, actuator_name: str, value: float):
        """设置执行器目标值"""
        aid = self.actuator_ids.get(actuator_name)
        if aid is not None:
            self.data.ctrl[aid] = value

    # ─── 物体管理 ───

    def set_object(self, object_key: str, offset_xy: Tuple[float, float] = (0, 0)):
        """
        设置当前抓取物体（修改几何、大小、质量、颜色）

        Args:
            object_key: 物体类型名
            offset_xy: XY 偏移 (m)，模拟物体不在手掌正下方的场景
        """
        geo = OBJECT_GEOMETRY.get(object_key)
        if geo is None:
            raise ValueError(f"Unknown object: {object_key}")

        self._current_object = object_key
        self._obj_offset = np.array([offset_xy[0], offset_xy[1], 0.0])

        # 修改物体几何形状、大小和质量
        gid = self.geom_ids.get('obj_geom')
        if gid is not None:
            mj_shape = SHAPE_TO_MJGEOM.get(geo['shape'], 'sphere')
            # MuJoCo geom_size 固定3元素, 不同类型前n位有效
            if mj_shape == 'sphere':
                new_size = [geo['diameter']/2, 0.0, 0.0]
            elif mj_shape == 'box':
                new_size = [geo['width']/2, geo['height']/2, geo['diameter']/2]
            elif mj_shape == 'cylinder':
                new_size = [geo['diameter']/2, geo['height']/2, 0.0]
            else:
                new_size = [0.028, 0.028, 0.028]
            self.model.geom_type[gid] = getattr(mujoco.mjtGeom, f'mjGEOM_{mj_shape.upper()}', 6)
            self.model.geom_size[gid] = new_size
            # 修改物体body的质量
            obj_bid = self.body_ids.get('object')
            if obj_bid is not None:
                self.model.body_mass[obj_bid] = geo['mass']

            # 根据物体类型赋予不同颜色
            color_map = {
                'sphere': (0.9, 0.2, 0.2, 1.0),   # 红色
                'box': (0.2, 0.8, 0.2, 1.0),      # 绿色
                'cylinder': (0.2, 0.2, 0.8, 1.0), # 蓝色
                'long_rod': (0.9, 0.6, 0.1, 1.0), # 橙色
                'mushroom': (0.8, 0.4, 0.8, 1.0), # 紫色
                'dumbbell': (0.9, 0.9, 0.2, 1.0), # 黄色
                'disc': (0.2, 0.8, 0.8, 1.0),     # 青色
            }
            color = color_map.get(object_key, (0.8, 0.3, 0.2, 1.0))
            self.model.geom_rgba[gid] = color

        # 通过修改 qpos 来设置物体的初始位置
        free_adr = self.model.jnt_qposadr[self.joint_ids['obj_free']]
        base_pos = np.array([0, 0, 0.76])
        new_pos = base_pos + self._obj_offset
        # freejoint has 7 qpos: 3 position + 4 quaternion
        self.data.qpos[free_adr:free_adr+3] = new_pos
        self.data.qpos[free_adr+3:free_adr+7] = [1, 0, 0, 0]  # identity quaternion

        return geo

    def get_object_geo(self, object_key: str = None) -> dict:
        """获取物体几何参数"""
        if object_key is None:
            object_key = getattr(self, '_current_object', 'sphere')
        return OBJECT_GEOMETRY.get(object_key, OBJECT_GEOMETRY['sphere'])

    # ─── 仿真控制 ───

    def reset(self, object_key: str = 'sphere',
              object_offset: Tuple[float, float] = (0, 0),
              randomize_offset: bool = False) -> dict:
        """重置仿真环境"""
        # 先修改物体几何（必须在mj_resetData之前，因为模型在reset后重建）
        geo = OBJECT_GEOMETRY.get(object_key, OBJECT_GEOMETRY['sphere'])
        gid = self.geom_ids.get('obj_geom')
        if gid is not None:
            mj_shape = SHAPE_TO_MJGEOM.get(geo['shape'], 'sphere')
            if mj_shape == 'sphere':
                new_size = [geo['diameter']/2, 0.0, 0.0]
            elif mj_shape == 'box':
                new_size = [geo['width']/2, geo['height']/2, geo['diameter']/2]
            elif mj_shape == 'cylinder':
                new_size = [geo['diameter']/2, geo['height']/2, 0.0]
            else:
                new_size = [0.028, 0.028, 0.028]
            self.model.geom_type[gid] = getattr(mujoco.mjtGeom, f'mjGEOM_{mj_shape.upper()}', 6)
            self.model.geom_size[gid] = new_size
            obj_bid = self.body_ids.get('object')
            if obj_bid is not None:
                self.model.body_mass[obj_bid] = geo['mass']
            color_map = {
                'sphere': (0.9, 0.2, 0.2, 1.0),
                'box': (0.2, 0.8, 0.2, 1.0),
                'cylinder': (0.2, 0.2, 0.8, 1.0),
                'long_rod': (0.9, 0.6, 0.1, 1.0),
                'mushroom': (0.8, 0.4, 0.8, 1.0),
                'dumbbell': (0.9, 0.9, 0.2, 1.0),
                'disc': (0.2, 0.8, 0.8, 1.0),
            }
            color = color_map.get(object_key, (0.8, 0.3, 0.2, 1.0))
            self.model.geom_rgba[gid] = color

        mujoco.mj_resetData(self.model, self.data)
        self._current_object = object_key

        if randomize_offset:
            ox, oy = np.random.uniform(-0.10, 0.10, 2)
            object_offset = (ox, oy)

        # 直接操作 qpos 数组 (比 set_joint_qpos 更可靠)
        if 'slide_x' in self.joint_ids:
            for j in ['slide_x','slide_y','lift_z','wrist_pitch',
                       'wrist_yaw','hand_reach']:
                if j in self.joint_ids:
                    self.data.qpos[self.model.jnt_qposadr[self.joint_ids[j]]] = 0.0
        elif 'j1' in self.joint_ids:
            init6 = {'j1':0.0,'j2':-0.8,'j3':1.6,'j4':0.0,'j5':-0.8,'j6':0.0}
            for jn, v in init6.items():
                if jn in self.joint_ids:
                    adr = self.model.jnt_qposadr[self.joint_ids[jn]]
                    self.data.qpos[adr] = v
                    if jn in self.actuator_ids:
                        self.data.ctrl[self.actuator_ids[jn]] = v

        # 手指归零
        for f in ['THJ1','THJ2','FFJ1','FFJ2','MFJ1','MFJ2',
                  'RFJ1','RFJ2','LFJ1','LFJ2','fl_j','fr_j']:
            if f in self.joint_ids:
                self.data.qpos[self.model.jnt_qposadr[self.joint_ids[f]]] = 0.0

        # 物体初始位置（默认底面在桌面0.72上，中心高度=0.72+半径）
        # 对于sphere: 半径0.028m, 中心在0.748
        # 但不同的object_key对应不同尺寸, 统一用0.74让物体底面刚好接触桌面
        if 'obj_free' in self.joint_ids:
            adr = self.model.jnt_qposadr[self.joint_ids['obj_free']]
            self.data.qpos[adr:adr+3] = [object_offset[0], object_offset[1], 0.72 + 0.028]
            self.data.qpos[adr+3:adr+7] = [1, 0, 0, 0]

        mujoco.mj_forward(self.model, self.data)
        return self.get_observation()

    def step(self, ctrl: np.ndarray) -> Tuple[dict, float, bool, dict]:
        """
        执行一步仿真

        Args:
            ctrl: 控制信号数组 (长度 = nu)

        Returns:
            (observation, reward, done, info)
        """
        self.data.ctrl[:] = ctrl
        mujoco.mj_step(self.model, self.data)
        obs = self.get_observation()
        reward = self._compute_reward()
        done = self._check_done()
        info = self._get_info()
        return obs, reward, done, info

    def step_multi(self, ctrl: np.ndarray, n_steps: int = 50) -> Tuple[dict, float, bool, dict]:
        """多步推进"""
        for _ in range(n_steps):
            self.data.ctrl[:] = ctrl
            mujoco.mj_step(self.model, self.data)
        obs = self.get_observation()
        reward = self._compute_reward()
        done = self._check_done()
        info = self._get_info()
        return obs, reward, done, info

    # ─── 观测 ───

    def get_observation(self) -> dict:
        """获取完整观测"""
        obs = {
            'time': float(self.data.time),
            'qpos': self.data.qpos.copy(),
            'qvel': self.data.qvel.copy(),
            'object_pos': self.data.xpos[self.body_ids.get('object', 0)].copy(),
            'palm_pos': self.data.xpos[self.body_ids.get('palm', 
                self.body_ids.get('gripper_base', 
                self.body_ids.get('link6', 0)))].copy(),
            'ncon': self.data.ncon,
            'contact': [],
            'joints': {},
            'rgb': {},  # 摄像头RGB图像（name→array）
            'depth': {},  # 摄像头深度图像
        }

        # 渲染摄像头图像
        if self.model.ncam > 0:
            for i in range(self.model.ncam):
                cam_name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_CAMERA, i)
                if cam_name is None:
                    cam_name = f'cam_{i}'
                rgb = np.zeros((self.model.vis.global_.offwidth, 
                                self.model.vis.global_.offheight, 3), dtype=np.uint8)
                depth = np.zeros((self.model.vis.global_.offwidth,
                                  self.model.vis.global_.offheight), dtype=np.float32)
                # 注意：无头模式下mujoco.render需要context
                # 这里用mjvCamera方式渲染
                try:
                    scn = mujoco.MjvScene(self.model, maxgeom=1000)
                    cam = mujoco.MjvCamera()
                    mujoco.mjv_defaultFreeCamera(self.model, cam)
                    cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                    if i < mujoco.mjtCamera.mjNCAMERA:
                        cam.fixedcamid = i
                        cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                    else:
                        cam.trackbodyid = self.body_ids.get('object', 0)
                        cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
                    
                    rect = mujoco.MjvRect(0, 0, 640, 480)
                    mujoco.mjv_updateScene(self.model, self.data, mujoco.MjvOption(), 
                                            None, cam, mujoco.mjtCatBit.mjCAT_ALL, scn)
                    # 渲染
                    rgb_img = np.zeros((480, 640, 3), dtype=np.uint8)
                    depth_img = np.zeros((480, 640), dtype=np.float32)
                    mujoco.mjr_render(rect, scn, None)
                    # mjr_render需要context才能工作，在无头模式下不可用
                    # 预留接口，等待有头环境
                except Exception:
                    pass

        obs['rgb'] = {}
        obs['depth'] = {}

        # 关节角度
        for jname in self.joint_ids:
            try:
                obs['joints'][jname] = self.get_joint_qpos(jname)
            except:
                pass

        # 接触信息
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            g1 = self.model.geom(c.geom1).name
            g2 = self.model.geom(c.geom2).name
            obs['contact'].append({
                'geom1': g1, 'geom2': g2,
                'force': c.dist if hasattr(c, 'dist') else 0.0,
            })

        # 物体提升高度
        obj_z = obs['object_pos'][2]
        obs['lift_height'] = obj_z - 0.72  # 桌面高度 0.72

        return obs

    def _compute_reward(self) -> float:
        """奖励（用于基线训练，YLYW 零样本不用）"""
        return 0.0

    def _check_done(self) -> bool:
        """检查是否完成"""
        return False

    def _get_info(self) -> dict:
        return {}

    # ─── 便捷方法 ───

    def get_obj_lift_mm(self) -> float:
        """获取物体提升高度 (mm)"""
        obj_bid = self.body_ids.get('object')
        if obj_bid is None:
            return 0.0
        return (self.data.xpos[obj_bid][2] - 0.72) * 1000

    def check_success(self, threshold_mm: float = 3.0) -> bool:
        """检查抓取是否成功"""
        return self.get_obj_lift_mm() > threshold_mm

    def get_finger_contacts(self) -> dict:
        """获取各手指接触状态"""
        fingers = ['thumb', 'index', 'middle', 'ring', 'pinky']
        contacts = {f: False for f in fingers}
        for i in range(self.data.ncon):
            g1 = self.model.geom(self.data.contact[i].geom1).name
            g2 = self.model.geom(self.data.contact[i].geom2).name
            for f in fingers:
                if f in g1 or f in g2:
                    contacts[f] = True
        return contacts

    def print_state(self):
        """打印当前状态"""
        print(f"t={self.data.time:.3f}, obj_lift={self.get_obj_lift_mm():+.1f}mm")
        print(f"  slide_x={self.get_joint_qpos('slide_x'):+.3f}, "
              f"slide_y={self.get_joint_qpos('slide_y'):+.3f}, "
              f"lift_z={self.get_joint_qpos('lift_z'):+.3f}")
        contacts = self.get_finger_contacts()
        n = sum(1 for v in contacts.values() if v)
        print(f"  fingers contacting: {n}/5 {contacts}")


def quick_test():
    """快速测试环境能否加载"""
    env = CrossBodyEnv(body_type='shadow_hand_3axis', headless=True)
    obs = env.reset(object_key='sphere')
    print("Reset OK. Observation keys:", list(obs.keys()))
    print(f"nq={env.model.nq}, nu={env.model.nu}")
    print(f"Joint names: {list(env.joint_ids.keys())}")
    print(f"Actuator names: {list(env.actuator_ids.keys())}")

    # 简单测试：降臂
    ctrl = np.zeros(env.model.nu)
    ctrl[env.actuator_ids.get('lift_z', 0)] = -0.20
    for _ in range(200):
        env.step(ctrl)
    print(f"After lowering: lift_z={env.get_joint_qpos('lift_z'):+.3f}")
    contacts = env.get_finger_contacts()
    print(f"Finger contacts: {contacts}")
    print(f"Lift: {env.get_obj_lift_mm():+.1f}mm")

    # 测试 XY 滑动
    ctrl = np.zeros(env.model.nu)
    ctrl[env.actuator_ids.get('slide_x', 0)] = 0.05
    ctrl[env.actuator_ids.get('slide_y', 0)] = 0.03
    for _ in range(200):
        env.step(ctrl)
    print(f"After XY move: slide_x={env.get_joint_qpos('slide_x'):+.3f}, "
          f"slide_y={env.get_joint_qpos('slide_y'):+.3f}")

    print("\n✅ quick_test passed!")
    return env


if __name__ == '__main__':
    quick_test()
