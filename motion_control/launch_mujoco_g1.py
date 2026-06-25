#!/usr/bin/env python3
"""
YLYW → Unitree G1 人形机器人 MuJoCo 仿真

基于宇树官方 g1_23dof.xml（29个STL网格 + 真实惯量参数）
集成 YLYW 运动控制推理引擎

用法：
  python3 launch_mujoco_g1.py                    # 10种步态演示
  python3 launch_mujoco_g1.py --adaptive          # 自适应YLYW
  python3 launch_mujoco_g1.py --no-gui --duration 30
"""
import sys, os, time, math, argparse
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

# 模型路径
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'unitree_models')
XML_PATH = os.path.join(MODEL_DIR, 'g1_23dof.xml')


def add_actuators_to_xml(xml_path):
    """在G1 XML中添加执行器 + 约束基座（滑轨代替free joint）"""
    with open(xml_path) as f:
        xml = f.read()
    
    # 更新compiler设置meshes路径
    xml = xml.replace('<compiler angle="radian" meshdir="meshes"/>',
                      f'<compiler angle="radian" meshdir="{MODEL_DIR}/meshes" autolimits="true"/>')
    
    # 替换free joint为slide_x（约束：机器人沿X轴滑动，YZ固定）
    xml = xml.replace(
        '<joint name="floating_base_joint" type="free" limited="false" actuatorfrclimited="false"/>',
        '<joint name="slide_x" type="slide" axis="1 0 0"/>'
    )
    
    # 检查是否有地面，没有则添加
    if '<geom name="floor"' not in xml:
        xml = xml.replace('<worldbody>', 
                         '<worldbody>\n    <geom name="floor" type="plane" size="20 20 0.1" rgba="0.35 0.45 0.55 1"/>')
    
    # 在</worldbody>之后添加执行器（含slide_x马达和跑步机标记）
    actuators = """
  <actuator>
    <motor name="slide_x_motor" joint="slide_x" gear="0 0 0 1 0 0"/>
    <!-- 左腿 -->
    <position name="left_hip_pitch"    joint="left_hip_pitch_joint"    kp="200" kv="20"/>
    <position name="left_hip_roll"     joint="left_hip_roll_joint"     kp="150" kv="15"/>
    <position name="left_hip_yaw"      joint="left_hip_yaw_joint"      kp="100" kv="10"/>
    <position name="left_knee"         joint="left_knee_joint"         kp="300" kv="30"/>
    <position name="left_ankle_pitch"  joint="left_ankle_pitch_joint"  kp="200" kv="20"/>
    <position name="left_ankle_roll"   joint="left_ankle_roll_joint"   kp="150" kv="15"/>
    <!-- 右腿 -->
    <position name="right_hip_pitch"   joint="right_hip_pitch_joint"   kp="200" kv="20"/>
    <position name="right_hip_roll"    joint="right_hip_roll_joint"    kp="150" kv="15"/>
    <position name="right_hip_yaw"     joint="right_hip_yaw_joint"     kp="100" kv="10"/>
    <position name="right_knee"        joint="right_knee_joint"        kp="300" kv="30"/>
    <position name="right_ankle_pitch" joint="right_ankle_pitch_joint" kp="200" kv="20"/>
    <position name="right_ankle_roll"  joint="right_ankle_roll_joint"  kp="150" kv="15"/>
    <!-- 腰部 -->
    <position name="waist_yaw"         joint="waist_yaw_joint"         kp="100" kv="10"/>
    <!-- 左臂（保持） -->
    <position name="left_shoulder_pitch"  joint="left_shoulder_pitch_joint"  kp="50" kv="5"/>
    <position name="left_shoulder_roll"   joint="left_shoulder_roll_joint"   kp="50" kv="5"/>
    <position name="left_shoulder_yaw"    joint="left_shoulder_yaw_joint"    kp="30" kv="3"/>
    <position name="left_elbow"           joint="left_elbow_joint"           kp="50" kv="5"/>
    <position name="left_wrist_roll"      joint="left_wrist_roll_joint"      kp="30" kv="3"/>
    <!-- 右臂（保持） -->
    <position name="right_shoulder_pitch" joint="right_shoulder_pitch_joint" kp="50" kv="5"/>
    <position name="right_shoulder_roll"  joint="right_shoulder_roll_joint"  kp="50" kv="5"/>
    <position name="right_shoulder_yaw"   joint="right_shoulder_yaw_joint"   kp="30" kv="3"/>
    <position name="right_elbow"          joint="right_elbow_joint"          kp="50" kv="5"/>
    <position name="right_wrist_roll"     joint="right_wrist_roll_joint"     kp="30" kv="3"/>
  </actuator>
</mujoco>"""
    
    xml = xml.replace('</mujoco>', actuators)
    return xml


