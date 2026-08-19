#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_calibrated.py — 《红楼梦》语境→语义类别判别 · 度量校准版（方案甲）

修复三个真实问题：
 1. 【平值余弦陷阱】金=乾=[0.79*6]平值向量与任何整体偏高语境天然高余弦
      → 用"中心化余弦"（先去均值），平值向量归一化为零向量，公平化。
 2. 【哈希污染】_stable_yao 的哈希回退对无义字产生维间系统偏差，
     环境污染语境聚合 → 只聚合"真部首语义字"（走了部首通道的），过滤哈希噪声。
 3. 【判别可信度】中性语境应回归中性 → 用"不含目标类词的随机句"做基线对照。

输出：逐类别 语境→语义类别 判别准确率 + 中性基线，诚实展示"哪些类已涌现、哪些还不行"。
"""
import re, sys, math, random
from collections import Counter

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")   # nested_growth/, language/
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

PROTO = {"水":"水", "火":"火", "木":"树", "金":"金", "土":"山"}
def yao(w): return NG._stable_yao(w)
def is_sem(w): return NG._radical_yao(w) is not None

def center(v):
    m = sum(v)/len(v); return [x-m for x in v]
def cos_c(a, b):
    a=center(a); b=center(b)
    na=math.sqrt(sum(x*x for x in a)) or 1.0
    nb=math.sqrt(sum(x*x for x in b)) or 1.0
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(a,b))/(na*nb)

def env_of(s):
    acc = [yao(ch) for ch in s if is_sem(ch)]
    if len(acc) < 2: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]

def guess(s):
    env = env_of(s)
    if not env: return None
    return max(PROTO, key=lambda c: cos_c(env, yao(PROTO[c])))

def main():
    print(f"红楼句子: {len(sents)}  →  校准度量: 中心化余弦 + 只聚合部首语义字")
    print("═"*58)
    print("① 中性基线对照（不含任何涉类词）")
    res = Counter(); neut=0
    STOP = set("水雨泪酒江火烛树花金山石尘")
    for s in sents:
        if any(w in s for w in STOP):
            continue
        g = guess(s)
        if g: res[g]+=1; neut+=1
    print(f"   中性语境 {neut} 句 → 分布: " + ", ".join(f"{c}:{res[c]} ({res[c]/max(neut,1)*100:.0f}%)" for c in PROTO) )
    print()
    print("② 逐类判别（挖掉目标词后，语境能否猜中该词所属语义类别）")
    print("─"*58)
    tests = {
        "水类":["江","河","海","溪","泉","水","雨","泪","酒"],
        "火类":["火","烛","灯","焰"],
        "木类":["树","林","枝","花"],
        "土石类":["山","石","尘","土"],
    }
    overall_ok = overall_tot = 0
    for cat, ws in tests.items():
        ok=tot=0
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:30]:
                g = guess(s.replace(w,""))
                if g:
                    tot+=1; overall_tot+=1
                    if g==cat[0]: ok+=1; overall_ok+=1
        print(f"   {cat}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%   (随机≈20-25%)")
    print("─"*58)
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%")

if __name__ == "__main__":
    main()
