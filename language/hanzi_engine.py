"""
YLYW 汉语理解引擎 — 递归YLYW架构

核心思想：字/词/句三个层级，每个层级都是一个独立的YLYW推理引擎。
- 字级YLYW: 输入=部首卦象 → 乘承比应 → 六爻编码 → 字卦象
- 词级YLYW: 输入=字卦象   → 乘承比应 → 六爻编码 → 词卦象
- 句级YLYW: 输入=词卦象   → 乘承比应 → 六爻编码 → 句卦象

每层的 L1(八卦隶属度) = 下一层的卦象
每层的 L2(六爻编码) = 元素间乘承比应 → 爻值
每层的 L3(卦象匹配) = 余弦匹配64卦

使用方式:
    >>> from hanzi_engine import HanziEngine
    >>> engine = HanziEngine()
    >>> engine.char('关')    # 字级YLYW推理
    >>> engine.word('关闭')  # 词级YLYW推理
    >>> engine.sentence('关上门')  # 句级YLYW推理
"""

import json
import math
import os
import sys
import numpy as np
from typing import Dict, List, Tuple, Optional

# 确保YLYW核心可导入
YLYW_PATH = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_PATH not in sys.path:
    sys.path.insert(0, YLYW_PATH)
    from ylyw_core import HexagramRuleBase, Hexagram
    _HRULE = HexagramRuleBase()
else:
    from ylyw_core import HexagramRuleBase, Hexagram
    _HRULE = HexagramRuleBase()

# ── 数据路径 ──────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))

# ── 八卦常数 ──────────────────────────────────────────────
BAGUA = ["乾","兑","离","震","巽","坎","艮","坤"]

# 八卦互生/互克关系（用于乘承比应）
# 相生：木火土金水（震巽生离、离生坤、坤生乾兑、乾兑生坎、坎生震巽）
BAGUA_SHENG = {
    "震": ["离"], "巽": ["离"], "离": ["坤"], "坤": ["乾","兑"],
    "乾": ["坎"], "兑": ["坎"], "坎": ["震","巽"], "艮": ["坎"],
}
# 相克：木克土、土克水、水克火、火克金、金克木
BAGUA_KE = {
    "震": ["坤"], "巽": ["坤"], "坤": ["坎"], "坎": ["离"],
    "离": ["乾","兑"], "乾": ["震","巽"], "兑": ["震","巽"], "艮": ["坎"],
}


# ── 数据加载 ──────────────────────────────────────────────
def _load_json(filename: str) -> dict:
    path = os.path.join(BASE, filename)
    with open(path, encoding='utf-8') as f:
        return json.load(f)

from hanzi_decomposition import HANZI_DECOMPOSITION
from decomp_to_fuzzy_map import DECOMP_TO_FUZZY_RADICAL
from ylyw_core import HexagramRuleBase, Hexagram

_HRULE = HexagramRuleBase()

RADICAL_DATA = _load_json('radical_fuzzy_base.json')
IDEO_KB = _load_json('ideograph_knowledge_base.json')
FUNC_WORDS = _load_json('function_words.json')
KNOWN_RADS = set(RADICAL_DATA.keys())
DECOMP = HANZI_DECOMPOSITION
DECOMP_MAP = DECOMP_TO_FUZZY_RADICAL


# ══════════════════════════════════════════════════════════════
# 通用YLYW层处理器
# ══════════════════════════════════════════════════════════════

