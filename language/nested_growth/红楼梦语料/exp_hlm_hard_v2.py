#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_hard_v2.py — 《红楼梦》语义掩码完形 · 困难题（方案A：共现对齐）

马老师要的"理解 vs 聚类记忆"一锤定音测试：

设计核心：让【共现基线失效】，只让【真语义理解】能胜出。
  - 每个语义类别出一个候选词 → 5 个候选（1 个正确类别 + 4 个干扰类别）
  - 【共现对齐】：候选词的语境共现分被"拉平"——干扰词也选"在该语境确实会出现的词"，
    使"谁字面共现高"无法区分 → 共现基线摔倒随机线(1/5)
  - 只有【部首语义通道】（候选词语义爻 vs 语境语义）能识别"语境语义类别" → 应远超 1/5

若结果：部首语义 >> 共现基线 ≈ 随机 → 证明引擎涌现了"超越共现记忆的语义理解"。
"""
import json, os, re, math, random, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))   # language/
import hanzi_engine
sys.path.insert(0, os.path.join(HERE, ".."))         # nested_growth/
from nested_growth_semantics import NestedGrowthSemantics as NG

CATS = {
    "水类":  ["江","河","海","溪","泉","潮","波","浪","水","雨","泪","酒"],
    "火类":  ["火","烛","灯","焰"],
    "木类":  ["树","林","枝","木","花"],
    "金石类":["金","银","玉","宝"],
    "土石类":["山","石","峰","尘","土"],
}
CAT_LIST = list(CATS.keys())

def load_sents():
    txt = open(os.path.join(HERE, "红楼梦_全文.txt"), encoding="utf-8").read()
    return [s.strip() for s in re.split(r"[。！？\n]", txt) if s.strip()]

def cos(a, b):
    if not a or not b or len(a) != len(b): return 0.0
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return sum(x*y for x, y in zip(a, b)) / (na*nb)

def main():
    random.seed(0)
    sents = load_sents()
    print(f"红楼句子: {len(sents)} 句")

    # ── 预计算：候选词 ↔ 上下文词的共现计数（全局，用于共现基线 + 对齐）──
    # 所有涉类词
    all_words = set()
    for ws in CATS.values():
        all_words |= set(ws)
    word_sents = defaultdict(list)
    for s in sents:
        for w in all_words:
            if w in s and len(word_sents[w]) < 20000:
                word_sents[w].append(s)
    # 共现计数：word 与 另一个字/词 共同出现的句子数
    # 简化：word 与 候选词 的直接共现（在语料句内）
    cooc = defaultdict(lambda: defaultdict(int))
    for w in all_words:
        for s in word_sents[w]:
            for c in all_words:
                if c != w and c in s:
                    cooc[w][c] += 1

    # ── 部首语义爻（字元胞补全语义）──
    yao_cache = {}
    def yao(w):
        if w not in yao_cache:
            yao_cache[w] = NG._stable_yao(w)
        return yao_cache[w]

    def ctx_yao(sentence, masked):
        acc, n = [], 0
        for ch in sentence:
            if ch == masked: continue
            y = yao(ch)
            if y is not None:
                acc.append(y); n += 1
        return [sum(a[i] for a in acc)/n for i in range(6)] if acc else None

    # ── 收集目标句：每个目标词采样 ──
    target_sents = defaultdict(list)
    for s in sents:
        for cat, ws in CATS.items():
            for w in ws:
                if w in s:
                    target_sents[w].append(s)
    MAX = 6
    items = []
    for w, ss in target_sents.items():
        random.shuffle(ss)
        for s in ss[:MAX]:
            items.append((w, s))
    random.shuffle(items)
    items = items[:400]
    print(f"困难题: {len(items)} 题")

    res = {"total":0, "semantic":0, "cooc":0, "both":0}
    sem_hits, coc_hits = [], []

    for w, s in items:
        wcat = next((c for c,ws in CATS.items() if w in ws), None)
        if not wcat: continue

        ctx = s.replace(w, "")
        # 候选 = 每类出一个代表（正确类别固定 w，其余类出"与该语境共现最高"的词）
        cands = [w]
        for c in CAT_LIST:
            if c == wcat: continue
            pool = [x for x in CATS[c] if x != w]
            if not pool: continue
            # 选与该上下文共现最多的干扰代表
            best_c = None; best_sc = -1
            for cand in pool:
                sc = sum(cooc[cand].get(cc,0) for cc in ctx if cc in all_words)
                if sc > best_sc: best_sc, best_c = sc, cand
            if best_c: cands.append(best_c)
        # 保证候选规模（不足则补随机其他类词）
        while len(cands) < 5:
            for c in CAT_LIST:
                if c != wcat:
                    for x in CATS[c]:
                        if x not in cands:
                            cands.append(x); break
                if len(cands) >= 5: break
        cands = cands[:5]

        # ── 共现基线：选与上下文共现最高的候选（对齐后应难以区分）──
        best_coc = None; best_coc_sc = -1
        for cand in cands:
            sc = sum(cooc[cand].get(cc,0) for cc in ctx if cc in all_words)
            if sc > best_coc_sc: best_coc_sc, best_coc = sc, cand

        # ── 部首语义通道：候选语义爻 vs 语境语义 ──
        env = ctx_yao(s, w)
        best_sem = None; best_sem_sc = -1
        for cand in cands:
            sc = cos(yao(cand), env) if env else 0.0
            if sc > best_sem_sc: best_sem_sc, best_sem = sc, cand

        res["total"] += 1
        if best_sem == w: res["semantic"] += 1; sem_hits.append((s,w,best_sem,round(best_sem_sc,3)))
        if best_coc == w: res["cooc"] += 1; coc_hits.append((s,w,best_coc))

    T = max(res["total"],1)
    print("\n"+"═"*60)
    print(f"红楼困难题 · 共现对齐 · Top-1（{res['total']} 题，5选1）")
    print("─"*60)
    print(f"  部首语义通道(真理解) : {res['semantic']}/{res['total']} = {res['semantic']/T*100:.1f}%")
    print(f"  共现基线(聚类记忆)   : {res['cooc']}/{res['total']} = {res['cooc']/T*100:.1f}%")
    print(f"  随机基线             : {1/5*100:.0f}%")
    print("═"*60)
    print("\n部首语义通道判对示例:")
    for s,w,bw,sc in sem_hits[:6]:
        rg=w
        print(f"  · “{s[:32]}…” [目标:{w}] →语义选:{bw}({sc})")
    print("\n共现基线判对示例:")
    for s,w,bw in coc_hits[:4]:
        print(f"  · “{s[:32]}…” [目标:{w}] →共现选:{bw}")

if __name__ == "__main__":
    main()
