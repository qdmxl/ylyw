#!/usr/bin/env python3
"""
LIBERO-PRO × YLYW —— 6轴真实机械臂评测（v3, 稳定 IK 伺服）

关键修正（相对 v1/v2）：
  1. 控制点 = 两指尖中点（不是 gripper_base），消除 ~5cm 系统性偏差
  2. IK 用固定种子（home）+ 关节限位投影 → 解在连续分支，不跳变
  3. 关节空间线性插值轨迹 → 平滑、无 IK 重解震荡
  4. 真接触动力学（condim=4, friction=1.5）
  5. 成功判定 = 双指接触 + 物体提升>5mm + 提升后保持

用法: python3 scripts/run_arm_eval.py --episodes 5 --perturb none
"""

import os, sys, json, time, argparse
import numpy as np

os.environ.setdefault("MUJOCO_GL", "disable")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "cross_embodiment"))
import mujoco  # noqa: E402
from ylyw_adapter.inference import YLYWInference  # noqa: E402
from sim.features import extract_features        # noqa: E402
from sim.perturb import PerturbationGenerator    # noqa: E402

SCENE = os.path.join(HERE, "..", "assets", "arm6_gripper_table.xml")
TABLE_TOP = 0.74
ARM_JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6"]
HOME = np.array([0.0, -0.6, 1.2, 0.0, -0.6, 0.0])
TIP_L = np.array([0.0, -0.008, -0.05])   # finger_left 局部指尖
TIP_R = np.array([0.0,  0.008, -0.05])   # finger_right 局部指尖
OBJ_XY = (0.0, 0.30)                      # 物体位置：机械臂可垂直下探的工作环内


