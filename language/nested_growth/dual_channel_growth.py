#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dual_channel_growth.py — 统一双通道嵌套自增长语义理解系统（方案甲，干净版）

把三条线融成一个引擎：
  1) 字形先验通道 (先天)：部首八卦六爻 —— 自然范畴先验
  2) 语料涌现通道 (后天)：PMI 共现指纹 —— 从大量阅读自组织出语义类/知识库
  3) 嵌套自增长 + 知几校准：元胞随阅读繁殖、词嵌套承字、bias 校准语义判别

端到端演示（读得越多 → 系统越复杂 → 语义理解越巩固，三类指标单调上升）：
  G1 覆盖面：认识的不同字符数           ↑
  G2 复杂度：繁殖出的词元胞数           ↑
  G3 语义收敛：语料增量下语义类稳定率   ↑  ← 语义世界随阅读定形（理解巩固）
"""
import os, json, math, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在是一和不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过"
           "把被上下由因此也它但很都外内较实指已本及个别要" 
           "。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \\n")


def load_corpus(frac=1.0, seed=0):
    corpus = json.load(open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
    if frac < 1.0:
        rnd = random.Random(seed)
        corpus = rnd.sample(corpus, int(len(corpus)*frac))
    return corpus


def build_pmi(corpus, maxvocab=300):
    co = defaultdict(Counter); freq = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1
    L = sum(len(s) for s in corpus) or 1
    vocab = [c for c, _ in freq.most_common(400) if c not in FUNC][:maxvocab]
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


class SemanticCell:
    __slots__ = ("text", "kind", "yao", "ctx", "bias", "label", "children", "strength")
    def __init__(self, text, kind, yao=None, ctx=None, bias=None, label=None, children=None):
        self.text = text
        self.kind = kind
        self.yao = yao if yao is not None else [0.5]*8
        self.ctx = ctx if ctx is not None else []
        self.bias = bias if bias is not None else [0.0]*8
        self.label = label
        self.children = children or []
        self.strength = 1.0

    def pred_gua(self):
        s = [self.yao[k] + self.bias[k] for k in range(8)]
        return max(range(8), key=lambda k: s[k])


def run_growth(corpus_fracs, seed=0):
    """按语料比例增量阅读，输出每个阶段的成长指标。"""
    corpus = load_corpus(1.0, seed)
    results = []
    for frac in corpus_fracs:
        sub = corpus[:int(len(corpus)*frac)]
        pmiv, vocab, freq = build_pmi(sub)
        seen_chars = set()
        words = set()
        char_cells = {}
        word_cells = {}
        n_class_stable = 0
        # 语义类（粗聚类）——用 k-means 简化：按字形卦聚类做"先天语义类"
        # 实际用 语料PMI 在高维上直接做"字词所属类"，这里演示用 字形主导卦 作为结构锚
        for sent in sub:
            for ch in set(sent):
                if ch in FUNC:
                    continue
                seen_chars.add(ch)
                if ch not in char_cells:
                    yao = [0.5]*8; ctx = []
                    try:
                        from exp_growth import char_sem_vec
                        y = char_sem_vec(ch)
                        if any(abs(x-0.5) > 0.12 for x in y):
                            yao = y
                        ctx = pmiv(ch)
                    except Exception:
                        pass
                    char_cells[ch] = SemanticCell(ch, 'char', yao=yao, ctx=ctx, label=ch)
            chars = [c for c in sent if c not in FUNC]
            for i in range(len(chars)-1):
                w = chars[i]+chars[i+1]
                c1, c2 = char_cells.get(chars[i]), char_cells.get(chars[i+1])
                if c1 and c2 and w not in word_cells:
                    yao = [(c1.yao[k]+c2.yao[k])/2 for k in range(8)]
                    bias = [(c1.bias[k]+c2.bias[k])/2 for k in range(8)]
                    word_cells[w] = SemanticCell(w, 'word', yao=yao, ctx=pmiv(w), bias=bias,
                                                 children=[chars[i], chars[i+1]])
        # 指标
        results.append({
            'frac': frac, 'n_sent': len(sub),
            'G1_chars': len(seen_chars),
            'G2_word_cells': len(word_cells),
            'G2_char_cells': len(char_cells),
            'G2_total_cells': len(char_cells)+len(word_cells),
        })
    return results


if __name__ == "__main__":
    fracs = [0.05, 0.1, 0.2, 0.4, 0.7, 1.0]
    print("=== 双通道嵌套自增长语义系统：真实语料增量阅读成长 ===\n")
    res = run_growth(fracs)
    print(f"{'阅读句数':>8} {'认识字符':>8} {'字元胞':>8} {'词元胞(嵌套)':>10} {'总元胞':>8}")
    for r in res:
        print(f"{r['n_sent']:>8} {r['G1_chars']:>8} {r['G2_char_cells']:>8} "
              f"{r['G2_word_cells']:>10} {r['G2_total_cells']:>8}")


# ---------- G3：语义收敛 / 理解巩固 ----------
def run_convergence(seed=0):
    """语料增量分 6 段顺序阅读; 每段后对'已认识的实义字'重新自组织语义类;
    测相邻阶段语义类划分的一致率 —— 随阅读量, 语义划分逐渐稳定(收敛)。
    一致率↑ = 系统对语义世界的认识逐渐定形(理解巩固)。"""
    corpus = load_corpus(1.0, seed)
    stages = [0.05, 0.12, 0.25, 0.5, 0.75, 1.0]
    prev_assign = None
    rows = []
    for frac in stages:
        sub = corpus[:int(len(corpus)*frac)]
        pmiv, vocab, freq = build_pmi(sub, maxvocab=250)
        targets = [c for c, f in freq.most_common(200) if f >= 6 and c not in FUNC]
        vec = {ch: pmiv(ch) for ch in targets}
        # 用字形主导卦作初始种子 + kmeans 迭代，得到当前阶段语义分簇
        seeds = []
        from exp_growth import char_sem_vec
        for ch in targets:
            y = char_sem_vec(ch)
            if any(abs(x-0.5) > 0.12 for x in y):
                dom = max(range(8), key=lambda k: y[k])
                seeds.append((ch, dom))
        if len(set(d for _, d in seeds)) < 2:
            rows.append({'frac': frac, 'n': len(targets), 'stable': None})
            prev_assign = dict(enumerate(targets))
            continue
        # 按字形主导卦分8簇初始化质心
        cents = {}
        for g in range(8):
            ms = [ch for ch, gg in seeds if gg == g]
            if ms:
                d = len(vocab)
                c = [0.0]*d
                for m in ms:
                    vm = vec[m]
                    for k in range(d): c[k] += vm[k]/len(ms)
                cents[g] = c
        cents = {g: cents[g] for g in range(8) if g in cents}
        assign = {}
        for _ in range(10):
            for ch in targets:
                if cents:
                    assign[ch] = max(cents, key=lambda g: cos(vec[ch], cents[g]))
            for g in cents:
                ms = [ch for ch in targets if assign.get(ch) == g]
                if ms:
                    d = len(vocab)
                    c = [0.0]*d
                    for m in ms:
                        vm = vec[m]
                        for k in range(d): c[k] += vm[k]/len(ms)
                    cents[g] = c
        # 稳定率：与上一阶段共享字的 分簇一致率(用最近邻质心对齐后的ARI简单版)
        stable = None
        if prev_assign is not None:
            shared = [c for c in assign if c in prev_assign]
            if shared:
                # 对齐：找一个映射使共享字分类最一致（用重心）
                agree = 0
                for c in shared:
                    # 上一阶段c属于prev_c, 本阶段g; 判断"本阶段g下的邻居"是否同prev_c
                    g0 = assign[c]
                    same_prev = [x for x in shared if prev_assign[x] == prev_assign[c]]
                    same_now = [x for x in shared if assign[x] == g0]
                    inter = len(set(same_prev) & set(same_now))
                    union = len(set(same_prev) | set(same_now)) or 1
                    agree += inter / union
                stable = agree / max(1, len(shared))
        rows.append({'frac': frac, 'n': len(targets), 'stable': round(stable, 3) if stable is not None else None})
        prev_assign = assign
    return rows
