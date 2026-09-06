#!/usr/bin/env python3
"""MicroDuck 真·MuJoCo 渲染 + 动图(有 OpenGL 则真效果,无则回退点云)。

- 自动探测本机 OpenGL 显示(Wayland/Xwayland 授权),可用则用 MuJoCo Renderer 出真彩图;
- 不可用则回退到 matplotlib 点云渲染(draw_state.draw_state)。
- 支持单帧(某 keyframe 姿态)或动图(配合 ylyw 控制器)。

用法:
  python scripts/render_frames.py --key STAND --out data/shot.png
  python scripts/render_frames.py --key STAND --anim --horizon 2.0 --out data/duck.gif
"""
import os
import sys
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mujoco  # noqa:E402
from gl_env import configure_opengl_env  # noqa:E402
from env.microduck_env import ensure_control_model, SERVO_JOINTS, _HOME  # noqa:E402
from draw_state import draw_state  # noqa:E402


_ALGOS = {}  # 注册动图控制器选择器(可选导入)


def _resolve_controllers(name):
    if not name:
        return ()
    if name == "walk":
        try:
            from ylyw_algos.gait import make_walk_ctrl
            return (make_walk_ctrl(speed_ramp=0.0),)
        except Exception as e:
            print("[warn] walk algo unavailable:", e)
            return ()
    if name == "hold":
        return (hold_stand,)
    if name in ("ylyw2", "ylyw", "zhiji", "v2"):
        try:
            from ylyw_algos.ylyw_gait_v2 import YLYWMicroDuckGait
            return (YLYWMicroDuckGait(intent="walk", lean=0.012),)
        except Exception as e:
            print("[warn] ylyw-v2 algo unavailable:", e)
            return ()
    if name in ("waddle", "ylyww", "duck"):
        try:
            from ylyw_algos.ylyw_gait_v2 import YLYWMicroDuckGait
            return (YLYWMicroDuckGait(intent="waddle"),)
        except Exception as e:
            print("[warn] waddle algo unavailable:", e)
            return ()
    raise SystemExit(f"未知 --algo {name}(可用: walk / hold / ylyw2 / waddle)")


def gl_probe() -> bool:
    try:
        m = mujoco.MjModel.from_xml_string(
            "<mujoco model='g'><worldbody><geom size='0.1'/></worldbody></mujoco>")
        ctx = mujoco.GLContext(64, 64)
        ctx.make_current()
        mujoco.MjrContext(m, mujoco.mjtFontScale.mjFONTSCALE_100)
        return True
    except Exception:
        return False


def _set_camera(ren, model, data, lookat=(0, 0.008, 0.09),
                distance=0.62, elevation=-25, azimuth=135):
    ren.update_scene(data)
    cam = ren.scene.camera[0]
    for name, val in (("distance", distance), ("elevation", elevation),
                      ("azimuth", azimuth)):
        try:
            setattr(cam, name, val)
        except Exception:
            pass
    try:
        cam.lookat[:] = lookat
    except Exception:
        pass


def _fallback(keyframe, out):
    from draw_state import draw_state
    xml = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "models", "microduck", "_ylyw_control_scene.xml")
    print("[真渲染不可用,回退到 matplotlib 点云]")
    draw_state(xml, keyframe=keyframe, out=out)


def render_frames(xml_path=None, out=None, keyframe=None,
                  controllers=(), horizon_s=2.0, step_s=0.05, fps=12):
    xml = xml_path or ensure_control_model()
    m = mujoco.MjModel.from_xml_path(xml)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)

    configure_opengl_env()
    if not gl_probe():
        _fallback(keyframe, out)
        return out

    W = int(m.vis.global_.offwidth)
    H = int(m.vis.global_.offheight)
    ren = mujoco.Renderer(m, height=H, width=W)
    from PIL import Image

    def snap():
        return Image.fromarray(np.ascontiguousarray(ren.render()[:, :, :3]))

    if controllers:
        from env.microduck_env import StandingEnv
        env = StandingEnv(xml_path=xml, control_dt=0.02)
        env.reset(keyframe or "STAND")
        n = int(horizon_s / max(step_s, 1e-6))
        every = max(1, int(round(1.0 / step_s / fps)))
        imgs = []
        for i in range(n):
            obs = env.observe()
            for ctrl in controllers:
                t = ctrl(env, obs, i * step_s)
                if t is not None:
                    env.set_target(np.asarray(t, dtype=float))
            for _ in range(int(env.control_dt / env.dt)):
                mujoco.mj_step(env.model, env.data)
            if i % every == 0:
                # 相机跟随躯干水平位移
                cam = dict(lookat=(float(env.data.qpos[0]), 0.008, 0.09))
                _set_camera(ren, env.model, env.data, **cam)
                imgs.append(snap())
            if i % 200 == 0 and i:
                print(f"  渲染进度 {i}/{n}")
        ren.close()
        if not out.lower().endswith(".gif"):
            out = os.path.splitext(out)[0] + ".gif"
        imgs[0].save(out, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / fps), loop=0)
        fp = os.path.splitext(out)[0] + "_frame0.png"
        imgs[0].save(fp)
        print(f"已渲染动图 -> {out}  ({len(imgs)} 帧, {W}x{H})")
        print(f"首帧另存: {fp}")
        return out
    else:
        d = mujoco.MjData(m)
        if keyframe:
            for k in range(m.nkey):
                if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_KEY, k) == keyframe:
                    mujoco.mj_resetDataKeyframe(m, d, k)
                    break
        mujoco.mj_forward(m, d)
        _set_camera(ren, m, d)
        img = snap()
        ren.close()
        if not out.lower().endswith((".png", ".jpg", ".jpeg")):
            out = os.path.splitext(out)[0] + ".png"
        img.save(out)
        print(f"已渲染 -> {out}  ({W}x{H})")
        return out


def hold_stand(env, obs, t):
    return np.array([_HOME[j] for j in SERVO_JOINTS], dtype=float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--anim", action="store_true")
    ap.add_argument("--horizon", type=float, default=2.0)
    ap.add_argument("--step", type=float, default=0.05)
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--algo", default=None, help="动图控制器选择: walk / hold (默认 hold)")
    a = ap.parse_args()
    if a.anim and not a.algo:
        a.algo = "hold"
    ctrls = _resolve_controllers(a.algo)
    ext_ok = a.out.lower().endswith((".gif", ".png", ".jpg", ".jpeg"))
    out = a.out if ext_ok else (a.out + (".gif" if a.anim else ".png"))
    render_frames(keyframe=a.key, out=out, controllers=ctrls,
                  horizon_s=a.horizon, step_s=a.step, fps=a.fps)


if __name__ == "__main__":
    main()
