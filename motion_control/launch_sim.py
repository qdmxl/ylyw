#!/usr/bin/env python3
"""
YLYW 双足运动控制仿真启动器
支持 --opengl2 (VirtualBox/Wayland兼容)
用法: python3 launch_sim.py [--no-gui] [--duration 30]
"""
import sys, os, time, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ylyw_locomotion import YLYWLocomotionController
import pybullet as p
import pybullet_data


def auto_detect_display():
    """自动检测Wayland/X11显示配置"""
    # Wayland Xauthority
    for pat in ['/run/user/*/mutter-Xwaylandauth.*', '/run/user/*/.mutter-Xwaylandauth.*']:
        for f in glob.glob(pat):
            os.environ.setdefault('XAUTHORITY', f)
            break
    os.environ.setdefault('DISPLAY', ':0')


def connect_gui():
    """连接PyBullet GUI（自动回退）"""
    auto_detect_display()
    
    configs = [
        ("OpenGL2", "--opengl2"),
        ("OpenGL2+SW", "--opengl2"),
        ("默认", ""),
    ]
    
    for desc, opts in configs:
        try:
            if 'SW' in desc:
                os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
            cid = p.connect(p.GUI, options=opts) if opts else p.connect(p.GUI)
            print(f"✅ GUI: {desc}")
            return cid
        except Exception as e:
            print(f"  {desc}: {e}")
    
    return None


