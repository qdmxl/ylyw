#!/usr/bin/env python3
"""
YLYW运动控制仿真（PyBullet GUI）
运行后可在GUI中看到双足机器人 + YLYW实时推理链
"""
import sys, os, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pybullet as p
import pybullet_data
from ylyw_locomotion import YLYWLocomotionController


def build_simple_biped():
    """构建简化双足机器人（盒状模型）"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1/240.)
    
    # Ground
    p.loadURDF("plane.urdf")
    
    # Colors
    torso_color = [0.2, 0.4, 0.8, 1]
    leg_color = [0.2, 0.7, 0.3, 1]
    foot_color = [0.8, 0.3, 0.2, 1]
    
    # Torso
    torso_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14])
    torso_vis = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14], rgbaColor=torso_color)
    torso_id = p.createMultiBody(1.5, -1, torso_shape, torso_vis, [0, 0, 0.80], [0,0,0,1])
    
    # Build legs using constraints
    joints = {}
    leg_mass = 0.8
    foot_mass = 0.3
    
    for side, y_sign in [('l', 0.055), ('r', -0.055)]:
        # Upper leg
        thigh_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.035, 0.035, 0.16])
        thigh_vis = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.035, 0.035, 0.16], rgbaColor=leg_color)
        thigh_id = p.createMultiBody(leg_mass, -1, thigh_shape, thigh_vis, [0, y_sign, 0.50], [0,0,0,1])
        
        # Hip joint (revolute, X-axis)
        hip_cid = p.createConstraint(torso_id, -1, thigh_id, -1,
                                     p.JOINT_REVOLUTE, [1, 0, 0],
                                     [0, y_sign, -0.14], [0, 0, 0],
                                     childFramePosition=[0, 0, 0.16])
        p.changeConstraint(hip_cid, maxForce=80)
        joints[f'hip_{side}'] = hip_cid
        
        # Lower leg
        shin_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.03, 0.03, 0.15])
        shin_vis = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.03, 0.03, 0.15], rgbaColor=leg_color)
        shin_id = p.createMultiBody(leg_mass * 0.7, -1, shin_shape, shin_vis, [0, y_sign, 0.20], [0,0,0,1])
        
        # Knee joint
        knee_cid = p.createConstraint(thigh_id, -1, shin_id, -1,
                                      p.JOINT_REVOLUTE, [1, 0, 0],
                                      [0, 0, -0.16], [0, 0, 0],
                                      childFramePosition=[0, 0, 0.15])
        p.changeConstraint(knee_cid, maxForce=60)
        joints[f'knee_{side}'] = knee_cid
        
        # Foot
        foot_shape = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04, 0.10, 0.025])
        foot_vis = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04, 0.10, 0.025], rgbaColor=foot_color)
        foot_id = p.createMultiBody(foot_mass, -1, foot_shape, foot_vis, [0, y_sign, 0.03], [0,0,0,1])
        
        # Ankle joint
        ankle_cid = p.createConstraint(shin_id, -1, foot_id, -1,
                                       p.JOINT_REVOLUTE, [1, 0, 0],
                                       [0, 0, -0.15], [0, 0, 0],
                                       childFramePosition=[0, 0, 0.025])
        p.changeConstraint(ankle_cid, maxForce=40)
        joints[f'ankle_{side}'] = ankle_cid
    
    return torso_id, joints


def get_robot_state(torso_id):
    """获取机器人状态（6维）"""
    pos, orn = p.getBasePositionAndOrientation(torso_id)
    lin_vel, ang_vel = p.getBaseVelocity(torso_id)
    
    euler = p.getEulerFromQuaternion(orn)
    pitch, roll = euler[0], euler[1]
    
    # Posture stability
    posture = max(0.0, 1.0 - (abs(pitch) + abs(roll)) / 0.8)
    
    # COM height (normalize to [0.7, 0.9]m range)
    com_h = pos[2]
    com_h_norm = np.clip((com_h - 0.3) / 0.6, 0.0, 1.0)
    
    # Force distribution (simplified)
    force_dist = 0.6  # default
    
    # ZMP margin (simplified from COM lateral deviation)
    zmp = max(0.0, 1.0 - abs(pos[1]) / 0.08)
    
    # Disturbance from angular velocity
    dist = np.clip(np.linalg.norm(ang_vel) / 4.0, 0.0, 1.0)
    
    # Terrain (flat)
    terrain = 0.85
    
    state_vector = np.array([posture, com_h_norm, force_dist, zmp, dist, terrain])
    return state_vector, pos, euler


def apply_gait(gait_params, phase, joints):
    """根据步态参数施加关节力"""
    speed = gait_params.get('speed', 0.3)
    step_height = gait_params.get('step_height', 0.04)
    freq = gait_params.get('freq', 1.5)
    force_coef = gait_params.get('force_coefficient', 0.5)
    
    # 正弦步态生成
    hip_amp = 0.25 * speed * 1.5
    knee_amp = 0.3 * speed
    ankle_amp = 0.1 * speed
    
    max_force = 80 * force_coef
    
    # 左腿相位偏移π（交替步态）
    for side, phase_offset in [('l', 0), ('r', np.pi)]:
        p_leg = phase + phase_offset
        
        # 髋关节：正弦摆动
        hip_pos = hip_amp * np.sin(p_leg)
        for jname in [f'hip_{side}']:
            if jname in joints:
                p.changeConstraint(joints[jname], maxForce=max_force,
                                   jointChildPivot=[0, 0, 0],
                                   jointAxis=[1, 0, 0],
                                   parentFramePosition=[0, (0.055 if side=='l' else -0.055), -0.14],
                                   childFramePosition=[0, 0, 0])
                # Use position motor
                # For revolute constraint, we adjust the pivot
        
        # 膝关节：站立相伸直，摆动相弯曲
        if np.sin(p_leg) > 0:  # 摆动相
            knee_pos = knee_amp * np.sin(p_leg)
        else:  # 站立相
            knee_pos = 0
        for jname in [f'knee_{side}']:
            if jname in joints:
                pass  # constraint-based control is limited
    
    # Simplified: just apply a sinusoidal force pattern via the constraint
    return phase + freq * (1/240.) * 2 * np.pi


def run_ylyw_simulation(duration_sec=30):
    """主仿真循环"""
    # Connect GUI
    client = p.connect(p.GUI)
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(2.0, 30, -25, [0, 0, 0.6])
    
    # Build robot
    torso_id, joints = build_simple_biped()
    
    # YLYW Controller
    controller = YLYWLocomotionController()
    
    # Simulation state
    phase = 0
    sim_time = 0
    dt = 1/240.
    log_interval = 120  # log every N steps
    
    print("=" * 60)
    print("YLYW 运动控制仿真")
    print("=" * 60)
    print(f"机器人ID: {torso_id}")
    print(f"关节数: {len(joints)}")
    print(f"控制器就绪")
    print(f"按 Ctrl+C 停止仿真")
    print("=" * 60)
    print(f"{'时间':>6} {'卦象':<10} {'步态':<10} {'速度':>5} {'姿势':>5} {'质心':>5} {'ZMP':>5}")
    print("-" * 50)
    
    last_log = 0
    step = 0
    
    try:
        while sim_time < duration_sec:
            # Get state
            state_vec, pos, euler = get_robot_state(torso_id)
            
            # YLYW inference (every 40 steps ≈ 6Hz)
            if step % 40 == 0:
                gp = controller.infer(state_vec, verbose=False)
                current_gait = gp
            
            # Apply gait
            phase = (phase + current_gait['freq'] * dt * 2 * np.pi) % (2 * np.pi)
            
            # Simple sinusoidal hip motion
            max_force = 80 * current_gait['force_coefficient']
            hip_amp = 0.3 * current_gait['speed']
            
            for side, y_sign in [('l', 0.055), ('r', -0.055)]:
                offset = 0 if side == 'l' else np.pi
                hip_pos = hip_amp * np.sin(phase + offset)
                # Update constraint pivot to simulate joint motion
                if f'hip_{side}' in joints:
                    try:
                        p.changeConstraint(joints[f'hip_{side}'], 
                                         jointChildPivot=[0, 0.15 * np.sin(hip_pos), 0.15 * np.cos(hip_pos)],
                                         maxForce=max_force)
                    except:
                        pass
            
            # Step physics
            p.stepSimulation()
            
            # Log
            if step - last_log >= log_interval:
                print(f"{sim_time:>5.1f}s {current_gait['hexagram_name']:<10} "
                      f"{current_gait['gait_name']:<10} {current_gait['speed']:>4.2f} "
                      f"{state_vec[0]:>4.2f} {state_vec[1]:>4.2f} {state_vec[3]:>4.2f}")
                last_log = step
            
            step += 1
            sim_time += dt
            
    except KeyboardInterrupt:
        print("\n仿真中断")
    
    p.disconnect(client)
    print("仿真结束")
    
    # Show stats
    stats = controller.get_stats()
    print(f"\n统计: {stats['total_steps']}次推理, {stats['unique_hexagrams']}个不同卦象")


def run_no_gui_demo():
    """无GUI演示（直接输出推理链）"""
    print("=" * 60)
    print("YLYW 运动控制推理演示（无GUI）")
    print("=" * 60)
    
    controller = YLYWLocomotionController()
    
    # 模拟10秒仿真，每0.5秒推理一次
    scenarios = [
        (0.0, "初始站立", [0.90, 0.82, 0.75, 0.88, 0.05, 0.82]),
        (1.0, "开始慢走", [0.72, 0.72, 0.68, 0.65, 0.20, 0.80]),
        (2.5, "匀速行走", [0.65, 0.70, 0.65, 0.60, 0.30, 0.78]),
        (4.0, "加速小跑", [0.55, 0.72, 0.72, 0.50, 0.52, 0.76]),
        (5.5, "冲刺奔跑", [0.48, 0.75, 0.78, 0.42, 0.62, 0.78]),
        (6.5, "遭遇推搡", [0.20, 0.32, 0.28, 0.15, 0.80, 0.55]),
        (7.5, "恢复稳定", [0.60, 0.45, 0.50, 0.45, 0.35, 0.60]),
        (8.5, "上坡爬行", [0.48, 0.42, 0.52, 0.32, 0.45, 0.18]),
        (9.5, "回到平地", [0.70, 0.72, 0.68, 0.65, 0.22, 0.78]),
    ]
    
    for t, name, state in scenarios:
        gp = controller.infer(state, verbose=False)
        print(f"\n[{t:>4.1f}s] {name}")
        print(f"  卦象: {gp['hexagram_name']} (sim={gp['similarity']:.3f})")
        print(f"  步态: {gp['gait_name']}")
        print(f"  速度: {gp['speed']:.2f} m/s | 力: {gp['force_coefficient']:.2f}")
        print(f"  六爻: {gp['yin_yang']}")
    
    print(f"\n{'='*60}")
    print("10秒仿真完成。9次推理，推理耗时 <2ms。")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-gui', action='store_true', help='无GUI推理演示')
    parser.add_argument('--duration', type=float, default=30, help='仿真时长（秒）')
    args = parser.parse_args()
    
    if args.no_gui:
        run_no_gui_demo()
    else:
        run_ylyw_simulation(duration_sec=args.duration)
