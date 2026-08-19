#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_bianzheng_v1.py — 统一辨证判别器 v1（一期：病位 + 八纲 + 气血津液 一体）

设计（马老师 2026-08-16 拍板"三个维度一起，内在联系不割裂"）：
  中医辨证多维度本是一体（如"脾虚"同时含 病位脾+八纲虚+气虚），
  不应拆成独立分类器。引擎对输入症状**同时点亮**匹配的多维标签，输出完整辨证。
  解析：同句内病位+八纲+气血津液联合涌现；五行传变（时序）留二期。

方法：
  每辨证标签由其"代表核心字/字集"在语料中的**词级PMI强伴随词**自动学出特征词典
  （不手写种子词=纯涌现），输入症状词 → 与各标签特征匹配 → 维度内投票 → 输出多维。
  病位维度内是互斥选一（一脏），八纲/气血维度内可并出多标签（如 痰+热）。
"""
import json, math, re, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠")

# 训练语料（全13部）
TRAIN = [
    "corpus_neijing_wenyan.json","corpus_nannjing_wenyan.json","corpus_shanghan_wenyan.json",
    "corpus_jinkui_wenyan.json","corpus_bencao_wenyan.json","corpus_maijing_wenyan.json",
    "corpus_zhenjiu_jia_wenyan.json","corpus_zhenjiu_da_wenyan.json","corpus_zhongcang_wenyan.json",
    "corpus_danxi_wenyan.json","corpus_bingyuan_wenyan.json","corpus_piwei_wenyan.json",
    "corpus_wenbing_wenyan.json",
]

# 维度划分（互斥组：dim=="zang" 病位五选一；其余可并出）
# word=PWMI学习用的代表字集（语料里该字出现≈标签出现）——用于自动学特征词
LABELS = [
    dict(dim="zang",  tag="心",  cores="心"),
    dict(dim="zang",  tag="肝",  cores="肝"),
    dict(dim="zang",  tag="脾",  cores="脾"),
    dict(dim="zang",  tag="肺",  cores="肺"),
    dict(dim="zang",  tag="肾",  cores="肾"),
    dict(dim="bagang", tag="寒", cores="寒"),
    dict(dim="bagang", tag="热", cores="热"),
    dict(dim="bagang", tag="虚", cores="虚"),
    dict(dim="bagang", tag="实", cores="实"),
    dict(dim="qi",    tag="气虚", cores="气"),
    dict(dim="qi",    tag="血虚", cores="血"),
    dict(dim="qi",    tag="血瘀", cores="瘀"),
    dict(dim="qi",    tag="痰",  cores="痰"),
    dict(dim="qi",    tag="湿",  cores="湿"),
    dict(dim="qi",    tag="水停", cores="水"),
    dict(dim="qi",    tag="津亏", cores="津"),
]

def load():
    sents = []
    for f in TRAIN:
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            sents.extend(json.load(open(p, encoding="utf-8")))
    return sents

def seg_words(s):
    s = [c if c not in FUNC else '|' for c in s]
    return [p for p in ''.join(s).split('|') if p]

def build(sents):
    N = len(sents)
    docF = Counter(); docW = Counter()
    clist = "心肝脾肺肾寒热虚实气血瘀痰湿水津"  # 标签核心字全集
    docC = {c: 0 for c in clist}
    for s in sents:
        for c in clist:
            if c in s: docC[c] += 1
    # 词-核心字 共现
    co = defaultdict(Counter)
    for s in sents:
        pres = set(c for c in clist if c in s)
        for w in seg_words(s):
            for i in range(len(w)-1):
                big = w[i:i+2]
                if len(set(big)) < 2: continue
                docF[big] += 1
                for c in pres:
                    co[big][c] += 1
    # 建每标签特征词典：其核心字强PMI伴随词
    feat = {}
    for L in LABELS:
        core = L["cores"]
        scores = {}
        for w, ctr in co.items():
            c = ctr.get(core, 0)
            if c == 0: continue
            pmi = math.log((c/N)/((docF[w]/N)*(docC[core]/N)+1e-12))
            if pmi > 2:                                  # 只留强伴随（特异证候）
                scores[w] = pmi
        # 取每标签最强前K个即为其"涌现特征"
        feat[L["tag"]] = dict(sorted(scores.items(), key=lambda kv:-kv[1])[:40])
    return N, docF, docC, feat

def judge(sym, feat, N, docF, docC):
    """返回 {dim: {tag: score}} 多维标签"""
    votes = defaultdict(lambda: defaultdict(float))
    for w in set(seg_words(sym)):
        for i in range(len(w)-1):
            big = w[i:i+2]
            if len(set(big)) < 2: continue
            gold = None; gs = -1e9
            for tag, d in feat.items():
                sc = d.get(big, 0)
                if sc > gs: gs = sc; gold = tag
            if gold and gs > 0:
                L = next(l for l in LABELS if l["tag"] == gold)
                votes[L["dim"]][gold] += gs
    return votes

def pick(votes):
    out = {}
    # 病位五选一
    zang = votes.get("zang", {})
    if zang and max(zang.values()) > 0:
        out["病位"] = max(zang, key=lambda t: zang[t])
    # 八纲：可并出（但互斥对寒/热、虚/实取强者）
    bag = votes.get("bagang", {})
    if bag and max(bag.values()) > 0:
        pairs = [("寒","热"),("虚","实")]
        for a,b in pairs:
            sa=bag.get(a,0); sb=bag.get(b,0)
            if max(sa,sb)>0:
                out.setdefault("八纲",[]).append(a if sa>=sb else b)
    # 气血津液：可多并出
    q = votes.get("qi", {})
    if q and max(q.values())>0:
        out["气血津液"] = sorted([t for t,s in q.items() if s>0], key=lambda t:-q[t])[:4]
    return out

if __name__ == "__main__":
    sents = load()
    print(f"训练语料: {len(sents)}句 (全13部)")
    N, docF, docC, feat = build(sents)
    # 展示每标签涌现出的特征词
    print("\n=== 各辨证标签 语料涌现特征词(PMI>2 前6) ===")
    for L in LABELS:
        fs = list(feat[L["tag"]].keys())[:6]
        print(f"  {L['tag']:<6} {','.join(fs)}")
    # 判测试
    tests = [
        ("病位·心 八纲·热 津亏", "心火亢盛，心烦失眠，口舌生疮，小便黄，口渴咽干"),
        ("病位·肝 八纲·实", "肝郁气滞，胁肋胀痛，善太息，情志抑郁"),
        ("病位·脾 八纲·虚 气虚", "脾气虚，食少腹胀，倦怠乏力，便溏"),
        ("病位·肺 八纲·寒", "风寒犯肺，咳嗽痰白，恶寒发热，鼻塞"),
        ("病位·肾 八纲·虚 津亏", "肾阴虚，腰膝酸软，五心烦热，潮热盗汗"),
        ("病位·肝 血瘀", "肝血瘀滞，胁下刺痛，痛处固定，舌紫暗"),
        ("病位·脾 湿 水停", "脾虚湿盛，全身浮肿，腹胀，小便不利，苔腻"),
        ("病位·肺 痰 热", "痰热壅肺，咳嗽痰黄，胸闷气促，发热"),
    ]
    print("\n=== 统一辨证判别 v1 ===")
    for gold, sym in tests:
        v = judge(sym, feat, N, docF, docC)
        r = pick(v)
        zr = r.get("病位","?")
        ba = "".join(r.get("八纲",[]))
        q = " ".join(r.get("气血津液",[]))
        gz = gold.split()[0][3:]
        hit = "✓" if (zr and zr in gz) else "✗"
        print(f"  {gold}\n      «{sym}»\n      → 病位:{zr} 八纲:{ba} 气血津液:{q} {hit}")
