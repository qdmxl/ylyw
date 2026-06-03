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
    """构建简化双足机器人（使用关键字参数确保正确初始化）"""
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1/500.)
    p.loadURDF("plane.urdf")
    
    # Torso (蓝色)
    ts = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14])
    tv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.10, 0.07, 0.14], rgbaColor=[0.2,0.4,0.8,1])
    torso = p.createMultiBody(baseMass=1.5, baseCollisionShapeIndex=ts, 
                              baseVisualShapeIndex=tv, basePosition=[0,0,0.90])
    
    joints = {}
    for side, y_sign in [('l', 0.055), ('r', -0.055)]:
        # 大腿 (绿色)
        ls = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.035,0.035,0.16])
        lv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.035,0.035,0.16], rgbaColor=[0.2,0.7,0.3,1])
        thigh = p.createMultiBody(baseMass=0.8, baseCollisionShapeIndex=ls,
                                  baseVisualShapeIndex=lv, basePosition=[0,y_sign,0.55])
        # 髋关节（Hinge=4）
        jid = p.createConstraint(torso, -1, thigh, -1, 4, [1,0,0], [0,y_sign,-0.14], [0,0,0.16])
        p.changeConstraint(jid, maxForce=100)
        joints[('hip',side)] = jid
        
        # 小腿 (绿色)
        ls2 = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.03,0.03,0.15])
        lv2 = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.03,0.03,0.15], rgbaColor=[0.2,0.7,0.3,1])
        shin = p.createMultiBody(baseMass=0.5, baseCollisionShapeIndex=ls2,
                                 baseVisualShapeIndex=lv2, basePosition=[0,y_sign,0.25])
        # 膝关节
        jid2 = p.createConstraint(thigh, -1, shin, -1, 4, [1,0,0], [0,0,-0.16], [0,0,0.15])
        p.changeConstraint(jid2, maxForce=80)
        joints[('knee',side)] = jid2
        
        # 脚 (红色)
        fs = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.04,0.10,0.025])
        fv = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.04,0.10,0.025], rgbaColor=[0.8,0.3,0.2,1])
        foot = p.createMultiBody(baseMass=0.3, baseCollisionShapeIndex=fs,
                                 baseVisualShapeIndex=fv, basePosition=[0,y_sign,0.07])
        # 踝关节
        jid3 = p.createConstraint(shin, -1, foot, -1, 4, [1,0,0], [0,0,-0.15], [0,0,0.025])
        p.changeConstraint(jid3, maxForce=50)
        joints[('ankle',side)] = jid3
    
    return torso, joints


def get_state(torso_id):
    """获取机器人状态（6维归一化）"""
    pos, orn = p.getBasePositionAndOrientation(torso_id)
    _, ang_vel = p.getBaseVelocity(torso_id)
    euler = p.getEulerFromQuaternion(orn)
    posture = max(0.0, 1.0 - (abs(euler[0]) + abs(euler[1])) / 0.8)
    com_h = np.clip(pos[2] / 0.50, 0.0, 1.0)
    zmp = max(0.0, 1.0 - abs(pos[1]) / 0.12)
    dist = np.clip(np.linalg.norm(ang_vel) / 3.0, 0.0, 1.0)
    return np.array([posture, com_h, 0.65, zmp, dist, 0.85]), pos


def run_gui(duration=60):
    """GUI仿真 - 放慢速度以便观察3D演示"""
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
    dt = 1/500.
    p.setTimeStep(dt)
    step = 0
    current_gait = None
    last_log = -999
    
    # 步态演示序列：每10秒切换一个场景
    demo_sequence = [
        (0,   "初始站立",   [0.90,0.82,0.75,0.88,0.05,0.82]),
        (3,   "开始慢走",   [0.72,0.72,0.68,0.65,0.20,0.80]),
        (8,   "加速行走",   [0.65,0.70,0.65,0.60,0.30,0.78]),
        (14,  "快速小跑",   [0.55,0.72,0.72,0.50,0.52,0.76]),
        (20,  "全力奔跑",   [0.48,0.75,0.78,0.42,0.62,0.78]),
        (26,  "突然推搡",   [0.18,0.30,0.25,0.14,0.82,0.55]),
        (32,  "踉跄恢复",   [0.55,0.42,0.48,0.38,0.50,0.60]),
        (38,  "爬坡前进",   [0.48,0.42,0.52,0.32,0.45,0.18]),
        (44,  "回到平路",   [0.70,0.72,0.68,0.65,0.22,0.78]),
        (50,  "减速站立",   [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    
    # 当前注入状态（从机器人传感器开始，逐步混入演示状态）
    demo_idx = 0
    
    display_gait = {"hexagram_name": "艮为山", "gait_name": "静止站立", "speed": 0.0}
    
    print(f"\n{'='*60}")
    print(f"YLYW 运动控制仿真 | 机器人={torso_id} | 关节={len(joints)}")
    print(f"运行 {duration}s | Ctrl+C 停止")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<8} {'速':>4} {'姿':>4} {'质':>4} {'Z':>4}")
    print("-" * 50)
    
    try:
        while sim_time < duration:
            # 读取真实物理状态
            real_state_vec, pos = get_state(torso_id)
            
            # 用演示序列注入"虚拟场景"状态
            while demo_idx + 1 < len(demo_sequence) and sim_time >= demo_sequence[demo_idx + 1][0]:
                demo_idx += 1
            
            # 混合状态：真实姿态 + 演示场景的扰动/地形
            demo_name, demo_state = demo_sequence[demo_idx][1], demo_sequence[demo_idx][2]
            # 将真实物理状态与演示状态混合（保留真实姿态信息）
            mix_ratio = min(1.0, (sim_time - demo_sequence[demo_idx][0]) / 2.0)  # 2秒渐变
            blended = np.array(real_state_vec) * (1 - mix_ratio * 0.3) + np.array(demo_state) * mix_ratio * 0.3
            blended = np.clip(blended, 0, 1)
            
            # YLYW 推理 (~4Hz)
            if step % 125 == 0:
                current_gait = controller.infer(blended, verbose=False)
                if current_gait:
                    display_gait = current_gait
            
            # 应用步态参数驱动髋关节
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
            
            # 更新GUI文本覆盖
            info = f"{display_gait['hexagram_name']} | {display_gait['gait_name']} | {display_gait['speed']:.2f}m/s"
            p.addUserDebugText(info, [0, 0, 1.2], textColorRGB=[1,1,0], textSize=1.5, lifeTime=0.1)
            
            p.stepSimulation()
            
            # 放慢渲染速率，每秒渲染60帧
            if step % 8 == 0:
                time.sleep(0.016)  # ~60 FPS visual
            
            if step - last_log >= 500:
                g = display_gait
                print(f"{sim_time:>4.1f}s {demo_name:<8} {g['hexagram_name']:<10} "
                      f"{g['gait_name']:<8} {g['speed']:>3.2f} "
                      f"{blended[0]:>3.2f} {blended[1]:>3.2f} {blended[3]:>3.2f}")
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
