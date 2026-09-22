#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bagua64.py — 【64卦全空间编码】类人脑语义引擎的新基底（P1）

马老师判断(1)：8卦分辨率对海量汉字/词句不够，应采用64卦结合六爻实现精准区分。

本模块确立 64 卦 = 6 爻(位)的全部 2^6=64 种排列，作为语义基元的**完整状态空间**：
  - index 0..63（十进制）↔ 6 位 {0,1}；阴爻=0，阳爻=1
  - 传统八经卦只是其中 8 个"尖峰原型"（乾=63、坤=0、离=45、坎=18…）
  - 参考 8 卦六位定义的来源（下卦3爻+上卦3爻，上为高bit），保持与
    nested_growth_semantics.YAO_BY_BAGUA / spike_quantum_polysemy.BAGUA 一致。

双用途设计（经典 + 量子同一套几何）：
  - 经典侧：字/词/句映射到一个 **64 维软概率分布** p∈[0,1]^64（Σp=1）
    → 分辨率从 8 槽位提升到 64 槽位，可表达中间态/混合卦。
  - 量子侧：同一 64 维空间对应 **6-qubit 复态向量** |ψ⟩∈ℂ^64，
    每计算基态 |index⟩ = 一卦；叠加/纠缠/测量都在这个空间做。

自带六爻变(卦变/错卦/综卦/互卦)的60 4卦转换规律工具——回应马老师"利用64卦
系统内部的丰富联系及转换规律，学习汉字系统内部的自组织规律"。

⚠️ 方法学铁律（防再犯老错）：64 卦仍远小于上万汉字，**必须组合/分布编码**，
   严禁"一字一卦"的静态映射。
