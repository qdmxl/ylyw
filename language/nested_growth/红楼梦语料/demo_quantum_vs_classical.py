#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_quantum_vs_classical.py — 【量子化 YLYW 语义理解 demo】

把量子择义接回 YLYW 字→词→句语义链，与经典引擎实测对比。

量子语义链：
  字/部首 → 卦基态 |卦⟩（6-qubit 计算基态）
  词      → 多义**叠加态** |词⟩ = Σ_i √p_i |卦_i⟩（义项并存，不切义）
  句      → 句态 |句⟩ = Σ_词 c_word·|词⟩（词态叠加，语义合成）
  语境    → 投影测量（用邻词/语境卦筛选测量概率）
  判卦    → 测句态得到各卦概率，概率最高者 = 句的语义卦

与经典对比（同批含部首词句子）：
  经典：word_sem_yao 整词部首爻 → 句均值 → 判卦
  量子：词的叠加态 → 句叠加态 → 测量 |火>|水>|木>... 概率 → 判卦

预期差异点：
  经典易"切片/单卦坍缩"（今天多义管线的顽疾）
  量子各卦概率始终健康分布（除语境强压），多义结构永存
"""
import re, sys, random, math
import numpy as np
from collections import Counter
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(7)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

# ---- 量子基础设施（6-qubit statevector）----
BG = list(NG.YAO_BY_BAGUA)
def bits_of(bg): return NG.YAO_BY_BAGUA[bg]
def basis_index(bits):
    idx = 0
    for b in bits: idx = (idx << 1) | int(round(b))
    return idx
_BASIS = {}   # bg -> 计算基态(64维单热)
for bg in BG:
    v = np.zeros(2**6, dtype=complex); v[basis_index(bits_of(bg))] = 1.0; _BASIS[bg] = v

def proj(bg): s=_BASIS[bg]; return np.outer(s, s.conj())
def p_of(state, bg): return float(abs(np.vdot(_BASIS[bg], state))**2)
def normalize(v):
    n = np.linalg.norm(v); return v/n if n > 1e-12 else v

# ---- 词 → 叠加态 ----
def word_state(w) -> np.ndarray:
    """词 = 其各卦先验叠加。用 word_sem_yao 的爻做成卦概率分布。
    每爻值作为对应卦的先验强度(略作 0/1 化的软概率)。"""
    y = NG.word_sem_yao(w)
    if y is None or y == NG.NEUTRAL_YAO:
        return None
    # 把爻向量映射到 8 卦先验: 距离越近强度越大
    pri = {}
    for bg in BG:
        # 乾坤中位偏; 六卦余弦
        if bg == "乾": pri[bg] = max(0.0, sum(y)/6 - 0.5)
        elif bg == "坤": pri[bg] = max(0.0, 0.5 - sum(y)/6)
        else:
            m = sum(y)/6
            dy = [(x-m) for x in y]
            ny = math.sqrt(sum(x*x for x in dy)) or 1e-9
            bb = bits_of(bg); mb = sum(bb)/6
            db = [x-mb for x in bb]
            nb = math.sqrt(sum(x*x for x in db)) or 1e-9
            pri[bg] = max(0.0, sum(a*b for a,b in zip(dy,db))/(ny*nb))
    tot = sum(pri.values())
    if tot < 1e-9:
        return None
    state = np.zeros(2**6, dtype=complex)
    for bg, s in pri.items():
        if s > 0: state += math.sqrt(s/tot) * _BASIS[bg]
    return normalize(state)

# ---- 句 → 句叠加态 ----
def sentence_state(words) -> np.ndarray:
    """句态 = 各词叠加态之和(语义合成)。跳过实体/无语义词。"""
    acc = []
    for w in words:
        s = word_state(w)
        if s is not None: acc.append(s)
    if not acc: return None
    total = np.zeros(2**6, dtype=complex)
    for s in acc: total += s
    return normalize(total)

def quantum_guess(words):
    st = sentence_state(words)
    if st is None: return None
    probs = {bg: p_of(st, bg) for bg in BG}
    return max(probs, key=probs.get), probs

# ---- 经典对照 ----
def classical_guess(words):
    acc = []
    for w in words:
        y = NG.word_sem_yao(w)
        if y is not None and y != NG.NEUTRAL_YAO: acc.append(y)
    if not acc: return None
    env = [sum(a[i] for a in acc)/len(acc) for i in range(6)]
    return max(BG, key=lambda b: NG.bscore(env, b))

# ---- 分词 ----
big = Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT, encoding="utf-8").read()): big[m] += 1
common = [w for w,c in big.most_common(3000) if c >= 25]
WORDK = set(NG.ENTITY_WORDS) | set(common)
def seg(s):
    i=0; out=[]
    while i < len(s):
        m=None
        for ln in range(min(4, len(s)-i), 0, -1):
            w=s[i:i+ln]
            if w in WORDK: m=w; break
        if m: out.append(m); i += len(m)
        else: out.append(s[i]); i += 1
    return out

# ---- 测试句：各卦部首词 ----
TEST_W = {
 "坎": ["水","雨","泪","江","河","海","溪"],
 "离": ["火","烛","灯","焰","热","晴","照"],
 "巽": ["树","林","枝","森","梁","柱"],
 "乾": ["金","银","钱","珠","宝","玉"],
 "坤": ["地","城","墙","尘","壤"],
 "艮": ["山","石","峰","峦","峻"],
}
def build():
    ts=[]
    for bg, ws in TEST_W.items():
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<50]
            random.shuffle(ss)
            for s in ss[:20]: ts.append((bg, w, s))
    return ts
TS = build()

def main():
    print(f"量子化YLYW vs 经典：句层判别对比  测试句={len(TS)}\n")
    # 量子
    qok=q_tot=0; qper={}; qdist=Counter()
    for bg,w,s in TS:
        words=seg(s.replace(w,""))
        g=quantum_guess(words)
        if g:
            gl,_=g; qdist[gl]+=1; q_tot+=1; qok+=(gl==bg); qper.setdefault(bg,[0,0]); qper[bg][1]+=1; qper[bg][0]+=(gl==bg)
    # 经典
    cok=c_tot=0; cper={}; cdist=Counter()
    for bg,w,s in TS:
        g=classical_guess(seg(s.replace(w,"")))
        if g: cdist[g]+=1; c_tot+=1; cok+=(g==bg); cper.setdefault(bg,[0,0]); cper[bg][1]+=1; cper[bg][0]+=(g==bg)
    print(f"量子: {qok}/{q_tot}={qok/max(q_tot,1)*100:.0f}%   判别分布={dict(qdist)}")
    print(f"经典: {cok}/{c_tot}={cok/max(c_tot,1)*100:.0f}%   判别分布={dict(cdist)}")
    print(f"\n逐卦准确率（量子 vs 经典）:")
    print(f"{'卦':<4}{'量子':<12}{'经典':<12}")
    for bg in TEST_W:
        a=qper.get(bg,[0,0]); b=cper.get(bg,[0,0])
        print(f"  {bg}: {a[0]}/{a[1]}({a[0]/max(a[1],1)*100:.0f}%)  {b[0]}/{b[1]}({b[0]/max(b[1],1)*100:.0f}%)")
    print("\n判别分布多样性(信息熵, 越均分越高越健康):")
    def entropy(dist):
        import math
        tot=sum(dist.values()); 
        return -sum((c/tot)*math.log2(c/tot) for c in dist.values() if c)
    print(f"  量子 H={entropy(qdist):.2f} bits   经典 H={entropy(cdist):.2f} bits")

if __name__ == "__main__":
    main()
