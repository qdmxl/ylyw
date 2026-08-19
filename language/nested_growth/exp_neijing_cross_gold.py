#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_cross_gold.py — 测试4：跨典籍泛化（内经→金匮要略）

《金匮要略》(张仲景杂病)与《内经》同为"脏腑辨证"体系, 但篇章/表述全异。
用《内经》训练的脏腑语义指纹, 零样本识别金匮各篇条文讲的是哪个脏腑的病证。

金标准 = 金匮篇目自带的脏腑归属(篇名即标签):
  肺痿肺痈篇→肺, 胸痹心痛篇→心, 腹满寒疝篇→脾/中焦,
  水气/黄疸→肝肾, 痰饮/咳嗽→肺脾(仅用有明确单脏标签的篇)

对照：随机基线(top1 from 11脏腑≈1/11≈9%)。
"""
import os, json, math, re, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")
ZANG = "心肝脾肺肾胃胆膀胱小肠大肠三焦"

# 金匮篇的脏腑标准（篇名即金标准; 只取单脏明确篇）
GOLD_CHAPTERS = [
    ("肺痿肺痈", "肺"),
    ("胸痹心痛", "心"),
    ("腹满寒疝", "脾"),
    ("黄疸", "肝"),
    ("水气", "肾"),
]

def load_corpus(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def build_pmi(corpus, maxvocab=320):
    co=defaultdict(Counter); freq=Counter(); docf=Counter()
    for s in corpus:
        u=set(s)
        for ch in u:
            if ch in FUNC: continue
            freq[ch]+=1
            for ch2 in u:
                if ch2 in FUNC: continue
                if ch!=ch2: co[ch][ch2]+=1; docf[ch2]+=1
    L=sum(len(s) for s in corpus) or 1
    vocab=[c for c,_ in freq.most_common(600) if c not in FUNC][:maxvocab]
    idf={c:max(1.0,math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v=[0.0]*len(vocab); fch=freq[ch]
        for i,c in enumerate(vocab):
            p=co[ch].get(c,0)
            if p: v[i]=max(0.0,math.log((p/L)/((fch/L)*(freq[c]/L)+1e-9)))*idf[c]
        return v
    return pmiv, vocab

def cos(a,b):
    da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
    return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)

def parse_jinkui():
    t=open(os.path.join(HERE,"金匮要略_原文.txt"),encoding="utf-8",errors="ignore").read()
    t=re.sub(r'<[^>]+>','',t)
    t='\n'.join(l.strip() for l in t.split('\n') if l.strip() and not re.match(r'^(书名|作者|朝代|年份)',l.strip()) and l.strip()!='目录')
    t=re.sub(r'属性：?','',t); t=re.sub(r'\s+','',t); t=t.replace('∶','：')
    # 按篇名切分: 篇名 = 病脉证治 或 病证治
    # 用章节标记切
    chaps={}
    for title, z in GOLD_CHAPTERS:
        # 找该篇起止
        start=t.find(title)
        if start<0: continue
        # 下一篇起点
        candidates=[(ch,t.find(ch)) for ch,_ in GOLD_CHAPTERS if t.find(ch)>start]
        nxt=min([p for _,p in candidates if p>start], default=len(t))
        seg=t[start:nxt]
        chaps[title]=seg
    return chaps

def main():
    neijing=load_corpus("corpus_neijing_wenyan.json")
    pmiv, vocab = build_pmi(neijing)
    chaps = parse_jinkui()
    cache={}
    print("="*74)
    print("测试4B：跨典籍泛化（《黄帝内经》→《金匮要略》脏腑辨证）")
    print("="*74)

    # 关键词匹配的朴素基线: 判句向量最近脏腑
    def chapter_predict(seg):
        # 逐条条文判top1脏腑
        items=[x for x in re.split(r'(?<=\d)．|(?<=\d)\.', seg) if len(x)>15]
        votes=defaultdict(float)
        for it in items:
            v=[0.0]*len(vocab); used=0
            for ch in set(it):
                if ch in FUNC: continue
                if ch not in cache:
                    cache[ch]=pmiv(ch)
                tv=cache[ch]
                if any(tv):
                    for k in range(len(v)): v[k]+=tv[k]; used+=1
            if not used: continue
            n=math.sqrt(sum(x*x for x in v)) or 1
            vs=[x/n for x in v]
            sims={z:cos(vs,pmiv(z)) for z in ZANG}
            best=max(sims, key=lambda z:sims[z])
            votes[best]+=1
        return votes

    rnd=random.Random(0)
    print(f"{'金匮篇':<14}{'金标准':<6}{'引擎top1':<8}{'命中':<6}  判定详情(top3)")
    t1=0; total=0
    results=[]
    for title, truth in GOLD_CHAPTERS:
        seg=chaps.get(title)
        if not seg: continue
        votes=chapter_predict(seg)
        top=sorted(votes.items(), key=lambda kv:-kv[1])[:3]
        best=top[0][0] if top else '?'
        hit = best==truth
        if hit: t1+=1
        total+=1
        detail="  ".join(f"{z}:{ct}" for z,ct in top)
        print(f"{title:<14}{truth:<6}{best:<8}{'✓' if hit else '✗':<6}  {detail}")
        results.append((title,truth,best,hit))
    print(f"\n  → 跨典籍top1命中: {t1}/{total}")

    # 随机基线
    r_hit=sum(1 for _,_,_,h in results if False)
    print(f"  随机基线 ≈ 1/11 ≈ 9%")

if __name__=="__main__":
    main()
