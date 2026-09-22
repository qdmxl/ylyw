#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_learn64.py — 词典释义 → 64卦种子 (方案A: 词典初始化先天知识)

核心思路（回应马老师：不做结构化知识库，而是"学习调整进64卦系统"）：

把《现代汉语词典》每个字头的**真实释义文本**当作语料，
用已有的部首/字→64卦先验，把释义里每个汉字的卦分布**累积**到该字头上，
得到一个"先天字义卦轮廓"。这个轮廓作为该字64卦叠加态的**初始种子**，
之后读真实语料还会持续学习调整 → 先天知识+后天演化，不是静态查表。

流程:
  1) 读 dict_seed.json（解析好的单字字头+释义）
  2) 对每个字，扫描其所有释义文本中的汉字
  3) 每个汉字用 radical/char 先验查卦分布，加权累积到字头
     （权重: 释义中该字越靠前/越核心，越接近字义 → 加权）
  4) 归一成64卦软分布 → 该字的量子叠加态种子(振幅=√p)
输出: seed_quantum.json {字: {psi(64复), dist64(64浮), senses, pos}}
"""
from __future__ import annotations
import json, os, math
from collections import Counter, defaultdict
import numpy as np

from bagua64 import soft_from_bagua, top_k
from dict_prior import radical_prior64, char_senses, function_word, prior64_semantic


# 释义中出现的高频虚化/泛义字：语义指向不可靠，不贡献主导（只降权，不进排除名单）
# 这类字在多数字的释义里都出现，纯靠频率堆权重，会拉偏主导卦
VAGUE_CHARS = set("点时位所地等处者来去一二三四五六七八九十之与及并面种样")


def contribution_weight(pd, sense_w: float, is_vague: bool) -> float:
    """贡献字权重 = 语义指向纯度 × 位置权 × 虚化降权。

    关键：主导卦的**纯度**(top1概率)决定该字能否提供可靠语义方向。
    - 纯净指向字(如江→坎0.9)：贡献高
    - 多义/模糊字(如点→离0.54,熵1.45)：贡献按纯度打折
    - 虚化高频字(点/时/位)：再额外降权，防止频率堆起来拉偏主导
    """
    p = np.asarray(pd, dtype=float)
    gi, gp, gn = top_k(p, 1)[0]
    pur = max(float(gp), 0.0)                 # 主导纯度[0,1]
    w = sense_w * (0.3 + 0.7 * pur)           # 纯度加权：不纯净字贡献低
    if is_vague:
        w *= 0.3                               # 虚化高频字额外降权
    return w


_HERE = os.path.dirname(os.path.abspath(__file__))
SEED_FILE = os.path.join(_HERE, "dict_seed.json")
OUT_FILE = os.path.join(_HERE, "seed_quantum.json")


def load_seed(path: str = SEED_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def char_prior_dist(ch: str) -> np.ndarray | None:
    """取单字的 64卦先验分布（字典书义 或 部首 或 64卦语义命中，无则None）。"""
    ss = char_senses(ch)
    if ss and len(ss) > 0:
        # 取首义项主导（最字面义）
        return ss[0]["dist64"]
    r = radical_prior64(ch)
    if r is not None:
        return r
    # 64卦语义命中层（V3: 让字义落到具体64卦位，激活56维）
    sem = prior64_semantic(ch)
    if sem is not None:
        return sem
    return None


# 先天锚显式覆盖表(中文核心自然意象): 只收录我们确信的正卦,
# 用于矫正'词典释义关联字聚合'对核心字的带偏(如 玉→艮 而非坎)。
# 值 = (卦名, 覆盖后主象最低概率)。不抹除其余学习面, 只保证主象正确。
CANONICAL_ANCHOR_GUA = """
# 五行
水 坎  火 离  木 巽  金 乾
# 山石(艮)
山 艮  石 艮  岩 艮  玉 艮  珠 艮  宝 艮  头 艮  首 艮  丘 艮  峰 艮
止 艮  静 艮  阻 艮  固 艮  岡 艮
# 风木(巽)
风 巽  树 巽  林 巽  枝 巽  叶 巽  草 巽  竹 巽  木 巽
# 泽口悦(兑)
兑 兑  泽 兑  悦 兑  喜 兑  笑 兑  口 兑  言 兑  说 兑
# 日火雷电(离/震)
日 离  光 离  明 离  亮 离  晒 离  炎 离
雷 震  电 震  动 震  龙 震  魂 震  惊 震
# 水(坎)
水 坎  泉 坎  溪 坎  河 坎  江 坎  海 坎  雨 坎  雪 坎  冰 坎  云 坎
月 坎  暗 坎  隐 坎  险 坎  深 坎
# 天父强(乾)
天 乾  乾 乾  父 乾  君 乾  刚 乾  强 乾  健 乾  刚 乾
# 地母顺(坤)
地 坤  母 坤  顺 坤  厚 坤  土 坤
# 心情感(离) — 内热/心火
心 离  情 离  爱 离  怒 离  欲 离
"""

_CANONICAL_MAP = {}
for _ln in CANONICAL_ANCHOR_GUA.strip().splitlines():
    _parts = _ln.split()
    if not _parts or _parts[0].startswith("#"):
        continue
    # 每行形如: 字 卦 [字 卦 ...]  (两个字一组, 交替)
    for _i in range(0, len(_parts) - 1, 2):
        _ch, _gua = _parts[_i], _parts[_i + 1]
        if _ch in _CANONICAL_MAP:
            _CANONICAL_MAP[_ch].add(_gua)
        else:
            _CANONICAL_MAP[_ch] = {_gua}


def _apply_canonical_anchor(dist: np.ndarray, ch: str):
    """把 `dist`(64维软分布, 原地修改) 中 ch 的正卦强置为主象(最低 prob)。
    用于矫正词典聚合带偏的核心自然意象字。
    """
    if ch not in _CANONICAL_MAP:
        return
    try:
        from gua64_semantics import NAME_INDEX
        idxs = [NAME_INDEX[g] for g in _CANONICAL_MAP[ch]]
    except Exception:
        return
    # 保主象概率下限(默认0.5), 不抹除其余学习面
    target = 0.5
    cur = max(dist[i] for i in idxs)
    if cur >= target:
        return                                    # 正卦已是主象, 无需改
    # 其余分量按原比例缩放到 (1-target), 正卦分量置为 target/卦数
    other = dist.copy()
    for i in idxs:
        other[i] = 0.0
    other_sum = other.sum()
    if other_sum + 1e-12 < 1e-12:
        return
    scale = (1.0 - target) / other_sum
    for i in range(dist.shape[0]):
        if i not in idxs:
            dist[i] = other[i] * scale            # 只缩放非正卦分量
        else:
            dist[i] = target / len(idxs)          # 正卦分量直接置目标(平分)
    # 已是归一(=1), 无需再除
    # s = dist.sum()
    # if s > 0:
    #     dist /= s



def build_seed(seed: dict) -> dict:
    """从词典释义累积每个字的 64卦种子叠加态。"""
    result = {}
    for ch, info in seed.items():
        senses = info.get("senses", [])
        n_entry = info.get("n_entry", 1)
        acc = np.zeros(64, dtype=float)
        context_words = Counter()   # 记录贡献字(可诊断)
        for si, sense in enumerate(senses):
            # 词性加权: 词典核心义项权重更高(靠前)
            sense_w = 1.0 / (1 + 0.3 * si)
            for wch in sense:
                if not ("\u4e00" <= wch <= "\u9fff"):
                    continue
                if wch == ch:
                    continue                      # 排除字头自身(防自我强化中性)
                if function_word(wch):
                    continue                      # 排除虚词/语法字(防坤污染)
                pd = char_prior_dist(wch)
                if pd is None:
                    continue
                w = contribution_weight(pd, sense_w, wch in VAGUE_CHARS)
                if w <= 1e-6:
                    continue
                acc += w * np.asarray(pd, dtype=float)
                context_words[wch] += w
        # 若无任何先验命中 → 均匀种子(低先验)
        tot = acc.sum()
        if tot < 1e-9:
            dist = np.full(64, 1.0 / 64.0)
        else:
            dist = acc / tot
        # 先天锚显式覆盖(马老师选A): 自然意象核心字被'释义关联字聚合'带偏时,
        # 用置信的正卦强置为先天主象(不抹除其余学习面, 只保主象正确)
        _apply_canonical_anchor(dist, ch)
        psi = np.sqrt(dist).astype(complex)      # 振幅 = √概率
        result[ch] = {
            "psi_re": [float(p.real) for p in psi],
            "psi_im": [float(p.imag) for p in psi],
            "dist64": dist.tolist(),
            "pos": info.get("pos", []),
            "n_entry": n_entry,
            "n_sense": info.get("n_sense", len(senses)),
            # 诊断: 贡献占比最高的几个先验字
            "top_ctx": context_words.most_common(5),
        }
    return result


def save(result: dict, path: str = OUT_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=0)
    print(f"已保存: {path} ({os.path.getsize(path)//1024}KB)")


if __name__ == "__main__":
    seed = load_seed()
    print(f"读入词典种子: {len(seed)} 字")
    res = build_seed(seed)
    print(f"生成64卦种子: {len(res)} 字")
    # 抽样验证: 水火心点金
    from bagua64 import top_k
    print("\n=== 词典学习出的先天字义卦轮廓(抽样) ===")
    for ch in ["水", "火", "心", "点", "金", "山", "雨", "木", "黑", "开"]:
        if ch in res:
            d = np.asarray(res[ch]["dist64"])
            tops = ", ".join(f"{n}{v:.2f}" for i, v, n in top_k(d, 3))
            top_ctx = "".join(c for c, _ in res[ch]["top_ctx"][:6])
            print(f"  『{ch}』top卦: [{tops}]  <释义贡献字: {top_ctx}>")
    save(res)
