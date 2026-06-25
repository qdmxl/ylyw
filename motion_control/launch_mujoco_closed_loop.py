#!/usr/bin/env python3
"""
YLYW MuJoCo 闭环仿真 + 自适应控制

升级：从开环状态预设 → 闭环物理反馈
- 从MuJoCo物理引擎读取真实状态（qpos/qvel/接触力）
- YLYW推理步态参数
- 髋/膝/踝关节正弦位置控制
- 摔倒检测 + 自适应修正（可选 --adaptive）

用法：
  python3 launch_mujoco_closed_loop.py                    # 静态YLYW闭环
  python3 launch_mujoco_closed_loop.py --adaptive          # 自适应YLYW闭环
  python3 launch_mujoco_closed_loop.py --no-gui            # 无头模式（打印统计）
  python3 launch_mujoco_closed_loop.py --duration 120      # 运行120秒
  python3 launch_mujoco_closed_loop.py --terrain ice       # 冰面地形
"""
import sys, os, time, math, json, argparse
import numpy as np

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')
os.environ.setdefault('EGL_PLATFORM', 'x11')
os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
os.environ.setdefault('GDK_BACKEND', 'x11')
os.environ.setdefault('XDG_SESSION_TYPE', 'x11')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_locomotion import YLYWLocomotionController
from ylyw_adaptive import YLYWAdaptiveController
import mujoco, mujoco.viewer
import warnings
warnings.filterwarnings('ignore')

# MuJoCo XML与人形机器人模型（同launch_mujoco.py）
from launch_mujoco import XML as ROBOT_XML


class MujocoStateExtractor:
    """从MuJoCo data中提取YLYW 6D状态向量"""
    
    def __init__(self, model, data):
        self.model = model
        self.data = data
        self._com_z_filtered = 0.95
        
        # 获取关键body ID
        self.torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'torso')
        self.torso_qpos_addr = model.jnt_qposadr[model.body_jntadr[self.torso_id]]
        
        # 获取执行器名→ID映射
        self.act_map = {
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i
            for i in range(model.nu)
        }
        
    def extract(self, terrain_friction=1.0):
        """
        从MuJoCo物理状态提取 [posture, com_h, force_dist, zmp, disturbance, terrain]
        全部归一化到[0,1]
        """
        # 躯干位置（从xpos）
        torso_pos = self.data.xpos[self.torso_id]
        tx, ty, tz = torso_pos[0], torso_pos[1], torso_pos[2]
        
        # 躯干姿态（从xquat）
        torso_quat = self.data.xquat[self.torso_id]
        qw, qx, qy, qz = torso_quat[0], torso_quat[1], torso_quat[2], torso_quat[3]
        
        # Quaternion → roll, pitch
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx*qx + qy*qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2 * (qw * qy - qz * qx)
        pitch = math.asin(max(-1, min(1, sinp)))
        
        tilt = abs(roll) + abs(pitch)
        posture = max(0.0, 1.0 - tilt / 0.5)
        
        # COM高度
        self._com_z_filtered = 0.9 * self._com_z_filtered + 0.1 * tz
        com_h = max(0.0, min(1.0, self._com_z_filtered / 0.95))
        
        # 力分布（从左右髋执行器力矩差异推断）
        lh_force = abs(self.data.actuator_force[self.act_map['lh_m']])
        rh_force = abs(self.data.actuator_force[self.act_map['rh_m']])
        total_force = lh_force + rh_force + 1e-6
        force_asymmetry = abs(lh_force - rh_force) / total_force
        force_dist = max(0.0, 1.0 - force_asymmetry)
        
        # ZMP裕度（从躯干倾角+速度推断）
        sx_dof = self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        vx = self.data.qvel[sx_dof]
        zmp = max(0.05, 1.0 - tilt * 2.0 - min(abs(vx), 5.0) * 0.1)
        
        # 扰动
        disturbance = min(1.0, tilt * 2.0 + abs(vx - 0.5) * 0.5)
        
        # 地形
        terrain = 0.80 * terrain_friction
        
        return [posture, com_h, force_dist, zmp, disturbance, terrain], {
            'tilt': tilt, 'com_z': tz, 'vx': vx,
            'force_asym': force_asymmetry,
        }


