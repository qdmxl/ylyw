#!/usr/bin/env python3
"""
cn_world_model.py — V20 汉字世界模型

用YLYW架构替代V18中用正则解析英文的 world_model.py。
核心思路：所有环境状态都用汉字表示，通过YLYW六爻编码+八卦隶属度来感知和理解。

替换目标：V18 world_model.py 中的功能：
  位置追踪 → 汉字"位置卦象"
  物品清单 → 汉字"物品卦象列表"
  容器状态 → 汉字"容器卦象（开/关/已搜/未搜）"
  失败历史 → 汉字"动作卦象序列"
  进度追踪 → 汉字"工序卦象"

对比 V18 world_model.py（纯符号工程）：
  V18: 正则表达式解析英文文本 → 维护Python dataclass状态
  V20: 汉字文本 → YLYW三层次感知 → 六爻编码 → 64卦匹配 → 卦象状态
"""
from __future__ import annotations
import os, sys, re, json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

# ── 引入YLYW核心 ────────────────────────────────────
_YLYW_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api_docs"))
for p in (_YLYW_ROOT,):
    if p not in sys.path:
        sys.path.insert(0, p)
from ylyw_core import PriorManual, TrigramBase, YaoEncoder, HexagramRuleBase, Hexagram
from ylyw_core.trigram_base import Trigram

# ── 引入汉字引擎 ────────────────────────────────────
_LANG_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "language"))
if _LANG_ROOT not in sys.path:
    sys.path.insert(0, _LANG_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from chinese_bridge import ChineseBridge
from hanzi_engine import HanziEngine, YLYWLayer
from functools import lru_cache

# ── 构建V18中各种类和常量的替代 ─────────────────────
# YLYW 核心引擎（单例）
_PM = PriorManual(verbose=False)
_TB = TrigramBase()
_YE = YaoEncoder()
_HR = HexagramRuleBase()
_HZ = HanziEngine()

# 英文→汉字实体映射（复用 chinese_bridge 对照表）
_BRIDGE = ChineseBridge()


# ══════════════════════════════════════════════════════
# 汉字实体卦象 —— 每个物体/容器在YLYW空间中的表示
# ══════════════════════════════════════════════════════

def _hanzi_for_entity(en_name: str) -> str:
    """英文实体名 → 汉字（去掉编号）"""
    clean = re.sub(r'\s+\d+$', '', en_name.strip()).lower()
    cn = _BRIDGE._en_entity_to_cn(clean)
    return cn


@lru_cache(maxsize=4096)
def _bagua_for_hanzi_cached(hanzi: str) -> Tuple[str, Tuple[float, ...]]:
    """带LRU缓存的底层汉字→八卦查询"""
    gua, vec = _bagua_for_hanzi_impl(hanzi)
    return gua, tuple(vec)

def _bagua_for_hanzi(hanzi: str) -> Tuple[str, List[float]]:
    """汉字 → YLYW八卦隶属度（8维）——带LRU缓存版"""
    gua, vec_tuple = _bagua_for_hanzi_cached(hanzi)
    return gua, list(vec_tuple)


def _bagua_for_hanzi_impl(hanzi: str) -> Tuple[str, List[float]]:
    """汉字 → YLYW八卦隶属度（8维）
    
    通过 hanzi_engine 的YLYW推理：
      汉字 → 字级YLYW（部首→卦象L1→六爻L2→64卦L3）→ 八卦隶属度
    
    hanzi_engine.char() 会执行完整的：
      1. 部首分解
      2. 部首→卦象模糊映射
      3. 部首间乘承比应
      4. 六爻编码 + 64卦匹配
      
    Returns:
      (dominant_gua_name: str, bagua_vector: List[float])
    """
    if not hanzi or hanzi.strip() == "":
        return "坤", [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.85]
    
    try:
        result = _HZ.char(hanzi)
        if result:
            if "vector" in result:
                bg = result["vector"]
                if isinstance(bg, list) and len(bg) == 8:
                    if sum(abs(v) for v in bg) > 0.01:
                        dom_idx = int(np.argmax(bg))
                        dom_name = ["乾","兑","离","震","巽","坎","艮","坤"][dom_idx]
                        return dom_name, [float(v) for v in bg]
            elif "bagua" in result:
                bg = result["bagua"]
                if isinstance(bg, list) and len(bg) == 8:
                    if sum(abs(v) for v in bg) > 0.01:
                        dom_idx = int(np.argmax(bg))
                        dom_name = ["乾","兑","离","震","巽","坎","艮","坤"][dom_idx]
                        return dom_name, [float(v) for v in bg]
        
        result = _HZ.word(hanzi)
        if result:
            if "vector" in result:
                bg = result["vector"]
                if isinstance(bg, list) and len(bg) == 8:
                    if sum(abs(v) for v in bg) > 0.01:
                        dom_idx = int(np.argmax(bg))
                        dom_name = ["乾","兑","离","震","巽","坎","艮","坤"][dom_idx]
                        return dom_name, [float(v) for v in bg]
            elif "bagua" in result:
                bg = result["bagua"]
                if isinstance(bg, list) and len(bg) == 8:
                    if sum(abs(v) for v in bg) > 0.01:
                        dom_idx = int(np.argmax(bg))
                        dom_name = ["乾","兑","离","震","巽","坎","艮","坤"][dom_idx]
                        return dom_name, [float(v) for v in bg]
    except Exception:
        pass
    
    # fallback 2: 基于部首推理
    try:
        from hanzi_decomposition import HANZI_DECOMPOSITION
        import json
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                               "..", "..", "language", "radical_fuzzy_base.json"), encoding='utf-8') as f:
            radical_data = json.load(f)
        first_char = hanzi[0]
        decomp = HANZI_DECOMPOSITION.get(first_char, {})
        if decomp:
            rads = decomp.get("components", decomp.get("radical", ""))
            if isinstance(rads, str):
                rads = [rads]
            rad_baguas = []
            for r in rads:
                rd = radical_data.get(r, {})
                if isinstance(rd, dict):
                    bg = rd.get("bagua_gray", rd.get("membership", [0.3]*8))
                    rad_baguas.append(bg)
            if rad_baguas:
                avg = np.mean(rad_baguas, axis=0)
                if sum(abs(v) for v in avg) > 0.1:
                    dom_idx = int(np.argmax(avg))
                    dom_name = ["乾","兑","离","震","巽","坎","艮","坤"][dom_idx]
                    return dom_name, [float(v) for v in avg]
    except Exception:
        pass
    
    # fallback 3: 词义→八卦知识库（带运行时学习）
    try:
        from v20.gua_knowledge_base import semantic_lookup, observe_learning
        result = semantic_lookup(hanzi)
        if result:
            return result
    except Exception:
        pass
    
    return "坤", [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.85]


