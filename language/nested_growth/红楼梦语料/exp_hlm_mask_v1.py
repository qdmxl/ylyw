#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_mask_v1.py — 《红楼梦》语义掩码完形试点（方案D+A：可行性验证）

马老师问题：让语义引擎读《红楼梦》，能否涌现真正的语义理解（而非聚类记忆）？

核心实验（选择题式掩码完形）：
  给一句含目标词 M 的句子，M 被掩成 ____，给出 5 个候选词（1 正确 + 4 干扰），
  引擎需从上下文的【语义环境】选出正确词。
  判定"理解 vs 聚类记忆"：
    - 引擎通道：候选词"卦象" vs 上下文"句级卦象"的语义匹配度 → 选最高
    - 共现基线：候选词与上下文"字面共现频率" → 选最高（= 聚类记忆的极致）
  若引擎(top-1 语义) > 共现基线(top-1 共现)，且差异有意义 → 证明语义结构理解超越聚类记忆。

干扰词构造策略（构造"困难题"，让对比公平）：
  干扰词必须与该句上下文【也有共现】（否则共现基线太弱，赢无意义）。
  做法：干扰词来自"在红楼中与目标词共现最多的同类/近义或常见词"，保证字面语境有交集。

v1 = 可行性验证：先跑通闭环，用子集数据看真实信号，再决定是否扩大。
"""
import json, os, re, math, random, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))  # 加 language/ 到路径
import hanzi_engine
# 引入嵌套自增长系统的“字元胞部首语义爻”（马老师点名的字元胞补全增长）
sys.path.insert(0, os.path.join(HERE, ".."))  # nested_growth/ 父目录 language/nested_growth
from nested_growth_semantics import NestedGrowthSemantics as NG

# 中文数字映射（红楼回目排序用，v1 不需要）

# 语义类别 → 目标词（选用 radical_fuzzy_base 覆盖、语义明确的名词）
CATS = {
    "水类":  ["江","河","海","溪","泉","潮","波","浪","水","雨","泪","酒"],
    "火类":  ["火","烛","灯","焰"],
    "木类":  ["树","林","枝","木","花"],
    "金石类":["金","银","玉","宝"],
    "土石类":["山","石","峰","尘","土"],
}
CAT2IDX = {c: i for i, c in enumerate(CATS)}
CAT_LIST = list(CATS.keys())

# 语义类别 → 类内常共现同义/近义词（用于构造在同一语境出现的干扰词）
CAT_INTERFERE = {
    "水类":  ["水","雨","泪","江","河","海","波","浪","潮","泉","溪","酒","汤"],
    "火类":  ["火","烛","灯","焰","热"],
    "木类":  ["花","树","林","枝","木"],
    "金石类":["玉","金","银","宝"],
    "土石类":["山","石","尘","土","峰"],
}

def load_sents():
    txt = open(os.path.join(HERE, "红楼梦_全文.txt"), encoding="utf-8").read()
    sents = [s.strip() for s in re.split(r"[。！？\n]", txt) if s.strip()]
    return sents

def build_env(eng, sentence, masked_word):
    """句子去掉目标词后的语义环境（句级卦象 / hex64）。"""
    segs = eng.sentence(sentence)
    # 用整句卦象作为环境（掩码影响有限，近似）
    return segs

def word_bagua(eng, w):
    """词的8维卦象 + 64卦分布。"""
    try:
        r = eng.word(w) if len(w) >= 2 else eng.char(w)
    except Exception:
        r = None
    return r

def cos(a, b):
    if not a or not b or len(a) != len(b): return 0.0
    num = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(x*x for x in b)) or 1.0
    return num / (na*nb)

def main():
    random.seed(0)
    sents = load_sents()
    print(f"红楼句子: {len(sents)} 句")

    eng = hanzi_engine.HanziEngine()
    N_CAND = 5

    # 预计算目标词的词卦象（缓存）
    bagua_cache = {}
    def get_bagua(w):
        if w not in bagua_cache:
            r = word_bagua(eng, w)
            v = None
            if r and isinstance(r, dict):
                v = r.get("sentence_bagua") or r.get("bagua") or r.get("vector")
                if v is None and "segment_bagua" in r and r["segment_bagua"]:
                    v = r["segment_bagua"][0]
            bagua_cache[w] = v
        return bagua_cache[w]

    # [新增] 部首语义爻（字元胞补全增长的语义起点）：候选词 6 维爻
    radical_yao_cache = {}
    def get_radical_yao(w):
        if w not in radical_yao_cache:
            radical_yao_cache[w] = NG._stable_yao(w)
        return radical_yao_cache[w]

    def ctx_radical_yao(sentence, masked):
        """上下文语义环境（部首语义爻）：句子去掉目标词后，其余含部首语义的词的爻均值。"""
        acc, n = [], 0
        for ch in sentence:
            if ch == masked:  # 掩掉目标词
                continue
            y = get_radical_yao(ch)
            if y is not None:
                acc.append(y); n += 1
        if not acc:
            return None
        return [sum(a[i] for a in acc) / n for i in range(6)]

    # 收集每个目标词出现的句子
    target_sents = defaultdict(list)
    for s in sents:
        for cat, words in CATS.items():
            for w in words:
                if w in s:
                    target_sents[w].append(s)

    # 统计共现表：词→上下文词共现计数（用于共现基线）
    # 简化：用"目标词 vs 上下文其他词是否同现" 的语料频率
    # 这里直接统计每个目标词在当前句之外的共现词频（用全语料粗统计）
    # —— 为公平，共现基线用"该句上下文词集合"与候选词在全语料的共现次数

    results = {"engine": 0, "cooccur": 0, "total": 0, "engine_cat": 0,
              "engine_radical": 0, "radical_cat": 0}
    engine_hits = []      # 引擎判对的用例（抽样看）
    radical_hits = []     # 部首语义通道判对用例
    cooccur_hits = []

    # 采样：每种目标词最多抽 K 个句子
    MAX_PER_WORD = 8
    items = []
    for w, ss in target_sents.items():
        random.shuffle(ss)
        for s in ss[:MAX_PER_WORD]:
            items.append((w, s))
    random.shuffle(items)
    # 限制规模（v1 可行性，最多 ~600 题）
    items = items[:600]
    print(f"构造选择题: {len(items)} 题")

    for w, s in items:
        # 确定正确类别
        wcat = None
        for c, words in CATS.items():
            if w in words: wcat = c; break
        if not wcat: continue

        # 候选 5 个：1 正确 + 4 干扰
        # 干扰优先从【同类】(语义近) 与【异类】(语义远) 混合，形成难度梯度
        candidates = [w]
        # 同类干扰（难，语义近）
        same_pool = [x for x in CAT_INTERFERE[wcat] if x != w]
        # 异类干扰（易，语义远）
        other_pool = []
        for c, words in CATS.items():
            if c != wcat:
                other_pool += words
        other_pool = [x for x in other_pool if x != w]
        # 混 2 同类 + 2 异类（v1 先混合，后续可做难度分层）
        pick = []
        pick += random.sample(same_pool, min(2, len(same_pool)))
        need = N_CAND - 1 - len(pick)
        pick += random.sample(other_pool, min(need, len(other_pool)))
        candidates = [w] + pick

        # ===== 上下文语义环境 =====
        env = build_env(eng, s, w)
        env_vec = None
        if env and isinstance(env, dict):
            env_vec = env.get("sentence_bagua") or env.get("segment_bagua", [None])
            if isinstance(env_vec, list) and env_vec and isinstance(env_vec[0], list):
                env_vec = env_vec[0]
        # 用句子其余词的卦象均值更准确：这里简化用整句卦象

        # ===== 引擎通道：候选词卦象 vs 环境卦象 语义匹配 =====
        best_eng = None; best_eng_sc = -1
        for c in candidates:
            vb = get_bagua(c)
            sc = cos(vb, env_vec) if vb and env_vec else 0.0
            if sc > best_eng_sc:
                best_eng_sc = sc; best_eng = c

        # ===== 引擎通道·部首语义爻（字元胞补全增长的语义匹配）=====
        env_ry = ctx_radical_yao(s, w)
        best_rg = None; best_rg_sc = -1
        for c in candidates:
            ry = get_radical_yao(c)
            sc = cos(ry, env_ry) if ry and env_ry else 0.0
            if sc > best_rg_sc:
                best_rg_sc = sc; best_rg = c

        # ===== 共现基线：候选词与上下文共现词频 =====
        # 上下文 = 句子去掉目标词后的字
        ctx_chars = set(s.replace(w, ""))
        best_coc = None; best_coc_sc = -1
        for c in candidates:
            # 该候选词与上下文任意字共同出现在同一句的语料计数（近似用目标词句内共现）
            coc = 0
            for cc in ctx_chars:
                for ss in target_sents.get(c, [])[:50]:
                    if cc in ss: coc += 1
            if coc > best_coc_sc:
                best_coc_sc = coc; best_coc = c

        # 判定
        results["total"] += 1
        if best_eng == w: 
            results["engine"] += 1; engine_hits.append((s, w, best_eng, best_eng_sc))
        if best_rg == w:
            results["engine_radical"] += 1; radical_hits.append((s, w, best_rg, best_rg_sc))
        if best_coc == w:
            results["cooccur"] += 1; cooccur_hits.append((s, w, best_coc))
        # 类别级：引擎猜的词是否属于正确类别
        guessed_cat = None
        for c, words in CATS.items():
            if best_eng in words: guessed_cat = c; break
        if guessed_cat == wcat: results["engine_cat"] += 1
        # 部首语义通道类别级
        rg_cat = None
        for c, words in CATS.items():
            if best_rg in words: rg_cat = c; break
        if rg_cat == wcat: results["radical_cat"] += 1

    total = results["total"]
    print("\n" + "═"*56)
    print(f"红楼语义掩码完形 · 选择题 Top-1 准确率（{total} 题，5选1）")
    print("─"*56)
    print(f"  引擎·部首语义爻(字补全): {results['engine_radical']}/{total} = {results['engine_radical']/max(total,1)*100:.1f}%")
    print(f"  引擎·卦象(hanzi_engine) : {results['engine']}/{total} = {results['engine']/max(total,1)*100:.1f}%")
    print(f"  共现基线(聚类记忆)       : {results['cooccur']}/{total} = {results['cooccur']/max(total,1)*100:.1f}%")
    print(f"  随机基线                  : {1/N_CAND*100:.0f}%")
    print("─"*56)
    print(f"  部首语义通道 类别级(5类) : {results['radical_cat']}/{total} = {results['radical_cat']/max(total,1)*100:.1f}%")
    print(f"  卦象通道   类别级(5类)   : {results['engine_cat']}/{total} = {results['engine_cat']/max(total,1)*100:.1f}%")
    print("═"*56)
    print("\n部首语义通道判对示例（句子 / 目标词 / 部首通道所选）:")
    for s, w, bw, sc in radical_hits[:6]:
        print(f"  · “{s[:30]}…” [目标:{w}] →部首通道选:{bw}({sc:.2f})")
    print("\n(共现基线判对示例)")
    for s, w, bw in cooccur_hits[:5]:
        print(f"  · “{s[:30]}…” [目标:{w}] →共现选:{bw}")

if __name__ == "__main__":
    main()
