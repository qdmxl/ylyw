#!/usr/bin/env python3
"""
LIBERO-PRO（轻量版）评测主循环

对每个扰动条件：
  for episode in range(N):
    1. 构造/扰动任务
    2. 提取 YLYW 特征 → 推理 → 卦象 + 策略
    3. 策略 → 动作 → 仿真推进
    4. 判定成功，记录卦象、成功率、轨迹
汇总：各条件成功率、卦象分布、语义一致性、方差
"""

import os
import sys
import json
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from env import LiteGraspEnv          # noqa: E402
from features import extract_features  # noqa: E402
from perturb import PerturbationGenerator  # noqa: E402
from ylyw_adapter.inference import YLYWInference  # noqa: E402


BASE_OBJECT = {"pos": [0.3, 0.1, 0.05], "size": 0.05, "shape": "sphere",
               "mass": 0.03, "color": "red"}
BASE_TASK = {"target_pos": [0.3, -0.1, 0.02], "n_obstacles": 0, "task_priority": 0.8}
BASE_INSTR = "pick up the block"


def run_episode(env_obj, task, instr, inference, max_steps=400, succ_cm=3.0):
    env = LiteGraspEnv(env_obj, target_pos=task["target_pos"])
    env.reset()

    hexagram = None
    result = None
    history = []
    target = np.array(task["target_pos"], dtype=float)

    for t in range(max_steps):
        env.try_grasp()
        ee_pos = env.get_ee_pos()
        obj_pos = env.get_obj_pos()
        state = {
            "obj_pos": obj_pos,
            "obj_size": env_obj["size"],
            "obj_mass": env_obj.get("mass", 0.03),
            "obj_shape": env_obj["shape"],
            "ee_pos": ee_pos,
            "target_pos": task["target_pos"],
            "n_obstacles": task.get("n_obstacles", 0),
            "task_priority": task.get("task_priority", 0.8),
        }
        feats = extract_features(state)
        result = inference.infer(feats)
        if hexagram is None:
            hexagram = result["hexagram"]   # 首帧卦象（决策依据）

        # 目标：未抓取时靠近物体，已抓取时携带物体到 target
        # 关键：抓取后物体位于 ee + offset，因此末端目标 = target - offset
        if not env.grasped:
            goal = obj_pos + np.array([0, 0, 0.005])
        else:
            goal = target - env._grasp_offset
        action = inference.strategy_to_action(result, ee_pos, goal, gripper_open=1.0)

        env.apply_ee_velocity(action["delta_pos"])
        env.step()
        history.append(float(np.linalg.norm(env.get_obj_pos() - target)))

        d = float(np.linalg.norm(env.get_obj_pos() - target))
        if env.grasped and t > 20 and d < succ_cm / 100.0:
            return True, hexagram, result, history

    final_d = float(np.linalg.norm(env.get_obj_pos() - target))
    return final_d < succ_cm / 100.0, hexagram, result, history


def run_eval(config: dict, episodes: int = 20, conditions=None, seed: int = 42, verbose=True):
    gen = PerturbationGenerator(config, seed=seed)
    conds = gen.generate_conditions()
    conditions = conditions or list(conds.keys())
    inference = YLYWInference()

    report = {"meta": {"episodes": episodes, "seed": seed,
                       "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
              "conditions": {}}

    for cond in conditions:
        fn = conds[cond]
        succ = 0
        hexagrams = []
        for ep in range(episodes):
            obj, task, instr = fn(dict(BASE_OBJECT), dict(BASE_TASK), BASE_INSTR)
            # 给每次 episode 一点随机性
            if cond in ("none", "semantic", "task"):
                obj = gen.perturb_position(obj) if cond != "none" else obj
            ok, hx, res, _ = run_episode(obj, task, instr, inference)
            succ += int(ok)
            hexagrams.append(hx)
        rate = succ / episodes
        # 卦象多样性（用来判断语义扰动是否保持稳定）
        from collections import Counter
        hx_dist = Counter(hexagrams)
        dominant_share = max(hx_dist.values()) / episodes if hexagrams else 0.0
        report["conditions"][cond] = {
            "success_rate": rate,
            "n_episodes": episodes,
            "hexagram_distribution": dict(hx_dist),
            "dominant_hexagram_share": dominant_share,
            "unique_hexagrams": len(hx_dist),
        }
        if verbose:
            print(f"[{cond:9s}] 成功率 {rate:5.1%} | 主卦占比 {dominant_share:5.1%} "
                  f"| 独特卦象 {len(hx_dist)} | 主卦 {hexagrams[0] if hexagrams else '-'}")

    return report


if __name__ == "__main__":
    import yaml
    cfg_path = os.path.join(os.path.dirname(_HERE), "configs", "perturbation.yaml")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    rep = run_eval(cfg, episodes=5)
    print(json.dumps(rep, ensure_ascii=False, indent=2)[:800])