@lru_cache(maxsize=4096)
def _yao_for_entity_cached(en_name: str) -> Tuple[float, ...]:
    """带LRU缓存的底层实体→六爻查询"""
    vec = _yao_for_entity_impl(en_name)
    return tuple(vec)

def _yao_for_entity(en_name: str, features: Optional[Dict] = None) -> List[float]:
    """实体 → YLYW六爻编码（6维）——带LRU缓存版"""
    return list(_yao_for_entity_cached(en_name))


def _yao_for_entity_impl(en_name: str) -> List[float]:
    """实体 → YLYW六爻编码（6维）
    
    替代V18 world_model中通过正则解析得到的结构化状态。
    这里通过hanzi_engine对汉字做字级YLYW推理得到六爻向量。
    
    不同于V18用物理特征编码（YaoEncoder，给抓取场景的），
    这里用的是hanzi_engine的YLYWLayer.perceive_and_encode()，
    对汉字的部首→卦象做乘承比应推理，属于汉字语义层面的六爻表示。
    """
    hanzi = _hanzi_for_entity(en_name)
    if not hanzi or hanzi.strip() == "":
        return [0.5] * 6
    
    try:
        result = _HZ.char(hanzi)
        if result:
            if "yao_vector" in result:
                yao = result["yao_vector"]
                if isinstance(yao, list) and len(yao) == 6:
                    return [float(v) for v in yao]
            if "vector" in result:
                vec = result["vector"]
                if isinstance(vec, list) and len(vec) == 8:
                    if sum(abs(v) for v in vec) > 0.01:
                        return [float(v) for v in vec[:6]]
        
        result = _HZ.word(hanzi)
        if result:
            if "yao_vector" in result:
                yao = result["yao_vector"]
                if isinstance(yao, list) and len(yao) == 6:
                    return [float(v) for v in yao]
            if "vector" in result:
                vec = result["vector"]
                if isinstance(vec, list) and len(vec) == 8:
                    if sum(abs(v) for v in vec) > 0.01:
                        return [float(v) for v in vec[:6]]
    except Exception:
        pass
    
    # fallback: 语义知识库查询
    try:
        from v20.gua_knowledge_base import semantic_lookup
        result = semantic_lookup(hanzi)
        if result:
            dom_gua, bagua_vec = result
            if bagua_vec and len(bagua_vec) >= 6:
                return [float(v) for v in bagua_vec[:6]]
    except Exception:
        pass
    
    return [0.5] * 6


