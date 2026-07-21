#!/usr/bin/env python3
"""
6轴协作机械臂 + 灵巧手 — 本体配置 (YLYW 直接控制版)

与3轴臂一样，卦象策略直接决定6个关节的目标位置。
不再使用中间 IK 层——YLYW 的 64 卦规则本身就是控制策略。

六爻映射 (针对6轴臂):
  初爻: 末端与物体的 XY 平面距离较近?
  二爻: 末端 Z 方向已接近物体高度?
  三爻: 灵巧手接触了物体?
  四爻: 手指弯曲度足以包裹?
  五爻: 物体已提升?
  上爻: 安全裕度/无关节超限?
"""

import numpy as np
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_config import BodyConfig, YaoThresholds

FINGER_ACT = ['THJ1','THJ2','FFJ1','FFJ2','MFJ1','MFJ2','RFJ1','RFJ2','LFJ1','LFJ2']
FINGER_NAMES = ['thumb','index','middle','ring','pinky']

# 6轴臂的初始关节角 (待机姿态，臂竖直向上)
Q_HOME = np.array([0.0, -0.8, 1.6, 0.0, -0.8, 0.0])


class Arm6HandConfig(BodyConfig):
    """6轴臂 + 灵巧手 — YLYW 直接关节控制"""

    def __init__(self):
        super().__init__()
        self.name = "arm6_hand"
        self.n_dof = 16
        self.n_ctrl = 16
        self.end_effector = "5-finger dexterous hand on 6-DOF arm"
        self.description = "UR5-style 6-DOF arm + Shadow Hand, YLYW direct joint control"

        self.xy_align_thresh = 0.05    # 放宽到50mm（提升初爻灵敏度）
        self.z_approach_thresh = 0.08  # 放宽到80mm
        self.lift_threshold = 0.01     # 降到10mm（小物体也能触发）
        self.contact_finger_thresh = 2 # 2指接触就算

        # 6轴臂关节范围 (弧度)
        self.joint_ranges = [
            (-3.14, 3.14),   # j1
            (-2.5, 2.5),     # j2
            (-2.5, 2.5),     # j3
            (-3.14, 3.14),   # j4
            (-2.0, 2.0),     # j5
            (-3.14, 3.14),   # j6
        ]

    def encode_yao(self, bagua, obs):
        """六爻编码: 6轴臂状态 → 6维决策空间 (动态感知版)"""
        yao = np.zeros(6)
        joints = obs.get('joints', {})
        contacts = obs.get('contact', [])
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.26]))
        lift_h = obs.get('lift_height', 0.0)

        dx = palm_pos[0] - obj_pos[0]
        dy = palm_pos[1] - obj_pos[1]
        xy_dist = math.sqrt(dx*dx + dy*dy)
        z_dist = palm_pos[2] - obj_pos[2]

        # 接触（用FINGER_ACT前缀匹配，兼容不同几何体命名）
        contact_fingers = set()
        for c in contacts:
            g1, g2 = c.get('geom1',''), c.get('geom2','')
            for act in FINGER_ACT:
                if (act in g1 and 'obj' in g2) or (act in g2 and 'obj' in g1):
                    if 'TH' in act: contact_fingers.add('thumb')
                    elif 'FF' in act: contact_fingers.add('index')
                    elif 'MF' in act: contact_fingers.add('middle')
                    elif 'RF' in act: contact_fingers.add('ring')
                    elif 'LF' in act: contact_fingers.add('pinky')
        n_contacts = len(contact_fingers)

        # 手指弯曲
        curls = [abs(joints.get(a, 0)) for a in FINGER_ACT]
        avg_curl = np.mean(curls) if curls else 0

        lift = max(0, lift_h)

        # ─── 六爻编码 ───
        obj_feat = obs.get('object_features', {})
        roll = obj_feat.get('roll_tendency', 0.5)
        adaptive_sigma = self.xy_align_thresh * (0.8 + roll * 0.4)
        yao[0] = YaoThresholds.gaussian(xy_dist, center=0.0, sigma=adaptive_sigma)

        # 提升比（先算，被二爻、三爻、五爻都需要）
        lift_ratio = np.clip(lift / self.lift_threshold, 0, 1)

        ideal_z = 0.0
        z_sigma = self.z_approach_thresh * (0.8 + roll * 0.4)
        yao[1] = YaoThresholds.gaussian(z_dist, center=ideal_z, sigma=z_sigma)

        # 三爻: 接触力
        # 如果已提升（五爻>0.3），推定接触已建立（能提升说明手指抓住了物体）
        if lift_ratio > 0.3:
            yao[2] = 0.9
        else:
            yao[2] = np.clip(n_contacts / 1.0, 0, 1)

        # 四爻: 手指弯曲度（avg_curl 是关节角绝对值，最大约0.5-0.7）
        yao[3] = np.clip(avg_curl / 0.4, 0, 1)

        # 五爻: 提升
        yao[4] = lift_ratio

        # 上爻: 释放信号
        dist_to_center = math.sqrt(obj_pos[0]**2 + obj_pos[1]**2)

        # 释放条件（更宽松）:
        #   - 提升>1mm 或 手指充分弯曲
        #   - 物体距离中心<30cm
        ready_to_release = (
            (lift > 0.001 or avg_curl > 0.15) and  # 提升或弯曲
            dist_to_center < 0.30                   # 30cm内
        )

        # 释放计数器（维持信号稳定）
        if not hasattr(self, '_release_counter'):
            self._release_counter = 0

        # 提升状态下不重置计数器（防止释放→下降→再提升的循环）
        if lift < 1 and self._release_counter > 50:
            self._release_counter = 0
        
        if ready_to_release:
            self._release_counter = min(60, self._release_counter + 3)  # 快速累积
        else:
            self._release_counter = max(0, self._release_counter - 1)

        # 上爻输出：超过30即触发
        release_signal = min(1.0, self._release_counter / 30.0)
        yao[5] = release_signal * 0.95

        return yao

    def decode_action(self, strategy, obs, current_ctrl=None):
        """
        卦象驱动的6轴臂+灵巧手动作解码 (动态感知版)

        不再用静态关节构型，而是基于物体位置动态计算目标关节角。
        核心：使用逆端点到物体的偏移，通过 joint-space damping 生成平滑运动。
        """
        ctrl = np.zeros(self.n_ctrl)
        if current_ctrl is not None:
            ctrl[:] = current_ctrl

        stype = strategy.get('strategy_type', 'standard_grasp')
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
        stype = STYPE_MAP.get(stype, stype)
        # 对剩余未映射名分组
        GRASP_FAMILY = {'cautious_grasp','interlocking_grasp','conditional_grasp','corrective_grasp',
                        'adhesion_grasp','parallel_ext','wrap_grasp','lateral_grasp','precision_grasp',
                        'stable_grasp','standard_grasp','tight_grasp','power_grasp'}
        RELEASE_FAMILY = {'release','object_release','careful_release'}
        RETRY_FAMILY = {'avoid_or_retry','retry','stabilize','non_conflict_grasp'}
        BALANCED_FAMILY = {'balanced_grasp','keep','hold','maintain','done'}
        IDLE_FAMILY = {'待机','idle','home','reset'}
        if stype in GRASP_FAMILY:
            stype = '全力抓取/执行'
        elif stype in RELEASE_FAMILY:
            stype = '松开/释放'
        elif stype in RETRY_FAMILY:
            stype = '任务未完成/继续尝试'
        elif stype in BALANCED_FAMILY:
            stype = '任务完成/确认'
        elif stype in IDLE_FAMILY:
            stype = '待机/准备'
        params = strategy.get('params', {})
        force = params.get('force', 0.5)
        speed = params.get('speed', 0.5)

        joints = obs.get('joints', {})
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.26]))

        q_cur = np.array([joints.get(f'j{i}', Q_HOME[i-1]) for i in range(1, 7)])
        dx = obj_pos[0] - palm_pos[0]
        dy = obj_pos[1] - palm_pos[1]
        dz = obj_pos[2] - palm_pos[2]
        xy_dist = math.sqrt(dx*dx + dy*dy)

        # ─── 动态关节生成 ───
        # j1: 朝向物体
        j1_target = math.atan2(dy, dx) if xy_dist > 0.005 else q_cur[0]
        planar_dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        reach_ratio = min(1.0, planar_dist / 0.4)

        # 基础接近构型（按距离动态调节）
        # 修正：j3 不要太高（高于0.8就让手掌朝天）；j3=0.3左右手指指向桌面
        j2_target = -0.8 + reach_ratio * 0.3
        j3_target = 1.0 - reach_ratio * 0.7  # 从1.0(收)到0.3(放)
        j5_target = -0.8 + reach_ratio * 0.2
        q_approach = np.array([j1_target, j2_target, j3_target, 0.0, j5_target, 0.0])
        q_lift = np.array([0.0, 0.3, 0.3, 0.0, -0.25, 0.0])
        q_release = np.array([0.0, -0.2, 0.6, 0.0, -0.3, 0.0])

        # 全局释放锁——一旦释放过，任何策略都输出下降+松手
        if not hasattr(self, '_released_once'):
            self._released_once = False
        if self._released_once:
            ctrl[:6] = q_release
            ctrl[6:] = [0.1] * 10
            return ctrl

        # ─── 策略分支 — 直接输出目标位置（position actuator 接受目标值）───
        if stype in ("全力抓取/执行", "power_grasp"):
            if planar_dist < 0.15:
                ctrl[:6] = [j1_target, -0.2, 0.4, 0.0, -0.5, 0.0]
            else:
                ctrl[:6] = q_approach
            ctrl[6:] = [0.4 + 0.5 * force] * 10

        elif stype in ("任务完成/确认", "balanced_grasp"):
            # 一次释放锁——释放后不再回到提升态
            if not hasattr(self, '_released_once'):
                self._released_once = False
            
            if self._released_once:
                # 已释放：保持下降+手指微开
                ctrl[:6] = q_release
                ctrl[6:] = [0.1] * 10
            else:
                yao_upper = strategy.get('yao', np.zeros(6))[5]
                if yao_upper > 0.5:
                    ctrl[:6] = q_release  # 下降
                    ctrl[6:] = [0.15] * 10  # 半松
                    self._released_once = True  # 锁定释放
                else:
                    ctrl[:6] = q_lift  # 提升
                    ctrl[6:] = [0.3 + 0.2 * force] * 10

        elif stype == "松开/释放":
            ctrl[:6] = q_release
            if not hasattr(self, '_released_once'):
                self._released_once = False
            self._released_once = True
            yao_upper = strategy.get('yao', np.zeros(6))[5]
            ctrl[6:] = [0.15 if yao_upper < 0.5 else 0.0] * 10

        elif stype in ("待机/准备",):
            ctrl[:6] = Q_HOME.copy()
            ctrl[6:] = [0.0] * 10

        elif stype == "缓慢接近/精确对准":
            ctrl[:6] = q_approach
            if planar_dist < 0.2:
                ctrl[2] = min(1.6, q_cur[2] + 0.01)
            ctrl[6:] = [0.1 + 0.1 * force] * 10

        elif stype in ("任务未完成/继续尝试", "non_conflict_grasp"):
            ctrl[:6] = [j1_target, -0.4, 1.3, 0.1, -0.7, 0.0]
            ctrl[6:] = [0.5 + 0.4 * force] * 10

        elif stype == "保持接触/轻微调整":
            ctrl[:6] = q_cur.copy()
            ctrl[4] += 0.01 * math.sin(obs.get('time', 0) * 2)
            ctrl[6:] = [0.3 + 0.2 * force] * 10

        else:
            ctrl[:6] = Q_HOME.copy()
            ctrl[6:] = [0.0] * 10

        return ctrl
