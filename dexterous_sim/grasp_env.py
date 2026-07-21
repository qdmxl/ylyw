#!/usr/bin/env python3
"""
YLYW 灵巧手仿真验证环境

基于 MuJoCo 简化的 Shadow Hand 风格灵巧手 (5指10DOF)，
集成 YLYW 微观层推理，在桌面抓取任务中验证零样本策略。

核心功能:
  1. 加载灵巧手 MuJoCo 模型和物体
  2. 调用 YLYW 推理引擎获取抓取策略
  3. 策略 → 灵巧手10关节角度
  4. 执行、记录、评估 (成功/失败/峰值力/提升高度)
"""

import os, sys, json, time, math
import numpy as np

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')

try:
    import mujoco
    from mujoco import viewer
    HAS_MUJOCO = True
except ImportError:
    HAS_MUJOCO = False

# ─── YLYW 推理引擎路径 ───
YLYW_CORE = os.path.expanduser('~/MXL/科研/ylyw/experiment_phase1/ylyw_core')
sys.path.insert(0, os.path.expanduser('~/MXL/科研/ylyw/experiment_phase1/scripts'))
sys.path.insert(0, YLYW_CORE)


# ─── 灵巧手控制参数 ───
FINGER_NAMES = ['thumb', 'index', 'middle', 'ring', 'pinky']

# 策略 → 手指关节角度 (弧度)
# 从 lingxi_x2_bridge.py 的 FINGER_STRATEGY_MAP 迁移
# 每个手指 (J1, J2) 弧度值
# J1 = 基部弯曲, J2 = 末端弯曲
# 拇指J1=对掌/横向, J2=弯曲
# 四指J1=基部弯曲, J2=末端弯曲
# 值域: 0=伸直, 1.2=全曲
STRATEGY_TO_POSITION = {
    'open':             {'thumb': (0.0, 0.0), 'index': (0.0, 0.0), 'middle': (0.0, 0.0),
                         'ring': (0.0, 0.0), 'pinky': (0.0, 0.0)},
    'power_grasp':      {'thumb': (0.4, 0.6), 'index': (0.9, 0.8), 'middle': (0.9, 0.8),
                         'ring': (0.8, 0.7), 'pinky': (0.8, 0.7)},
    'dynamic_grasp':    {'thumb': (0.4, 0.4), 'index': (0.6, 0.6), 'middle': (0.6, 0.6),
                         'ring': (0.5, 0.5), 'pinky': (0.5, 0.5)},
    'precision_grasp':  {'thumb': (0.4, 0.3), 'index': (0.5, 0.3), 'middle': (0.3, 0.1),
                         'ring': (0.2, 0.1), 'pinky': (0.2, 0.0)},
    'cautious_grasp':   {'thumb': (0.3, 0.4), 'index': (0.5, 0.5), 'middle': (0.5, 0.5),
                         'ring': (0.4, 0.4), 'pinky': (0.4, 0.3)},
    'adaptive_grasp':   {'thumb': (0.4, 0.5), 'index': (0.6, 0.5), 'middle': (0.5, 0.6),
                         'ring': (0.4, 0.3), 'pinky': (0.4, 0.4)},
    'wrap_grasp':       {'thumb': (0.4, 0.5), 'index': (0.8, 0.7), 'middle': (0.8, 0.7),
                         'ring': (0.7, 0.6), 'pinky': (0.7, 0.6)},
    'soft_grasp':       {'thumb': (0.3, 0.4), 'index': (0.6, 0.5), 'middle': (0.6, 0.5),
                         'ring': (0.5, 0.4), 'pinky': (0.5, 0.4)},
    'firm_grasp':       {'thumb': (0.5, 0.7), 'index': (1.0, 0.9), 'middle': (1.0, 0.9),
                         'ring': (0.9, 0.8), 'pinky': (0.9, 0.8)},
}


