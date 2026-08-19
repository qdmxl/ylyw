#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_unified_coldstart.py — 方案A加强：真冷启动泛化
统一评分最大的价值 = 语料外新字/新词（从未见过）也能靠字形结构先验泛化落类。

方法：
  1. 用"部分主题词"训练（构造语料只含部分字），学 G(字形六爻->语义类) 和 bias
  2. 测试 = 训练语料中**从未出现的字**（语料外）
  3. 对比：纯语料(对未见字无指纹→失效) vs 统一字形G(可泛化)
  4. 测"嵌套继承"：新双字词 = 两个已知字的组合，词bias继承字bias均值 → 判断词类
"""
import os, json, math, random
from collections import defaultdict, Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
from exp_unified_score import build_pmi, cos, get_yao, FUNC


def make_partial_corpus(holdout_words_total):
    """构造语料：随机把若干主题词整体作为'语料外'(holdout)，语料只含其余词。"""
    from build_multitopic_corpus import TOPICS
    corpus = json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))
    class_names = list(TOPICS.keys())
    class_of = {}
    for ci, (t, words) in enumerate(TOPICS.items()):
        for w in words:
            for ch in w:
                class_of[ch] = ci
    # 随机holdout若干字
    all_chars = list(class_of.keys())
    rnd = random.Random(0)
    rnd.shuffle(all_chars)
    holdout = set(all_chars[:holdout_words_total])
    # 语料过滤掉holdout字
    filtered = [s for s in corpus if not any(c in holdout for c in s)]
    return filtered, class_names, class_of, holdout


def learn_shared(corpus, C):
    """学字形G(共享)。只需要字形六爻+语料类质心。"""
    pmiv, vocab, freq = build_pmi(corpus)
    chars = [c for c, ci in class_of.items() if freq.get(c, 0) >= 6 and c not in holdout]
    vec = {ch: pmiv(ch) for ch in chars}
    centroids = {}
    for ci in range(C):
        ms = [ch for ch in chars if class_of[ch] == ci]
        v = np.zeros(len(vocab))
        for m in ms:
            v += np.array(vec[m])
        v /= max(1, len(ms))
        centroids[ci] = v
    G = np.zeros((C, 8)); lr = 0.05
    for _ in range(25):
        for ch in chars:
            lab = class_of[ch]
            yao = np.array(get_yao(ch))
            ctx = np.array(vec[ch])
            ctxsim = np.array([cos(ctx, centroids[c]) for c in range(C)])
            score = 0.5*G.dot(yao) + 0.5*ctxsim
            pred = int(np.argmax(score))
            if pred != lab:
                G[lab] += lr*yao
                G[pred] -= lr*yao
    return G, centroids, vec, chars


def main():
    global class_of, holdout
    holdout_total = 30
    corpus, class_names, class_of, holdout = make_partial_corpus(holdout_total)
    C = len(class_names)
    print("=== 方案A加强：真冷启动泛化（统一机制的价值）===")
    print(f"语料主题类 {C} 个; holdout(语料外)字 {len(holdout)} 个: {sorted(holdout)}\n")

    G, centroids, vec, chars = learn_shared(corpus, C)

    # 纯语料：未见字根本没指纹 → 只能随猜（或最近邻失败）
    def pure_ctx(ch):
        if ch not in vec:
            return None  # 语料外，无指纹
        return int(np.argmax([cos(vec[ch], centroids[c]) for c in range(C)]))

    # 统一：字形G 可泛化到未见字
    def unified(ch):
        yao = np.array(get_yao(ch))
        return int(np.argmax(G.dot(yao)))

    acc_single = 0; acc_gu = 0; unk_total = 0
    for ch in sorted(holdout):
        if all(abs(x-0.5) <= 0.12 for x in get_yao(ch)):
            continue  # 无字形信息
        true = class_of[ch]
        p = pure_ctx(ch)
        tru = unified(ch)
        unk_total += 1
        if p is not None and p == true:
            acc_single += 1
        if tru == true:
            acc_gu += 1
    if unk_total:
        print(f"[纯语料] 语料外字落类: 有指纹的字 {sum(1 for c in holdout if c in vec)} 个, "
              f"能判对 {acc_single} 个")
        print(f"[统一G]  语料外字靠字形结构泛化: {acc_gu}/{unk_total} = {acc_gu/unk_total*100:.0f}%")

    # 嵌套继承：新双字词 = holdout字 + 已知字，词bias继承
    print("\n--- 嵌套继承：新词由组成部分字判断 ---")
    known = [c for c in class_of if c not in holdout]
    tested = 0; correct = 0
    for wh in sorted(holdout):
        if all(abs(x-0.5) <= 0.12 for x in get_yao(wh)):
            continue
        for wk in known[:5]:
            word = wh + wk
            true = class_of[wh]
            yao = [(get_yao(wh)[k]+get_yao(wk)[k])/2 for k in range(8)]
            pred = int(np.argmax(G.dot(np.array(yao))))
            tested += 1
            correct += (pred == true)
    if tested:
        print(f"新词{(len(holdout))}×5组合: 用组成字六爻均值过G落类, 判对 {correct}/{tested} = {correct/tested*100:.0f}%")


if __name__ == "__main__":
    main()
