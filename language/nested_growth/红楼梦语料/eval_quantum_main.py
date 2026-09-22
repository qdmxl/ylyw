#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_quantum_main.py — 【量子主管线 vs 经典引擎】对比评测

马老师：经典引擎改为量子的。本脚本直接对比：
  - 经典 engine64（义项列表硬切 + 局部语境）
  - 量子 engine64q（6-qubit叠加态 + 语境测量）
在【多义择义】【抗坍缩】【分布健康度】【语义内化】四个机制维度的差异。

诚实原则：报告原始测量/概率/熵，不调阈值追数字。
"""
from __future__ import annotations
import numpy as np

from engine64 import Engine64
from engine64q import Engine64Q
from bagua64 import top_k, entropy, BAGUA_INDEX


def e1_compare_polysemy():
    print("=" * 66)
    print("D1 · 多义词『点』择义：经典(切义) vs 量子(测量)")
    print("=" * 66)
    cases = {
        "点火做饭": "火(离)", "雨水点滴": "水(坎)",
        "点头示意": "动作", "三点了": "时间",
    }
    print(f"  {'语境':<8}{'经典主导':<14}{'量子主导':<14}{'量子多义保持(P水>0?)':<18}")
    for sent, expect in cases.items():
        # 经典
        ce = Engine64(seed=1); ce.ensure_word("点"); ce.learn_sentence(list(sent))
        cgi, cgn, cgp = ce.cells["点"].dom_gua()
        # 量子 (重建避免累积)
        qe = Engine64Q(seed=1); qe.ensure_word("点"); qe.learn_sentence(list(sent))
        qgi, qgn, qgp = qe.cells["点"].dom()
        d = qe.cells["点"].psi_dist()
        p_akan = d[BAGUA_INDEX["坎"]]
        keep = "✓" if p_akan > 0.2 else "✗"
        print(f"  {sent:<8}{cgn+' ('+str(round(cgp,2))+')':<14}"
              f"{qgn+' ('+str(round(qgp,2))+')':<14}{keep} P水={p_akan:.2f}  期望={expect}")


def e2_dist_health():
    print("\n" + "=" * 66)
    print("D2 · 判别/多义分布健康度（抗坍缩）")
    print("=" * 66)
    # 通读红楼开头100句，统计各词主导卦分布是否健康（无单极坍缩）
    from corpus_learn64 import load_hlm, split_sentences
    sents = load_hlm("红楼梦_全文.txt", 200)
    qe = Engine64Q(seed=0)
    ce = Engine64(seed=0)
    for s in sents:
        ce.learn_sentence(list(s))
        qe.learn_sentence(list(s))
    # 统计所有词胞主导卦分布的熵（越高越健康/多义丰富）
    ce_ents = [c.ent() for c in ce.cells.values()]
    qe_ents = [c.ent() for c in qe.cells.values()]
    print(f"  引擎规模: 经典{len(ce.cells)}胞 vs 量子{len(qe.cells)}胞")
    print(f"  词胞平均语义熵(多义丰富度, 越大越健康): "
          f"经典={np.mean(ce_ents):.2f}bit vs 量子={np.mean(qe_ents):.2f}bit")
    print(f"  熵≥2bit的'多义共存'胞占比: "
          f"经典={np.mean([e>=2 for e in ce_ents]):.1%} vs 量子={np.mean([e>=2 for e in qe_ents]):.1%}")


def e3_internalization():
    print("\n" + "=" * 66)
    print("D3 · 语义内化（阅读200句后关键词语义漂移/丰富）")
    print("=" * 66)
    from corpus_learn64 import load_hlm
    sents = load_hlm("红楼梦_全文.txt", 200)
    qe = Engine64Q(seed=0)
    # 记录阅读前后
    before = {}
    for w in ["火", "水", "心", "白"]:
        qe.ensure_word(w)
        before[w] = (qe.cells[w].dom()[1], round(qe.cells[w].dom()[2], 2))
    for s in sents:
        qe.learn_sentence(list(s))
    print(f"  {'词':<6}{'初始主导':<16}{'阅读200句后主导':<16}")
    for w in ["火", "水", "心", "白"]:
        gi, gn, gp = qe.cells[w].dom()
        print(f"  {w:<6}{before[w][0]+' ('+str(before[w][1])+')':<16}{gn+' ('+str(round(gp,2))+')':<16}")


def main():
    e1_compare_polysemy()
    e2_dist_health()
    e3_internalization()
    print("\n" + "=" * 66)
    print("量子主管线 vs 经典 对比完成")
    print("=" * 66)


if __name__ == "__main__":
    main()
