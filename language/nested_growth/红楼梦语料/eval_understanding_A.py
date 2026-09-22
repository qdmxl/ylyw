#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《红楼梦》理解测试(A·语境推导版)
=================================
马老师方向：评测"系统读这句时的即时理解"，不是"记忆检索"。
关键改动：目标字起点=【先天种子】(不复用已内化记忆词态)，
句语境=句中其他实词的先天psi叠加；用受激注入把目标字向语境**推**，
读出"这句话让该字偏向哪卦"。

- 纯先天+语境 => 测的是语境推导/理解能力
- 多义词应当随真实语境消歧
"""
import sys, numpy as np
from bagua64 import top_k, state_to_dist
from dict_prior import function_word

sys.path.insert(0, ".")


def load_engine():
    from engine64q import Engine64Q
    from corpus_learn64 import split_sentences
    eng = Engine64Q(seed=0, prior_decay=40)
    eng.load_quantum_seed()
    full = split_sentences(open("红楼梦_全文.txt", encoding="utf-8").read())
    return eng, full


def char_prior_psi(eng, ch):
    """取字的先天psi: 优先词典型种子, 其次dict_prior, 其次均匀。不碰已内化记忆。"""
    if ch in eng._qseeds:
        return eng._qseeds[ch]
    p = eng._dict_prior_psi(ch, "char")
    if p is not None:
        return p
    return np.full(64, 1.0 / 8.0, dtype=complex)


def infer_in_context(eng, words, target, inject=0.6):
    """给定句子(含target) → 用语境把target从先天起点推出, 返回主导卦+句主题。"""
    # 1) 句中实词语境 = 其他实词先天psi叠加
    ctx = np.zeros(64, dtype=complex)
    for w in words:
        if w == target:
            continue
        if function_word(w) and len(w) == 1:
            continue
        ctx += char_prior_psi(eng, w)
    cn = np.linalg.norm(ctx)
    ctx_dir = ctx / cn if cn > 1e-12 else None

    # 2) 目标字起点 = 先天种子
    psi0 = char_prior_psi(eng, target)
    if ctx_dir is None:
        return None, None
    # 3) 受激注入: 先天起点 + 语境方向(可学新义/切义)
    psi = (1 - inject) * psi0 + inject * ctx_dir
    n = np.linalg.norm(psi)
    psi = psi / n if n > 1e-12 else psi0
    d = state_to_dist(psi)
    gi, gp, gn = top_k(d, 1)[0]
    # 句主题(全实词先天平均)
    theme = [(g, round(p, 2)) for (_, p, g) in top_k(state_to_dist(ctx / (cn + 1e-12)) if cn > 1e-12 else np.full(64, 1 / 64), 3)]
    return (gn, gp), theme


def extract_real_sents(full, target, n=4, max_len=14):
    out = []
    for s in full:
        if target in s and 4 <= len(s) <= max_len:
            out.append("".join(s))
        if len(out) >= n:
            break
    return out


TARGETS = ["哭", "泪", "水", "火", "心", "头", "笑", "怒", "爱", "气", "情", "梦", "风", "雨", "花", "玉"]


def main():
    eng, full = load_engine()
    print("[引擎] 先天种子已载(评测用先天起点+语境, 不复用记忆)")
    for target in TARGETS:
        sents = extract_real_sents(full, target)
        if not sents:
            print(f"\n『{target}』 无合适句子"); continue
        print(f"\n{'='*66}\n『{target}』 先天+语境 即时推导 (注入强度0.6)\n{'='*66}")
        for snum, sent in enumerate(sents):
            words = list(sent)
            res, theme = infer_in_context(eng, words, target)
            if res is None:
                continue
            gn, gp = res
            # 先天本征(无语境时)
            d0 = state_to_dist(char_prior_psi(eng, target))
            g0, _, g0n = top_k(d0, 1)[0]
            mark = "≠" if gn != g0n else "="
            print(f"  句{snum}「{sent}」")
            print(f"     [先天本征:{g0n}] →[语境注入:{gn}({gp:.2f})] {mark} | 句主题:{theme}")


if __name__ == "__main__":
    main()
