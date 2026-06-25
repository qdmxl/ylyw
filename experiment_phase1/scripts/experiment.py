#!/usr/bin/env python3
"""
YLYW 论文抓取验证实验 — 主实验脚本 (Experiment)

完整实验编排：仿真物体生成 → YLYW推理 → 策略映射 → 结果汇总

四个实验（对应论文中的实验设计）：
  实验一：零样本基线 — 8类×40物体×3重复 = 120次推理
  实验二：爻位力修正 — modifier 对比分析
  实验三：策略多样性 — 按类型统计策略分布
  实验四：难度鲁棒性 — easy/medium/hard 三档对比

用法:
  # 完整实验
  python3 experiment.py --objects 40 --repeats 3

  # 快速测试
  python3 experiment.py --objects 8 --repeats 1

  # 指定难度
  python3 experiment.py --difficulty hard

  # 消融对比
  python3 experiment.py --ablation  # 含爻位关系开关对比

输出:
  results.csv  — 每条实验记录
  results.json — 完整结构化数据
"""

import sys
import os
import time
import csv
import json
import argparse
import random
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 路径设置
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent          # experiment_phase1/
YLYW_ROOT = PROJECT_DIR.parent           # ylyw/
RESEARCH_ROOT = YLYW_ROOT.parent         # 科研/
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(YLYW_ROOT))
sys.path.insert(0, str(RESEARCH_ROOT))   # 使 'import ylyw' 可用

from ylyw_core.prior_manual import PriorManual
from ylyw.simulation import SimulationScene, OBJECT_TEMPLATES
from strategy_mapping import StrategyMapper
from simulation_scene import EnhancedSimulationScene


# ============================================================
# 实验配置
# ============================================================
class ExperimentConfig:
    """实验参数"""

    def __init__(self, **kwargs):
        self.num_objects = kwargs.get("num_objects", 40)
        self.repeats = kwargs.get("repeats", 3)
        self.seed = kwargs.get("seed", 42)
        self.difficulty = kwargs.get("difficulty", "medium")
        self.use_yao_relations = kwargs.get("use_yao_relations", True)
        self.verbose = kwargs.get("verbose", False)
        self.object_types = kwargs.get("object_types",
                                       list(OBJECT_TEMPLATES.keys()))
        self.output_dir = kwargs.get("output_dir", "data")
        self.run_id = kwargs.get("run_id",
                                 datetime.now().strftime("%Y%m%d_%H%M%S"))

    def to_dict(self) -> dict:
        return {
            "num_objects": self.num_objects,
            "repeats": self.repeats,
            "seed": self.seed,
            "difficulty": self.difficulty,
            "use_yao_relations": self.use_yao_relations,
            "object_types": self.object_types,
            "run_id": self.run_id,
        }


# ============================================================
# 实验结果数据结构
# ============================================================
class TrialResult:
    def __init__(self, obj_id=0, obj_type="unknown", obj_variant="",
                 trial=0, hexagram_name="", hexagram_similarity=0.0,
                 strategy_type="", force_preset=0.5, modifier=1.0,
                 effective_force=0.5, S_yao=0.0, inference_ms=0.0,
                 strategy_label="neutral", difficulty="medium",
                 occluded=False, yao_relations_enabled=True):
        self.obj_id = obj_id
        self.obj_type = obj_type
        self.obj_variant = obj_variant
        self.trial = trial
        self.hexagram_name = hexagram_name
        self.hexagram_similarity = hexagram_similarity
        self.strategy_type = strategy_type
        self.force_preset = force_preset
        self.modifier = modifier
        self.effective_force = effective_force
        self.S_yao = S_yao
        self.inference_ms = inference_ms
        self.strategy_label = strategy_label
        self.difficulty = difficulty
        self.occluded = occluded
        self.yao_relations_enabled = yao_relations_enabled

    def to_dict(self) -> dict:
        return {
            "obj_id": self.obj_id,
            "obj_type": self.obj_type,
            "obj_variant": self.obj_variant,
            "trial": self.trial,
            "hexagram_name": self.hexagram_name,
            "hexagram_similarity": self.hexagram_similarity,
            "strategy_type": self.strategy_type,
            "force_preset": self.force_preset,
            "modifier": self.modifier,
            "effective_force": self.effective_force,
            "S_yao": self.S_yao,
            "inference_ms": self.inference_ms,
            "strategy_label": self.strategy_label,
            "difficulty": self.difficulty,
            "occluded": self.occluded,
            "yao_relations_enabled": self.yao_relations_enabled,
        }


