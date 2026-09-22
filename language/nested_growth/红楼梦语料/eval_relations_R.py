#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《红楼梦》语义空间关系测试(R) —— 马老师核心: 理解=在语义空间里建立关系
=========================================================================
不再"归八卦名", 而是测**语义关系**(词态矢量间的几何):
  - 同义/近义: 高保真(fidelity高)
  - 反义/对比: 低保真(距离远)
  - 语境指向: 目标词在某句语境下, 距离变化(被推向哪类语义)

三段论证:
  R1 近义关系: 泪↔涕, 悲↔痛, 欢↔喜, 怒↔愤, 走↔奔, 明↔亮 应高fidelity
  R2 反义关系: 爱↔恨, 生↔死, 逆↔顺, 新↔旧, 冷↔热, 悲↔喜 应低fidelity
  R3 语境指向: 同上词在不同红楼句里, 与对立义参考词的fidelity变化
"""
import sys, numpy as np
from bagua64 import fidelity, cosine_sim, sem_dist, dist_to, project_onto, basis_state
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
    if ch in eng._qseeds:
        return eng._qseeds[ch]
    p = eng._dict_prior_psi(ch, "char")
    if p is not None:
        return p
    return np.full(64, 1.0 / 8.0, dtype=complex)


def word_psi_in_ctx(eng, words, target, inject=0.6):
    """目标字在句子语境下的语义态(先天起点+语境受激注入)。返回 psi。"""
    ctx = np.zeros(64, dtype=complex)
    for w in words:
        if w == target:
            continue
        if function_word(w) and len(w) == 1:
            continue
        ctx += char_prior_psi(eng, w)
    cn = np.linalg.norm(ctx)
    psi0 = char_prior_psi(eng, target)
    if cn < 1e-12:
        return psi0
    ctx_dir = ctx / cn
    return project_onto(psi0, ctx_dir, strength=inject)


def rel_fidelity(eng, ctx_words, target, refs):
    """目标词在该语境下的态 → 到各参考词的fidelity关系谱。"""
    psi = word_psi_in_ctx(eng, ctx_words, target)
    out = {}
    for refname, refchar in refs.items():
        out[refname] = fidelity(psi, char_prior_psi(eng, refchar))
    return psi, out


# ---------- 关系测试用例 ----------
SYNONYMS = [   # 近义对(红楼里应语义接近): (a,b)
    ("泪", "涕"), ("悲", "痛"), ("欢", "喜"), ("怒", "愤"),
    ("走", "奔"), ("明", "亮"), ("笑", "言"), ("哭", "啼"),
]
ANTONYMS = [   # 反义对(应语义对立): (a,b)
    ("爱", "恨"), ("生", "死"), ("逆", "顺"), ("新", "旧"),
    ("冷", "热"), ("悲", "喜"), ("起", "落"), ("入", "出"),
]


def main():
    eng, full = load_engine()
    print("=== R1 近义关系: 同义词应高保真 (fidelity 1=完全同义) ===")
    for a, b in SYNONYMS:
        if a not in eng._qseeds or b not in eng._qseeds:
            print(f"  {a}~{b}: (种子缺失)"); continue
        f = fidelity(char_prior_psi(eng, a), char_prior_psi(eng, b))
        bar = "█" * int(f * 20)
        print(f"  {a}~{b}: fid={f:.2f} {bar}")

    print("\n=== R2 反义关系: 反义词应激保真 (0=完全对立) ===")
    for a, b in ANTONYMS:
        if a not in eng._qseeds or b not in eng._qseeds:
            print(f"  {a}~{b}: (种子缺失)"); continue
        f = fidelity(char_prior_psi(eng, a), char_prior_psi(eng, b))
        bar = "█" * int((1 - f) * 20)
        print(f"  {a}~{b}: 距离={1-f:.2f}(对){bar}   fid={f:.2f}")

    print("\n=== R3 语境指向: 同词在不同红楼句, 与对立义参考的fidelity变化 ===")
    # 用'悲/喜'做对立参考, 看'泪'在'辛酸泪'(悲语境) vs '欢天喜地'(喜语境) 的指向
    cases = [
        ("泪", ["一把辛酸泪"], {"悲": "悲", "喜": "喜", "水": "水"}),
        ("泪", ["一生眼泪还他"], {"悲": "悲", "喜": "喜", "水": "水"}),
    ]
    for target, ctxs, refs in cases:
        for ctx in ctxs:
            psi, rel = rel_fidelity(eng, list(ctx), target, refs)
            s = "  ".join(f"{k}:{v:.2f}" for k, v in rel.items())
            print(f"  「{ctx}」中『{target}』 关系谱: {s}")


if __name__ == "__main__":
    main()
