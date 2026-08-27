#!/usr/bin/env python3
"""13 维特征逐维消融/敏感性分析 —— 证明每一维对最终抓取决策的实际贡献。

思路：
  对一批多形状物体，先算出"基线"决策（strategy/hexagram/卦象分/爻位质量/力/接近角）。
  然后对 13 个特征维度之一固定为“全样本均值”（消除该维信息量），重跑完整 YLYW
  推理链路（L1/L2/L3），比较决策是否/如何改变：
    - 策略是否翻转（strategy flip）
    - 卦象是否翻转（hexagram flip）
    - 连续量变化：Δyao_quality, Δhexagram_score, Δforce, Δapproach_angle
  变化量越大 → 该维对决策贡献越大；“零变化”维度说明其信息未进入决策（需审查）。

输出：
  - 逐维贡献度表（CSV/控制台）
  - 各维翻转率与连续量平均变化

用法:
  cd real_robot_grasp
  python3 feature_ablation.py --rounds 30 --seed 2026 --out experiments/ablation
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # motion_control

from real_robot_grasp.ylyw_grasp_planner import YlywGraspPlanner  # noqa: E402
from real_robot_grasp.object_features import (  # noqa: E402
    analyze_object, FeaturesConfig)
from real_robot_grasp.run_paper_experiments import gen_scene  # noqa: E402

# 喂给 YLYW 的 13 维特征(见 prior_manual.perceive_and_encode 注释)。
FEATURE_DIMS = [
    "stability", "roll_tendency", "strength_needed", "fragility",
    "task_priority", "reachability", "support_area", "occlusion",
    "obstacle_density", "grasp_surface_quality", "weight_ratio",
    "visibility", "deformability",
]


def _decision_vec(plan) -> Tuple:
    """把一次抓取决策编码成可比较的向量。"""
    return (
        str(getattr(plan, "strategy_type", "")),
        str(getattr(plan, "hexagram", "")),
        str(getattr(plan, "hexagram_cn", "")),
        float(getattr(plan, "yao_quality", 0.0)),
        float(getattr(plan, "hexagram_score", 0.0)),
        float(getattr(plan, "force", 0.5)),
        float(getattr(plan, "approach_angle_deg", 0.0)),
    )


def _freeze(obj, feat_mean: Dict[str, float], dim: str):
    """返回一个 features[dim] 被固定为全局均值的 ObjectFeatures 副本。"""
    clone = deepcopy(obj)
    f = dict(clone.features)
    base = dict(f)
    base.pop("_mass_kg", None)          # 内部量不参与该 13 维消融
    f[dim] = float(feat_mean[dim])
    clone.features = f
    return clone


def run_ablation(args):
    rng = np.random.default_rng(args.seed)
    feat_cfg = FeaturesConfig(min_points=30)
    planner = YlywGraspPlanner(); planner.load()

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent / out
    out.mkdir(parents=True, exist_ok=True)

    # —— 收集一批物体及其基线特征 ——
    objs = []          # (obj, baseline_decision)
    baseline_feats = []
    for _rnd in range(args.rounds):
        clouds, labels = gen_scene(rng)
        for ci, (cloud, label) in enumerate(zip(clouds, labels)):
            seg = analyze_object(
                cloud, feat_cfg, label=label,
                all_clouds=[c for j, (c, _) in enumerate(zip(clouds, labels))
                            if j != ci],
                num_clouds=len(clouds))
            if seg is None:
                continue
            plan = planner.plan(seg)
            objs.append(seg)
            baseline_feats.append(dict(planner.build_features(seg)))
            # 同时给 obj 存基线决策便于对比
            seg._baseline_decision = _decision_vec(plan)
            seg._baseline_plan = plan
    n = len(objs)
    print(f"共分析 {n} 个物体(多形状混合)")

    # —— 全局均值(基线特征) ——
    feat_mean = {}
    for dim in FEATURE_DIMS:
        vals = [f.get(dim, np.nan) for f in baseline_feats]
        vals = [v for v in vals if isinstance(v, (int, float)) and not np.isnan(v)]
        feat_mean[dim] = float(np.mean(vals))

    # —— 逐维消融 ——
    rows = []
    for dim in FEATURE_DIMS:
        flip_strategy = flip_hexagram = 0
        d_yao = d_hex_score = d_force = d_angle = 0.0
        changed = 0
        per_obj = []
        for obj in objs:
            frozen = _freeze(obj, feat_mean, dim)
            p = planner.plan(frozen)
            vec = _decision_vec(p)
            base = obj._baseline_decision
            # 1) 是否改变(整体)
            dvec = tuple(
                round(abs(float(a) - float(b)), 4) if isinstance(a, (int, float))
                and isinstance(b, (int, float)) else (a != b)
                for a, b in zip(vec, base))
            is_change = any(dvec)
            changed += int(is_change)
            if is_change:
                per_obj.append((obj.label, base, vec))
            # 2) 策略翻转
            if vec[0] != base[0]:
                flip_strategy += 1
            # 3) 卦象翻特
            if vec[2] != base[2]:
                flip_hexagram += 1
            # 4) 连续量平均变化(取绝对值)
            d_yao += abs(vec[3] - base[3])
            d_hex_score += abs(vec[4] - base[4])
            d_force += abs(vec[5] - base[5])
            d_angle += abs(vec[6] - base[6])
        rows.append({
            "dim": dim,
            "n": n,
            "mean_value": round(feat_mean[dim], 3),
            "change_ratio": round(changed / max(n, 1), 4),   # 该维固定后决策变化的占比
            "strategy_flip_ratio": round(flip_strategy / max(n, 1), 4),
            "hexagram_flip_ratio": round(flip_hexagram / max(n, 1), 4),
            "mean_d_yao_quality": round(d_yao / max(n, 1), 4),
            "mean_d_hexagram_score": round(d_hex_score / max(n, 1), 4),
            "mean_d_force": round(d_force / max(n, 1), 4),
            "mean_d_approach_angle": round(d_angle / max(n, 1), 4),
            "examples": per_obj[:3],
        })

    # —— 排序：按 change_ratio 降序(贡献最大在前) ——
    rows.sort(key=lambda r: (-r["change_ratio"], -r["mean_d_yao_quality"]))

    print("\n===== 逐维消融结果(固定该维为均值后, 决策变化) =====")
    print(f"{'特征':<22s}{'变化占比':>8s}{'策略翻':>7s}{'卦象翻':>7s}"
          f"{'Δ爻质':>8s}{'Δ卦分':>8s}{'Δ力':>7s}{'Δ角':>7s}")
    print("-" * 78)
    for r in rows:
        print(f"{r['dim']:<22s}{r['change_ratio']:8.2%}{r['strategy_flip_ratio']:7.2%}"
              f"{r['hexagram_flip_ratio']:7.2%}{r['mean_d_yao_quality']:8.4f}"
              f"{r['mean_d_hexagram_score']:8.4f}{r['mean_d_force']:7.4f}"
              f"{r['mean_d_approach_angle']:7.2f}")

    # 结论
    zero = [r["dim"] for r in rows if r["change_ratio"] == 0]
    high = rows[0]["dim"] if rows else ""
    print("\n结论:")
    print(f"  - 贡献最高(固定后决策变化最多): {high}")
    if zero:
        print(f"  - 固定后*始终*零变化的维度(信息未进入决策, 需加强或审查): {zero}")
    else:
        print("  - 全部 13 维固定后都会改变部分物体决策 → 每一维都对决策有实际贡献")

    # 保存
    (out / "feature_ablation.csv").write_text(
        _to_csv(rows), encoding="utf-8")
    (out / "feature_ablation.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {out / 'feature_ablation.csv'} / .json")


def _to_csv(rows: List[Dict]) -> str:
    keys = ["dim", "mean_value", "change_ratio", "strategy_flip_ratio",
            "hexagram_flip_ratio", "mean_d_yao_quality", "mean_d_hexagram_score",
            "mean_d_force", "mean_d_approach_angle"]
    lines = [",".join(keys)]
    for r in rows:
        lines.append(",".join(str(r[k]) for k in keys))
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=30)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", default="experiments/ablation")
    args = p.parse_args()
    run_ablation(args)


if __name__ == "__main__":
    main()