class YLYWLayer:
    """
    一个通用的YLYW推理层，可在字/词/句三个尺度上复用。

    工作流程（与 PriorManual 同构）：
      L1: 接收一组"元素"的八卦隶属度（来自下一层）
      L2: 元素间的乘承比应关系 → 六爻向量
      L3: 六爻向量 → 64卦匹配 → 输出本层的卦象

    Attributes:
        name: 层级名（"char"/"word"/"sentence"）
    """

    def __init__(self, name: str = "layer"):
        self.name = name

    def perceive_and_encode(self, element_baguas: List[List[float]],
                            element_roles: List[str] = None,
                            relations: List[Dict] = None) -> Dict:
        """
        L1 → L2 → L3 完整推理链。

        Args:
            element_baguas: 每个子元素的8维八卦隶属度
            element_roles:  每个子元素的语义角色（如"动作/物体/虚词"）
            relations:      子元素间的预设关系（如跨虚词连接）

        Returns:
            yao_vector: 6维爻向量
            bagua:      8维本层卦象
            hexagram:   最佳匹配卦象名
            score:      匹配分数
            relations:  元素间的乘承比应关系
        """
        n = len(element_baguas)
        if n == 0:
            return self._empty_result()

        if element_roles is None:
            element_roles = ["物体"] * n

        # ── L1: 已直接输入（子元素卦象就是本层的"八卦隶属度"）──

        # ── L1.5: 卦象去偏——每个维度独立拉伸到[0.05, 0.95]
        # 消除部首隶属度偏态分布的影响
        debiased = []
        for b in element_baguas:
            lo = min(b)
            hi = max(b)
            if hi - lo > 0.01:
                db = [0.05 + (v - lo) / (hi - lo) * 0.9 for v in b]
            else:
                db = b
            debiased.append(db)
        
        # ── L2: 乘承比应关系计算 → 六爻编码 ──
        rels = self._calc_relations(debiased, element_roles, relations)
        yao = self._yao_from_relations(debiased, rels, element_roles)

        # ── L3: 64卦匹配 ──
        hex_name, score = self._match_hexagram(yao)
        bagua = self._yao_to_bagua(yao)
        
        # 64卦完整分布（每个卦的余弦匹配度）
        hex64 = self._match_64hexagrams(yao)

        return {
            "yao_vector": [round(v, 4) for v in yao],
            "bagua": [round(v, 4) for v in bagua],
            "hexagram": hex_name,
            "hexagram_score": round(score, 4),
            "hex64": [round(v, 4) for v in hex64],  # 64维卦象分布
            "relations": rels,
            "n_elements": n,
        }

    def _calc_relations(self, baguas: List[List[float]],
                        roles: List[str],
                        preset_relations: List[Dict] = None) -> List[Dict]:
        """
        计算元素间的乘承比应关系。
        """
        n = len(baguas)
        # 如果是64维输入（句层接收词层的hex64），先降维到8维
        # 8维 = 将8个卦各8个细分卦的匹配度求和
        if baguas and len(baguas[0]) == 64:
            reduced = []
            for b64 in baguas:
                # 每个卦位映射到其对应八卦：
                # 64卦分为8组，每组8个
                b8 = [0.0]*8
                for i in range(64):
                    b8[i // 8] += b64[i]
                # 归一化
                mx = max(b8) if max(b8) > 0 else 1.0
                reduced.append([v / mx for v in b8])
            baguas = reduced
        doms = [BAGUA[b.index(max(b))] for b in baguas]
        relations = []

        if preset_relations:
            relations = preset_relations

        for i in range(n):
            for j in range(i + 1, n):
                if roles[i] == "虚词" or roles[j] == "虚词":
                    continue

                adj = (j - i == 1)
                di, dj = doms[i], doms[j]

                # 乘：前动作后物体
                if adj and roles[i] == "动作" and roles[j] in ("物体", "状态"):
                    relations.append({
                        "from": i, "to": j, "type": "乘",
                        "from_dom": di, "to_dom": dj,
                    })
                # 承：前物体后动作  
                elif adj and roles[i] in ("物体", "状态") and roles[j] == "动作":
                    relations.append({
                        "from": i, "to": j, "type": "承",
                        "from_dom": di, "to_dom": dj,
                    })
                # 比：同角色相邻
                elif adj and roles[i] == roles[j]:
                    relations.append({
                        "from": i, "to": j, "type": "比",
                        "from_dom": di, "to_dom": dj,
                    })
                # 应：同卦相隔
                elif j - i >= 2 and di == dj:
                    relations.append({
                        "from": i, "to": j, "type": "应",
                        "from_dom": di, "to_dom": dj,
                    })

        return relations

    def _yao_from_relations(self, baguas: List[List[float]],
                            relations: List[Dict],
                            roles: List[str]) -> List[float]:
        """
        从元素卦象和乘承比应关系 → 6维爻向量。
        
        核心改进（2026-07-09）:
        - 每爻独立由所有元素的八卦加权融合，不按阴阳位分派
        - 动作元素和物体元素在每爻上混合贡献（动作主导高爻位、物体主导低爻位）
        - 乘/承关系对爻位的方向性调制
        """
        if not baguas:
            return [0.5] * 6

        def clip(v):
            return max(0.05, min(0.95, v))

        n = len(baguas)

        # 支持64维和8维输入
        def _ensure_8d(vec):
            if len(vec) == 64:
                b8 = [0.0]*8
                for i in range(64):
                    b8[i // 8] += vec[i]
                mx = max(b8) if max(b8) > 0 else 1.0
                return [v / mx for v in b8]
            return vec

        baguas8 = [_ensure_8d(b) for b in baguas]

        # 对每个角色类别分别累积八卦隶属度
        # role_accum[role] = 8维向量和
        role_accum = {}
        role_count = {}
        for i, r in enumerate(roles):
            if r not in role_accum:
                role_accum[r] = [0.0]*8
                role_count[r] = 0
            for d in range(8):
                role_accum[r][d] += baguas8[i][d]
            role_count[r] += 1

        # 归一化每个角色的平均八卦
        role_avg = {}
        for r in role_accum:
            cnt = role_count[r] if role_count[r] > 0 else 1
            role_avg[r] = [v / cnt for v in role_accum[r]]

        # 如果没有动作元素，用所有元素的融合
        action_bagua = role_avg.get("动作", None)
        object_bagua = role_avg.get("物体", None) or role_avg.get("状态", None)
        if action_bagua is None and object_bagua is None:
            # 全部元素取平均
            all_avg = [0.0]*8
            for b in baguas8:
                for d in range(8):
                    all_avg[d] += b[d]
            all_avg = [v / n for v in all_avg]
            action_bagua = all_avg
            object_bagua = [0.15]*8
        elif action_bagua is None:
            action_bagua = [0.15]*8
        elif object_bagua is None:
            object_bagua = [0.15]*8

        # ── 6爻构造（交替混合深度法）──
        # 每爻=动作卦象和物体卦象按位交替加权
        # 爻位0(初)→5(上)：动作权重从大→小再变大，形成锯齿
        # 这样同一动作+不同物体在每爻都有差异
        # 避免单调递增导致三爻相同

        action_w = [0.60, 0.35, 0.55, 0.40, 0.50, 0.45]
        #             0      1      2      3      4      5
        #            初     二     三     四     五     上
        # 动作权:   0.60   0.35   0.55   0.40   0.50   0.45
        # 物体权:   0.40   0.65   0.45   0.60   0.50   0.55

        yao = [0.0]*6

        # 乘承比应统计
        cheng_count = sum(1 for rel in relations if rel["type"] == "乘")
        cheng_factor = 1.0 + cheng_count * 0.02

        for pos in range(6):
            aw = action_w[pos]
            ow = 1.0 - aw

            # 混合八卦
            mixed = [action_bagua[d] * aw + object_bagua[d] * ow for d in range(8)]

            # 混合向量的能量
            max_val = max(mixed)
            avg_val = sum(mixed) / 8.0
            val = max_val * 0.55 + avg_val * 0.45

            # 乘承比应微调
            val *= cheng_factor
            yao[pos] = clip(val)

        return yao

    def _match_hexagram(self, yao: List[float]):
        """匹配最佳64卦（只接受6维爻向量输入）"""
        try:
            if len(yao) >= 6:
                h, s = _HRULE.get_best_hexagram(yao[:6])
            else:
                h, s = _HRULE.get_best_hexagram(yao)
            if h:
                rule = _HRULE.get_rule(h)
                return rule.get("name", h.name), s
        except Exception as e:
            pass
        return "?", 0.0

    def _match_64hexagrams(self, yao: List[float]) -> List[float]:
        """返回64维卦象匹配度分布（用6爻余弦匹配64卦）"""
        result = [0.0] * 64
        try:
            yao6 = yao[:6] if len(yao) >= 6 else [0.5]*6
            top = _HRULE.get_top_k_hexagrams(yao6, k=64)
            for hx, score in top:
                result[hx.value] = score
        except Exception as e:
            pass
        return result

    def _yao_to_bagua(self, yao: List[float]) -> List[float]:
        """64/6维 → 8维卦象（反向投影）"""
        bagua = [0.15] * 8
        if len(yao) >= 64:
            # 64维: 8组求和
            for i, v in enumerate(yao[:64]):
                bagua[i // 8] += v
            mx = max(bagua) if max(bagua) > 0 else 1.0
            return [v / mx for v in bagua]
        # 6维兼容
        for bg_idx, y_idx in enumerate([0, 1, 5, 2, 3, 4]):
            if y_idx < len(yao):
                bagua[bg_idx] = max(bagua[bg_idx], yao[y_idx] * 0.6)
        return bagua

    def _empty_result(self):
        return {
            "yao_vector": [0.5] * 6,
            "bagua": [0.25] * 8,
            "hexagram": "?",
            "hexagram_score": 0.0,
            "hex64": [0.0] * 64,
            "relations": [],
            "n_elements": 0,
        }


# ══════════════════════════════════════════════════════════════
# L0: 部首→汉字卦象（测字六法）
# ══════════════════════════════════════════════════════════════

def char_to_bagua(char: str) -> Dict:
    """
    测字六法：汉字 → 8维八卦隶属度。

    这是整个递归架构的"基座层"（L0）——输入单个汉字，
    输出该汉字的八卦隶属度供上层YLYW使用。

    测字六法按优先级：
      1. 整体观象法（"品"→兑、"山"→艮）
      2. 心意取向法（字义决定卦象）
      3. 义符声符加权（形旁×0.7 + 声旁×0.3）
      4. 形似物象兜底
      5. 笔画加减
      6. 部首间乘承比应（两个部首用YLYWLayer处理）
    """

    # 手工向量覆盖（为ALFWorld关键现代字预设8维向量）
    # 8维顺序：乾 兑 离 震 巽 坎 艮 坤
    KNOWN_VECTORS = {
        # 8维顺序：乾 兑 离 震 巽 坎 艮 坤

        # ═══ 家具/容器（多点激活）═══
        "柜": [0.15, 0.10, 0.10, 0.25, 0.20, 0.10, 0.65, 0.50],  # 艮+坤+震(藏纳)
        "箱": [0.10, 0.10, 0.10, 0.15, 0.20, 0.10, 0.45, 0.70],  # 坤+艮(包容)
        "桌": [0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.15, 0.50],  # 巽+坤(平载)
        "台": [0.10, 0.10, 0.10, 0.10, 0.55, 0.10, 0.15, 0.55],  # 巽+坤(平载)
        "槽": [0.10, 0.10, 0.10, 0.10, 0.10, 0.70, 0.15, 0.30],  # 坎+坤(水容)
        "架": [0.15, 0.10, 0.10, 0.10, 0.70, 0.10, 0.15, 0.10],  # 巽(架)+乾(刚)
        "屉": [0.10, 0.10, 0.10, 0.10, 0.15, 0.10, 0.60, 0.45],  # 艮+坤(藏纳)
        "桶": [0.10, 0.10, 0.10, 0.10, 0.10, 0.40, 0.10, 0.60],  # 坤+坎(容水)
        "瓶": [0.10, 0.10, 0.10, 0.10, 0.10, 0.50, 0.40, 0.25],  # 坎+艮(水藏)
        "罐": [0.35, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15, 0.50],  # 乾+坤(刚容)
        "盆": [0.10, 0.10, 0.10, 0.10, 0.10, 0.25, 0.30, 0.60],  # 坤+艮(容止)

        # ═══ 厨具/食器（多点激活）═══
        "盘": [0.10, 0.10, 0.10, 0.10, 0.20, 0.10, 0.15, 0.70],  # 坤(容)+巽(平)
        "碟": [0.10, 0.10, 0.10, 0.10, 0.20, 0.10, 0.10, 0.60],  # 坤(容)+巽(平)
        "碗": [0.10, 0.10, 0.10, 0.10, 0.10, 0.55, 0.10, 0.50],  # 坎+坤(水容)
        "杯": [0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.45],  # 坎+坤(水容)
        "壶": [0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.45],  # 坎+坤(水容)
        "锅": [0.10, 0.10, 0.60, 0.10, 0.10, 0.25, 0.10, 0.10],  # 离+坎(火烹水)
        "刀": [0.20, 0.70, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10],  # 兑(毁)+乾(刚)
        "勺": [0.10, 0.10, 0.10, 0.10, 0.10, 0.55, 0.10, 0.30],  # 坎+坤(水容)
        "叉": [0.10, 0.10, 0.10, 0.60, 0.10, 0.10, 0.10, 0.15],  # 震(分)+坤
        "筷": [0.10, 0.10, 0.10, 0.55, 0.50, 0.10, 0.10, 0.10],  # 震+巽(动入)

        # ═══ 电器 ═══
        "灯": [0.10, 0.10, 0.70, 0.10, 0.10, 0.10, 0.10, 0.10],  # 离(明)
        "炉": [0.10, 0.10, 0.65, 0.20, 0.10, 0.10, 0.10, 0.10],  # 离+震(火热)
        "机": [0.20, 0.10, 0.10, 0.60, 0.10, 0.10, 0.10, 0.10],  # 震+乾(机动)
        "微": [0.10, 0.10, 0.55, 0.40, 0.10, 0.10, 0.10, 0.10],  # 离+震(波)

        # ═══ 食物（多点激活）═══
        "肉": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15, 0.65],  # 坤(体)
        "蛋": [0.10, 0.10, 0.10, 0.10, 0.20, 0.10, 0.20, 0.60],  # 坤+巽(生出)
        "奶": [0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.30],  # 坎+坤(水养)
        "菜": [0.10, 0.10, 0.10, 0.55, 0.30, 0.10, 0.10, 0.20],  # 震+巽(生长)
        "果": [0.10, 0.10, 0.10, 0.55, 0.25, 0.10, 0.10, 0.15],  # 震+巽(生长)
        "鱼": [0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.20],  # 坎+坤(水生)
        "牛": [0.55, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15],  # 乾+坤
        "猪": [0.10, 0.10, 0.10, 0.10, 0.10, 0.20, 0.10, 0.55],  # 坤+坎
        "鸡": [0.10, 0.10, 0.10, 0.15, 0.55, 0.10, 0.10, 0.10],  # 巽+震
        "苹": [0.10, 0.35, 0.10, 0.35, 0.15, 0.10, 0.10, 0.10],  # 兑+震
        "香": [0.10, 0.35, 0.10, 0.10, 0.15, 0.10, 0.10, 0.10],  # 兑
        "面": [0.10, 0.10, 0.35, 0.10, 0.10, 0.10, 0.10, 0.40],  # 离+坤
        "包": [0.20, 0.30, 0.30, 0.15, 0.30, 0.15, 0.15, 0.15],  # 多激活
        "糖": [0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.35, 0.55],  # 坤+艮
        "盐": [0.35, 0.10, 0.10, 0.15, 0.10, 0.15, 0.10, 0.10],  # 乾+震
        "油": [0.10, 0.35, 0.10, 0.10, 0.10, 0.15, 0.10, 0.20],  # 兑+坤
        "酱": [0.10, 0.35, 0.10, 0.10, 0.10, 0.40, 0.10, 0.20],  # 兑+坎+坤
        "醋": [0.10, 0.10, 0.10, 0.35, 0.10, 0.40, 0.10, 0.10],  # 震+坎
        "米": [0.10, 0.10, 0.10, 0.10, 0.40, 0.10, 0.15, 0.50],  # 巽+坤

        # ═══ 动词（多点激活——关键！）═══
        "去": [0.10, 0.10, 0.10, 0.65, 0.25, 0.10, 0.10, 0.10],  # 震(行)+巽(入)
        "拿": [0.65, 0.10, 0.10, 0.30, 0.10, 0.10, 0.10, 0.10],  # 乾+震(手取动)
        "取": [0.55, 0.10, 0.10, 0.35, 0.10, 0.10, 0.10, 0.10],  # 乾+震(手取动)
        "放": [0.10, 0.10, 0.10, 0.10, 0.60, 0.10, 0.15, 0.40],  # 巽+坤(置入)
        "扔": [0.10, 0.65, 0.10, 0.55, 0.10, 0.10, 0.10, 0.10],  # 兑+震(毁弃)
        "丢": [0.10, 0.45, 0.30, 0.50, 0.10, 0.10, 0.10, 0.10],  # 兑+震+离
        "开": [0.10, 0.60, 0.25, 0.30, 0.10, 0.10, 0.10, 0.10],  # 兑+离+震(开启)
        "关": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.65, 0.40],  # 艮+坤(闭止)
        "闭": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.35],  # 艮+坤(闭止)
        "洗": [0.10, 0.10, 0.10, 0.25, 0.10, 0.70, 0.10, 0.35],  # 坎+震+坤(水动净)
        "擦": [0.10, 0.10, 0.10, 0.35, 0.25, 0.60, 0.10, 0.10],  # 坎+震+巽
        "刷": [0.10, 0.10, 0.10, 0.30, 0.10, 0.60, 0.10, 0.25],  # 坎+震+坤
        "扫": [0.10, 0.10, 0.10, 0.50, 0.40, 0.10, 0.10, 0.10],  # 震+巽
        "倒": [0.10, 0.10, 0.35, 0.35, 0.10, 0.40, 0.10, 0.10],  # 离+坎+震
        "切": [0.10, 0.55, 0.10, 0.25, 0.10, 0.10, 0.10, 0.30],  # 兑+震+坤(毁分)
        "盖": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.55, 0.45],  # 艮+坤(覆盖)
        "塞": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.60, 0.35],  # 艮+坤
        "插": [0.10, 0.10, 0.35, 0.25, 0.40, 0.10, 0.10, 0.10],  # 离+巽+震
        "拔": [0.10, 0.10, 0.10, 0.35, 0.50, 0.10, 0.10, 0.10],  # 巽+震
        "转": [0.10, 0.10, 0.10, 0.50, 0.40, 0.10, 0.10, 0.10],  # 震+巽(转动)
        "调": [0.10, 0.10, 0.20, 0.50, 0.40, 0.10, 0.10, 0.10],  # 震+巽+离
        "按": [0.10, 0.50, 0.10, 0.25, 0.10, 0.10, 0.10, 0.10],  # 兑+震
        "敲": [0.10, 0.30, 0.10, 0.50, 0.30, 0.10, 0.10, 0.10],  # 震+巽+兑
        "触": [0.10, 0.25, 0.10, 0.50, 0.10, 0.10, 0.25, 0.10],  # 震+兑+艮
        "压": [0.10, 0.10, 0.10, 0.40, 0.10, 0.10, 0.40, 0.20],  # 震+艮+坤
        "拉": [0.30, 0.30, 0.20, 0.40, 0.20, 0.10, 0.10, 0.10],  # 多激活
        "推": [0.30, 0.30, 0.20, 0.40, 0.30, 0.10, 0.10, 0.10],  # 多激活
        "热": [0.10, 0.10, 0.70, 0.25, 0.10, 0.10, 0.10, 0.10],  # 离+震(火热)
        "冷": [0.10, 0.10, 0.10, 0.10, 0.10, 0.65, 0.25, 0.20],  # 坎+艮+坤(寒冷)
        "冰": [0.10, 0.10, 0.10, 0.10, 0.10, 0.75, 0.25, 0.10],  # 坎(冰寒)+艮
        "看": [0.10, 0.10, 0.60, 0.30, 0.10, 0.10, 0.10, 0.10],  # 离(目明)+震(动)
        "照": [0.10, 0.10, 0.65, 0.10, 0.10, 0.10, 0.10, 0.10],  # 离(光)
        "找": [0.10, 0.10, 0.35, 0.60, 0.10, 0.10, 0.10, 0.10],  # 震+离(行动求明)
        "用": [0.60, 0.10, 0.10, 0.25, 0.10, 0.10, 0.10, 0.10],  # 乾+震(用能动)
        "打": [0.10, 0.10, 0.10, 0.70, 0.35, 0.10, 0.10, 0.10],  # 震+巽
        "烧": [0.10, 0.10, 0.65, 0.20, 0.10, 0.10, 0.10, 0.10],  # 离+震
        "煮": [0.10, 0.10, 0.50, 0.10, 0.10, 0.45, 0.10, 0.10],  # 离+坎(水火)
        "烤": [0.10, 0.10, 0.60, 0.10, 0.10, 0.15, 0.10, 0.10],  # 离+坎

        # ═══ 状态/形容词（多点激活）═══
        "干": [0.10, 0.10, 0.55, 0.10, 0.10, 0.10, 0.10, 0.35],  # 离+坤(干燥)
        "净": [0.10, 0.10, 0.15, 0.10, 0.10, 0.55, 0.10, 0.35],  # 坎+坤(净洁)
        "脏": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.15, 0.60],  # 坤(浊污)
        "湿": [0.10, 0.10, 0.10, 0.10, 0.10, 0.65, 0.10, 0.20],  # 坎+坤(水湿)
        "好": [0.40, 0.10, 0.15, 0.10, 0.10, 0.10, 0.10, 0.30],  # 乾+坤
        "坏": [0.10, 0.15, 0.10, 0.10, 0.10, 0.10, 0.25, 0.45],  # 坤+艮
        "新": [0.10, 0.10, 0.35, 0.40, 0.20, 0.10, 0.10, 0.10],  # 离+震+巽
        "旧": [0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.50, 0.40],  # 艮+坤
        "大": [0.55, 0.10, 0.10, 0.20, 0.10, 0.10, 0.10, 0.10],  # 乾+震
        "小": [0.10, 0.10, 0.10, 0.15, 0.40, 0.10, 0.35, 0.10],  # 巽+艮
    }
    if char in KNOWN_VECTORS:
        vec = KNOWN_VECTORS[char]
        dom = BAGUA[vec.index(max(vec))]
        return {"char": char, "vector": vec,
                "dominant": dom, "method": "手工向量"}

    # 规则1: 整体取象
    shape_bagua = {
        "田": "坤", "口": "坤", "囗": "坤", "四": "坤",
        "火": "离", "光": "离", "炎": "离", "灾": "离",
        "山": "艮",
        "水": "坎",
        "品": "兑", "鑫": "兑", "森": "兑",
        "大": "震", "丈": "震",
    }
    if char in shape_bagua:
        dom = shape_bagua[char]
        vec = [0.05] * 8
        vec[BAGUA.index(dom)] = 0.85
        return {"char": char, "vector": vec, "dominant": dom,
                "method": "整体取象"}

    # 规则2: 心意取向（字义仲裁）
    meaning_map = {
        "明": "离", "光": "离", "暖": "离",
        "关": "艮", "闭": "艮", "停": "艮", "止": "艮",
        "险": "坎", "危": "坎", "深": "坎", "暗": "坎",
        "热": "离", "烫": "离",
        "洗": "坎", "清": "坎",
        "喜": "兑", "悦": "兑", "说": "兑",
        "动": "震", "行": "震", "走": "震", "跑": "震",
        "开": "兑", "打": "震",
        "强": "乾", "贵": "乾", "王": "乾",
    }
    if char in meaning_map:
        dom = meaning_map[char]
        vec = [0.05] * 8
        vec[BAGUA.index(dom)] = 0.80
        return {"char": char, "vector": vec, "dominant": dom,
                "method": "心意取象"}

    # 规则3+4: 部首拆分 + 形似兜底
    comps = DECOMP.get(char, [char])
    rads = []
    for c in comps:
        m = DECOMP_MAP.get(c, c)
        if m in KNOWN_RADS:
            rads.append(m)

    if rads:
        # 多个部首 → 用YLYWLayer处理部首间乘承比应
        rad_baguas = [RADICAL_DATA[r]["membership"] for r in rads]
        layer = YLYWLayer("char")
        # 多个部首的自动角色分配（义符=物体，声符=动作，多余=物体）
        roles = ["物体", "动作"] + ["物体"] * (len(rads) - 2) if len(rads) >= 2 else ["物体"]
        result = layer.perceive_and_encode(rad_baguas, roles[:len(rads)])
        return {"char": char, "vector": result["bagua"],
                "dominant": BAGUA[result["bagua"].index(max(result["bagua"]))],
                "method": "部首YLYW乘承比应",
                "hexagram": result["hexagram"],
                "radicals_used": rads}

    # 完全未知：均匀默认
    seed = ord(char) % 8
    vec = [0.10] * 8
    vec[seed] += 0.20
    return {"char": char, "vector": vec,
            "dominant": BAGUA[seed], "method": "默认"}