class GaitToJoints:
    """YLYW步态参数 → MuJoCo关节角度目标"""
    
    def __init__(self):
        self.phase = 0.0
        self.prev_gait = None
    
    def get_joint_angles(self, gait_params, dt):
        """
        计算当前时刻的髋/膝/踝目标角度
        
        Returns:
            dict: {'lh': angle, 'lk': angle, 'la': angle, 'rh': ..., 'rk': ..., 'ra': ...}
        """
        speed = gait_params.get('speed', 0.0)
        freq = gait_params.get('freq', 0.0)
        step_h = gait_params.get('step_height', 0.0)
        force_coef = gait_params.get('force_coefficient', 0.5)
        
        if speed < 0.02:
            self.phase = 0.0
            return {'lh': 0, 'lk': 0, 'la': 0, 'rh': 0, 'rk': 0, 'ra': 0}
        
        self.phase += freq * dt * 2 * math.pi
        self.phase %= 2 * math.pi
        
        # 步态幅度
        hip_amp = 0.65 * min(speed, 1.5)
        knee_amp = 0.50 * min(speed, 1.5)
        ankle_amp = 0.08 * hip_amp
        
        # 左右腿相位差π
        l_phase = self.phase
        r_phase = self.phase + math.pi
        
        angles = {
            'lh': hip_amp * math.sin(l_phase),
            'lk': knee_amp * max(0, math.sin(l_phase)),
            'la': -ankle_amp * math.sin(l_phase),
            'rh': hip_amp * math.sin(r_phase),
            'rk': knee_amp * max(0, math.sin(r_phase)),
            'ra': -ankle_amp * math.sin(r_phase),
        }
        
        self.prev_gait = gait_params
        return angles


