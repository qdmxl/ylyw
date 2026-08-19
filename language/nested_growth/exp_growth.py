#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_growth.py — 嵌套自增长语义系统演示实验（语义范畴归类）

核心假设演示（忠实于 YLYW 汉字语义底座）：
  喂入语料越多 → 系统繁殖出更多语义元胞（字→词嵌套，变复杂）
  → 每个元胞的 H 自学习（知几校准） → 语义范畴归类准确率(泛化)上升

任务：语义范畴归类（8 大范畴 = 八卦）
  每个汉字通过部首 → 八卦隶属度（YLYW L0 基座）→ 主导卦即范畴。
  e.g. 氵→坎(水)、火→离、木→震、土→坤、金→乾、心→离 …
  汉字结构(部首)真正的语义信息就是"语义范畴"，而非伦理学褒贬。

增长与泛化：
  - 字元胞：学习常见字的范畴（先天准确，baseline）
  - 词级繁殖：观察到字组合 → 繁殖词级元胞（嵌套在字系统之上）
  - 泛化：测试遇到"训练未见的新词组合" → 通过已学的字元胞合成判断新词范畴
  - 增长率对比：growth_off 遇新词只有字级；growth_on 繁殖词级+H学习

组合判范：每次判断 = 元胞 θ 调制六爻 → argmax 推范畴；句子 = 元胞预测众数。
"""
from __future__ import annotations
import json, os, random, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from nested_growth_semantics import NestedGrowthSemantics, DEFAULT_THETA, KEYS

# 八卦名（对应 8 维 membership 顺序）
BAGUA_NAMES = {0: "乾", 1: "兑", 2: "离", 3: "震", 4: "巽", 5: "坎", 6: "艮", 7: "坤"}
BAGUA_IDX = {v: k for k, v in BAGUA_NAMES.items()}

# ---- 汉字语义底座：部首 → 8维八卦隶属（YLYW L0 基座） ----
_decomp = None
_rfuzzy = None
def _load_bases():
    global _decomp, _rfuzzy
    if _decomp is None:
        try:
            from hanzi_decomposition import HANZI_DECOMPOSITION
        except Exception:
            HANZI_DECOMPOSITION = {}
        try:
            from decomp_to_fuzzy_map import DECOMP_TO_FUZZY_RADICAL
        except Exception:
            DECOMP_TO_FUZZY_RADICAL = {}
        _decomp = (HANZI_DECOMPOSITION, DECOMP_TO_FUZZY_RADICAL)
        with open(os.path.join(HERE, "..", "radical_fuzzy_base.json"), encoding="utf-8") as f:
            _rfuzzy = json.load(f)
    return _decomp, _rfuzzy


def char_sem_vec(ch: str):
    """汉字 → 8维八卦隶属度（部首→八卦，无部首则中性）。"""
    (HANZI_DECOMPOSITION, DECOMP_TO_FUZZY_RADICAL), rf = _load_bases()
    comps = HANZI_DECOMPOSITION.get(ch, [])
    rads = []
    for cx in comps:
        m = DECOMP_TO_FUZZY_RADICAL.get(cx)
        if m and m in rf and m not in rads:
            rads.append(m)
    if not rads:
        return [0.5] * 8
    vec = [0.0] * 8
    for r in rads:
        for j in range(8):
            vec[j] += rf[r]["membership"][j]
    return [v / len(rads) for v in vec]


def char_label(ch: str):
    """汉字的真范畴标签 = 主导卦（8类之一）。无部首返回 None。"""
    v = char_sem_vec(ch)
    if not any(abs(x - 0.5) > 0.15 for x in v):
        return None
    return BAGUA_NAMES[max(range(8), key=lambda k: v[k])]


def word_sem_yao(word: str):
    """词 → 8维语义爻向量（= 组成字八卦的合成，词系统嵌套在字系统之上）"""
    char_yaos = [char_sem_vec(c) for c in word]
    n = len(word)
    if n == 1:
        return char_yaos[0]
    return [sum(v[k] for v in char_yaos) / n for k in range(8)]


def word_label(word: str):
    """词的真范畴标签 = 组成字主导卦众数。"""
    labs = [char_label(c) for c in word]
    labs = [l for l in labs if l is not None]
    if not labs:
        return None
    cnt = defaultdict(int)
    for l in labs:
        cnt[l] += 1
    return max(cnt, key=cnt.get)


# ---------------- 语料（语义范畴归类） ----------------
def build_vocab(rnd):
    """从 radical_fuzzy examples 提取 字→范畴 库（含歧义字，保留先天错误面）。"""
    (_, _), rf = _load_bases()
    by_cat = defaultdict(list)
    for rad, info in rf.items():
        lab = BAGUA_NAMES[max(range(8), key=lambda k: info["membership"][k])]
        for ex in info.get("examples", []):
            if char_label(ex) is not None and ex not in by_cat[lab]:
                by_cat[lab].append(ex)
    vocab = {ch: cat for cat, chs in by_cat.items() for ch in chs}
    return vocab, dict(by_cat)


def build_sentences(vocab, by_cat, rnd):
    """构造句子：每句 = 同一范畴的 2-3 个词。词 = 单字 或 2字复合词。真标签=该范畴。
    2字复合词(如"江湖")用于触发词级繁殖与嵌套增长。"""
    cats = [c for c in by_cat if by_cat[c]]
    sents = []
    for _ in range(120):
        cat = rnd.choice(cats)
        pool = by_cat[cat]
        k = rnd.randint(1, 3)
        words = []
        for _ in range(k):
            c1, c2 = rnd.choice(pool), rnd.choice(pool)
            if rnd.random() < 0.6:
                # 2字复合词（触发词级繁殖）
                words.append(c1 + c2)
            else:
                words.append(c1)
        sents.append({
            "words": words,
            "label": cat,
            "chars": list("".join(words)),
        })
    rnd.shuffle(sents)
    return sents


# ---------------- 训练/预测 ----------------
def cell_yao(c):
    """元胞的真实语义六爻（词→组成字合成；字→部首八卦）"""
    return word_sem_yao(c.word)


def predict_cell(c, bias=None):
    """元胞预测范畴 = argmax(六爻 + 校准偏置 bias)。
    bias=0 时为纯先天(部首八卦argmax)；bias 由经验(知几)校准修正。"""
    yao = cell_yao(c)
    b = bias if bias is not None else [0.0] * 8
    score = [yao[k] + b[k] for k in range(8)]
    return BAGUA_NAMES[int(max(range(8), key=lambda k: score[k]))]


def vote_judge(sys_, words, growth_on, chars=None, biases=None):
    """句子预测：各词/字元胞独立判范畴，取众数。返回 (预测范畴, 参与元胞, 命中词数) """
    votes = []
    pred_cells = []
    n_word_hit = 0
    biases = biases or {}
    if growth_on and words:
        for w in words:
            if not w:
                continue
            cw = sys_.cells.get(w)
            if cw is not None:
                votes.append(predict_cell(cw, biases.get(cw.word)))
                pred_cells.append(cw)
                n_word_hit += 1
    if not votes:
        for ch in (chars or []):
            cc = sys_.cells.get(ch)
            if cc is not None:
                votes.append(predict_cell(cc, biases.get(cc.word)))
                pred_cells.append(cc)
    if not votes:
        return None, [], 0
    cnt = defaultdict(int)
    for v in votes:
        cnt[v] += 1
    return max(cnt, key=cnt.get), pred_cells, n_word_hit


def apply_bias_update(biases, cell, yao, true_label, won, lr):
    """知几校准：bias = K_calibration。判错→往正确方向拉；判对→轻微巩固。
    只修正先天不明确的判定(六爻平坦/歧义字)，不破坏先天正确。"""
    b = biases.get(cell.word)
    if b is None:
        b = [0.0] * 8
    true_i = BAGUA_IDX[true_label]
    pred_i = int(max(range(8), key=lambda k: yao[k] + b[k]))
    if won:
        # 判对：向预测方向轻微巩固（知几增强）
        b[pred_i] += 0.05 * lr
    else:
        # 判错：抬正确、压错误（知耻修正，幅度大）
        b[true_i] += 0.5 * lr
        b[pred_i] -= 0.5 * lr
    biases[cell.word] = [max(-1.0, min(1.0, x)) for x in b]


def train_and_eval(growth_on: bool, seed: int, train_frac: float = 0.6):
    rnd = random.Random(seed)
    vocab, by_cat = build_vocab(rnd)
    sents = build_sentences(vocab, by_cat, rnd)
    n = len(sents)
    cut = int(n * train_frac)
    train, test = sents[:cut], sents[cut:]

    sys_ = NestedGrowthSemantics(max_cells=400, seed=seed,
                                 alpha_q=(0.25 if growth_on else 0.0),
                                 alpha_s=(0.02 if growth_on else 0.0))
    biases = {}          # 元胞级别校准（K_calibration）
    lr = 0.4 if growth_on else 0.0

    def ensure_bias(c):
        """词元胞继承组成字的先验校准(bias)，嵌套传递知识。"""
        if c.word in biases:
            return biases[c.word]
        if len(c.word) >= 2:
            char_b = [biases.get(ch) for ch in c.word if ch in biases]
            if char_b:
                n = len(char_b)
                bias = [sum(b[k] for b in char_b) / n for k in range(8)]
                biases[c.word] = bias
                return bias
        return None

    # 字元胞种子：训练语料高频字
    char_count = defaultdict(int)
    for s in train:
        for ch in s["chars"]:
            char_count[ch] += 1
    seed_chars = [c for c, _ in sorted(char_count.items(), key=lambda x: -x[1])[:30]]
    sys_.seed(seed_chars)

    growth_curve = []
    for si, s in enumerate(train):
        if growth_on:
            cells, recs = sys_.process_sentence(s["chars"], father=None, words=s["words"])
        else:
            cells, recs = sys_.process_sentence(s["chars"], father=None)
        # 词元胞繁殖后先继承字先验，再参与判断
        if growth_on:
            for w in s["words"]:
                cw = sys_.cells.get(w)
                if cw is not None:
                    ensure_bias(cw)
        pred, pred_cells, _ = vote_judge(sys_, s["words"], growth_on,
                                         chars=s["chars"], biases=biases)
        correct = (pred == s["label"])
        # 各元胞独立反馈（知几/知耻）：判对自己范畴→赢，错→输
        for c in pred_cells:
            yao = cell_yao(c)
            c.record_decision_learn(yao)
            pred_ok = (predict_cell(c, biases.get(c.word)) == s["label"])
            c.commit_game(won=pred_ok)
            # 知几校准偏置（仅 growth_on 时学习）
            if growth_on:
                apply_bias_update(biases, c, yao, s["label"], pred_ok, lr)
        if si % 10 == 0 or si == len(train) - 1:
            growth_curve.append({"step": si, "cells": len(sys_.cells),
                                 "active": sys_.complexity()["active_cells"]})

    # 测试段：泛化（不学习）
    correct = 0
    test_curve = []
    unseen_word_hits = 0
    for si, s in enumerate(test):
        if growth_on:
            cells, recs = sys_.process_sentence(s["chars"], father=None, words=s["words"])
        else:
            cells, recs = sys_.process_sentence(s["chars"], father=None)
        # 测试段也允许词元胞继承字先验(只继承不更新，公平泛化)
        if growth_on:
            for w in s["words"]:
                cw = sys_.cells.get(w)
                if cw is not None:
                    ensure_bias(cw)
        pred, pred_cells, nwh = vote_judge(sys_, s["words"], growth_on,
                                           chars=s["chars"], biases=biases)
        ok = (pred == s["label"])
        correct += ok
        unseen_word_hits += nwh
        test_curve.append({"step": si, "correct": ok,
                           "acc": correct / (si + 1),
                           "cells": len(sys_.cells)})

    return {
        "growth_on": growth_on, "seed": seed,
        "n_train": len(train), "n_test": len(test),
        "test_acc": correct / len(test),
        "complexity": sys_.complexity(),
        "growth_curve": growth_curve,
        "test_curve": test_curve,
        "word_cells": [w for w, c in sys_.cells.items() if len(w) >= 2],
        "cell_samples": [{"w": c.word, "e": c.encounters, "wins": c.wins, "losses": c.losses,
                          "theta": c.theta_dict()} for w, c in sys_.cells.items()
                         if len(c.word) >= 2],
    }


if __name__ == "__main__":
    print("=== 嵌套自增长语义系统实验（语义范畴归类） ===\n")
    print("--- 静态H (growth_off, α=0, 不繁殖词级元胞) ---")
    r_off = train_and_eval(growth_on=False, seed=0, train_frac=0.6)
    print(f"测试准确率: {r_off['test_acc']*100:.1f}%   n_train={r_off['n_train']} n_test={r_off['n_test']}")
    print(f"元胞总数: {r_off['complexity']['total_cells']}  词级元胞: {len(r_off['word_cells'])}")

    print("\n--- 自增长H (growth_on, α>0, 繁殖词级元胞) ---")
    r_on = train_and_eval(growth_on=True, seed=0, train_frac=0.6)
    print(f"测试准确率: {r_on['test_acc']*100:.1f}%   n_train={r_on['n_train']} n_test={r_on['n_test']}")
    print(f"元胞总数: {r_on['complexity']['total_cells']}  词级元胞: {len(r_on['word_cells'])}")

    with open("results_growth.json", "w", encoding="utf-8") as f:
        json.dump({"static": r_off, "growth": r_on}, f, ensure_ascii=False, indent=2)
    print("\n已保存 results_growth.json")
