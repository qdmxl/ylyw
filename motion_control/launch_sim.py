#!/usr/bin/env python3
"""
YLYW 双足运动控制仿真 — 基础形状版
球体+盒体搭建，保证渲染可见
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
            print(f"✅ GUI: {desc}"); return cid
        except: pass
    return None


def build_box_robot():
    """球体+盒体搭建可见机器人"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1/500.)
    p.loadURDF("plane.urdf")

    # 头部 - 球体
    hs = p.createCollisionShape(p.GEOM_SPHERE, radius=0.12)
    hv = p.createVisualShape(p.GEOM_SPHERE, radius=0.12, rgbaColor=[1, 0.85, 0.7, 1])
    head = p.createMultiBody(baseMass=0.5, baseCollisionShapeIndex=hs,
                             baseVisualShapeIndex=hv, basePosition=[0, 0, 1.25])

    # 躯干 - 蓝色盒
    ts = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.12, 0.08, 0.20])
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.12, 0.08, 0.20], rgbaColor=[0.2, 0.4, 0.9, 1])
    torso = p.createMultiBody(baseMass=1.0, baseCollisionShapeIndex=ts,
                              baseVisualShapeIndex=tv, basePosition=[0, 0, 0.80])

    # 头-躯干固定
    p.createConstraint(torso, -1, head, -1, p.JOINT_FIXED, [0, 0, 0], [0, 0, 0.20], [0, 0, 0.40])

    joints = {}
    for side, y_sign in [('l', 0.08), ('r', -0.08)]:
        # 大腿 - 绿色圆柱
        us = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.04, height=0.30)
        uv = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=0.30, rgbaColor=[0.2, 0.8, 0.3, 1])
        thigh = p.createMultiBody(baseMass=0.0, baseCollisionShapeIndex=us,
                                  baseVisualShapeIndex=uv, basePosition=[0, y_sign, 0.55])

        # 髋关节 - 铰链
        jid = p.createConstraint(torso, -1, thigh, -1, 4, [1, 0, 0],
                                 [0, y_sign, -0.18], [0, 0, 0])
        p.changeConstraint(jid, maxForce=200)
        joints[('hip', side)] = jid
        joints[('hip_body', side)] = thigh

        # 小腿 - 绿色圆柱
        ls = p.createCollisionShape(p.GEOM_CYLINDER, radius=0.035, height=0.28)
        lv = p.createVisualShape(p.GEOM_CYLINDER, radius=0.035, length=0.28, rgbaColor=[0.2, 0.8, 0.3, 1])
        shin = p.createMultiBody(baseMass=0.0, baseCollisionShapeIndex=ls,
                                 baseVisualShapeIndex=lv, basePosition=[0, y_sign, 0.25])

        jid2 = p.createConstraint(thigh, -1, shin, -1, 4, [1, 0, 0],
                                  [0, 0, -0.15], [0, 0, 0.14])
        p.changeConstraint(jid2, maxForce=150)
        joints[('knee', side)] = jid2
        joints[('knee_body', side)] = shin

        # 脚 - 红色盒
        fs = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.05, 0.12, 0.03])
        fv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.05, 0.12, 0.03], rgbaColor=[0.9, 0.2, 0.2, 1])
        foot = p.createMultiBody(baseMass=0.0, baseCollisionShapeIndex=fs,
                                 baseVisualShapeIndex=fv, basePosition=[0, y_sign, 0.07])

        jid3 = p.createConstraint(shin, -1, foot, -1, 4, [1, 0, 0],
                                  [0, 0, -0.14], [0, 0, 0.03])
        p.changeConstraint(jid3, maxForce=100)
        joints[('ankle', side)] = jid3

    return torso, joints


def run_gui(duration=30):
    client = connect_gui()
    if client is None:
        print("❌ GUI失败"); return

    torso_id, joints = build_box_robot()
    controller = YLYWLocomotionController()

    # 正面视角
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(cameraDistance=1.5, cameraYaw=0, cameraPitch=-5,
                                  cameraTargetPosition=[0, 0, 0.85])

    phase = 0.0; sim_time = 0.0; dt = 1/500.; step = 0
    current_gait = None; last_log = -999
    display_gait = {"hexagram_name": "艮为山", "gait_name": "静止站立", "speed": 0.0}

    # 每3秒切换场景
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
    print(f"YLYW 运动控制仿真 | 基础形状机器人 | {len(joints)//2}关节")
    print(f"运行 {duration}s | Ctrl+C 停止")
    print(f"{'='*55}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<8} {'速':>4} {'六爻'}")
    print("-" * 55)

    try:
        while sim_time < duration:
            while demo_idx+1 < len(demo_seq) and sim_time >= demo_seq[demo_idx+1][0]:
                demo_idx += 1
            name, dstate = demo_seq[demo_idx][1], demo_seq[demo_idx][2]

            if step % 125 == 0:
                current_gait = controller.infer(np.array(dstate), verbose=False)
                if current_gait: display_gait = current_gait

            if current_gait:
                spd = current_gait['speed']
                freq = current_gait['freq']
                fc = current_gait['force_coefficient']
                phase += freq * dt * 2 * math.pi; phase %= 2 * math.pi
                force = 200 * fc

                if spd < 0.05:
                    for side in ['l', 'r']:
                        try:
                            p.changeConstraint(joints[('hip', side)], jointChildPivot=[0,0,0], maxForce=force)
                            p.changeConstraint(joints[('knee', side)], jointChildPivot=[0,0,0], maxForce=force)
                        except: pass
                else:
                    amp_h = 0.5 * spd
                    amp_k = 0.4 * spd
                    for side, off in [('l', 0), ('r', math.pi)]:
                        p_leg = phase + off
                        hp = amp_h * math.sin(p_leg)
                        kp = amp_k * math.sin(p_leg) if math.sin(p_leg) > 0 else 0
                        try:
                            p.changeConstraint(joints[('hip', side)],
                                             jointChildPivot=[0, 0.15*math.sin(hp), 0.15*math.cos(hp)],
                                             maxForce=force)
                            p.changeConstraint(joints[('knee', side)],
                                             jointChildPivot=[0, 0.12*math.sin(kp), 0.12*math.cos(kp)],
                                             maxForce=force*0.7)
                        except: pass

            if step % 250 == 0:
                p.addUserDebugText(
                    f"{display_gait['hexagram_name']} | {display_gait['gait_name']} | {display_gait['speed']:.2f}m/s",
                    [0, 0, 1.6], [1, 1, 0], 1.2, lifeTime=1.0)

            p.stepSimulation()
            if step % 8 == 0: time.sleep(0.016)

            if step - last_log >= 500:
                g = display_gait
                print(f"{sim_time:>4.1f}s {name:<8} {g['hexagram_name']:<10} "
                      f"{g['gait_name']:<8} {g['speed']:>3.2f} {g.get('yin_yang','------')}")
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
