#!/usr/bin/env python3
"""
YLYW → 灵犀X2 速度控制仿真
PyBullet 运动学动画 + 模拟IMU反馈 + YLYW闭环推理

数据流:
  机器人运动状态 → 模拟IMU(accel+gyro) → 6D状态向量 → YLYW推理
  → 步态参数 → McLocomotionVelocity(forward/lateral/angular)
  → 更新机器人位姿

与真实灵犀X2的接口完全一致:
  - IMU: orientation + angular_velocity + linear_acceleration
  - 输出: forward/lateral/angular velocity (m/s, rad/s)
"""
import sys, os, time, math, numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ylyw_locomotion import YLYWLocomotionController
import pybullet as p, pybullet_data


# ============================================================
# IMU 模拟器
# ============================================================
class SimulatedIMU:
    """
    从机器人运动状态模拟 6 轴 IMU 读数
    
    模拟灵犀X2胸部IMU (/aima/hal/imu/chest/state)
    输出格式: sensor_msgs/Imu
      - orientation (quaternion): 躯干姿态
      - angular_velocity (rad/s): 三轴角速度
      - linear_acceleration (m/s^2): 三轴加速度
    """
    
    def __init__(self):
        self.prev_orientation = None  # euler [roll, pitch, yaw]
        self.prev_time = None
        self.dt = 1.0 / 50.0  # 50Hz
    
    def read(self, robot_com, robot_orientation, robot_velocity, phase, sim_time, gait_info=None, disturbance_force=0.0):
        """
        模拟 IMU 读数
        
        Args:
            robot_com: [x, y, z] 质心位置
            robot_orientation: [roll, pitch, yaw] 躯干姿态 (radians)
            robot_velocity: [vx, vy, vz] 质心速度
            phase: 步态相位
            sim_time: 仿真时间
            gait_info: dict {gait_name, speed} 当前步态信息
            disturbance_force: 外部扰动力(N)
        
        Returns:
            imu_data: dict 含 orientation, angular_velocity, linear_acceleration
        """
        speed = gait_info.get('speed', 0.0) if gait_info else 0.0
        gait_name = gait_info.get('gait_name', '静止站立') if gait_info else '静止站立'
        
        # 不同步态的身体摆动参数
        if speed < 0.01:
            # 静止站立: 微小姿态漂移
            sway_roll = 0.003 * math.sin(sim_time * 0.5)
            sway_pitch = 0.002 * math.cos(sim_time * 0.7 + 0.5)
            vert_osc = 0.0
            ang_osc = 0.0
        elif speed < 0.3:
            # 慢走: 中等摆动
            sway_roll = 0.04 * math.sin(phase)
            sway_pitch = 0.03 * math.sin(phase + math.pi/4)
            vert_osc = 0.8 * math.sin(phase * 2)
            ang_osc = 0.3
        elif speed < 0.5:
            # 正常行走: 明显摆动
            sway_roll = 0.09 * math.sin(phase)
            sway_pitch = 0.07 * math.sin(phase + math.pi/4)
            vert_osc = 2.0 * math.sin(phase * 2)
            ang_osc = 0.6
        elif speed < 0.8:
            # 快走/小跑: 大幅度摆动
            sway_roll = 0.13 * math.sin(phase)
            sway_pitch = 0.10 * math.sin(phase + math.pi/3)
            vert_osc = 3.5 * math.sin(phase * 2)
            ang_osc = 1.2
        else:
            # 奔跑: 剧烈摆动
            sway_roll = 0.15 * math.sin(phase)
            sway_pitch = 0.12 * math.sin(phase + math.pi/3)
            vert_osc = 5.0 * math.sin(phase * 2)
            ang_osc = 1.5
        
        # 外部扰动叠加
        if disturbance_force > 0:
            sway_roll += disturbance_force * 0.0005 * math.sin(sim_time * 8)
            vert_osc += disturbance_force * 0.01 * abs(math.sin(sim_time * 10))
        
        roll = robot_orientation[0] + sway_roll
        pitch = robot_orientation[1] + sway_pitch
        
        # orientation → quaternion (Euler ZYX)
        cr, sr = math.cos(roll*0.5), math.sin(roll*0.5)
        cp, sp = math.cos(pitch*0.5), math.sin(pitch*0.5)
        cy, sy = math.cos(robot_orientation[2]*0.5), math.sin(robot_orientation[2]*0.5)
        
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy
        qw = cr * cp * cy + sr * sp * sy
        
        # 角速度: 从摆动参数直接计算 (gyro模拟)
        # 摆动 = A*sin(ωt), 角速度 = A*ω*cos(ωt)
        if speed < 0.01:
            ang_vel_x = 0.003 * 0.5 * math.cos(sim_time * 0.5)
            ang_vel_y = -0.002 * 0.7 * math.sin(sim_time * 0.7 + 0.5)
            ang_vel_z = 0.0
        elif speed < 0.3:
            ft = 1.2 + speed * 0.5
            ang_vel_x = 0.04 * ft * math.cos(phase)
            ang_vel_y = 0.03 * ft * math.cos(phase + math.pi/4)
            ang_vel_z = 0.0
        elif speed < 0.5:
            ft = 1.6 + speed * 0.5
            ang_vel_x = 0.09 * ft * math.cos(phase)
            ang_vel_y = 0.07 * ft * math.cos(phase + math.pi/4)
            ang_vel_z = 0.0
        elif speed < 0.8:
            ft = 2.0 + speed * 0.5
            ang_vel_x = 0.13 * ft * math.cos(phase)
            ang_vel_y = 0.10 * ft * math.cos(phase + math.pi/3)
            ang_vel_z = 0.0
        else:
            ft = 3.0 + speed * 0.5
            ang_vel_x = 0.15 * ft * math.cos(phase)
            ang_vel_y = 0.12 * ft * math.cos(phase + math.pi/3)
            ang_vel_z = 0.0
        
        if disturbance_force > 0:
            ang_vel_x += disturbance_force * 0.002 * math.cos(sim_time * 8) * 8
            ang_vel_y += disturbance_force * 0.002 * math.sin(sim_time * 10) * 10
        
        # 加速度
        ax = 0.0
        ay = 0.0
        az = 9.81 + vert_osc  # 重力 + 步态垂直振动
        
        if disturbance_force > 0:
            ay += disturbance_force * 0.05 * math.sin(sim_time * 12)
        
        self.prev_orientation = [roll, pitch, robot_orientation[2]]
        self.prev_time = sim_time
        
        return {
            'orientation':      {'x': qx, 'y': qy, 'z': qz, 'w': qw},
            'angular_velocity': {'x': ang_vel_x, 'y': ang_vel_y, 'z': ang_vel_z},
            'linear_acceleration': {'x': ax, 'y': ay, 'z': az},
        }


