#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_dual_channel_growth.py — 方案甲端到端演示：跑 G1(覆盖)+G2(复杂)+G3(收敛)
并生成三维成长可视化 growth.png
"""
import sys, json
sys.path.insert(0, ".")
from dual_channel_growth import run_growth, run_convergence

res = run_growth([0.05, 0.1, 0.2, 0.4, 0.7, 1.0])
conv = run_convergence()

print("=== 方案甲：双通道嵌套自增长语义系统 端到端演示 ===\n")
print("【G1+G2】阅读量 → 覆盖面 → 复杂度")
print(f"{'阅读句':>6} {'认识字符':>8} {'字元胞':>6} {'词元胞':>8} {'总元胞':>8}")
for r in res:
    print(f"{r['n_sent']:>6} {r['G1_chars']:>8} {r['G2_char_cells']:>6} "
          f"{r['G2_word_cells']:>8} {r['G2_total_cells']:>8}")

print("\n【G3】阅读增量 → 语义收敛(理解巩固)")
print(f"{'阅读比例':>8} {'语义类字数':>8} {'稳定率':>8}")
for r in conv:
    s = r['stable']
    print(f"{r['frac']*100:>6.0f}% {r['n']:>8} {('—' if s is None else f'{s*100:.0f}%'):>8}")

# 保存指标供绘图
json.dump({"growth": res, "conv": conv}, open("growth_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已保存 growth_metrics.json")