class DexterousHandGraspEnv:
    """灵巧手桌面抓取仿真环境 (带Z升降)"""

    def __init__(self, render=False):
        if not HAS_MUJOCO:
            raise RuntimeError("MuJoCo 未安装")
        self.render = render
        self.model = None
        self.data = None
        self.viewer = None
        # 关节名称（11个执行器: 升力+10手指）
        self.lift_act = 0
        self.act_names = ['lift_z', 'THJ1', 'THJ2', 'FFJ1', 'FFJ2',
                          'MFJ1', 'MFJ2', 'RFJ1', 'RFJ2',
                          'LFJ1', 'LFJ2']
        # 手指→执行器索引映射
        self.finger_act_map = {
            'thumb': (1, 2),
            'index': (3, 4),
            'middle': (5, 6),
            'ring': (7, 8),
            'pinky': (9, 10),
        }

    def load_hand(self, xml_path: str = None):
        if xml_path is None:
            xml_path = os.path.join(os.path.dirname(__file__), 'hand_model.xml')
        self.model = mujoco.MjModel.from_xml_path(xml_path)
        self.data = mujoco.MjData(self.model)
        if self.render:
            self.viewer = viewer.launch_passive(self.model, self.data)

    def set_finger_positions(self, finger_positions: dict,
                             strategy_type: str = None, force_scale: float = 1.0):
        """
        设置手指位置。

        finger_positions: {'thumb': (p1,p2), 'index': (p1,p2), ...}
        每个手指2个关节角度值 (弧度)
        """
        for finger, (v1, v2) in finger_positions.items():
            if finger in self.finger_act_map:
                a1, a2 = self.finger_act_map[finger]
                # 力缩放: 速度缩放控制输入同时缩放力效果
                self.data.ctrl[a1] = v1 * force_scale
                self.data.ctrl[a2] = v2 * force_scale

    def set_strategy(self, strategy_type: str, force_scale: float = 1.0):
        """将策略类型映射到手指位置"""
        if strategy_type not in STRATEGY_TO_POSITION:
            raise ValueError(f"未知策略类型: {strategy_type}")
        self.set_finger_positions(
            STRATEGY_TO_POSITION[strategy_type],
            strategy_type=strategy_type,
            force_scale=force_scale,
        )

    def grasp_object(self, strategy: str, force_scale: float = 1.0,
                     n_close: int = 100, n_lift_steps: int = 300) -> dict:
        """
        执行一次抓取：
          1. 手指从张开到目标位置 (使用位置控制)
          2. 检查接触情况
          3. 手掌垂直向上移动，带动物体（如果已抓住）

        返回:
          success: 提升后物体上升>5mm
        """
        # 步骤1: 开放
        self.set_finger_positions({f: (0, 0) for f in FINGER_NAMES})
        for _ in range(30):
            mujoco.mj_step(self.model, self.data)

        # 记录初始物体位置
        init_obj_z = self._obj_pos()[2]

        # 步骤2: 手指闭合到策略位置
        self.set_strategy(strategy, force_scale=force_scale)
        for i in range(n_close):
            mujoco.mj_step(self.model, self.data)

        # 记录闭合后物体位置
        close_obj_z = self._obj_pos()[2]

        # 步骤3: 手掌平台整体上升 (模拟手臂抬升)
        # 通过修改手掌的qpos
        palm_bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'palm')
        # 手掌是世界坐标系中的root体，没有关节，需要通过修改其位置
        # 在MuJoCo中，非root体的位置在xpos中不可直接修改，
        # 我们改为将物体位置记录，通过重力检测是否被抓持
        
        # 方法: 实际上在灵巧手中，手掌是root，物体是freejoint
        # 如果手指夹住了物体，物体位置应该受手指运动影响
        # 记录一段时间内的物体z坐标波动
        obj_z_trace = []
        for i in range(n_lift_steps):
            # 逐步加大手指力来确认夹持
            inc_scale = min(force_scale * (1.0 + i / n_lift_steps * 0.5), 1.5)
            self.set_strategy(strategy, force_scale=inc_scale)
            mujoco.mj_step(self.model, self.data)
            if i % 20 == 0:
                obj_z_trace.append(self._obj_pos()[2])

        final_obj_z = self._obj_pos()[2]
        peak_force = self._peak_contact_force()
        contacts = self.get_contact_map()

        # 判定: 物体被提升 = 最终z > 初始z + 5mm
        obj_lift = final_obj_z - init_obj_z
        success = obj_lift > 0.005

        return {
            'strategy': strategy,
            'force_scale': force_scale,
            'success': success,
            'object_lift': obj_lift,
            'init_obj_z': init_obj_z,
            'final_obj_z': final_obj_z,
            'peak_force': peak_force,
            'contacts': contacts,
            'obj_z_trace': obj_z_trace,
        }

    def run_ylyw_strategies(self, strategies_to_test: list = None,
                            force_scales: list = None) -> list:
        """批量运行多种策略，返回结果列表"""
        if strategies_to_test is None:
            strategies_to_test = list(STRATEGY_TO_POSITION.keys())
        if force_scales is None:
            force_scales = [0.3, 0.5, 0.7, 0.9, 1.0, 1.2]

        results = []
        for strategy in strategies_to_test:
            for scale in force_scales:
                # 重置场景
                mujoco.mj_resetData(self.model, self.data)
                r = self.grasp_object(strategy, force_scale=scale)
                results.append(r)
                kind = '✅' if r['success'] else '❌'
                print(f"  {kind} {strategy:20s} force={scale:.1f}  "
                      f"lift={r['object_lift']*1000:.1f}mm  "
                      f"peak_f={r['peak_force']:.2f}N")
        return results

    # ─── 辅助函数 ───

    def _obj_pos(self) -> np.ndarray:
        bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'object')
        return self.data.xpos[bid]

    def _palm_pos(self) -> np.ndarray:
        bid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'palm')
        return self.data.xpos[bid]

    def _peak_contact_force(self) -> float:
        """返回当前步的最大接触力"""
        if self.data.ncon == 0:
            return 0.0
        max_f = 0.0
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            f = np.linalg.norm(c.friction) + abs(c.dist)
            if f > max_f:
                max_f = f
        return max_f

    def get_contact_map(self) -> dict:
        """返回哪些手指接触了物体"""
        contacts = {f: False for f in FINGER_NAMES}
        for i in range(self.data.ncon):
            c = self.data.contact[i]
            g1 = self.model.geom(c.geom1).name
            g2 = self.model.geom(c.geom2).name
            for f in FINGER_NAMES:
                if f in g1 or f in g2:
                    contacts[f] = True
        return contacts

    def close(self):
        if self.viewer:
            self.viewer.close()