# ============================================================
# 策略合理性评估
# ============================================================
REASONABLE_KEYWORDS = {
    "sphere":   ["dynamic", "following", "non_conflict", "conditional",
                 "adaptive", "compliant", "soft", "cautious", "wrap",
                 "predictive"],
    "cube":     ["power", "forceful", "wrap", "precise", "direct", "stable",
                 "standard", "balanced", "robust", "power_accumulating"],
    "cylinder": ["dynamic", "following", "power", "adaptive", "direct",
                 "wrap", "stable", "compliant"],
    "bowl":     ["precise", "cautious", "adaptive", "wrap", "gentle", "soft",
                 "conditional", "top_down"],
    "bottle":   ["cautious", "precise", "adaptive", "gentle", "conditional",
                 "compliant"],
    "plate":    ["precise", "conditional", "gentle", "cautious", "balanced",
                 "top_down"],
    "rock":     ["adaptive", "power", "forceful", "compliant", "wrap",
                 "robust_power"],
    "vase":     ["cautious", "precise", "gentle", "adaptive", "conditional"],
}

ERROR_KEYWORDS = {
    "sphere":   ["power_grasp", "forceful", "power_accumulating", "robust_power"],
    "cube":     ["dynamic"],
    "bowl":     ["power_grasp", "forceful", "dynamic", "power_accumulating",
                 "robust_power"],
    "bottle":   ["power_grasp", "forceful", "dynamic", "robust_power"],
    "plate":    ["power_grasp", "forceful", "dynamic", "robust_power"],
    "vase":     ["power_grasp", "forceful", "dynamic", "robust_power"],
}


def evaluate_strategy(obj_type: str, strategy: str) -> str:
    """按白名单/黑名单评估策略合理性"""
    errors = ERROR_KEYWORDS.get(obj_type, [])
    if any(e in strategy for e in errors):
        return "error"
    reasonable = REASONABLE_KEYWORDS.get(obj_type, ["standard", "balanced"])
    if any(r in strategy for r in reasonable):
        return "reasonable"
    return "neutral"