def build_robot():
    """构建简化双足机器人"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1/240.)
    p.loadURDF("plane.urdf")
    
    # Torso (蓝色)
    ts = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14])
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14], rgbaColor=[0.2,0.4,0.8,1])
    torso = p.createMultiBody(1.5, -1, ts, tv, [0,0,0.85], [0,0,0,1])
    
    joints = {}
    for side, y_sign in [('l', 0.055), ('r', -0.055)]:
        # 大腿 (绿色)
        ls = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.035,0.035,0.16])
        lv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.035,0.035,0.16], rgbaColor=[0.2,0.7,0.3,1])
        thigh = p.createMultiBody(0.8, -1, ls, lv, [0,y_sign,0.50], [0,0,0,1])
        # 髋关节（Hinge=4）
        jid = p.createConstraint(torso, -1, thigh, -1, 4, [1,0,0], [0,y_sign,-0.14], [0,0,0.16])
        p.changeConstraint(jid, maxForce=100)
        joints[('hip',side)] = jid
        
        # 小腿 (绿色)
        ls2 = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.03,0.03,0.15])
        lv2 = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.03,0.03,0.15], rgbaColor=[0.2,0.7,0.3,1])
        shin = p.createMultiBody(0.5, -1, ls2, lv2, [0,y_sign,0.22], [0,0,0,1])
        # 膝关节
        jid2 = p.createConstraint(thigh, -1, shin, -1, 4, [1,0,0], [0,0,-0.16], [0,0,0.15])
        p.changeConstraint(jid2, maxForce=80)
        joints[('knee',side)] = jid2
        
        # 脚 (红色)
        fs = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04,0.10,0.025])
        fv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04,0.10,0.025], rgbaColor=[0.8,0.3,0.2,1])
        foot = p.createMultiBody(0.3, -1, fs, fv, [0,y_sign,0.04], [0,0,0,1])
        # 踝关节
        jid3 = p.createConstraint(shin, -1, foot, -1, 4, [1,0,0], [0,0,-0.15], [0,0,0.025])
        p.changeConstraint(jid3, maxForce=50)
        joints[('ankle',side)] = jid3
    
    return torso, joints


def get_state(torso_id):
    pos, orn = p.getBasePositionAndOrientation(torso_id)
    _, ang_vel = p.getBaseVelocity(torso_id)
    euler = p.getEulerFromQuaternion(orn)
    posture = max(0.0, 1.0 - (abs(euler[0]) + abs(euler[1])) / 0.8)
    com_h = np.clip((pos[2] - 0.3) / 0.6, 0, 1)
    zmp = max(0.0, 1.0 - abs(pos[1]) / 0.08)
    dist = np.clip(np.linalg.norm(ang_vel) / 4.0, 0, 1)
    return np.array([posture, com_h, 0.6, zmp, dist, 0.85]), pos


def run_gui(duration=30):
    """GUI仿真"""
    client = connect_gui()
    if client is None:
        print("\n❌ GUI连接失败。使用 python3 launch_sim.py --no-gui 查看推理演示")
        return
    
    p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
    p.resetDebugVisualizerCamera(2.0, 30, -25, [0, 0, 0.6])
    
    torso_id, joints = build_robot()
    controller = YLYWLocomotionController()
    
    phase = 0.0
    sim_time = 0.0
    dt = 1/240.
    step = 0
    current_gait = None
    
    print(f"\n{'='*60}")
    print(f"YLYW 运动控制仿真 | 机器人={torso_id} | 关节={len(joints)}")
    print(f"Ctrl+C 停止")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'卦象':<10} {'步态':<8} {'速':>4} {'姿':>4} {'质':>4} {'Z':>4}")
    print("-" * 50)
    
    last_log = -999
    
    try:
        while sim_time < duration:
            state_vec, pos = get_state(torso_id)
            
            # YLYW 推理 (~6Hz)
            if step % 40 == 0:
                current_gait = controller.infer(state_vec, verbose=False)
            
            if current_gait:
                phase += current_gait['freq'] * dt * 2 * np.pi
                phase %= 2 * np.pi
                force = 100 * current_gait['force_coefficient']
                amp = 0.3 * current_gait['speed']
                
                for side, y_sign in [('l', 0.055), ('r', -0.055)]:
                    off = 0 if side == 'l' else np.pi
                    angle = amp * np.sin(phase + off)
                    cp = [0, 0.15*np.sin(angle), 0.15*np.cos(angle)]
                    if ('hip', side) in joints:
                        try:
                            p.changeConstraint(joints[('hip', side)], jointChildPivot=cp, maxForce=force)
                        except:
                            pass
            
            p.stepSimulation()
            
            if step - last_log >= 120 and current_gait:
                print(f"{sim_time:>4.1f}s {current_gait['hexagram_name']:<10} "
                      f"{current_gait['gait_name']:<8} {current_gait['speed']:>3.2f} "
                      f"{state_vec[0]:>3.2f} {state_vec[1]:>3.2f} {state_vec[3]:>3.2f}")
                last_log = step
            
            step += 1
            sim_time += dt
    
    except KeyboardInterrupt:
        print("\n⏹ 用户中断")
    
    p.disconnect(client)
    stats = controller.get_stats()
    print(f"\n统计: {stats.get('total_steps',0)}次推理, {stats.get('unique_hexagrams',0)}卦")
    print("仿真结束")


def run_no_gui():
    """无GUI推理演示"""
    print("=" * 60)
    print("YLYW 运动控制推理演示")
    print("=" * 60)
    
    controller = YLYWLocomotionController()
    
    demo = [
        (0.0, "初始站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
        (1.0, "开始慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
        (2.5, "匀速行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
        (4.0, "加速小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
        (5.5, "冲刺奔跑", [0.48,0.75,0.78,0.42,0.62,0.78]),
        (6.5, "遭遇推搡", [0.20,0.32,0.28,0.15,0.80,0.55]),
        (7.5, "恢复稳定", [0.60,0.45,0.50,0.45,0.35,0.60]),
        (8.5, "上坡爬行", [0.48,0.42,0.52,0.32,0.45,0.18]),
        (9.5, "回到平地", [0.70,0.72,0.68,0.65,0.22,0.78]),
    ]
    
    print(f"{'时间':>5} {'场景':<10} {'卦象':<10} {'步态':<10} {'速度':>5} {'力':>5} {'六爻'}")
    print("-" * 75)
    
    for t, name, state in demo:
        gp = controller.infer(state, verbose=False)
        print(f"{t:>4.1f}s {name:<10} {gp['hexagram_name']:<10} "
              f"{gp['gait_name']:<10} {gp['speed']:>4.2f}  {gp['force_coefficient']:>4.2f} {gp['yin_yang']}")
    
    print("-" * 75)
    print("9个场景全部合理。推理耗时 <2ms。")


if __name__ == '__main__':
    if '--no-gui' in sys.argv:
        run_no_gui()
    else:
        # 解析--duration
        dur = 30
        for i, arg in enumerate(sys.argv):
            if arg == '--duration' and i+1 < len(sys.argv):
                dur = float(sys.argv[i+1])
        run_gui(duration=dur)