# ============================================================
# IMU → 6D 状态映射器
# ============================================================
class IMUtoState:
    """将 IMU 数据映射为 YLYW 6 维状态向量 [0,1]"""
    
    def __init__(self):
        self.filtered_accel_z = 9.81  # 低通滤波后的Z加速度
    
    def convert(self, imu_data):
        """
        IMU → [posture, com_h, force_dist, zmp, disturbance, terrain]
        全部归一化到 [0,1]
        """
        # 姿态稳定性: 从 orientation quaternion 计算倾角
        qx, qy, qz, qw = [imu_data['orientation'][k] for k in ['x','y','z','w']]
        # ZYX Euler: roll, pitch
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx*qx + qy*qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        sinp = 2 * (qw * qy - qz * qx)
        pitch = math.asin(max(-1, min(1, sinp)))
        
        tilt = abs(roll) + abs(pitch)
        posture = max(0, 1.0 - tilt / 0.5)  # 倾角 0.5rad ≈ 28.6° 完全不稳定
        
        # 质心高度: 从 Z 加速度推断
        az = imu_data['linear_acceleration']['z']
        self.filtered_accel_z = 0.9 * self.filtered_accel_z + 0.1 * az
        com_h = max(0, min(1, self.filtered_accel_z / 9.81))
        
        # 力分布均匀性: 从步态对称性推断（加速度X/Y方差）
        ax, ay = imu_data['linear_acceleration']['x'], imu_data['linear_acceleration']['y']
        lateral_asym = abs(ay) / 9.81  # 侧向不对称度
        force_dist = max(0, 1.0 - lateral_asym * 5)
        
        # ZMP 裕度: 从倾角+角速度推断
        ang_vel = imu_data['angular_velocity']
        ang_mag = math.sqrt(ang_vel['x']**2 + ang_vel['y']**2 + ang_vel['z']**2)
        zmp = max(0.05, 1.0 - tilt * 2.0 - min(ang_mag, 5.0) * 0.1)
        
        # 扰动: 从角速度+加速度变化率
        disturbance = min(1.0, min(ang_mag, 5.0) * 0.15 + abs(az - 9.81) / 15.0)
        
        # 地形: 从加速度高频分量推断（间接）
        terrain = 0.8  # 默认平坦
        
        return [posture, com_h, force_dist, zmp, disturbance, terrain]


