#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_distributional_selforganize.py — 分布语义自组织：从大量阅读自动整理语义类

验证马老师核心设想：**能否通过大量上下文的阅读，自己整理/内建知识库？**

方法（distributional semantics / 共现统计，成熟且与YLYW兼容）：
  1. 读入真实中文语料（corpus.json，8.7万字真实论文文本）
  2. 对每个字统计"同句共现上下文向量"（它在什么语言环境里出现）
  3. 用余弦相似度衡量字与字的语义相近度
  4. 聚类 → 自动浮现语义类（如 量子/计算、学习/知识、物理/性质…）
  5. 与 YLYW 部首八卦对照：检验"语料涌现的语义结构"是否合理、能否作为内生知识库

对照实验：context=同句共现(纯语料涌现) vs context=部首八卦(字形先验)。
"""
import os, json, math, re
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))


def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))


def build_cooccur(corpus, window="sentence"):
    """共现矩阵：字 ↔ 同句内的字（共现次数）。"""
    co = defaultdict(Counter)   # co[ch1][ch2] = 次数
    freq = Counter()
    for sent in corpus:
        chars = list(sent)
        uniq = set(chars)
        for ch in uniq:
            freq[ch] += 1
        for ch in uniq:
            for ch2 in uniq:
                if ch != ch2:
                    co[ch][ch2] += 1
    return co, freq


def context_vector(co, ch, vocab, N=500):
    """ch 的共现上下文向量（对高频字表归一）。"""
    v = [0.0] * N
    for i, c in enumerate(vocab):
        v[i] = co[ch].get(c, 0.0)
    return v


def cosine(a, b):
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0 or db == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (da * db)


def pmi_weight(co, freq, ch, c, corpus_len):
    """PMI 加权共现：降低高频虚字噪声，突出强关联。"""
    n = co[ch].get(c, 0)
    if n == 0:
        return 0.0
    pc = freq[c] / corpus_len
    pcc = n / corpus_len
    # 平滑
    return max(0.0, math.log(pcc / ( (freq[ch]/corpus_len) * pc + 1e-9) ))


def main():
    corpus = load_corpus()
    corpus_len = sum(len(s) for s in corpus)  # 总字次
    co, freq = build_cooccur(corpus)
    # 停用字（虚词/标点/高频功能字）：分布语义中应排除
    STOP = set("。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \\n \\t \\u3000") | set(
        "的了在是一和不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已")
    # 高频字表作为上下文维度
    vocab = [c for c, _ in freq.most_common(400) if c not in STOP]
    targets = [c for c, f in freq.most_common(160) if f >= 8 and c not in STOP]

    def pmi_vec(ch):
        return [pmi_weight(co, freq, ch, c, corpus_len) for c in vocab]

    vecs = {ch: pmi_vec(ch) for ch in targets}

    print("=== 分布语义自组织：共现→语义相近字 (已排除虚词/停用字) ===")
    print(f"语料: {len(corpus)}句, {corpus_len}字次, 上下文表{len(vocab)}, 目标实义字{len(targets)}")
    # 找语义群：对每个目标字列最相近的5个
    probe = [c for c in targets if freq[c] >= 15][:16]
    for ch in probe:
        sims = [(c2, cosine(vecs[ch], vecs[c2])) for c2 in targets if c2 != ch]
        sims.sort(key=lambda x: -x[1])
        top = [(c2, round(s, 2)) for c2, s in sims[:5] if s > 0]
        print(f"  {ch}: " + "  ".join(f"{c2}({s})" for c2, s in top))


if __name__ == "__main__":
    main()
