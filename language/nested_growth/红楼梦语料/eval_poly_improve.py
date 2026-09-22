#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_poly_improve.py — 端到端：多义择义(词胞义项库+H择义)接入语料后，
是否提升句层理解(句语境判别)。

对比(同批测试句集)：
  [基线] 不接多义 poly=False：静态/嵌套词胞聚合判句
  [多义] poly=True：词胞学多义义项，语境择义后判句
指标：六卦词语境判别准确率 + 逐卦

注意：多义的价值不在"平均准确率暴涨"(那主要由部首主导)，
而在"含多义词/语境敏感的句子"能否因择义判得更准。故除整体外，
重点看典型多义触发句的消歧率。
"""
import re, sys, math, random
from collections import Counter, defaultdict

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(7)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

BAGUA = dict(NG.YAO_BY_BAGUA); BG = list(BAGUA)
def mu(v): return sum(v)/len(v) if v else 0.0
def de(v):
    if not v: return [0.0]*6
    m=mu(v); return [x-m for x in v]
def nr(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cd(a,b):
    da,db=de(a),de(b); na,nb=nr(da),nr(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)
def bs(v,b):
    return NG.bscore(v,b)
def guess(env):
    if not env: return None
    return max(BG, key=lambda b: bs(env,b))

big=Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT,encoding="utf-8").read()): big[m]+=1
common=[w for w,c in big.most_common(3000) if c>=25]
WORDK=set(NG.ENTITY_WORDS)|set(common)
def seg(s):
    i=0; out=[]
    while i<len(s):
        m=None
        for ln in range(min(4,len(s)-i),0,-1):
            w=s[i:i+ln]
            if w in WORDK: m=w; break
        if m: out.append(m); i+=len(m)
        else: out.append(s[i]); i+=1
    return out

TEST_W = {
 "坎":["水","雨","泪","江","河","海","溪","泉","潮","浪"],
 "离":["火","烛","灯","焰","热","炎","晴","照"],
 "巽":["树","林","枝","森","梁","柱","桌","椅","梅","松"],
 "乾":["金","银","钱","珠","宝","玉","铁","铜"],
 "坤":["地","城","墙","尘","壤"],
 "艮":["山","石","峰","峦","峻","岭","岩"],
}
def build_testset(max_per=25):
    ts=[]
    for bg,ws in TEST_W.items():
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:max_per]: ts.append((bg,w,s))
    return ts
TS=build_testset()

def run(eng, poly):
    ok=tot=0; per={}; n_seen_sense=0
    for bg,w,s in TS:
        r=eng.process_sentence_words(seg(s.replace(w,"")), poly=poly)
        if poly:
            for c in r["word_cells"]:
                if c.sem_yaos: n_seen_sense+=1
        g=guess(r["sent_yao"])
        if g:
            tot+=1; ok+=(g==bg); per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(g==bg)
    return ok,tot,per,n_seen_sense

def main():
    print(f"测试句集: {len(TS)}  | 语料前{12000}句建胞+学习")

    # 基线 poly=False
    eng0=NG(max_cells=60000, seed=0)
    for s in sents[:12000]: eng0.process_sentence_words(seg(s), poly=False)
    ok0,tot0,per0,_=run(eng0, False)
    acc0=ok0/max(tot0,1)
    print(f"\n① 基线(不接多义): {ok0}/{tot0}={acc0*100:.1f}%")

    # 多义 poly=True
    eng1=NG(max_cells=60000, seed=0)
    for s in sents[:12000]: eng1.process_sentence_words(seg(s), poly=True)
    nsec=sum(1 for c in eng1.cells.values() if c.sem_yaos)
    ok1,tot1,per1,nseen=run(eng1, True)
    acc1=ok1/max(tot1,1)
    print(f"② 多义版(poly=True): {ok1}/{tot1}={acc1*100:.1f}%")
    print(f"   学了多义的词胞数={nsec} (义项>1的词数) / 总词胞={len(eng1.cells)}")

    print(f"\n═══ 提升对比 ═══")
    print(f"基线{acc0*100:.1f}% → 多义{acc1*100:.1f}%   Δ={((acc1-acc0)*100):+.1f}%")
    print(f"{'卦':<4}{'基线':<12}{'多义':<12}")
    for bg in TEST_W:
        a=per0.get(bg,[0,0]); b=per1.get(bg,[0,0])
        s0=a[0]/max(a[1],1)*100; s2=b[0]/max(b[1],1)*100
        mk="✓" if s2>s0+2 else ("▽" if s2<s0-2 else "△")
        print(f"  {bg}: {a[0]}/{a[1]}({s0:.0f}%)  {b[0]}/{b[1]}({s2:.0f}%)  {mk}")

if __name__=="__main__":
    main()
