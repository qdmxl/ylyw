#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_unified_sparse.py — 方案A：半冷启动（语料极稀疏）时统一机制的价值
真实场景：新字刚进入语料，只出现过1~2次，语料指纹很稀、不可靠。
此时字形通道的'范畴毛估' + 稀疏语料能否优于'纯稀疏语料'？
   统一 score[c] = λ·G(字形->c) + (1-λ)·ctxsim(稀疏指纹->c)
"""
import os, json, math, random
from collections import defaultdict, Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
from exp_unified_score import build_pmi, cos, get_yao, FUNC


def main():
    from build_multitopic_corpus import TOPICS
    full = json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))
    class_names = list(TOPICS.keys()); C = len(class_names)
    class_of = {}
    for ci, (t, words) in enumerate(TOPICS.items()):
        for w in words:
            for ch in w:
                class_of[ch] = ci

    # 训练语料 = 80% 的句子；另20%作为"冷启动句"：只让部分字在其中少量出现
    rnd = random.Random(0)
    rnd.shuffle(full)
    cut = int(len(full)*0.8)
    train_corpus = full[:cut]

    # 用全部语料建PMI（学习阶段看全部），但模拟：测试字只在新句子低频出现
    pmiv, vocab, freq = build_pmi(train_corpus)
    chars = [c for c, ci in class_of.items() if freq.get(c, 0) >= 8]
    vec = {ch: pmiv(ch) for ch in chars}
    centroids = {}
    for ci in range(C):
        ms = [ch for ch in chars if class_of[ch] == ci]
        v = np.zeros(len(vocab))
        for m in ms:
            v += np.array(vec[m])
        v /= max(1, len(ms))
        centroids[ci] = v

    # 学共享字形G
    G = np.zeros((C, 8)); lr = 0.05
    for _ in range(25):
        for ch in chars:
            lab = class_of[ch]
            yao = np.array(get_yao(ch))
            ctxv = np.array(vec[ch])
            ctxsim = np.array([cos(ctxv, centroids[c]) for c in range(C)])
            score = 0.5*G.dot(yao) + 0.5*ctxsim
            pred = int(np.argmax(score))
            if pred != lab:
                G[lab] += lr*yao; G[pred] -= lr*yao

    # 模拟稀疏指纹：只用 1~3 次共现构造 ctx（真实中刚见到）
    def sparse_ctx(ch, n_occ):
        # 从全语料取 ch 出现的句子，仅取 n_occ 句构建PMI（稀疏）
        occur = [s for s in full if ch in s]
        if not occur:
            return None
        sub = occur[:n_occ]
        pmiv2, vocab2, _ = build_pmi(sub)
        return pmiv2(ch) if ch in vocab2 or True else None

    print("=== 方案A：半冷启动（语料极稀疏）时统一机制的价值 ===\n")
    # 选语料中出现频次中的字做测试（模拟"刚进入"）
    test_chars = [c for c in class_of if 3 <= freq.get(c, 0) <= 40]
    print(f"稀疏测试字 {len(test_chars)} 个（语料中低频出现）\n")
    tr = [30, 12, 5, 2, 1]
    print(f"{'稀疏共现数':>8} | {'[纯稀疏语料]':>14} | {'[统一G+稀疏]':>14} | {'[统一增益]':>10}")
    for n_occ in tr:
        ok_p = ok_u = tot = 0
        for ch in test_chars:
            if all(abs(x-0.5) <= 0.12 for x in get_yao(ch)):
                continue
            true = class_of[ch]
            sctx = sparse_ctx(ch, n_occ)
            if sctx is None:
                continue
            yao = np.array(get_yao(ch))
            # 纯稀疏语料
            pred_p = int(np.argmax([cos(np.array(sctx), centroids[c]) for c in range(C)]))
            if pred_p == true: ok_p += 1
            # 统一（字形G + 稀疏语料）
            cs = np.array([cos(np.array(sctx), centroids[c]) for c in range(C)])
            score = 0.5*G.dot(yao) + 0.5*cs
            pred_u = int(np.argmax(score))
            if pred_u == true: ok_u += 1
            tot += 1
        if tot:
            pc, uc = ok_p/tot*100, ok_u/tot*100
            print(f"{n_occ:>8} | {pc:>13.1f}% | {uc:>13.1f}% | {uc-pc:>+9.1f}pt")


if __name__ == "__main__":
    main()
