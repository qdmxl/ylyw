#!/usr/bin/env python3
"""
YLYW 推理引擎封装 (YLYW Engine)

提供命令行接口，支持：
  - 单物体推理（展示完整推理链）
  - 批量推理（输出 CSV）
  - 与 experiment.py 配合的编程接口

用法:
  # 单物体推理
  python3 ylyw_engine.py --object tennis_ball

  # 批量推理
  python3 ylyw_engine.py --batch --objects 40 --repeats 3 --csv results.csv

  # 演示模式
  python3 ylyw_engine.py --demo
"""

import sys
import os
import time
import csv
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 路径设置
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent          # experiment_phase1/
YLYW_ROOT = PROJECT_DIR.parent           # ylyw/
RESEARCH_ROOT = YLYW_ROOT.parent         # 科研/
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(YLYW_ROOT))
sys.path.insert(0, str(RESEARCH_ROOT))

from ylyw_core.prior_manual import PriorManual
from ylyw.simulation import SimulationScene, OBJECT_TEMPLATES
from object_presets import OBJECT_PRESETS, get_feature_dict


# ============================================================
# YLYW 引擎
# ============================================================
class YLYWEngine:
    """YLYW 推理引擎封装"""

    def __init__(self, verbose=False, use_yao_relations=True):
        self.manual = PriorManual(verbose=verbose)
        self.use_yao_relations = use_yao_relations
        self.verbose = verbose

        # 策略合理性白名单（按物体类型，关键词匹配）
        self.reasonable_keywords = {
            "sphere":   ["dynamic", "wrap", "adaptive", "following",
                         "non_conflict", "conditional", "compliant",
                         "soft", "cautious", "predictive"],
            "cube":     ["power", "forceful", "wrap", "precise", "direct",
                         "stable", "standard", "balanced", "robust"],
            "cylinder": ["dynamic", "wrap", "power", "following", "adaptive",
                         "direct", "stable"],
            "bowl":     ["precise", "cautious", "wrap", "conditional",
                         "gentle", "adaptive", "soft"],
            "bottle":   ["cautious", "precise", "conditional", "gentle",
                         "adaptive"],
            "plate":    ["precise", "conditional", "gentle", "cautious"],
            "rock":     ["adaptive", "power", "wrap", "forceful", "compliant"],
            "vase":     ["cautious", "precise", "gentle", "conditional"],
        }
        self.error_keywords = {
            "sphere":   ["power_grasp", "forceful", "power_accumulating"],
            "cube":     ["dynamic"],
            "bowl":     ["power_grasp", "forceful", "dynamic", "power_accumulating"],
            "bottle":   ["power_grasp", "forceful", "dynamic"],
            "plate":    ["power_grasp", "forceful", "dynamic"],
            "vase":     ["power_grasp", "forceful", "dynamic"],
        }

    def infer(self, features: dict) -> dict:
        """单次推理"""
        t0 = time.perf_counter()
        perception, strategy = self.manual.process(features)
        t_ms = (time.perf_counter() - t0) * 1000

        return {
            "perception": perception,
            "strategy": strategy,
            "inference_ms": round(t_ms, 2),
        }

    def infer_from_preset(self, obj_key: str) -> dict:
        """从预设物体推理"""
        features = get_feature_dict(obj_key)
        return self.infer(features)

    def batch_infer(self, objects: List[Tuple[int, str, dict]]) -> List[dict]:
        """批量推理"""
        results = []
        for obj_id, obj_type, features in objects:
            result = self.infer(features)
            result.update({
                "obj_id": obj_id,
                "obj_type": obj_type,
            })
            results.append(result)
        return results

    def evaluate_strategy(self, obj_type: str, strategy_type: str) -> str:
        """评估策略合理性"""
        errors = self.error_keywords.get(obj_type, [])
        if any(e in strategy_type for e in errors):
            return "error"
        reasonable = self.reasonable_keywords.get(obj_type, [])
        if any(r in strategy_type for r in reasonable):
            return "reasonable"
        return "neutral"

    def format_result(self, obj_type: str, obj_name: str,
                      result: dict) -> dict:
        """将推理结果格式化为标准化输出"""
        p = result["perception"]
        s = result["strategy"]
        label = self.evaluate_strategy(obj_type, s["type"])

        yaorel = p.get("yao_relations")
        S_yao = (s.get("yao_quality", 0) or
                 (yaorel.score_overall if yaorel else 0))

        return {
            "obj_type": obj_type,
            "obj_name": obj_name,
            "hexagram_name": (p["best_hexagram"].name
                              if p["best_hexagram"] else "unknown"),
            "hexagram_similarity": round(float(p["hexagram_match_score"]), 4),
            "strategy_type": s["type"],
            "force_preset": s["force"],
            "modifier": s.get("force_modifier", 1.0),
            "S_yao": round(float(S_yao), 4),
            "inference_ms": result["inference_ms"],
            "yao_vector": p["yao_vector"].tolist()
                          if hasattr(p["yao_vector"], "tolist")
                          else list(p["yao_vector"]),
            "trigram_membership": p["trigram_memberships"].tolist()
                                  if hasattr(p["trigram_memberships"], "tolist")
                                  else list(p["trigram_memberships"]),
            "strategy_label": label,
        }

    def explain(self, features: dict) -> str:
        """生成可解释推理链"""
        perception, _ = self.manual.process(features)
        return self.manual.explain_reasoning(perception)

    def get_summary_stats(self, results: List[dict]) -> dict:
        """从结果列表计算汇总统计"""
        total = len(results)
        if total == 0:
            return {}

        reasonable = sum(1 for r in results
                        if r["strategy_label"] == "reasonable")
        errors = sum(1 for r in results
                    if r["strategy_label"] == "error")

        strategies = {}
        for r in results:
            s = r["strategy_type"]
            strategies[s] = strategies.get(s, 0) + 1

        avg_infer = np.mean([r["inference_ms"] for r in results])
        avg_sim = np.mean([r["hexagram_similarity"] for r in results])
        avg_S_yao = np.mean([r["S_yao"] for r in results])

        # 按类型统计
        per_type = {}
        for r in results:
            t = r["obj_type"]
            if t not in per_type:
                per_type[t] = {"total": 0, "reasonable": 0, "error": 0}
            per_type[t]["total"] += 1
            if r["strategy_label"] == "reasonable":
                per_type[t]["reasonable"] += 1
            elif r["strategy_label"] == "error":
                per_type[t]["error"] += 1

        return {
            "total": total,
            "reasonable": reasonable,
            "reasonable_pct": round(100 * reasonable / total, 1),
            "error": errors,
            "error_pct": round(100 * errors / total, 1),
            "avg_inference_ms": round(avg_infer, 2),
            "avg_similarity": round(avg_sim, 4),
            "avg_S_yao": round(avg_S_yao, 2),
            "strategy_distribution": strategies,
            "per_type": per_type,
        }

    def print_summary(self, stats: dict):
        """打印汇总统计"""
        print(f"\n{'='*60}")
        print(f"  YLYW EXPERIMENT SUMMARY")
        print(f"{'='*60}")
        print(f"  Total trials:      {stats.get('total', 0)}")
        print(f"  Reasonable:        {stats.get('reasonable', 0)} "
              f"({stats.get('reasonable_pct', 0)}%)")
        print(f"  Errors:            {stats.get('error', 0)} "
              f"({stats.get('error_pct', 0)}%)")
        print(f"  Neutral:           {stats.get('total',0) - stats.get('reasonable',0) - stats.get('error',0)}")
        print(f"  Avg inference:     {stats.get('avg_inference_ms', 0)} ms")
        print(f"  Avg similarity:    {stats.get('avg_similarity', 0)}")
        print(f"  Avg S_yao:         {stats.get('avg_S_yao', 0)}")
        print(f"")
        strategies = stats.get("strategy_distribution", {})
        if strategies:
            print(f"  Strategy distribution:")
            max_c = max(strategies.values())
            for s, c in sorted(strategies.items(), key=lambda x: -x[1]):
                bar = "█" * int(c * 40 / max_c) if max_c > 0 else ""
                print(f"    {s:30s} {bar} {c}")
        per_type = stats.get("per_type", {})
        if per_type:
            print(f"\n  Per-type reasonable rate:")
            for t, info in sorted(per_type.items()):
                rate = (100 * info["reasonable"] / info["total"]
                        if info["total"] > 0 else 0)
                print(f"    {t:8s}: {rate:5.1f}% ({info['reasonable']}/{info['total']})"
                      f"  errors={info['error']}")
        print(f"{'='*60}\n")

    def save_csv(self, results: List[dict], path: str):
        """保存结果为 CSV"""
        fieldnames = [
            "obj_type", "obj_name",
            "hexagram_name", "hexagram_similarity",
            "strategy_type", "force_preset", "modifier",
            "S_yao", "inference_ms", "strategy_label",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
        print(f"📁 CSV saved: {path}")

    def save_json(self, results: List[dict], stats: dict, path: str):
        """保存结果为 JSON"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "results": results,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        print(f"📁 JSON saved: {path}")


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="YLYW 推理引擎 — 抓取策略推理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 ylyw_engine.py --object tennis_ball           # 单物体推理
  python3 ylyw_engine.py --batch --objects 40 --csv results.csv  # 批量
  python3 ylyw_engine.py --demo                        # 演示模式
        """,
    )
    parser.add_argument("--object", type=str, metavar="KEY",
                        help="单个物体（如 tennis_ball）")
    parser.add_argument("--batch", action="store_true",
                        help="批量推理模式")
    parser.add_argument("--objects", type=int, default=40,
                        help="批量时物体总数")
    parser.add_argument("--repeats", type=int, default=3,
                        help="每个物体重复次数")
    parser.add_argument("--csv", type=str, default="results.csv",
                        help="CSV 输出路径")
    parser.add_argument("--json", type=str, default=None,
                        help="JSON 输出路径")
    parser.add_argument("--demo", action="store_true",
                        help="演示模式（详尽推理链）")
    parser.add_argument("--quiet", action="store_true",
                        help="安静模式")
    parser.add_argument("--no-yao", action="store_true",
                        help="禁用爻位关系运算")
    args = parser.parse_args()

    engine = YLYWEngine(
        verbose=args.demo,
        use_yao_relations=not args.no_yao,
    )

    if args.demo:
        # 演示模式：每类物体一个，展示推理链
        print("=" * 60)
        print("  YLYW DEMO — One object per type")
        print("=" * 60)
        scene = SimulationScene(seed=42)
        obj_types = list(OBJECT_TEMPLATES.keys())
        for obj_type in obj_types:
            objs = scene.generate_scene_with_types([obj_type])
            obj = objs[0]
            features = obj.features.to_dict()
            print(f"\n{'─'*60}")
            print(f"  Type: {obj_type} ({obj.display_name})")
            print(f"{'─'*60}")
            chain = engine.explain(features)
            print(chain)
            input("\n  Press Enter for next...")
        return 0

    if args.batch:
        print(f"\n{'='*60}")
        print(f"  YLYW BATCH INFERENCE")
        print(f"  Objects: {args.objects}  |  Repeats: {args.repeats}")
        print(f"{'='*60}\n")

        scene = SimulationScene(seed=42)
        total = args.objects * args.repeats
        results = []

        # 按类型均匀生成
        obj_types = list(OBJECT_TEMPLATES.keys())
        per_type = max(1, args.objects // len(obj_types))
        use_types = obj_types * per_type
        use_types = use_types[:args.objects]

        trial_count = 0
        for repeat in range(args.repeats):
            for obj_id, obj_type in enumerate(use_types):
                trial_count += 1
                objs = scene.generate_scene_with_types([obj_type])
                obj = objs[0]
                features = obj.features.to_dict()

                result = engine.infer(features)
                formatted = engine.format_result(
                    obj_type, obj.display_name, result)

                # 为重复实验标记不同 trial
                formatted["obj_id"] = obj_id
                formatted["trial"] = repeat
                formatted["obj_type"] = obj_type
                formatted["obj_name"] = f"{obj.display_name}_r{repeat}"
                results.append(formatted)

                # 进度
                pct = trial_count * 100 // total
                bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
                if not args.quiet:
                    print(f"\r[{bar}] {trial_count}/{total} "
                          f"| {obj_type:6s} → {formatted['strategy_type']:25s} "
                          f"| {formatted['strategy_label']}", end="")
        print()

        stats = engine.get_summary_stats(results)
        engine.print_summary(stats)
        engine.save_csv(results, args.csv)
        if args.json:
            engine.save_json(results, stats, args.json)
        return 0

    if args.object:
        obj_key = args.object
        if obj_key not in OBJECT_PRESETS:
            print(f"❌ Unknown object: {obj_key}")
            print(f"   Available: {', '.join(OBJECT_PRESETS.keys())}")
            return 1

        obj_info = OBJECT_PRESETS[obj_key]
        features = get_feature_dict(obj_key)

        print(f"\n{'='*60}")
        print(f"  Object: {obj_info['name']} ({obj_key})")
        print(f"  Type:   {obj_info['type']}")
        print(f"{'='*60}")

        # 特征值
        print(f"\n  📐 13D Physical Features:")
        for name, val in [
            ("stability", features["stability"]),
            ("roll_tendency", features["roll_tendency"]),
            ("strength_needed", features["strength_needed"]),
            ("fragility", features["fragility"]),
            ("reachability", features["reachability"]),
            ("grasp_surface", features["grasp_surface_quality"]),
            ("support_area", features["support_area"]),
            ("occlusion", features["occlusion"]),
            ("obstacle_density", features["obstacle_density"]),
            ("task_priority", features["task_priority"]),
            ("weight_ratio", features["weight_ratio"]),
            ("visibility", features["visibility"]),
            ("deformability", features["deformability"]),
        ]:
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"    {name:18s} [{bar}] {val:.3f}")

        # 完整推理链
        print()
        chain = engine.explain(features)
        print(chain)
        return 0

    # 默认：列出可用物体
    print("YLYW Engine — Available commands:")
    print("  --object KEY    Single object inference")
    print("  --batch         Batch inference")
    print("  --demo          Demo mode")
    print()
    print("Available objects:")
    for key, info in OBJECT_PRESETS.items():
        print(f"  {key:20s} {info['name']} ({info['type']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
