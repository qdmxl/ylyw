#!/usr/bin/env python3
"""
YLYW 运动控制仿真 — MuJoCo版
精细人形机器人 + 物理渲染 + 10种步态演示
"""
import sys, os, time, math, numpy as np

# 强制软件渲染 + 窗口装饰修复
os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')
os.environ.setdefault('EGL_PLATFORM', 'x11')
os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
os.environ.setdefault('GLFW_IM_MODULE', 'ibus')
os.environ.setdefault('GDK_BACKEND', 'x11')              # 强制GTK用X11
os.environ.setdefault('XDG_SESSION_TYPE', 'x11')       # 避免Wayland窗口装饰问题
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_locomotion import YLYWLocomotionController
import mujoco, mujoco.viewer


XML = '''
<mujoco>
  <option timestep="0.005" gravity="0 0 -9.81"/>
  <asset>
    <texture name="grid" type="2d" builtin="checker" width="512" height="512"
             rgb1="0.2 0.3 0.4" rgb2="0.35 0.45 0.55"/>
    <material name="grid" texture="grid" texrepeat="10 10" reflectance="0.15"/>
    <material name="torso" rgba="0.28 0.48 0.78 1" shininess="0.6"/>
    <material name="head" rgba="0.85 0.75 0.62 1" shininess="0.5"/>
    <material name="limb" rgba="0.22 0.52 0.32 1" shininess="0.4"/>
    <material name="joint" rgba="0.45 0.45 0.50 1" shininess="0.8"/>
    <material name="foot" rgba="0.75 0.22 0.22 1" shininess="0.3"/>
    <material name="arm" rgba="0.55 0.58 0.62 1" shininess="0.4"/>
  </asset>
  <worldbody>
    <light directional="true" pos="4 4 6" dir="-1 -1 -2" diffuse="0.9 0.9 0.9" specular="0.3 0.3 0.3"/>
    <light directional="true" pos="-3 -3 4" dir="1 1 -1" diffuse="0.4 0.4 0.4"/>
    <geom name="floor" type="plane" size="10 10 0.1" material="grid"/>
    
    <body name="torso" pos="0 0 0.95">
      <joint name="slide_x" type="slide" axis="1 0 0"/>  <!-- 躯干沿X轴滑动 -->
      <!-- 躯干 -->
      <geom type="box" size="0.13 0.10 0.22" material="torso"/>
      <geom type="box" size="0.15 0.12 0.06" pos="0 0 0.18" material="torso"/>
      <!-- 头部 -->
      <geom type="sphere" size="0.09" pos="0 0 0.30" material="head"/>
      <!-- 颈部关节 -->
      <geom type="sphere" size="0.04" pos="0 0 0.25" material="joint"/>
      
      <!-- 左臂 -->
      <body pos="0 0.13 0.16">
        <joint type="ball"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.20" size="0.035" material="arm"/>
        <geom type="sphere" size="0.04" material="joint"/>
        <body pos="0 0 -0.20">
          <joint type="hinge" axis="1 0 0" range="-2.5 0.3"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.16" size="0.03" material="arm"/>
        </body>
      </body>
      
      <!-- 右臂 -->
      <body pos="0 -0.13 0.16">
        <joint type="ball"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.20" size="0.035" material="arm"/>
        <geom type="sphere" size="0.04" material="joint"/>
        <body pos="0 0 -0.20">
          <joint type="hinge" axis="1 0 0" range="-2.5 0.3"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.16" size="0.03" material="arm"/>
        </body>
      </body>
      
      <!-- 左腿 -->
      <body pos="0 0.07 -0.22">
        <joint name="lh" type="hinge" axis="0 1 0" range="-1.5 0.5"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.30" size="0.045" material="limb"/>
        <geom type="sphere" size="0.05" material="joint"/>
        <body pos="0 0 -0.30">
          <joint name="lk" type="hinge" axis="1 0 0" range="0 2.0"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.26" size="0.04" material="limb"/>
          <geom type="sphere" size="0.04" material="joint"/>
          <body pos="0 0 -0.26">
            <joint name="la" type="hinge" axis="1 0 0" range="-0.5 0.8"/>
            <geom type="box" size="0.06 0.04 0.025" pos="0.04 0 -0.02" material="foot"/>
          </body>
        </body>
      </body>
      
      <!-- 右腿 -->
      <body pos="0 -0.07 -0.22">
        <joint name="rh" type="hinge" axis="0 1 0" range="-0.5 1.5"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.30" size="0.045" material="limb"/>
        <geom type="sphere" size="0.05" material="joint"/>
        <body pos="0 0 -0.30">
          <joint name="rk" type="hinge" axis="1 0 0" range="0 2.0"/>
          <geom type="capsule" fromto="0 0 0 0 0 -0.26" size="0.04" material="limb"/>
          <geom type="sphere" size="0.04" material="joint"/>
          <body pos="0 0 -0.26">
            <joint name="ra" type="hinge" axis="1 0 0" range="-0.5 0.8"/>
            <geom type="box" size="0.06 0.04 0.025" pos="0.04 0 -0.02" material="foot"/>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor name="sx_m" joint="slide_x" gear="0 0 0 1 0 0"/>
    <motor name="lh_m" joint="lh" gear="1"/>
    <motor name="lk_m" joint="lk" gear="1"/>
    <motor name="la_m" joint="la" gear="1"/>
    <motor name="rh_m" joint="rh" gear="1"/>
    <motor name="rk_m" joint="rk" gear="1"/>
    <motor name="ra_m" joint="ra" gear="1"/>
  </actuator>
</mujoco>
'''


