#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_collapse.py — 诊断分类坍缩发生在哪一层。

对比同批测试句的三种词义来源：
  A. 纯静态 word_sem_yao（不繁殖不择义）
  B. 嵌套词胞·不择义 (poly=False)：繁殖后的 c.sem_yao
  C. 嵌套词胞·择义   (poly=True) ：经 sense_select 择义后的词义
追踪：逐步看坍缩(单卦暴涨/他卦崩)从 A→B→C 哪一步开始。
输出：每卦判为该卦的分布 + 各卦准确率。
"""
import re, sys, math, random
from collections import Counter
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG
random.seed(7)
TXT="红楼梦_全文.txt"
sents=[s.strip() for s in re.split(r"[。！？\n]",open(TXT,encoding="utf-8").read()) if s.strip()]
BG=list(NG.YAO_BY_BAGUA)

def guess(env):
    if not env: return None
    return max(BG, key=lambda b: NG.bscore(env,b))

big=Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}",open(TXT,encoding="utf-8").read()): big[m]+=1
common=[w for w,c in big.most_common(3000) if c>=25]
WORDK=set(NG.ENTITY_WORDS)|set(common)
def seg(s):
    i=0;out=[]
    while i<len(s):
        m=None
        for ln in range(min(4,len(s)-i),0,-1):
            w=s[i:i+ln]
            if w in WORDK: m=w;break
        if m: out.append(m); i+=len(m)
        else: out.append(s[i]); i+=1
    return out

TEST_W={"坎":["水","雨","泪","江","河"],"离":["火","烛","灯","焰","热"],"巽":["树","林","枝","森"],"乾":["金","银","钱","珠","宝"],"坤":["地","城","墙","尘"],"艮":["山","石","峰","峻"]}
TS=[]
for bg,ws in TEST_W.items():
    for w in ws:
        ss=[s for s in sents if w in s and len(s)<60]; random.shuffle(ss)
        for s in ss[:20]: TS.append((bg,w,s))

# A: 纯静态
def run_static():
    dist=Counter(); ok=tot=0; per={}
    for bg,w,s in TS:
        acc=[]
        for tk in seg(s.replace(w,"")):
            y=NG.word_sem_yao(tk)
            if y is not None and y!=NG.NEUTRAL_YAO: acc.append(y)
        if not acc: continue
        env=[sum(a[i] for a in acc)/len(acc) for i in range(6)]
        g=guess(env)
        if g: dist[g]+=1; tot+=1; ok+=(g==bg); per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(g==bg)
    return dist,ok,tot,per

def fmt(res):
    dist,ok,tot,per=res
    print(f"  准确率 {ok}/{tot}={ok/max(tot,1)*100:.0f}%  判别分布={dict(dist)}")
    return per

def run_poly(poly):
    eng=NG(max_cells=60000,seed=0)
    for s in sents[:12000]: eng.process_sentence_words(seg(s),poly=poly)
    dist=Counter(); ok=tot=0; per={}
    for bg,w,s in TS:
        r=eng.process_sentence_words(seg(s.replace(w,"")),poly=poly)
        g=guess(r["sent_yao"])
        if g: dist[g]+=1; tot+=1; ok+=(g==bg); per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(g==bg)
    return dist,ok,tot,per

print(f"测试句: {len(TS)}  | 训练语料前12000句\n")
print("A. 纯静态 word_sem_yao(不繁殖不择义):")
perA=fmt(run_static())
print("B. 嵌套词胞·不择义(poly=False):")
perB=fmt(run_poly(False))
print("C. 嵌套词胞·择义(poly=True):")
perC=fmt(run_poly(True))
print("\n逐卦准确率对照(A静态 / B嵌套不择义 / C择义):")
for bg in TEST_W:
    a=perA.get(bg,[0,0]); b=perB.get(bg,[0,0]); c=perC.get(bg,[0,0])
    print(f"  {bg}: A={a[0]}/{a[1]}({a[0]/max(a[1],1)*100:.0f}%)  B={b[0]}/{b[1]}({b[0]/max(b[1],1)*100:.0f}%)  C={c[0]}/{c[1]}({c[0]/max(c[1],1)*100:.0f}%)")
