#!/usr/bin/env python3
"""MicroDuck 离屏渲染存帧 —— 无 GUI 环境下可视化验证。

用法:
    python scripts/render_shot.py [--out shot.png]
渲染当前 STAND 姿态的一张图(headless,用 EGL/OSMesa)。
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mujoco
import numpy as np

from env.microduck_env import ensure_control_model


def render_shot(xml_path: str, out: str, height: int = 720, width: int = 1280,
                elevation: float = -30, azimuth: float = 150, distance: float = 1.2):
    m = mujoco.MjModel.from_xml_path(xml_path)
    # 读取模型声明的离屏帧缓冲宽高(MuJoCo 3 限制渲染尺寸 <= framebuffer)
    fbw = m.vis.global_.offwidth
    fbh = m.vis.global_.offheight
    width = min(width, fbw)
    height = min(height, fbh)
    d = mujoco.MjData(m)
    # STAND keyframe (index 1 由名字找)
    for k in range(m.nkey):
        if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_KEY, k) == "STAND":
            mujoco.mj_resetDataKeyframe(m, d, k)
            break
    mujoco.mj_forward(m, d)

    renderer = mujoco.Renderer(m, height=height, width=width)
    renderer.update_scene(d, camera=-1)
    renderer.scene.camera[0].elevation = elevation
    renderer.scene.camera[0].azimuth = azimuth
    renderer.scene.camera[0].distance = distance
    # Renderer.update_scene 已建立; 用默认 camera 0 需重设视角后重渲染
    renderer.disable_overlay = True
    renderer.update_scene(d)  # 重新用默认自由相机
    # 直接改 viewport 相机参数后需再次 update? 用自由相机 + lookat
    cam = renderer.scene.camera[0]
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.elevation = elevation
    cam.azimuth = azimuth
    cam.distance = distance
    cam.lookat[:] = [0, 0, 0.1]
    pixels = renderer.render()
    renderer.close()

    from PIL import Image
    img = Image.fromarray(pixels)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    img.save(out)
    print(f"已渲染 -> {out}  ({img.size[0]}x{img.size[1]})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "duck_stand.png"))
    ap.add_argument("--xml", default=None)
    args = ap.parse_args()
    xml = args.xml or ensure_control_model()
    render_shot(xml, args.out)


if __name__ == "__main__":
    main()
