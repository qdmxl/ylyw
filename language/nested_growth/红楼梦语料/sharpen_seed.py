#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
先天种子语义分辨率锐化 (sharpen_seed)
======================================
马老师指示: 提升先天种子语义分辨率——让每个字的语义态在64维空间"立起来",
反义词分开、近义词聚拢、语境指向有效。

原理: 当前种子主导概率均值仅0.268(熵4.7), 大量字前二卦概率接近(多义平分糊在
空间中心)。锐化 = 把主导卦概率向目标区间提纯, 其余分量按比例保留(不清零,
保留合理多义尾)。

关键设计: 保留**真多义**(一个字确实双义, 如'点'=离+坎), 只压缩**噪声散布**
(50个分量各0.01的均匀尾)。判据: 若某字有多个卦概率显著(第二卦≥threshold),
视为真多义, 锐化保留其多义结构; 否则压缩到单主导。

锐化目标 t_g: 主导落于 [t_lo, t_hi], 默认 [0.42, 0.62]。
"""
import os, json
import numpy as np
from bagua64 import top_k, entropy

SEED_FILE = "seed_quantum.json"
OUT_FILE = "seed_sharpened.json"


def sharpen_dist(dist: np.ndarray, t_lo: float = 0.42, t_hi: float = 0.62,
                 keep_multi: float = 0.22) -> np.ndarray:
    """单字分布锐化。
    - t_lo/t_hi: 主导卦目标区间
    - keep_multi: 视作'真多义'的第二卦概率下限(保留其结构)
    """
    d = np.asarray(dist, dtype=float)
    d = d / d.sum()
    order = np.argsort(d)[::-1]
    g1 = order[0]; p1 = float(d[g1])
    g2 = order[1]; p2 = float(d[g2])
    # 已足够清晰 → 不动
    if p1 >= t_hi:
        return d
    # 判断真多义: 第二卦显著(≥keep_multi) 且 与前二接近(差距<0.2)
    multi = (p2 >= keep_multi) and (p1 - p2 < 0.22)
    if multi:
        # 真多义: 保持前二卦结构, 只提升主位到 t_lo, 压缩均匀尾
        t1 = np.clip(p1 / (p1 + p2) * (t_lo + (t_hi - t_lo)), t_lo, t_hi)
        # 前二卦一起提纯, 其余按比例压缩
        buf = d.copy()
        others = float(buf[order[2:]].sum()) if len(order) > 2 else 0.0
        share = others / (p1 + p2) * 0.5     # 尾压缩到原比例的一半(温和)
        s12 = t1 + min(1 - t1, p2 / (p1 + p2) * (1 - t1))
        # 归一化重建
        p_new = np.zeros(64)
        p_new[g1] = t1
        p_new[g2] = (1 - t1) * (p2 / (p1 + p2))
        # 其余分量按原相对比例填充剩余
        rem = 1 - p_new[g1] - p_new[g2]
        if len(order) > 2:
            o_sum = d[order[2:]].sum()
            if o_sum > 1e-12:
                p_new[order[2:]] = d[order[2:]] / o_sum * rem
        return p_new
    # 非多义(噪声散布): 压缩到单主导
    t1 = min(max(p1, t_lo), t_hi)
    others_total = 1 - p1
    p_new = np.zeros(64)
    p_new[g1] = t1
    rem = 1 - t1
    if others_total > 1e-12:
        p_new[order[1:]] = d[order[1:]] / others_total * rem
    else:
        p_new[g1] = 1.0
    return p_new


def to_psi(dist: np.ndarray) -> np.ndarray:
    return np.sqrt(np.clip(dist, 0, None)).astype(complex)


def main():
    with open(SEED_FILE, encoding="utf-8") as f:
        seed = json.load(f)
    print(f"读入种子 {len(seed)} 字")
    sharpened = {}
    for ch, info in seed.items():
        if "dist64" not in info:
            continue
        d_orig = np.asarray(info["dist64"], dtype=float)
        d_new = sharpen_dist(d_orig)
        psi = to_psi(d_new)
        sharpened[ch] = {
            "psi_re": [float(p.real) for p in psi],
            "psi_im": [float(p.imag) for p in psi],
            "dist64": d_new.tolist(),
            "pos": info.get("pos", []),
            "n_entry": info.get("n_entry", 1),
            "n_sense": info.get("n_sense", len(info.get("senses", []))),
            "top_ctx": info.get("top_ctx", []),
            "sharpened": True,
            "dom_orig": float(d_orig.max()),
            "dom_new": float(d_new.max()),
        }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sharpened, f, ensure_ascii=False)
    print(f"保存: {OUT_FILE} ({len(sharpened)}字)")

    # 统计前后对比
    D = np.array([info["dom_new"] for info in sharpened.values()])
    print(f"\n=== 锐化后主导分布 ===")
    for th in [0.3, 0.4, 0.5, 0.6, 0.7]:
        print(f"  主导>={th}: {np.mean(D>=th)*100:.1f}%")
    print(f"  主导均值: {np.mean(D):.3f}")
    # 抽样
    print("\n=== 抽样(锐化前后) ===")
    from bagua64 import top_k
    for ch in ["水", "火", "心", "点", "生", "死", "冷", "热", "爱", "恨"]:
        if ch in sharpened:
            o = np.asarray(seed[ch]["dist64"]); n = sharpened[ch]["dist64"]
            ot = ", ".join(f"{g}{p:.2f}" for _, p, g in top_k(o, 2))
            nt = ", ".join(f"{g}{p:.2f}" for _, p, g in top_k(np.asarray(n), 2))
            print(f"  {ch}: 原[{ot}](熵{entropy(o):.2f}) → 锐[{nt}](熵{entropy(np.asarray(n)):.2f})")


if __name__ == "__main__":
    main()
