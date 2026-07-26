#!/usr/bin/env python3
"""
V19 YLYW Scorer — 易理六爻 + 爻位关系混合评分器

与V18 ylyw_scorer 兼容接口，增加：
1. 从world_model状态构造情境文本 → 词级八卦感知
2. YaoRelations乘承比应分析 → 爻位关系报告
3. 混合评分：V18线性分 × 爻位关系修正 + 差距卦象语义对齐

核心理念：
  V18的6维手工公式太"工具化"——它告诉agent什么动作推进目标，
  但不告诉agent当前整体情境是否"得道"。
  V19恢复差距卦象(scene_yao - task_yao)作为情境感知信号，
  用YaoRelations做当位得中分析指导动作排序。
"""

import sys, os, math, json, numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter

# YLYW核心
YLYW_CORE = os.path.join(os.path.dirname(__file__), '..', '..', 'api_docs', 'ylyw_core')
sys.path.insert(0, YLYW_CORE)
from trigram_base import TrigramBase, Trigram
from yao_encoder import YaoEncoder, YaoPosition
from yao_relations import YaoRelations
from hexagram_rules import HexagramRuleBase, Hexagram

# V18 scorer 中的共用函数
V18_DIR = os.path.join(os.path.dirname(__file__), '..', 'v18')
sys.path.insert(0, V18_DIR)
from ylyw_scorer import _clip, parse_action, Candidate, location_prior

# ─── 语言支持 ─────────────────────────────────────
# HanziEngine 路径
LANG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'language')
sys.path.insert(0, LANG_DIR)
try:
    from hanzi_engine import HanziEngine
    HANZI_AVAILABLE = True
except ImportError:
    HANZI_AVAILABLE = False
    print("[V19] HanziEngine not available; falling back to trigram template matching")


# ═══════════════════════════════════════════════════════
# 情境构造器
# ═══════════════════════════════════════════════════════

# ALFWorld中英映射（用于构建中文情境文本）
EN2CN_ACTION = {
    'go': '去', 'take': '拿', 'put': '放', 'move': '移',
    'open': '开', 'close': '关', 'clean': '洗', 'heat': '热',
    'cool': '冷', 'examine': '看', 'use': '用', 'look': '看',
}

EN2CN_OBJ = {
    'plate': '盘子', 'bowl': '碗', 'cup': '杯子', 'mug': '杯子',
    'apple': '苹果', 'potato': '土豆', 'tomato': '番茄', 'egg': '鸡蛋',
    'bread': '面包', 'soap': '肥皂', 'knife': '刀', 'spoon': '勺子',
    'fork': '叉子', 'pan': '锅', 'pot': '锅', 'book': '书',
    'pencil': '铅笔', 'peppershaker': '胡椒瓶', 'saltshaker': '盐瓶',
    'butterknife': '黄油刀', 'soapbottle': '洗手液', 'spraybottle': '喷壶',
}

EN2CN_RECEP = {
    'countertop': '柜台', 'cabinet': '柜子', 'drawer': '抽屉',
    'shelf': '架子', 'desk': '桌子', 'sinkbasin': '水槽', 'fridge': '冰箱',
    'microwave': '微波炉', 'garbagecan': '垃圾桶', 'safe': '保险柜',
    'diningtable': '餐桌', 'bed': '床', 'armchair': '扶手椅',
    'desklamp': '台灯', 'floorlamp': '落地灯',
}

