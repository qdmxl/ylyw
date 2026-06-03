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
    """仿灵犀X2外形机器人（基础形状搭建）"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, 0)
    p.loadURDF("plane.urdf")
    
    bodies = {}
    # 颜色方案：银灰色躯干 + 深灰关节
    C_TORSO = [0.75, 0.78, 0.82, 1]   # 银灰
    C_HEAD  = [0.85, 0.88, 0.90, 1]   # 浅灰
    C_ARM   = [0.55, 0.58, 0.62, 1]   # 深灰
    C_LEG   = [0.50, 0.53, 0.57, 1]   # 腿深灰
    C_JOINT = [0.35, 0.38, 0.42, 1]   # 关节深色
    
    # 头部（球体）
    hv = p.createVisualShape(p.GEOM_SPHERE, radius=0.08, rgbaColor=C_HEAD)
    bodies['head'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=hv, basePosition=[0, 0, 1.28])
    
    # 躯干（圆角盒体）
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.13, 0.10, 0.25], rgbaColor=C_TORSO)
    bodies['torso'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv, basePosition=[0, 0, 0.90])
    
    # 上肢（左右臂）
    for side, y_sign in [('l', 0.12), ('r', -0.12)]:
        # 上臂
        ua = p.createVisualShape(p.GEOM_CYLINDER, radius=0.035, length=0.25, rgbaColor=C_ARM)
        bodies[f'upper_arm_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=ua,
                                                         basePosition=[0, y_sign, 1.02])
        # 前臂
        fa = p.createVisualShape(p.GEOM_CYLINDER, radius=0.03, length=0.22, rgbaColor=C_ARM)
        bodies[f'forearm_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=fa,
                                                       basePosition=[0, y_sign, 0.78])
    
    # 下肢（双腿，摆动用）
    for side, x_sign in [('l', 0.07), ('r', -0.07)]:
        # 大腿
        tv2 = p.createVisualShape(p.GEOM_CYLINDER, radius=0.045, length=0.30, rgbaColor=C_LEG)
        bodies[f'thigh_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=tv2,
                                                     basePosition=[x_sign, 0, 0.58])
        # 小腿
        sv = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=0.28, rgbaColor=C_LEG)
        bodies[f'shin_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=sv,
                                                    basePosition=[x_sign, 0, 0.28])
        # 脚（扁平盒体）
        fv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.06, 0.04, 0.025], rgbaColor=C_JOINT)
        bodies[f'foot_{side}'] = p.createMultiBody(baseMass=0, baseVisualShapeIndex=fv,
                                                    basePosition=[x_sign, 0, 0.04])
    
    return bodies


def animate_leg_side(bodies, side, x_sign, hip_angle, knee_angle, base_x=0):
    """运动学：绕Y轴摆动 + 脚部跟随"""
    L_thigh = 0.30
    L_shin = 0.28
    L_foot = 0.04
    
    hip_x = base_x + x_sign
    hip_pos = np.array([hip_x, 0, 0.58])
    knee_pos = hip_pos + np.array([L_thigh * math.sin(hip_angle), 0, -L_thigh * math.cos(hip_angle)])
    thigh_orn = p.getQuaternionFromEuler([0, hip_angle, 0])
    p.resetBasePositionAndOrientation(bodies[f'thigh_{side}'], hip_pos, thigh_orn)
    
    total = hip_angle + knee_angle
    shin_pos = knee_pos + np.array([L_shin * math.sin(total), 0, -L_shin * math.cos(total)])
    shin_orn = p.getQuaternionFromEuler([0, total, 0])
    p.resetBasePositionAndOrientation(bodies[f'shin_{side}'], shin_pos, shin_orn)
    
    # 脚部跟随小腿末端
    foot_pos = shin_pos + np.array([L_shin * 0.5 * math.sin(total), 0, -0.14 * math.cos(total)])
    p.resetBasePositionAndOrientation(bodies[f'foot_{side}'], foot_pos, [0, 0, 0, 1])


def run_gui(duration=30):
    client = connect_gui()
    if client is None:
        print("❌ GUI失败"); return

    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    # 45度斜侧视角：兼顾机器人形态和左右运动
    p.resetDebugVisualizerCamera(cameraDistance=2.0, cameraYaw=45, cameraPitch=-18,
                                  cameraTargetPosition=[0, 0, 0.80])
    
    bodies = build_kinematic_robot()
    controller = YLYWLocomotionController()
    
    phase = 0.0; sim_time = 0.0; dt = 1/120.; step = 0
    current_gait = None; last_log = -999
    robot_x = 0.0  # 机器人在X轴上的位置
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
    print(f"YLYW 运动控制仿真 | 仿灵犀X2 | 45°视角 | Ctrl+C 停止")
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
                
                # 机器人沿X轴移动（速度=步态速度）
                robot_x += spd * dt
                # 更新躯干和头部位置
                p.resetBasePositionAndOrientation(bodies['torso'], [robot_x, 0, 0.90], [0,0,0,1])
                p.resetBasePositionAndOrientation(bodies['head'], [robot_x, 0, 1.28], [0,0,0,1])
                # 摄像头跟随
                p.resetDebugVisualizerCamera(cameraDistance=2.0, cameraYaw=45, cameraPitch=-18,
                                              cameraTargetPosition=[robot_x, 0, 0.80])

                if spd < 0.03:
                    for side, x_sign in [('l', 0.07), ('r', -0.07)]:
                        animate_leg_side(bodies, side, x_sign, 0, 0, robot_x)
                else:
                    amp_h = 0.55 * spd
                    amp_k = 0.45 * spd
                    for side, x_sign, off in [('l', 0.07, 0), ('r', -0.07, math.pi)]:
                        p_leg = phase + off
                        hip_angle = amp_h * math.sin(p_leg)
                        knee_angle = amp_k * max(0, math.sin(p_leg))
                        animate_leg_side(bodies, side, x_sign, hip_angle, knee_angle, robot_x)

            p.stepSimulation()
            time.sleep(dt)

            if step % 60 == 0:
                p.addUserDebugText(
                    f"{display_gait['hexagram_name']} | {display_gait['gait_name']} | {display_gait['speed']:.2f}m/s",
                    [robot_x, 0, 1.60], [1, 1, 0], 1.2, lifeTime=0.6)

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