"""
from __future__ import annotations
import math
from typing import Dict, List, Optional
import numpy as np

# 6 位爻（下卦在低3位，上卦在高3位 —— 与 spike 一致：index 由高bit到低bit拼）
N_QUBIT = 6
N_STATE = 1 << N_QUBIT  # 64

# ------------------------------------------------------------
# 六爻 ↔ 卦序 ↔ 卦名 基础换算
# ------------------------------------------------------------
def ba64_index_to_yao(idx: int) -> List[int]:
    """卦序 index(0..63) → 6 位爻 [下爻...,上爻...]（高位→低位）。"""
    idx = int(idx) % N_STATE
    bits = []
    for _ in range(N_QUBIT):
        bits.append(idx & 1)
        idx >>= 1
    return bits  # bits[0]=低位(初爻), bits[5]=高位(上爻)

def ba64_index_to_yao_msb(idx: int) -> List[int]:
    """高位→低位顺序的6位（与 BAGUA 字典的书写顺序一致：{'乾':[1,1,1,1,1,1]}）。"""
    low = ba64_index_to_yao(idx)
    return list(reversed(low))

def yao_to_ba64_index(yao_msb: List[int]) -> int:
    """6位爻(高位→低位) → 卦序 index(0..63)。"""
    assert len(yao_msb) == 6, f"需要6爻, got {len(yao_msb)}"
    idx = 0
    for b in yao_msb:
        idx = (idx << 1) | int(b)
    return idx

# 传统八经卦 高位→低位 (2026-08-22 修正: 兑/震/巽/艮 四卦编码曾错位, 现按标准先天
# 码上下相重重建, 使每经卦 index=3位码重复(下卦+上卦), 与 64 维空间自洽)
# 正确 index: 乾63 兑27 离45 震9 巽54 坎18 艮36 坤0
BAGUA_YAO_MSB = {
    "乾": [1,1,1,1,1,1],
    "兑": [0,1,1,0,1,1],
    "离": [1,0,1,1,0,1],
    "震": [0,0,1,0,0,1],
    "巽": [1,1,0,1,1,0],
    "坎": [0,1,0,0,1,0],
    "艮": [1,0,0,1,0,0],
    "坤": [0,0,0,0,0,0],
}

def bagua_index(bg: str) -> int:
    """八经卦卦名 → 64卦空间 index(0..63)。"""
    return yao_to_ba64_index(BAGUA_YAO_MSB[bg])

BAGUA_INDEX = {bg: bagua_index(bg) for bg in BAGUA_YAO_MSB}
# 反查：从 64 空间 index 找它是不是八经卦、是哪个
INDEX_TO_BAGUA = {v: k for k, v in BAGUA_INDEX.items()}

def index_is_bagua(idx: int) -> Optional[str]:
    """若 index 恰是八经卦原型之一，返回卦名，否则 None。"""
    return INDEX_TO_BAGUA.get(int(idx) % N_STATE)

# ------------------------------------------------------------
# 卦名（有序）——64 卦的标准名（可按需懒加载，供可读性/论文）
# ------------------------------------------------------------
# 按经传统 64 卦名（此处标出，序即"伏羲/文王"常用顺序的宫序部分，便于对照）
GUA64_NAMES = [
    "乾","坤","屯","蒙","需","讼","师","比","小畜","履","泰","否","同人","大有",
    "谦","豫","随","蛊","临","观","噬嗑","贲","剥","复","无妄","大畜","颐","大过",
    "坎","离","咸","恒","遁","大壮","晋","明夷","家人","睽","蹇","解","损","益",
    "夬","姤","萃","升","困","井","革","鼎","震","艮","渐","归妹","丰","旅","巽",
    "兑","涣","节","中孚","小过","既济","未济",
]
# 注意：上表按常见卦序计 64 个；用卦名/编号映射时以 index 为准，名字仅作人类可读参考。

# ------------------------------------------------------------
# 64 卦软分布（经典侧）
# ------------------------------------------------------------
def soft_from_bagua(bagua: str, prob: float = 1.0) -> np.ndarray:
    """某八经卦 → 64维 one-hot 软分布（peak 集中在原型，可加 prob<1 稀释）。"""
    dist = np.full(N_STATE, (1.0 - prob) / (N_STATE - 1)) if N_STATE > 1 else np.ones(N_STATE)
    idx = BAGUA_INDEX[bagua]
    dist[idx] = prob
    return dist

def soft_from_dists(dists: List[np.ndarray], weights: Optional[List[float]] = None) -> np.ndarray:
    """多个 64维分布按权重合成（多字词=字分布组合；词=义项组合）。"""
    w = weights or [1.0] * len(dists)
    acc = np.zeros(N_STATE)
    for d, wt in zip(dists, w):
        acc += wt * np.asarray(d, dtype=float)
    s = acc.sum()
    return acc / s if s > 0 else np.full(N_STATE, 1.0 / N_STATE)

def entropy(p: np.ndarray) -> float:
    """分布熵（bits）。均匀=6.0, 单点=0.0。多义并存越高熵越高。"""
    p = np.asarray(p, dtype=float)
    p = p / p.sum() if p.sum() > 0 else np.full(N_STATE, 1.0 / N_STATE)
    return float(-np.sum(p * np.log2(p + 1e-12)))


# ------------------------------------------------------------
# 语义空间关系度量（马老师：理解=在语义空间里建立关系）
# 词的语义=64维态矢量; 语义关系=矢量间几何（保真度/内积/距离）
# ------------------------------------------------------------
def norm01(psi: np.ndarray) -> np.ndarray:
    """归一化复数态矢量。"""
    psi = np.asarray(psi, dtype=complex)
    n = np.linalg.norm(psi)
    return psi / n if n > 1e-12 else psi


def fidelity(psi_a: np.ndarray, psi_b: np.ndarray) -> float:
    """量子保真度 |⟨a|b⟩|²：两词态在语义空间的重叠度(0~1, 1=同一语义)。"""
    a = norm01(np.asarray(psi_a, dtype=complex))
    b = norm01(np.asarray(psi_b, dtype=complex))
    ov = np.vdot(a, b)
    return float(np.clip(np.abs(ov) ** 2, 0.0, 1.0))


def cosine_sim(p_a: np.ndarray, p_b: np.ndarray) -> float:
    """概率分布余弦相似度（互为备选，处理概率输入）。"""
    a = np.asarray(p_a, dtype=float)
    b = np.asarray(p_b, dtype=float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.clip(a @ b / (na * nb), -1.0, 1.0))


def sem_dist(psi_a: np.ndarray, psi_b: np.ndarray) -> float:
    """语义空间距离 = 1 - fidelity (0=最近, 1=最远)。"""
    return 1.0 - fidelity(psi_a, psi_b)


def dist_to(psi: np.ndarray, targets: dict) -> dict:
    """词态 → 到各参考词/卦态的保真度(语义关系谱)。
    targets: {名字: psi或分布}. 返回 {名: fidelity}。"""
    p = norm01(np.asarray(psi, dtype=complex))
    out = {}
    for name, t in targets.items():
        t = np.asarray(t, dtype=complex)
        # 若传的是概率分布, 转成幅值近似(或直接归一内部积)
        out[name] = fidelity(p, t)
    return out


def project_onto(psi: np.ndarray, ctx_dir: np.ndarray,
                 strength: float = 0.5) -> np.ndarray:
    """词态沿语境方向做强弱投影(受激注入): 测'语境把词推多远'。"""
    p = norm01(np.asarray(psi, dtype=complex))
    d = norm01(np.asarray(ctx_dir, dtype=complex))
    proj = np.vdot(d, p) * d
    new = (1 - strength) * p + strength * proj
    return norm01(new)

def _gua64_name(i: int) -> str:
    """返回某个 64 维 index 在六爻二进制坐标下的正确卦名。
    优先用 gua64_semantics(按引擎二进制坐标, 已对齐); 回退文王序 GUA64_NAMES。
    """
    try:
        from gua64_semantics import GUA_BY_INDEX
        g = GUA_BY_INDEX.get(int(i) % N_STATE)
        if g:
            return g["name"]
    except Exception:
        pass
    return GUA64_NAMES[int(i) % N_STATE]


def top_k(p: np.ndarray, k: int = 5) -> List[tuple]:
    """Top-k 卦（index, 概率, 卦名[若有]）。用六爻二进制坐标的卦名。"""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)[::-1][:k]
    out = []
    for i in order:
        nm = index_is_bagua(i)
        out.append((int(i), float(p[i]), INDEX_TO_BAGUA.get(int(i)) or _gua64_name(i)))
    return out

# ------------------------------------------------------------
# 64 卦转换规律（六爻变 / 错·综·互·变卦）—— 自组织规律的工具
# ------------------------------------------------------------
def cuo(index: int) -> int:      # 错卦：每位取反（旁通）
    return (~int(index)) & (N_STATE - 1)

def zong(index: int) -> int:     # 综卦：上下三爻整体互换（覆卦）
    y = ba64_index_to_yao(int(index))        # [低3位=下卦, 高3位=上卦]
    lower = y[0:3]; upper = y[3:6]
    new = upper + lower                        # 上下卦互换
    return yao_to_ba64_index(list(reversed(new)))

def hu(index: int) -> int:       # 互卦：取二三四爻为下卦、三四五爻为上卦
    y = ba64_index_to_yao(int(index))         # 0..5 = 初..上
    lower = [y[1], y[2], y[3]]                 # 2,3,4 爻
    upper = [y[2], y[3], y[4]]                 # 3,4,5 爻
    new_msb = list(reversed(upper + lower))
    return yao_to_ba64_index(new_msb)

def bian(index: int, which_yi_configurable: int) -> int:
    """变卦：仅翻转第 which(1..6) 爻。"""
    y = ba64_index_to_yao(int(index))
    k = (which_yi_configurable - 1) % 6
    y[k] ^= 1
    return yao_to_ba64_index(list(reversed(y)))

def gua64_transitions(index: int) -> Dict[str, int]:
    """一卦 → 错/综/互/六爻全变 的转换映射（64卦内部关系网络的一角）。"""
    return {
        "错": cuo(index), "综": zong(index), "互": hu(index),
        "变1": bian(index, 1), "变2": bian(index, 2), "变3": bian(index, 3),
        "变4": bian(index, 4), "变5": bian(index, 5), "变6": bian(index, 6),
        "乾_对应": BAGUA_INDEX["乾"] if index == BAGUA_INDEX["坤"] else BAGUA_INDEX["坤"],
    }

# ------------------------------------------------------------
# 量子侧：6-qubit statevector（64维复态），与 64卦软分布同几何
# ------------------------------------------------------------
def basis_state(idx: int, n: int = N_QUBIT) -> np.ndarray:
    """计算基态 |index⟩（单热复向量，2^n 维）。"""
    v = np.zeros(1 << n, dtype=complex)
    v[int(idx) % (1 << n)] = 1.0
    return v

def state_of_bagua(bg: str) -> np.ndarray:
    return basis_state(BAGUA_INDEX[bg])

def superposition(senses: Dict[str, float]) -> np.ndarray:
    """字典 {卦名:先验概率} → 64维归一化叠加态 |ψ⟩=Σ_i√p_i|i⟩。"""
    amps = []
    for bg, pp in senses.items():
        amps.append((math.sqrt(pp), basis_state(BAGUA_INDEX[bg])))
    v = np.zeros(N_STATE, dtype=complex)
    tot = sum(senses.values()) or 1.0
    for a, s in amps:
        v += a / math.sqrt(tot) * s
    n = np.linalg.norm(v)
    return v / n if n > 0 else v

def prob_dist_from_state(psi: np.ndarray) -> np.ndarray:
    """量子态 → 64维测量概率分布（经典可读）。"""
    return np.abs(psi) ** 2

def projector(idx: int) -> np.ndarray:
    s = basis_state(idx)
    return np.outer(s, s.conj())

def measure_prob(psi: np.ndarray, idx: int) -> float:
    s = basis_state(idx)
    return float(abs(np.vdot(s, psi)) ** 2)

def context_project(psi: np.ndarray, idx: int) -> np.ndarray:
    """语境=投影测量：压向某卦子空间并归一（结构仍存，只是偏转）。"""
    s = basis_state(idx)
    amp = np.vdot(s, psi)
    proj = amp * s
    n = np.linalg.norm(proj)
    return proj / n if n > 0 else proj

def state_to_dist(psi: np.ndarray) -> np.ndarray:
    """把任意态归一到 64 维概率分布（便于经典融合/存储）。"""
    p = np.abs(psi) ** 2
    s = p.sum()
    return p / s if s > 0 else np.full(N_STATE, 1.0 / N_STATE)


# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 64卦全空间编码自检 ===")
    print(f"状态空间大小 = 2^6 = {N_STATE}")
    print("八经卦在64卦空间的 index：")
    for bg in ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]:
        i = BAGUA_INDEX[bg]
        print(f"  {bg}: yao={ba64_index_to_yao_msb(i)} index={i} 卦序={i+1}")
    # 转换规律
    print("\n=== 64卦转换规律（以『乾』63、『坎』18 为例）===")
    for gi in (BAGUA_INDEX["乾"], BAGUA_INDEX["坎"]):
        tr = gua64_transitions(gi)
        print(f"  index={gi} ({INDEX_TO_BAGUA.get(gi, GUA64_NAMES[gi])}):", 
              {k: (v, INDEX_TO_BAGUA.get(v, GUA64_NAMES[v])) for k, v in tr.items()})
    # 软分布
    print("\n=== 64维软分布 ===")
    d1 = soft_from_bagua("乾", 0.6); d2 = soft_from_bagua("离", 0.4)
    mix = soft_from_dists([d1, d2], [0.5, 0.5])
    print(f"乾0.6单峰 熵={entropy(d1):.3f} bits  Top3={top_k(d1,3)}")
    print(f"乾0.5+离0.5合成 熵={entropy(mix):.3f} bits  Top3={top_k(mix,3)}")
    # 量子侧
    print("\n=== 6-qubit 叠加态 ===")
    psi = superposition({"乾": 0.5, "坎": 0.5})
    print(f"|乾⟩+50% |坎⟩ 范数={np.linalg.norm(psi):.4f}  P(乾)={measure_prob(psi,BAGUA_INDEX['乾']):.3f} "
          f"P(坎)={measure_prob(psi,BAGUA_INDEX['坎']):.3f}")
    print("64卦全空间编码 OK")