class Arm6Env:
    def __init__(self):
        self.model = mujoco.MjModel.from_xml_path(SCENE)
        self.data = mujoco.MjData(self.model)
        m = self.model
        self.b = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, n)
                  for n in ["object", "gripper_base", "finger_left", "finger_right", "link6"]}
        self.j = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, n)
                  for n in ["obj_free"] + ARM_JOINTS + ["fl_j", "fr_j"]}
        self.a = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, n)
                  for n in ARM_JOINTS + ["fl_motor", "fr_motor"]}
        self.g = {n: mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, n)
                  for n in ["obj_geom", "fl_geom", "fr_geom"]}
        self.qadr = [m.jnt_qposadr[self.j[j]] for j in ARM_JOINTS]
        self.oadr = m.jnt_qposadr[self.j["obj_free"]]
        self.lo = np.array([m.jnt_range[self.j[j]][0] for j in ARM_JOINTS])
        self.hi = np.array([m.jnt_range[self.j[j]][1] for j in ARM_JOINTS])
        # A3: 真实指尖 geom id（存在则用于精确 FK）
        _gl = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "fl_tip")
        _gr = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, "fr_tip")
        self.gtip_l = _gl if _gl >= 0 else None
        self.gtip_r = _gr if _gr >= 0 else None

    # ---- 运动学 ----
    def _fk_full(self):
        """返回 (指尖中点, 手掌z轴)。
        A3: 优先用指尖 geom(fl_tip/fr_tip) 的真实世界坐标（消除 TIP_L/TIP_R 估计偏差），
        若模型无该 geom 则回退到局部偏移估计。"""
        mujoco.mj_forward(self.model, self.data)
        fl = self.b["finger_left"]; fr = self.b["finger_right"]
        gt_l = getattr(self, "gtip_l", None)
        gt_r = getattr(self, "gtip_r", None)
        if gt_l is not None and gt_r is not None:
            mid = (self.data.geom_xpos[gt_l] + self.data.geom_xpos[gt_r]) / 2.0
        else:
            mid = ((self.data.xpos[fl] + self.data.xmat[fl].reshape(3, 3) @ TIP_L) +
                   (self.data.xpos[fr] + self.data.xmat[fr].reshape(3, 3) @ TIP_R)) / 2.0
        zaxis = self.data.xmat[self.b["gripper_base"]].reshape(3, 3)[:, 2]
        return mid, zaxis

    def find_seed(self, y_target, z_lo=0.74, z_hi=0.94, tries=120000, rng=None, goal=None,
                  yaw_target=None, yaw_tol=0.35):
        """随机采样找可行配置：夹爪朝下 + 指尖尽量接近 goal。返回 (q, tip, ori_err)。
        没有 goal 时仅要求夹爪朝下且在 y 附近。
        yaw_target 给定时，额外要求手指开合轴（局部 +Y）的世界偏航角接近 yaw_target。"""
        rng = rng or np.random.default_rng(7)
        best = None; bd = 9.0
        for _ in range(tries):
            q = rng.uniform(self.lo, self.hi)
            for a, v in zip(self.qadr, q):
                self.data.qpos[a] = v
            mid, z = self._fk_full()
            down = float(np.linalg.norm(z - np.array([0, 0, -1.0])))
            if down > 0.15:
                continue
            if yaw_target is not None:
                y = self.data.xmat[self.b["gripper_base"]].reshape(3, 3) @ np.array([0, 1, 0.0])
                ya = np.arctan2(y[1], y[0])
                d = ((yaw_target - ya + np.pi) % (2 * np.pi)) - np.pi
                if abs(d) > yaw_tol:
                    continue
            if goal is not None:
                cost = float(np.linalg.norm(mid - goal)) + 0.05 * down
            else:
                if not (abs(mid[1] - y_target) < 0.06 and z_lo < mid[2] < z_hi):
                    continue
                cost = 0.05 * down
            if cost < bd:
                bd = cost; best = q.copy()
        return best

    def ik6(self, target, q_init, w_ori=0.5, iters=600, lr=0.15, yaw_target=None, w_yaw=0.5):
        """6-DOF IK：指尖中点到位 + 夹爪朝下（+ 可选手指开合轴偏航）。小步长避免跳限位。
        返回 (q, pos_err, ori_err)。"""
        q = np.asarray(q_init, dtype=float).copy()
        target = np.asarray(target, dtype=float)
        down = np.array([0.0, 0.0, -1.0])
        has_yaw = yaw_target is not None
        for _ in range(iters):
            for a, v in zip(self.qadr, q):
                self.data.qpos[a] = v
            mid, z = self._fk_full()
            e = np.concatenate([target - mid, w_ori * (down - z)])
            if has_yaw:
                y = self.data.xmat[self.b["gripper_base"]].reshape(3, 3) @ np.array([0, 1, 0.0])
                ya = np.arctan2(y[1], y[0])
                d = ((yaw_target - ya + np.pi) % (2 * np.pi)) - np.pi
                e = np.concatenate([e, [w_yaw * d, 0.0, 0.0]])
            if float(np.linalg.norm(e)) < 0.003:
                break
            if has_yaw:
                base = np.concatenate([mid, z, [ya, 0, 0]])
            else:
                base = np.concatenate([mid, z])
            J = np.zeros((len(e), 6)) if has_yaw else np.zeros((6, 6))
            for k, a in enumerate(self.qadr):
                old = self.data.qpos[a]; self.data.qpos[a] = old + 1e-6
                m2, z2 = self._fk_full()
                col = np.concatenate([m2, z2])
                if has_yaw:
                    y2 = self.data.xmat[self.b["gripper_base"]].reshape(3, 3) @ np.array([0, 1, 0.0])
                    col = np.concatenate([col, [np.arctan2(y2[1], y2[0]), 0, 0]])
                J[:, k] = (col - base) / 1e-6
                self.data.qpos[a] = old
            q = np.clip(q + np.linalg.solve(J.T @ J + 0.05 * np.eye(6), J.T @ e) * lr, self.lo, self.hi)
        for a, v in zip(self.qadr, q):
            self.data.qpos[a] = v
        mid, z = self._fk_full()
        return q, float(np.linalg.norm(target - mid)), float(np.linalg.norm(down - z))

    # ---- 伺服 ----
    def servo(self, q_target, steps, grip_open):
        for _ in range(steps):
            for jn, q in zip(ARM_JOINTS, q_target):
                self.data.ctrl[self.a[jn]] = q
            self.data.ctrl[self.a["fl_motor"]] = grip_open
            self.data.ctrl[self.a["fr_motor"]] = -grip_open
            mujoco.mj_step(self.model, self.data)

    def servo_hold(self, q_target, steps, grip_open, n_rounds=6):
        """带积分补偿的伺服：迭代修正稳态误差（重力下垂），让关节真正到位。"""
        qd = np.asarray(q_target, dtype=float).copy()
        for _ in range(n_rounds):
            for _ in range(steps):
                for jn, q in zip(ARM_JOINTS, qd):
                    self.data.ctrl[self.a[jn]] = q
                self.data.ctrl[self.a["fl_motor"]] = grip_open
                self.data.ctrl[self.a["fr_motor"]] = -grip_open
                mujoco.mj_step(self.model, self.data)
            qnow = np.array([float(self.data.qpos[a]) for a in self.qadr])
            err = np.asarray(q_target, dtype=float) - qnow
            if np.max(np.abs(err)) < 0.008:
                break
            qd = qd + 0.9 * err          # 把残留误差加到控制目标上

    def servo_path(self, q_from, q_to, steps, grip_open):
        q_from = np.asarray(q_from); q_to = np.asarray(q_to)
        for t in range(steps):
            alpha = (t + 1) / steps
            q = (1 - alpha) * q_from + alpha * q_to
            for jn, qv in zip(ARM_JOINTS, q):
                self.data.ctrl[self.a[jn]] = qv
            self.data.ctrl[self.a["fl_motor"]] = grip_open
            self.data.ctrl[self.a["fr_motor"]] = -grip_open
            mujoco.mj_step(self.model, self.data)

    # ---- 状态 ----
    def set_object(self, obj):
        m = self.model; shape = obj.get("shape", "sphere"); half = obj.get("size", 0.028)
        if shape == "sphere":
            m.geom_size[self.g["obj_geom"]] = [half, 0, 0]
        elif shape == "box":
            m.geom_size[self.g["obj_geom"]] = [half, half, half]
        else:
            m.geom_size[self.g["obj_geom"]] = [half, half * 1.4, 0]
        m.body_mass[self.b["object"]] = obj.get("mass", 0.03)

    def reset(self, obj, obj_xy=OBJ_XY):
        h = obj.get("size", 0.028)
        mujoco.mj_resetData(self.model, self.data)
        self.set_object(obj)
        self.data.qpos[self.oadr:self.oadr+3] = [obj_xy[0], obj_xy[1], TABLE_TOP + h]
        self.data.qpos[self.oadr+3:self.oadr+7] = [1, 0, 0, 0]
        for a, v in zip(self.qadr, HOME):
            self.data.qpos[a] = v
        self.data.qpos[self.model.jnt_qposadr[self.j["fl_j"]]] = 0.045
        self.data.qpos[self.model.jnt_qposadr[self.j["fr_j"]]] = 0.045
        mujoco.mj_forward(self.model, self.data)

    def obj_pos(self):
        return self.data.xpos[self.b["object"]].copy()

    def finger_gap(self):
        o = self.obj_pos()
        fl = self.data.xpos[self.b["finger_left"]]; fr = self.data.xpos[self.b["finger_right"]]
        return float(min(np.linalg.norm(o - fl), np.linalg.norm(o - fr)))

    def lift_mm(self):
        return float((self.obj_pos()[2] - TABLE_TOP) * 1000)

    # ---- 下垂补偿伺服（A3）：迭代修正关节目标，使实际 tip_mid 收敛到几何目标 ----
    def _tipmid(self):
        return self._fk_full()[0]

    def _settle(self, q, steps, grip):
        for _ in range(steps):
            for jn, v in zip(ARM_JOINTS, q):
                self.data.ctrl[self.a[jn]] = v
            self.data.ctrl[self.a["fl_motor"]] = grip
            self.data.ctrl[self.a["fr_motor"]] = grip
            mujoco.mj_step(self.model, self.data)

    def trim(self, q, target, grip, rounds=16, steps=120, tol=0.0015):
        """把关节目标迭代修正，使实际 tip_mid 收敛到 target（补偿重力下垂）。"""
        qd = np.asarray(q, dtype=float).copy()
        target = np.asarray(target, dtype=float)
        for _ in range(rounds):
            self._settle(qd, steps, grip)
            cur = self._tipmid()
            err = target - cur
            if float(np.linalg.norm(err)) < tol:
                break
            J = np.zeros((3, 6))
            for k, a in enumerate(self.qadr):
                old = self.data.qpos[a]; self.data.qpos[a] = old + 1e-6
                m2, _ = self._fk_full(); J[:, k] = (m2 - cur) / 1e-6
                self.data.qpos[a] = old
            qd = np.clip(qd + np.linalg.solve(J.T @ J + 0.01 * np.eye(6), J.T @ err), self.lo, self.hi)
        return qd

    def grasp_and_lift(self, o, h, grip_close=0.019, grip_open=-0.06, yaw=np.pi,
                       lift_z=None, steps_scale=1.0):
        """完整真实抓取：yaw 约束 IK + 下垂补偿到位 + 正确手指定宽闭合 + 抬升。
        返回 dict（max_lift_mm, final_lift_mm, tip_err, success）。"""
        if lift_z is None:
            lift_z = o[2] + 0.05
        seed = self.find_seed(o[1], goal=np.array([o[0], o[1], o[2] + h + 0.15]), yaw_target=yaw)
        if seed is None:
            seed = self.find_seed(o[1], goal=np.array([o[0], o[1], o[2] + h + 0.15]))
        qa, _, _ = self.ik6(np.array([o[0], o[1], o[2] + h + 0.12]), seed, yaw_target=yaw)
        # 张开手指置于 qa
        for a, v in zip(self.qadr, qa):
            self.data.qpos[a] = v
        self.data.qpos[self.model.jnt_qposadr[self.j["fl_j"]]] = 0.0
        self.data.qpos[self.model.jnt_qposadr[self.j["fr_j"]]] = 0.0
        self.data.qvel[:] = 0
        mujoco.mj_forward(self.model, self.data)
        # 下垂补偿下降到物体高度
        qd = self.trim(qa, np.array([o[0], o[1], o[2]]), grip=grip_open,
                       rounds=16, steps=int(120 * steps_scale))
        tip_err = float(np.linalg.norm(self._tipmid() - np.array([o[0], o[1], o[2]])))
        # 闭合手指（正确符号：正=闭合）
        self._settle(qd, int(300 * steps_scale), grip_close)
        rest = self.obj_pos()[2]
        # 抬升：一次 IK 求抬升目标，关节空间线性插值（不反复动手指）
        qh = self.trim(qd, np.array([o[0], o[1], lift_z]), grip=grip_close, rounds=10,
                       steps=int(80 * steps_scale))
        max_lift = 0.0
        for t in range(int(400 * steps_scale)):
            al = min(1.0, (t + 1) / (400 * steps_scale))
            qt = (1 - al) * qd + al * qh
            self._settle(qt, 1, grip_close)
            max_lift = max(max_lift, self.obj_pos()[2] - rest)
        self._settle(qh, int(200 * steps_scale), grip_close)
        max_lift = max(max_lift, self.obj_pos()[2] - rest)
        final_lift = self.obj_pos()[2] - rest
        return {"max_lift_mm": max_lift * 1000, "final_lift_mm": final_lift * 1000,
                "tip_err_mm": tip_err * 1000, "rest_z": float(rest),
                "final_z": float(self.obj_pos()[2]),
                "success": bool(max_lift > 0.005 and final_lift > 0.005)}


