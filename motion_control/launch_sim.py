#!/usr/bin/env python3
"""
YLYW 双足运动控制仿真 — PyBullet Humanoid版
使用关节电机控制实现真实行走
"""
import sys, os, time, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ylyw_locomotion import YLYWLocomotionController
import pybullet as p
import pybullet_data


def auto_detect_display():
    for pat in ['/run/user/*/mutter-Xwaylandauth.*', '/run/user/*/.mutter-Xwaylandauth.*']:
        for f in glob.glob(pat):
            os.environ.setdefault('XAUTHORITY', f)
            break
    os.environ.setdefault('DISPLAY', ':0')


def connect_gui():
    auto_detect_display()
    configs = [("OpenGL2", "--opengl2"), ("默认", "")]
    for desc, opts in configs:
        try:
            cid = p.connect(p.GUI, options=opts) if opts else p.connect(p.GUI)
            print(f"✅ GUI: {desc}")
            return cid
        except Exception as e:
            print(f"  {desc}: {e}")
    return None


def run_gui(duration=30):
    """GUI仿真 - 使用PyBullet人形机器人 + 关节电机控制"""
    client = connect_gui()
    if client is None:
        print("\n❌ GUI连接失败。使用 python3 launch_sim.py --no-gui")
        return
    
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(2.5, 20, -15, [0, 0, 0.8])
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1/500.)
    p.loadURDF("plane.urdf")
    
    # 加载人形机器人（固定底座防止摔倒，专注展示步态）
    robot_id = p.loadURDF("humanoid/humanoid.urdf", [0, 0, 0.95], useFixedBase=True)
    # 取消腿部关节的固定约束，允许运动
    print(f"Robot ID: {robot_id}, Joints: {p.getNumJoints(robot_id)}")
    
    # 关节映射
    JOINT_NAMES = {}
    for i in range(p.getNumJoints(robot_id)):
        info = p.getJointInfo(robot_id, i)
        JOINT_NAMES[info[1].decode()] = i
    
    # 腿部关节
    LEG_JOINTS = {
        'left':  {'hip': JOINT_NAMES['left_hip'],  'knee': JOINT_NAMES['left_knee'],  'ankle': JOINT_NAMES['left_ankle']},
        'right': {'hip': JOINT_NAMES['right_hip'], 'knee': JOINT_NAMES['right_knee'], 'ankle': JOINT_NAMES['right_ankle']},
    }
    
    # 禁用默认电机，改Position控制
    for leg in LEG_JOINTS.values():
        for jid in leg.values():
            p.setJointMotorControl2(robot_id, jid, p.VELOCITY_CONTROL, force=0)
    
    controller = YLYWLocomotionController()
    
    # 步态参数
    phase = 0.0
    sim_time = 0.0
    dt = 1/500.
    step = 0
    current_gait = None
    last_log = -999
    
    # 快速演示序列（每3秒一个场景）
    demo_sequence = [
        (0,   "初始站立",   [0.90,0.82,0.75,0.88,0.05,0.82]),
        (3,   "开始慢走",   [0.72,0.72,0.68,0.65,0.20,0.80]),
        (6,   "加速行走",   [0.65,0.70,0.65,0.60,0.30,0.78]),
        (9,   "快速小跑",   [0.55,0.72,0.72,0.50,0.52,0.76]),
        (12,  "全力奔跑",   [0.48,0.75,0.78,0.42,0.62,0.78]),
        (15,  "突然推搡",   [0.18,0.30,0.25,0.14,0.82,0.55]),
        (18,  "踉跄恢复",   [0.55,0.42,0.48,0.38,0.50,0.60]),
        (21,  "爬坡前进",   [0.48,0.42,0.52,0.32,0.45,0.18]),
        (24,  "回到平路",   [0.70,0.72,0.68,0.65,0.22,0.78]),
        (27,  "减速站立",   [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    
    demo_idx = 0
    display_gait = {"hexagram_name": "艮为山", "gait_name": "静止站立", "speed": 0.0}
    
    print(f"\n{'='*60}")
    print(f"YLYW 运动控制仿真 | Humanoid | {len(LEG_JOINTS)*3} 腿部关节")
    print(f"运行 {duration}s | Ctrl+C 停止")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<8} {'速':>4}")
    print("-" * 45)
    
    try:
        while sim_time < duration:
            # 演示序列状态注入
            while demo_idx + 1 < len(demo_sequence) and sim_time >= demo_sequence[demo_idx + 1][0]:
                demo_idx += 1
            
            demo_name, demo_state = demo_sequence[demo_idx][1], demo_sequence[demo_idx][2]
            
            # YLYW推理 (~4Hz)
            if step % 125 == 0:
                current_gait = controller.infer(np.array(demo_state), verbose=False)
                if current_gait:
                    display_gait = current_gait
            
            # 关节运动控制
            if current_gait:
                speed = current_gait['speed']
                freq = current_gait['freq']
                force_coef = current_gait['force_coefficient']
                
                phase += freq * dt * 2 * np.pi
                phase %= 2 * np.pi
                
                max_force = 500 * force_coef  # 力矩缩放
                
                if speed < 0.05:
                    # 站立：保持关节在零位
                    for leg in LEG_JOINTS.values():
                        p.setJointMotorControl2(robot_id, leg['hip'], p.POSITION_CONTROL, targetPosition=0, force=max_force)
                        p.setJointMotorControl2(robot_id, leg['knee'], p.POSITION_CONTROL, targetPosition=0, force=max_force)
                        p.setJointMotorControl2(robot_id, leg['ankle'], p.POSITION_CONTROL, targetPosition=0, force=max_force)
                else:
                    # 行走：正弦步态
                    hip_amp = 0.5 * speed * 1.2
                    knee_amp = 0.6 * speed * 0.8
                    
                    for side, offset in [('left', 0), ('right', np.pi)]:
                        j = LEG_JOINTS[side]
                        p_leg = phase + offset
                        
                        # 髋关节：前后摆动
                        hip_pos = hip_amp * np.sin(p_leg)
                        p.setJointMotorControl2(robot_id, j['hip'], p.POSITION_CONTROL, targetPosition=hip_pos, force=max_force)
                        
                        # 膝关节：站立相伸直(0)，摆动相弯曲
                        if np.sin(p_leg) > 0:
                            knee_pos = knee_amp * np.sin(p_leg)
                        else:
                            knee_pos = 0
                        p.setJointMotorControl2(robot_id, j['knee'], p.POSITION_CONTROL, targetPosition=knee_pos, force=max_force * 0.7)
                        
                        # 踝关节：保持水平
                        p.setJointMotorControl2(robot_id, j['ankle'], p.POSITION_CONTROL, targetPosition=-0.1 * hip_amp * np.sin(p_leg), force=max_force * 0.5)
            
            # GUI叠加文字
            info = f"{display_gait['hexagram_name']} | {display_gait['gait_name']} | {display_gait['speed']:.2f}m/s"
            p.addUserDebugText(info, [0, 0, 2.0], textColorRGB=[1, 1, 0], textSize=1.5, lifeTime=0.15)
            
            p.stepSimulation()
            
            if step % 8 == 0:
                time.sleep(0.016)
            
            if step - last_log >= 500:
                print(f"{sim_time:>4.1f}s {demo_name:<8} {display_gait['hexagram_name']:<10} "
                      f"{display_gait['gait_name']:<8} {display_gait['speed']:>3.2f}")
                last_log = step
            
            step += 1
            sim_time += dt
    
    except KeyboardInterrupt:
        print("\n⏹ 用户中断")
    
    p.disconnect(client)
    stats = controller.get_stats()
    print(f"\n统计: {stats.get('total_steps',0)}次推理, {stats.get('unique_hexagrams',0)}卦")


def run_no_gui():
    controller = YLYWLocomotionController()
    demo = [
        (0, "初始站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
        (3, "开始慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
        (8, "加速行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
        (14,"快速小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
        (20,"全力奔跑", [0.48,0.75,0.78,0.42,0.62,0.78]),
        (26,"突然推搡", [0.18,0.30,0.25,0.14,0.82,0.55]),
        (32,"踉跄恢复", [0.55,0.42,0.48,0.38,0.50,0.60]),
        (38,"爬坡前进", [0.48,0.42,0.52,0.32,0.45,0.18]),
        (44,"回到平路", [0.70,0.72,0.68,0.65,0.22,0.78]),
        (50,"减速站立", [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    print(f"{'时间':>4} {'场景':<8} {'卦象':<10} {'步态':<10} {'速':>4} {'六爻'}")
    print("-" * 65)
    for t, name, state in demo:
        gp = controller.infer(state, verbose=False)
        print(f"{t:>3}s  {name:<8} {gp['hexagram_name']:<10} {gp['gait_name']:<10} {gp['speed']:>4.2f} {gp['yin_yang']}")
    print("-" * 65)


if __name__ == '__main__':
    if '--no-gui' in sys.argv:
        run_no_gui()
    else:
        dur = 60
        for i, arg in enumerate(sys.argv):
            if arg == '--duration' and i+1 < len(sys.argv):
                dur = float(sys.argv[i+1])
        run_gui(duration=dur)