# ============================================================
# YLYW 步态 → 灵犀X2 速度指令映射
# ============================================================
class GaitToVelocity:
    """
    将 YLYW 步态参数映射为灵犀X2 McLocomotionVelocity 消息
    
    灵犀X2 速度控制接口:
      - forward_velocity:  前进速度 (m/s), 范围 [0.2, 1.0]
      - lateral_velocity:  侧向速度 (m/s), 范围 [0.2, 1.0]  
      - angular_velocity:  转向速度 (rad/s), 范围 [0.1, 1.0]
    
    注意: MC 有启动阈值，<0.005 视为停止
    """
    
    # YLYW步态→灵犀X2速度映射表
    GAIT_SPEED_MAP = {
        '静止站立':   {'forward': 0.0, 'lateral': 0.0, 'angular': 0.0},
        '极慢爬行':   {'forward': 0.0, 'lateral': 0.0, 'angular': 0.0},
        '慢走':       {'forward': 0.25, 'lateral': 0.0, 'angular': 0.0},
        '谨慎行走':   {'forward': 0.22, 'lateral': 0.0, 'angular': 0.0},
        '过渡缓冲':   {'forward': 0.22, 'lateral': 0.0, 'angular': 0.0},
        '正常行走':   {'forward': 0.45, 'lateral': 0.0, 'angular': 0.0},
        '快速行走':   {'forward': 0.7, 'lateral': 0.0, 'angular': 0.0},
        '小跑步态':   {'forward': 0.85, 'lateral': 0.0, 'angular': 0.0},
        '奔跑':       {'forward': 1.0, 'lateral': 0.0, 'angular': 0.0},
        '爬坡步态':   {'forward': 0.25, 'lateral': 0.0, 'angular': 0.0},
        '下坡步态':   {'forward': 0.22, 'lateral': 0.0, 'angular': 0.0},
        '恢复步态':   {'forward': 0.0, 'lateral': 0.0, 'angular': 0.0},
        '自适应步态': {'forward': 0.30, 'lateral': 0.0, 'angular': 0.0},
        '转向步态':   {'forward': 0.0, 'lateral': 0.0, 'angular': 0.3},
    }
    
    @classmethod
    def convert(cls, gait_params):
        """YLYW步态 → 速度指令"""
        gait_name = gait_params.get('gait_name', '静止站立')
        velocity = cls.GAIT_SPEED_MAP.get(gait_name, {'forward': 0.0, 'lateral': 0.0, 'angular': 0.0})
        
        # 力系数调制速度
        force_coef = gait_params.get('force_coefficient', 0.5)
        
        return {
            'forward_velocity': velocity['forward'] * force_coef,
            'lateral_velocity': velocity['lateral'] * force_coef,
            'angular_velocity': velocity['angular'] * force_coef,
        }


