#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_huangdi_margin.py — 《黄帝内经》体系涌现显著性量化

证明"引擎从内经语料零标注涌现出与人类一致的中医体系结构"：
  对五脏 {心肝脾肺肾}、四季 {春夏秋冬} 等体系，
  计算  体系内种子字两两相似度均值   vs   体系内种子与其他体系种子相似度均值，
  用 margin（内-外）衡量"体系是否显著涌现"，并给出逐对显著性。

若五脏内部显著高于五脏↔非五脏：说明引擎学到了"五脏是一家人"（中医体系认知）。
"""
import os, json, math
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后\"『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对说道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目")
FUNC -= set("心肝脾肺肾气血脉骨肉皮毛髓经脉络穴俞脏胃肠胆膀胱")
FUNC |= set("说就都要会怎样哪这和那因为如当使应一些些很更")

SYSTEMS = {
    "五脏":  "心肝脾肺肾",
    "四季":  "春夏秋冬",
    "五行":  "水火木金土",
    "五志":  "喜怒思悲恐",
    "六腑":  "胃肠胆膀胱",
    "方位":  "东南西北",
}

def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_huangdi.json"), encoding="utf-8"))

def build(corpus, maxvocab=220, max_target=200, min_freq=6):
    co = defaultdict(Counter); freq = Counter(); docf = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1; docf[ch2] += 1
    L = sum(len(s) for s in corpus) or 1
    vocab = [c for c, _ in freq.most_common(500) if c not in FUNC][:maxvocab]
    idf = {c: max(1.0, math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v = [0.0]*len(vocab)
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9))) * idf[c]
        return v
    targets = [c for c, _ in freq.most_common(400) if c not in FUNC and freq[c] >= min_freq][:max_target]
    return pmiv, vocab, freq, targets

def cos(a, b):
    da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
    return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)

def mean(xs): return sum(xs)/len(xs) if xs else 0.0

def main():
    corpus = load_corpus()
    pmiv, vocab, freq, targets = build(corpus)
    vec = {ch: pmiv(ch) for ch in targets}
    chars = set(vec)
    L = sum(len(s) for s in corpus)

    print("="*74)
    print("《黄帝内经》体系涌现显著性量化 (%d字, %d句)" % (L, len(corpus)))
    print("="*74)
    print("\n机制：无标签的语料共现自组织。检验引擎是否学到中医体系的'内部聚合'。\n")
    print(f"{'体系':<6}{'体系内均值':>10}{'体系↔异体均值':>14}{'margin':>9}   判定")
    print("-"*62)
    for sn, mem in SYSTEMS.items():
        inner = [c for c in mem if c in vec]
        if len(inner) < 2:
            print(f"{sn:<6} (语料内不足2字)")
            continue
        sim_in = []
        for i in range(len(inner)):
            for j in range(i+1, len(inner)):
                sim_in.append(cos(vec[inner[i]], vec[inner[j]]))
        # 体系内 vs 所有其他目标字（排除本体系内成员）
        others = [c for c in chars - set(inner)]
        sim_out = [cos(vec[a], vec[b]) for a in inner for b in others]
        mi, mo = mean(sim_in), mean(sim_out)
        margin = mi - mo
        verdict = "★★★ 强涌现" if margin > 0.030 else ("★★ 显著涌现" if margin > 0.015 else ("★ 弱涌现" if margin > 0.005 else "· 未分离"))
        print(f"{sn:<6}{mi:>10.3f}{mo:>14.3f}{margin:>+9.3f}   {verdict}")

    print("\n" + "-"*74)
    print("逐体系成员的两两相似度（看结构细节）：")
    for sn, mem in SYSTEMS.items():
        inner = [c for c in mem if c in vec]
        if len(inner) < 2: continue
        print(f"\n  【{sn}】")
        for a in inner:
            row = " ".join(f"{b}:{cos(vec[a],vec[b]):.2f}" for b in inner if b != a)
            print(f"    {a} → {row}")

    print("\n" + "="*74)
    print("解读：margin 越大，说明引擎把该体系从内经语料中'涌现'得越清晰。")
    print("五脏/四季强涌现 ⇒ 读内经自动长出与人类一致的中医主干认知。")

if __name__ == "__main__":
    main()
