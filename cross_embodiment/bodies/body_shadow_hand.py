#!/usr/bin/env python3
"""
Shadow Hand + 3轴笛卡尔臂 — 本体配置

手臂:
  - slide_x: X轴平移(左右) ±80mm
  - slide_y: Y轴平移(前后) ±80mm
  - lift_z: Z轴升降
  - wrist_pitch: 俯仰
  - wrist_yaw:  偏转
  - hand_reach: 前伸微调

手指: 拇指+食指+中指+无名指+小指 (各2DOF)

六爻映射（手臂+手指统一的决策空间）:
  初爻: 手掌已XY对准目标?    ← 新增：3轴臂的核心价值
  二爻: 手指接近物体?        ← 是否足够接近
  三爻: 接触力已建立?        ← 是否接触
  四爻: 手指弯曲度足够?      ← 是否包住
  五爻: 提升成功?            ← 是否提起
  上爻: 安全裕度?            ← 滑动/失稳检测
"""

import numpy as np
from typing import Dict, Any
from bodies.base_config import BodyConfig, YaoThresholds

# 手指名称列表
FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']
FINGER_ACTUATORS = ['THJ1', 'THJ2', 'FFJ1', 'FFJ2', 'MFJ1', 'MFJ2',
                    'RFJ1', 'RFJ2', 'LFJ1', 'LFJ2']

# 控制信号索引顺序
CTRL_ORDER = [
    'slide_x', 'slide_y', 'lift_z',          # 3轴臂 (0,1,2)
    'wrist_pitch', 'wrist_yaw', 'hand_reach', # 手腕 (3,4,5)
    'THJ1', 'THJ2', 'FFJ1', 'FFJ2',           # 手指 (6-15)
    'MFJ1', 'MFJ2', 'RFJ1', 'RFJ2',
    'LFJ1', 'LFJ2',
]

# 手指力矩上限
MAX_TORQUE = {
    'thumb': 2.5, 'index': 2.0, 'middle': 2.0, 'ring': 1.8, 'pinky': 1.5
}