class MujocoClosedLoopSim:
    """MuJoCo YLYW闭环仿真"""
    
    def __init__(self, adaptive=False, learning_rate=0.05, terrain='normal'):
        self.adaptive = adaptive
        
        # 初始化YLYW控制器
        if adaptive:
            self.controller = YLYWAdaptiveController(learning_rate=learning_rate)
        else:
            self.controller = YLYWLocomotionController()
        
        # MuJoCo模型
        self.model = mujoco.MjModel.from_xml_string(ROBOT_XML)
        self.data = mujoco.MjData(self.model)
        
        # 地形参数
        self.terrain_friction = {'ice': 0.15, 'normal': 1.0, 'rough': 2.0}.get(terrain, 1.0)
        if terrain == 'ice':
            # 修改地面摩擦
            floor_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, 'floor')
            self.model.geom_friction[floor_id] = [self.terrain_friction, 0.01, 0.01]
        
        # 组件
        self.state_extractor = MujocoStateExtractor(self.model, self.data)
        self.gait_to_joints = GaitToJoints()
        
        # 执行器ID
        self.act_ids = {
            mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i
            for i in range(self.model.nu)
        }
        
        # 统计
        self.step_count = 0
        self.sim_time = 0.0
        self.dt = self.model.opt.timestep
        self.current_gait = None
        self.fell_count = 0
        self.fell_history = []
        self.state_history = []
        self.quality_history = []
        
        # 外部扰动
        self.push_force = 0.0
        self.push_schedule = []
    
    def schedule_push(self, sim_time, force, duration):
        """在指定时间注入侧向推力"""
        self.push_schedule.append((sim_time, force, duration))
    
    def step(self):
        """执行一步闭环仿真"""
        # 1. 提取MuJoCo状态
        state_6d, state_extra = self.state_extractor.extract(self.terrain_friction)
        
        # 2. 摔倒检测
        com_z = state_extra['com_z']
        tilt = state_extra['tilt']
        fell = com_z < 0.35 or tilt > 1.2
        
        if fell and not (self.fell_history and self.fell_history[-1]):
            self.fell_count += 1
        self.fell_history.append(fell)
        
        # 3. 构建反馈信号
        feedback = None
        if self.adaptive and self.step_count > 0:
            feedback = {
                'fell': fell,
                'com_deviation': max(0, abs(com_z - 0.95) - 0.05),
                'zmp_margin': state_6d[3],
                'speed_error': abs(state_extra.get('vx', 0) - 
                                   (self.current_gait.get('speed', 0) if self.current_gait else 0)) / 0.5,
                'energy_cost': sum(abs(self.data.ctrl[a]) for a in self.act_ids.values()) / max(1, len(self.act_ids)),
            }
        
        # 4. YLYW推理（10Hz，避免过度推理）
        if self.step_count % 3 == 0:  # dt=0.005s, 3步≈15ms, ~66Hz
            if self.adaptive:
                result = self.controller.step(np.array(state_6d), feedback=feedback)
                if feedback:
                    self.controller.give_feedback(feedback)
            else:
                result = self.controller.infer(np.array(state_6d), verbose=False)
            
            if result:
                self.current_gait = result
        
        # 5. 步态→关节角度→执行器力矩
        gait = self.current_gait or {'speed': 0, 'freq': 0, 'step_height': 0, 'force_coefficient': 0.5}
        joint_angles = self.gait_to_joints.get_joint_angles(gait, self.dt)
        
        # 清零所有执行器，然后设置目标位置
        for a in self.act_ids.values():
            self.data.ctrl[a] = 0
        
        # 对髋/膝/踝关节设置位置控制
        for joint_name, target_angle in joint_angles.items():
            motor_name = f'{joint_name}_m'
            if motor_name in self.act_ids:
                self.data.ctrl[self.act_ids[motor_name]] = target_angle
        
        # 6. 躯干滑动（跑步机效果）
        sx_dof = self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        speed = gait.get('speed', 0)
        target_speed = speed * 1.5
        self.data.qvel[sx_dof] = target_speed
        
        # 跑步机标记滑动
        for i in range(1, 11):
            m_jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f'm{i}')
            mdof = self.model.jnt_dofadr[m_jid]
            mqpos = self.model.jnt_qposadr[m_jid]
            self.data.qvel[mdof] = -speed * 6
            if self.data.qpos[mqpos] < -12:
                self.data.qpos[mqpos] += 20
        
        # 7. 外部扰动注入
        sx_dof = self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        if self.push_schedule:
            t, force, dur = self.push_schedule[0]
            if self.sim_time >= t and self.sim_time < t + dur:
                self.data.qvel[sx_dof] += force * 0.001 * math.sin(self.sim_time * 20)
            elif self.sim_time >= t + dur:
                self.push_schedule.pop(0)
        
        # 8. MuJoCo物理步进
        mujoco.mj_step(self.model, self.data)
        
        # 9. 记录
        quality = 1.0 - (0.5 * float(fell) + 0.3 * tilt + 0.2 * abs(com_z - 0.95))
        self.quality_history.append(quality)
        self.state_history.append({
            't': round(self.sim_time, 3),
            'state': [round(v, 3) for v in state_6d],
            'fell': fell,
            'quality': round(quality, 3),
        })
        
        self.step_count += 1
        self.sim_time += self.dt
        
        return state_6d, self.current_gait, fell, quality
    
    def get_summary(self):
        """获取运行统计"""
        is_adaptive = isinstance(self.controller, YLYWAdaptiveController)
        stats = {}
        if hasattr(self.controller, 'get_stats'):
            stats = self.controller.get_stats()
        
        return {
            'adaptive': is_adaptive,
            'total_steps': self.step_count,
            'sim_time': round(self.sim_time, 1),
            'fell_count': self.fell_count,
            'avg_quality': round(np.mean(self.quality_history), 3) if self.quality_history else 0,
            'inferences': stats.get('total_steps', self.step_count),
            'hexagram_diversity': stats.get('hexagram_diversity', 0),
            'adaptations': self.controller.total_adaptations if is_adaptive else 0,
        }