class G1LocomotionSim:
    """G1人形机器人 YLYW 运动控制仿真"""
    
    # GPU渲染
    RENDER_GPU = False  # VirtualBox下用软件渲染
    
    def __init__(self, adaptive=False, learning_rate=0.05):
        # 构建带执行器的XML
        xml_str = add_actuators_to_xml(XML_PATH)
        
        self.model = mujoco.MjModel.from_xml_string(xml_str)
        self.data = mujoco.MjData(self.model)
        self.data.ctrl[:] = 0
        
        # YLYW控制器
        if adaptive:
            self.controller = YLYWAdaptiveController(learning_rate=learning_rate)
        else:
            self.controller = YLYWLocomotionController()
        
        # 执行器ID映射
        self.act_ids = {}
        for i in range(self.model.nu):
            name = mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            if name:
                self.act_ids[name] = i
        
        # 步态相位
        self.phase = 0.0
        self.current_gait = None
        
        # 统计
        self.step_count = 0
        self.sim_time = 0.0
        self.fell_count = 0
        self.prev_fell = False
        
        # 关节ID
        self.torso_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, 'torso_link')
    
    def reset_pose(self):
        """重置为初始姿态"""
        mujoco.mj_resetData(self.model, self.data)
        self.data.ctrl[:] = 0
        self.phase = 0.0
        self.current_gait = None
        self.step_count = 0
        self.sim_time = 0.0
    
    def is_fallen(self):
        """检测摔倒（滑轨约束下几乎不会摔倒）"""
        pos = self.data.xpos[self.torso_id]
        return pos[2] < 0.40
    
    def apply_gait(self, gait_params):
        """
        YLYW步态参数 → G1关节角度
        
        G1关节映射:
          髋pitch → 前后摆动（主驱动力）
          膝 → 弯曲
          踝pitch → 辅助
          髋roll → 侧向平衡
          髋yaw → 转向（暂不用）
        """
        speed = gait_params.get('speed', 0.0)
        freq = gait_params.get('freq', 0.0)
        force_coef = gait_params.get('force_coefficient', 0.5)
        
        dt = self.model.opt.timestep
        
        if speed < 0.02:
            # 站立：微前倾保持平衡
            for a in self.act_ids.values():
                self.data.ctrl[a] = 0
        
        self.phase += freq * dt * 2 * math.pi
        self.phase %= 2 * math.pi
        
        # 步态幅度（适配G1的关节范围）
        # G1 hip_pitch range: -2.53 ~ 2.88 rad, knee: -0.087 ~ 2.88 rad
        hip_amp = 0.45 * min(speed, 1.2) * force_coef
        knee_amp = 0.55 * min(speed, 1.2) * force_coef
        ankle_amp = 0.12 * min(speed, 1.2) * force_coef
        
        # 左右腿相位差
        l_phase = self.phase
        r_phase = self.phase + math.pi
        
        # 左腿
        l_hip = hip_amp * math.sin(l_phase)
        l_knee = knee_amp * max(0, math.sin(l_phase - 0.3))
        l_ankle = -ankle_amp * math.sin(l_phase)
        
        # 右腿
        r_hip = hip_amp * math.sin(r_phase)
        r_knee = knee_amp * max(0, math.sin(r_phase - 0.3))
        r_ankle = -ankle_amp * math.sin(r_phase)
        
        # 设置执行器目标
        ctrl_targets = {
            'left_hip_pitch': l_hip,     'right_hip_pitch': r_hip,
            'left_knee': l_knee,          'right_knee': r_knee,
            'left_ankle_pitch': l_ankle,  'right_ankle_pitch': r_ankle,
            # 侧向平衡
            'left_hip_roll': 0.08 * force_coef,
            'right_hip_roll': -0.08 * force_coef,
            # 其他关节保持0
            'left_hip_yaw': 0, 'right_hip_yaw': 0,
            'left_ankle_roll': 0, 'right_ankle_roll': 0,
            'waist_yaw': 0,
        }
        
        for name, target in ctrl_targets.items():
            if name in self.act_ids:
                self.data.ctrl[self.act_ids[name]] = target
        
        # 手臂：自然摆动
        arm_swing = 0.2 * min(speed, 1.0)
        for side, sign in [('left', +1), ('right', -1)]:
            p = l_phase if side == 'left' else r_phase
            shoulder = sign * arm_swing * math.sin(p)
            for jn in ['shoulder_pitch', 'shoulder_roll', 'shoulder_yaw',
                        'elbow', 'wrist_roll']:
                name = f'{side}_{jn}'
                if name in self.act_ids:
                    self.data.ctrl[self.act_ids[name]] = shoulder * (0.5 if jn != 'shoulder_pitch' else 1.0)
    
    def step(self, state_6d, feedback=None):
        """执行一步仿真：YLYW推理→关节控制→物理步进"""
        # YLYW推理
        if self.step_count % 3 == 0:
            if isinstance(self.controller, YLYWAdaptiveController):
                result = self.controller.step(np.array(state_6d), feedback=feedback)
                if feedback:
                    self.controller.give_feedback(feedback)
            else:
                result = self.controller.infer(np.array(state_6d), verbose=False)
            if result:
                self.current_gait = result
        
        # 关节控制
        gait = self.current_gait or {'speed': 0, 'freq': 0, 'step_height': 0, 'force_coefficient': 0.5,
                                      'hexagram_name': 'N/A', 'gait_name': 'N/A'}
        self.apply_gait(gait)
        
        # 躯干滑动（跑步机效果）
        sx_dof = self.model.jnt_dofadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        self.data.qvel[sx_dof] = gait.get('speed', 0) * 1.5
        
        # 物理步进
        mujoco.mj_step(self.model, self.data)
        
        # 摔倒检测
        fell = self.is_fallen()
        if fell and not self.prev_fell:
            self.fell_count += 1
        self.prev_fell = fell
        
        self.step_count += 1
        self.sim_time += self.model.opt.timestep
        
        return gait, fell