def run_gui(duration=90):
    controller = YLYWLocomotionController()
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)
    
    # 执行器名→ID
    act_ids = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i 
               for i in range(model.nu)}
    
    phase = 0.0; sim_time = 0.0; dt = model.opt.timestep; step = 0
    display_gait = {"hexagram_name": "艮为山", "gait_name": "静止站立", "speed": 0.0}
    last_log = -999; current_gait = None
    
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
    demo_idx = 0; demo_name = demo_seq[0][1]
    
    print(f"{'='*55}")
    print(f"YLYW 运动控制 | MuJoCo渲染 | 10种步态 | 约2分钟")
    print(f"{'='*55}")
    print(f"{'时间':>5} {'场景':<8} {'卦象':<10} {'步态':<10} {'速':>4}")
    print("-" * 48)
    
    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.distance = 2.5
        viewer.cam.azimuth = 50
        viewer.cam.elevation = -12
        viewer.cam.lookat = [0, 0, 0.9]
        
        while viewer.is_running() and sim_time < duration:
            while demo_idx+1 < len(demo_seq) and sim_time >= demo_seq[demo_idx+1][0]:
                demo_idx += 1
            demo_name, dstate = demo_seq[demo_idx][1], demo_seq[demo_idx][2]
            
            if step % 3 == 0:
                current_gait = controller.infer(np.array(dstate), verbose=False)
                if current_gait: display_gait = current_gait
            
            # 关节控制
            for a in act_ids.values():
                data.ctrl[a] = 0
            
            if current_gait:
                spd = current_gait['speed']; freq = current_gait['freq']
                phase += freq * dt * 2 * math.pi; phase %= 2 * math.pi
                
                if spd >= 0.03:
                    amp_h = 0.6 * min(spd, 1.5)
                    amp_k = 0.5 * min(spd, 1.5)
                    for side, off in [('l', 0), ('r', math.pi)]:
                        p = phase + off
                        hip = amp_h * math.sin(p)
                        knee = amp_k * max(0, math.sin(p))
                        data.ctrl[act_ids[f'{side}h_m']] = hip
                        data.ctrl[act_ids[f'{side}k_m']] = knee
                        data.ctrl[act_ids[f'{side}a_m']] = -0.08 * hip
            
            # 躯干沿X轴移动（速度=步态速度）
            slide_speed = 0
            if current_gait:
                slide_speed = current_gait['speed']
            data.ctrl[act_ids['sx_m']] = slide_speed
            
            mujoco.mj_step(model, data)
            time.sleep(0.02)  # 控制视觉速度
            
            if step - last_log >= 200:
                g = display_gait
                print(f"{sim_time:>4.1f}s {demo_name:<8} {g['hexagram_name']:<10} "
                      f"{g['gait_name']:<10} {g['speed']:>3.2f}")
                last_log = step
            
            step += 1; sim_time += dt
            viewer.sync()
    
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
        (32,"放松恢复",[0.55,0.42,0.48,0.38,0.50,0.60]),
        (38,"爬坡前进",[0.48,0.42,0.52,0.32,0.45,0.18]),
        (44,"回到平路",[0.70,0.72,0.68,0.65,0.22,0.78]),
        (50,"减速站立",[0.88,0.78,0.72,0.85,0.10,0.80]),
    ]:
        gp = controller.infer(state, verbose=False)
        print(f"{t:>3}s {name:<8} {gp['hexagram_name']:<10} {gp['gait_name']:<10} {gp['speed']:>4.2f} {gp['yin_yang']}")


if __name__ == '__main__':
    # 重定向stderr以过滤MuJoCo常见无害警告
    import warnings
    warnings.filterwarnings('ignore')
    
    if '--no-gui' in sys.argv:
        run_no_gui()
    else:
        run_gui()
