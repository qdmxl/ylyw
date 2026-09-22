#!/usr/bin/env python3
"""
LIBERO-PRO 四类扰动生成器（本机轻量复刻）

对应官方：
  Object Perturbation    物体外观/尺寸
  Position Perturbation  初始空间位置
  Semantic Perturbation  指令语义改写
  Task Perturbation      任务逻辑重定义

设计要点：语义等价改写应当**不改变** YLYW 的卦象（验证语义理解），
而位置/物体扰动**应当改变**卦象并触发策略调整（验证情境重估）。
"""

import random
from typing import Dict, Any


class PerturbationGenerator:
    def __init__(self, config: dict, seed: int = 42):
        self.cfg = config
        self.rng = random.Random(seed)

    # ---------------- Object ----------------
    def perturb_object(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """改外观/尺寸，不改物理类别语义。"""
        c = self.cfg["object_perturbation"]
        if not c.get("enabled", True):
            return dict(obj)
        out = dict(obj)
        s = self.rng.uniform(*c["scale_range"])
        out["size"] = obj["size"] * s
        if not c.get("keep_shape", True):
            out["shape"] = self.rng.choice(["sphere", "box", "cylinder"])
        out["color"] = self.rng.choice(c["color_pool"])
        out["_perturbed"] = "object"
        return out

    # ---------------- Position ----------------
    def perturb_position(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        c = self.cfg["position_perturbation"]
        if not c.get("enabled", True):
            return dict(obj)
        out = dict(obj)
        dx = self.rng.uniform(*c["xy_offset_range"])
        dy = self.rng.uniform(*c["xy_offset_range"])
        dz = self.rng.uniform(*c["z_offset_range"])
        out["pos"] = [obj["pos"][0] + dx, obj["pos"][1] + dy, obj["pos"][2] + dz]
        out["yaw"] = self.rng.uniform(*c["rotate_range_deg"])
        out["_perturbed"] = "position"
        return out

    # ---------------- Semantic ----------------
    def perturb_instruction(self, instr: str) -> str:
        """语义等价改写：期望 YLYW 输出卦象保持一致。"""
        c = self.cfg["semantic_perturbation"]
        if not c.get("enabled", True):
            return instr
        for canon, variants in c.get("paraphrase_map", {}).items():
            if canon in instr:
                return instr.replace(canon, self.rng.choice(variants))
        return instr

    # ---------------- Task ----------------
    def perturb_task(self, task: Dict[str, Any], variant_name: str = None) -> Dict[str, Any]:
        c = self.cfg["task_perturbation"]
        if not c.get("enabled", True):
            return dict(task)
        variants = c.get("variants", [])
        v = next((x for x in variants if x["name"] == variant_name),
                 self.rng.choice(variants) if variants else None)
        out = dict(task)
        if v:
            out["task_variant"] = v["name"]
            if v["name"] == "swap_target":
                out["target_pos"] = [0.3, -0.15, 0.05]
            elif v["name"] == "add_obstacle":
                out["n_obstacles"] = task.get("n_obstacles", 0) + 2
            elif v["name"] == "reverse_order":
                out["reverse_order"] = True
            out["_perturbed"] = "task"
        return out

    # ---------------- Combined ----------------
    def generate_conditions(self) -> Dict[str, callable]:
        """返回评测条件 → 扰动函数的映射。"""
        return {
            "none": lambda o, t, i: (dict(o), dict(t), i),
            "object": lambda o, t, i: (self.perturb_object(o), dict(t), i),
            "position": lambda o, t, i: (self.perturb_position(o), dict(t), i),
            "semantic": lambda o, t, i: (dict(o), dict(t), self.perturb_instruction(i)),
            "task": lambda o, t, i: (dict(o), self.perturb_task(t), i),
            "all": lambda o, t, i: (
                self.perturb_position(self.perturb_object(o)),
                self.perturb_task(t),
                self.perturb_instruction(i),
            ),
        }