class ContextBuilder:
    """
    从world_model结构化状态 → 中文情境描述
    
    产出包含语义角色标记的情境文本，
    供HanziEngine逐词感知八卦向量。
    """
    
    def __init__(self):
        self.en2cn_obj = EN2CN_OBJ
        self.en2cn_recep = EN2CN_RECEP
        self.en2cn_action = EN2CN_ACTION
    
    def build(self, world, goal, phase: Dict) -> str:
        """
        构建完整情境文本
        """
        parts = []
        
        # 当前持有
        inv = getattr(world, 'inventory', None)
        if inv and len(inv) > 0:
            obj_id = list(inv)[0]
            obj_cn = self._obj_cn(obj_id)
            parts.append(f"手拿{obj_cn}")
        else:
            parts.append("空手")
        
        # 当前位置
        loc = getattr(world, 'location', None)
        if loc:
            loc_cn = self._recep_cn(loc)
            parts.append(f"在{loc_cn}前")
        
        # 可见物体
        objs = getattr(world, 'objs', {})
        visible = []
        for oid, o in objs.items():
            if hasattr(o, 'location') and o.location and not o.location == 'inventory':
                loc_cn = self._recep_cn(o.location)
                obj_cn = self._obj_cn(oid)
                visible.append(f"{obj_cn}在{loc_cn}上")
        if visible:
            parts.append(f"看见{'、'.join(visible[:3])}")
        
        # 容器状态
        receps = getattr(world, 'receps', {})
        closed = []
        for rid, r in receps.items():
            if hasattr(r, 'is_open') and not r.is_open:
                cn = self._recep_cn(rid)
                closed.append(cn)
        if closed:
            parts.append(f"{'、'.join(closed[:2])}关着")
        
        # 目标
        if goal:
            obj_cn = self._obj_cn(goal.object_class)
            recep_cn = self._recep_cn(goal.recep_class)
            if goal.needs_process():
                proc = goal.process or ''
                parts.append(f"目标:洗/热{obj_cn}放到{recep_cn}")
            elif goal.needs_light():
                parts.append(f"目标:在光下看{obj_cn}")
            elif goal.task_type == 'pick_two_obj_and_place':
                parts.append(f"目标:拿两个{obj_cn}放到{recep_cn}")
            else:
                parts.append(f"目标:把{obj_cn}放到{recep_cn}")
        
        return "。".join(parts)
    
    def build_task_context(self, world, goal, phase: Dict) -> str:
        """构建更简洁的任务进度描述（用于差距卦象）"""
        parts = []
        
        # 当前状态
        inv = getattr(world, 'inventory', None)
        holding = bool(inv and len(inv) > 0)
        
        status = phase.get('proc_done', False)
        placed = phase.get('placed_count', 0)
        searching = phase.get('searching', False)
        holding_target = phase.get('holding_target')
        
        if holding_target and holding:
            if status:
                parts.append("已处理持有物")
            else:
                parts.append("需处理持有物")
            parts.append("去找目标位置放")
        elif holding:
            parts.append("手持非目标物")
        elif searching:
            parts.append("搜索目标物中")
        else:
            parts.append("准备拿取")
        
        if placed > 0:
            parts.append(f"已放置{placed}件")
        
        return "。".join(parts)
    
    def _obj_cn(self, oid: str) -> str:
        if not oid:
            return "?"
        base = oid.strip().lower()
        # 去掉数字后缀
        import re
        base = re.sub(r'\s+\d+$', '', base)
        return self.en2cn_obj.get(base, base[:2])
    
    def _recep_cn(self, rid: str) -> str:
        if not rid:
            return "?"
        base = rid.strip().lower()
        import re
        base = re.sub(r'\s+\d+$', '', base)
        return self.en2cn_recep.get(base, base[:2])


# ═══════════════════════════════════════════════════════
# V19 YLYW 评分器
# ═══════════════════════════════════════════════════════

# 预计算上下文：每步只需算一次，供所有candidate复用
from typing import NamedTuple

PrecomputedContext = NamedTuple('PrecomputedContext', [
    ('scene_yao', Optional[List[float]]),
    ('task_yao', Optional[List[float]]),
    ('scene_report', 'Optional[Any]'),
    ('delta_yao', Optional[List[float]]),
    ('strategy_modifier', float),
])

