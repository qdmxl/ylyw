#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_huangdi_cluster.py — 《黄帝内经》语料自组织：层次聚类→体系涌现检验

不预设任何中医标签，纯从内经语料（PMI共现）对实义字做层次聚类，
然后看自动形成的族，是否天然对应中医体系（五脏/四季/五行/六腑…）。

这是"引擎涌现出与人类一致语义结构"的最干净证据：
若 五脏 各自成族 / 四季一族 / 五行一族，说明"读内经→自动长成中医语义骨架"。
"""
import os, json, math
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后\"『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对说道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目")
FUNC -= set("心肝脾肺肾气血脉骨肉皮毛髓经脉络穴俞脏胃肠胆膀胱")
FUNC |= set("说就都要会怎样哪这和那因为如当使应一些些很更")

CAT = {  # 用于展示的已知中医范畴（仅标注用，不影响聚类）
    "心":"脏","肝":"脏","脾":"脏","肺":"脏","肾":"脏",
    "水":"行","木":"行","金":"行","火":"行","土":"行",
    "春":"季","夏":"季","秋":"季","冬":"季",
    "胃":"腑","肠":"腑","胆":"腑","膀胱":"腑",
    "怒":"志","喜":"志","思":"志","悲":"志","恐":"志",
    "东":"方","南":"方","西":"方","北":"方",
}

def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_huangdi.json"), encoding="utf-8"))

def build(corpus, maxvocab=200, min_freq=6):
    co = defaultdict(Counter); freq = Counter(); docf = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1; docf[ch2] += 1
    L = sum(len(s) for s in corpus) or 1
    vocab = [c for c, _ in freq.most_common(500) if c not in FUNC][:maxvocab]
    idf = {c: max(1.0, math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v = [0.0]*len(vocab)
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9))) * idf[c]
        return v
    targets = [c for c, _ in freq.most_common(400) if c not in FUNC and freq[c] >= min_freq][:200]
    return pmiv, vocab, freq, targets

def cos(a, b):
    da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
    return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)

def main():
    corpus = load_corpus()
    pmiv, vocab, freq, targets = build(corpus)
    vec = {ch: pmiv(ch) for ch in targets}
    chars = list(vec)
    sim = {c: {c2: cos(vec[c], vec[c2]) for c2 in chars} for c in chars}

    # 贪心层次聚类（最大平均相似度合并）
    clusters = [[c] for c in chars]
    def clus_sim(a, b):
        s = 0.0; cnt = 0
        for x in a:
            for y in b:
                s += sim[x][y]; cnt += 1
        return s/max(1, cnt)
    from random import Random
    K = 16
    while len(clusters) > K:
        bi, bj, bs = -1, -1, -1.0
        for i in range(len(clusters)):
            for j in range(i+1, len(clusters)):
                s = clus_sim(clusters[i], clusters[j])
                if s > bs: bi, bj, bs = i, j, s
        newc = clusters[bi] + clusters[bj]
        rest = [clusters[k] for k in range(len(clusters)) if k not in (bi, bj)]
        clusters = rest + [newc]

    print("="*70)
    print(f"《黄帝内经》自组织层次聚类 (240778字, {len(chars)}实义字 → {K}族)")
    print("="*70)
    # 按族大小排，标注每个字的中医范畴
    for ci, cl in enumerate(sorted(clusters, key=len, reverse=True)):
        if not cl: continue
        center = max(cl, key=lambda x: sum(sim[x][y] for y in cl)/max(1, len(cl)-1))
        tags = {}
        for ch in cl:
            if ch in CAT:
                tags.setdefault(CAT[ch], []).append(ch)
        tagstr = "  ".join(f"{k}{sorted(v)}" for k, v in tags.items())
        shown = " ".join(cl[:14]) + (" …" if len(cl) > 14 else "")
        print(f"\n族{ci+1}({len(cl)}字)[{center}]: {shown}")
        if tagstr: print(f"     ↗ 中医范畴成员: {tagstr}")

if __name__ == "__main__":
    main()
