#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_diag_sep.py — 判别可分离性诊断：5类在语义空间是否可分？还是任务错位？

【动机】 v1~v4 反复出现"某一类霸占中性基线"（水/金来回横跳）。
  疑问：这到底是"判别度量没调好" 还是 "5类单字在原白话中本来就纠缠不清(任务错位)"?
  本文用量化回答：对每个类 c，统计
    1) 含该类词的真实语境 → 该类原型得分
    2) 中性语境 → 该类原型得分
    3) 两者分布重叠程度 (可分离性指标)
  若真实语境与中性语境得分高度重叠 → 判别任务在该类先天性不可分 → 是任务错位，
      修判别权重无解，应换"目标词存在与否"的二分类(更贴合语义引擎能力)或降任务难度。
"""
import re, sys, math, random
from collections import defaultdict
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT="红楼梦_全文.txt"
sents=[s.strip() for s in re.split(r"[。！？\n]",open(TXT,encoding="utf-8").read()) if s.strip()]

_YAO={}
def _sem(w):
    if w not in _YAO: _YAO[w]=NG.word_sem_yao(w)
    return _YAO[w]
def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m=sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a,b):
    da,db=delta_of(a),delta_of(b); na,nb=norm(da),norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)

PROTO_MEMBERS={
 "水":["水","江","河","海","雨","泪","酒","溪","泉","波"],
 "火":["火","烛","灯","焰","热","燃"],
 "木":["树","木","林","枝","花","叶","森"],
 "金":["金","银","铜","铁","锡","刀","剑"],
 "土":["山","石","土","尘","岩","地","坡"],
}
def proto_yao(cat):
    acc=[_sem(w) for w in PROTO_MEMBERS[cat] if _sem(w) is not None]
    if not acc: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]
PROTO={c:proto_yao(c) for c in PROTO_MEMBERS}

def score(v,proto): return cos_dir(v,proto)   # 纯方向可分性（去量纲）

def ctx_env(s):
    toks=[]
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y=_sem(w)
        if y is not None and y!=NG.NEUTRAL_YAO: toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

print("═"*62)
print("类内真实语境 vs 中性语境 的方向余弦分布（可分离性诊断）")
print("═"*62)
# 中性池
STOP0=set("水雨泪酒江火烛树花金山石尘泥")
neut=[s for s in sents if not any(w in s for w in STOP0) and len(s)<60]
neut_env=[e for s in neut if (e:=ctx_env(s))]

for cat,ws in PROTO_MEMBERS.items():
    real=[e for s in sents for w in ws
          if w in s and len(s)<60 for e in [ctx_env(s)] if e]
    # 该句是否包含其他类词？排除，避免混合类污染"该类真实语境"
    other=[x for c2,ws2 in PROTO_MEMBERS.items() if c2!=cat for x in ws2]
    real=[e for s in sents for w in ws
          if w in s and not any(o in s for o in other) and len(s)<60
          for e in [ctx_env(s)] if e]
    nreal=len(real); nneut=len(neut_env)
    real_mu=sum(score(e,PROTO[cat]) for e in real)/max(nreal,1)
    neut_mu=sum(score(e,PROTO[cat]) for e in neut_env)/max(nneut,1)
    # 重叠度：真实语境得分均值 与 中性得分分布 的 z 间隔
    mn=sum(score(e,PROTO[cat]) for e in neut_env)/max(nneut,1)
    sd=math.sqrt(sum((score(e,PROTO[cat])-mn)**2 for e in neut_env)/max(nneut,1)) or 1e-6
    z=(real_mu-mn)/sd   # 真实语境偏离中性基准几个标准差
    dist=f"真实含词={nreal}句  中性={nneut}句"
    print(f"\n[{cat}]  {dist}")
    print(f"   对{cat}原型 方向余弦: 真实语境均值={real_mu:+.3f}  "
          f"中性均值={mn:+.3f}±{sd:.3f}  偏离 z={z:+.1f}σ")
    print(f"   → {'明确可分离(z>3σ)' if z>3 else '弱可分离(1-3σ)' if z>1 else '✗ 不可分(任务错位)}'}")