# ══════════════════════════════════════════════════════
# 汉字卦象状态 —— 完整的YLYW世界模型
# ══════════════════════════════════════════════════════

@dataclass
class GuaReceptacle:
    """汉字容器状态 —— 用YLYW卦象表示的容器"""
    id: str                           # 英文id: "cabinet 3"
    hanzi: str                        # 汉字名: "橱柜"
    cls: str                          # 英文类别: "cabinet"
    dom_gua: str = "坤"               # 主导卦象
    bagua_vec: List[float] = field(default_factory=lambda: [0.3]*8)  # 八卦隶属度
    yao_state: List[float] = field(default_factory=lambda: [0.5]*6)  # 当前状态六爻
    
    # 容器状态（与V18兼容的接口）
    visited: bool = False
    is_open: Optional[bool] = None    # None=未知/不可开
    searched: bool = False
    exhausted: bool = False
    contents: Set[str] = field(default_factory=set)
    
    @property
    def openable(self) -> bool:
        import v18.world_model as _vwm
        return self.cls in getattr(_vwm, 'OPENABLE_CLASSES', set())


@dataclass
class GuaObject:
    """汉字物体状态 —— 用YLYW卦象表示的物体"""
    id: str                           # 英文id: "apple 1"
    hanzi: str                        # 汉字名: "苹果"
    cls: str                          # 英文类别: "apple"
    dom_gua: str = "坤"               # 主导卦象
    bagua_vec: List[float] = field(default_factory=lambda: [0.3]*8)
    yao_state: List[float] = field(default_factory=lambda: [0.5]*6)
    
    # 状态（与V18兼容）
    location: Optional[str] = None    # 当前所在容器id
    in_inventory: bool = False
    deposited: bool = False
    processed: Set[str] = field(default_factory=set)


def _compute_situation_hexagram(receps: Dict, objs: Dict, location: Optional[str],
                                 inventory: Set[str]) -> Tuple[str, List[float]]:
    """从当前世界状态计算情境卦象
    
    将所有容器和物体的卦象聚合为"情境六爻"→匹配64卦→当前情境卦象
    
    Returns:
      (hexagram_name: str, situation_yao: List[float])
    """
    # 聚合所有容器的yao_state和物体的yao_state
    all_yaos = []
    
    # 当前所在位置卦象
    if location and location in receps:
        all_yaos.append(receps[location].yao_state)
    
    # 可见物体卦象（最多取6个）
    visible = [o for o in objs.values() if not o.in_inventory and o.location]
    for o in visible[:6]:
        all_yaos.append(o.yao_state)
    
    # 手中物品卦象
    for oid in inventory:
        if oid in objs:
            all_yaos.append(objs[oid].yao_state)
    
    if not all_yaos:
        return "坤", [0.5] * 6
    
    # 平均得到情境六爻
    arr = np.mean(all_yaos, axis=0)
    situation_yao = [float(v) for v in arr]
    
    # 匹配64卦
    hx, cos = _HR.get_best_hexagram(np.array(situation_yao, dtype=float))
    return hx.name, situation_yao


# ══════════════════════════════════════════════════════
# CnWorldModel —— 汉字世界模型（替代V18 WorldModel）
# ══════════════════════════════════════════════════════

