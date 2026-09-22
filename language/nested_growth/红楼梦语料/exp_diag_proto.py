#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_diag_proto.py — A修法第一步：量化判别框架缺陷根因

诊断对象：exp_hlm_ng_v3.py 里的判别层（中心化余弦 + 单一字原型 PROTO）
问题记忆（8-19）："金=乾全是0.79平值向量，中心化后归零→金类永远选不到"
本文把 bug 量化：
  1) 每个原型词(水/火/树/金/山)经 word_sem_yao 得到的六爻向量
  2) 中心化后各自的范数(若≈0 → 该类被废)
  3) 5个原型两两余弦矩阵(类间不对称程度)
  4) 与"部首语义原型爻"对照(用 _radical_yao 的卦义而非单字哈希)
"""
import sys, math
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

def center(v):
    m = sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v))
def cos_c(a, b):
    a = center(a); b = center(b)
    na, nb = norm(a), norm(b)
    if na < 1e-9 or nb < 1e-9: return 0.0
    return sum(x*y for x, y in zip(a, b)) / (na*nb)

PROTO_OLD = {"水":"水", "火":"火", "木":"树", "金":"金", "土":"山"}

print("═══ ① 单一字原型经 word_sem_yao 的六爻 + 中心化范数 ═══")
print(f"{'类':<4}{'原型词':<6}{'六爻':<32}{'原范数':<8}{'中心化范数'}")
yaos = {}
for cat, w in PROTO_OLD.items():
    y = NG.word_sem_yao(w)
    yaos[cat] = y
    print(f"{cat:<4}{w:<6}{str([round(x,2) for x in y]):<32}"
          f"{norm(y):<8.3f}{norm(center(y)):.3f}  {'⚡被废' if norm(center(y)) < 0.05 else ''}")

print("\n═══ ② 中心化余弦矩阵（类间不对称→中性基线偏水根因） ═══")
cats = list(PROTO_OLD)
print("      " + "  ".join(f"{c:>6}" for c in cats))
for a in cats:
    row = "  ".join(f"{cos_c(yaos[a], yaos[b]):6.2f}" for b in cats)
    print(f"{a:<4}  {row}")

print("\n═══ ③ 用卦义原型(radical_yao) 对比：均衡化是否解决 ═══")
# 每个类别取一个"语义饱满、非平值"的卦义原型
BAGUA_PROTO = {
    "水": "水", "火": "火", "木": "木", "金": "金", "土": "山",
}
print(f"{'类':<4}{'原型':<6}{'六爻(radical)':<34}{'中心化范数'}")
by_rad = {}
for cat, w in BAGUA_PROTO.items():
    # 直接用部首语义优先的稳定爻（字→卦义，非哈希）
    y = NG._radical_yao(w) or NG._stable_yao(w)
    by_rad[cat] = y
    print(f"{cat:<4}{w:<6}{str([round(x,2) for x in y]):<34}{norm(center(y)):.3f}"
          f"{'  ⚡被废' if norm(center(y)) < 0.05 else ''}")

print("\n═══ ④ 卦义原型 中心化余弦矩阵 ═══")
print("      " + "  ".join(f"{c:>6}" for c in cats))
for a in cats:
    row = "  ".join(f"{cos_c(by_rad[a], by_rad[b]):6.2f}" for b in cats)
    print(f"{a:<4}  {row}")

# 关键指标：最小类间余弦间隔（越大越可分）
from itertools import combinations
def min_sep(m):
    mn = 99.0
    for a, b in combinations(m, 2):
        mn = min(mn, cos_c(m[a], m[b]))
    return mn
print(f"\n类间最小余弦间隔:  旧单一字原型={min_sep(yaos):.3f}  卦义原型={min_sep(by_rad):.3f}")
print(f"被废类数量(范数<0.05): 旧={sum(1 for c in yaos if norm(center(yaos[c]))<0.05)}"
      f"  卦义={sum(1 for c in by_rad if norm(center(by_rad[c]))<0.05)}")
