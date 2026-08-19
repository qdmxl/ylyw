#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_l2_shared_w.py — L2 会意字字义归类：共享可学习映射能否泛化？

验证马老师核心问题：统一机制(L2)能否实现真实语义理解？
  逐字 bias 只能记忆见过的字（无法泛化，已验证提升=0）。
  改为**共享可学习映射 W(8,8)**: score[cat] = W[cat]·yao, argmax 判范畴。
  共享权重对"未见字"也生效 → 应能泛化(先天37% → 学习后上升?)。

若成立：证明"六爻→字义范畴"存在可学习的泛化规则，即 L2 语义理解可用统一机制。
始终诚实：标签=知识库bagua_map主卦；学习用有部首先验的字；测试含未见字。
"""
import os, sys, json, random
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
from exp_growth import char_sem_vec, BAGUA_NAMES, BAGUA_IDX


def load():
    kb = json.load(open(os.path.join(HERE, "..", "ideograph_knowledge_base.json"),
                        encoding="utf-8"))
    items = []
    for ch, info in kb.items():
        bm = info.get("bagua_map", "")
        if not bm or bm[0] not in BAGUA_IDX:
            continue
        vec = char_sem_vec(ch)
        if not any(abs(x - 0.5) > 0.12 for x in vec):
            continue  # 只保留有部首先验的字（先天有信号）
        items.append({"char": ch, "label": BAGUA_IDX[bm[0]], "yao": vec})
    return items


def predict_all(W, items):
    ok = 0
    for it in items:
        y = it["yao"]; scores = [sum(W[c][k] * y[k] for k in range(8)) for c in range(8)]
        pred = max(range(8), key=lambda c: scores[c])
        ok += (pred == it["label"])
    return ok / max(1, len(items))


def run(learn_on, seed):
    rnd = random.Random(seed)
    items = load()
    rnd.shuffle(items)
    cut = int(len(items) * 0.7)
    train, test = items[:cut], items[cut:]
    # W[cat][k]: 六爻第k维 → 类别cat 的权重。init=恒等(≈argmax)
    W = [[0.9 if c == k else 0.45 for k in range(8)] for c in range(8)]
    lr = 0.02 if learn_on else 0.0
    for epoch in range(8):
        for it in train:
            y = it["yao"]; lab = it["label"]
            scores = [sum(W[c][k] * y[k] for k in range(8)) for c in range(8)]
            pred = max(range(8), key=lambda c: scores[c])
            if pred == lab:
                continue
            # 梯度：正确类升、错误类降（感知机式）
            for k in range(8):
                W[lab][k] += lr * y[k]
                W[pred][k] -= lr * y[k]
    a_train = predict_all(W, train)
    a_test = predict_all(W, test)
    return {"learn_on": learn_on, "seed": seed, "acc_train": a_train, "acc_test": a_test,
            "n_train": len(train), "n_test": len(test)}


if __name__ == "__main__":
    print("=== L2 会意字字义归类：共享可学习映射W(8x8) 泛化探测 ===\n")
    print("--- 静态 (W=恒等, 不学习) ---")
    ro = run(learn_on=False, seed=0)
    print(f"train先天: {ro['acc_train']*100:.1f}%   test先天: {ro['acc_test']*100:.1f}%  n_test={ro['n_test']}")
    print("\n--- 学习W (感知机式, 共享→可泛化) ---")
    rl = run(learn_on=True, seed=0)
    print(f"train: {rl['acc_train']*100:.1f}%   test(main含未见字): {rl['acc_test']*100:.1f}%")
    print(f"\ntest提升: {(rl['acc_test']-ro['acc_test'])*100:+.1f}pt")

    # 多seed稳健
    print("\n--- 多seed稳健性 (seed 0-4) ---")
    static=[]; learn=[]
    for s in range(5):
        r1=run(False,s); r2=run(True,s)
        static.append(r1['acc_test']); learn.append(r2['acc_test'])
    print(f" static test: {[round(x,2) for x in static]} mean={sum(static)/5:.3f}")
    print(f" learn  test: {[round(x,2) for x in learn]} mean={sum(learn)/5:.3f}")
    print(f" 平均提升: +{(sum(learn)-sum(static))/5*100:.1f}pt")
