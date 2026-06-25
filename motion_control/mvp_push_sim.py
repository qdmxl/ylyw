#!/usr/bin/env python3
"""
YLYW MVP 仿真 → 生成带时间戳的截图 + 视频(AVI)
"""
import os, math, numpy as np, cv2
os.environ.update({'LIBGL_ALWAYS_SOFTWARE': '1', 'EGL_PLATFORM': 'x11'})
import mujoco
from PIL import Image, ImageDraw, ImageFont
import io

W, H = 450, 450

XML = '''<mujoco>
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <visual><global offwidth="450" offheight="450"/></visual>
  <asset>
    <texture name="grid" type="2d" builtin="checker" width="512" height="512" rgb1="0.25 0.3 0.38" rgb2="0.35 0.4 0.48"/>
    <material name="grid" texture="grid" texrepeat="10 10" reflectance="0.1"/>
    <material name="pusher" rgba="0.28 0.48 0.78 0.95"/>
    <material name="obj" rgba="0.95 0.65 0.15 1"/>
    <material name="tgt" rgba="0.15 0.85 0.35 0.5"/>
  </asset>
  <worldbody>
    <light directional="true" pos="3 5 6" dir="-1 -2 -2" diffuse="0.9 0.9 0.9"/>
    <geom name="floor" type="plane" size="5 5 0.1" material="grid" friction="0.05 0.001 0.00001"/>
    <body name="pusher" pos="0 0 0.06">
      <joint name="px" type="slide" axis="1 0 0"/>
      <geom type="box" size="0.05 0.08 0.06" material="pusher"/>
    </body>
    <body name="obj" pos="0.35 0 0.05">
      <joint name="ox" type="slide" axis="1 0 0"/>
      <geom type="box" size="0.06 0.06 0.06" material="obj" mass="0.5"/>
    </body>
    <body name="tgt" pos="1.20 0 0.005">
      <geom name="tgt_g" type="cylinder" size="0.12 0.005" material="tgt"/>
    </body>
  </worldbody>
  <actuator>
    <position name="pm" joint="px" kp="200" kv="25"/>
  </actuator>
</mujoco>'''


class YLYW:
    def __init__(self):
        self.target_x = 1.2
    def control(self, ox):
        err = self.target_x - ox
        d = abs(err)
        if d < 0.02: return ox, 'done'
        if d > 0.3:   overshoot = 0.30
        elif d > 0.1: overshoot = 0.18
        else:         overshoot = 0.08
        return ox + overshoot, 'push'

class RandomMLP:
    def __init__(self, seed=888):
        rng = np.random.RandomState(seed)
        self.W1 = rng.randn(3,16)*5; self.W2 = rng.randn(16,1)*6
        self.b1 = rng.randn(16)*4; self.b2 = rng.randn(1)*4
        self.t = 0
    def control(self, ox):
        self.t += 0.002
        x = np.array([ox, math.sin(self.t*7), math.cos(self.t*5)])
        h = np.tanh(x@self.W1+self.b1)
        return float((h@self.W2+self.b2)[0]), 'chaotic'


def annotate_frame(pixels, name, t, ox, px):
    """Overlay timestamp, object position, and controller name on frame"""
    img = Image.fromarray(pixels)
    draw = ImageDraw.Draw(img)
    
    # Color bar at top
    color = (40, 100, 200) if name == 'YLYW' else (200, 60, 40)
    draw.rectangle([(0, 0), (W, 36)], fill=color)

    # Controller name (left)
    label = 'YLYW (Yijing Rules)' if name == 'YLYW' else 'Random MLP (Zero-shot)'
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except:
        font = ImageFont.load_default()
    draw.text((8, 6), label, fill=(255,255,255), font=font)

    # Timestamp (right)
    draw.text((W-140, 6), 't = %.1f s' % t, fill=(255,255,255), font=font)

    # Object info (bottom)
    draw.rectangle([(0, H-28), (W, H)], fill=(30,30,30,180))
    obj_text = f'Object X: {ox:.3f}m  |  Pusher X: {px:.3f}m  |  Target: 1.20m'
    draw.text((8, H-24), obj_text, fill=(220,220,220), font=font)

    return np.array(img)


