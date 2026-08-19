#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_sentence_level.py — 《黄帝内经》句级自组织验证

嵌套增长推进到"句"层(字→词→句, YLYW递归)。检验引擎能否从内经原文学出
【句法功能类别】并可自组织分离:
  定义句(……者，……也)  因果句(……则/故/是以……)  问答句(帝曰…?/问于)

机制: 句向量 = 句内实义词(双字词元胞)的共现指纹聚合;测三类句子 类内>类间。
"""
import os, json, math, random, re
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")

def load_corpus(name="corpus_neijing_wenyan.json"):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def collect_bigrams(corpus, min_freq=10, max_words=1200):
    big = Counter()
    for s in corpus:
        cs=[c for c in s if c not in FUNC]
        for i in range(len(cs)-1):
            w=cs[i]+cs[i+1]
            if len(set(w))==2: big[w]+=1
    return [w for w,c in big.most_common(max_words) if c>=min_freq]

def main():
    corpus = load_corpus()
    words = collect_bigrams(corpus)
    token_list = set(words)
    print("="*70)
    print("《黄帝内经》句级自组织验证 (%d句)  词元胞:%d" % (len(corpus), len(words)))
    print("="*70)

    # ---- 实义词的语料共现指纹 ----
    co=defaultdict(Counter); wfreq=Counter()
    def tokenize(s):
        cs=[c for c in s if c not in FUNC]
        out=[]; i=0
        while i<len(cs):
            if i<len(cs)-1 and cs[i]+cs[i+1] in token_list:
                out.append(cs[i]+cs[i+1]); i+=2
            else:
                out.append(cs[i]); i+=1
        return out if out else cs
    for s in corpus:
        toks=tokenize(s)
        u=set(toks)
        for t in u:
            wfreq[t]+=1
            for t2 in u:
                if t!=t2: co[t][t2]+=1
    real_tokens=[w for w,_ in wfreq.most_common(400) if wfreq[w]>=8]
    idx={w:i for i,w in enumerate(real_tokens)}
    rset=set(real_tokens)
    def wvec(w):
        v=[0.0]*len(real_tokens)
        if w not in co: return v
        for w2,n in co[w].items():
            if w2 in idx: v[idx[w2]]=math.log(1+n)
        return v
    cache={}
    def getvec(w):
        if w not in cache: cache[w]=wvec(w)
        return cache[w]
    def svec(s):
        toks=tokenize(s)
        v=[0.0]*len(real_tokens)
        for t in toks:
            if t in rset:
                tv=getvec(t)
                for k in range(len(v)): v[k]+=tv[k]
        norm=math.sqrt(sum(x*x for x in v)) or 1
        return [x/norm for x in v]
    def cos(a,b): return sum(x*y for x,y in zip(a,b))
    def mean(xs): return sum(xs)/len(xs) if xs else 0.0

    # ---- 句式分类：更严格/干净地采集完整句式 ----
    def tag_of(s):
        # 排除篇目标记残留(含'卷_'/'第..论'),排除残句
        if re.match(r'^(卷|黄帝内经)', s): return ['陈述']
        if len(s) > 80: return ['陈述']  # 长句多为叙述
        tags=[]
        # 定义句：完整"X者,Y也"判定结构，且非问答
        if '者' in s and s.endswith('也'):
            tags.append('定义')
        if re.search(r'[则故]', s) and '帝曰' not in s[:3]:
            tags.append('因果')
        if re.search(r'帝曰[^，。]{0,20}？|帝曰[^，。]{0,20}(邪|乎)|岐伯[曰对][^，。]{0,20}', s) and ('者' not in s or '也' not in s):
            tags.append('问答')
        return tags if tags else ['陈述']
    cat_sents=defaultdict(list)
    for s in corpus:
        for c in tag_of(s):
            cat_sents[c].append(s)
    rnd=random.Random(0)
    # 只保留与其它类重叠少的类（提高纯度和可分离性）
    cats=[c for c in ['定义','因果','问答'] if len(cat_sents[c])>=50]
    sample={c:rnd.sample(cat_sents[c],min(500,len(cat_sents[c]))) for c in cats}
    vecs={c:[svec(s) for s in sample[c]] for c in cats}
    print("\n各句式句数: "+", ".join(f"{c}:{len(cat_sents[c])}" for c in cats))

    print("\n【句级功能类别 类内 vs 类间 margin（句向量=词聚合）】")
    print(f"{'句式':<8}{'样本':>6}{'类内均值':>12}{'类间均值':>13}{'margin':>10} 判定")
    print("-"*62)
    for c in cats:
        inner=[cos(vecs[c][i],vecs[c][j]) for i in range(len(vecs[c])) for j in range(i+1,len(vecs[c]))]
        others=[x for cc in cats if cc!=c for x in vecs[cc]]
        outer=[cos(a,b) for a in vecs[c] for b in others[:300]]
        mi,mo=mean(inner),mean(outer); mg=mi-mo
        verd="★★★ 强" if mg>0.02 else("★★ 显著" if mg>0.01 else("★ 弱" if mg>0.004 else "· 未分离"))
        print(f"{c:<8}{len(vecs[c]):>6}{mi:>12.4f}{mo:>13.4f}{mg:>+10.4f} {verd}")

    print("\n【句式示例】")
    for c in ['定义','因果','问答']:
        if c not in cats: continue
        print(f"\n  · {c}句:")
        for s in rnd.sample(cat_sents[c], min(3,len(cat_sents[c]))):
            print(f"     「{s[:55]}」")

if __name__=="__main__":
    main()