class V19YLYWScorer:
    """
    V19 混合评分器
    
    工作流程：
      1. 对每个候选动作 → 计算V18线性6维（保留）
      2. 从world_model构造情境文本 → 
         a) HanziEngine感知词级八卦（或用trigram_base模板匹配）
         b) YaoRelations爻位关系分析
         c) 差距卦象诊断
      3. 混合评分：
         final = (1-alpha) * V18线性分 + alpha * 语义分 × 爻位修正
    """
    
    def __init__(self, mode: str = "full", seed: int = 0, alpha: float = 0.2):
        """
        Args:
            mode: "full"(混合) | "linear"(纯V18) | "ylyw_only"(纯卦象)
            alpha: 混合权重，0=pure V18, 1=pure 卦象
        """
        self.mode = mode
        self.alpha = alpha
        self.rng = np.random.RandomState(seed)
        
        # 核心组件
        self.trigram_base = TrigramBase()
        self.yao_encoder = YaoEncoder()
        self.yao_relations = YaoRelations()
        self.hexagram_rules = HexagramRuleBase()
        
        # HanziEngine（可选）
        self.hanzi = HanziEngine(verbose=False) if HANZI_AVAILABLE else None
        
        # 情境构造器
        self.context = ContextBuilder()
        
        # Debug缓存
        self._last_context = ""
        self._last_yao_info = {}
    
    def precompute_context(self, world, goal, phase: Dict) -> Optional[PrecomputedContext]:
        """
        每步预计算一次情境卦象感知，供所有candidate复用
        返回 None 表示感知失败（退化为V18线性评分）
        """
        if self.mode == "linear":
            return None
        context = self.context.build(world, goal, phase)
        task_context = self.context.build_task_context(world, goal, phase)
        self._last_context = context
        scene_bagua, scene_yao = self._perceive_context(context)
        task_bagua, task_yao = self._perceive_context(task_context)
        if scene_yao is None:
            return None
        scene_report = self.yao_relations.analyze(np.array(scene_yao))
        delta_yao = None
        if task_yao is not None:
            delta_yao = [scene_yao[i] - task_yao[i] for i in range(6)]
        return PrecomputedContext(
            scene_yao=scene_yao,
            task_yao=task_yao,
            scene_report=scene_report,
            delta_yao=delta_yao,
            strategy_modifier=scene_report.strategy_modifier if scene_report else 1.0,
        )

    def score_candidate(self, cmd: str, world, goal, phase: Dict,
                        precomputed: Optional[PrecomputedContext] = None) -> Candidate:
        """主入口：与V18接口兼容 + 可选预计算上下文参数"""
        
        parsed = parse_action(cmd)
        
        # 1. V18线性分（基准）
        v18_yao = self._v18_build_yao(parsed, world, goal, phase)
        v18_score, best_gua, _cos_score = self._v18_score(parsed, v18_yao, world, goal, phase)
        
        cand = Candidate(cmd, parsed,
                          yao=[round(v,3) for v in v18_yao],
                          ylyw_score=round(v18_score,4),
                          linear_score=round(v18_score,4),
                          hexagram=best_gua.name if best_gua else '',
                          hex_cn=self.hexagram_rules.get_rule(best_gua).get('name','') if best_gua else '')
        
        if self.mode == "linear" or precomputed is None:
            return cand
        
        # 2. 复用预计算的情境卦象
        scene_yao = precomputed.scene_yao
        task_yao = precomputed.task_yao
        scene_report = precomputed.scene_report
        delta_yao = precomputed.delta_yao
        modifier = precomputed.strategy_modifier
        
        if scene_yao is None:
            return cand  # 感知失败，回退V18
        
        # 2d. 候选动作在差距卦象空间中的对齐度
        semantic_score = self._semantic_alignment(
            parsed, v18_yao, delta_yao, scene_report
        )
        
        # 3. 混合评分
        if self.mode == "full":
            final = v18_score * modifier * (1 - self.alpha) + semantic_score * self.alpha
            cand.ylyw_score = round(final, 4)
        elif self.mode == "ylyw_only":
            cand.ylyw_score = round(semantic_score * 0.1 + v18_score * 0.9, 4)
        
        return cand
    
    def _v18_build_yao(self, parsed: Dict, world, goal, phase: Dict) -> List[float]:
        """V18的手工6维编码（直接使用V18公式）"""
        # 这里复用V18的build_yao逻辑
        # 为保持简洁，我们直接调用V18的方法
        from ylyw_scorer import YLYWScorer as V18Scorer
        # 动态创建V18评分器
        v18 = V18Scorer(mode='full')
        return v18.build_yao(parsed, world, goal, phase)
    
    def _v18_score(self, parsed, yao, world, goal, phase) -> float:
        """V18线性评分（原始计算）"""
        # V18的评分逻辑：目标推进幅度 × favorability
        y1, y2, y3, y4, y5, y6 = yao
        
        # 目标推进幅度（线性部分）
        progress = (0.30 * y1 + 0.20 * y2 + 0.20 * y3 + 
                    0.10 * y4 + 0.10 * y5 + 0.10 * y6)
        
        # 64卦favorability
        best_gua, cos_score = self.hexagram_rules.get_best_hexagram(np.array(yao))
        hex_rule = self.hexagram_rules.get_rule(best_gua) if best_gua else {}
        favor = hex_rule.get('grasp_strategy', {}).get('favorability', 0.5)
        
        # 动作卦亲和
        verb = parsed["verb"]
        verb_bagua = self._verb_to_bagua(verb)
        obj_cls = parsed.get("obj_cls")
        obj_bagua = self._obj_to_bagua(obj_cls) if obj_cls else None
        action_affinity = 0.92 + 0.08 * (
            self._bagua_similarity(verb_bagua, obj_bagua) 
            if obj_bagua is not None else 0.5
        )
        
        v18_score = progress * favor * action_affinity * (0.75 + 0.25 * cos_score)
        return v18_score, best_gua, cos_score
    
    # 兼容旧接口
    
    
    def _perceive_context(self, context: str) -> Tuple[Optional[List[float]], Optional[List[float]]]:
        """
        感知情境文本 → 返回(8D八卦隶属度, 6D六爻向量)
        
        使用HanziEngine逐词感知，再按语义角色加权聚合。
        HanziEngine不可用时，用TrigramBase+YaoEncoder模板匹配。
        """
        if not context or len(context.strip()) < 2:
            return None, None
        
        if self.hanzi and HANZI_AVAILABLE:
            try:
                result = self.hanzi.sentence(context)
                bagua = result.get('sentence_bagua', None)
                yao = result.get('yao_vector', None)
                if bagua is not None and yao is not None:
                    return list(bagua), list(yao)
            except:
                pass
        
        # Fallback: 从context中提取关键中文词做简单八卦映射
        return self._fallback_perceive(context)
    
    def _fallback_perceive(self, context: str) -> Tuple[List[float], List[float]]:
        """回退感知：基于预设词→卦映射"""
        
        # 中文词→主导八卦映射（来自HanziEngine char级输出）
        WORD_BAGUA = {
            '拿': 0,  # 乾
            '放': 7,  # 巽
            '走': 2,  # 震
            '洗': 5,  # 坎
            '看': 4,  # 离
            '开': 6,  # 兑
            '关': 3,  # 艮
            '热': 4,  # 离
            '冷': 5,  # 坎
            '手': 6,  # 兑
            '空': 0,  # 乾
            '放': 7,  # 巽
            '前': 2,  # 震
            '找': 0,  # 乾
            '搜': 2,  # 震
        }
        
        bagua_counts = [0] * 8
        total_weight = 0
        
        import re
        words = re.findall(r'[\u4e00-\u9fff]', context)
        for w in words:
            if w in WORD_BAGUA:
                idx = WORD_BAGUA[w]
                bagua_counts[idx] += 1.0
                total_weight += 1.0
            else:
                # 未登录词：均匀贡献
                total_weight += 0.1
        
        if total_weight < 0.5:
            return None, None
        
        bagua = [c / total_weight for c in bagua_counts]
        
        # 八卦 → 六爻编码（用简单的线性映射）
        # 把8个bagua分量映射到6个爻位的语义
        yao = [
            _clip(0.3 + 0.6 * bagua[0] - 0.3 * bagua[5]),  # y1: 乾-坎
            _clip(0.3 + 0.6 * bagua[6] - 0.3 * bagua[3]),  # y2: 兑-艮
            _clip(0.3 + 0.6 * bagua[4] - 0.3 * bagua[5]),  # y3: 离-坎
            _clip(0.3 + 0.6 * bagua[5] - 0.3 * bagua[0]),  # y4: 坎-乾
            _clip(0.3 + 0.6 * bagua[0] - 0.3 * bagua[7]),  # y5: 乾-巽
            _clip(0.3 + 0.6 * bagua[3] - 0.3 * bagua[2]),  # y6: 艮-震
        ]
        
        return bagua, yao
    
    def _semantic_alignment(self, parsed: Dict, v18_yao: List[float],
                            delta_yao: Optional[List[float]],
                            report) -> float:
        """
        候选动作的语义对齐分
        
        评估候选动作在"差距卦象空间"中的对齐程度。
        如果delta_yao显示当前策略在某维度偏离严重，
        则该维度上分数高意味着候选动作有助于修正偏差。
        """
        if delta_yao is None:
            return 0.5
        
        verb = parsed["verb"]
        
        # 差距卦象的符号向量（正=场景偏强，负=场景偏弱）
        delta_sign = [1.0 if d > 0.05 else (-1.0 if d < -0.05 else 0.0) for d in delta_yao]
        
        # 当前动作在6维上的倾向向量
        action_tendency = self._action_tendency(verb, parsed)
        
        # 对齐度 = 差距需要修正的方向 × 动作倾向的内积
        alignment = sum(d * a for d, a in zip(delta_sign, action_tendency))
        alignment = _clip(0.5 + 0.3 * alignment)
        
        # 爻位关系修正
        modifier = report.strategy_modifier
        
        return _clip(alignment * modifier)
    
    def _action_tendency(self, verb: str, parsed: Dict) -> List[float]:
        """动作类型在6维上的倾向向量"""
        TENDENCIES = {
            'go':     [0.7, 0.3, 0.2, 0.4, 0.6, 0.3],
            'take':   [0.5, 0.9, 0.3, 0.3, 0.7, 0.2],
            'put':    [0.5, 0.2, 0.5, 0.5, 0.5, 0.9],
            'move':   [0.5, 0.2, 0.5, 0.5, 0.5, 0.9],
            'open':   [0.6, 0.3, 0.2, 0.8, 0.5, 0.4],
            'close':  [0.6, 0.3, 0.2, 0.2, 0.4, 0.3],
            'clean':  [0.3, 0.5, 0.9, 0.6, 0.4, 0.3],
            'heat':   [0.3, 0.5, 0.9, 0.7, 0.4, 0.3],
            'cool':   [0.3, 0.5, 0.9, 0.7, 0.4, 0.3],
            'use':    [0.3, 0.5, 0.7, 0.5, 0.4, 0.3],
            'look':   [0.2, 0.2, 0.3, 0.2, 0.3, 0.5],
            'examine': [0.2, 0.2, 0.3, 0.2, 0.3, 0.5],
        }
        return TENDENCIES.get(verb, [0.5]*6)
    
    def _verb_to_bagua(self, verb: str) -> np.ndarray:
        """动词→八卦隶属度"""
        MAP = {
            'go': [0.6, 0.1, 0.6, 0.1, 0.1, 0.1, 0.1, 0.3],
            'take': [0.7, 0.2, 0.1, 0.5, 0.1, 0.2, 0.1, 0.1],
            'put': [0.1, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.6],
            'open': [0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.6, 0.2],
            'clean': [0.1, 0.4, 0.1, 0.1, 0.1, 0.7, 0.2, 0.2],
            'heat': [0.2, 0.1, 0.1, 0.1, 0.7, 0.1, 0.1, 0.1],
            'cool': [0.1, 0.2, 0.1, 0.1, 0.1, 0.7, 0.2, 0.2],
        }
        return np.array(MAP.get(verb, [0.3]*8))
    
    def _obj_to_bagua(self, obj_cls: str) -> Optional[np.ndarray]:
        """物体类别→八卦隶属度"""
        MAP = {
            'plate': [0.1, 0.7, 0.1, 0.4, 0.2, 0.1, 0.2, 0.3],
            'bowl': [0.1, 0.6, 0.1, 0.4, 0.2, 0.3, 0.2, 0.2],
            'cup': [0.2, 0.4, 0.1, 0.3, 0.3, 0.2, 0.3, 0.2],
            'apple': [0.2, 0.4, 0.2, 0.3, 0.3, 0.2, 0.3, 0.2],
            'knife': [0.7, 0.1, 0.1, 0.3, 0.1, 0.1, 0.1, 0.1],
            'soap': [0.1, 0.3, 0.1, 0.2, 0.1, 0.3, 0.3, 0.2],
            'bread': [0.1, 0.4, 0.1, 0.2, 0.3, 0.1, 0.2, 0.3],
            'tomato': [0.2, 0.3, 0.2, 0.2, 0.4, 0.3, 0.2, 0.2],
            'potato': [0.2, 0.5, 0.1, 0.4, 0.1, 0.1, 0.2, 0.2],
            'egg': [0.1, 0.3, 0.1, 0.2, 0.1, 0.1, 0.2, 0.1],
            'pencil': [0.3, 0.2, 0.1, 0.2, 0.2, 0.1, 0.2, 0.5],
            'book': [0.2, 0.3, 0.1, 0.4, 0.3, 0.1, 0.2, 0.3],
            'creditcard': [0.1, 0.2, 0.1, 0.2, 0.3, 0.1, 0.2, 0.1],
            'cellphone': [0.3, 0.2, 0.1, 0.2, 0.6, 0.1, 0.2, 0.2],
            'towel': [0.1, 0.5, 0.1, 0.3, 0.1, 0.3, 0.2, 0.4],
            'cloth': [0.1, 0.6, 0.1, 0.3, 0.1, 0.3, 0.2, 0.3],
        }
        return np.array(MAP.get(obj_cls, None)) if obj_cls and obj_cls in MAP else None
    
    def _bagua_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a is None or b is None:
            return 0.5
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    
    def get_context(self) -> str:
        return self._last_context
    
    # ──────────────────────────────────────────────
    # V18兼容接口：build_yao + dest_favorability
    # 用于agent的_maybe_retry等子流程
    # ──────────────────────────────────────────────
    def build_yao(self, parsed: Dict, world, goal, phase: Dict) -> List[float]:
        """V18兼容接口：构建6维六爻向量"""
        return self._v18_build_yao(parsed, world, goal, phase)
    
    def dest_favorability(self, world, goal, phase: Dict, dest_cls: str,
                          obj_cls: Optional[str] = None) -> float:
        """V18兼容接口：目的地卦象吉凶评分，用于重试链排序"""
        # 退化为V18的linear模式，避免依赖V19的完整pipeline
        return 0.5  # linear水平——不改变V18的优先排序
    
    def diagnose(self, world, goal, phase: Dict) -> Dict:
        """
        易理诊断接口：对当前情境做完整的卦象感知 + 爻位关系分析
        
        返回诊断报告，可在agent的stuck恢复逻辑中使用。
        """
        context = self.context.build(world, goal, phase)
        task_context = self.context.build_task_context(world, goal, phase)
        
        # 感知情境卦象
        scene_bagua, scene_yao = self._perceive_context(context)
        task_bagua, task_yao = self._perceive_context(task_context)
        
        report = {
            'scene_yao': scene_yao,
            'task_yao': task_yao,
            'delta_yao': None,
            'scene_report': None,
            'task_report': None,
            'diagnosis': 'normal',
            'suggestion': None,
        }
        
        if scene_yao is not None:
            sr = self.yao_relations.analyze(np.array(scene_yao))
            report['scene_report'] = sr
        
        if task_yao is not None and scene_yao is not None:
            tr = self.yao_relations.analyze(np.array(task_yao))
            report['task_report'] = tr
            delta = [scene_yao[i] - task_yao[i] for i in range(6)]
            report['delta_yao'] = delta
            
            # 诊断stuck原因
            report['diagnosis'], report['suggestion'] = self._diagnose_stuck(
                scene_yao, task_yao, delta, sr, tr, phase, goal
            )
        
        return report
    
    def _diagnose_stuck(self, scene_yao, task_yao, delta_yao,
                        scene_report, task_report, phase, goal=None) -> Tuple[str, str]:
        """
        从爻位关系诊断stuck原因
        
        返回 (诊断类型, 策略建议)
        """
        # --- 0. 最高优先级：look_at灯任务 → 灯是固定设备
        if goal is not None:
            needs_light = getattr(goal, 'needs_light', lambda: False)()
            task_type = getattr(goal, 'task_type', '')
            if needs_light or 'look' in str(task_type):
                return ('look_task_fix', '灯是固定设备，应在灯前使用use命令')
        
        # --- 1. 多处阴乘阳 → 外部阻力强（容器打不开、位置不对）
        if scene_report.cheng_count >= 2:
            return ('external_resistance', 
                    '多处阴乘阳，外部阻力大。建议切换探索目标，尝试不同容器')
        
        # --- 2. 上下无应 → 内部策略与外部环境不匹配
        if scene_report.ying_count == 0 and task_report and task_report.ying_count > 0:
            return ('strategy_mismatch',
                    '上下无应，当前策略与环境不匹配。建议从拿取/探索切换')
        
        # --- 3. 中位失据 → 决策方向迷茫
        if scene_report.score_dezhong < 0.25:
            return ('lost_direction',
                    '中位失据，方向不明确。建议扩大搜索范围，尝试新位置')
        
        # --- 4. 差距卦象的特定维度偏差
        if delta_yao is not None:
            # y1(行动)偏差大 → 位置不对
            if abs(delta_yao[0]) > 0.3:
                return ('position_mismatch',
                        '行动维度偏差大：当前位置与目标方向不一致')
            # y5(优先级)偏差大 → 抓错物体
            if abs(delta_yao[4]) > 0.3:
                return ('attention_mismatch',
                        '优先级维度偏差大：注意力放在错误目标上')
        
        # --- 5. 多处不当位 → 策略不稳
        if scene_report.dangwei_count <= 2:
            return ('unstable',
                    '多爻不当位，状态不稳。建议做简单的信息动作（look）重新评估')
        

        
        # --- 7. 六爻几乎全同（标差<0.02）→ 感知退化，随机扰动有益
        if max(scene_yao) - min(scene_yao) < 0.06:
            return ('stagnant_perception',
                    '卦象感知退化为均值，需融入随机探索')
        
        # --- 默认：V18原始frontier恢复
        return ('frontier_exhausted', None)
    
    def stuck_advice(self, world, goal, phase: Dict) -> Tuple[str, str]:
        """
        对外接口：返回 (诊断类型, 策略建议)
        可被agent_v18在stuck恢复点调用
        """
        diag = self.diagnose(world, goal, phase)
        return diag['diagnosis'], diag['suggestion']


