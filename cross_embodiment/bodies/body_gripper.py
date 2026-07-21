#!/usr/bin/env python3
"""
力控夹爪 + 3轴笛卡尔臂 — 本体配置

与灵巧手共享同一套 64 卦规则表和 3轴臂结构。
唯一不同的是末端执行器（夹爪 vs 灵巧手）和六爻语义。

六爻映射:
  初爻: 手掌已XY对准目标?
  二爻: 夹爪接近物体? (Z方向)
  三爻: 夹爪接触物体?
  四爻: 夹爪闭合度?
  五爻: 提升成功?
  上爻: 安全裕度? (滑脱检测)
"""

import numpy as np
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_config import BodyConfig, YaoThresholds


class Gripper3AxisConfig(BodyConfig):
    """力控夹爪 + 3轴臂配置"""

    def __init__(self):
        super().__init__()
        self.name = "force_gripper_3axis"
        self.n_dof = 5       # 3轴 + 2指
        self.n_ctrl = 5
        self.end_effector = "2-finger parallel gripper"
        self.description = "Force-controlled parallel gripper on 3-axis Cartesian arm"

        # 参数
        self.xy_align_thresh = 0.015      # 15mm
        self.approach_dist = 0.03         # 接近距离
        self.contact_force_thresh = 0.1   # 接触力阈值
        self.grip_close_thresh = 0.02     # 夹爪闭合 20mm(从初始间距70mm算)
        self.lift_threshold = 0.05        # 提升50mm

    def encode_yao(self, bagua: np.ndarray, obs: dict) -> np.ndarray:
        """
        六爻编码：力控夹爪 传感器 → 6维决策空间

        注意：与灵巧手共享相同的 L3 规则表，
        但 L2 编码语义不同——夹爪只能用"开/合+力"二元信号，
        不像灵巧手有5根手指的丰富接触信息。
        """
        yao = np.zeros(6)

        joints = obs.get('joints', {})
        contacts = obs.get('contact', [])
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.00]))
        lift_h = obs.get('lift_height', 0.0)

        # 手掌=夹爪中点位置
        gripper_pos = palm_pos

        # XY距离
        dx = gripper_pos[0] - obj_pos[0]
        dy = gripper_pos[1] - obj_pos[1]
        xy_dist = np.sqrt(dx**2 + dy**2)

        # Z距离
        z_dist = gripper_pos[2] - obj_pos[2]

        # 手指位置
        fl = joints.get('fl_j', 0.0)
        fr = joints.get('fr_j', 0.0)
        grip_open = 0.07 - fl - fr  # 初始间距~0.07m
        grip_close = max(0, grip_open)

        # 接触判断（夹爪碰到物体）
        n_contacts = 0
        for c in contacts:
            g1 = c.get('geom1', '')
            g2 = c.get('geom2', '')
            if ('fl_' in g1 or 'fr_' in g1) and 'obj' in g2:
                n_contacts += 1
            if ('fl_' in g2 or 'fr_' in g2) and 'obj' in g1:
                n_contacts += 1

        # 提升
        lift = max(0, lift_h)

        # === 六爻编码 ===

        # 初爻: XY已对准?
        yao[0] = YaoThresholds.gaussian(xy_dist, center=0.0, sigma=self.xy_align_thresh)

        # 二爻: Z接近物体?
        ideal_z = 0.02  # 夹爪正好在物体上方2cm
        yao[1] = YaoThresholds.gaussian(z_dist, center=ideal_z, sigma=0.025)
        if z_dist > 0.08:
            yao[1] *= 0.3  # 太远就减小

        # 三爻: 接触力建立? (夹爪接触 = 1/2指接触)
        yao[2] = np.clip(n_contacts / 2.0, 0, 1)

        # 四爻: 夹爪闭合度? (闭合越紧越高)
        # 完全张开=0, 完全闭合(夹爪距离<10mm)≈1
        yao[3] = np.clip(1.0 - grip_close / 0.06, 0, 1)

        # 五爻: 提升成功?
        yao[4] = np.clip(lift / self.lift_threshold, 0, 1)

        # 上爻: 安全裕度
        # 如果已经提起来了但接触掉了 → 不安全
        if lift > 0.01 and n_contacts < 1:
            yao[5] = 0.1
        else:
            yao[5] = 0.9 if lift > 0 else 1.0

        return yao

    def decode_action(self, strategy: dict, obs: dict,
                      current_ctrl: np.ndarray = None) -> np.ndarray:
        """
        卦象策略 → 3轴臂 + 夹爪力控制信号

        ctrl: [slide_x, slide_y, lift_z, fl_motor, fr_motor]
        """
        ctrl = np.zeros(self.n_ctrl)
        if current_ctrl is not None:
            ctrl[:] = current_ctrl

        strategy_type = strategy.get('strategy_type', strategy.get('strategy', '待机'))
        STYPE_MAP = {
            'power_grasp': '全力抓取/执行',
            'standard_grasp': '缓慢接近/精确对准', 'stable_grasp': '缓慢接近/精确对准',
            'tight_grasp': '全力抓取/执行', 'balanced_grasp': '任务完成/确认',
            'non_conflict_grasp': '任务未完成/继续尝试',
            'release': '松开/释放', '待机': '待机/准备', 'done': '任务完成/确认',
        }
        strategy_type = STYPE_MAP.get(strategy_type, strategy_type)
        # 对剩余未映射名分组
        GRASP_FAMILY = {'cautious_grasp','interlocking_grasp','conditional_grasp','corrective_grasp',
                        'adhesion_grasp','parallel_ext','wrap_grasp','lateral_grasp','precision_grasp',
                        'stable_grasp','standard_grasp','tight_grasp','power_grasp'}
        RELEASE_FAMILY = {'release','object_release','careful_release'}
        RETRY_FAMILY = {'avoid_or_retry','retry','stabilize','non_conflict_grasp'}
        BALANCED_FAMILY = {'balanced_grasp','keep','hold','maintain','done'}
        IDLE_FAMILY = {'待机','idle','home','reset'}
        if strategy_type in GRASP_FAMILY:
            strategy_type = '全力抓取/执行'
        elif strategy_type in RELEASE_FAMILY:
            strategy_type = '松开/释放'
        elif strategy_type in RETRY_FAMILY:
            strategy_type = '任务未完成/继续尝试'
        elif strategy_type in BALANCED_FAMILY:
            strategy_type = '任务完成/确认'
        elif strategy_type in IDLE_FAMILY:
            strategy_type = '待机/准备'
        params = strategy.get('params', {})
        speed = params.get('speed', 0.5)
        force = params.get('force', 0.5)

        joints = obs.get('joints', {})
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.00]))

        # 3D偏移
        dx = obj_pos[0] - palm_pos[0]
        dy = obj_pos[1] - palm_pos[1]
        dz = obj_pos[2] - palm_pos[2] - 0.01  # 略低于物体顶部

        if strategy_type == "全力抓取/执行":
            # 对齐+下降+闭合
            ctrl[0] = np.clip(dx * 40, -0.06, 0.06)
            ctrl[1] = np.clip(dy * 40, -0.06, 0.06)
            ctrl[2] = np.clip(dz * 20, -0.30, 0.05)
            # 夹爪用力闭合 (motor 正=闭合方向)
            grip_force = 0.3 + force * 0.5
            ctrl[3] = grip_force   # fl_motor
            ctrl[4] = grip_force   # fr_motor

        elif strategy_type == "任务完成/确认":
            # 检测是否已释放——从上爻信号判断
            yao_upper = strategy.get('yao', np.zeros(6))[5]
            if yao_upper > 0.5:
                # 释放模式：下降+松开
                ctrl[0] = 0.0
                ctrl[1] = 0.0
                ctrl[2] = -0.05   # 下降
                ctrl[3] = 0.1      # 微力
                ctrl[4] = 0.1
            else:
                ctrl[0] = 0.0
                ctrl[1] = 0.0
                ctrl[2] = 0.10  # 提升
                ctrl[3] = 0.4   # 保持力
                ctrl[4] = 0.4

        elif strategy_type in ("待机/准备", "待机"):
            # 张开回到初始
            ctrl[0:3] = 0.0
            ctrl[3] = -0.2  # 张开 (负=打开)
            ctrl[4] = -0.2

        elif strategy_type == "任务未完成/继续尝试":
            # 加大力度和接近
            ctrl[0] = np.clip(dx * 50, -0.08, 0.08)
            ctrl[1] = np.clip(dy * 50, -0.08, 0.08)
            ctrl[2] = np.clip(dz * 30, -0.30, 0.05)
            ctrl[3] = min(1.0, 0.5 + force * 0.6)
            ctrl[4] = min(1.0, 0.5 + force * 0.6)

        elif strategy_type == "缓慢接近/精确对准":
            ctrl[0] = np.clip(dx * 20, -0.03, 0.03)
            ctrl[1] = np.clip(dy * 20, -0.03, 0.03)
            ctrl[2] = np.clip(dz * 15, -0.20, 0.05)
            ctrl[3] = 0.05  # 轻微预夹
            ctrl[4] = 0.05

        elif strategy_type == "松开/释放":
            ctrl[0:3] = 0.0
            ctrl[3] = -0.3  # 张开
            ctrl[4] = -0.3

        else:
            # 默认
            ctrl[0] = np.clip(dx * 30, -0.05, 0.05)
            ctrl[1] = np.clip(dy * 30, -0.05, 0.05)
            ctrl[2] = np.clip(dz * 20, -0.25, 0.05)
            ctrl[3] = 0.2
            ctrl[4] = 0.2

        return ctrl


if __name__ == '__main__':
    config = Gripper3AxisConfig()
    print(f"Body: {config.name}")
    print(f"  DOF: {config.n_dof}, Ctrl: {config.n_ctrl}")
    print(f"  End effector: {config.end_effector}")

    bagua = np.array([0.8, 0.3, 0.2, 0.7, 0.1, 0.2, 0.3, 0.4])
    obs = {
        'joints': {'fl_j': 0.0, 'fr_j': 0.0, 'slide_x': 0.0, 'slide_y': 0.0, 'lift_z': 0.0},
        'object_pos': np.array([0.02, -0.01, 0.76]),
        'palm_pos': np.array([0.0, 0.0, 1.00]),
        'lift_height': 0.0,
        'contact': [],
    }
    yao = config.encode_yao(bagua, obs)
    print(f"  Sample yao: {yao}")

    # 验证解码
    strategy = {'strategy_type': '全力抓取/执行', 'params': {'speed': 0.7, 'force': 0.6}}
    ctrl = config.decode_action(strategy, obs)
    print(f"  Decode: {np.round(ctrl, 3)}")
    print("✅ Gripper3AxisConfig OK")