# ══════════════════════════════════════════════════════════════
# HanziEngine 主类
# ══════════════════════════════════════════════════════════════

class HanziEngine:
    """
    递归YLYW汉语理解引擎。

    字/词/句三个层级，各有一个YLYWLayer实例。
    下层输出卦象 = 上层输入的"八卦隶属度"。
    """

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.char_layer = YLYWLayer("char")
        self.word_layer = YLYWLayer("word")
        self.sentence_layer = YLYWLayer("sentence")

        # 功能词集（用于分词和角色判断）
        self.func_chars = set(FUNC_WORDS.keys()) | {
            "把","被","从","在","给","跟","比","将","向","用",
            "的","地","得","了","着","过","和","与","或",
            "但","而","且","如","为","以","到","让","叫",
            "一","这","那","哪","什","怎","多","很","太","更","最",
            "都","就","才","还","又","再","已","正","每","各","别",
            "上","下","里","外","前","后","中",
        }
        # 时序标记词（用于解析动作顺序）
        self.temporal_markers = {"先","后","再","然后","接着","最后",
                                 "之前","之后","以前","以后","同时"}
        self.known_phrases = {"怎么","什么","这么","那么","哪个","那里","这里",
                              "是否","可以","应该","能够","需要","已经","正在",
                              "所有","这些","那些","其中","同时","比如","因为",
                              "虽然","但是","而且","还有","或者","然后","所以"}
        # ALFWorld家居场景高频词（扩展）
        self.alfworld_phrases = {
            "脏碗","脏盘","脏盘子","脏碗","脏的","干净的","干净的盘子","干净的碗",
            "热咖啡","热牛奶","热食物","冰凉","冷水",
            "肥皂","盘子","杯子","碗","笔","食物","苹果","牛奶","咖啡","土豆",
            "微波炉","冰箱","水槽","柜台","桌子","台子","架子","柜子","碗柜","抽屉","台灯","落地灯","沙发","椅子",
            "垃圾桶","洗手台","水槽","水池","保险箱","咖啡机",
            "用手电筒","洗干净","擦干净","热一下",
            "拿起来","放进去","拿出来","取出来","扔进去",
            "黄油刀","锅铲","光盘","钥匙链","胡椒瓶","盐瓶","遥控器","洗手液瓶","皮搋子",
            "棒球棒","纸巾盒","卫生纸","闹钟","玻璃瓶","喷壶","洗碗海绵","信用卡","笔记本",

            # 复合位置词
            "水槽边","水槽旁","冰箱里","柜台上","桌子上","台子上","架子上","抽屉里",
            "水池边","餐桌旁","椅子旁","沙发旁","保险箱里","保险箱上",
        }
        self.complement_words = {"上","下","进","出","起","开","过","到",
                                 "来","去","好","完","成","住","着","掉"}
        # 位置方位词（不是补语，是位置后缀）
        self.location_particles = {"边","旁","侧","附近"}
        # 功能词中的方位词（可能需要与前面的位置词合并）
        self.func_location_chars = {"上","下","里","外","前","后"}
        self.action_chars = {"打","开","关","按","压","拉","推","放","拿","取","扔","丢","抛",
                             "洗","清","擦","扫","刷","烧","热","冷","加","减",
                             "设","调","换","选","点","拧","插","拔","拨","转",
                             "检","查","铲","切","削","砍","劈",
                             "找","寻","搜","看","瞧","望","观","见","听","闻",
                             "端","捧","握","举","托","抱","扶","提",
                             "靠","贴","摆","铺","盖","罩","扣","封","堵","埋",
                             "坐","站","立","躺","蹲","跪",
                             "踩","踢","跨","迈","登","踏",
                             "穿","戴","套","披","挂",
                             "泡","烫","煮","蒸","烤","煎","炸","炒",
                             "堆","叠","收","拾","分","合",
                             "包","裹","卷","扎","系","捆",
                             "推","拉","拖","拽","扯","撕","抽",
                             "移"}
        self.noun_endings = {"机","炉","箱","器","键","具","杯","碗","盘","锅",
                             "桌","椅","柜","灯","扇","门","窗","瓶","罐","池",
                             "床","台","架","线","缆","板","卡","纸","布","衣",
                             "果","蔬","菜","肉","米","面","蛋","奶","油","酱",
                             "药","水","火","气","电","光","声","影","形",
                             "子","食","物","品","具","料","汁","汤","渣",
                             "桶","皂","笔","刀","勺","叉","壶"}
        # 位置后缀字（用于识别"桌子上/水槽边/冰箱里"等位置修饰）
        self.location_suffix = {"上","下","里","外","前","后","旁","边","侧","附近","旁边"}
        # 属性形容词（用于识别"脏/干净/热/冷"等物体修饰）
        self.attribute_words = {"脏","干净","热","冷","冰","新鲜","坏的","湿","干",
                               "大","小","红","黄","蓝","旧","新","破"}

    # ══ L0: 单字 ══
    def char(self, char: str) -> Dict:
        """字级卦象：测字六法 → 8维八卦隶属度"""
        result = char_to_bagua(char)
        # 为char输出也增加hex64（单字六爻→64卦分布）
        if "hex64" not in result:
            try:
                yao = result.get("yao_vector", [0.5]*6)
                if len(yao) != 6:
                    yao = [0.5]*6
                result["hex64"] = self._match_64hexagrams(yao)
            except:
                result["hex64"] = [0.0]*64
        return result

    # ══ L2: 词语 ══
    def word(self, word: str) -> Dict:
        """
        词级卦象：用YLYWLayer处理字间乘承比应。

        每个字作为一个"元素"输入YLYWLayer，
        字的卦象作为元素的八卦隶属度。
        字间的乘承比应由YLYWLayer自动计算。
        """
        if len(word) <= 1:
            return self.char(word)

        chars = list(word)
        char_results = [self.char(c) for c in chars]
        char_baguas = [r["vector"] for r in char_results]
        char_roles = []

        for c in chars:
            if c in self.func_chars:
                char_roles.append("虚词")
            elif any(ac in c for ac in self.action_chars):
                char_roles.append("动作")
            elif c in self.complement_words:
                char_roles.append("补语")
            else:
                char_roles.append("物体")

        result = self.word_layer.perceive_and_encode(char_baguas, char_roles)
        dom_idx = result["bagua"].index(max(result["bagua"]))

        return {
            "word": word,
            "bagua": result["bagua"],
            "yao_vector": result["yao_vector"],
            "hex64": result["hex64"],            # 64维卦象分布
            "dominant": BAGUA[dom_idx],
            "hexagram": result["hexagram"],
            "hexagram_score": result["hexagram_score"],
            "relations": result["relations"],
            "chars": [{"char": c, "dominant": r["dominant"]}
                      for c, r in zip(chars, char_results)],
        }

    # ══ L3: 句子 ══
    def sentence(self, text: str) -> Dict:
        """
        句级卦象：用YLYWLayer处理词间乘承比应。

        每个词的元素卦象来自 word() 的输出，
        词间的乘承比应 + 跨虚词连接由YLYWLayer自动处理。
        """
        segments = self._segment(text)
        if not segments:
            return self._empty_sentence(text)

        # ★ 如果只有一个segment，直接返回词级结果
        # （句级的perceive_and_encode只有一个元素时无法区分动作/物体）
        if len(segments) == 1:
            seg = segments[0]
            if len(seg) <= 1:
                wr = self.char(seg)
            else:
                wr = self.word(seg)
            role = self._guess_role(seg, wr)
            return self._single_segment_sentence(text, seg, wr, role)

        # 每个词的卦象和角色
        word_results = []
        word_baguas = []
        word_roles = []
        word_rels = []

        for seg in segments:
            if len(seg) <= 1:
                wr = self.char(seg)
            else:
                wr = self.word(seg)

            word_results.append(wr)
            # 词级8维卦象作为句级输入（64维降维到8维后丢失了区分度）
            word_baguas.append(wr.get("bagua", wr.get("vector", [0.15]*8)))

            role = self._guess_role(seg, wr)
            word_roles.append(role)

        # 跨虚词连接预设
        preset_rels = []
        real_indices = [i for i, r in enumerate(word_roles) if r != "虚词"]
        for k in range(len(real_indices) - 1):
            i, j = real_indices[k], real_indices[k + 1]
            if j - i == 2:  # 中间有一个虚词
                if word_roles[i] == "动作" and word_roles[j] in ("物体", "状态"):
                    preset_rels.append({
                        "from": i, "to": j, "type": "乘(跨虚词)",
                        "from_dom": word_results[i].get("dominant", "?"),
                        "to_dom": word_results[j].get("dominant", "?"),
                    })
                elif word_roles[i] in ("物体", "状态") and word_roles[j] == "动作":
                    preset_rels.append({
                        "from": i, "to": j, "type": "承(跨虚词)",
                        "from_dom": word_results[i].get("dominant", "?"),
                        "to_dom": word_results[j].get("dominant", "?"),
                    })

        result = self.sentence_layer.perceive_and_encode(
            word_baguas, word_roles, preset_rels)

        # 六爻模板覆写已移除（V12: 让YLYWLayer乘承比应自然处理名词差异）

        # 人类可读格式
        readable_rels = []
        for rel in result["relations"]:
            fi = rel.get("from", 0) if isinstance(rel.get("from"), int) else 0
            ti = rel.get("to", 1) if isinstance(rel.get("to"), int) else 1
            if isinstance(fi, int) and fi < len(segments):
                readable_rels.append({
                    "from": segments[fi],
                    "to": segments[ti] if ti < len(segments) else "?",
                    "relation": rel["type"],
                    "meaning": "%s→%s" % (
                        rel.get("from_dom", "?"), rel.get("to_dom", "?")),
                })

        return {
            "text": text,
            "segments": segments,
            "segment_bagua": word_baguas,
            "segment_dominant": [w.get("dominant", "?") for w in word_results],
            "segment_role": word_roles,
            "segment_hexagram": [w.get("hexagram", "?") for w in word_results],
            "mutua_relations": readable_rels,
            "main_hexagram": result["hexagram"],
            "hexagram_score": result["hexagram_score"],
            "yao_vector": result["yao_vector"],
            "hex64": result["hex64"],  # 64维卦象分布
            "sentence_bagua": result["bagua"],
            "dominant_bagua": BAGUA[result["bagua"].index(max(result["bagua"]))],
            "interpretation": self._interpret(text, segments, word_results,
                                              readable_rels, result),
            "dependencies": self._parse_dependencies(segments, word_roles, word_results),
        }

    # ── 分词 ──
    def _segment(self, text: str) -> List[str]:
        """
        改良分词器：正向最大匹配 + 动词/名词字典 + 单字分裂
        
        核心策略：
        1. 优先匹配已知多字词（known_phrases + known_words）
        2. 从右向左扫描，遇到动作字/补语/名词结尾字时尝试切分
        3. 功能词（虚词）作为必分割点
        4. 最终确保每个segment都尽量是语义单元
        """
        # 合并所有已知词（按词长降序排列，优先匹配长词）
        known_dict = self.known_phrases | self.alfworld_phrases | {
            # ALFWorld/家居场景常用双字词
            "盘子","杯子","碗筷","碗柜","碗盘","毛巾","衣服","抹布",
            "苹果","香蕉","土豆","番茄","蔬菜","鸡蛋","牛奶","面包","萝卜","白菜",
            "冰箱","微波","烤箱","炉灶","水槽","水池","洗碗",
            "柜台","餐桌","书桌","衣柜","柜子","桌子","抽屉","架子","凳子","厨柜","碗柜",
            "微波炉","保险箱","咖啡机",
            "干净","脏的","湿的","干的","热的","冷的","冰的","熟的","生的","湿的",
            "打开","关闭","清洗","加热","冷却","设置","检查","清洁","擦拭","洗洗","刷刷",
            "放到","放入","拿出","取出","端起","拿起","放下","放回","打开","关上",
            "启动","停止","开始","完成","重新",
            "两个","三个","所有","这些","那些","一个","那个","哪个","这个",
            "饮料","蔬菜","食物","水果","厨房","餐桌","餐盘",
            "进去","出来","上来","下去",
            # 动作+目标常见组合
            "去柜台","去冰箱","去水槽","去柜子","去桌子","去抽屉","去微波","去微波炉","去保险箱",
            "拿盘子","拿杯子","拿苹果","拿食物","拿土豆","拿碗",
            "放柜台","放冰箱","放桌子","放柜子","放盒子","放架子","放垃圾桶",
            "洗盘子","洗杯子","洗碗","洗苹果","洗菜",
            "热食物","热菜","热牛奶",
            "冷饮料","冷牛奶",
            "找盘子","找杯子","找苹果","找食物","找工具","找水槽","找冰箱","找柜台","找桌子","找柜子",
            "找微波","找灯","找台灯","找落地灯",
            # 灯类物体
            "台灯","落地灯","灯光","光源",
            "看看","洗洗","擦擦","刷刷","热热","冷冷",
            "看看","洗洗","擦擦","刷刷","热热","冷冷",
            # 看/看看+物体（look_at场景专用）— 只保留看+物体整体，不保留看看+物体
            "看闹钟","看棒球","看篮球","看书","看碗","看盒子","看光盘","看手机",
            "看信用卡","看钥匙","看笔记本","看杯子","看报纸","看铅笔","看遥控器",
            "看雕像","看花瓶","看卫生纸","看面包","看鸡蛋","看锅","看肥皂","看锅铲","看皮搋子",
            "看棒球棒","看遥控器","看钥匙链","看笔记本",

            # 数量+物体组合
            "两块肥皂","两块光盘","两块盘子","两块杯子","两块碗","两块苹果","两块面包","两块鸡蛋",
            "两块胡椒瓶","两块钥匙链","两块卫生纸","两块枕头","两块AppleSliced",


        }
        
        # 补语集合（用于辅助拆分）
        compound_complements = {"进去","出来","上来","下去","过来","回去"}
        
        # 构建按词长倒序的列表
        known_sorted = sorted(known_dict, key=len, reverse=True)
        
        def _merge_action_with_right(seg: str) -> List[str]:
            """处理动词+补语/名词的黏合"""
            if not seg:
                return []
            
            # 先尝试匹配已知词（如果完整匹配则直接返回该词）
            if seg in known_dict:
                return [seg]
            # 匹配已知前缀
            for kw in known_sorted:
                if seg.startswith(kw) and len(kw) <= len(seg):
                    rest = seg[len(kw):]
                    # 如果后缀是补语或名词结尾，也切
                    if rest in self.complement_words:
                        return [kw, rest]
                    if len(rest) == 1 and rest in self.noun_endings:
                        return [kw, rest]
                    # 后缀本身也可能是已知词
                    rest_parts = _merge_action_with_right(rest)
                    return [kw] + rest_parts
            
            # 按动作字位置拆分
            for i, c in enumerate(seg):
                if c in self.action_chars and i > 0:
                    # 找到了动作字在中间，前面是名词
                    left = seg[:i]
                    right = seg[i:]
                    # 对right递归拆分
                    right_parts = _merge_action_with_right(right)
                    left_parts = _merge_action_with_right(left)
                    return left_parts + right_parts
                if c in self.complement_words and i > 0:
                    # 补语在中间，切分动词+补语
                    left = seg[:i]
                    right = seg[i:]
                    left_parts = _merge_action_with_right(left)
                    return left_parts + [right]
                if c in self.noun_endings and i > 0:
                    # 名词结尾字，切出名词
                    left = seg[:i+1]
                    right = seg[i+1:]
                    if right:
                        right_parts = _merge_action_with_right(right)
                        return [left] + right_parts
                    return [left]
            
            # 都没有匹配到，看第一个字是否是动作
            if seg and seg[0] in self.action_chars:
                # 动词开头：
                # 1) 检查末尾是否有补语
                for i in range(len(seg)-1, 0, -1):
                    if seg[i:] in self.complement_words:
                        return [seg[:i], seg[i:]]
                    if seg[i:] in compound_complements:
                        return [seg[:i], seg[i:]]
                # 2) 检查是否有名词结尾字，切分：动词+名词对象
                for i in range(len(seg)-1, 0, -1):
                    if seg[i] in self.noun_endings:
                        left = seg[:i]
                        right = seg[i:]
                        if left:
                            return _merge_action_with_right(left) + [right]
                        return [right]
                # 3) 动词+整体宾语
                return [seg]
            
            # 检查末尾复音补语
            if len(seg) >= 2 and seg[-2:] in compound_complements:
                return [seg[:-2], seg[-2:]]
            if len(seg) >= 2 and seg[-1] in self.complement_words:
                return [seg[:-1], seg[-1:]]
            
            # 单字或短词，直接返回
            if len(seg) <= 2:
                return [seg]
            
            # 长串：找第一个名词结尾字，切开
            for i, c in enumerate(seg):
                if c in self.noun_endings and i < len(seg)-1:
                    left = seg[:i+1]
                    right = seg[i+1:]
                    return [left] + _merge_action_with_right(right)
            
            return [seg]

        def _split_by_func(s: str) -> List[str]:
            """按功能词分割"""
            if not s:
                return []
            # 优先按功能词分割（确保虚词能正确分离）
            for i, c in enumerate(s):
                if c in self.func_chars:
                    left = s[:i].strip()
                    right = s[i+1:].strip()
                    result = []
                    if left:
                        result.extend(_merge_action_with_right(left))
                    result.append(c)
                    if right:
                        result.extend(_split_by_func(right))
                    return result
            # 没有功能词，对整个串做动作/名词拆分
            return _merge_action_with_right(s)
        
        segments = _split_by_func(text)
        
        # 后处理：合并或拆分个别case
        final = []
        for i, seg in enumerate(segments):
            if not seg:
                continue
            # 位置方位后缀（"边","里","上"等）前如果有物体词，合并
            if seg.strip() in self.location_particles and final:
                prev = final[-1].strip()
                # 如果前一个词不是纯功能词（且不是孤立虚词），合并
                if prev not in self.func_chars and prev not in self.complement_words:
                    final[-1] = final[-1] + seg.strip()
                    continue
            # 位置方位后缀（"上","里","下"等）— 这些在func_chars中
            # 但注意"后"是时序标记词，不要与动词合并
            if seg.strip() in ("上","里","下","外","前") and final:
                prev = final[-1].strip()
                # 如果前一个词是物体词或者以物体结尾字结束，合并
                if any(prev.endswith(e) for e in self.noun_endings) or prev in self.alfworld_phrases:
                    final[-1] = final[-1] + seg.strip()
                    continue
            # 时序标记词"后"不与前面的词合并
            final.append(seg)
        
        return final

    # ── 角色判断 ──
    def _guess_role(self, text: str, word_result: Dict) -> str:
        if text in self.func_chars:
            return "虚词"
        if text in self.complement_words:
            return "补语"
        if any(text.endswith(e) for e in self.noun_endings):
            return "物体"
        # 以位置方位词结尾的判为物体（如"水槽边""抽屉里""柜台上"）
        if any(text.endswith(e) for e in self.location_particles):
            return "物体"
        if any(text.endswith(e) for e in self.func_location_chars if e not in self.complement_words):
            # 检查前面是否有位置词词根（如在"抽屉里"中"抽屉"是位置词）
            for loc in ["水槽","冰箱","柜台","柜子","桌子","台子","架子","抽屉",
                       "厨房","卧室","客厅","书架","餐桌"]:
                if loc in text and text != loc:
                    return "物体"
        if any(c in text for c in self.action_chars):
            return "动作"

        # 兜底：先用action_chars检查（覆盖已知动词）
        if any(c in self.action_chars for c in text):
            return "动作"
        dom = word_result.get("dominant", "?")
        if dom in ("坎", "巽"):
            return "状态"
        if dom in ("坤", "艮", "离"):
            return "物体"
        if dom in ("震", "乾", "兑"):
            common_verb_rad = {"扌","氵","火","口","讠","辶","彳","刂","亻","力"}
            for c in text:
                if c in common_verb_rad:
                    return "动作"
            # 重复动词（看看、洗洗等）也是动作
            if len(text) == 2 and text[0] == text[1] and text[0] in self.action_chars:
                    return "动作"
        return "物体"  # 默认物体

    # ── 语义解释 ──
    def _single_segment_sentence(self, text: str, seg: str,
                                  word_result: Dict, role: str) -> Dict:
        """
        单segment句子的快捷路径——直接使用词级或字级结果。
        避免只有一个元素时 YLYWLayer 退化导致信息损失。
        """
        yao = word_result.get("yao_vector", [0.5]*6)
        bagua = word_result.get("bagua", [0.25]*8)
        hex64 = word_result.get("hex64", [0.0]*64)
        hex_name = word_result.get("hexagram", "?")
        hex_score = word_result.get("hexagram_score", 0.0)
        dominant = word_result.get("dominant", "?")

        sentence_bagua = [(v + 0.1) / 1.1 for v in bagua]

        return {
            "text": text,
            "segments": [seg],
            "segment_bagua": [bagua],
            "segment_dominant": [dominant],
            "segment_role": [role],
            "segment_hexagram": [hex_name],
            "mutua_relations": [],
            "main_hexagram": hex_name,
            "hexagram_score": hex_score,
            "yao_vector": [round(v, 4) for v in yao],
            "hex64": [round(v, 4) for v in hex64],
            "sentence_bagua": [round(v, 4) for v in sentence_bagua],
            "dominant_bagua": dominant,
            "interpretation": self._interpret(text, [seg], [word_result], [],
                {"hexagram": hex_name, "yao_vector": yao}),
            "dependencies": [],
        }

    def _interpret(self, text, segments, word_results, rels, result):
        parts = " | ".join("%s[%s]" % (s, w.get("dominant", "?"))
                          for s, w in zip(segments, word_results))
        rel_str = " | ".join("%s%s%s" % (
            r["from"],
            {"乘":"⊃","承":"⊂","比":"‖","应":"≈","乘(跨虚词)":"?→","承(跨虚词)":"?←"}.get(r["relation"], "?"),
            r["to"]
        ) for r in rels[:3]) if rels else "—"

        yao_types = "".join("—" if v >= 0.5 else "-" for v in result["yao_vector"])
        return "词: %s | 互卦: %s | 主卦:%s | %s" % (
            parts, rel_str, result["hexagram"], yao_types)

    def _empty_sentence(self, text):
        return {"text": text, "segments": [], "segment_bagua": [],
                "segment_dominant": [], "segment_role": [],
                "segment_hexagram": [], "mutua_relations": [],
                "main_hexagram": "?", "hexagram_score": 0.0,
                "hex64": [0.0]*64,
                "yao_vector": [0.5]*6, "sentence_bagua": [0.25]*8,
                "dominant_bagua": "?", "interpretation": "空句"}

    # ── 相似度 ──
    def similarity(self, a: str, b: str) -> float:
        """基于句级卦象的余弦相似度"""
        ra = self.sentence(a)["sentence_bagua"]
        rb = self.sentence(b)["sentence_bagua"]
        dot = sum(x*y for x, y in zip(ra, rb))
        na = math.sqrt(sum(v*v for v in ra))
        nb = math.sqrt(sum(v*v for v in rb))
        if na == 0 or nb == 0:
            return 0.0
        return round(dot / (na * nb), 4)

    # ── 解释 ──
    def explain(self, text: str) -> str:
        r = self.sentence(text)
        lines = ["=" * 55, "YLYW递归推理 — 「%s」" % text, "=" * 55]
        lines.append("\n▎分词: " + " | ".join(r["segments"]))
        lines.append("\n▎词级卦象:")
        for i, seg in enumerate(r["segments"]):
            hex_name = r["segment_hexagram"][i]
            dom = r["segment_dominant"][i]
            lines.append("  %s → %s(主导:%s)" % (seg, hex_name, dom))
        lines.append("\n▎词间互卦:")
        for rel in r["mutua_relations"][:5]:
            lines.append("  %s %s %s" % (
                rel["from"], rel["relation"], rel["to"]))
        lines.append("\n▎句级六爻: " + " ".join("%.3f" % v for v in r["yao_vector"]))
        lines.append("▎句级主卦: %s (%.4f)" % (r["main_hexagram"], r["hexagram_score"]))
        lines.append("▎语义: " + r["interpretation"])
        return "\n".join(lines)

    def to_ylyw(self, text: str) -> Dict:
        """输出兼容 PriorManual 的格式"""
        s = self.sentence(text)
        return {
            "text": text,
            "yao_vector": s["yao_vector"],
            "trigram_memberships": s["sentence_bagua"],
            "dominant_trigram_guess": s["dominant_bagua"],
            "best_hexagram_guess": s["main_hexagram"],
            "hexagram_match_score": s["hexagram_score"],
        }

    # ══ 依存关系解析（卦象驱动版） ══
    def _parse_dependencies(self, segments: List[str], roles: List[str],
                           word_results: List[Dict] = None) -> List[Dict]:
        """
        基于卦象推理的依存关系解析。
        
        不依赖任何硬编码词表，只用卦象的先验语义来判断修饰关系。
        
        八卦的天然语义（用于判定依存）：
          艮(止/藏)、坤(载/容) → 位置/容器 → 常作为位置修饰语
          坎(水/险) → 液体/寒冷 → 常作为属性修饰语（冷水/脏）
          离(火/明) → 热/光/干 → 常作为属性修饰语（热/干净）
          震(动)、乾(健)、兑(悦) → 动作性 → 不会是修饰语
          巽(入/散) → 中性/工具 → 可能是被修饰的中心词
        
        判断规则：
          1. 两个物体紧邻或相隔"的"时
             - 如果前一个的主导八卦是艮/坤 → loc_mod（位置修饰）
             - 如果前一个的主导八卦是坎/离 → attr_mod（属性修饰）
          2. 通过互卦关系中的"应"来跨距离判断修饰关系
        """
        dependencies = []
        
        # 构建bagua信息索引
        seg_bagua = {}  # idx -> dominant_bagua
        if word_results:
            for i, wr in enumerate(word_results):
                if i < len(segments):
                    dom = wr.get("dominant", "?")
                    seg_bagua[i] = dom
        
        def is_position_bagua(bg, seg=""):
            """卦象是否偏向位置/容器语义
            额外检查：即使卦象不是艮/坤，但如果以方位后缀结尾也是位置
            """
            if bg in ("艮", "坤"):
                return True
            # 以方位后缀结尾的词（如"桌子旁""水槽边"）也是位置
            if any(seg.endswith(e) for e in ("边","旁","侧","里","上","下")):
                return True
            return False
        
        def is_attribute_bagua(bg):
            """卦象是否偏向属性/状态语义
            坎(水/寒) → 冷/湿/脏的属性
            离(火/明) → 热/干净/明亮的属性
            但要注意：以方位后缀结尾的词即使是坎卦也是位置，不是属性
            """
            return bg in ("坎", "离")
        
        def is_action_bagua(bg):
            """卦象是否偏向动作语义"""
            return bg in ("震", "乾", "兑")
        
        # ---- 规则1: 相邻物体间通过"的"连接的修饰关系 ----
        obj_indices = [i for i, r in enumerate(roles) if r == '物体']
        
        for j in range(len(obj_indices) - 1):
            i1 = obj_indices[j]
            i2 = obj_indices[j + 1]
            between = segments[i1+1:i2] if i2 > i1 + 1 else []
            
            # 只处理中间有"的"或全是虚词的情况
            if not ("的" in between or all(s in self.func_chars for s in between)):
                continue
            
            if segments[i1] == segments[i2]:
                continue
            
            bg1 = seg_bagua.get(i1, "?")
            bg2 = seg_bagua.get(i2, "?")
            
            # 前一个卦象 → 修饰关系类型
            if is_position_bagua(bg1, segments[i1]):
                dep_type = "loc_mod"
                dependencies.append({
                    "modifier": segments[i1],
                    "head": segments[i2],
                    "type": dep_type,
                    "modifier_idx": i1,
                    "head_idx": i2,
                    "marker": "的" if "的" in between else "",
                    "reason": f"{bg1}→位置修饰",
                })
            elif is_attribute_bagua(bg1):
                dep_type = "attr_mod"
                dependencies.append({
                    "modifier": segments[i1],
                    "head": segments[i2],
                    "type": dep_type,
                    "modifier_idx": i1,
                    "head_idx": i2,
                    "marker": "的" if "的" in between else "",
                    "reason": f"{bg1}→属性修饰",
                })
        
        # ---- 规则2: 通过互卦关系中的"应"来识别跨距离修饰 ----
        # 互卦关系已经在sentence()中计算好了
        # 两个物体间如果有"应"关系，且前一个的卦象偏向位置/属性
        # 则判断为修饰关系
        # 注意：这里不直接依赖mutua_relations，而是从seg_bagua推断
        # 因为互卦关系已经是sentence()的输出，这里只做解析
        
        # ---- 规则3: 位置方位后缀词（以"边/里/上/旁"结尾）作为修饰语 ----
        for i, seg in enumerate(segments):
            if roles[i] != '物体':
                continue
            bg = seg_bagua.get(i, "?")
            if not is_position_bagua(bg, seg):
                continue
            # 如果后面紧跟着"的"+物体，建立位置修饰关系
            if i + 2 < len(segments) and segments[i+1] == "的" and roles[i+2] == '物体':
                center = segments[i+2]
                if center != seg:
                    already = any(d["modifier_idx"] == i and d["head_idx"] == i+2 for d in dependencies)
                    if not already:
                        dependencies.append({
                            "modifier": seg,
                            "head": center,
                            "type": "loc_mod",
                            "modifier_idx": i,
                            "head_idx": i + 2,
                            "marker": "的",
                            "reason": f"{bg}+方位后缀→位置修饰",
                        })
        
        # 去重
        seen = set()
        unique_deps = []
        for d in dependencies:
            key = (d["modifier_idx"], d["head_idx"])
            if key not in seen:
                seen.add(key)
                unique_deps.append(d)
        
        return unique_deps

    # ══ 时序解析 ══
    def parse_temporal(self, text: str) -> Dict:
        """
        从中文任务描述中解析动作的时序关系。
        
        利用虚词标记识别动作的先后顺序，不受动词出现位置影响。
        
        时序标记词及其含义：
          "先" → 标记它后面的动作为前序
          "后" → 标记它前面的动作为前序
          "再" → 标记它后面的动作为后续
          "然后" → 标记后续关系
          "之前" → 标记它前面的动作发生在后面
          "之后" → 标记它前面的动作发生在前面
          
        返回：
          {
            "actions": [动作1, 动作2, ...],  # 按执行顺序排列
            "raw_verbs": [句中出现的动词],
            "markers": [
              {"type": "顺序/倒装", "before": ..., "after": ..., "marker": "先/后/再/之前/之后"},
            ],
            "order_type": "顺序/倒装/并列/条件"
          }
        """
        # 先用sentence分词
        r = self.sentence(text)
        segments = r["segments"]
        seg_roles = r["segment_role"]
        
        # 提取动词及其位置
        verbs = [(i, segments[i]) for i in range(len(segments)) 
                 if seg_roles[i] == '动作']
        
        # 检测未正确合并的"之前/之后"（分词可能拆成"之"+"前"/"后"）
        merged_segments = list(segments)
        merged_roles = list(seg_roles)
        for i in range(len(merged_segments) - 1, -1, -1):
            if merged_segments[i] == "之" and i + 1 < len(merged_segments) and merged_segments[i+1] in ("前", "后"):
                merged_segments[i] = "之" + merged_segments[i+1]
                del merged_segments[i+1]
                merged_roles[i] = "虚词"
                del merged_roles[i+1]
        # 清理空的segment
        merged_segments = [s for s in merged_segments if s]
        # 重新建立verbs
        verbs = []
        for i, s in enumerate(merged_segments):
            # 对每个segment重新判断角色
            # 如果是动作字表中的字符，判为动作
            if any(c in self.action_chars for c in s) and s not in self.func_chars:
                # 排除"热咖啡"这种名词被误判为动词
                # 检查是否有名词结尾特征
                if not any(s.endswith(e) for e in self.noun_endings):
                    verbs.append((i, s))
        segments = merged_segments
        seg_roles = merged_roles
        
        # 提取虚词中的时序标记
        markers = []
        for i, seg in enumerate(segments):
            if seg in self.temporal_markers:
                marker_info = {"marker": seg, "index": i}
                
                if seg == "先":
                    for vi, v in verbs:
                        if vi > i:
                            marker_info["marks"] = v
                            marker_info["type"] = "前序"
                            break
                elif seg == "后":
                    for vi, v in reversed(verbs):
                        if vi < i:
                            marker_info["marks"] = v
                            marker_info["type"] = "前序"
                            break
                elif seg == "再":
                    for vi, v in verbs:
                        if vi > i:
                            marker_info["marks"] = v
                            marker_info["type"] = "后续"
                            break
                elif seg == "之前":
                    # "...之前" 标记在它之前出现的动作是后执行的
                    for vi, v in reversed(verbs):
                        if vi < i:
                            marker_info["marks"] = v
                            marker_info["type"] = "倒装"
                            break
                elif seg == "之后":
                    for vi, v in reversed(verbs):
                        if vi < i:
                            marker_info["marks"] = v
                            marker_info["type"] = "前序"
                            break
                
                markers.append(marker_info)
        
        # 检查是否有"先"和"再"同时出现的"先...再..."结构
        has_xian = any(m["marker"] == "先" for m in markers)
        has_zai = any(m["marker"] == "再" for m in markers)
        has_hou = any(m["marker"] == "后" for m in markers)
        has_zhihou = any(m["marker"] == "之后" for m in markers)
        has_zhiqian = any(m["marker"] == "之前" for m in markers)
        
        # 解析明显的顺序标记
        tmp_actions = []
        
        if has_xian and has_zai:
            # "先...再..."结构 → 先出现的动词在前，后出现的后
            xian_verbs = []
            zai_verbs = []
            in_xian = False
            in_zai = False
            for seg in segments:
                if seg == "先":
                    in_xian = True
                    in_zai = False
                elif seg == "再":
                    in_xian = False
                    in_zai = True
                elif seg_roles[segments.index(seg)] == '动作' if seg in segments else False:
                    idx = segments.index(seg)
                    if seg_roles[idx] == '动作':
                        if in_xian:
                            xian_verbs.append(seg)
                        if in_zai:
                            zai_verbs.append(seg)
            # 修正：直接从verbs中判断位置
            xian_idx = next((i for i, s in enumerate(segments) if s == "先"), -1)
            zai_idx = next((i for i, s in enumerate(segments) if s == "再"), -1)
            
            before_verbs = [v for i, v in verbs if i > xian_idx and (zai_idx < 0 or i < zai_idx)]
            after_verbs = [v for i, v in verbs if i > zai_idx]
            tmp_actions = before_verbs + after_verbs
            order_type = "顺序(先...再...)"
        
        elif has_hou or has_zhihou:
            # "...后"或"...之后"结构 → 标记前面的动词在前
            hou_kw = "后" if has_hou else "之后"
            hou_idx = next((i for i, s in enumerate(segments) if s == hou_kw), -1)
            before = [v for i, v in verbs if i < hou_idx]
            after = [v for i, v in verbs if i > hou_idx]
            tmp_actions = before + after
            order_type = f"顺序(...{hou_kw}...)"
        
        elif has_zhiqian:
            # "...之前"结构 → "之前"前面的动词在"之后"执行（倒装）
            qian_idx = next((i for i, s in enumerate(segments) if s == "之前"), -1)
            before = [v for i, v in verbs if i < qian_idx]
            after = [v for i, v in verbs if i > qian_idx]
            # 倒装：before中的动作实际上在"之后"执行
            tmp_actions = after + before
            order_type = "倒装(...之前...)"
        
        elif len(verbs) <= 1:
            tmp_actions = [v for _, v in verbs]
            order_type = "单动作"
        
        elif has_xian and not has_zai:
            # 只有"先"没有"再"的情况（如"为了...先把..."）
            xian_idx = next((i for i, s in enumerate(segments) if s == "先"), -1)
            before = [v for i, v in verbs if i > xian_idx]
            after = [v for i, v in verbs if i < xian_idx]
            tmp_actions = before + after
            order_type = "顺序(有先标记)"
        
        else:
            # 无显式标记
            tmp_actions = [v for _, v in verbs]
            # 检查"为了"等倒装暗示
            has_weile = any("为了" in s or (s == "为" and i+1 < len(segments) and segments[i+1] in ("了","着")) for i, s in enumerate(segments))
            if has_weile:
                order_type = "倒装(为了)"
            else:
                order_type = "顺序(默认)"
        
        # 去重（同一个动词可能在多个位置出现）
        seen = set()
        actions = []
        for v in tmp_actions:
            if v not in seen:
                seen.add(v)
                actions.append(v)
        
        return {
            "actions_ordered": actions,
            "raw_verbs": [v for _, v in verbs],
            "markers": markers,
            "order_type": order_type,
        }

    def __repr__(self):
        return "HanziEngine(递归YLYW: 字→词→句)"
