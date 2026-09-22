#!/usr/bin/env python3
"""
run_arm_eval_v2.py — 真实 6 轴机械臂抓取评测（A3 修正版）

与 v1 的关键差别：
- 使用修正夹爪场景 assets/arm6_gripper_table_a2.xml（mount 不挡、手指强伺服、高摩擦）
- IK 带 yaw 约束（手指开合轴对齐）
- 到位置用 trim() 闭环补偿重力下垂（关键！否则 j2 下垂 ~0.2rad → 指尖低 4.7cm）
- 手指正确符号：正=闭合
- 真实抓取判定：双指接触 + 物体离台提升 > 5mm

用法：
  python scripts/run_arm_eval_v2.py --episodes 20 --perturb none
  python scripts/run_arm_eval_v2.py --episodes 20 --perturb object
"""
import os, sys, json, argparse, datetime
os.environ.setdefault("MUJOCO_GL", "disable")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
import importlib.util

spec = importlib.util.spec_from_file_location("rae", os.path.join(HERE, "run_arm_eval.py"))
rae = importlib.util.module_from_spec(spec); spec.loader.exec_module(rae)

SCENE = os.path.join(HERE, "..", "assets", "arm6_gripper_table_a2.xml")
OBJ_XY = (0.0, 0.25)

# 可抓取物体：细高立方体（在 2.5cm 桌面净空下可侧夹）。球体因桌面净空 < 手指长度无法稳夹。
OBJECTS = {
    "box":   {"shape": "box",    "size": 0.03, "half": [0.02, 0.02, 0.03], "mass": 0.03, "z_off": 0.03},
    "tall":  {"shape": "box",    "size": 0.035, "half": [0.018, 0.018, 0.035], "mass": 0.03, "z_off": 0.035},
}


def make_env(obj_key, obj_xy=OBJ_XY):
    import mujoco
    rae.SCENE = SCENE
    env = rae.Arm6Env()
    o = OBJECTS[obj_key]
    env.reset({"size": o["size"], "shape": o["shape"], "mass": o["mass"]}, obj_xy=obj_xy)
    m = env.model
    gid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "obj_geom")
    m.geom_type[gid] = mujoco.mjtGeom.mjGEOM_BOX
    m.geom_size[gid] = o["half"]
    z = rae.TABLE_TOP + o["z_off"]
    env.data.qpos[env.oadr:env.oadr + 3] = [obj_xy[0], obj_xy[1], z]
    env.data.qpos[env.oadr + 3:env.oadr + 7] = [1, 0, 0, 0]
    env.data.qvel[:] = 0
    mujoco.mj_forward(m, env.data)
    return env, np.array([obj_xy[0], obj_xy[1], z])


def run(episodes, obj_key, perturb, seed0=0):
    rows = []
    for ep in range(episodes):
        rng = np.random.default_rng(seed0 + ep)
        # 扰动：物体位置/朝向微扰
        if perturb in ("object", "all"):
            dx = rng.uniform(-0.02, 0.02); dy = rng.uniform(-0.02, 0.02)
            xy = (OBJ_XY[0] + dx, OBJ_XY[1] + dy)
        else:
            xy = OBJ_XY
        env, o = make_env(obj_key, obj_xy=xy)
        grip_close = float(rng.uniform(0.016, 0.022)) if perturb in ("object", "all") else 0.019
        try:
            r = env.grasp_and_lift(o, OBJECTS[obj_key]["z_off"], grip_close=grip_close,
                                   lift_z=0.80, steps_scale=0.6)
        except Exception as e:
            r = {"success": False, "max_lift_mm": 0.0, "final_lift_mm": 0.0,
                 "tip_err_mm": -1, "err": str(e)}
        r["ep"] = ep
        r["obj_xy"] = list(xy)
        r["grip_close"] = grip_close
        rows.append(r)
        print("ep %2d/%d  obj_xy=(%+.3f,%+.3f) close=%.3f  tip_err=%.2fmm  max_lift=%.1fmm  SUCCESS=%s"
              % (ep + 1, episodes, xy[0], xy[1], grip_close, r.get("tip_err_mm", -1),
                 r.get("max_lift_mm", 0), r["success"]))
    n = len(rows); nsucc = sum(1 for r in rows if r["success"])
    out = {"obj": obj_key, "perturb": perturb, "episodes": n, "success": nsucc,
           "success_rate": nsucc / n if n else 0.0,
           "mean_max_lift_mm": float(np.mean([r.get("max_lift_mm", 0) for r in rows])),
           "mean_tip_err_mm": float(np.mean([r.get("tip_err_mm", 0) for r in rows])),
           "rows": rows}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--object", default="box", choices=list(OBJECTS))
    ap.add_argument("--perturb", default="none")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = run(a.episodes, a.object, a.perturb, seed0=a.seed)
    res["timestamp"] = datetime.datetime.now().isoformat()
    res["disclaimer"] = ("真实 6 轴 MuJoCo 臂（自建场景，非官方 LIBERO-PRO/Franka）；"
                         "物体为可抓取立方体；成功率=双指接触且提升>5mm")
    print("\n=== 汇总 ===")
    print("物体=%s 扰动=%s eps=%d 成功=%d 成功率=%.1f%% 平均提升=%.1fmm 平均tip误差=%.2fmm"
          % (res["obj"], res["perturb"], res["episodes"], res["success"],
             res["success_rate"] * 100, res["mean_max_lift_mm"], res["mean_tip_err_mm"]))
    if a.out is None:
        a.out = os.path.join(HERE, "..", "results", "arm_eval_v2_%s_%s_%s.json"
                             % (res["obj"], res["perturb"], datetime.datetime.now().strftime("%Y%m%d_%H%M%S")))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("已保存:", a.out)


if __name__ == "__main__":
    main()
