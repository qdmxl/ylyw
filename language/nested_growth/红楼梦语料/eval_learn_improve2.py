#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_learn_improve2.py — 修正版无监督学习：对比监督 + 去偏 + 保留部首先验

覆复盘(v2结果) & 方法学教训：
  上一版用"句主导卦"做监督目标，但红楼主导卦分布严重偏乾(乾2309/坤133≈17:1)，
  导致学习把水/金/火等词全部往乾拉 → 破坏部首区分度，判别从35%掉到23%。
  根因：**监督信号有偏** = argmax(主导卦)作为唯一老师，天然带偏；
        且"向主导卦归并" = 聚类式退化，违背"理解≠聚类、不能退化"军规。

修正三原则：
  R1 对比监督：词的学习信号 = 该词在当前句**相对其他卦的判别显著性**，
     而非"绝对主导卦"。用软对比(soft attention)而非 argmax。
  R2 去偏：主导卦分布不均匀 → 学习目标做频率去偏(除以先验出现率)，去掉"乾兜底"污染。
  R3 保留先验：词语义爻只在"部首无决断(低判别置信)"时才允许较大校正；
     部首明确的词(水/火/金)只做微调，不推翻部首先验(温和学习)。

评测：同批测试句，静态基线 vs 修正版学习后。目标：不降反升。
"""
import re, sys, math, random
from collections import Counter, defaultdict

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(7)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

BAGUA = dict(NG.YAO_BY_BAGUA)
BG = list(BAGUA.keys())
def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m=sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a,b):
    da,db=delta_of(a),delta_of(b); na,nb=norm(da),norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)
def bscore(v,bg):
    if bg=="乾": return mu_of(v)-0.5
    if bg=="坤": return 0.5-mu_of(v)
    return cos_dir(v,BAGUA[bg])
def all_scores(v):   # 8卦得分
    return {b:bscore(v,b) for b in BG}
def guess_env(env):
    if not env: return None
    return max(BG, key=lambda b: bscore(env,b))

big=Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT,encoding="utf-8").read()):
    big[m]+=1
common=[w for w,c in big.most_common(3000) if c>=25]
WORDK = set(NG.ENTITY_WORDS) | set(common)
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
    tset=[]
    for bg,ws in TEST_W.items():
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:max_per]:
                tset.append((bg,w,s))
    return tset

def run_tset(tset, ctxfn):
    per={}; ok=0; tot=0
    for bg,w,s in tset:
        env=ctxfn(s.replace(w,""))
        g=guess_env(env)
        if g: tot+=1; ok+=(g==bg); per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(g==bg)
    return per, ok, tot

def _sem_keep(w):   # 静态词义爻（保留部首先验，用于R3判断置信）
    return NG.word_sem_yao(w)

def main():
    tset=build_testset()
    print(f"测试句集: {len(tset)}")

    # 静态基线
    def ctx_static(s):
        acc=[]
        for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
            y=NG.word_sem_yao(w)
            if y is not None and y!=NG.NEUTRAL_YAO: acc.append(y)
        if not acc: return None
        return [sum(a[i] for a in acc)/len(acc) for i in range(6)]
    per0,ok0,tot0=run_tset(tset,ctx_static)
    acc0=ok0/max(tot0,1)
    print(f"① 静态基线(不学): {ok0}/{tot0}={acc0*100:.1f}%")

    # ── 修正版学习 ──
    eng=NG(max_cells=60000, seed=0)
    print("\n② 修正版学习(对比监督+去偏+温和) 喂12000句...")
    # 先统计主导卦先验(去偏用)
    pri=Counter()
    for s in sents[:12000]:
        r=eng.process_sentence_words(seg(s))
        if r["sent_yao"]:
            g=guess_env(r["sent_yao"])
            if g: pri[g]+=1
    pri_m=sum(pri.values()) or 1
    priw={b: (pri_m/8)/max(pri[b],1) for b in BG}   # 去偏权重：稀有卦权重大
    print("   去偏权重(稀有卦↑):", {b: round(priw[b],2) for b in BG})

    # 学习主循环
    WACC=defaultdict(list)   # word -> 每词的8卦相关性累积(去偏加权)
    n_seen=defaultdict(int)
    for s in sents[:12000]:
        words=seg(s)
        if len(words)<3: continue
        r=eng.process_sentence_words(words)
        sy=r["sent_yao"]
        if sy is None: continue
        sall=all_scores(sy)
        # 此句的"标准向量" = 8卦去偏得分（对比/相对监督目标）
        # 用 softmax 温度低些 → 近似 soft 对比，不取 argmax
        mx=max(sall.values()); 
        wt={}
        sm=sum(math.exp(sall[b]-mx)*priw[b] for b in BG) or 1e-9
        for b in BG:
            wt[b]=(math.exp(sall[b]-mx)*priw[b])/sm
        # 句目标爻 = 按相对显著性对8卦爻加权（对比监督）
        tgt=[sum(wt[b]*BAGUA[b][i] for b in BG) for i in range(6)]
        for c in r["word_cells"]:
            if c.is_entity or c.sem_yao is None: continue
            # R3 置信: 词自身部首爻的判别置信度(越高越不动)
            cs=all_scores(c.sem_yao); cconf=max(cs.values())- (sorted(cs.values(),reverse=True)[1] if len(cs)>1 else cs["乾"])
            gain = 1.0 if cconf<0.15 else (0.3 if cconf<0.35 else 0.08)  # 部首明确的词微弱学
            n_seen[c.word]+=1
            WACC[c.word].append((gain, [c.sem_yao[i] for i in range(6)], tgt))
    # apply
    applied=0
    for w, lst in WACC.items():
        c=eng.cells.get(w)
        if c is None or c.sem_yao is None: continue
        # 修正: 向"句相对显著性目标"温和靠拢，但保留部首
        base=c.sem_yao
        # 只考虑高gain(低置信)词做实质改变
        avg_gain=sum(g for g,_,_ in lst)/len(lst)
        if avg_gain<0.4:
            continue  # 部首明确词基本不动（保留先验）
        # 计算整体累积目标
        base=c.sem_yao
        acc=[0.0]*6
        for g,basev,tgt in lst:
            for i in range(6): acc[i]+= g*(tgt[i]-basev[i])
        new=[max(0.0,min(1.0, base[i]+0.04*acc[i]/len(lst))) for i in range(6)]
        c.learned_sem=new; c.sem_yao=list(new); applied+=1
    print(f"   实际校准(低置信词优先)= {applied} 词胞")

    def ctx_eng(s):
        r=eng.process_sentence_words(seg(s)); return r["sent_yao"]
    per2,ok2,tot2=run_tset(tset,ctx_eng)
    acc2=ok2/max(tot2,1)
    print(f"③ 学后(修正): {ok2}/{tot2}={acc2*100:.1f}%")
    print(f"\n═══ 对比 ═══ 静态{acc0*100:.1f}% → 学后{acc2*100:.1f}%  Δ={((acc2-acc0)*100):+.1f}%")
    print(f"{'卦':<4}{'静态':<12}{'学后':<12}")
    for bg in TEST_W:
        a=per0.get(bg,[0,0]); b=per2.get(bg,[0,0])
        s0=a[0]/max(a[1],1)*100; s2=b[0]/max(b[1],1)*100
        mk="✓" if s2>s0+2 else ("▽" if s2<s0-2 else "△")
        print(f"  {bg}: {a[0]}/{a[1]}({s0:.0f}%)  {b[0]}/{b[1]}({s2:.0f}%)  {mk}")

if __name__=="__main__":
    main()
