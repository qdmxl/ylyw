#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_ng_v3fixed.py — A修法 v3：正交分解判别（均值饱满度 + 波动方向）

【背景链】
  v1 (8-19, calibrated): 中心化余弦 → 金=乾平值被废(0%), 中性偏水(79%)
  v2 (上一版, probe):    纯共激活核(无方向) → 中性偏金(85%), 土=0%, 15%全掉随机
  根因：中心化 杀死平值类；无方向核 杀死非平值类。单一度量两头吃亏。

【A修法 v3 = 正交分解，两类信息各自比】把每个六爻向量拆成两个正交分量：
    v = μ·1̄ + Δv          (μ=均值/饱满度, Δv=去均值波动/方向)
  判别分数 = 方向分 + 饱满分：
    score(v, proto) = α · cos(Δv, Δproto)      # 方向(区分水火木土)
                   + β · sim(μ, μproto)         # 饱满度(区分金=乾纯阳)
  这样：
    · 水/火/木/土 方向分明 → 靠方向分胜出
    · 金=乾=全平值 → 方向分=0(自然弱), 但 μ大 → 靠饱满分胜出（不再被废）
    · 中性语境 μ中低、方向杂 → 各方向分摊，不霸占
原型：每类多词成员均值（均衡）。

【输出】 ①中性基线(应近均匀) ②逐类判别 ③消融Δ(主证据,免疫偏差)
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

# ---------- 正交分解 ----------
def mu_of(v):  # 均值/饱满度分量
    return sum(v)/len(v) if v else 0.0
def delta_of(v):  # 去均值波动/方向分量（非中心化的方向保留在Δ里）
    if not v: return [0.0]*6
    m = sum(v)/len(v)
    return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a, b):  # Δv 方向余弦
    da, db = delta_of(a), delta_of(b)
    na, nb = norm(da), norm(db)
    if na < 1e-9 or nb < 1e-9: return 0.0
    return sum(x*y for x, y in zip(da, db))/(na*nb)

ALPHA = 1.0      # 方向权
BETA = 0.6       # 饱满权（金=乾靠它，但压不过方向分明类）

def score(v, proto):
    dir_s = cos_dir(v, proto)
    mu_s = mu_of(v) * mu_of(proto)      # 两向量饱满度之积（金×金高，中性低）
    return ALPHA * dir_s + BETA * mu_s

# ---------- 多词均衡原型 ----------
PROTO_MEMBERS = {
    "水": ["水","江","河","海","雨","泪","酒","溪","泉","波"],
    "火": ["火","烛","灯","焰","热","燃"],
    "木": ["树","木","林","枝","花","叶","森"],
    "金": ["金","银","铜","铁","锡","刀","剑"],
    "土": ["山","石","土","尘","岩","地","坡"],
}
def proto_yao(cat):
    acc = [_sem(w) for w in PROTO_MEMBERS[cat] if _sem(w) is not None]
    if not acc: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]
PROTO = {c: proto_yao(c) for c in PROTO_MEMBERS}

print("═══ 正交分解原型 ═══")
for c, y in PROTO.items():
    print(f"  {c:<3} μ(饱满)={mu_of(y):.3f}  Δ范数={norm(delta_of(y)):.3f}")

def guess_env(env):
    if not env: return None
    best_c, best_k = None, -1e9
    for c, py in PROTO.items():
        if py is None: continue
        k = score(env, py)
        if k > best_k: best_k, best_c = k, c
    return best_c

def ctx_env(s):
    toks = []
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

def main():
    print(f"\n红楼句子: {len(sents)}  →  A-v3: 正交分解(饱满+方向)")
    print("═"*60)
    STOP0 = set("水雨泪酒江火烛树花金山石尘泥")
    res = Counter(); neut = 0
    for s in sents:
        if any(w in s for w in STOP0): continue
        g = guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    print("\n① 中性基线对照（应接近均匀, n={}）:".format(neut))
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
    print("\n" + "═"*60)
    print("③ 消融Δ（主证据,免疫偏差）：挖掉类内词→该类核激活应下降(Δ<0)")
    keep = defaultdict(float); drop = defaultdict(float); cnt = Counter()
    for s in sents:
        if len(s) >= 60: continue
        for cat, ws in cats.items():
            present = [w for w in ws if w in s]
            if not present: continue
            cnt[cat]+=1
            env_k = ctx_env(s)
            env_d = ctx_env(re.sub("|".join(re.escape(w) for w in present), "", s))
            if env_k: keep[cat]+= score(env_k, PROTO[cat])
            if env_d: drop[cat]+= score(env_d, PROTO[cat])
    for cat in cats:
        k = keep[cat]/max(cnt[cat],1)
        d = drop[cat]/max(cnt[cat],1)
        print(f"   {cat}: 含词={k:.3f}  挖后={d:.3f}  Δ={d-k:+.3f}  (应<0)")

if __name__ == "__main__":
    main()
    ablation()
