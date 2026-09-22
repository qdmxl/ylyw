#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_learn_improve.py — 端到端验证：分布学习(词+句同步学)是否提升句层理解能力

对比：
  [基线] 静态 word_sem_yao（不学） → 句层语境判别
  [学后] 喂语料让词胞/句胞分布学习 → 再判同批测试句
指标：基准准确率、含卦词语境判别准确率的提升

流程：
  1. 构造同一批测试句（含各卦义旁词、挖词判别）
  2. 静态基线：用 NG.word_sem_yao + 上下文聚合 判卦
  3. 引擎学完语料后：用 eng.process_sentence_words(嵌套,带learned_sem) 判卦
  4. 输出对比
"""
import re, sys, math, random
from collections import Counter, defaultdict

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(7)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

BAGUA = dict(NG.YAO_BY_BAGUA)
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
def guess_env(env):
    if not env: return None
    return max(BAGUA, key=lambda b: bscore(env,b))

# 分词词库
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

# 测试卦词表
TEST_W = {
 "坎":["水","雨","泪","江","河","海","溪","泉","潮","浪"],
 "离":["火","烛","灯","焰","热","炎","晴","照"],
 "巽":["树","林","枝","森","梁","柱","桌","椅","梅","松"],
 "乾":["金","银","钱","珠","宝","玉","铁","铜"],
 "坤":["地","城","墙","尘","壤"],
 "艮":["山","石","峰","峦","峻","岭","岩"],
}
# 预采样测试集（每卦若干句，挖词后用，保证前后同批）
def build_testset(max_per=25):
    tset = []
    for bg, ws in TEST_W.items():
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:max_per]:
                tset.append((bg, w, s))
    return tset

# 静态基线上下文（词义爻=word_sem_yao，跳过实体/时间）
_YAO={}
def _sem(w):
    if w not in _YAO: _YAO[w]=NG.word_sem_yao(w)
    return _YAO[w]
def ctx_env_static(s):
    acc=[]
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y=NG.word_sem_yao(w)
        if y is not None and y!=NG.NEUTRAL_YAO:
            acc.append(y)
    if not acc: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]

def run_tset(tset, ctxfn):
    per={}; ok_all=tot_all=0
    for bg, w, s in tset:
        env = ctxfn(s.replace(w,""))
        g = guess_env(env)
        if g:
            tot_all+=1; ok_all += (g==bg)
            per.setdefault(bg,[0,0]); per[bg][1]+=1; per[bg][0]+=(g==bg)
    return per, ok_all, tot_all

def main():
    tset = build_testset()
    print(f"测试句集: {len(tset)} (六卦各含词/挖词, 同批对比)")

    # ① 静态基线
    per0, ok0, tot0 = run_tset(tset, ctx_env_static)
    acc0=ok0/max(tot0,1)
    print(f"\n① 静态基线(word_sem_yao, 不学): {ok0}/{tot0} = {acc0*100:.1f}%")

    # ② 分布学习（词+句同步学），更大学习量
    eng = NG(max_cells=50000, seed=0)
    eta=0.10
    print(f"\n② 分布学习: 喂语料{len(sents[:12000])}句(eta={eta}, 词句同步学)...")
    n_seen=defaultdict(int); drift=defaultdict(lambda:[0.0]*6)
    step=0
    for s in sents[:12000]:
        words=seg(s)
        if len(words)<3: continue
        r=eng.process_sentence_words(words)
        sy=r["sent_yao"]
        if sy is None: continue
        gs=guess_env(sy)
        if gs is None: continue
        gy=BAGUA[gs]
        for c in r["word_cells"]:
            if c.is_entity or c.sem_yao is None: continue
            comp=bscore(c.sem_yao, gs)
            push=1.0 if comp>0.05 else (-1.0 if comp<-0.05 else 0.3)
            n_seen[c.word]+=1
            for i in range(6):
                drift[c.word][i]+= push*(gy[i]-c.sem_yao[i])
    # apply: 写入 learned_sem
    applied=0
    for w,d in drift.items():
        c=eng.cells.get(w)
        if c is None or c.sem_yao is None: continue
        n=n_seen[w]
        new=[c.sem_yao[i]+eta*d[i]/max(n,1) for i in range(6)]
        new=[max(0.0,min(1.0,x)) for x in new]
        c.learned_sem=new; c.sem_yao=list(new); applied+=1
    print(f"   学了 {applied} 个词胞(持久 learned_sem)")

    # ③ 学后：用引擎嵌套接口判同批测试句
    def ctx_eng(s):
        r = eng.process_sentence_words(seg(s))
        return r["sent_yao"]
    per2, ok2, tot2 = run_tset(tset, ctx_eng)
    acc2=ok2/max(tot2,1)
    print(f"\n③ 学后(嵌套+learned_sem): {ok2}/{tot2} = {acc2*100:.1f}%")

    print(f"\n═══ 提升对比 ═══")
    print(f"静态基线: {acc0*100:.1f}%  vs  学后: {acc2*100:.1f}%   →  Δ={((acc2-acc0)*100):+.1f}%")
    print("逐卦对照（学前后）:")
    print(f"{'卦':<4}{'静态':<10}{'学后':<10}")
    for bg in TEST_W:
        a = per0.get(bg,[0,0]); b=per2.get(bg,[0,0])
        s0=a[0]/max(a[1],1)*100; s2=b[0]/max(b[1],1)*100
        mark="✓" if s2>s0+2 else ("△" if s2>=s0 else "▽")
        print(f"  {bg}: {a[0]}/{a[1]}({s0:.0f}%)  {b[0]}/{b[1]}({s2:.0f}%)  {mark}")

if __name__=="__main__":
    main()
