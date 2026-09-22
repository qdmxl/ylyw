#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine64.py — 【64卦字典先验 · 类人脑汉语语义引擎】(P3)

整合马老师今天五条架构判断，在 64 卦全空间上实现"经典内化 + 量子增强"的
类人脑学习模型。核心突破 vs 08-21 旧引擎(nested_growth_semantics.py)：

  旧引擎问题 → 新引擎方案
  ─────────────────────────────────────────────
  ① 8卦标签(8槽位)     → ② 64卦全空间软分布(64槽位, bagua64.py)
  ③ 静态部首查表       → ④ 字典/说文先验初始化+内化(dict_prior.py)
  ⑤ 只字形语义         → ⑥ 字形(先天)+语料共现(后天) 双通道
  ⑦ 单词义项列表硬切   → ⑧ 字典义项先验 + 量子叠加/测量 择义(不坍缩)
  ⑨ 无量子             → ⑩ 6-qubit 64维 叠加/纠缠/测量 增强层

设计原则（方法学军规，防再犯老错）：
  · 字典先验 = 初始化 + 强正则（内化），不是检索库
  · 基础义保护：首义项=字典本义，学习只新增/收敛，绝不覆盖
  · 64卦远小于上万字 → 用 64维分布组合编码，严禁"一字一卦"
  · 经典承载大规模自学习；量子做高维语义增强（叠加/测量/纠缠）
  · 诚实评测，不调阈值追数字

