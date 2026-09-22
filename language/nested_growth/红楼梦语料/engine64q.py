#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine64q.py — 【量子主管线引擎】经典引擎量子化改造 (Q-Main)

马老师(09-46)：经典引擎改为量子的，不要再保留经典主管线。

本文件把 engine64.py 的择义/内化核心从"经典义项硬切"改造为
**6-qubit 量子叠加态 + 测量** 的主管线：

  经典 engine64（弃用主管线）           量子 engine64q（新主管线）
  ─────────────────────────────────  ─────────────────────────────
  词胞存义项列表 senses[], 硬切激活一个  词胞存 6-qubit 叠加态 |ψ⟩(64维复向量)
  多义=义项列表                     多义=叠加(α|离⟩+β|坎⟩+…), 天然并存
  语境=经典度匹配选义项               语境=**测量算子**(投影偏转), 概率变结构永存
  词义=激活义项分布                  词义=测量得到64维概率分布
  学习=义项收敛/新增(列表操作)        学习=受控量子演化(酉/测量偏转并入知识)

核心量子机制(回应马老师判断5：量子易理自生成+自学习+64卦内化)：
  - 多义不坍缩：词态保持叠加；语境只是测量偏转，不硬切
  - 语境测量：句语境转成"目标方向"|target⟩，词态向 target 弱测量
  - 基础义保护：字典本义对应卦方向作"保护方向"，测量更新受尺度约束
  - 自学习内化：测量结果作为学习信号，调整词态朝被语境激发的卦方向演化

⚠️ 方法与军规
  - 量子主管线只存叠加态(复向量)，不维护"义项列表"硬切
  - 64卦=6-qubit；经典64维分布=叠加态的测量概率(可观察量期望)
  - 经典承载大规模记忆(词表/字典先验初始化)，量子承载语义表达与择义