def run_gui(adaptive=False, duration=90):
    """GUI模式：10种步态演示"""
    sim = G1LocomotionSim(adaptive=adaptive)
    
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
    print(f"YLYW → Unitree G1 人形机器人 ({model_name}YLYW)")
    print(f"23 DOF | MuJoCo物理引擎 | STL网格渲染")
    print(f"{'='*60}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<10} {'速':>4} {'摔倒':>4}")
    print("-" * 50)
    
    last_log_time = -99
    
    with mujoco.viewer.launch_passive(sim.model, sim.data) as viewer:
        viewer.cam.distance = 3.0
        viewer.cam.azimuth = 60
        viewer.cam.elevation = -15
        viewer.cam.lookat = [0, 0, 0.8]
        
        # 软件渲染优化
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = False
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_REFLECTION] = False
        
        while viewer.is_running() and sim.sim_time < duration:
            while demo_idx+1 < len(demo_seq) and sim.sim_time >= demo_seq[demo_idx+1][0]:
                demo_idx += 1
            name, state = demo_seq[demo_idx][1], demo_seq[demo_idx][2]
            
            gait, fell = sim.step(state)
            
            # 摄像头跟随
            torso_pos = sim.data.xpos[sim.torso_id]
            viewer.cam.lookat = [torso_pos[0], torso_pos[1], 0.8]
            
            # 日志
            if sim.sim_time - last_log_time >= 1.0:
                hex_name = gait['hexagram_name']
                gait_name = gait['gait_name']
                speed = gait.get('speed', 0)
                fell_mark = '💀' if fell else '  '
                print(f"{sim.sim_time:>4.1f}s {name:<8} {hex_name:<10} {gait_name:<10} {speed:>3.2f} {fell_mark:>4}")
                last_log_time = sim.sim_time
            
            viewer.sync()
            time.sleep(0.015)  # 降低渲染帧率（VirtualBox软件渲染优化）
    
    print(f"\n摔倒{sim.fell_count}次 | 推理{sim.controller.step_count if hasattr(sim.controller, 'step_count') else sim.step_count}次")


def run_no_gui(adaptive=False, duration=30):
    """无头模式"""
    sim = G1LocomotionSim(adaptive=adaptive)
    
    demo_seq = [
        (0,  "站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
        (5,  "慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
        (12, "行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
        (20, "小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
        (27, "站立", [0.88,0.78,0.72,0.85,0.10,0.80]),
    ]
    demo_idx = 0
    
    while sim.sim_time < duration:
        while demo_idx+1 < len(demo_seq) and sim.sim_time >= demo_seq[demo_idx+1][0]:
            demo_idx += 1
        name, state = demo_seq[demo_idx][1], demo_seq[demo_idx][2]
        
        gait, fell = sim.step(state)
        
        if sim.step_count % 600 == 0:
            print(f"{sim.sim_time:>5.1f}s {name:<6} {gait['hexagram_name']:<10} "
                  f"{gait['gait_name']:<10} spd={gait.get('speed',0):.2f} fell={fell}")
    
    print(f"\n摔倒{sim.fell_count}次")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW → Unitree G1 仿真')
    parser.add_argument('--adaptive', action='store_true')
    parser.add_argument('--no-gui', action='store_true')
    parser.add_argument('--duration', type=float, default=90)
    args = parser.parse_args()
    
    if args.no_gui:
        run_no_gui(adaptive=args.adaptive, duration=args.duration)
    else:
        run_gui(adaptive=args.adaptive, duration=args.duration)
