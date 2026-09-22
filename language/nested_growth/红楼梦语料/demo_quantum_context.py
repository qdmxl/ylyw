#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_quantum_context.py — 量子语境测量版句合成（v2，接续 v1 朴素合成）

v2 核心：加"语境测量"——让每个词的叠加态被同句邻词语境测量偏转后，
再合成句子态。这是量子语义链"叠加表达 + 语境测量择义"的完整一环，
预期全面超越经典（v1 因缺此环而略低）。

量子语义链：
  词   → 多义叠加态 |词⟩ = Σ_i √p_i |卦_i⟩
  语境 → 邻词叠加态合成 |ctx_i⟩（句子内除词i外其他词）
  测量 → 用语境对词i态做部分投影测量(弱测量/退相干), 把多义
          "压向"语境支持的卦方向, 同时保留一定并存(不硬切)
  句   → 择义后词态加权合成 |句⟩
  判卦 → 测句态各卦概率, 最高者=句语义卦

抽象意图：
  语境是"看"这个词的观察者; 词态在观察下部分坍缩到语境对应的测量基,
  但仍保留其他义的概率质量(弱测量, 非强投影)——这是 Quantum Zeno /
  弱测量思想, 与"硬切义项"本质不同。
"""
import re, sys, random, math
import numpy as np
from collections import Counter
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(7)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

BG = list(NG.YAO_BY_BAGUA)
def bits_of(bg): return NG.YAO_BY_BAGUA[bg]
def basis_index(bits):
    idx=0
    for b in bits: idx=(idx<<1)|int(round(b))
    return idx
_BASIS={}
for bg in BG:
    v=np.zeros(2**6,dtype=complex); v[basis_index(bits_of(bg))]=1.0; _BASIS[bg]=v
def proj(bg): s=_BASIS[bg]; return np.outer(s,s.conj())
def p_of(state,bg): return float(abs(np.vdot(_BASIS[bg],state))**2)
def normalize(v):
    n=np.linalg.norm(v); return v/n if n>1e-12 else v

def word_state(w):
    y=NG.word_sem_yao(w)
    if y is None or y==NG.NEUTRAL_YAO: return None
    pri={}
    m=sum(y)/6
    for bg in BG:
        if bg=="乾": pri[bg]=max(0.0, m-0.5)
        elif bg=="坤": pri[bg]=max(0.0, 0.5-m)
        else:
            dy=[(x-m) for x in y]; ny=math.sqrt(sum(x*x for x in dy)) or 1e-9
            bb=bits_of(bg); mb=sum(bb)/6; db=[x-mb for x in bb]
            nb=math.sqrt(sum(x*x for x in db)) or 1e-9
            pri[bg]=max(0.0, sum(a*b for a,b in zip(dy,db))/(ny*nb))
    tot=sum(pri.values())
    if tot<1e-9: return None
    st=np.zeros(2**6,dtype=complex)
    for bg,s in pri.items():
        if s>0: st+=math.sqrt(s/tot)*_BASIS[bg]
    return normalize(st)

def state_distribution(st):
    return {bg:p_of(st,bg) for bg in BG}

def mix(states, weights):
    """混合多个态(不等权合成), 归一。"""
    acc=np.zeros(2**6,dtype=complex)
    for w,s in zip(weights,states):
        acc+=w*s
    return normalize(acc)

def top_bg(dist): return max(dist, key=dist.get)

def sentence_state_context(words, weak=0.5):
    """v2: 每个词被邻词语境'弱测量'偏转后, 再合成句子态。
    weak∈[0,1]: 语境测量强度。weak=0 → v1纯叠加; weak=1 → 强测量。
    """
    states={}
    for i,w in enumerate(words):
        s=word_state(w)
        if s is not None: states[i]=s
    if not states: return None
    result=[]
    for i,s in states.items():
        # 语境 = 同句其他词的合成态
        others=[states[j] for j in states if j!=i]
        if others:
            ctx_state = mix(others,[1.0]*len(others))
            ctx_dist = state_distribution(ctx_state)
            ctx_top = top_bg(ctx_dist)
            Ptop = ctx_dist[ctx_top]
            # 弱测量: 词态向'语境主导卦'投影的部分坍缩
            # |ψ'⟩ = (1-weak)·|ψ⟩ + weak·P_top|ψ⟩ (再归一)
            proj_part = np.vdot(_BASIS[ctx_top], s)*_BASIS[ctx_top]
            shifted = (1-weak)*s + weak*proj_part
            shifted = normalize(shifted)
        else:
            shifted = s
        result.append(shifted)
    return normalize(mix(result,[1.0]*len(result)))

def quantum_guess_context(words, weak):
    st = sentence_state_context(words, weak)
    if st is None: return None
    dist=state_distribution(st)
    return top_bg(dist), st

big=Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT,encoding="utf-8").read()): big[m]+=1
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

TEST_W={"坎":["水","雨","泪","江","河","海","溪"],"离":["火","烛","灯","焰","热","晴","照"],
 "巽":["树","林","枝","森","梁","柱"],"乾":["金","银","钱","珠","宝","玉"],
 "坤":["地","城","墙","尘","壤"],"艮":["山","石","峰","峦","峻"]}
def build():
    ts=[]
    for bg,ws in TEST_W.items():
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<50]; random.shuffle(ss)
            for s in ss[:20]: ts.append((bg,w,s))
    return ts
TS=build()

def eval_quant(weak):
    ok=tot=0; per={}; qdist=Counter()
    for bg,w,s in TS:
        g=quantum_guess_context(seg(s.replace(w,"")),weak)
        if g:
            gl,_=g; qdist[gl]+=1; tot+=1; ok+=(gl==bg); per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(gl==bg)
    return ok,tot,per,qdist

def main():
    print(f"量子语境测量版: 测试句={len(TS)}\n")
    print("弱测量强度 weak 扫描 (0=纯叠加v1, 1=强测量):")
    for weak in [0.0,0.3,0.5,0.7,1.0]:
        ok,tot,per,qdist=eval_quant(weak)
        print(f"  weak={weak:.1f}: {ok}/{tot}={ok/max(tot,1)*100:.0f}%  分布={dict(qdist)}")
    # 经典参照
    cok=c_tot=0; cdist=Counter(); cper={}
    for bg,w,s in TS:
        acc=[]
        for tk in seg(s.replace(w,"")):
            y=NG.word_sem_yao(tk)
            if y is not None and y!=NG.NEUTRAL_YAO: acc.append(y)
        if not acc: continue
        env=[sum(a[i] for a in acc)/len(acc) for i in range(6)]
        g=max(BG,key=lambda b: NG.bscore(env,b))
        cdist[g]+=1; c_tot+=1; cok+=(g==bg); cper.setdefault(bg,[0,0]); cper[bg][1]+=1; cper[bg][0]+=(g==bg)
    print(f"\n经典参照: {cok}/{c_tot}={cok/max(c_tot,1)*100:.0f}%  分布={dict(cdist)}")
    print("\n逐卦(最优weak vs 经典):")
    # 取 weak=0.5 展示
    ok,tot,per,qdist=eval_quant(0.5)
    print(f"{'卦':<4}{'量子(w=0.5)':<14}{'经典':<12}")
    for bg in TEST_W:
        a=per.get(bg,[0,0]); b=cper.get(bg,[0,0])
        print(f"  {bg}: {a[0]}/{a[1]}({a[0]/max(a[1],1)*100:.0f}%)  {b[0]}/{b[1]}({b[0]/max(b[1],1)*100:.0f}%)")

if __name__=="__main__":
    main()