"""
from __future__ import annotations
import json, math, os
from typing import Dict, List, Optional, Tuple
import numpy as np

from bagua64 import (N_STATE, soft_from_bagua, top_k, entropy,
                     BAGUA_INDEX, superposition, context_project,
                     state_to_dist, measure_prob)
from dict_prior import char_senses, word_senses, function_word


# ============================================================
# 量子元胞：状态 = 6-qubit 叠加态
# ============================================================
class QuantumCell:
    """量子语义元胞：核心状态是 6-qubit 叠加态 |ψ⟩∈ℂ^64。

    psi     : 64维复振幅向量（词胞语义的量子态，多义并存）
    base_psi: 字典本义的量子态（保护方向，学习不覆盖）
    prior   : 64维先验概率分布（从字典初始化，用于测量分布/复杂度）
    """
    __slots__ = ("word", "level", "parents", "children", "psi", "base_psi",
                 "born_step", "id", "pos", "domain", "encounters", "last_step")

    def __init__(self, word: str, level: str = "char",
                 parents: Optional[List["QuantumCell"]] = None,
                 base_psi: Optional[np.ndarray] = None,
                 born_step: int = 0, cid: int = 0):
        self.word = word
        self.level = level
        self.parents = parents or []
        self.children = []
        self.psi = np.zeros(N_STATE, dtype=complex)
        if base_psi is not None:
            self.psi = base_psi.copy()
        # 字典本义态（保护方向）
        self.base_psi = base_psi.copy() if base_psi is not None else None
        self.born_step = born_step
        self.id = cid
        self.pos = "N/A"
        self.domain = "N/A"
        self.encounters = 0
        self.last_step = 0

    # --- 观测：测量概率分布（64卦可读） ---
    def psi_dist(self) -> np.ndarray:
        """叠加态 → 64维测量概率分布。"""
        return state_to_dist(self.psi)

    def dom(self) -> Tuple[int, str, float]:
        t = top_k(self.psi_dist(), 1)[0]
        return (t[0], t[2], t[1])

    def ent(self) -> float:
        return entropy(self.psi_dist())

    def __repr__(self):
        try:
            gi, gn, gp = self.dom()
        except Exception:
            gi, gn, gp = -1, "?", 0
        return f"<QCell '{self.word}' [{self.level}] 主导=({gi},{gn},{gp:.2f}) 熵={self.ent():.2f}bit>"


# ============================================================
# 量子主管线引擎
# ============================================================
class Engine64Q:
    """64卦量子主管线引擎：以 6-qubit 叠加态为核心表达，语境=测量。"""

    def __init__(self, seed: int = 0, measure_strength: float = 0.5,
                 learn_rate: float = 0.25, base_guard: float = 0.6,
                 purity_floor: float = 0.30, purity_boost: float = 0.35,
                 prior_decay: float = 40.0):
        """
        prior_decay: 先天先验随使用证据的衰减率（马老师：不怕初始有错，靠后续学习修正）。
        base_guard 不是锁定初始归属，而是随 encounters 增多而减弱拉力——
        初期靠先天种子，中期语料逐渐接手，后期语料主导，允许初始错误被修正。
        """
        self.rng = np.random.default_rng(seed)
        self.cells: Dict[str, QuantumCell] = {}
        self.step = 0
        self._cid = 0
        self.measure_strength = measure_strength  # 语境测量强度 t
        self.learn_rate = learn_rate              # 学习并入率
        self.base_guard = base_guard              # 初始本义保护强度
        self.purity_floor = purity_floor          # 主导卦权重下限(防弥散)
        self.purity_boost = purity_boost          # 弥散收缩强度
        self.prior_decay = prior_decay            # 先验随证据衰减率(越大衰减越慢)
        self._qseeds: Dict[str, np.ndarray] = {}  # 词典型种子(64量子态)

    # ---------- 出生：字典先验 → 叠加态初始化 ----------
    def _dict_prior_psi(self, w: str, level: str) -> Optional[np.ndarray]:
        """字典先验 → 叠加态。多义 = 多个卦方向的叠加（不切义）。"""
        senses = char_senses(w) if level == "char" else word_senses(w)
        if senses is None or len(senses) == 0:
            from dict_prior import radical_prior64, prior64_semantic
            # 优先64卦语义命中(具体卦位, 激活56维); 回退8经卦部首路由
            sem = prior64_semantic(w)
            if sem is not None:
                return np.sqrt(np.asarray(sem, dtype=float)).astype(complex)
            r = radical_prior64(w)
            if r is None:
                return None
            # 单方向叠加
            return np.sqrt(np.asarray(r, dtype=float)).astype(complex)
        # 多义 → 把每个义项主导卦按其强度叠加
        weights = {}
        for s in senses:
            d = s["dist64"]
            gi, gp, gn = top_k(d, 1)[0]
            weights[gn] = weights.get(gn, 0.0) + gp * s.get("strength", 0.8)
        tot = sum(weights.values()) or 1.0
        weights = {k: v / tot for k, v in weights.items()}
        return superposition(weights)

    def load_quantum_seed(self, path: Optional[str] = None):
        """词典学习出的量子种子初始化（方案A：先天知识）。
        用 seed_quantum.json 的每字量子态覆盖 dict_prior 手写先验。
        """
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "seed_quantum.json")
        if not os.path.exists(path):
            print(f"  [预警] 量子种子不存在: {path}")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        n = 0
        for ch, info in data.items():
            if "psi_re" in info and "psi_im" in info:
                psi = np.array(info["psi_re"], dtype=complex) \
                      + 1j * np.array(info["psi_im"], dtype=complex)
            else:
                psi = np.sqrt(np.asarray(info["dist64"], dtype=float)).astype(complex)
            if abs(np.linalg.norm(psi) - 1.0) > 1e-3:
                psi = psi / (np.linalg.norm(psi) + 1e-12)
            self._qseeds[ch] = psi
            n += 1
        print(f"  [量子种子] 已加载 {n} 字的词典先天知识")

    def ensure(self, w: str, level: str = "char",
               parents: Optional[List[QuantumCell]] = None) -> QuantumCell:
        if w not in self.cells:
            base_psi = None
            # 1) 优先词典型量子种子(先天知识)
            if w in self._qseeds:
                base_psi = self._qseeds[w].copy()
            # 2) 其次 dict_prior 手写先验
            if base_psi is None:
                base_psi = self._dict_prior_psi(w, level)
            if base_psi is None:
                # 无字典先验 → 均匀叠加（低先验）
                base_psi = np.full(N_STATE, 1.0 / math.sqrt(N_STATE), dtype=complex)
            c = QuantumCell(w, level=level, parents=parents,
                            base_psi=base_psi, born_step=self.step, cid=self._cid)
            self._cid += 1
            self.cells[w] = c
            if parents:
                for p in parents:
                    p.children.append(c)
            return c
        c = self.cells[w]
        if parents and all(p not in c.parents for p in parents):
            c.parents.extend(parents)
            for p in parents:
                p.children.append(c)
        return c

    def ensure_char(self, w: str) -> List[QuantumCell]:
        return [self.ensure(ch, "char") for ch in w]

    def ensure_word(self, w: str) -> QuantumCell:
        char_cells = self.ensure_char(w)
        if w not in self.cells:
            # 词级：优先词典种子，其次 dict 先验，其次继承字父辈叠加
            base_psi = None
            if w in self._qseeds:
                base_psi = self._qseeds[w].copy()
            if base_psi is None:
                base_psi = self._dict_prior_psi(w, "word")
            if base_psi is None:
                acc = sum(c.psi for c in char_cells)
                acc = acc / (np.linalg.norm(acc) + 1e-12)
                base_psi = acc
            c = QuantumCell(w, level="word", parents=char_cells,
                            base_psi=base_psi, born_step=self.step, cid=self._cid)
            self._cid += 1
            self.cells[w] = c
            for cc in char_cells:
                cc.children.append(c)
            return c
        return self.cells[w]

    # ---------- 语境 = 测量（核心量子机制） ----------
    @staticmethod
    def _ctx_direction(sent_psi: np.ndarray) -> np.ndarray:
        """句语境方向：取句叠加态自身（或归一），作为测量目标方向。"""
        return sent_psi / (np.linalg.norm(sent_psi) + 1e-12)

    def measure_update(self, cell: QuantumCell, ctx_dir: np.ndarray):
        """把词态向语境方向做弱测量：psi = (1-t)·psi + t·proj(ctx_dir)。

        proj(ctx_dir)|psi⟩ = ⟨ctx_dir|psi⟩·|ctx_dir⟩   (投影到语境方向)
        混合后归一。此操作**偏转概率但不破坏多义结构**（抗坍缩）。
        """
        if np.linalg.norm(ctx_dir) < 1e-9:
            return
        proj = np.vdot(ctx_dir, cell.psi) * ctx_dir
        new = (1 - self.measure_strength) * cell.psi + self.measure_strength * proj
        n = np.linalg.norm(new)
        cell.psi = new / n if n > 1e-12 else cell.psi

    def learn_evolve(self, cell: QuantumCell, ctx_dir: np.ndarray):
        """自学习内化：把语境知识并入词态（受字典本义保护约束）。

        量子要点：纯投影测量只能强化词态中**已有**的卦分量（不同卦基态正交，
        ⟨坎|离⟩=0），所以不能凭空制造新义。
        故采用**开放系统演化+受激注入**：
          psi' = (1-η)·[测量偏转psi] + η·[注入语境方向振幅]
        - 测量偏转：强化与语境一致的分量（抗坍缩，保留多义）
        - 受激注入：把语境方向(新义)的振幅引入词态，实现"学新义/切义"
        - base_guard：事后拉回字典本义，防基础义被洗白
        η(learn_strength)=本义冲突时降权，多义性保留。
        """
        # 1) 测量偏转：proj 到语境方向（仅保留/强化一致分量）
        proj = np.vdot(ctx_dir, cell.psi) * ctx_dir
        measured = (1 - self.measure_strength) * cell.psi + self.measure_strength * proj
        # 2) 受激注入：引入语境方向振幅（可学新义/切义）
        #    与词态当前主导方向越不同，注入越需克制（防无脑跳义）
        strength = self.learn_rate
        evolved = (1 - strength) * measured + strength * ctx_dir
        n = np.linalg.norm(evolved)
        if n > 1e-12:
            cell.psi = evolved / n
        # 3) 基础义保护（自适应衰减：初期靠先天，证据越多先天拉力越弱）
        #    马老师重点：不怕初始归属有错，后续语料逐步修正。base_guard 不能
        #    永远锁定错误的初始种子，而要随 encounters(证据) 衰减，让位给语料。
        base = cell.base_psi
        if base is not None and np.linalg.norm(base) > 1e-9:
            # 衰减因子: encounters 越多，先验拉力越小 (证据充分后语料主导)
            eff_guard = self.base_guard / (1.0 + cell.encounters / self.prior_decay)
            if eff_guard > 1e-3:
                cell.psi = (cell.psi + eff_guard * base) / \
                    (np.linalg.norm(cell.psi + eff_guard * base) + 1e-12)
        # 4) 弥散约束(防量子态无限扩散/主导弱化)
        self._contract_dominant(cell)

    def _contract_dominant(self, cell: QuantumCell):
        """弥散收缩：主导卦跌破下限时向**先天base方向**温和提纯(保留多义尾)。

        对照实验关键发现(2026-08-22)：提纯锚"当前主导"会在长时间尺度上
        把语料的微弱偏斜雪崩放大(水坎被"人说玉宝"拉成乾0.42)。而锚"先天base"
        (水坎/火离/木巽/金乾 先天主导本就正确)能保住先天。
        故：提纯方向**始终参考先天base**(防语料绑架)，强度温和(方案C)。
        """
        # 锚点: 先天base主导方向(防语料偏斜绑架)；无base才回退当前主导
        base = cell.base_psi if cell.base_psi is not None else cell.psi
        ga, gap, _ = top_k(state_to_dist(base), 1)[0]
        d = state_to_dist(cell.psi)
        gp = float(d[ga])
        if gp >= self.purity_floor:
            return                      # 先天主导方向仍清晰，不干预
        # 提纯强度随证据温和爬升(方案C): 早期≈floor, 后期→floor*1.4(cap0.5)
        prog = min(1.0, cell.encounters / max(1.0, self.prior_decay))
        t_g = self.purity_floor + (self.purity_floor * 0.4) * prog
        t_g = min(t_g, 0.50)
        # 非锚点分量按原比例缩放到 (1-t_g)
        others = d.copy(); others[ga] = 0.0
        s_others = others.sum()
        if s_others < 1e-12:
            return
        others = others / s_others * (1 - t_g)
        p_new = others.copy(); p_new[ga] = t_g
        # 重建振幅(保留各分量原相位)
        phases = np.ones(64, dtype=complex)
        for k in range(64):
            if np.abs(cell.psi[k]) > 1e-12:
                phases[k] = cell.psi[k] / np.abs(cell.psi[k])
        new = phases * np.sqrt(np.clip(p_new, 0, None))
        cell.psi = new / (np.linalg.norm(new) + 1e-12)

    def process_sentence(self, words: List[str]) -> Dict:
        """句子 → 各词量子态 + 句量子态（张量/叠加合成）。"""
        self.step += 1
        word_cells = [self.ensure_word(w) for w in words if w]
        for c in word_cells:
            c.last_step = self.step
            c.encounters += 1
        # 句量子态 = 各词叠加态之和（语境测量方向）
        sent_psi = sum(c.psi for c in word_cells)
        sn = np.linalg.norm(sent_psi)
        sent_psi = sent_psi / sn if sn > 1e-12 else sent_psi
        return {"word_cells": word_cells, "sent_psi": sent_psi,
                "sent_dist": state_to_dist(sent_psi)}

    def learn_sentence(self, words: List[str], win: int = 2):
        """会话级学习：每个非虚词词胞向【邻词局部语境】做测量内化。

        关键(回应经典版病灶)：用邻词窗口叠加态作测量方向，而非整句均值——
        整句方向消歧结构被稀释。邻词方向保留局部消歧信息。
        """
        result = self.process_sentence(words)
        cells = result["word_cells"]
        for i, c in enumerate(cells):
            if function_word(c.word) and len(c.word) == 1:
                continue
            # 邻词窗口词态叠加 → 测量方向（目标词除外，且排除低语义内容字）
            lo, hi = max(0, i - win), min(len(cells), i + win + 1)
            neigh = [cells[j].psi for j in range(lo, hi) if j != i
                     and not (function_word(cells[j].word) and len(cells[j].word) == 1)]
            if neigh:
                ctx_psi = sum(neigh)
            else:
                ctx_psi = result["sent_psi"]   # 孤立词回退整句
            ctx_dir = self._ctx_direction(ctx_psi)
            if np.linalg.norm(ctx_dir) < 1e-9:
                continue
            self.learn_evolve(c, ctx_dir)
        return result

    # ---------- 复杂度 / 持久化 ----------
    def complexity(self) -> Dict:
        return {
            "total_cells": len(self.cells),
            "char_cells": sum(1 for c in self.cells.values() if c.level == "char"),
            "word_cells": sum(1 for c in self.cells.values() if c.level == "word"),
            "avg_entropy": sum(c.ent() for c in self.cells.values()) / max(1, len(self.cells)),
        }

    def snapshot(self) -> Dict:
        cells = []
        for c in self.cells.values():
            cells.append({
                "word": c.word, "level": c.level, "id": c.id,
                "psi": c.psi.tolist(),
                "base_psi": (c.base_psi.tolist() if c.base_psi is not None else None),
            })
        return {"step": self.step, "cells": cells}

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.snapshot(), f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 量子主管线引擎 自检 ===")
    eng = Engine64Q(seed=1)
    for w in ["点", "江河", "的", "火", "心"]:
        c = eng.ensure_word(w)
        gi, gn, gp = c.dom()
        print(f"  『{w}』[{c.level}] 主导=({gi},{gn},{gp:.2f}) 熵={c.ent():.2f}bit "
              f"(字典先验叠加态)")
    # 量子择义：不同语境下『点』主导变化
    print("\n  量子择义（语境=局部测量偏转, 结构永存）:")
    for sent in ["点火做饭", "雨水点滴", "点头示意", "三点了"]:
        # 重建点位（用量子初始态重测，避免累积）
        eng = Engine64Q(seed=1)
        eng.ensure_word("点")
        eng.learn_sentence(list(sent))
        gi, gn, gp = eng.cells["点"].dom()
        # 检查多义结构是否保留（P水/火 是否都>0）
        d = eng.cells["点"].psi_dist()
        p_li = d[BAGUA_INDEX["离"]]; p_kan = d[BAGUA_INDEX["坎"]]
        print(f"    『{sent}』→ 点主导=({gi},{gn},{gp:.2f}) | P(离/火)={p_li:.2f} P(坎/水)={p_kan:.2f}")
    print("\n  量子主管线引擎 OK（多义叠加+语境测量）")