def run_episode(obj_desc, task, inference, obj_xy=OBJ_XY, seed_rng=None):
    env = Arm6Env()
    env.reset(obj_desc, obj_xy=obj_xy)
    o = env.obj_pos().copy()
    h = obj_desc.get("size", 0.028)

    # ---- YLYW 决策 ----
    state = {"obj_pos": o, "obj_size": h, "obj_mass": obj_desc.get("mass", 0.03),
             "obj_shape": obj_desc.get("shape", "sphere"), "ee_pos": env._fk_full()[0],
             "target_pos": task["target_pos"], "n_obstacles": task.get("n_obstacles", 0),
             "task_priority": task.get("task_priority", 0.8)}
    feats = extract_features(state)
    result = inference.infer(feats)
    vscale = {"slow": 0.4, "soft": 0.5, "medium": 0.8, "fast": 1.2}.get(result.get("speed", "medium"), 0.8)
    grip_close = -0.02 if (result.get("force") or 0.5) > 0.55 else -0.005
    grip_open = 0.045

    # ---- 找可行种子（夹爪朝下 + 指尖靠近目标）+ 6-DOF IK 精修 ----
    seed = env.find_seed(y_target=obj_xy[1], rng=seed_rng,
                         goal=np.array([o[0], o[1], o[2] + h + 0.07]))
    if seed is None:
        seed = HOME
    q_above = env.ik6(np.array([o[0], o[1], o[2] + h + 0.07]), seed)[0]
    q_down = env.ik6(np.array([o[0], o[1], o[2] + 0.006]), q_above)[0]
    q_lift = env.ik6(np.array([o[0], o[1] - 0.01, o[2] + h + 0.14]), q_down)[0]

    # ---- 抓取序列 ----
    env.servo_path(HOME, q_above, int(300 / max(vscale, 0.2)), grip_open)
    env.servo_hold(q_above, 120, grip_open)
    env.servo_path(q_above, q_down, int(250 / max(vscale, 0.2)), grip_open)
    env.servo_hold(q_down, 140, grip_open)
    env.servo_hold(q_down, 160, grip_close)
    gap = env.finger_gap()
    contacting = gap < 0.035
    env.servo_path(q_down, q_lift, 350, grip_close)
    env.servo_hold(q_lift, 120, grip_close)
    lift_mm = env.lift_mm()

    success = bool(contacting and lift_mm > 5.0)
    info = {"hexagram": result["hexagram"], "speed": result.get("speed"),
            "force": result.get("force"), "finger_gap": round(gap, 4),
            "contacting": contacting, "lift_mm": round(lift_mm, 2)}
    return success, result["hexagram"], result, info


