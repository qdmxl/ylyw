#!/usr/bin/env python3
"""MicroDuck Headless 网格可视化 (matplotlib 3D + trimesh, 不需 OpenGL/GPU)。

以“低模缓存 + 只给较大部件建表面、小零件画散点”的方式快速成图,
用于无 GUI / 无 GPU 环境下直观核对 ylyw 输出的姿态与步态相位帧。

用法:
    首次 / 重建缓存:   python scripts/draw_state.py --precache
    画某姿态帧:        python scripts/draw_state.py [--key STAND|SIT|FOLD] [--out data/pose.png]
"""
import os
import sys
import re
import argparse

import numpy as np
import mujoco

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IMPORTS = True
try:
    import trimesh
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as e:  # pragma: no cover
    IMPORTS = False
    _ERR = e

_SUBDIR = os.path.join(os.path.dirname(__file__), "..")
_MODEL = os.path.join(_SUBDIR, "models", "microduck", "_ylyw_control_scene.xml")
_CACHE = os.path.join(_SUBDIR, "cache", "microduck_meshes.npz")


def _includes(txt):
    return re.findall(r'<include\s+file="([^"]+)"', txt)


def _mesh_files(txt):
    return re.findall(r'<mesh\s+file="([^"]+\.stl)"', txt)


def mesh_order(xml_path):
    """随 include 到机器人 xml, 取得按 <asset><mesh> 顺序的 stl 名列表(=模型 mesh id 顺序)。
    """
    base = os.path.dirname(os.path.abspath(xml_path))
    with open(xml_path, encoding="utf-8") as f:
        txt = f.read()
    best = (0, [])
    for inc in _includes(txt):
        p = os.path.join(base, inc)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f2:
            it = f2.read()
        if "<worldbody" in it:
            ms = _mesh_files(it)
            if len(ms) > best[0]:
                best = (len(ms), ms)
    return best[1] if best[0] else _mesh_files(txt)


def build_cache(xml_path, force=False, max_tris=150):
    if os.path.exists(_CACHE) and not force:
        return _CACHE
    order = mesh_order(xml_path)
    asset_dir = os.path.join(os.path.dirname(os.path.abspath(xml_path)), "assets")
    kv = {}
    names = []
    for name in order:
        p = os.path.join(asset_dir, name)
        if not os.path.exists(p):
            continue
        tm = trimesh.load(p, force="mesh", process=True)
        if len(tm.faces) > max_tris:
            try:
                tm = tm.simplify_quadric_decimation(max_tris)
            except Exception:
                pass
        kv[f"v{len(names)}"] = np.asarray(tm.vertices, dtype=np.float32)
        kv[f"f{len(names)}"] = np.asarray(tm.faces, dtype=np.int64)
        names.append(name)
    os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
    np.savez_compressed(_CACHE, names=np.array(names), **kv)
    print(f"缓存已生成: {_CACHE} (部件 {len(names)})")
    return _CACHE


def _load_cache(xml_path):
    order = mesh_order(xml_path)
    z = np.load(_CACHE, allow_pickle=True)
    names = list(z["names"])
    store = {}
    for i, o in enumerate(order):
        if o in names:
            j = names.index(o)
            if f"v{j}" in z and f"f{j}" in z:
                store[o] = (z[f"v{j}"], z[f"f{j}"])
    return store


def draw_state(xml_path, out, keyframe=None, qpos_override=None,
               elev_deg=20, azim_deg=15, show=False):
    if not IMPORTS:
        raise RuntimeError(f"缺少 trimesh/matplotlib 依赖: {_ERR}")
    if not os.path.exists(_CACHE):
        build_cache(xml_path)
    parts = _load_cache(xml_path)
    order = mesh_order(xml_path)

    m = mujoco.MjModel.from_xml_path(xml_path)
    d = mujoco.MjData(m)
    if keyframe:
        for k in range(m.nkey):
            if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_KEY, k) == keyframe:
                mujoco.mj_resetDataKeyframe(m, d, k)
                break
    if qpos_override is not None:
        d.qpos[:] = np.asarray(qpos_override, dtype=float)
    mujoco.mj_forward(m, d)

    # 点云端渲染: 每个 mesh geom 用它顶点的“最密集中心样本点”,保证速度。
    # 对较大部件抽得密一点(按表面三角数),小部件只画中心一种。
    pc = []  # 每项 (n,3) 世界坐标
    cc = []  # 每项对应颜色
    for g in range(m.ngeom):
        if m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        meshid = m.geom_dataid[g]
        if meshid >= len(order) or order[meshid] not in parts:
            continue
        verts, _faces = parts[order[meshid]]
        R = d.geom_xmat[g].reshape(3, 3)
        p = d.geom_xpos[g]
        vw = np.asarray(verts, dtype=np.float64)
        # 质心 + 若干均匀抽点,最多 NPOINT 点以保帧速
        n = len(vw)
        NPOINT = 120
        keep = np.unique(np.linspace(0, n - 1, min(NPOINT, n)).astype(int))
        c = np.append(vw.mean(0), vw[keep].mean(0))
        pts = np.vstack([vw.mean(0)[None, :], vw[keep]])
        col = tuple(m.geom_rgba[g][:3]) if m.geom_rgba[g] is not None else (0.72, 0.72, 0.72)
        w = pts @ R.T + p
        pc.append(w)
        cc += [col] * len(w)
    P = np.vstack(pc)

    fig = plt.figure(figsize=(7, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(P[:, 0], P[:, 1], P[:, 2], s=6, c=cc, alpha=0.7, depthshade=False)
    # 关节链骨架(便于看懂步态)
    gs = np.linspace(-0.3, 0.3, 3)
    gxx, gyy = np.meshgrid(gs, gs)
    ax.plot_surface(gxx, gyy, np.zeros_like(gxx), alpha=0.12, color="0.5")
    ax.set_xlim(-0.24, 0.24); ax.set_ylim(-0.24, 0.24); ax.set_zlim(-0.02, 0.36)
    ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
    ax.view_init(elev=elev_deg, azim=azim_deg)
    ax.set_box_aspect((1, 1, 1))
    ax.set_title(f"MicroDuck @ {keyframe or 'custom'}  trunk_z={float(d.qpos[2]):.3f}")
    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    fig.savefig(out, dpi=110)
    print(f"已绘制 -> {out}  (点 {len(P)})")
    if show:
        plt.show()
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", default=_MODEL)
    ap.add_argument("--out", default=os.path.join(_SUBDIR, "data", "pose.png"))
    ap.add_argument("--key", default=None)
    ap.add_argument("--elev", type=float, default=20.0)
    ap.add_argument("--azim", type=float, default=15.0)
    ap.add_argument("--precache", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.precache:
        build_cache(os.path.abspath(a.xml), force=a.force)
    else:
        draw_state(os.path.abspath(a.xml), keyframe=a.key, out=os.path.abspath(a.out),
                   elev_deg=a.elev, azim_deg=a.azim)


if __name__ == "__main__":
    main()