# ═══════════════════════════════════════════════════════
# 测试入口
# ═══════════════════════════════════════════════════════

def test_context_builder():
    """测试情境构造器"""
    cb = ContextBuilder()
    
    # 模拟一个简单的world状态
    class MockWorld:
        def __init__(self):
            self.location = "countertop 1"
            self.inventory = {"plate 2"}
            self.objs = {}
            self.receps = {}
    
    class MockObj:
        def __init__(self, loc):
            self.location = loc
    
    class MockGoal:
        def __init__(self):
            self.task_type = "pick_clean_then_place_in_recep"
            self.object_class = "plate"
            self.recep_class = "countertop"
            self.process = "clean"
            self.tool_class = "sinkbasin"
        def needs_process(self): return True
        def needs_light(self): return False
        def is_target(self, cls): return cls == "plate"
    
    world = MockWorld()
    world.objs = {"plate 1": MockObj("countertop 1"), "plate 2": MockObj("inventory")}
    world.receps = {"cabinet 1": type('R', (), {'is_open': False})()}
    
    goal = MockGoal()
    phase = {"proc_done": True, "placed_count": 0, "searching": False, "holding_target": "plate 2"}
    
    context = cb.build(world, goal, phase)
    print(f"  Context: {context}")
    
    task_context = cb.build_task_context(world, goal, phase)
    print(f"  Task context: {task_context}")
    
    return context, task_context


if __name__ == "__main__":
    print("=== V19 Scorer 测试 ===")
    context, task_context = test_context_builder()
    
    print("\n=== 感知测试 ===")
    scorer = V19YLYWScorer(mode="full", alpha=0.3)
    bagua, yao = scorer._perceive_context(context)
    if bagua:
        print(f"  bagua: {[round(v,3) for v in bagua]}")
        print(f"  yao:   {[round(v,3) for v in yao]}")
    
    print("\n=== 卦象感知 + 关系分析 ===")
    for ctx_name, ctx in [("情境", context), ("任务", task_context)]:
        bg, yv = scorer._perceive_context(ctx)
        if yv:
            report = scorer.yao_relations.analyze(np.array(yv))
            print(f"  [{ctx_name}] yao={[round(v,2) for v in yv]}")
            print(f"    当位: {report.dangwei_count}/6, 得中得分: {report.score_dezhong:.2f}")
            print(f"    乘(逆): {report.cheng_count}处, 应: {report.ying_count}/3")
            print(f"    综合质量: {report.score_overall:.2f}, 谨慎: {report.caution_level}")
            print(f"    建议: {report.advice[:2]}")
    
    print("\nV19 Scorer 原型就绪 ✓")