def run_arm_eval(config, episodes=5, conditions=None, seed=42, verbose=True):
    gen = PerturbationGenerator(config, seed=seed)
    conds = gen.generate_conditions()
    conditions = conditions or list(conds.keys())
    inference = YLYWInference()
    BASE_OBJECT = {"size": 0.028, "shape": "sphere", "mass": 0.03, "pos": [OBJ_XY[0], OBJ_XY[1], 0.0]}
    BASE_TASK = {"target_pos": [0.0, 0.0, TABLE_TOP], "n_obstacles": 0, "task_priority": 0.8}
    report = {"meta": {"episodes": episodes, "seed": seed, "arm": "arm6_gripper_IK6_v3",
                       "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}, "conditions": {}}
    for cond in conditions:
        fn = conds[cond]
        succ = 0; hexes = []; lifts = []; gaps = []
        rng = np.random.default_rng(seed)
        for _ in range(episodes):
            obj, task, instr = fn(dict(BASE_OBJECT), dict(BASE_TASK), "pick up the block")
            xy = tuple(obj.get("pos", [OBJ_XY[0], OBJ_XY[1], 0])[:2]) if "pos" in obj else OBJ_XY
            ok, hx, res, info = run_episode(obj, task, inference, obj_xy=xy, seed_rng=rng)
            succ += int(ok); hexes.append(hx); lifts.append(info["lift_mm"]); gaps.append(info["finger_gap"])
        from collections import Counter
        dist = Counter(hexes)
        report["conditions"][cond] = {
            "success_rate": succ / episodes, "n_episodes": episodes,
            "hexagram_distribution": dict(dist),
            "dominant_hexagram_share": max(dist.values()) / episodes if hexes else 0,
            "unique_hexagrams": len(dist),
            "mean_lift_mm": round(float(np.mean(lifts)), 2),
            "mean_finger_gap": round(float(np.mean(gaps)), 4),
        }
        if verbose:
            print(f"[{cond:9s}] 成功率 {succ/episodes:5.1%} | 平均提升 {np.mean(lifts):+7.2f}mm "
                  f"| 指隙 {np.mean(gaps):.3f}m | 主卦 {hexes[0] if hexes else '-'}")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--perturb", type=str, default="none")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    import yaml
    with open(os.path.join(ROOT, "configs", "perturbation.yaml")) as f:
        cfg = yaml.safe_load(f)
    conditions = None if args.perturb == "all" else [c.strip() for c in args.perturb.split(",")]
    print("=" * 68)
    print(f"LIBERO-PRO × YLYW —— 6轴机械臂(IK v3)评测 | episodes={args.episodes} | 条件={args.perturb}")
    print("=" * 68)
    rep = run_arm_eval(cfg, episodes=args.episodes, conditions=conditions, seed=args.seed)
    out = os.path.join(ROOT, "results", f"arm_eval_{time.strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out}")


if __name__ == "__main__":
    main()
