#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_ideograph_l2.py — 探测：L2 会意字字义归类能否用"统一嵌套机制"学习

任务：209 个会意字（知识库 ideograph_knowledge_base.json）→ 字义归类卦范畴。
  标签 = 知识库 bagua_map 主卦（e.g. 休→艮止息、仁→乾至善、明→离光明、泉→坎源泉）。
六爻 = 部首八卦隶属度。先天一致率仅 37%（部首卦≠字义卦，需学习补齐）。
判断 = argmax(六爻 + bias)，bias 由知几校准学习。

验证目标：先天 37% → 学习后准确率是否显著上升？
若成立 → 证明统一嵌套自增长机制可承载"字义理解(归类)"，且用真实字。
"""
import os, sys, json, random
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
from exp_growth import char_sem_vec, BAGUA_NAMES, BAGUA_IDX


def load_ideograph():
    kb = json.load(open(os.path.join(HERE, "..", "ideograph_knowledge_base.json"),
                        encoding="utf-8"))
    items = []
    for ch, info in kb.items():
        bm = info.get("bagua_map", "")
        if not bm:
            continue
        g = bm[0]
        if g not in BAGUA_IDX:
            continue
        vec = char_sem_vec(ch)
        items.append({"char": ch, "label": g, "yao": vec,
                      "has_prior": any(abs(x - 0.5) > 0.12 for x in vec)})
    return items


def accuracy(items, biases):
    correct = 0
    for it in items:
        b = biases.get(it["char"]) or [0.0] * 8
        pred = BAGUA_NAMES[max(range(8), key=lambda k: it["yao"][k] + b[k])]
        correct += (pred == it["label"])
    return correct / max(1, len(items))


def run(learn_on, seed):
    rnd = random.Random(seed)
    items = load_ideograph()
    # 只保留有部首先验的字（六爻平坦的字先天无信号，归入"需学习"但仍纳入准确率）
    labeled = [it for it in items]
    rnd.shuffle(labeled)
    cut = int(len(labeled) * 0.7)
    train, test = labeled[:cut], labeled[cut:]
    biases = {}
    lr = 0.5 if learn_on else 0.0

    # 训练
    for it in train:
        if not it["has_prior"]:
            continue  # 平坦字先天无信息，不产生校准信号（避免随机）
        yao, true = it["yao"], it["label"]
        true_i = BAGUA_IDX[true]
        b = biases.get(it["char"]) or [0.0] * 8
        pred_i = max(range(8), key=lambda k: yao[k] + b[k])
        won = (BAGUA_NAMES[pred_i] == true)
        if learn_on:
            if won:
                b[pred_i] += 0.03 * lr
            else:
                b[true_i] += 0.6 * lr
                b[pred_i] -= 0.6 * lr
            biases[it["char"]] = [max(-1.0, min(1.0, x)) for x in b]

    acc_train = accuracy(train, biases)
    acc_test = accuracy(test, biases)
    # 只看"有部首先验"且训练未见过的字（真正的泛化）
    test_prior = [it for it in test if it["has_prior"]]
    acc_test_prior = accuracy(test_prior, biases)
    train_seen = {it["char"] for it in train}
    unseen_prior = [it for it in test_prior if it["char"] not in train_seen]
    acc_unseen = accuracy(unseen_prior, biases)
    return {
        "learn_on": learn_on, "seed": seed,
        "n_train": len(train), "n_test": len(test),
        "acc_train": acc_train, "acc_test": acc_test,
        "acc_test_prior": acc_test_prior,
        "acc_unseen_prior": acc_unseen,
        "n_unseen_prior": len(unseen_prior),
    }


if __name__ == "__main__":
    print("=== L2 会意字字义归类：统一机制可学性探测 ===\n")
    print("--- 静态H (不改bias) ---")
    ro = run(learn_on=False, seed=0)
    print(f"测试准确率(all): {ro['acc_test']*100:.1f}%  (prior池: {ro['acc_test_prior']*100:.1f}%)")
    print(f"未见字泛化(prior): {ro['acc_unseen_prior']*100:.1f}%  (n={ro['n_unseen_prior']})")

    print("\n--- 知几校准H (学习bias) ---")
    rl = run(learn_on=True, seed=0)
    print(f"测试准确率(all): {rl['acc_test']*100:.1f}%  (prior池: {rl['acc_test_prior']*100:.1f}%)")
    print(f"未见字泛化(prior): {rl['acc_unseen_prior']*100:.1f}%  (n={rl['n_unseen_prior']})")
    print(f"\n提升(prior池): +{(rl['acc_test_prior']-ro['acc_test_prior'])*100:.1f}pt")
