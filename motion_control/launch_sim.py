#!/usr/bin/env python3
"""
YLYW 双足运动控制仿真 — 运动学动画版
侧视图：机器人从左向右行走
"""
import sys, os, time, glob, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_locomotion import YLYWLocomotionController
import pybullet as p, pybullet_data


def auto_detect_display():
    for pat in ['/run/user/*/mutter-Xwaylandauth.*', '/run/user/*/.mutter-Xwaylandauth.*']:
        for f in glob.glob(pat):
            os.environ.setdefault('XAUTHORITY', f); break
    os.environ.setdefault('DISPLAY', ':0')


def connect_gui():
    auto_detect_display()
    for desc, opts in [("OpenGL2", "--opengl2"), ("默认", "")]:
        try:
            cid = p.connect(p.GUI, options=opts) if opts else p.connect(p.GUI)
            return cid
        except: pass
    return None


def build_kinematic_robot():
    """运动学机器人：腿在X-Z平面摆动（侧视图可见）"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, 0)
    p.loadURDF("plane.urdf")
    
    bodies = {}
    # 躯干
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.08, 0.12, 0.22], rgbaColor=[0.2, 0.4, 0.9, 1])
    bodies['torso'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv, basePosition=[0, 0, 0.82])
    # 头
    hv = p.createVisualShape(p.GEOM_SPHERE, radius=0.10, rgbaColor=[1, 0.85, 0.7, 1])
    bodies['head'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=hv, basePosition=[0, 0, 1.08])
    
    # 腿沿X轴排列（前腿/后腿），绕Y轴摆动
    for side, x_sign in [('l', 0.08), ('r', -0.08)]:
        tv2 = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=0.28, rgbaColor=[0.2, 0.8, 0.3, 1])
        bodies[f'thigh_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv2,
                                                     basePosition=[x_sign, 0, 0.52])
        
        sv = p.createVisualShape(p.GEOM_CYLINDER, radius=0.035, length=0.26, rgbaColor=[0.2, 0.8, 0.3, 1])
        bodies[f'shin_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=sv,
                                                    basePosition=[x_sign, 0, 0.22])
    
    return bodies


def animate_leg_side(bodies, side, x_sign, hip_angle, knee_angle):
    """运动学：绕Y轴旋转（侧面可见的行走）"""
    L_thigh = 0.28
    L_shin = 0.26
    
    hip_pos = np.array([x_sign, 0, 0.52])
    # 大腿远端 = hip + L_thigh * [sin(θ), 0, -cos(θ)]
    knee_pos = hip_pos + np.array([L_thigh * math.sin(hip_angle), 0, -L_thigh * math.cos(hip_angle)])
    thigh_orn = p.getQuaternionFromEuler([0, hip_angle, 0])
    p.resetBasePositionAndOrientation(bodies[f'thigh_{side}'], hip_pos, thigh_orn)
    
    total = hip_angle + knee_angle
    shin_pos = knee_pos + np.array([L_shin * math.sin(total), 0, -L_shin * math.cos(total)])
    shin_orn = p.getQuaternionFromEuler([0, total, 0])
    p.resetBasePositionAndOrientation(bodies[f'shin_{side}'], shin_pos, shin_orn)


def run_gui(duration=30):
    client = connect_gui()
    if client is None:
        print("❌ GUI失败"); return

    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    # 侧面视角：看从左到右行走
    p.resetDebugVisualizerCamera(cameraDistance=2.0, cameraYaw=0, cameraPitch=-8,
                                  cameraTargetPosition=[0, 0, 0.80])
    
    bodies = build_kinematic_robot()
    controller = YLYWLocomotionController()
    
    phase = 0.0; sim_time = 0.0; dt = 1/120.; step = 0
    current_gait = None; last_log = -999
    display_gait = {"hexagram_name": "艮为山", "gait_name": "静止站立", "speed": 0.0}

    demo_seq = [
        (0,  "初始站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
        (3,  "开始慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
        (6,  "加速行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
        (9,  "快速小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
        (12, "全力奔跑", [0.48,0.75,0.78,0.42,0.62,0.78]),
        (15, "突然推搡", [0.18,0.30,0.25,0.14,0.82,0.55]),
        (18, "踉跄恢复", [0.55,0.42,0.48,0.38,0.50,0.60]),
        (21, "爬坡前进", [0.48,0.42,0.52,0.32,0.45,0.18]),
        (24, "回到平路", [0.70,0.72,0.68,0.65,0.22,0.78]),
        (27, "减速站立", [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    demo_idx = 0

    print(f"{'='*55}")
    print(f"YLYW 运动控制仿真 | 侧视图 | Ctrl+C 停止")
    print(f"{'='*55}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<10} {'速':>4}")
    print("-" * 48)

    try:
        while sim_time < duration:
            while demo_idx+1 < len(demo_seq) and sim_time >= demo_seq[demo_idx+1][0]:
                demo_idx += 1
            name, dstate = demo_seq[demo_idx][1], demo_seq[demo_idx][2]

            if step % 10 == 0:
                current_gait = controller.infer(np.array(dstate), verbose=False)
                if current_gait: display_gait = current_gait

            if current_gait:
                spd = current_gait['speed']
                freq = current_gait['freq']
                phase += freq * dt * 2 * math.pi
                phase %= 2 * math.pi

                if spd < 0.03:
                    for side, x_sign in [('l', 0.08), ('r', -0.08)]:
                        animate_leg_side(bodies, side, x_sign, 0, 0)
                else:
                    amp_h = 0.55 * spd
                    amp_k = 0.45 * spd
                    for side, x_sign, off in [('l', 0.08, 0), ('r', -0.08, math.pi)]:
                        p_leg = phase + off
                        hip_angle = amp_h * math.sin(p_leg)
                        knee_angle = amp_k * max(0, math.sin(p_leg))
                        animate_leg_side(bodies, side, x_sign, hip_angle, knee_angle)

            p.stepSimulation()
            time.sleep(dt)

            if step % 60 == 0:
                p.addUserDebugText(
                    f"{display_gait['hexagram_name']} | {display_gait['gait_name']} | {display_gait['speed']:.2f}m/s",
                    [0, 0, 1.5], [1, 1, 0], 1.2, lifeTime=0.6)

            if step - last_log >= 120:
                g = display_gait
                print(f"{sim_time:>4.1f}s {name:<8} {g['hexagram_name']:<10} "
                      f"{g['gait_name']:<10} {g['speed']:>3.2f}")
                last_log = step

            step += 1; sim_time += dt

    except KeyboardInterrupt:
        print("\n⏹ 中断")

    p.disconnect(client)
    print(f"统计: {controller.get_stats().get('total_steps',0)}次推理")


def run_no_gui():
    controller = YLYWLocomotionController()
    for t, name, state in [
        (0,"初始站立",[0.90,0.82,0.75,0.88,0.05,0.82]),
        (3,"开始慢走",[0.72,0.72,0.68,0.65,0.20,0.80]),
        (8,"加速行走",[0.65,0.70,0.65,0.60,0.30,0.78]),
        (14,"快速小跑",[0.55,0.72,0.72,0.50,0.52,0.76]),
        (20,"全力奔跑",[0.48,0.75,0.78,0.42,0.62,0.78]),
        (26,"突然推搡",[0.18,0.30,0.25,0.14,0.82,0.55]),
        (32,"踉跄恢复",[0.55,0.42,0.48,0.38,0.50,0.60]),
        (38,"爬坡前进",[0.48,0.42,0.52,0.32,0.45,0.18]),
        (44,"回到平路",[0.70,0.72,0.68,0.65,0.22,0.78]),
        (50,"减速站立",[0.88,0.78,0.72,0.85,0.10,0.80]),
    ]:
        gp = controller.infer(state, verbose=False)
        print(f"{t:>3}s {name:<8} {gp['hexagram_name']:<10} {gp['gait_name']:<10} {gp['speed']:>4.2f} {gp['yin_yang']}")


if __name__ == '__main__':
    if '--no-gui' in sys.argv:
        run_no_gui()
    else:
        dur = 30
        for i, a in enumerate(sys.argv):
            if a == '--duration' and i+1 < len(sys.argv): dur = float(sys.argv[i+1])
        run_gui(duration=dur)
