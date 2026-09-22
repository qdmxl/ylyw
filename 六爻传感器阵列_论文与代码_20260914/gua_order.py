#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gua_order.py —— 卦序映射工具（修正语言引擎的卦序隐患）

背景:
  语言引擎 hanzi_engine.py 中, 64卦分布 -> 8卦(八卦)的降维使用了
  `bagua[i // 8]` 的假设, 即"文王序每8个连续卦对应一个八卦位"。
  经核对, 该假设【错误】:
     文王序第0-7卦 = 乾/坤/屯/蒙/需/讼/师/比  (并非八卦)
  正确做法: 按卦的【上卦】(或下卦)归类到八卦。

本模块提供:
  1. TRIGRAM_SYMBOL: 八卦符号 -> 卦名索引(0..7, 对应 BAGUA 顺序)
  2. hex64_to_bagua8(): 用正确的上卦归类把64维分布降维到8维
  3. 分宫卦象次序(京房八宫)生成器 —— 用于"卦变序列"建模
"""
import numpy as np

# 与 hanzi_engine.BAGUA 完全一致的顺序
BAGUA = ["乾","兑","离","震","巽","坎","艮","坤"]

# 八卦符号 -> 索引
SYMBOL_TO_IDX = {
    "☰": 0,  # 乾
    "☱": 1,  # 兑
    "☲": 2,  # 离
    "☳": 3,  # 震
    "☴": 4,  # 巽
    "☵": 5,  # 坎
    "☶": 6,  # 艮
    "☷": 7,  # 坤
}

# 三爻位(binary, bit0=下) -> 索引;  用于从六爻反推
TRIGRAM_BITS_TO_IDX = {
    0b111: 0,  # 乾
    0b011: 1,  # 兑
    0b101: 2,  # 离
    0b001: 3,  # 震
    0b110: 4,  # 巽
    0b010: 5,  # 坎
    0b100: 6,  # 艮
    0b000: 7,  # 坤
}


def build_upper_map():
    """64卦(文王序 index) -> 上卦八卦索引(0..7)。
    通过 RuleBase 的 upper_lower 符号建立。
    """
    import sys, os
    sys.path.insert(0, os.path.expanduser("~/MXL/科研/ylyw/api_docs"))
    from ylyw_core.hexagram_rules import Hexagram, HexagramRuleBase
    hr = HexagramRuleBase()
    m = {}
    for i in range(64):
        ul = hr.get_rule(Hexagram(i)).get("upper_lower", ("?", "?"))
        up_sym = ul[0]
        m[i] = SYMBOL_TO_IDX.get(up_sym, -1)
    # 校验: 每个八卦各得8卦
    from collections import Counter
    c = Counter(m.values())
    assert all(c.get(k, 0) == 8 for k in range(8)), f"上卦归类不平衡: {c}"
    return m


def hex64_to_bagua8(dist64, mode="upper", normalize=True):
    """把64维卦象分布按【上卦/下卦】降维为8维八卦分布。"""
    m = _UPPER_MAP if mode == "upper" else _LOWER_MAP
    b8 = [0.0] * 8
    for i in range(64):
        gi = m.get(i, -1)
        if gi >= 0:
            b8[gi] += dist64[i]
    if normalize:
        mx = max(b8) if max(b8) > 0 else 1.0
        b8 = [v / mx for v in b8]
    return b8


def yao6_to_bagua8(yao, mode="upper"):
    """6维爻向量([0..5]=初..上, 值∈[0,1] 越大越阳) -> 8维八卦隶属度。
    上卦 = 爻[3,4,5], 下卦 = 爻[0,1,2]。
    用各卦的"连续隶属度"软匹配: 每个三爻组合(共8种)的似然。
    """
    if len(yao) < 6:
        yao = list(yao) + [0.5] * (6 - len(yao))
    seg = yao[3:6] if mode == "upper" else yao[0:3]
    b8 = [0.0] * 8
    for bits, idx in TRIGRAM_BITS_TO_IDX.items():
        p = 1.0
        for k in range(3):
            want_yang = (bits >> k) & 1
            v = max(0.0, min(1.0, seg[k]))
            p *= v if want_yang else (1 - v)
        b8[idx] = p
    s = sum(b8) or 1.0
    return [v / s for v in b8]


# ---------------- 分宫卦象次序(京房八宫) ----------------
TRIGRAM_ORDER = ["乾","兑","离","震","巽","坎","艮","坤"]
TRIGRAM_BITS = {"乾":0b111,"兑":0b011,"离":0b101,"震":0b001,
                "巽":0b110,"坎":0b010,"艮":0b100,"坤":0b000}


def bagong_sequence():
    """返回 [(宫, 序号0..7, 卦六爻bit, 名称), ...] 长度64。
    序号: 0本宫 1一世 2二世 3三世 4四世 5五世 6游魂 7归魂
    """
    def flip(q, i): return q ^ (1 << i)
    def tname(q, which):
        v = q & 0b111 if which == "下" else (q >> 3) & 0b111
        for n, b in TRIGRAM_BITS.items():
            if b == v: return n
        return "?"
    out = []
    for pal in TRIGRAM_ORDER:
        q0 = TRIGRAM_BITS[pal] | (TRIGRAM_BITS[pal] << 3)
        cur = q0
        qs = [q0]
        for k in range(1, 6):
            cur = flip(cur, k - 1); qs.append(cur)
        cur = flip(cur, 3); qs.append(cur)
        inner = TRIGRAM_BITS[pal]
        qs.append((cur & 0b111000) | inner)
        labels = ["本宫","一世","二世","三世","四世","五世","游魂","归魂"]
        for k, q in enumerate(qs):
            out.append((pal, k, q, labels[k]))
    return out


_BAGONG = bagong_sequence()
# 六爻bit -> 分宫序全局索引(0..63)
BAGONG_INDEX = {q: i for i, (pal, k, q, lab) in enumerate(_BAGONG)}
# 六爻bit -> (宫, 世序label)
BAGONG_LABEL = {q: (pal, lab) for pal, k, q, lab in _BAGONG}


def bagong_index_from_yao(yao_bits6):
    """六爻bit(bit0=初) -> 分宫序索引 0..63"""
    return BAGONG_INDEX.get(yao_bits6 & 0b111111, -1)


def hamming(a, b):
    """两个六爻bit的汉明距离(= 相差的爻数, 卦变步长)"""
    return bin((a ^ b) & 0b111111).count("1")


_UPPER_MAP = build_upper_map()
_LOWER_MAP = None  # 需要时再建


def build_lower_map():
    import sys, os
    sys.path.insert(0, os.path.expanduser("~/MXL/科研/ylyw/api_docs"))
    from ylyw_core.hexagram_rules import Hexagram, HexagramRuleBase
    hr = HexagramRuleBase()
    m = {}
    for i in range(64):
        ul = hr.get_rule(Hexagram(i)).get("upper_lower", ("?", "?"))
        m[i] = SYMBOL_TO_IDX.get(ul[1], -1)
    return m


if __name__ == "__main__":
    print("== 上卦归类校验(每卦8个) ==")
    from collections import Counter
    print(Counter(_UPPER_MAP.values()))
    print("\n== 分宫卦象次序(前16) ==")
    for pal, k, q, lab in _BAGONG[:16]:
        bits = "".join("1" if (q >> i) & 1 else "0" for i in range(6))
        print(f"  {pal}宫 {lab:4s} [{bits}]")
    print("\n== 汉明距离测试 ==")
    seq = [q for _, _, q, _ in _BAGONG[:8]]
    print("乾宫相邻卦汉明距离:", [hamming(seq[i], seq[i+1]) for i in range(7)])
