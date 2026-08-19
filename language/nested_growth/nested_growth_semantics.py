#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nested_growth_semantics.py
==========================
嵌套自增长语义系统核心库

一个可自适应、可自我繁殖增长的复杂系统：
喂入语料越多 → 繁殖出新的语义"元胞"(每个元胞=一个独立小八卦系统)
→ 每个元胞的 H 规则权重自学习 → 系统变复杂、语义理解变强。

借鉴 YLYW 分层嵌套结构（字→词→句递归推理）：
  每个元胞 = 一个 mini 语义系统，内部用 6爻向量 表示其语义状态，
  用可学习权重 H=[J_adj,J_ying,h_dang,h_zhong,J_comp] 决定其六爻如何
  聚合出语义倾向（等价于小型哈密顿规则引擎）。

机制（完全对齐 YLYW 知几/知耻/爻调）：
  - 知几繁殖(Growth)：见陌生语义 → 繁殖新元胞（先验只增强不覆盖，继承父辈theta）
  - 爻调(H自学习)：每局成败 → 灵敏度归因 → 各元胞独立校准自己的H
  - 知耻淘汰(Dormancy)：长期无用 → 休眠保留（不毁灭先验）

用途：最小可跑增长演示 + 后续论文§新章节的蓝本。
"""
from __future__ import annotations
import json, os, math, random
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

DEFAULT_THETA = [1.0, 0.5, 0.30, 0.15, 0.5]   # Config-C: J_adj,J_ying,h_dang,h_zhong,J_comp
THETA_LOWER = [0.05, 0.05, 0.0, 0.0, 0.05]
THETA_UPPER = [2.0, 2.0, 1.0, 1.0, 2.0]
KEYS = ["J_adj", "J_ying", "h_dang", "h_zhong", "J_comp"]


# ============================================================
# 元胞：一个最小语义八卦系统
# ============================================================
class SemanticCell:
    """一个可独立学习的语义元胞（mini-YLYW系统，带可学习H）"""

    __slots__ = ("word", "parents", "children", "theta", "lh_buf",
                 "encounters", "wins", "losses", "last_step", "born_step",
                 "born_from", "state", "id", "cache_key",
                 "level", "sem_yao", "is_entity")

    def __init__(self, word: str, theta: Optional[List[float]] = None,
                 parents: Optional[List["SemanticCell"]] = None,
                 born_step: int = 0, born_from: str = "seed", cid: int = 0,
                 level: str = "char", sem_yao: Optional[List[float]] = None,
                 is_entity: bool = False):
        self.word = word
        self.parents = parents or []
        self.children = []
        self.theta = list(theta) if theta is not None else list(DEFAULT_THETA)
        self.lh_buf = []          # 灵敏度缓冲（局内爻调累积）
        self.encounters = 0
        self.wins = 0
        self.losses = 0
        self.last_step = 0
        self.born_step = born_step
        self.born_from = born_from
        self.state = "active"     # active | dormant
        self.id = cid
        self.cache_key = word
        # [词胞/句胞语义层] 嵌套理解新增字段（不进 snapshot，旧模型兼容）
        self.level = level                 # char | word | sentence
        self.sem_yao = sem_yao             # 该元胞的语义六爻（None=未定）
        self.is_entity = is_entity         # 命名实体（人名词等）标记

    # ---------- 六爻聚合：轻量"可学习H规则引擎" ----------
    def compose(self, yao: List[float]) -> float:
        """
        用本元胞的 H 权重从六爻向量聚合出"语义激活强度" s ∈ [0,1]。
        H 的 5 权重在这里起到"规则调制六爻"的作用：
          - J_adj: 相邻爻协同放大(首尾-上卦下卦的整体一致性)
          - J_ying: 一二/五上等应位爻的呼应
          - h_dang/h_zhong: 位置偏好(重心偏中)
          - J_comp: 竞争(爻值离中即变, 强调变化)
        简单可解释且保留"θ改变→语义输出改变"的可学习性。
        """
        if not yao:
            return 0.5
        v = yao
        J_adj, J_ying, h_dang, h_zhong, J_comp = [max(0.0, t) for t in self.theta]
        # 相邻一致性（同相放大）
        adj = sum(v[i] * v[i + 1] for i in range(len(v) - 1)) / (len(v) - 1)
        # 应位呼应（上下卦对应位：0-3,1-4,2-5）
        pairs = [(i, i + 3) for i in range(len(v) - 3)]
        ying = (sum(v[a] * v[b] for a, b in pairs) / len(pairs)) if pairs else 0.0
        # 重心（2,5中位强化即得中）
        n = len(v)
        if n >= 5:
            zhong = (v[1] + v[4]) / 2.0
        elif n >= 3:
            zhong = v[n // 2]
        else:
            zhong = 0.5
        # 均值(当位基线) + 波动(竞争)
        mean = sum(v) / n
        spread = math.sqrt(sum((x - mean) ** 2 for x in v) / n)
        s = (0.35 * mean + 0.25 * J_adj * adj + 0.15 * J_ying * ying
             + 0.10 * h_dang * mean + 0.05 * h_zhong * zhong
             + 0.10 * J_comp * spread)
        return max(0.0, min(1.0, s))

    # ---------- 灵敏度归因（H对θ的导数，无需反传） ----------
    def sensitivity(self, yao: List[float]) -> List[float]:
        """该决策下，θ每分量对本元胞输出 s 的灵敏度。"""
        if not yao:
            return [0.0] * len(self.theta)
        v = yao
        n = len(v)
        adj = sum(v[i] * v[i + 1] for i in range(n - 1)) / (n - 1)
        pairs = [(i, i + 3) for i in range(n - 3)]
        ying = (sum(v[a] * v[b] for a, b in pairs) / len(pairs)) if pairs else 0.0
        mean = sum(v) / n
        spread = math.sqrt(sum((x - mean) ** 2 for x in v) / n)
        # 5权重各自系数（把输出写成 s = Σ_k coeff_k·θ_k + bias 的线性形式）
        co = [0.25 * mean, 0.15 * ying, 0.10 * mean, 0.05 * ((v[1] + v[4]) / 2.0 if n >= 5 else 0.5), 0.10 * spread]
        return co

    def record_decision_learn(self, yao: List[float]):
        """记录一次由本元胞主导的决策（存灵敏度，供局末校准）。"""
        self.lh_buf.append(self.sensitivity(yao))
        self.encounters += 1

    def commit_game(self, won: bool, alpha_q: float = 0.2, alpha_s: float = 0.02):
        """局末：用本局灵敏度对H做知几校准（成功强化>失败惩罚的不对称）。"""
        if not self.lh_buf:
            return 0.0
        g = [sum(b[k] for b in self.lh_buf) / len(self.lh_buf) for k in range(len(self.theta))]
        # 不对称：赢局幅大且方向正；输局幅小
        sign = 1.0 if won else -1.0
        alpha = alpha_q if won else alpha_q * 0.5   # 失败惩罚减半(先验只增强不覆盖)
        delta = [sign * alpha * g[k] + alpha_s * (g[k] if won else -0.2) for k in range(len(self.theta))]
        for k in range(len(self.theta)):
            self.theta[k] = max(THETA_LOWER[k], min(THETA_UPPER[k], self.theta[k] + delta[k]))
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.lh_buf = []
        return sum(abs(d) for d in delta)

    def theta_dict(self) -> Dict[str, float]:
        return dict(zip(KEYS, [round(float(x), 4) for x in self.theta]))

    def score(self) -> float:
        """元胞价值（知几强化/知耻衰减用）"""
        return (self.wins + 1.0) / (self.wins + self.losses + 2.0)

    def __repr__(self):
        return (f"<Cell '{self.word}' #{self.id} "
                f"e={self.encounters} w={self.wins} l={self.losses} "
                f"{self.state} θ={self.theta_dict()}>")


# ============================================================
# 嵌套自增长语义系统
# ============================================================
class NestedGrowthSemantics:
    """主系统：管理元胞繁殖 / H自学习 / 嵌套 / 淘汰"""

    def __init__(self, max_cells: int = 500, seed: int = 0,
                 alpha_q: float = 0.2, alpha_s: float = 0.02,
                 dormancy_threshold: int = 30):
        self.max_cells = max_cells
        self.alpha_q = alpha_q
        self.alpha_s = alpha_s
        self.dormancy_threshold = dormancy_threshold
        self.rng = random.Random(seed)
        self.cells: Dict[str, SemanticCell] = {}   # key=word → cell
        self.roots: List[SemanticCell] = []        # 顶层元胞（无父）
        self.step = 0
        self._cid = 0

    # ---------- 播种 / 查找 / 繁殖 ----------
    def seed(self, words: List[str], theta: Optional[List[float]] = None):
        for w in words:
            if w not in self.cells:
                c = SemanticCell(w, theta=theta, born_step=0, born_from="seed",
                                 cid=self._cid); self._cid += 1
                self.cells[w] = c
                self.roots.append(c)

    def get_cell(self, word: str) -> Optional[SemanticCell]:
        return self.cells.get(word)

    def find_best(self, words: List[str]) -> Optional[SemanticCell]:
        """在已有元胞中找最匹配的（可为多字：优先长匹配）"""
        for ln in range(min(3, len(words)), 0, -1):
            for i in range(len(words) - ln + 1):
                w = "".join(words[i:i + ln])
                if w in self.cells:
                    return self.cells[w]
        return None

    @staticmethod
    def _mutate(theta: List[float], noise: float) -> List[float]:
        return [max(THETA_LOWER[k], min(THETA_UPPER[k], t + random.uniform(-noise, noise)))
                for k, t in enumerate(theta)]

    def grow(self, word: str, father: Optional[SemanticCell] = None) -> SemanticCell:
        """繁殖新元胞（父辈theta继承+微扰，先验只增强不覆盖）"""
        base = father.theta if father is not None else list(DEFAULT_THETA)
        theta = self._mutate(base, noise=0.05)
        c = SemanticCell(word, theta=theta,
                         parents=[father] if father else [],
                         born_step=self.step,
                         born_from=f"{father.word}" if father else "root",
                         cid=self._cid)
        self._cid += 1
        self.cells[word] = c
        if father is not None:
            father.children.append(c)
        else:
            self.roots.append(c)
        return c

    def ensure(self, word: str, father: Optional[SemanticCell] = None) -> SemanticCell:
        """有则取，无则繁殖。返回元胞。"""
        if word in self.cells:
            c = self.cells[word]
            if father is not None and father not in c.parents:
                c.parents.append(father)
                father.children.append(c)
            return c
        return self.grow(word, father)

    # ---------- 推理：输入一句话的语义特征 → 选出/繁殖元胞 ----------
    def process_sentence(self, tokens: List[str],
                         father: Optional[SemanticCell] = None,
                         words: Optional[List[str]] = None):
        """
        处理一句话：(可能繁殖字元胞/词级元胞) → 找到元胞，返回命中元胞列表与记录。

        支持嵌套生长：
          - tokens: 字符序列（用于建立字元胞）
          - words : 词切分序列（可选）。提供的词若不存在词元胞，
                    则先确保其组成字有字元胞，再以这些字元胞为父繁殖出词级元胞
                    → 词系统嵌套在字系统之上。
        返回 (命中的元胞列表, 记录)
        """
        self.step += 1
        hit_cells = []
        records = []
        # 1) 确保所有组成字有字元胞（无则繁殖，父为句级/相邻）
        for ch in tokens:
            if ch not in self.cells:
                self.grow(ch, father)
        # 2) 处理词级嵌套（若提供词切分）
        if words:
            for w in words:
                if not w:
                    continue
                if w not in self.cells:
                    # 词级元胞：父 = 组成字元胞（嵌套在字系统之上）
                    char_cells = [self.cells[c] for c in w if c in self.cells]
                    cell_father = char_cells[0] if char_cells else father
                    self.grow(w, cell_father)
                c = self.cells[w]
                c.last_step = self.step
                hit_cells.append(c)
                records.append({"tok": w, "cell": w, "born_step": c.born_step,
                                "born_from": c.born_from, "new": c.born_step == self.step,
                                "level": "word"})
        else:
            # 无词切分：字级处理（命中已有字/长元胞）
            i = 0
            n = len(tokens)
            while i < n:
                picked = None; plen = 0
                for ln in range(min(4, n - i), 0, -1):
                    w = "".join(tokens[i:i + ln])
                    if w in self.cells:
                        picked = self.cells[w]; plen = ln; break
                if picked is None:
                    picked = self.cells.get(tokens[i])
                    plen = 1
                if picked is not None:
                    picked.last_step = self.step
                    hit_cells.append(picked)
                    records.append({"tok": picked.word, "cell": picked.word,
                                    "born_step": picked.born_step,
                                    "born_from": picked.born_from,
                                    "new": picked.born_step == self.step,
                                    "level": "word" if len(picked.word) >= 2 else "char"})
                i += max(plen, 1)
        return hit_cells, records

    # ---------- [词胞/句胞] 以词为主处理 + 聚合句胞 ----------
    def ensure_word_cell(self, w: str) -> SemanticCell:
        """确保词胞存在（父=组成字胞），并赋词级语义爻（消歧后）。"""
        if w not in self.cells:
            char_father = None
            for ch in w:
                if ch in self.cells:
                    char_father = self.cells[ch]; break
            c = self.grow(w, char_father)
            c.level = "word"
        else:
            c = self.cells[w]
        # 词级语义爻（命名实体/时间词消歧，否则词义聚合）
        c.sem_yao = self.word_sem_yao(w)
        c.is_entity = self.is_entity_word(w)
        c.last_step = self.step
        return c

    def process_sentence_words(self, words: List[str]):
        """[以词为主] 处理一句：保证字胞→词胞嵌套，聚合词胞生成句胞语义。

        返回 dict:
          word_cells : 参与词胞列表
          sent_yao   : 句胞语义（词胞语义爻均值），无则 None
          sent_cell  : 句胞对象（父=参与词胞）
          records    : 每词记录
        """
        self.step += 1
        word_cells, records = [], []
        for w in words:
            if not w:
                continue
            c = self.ensure_word_cell(w)
            word_cells.append(c)
            records.append({"tok": w, "level": "word",
                            "entity": c.is_entity,
                            "new": c.born_step == self.step})
        # 句胞：聚合词胞语义爻（命名实体/虚词不稀释语义主流）
        sem_yaos = [c.sem_yao for c in word_cells if c.sem_yao is not None]
        sent_yao = self._mean_yao(sem_yaos) if sem_yaos else None
        sent_cell = SemanticCell(
            "<s>" + str(self.step), theta=list(DEFAULT_THETA),
            parents=word_cells, born_step=self.step,
            born_from="sentence", cid=self._cid, level="sentence",
            sem_yao=sent_yao, is_entity=False)
        self._cid += 1
        for c in word_cells:
            c.children.append(sent_cell)
        return {"word_cells": word_cells, "sent_yao": sent_yao,
                "sent_cell": sent_cell, "records": records}

    def sentence_semantics(self, words: List[str]) -> Optional[List[float]]:
        """便捷：直接返回一句的句胞语义爻（无则 None）。"""
        return self.process_sentence_words(words)["sent_yao"]

    # ---------- 局末校准：对参与元胞校H ----------
    def commit(self, cells: List[SemanticCell], won: bool,
               yao_for_cell: Optional[Dict[str, List[float]]] = None):
        total_delta = 0.0
        for idx, c in enumerate(cells):
            # 用统一六爻(可传，否则用元胞名长度造稳定向量)
            yao = yao_for_cell.get(c.word) if yao_for_cell else None
            if yao is None:
                yao = self._stable_yao(c.word)
            c.record_decision_learn(yao)
            total_delta += c.commit_game(won, self.alpha_q, self.alpha_s)
        # 知耻：长期无用休眠
        for c in list(self.cells.values()):
            self.step += 0
            if c.state == "active" and self.step - c.last_step > self.dormancy_threshold:
                c.state = "dormant"
        return total_delta

    # ── 部首先验语义通道（字元胞补全增长的语义起点）──
    # 以下卦为“独体/部首特征 → 主导八卦 → 标准六爻(下卦3爻+上卦3爻, 阴0阳1)”。
    # 目的：字元胞一出生即携带真实部首结构语义(而非纯哈希壳)，
    #       使水/火/木/金/土/石 等核心字在嵌套自增长中浮现正确语义区分度。
    YAO_BY_BAGUA = {
        "乾": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "兑": [0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "离": [1.0, 0.0, 1.0, 1.0, 0.0, 1.0],
        "震": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        "巽": [0.0, 1.0, 1.0, 0.0, 1.0, 1.0],
        "坎": [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
        "艮": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        "坤": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    }
    # 部首特征检测：(真实部首集合, 主导八卦, 强度)
    #   第一个集合 = 真实部首字符（含在被测字中即命中，如“江”含氵）
    #   第二个集合 = 该部首主导语义的独体字（如 水本身、江、河…兑水义）
    RADICAL_SEMANTICS = [
        # (部首字符, 义旁独体字, 主导八卦, 强度)
        (set("氵水冫"), set("水雨泪酒汤江河海溪泉潮波浪浆潇湘浴滋洲泛滥沐浴"), "坎", 0.85),
        (set("灬火"), set("火烛灯焰炽燃炎炎热煮烹烤煎熏"), "离", 0.85),
        (set("木"), set("木林树树枝梗梢株果板柜桌椅床梁柱梯机森棵梅杏桃松柏"), "巽", 0.70),
        (set("钅金"), set("金银钱铁铜锡锣铃珠宝玉贝"), "乾", 0.70),
        (set("土"), set("土尘地城墙坪坡堤垣垒基堆堂埃址壤"), "坤", 0.65),
        (set("石"), set("石岩矿礁磅礴磊砦确砚砂碎砺碰砖"), "艮", 0.65),
        (set("山"), set("山岭峰峦峻岫崇巍嶂岗崖岸岩"), "艮", 0.85),
        (set("日"), set("日晖晴煦旭旦晨昱昊星时刻昨昏曝暖映明时"), "离", 0.60),
    ]

    @classmethod
    def _radical_yao(cls, word: str) -> Optional[List[float]]:
        """部首语义先验：词内含已知语义部首或义旁独体字 → 返回其主导八卦的六爻(软值)，否则 None。"""
        best = None  # (强度, 爻列表)
        for rads, meaning, bagua, strength in cls.RADICAL_SEMANTICS:
            # 命中条件：词内含部首字符 或 词本身是义旁独体字
            hit = any(r in word for r in rads) or word in meaning
            if hit:
                base = cls.YAO_BY_BAGUA[bagua]
                # 软值：以 strength 为核心激活，其余爻基线 0.5→被拉向非核心
                yao = [base[i] * strength + (1 - strength) * 0.3 for i in range(6)]
                if best is None or strength > best[0]:
                    best = (strength, yao)
        return best[1] if best else None

    @classmethod
    def _stable_yao(cls, word: str) -> List[float]:
        """为元胞名生成稳定的六爻向量。
        优先：部首先验语义（字元胞补全增长的语义起点）。
        回退：确定性哈希。"""
        sem = cls._radical_yao(word)
        if sem is not None:
            return sem
        h = 0
        for ch in word:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        yao = []
        for i in range(6):
            yao.append(0.1 + ((h >> (i * 4)) & 0xF) / 15.0 * 0.8)
        return yao

    # ═══════════════════ 词级消歧 + 词胞/句胞语义层 ═══════════════════
    # 马老师原则：理解不能只在字层面——词胞自动嵌套生成后以词为主理解，
    #              句灵生成后以句为主理解。
    # 静态“字→部首→卦象”在真实文体（人名/虚词密集史白话）会字义漂移
    # (“宝玉”是人名非金石、“日/时”是时间词非火)。故在词级消歧：
    #   1) 命名实体(人名词) → 不按字归因，给中性专名爻
    #   2) 时间词          → 不按“日=火”归因，给时间类爻
    #   3) 普通词          → 按整词/组成字的部首语义聚合

    # 红楼高频命名实体（人名/专名）——词胞中立化，不做字面部首归因
    ENTITY_WORDS = frozenset("""
        宝玉 黛玉 宝钗 湘云 袭人 晴雯 紫鹃 雪雁 探春 迎春 惜春 李纨
        凤姐 凤姐儿 王熙凤 林黛玉 贾宝玉 薛宝钗 史湘云 香菱 平儿 鸳鸯 坠儿 芳官
        宝琴 岫烟 宝钗 宝琴 岫烟 纹绮 纨 贾母 贾政 贾赦 贾珍 贾琏 贾蓉 贾环 贾芸 贾兰
        薛蟠 薛蝌 柳湘莲 秦钟 秦可卿 尤氏 尤二姐 尤三姐 妙玉 元春 巧姐 巧姐儿 傻大姐
        焙茗 茗烟 金钏 金钏儿 玉钏 司棋 侍书 入画 翠缕 琥珀 珍珠 麝月 秋纹 碧痕
        红玉 林之孝 赖大 赖升 周瑞 甄士隐 贾雨村 封肃 门子 娇杏 卜世仁
        张如圭 林如海 贾敏 冷子兴 空空道人 茫茫大士 渺渺真人 警幻仙姑
    """.split())
    # 时间/虚貌词——不按“日=火/月=肉”等部首归因
    TIME_WORDS = frozenset("日时时时辰刻早晚今昨明日夜朝夕年月岁")

    NEUTRAL_YAO = [0.5] * 6          # 专名/时间等中立语义爻
    TIME_YAO = [0.40, 0.55, 0.45, 0.55, 0.40, 0.50]  # 时间类爻（区别于五行类）

    @classmethod
    def is_entity_word(cls, w: str) -> bool:
        return w in cls.ENTITY_WORDS

    @classmethod
    def word_sem_yao(cls, w: str) -> Optional[List[float]]:
        """词级语义爻（以词为主）：
        - 命名实体 → 中立专名爻
        - 时间词    → 时间类爻
        - 否则      先用整词部首语义；再退化为组成字部首语义聚合
        """
        if w in cls.ENTITY_WORDS:
            return list(cls.NEUTRAL_YAO)
        if w in cls.TIME_WORDS:
            return list(cls.TIME_YAO)
        # 整词部首语义
        whole = cls._radical_yao(w)
        if whole is not None:
            return whole
        # 组成字聚合（跳过被消歧的单字）
        acc, n = [], 0
        for ch in w:
            if ch in cls.ENTITY_WORDS or ch in cls.TIME_WORDS:
                continue
            y = cls._radical_yao(ch)
            if y is not None:
                acc.append(y); n += 1
        if n:
            return [sum(a[i] for a in acc) / n for i in range(6)]
        return None

    @staticmethod
    def _mean_yao(yaos: List[List[float]]) -> Optional[List[float]]:
        if not yaos:
            return None
        return [sum(y[i] for y in yaos) / len(yaos) for i in range(6)]

    # ---------- 系统复杂度指标 ----------
    def complexity(self) -> Dict:
        active = [c for c in self.cells.values() if c.state == "active"]
        depth = {}
        def _depth(c, seen):
            if c.id in seen:
                return 0  # 防环
            if c.id not in depth:
                seen.add(c.id)
                depth[c.id] = 1 + max((_depth(p, seen) for p in c.parents), default=0)
                seen.discard(c.id)
            return depth[c.id]
        for c in active:
            _depth(c, set())
        depths = [depth[c.id] for c in active] or [0]
        return {
            "total_cells": len(self.cells),
            "active_cells": len(active),
            "dormant_cells": len(self.cells) - len(active),
            "max_depth": max(depths),
            "mean_depth": sum(depths) / len(depths),
            "total_theta_var": sum((abs(c.theta[0] - DEFAULT_THETA[0])) for c in active),
            "new_cells_this_run": self.step and len(active),
        }

    def snapshot(self) -> Dict:
        return {
            "step": self.step,
            "cells": [{"word": c.word, "state": c.state, "encounters": c.encounters,
                       "wins": c.wins, "losses": c.losses, "born_from": c.born_from,
                       "theta": c.theta_dict()}
                      for c in self.cells.values()],
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.snapshot(), f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.cells.clear(); self.roots.clear()
        for cd in data["cells"]:
            c = SemanticCell(cd["word"], theta=[cd["theta"].get(k, DEFAULT_THETA[i]) for i, k in enumerate(KEYS)],
                             born_from=cd["born_from"], cid=self._cid); self._cid += 1
            c.state = cd["state"]; c.encounters = cd["encounters"]
            c.wins = cd["wins"]; c.losses = cd["losses"]
            self.cells[c.word] = c
        self.step = data["step"]
        return self
