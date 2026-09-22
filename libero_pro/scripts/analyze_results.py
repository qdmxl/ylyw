#!/usr/bin/env python3
"""
结果分析：语义一致性 + 扰动鲁棒性

关键指标（论文叙事核心）：
  - success_rate            各扰动下的任务成功率
  - robust_drop             相对 none 基线的成功率衰减
  - semantic_consistency    语义扰动下卦象与基线的一致率（越高越好 → 语义理解）
  - hexagram_shift_ratio    物体/位置扰动下卦象变化率（应 > 0 → 情境重估）
"""

import os
import sys
import json
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_latest():
    files = sorted(glob.glob(os.path.join(ROOT, "results", "local_eval_*.json")))
    if not files:
        raise FileNotFoundError("results/ 下没有评测结果")
    with open(files[-1]) as f:
        return json.load(f), files[-1]


def analyze(report: dict):
    conds = report["conditions"]
    base = conds.get("none", {})
    base_hx = set(base.get("hexagram_distribution", {}).keys())

    print("=" * 68)
    print("LIBERO-PRO × YLYW 结果分析")
    print("=" * 68)
    print(f"{'条件':<10}{'成功率':>8}{'衰减':>8}{'主卦占比':>10}{'独特卦象':>10}{'与基线同卦':>12}")
    print("-" * 68)

    summary = {}
    for name, d in conds.items():
        rate = d["success_rate"]
        drop = base["success_rate"] - rate
        hx = d.get("hexagram_distribution", {})
        # 与基线共享的卦象占比
        shared = sum(v for k, v in hx.items() if k in base_hx)
        total = sum(hx.values()) or 1
        overlap = shared / total
        print(f"{name:<10}{rate:>7.1%}{drop:>+8.1%}{d['dominant_hexagram_share']:>10.1%}"
              f"{d['unique_hexagrams']:>10}{overlap:>12.1%}")
        summary[name] = {"success_rate": rate, "drop": drop,
                         "hexagram_overlap_with_base": overlap,
                         "unique_hexagrams": d["unique_hexagrams"]}

    print("-" * 68)
    # 语义一致性：semantic 应保持与 none 高重叠
    sem = summary.get("semantic")
    if sem:
        print(f"\n[语义一致性] semantic 扰动与基线卦象重叠 = {sem['hexagram_overlap_with_base']:.1%}")
        print("  → 越高说明 YLYW 对语义等价改写保持稳定（语义理解而非 token 匹配）")
    # 情境重估：position/object 应有卦象变化
    for name in ("object", "position", "task", "all"):
        s = summary.get(name)
        if s:
            shift = 1.0 - s["hexagram_overlap_with_base"]
            print(f"[情境重估] {name:8s} 卦象变化率 = {shift:.1%} （期望 > 0）")

    max_drop = max((v["drop"] for k, v in summary.items() if k != "none"), default=0)
    print("\n[鲁棒性] 最大成功率衰减 = {:.1f}%（VLA 在官方 LIBERO-PRO 上为 ~90%→0%）".format(max_drop * 100))
    return summary


if __name__ == "__main__":
    report, path = load_latest()
    print(f"分析文件: {path}\n")
    s = analyze(report)
    out = os.path.join(ROOT, "results", "analysis_latest.json")
    with open(out, "w") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    print(f"\n分析结果已保存: {out}")