# ============================================================
# 实验结果分析器
# ============================================================
class ResultsAnalyzer:
    """分析实验结果"""

    @staticmethod
    def compute_stats(results: List[TrialResult]) -> dict:
        """从结果列表计算汇总统计"""
        total = len(results)
        if total == 0:
            return {}

        reasonable = sum(1 for r in results if r.strategy_label == "reasonable")
        errors = sum(1 for r in results if r.strategy_label == "error")
        neutral = total - reasonable - errors

        # 策略分布
        strategies = {}
        for r in results:
            s = r.strategy_type
            strategies[s] = strategies.get(s, 0) + 1

        # 数值统计
        avg_infer = np.mean([r.inference_ms for r in results])
        avg_sim = np.mean([r.hexagram_similarity for r in results])
        avg_S_yao = np.mean([r.S_yao for r in results])
        avg_force = np.mean([r.effective_force for r in results])

        # 按类型
        per_type = {}
        for r in results:
            t = r.obj_type
            if t not in per_type:
                per_type[t] = {"total": 0, "reasonable": 0, "error": 0,
                              "strategies": set(), "S_yao_sum": 0, "force_sum": 0}
            info = per_type[t]
            info["total"] += 1
            if r.strategy_label == "reasonable":
                info["reasonable"] += 1
            elif r.strategy_label == "error":
                info["error"] += 1
            info["strategies"].add(r.strategy_type)
            info["S_yao_sum"] += r.S_yao
            info["force_sum"] += r.effective_force

        # 按难度
        per_diff = {}
        for r in results:
            d = r.difficulty
            if d not in per_diff:
                per_diff[d] = {"total": 0, "reasonable": 0, "error": 0}
            per_diff[d]["total"] += 1
            if r.strategy_label == "reasonable":
                per_diff[d]["reasonable"] += 1
            elif r.strategy_label == "error":
                per_diff[d]["error"] += 1

        # 按遮挡
        occ_results = [r for r in results if r.occluded]
        vis_results = [r for r in results if not r.occluded]
        occ_rate = (sum(1 for r in occ_results if r.strategy_label == "reasonable")
                    / len(occ_results)) if occ_results else 0
        vis_rate = (sum(1 for r in vis_results if r.strategy_label == "reasonable")
                    / len(vis_results)) if vis_results else 0

        return {
            "total": total,
            "reasonable": reasonable,
            "reasonable_pct": round(100 * reasonable / total, 1),
            "error": errors,
            "error_pct": round(100 * errors / total, 1),
            "neutral": neutral,
            "neutral_pct": round(100 * neutral / total, 1),
            "avg_inference_ms": round(avg_infer, 2),
            "avg_similarity": round(avg_sim, 4),
            "avg_S_yao": round(avg_S_yao, 2),
            "avg_effective_force": round(avg_force, 2),
            "strategy_distribution": strategies,
            "unique_strategies": len(strategies),
            "per_type": {t: {
                "total": i["total"],
                "reasonable": i["reasonable"],
                "reasonable_pct": round(100 * i["reasonable"] / i["total"], 1),
                "error": i["error"],
                "unique_strategies": len(i["strategies"]),
                "avg_S_yao": round(i["S_yao_sum"] / i["total"], 3),
                "avg_force": round(i["force_sum"] / i["total"], 3),
            } for t, i in sorted(per_type.items())},
            "per_difficulty": {d: {
                "total": i["total"],
                "reasonable_pct": round(100 * i["reasonable"] / i["total"], 1),
                "error_pct": round(100 * i["error"] / i["total"], 1),
            } for d, i in sorted(per_diff.items())},
            "occlusion_impact": {
                "occluded_rate": round(100 * occ_rate, 1),
                "visible_rate": round(100 * vis_rate, 1),
                "delta": round(100 * (vis_rate - occ_rate), 1),
            },
        }

    @staticmethod
    def print_stats(stats: dict):
        """打印汇总报告"""
        print(f"\n{'='*60}")
        print(f"  YLYW EXPERIMENT RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"  Total trials:          {stats['total']}")
        print(f"  Reasonable strategies: {stats['reasonable']} "
              f"({stats['reasonable_pct']}%) ✅")
        print(f"  Neutral strategies:    {stats['neutral']} "
              f"({stats['neutral_pct']}%) —")
        print(f"  Error strategies:      {stats['error']} "
              f"({stats['error_pct']}%) ❌")
        print(f"  Unique strategies:     {stats['unique_strategies']}")
        print(f"  Avg inference:         {stats['avg_inference_ms']} ms")
        print(f"  Avg similarity:        {stats['avg_similarity']}")
        print(f"  Avg S_yao:             {stats['avg_S_yao']}")
        print(f"  Avg effective force:   {stats['avg_effective_force']}")

        # 策略分布
        print(f"\n  Strategy distribution:")
        strats = stats["strategy_distribution"]
        max_c = max(strats.values()) if strats else 1
        for s, c in sorted(strats.items(), key=lambda x: -x[1])[:15]:
            bar = "█" * int(c * 40 / max_c)
            print(f"    {s:30s} {bar} {c}")

        # 按类型
        print(f"\n  Per-type reasonable rate:")
        for t, info in stats["per_type"].items():
            print(f"    {t:8s}: {info['reasonable_pct']:5.1f}% "
                  f"({info['reasonable']}/{info['total']}) "
                  f"errors={info['error']} "
                  f"strategies={info['unique_strategies']} "
                  f"S_yao={info['avg_S_yao']:.2f} "
                  f"force={info['avg_force']:.2f}")

        # 遮挡影响
        occ = stats["occlusion_impact"]
        print(f"\n  Occlusion impact:")
        print(f"    Occluded: {occ['occluded_rate']}%  "
              f"Visible: {occ['visible_rate']}%  "
              f"Δ={occ['delta']}%")

        # 按难度
        if len(stats.get("per_difficulty", {})) > 1:
            print(f"\n  Per-difficulty reasonable rate:")
            for d, info in stats["per_difficulty"].items():
                print(f"    {d:6s}: {info['reasonable_pct']}% "
                      f"(errors={info['error_pct']}%)")

        print(f"{'='*60}\n")

    @staticmethod
    def save_csv(results: List[TrialResult], path: str):
        """保存 CSV"""
        fieldnames = [
            "obj_id", "obj_type", "obj_variant", "trial",
            "hexagram_name", "hexagram_similarity",
            "strategy_type", "force_preset", "modifier",
            "effective_force", "S_yao", "inference_ms",
            "strategy_label", "difficulty", "occluded",
            "yao_relations_enabled",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(r.to_dict())
        print(f"📁 CSV saved: {path}")

    @staticmethod
    def save_json(results: List[TrialResult], stats: dict, config: dict,
                  path: str):
        """保存 JSON"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "config": config,
            "stats": stats,
            "results": [r.to_dict() for r in results],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"📁 JSON saved: {path}")


# ============================================================
# 实验管理器
# ============================================================
class ExperimentRunner:
    """YLYW 抓取验证实验运行器"""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.manual = PriorManual(verbose=config.verbose)
        self.simulation = None  # 延迟初始化
        self.mapper = StrategyMapper()
        self.results: List[TrialResult] = []

    def run(self) -> List[TrialResult]:
        """执行完整实验"""
        start_time = time.time()
        cfg = self.config

        print(f"\n{'='*60}")
        print(f"  YLYW GRASP VERIFICATION EXPERIMENT")
        print(f"{'='*60}")
        print(f"  Objects:        {cfg.num_objects}")
        print(f"  Object types:   {', '.join(cfg.object_types)}")
        print(f"  Repeats:        {cfg.repeats}")
        print(f"  Total trials:   {cfg.num_objects * cfg.repeats}")
        print(f"  Difficulty:     {cfg.difficulty}")
        print(f"  Yao relations:  {cfg.use_yao_relations}")
        print(f"  Seed:           {cfg.seed}")
        print(f"  Run ID:         {cfg.run_id}")
        print(f"{'='*60}\n")

        # 生成物体
        self.simulation = EnhancedSimulationScene(
            seed=cfg.seed,
            difficulty=cfg.difficulty,
            enabled_types=cfg.object_types,
        )

        objects_per_type = max(1, cfg.num_objects // len(cfg.object_types))
        all_features, all_meta = self.simulation.generate_batch(
            objects_per_type=objects_per_type,
            types=cfg.object_types,
        )

        # 截断到 num_objects
        all_features = all_features[:cfg.num_objects]
        all_meta = all_meta[:cfg.num_objects]

        print(f"  Generated {len(all_features)} objects across "
              f"{len(cfg.object_types)} types\n")

        # 执行实验
        total = len(all_features) * cfg.repeats
        trial_count = 0

        for obj_id, (features, meta) in enumerate(zip(all_features, all_meta)):
            for trial_idx in range(cfg.repeats):
                trial_count += 1

                # 推理
                result = self._run_single_trial(
                    obj_id, meta["type"], meta["variant"],
                    features, trial_idx,
                    meta["occluded"],
                )
                self.results.append(result)

                # 进度
                pct = trial_count * 100 // total
                bar = "█" * (pct // 2) + "░" * (50 - pct // 2)
                print(f"\r  [{bar}] {trial_count}/{total} "
                      f"| {result.obj_type:6s} → "
                      f"{result.strategy_type:25s} "
                      f"| {result.strategy_label:10s} "
                      f"| S={result.S_yao:.2f} "
                      f"| f={result.effective_force:.2f}",
                      end="" if not cfg.verbose else "\n")

        elapsed = time.time() - start_time
        print(f"\n\n  ✅ Experiment complete in {elapsed:.1f}s "
              f"({total/elapsed:.1f} trials/s)\n")

        # 分析
        analyzer = ResultsAnalyzer()
        stats = analyzer.compute_stats(self.results)
        analyzer.print_stats(stats)

        # 保存
        os.makedirs(cfg.output_dir, exist_ok=True)
        csv_path = os.path.join(cfg.output_dir, f"results_{cfg.run_id}.csv")
        json_path = os.path.join(cfg.output_dir, f"results_{cfg.run_id}.json")
        analyzer.save_csv(self.results, csv_path)
        analyzer.save_json(self.results, stats, cfg.to_dict(), json_path)

        return self.results

    def _run_single_trial(self, obj_id: int, obj_type: str,
                          variant: str, features: np.ndarray,
                          trial: int, occluded: bool) -> TrialResult:
        """单次实验"""
        # 特征转 dict
        fdict = {
            "stability": float(features[0]),
            "roll_tendency": float(features[1]),
            "strength_needed": float(features[2]),
            "fragility": float(features[3]),
            "reachability": float(features[4]),
            "grasp_surface_quality": float(features[5]),
            "support_area": float(features[6]),
            "occlusion": float(features[7]),
            "obstacle_density": float(features[8]),
            "task_priority": float(features[9]),
            "weight_ratio": float(features[10]),
            "visibility": float(features[11]),
            "deformability": float(features[12]),
        }

        # YLYW 推理
        t0 = time.perf_counter()
        perception, strategy = self.manual.process(fdict)
        t_ms = (time.perf_counter() - t0) * 1000

        # 提取结果
        hex_name = (perception["best_hexagram"].name
                    if perception["best_hexagram"] else "unknown")
        similarity = float(perception["hexagram_match_score"])
        s_type = strategy["type"]
        force_preset = strategy["force"]
        modifier = strategy.get("force_modifier", 1.0)
        effective_force = force_preset * modifier
        yaorel = perception.get("yao_relations")
        S_yao = (strategy.get("yao_quality", 0) or
                 (yaorel.score_overall if yaorel else 0))
        S_yao = float(S_yao)

        # 评估
        label = evaluate_strategy(obj_type, s_type)

        return TrialResult(
            obj_id=obj_id,
            obj_type=obj_type,
            obj_variant=variant,
            trial=trial,
            hexagram_name=hex_name,
            hexagram_similarity=round(similarity, 4),
            strategy_type=s_type,
            force_preset=round(force_preset, 2),
            modifier=round(modifier, 2),
            effective_force=round(effective_force, 2),
            S_yao=round(S_yao, 2),
            inference_ms=round(t_ms, 2),
            strategy_label=label,
            difficulty=self.config.difficulty,
            occluded=occluded,
            yao_relations_enabled=self.config.use_yao_relations,
        )

    def run_ablation(self) -> Dict[str, List[TrialResult]]:
        """消融实验：爻位关系开关对比"""
        print(f"\n{'='*60}")
        print(f"  YLYW ABLATION STUDY — Yao Relations ON vs OFF")
        print(f"{'='*60}\n")

        results_all = {}

        for use_yao, label in [(True, "with_yao"), (False, "without_yao")]:
            cfg = self.config
            cfg.use_yao_relations = use_yao
            self.results = []

            print(f"\n  Running: YLYW {label} ...")
            self.run()
            results_all[label] = list(self.results)

        # 对比
        print(f"\n{'='*60}")
        print(f"  ABLATION COMPARISON")
        print(f"{'='*60}")

        for label, results in results_all.items():
            stats = ResultsAnalyzer.compute_stats(results)
            print(f"\n  [{label}]")
            print(f"    Reasonable:  {stats['reasonable_pct']}% "
                  f"({stats['reasonable']}/{stats['total']})")
            print(f"    Errors:      {stats['error_pct']}% "
                  f"({stats['error']}/{stats['total']})")
            print(f"    Avg S_yao:   {stats['avg_S_yao']}")
            print(f"    Avg force:   {stats['avg_effective_force']}")
            print(f"    Unique stg:  {stats['unique_strategies']}")
            print(f"    Avg infer:   {stats['avg_inference_ms']} ms")

        return results_all


# ============================================================
# main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="YLYW Grasp Verification Experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--objects", type=int, default=40,
                        help="Number of objects (default: 40)")
    parser.add_argument("--repeats", type=int, default=3,
                        help="Repeats per object (default: 3)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--difficulty", type=str, default="medium",
                        choices=["easy", "medium", "hard"],
                        help="Scene difficulty (default: medium)")
    parser.add_argument("--types", type=str, nargs="+",
                        default=list(OBJECT_TEMPLATES.keys()),
                        help="Object types (default: all 8)")
    parser.add_argument("--no-yao", action="store_true",
                        help="Disable yao relations")
    parser.add_argument("--ablation", action="store_true",
                        help="Run ablation study (yao relations ON vs OFF)")
    parser.add_argument("--output", type=str, default="data",
                        help="Output directory (default: data)")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--demo", action="store_true",
                        help="Demo mode: 8 objects, 1 repeat")
    args = parser.parse_args()

    if args.demo:
        args.objects = 8
        args.repeats = 1

    config = ExperimentConfig(
        num_objects=args.objects,
        repeats=args.repeats,
        seed=args.seed,
        difficulty=args.difficulty,
        use_yao_relations=not args.no_yao,
        verbose=args.verbose,
        object_types=args.types,
        output_dir=args.output,
    )

    runner = ExperimentRunner(config)

    if args.ablation:
        runner.run_ablation()
    else:
        runner.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