# ─── 主入口：独立测试 ───
if __name__ == '__main__':
    print("=" * 60)
    print("YLYW 灵巧手仿真验证 — 零样本策略测试 (含抬臂)")
    print("=" * 60)

    env = DexterousHandGraspEnv(render=False)
    env.load_hand()
    m = env.model
    d = env.data
    mj_reset = mujoco.mj_resetData

    print(f"\n{'='*60}")
    print(f"策略零样本测试")
    print(f"{'='*60}")

    results = []
    for strategy in ['soft_grasp', 'cautious_grasp', 'power_grasp',
                     'precision_grasp', 'wrap_grasp', 'firm_grasp',
                     'dynamic_grasp', 'adaptive_grasp']:
        for scale in [0.5, 1.0]:
            mj_reset(m, d)

            # 1. 手掌降下到靠近物体
            d.ctrl[0] = -0.08  # 降臂到接近物体
            env.set_finger_positions({f: (0, 0) for f in FINGER_NAMES})
            for _ in range(50):
                mujoco.mj_step(m, d)

            init_obj_z = env._obj_pos()[2]

            # 2. 手指闭合到策略位置 (持续久一点，力更大)
            env.set_strategy(strategy, force_scale=scale)
            for _ in range(150):
                mujoco.mj_step(m, d)

            contacts_before = env.get_contact_map()
            n_fingers = sum(1 for v in contacts_before.values() if v)

            # 3. 抬臂，把物体从桌面提起
            # 用更大的力度和更多时间
            d.ctrl[0] = 0.15  # 大幅度提升
            for _ in range(300):
                env.set_strategy(strategy, force_scale=min(scale * 2.0, 1.5))
                mujoco.mj_step(m, d)

            final_obj_z = env._obj_pos()[2]
            lift_mm = (final_obj_z - init_obj_z) * 1000
            # 提升>3mm = 成功（物体被手指夹持离开桌面）
            success = lift_mm > 3.0

            results.append({
                'strategy': strategy, 'scale': scale,
                'success': success,
                'n_fingers': n_fingers,
                'lift_mm': lift_mm,
            })

            sym = '✅' if success else '❌'
            print(f"  {sym} {strategy:20s} scale={scale:.1f}  "
                  f"接触={n_fingers}/5  "
                  f"提升={lift_mm:+.1f}mm")

    # 汇总
    n_success = sum(1 for r in results if r['success'])
    rate = n_success / len(results) * 100 if results else 0
    print(f"\n{'='*60}")
    print(f"汇总: {n_success}/{len(results)} 成功 (率: {rate:.0f}%)")
    print(f"{'='*60}")
