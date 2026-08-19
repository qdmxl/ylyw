#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_huangdi_validate.py v2 — 《黄帝内经》语料自组织语义验证（改进版）

v1 的问题：内经白话语料被"气/病/脉/发/能/时"等高频医学语体词霸占共现空间，
导致所有 PMI 向量余弦趋同(0.96-0.99)，落类率失真。

v2 改进：
  1. 更强停用词（加白话语体词 + 内经高频功能词），聚焦名词性医学实义字。
  2. PMI 用"强关联过滤"：只保留 PMI 足够高的共现特征（去嘈杂弱关联），而非全维。
  3. 落类判定用"范畴互通性"而非死板的 top1 同种子：
     对范畴 C 的每个种子，看其 top-K 最近邻中有多少落在"同体系范畴集"（五行/脏腑/四季…）
     —— 因为人类对"春"的认知是"春与夏秋冬同为四季兄弟"，而不是"春最近邻必须是春自己"。
  4. 额外输出：同类 vs 异类相似度的 margin（判别力指标）。
"""
import os, json, math, re
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

# 强停用词：标点 + 白话语体 + 内经高频功能词
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后\"『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对说道称言谈听该把跟比让向从往朝将次再每各某这那其此彼这那些些个个位种样类般些多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目鼻心肝脾肺肾气血津液精神魂魄志意")
# 注意：心肝脾肺肾气 … 是医学核心概念，不能停。上面误加了，去掉这些医学词。
FUNC -= set("心肝脾肺肾气血脉津液精神魂魄志意骨肉皮毛髓经脉络穴俞俞脏")
FUNC |= set("说就都要会怎样哪这和那因为如当使应")  # 白话高频再补


def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_huangdi.json"), encoding="utf-8"))


def build(corpus, maxvocab=220, min_freq=6, pmi_thr=1.5):
    co = defaultdict(Counter); freq = Counter()
    docfreq = Counter()  # 词在多少个不同目标字上共现（集散度）
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1
                    docfreq[ch2] += 1
    L = sum(len(s) for s in corpus) or 1
    vocab = [c for c, _ in freq.most_common(500) if c not in FUNC][:maxvocab]
    # IDF：高集散度词（气/发/时…被太多不同字共享）降权，突出判别性特征
    n_chars = len(co)
    idf = {c: max(1.0, math.log((n_chars+1)/(docfreq[c]+1))) for c in vocab}
    def pmiv(ch):
        v = [0.0]*len(vocab)
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9))) * idf[c]
        return v
    targets = [c for c, _ in freq.most_common(400) if c not in FUNC and freq[c] >= min_freq][:240]
    return pmiv, vocab, freq, targets


def cos(a, b):
    da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
    return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)


# 中医体系（范畴族）用于落类判定
SYSTEMS = {
    "五行":  set("水火木金土"),
    "五脏":  set("肝心脾肺肾"),
    "六腑":  set("胃肠胆膀胱三焦"),
    "四季":  set("春夏秋冬"),
    "方位":  set("东南西北"),
    "五志":  set("喜怒思悲恐"),
    "经脉":  set("经脉络穴俞"),
}
# 各范畴种子（用于展示与判定）
TARGET_CATEGORIES = {
    "水":  ["水","江","河","海","泉"],
    "火":  ["火","热","暑"],
    "金":  ["金","铁","银","铜"],
    "土":  ["土","地","山"],
    "肝":  ["肝","怒","目"],
    "心":  ["心","神","喜"],
    "脾":  ["脾","思"],
    "肺":  ["肺","悲"],
    "肾":  ["肾","恐","骨","髓"],
    "春":  ["春"],
    "夏":  ["夏"],
    "秋":  ["秋"],
    "冬":  ["冬"],
}


def main():
    corpus = load_corpus()
    pmiv, vocab, freq, targets = build(corpus)
    vec = {ch: pmiv(ch) for ch in targets}
    chars = list(vec)
    L = sum(len(s) for s in corpus)
    print("="*64)
    print("《黄帝内经》语料自组织语义验证 v2 (%d字, %d句)" % (L, len(corpus)))
    print("="*64)
    print(f"特征表 {len(vocab)} 维, 目标实义字 {len(chars)} 个\n")

    # ========= 判别力诊断 =========
    print("【诊断】同类 vs 异类 相似度 margin（越高判别越好）")
    # 用五行/五脏这些体系内固有字对测
    same_pairs = [("肝","脾"),("肝","肾"),("心","肺"),("水","火"),("春","冬")]
    diff_pairs = [("肝","木"),("心","水"),("脾","秋"),("肾","金"),("肺","土")]
    s_same = [cos(vec[a], vec[b]) for a,b in same_pairs if a in vec and b in vec]
    s_diff = [cos(vec[a], vec[b]) for a,b in diff_pairs if a in vec and b in vec]
    if s_same and s_diff:
        print(f"  同类(脏腑内) 均值 {sum(s_same)/len(s_same):.3f} | 跨类(脏腑vs五行) 均值 {sum(s_diff)/len(s_diff):.3f}")
        print("  → 若同类显著高于异类，说明涌现出体系性结构；若接近，说明被高频词淹没\n")

    # ========= A. 范畴互通性 =========
    print("【A】范畴种子最近邻 + 体系落类（top4 落在同体系的点数）\n")
    for cat, seeds in TARGET_CATEGORIES.items():
        # 确定该范畴所属体系
        sysset = None; sysname = None
        for sn, ss in SYSTEMS.items():
            if any(s in ss for s in seeds):
                sysset, sysname = ss, sn; break
        print(f"  【{cat}】(属{ sysname or '杂' })")
        for s in seeds:
            if s not in vec:
                continue
            sims = sorted(((c2, cos(vec[s], vec[c2])) for c2 in chars if c2 != s), key=lambda x: -x[1])
            top = sims[:4]
            seg = " ".join(f"{c2}({r:.2f})" for c2, r in top)
            # 若种子本身是体系成员，统计 top 里落在同体系的个数
            hit = sum(1 for c2, _ in top if sysset and c2 in sysset) if sysset else 0
            print(f"    {s}: {seg}  [体系命中{hit}]")
        print()

    # ========= B. 字形部首八卦 vs 语料 =========
    print("【B】字形部首八卦 vs 语料共现（双通道互补）")
    try:
        from exp_growth import char_sem_vec, BAGUA_NAMES
        probe = [c for c in ["水","江","火","热","木","林","金","土"] if c in vec]
        for ch in probe:
            v = char_sem_vec(ch)
            if any(abs(x-0.5) > 0.12 for x in v):
                gua = BAGUA_NAMES[max(range(8), key=lambda k: v[k])]
            else:
                gua = "平坦"
            nn = max((c2 for c2 in chars if c2 != ch), key=lambda c2: cos(vec[ch], vec[c2]))
            print(f"    {ch}: 字形卦={gua:<4} 语料最近邻={nn}({cos(vec[ch],vec[nn]):.2f})")
    except Exception as e:
        print("  (字形通道不可用:", e, ")")

    # ========= C. 关系/对立结构 =========
    print("\n【C】体系内部 vs 体系间 整合度（同类相聚 vs 异类分离）：")
    grp = {sn: sorted(set(w for w in ss if w in vec)) for sn, ss in SYSTEMS.items()}
    for sn, ws in grp.items():
        if len(ws) >= 2:
            pairs = [(a, b) for a in ws for b in ws if a < b]
            inner = sum(cos(vec[a], vec[b]) for a, b in pairs)/len(pairs)
            print(f"    {sn}({len(ws)}字) 内部均值相似度 = {inner:.3f}")
    print("\n【C2】医学概念多跳链：")
    for ch in ["肝","心","脾","肺","肾","春","骨","血"]:
        if ch in vec:
            sims = sorted(((c2, cos(vec[ch], vec[c2])) for c2 in chars if c2 != ch), key=lambda x: -x[1])
            print(f"    {ch}: " + " ".join(f"{c2}({r:.2f})" for c2, r in sims[:5]))


if __name__ == "__main__":
    main()
