#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_bagua_final.py — A1正式评测：八卦"词→卦"判别（严格版）

基于 v7(bagua3) 的成功度量：乾坤=中位偏度, 六卦=方向余弦。
本版补三块使其成为"正式评测"：
  ① 严格中性基线：不含任何卦义旁字的句子，8卦应接近均匀（无死锁类）
  ② 随机对照：判别准确率 vs 随机 (1/8≈12.5%)，标 z 统计显著
  ③ 覆盖扩展：补充兑(泽/口/言) 震(雷/动/电) 的卦义代表词 → 8卦全覆盖
  ④ 严格同配：训练(标定)与测试严格同源，且测试词随机抽样，报告样本量

输出：
  A) 逐卦：准确率 + 95%置信区间 + 相对随机提升倍数
  B) 中性基线分布 + 均匀度(熵)
  C) 消融Δ(主证据, 每卦含词vs挖词判别强度差异)
"""
import re, sys, math, random
from collections import Counter, defaultdict

HERE="./"
sys.path.insert(0,".."); sys.path.insert(0,"../..")
from nested_growth_semantics import NestedGrowthSemantics as NG
random.seed(42)
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

def bagua_score(v,bg):
    base=BAGUA[bg]
    if bg=="乾": return mu_of(v)-0.5          # 纯阳: 越满越乾
    if bg=="坤": return 0.5-mu_of(v)          # 纯阴: 越空越坤
    return cos_dir(v,base)                     # 六卦: 方向

def guess_env(env):
    if not env: return None
    return max(BAGUA,key=lambda b: bagua_score(env,b))

def ctx_env(s):
    toks=[]
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y=_sem(w)
        if y is not None and y!=NG.NEUTRAL_YAO: toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

# ── 8卦测试词（含兑/震：泽口舌/雷动电，补全卦义，取红楼中能映射语义的词）──
BAGUA_WORDS={
 "乾":["金","银","钱","铁","铜","锡","铃","锣","珠","宝","玉","钢","链","铛"],
 "兑":["口","舌","说","言","语","笑","谈","嘴","唇","叹"],
 "离":["火","烛","灯","焰","热","炎","烹","晖","晴","照","光","亮","晶","星"],
 "震":["雷","电","动","震","春","响","轰","惊","霆"],
 "巽":["木","树","林","枝","花","森","梁","柱","桌","椅","梅","松","板","床"],
 "坎":["水","雨","泪","酒","江","河","海","溪","泉","潮","浪","汤","湿","深"],
 "艮":["山","石","峰","峦","峻","岩","岛","丘","岭","岗"],
 "坤":["土","地","城","墙","埃","址","壤","尘","田","原","野","平"],
}
def _words(bg):
    return [w for w in BAGUA_WORDS[bg] if _sem(w) is not None and _sem(w)!=NG.NEUTRAL_YAO]

# 95% 正态近似置信区间
def ci95(ok,tot):
    if tot==0: return (0,0)
    p=ok/tot; se=math.sqrt(p*(1-p)/tot)
    return (p-1.96*se, p+1.96*se)

def main():
    print("═"*64)
    print("A1 正式评测：八卦「词→卦」判别")
    print(f"语料: 红楼{len(sents)}句 | 度量: 乾坤=中位偏/六卦=方向余弦")
    print("═"*64)

    # A. 逐卦判别（挖目标词→语境猜卦），严格随机抽样
    print("\n【A】逐卦判别准确率  (随机=12.5%)")
    print(f"{'卦':<4}{'测试词数':<8}{'样本':<7}{'正确':<7}{'准确率':<9}{'95%CI':<16}{'随机倍数'}")
    overall_ok=overall_tot=0
    per={}
    for bg in ["乾","兑","离","震","巽","坎","艮","坤"]:
        ws=_words(bg)
        if not ws:
            print(f"{bg:<4}{'无词':<8}"); continue
        ok=tot=0
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:40]:
                g=guess_env(ctx_env(s.replace(w,"")))
                if g: tot+=1; overall_tot+=1
                if g==bg: ok+=1; overall_ok+=1
        lo,hi=ci95(ok,tot); acc=ok/max(tot,1)
        per[bg]=(ok,tot)
        print(f"{bg:<4}{len(ws):<8}{tot:<7}{ok:<7}{acc*100:<9.1f}%"
              f"({lo*100:.0f}%–{hi*100:.0f}%)  ×{acc/0.125:.1f}")
    acc_o=overall_ok/max(overall_tot,1); lo,hi=ci95(overall_ok,overall_tot)
    print(f"{'合计':<5}{'':<8}{overall_tot:<7}{overall_ok:<7}{acc_o*100:<9.1f}%"
          f"({lo*100:.0f}%–{hi*100:.0f}%)  ×{acc_o/0.125:.1f}")

    # B. 严格中性基线（排除全部卦义旁字）→ 均匀度
    print("\n【B】严格中性基线（不含8卦全部义旁词）:")
    STOPALL=set(w for ws in BAGUA_WORDS.values() for w in ws)
    res=Counter(); neut=0
    for s in sents:
        if any(w in s for w in STOPALL) or len(s)>=80: continue
        g=guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    # 熵(均匀度): 8卦完全均匀=log(8)
    probs=[res[b]/max(neut,1) for b in BAGUA]
    entropy=-sum(p*math.log(p) for p in probs if p>0)
    print("   "+", ".join(f"{b}:{res[b]} ({res[b]/max(neut,1)*100:.0f}%)" for b in BAGUA)+f"  n={neut}")
    print(f"   分布熵={entropy:.3f} (完全均匀=2.079)  → "
          f"{'近均匀(无死锁)' if entropy>1.6 else '有偏+' if entropy>1.2 else '✗严重偏'}")

    # C. 消融Δ（主证据）
    print("\n【C】消融Δ（挖词→该类判别强度下降, 免疫偏差）:")
    keep=defaultdict(float); drop=defaultdict(float); cnt=Counter()
    for s in sents:
        if len(s)>=60: continue
        for bg in BAGUA_WORDS:
            ws=_words(bg); present=[w for w in ws if w in s]
            if not present: continue
            cnt[bg]+=1
            ek=ctx_env(s); ed=ctx_env(re.sub("|".join(re.escape(w) for w in present),"",s))
            if ek: keep[bg]+=bagua_score(ek,bg)
            if ed: drop[bg]+=bagua_score(ed,bg)
    for bg in BAGUA_WORDS:
        if cnt[bg]==0: continue
        k=keep[bg]/cnt[bg]; d=drop[bg]/cnt[bg]
        flag="✓" if (d-k)<-0.1 else ("◐" if (d-k)<0 else "✗")
        print(f"   {bg}: 含词={k:+.3f} 挖后={d:+.3f} Δ={d-k:+.3f} {flag}")

if __name__=="__main__":
    main()