本文件 = 主引擎（可导入 + 可跑自检）。量子增强层在 P5 单独打通。
"""
from __future__ import annotations
import json, math, os, random
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from bagua64 import (N_STATE, soft_from_bagua, soft_from_dists, top_k, entropy,
                     BAGUA_INDEX, state_of_bagua, superposition, measure_prob,
                     context_project, prob_dist_from_state, state_to_dist,
                     gua64_transitions)
from dict_prior import (char_senses, word_senses, radical_prior64,
                        function_word, char_prior_cover)


# ============================================================
# 语义元胞（64卦版）
# ============================================================
class Cell64:
    """一个语义元胞：承载 64卦语义状态 + 字典先验义项库 + 可学习参数。

    三级层次：char(字胞) < word(词胞) < sentence(句胞)
    关键属性：
      dist      : 当前激活的 64维语义分布（经典可读态）
      senses    : 义项库（每义项=64维分布 + 字典元数据），senses[0]=字典本义(保护)
      quantum   : 6-qubit 叠加态（量子层用，semantic 的复态表达）
    """
    __slots__ = ("word", "level", "parents", "children", "dist", "senses",
                 "quantum", "born_step", "id", "pos", "domain", "learned_scale",
                 "encounters", "last_step")

    def __init__(self, word: str, level: str = "char", parents: Optional[List["Cell64"]] = None,
                 senses: Optional[List[Dict]] = None, dist: Optional[np.ndarray] = None,
                 born_step: int = 0, cid: int = 0):
        self.word = word
        self.level = level
        self.parents = parents or []
        self.children = []
        self.senses = senses or []           # 义项库（[0]=字典本义）
        if dist is not None:
            self.dist = np.asarray(dist, dtype=float)
        elif senses:
            self.dist = senses[0]["dist64"].copy()
        else:
            self.dist = np.full(N_STATE, 1.0 / N_STATE)
        self.quantum = None                  # 由量子层填充
        self.born_step = born_step
        self.id = cid
        self.pos = senses[0]["pos"] if senses else "N/A"
        self.domain = senses[0]["domain"] if senses else "N/A"
        self.learned_scale = 0.0             # 语料学习对内化的贡献度
        self.encounters = 0
        self.last_step = 0

    def dom_gua(self) -> Tuple[int, str, float]:
        """当前主导卦 (index, 卦名/名, 概率)。"""
        t = top_k(self.dist, 1)[0]
        return (t[0], t[2], t[1])

    def ent(self) -> float:
        return entropy(self.dist)

    def __repr__(self):
        try:
            gi, gn, gp = self.dom_gua()
        except Exception:
            gi, gn, gp = -1, "?", 0
        return f"<Cell64 '{self.word}' [{self.level}] 主导=({gi},{gn},{gp:.2f}) 义项={len(self.senses)}>"


# ============================================================
# 64卦字典先验 · 类人脑语义引擎
# ============================================================
class Engine64:
    """主引擎：字典先验内化 + 64卦嵌套生长 + 语料双通道学习 + 量子增强接口。

    类人脑流程（对齐马老师判断）：
      出生：字/词胞用【字典先验】初始化义项库(senses)与64卦分布 →
          引擎"已学过词典"
      生长：处理语料 → 字胞→词胞→句胞 三级嵌套自生成 → 语义逐级继承
      学习：观察语料新语境 → 择义(量子测量/经典匹配) → 新义项收敛/新增
           → 字典本义(senses[0])始终保护
      量子：词/句可转为 6-qubit 叠加态做抗坍缩表达与语境测量增强
    """
    # 64 卦内化：字 → 词 → 句
    def __init__(self, seed: int = 0, proto_scale: float = 0.8):
        self.rng = random.Random(seed)
        self.cells: Dict[str, Cell64] = {}
        self.step = 0
        self._cid = 0
        self.proto_scale = proto_scale   # 部首先验强度
        # 语料非对称学习
        self.alpha_learn = 0.3           # 观察新语境并入强度
        self.new_sense_thr = 0.45        # 与既有义项匹配阈值(低=易新增)
        self.max_senses = 6

    # ---------- 出生（字典先验初始化） ----------
    def _make_cell(self, w: str, level: str, parents: Optional[List[Cell64]] = None):
        if level == "char":
            senses = char_senses(w)
        else:
            senses = word_senses(w)
        # 字典查不到 → 用部首/字源先验生成一个基础义项（非零样本：仍带先天字形语义）
        if senses is None or len(senses) == 0:
            r = radical_prior64(w)
            if r is None:
                # 组装字先验：取组字部首聚合（词级才降级到这）
                agg = []
                for ch in w:
                    cr = radical_prior64(ch)
                    if cr is not None:
                        agg.append(cr)
                r = soft_from_dists(agg) if agg else None
            if r is not None:
                senses = [{"dist64": r, "pos": "N/A", "domain": "部首先验", "strength": self.proto_scale}]
            else:
                # 彻底查不到 → 均匀(中性)，但标为弱先验(引擎"没学过这个词")
                senses = [{"dist64": np.full(N_STATE, 1.0 / N_STATE),
                           "pos": "N/A", "domain": "未知", "strength": 0.0}]
        return Cell64(w, level=level, parents=parents, senses=senses,
                      born_step=self.step, cid=self._cid)

    def ensure(self, w: str, level: str = "char",
               parents: Optional[List[Cell64]] = None) -> Cell64:
        """有则取，无则按字典先验出生。"""
        key = w
        if key not in self.cells:
            c = self._make_cell(key, level, parents)
            self._cid += 1
            self.cells[key] = c
            if parents:
                for p in parents:
                    p.children.append(c)
            return c
        c = self.cells[key]
        if parents and all(p not in c.parents for p in parents):
            c.parents.extend(parents)
            for p in parents:
                p.children.append(c)
        return c

    def reset_cell(self, w: str):
        """把词胞重置回字典先验状态（清掉语料学到的义项，用于受控多义测试）。"""
        c = self.ensure_word(w) if w not in self.cells else self.cells[w]
        senses = word_senses(w) if c.level != "char" else char_senses(w)
        if senses:
            c.senses = senses
            c.dist = senses[0]["dist64"].copy()
            c.pos = senses[0]["pos"]
            c.domain = senses[0]["domain"]
        return c

    # ---------- 三级嵌套自生成 ----------
    def ensure_char(self, w: str) -> List[Cell64]:
        outs = []
        for ch in w:
            outs.append(self.ensure(ch, "char"))
        return outs

    def ensure_word(self, w: str) -> Cell64:
        """词胞：父=组字字胞；语义=字典词先验（若词典给出），否则从字父辈继承。"""
        char_cells = self.ensure_char(w)
        c = self.ensure(w, "word", char_cells)
        # 词义刷新：词典先验优先；无则继承字父辈分布组合
        senses = word_senses(w)
        if senses and c.born_step == self.step:
            c.senses = senses
            c.dist = senses[0]["dist64"].copy()
            c.pos = senses[0]["pos"]
            c.domain = senses[0]["domain"]
        elif c.born_step == self.step and not senses:
            # 词无词典先验：从字父辈组合（先天字形通道）
            dists = [cc.dist for cc in char_cells]
            c.dist = soft_from_dists(dists)
        return c

    def process_sentence(self, words: List[str], segment: bool = False) -> Dict:
        """字胞→词胞→句胞 处理一句。返回句胞语义 + 词胞列表。

        - 默认(segment=False)：直接按传入的序列建胞。若传入字符序列 → 字级；
          若传入词序列 → 词级。受控逐字测试保持原始行为(择义正确)。
        - segment=True：对字符序列做保守词切分(仅合并已在字典/已有词胞的真词，
          绝不盲目拼三字垃圾词→见 _segment_words 说明)，用于长文本内化。
        """
        self.step += 1
        if segment and len(words) > 1 and all(len(w) == 1 for w in words):
            words = self._segment_words(words)
        word_cells = [self.ensure_word(w) for w in words if w]
        for c in word_cells:
            c.last_step = self.step
            c.encounters += 1
        # 句胞 = 词胞分布组合
        sent = Cell64("<s>" + str(self.step), level="sentence",
                      parents=word_cells, born_step=self.step, cid=self._cid)
        self._cid += 1
        dists = [c.dist for c in word_cells]
        sent.dist = soft_from_dists(dists) if dists else np.full(N_STATE, 1.0 / N_STATE)
        for wc in word_cells:
            wc.children.append(sent)
        self._last_sent = sent
        return {"word_cells": word_cells, "sent_cell": sent, "sent_dist": sent.dist}

    def _segment_words(self, chars: List[str]) -> List[str]:
        """保守词切分：只合并能证明是'真词'的双字组合。

        判据(任一)：① 已在 cells(就读过的词) ② 字典词(word_senses命中)
        ③ 两个字**同部首语义**(如氵氵=水词) → 临时合并。
        绝不盲目拼三字/乱拼(那会制造'点火做'式垃圾词,破坏择义——今天教训)。
        """
        out, i = [], 0
        n = len(chars)
        while i < n:
            # 双字真词优先（只在充分证据下合并，否则保持单字）
            if i + 1 < n:
                big = "".join(chars[i:i + 2])
                is_real = (big in self.cells) or (word_senses(big) is not None) \
                          or self._bigram_radical(big)
                if is_real:
                    out.append(big)
                    i += 2
                    continue
            out.append(chars[i])
            i += 1
        return out

    @staticmethod
    def _bigram_radical(big: str) -> bool:
        """双字是否构成真词：两字主导卦一致（同语义域，如 火+焰=离离）、
        或已在字典先验。防止乱把不同语义字拼成词。"""
        from dict_prior import radical_prior64
        a, b = radical_prior64(big[0]), radical_prior64(big[1])
        if a is None or b is None:
            return False
        # 判主导卦一致性（用 top1)
        from bagua64 import top_k
        ga = top_k(a, 1)[0][0]
        gb = top_k(b, 1)[0][0]
        return ga == gb

    # ---------- 语料学习（知识内化） ----------
    def _ctx_from_words(self, cells: List[Cell64]) -> Optional[np.ndarray]:
        """句语境 = 各词激活分布（除实体/虚词加权后的均值）。"""
        dists = [c.dist for c in cells]
        if not dists:
            return None
        return soft_from_dists(dists)

    def learn_sentence(self, words: List[str], ctx: Optional[np.ndarray] = None,
                      win: int = 2, segment: bool = False):
        """观察一句 → 对每个非虚词词胞做"知识内化"（收敛或新增义项）。

        关键(修复08-21架构问题)：择义语境改用**局部细窗口(邻词)**而非整句均值——
        整句均值语境太粗、消歧结构被稀释(昨天坍缩根因)；邻词窗口保留局部消歧信息。
        - segment=True：对字符序列做保守词切分(长文本内化用，形成词胞)
        - 只有语境足够鲜明且带明确自然卦指向才触发学习（防中性/坤污染）
        - 字典本义 senses[0] 保护(学习只收敛/新增, 不覆盖本义)
        """
        result = self.process_sentence(words, segment=segment)
        if ctx is not None:
            pass
        cells = result["word_cells"]
        for i, c in enumerate(cells):
            if function_word(c.word):
                continue          # 虚词不学语料义（语法功能由字典定）
            # 邻词窗口语境：目标词前后 win 个词的分布组合（局部消歧）
            lo, hi = max(0, i - win), min(len(cells), i + win + 1)
            neigh = [cells[j].dist for j in range(lo, hi) if j != i]
            if neigh:
                local_ctx = soft_from_dists(neigh)
            else:
                # 孤立单字词(无邻居) → 回退整句语境（词级切分的合理回退）
                local_ctx = result["sent_dist"]
            if entropy(local_ctx) > 5.5:
                continue           # 局部语境太均匀(无明显消歧结构)
            if not self._ctx_has_gua(local_ctx):
                continue           # 语境无明确自然卦指向(太多中性/坤噪) → 不学
            self._observe(c, local_ctx)
        return result

    @staticmethod
    def _ctx_has_gua(ctx: np.ndarray, min_peak: float = 0.20) -> bool:
        """语境有效性门控：是否存在一个明确的主导卦(峰显著高于均匀基线)。

        防止中性/杂混语境(主导落向坤/均匀)污染义项库——这是今天全篇测试
        发现的'义项被坤洗白'的根本门控。基线=1/64≈0.0156；要求主导峰≥min_peak
        (对64维分布而言0.20是相当强的结构)。
        zero-Kun(满0)等平坦分布被排除。
        """
        peak = float(np.max(np.asarray(ctx, dtype=float)))
        return peak >= min_peak

    def _observe(self, cell: Cell64, ctx: np.ndarray):
        """词胞知识内化：把句语境代表的语义并入义项库。"""
        # 与既有各义项匹配
        best_i, best_m = 0, -1.0
        for i, s in enumerate(cell.senses):
            m = self._dist_match(s["dist64"], ctx)
            if m > best_m:
                best_m, best_i = m, i
        if best_m >= self.new_sense_thr:
            # 并入既有义（收敛）——基础义(0)更保守
            alpha = 0.15 if best_i == 0 else self.alpha_learn
            cell.senses[best_i]["dist64"] = cell.senses[best_i]["dist64"] * (1 - alpha) + ctx * alpha
        else:
            if len(cell.senses) < self.max_senses:
                cell.senses.append({"dist64": ctx.copy(), "pos": "语料",
                                    "domain": "语料义项", "strength": self.alpha_learn})
            else:
                # 替换最不相关义项（仍保护[0]本义）
                worst = min(range(1, len(cell.senses)),
                            key=lambda i: self._dist_match(cell.senses[i]["dist64"], ctx))
                cell.senses[worst] = {"dist64": ctx.copy(), "pos": "语料",
                                      "domain": "语料义项", "strength": self.alpha_learn}
        # 激活义 = 与语境最匹配的义项（择义，不改结构）
        cell.dist = cell.senses[best_i]["dist64"].copy()
        cell.learned_scale += 1.0

    @staticmethod
    def _dist_match(a: np.ndarray, b: np.ndarray) -> float:
        """两64维分布匹配度[0,1]。用归一化重叠/内积。"""
        a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
        den = math.sqrt(a.sum() * b.sum()) or 1e-9
        return float(np.dot(a, b) / den)

    # ---------- 量子增强接口（P5 打通） ----------
    def to_quantum(self, cell: Cell64) -> np.ndarray:
        """把元胞64维分布 → 6-qubit 叠加态。
        高度多义(语义分散)的元胞天然是宽叠加 → 抗坍缩(核心价值)。"""
        p = np.asarray(cell.dist, dtype=float)
        p = p / p.sum()
        psi = np.sqrt(p).astype(complex)     # 振幅 = √概率
        return psi

    def quantum_ctx(self, sent_dist: np.ndarray, ctx_gua: str,
                    t: float = 0.5) -> np.ndarray:
        """语境弱测量：把句态压向语境卦(t=测量强度)，返回偏转后的分布。"""
        psi = np.sqrt(np.asarray(sent_dist, dtype=float))
        psi = psi / np.linalg.norm(psi)
        proj = context_project(psi, BAGUA_INDEX[ctx_gua])
        # 混合: 原始态 + 语境投影态
        mix = (1 - t) * psi + t * proj * np.sign(np.vdot(proj, psi) + 1e-9)
        return state_to_dist(mix)

    def quantum_superpose_word(self, cell: Cell64) -> np.ndarray:
        """多义词胞 → 量子叠加态（显式表达多义共存，不切义）。"""
        weights = {}
        for s in cell.senses:
            gi, gp, gn = top_k(s["dist64"], 1)[0]   # (index, prob, name)
            weights[gn] = weights.get(gn, 0.0) + gp
        # 归一
        tot = sum(weights.values()) or 1.0
        weights = {k: v / tot for k, v in weights.items()}
        return superposition(weights)

    # ---------- 持久化（保留义项+64卦分布） ----------
    def snapshot(self) -> Dict:
        cells = []
        for c in self.cells.values():
            cells.append({
                "word": c.word, "level": c.level, "id": c.id,
                "pos": c.pos, "domain": c.domain,
                "senses": [{"dist": s["dist64"].tolist(), "pos": s["pos"],
                            "domain": s["domain"], "strength": s["strength"]}
                           for s in c.senses],
                "dist": c.dist.tolist(),
            })
        return {"step": self.step, "cells": cells}

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.snapshot(), f, ensure_ascii=False, indent=2)

    # ---------- 复杂度 ----------
    def complexity(self) -> Dict:
        return {
            "total_cells": len(self.cells),
            "char_cells": sum(1 for c in self.cells.values() if c.level == "char"),
            "word_cells": sum(1 for c in self.cells.values() if c.level == "word"),
            "dict_prior_cells": sum(1 for c in self.cells.values()
                                    if c.senses and c.senses[0]["domain"] not in ("未知", "部首先验")),
            "avg_senses": sum(len(c.senses) for c in self.cells.values()) / max(1, len(self.cells)),
        }


# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 64卦字典先验引擎 自检 ===")
    eng = Engine64(seed=1)
    # 1) 字典先验出生
    for w in ["点", "江河", "的", "火", "心"]:
        c = eng.ensure_word(w)
        gi, gn, gp = c.dom_gua()
        print(f"  『{w}』[{c.level}] 主导=({gi},{gn},{gp:.2f}) 义项数={len(c.senses)} 熵={c.ent():.2f}bits")
    # 2) 多义字『点』量子叠加（不坍缩）
    c = eng.cells["点"]
    psi = eng.quantum_superpose_word(c)
    print(f"\n  多义『点』量子叠加态: P(离/火)={measure_prob(psi,BAGUA_INDEX['离']):.3f} "
          f"P(坎/水)={measure_prob(psi,BAGUA_INDEX['坎']):.3f} (双义共存,不坍缩)")
    # 3) 语料学习内化：给『点』喂"点火"语境
    print(f"\n  学习前 『点』主导={c.dom_gua()[1]}")
    eng.learn_sentence(["点火"])
    gi, gn, gp = eng.cells["点"].dom_gua()
    print(f"  学『点火』后 『点』主导=({gi},{gn},{gp:.2f}) 义项={len(c.senses)}")
    # 4) 三级嵌套 + 复杂度
    eng.process_sentence(["江河", "清澈"])
    print(f"\n  复杂度: {eng.complexity()}")
    print("64卦字典先验引擎 OK")