class ShadowHand3AxisConfig(BodyConfig):
    """Shadow Hand + 3轴臂配置"""

    def __init__(self):
        super().__init__()
        self.name = "shadow_hand_3axis"
        self.n_dof = 16     # 3+3+10
        self.n_ctrl = 16
        self.end_effector = "5-finger dexterous hand"
        self.description = "Shadow Hand dexterous hand on 3-axis Cartesian arm"

        # 各分类参数
        self.palm_center = np.array([0.0, 0.0, 1.00])  # 手掌默认世界坐标

        # 物体→指尖接近距离阈值
        self.approach_dist = 0.04   # m
        self.contact_force_thresh = 0.15
        self.lift_threshold = 0.05  # m
        self.xy_align_thresh = 0.015  # m (15mm)

    def encode_yao(self, bagua: np.ndarray, obs: dict) -> np.ndarray:
        """
        六爻编码：3轴臂 + 灵巧手 传感器状态 → 6维决策空间

        L2 的设计关键在于每个爻有明确的语义锚定，
        从初爻到上爻对应抓取任务的递进阶段。

        Returns:
            yao: 6维, 每维 ∈ [0,1]
        """
        yao = np.zeros(6)

        # === 提取传感器信息 ===
        joints = obs.get('joints', {})
        contacts = obs.get('contact', [])
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.00]))
        lift_h = obs.get('lift_height', 0.0)

        # XY 距离（手掌到物体的水平距离）
        dx = palm_pos[0] - obj_pos[0]
        dy = palm_pos[1] - obj_pos[1]
        xy_dist = np.sqrt(dx**2 + dy**2)

        # Z 距离
        z_dist = palm_pos[2] - obj_pos[2]

        # 识别哪些 geom 是手指尖
        contact_fingers = set()
        for c in contacts:
            g1 = c.get('geom1', '')
            g2 = c.get('geom2', '')
            for f in FINGER_NAMES:
                if (f in g1 and ('obj' in g2 or 'obj' in g2)) or \
                   (f in g2 and ('obj' in g1 or 'obj' in g1)):
                    contact_fingers.add(f)

        n_contacts = len(contact_fingers)

        # 手指弯曲度（各关节弯曲量平均值）
        finger_curls = []
        for act in FINGER_ACTUATORS:
            v = joints.get(act, 0.0)
            finger_curls.append(v)
        avg_curl = np.mean(finger_curls) if finger_curls else 0.0

        # 提升高度
        lift = max(0, lift_h)

        # 滑动检测（物体Z速度）
        obj_vel = obs.get('qvel', np.zeros(self.n_dof + 6))

        # === 六爻编码 ===

        # 初爻: 手掌已XY对准?
        # 当 xy_dist < 阈值 → 1, 否则随距离递减
        yao[0] = YaoThresholds.gaussian(xy_dist, center=0.0, sigma=self.xy_align_thresh)
        # 如果是逆映射（越大越好）
        # yao[0] = 1.0 - np.clip(xy_dist / (self.xy_align_thresh * 3), 0, 1)

        # 二爻: 已接近/已提升?
        # z_dist 越小（手掌越靠近物体）→ 值越高
        # 修正：当五爻>0.3（已提升）时不再需要Z接近，推定=1
        lift_ratio = np.clip(lift / self.lift_threshold, 0, 1)
        if lift_ratio > 0.3:
            yao[1] = 0.8  # 已提升 → 推定已接近
        else:
            ideal_z = 0.04
            yao[1] = YaoThresholds.gaussian(z_dist, center=ideal_z, sigma=0.03)
            if z_dist > 0.10:
                yao[1] *= 0.5

        # 三爻: 接触力建立了吗？
        # 接触手指越多越好，但3根以上就够了
        # 关键修正：如果能提升（五爻>0.3），推定接触已建立
        if lift > 0.003:  # 提升>3mm → 一定有接触
            contact_confidence = 0.9
        else:
            contact_confidence = np.clip(n_contacts / 2.0, 0, 1)
        yao[2] = contact_confidence

        # 四爻: 手指弯曲度足够包裹物体?
        yao[3] = np.clip((avg_curl - 0.1) / 0.5, 0, 1)

        # 五爻: 提升成功？
        yao[4] = np.clip(lift / self.lift_threshold, 0, 1)

        # 上爻: 释放信号
        # 当五爻>0.5（已提升）+ 四爻>0.2（手指已闭合）时触发释放
        # 这是3轴臂的自然行为：稳定抓住后维持50步→触发释放
        ready_for_release = (yao[3] > 0.15 and yao[4] > 0.5)
        
        # 计数器
        if not hasattr(self, '_release_counter'):
            self._release_counter = 0
        if lift < 0.001:
            self._release_counter = 0
        
        if ready_for_release:
            self._release_counter += 1
        else:
            self._release_counter = max(0, self._release_counter - 1)
        
        # 25步触发（约¼秒的物理时间）
        yao[5] = min(1.0, self._release_counter / 25.0)

        return yao

    def decode_action(self, strategy: dict, obs: dict,
                      current_ctrl: np.ndarray = None) -> np.ndarray:
        """
        卦象策略 → 3轴臂 + 手指 控制信号

        Args:
            strategy: L3输出的策略字典
                { "gua": str, "strategy": str, "params": dict }
            obs: 当前观测
            current_ctrl: 当前控制信号（用于平滑过渡）

        Returns:
            ctrl: 16维控制信号
        """
        ctrl = np.zeros(self.n_ctrl)
        if current_ctrl is not None:
            ctrl[:] = current_ctrl

        strategy_type = strategy.get('strategy_type', strategy.get('strategy', '待机'))
        # 策略名标准化
        STYPE_MAP = {
            'power_grasp': '全力抓取/执行',
            'standard_grasp': '缓慢接近/精确对准', 'stable_grasp': '缓慢接近/精确对准',
            'tight_grasp': '全力抓取/执行',
            'balanced_grasp': '任务完成/确认',
            'non_conflict_grasp': '任务未完成/继续尝试',
            'release': '松开/释放',
            '待机': '待机/准备',
            'done': '任务完成/确认',
        }
        strategy_type = STYPE_MAP.get(strategy_type, strategy_type)
        
        # 对剩余的未映射英文名，按语义分组映射到中文策略
        GRASP_FAMILY = {'cautious_grasp','interlocking_grasp','conditional_grasp','corrective_grasp',
                        'adhesion_grasp','parallel_ext','wrap_grasp','lateral_grasp','precision_grasp'}
        RELEASE_FAMILY = {'release','object_release','careful_release'}
        RETRY_FAMILY = {'avoid_or_retry','retry','stabilize'}
        BALANCED_FAMILY = {'balanced_grasp','keep','hold','maintain'}
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
        precision = params.get('precision', 'medium')

        joints = obs.get('joints', {})
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.00]))

        # 计算手掌到物体的3D偏移
        dx = obj_pos[0] - palm_pos[0]
        dy = obj_pos[1] - palm_pos[1]
        dz = obj_pos[2] - palm_pos[2] - 0.02  # 略高于物体中心

        # ─── 根据策略类型生成控制信号 ───

        if strategy_type == "全力抓取/执行":
            # 1) 对齐XY: slide_x, slide_y 趋近物体
            align_gain = min(speed * 0.5, 0.5)
            ctrl[0] = dx * align_gain * 50      # slide_x
            ctrl[1] = dy * align_gain * 50      # slide_y
            # 2) 降臂接近
            ctrl[2] = dz * speed * 30            # lift_z
            # 3) 手腕采用默认角度
            ctrl[3] = 0.15                        # wrist_pitch (微俯)
            ctrl[4] = 0.0                         # wrist_yaw
            # 4) 前伸
            ctrl[5] = 0.03                        # hand_reach
            # 5) 手指全闭合
            for i, act in enumerate(FINGER_ACTUATORS):
                ctrl[6 + i] = 0.8 * force + 0.2

        elif strategy_type == "任务完成/确认":
            # 检测是否已释放——从上爻信号判断
            yao_upper = strategy.get('yao', np.zeros(6))[5]
            if yao_upper > 0.5:
                # 释放模式：下降+半松手
                ctrl[0] = 0.0
                ctrl[1] = 0.0
                ctrl[2] = -0.05                     # 下降
                for i in range(10):
                    ctrl[6 + i] = 0.15 * force      # 半松
            else:
                # 提升到位，保持抓取力
                ctrl[0] = 0.0
                ctrl[1] = 0.0
                ctrl[2] = 0.12                        # 提升
                for i in range(10):
                    ctrl[6 + i] = 0.6 * force

        elif strategy_type in ("待机/准备", "待机"):
            # 回到初始位置，手指张开
            ctrl[0:3] = 0.0
            ctrl[3:6] = 0.0
            for i in range(10):
                ctrl[6 + i] = 0.0

        elif strategy_type == "任务未完成/继续尝试":
            # 尝试不同的手腕角度和前伸
            ctrl[0] = dx * 0.3 * 50
            ctrl[1] = dy * 0.3 * 50
            ctrl[2] = dz * 0.8 * 30
            ctrl[3] = 0.3                          # 更倾斜
            ctrl[4] = 0.0
            ctrl[5] = 0.05                         # 更多前伸
            for i in range(10):
                ctrl[6 + i] = 0.9 * force          # 更用力

        else:
            # 默认: 匀速接近
            ctrl[0] = dx * 0.3 * 50
            ctrl[1] = dy * 0.3 * 50
            ctrl[2] = dz * 0.5 * 30
            ctrl[3] = 0.1
            ctrl[4] = 0.0
            ctrl[5] = 0.02
            for i in range(10):
                ctrl[6 + i] = 0.5

        return ctrl

    @staticmethod
    def finger_angles_from_strategy(strategy_name: str, force_scale: float = 1.0) -> list:
        """
        根据策略名获取手指角度配置（兼容原 dexterous_sim 的 STRATEGY_TO_POSITION）

        Returns:
            10个手指关节的目标位置
        """
        # 策略→手指关节映射
        strategy_map = {
            'open':       [0,0, 0,0, 0,0, 0,0, 0,0],
            'power_grasp': [0.4,0.6, 0.9,0.8, 0.9,0.8, 0.8,0.7, 0.8,0.7],
            'precision':  [0.5,0.3, 0.7,0.5, 0.6,0.5, 0.5,0.4, 0.4,0.3],
            'wrap_grasp': [0.4,0.5, 0.8,0.7, 0.8,0.7, 0.7,0.6, 0.7,0.6],
            'firm_grasp': [0.5,0.7, 1.0,0.9, 1.0,0.9, 0.9,0.8, 0.9,0.8],
            'soft_grasp': [0.3,0.4, 0.6,0.5, 0.6,0.5, 0.5,0.4, 0.5,0.4],
        }
        angles = strategy_map.get(strategy_name, strategy_map['open'])
        return [a * min(force_scale, 1.5) for a in angles]


if __name__ == '__main__':
    config = ShadowHand3AxisConfig()
    print(f"Body: {config.name}")
    print(f"  DOF: {config.n_dof}, Ctrl: {config.n_ctrl}")
    print(f"  End effector: {config.end_effector}")

    # 模拟编码
    bagua = np.array([0.8, 0.3, 0.2, 0.7, 0.1, 0.2, 0.3, 0.4])
    obs = {
        'joints': {a: 0.5 for a in FINGER_ACTUATORS},
        'object_pos': np.array([0.01, -0.02, 0.76]),
        'palm_pos': np.array([0.0, 0.0, 1.00]),
        'lift_height': 0.0,
        'contact': [],
    }
    yao = config.encode_yao(bagua, obs)
    print(f"  Sample yao: {yao}")
    print("✅ ShadowHand3AxisConfig OK")
