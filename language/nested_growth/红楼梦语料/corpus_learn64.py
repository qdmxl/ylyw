#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corpus_learn64.py — 【红楼梦真实语料 · 自生成+知识内化测试】(P6)

马老师判断(4)：随着小说、医典等大量阅读，内化的基础汉字知识得到应用，
能更加丰富对汉语的理解。这正是语义引擎应具备的架构。

本脚本用红楼梦全文的一部分做**受控的自学习内化实验**：
  1. 让 Engine64 通读一定量红楼句子（作为词序列喂入）
  2. 观察：词胞义项库如何从"字典先验"被真实语料**丰富/收敛/新增**（内化）
  3. 验证四级结构(字→词→句)在长文本上的自生成复杂度增长
  4. 报告关键词（火/水/心/点/打…）的义项进化

不是追数字，而是验证"阅读→内化→语义变丰富"的类人脑学习闭环是否成立。
"""
from __future__ import annotations
import re, sys, time
from typing import Dict, List
import numpy as np

from engine64 import Engine64
from bagua64 import top_k, entropy
from dict_prior import word_senses, char_senses, function_word

# 简单分词：按标点切分句子，取句子为词列表（原型用，不引大分词器）
def split_sentences(text: str) -> List[List[str]]:
    text = re.sub(r'\s+', '', text)
    sents = re.split(r'[。！？；\n，、：""''（）【】]', text)
    return [list(s) for s in sents if len(s) >= 2]


def load_hlm(path: str, limit_sent: int) -> List[List[str]]:
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    sents = split_sentences(raw)
    return sents[:limit_sent]


def e_internalization(eng: Engine64, sents: List[List[str]]):
    print("\n" + "=" * 66)
    print("E-A · 红楼梦阅读 → 知识内化（词胞义项库从字典先验被语料丰富）")
    print("=" * 66)
    # 追踪几个看过字典先验的词，观察语料内化后义项变化
    track = ["火", "水", "心", "点", "白", "金"]
    before = {}
    for w in track:
        # 预建词胞（用字典先验初始化），记录初始义项数
        c = eng.ensure_word(w)
        before[w] = len(c.senses)
    print(f"  阅读前字典先验义项数: {before}")

    n_sent = 0
    for sent in sents:
        eng.learn_sentence(sent, segment=True)   # 保守词切分 + 局部语境内化
        n_sent += 1
    print(f"  已通读 {n_sent} 句(词切分内化)")

    after = {w: len(eng.cells[w].senses) for w in track if w in eng.cells}
    print(f"  阅读后义项数: {after}")
    print(f"  内化增量: { {w: after[w] - before.get(w, 0) for w in after} }")
    print("\n  各追踪词主导卦（字典先验→语料内化后）:")
    for w in track:
        if w in eng.cells:
            c = eng.cells[w]
            gi, gn, gp = c.dom_gua()
            print(f"    『{w}』主导=({gi},{gn},{gp:.2f}) 义项数={len(c.senses)} "
                  f"各义项主导={[top_k(s['dist64'],1)[0][2] for s in c.senses]}")


def e_complexity_growth(eng: Engine64, sents: List[List[str]]):
    print("\n" + "=" * 66)
    print("E-B · 自生成复杂度增长（字→词→句四级网络）")
    print("=" * 66)
    comp = eng.complexity()
    print(f"  通读后系统规模: {comp}")
    print(f"  平均每词义项数: {comp['avg_senses']:.2f}")
    print(f"  → 语料阅读使字胞/词胞繁殖、义项累积，语义网络变丰富（类人脑生长）")


def e_sentence_understanding(eng: Engine64):
    print("\n" + "=" * 66)
    print("E-C · 内化后句层语义理解（读红楼后再判新句）")
    print("=" * 66)
    # 读完整本红楼后，测试它对新句子的语义倾向
    test_sents = [
        "火光照亮了房间",
        "河水缓缓流淌",
        "他心里十分激动",
        "她用木梳梳理头发",
        "金钗在阳光下闪烁",
    ]
    for sent in test_sents:
        r = eng.process_sentence(list(sent))
        top = top_k(r["sent_dist"], 3)
        disp = ", ".join(f"{t[2]}({t[1]:.2f})" for t in top)
        print(f"    『{sent}』 → 句主导: {disp}")


def main():
    hlm = "/home/lijinhan/MXL/科研/ylyw/language/nested_growth/红楼梦语料/红楼梦_全文.txt"
    LIMIT = 8000   # 先通读前8000句（足够海量观察内化）
    print("红楼梦全篇自学习+知识内化测试")
    print(f"通读语料: 前 {LIMIT} 句")
    t0 = time.time()
    sents = load_hlm(hlm, LIMIT)
    print(f"加载 {len(sents)} 句，耗时 {time.time()-t0:.1f}s")
    eng = Engine64(seed=0)
    e_internalization(eng, sents)
    e_complexity_growth(eng, sents)
    e_sentence_understanding(eng)
    print("\n" + "=" * 66)
    print("红楼梦内化测试完成")
    print("=" * 66)


if __name__ == "__main__":
    main()
