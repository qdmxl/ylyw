#!/usr/bin/env python3
"""自动探测本机可用的 MuJoCo OpenGL 显示环境(Wayland/Xwayland/X11)。

在没有 GUI(纯 headless,无 OpenGL)的机器上自动回退到 matplotlib 点云;
在此 Ubuntu Wayland + VirtualBox 桌面上自动找到 Xwayland 的 :0 + 授权 cookie,
从而能让 MuJoCo Renderer / viewer 跑出**真渲染效果**。

用法(在脚本入口处先调用):
    from gl_env import configure_opengl_env, gl_available, display_env
    ok = configure_opengl_env()
    if ok:
        # 可安全创建 mujoco.GLContext / mujoco.Renderer
    else:
        # 回退到 matplotlib
"""
import os
import re
import glob


def _candidate_displays():
    """返回 (display, authfile) 候选,按优先序。"""
    cands = []
    # 1) 环境里已给的
    if os.environ.get("DISPLAY"):
        cands.append((os.environ["DISPLAY"], os.environ.get("XAUTHORITY")))
    # 2) X unix socket 目录里的 :N
    for sock in sorted(glob.glob("/tmp/.X11-unix/X*"), key=lambda p: int(p.rsplit("X", 1)[-1] or 0)):
        disp = ":" + sock.rsplit("X", 1)[-1]
        cands.append((disp, os.environ.get("XAUTHORITY")))
    # 3) 给每个 display 配套其 Xwayland mutter auth(常见于 GNOME Wayland)
    res = []
    for disp, auth in cands:
        res.append((disp, auth))
    return res


def _mutter_auth():
    """找到 /run/user/<uid>/.mutter-Xwaylandauth.*(Xwayland 的授权文件)。"""
    for base in glob.glob("/run/user/*/"):
        for f in glob.glob(base + ".mutter-Xwaylandauth.*"):
            return f
    return None


def _find_auth_for(display):
    if not display:
        return None
    # 找恰好为 DISPLAY 指定的 Xwayland cookie(由 auth 文件名后缀给出 sock)
    # mutter 文件名是随机的由 -displayfd 决定,无法直接从名。对已知 mutter auth: 值共享
    return None


def configure_opengl_env() -> bool:
    """尝试把 os.environ['DISPLAY']/['XAUTHORITY']/['MUJOCO_GL'] 设成交互可用的;
    返回 True 表示可以尝试 OpenGL(最终以能否建 MjrContext 为准)。"""
    # 若已有 DISPLAY 且 socket 存在优先不动
    auth_candidates = []
    ma = _mutter_auth()
    if ma:
        auth_candidates.append(ma)
    # 组合
    best = None
    for sock in sorted(glob.glob("/tmp/.X11-unix/X*"), key=lambda p: int(p.split("X")[-1])):
        disp = ":" + sock.split("X")[-1]
        for auth in ([os.environ.get("XAUTHORITY")] + auth_candidates):
            if auth and os.path.exists(auth):
                best = (disp, auth)
                break
        if best:
            break
    if best is None:
        # 至少留一个 socket 给别的探路
        if glob.glob("/tmp/.X11-unix/X*"):
            best = (":" + os.path.basename(sorted(glob.glob("/tmp/.X11-unix/X*"))).split("X")[-1],
                    os.environ.get("XAUTHORITY"))
    if best:
        disp, auth = best
        os.environ["DISPLAY"] = disp
        if auth:
            os.environ["XAUTHORITY"] = auth
        os.environ.setdefault("MUJOCO_GL", "glfw")
    return best is not None and os.environ.get("DISPLAY")


def _gl_can_render(force_env=1) -> bool:
    import mujoco
    try:
        ctx = mujoco.GLContext(64, 64)
        ctx.make_current()
        _p = mujoco.MjrContext  # touch
        ok = True
        # MjrContext 需一个 model
        import tempfile
        # 用极简 model 校验
        xml = "<mujoco model='g'><worldbody><geom type='sphere' size='0.1'/></worldbody></mujoco>"
        m = mujoco.MjModel.from_xml_string(xml)
        stub = mujoco.MjrContext(m, mujoco.mjtFontScale.mjFONTSCALE_100)
        ok = stub is not None
        del stub
    except Exception:
        ok = False
    finally:
        pass
    return ok


def gl_available() -> bool:
    """完整探测:配置环境后真的创建一次上下文;只在首次 import 后做一次(带缓存)。"""
    if not configure_opengl_env():
        return False
    if getattr(gl_available, "_cached", None) is None:
        gl_available._cached = _gl_can_render()
    return gl_available._cached


def display_summary() -> str:
    if os.environ.get("DISPLAY"):
        return os.environ["DISPLAY"]
    return "(none)"
