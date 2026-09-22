#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_seed_init.py — 验证词典型量子种子初始化效果

对比 engine64q 用【手写dict_prior】vs【词典学习种子seed_quantum.json】初始化时，
关键字的先天卦轮廓差异。直接反映"词典知识是否学进64卦系统"。
"""
import numpy as np
from engine64q import Engine64Q
from bagua64 import top_k

def show(tag, eng, words):
    print(f"\n=== {tag} ===")
    for w in words:
        c = eng.ensure_word(w)
        d = c.psi_dist()
        tops = ", ".join(f"{n}{v:.2f}" for i, v, n in top_k(d, 3))
        print(f"  『{w}』 熵={c.ent():.2f}bit  top:[{tops}]")

def main():
    words = ["水", "火", "心", "点", "金", "山", "雨", "木", "黑", "开"]
    # 手写 dict_prior
    classic = Engine64Q(seed=0)
    show("手写 dict_prior 初始化", classic, words)
    # 词典学习种子
    qseed = Engine64Q(seed=0)
    qseed.load_quantum_seed()
    show("词典型 quantum seed 初始化", qseed, words)
    # 词典种子内化后读语料再变(先天+后天)
    from corpus_learn64 import load_hlm
    sents = load_hlm("红楼梦_全文.txt", 300)
    for s in sents:
        qseed.learn_sentence(list(s))
    show("词典型种子 + 读红楼300句(先天+后天演化)", qseed, words)

if __name__ == "__main__":
    main()
