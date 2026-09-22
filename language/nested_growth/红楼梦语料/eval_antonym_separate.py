#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案甲验证: '冷/热''新/旧' 源头同卦 → 读真实对立语境能否被拉开
马老师: 不怕一开始有错, 靠后续学习修正。测对立共现句子反复学后, 距离变化。
"""
import sys, numpy as np
sys.path.insert(0, ".")
from engine64q import Engine64Q
from corpus_learn64 import split_sentences
from bagua64 import fidelity, basis_state, BAGUA_INDEX

PAIRS = [("冷", "热"), ("新", "旧"), ("生", "死"), ("入", "出")]
# 每对的对立共现真实句(从红楼抽取, 已确认存在)
PAIR_SENTS = {
    ("冷", "热"): ["忽冷忽热", "试了冷热", "或一时冷热不便"],
    ("新", "旧"): ["不但是洗旧翻新", "编新不如述旧", "一色儿半新不旧"],
    ("生", "死"): ["生关死劫谁能躲", "你祖宗九死一生", "且能断人的生死"],
    ("入", "出"): ["东西两角门有人出入", "任意可以出入", "小女入都"],
}


def track_pair(eng, a, b, sents, log_every=None):
    f0 = fidelity(eng._qseeds[a], eng._qseeds[b])
    d0 = 1 - f0
    rows = [(0, d0)]
    for i, s in enumerate(sents, 1):
        eng.learn_sentence(list(s))
        if log_every and i % log_every == 0:
            rows.append((i, round(1 - fidelity(eng.cells[a].psi, eng.cells[b].psi), 3)))
    return rows


def main():
    eng = Engine64Q(seed=0, prior_decay=40)
    eng.load_quantum_seed("seed_sharpened.json")   # 锐化种子
    print("[引擎] 已加载锐化先天种子\n")
    for a, b in PAIRS:
        # 初始距离
        eng.ensure_word(a); eng.ensure_word(b)
        d0 = 1 - fidelity(eng.cells[a].psi, eng.cells[b].psi)
        print(f"{'='*58}\n『{a}』vs『{b}』  初始语义距离={d0:.3f}\n{'='*58}")
        # 反复读对立语境 N轮
        N = 40
        for rnd in range(1, N + 1):
            for s in PAIR_SENTS[(a, b)]:
                eng.learn_sentence(list(s))
            if rnd in (1, 5, 10, 20, 40):
                d = 1 - fidelity(eng.cells[a].psi, eng.cells[b].psi)
                ha = eng.cells[a].dom(); hb = eng.cells[b].dom()
                print(f"  第{rnd*len(PAIR_SENTS[(a,b)])}次语境后: 距离={d:.3f}   {a}:{ha[1]}({ha[2]:.2f}) {b}:{hb[1]}({hb[2]:.2f})")


if __name__ == "__main__":
    main()
