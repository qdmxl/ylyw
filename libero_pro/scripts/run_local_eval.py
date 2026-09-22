#!/usr/bin/env python3
"""
一键运行 LIBERO-PRO 轻量版评测（阶段一）

用法:
    python3 scripts/run_local_eval.py --episodes 20 --perturb all
    python3 scripts/run_local_eval.py --episodes 10 --perturb none,position,semantic
"""

import os
import sys
import json
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import yaml  # noqa: E402
from sim.runner import run_eval  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="LIBERO-PRO × YLYW 本地评测")
    ap.add_argument("--episodes", type=int, default=20, help="每个条件的 episode 数")
    ap.add_argument("--perturb", type=str, default="all",
                    help="条件: all 或逗号分隔 none,object,position,semantic,task")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    cfg_path = os.path.join(ROOT, "configs", "perturbation.yaml")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    conditions = None if args.perturb == "all" else [c.strip() for c in args.perturb.split(",")]

    print("=" * 64)
    print(f"LIBERO-PRO × YLYW 轻量评测 | episodes={args.episodes} | 条件={args.perturb}")
    print("=" * 64)
    report = run_eval(cfg, episodes=args.episodes, conditions=conditions, seed=args.seed)

    # 汇总：扰动下的平均衰减
    conds = report["conditions"]
    if "none" in conds:
        base = conds["none"]["success_rate"]
        print("-" * 64)
        for name, d in conds.items():
            drop = base - d["success_rate"]
            print(f"  {name:9s} 成功率 {d['success_rate']:5.1%}  (相对 none 变化 {drop:+.1%})")

    out_dir = os.path.join(ROOT, "results")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = args.out or os.path.join(out_dir, f"local_eval_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("-" * 64)
    print(f"结果已保存: {out_path}")


if __name__ == "__main__":
    main()