def run_simulation_demo(adaptive=False, duration=60, terrain='normal', learning_rate=0.05):
    """
    演示模式：用预设场景序列驱动YLYW推理，但反馈来自MuJoCo物理
    
    这个模式的核心价值：
    - 推理输入 = demo状态序列（模拟IMU读数）
    - 反馈信号 = MuJoCo真实物理（实际摔倒、COM偏差、关节力矩）
    - 如果步态选择不当（如状态差但选了高速卦），MuJoCo会真实摔倒
    - 自适应控制器可以检测摔倒→诊断→修正
    """
    sim = MujocoClosedLoopSim(adaptive=adaptive, learning_rate=learning_rate, terrain=terrain)
    
    # 开环demo状态序列（用于驱动YLYW推理）
    demo_seq = [
        (0,  "初始站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
        (10, "开始慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
        (20, "加速行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
        (30, "快速小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
        (40, "全力奔跑", [0.48,0.75,0.78,0.42,0.62,0.78]),
        (50, "突然推搡", [0.18,0.30,0.25,0.14,0.82,0.55]),
        (58, "放松恢复", [0.55,0.42,0.48,0.38,0.50,0.60]),
        (66, "爬坡前进", [0.48,0.42,0.52,0.32,0.45,0.18]),
        (74, "回到平路", [0.70,0.72,0.68,0.65,0.22,0.78]),
        (82, "减速站立", [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    demo_idx = 0
    
    model_name = "自适应" if adaptive else "静态"
    print(f"{'='*60}")
    print(f"YLYW MuJoCo 演示 ({model_name}YLYW)")
    print(f"地形: {terrain} | 时长: {duration}s")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<10} {'速':>4} {'摔倒':>4} {'修正'}")
    print("-" * 56)
    
    last_log_time = -99
    
    with mujoco.viewer.launch_passive(sim.model, sim.data) as viewer:
        viewer.cam.distance = 2.5
        viewer.cam.azimuth = 50
        viewer.cam.elevation = -12
        
        while viewer.is_running() and sim.sim_time < duration:
            # 从demo序列获取当前"期望"状态
            while demo_idx+1 < len(demo_seq) and sim.sim_time >= demo_seq[demo_idx+1][0]:
                demo_idx += 1
            demo_name, demo_state = demo_seq[demo_idx][1], demo_seq[demo_idx][2]
            
            # 读取MuJoCo真实状态作为反馈
            mu_state, mu_extra = sim.state_extractor.extract(sim.terrain_friction)
            com_z = mu_extra['com_z']
            tilt = mu_extra['tilt']
            fell = com_z < 0.35 or tilt > 1.2
            
            # 构建反馈
            feedback = None
            if adaptive and sim.step_count > 0:
                feedback = {
                    'fell': fell,
                    'com_deviation': max(0, abs(com_z - 0.95) - 0.05),
                    'zmp_margin': mu_state[3],
                    'speed_error': 0,
                    'energy_cost': sum(abs(sim.data.ctrl[a]) for a in sim.act_ids.values()) / 6,
                }
            
            # YLYW推理（输入=demo状态，反馈=MuJoCo物理）
            if sim.step_count % 3 == 0:
                if adaptive:
                    result = sim.controller.step(np.array(demo_state), feedback=feedback)
                    if feedback:
                        sim.controller.give_feedback(feedback)
                else:
                    result = sim.controller.infer(np.array(demo_state), verbose=False)
                if result:
                    sim.current_gait = result
            
            # 步态→关节角度
            gait = sim.current_gait or {'speed': 0, 'freq': 0, 'step_height': 0, 'force_coefficient': 0.5}
            joint_angles = sim.gait_to_joints.get_joint_angles(gait, sim.dt)
            
            # 关节控制
            for a in sim.act_ids.values():
                sim.data.ctrl[a] = 0
            for joint_name, target_angle in joint_angles.items():
                motor_name = f'{joint_name}_m'
                if motor_name in sim.act_ids:
                    sim.data.ctrl[sim.act_ids[motor_name]] = target_angle
            
            # 躯干滑动
            sx_dof = sim.model.jnt_dofadr[mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
            speed = gait.get('speed', 0)
            sim.data.qvel[sx_dof] = speed * 1.5
            
            # 跑步机标记
            for i in range(1, 11):
                m_jid = mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_JOINT, f'm{i}')
                mdof = sim.model.jnt_dofadr[m_jid]
                mqpos = sim.model.jnt_qposadr[m_jid]
                sim.data.qvel[mdof] = -speed * 6
                if sim.data.qpos[mqpos] < -12:
                    sim.data.qpos[mqpos] += 20
            
            # MuJoCo物理步进
            mujoco.mj_step(sim.model, sim.data)
            
            # 摄像头跟随
            sx_qpos = sim.model.jnt_qposadr[mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
            viewer.cam.lookat = [sim.data.qpos[sx_qpos], 0, 0.9]
            
            # 摔倒计数
            if fell and not (sim.fell_history and sim.fell_history[-1]):
                sim.fell_count += 1
            sim.fell_history.append(fell)
            
            # 日志
            if sim.sim_time - last_log_time >= 1.0:
                hex_name = gait['hexagram_name'] if gait else 'N/A'
                gait_name_s = gait['gait_name'] if gait else 'N/A'
                speed_s = gait['speed'] if gait else 0
                correction = ''
                if adaptive and hasattr(sim.controller, 'last_diagnosis') and sim.controller.last_diagnosis:
                    d = sim.controller.last_diagnosis
                    correction = f"⚡{d['severity'][:4]}"
                fell_mark = '💀' if fell else '  '
                print(f"{sim.sim_time:>4.1f}s {demo_name:<8} {hex_name:<10} {gait_name_s:<10} "
                      f"{speed_s:>3.2f} {fell_mark:>4} {correction}")
                last_log_time = sim.sim_time
            
            sim.step_count += 1
            sim.sim_time += sim.dt
            viewer.sync()
            time.sleep(0.005)
    
    summary = sim.get_summary()
    print(f"\n演示汇总: 摔倒{summary['fell_count']}次 | 修正{summary['adaptations']}次")
    if adaptive and hasattr(sim.controller, 'get_adaptation_summary'):
        print(sim.controller.get_adaptation_summary())
    return summary, sim


def run_no_gui(adaptive=False, duration=30, terrain='normal', learning_rate=0.05):
    """无头模式：只打印统计"""
    sim = MujocoClosedLoopSim(adaptive=adaptive, learning_rate=learning_rate, terrain=terrain)
    
    warmup_steps = 200
    while sim.sim_time < duration:
        if sim.step_count < warmup_steps:
            sim.data.ctrl[:] = 0
            mujoco.mj_step(sim.model, sim.data)
            sim.step_count += 1
            sim.sim_time += sim.dt
            continue
        
        state, gait, fell, quality = sim.step()
        
        if sim.step_count % 600 == 0:  # ~3s
            gait_name = gait['gait_name'] if gait else 'N/A'
            hex_name = gait['hexagram_name'] if gait else 'N/A'
            print(f"{sim.sim_time:>5.1f}s {hex_name:<8} {gait_name:<10} "
                  f"fell={fell} q={quality:.3f}")
    
    summary = sim.get_summary()
    print(f"\n摔倒{summary['fell_count']}次 | 平均质量{summary['avg_quality']:.3f}")
    return summary, sim


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW MuJoCo闭环仿真')
    parser.add_argument('--adaptive', action='store_true', help='启用自适应YLYW')
    parser.add_argument('--no-gui', action='store_true', help='无头模式')
    parser.add_argument('--duration', type=float, default=60, help='仿真时长(秒)')
    parser.add_argument('--terrain', choices=['normal', 'ice', 'rough'], default='normal')
    parser.add_argument('--lr', type=float, default=0.05, help='自适应学习率')
    parser.add_argument('--demo', action='store_true', default=True, help='演示模式（预设场景+YLYW，反馈来自MuJoCo物理）')
    parser.add_argument('--closed-loop', action='store_true', help='真闭环模式（从MuJoCo状态驱动YLYW）')
    parser.add_argument('--compare', action='store_true', help='对比静态vs自适应')
    args = parser.parse_args()
    
    if args.compare:
        print("=" * 60)
        print("对比实验: 静态YLYW vs 自适应YLYW")
        print("=" * 60)
        
        print("\n--- 静态YLYW ---")
        s_summary, _ = run_simulation_demo(adaptive=False, duration=args.duration,
                                   terrain=args.terrain, learning_rate=args.lr)
        
        print("\n--- 自适应YLYW ---")
        a_summary, _ = run_simulation_demo(adaptive=True, duration=args.duration,
                                   terrain=args.terrain, learning_rate=args.lr)
        
        print(f"\n{'='*60}")
        print(f"对比结果")
        print(f"{'指标':<20} {'静态':>10} {'自适应':>10}")
        print('-' * 45)
        print(f"{'摔倒次数':<20} {s_summary['fell_count']:>10} {a_summary['fell_count']:>10}")
        print(f"{'平均质量':<20} {s_summary['avg_quality']:>10.3f} {a_summary['avg_quality']:>10.3f}")
        print(f"{'自适应修正':<20} {'-':>10} {a_summary['adaptations']:>10}")
    
    elif args.no_gui:
        run_simulation_demo(adaptive=args.adaptive, duration=args.duration,
                            terrain=args.terrain, learning_rate=args.lr)
    elif args.closed_loop:
        from launch_mujoco_closed_loop import run_simulation
        run_simulation(adaptive=args.adaptive, duration=args.duration,
                        terrain=args.terrain, learning_rate=args.lr)
    else:
        run_simulation_demo(adaptive=args.adaptive, duration=args.duration,
                            terrain=args.terrain, learning_rate=args.lr)