def simulate(ctrl_class, name, out_dir, fps=30):
    """Run simulation, capture frames, save video + annotated snapshots"""
    os.makedirs(out_dir, exist_ok=True)
    
    model = mujoco.MjModel.from_xml_string(XML)
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, W, H)
    cam = mujoco.MjvCamera()
    cam.lookat = (0.6, 0.0, 0.12)
    cam.distance = 2.2
    cam.elevation = -12
    cam.azimuth = 170
    opt = mujoco.MjvOption()
    dt = model.opt.timestep
    
    # Duration: 25s, record every other physics step to match fps
    duration = 25.0
    record_interval = int(1.0 / (fps * dt))  # steps per frame
    total_frames = int(fps * duration)
    
    # Video writer (AVI format, MJPG codec for compatibility)
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    video_path = os.path.join(out_dir, f'{name}_simulation.avi')
    video_writer = cv2.VideoWriter(video_path, fourcc, fps, (W, H))
    
    # Snapshot times (for paper figures)
    snapshot_times = [0.0, 5.0, 12.5, 24.5]
    snapshot_idx = 0
    
    ctrl = ctrl_class()
    px_hist, ox_hist = [], []
    
    print(f'  [{name}] Recording {total_frames} frames...')
    frame_count = 0
    for step in range(int(duration / dt)):
        t = step * dt
        
        if step == 0:
            mujoco.mj_forward(model, data)
        
        ox = data.body('obj').xpos[0]
        px = data.body('pusher').xpos[0]
        
        target, phase = ctrl.control(ox)
        data.ctrl[0] = target
        mujoco.mj_step(model, data)
        
        # Record at fps rate
        if step % record_interval == 0:
            mujoco.mjv_updateScene(model, data, opt, None, cam,
                                   mujoco.mjtCatBit.mjCAT_ALL, renderer.scene)
            renderer.update_scene(data)
            pixels = renderer.render()
            
            # Annotate
            annotated = annotate_frame(pixels, name, t, ox, px)
            
            # Write video frame
            video_writer.write(cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))
            frame_count += 1
            
            # Save snapshot if at target time
            if snapshot_idx < len(snapshot_times) and t >= snapshot_times[snapshot_idx]:
                snap_path = os.path.join(out_dir, f'{name}_t{snapshot_times[snapshot_idx]:.1f}s.png')
                Image.fromarray(annotated).save(snap_path)
                print(f'    snapshot: t={snapshot_times[snapshot_idx]:.1f}s  ox={ox:.3f}m  px={px:.3f}m')
                snapshot_idx += 1
        
        ox_hist.append(ox)
        px_hist.append(px)
    
    video_writer.release()
    renderer.close()
    
    final_ox = ox_hist[-1]
    return {
        'name': name, 'final_x': final_ox, 'error': abs(final_ox - 1.2),
        'success': abs(final_ox - 1.2) < 0.10,
        'video': video_path,
        'traj': ox_hist[::int(len(ox_hist)/10)]
    }


if __name__ == '__main__':
    out = '/home/lijinhan/MXL/科研/ylyw/motion_control/mvp_screenshots'
    import shutil
    if os.path.isdir(out):
        shutil.rmtree(out)
    
    print('=' * 55)
    print('YLYW MVP: Push-to-Target Simulation + Video Recording')
    print('=' * 55)
    print()
    
    r_ylyw = simulate(YLYW, 'ylyw', out, fps=30)
    print(f'\n  YLYW: final_x={r_ylyw["final_x"]:.3f}m  error={r_ylyw["error"]:.3f}m  '
          f'ok={r_ylyw["success"]}')
    print(f'  Video: {r_ylyw["video"]}')
    
    print()
    r_mlp = simulate(RandomMLP, 'mlp', out, fps=30)
    print(f'\n  MLP:  final_x={r_mlp["final_x"]:.3f}m  error={r_mlp["error"]:.3f}m  '
          f'ok={r_mlp["success"]}')
    print(f'  Video: {r_mlp["video"]}')
    
    print()
    print('=' * 55)
    print('Comparison:')
    print(f'  YLYW: {r_ylyw["final_x"]:.3f}m (err={r_ylyw["error"]:.3f})')
    print(f'  MLP:  {r_mlp["final_x"]:.3f}m (err={r_mlp["error"]:.3f})')
    print()
    print(f'Outputs in: {out}/')
