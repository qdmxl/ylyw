#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_bagua3.py — A修法终极：八卦判别，乾坤用"中位偏度"、其余六卦用"方向余弦"

【核心认知(易经智慧)】 全平值卦(乾=111111/坤=000000)的语义不存在于"方向"，而在"中位偏"：
   乾 = 纯阳/刚健  → 语义爻均值越接近1越乾      (mean→1)
   坤 = 纯阴/柔顺  → 语义爻均值越接近0越坤      (mean→0)
   其余六卦(离震巽坎艮兑)语义存在于"波动方向"   → 用去均值方向余弦
  所以判别要与卦"本性"匹配：平值卦比"中位偏"，非平值卦比"方向"。
  这才能在同一框架下检验全部8卦(有测试词的6卦)，不再让乾坤陪跑。

验证任务(与引擎同构)：含某卦义旁字的语境，应被判成该卦。
  例: 含"水/雨/江"的语境→坎;  含"金/银/玉"→乾;  含"土/地/尘"→坤
  指标: ①判别准确率(对/错较八卦全候选) ②中性基线均匀度 ③消融Δ
"""
import re, sys, math, random
from collections import Counter, defaultdict

HERE="./"
sys.path.insert(0,".."); sys.path.insert(0,"../..")
from nested_growth_semantics import NestedGrowthSemantics as NG
random.seed(0)
TXT="红楼梦_全文.txt"
sents=[s.strip() for s in re.split(r"[。！？\n]",open(TXT,encoding="utf-8").read()) if s.strip()]

_YAO={}
def _sem(w):
    if w not in _YAO: _YAO[w]=NG.word_sem_yao(w)
    return _YAO[w]

BAGUA=dict(NG.YAO_BY_BAGUA)
def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m=sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a,b):
    da,db=delta_of(a),delta_of(b); na,nb=norm(da),norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)

def bagua_score(v, bg):
    """按卦本性判别：乾坤~中位偏, 其余~方向余弦。返回-1..1"""
    base=BAGUA[bg]
    if bg=="乾":   # 纯阳: 越接近全1越好
        return mu_of(v) - 0.5
    if bg=="坤":   # 纯阴: 越接近全0越好
        return 0.5 - mu_of(v)
    # 非平值卦: 方向余弦(去均值)
    return cos_dir(v, base)

def guess_env(env):
    if not env: return None
    return max(BAGUA, key=lambda b: bagua_score(env, b))

def ctx_env(s):
    toks=[]
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y=_sem(w)
        if y is not None and y!=NG.NEUTRAL_YAO: toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

# 测试词：各卦义旁字（来自 RADICAL_SEMANTICS）
BAGUA_WORDS={
 "坎":["水","雨","泪","酒","江","河","海","溪","泉","潮","浪","汤"],
 "离":["火","烛","灯","焰","热","炎","烹","晖","晴","照"],
 "巽":["木","树","林","枝","花","森","梁","柱","桌","椅","梅","松"],
 "乾":["金","银","钱","铁","铜","锡","铃","锣","珠","宝","玉"],
 "坤":["土","地","城","墙","埃","址","壤","尘"],
 "艮":["山","石","峰","峦","峻","岩","岛"],
}
# 只保留引擎能产语义爻的词
def _words(bg):
    return [w for w in BAGUA_WORDS[bg] if _sem(w) is not None and _sem(w)!=NG.NEUTRAL_YAO]

def main():
    print(f"\n红楼句子:{len(sents)}  终极判别:乾坤=中位偏,六卦=方向(与八卦同构)")
    print("═"*62)
    print("各卦测试词:", {bg:[w for w in _words(bg)] for bg in BAGUA_WORDS})

    # 中性基线
    STOPALL=set(w for ws in BAGUA_WORDS.values() for w in ws)
    res=Counter(); neut=0
    for s in sents:
        if any(w in s for w in STOPALL): continue
        g=guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    print(f"\n① 中性基线(应接近均匀,n={neut}):")
    print("   "+", ".join(f"{b}:{res[b]} ({res[b]/max(neut,1)*100:.0f}%)" for b in BAGUA))

    print("\n② 逐卦判别(挖掉目标词→语境猜卦):")
    overall_ok=overall_tot=0
    for bg,ws0 in BAGUA_WORDS.items():
        ws=_words(bg)
        if not ws: continue
        ok=tot=0
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:40]:
                g=guess_env(ctx_env(s.replace(w,"")))
                if g:
                    tot+=1; overall_tot+=1
                    if g==bg: ok+=1; overall_ok+=1
        print(f"   {bg}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%  (随机≈12.5%)")
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%")

    print("\n③ 消融Δ(主证据): 挖类内词→该类判别强度应下降(Δ<0)")
    keep=defaultdict(float); drop=defaultdict(float); cnt=Counter()
    for s in sents:
        if len(s)>=60: continue
        for bg,ws0 in BAGUA_WORDS.items():
            ws=_words(bg); present=[w for w in ws if w in s]
            if not present: continue
            cnt[bg]+=1
            ek=ctx_env(s); ed=ctx_env(re.sub("|".join(re.escape(w) for w in present),"",s))
            if ek: keep[bg]+= bagua_score(ek,bg)
            if ed: drop[bg]+= bagua_score(ed,bg)
    for bg in BAGUA_WORDS:
        if cnt[bg]==0: continue
        k=keep[bg]/cnt[bg]; d=drop[bg]/cnt[bg]
        print(f"   {bg}: 含词={k:+.3f} 挖后={d:+.3f} Δ={d-k:+.3f} (应<0)")

if __name__=="__main__":
    main()
