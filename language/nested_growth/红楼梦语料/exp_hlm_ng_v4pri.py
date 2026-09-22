#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_ng_v4pri.py — A修法 v4：先验校正（中性基准去偏）+ 方向主导

【v3遗留】 正交分解后中性基线仍偏金(55%)：金=乾 μ=0.79 六大类最高，
  饱满项让"金范式"在无关语境霸占。水/土等低μ类被压制。

【v4根因】 不是方向分不行，而是量纲不齐：每类对中性语境的"基线得分"不同
          (金先天高)。要拿到"干净绝对准确率"必须做 **类别先验去偏**：
  对每个类 c，先在中性语料上测出该类对中性语境的期望得分 E_neutral[c]，
  判别时用 **相对偏离** score(v,proto_c) − E_neutral[c]，
  谁的相对偏离最正，谁就更"被这个语境特异地激活"。
  这一步统计上叫 class-conditional prior subtraction（类别条件先验校正）。

【metric】方向余弦为主（水/火/木/土），金=乾无方向→方向分≈0；
         金靠"高μ×(语境高μ)"的饱满项在"真金语境"(君主体/富丽/刀兵)胜出，
         且先验校正确保无关语境不误判金。α/β 与 E_neutral 一起标定。

【对照】①中性基线(近均匀) ②逐类判别 ③消融Δ(主证据)
"""
import re, sys, math, random
from collections import Counter, defaultdict

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

_YAO = {}
def _sem(w):
    if w not in _YAO:
        _YAO[w] = NG.word_sem_yao(w)
    return _YAO[w]

def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m = sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a, b):
    da, db = delta_of(a), delta_of(b)
    na, nb = norm(da), norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)

PROTO_MEMBERS = {
    "水":["水","江","河","海","雨","泪","酒","溪","泉","波"],
    "火":["火","烛","灯","焰","热","燃"],
    "木":["树","木","林","枝","花","叶","森"],
    "金":["金","银","铜","铁","锡","刀","剑"],
    "土":["山","石","土","尘","岩","地","坡"],
}
def proto_yao(cat):
    acc = [_sem(w) for w in PROTO_MEMBERS[cat] if _sem(w) is not None]
    if not acc: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]
PROTO = {c: proto_yao(c) for c in PROTO_MEMBERS}

ALPHA = 1.0
BETA = 0.9

def raw_score(v, proto):
    return ALPHA*cos_dir(v, proto) + BETA*mu_of(v)*mu_of(proto)

def ctx_env(s):
    toks = []
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

# ---------- 先验校正：在中性语料上标定各基准分 ----------
STOP0 = set("水雨泪酒江火烛树花金山石尘泥")
def neutral_pool(n=1500):
    pool = [s for s in sents if not any(w in s for w in STOP0) and len(s)<60]
    random.shuffle(pool)
    return pool[:n]

E_NEUTRAL = {c: 0.0 for c in PROTO}
def calibrate_prior():
    pool = neutral_pool()
    acc = {c: 0.0 for c in PROTO}; n = 0
    for s in pool:
        env = ctx_env(s)
        if env:
            n += 1
            for c, py in PROTO.items():
                acc[c] += raw_score(env, py)
    for c in PROTO:
        E_NEUTRAL[c] = acc[c]/max(n, 1)
    print("类别相对中性基准分 E_neutral[c]:")
    print("   " + ", ".join(f"{c}:{E_NEUTRAL[c]:+.3f}" for c in PROTO))
    return n

def guess_env(env):
    if not env: return None
    best_c, best_s = None, -1e9
    for c, py in PROTO.items():
        if py is None: continue
        s = raw_score(env, py) - E_NEUTRAL[c]   # 相对偏离（先验去偏）
        if s > best_s: best_s, best_c = s, c
    return best_c

def main():
    print(f"\n红楼句子:{len(sents)}  A-v4: 方向主导 + 先验校正")
    print("═"*60)
    calibrate_prior()
    res = Counter(); neut = 0
    # 中性基线也用"非训练的那部分中性句"
    pool = neutral_pool(3000); train = (E_NEUTRAL and 1500)
    others = pool[1500:] if len(pool) > 1500 else pool
    res = Counter()
    for s in others:
        g = guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    print(f"\n① 中性基线对照(用未标定中性句, n={neut}):")
    print("   " + ", ".join(f"{c}:{res[c]} ({res[c]/max(neut,1)*100:.0f}%)" for c in PROTO))

    tests = {
        "水类":["江","河","海","溪","泉","水","雨","泪","酒"],
        "火类":["火","烛","灯","焰"],
        "木类":["树","林","枝","花"],
        "土石类":["山","石","尘","土"],
    }
    print("\n② 逐类判别（挖掉目标词→语境猜类别）:")
    overall_ok = overall_tot = 0
    for cat, ws in tests.items():
        ok = tot = 0
        for w in ws:
            ss = [s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:40]:
                g = guess_env(ctx_env(s.replace(w, "")))
                if g:
                    tot+=1; overall_tot+=1
                    if g == cat[0]: ok+=1; overall_ok+=1
        print(f"   {cat}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%  (随机≈20%)")
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%")

def ablation():
    cats = {"水":["水","雨","泪","酒","江","河","海","溪","泉","波"],
            "火":["火","烛","灯","焰","热","燃"],
            "木":["树","木","林","枝","花","叶","森"],
            "土":["山","石","土","尘","岩","地","坡"]}
    print("\n"+"═"*60)
    print("③ 消融Δ(主证据)：挖类内词→该类相对得分应显著下降(Δ<0)")
    keep = defaultdict(float); drop = defaultdict(float); cnt = Counter()
    for s in sents:
        if len(s)>=60: continue
        for cat, ws in cats.items():
            present=[w for w in ws if w in s]
            if not present: continue
            cnt[cat]+=1
            ek=ctx_env(s); ed=ctx_env(re.sub("|".join(re.escape(w) for w in present),"",s))
            if ek: keep[cat]+= raw_score(ek,PROTO[cat])-E_NEUTRAL[cat]
            if ed: drop[cat]+= raw_score(ed,PROTO[cat])-E_NEUTRAL[cat]
    for cat in cats:
        k=keep[cat]/max(cnt[cat],1); d=drop[cat]/max(cnt[cat],1)
        print(f"   {cat}: 含词={k:+.3f} 挖后={d:+.3f} Δ={d-k:+.3f} (应<0)")

if __name__ == "__main__":
    main()
    ablation()
