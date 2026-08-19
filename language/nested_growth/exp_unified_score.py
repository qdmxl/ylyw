#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_unified_score.py — 方案A：真·统一双通道评分

把"字形×语料"合成一个元胞对一个语义类的单一分数：
    score[c] = λ·G(字形六爻→c) + (1-λ)·ctxsim(语料指纹→c) + bias[c]
    class = argmax_c score[c]

用多主题语料（6个已知语义类）作为 ground-truth，测统一评分的准确率，
并对比：
  [纯语料] 只有 ctxsim
  [统一λ=0.5] 字形先验投影 + 语料证据 + bias校准
  [新词冷启动] 语料未见的新字/词，字形结构+继承bias能否补足

G：可学习共享映射 (8维六爻 -> C维语义类分数) —— 先天结构先验
ctxsim：语料指纹与类质心的余弦相似度 —— 后天语义证据
bias：知几校准向量 —— 经验修正
"""
import os, json, math, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
FUNC = set("的了在是一和不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \\n")


def load_multitopic():
    from build_multitopic_corpus import TOPICS
    corpus = json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))
    class_names = list(TOPICS.keys())
    class_of = {}
    for ci, (t, words) in enumerate(TOPICS.items()):
        for w in words:
            for ch in w:
                class_of[ch] = ci
    return corpus, class_names, class_of


def build_pmi(corpus, maxvocab=250):
    co = defaultdict(Counter); freq = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1
    L = sum(len(s) for s in corpus) or 1
    vocab = [c for c, _ in freq.most_common(300) if c not in FUNC][:maxvocab]
    def pmiv(ch):
        v = [0.0]*len(vocab)
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9)))
        return v
    return pmiv, vocab, freq


def cos(a, b):
    da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
    return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)


def learn_classifier(train_chars, class_of, vec, centroids, C, n_yao=8, lr=0.02, epochs=20):
    """学习字形六爻 -> 语义类的共享映射 G(C x n_yao) 和 通道权重 lambda.
    感知机式：G[true] += lr·yao, G[pred] -= lr·yao；对每个训练字。
    返回 G, lam(通道权重), bias_per_char."""
    import numpy as np
    G = np.zeros((C, n_yao))
    lam = 0.5
    bias = {}
    for _ in range(epochs):
        for ch in train_chars:
            lab = class_of[ch]
            yao = np.array(get_yao(ch))          # 8维字形六爻
            ctx = np.array(vec[ch])              # 语料指纹
            ctxsim = np.array([cos(ctx, centroids[c]) for c in range(C)])
            shape = G.dot(yao)                   # C维
            score = lam*shape + (1-lam)*ctxsim + np.array(bias.get(ch, [0.0]*C))
            pred = int(np.argmax(score))
            if pred != lab:
                G[lab] += lr*yao
                G[pred] -= lr*yao
                b = bias.get(ch, [0.0]*C)
                b[lab] += 0.3*lr
                b[pred] -= 0.3*lr
                bias[ch] = b
    return G, lam, bias


def predict(ch, G, lam, vec, centroids, C, bias=None):
    import numpy as np
    yao = np.array(get_yao(ch))
    ctx = np.array(vec[ch])
    ctxsim = np.array([cos(ctx, centroids[c]) for c in range(C)])
    shape = G.dot(yao)
    b = np.array(bias.get(ch, [0.0]*C)) if bias else np.zeros(C)
    score = lam*shape + (1-lam)*ctxsim + b
    return int(np.argmax(score))


def get_yao(ch):
    try:
        from exp_growth import char_sem_vec
        y = char_sem_vec(ch)
        if any(abs(x-0.5) > 0.12 for x in y):
            return y
    except Exception:
        pass
    return [0.5]*8


def main():
    import numpy as np
    corpus, class_names, class_of = load_multitopic()
    C = len(class_names)
    pmiv, vocab, freq = build_pmi(corpus)
    chars = [c for c, ci in class_of.items() if freq.get(c, 0) >= 8]
    vec = {ch: pmiv(ch) for ch in chars}
    # 类质心（语料指纹）
    centroids = {}
    for ci in range(C):
        ms = [ch for ch in chars if class_of[ch] == ci]
        v = np.zeros(len(vocab))
        for m in ms:
            v += np.array(vec[m])
        v /= max(1, len(ms))
        centroids[ci] = v

    # 训练/测试切分
    rnd = random.Random(0)
    rnd.shuffle(chars)
    cut = int(len(chars)*0.7)
    train, test = chars[:cut], chars[cut:]

    G, lam, bias = learn_classifier(train, class_of, vec, centroids, C)

    # [纯语料] 只 ctxsim
    def pure_ctx(ch):
        return int(np.argmax([cos(vec[ch], centroids[c]) for c in range(C)]))
    acc_ctx = sum(1 for ch in test if pure_ctx(ch) == class_of[ch])/len(test)

    # [统一] G+ctxsim+bias
    acc_unif = sum(1 for ch in test if predict(ch, G, lam, vec, centroids, C, bias) == class_of[ch])/len(test)

    print("=== 方案A：真·统一双通道评分 ===\n")
    print(f"语义类数 C={C}, 训练字{len(train)}, 测试字{len(test)}")
    print(f"[纯语料] (仅语料指纹):      {acc_ctx*100:.1f}%")
    print(f"[统一] (字形G + 语料 + bias): {acc_unif*100:.1f}%")

    # 新词冷启动：训练没见过的字
    unseen = [c for c in test if c not in train]
    print(f"冷启动测试(训练未见字): {len(unseen)}个, "
          f"统一评分准确率 {sum(1 for c in unseen if predict(c, G, lam, vec, centroids, C, bias)==class_of[c])/max(1,len(unseen))*100:.1f}%")
    # bias热启动对照：把train的bias传给同部首未见字(继承≈bias共享)
    print(f"  (对照:同一G但无bias, 冷启动) "
          f"{sum(1 for c in unseen if predict(c, G, lam, vec, centroids, C, None)==class_of[c])/max(1,len(unseen))*100:.1f}%")


if __name__ == "__main__":
    main()
