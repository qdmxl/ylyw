#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_suwen_margin.py — 《素问》文言原文 体系涌现显著性量化（可改语料/标题）"""
import os, json, math
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)
CORPUS = os.path.join(HERE, "corpus_suwen_wenyan.json")
LABEL = "《黄帝内经·素问》文言原文(王冰注,81篇) 体系涌现"
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后\"『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对说道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目")
FUNC -= set("心肝脾肺肾气血脉骨肉皮毛髓经脉络穴俞脏胃肠胆膀胱")
FUNC |= set("说就都要会怎样哪这和那因为如当使应一些些很更")

SYSTEMS = {"五脏":"心肝脾肺肾","四季":"春夏秋冬","五行":"水火木金土","五志":"喜怒思悲恐"}

def load_corpus():
    # 语料固定位于项目目录,用项目绝对路径
    proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 兼容在子目录调用
    if os.path.exists(CORPUS):
        return json.load(open(CORPUS, encoding="utf-8"))
    # 构造时 fallback
    return json.load(open(os.path.join(HERE, os.path.basename(CORPUS)), encoding="utf-8"))

def build(corpus, maxvocab=260, max_target=220, min_freq=6):
    co=defaultdict(Counter); freq=Counter(); docf=Counter()
    for s in corpus:
        u=set(s)
        for ch in u:
            freq[ch]+=1
            for ch2 in u:
                if ch!=ch2:
                    co[ch][ch2]+=1; docf[ch2]+=1
    L=sum(len(s) for s in corpus) or 1
    vocab=[c for c,_ in freq.most_common(500) if c not in FUNC][:maxvocab]
    idf={c:max(1.0,math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v=[0.0]*len(vocab)
        for i,c in enumerate(vocab):
            p=co[ch].get(c,0)
            if p:
                v[i]=max(0.0,math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9)))*idf[c]
        return v
    targets=[c for c,_ in freq.most_common(400) if c not in FUNC and freq[c]>=min_freq][:max_target]
    return pmiv,vocab,freq,targets

def cos(a,b):
    da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
    return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)
def mean(xs): return sum(xs)/len(xs) if xs else 0.0

def main():
    corpus=load_corpus()
    pmiv,vocab,freq,targets=build(corpus)
    vec={ch:pmiv(ch) for ch in targets}
    chars=set(vec)
    L=sum(len(s) for s in corpus)
    print("="*70); print(LABEL+"  (%d字, %d句)"%(L,len(corpus))); print("="*70)
    print("机制：无标签语料共现自组织。检验引擎是否学到中医体系'内部聚合'。\n")
    print(f"{'体系':<6}{'体系内':>9}{'体系↔外界':>12}{'margin':>9}  判定")
    print("-"*58)
    for sn,mem in SYSTEMS.items():
        inner=[c for c in mem if c in vec]
        if len(inner)<2:
            print(f"{sn:<6}(语料内不足2字)"); continue
        sim_in=[cos(vec[inner[i]],vec[inner[j]]) for i in range(len(inner)) for j in range(i+1,len(inner))]
        others=[c for c in chars-set(inner)]
        sim_out=[cos(vec[a],vec[b]) for a in inner for b in others]
        mi,mo=mean(sim_in),mean(sim_out); margin=mi-mo
        verdict="★★★ 强涌现" if margin>0.03 else("★★ 显著" if margin>0.015 else("★ 弱" if margin>0.005 else "· 未分离"))
        print(f"{sn:<6}{mi:>9.3f}{mo:>12.3f}{margin:>+9.3f}  {verdict}")
    print("\n"+'-'*70, "\n逐成员两两相似度:")
    for sn,mem in SYSTEMS.items():
        inner=[c for c in mem if c in vec]
        if len(inner)<2: continue
        print(f"\n  【{sn}】")
        for a in inner:
            print(f"    {a} → "+" ".join(f"{b}:{cos(vec[a],vec[b]):.2f}" for b in inner if b!=a))
    print("\n"+"="*70)
    print("解读：margin越大，引擎把该体系从语料'涌现'得越清晰。")

if __name__=="__main__":
    main()
