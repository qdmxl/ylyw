#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_sentence_theme.py — 《黄帝内经》句级【主题】自组织验证

YLYW 字→词→句 嵌套：句 = 词元胞的组合，句的语义主题从组成词的共现中涌现。
检验：句向量(句内词共现指纹聚合)能否识别"这句在讲什么主题"。
主题标签 = 句内主题实义字符计票(≥2票);测主题句 类内 vs 类间 margin。
"""
import os, json, math, random, re
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
TOPIC_CHARS = {"肝":"肝肾","肾":"肝肾","心":"心肺","肺":"心肺","脾":"脾胃","胃":"脾胃",
               "气":"气血","血":"气血","经":"经络","络":"经络","脉":"经络","津":"津液","液":"津液",
               "春":"四时","夏":"四时","秋":"四时","冬":"四时"}
CORPUS = os.path.join(HERE, "corpus_neijing_wenyan.json")

def load_corpus():
    return json.load(open(CORPUS, encoding="utf-8"))

def main():
    nel = load_corpus()
    big = Counter()
    for s in nel:
        cs = [c for c in s if c not in FUNC]
        for i in range(len(cs)-1):
            w = cs[i]+cs[i+1]
            if len(set(w)) == 2: big[w] += 1
    words = [w for w, c in big.most_common(1200) if c >= 10]
    token_list = set(words)
    print("="*70)
    print("《黄帝内经》句级【主题】自组织验证 (%d句)  词元胞:%d" % (len(nel), len(words)))
    print("="*70)

    def tokenize(s):
        cs = [c for c in s if c not in FUNC]; out=[]; i=0
        while i < len(cs):
            if i < len(cs)-1 and cs[i]+cs[i+1] in token_list:
                out.append(cs[i]+cs[i+1]); i += 2
            else:
                out.append(cs[i]); i += 1
        return out if out else cs

    co = defaultdict(Counter); wfreq = Counter()
    for s in nel:
        for t in set(tokenize(s)):
            wfreq[t] += 1
            for t2 in set(tokenize(s)):
                if t != t2: co[t][t2] += 1
    real = [w for w, _ in wfreq.most_common(300) if wfreq[w] >= 8]
    rset = set(real); idx = {w: i for i, w in enumerate(real)}
    def wvec(w):
        v = [0.0]*len(real)
        if w not in co: return v
        for w2, n in co[w].items():
            if w2 in idx: v[idx[w2]] = math.log(1+n)
        return v
    cache = {}
    def sv(s):
        v = [0.0]*len(real)
        for t in tokenize(s):
            if t in rset:
                tv = cache.setdefault(t, wvec(t))
                for k in range(len(v)): v[k] += tv[k]
        n = math.sqrt(sum(x*x for x in v)) or 1
        return [x/n for x in v]
    def cos(a, b): return sum(x*y for x, y in zip(a, b))
    def mean(xs): return sum(xs)/len(xs) if xs else 0.0

    topic_sents = defaultdict(list)
    for s in nel:
        cnt = defaultdict(int)
        for t in set(tokenize(s)):
            for ch in t:
                if ch in TOPIC_CHARS: cnt[TOPIC_CHARS[ch]] += 1
        dom = [c for c, n in cnt.items() if n >= 2]
        if len(dom) == 1:
            topic_sents[dom[0]].append(s)
    rnd = random.Random(1)
    print("\n各主题句数:", ", ".join(f"{t}:{len(ss)}" for t, ss in topic_sents.items()))
    cats = [t for t in topic_sents if len(topic_sents[t]) >= 80]
    sample = {t: rnd.sample(topic_sents[t], min(400, len(topic_sents[t]))) for t in cats}
    vecs = {t: [sv(x) for x in sample[t]] for t in cats}

    print("\n【句级主题 类内 vs 类间 margin】")
    print(f"{'主题':<8}{'样本':>5}{'类内':>9}{'类间':>10}{'margin':>10} 判定")
    print("-"*56)
    for t in cats:
        inner = [cos(vecs[t][i], vecs[t][j]) for i in range(len(vecs[t])) for j in range(i+1, len(vecs[t]))]
        others = [x for tt in cats if tt != t for x in vecs[tt]]
        outer = [cos(a, b) for a in vecs[t] for b in others[:300]]
        mi, mo = mean(inner), mean(outer); mg = mi-mo
        verd = "★★★ 强" if mg > 0.02 else("★★ 显著" if mg > 0.01 else("★ 弱" if mg > 0.004 else "· 未分离"))
        print(f"{t:<8}{len(vecs[t]):>5}{mi:>9.4f}{mo:>10.4f}{mg:>+10.4f} {verd}")

    print("\n【主题句示例】")
    for t in cats[:5]:
        print(f"\n  · {t}:")
        for s in rnd.sample(topic_sents[t], min(2, len(topic_sents[t]))):
            print(f"     「{s[:50]}」")

if __name__ == "__main__":
    main()