# ============================================================
# PyBullet 仿真
# ============================================================
def build_robot():
    """简化双足机器人模型"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.loadURDF("plane.urdf")
    
    bodies = {}
    C_TORSO = [0.4, 0.5, 0.7, 1]
    C_HEAD = [0.5, 0.6, 0.8, 1]
    C_LEG = [0.3, 0.4, 0.6, 1]
    C_FOOT = [0.2, 0.3, 0.5, 1]
    
    hv = p.createVisualShape(p.GEOM_SPHERE, radius=0.08, rgbaColor=C_HEAD)
    bodies['head'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=hv, basePosition=[0, 0, 1.30])
    
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.15, 0.12, 0.28], rgbaColor=C_TORSO)
    bodies['torso'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv, basePosition=[0, 0, 0.92])
    
    for side, x_sign in [('l', 0.08), ('r', -0.08)]:
        tv2 = p.createVisualShape(p.GEOM_CYLINDER, radius=0.05, length=0.32, rgbaColor=C_LEG)
        bodies[f'thigh_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv2,
                                                     basePosition=[x_sign, 0, 0.60])
        sv = p.createVisualShape(p.GEOM_CYLINDER, radius=0.045, length=0.30, rgbaColor=C_LEG)
        bodies[f'shin_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=sv,
                                                    basePosition=[x_sign, 0, 0.28])
        fv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.07, 0.05, 0.03], rgbaColor=C_FOOT)
        bodies[f'foot_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=fv,
                                                    basePosition=[x_sign, 0, 0.04])
    return bodies


def animate_leg(bodies, side, x_sign, hip_angle, knee_angle, base_x):
    L_thigh, L_shin = 0.32, 0.30
    hip_pos = np.array([base_x + x_sign, 0, 0.60])
    knee_pos = hip_pos + np.array([L_thigh * math.sin(hip_angle), 0, -L_thigh * math.cos(hip_angle)])
    p.resetBasePositionAndOrientation(bodies[f'thigh_{side}'], hip_pos,
                                       p.getQuaternionFromEuler([0, hip_angle, 0]))
    total = hip_angle + knee_angle
    shin_pos = knee_pos + np.array([L_shin * math.sin(total), 0, -L_shin * math.cos(total)])
    p.resetBasePositionAndOrientation(bodies[f'shin_{side}'], shin_pos,
                                       p.getQuaternionFromEuler([0, total, 0]))
    foot_pos = shin_pos + np.array([0.05 * math.sin(total), 0, -0.03])
    p.resetBasePositionAndOrientation(bodies[f'foot_{side}'], foot_pos, [0, 0, 0, 1])


def run_simulation(duration=60):
    """主仿真循环: IMU→YLYW→速度指令→动画"""
    try:
        client = p.connect(p.GUI, options='--opengl2')
    except:
        client = p.connect(p.GUI)
    
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(cameraDistance=2.5, cameraYaw=40, cameraPitch=-20,
                                  cameraTargetPosition=[0, 0, 0.80])
    
    bodies = build_robot()
    controller = YLYWLocomotionController()
    imu_sim = SimulatedIMU()
    imu2state = IMUtoState()
    
    # 仿真状态
    robot_x = 0.0
    robot_orientation = [0.0, 0.0, 0.0]  # roll, pitch, yaw
    robot_velocity = [0.0, 0.0, 0.0]  # vx, vy, vz
    phase = 0.0
    sim_time = 0.0
    dt = 1.0 / 120.0
    step = 0
    last_log = -999
    
    # 当前显示信息
    display = {
        'hexagram_name': '艮为山', 'gait_name': '静止站立',
        'forward_vel': 0.0, 'similarity': 0.0
    }
    
    # 扰动注入序列（模拟推搡测试）
    # (时刻, 侧向力, 持续时间)
    disturbance_seq = [
        (10, 200, 0.2),   # 10s: 200N侧推 0.2s
        (20, 300, 0.2),   # 20s: 300N侧推
        (35, 150, 0.3),   # 35s: 150N持续推
    ]
    dist_idx = 0
    current_disturbance = 0.0
    
    print(f"{'='*60}")
    print(f"YLYW → 灵犀X2 速度控制仿真 (闭环IMU反馈)")
    print(f"数据流: 模拟IMU → 6D状态 → YLYW → 步态 → VelocityCmd")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'卦象':<8} {'步态':<8} {'前向速度':>7} {'姿态':>6}")
    print("-" * 50)
    
    try:
        while sim_time < duration:
            # 注入扰动
            while dist_idx < len(disturbance_seq) and sim_time >= disturbance_seq[dist_idx][0]:
                current_disturbance = disturbance_seq[dist_idx][1]
                dist_idx += 1
            if current_disturbance > 0:
                current_disturbance = max(0, current_disturbance - dt * 500)
                
                # 扰动影响姿态
                robot_orientation[0] += current_disturbance * 0.00001 * dt
                robot_velocity[1] += (current_disturbance * 0.0001 if step % 2 == 0 else -current_disturbance * 0.0001) * dt
            
            # 模拟 IMU 读数（传入当前步态信息以生成真实的传感器数据）
            gait_info_for_imu = display if display['gait_name'] != '静止站立' else None
            imu_data = imu_sim.read(
                [robot_x, 0, 0.92], robot_orientation, robot_velocity, phase, sim_time,
                gait_info={'gait_name': display['gait_name'],
                            'speed': display['forward_vel']},
                disturbance_force=current_disturbance
            )
            
            # IMU → 6D 状态
            if step % 15 == 0:  # ~8Hz YLYW 推理（50Hz 过采样没必要）
                state_6d = imu2state.convert(imu_data)
                gait = controller.infer(np.array(state_6d), verbose=False)
                if gait:
                    velocity_cmd = GaitToVelocity.convert(gait)
                    display = {
                        'hexagram_name': gait['hexagram_name'],
                        'gait_name': gait['gait_name'],
                        'forward_vel': velocity_cmd['forward_velocity'],
                        'similarity': gait['similarity'],
                    }
                    
                    # 推搡时姿态恶化过头 → 强制覆盖 YLYW (安全兜底)
                    if current_disturbance > 200:
                        display['gait_name'] = '恢复步态'
                        display['forward_vel'] = 0.0
            
            # 根据速度指令驱动动画
            fwd = display['forward_vel']
            
            if fwd < 0.01:
                # 静止站立
                for side, x_sign in [('l', 0.08), ('r', -0.08)]:
                    animate_leg(bodies, side, x_sign, 0, 0, robot_x)
            else:
                freq = 1.6 + fwd * 2.0  # 步频随速度增加
                phase += freq * dt * 2 * math.pi
                phase %= 2 * math.pi
                
                robot_x += fwd * dt
                
                # 前进速度越快，步幅越大
                amp_h = 0.3 + fwd * 0.25
                amp_k = 0.2 + fwd * 0.2
                
                for side, x_sign, off in [('l', 0.08, 0), ('r', -0.08, math.pi)]:
                    p_leg = phase + off
                    hip = amp_h * math.sin(p_leg)
                    knee = amp_k * max(0, math.sin(p_leg))
                    animate_leg(bodies, side, x_sign, hip, knee, robot_x)
            
            # 更新躯干和头部
            p.resetBasePositionAndOrientation(bodies['torso'],
                                               [robot_x, 0, 0.92],
                                               p.getQuaternionFromEuler(robot_orientation))
            p.resetBasePositionAndOrientation(bodies['head'],
                                               [robot_x, 0, 1.30],
                                               [0, 0, 0, 1])
            p.resetDebugVisualizerCamera(cameraDistance=2.5, cameraYaw=40, cameraPitch=-20,
                                          cameraTargetPosition=[robot_x, 0, 0.80])
            
            # 显示信息
            if step % 30 == 0:
                ylyw_text = f"{display['hexagram_name']} | {display['gait_name']}"
                vel_text = f"Fwd:{display['forward_vel']:.2f}m/s | YLYW→灵犀X2"
                p.addUserDebugText(ylyw_text, [robot_x, 0, 1.65], [1, 0.8, 0], 1.5, lifeTime=0.5)
                p.addUserDebugText(vel_text, [robot_x, 0, 1.50], [0.5, 1, 0.5], 1.2, lifeTime=0.5)
            
            if sim_time > 0 and step - last_log >= 150:
                tilt = abs(robot_orientation[0]) + abs(robot_orientation[1])
                print(f"{sim_time:>4.1f}s {display['hexagram_name']:<8} "
                      f"{display['gait_name']:<8} {display['forward_vel']:>6.2f}m/s "
                      f"{tilt:>5.3f}rad")
                last_log = step
            
            p.stepSimulation()
            time.sleep(dt)
            step += 1
            sim_time += dt
    
    except KeyboardInterrupt:
        print("\n⏹ 中断")
    
    stats = controller.get_stats()
    print(f"\n{'='*60}")
    print(f"仿真结束: {stats.get('total_steps', 0)}次推理, "
          f"{stats.get('unique_hexagrams', 0)}个不同卦象")
    print(f"接口: YLYW步态 → 灵犀X2 McLocomotionVelocity (forward/lateral/angular)")
    p.disconnect(client)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--duration', type=float, default=60)
    args = p.parse_args()
    run_simulation(duration=args.duration)