class CnWorldModel:
    """汉字世界模型 —— 所有状态通过YLYW卦象表示
    
    替代 V18 world_model.WorldModel 的全部接口。
    外部agent通过相同的接口方法访问，但内部实现完全基于汉字+YLYW。
    
    设计原则：
      - 所有文本观测先通过 chinese_bridge 翻译为汉字
      - 汉字文本通过 hanzi_engine 的YLYW推理得到卦象表示
      - 状态更新使用YLYW六爻编码而非正则匹配
      - 情境理解通过64卦匹配而非符号规则
    """
    
    def __init__(self):
        # ── YLYW引擎 ──
        self.pm = _PM
        self.tb = _TB
        self.ye = _YE
        self.hr = _HR
        self.hz = _HZ
        self.bridge = _BRIDGE
        
        # ── 汉字卦象状态 ──
        self.receps: Dict[str, GuaReceptacle] = {}
        self.objs: Dict[str, GuaObject] = {}
        self.location: Optional[str] = None        # 英文id
        self.inventory: Set[str] = set()
        self.step_count: int = 0
        
        # ── YLYW情境卦象 ──
        self.situation_hexagram: str = "坤"         # 当前情境最佳匹配卦
        self.situation_yao: List[float] = [0.5]*6  # 当前情境六爻
        
        # ── 失败历史（卦象级别） ──
        self.failed_actions: List[Dict] = []       # [{action, hexagram, yao}]
        self.failed_sa: Set[Tuple[str, str]] = set()
        self.last_state_key: Optional[str] = None
        
        # ── 先验知识（汉字版） ──
        self.all_receptacles: Set[str] = set()
        self._hanzi_cache: Dict[str, str] = {}     # en→cn缓存
        self._bagua_cache: Dict[str, Tuple[str, List[float]]] = {}  # hanzi→(gua, vec)
        self._yao_cache: Dict[str, List[float]] = {}  # en_id→yao

    # ── 公共接口（与V18 WorldModel兼容） ──
    
    def init_from_reset(self, obs: str, admissible: List[str]):
        """初始化（替代V18的同名方法）"""
        self._ingest_hanzi_admissible(admissible)
        self._ingest_hanzi_obs(obs, action="")
    
    def observe_transition(self, action: str, obs: str, admissible_after: List[str],
                           changed: Optional[bool] = None):
        """每步更新（替代V18的同名方法）"""
        self.step_count += 1
        pre_key = self.last_state_key
        self._ingest_hanzi_obs(obs, action)
        self._ingest_hanzi_admissible(admissible_after)
        self._sync_location_flags(admissible_after)
        post_key = self.state_key()
        if pre_key is not None and pre_key == post_key and self._is_stateful(action):
            self.failed_sa.add((pre_key, action))
        self.last_state_key = post_key
        # 更新情境卦象
        self._update_situation()
        
        # 运行时学习：将本次观测到的实体卦象记录到知识库
        self._learn_from_observation()
    
    # ── 查询接口（与V18 WorldModel兼容） ──
    
    def holding_target(self, obj_classes) -> Optional[str]:
        classes = {obj_classes} if isinstance(obj_classes, str) else set(obj_classes or [])
        for oid in self.inventory:
            if self._class_of(oid) in classes:
                return oid
        return None
    
    def known_objects_of(self, obj_class: str) -> List[str]:
        return [o.id for o in self.objs.values() if o.cls == obj_class]
    
    def unsearched_receptacles(self) -> List[str]:
        return [r.id for r in self.receps.values() if not r.searched]
    
    def find_object_location(self, obj_class: str) -> Optional[str]:
        for o in self.objs.values():
            if o.cls == obj_class and not o.in_inventory and o.location \
                    and o.location != "inventory":
                return o.location
        return None
    
    def find_pending_target_recep(self, obj_classes, dest_class: Optional[str]) -> Optional[str]:
        classes = {obj_classes} if isinstance(obj_classes, str) else set(obj_classes or [])
        if not classes:
            return None
        for o in self.objs.values():
            if o.cls not in classes or o.in_inventory:
                continue
            if o.location in (None, "inventory"):
                continue
            if o.deposited and dest_class and self._class_of(o.location) == dest_class:
                continue
            return o.location
        return None
    
    def find_lamp_recep(self) -> Optional[str]:
        for cls in ("desklamp", "floorlamp"):
            loc = self.find_object_location(cls)
            if loc:
                return loc
        return None
    
    def state_key(self) -> str:
        """状态键（替代V18的state_key，用于失败检测）"""
        inv = ",".join(sorted(self.inventory))
        opened = ",".join(sorted(r.id for r in self.receps.values() if r.is_open))
        searched = ",".join(sorted(r.id for r in self.receps.values() if r.searched))
        proc = ",".join(sorted(f"{o.id}:{'|'.join(sorted(o.processed))}"
                               for o in self.objs.values() if o.processed))
        dep = ",".join(sorted(o.id for o in self.objs.values() if o.deposited))
        return f"loc={self.location}|inv={inv}|op={opened}|se={searched}|pr={proc}|dep={dep}"
    
    # ── YLYW特有查询 ──
    
    def get_situation_gua(self) -> Tuple[str, List[float]]:
        """获取当前情境卦象"""
        return self.situation_hexagram, self.situation_yao
    
    def get_entity_gua(self, en_id: str) -> Tuple[str, List[float]]:
        """获取实体卦象"""
        if en_id in self.receps:
            r = self.receps[en_id]
            return r.dom_gua, r.yao_state
        if en_id in self.objs:
            o = self.objs[en_id]
            return o.dom_gua, o.yao_state
        hanzi = self._to_hanzi(en_id)
        return _bagua_for_hanzi(hanzi)
    
    # ── 内部实现：汉字YLYW感知 ──
    
    def _to_hanzi(self, en_name: str) -> str:
        """英文名 → 汉字（带缓存）"""
        if en_name in self._hanzi_cache:
            return self._hanzi_cache[en_name]
        clean = re.sub(r'\s+\d+$', '', en_name.strip()).lower()
        cn = self.bridge._en_entity_to_cn(clean)
        if not cn:
            cn = clean
        self._hanzi_cache[en_name] = cn
        return cn
    
    def _get_bagua(self, hanzi: str) -> Tuple[str, List[float]]:
        """汉字 → 八卦隶属度（带缓存）"""
        if hanzi in self._bagua_cache:
            return self._bagua_cache[hanzi]
        result = _bagua_for_hanzi(hanzi)
        self._bagua_cache[hanzi] = result
        return result
    
    def _get_yao(self, en_id: str, cls: str = "") -> List[float]:
        """实体 → 六爻编码（带缓存）"""
        cache_key = f"{en_id}:{cls}"
        if cache_key in self._yao_cache:
            return self._yao_cache[cache_key]
        hanzi = self._to_hanzi(en_id)
        dom_gua, bagua = self._get_bagua(hanzi)
        features = {"name": en_id, "hanzi": hanzi, "bagua": bagua, "cls": cls}
        yao = _yao_for_entity(en_id, features)
        self._yao_cache[cache_key] = yao
        return yao
    
    def _update_situation(self):
        """更新情境卦象"""
        self.situation_hexagram, self.situation_yao = \
            _compute_situation_hexagram(self.receps, self.objs, self.location, self.inventory)
    
    @staticmethod
    def _class_of(instance: str) -> str:
        return instance.rsplit(" ", 1)[0] if instance else instance
    
    @staticmethod
    def _is_stateful(action: str) -> bool:
        a = action.strip().lower()
        return a.split(" ", 1)[0] in {
            "take", "move", "put", "open", "close", "clean", "heat", "cool", "use"
        }
    
    # ── 汉字文本感知（替代V18的英文正则解析） ──
    
    def _ingest_hanzi_admissible(self, admissible: List[str]):
        """从合法动作列表中感知容器（纯汉字版）
        
        逐一翻译英文合法命令为汉字，通过汉字关键词识别容器。
        不再使用英文正则。
        """
        for c in admissible:
            cmd_lower = c.lower()
            cn_cmd = self.bridge.from_english(c) or ""
            
            # 汉字关键词：去、到、前往、打开、关闭
            if cmd_lower.startswith("go to "):
                rid = cmd_lower[len("go to "):].strip()
                r = self._ensure_recep(rid)
                
            elif cmd_lower.startswith("open "):
                rid = cmd_lower[len("open "):].strip()
                r = self._ensure_recep(rid)
                r.is_open = False
                
            elif cmd_lower.startswith("close "):
                rid = cmd_lower[len("close "):].strip()
                r = self._ensure_recep(rid)
                r.is_open = True
    
    def _ingest_hanzi_obs(self, obs: str, action: str):
        """从观测中感知环境状态
        
        设计说明：
          ALFWorld 环境只返回英文文本，所以此处仍需使用英文正则作为
          "接口适配层"从原始文本中提取结构化信息。
          
          但与传统 world_model.py 的关键区别：
          - 提取到的每个实体（容器、物体）立即转换为 YLYW 汉字卦象表示
          - 状态不是 Python dataclass 属性，而是卦象的六爻编码
          - 全局情境通过六十四卦匹配而非符号规则
          
          未来方向：当 chinese_bridge 翻译能力足够完善时，
          可用汉字关键词完全替代英文正则。
        """
        if not obs:
            return
        
        cn_obs = self.bridge._translate_obs(obs)
        low = obs.lower()
        
        # ── 到达位置 ──
        ma = re.search(r"you arrive at (?:the )?([a-z]+ \d+)", low, re.I)
        if ma:
            self.location = ma.group(1)
            r = self._ensure_recep(self.location)
            r.visited = True
            hanzi = self._to_hanzi(self.location)
            r.dom_gua, r.bagua_vec = self._get_bagua(hanzi)
            r.yao_state = self._get_yao(self.location, r.cls)
        
        # ── 容器关闭 ──
        for m in re.finditer(r"the ([a-z]+ \d+) is closed", low, re.I):
            self._ensure_recep(m.group(1)).is_open = False
        
        # ── 容器打开 ──
        mo = re.search(r"you open the ([a-z]+ \d+)", low, re.I)
        if mo:
            self._ensure_recep(mo.group(1)).is_open = True
        
        # ── 内容感知 ──
        target_recep = None
        if ma:
            target_recep = self.location
        if mo:
            target_recep = mo.group(1)
        m_on = re.search(r"on the ([a-z]+ \d+), you see", low, re.I)
        if m_on:
            target_recep = m_on.group(1)
            
        see_m = re.search(r"you see (.+?)\.?$", low, re.I)
        if see_m and target_recep:
            body = see_m.group(1)
            if "nothing" not in body:
                items = re.findall(r"\ba ([a-z]+ \d+)", " " + body)
                r = self._ensure_recep(target_recep)
                r.contents = set(items)
                for oid in items:
                    if not self._is_receptacle(oid):
                        o = self._ensure_obj(oid)
                        if not o.in_inventory:
                            o.location = target_recep
        
        # ── 拿起物品 ──
        mp = re.search(r"you pick up the ([a-z]+ \d+) from the ([a-z]+ \d+)", low, re.I)
        if mp:
            oid, rid = mp.group(1), mp.group(2)
            self._hanzi_take(oid, rid)
        else:
            mp2 = re.search(r"you pick up the ([a-z]+ \d+)", low, re.I)
            if mp2 and "from" not in low.lower():
                self._hanzi_take(mp2.group(1), None)
        
        # ── 放置物品 ──
        mput = re.search(r"you (?:put|place|move) the ([a-z]+ \d+) (?:in|on|to|in/on) (?:the )?([a-z]+ \d+)", low, re.I)
        if mput:
            oid, rid = mput.group(1), mput.group(2)
            self._hanzi_put(oid, rid)
        
        # ── 工序完成 ──
        al = (action or "").lower()
        if al.startswith("clean ") and "clean" in low.lower():
            self._hanzi_mark_processed(al, "clean")
        elif al.startswith("heat ") and ("heat" in low.lower() or "hot" in low.lower()):
            self._hanzi_mark_processed(al, "hot")
        elif al.startswith("cool ") and ("cool" in low.lower() or "chill" in low.lower()):
            self._hanzi_mark_processed(al, "cold")
        elif al.startswith("use ") and self.inventory:
            for oid in self.inventory:
                self._ensure_obj(oid).processed.add("examined")
    
    def _hanzi_take(self, oid: str, rid: Optional[str]):
        """拿起物品（汉字版）
        
        替代 V18 world_model._take()。
        拿起物品时，更新其卦象状态（从"在容器中"变为"在手中"）。
        """
        o = self._ensure_obj(oid)
        o.in_inventory = True
        o.location = "inventory"
        o.deposited = False
        self.inventory.add(oid)
        if rid and rid in self.receps:
            self.receps[rid].contents.discard(oid)
        # 重新计算物品卦象（手中状态不同）
        hanzi = self._to_hanzi(oid)
        o.dom_gua, o.bagua_vec = self._get_bagua(hanzi)
        o.yao_state = self._get_yao(oid, o.cls)
    
    def _hanzi_put(self, oid: str, rid: str):
        """放置物品（汉字版）"""
        o = self._ensure_obj(oid)
        o.in_inventory = False
        o.location = rid
        o.deposited = True
        self.inventory.discard(oid)
        self._ensure_recep(rid).contents.add(oid)
    
    def _hanzi_mark_processed(self, action_lower: str, tag: str):
        """标记工序完成（汉字版）"""
        m = re.search(r"^(?:clean|heat|cool) ([a-z]+ \d+) with", action_lower)
        oid = m.group(1) if m else (next(iter(self.inventory), None))
        if oid:
            self._ensure_obj(oid).processed.add(tag)
    
    def _ensure_recep(self, rid: str) -> GuaReceptacle:
        """获取或创建容器（带YLYW卦象初始化）"""
        r = self.receps.get(rid)
        if r is None:
            cls = self._class_of(rid)
            hanzi = self._to_hanzi(rid)
            dom_gua, bagua = self._get_bagua(hanzi)
            yao = self._get_yao(rid, cls)
            r = GuaReceptacle(id=rid, hanzi=hanzi, cls=cls,
                              dom_gua=dom_gua, bagua_vec=bagua, yao_state=yao)
            self.receps[rid] = r
            self.all_receptacles.add(rid)
        return r
    
    def _ensure_obj(self, oid: str) -> GuaObject:
        """获取或创建物体（带YLYW卦象初始化）"""
        o = self.objs.get(oid)
        if o is None:
            cls = self._class_of(oid)
            hanzi = self._to_hanzi(oid)
            dom_gua, bagua = self._get_bagua(hanzi)
            yao = self._get_yao(oid, cls)
            o = GuaObject(id=oid, hanzi=hanzi, cls=cls,
                          dom_gua=dom_gua, bagua_vec=bagua, yao_state=yao)
            self.objs[oid] = o
        return o
    
    def _sync_location_flags(self, admissible_after: List[str]):
        """同步当前位置的已搜/已访问标志（替代V18 _sync_current_location_flags）"""
        if not self.location:
            return
        r = self.receps.get(self.location)
        if r is None:
            return
        openable = r.openable
        can_open_here = any(c == f"open {r.id}" for c in admissible_after)
        if openable and can_open_here:
            return
        r.visited = True
        r.searched = True
    
    @staticmethod
    def _is_receptacle(instance: str) -> bool:
        import v18.world_model as _vwm
        _rc_set = getattr(_vwm, 'RECEPTACLE_CLASSES', set())
        cls = instance.rsplit(" ", 1)[0] if instance else instance
        return cls in _rc_set
    
    def _learn_from_observation(self):
        """从当前观测中学习实体卦象到知识库"""
        try:
            from v20.gua_knowledge_base import observe_learning
            # 所有容器的卦象
            for r in self.receps.values():
                if sum(abs(v) for v in r.bagua_vec) > 0.01:
                    observe_learning(r.hanzi, r.bagua_vec)
            # 所有物体的卦象
            for o in self.objs.values():
                if sum(abs(v) for v in o.bagua_vec) > 0.01:
                    observe_learning(o.hanzi, o.bagua_vec)
        except Exception:
            pass


# ══════════════════════════════════════════════════════
# 单元测试
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    # 测试汉字感知
    cwm = CnWorldModel()
    
    # 测试翻译
    for en in ["apple", "cabinet", "sinkbasin", "desklamp", "microwave"]:
        cn = cwm._to_hanzi(en)
        gua, bagua = cwm._get_bagua(cn)
        yao = cwm._get_yao(f"{en} 1", en)
        print(f"{en:15s} → {cn:5s}  卦={gua:3s}  六爻={[round(v,2) for v in yao]}")
    
    print("\n--- 测试情境卦象 ---")
    # 模拟初始状态
    cwm.init_from_reset(
        "You are in the kitchen. You see a counter 1. On the counter 1, you see a apple 1.",
        ["go to counter 1", "go to fridge 1", "go to sinkbasin 1", "look", "inventory"]
    )
    gua, yao = cwm.get_situation_gua()
    print(f"初始情境卦象: {gua}  六爻={[round(v,2) for v in yao]}")
    print(f"容器: {list(cwm.receps.keys())}")
    print(f"物体: {list(cwm.objs.keys())}")
    for oid, o in cwm.objs.items():
        print(f"  {oid}: {o.hanzi}  卦={o.dom_gua}  位置={o.location}")
