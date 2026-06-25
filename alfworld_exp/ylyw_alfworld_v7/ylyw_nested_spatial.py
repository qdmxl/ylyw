#!/usr/bin/env python3
"""
YLYW 嵌套空间探索模型 (Nested Spatial Explorer)

哲学基础：
  《周易·系辞》："仰以观于天文，俯以察于地理，是故知幽明之故"
  
  空间探索的本质是"格物致知"——每到一个新位置，观察到的物体
  布局构成一个"空间卦象"，所有已探索位置构成一个"空间六十四卦图谱"。
  
  嵌套结构：
    L0: 外层（空间态势感知层）—— 管理空间记忆，更新认知
    L1: 八卦基元 —— 编码位置类型（countertop→坤, sink→坎, lamp→离...）
    L2: 六爻编码 —— 编码空间探索状态（未知度、目标匹配度、探索深度...）
    L3: 六十四卦 —— 匹配探索策略（先观-后取-再行）
    
  自学习机制：
    每次探索一个新位置 → 更新空间记忆 → 重新编码六爻状态
    → 重新匹配卦象 → 策略更新 → 下一个决策更精准
"""

import sys
import os
import re
import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

from ylyw_core import PriorManual
from ylyw_core.yao_encoder import YaoEncoder, YaoPosition
from ylyw_core.trigram_base import TrigramBase, Trigram


# ============================================================
# L1: 空间八卦基元
# ============================================================

class SpatialTrigramBase:
    """
    空间八卦编码——将物理空间映射到八卦符号系统
    
    每个位置类型有一个主导八卦属性和次要属性：
      乾☰(天) — 高处/顶层存储：shelf, cabinet, dresser, safe
      坤☷(地) — 平面/承载面：countertop, desk, table, bed
      震☳(雷) — 动态/可开合：drawer
      巽☴(风) — 入口/过渡/柔软：doorway, cloth类
      坎☵(水) — 水相关/冷却：sinkbasin, fridge, toilet
      离☲(火) — 热源/光源：microwave, stoveburner, desklamp, toaster
      艮☶(山) — 静止/收纳：garbagecan, laundryhamper
      兑☱(泽) — 金属/液体容器：pot, pan, metal objects
    
    每个物体也有卦象，叠加到所在位置的卦象上，形成位置的"复合卦象"
    """
    
    # 位置 → 卦象
    LOCATION_BAGUA = {
        'shelf': '乾', 'cabinet': '乾', 'dresser': '乾', 'safe': '乾',
        'countertop': '坤', 'desk': '坤', 'table': '坤', 'bed': '坤',
        'sidetable': '坤', 'coffeetable': '坤', 'diningtable': '坤',
        'tvstand': '坤', 'sofa': '坤', 'armchair': '坤', 'ottoman': '坤',
        'drawer': '震',
        'doorway': '巽',
        'sinkbasin': '坎', 'fridge': '坎', 'toilet': '坎', 'bathtub': '坎',
        'microwave': '离', 'toaster': '离', 'coffeemachine': '离',
        'stoveburner': '离', 'desklamp': '离', 'floorlamp': '离',
        'garbagecan': '艮', 'laundryhamper': '艮',
    }
    
    # 物体 → 卦象
    OBJECT_BAGUA = {
        'keychain': '乾', 'creditcard': '乾', 'watch': '乾', 'alarmclock': '乾',
        'book': '坤', 'newspaper': '坤', 'box': '坤', 'tissuebox': '坤', 'pillow': '坤',
        'basketball': '震', 'baseballbat': '震',
        'cloth': '巽', 'towel': '巽', 'soapbar': '巽', 'sponge': '巽', 'blinds': '巽',
        'bottle': '坎', 'glass': '坎', 'mug': '坎', 'bowl': '坎', 'cup': '坎',
        'winebottle': '坎', 'spraybottle': '坎', 'soapbottle': '坎', 'glassbottle': '坎',
        'laptop': '离', 'cellphone': '离',
        'statue': '艮', 'vase': '艮', 'mirror': '艮', 'cane': '艮', 'plunger': '艮',
        'knife': '兑', 'fork': '兑', 'spoon': '兑', 'spatula': '兑',
        'pan': '兑', 'pot': '兑', 'plate': '兑', 'ladle': '兑',
        'whisk': '兑', 'butterknife': '兑', 'saltshaker': '兑', 'peppershaker': '兑',
        'apple': '坤', 'potato': '坤', 'egg': '坤', 'lettuce': '坤',
        'bread': '坤', 'tomato': '坤', 'pencil': '坤', 'pen': '坤', 'cd': '坤',
    }
    
    # 八卦相生（空间引导用）
    GENERATION = {'乾': '坤', '兑': '坤', '离': '震', '震': '坎',
                   '巽': '坎', '坎': '兑', '艮': '离', '坤': '离'}
    
    _bagua_order = ['乾', '坤', '震', '巽', '坎', '离', '艮', '兑']
    
    def location_to_bagua(self, loc_name: str) -> str:
        for key, bg in self.LOCATION_BAGUA.items():
            if key in loc_name:
                return bg
        return '坤'
    
    def object_to_bagua(self, obj_name: str) -> str:
        return self.OBJECT_BAGUA.get(obj_name, '坤')
    
    def bagua_to_index(self, bagua: str) -> int:
        return self._bagua_order.index(bagua) if bagua in self._bagua_order else 1
    
    def parent_bagua(self, bagua: str) -> str:
        """返回'生'该卦的父卦（要找到该类型物体，应优先去哪类位置）"""
        return self.GENERATION.get(bagua, '坤')


# ============================================================
# L2: 空间探索六爻编码器
# ============================================================

class SpatialYaoEncoder:
    """
    空间探索状态 → 六爻向量
    
    六爻定义（从下到上）：
      初爻: 空间未知度 — 还有多少位置未探索？(0=全未知, 1=全已知)
      二爻: 目标匹配度 — 当前已知物体与任务目标的语义重合度
      三爻: 探索深度 — 已探索层数 / 已有多少不同区域被覆盖
      四爻: 反馈有效性 — 最近几步探索是否带来了新信息
      五爻: 任务进度 — 是否找到了目标物体 / 推进了多少 phase
      上爻: 空间约束 — 剩余可探索目标数量（0个 = 卡住）
    
    自学习机制：
      每次探索后重新编码 → 六爻值改变 → 匹配的卦象改变 → 策略调整
    """
    
    def __init__(self):
        self.yao_positions = list(YaoPosition)
    
    def encode(self, spatial_state: Dict) -> np.ndarray:
        """
        Args:
            spatial_state: {
                'total_locations': int,        # 总可探索位置数
                'visited_locations': int,       # 已访问位置数
                'found_objects': set,           # 已发现的物体名集合
                'target_objects': set,          # 目标物体名集合
                'target_bagua': str,            # 目标物体八卦属性
                'recent_discoveries': int,      # 最近3步新发现的物体数
                'phase_progress': float,        # 任务进度 [0,1]
                'stuck_indicator': float,       # 卡住程度 [0,1] (0=正常, 1=完全卡住)
            }
        """
        features = {
            'unknownness': 1.0 - min(1.0, spatial_state.get('visited_locations', 0) / 
                              max(1, spatial_state.get('total_locations', 1))),
            'target_match': self._calc_target_match(spatial_state),
            'exploration_depth': min(1.0, spatial_state.get('visited_locations', 0) / 20),
            'feedback_quality': min(1.0, spatial_state.get('recent_discoveries', 0) / 3),
            'task_progress': spatial_state.get('phase_progress', 0.0),
            'space_constraint': spatial_state.get('stuck_indicator', 0.0),
        }
        
        # 用 YLYW 原生编码器
        yao = np.zeros(6, dtype=np.float32)
        yao[0] = features['unknownness']
        yao[1] = features['target_match']
        yao[2] = features['exploration_depth']
        yao[3] = features['feedback_quality']
        yao[4] = features['task_progress']
        yao[5] = 1.0 - features['space_constraint']  # 上爻反转
        
        return yao
    
    def _calc_target_match(self, state: Dict) -> float:
        """计算目标匹配度：已发现的物体中有多少匹配目标"""
        found = state.get('found_objects', set())
        targets = state.get('target_objects', set())
        if not targets:
            return 0.0
        match_count = sum(1 for t in targets if any(t in f for f in found))
        return match_count / len(targets)


# ============================================================
# L3: 空间探索策略库 (六十四卦映射)
# ============================================================

class SpatialStrategyBase:
    """
    六十四卦 → 空间探索策略
    
    关键卦象与探索策略的映射：
    
      观卦(䷓) — 先观察后行动 → 优先 look/inventory 而非 go
      复卦(䷗) — 反复探索 → 回溯已访问位置，可能有遗漏
      蹇卦(䷦) — 遇到困难 → 改变探索方向，避免死循环
      解卦(䷧) — 困难解除 → 刚找到目标，应快速推进任务
      渐卦(䷴) — 渐进探索 → 逐层深入未访问区域
      需卦(䷄) — 等待时机 → 当前位置可能有遗漏，先 look
      师卦(䷆) — 集中力量 → 目标明确，直接去语义匹配的位置
      比卦(䷇) — 亲附接近 → 优先去与目标物体卦象相生的位置
    """
    
    STRATEGIES = {
        'GUAN': {   # ䷓ 观卦
            'name': '观卦-先观后行',
            'priority': ['look', 'inventory', 'examine'],
            'max_go_steps': 1,
            'description': '先观察环境，再决定行动方向',
        },
        'FU': {     # ䷗ 复卦
            'name': '复卦-反复探索',
            'priority': ['go to'],
            'revisit_ok': True,
            'description': '回到已访问位置，可能有遗漏的线索',
        },
        'JIAN': {   # ䷦ 蹇卦 (水山蹇)
            'name': '蹇卦-困难转向',
            'priority': ['go to'],
            'avoid_recent': 5,
            'description': '前路艰难，改变方向绕过障碍',
        },
        'XIE': {    # ䷧ 解卦 (雷水解)
            'name': '解卦-困难解除',
            'priority': ['take', 'use', 'clean', 'heat', 'cool', 'put'],
            'skip_explore': True,
            'description': '目标已发现，集中执行任务动作',
        },
        'JIAN_GUA': {  # ䷴ 渐卦 (风山渐)
            'name': '渐卦-渐进探索',
            'priority': ['go to'],
            'explore_deep': True,
            'description': '一步一步深入未知区域',
        },
        'XU': {     # ䷄ 需卦 (水天需)
            'name': '需卦-等待时机',
            'priority': ['look', 'examine', 'go to'],
            'description': '不急于行动，先充分观察',
        },
        'SHI': {    # ䷆ 师卦 (地水师)
            'name': '师卦-集中突破',
            'priority': ['go to'],
            'target_guided': True,
            'description': '目标明确，集中力量直达目标位置',
        },
        'BI': {     # ䷇ 比卦 (水地比)
            'name': '比卦-亲附接近',
            'priority': ['go to'],
            'bagua_guided': True,
            'description': '根据卦象相生关系选择接近目标的位置',
        },
    }
    
    DEFAULT_STRATEGY = {
        'name': '默认探索',
        'priority': ['go to'],
        'description': '标准空间探索',
    }
    
    def match_strategy(self, yao_vector: np.ndarray,
                        hexagram_rules) -> Tuple[str, Dict]:
        """
        根据六爻向量匹配最佳探索策略
        
        匹配规则（先验知识）：
          - 高未知度 + 低目标匹配 → 渐卦（逐步探索）
          - 高未知度 + 低反馈 → 观卦（先观察）
          - 低未知度 + 低目标匹配 → 蹇卦（方向错误，需改变）
          - 高目标匹配 + 低进度 → 师卦（集中突破）
          - 高目标匹配 + 高进度 → 解卦（快速完成）
          - 空间约束高 → 复卦（回到原点）
        """
        # 尝试匹配最佳卦象
        best_hexagram, score = hexagram_rules.get_best_hexagram(yao_vector)
        hex_name = best_hexagram.name if best_hexagram else ''
        
        # 根据 hexagram name 查找策略
        strategy = self.STRATEGIES.get(hex_name, self.DEFAULT_STRATEGY)
        
        # 根根据爻值微调策略（自学习）
        strategy = dict(strategy)  # copy
        
        # 如果最近反馈好 → 增强探索
        if yao_vector[3] > 0.6:
            strategy['boost_explore'] = True
        
        # 如果目标匹配度高 → 优先执行任务动作
        if yao_vector[1] > 0.5:
            strategy['priority'] = ['take', 'use', 'clean', 'heat', 'cool', 'put', 'go to']
        
        return hex_name, strategy


# ============================================================
# L0: 外层 — 空间态势感知层（嵌套入口）
# ============================================================

class NestedSpatialExplorer:
    """
    YLYW 嵌套空间探索模型
    
    架构:
      L0 (外层): 空间态势感知 — 管理记忆、更新认知、调度内层
      L1: 空间八卦编码 — 位置/物体 → 卦象
      L2: 空间六爻编码 — 探索状态 → 爻向量
      L3: 探索策略库 — 爻向量 → 策略决策
      
    嵌套含义:
      内层 YLYW (L1-L3) 负责每一步的"微观决策"
      外层 L0 负责"宏观态势"——积累空间知识，修正内层输入
    
    自学习流程:
      1. 每步执行 → 观察结果 → 更新 spatial_memory
      2. 重新编码六爻（含新的空间知识）
      3. 重新匹配卦象/策略
      4. 策略指导下一步选择
    """
    
    def __init__(self, llm_guide=None):
        self.spatial_bagua = SpatialTrigramBase()
        self.spatial_encoder = SpatialYaoEncoder()
        self.strategy_base = SpatialStrategyBase()
        self.manual = PriorManual(verbose=False)
        self.llm_guide = llm_guide
        
        # L-1 结构化认知层
        self.cognition = None  # StructuralCognitionLayer 实例
        
        # 空间记忆（自学习的核心数据结构）
        self.memory = None  # 每个游戏重置
        self.task_desc = ""
        self.target_objects = set()
        self.target_bagua = '坤'
        self.exploration_history = []
        self.last_strategy = None
        self.last_hexagram = None
        
        # LLM 语义实体
        self._entity_cache = {}
        
        # 常识先验置信度 - 场景自适应自学习
        # key=位置类型(bed/desk/shelf...), value=当前置信度(初始=常识先验分)
        self._location_confidence = {}
        self._prior_weights = {}  # 固化权重: {位置类型: 常识先验分}
    
    def reset(self, task_desc: str, task_type: str = ""):
        """重置探索状态"""
        self.memory = {
            'visited': {},           # {loc_name: {objects, bagua, visit_count}}
            'found_objects': set(),  # 全局发现的所有物体
            'total_locations': 0,    # 将在首次记录时更新
            'step_in_phase': 0,
            'phase_progress': 0.0,
        }
        self.task_desc = task_desc
        self.exploration_history = []
        self.last_strategy = None
        self.last_hexagram = None
        
        # 从 LLM guide 获取目标信息
        if self.llm_guide:
            entities = self.llm_guide.get_target_entities(task_desc, task_type)
            self.target_objects = set(entities.get('objects', []))
            self._entity_cache = entities
        else:
            self.target_objects = set()
            self._entity_cache = {}
        
        # 初始化常识先验置信度
        self._init_prior_weights()
        
        # 确定目标卦象
        if self.target_objects:
            first_obj = list(self.target_objects)[0]
            self.target_bagua = self.spatial_bagua.object_to_bagua(first_obj)
        
        # 初始化 L-1 结构化认知层
        try:
            from structural_cognition_layer import StructuralCognitionLayer
            self.cognition = StructuralCognitionLayer()
            expected = set(self._prior_weights.keys())
            tools = set(self._entity_cache.get('tools', []))
            self.cognition.reset(task_type, self.target_objects, tools, expected)
        except ImportError:
            self.cognition = None
    
    def _init_prior_weights(self):
        """初始化常识先验权重——固化物体→位置关联知识"""
        hints = self._entity_cache.get('object_hints', {})
        priority = self._entity_cache.get('exploration_priority', [])
        
        self._prior_weights = {}
        # 排名越前权重越高
        for rank, loc in enumerate(priority):
            self._prior_weights[loc] = 1.0 - rank * 0.05  # 第1名=1.0, 第2名=0.95...
        
        # 补充 hints 中不在 priority 的位置
        for obj, loc_list in hints.items():
            for loc in loc_list:
                if loc not in self._prior_weights:
                    self._prior_weights[loc] = 0.5
        
        # 当前置信度 = 先验权重
        self._location_confidence = dict(self._prior_weights)
    
    def record_step(self, action: str, obs: str):
        """记录每一步，更新空间记忆 — 自学习的核心"""
        action_lower = action.lower().strip()
        self.exploration_history.append(action)
        
        if action_lower.startswith('go to '):
            loc = self._normalize(action_lower.replace('go to ', ''))
            
            # 从 obs 提取物体
            objects = set()
            for m in re.finditer(r'(?:a|an)\s+([a-zA-Z]+)(?:\s*\d+)?', obs):
                o = m.group(1).lower()
                if o not in ('you', 'the', 'middle', 'room'):
                    objects.add(o)
                    self.memory['found_objects'].add(o)
            
            # 记录或更新位置
            if loc not in self.memory['visited']:
                bagua = self.spatial_bagua.location_to_bagua(loc)
                self.memory['visited'][loc] = {
                    'objects': objects,
                    'bagua': bagua,
                    'visit_count': 1,
                    'first_discovery': len(objects),
                }
            else:
                prev = self.memory['visited'][loc]
                new_objs = objects - prev['objects']
                prev['objects'] |= objects
                prev['visit_count'] += 1
                prev['recent_discovery'] = len(new_objs)
            
            self.memory['total_locations'] = max(
                self.memory['total_locations'], len(self.memory['visited']))
            
            # *** 自学习: 更新位置置信度 ***
            # 提取位置类型(bed 1 → bed)
            loc_type = re.sub(r'\s*\d+$', '', loc)
            has_target = any(
                any(t in o for o in objects) 
                for t in self.target_objects
            )
            if not has_target and loc_type in self._location_confidence:
                # 去了但没找到目标 → 降低该类型位置的置信度
                old_conf = self._location_confidence[loc_type]
                self._location_confidence[loc_type] = max(0.0, old_conf - 0.25)
            elif has_target and loc_type in self._location_confidence:
                # 找到了 → 提高该类型置信度
                self._location_confidence[loc_type] = min(1.0, self._location_confidence[loc_type] + 0.3)
        
        # phase progress 更新
        if self.memory['found_objects']:
            match_count = sum(1 for t in self.target_objects 
                            if any(t in f for f in self.memory['found_objects']))
            self.memory['phase_progress'] = min(1.0, 
                match_count / max(1, len(self.target_objects)))
        
        # L-1 结构化认知更新
        if self.cognition and action_lower.startswith('go to '):
            loc_type = re.sub(r'\s*\d+$', '', self._normalize(action_lower.replace('go to ', '')))
            visited_types = set(re.sub(r'\s*\d+$', '', loc) for loc in self.memory['visited'].keys())
            # total_types = 当前访问过的类型数 + 估计未访问数
            # 保守估计: 假设还有 visited_types * 0.5 个未访问
            estimated_total = max(len(visited_types), 
                                   int(len(visited_types) * 1.5))
            self.cognition.update(loc_type, objects, len(visited_types), estimated_total, 0)
    
    def get_spatial_state(self, current_phase: int,
                           admissible_commands: List[str]) -> Dict:
        """生成当前空间状态的六爻编码输入"""
        total_loc = len(admissible_commands) if admissible_commands else 1
        visited = len(self.memory['visited'])
        
        # 最近3步发现了多少新物体
        recent = 0
        for i in range(1, min(4, len(self.exploration_history) + 1)):
            if i <= len(self.exploration_history):
                recent += self._count_recent_discoveries(i)
        
        # 卡住检测
        stuck = 0.0
        if len(self.exploration_history) >= 4:
            last4 = self.exploration_history[-4:]
            go_actions = [a for a in last4 if a.startswith('go to ')]
            unique_gos = len(set(go_actions))
            if len(go_actions) >= 3 and unique_gos <= 2:
                stuck = 0.8  # 反复在两个位置间切换
            elif self.memory['phase_progress'] == 0 and visited >= 6:
                stuck = 0.5
        
        return {
            'total_locations': total_loc,
            'visited_locations': visited,
            'found_objects': self.memory['found_objects'],
            'target_objects': self.target_objects,
            'target_bagua': self.target_bagua,
            'recent_discoveries': recent,
            'phase_progress': self.memory['phase_progress'],
            'stuck_indicator': stuck,
        }
    
    def select_explore_target(self, go_cmds: List[str]) -> Optional[str]:
        """
        根据当前自学习状态 + L-1 认知结果选择探索目标
        
        决策流程:
          0. 查询 L-1: 是否该放弃？是否找到目标？
          1. 编码当前空间状态 → 六爻向量
          2. 匹配最佳卦象 → 探索策略
          3. 根据策略 + L-1 recommendation 筛选/排序 go_cmds
          4. 返回最佳目标
        """
        if not go_cmds:
            return None
        
        # Step 0: L-1 结构化认知
        if self.cognition:
            rec = self.cognition.recommendation
            if rec == 'abort':
                # 认知层判定不可完成 → 返回 None 让上层处理
                return None
            if rec == 'search_anywhere':
                # 忽略常识先验，探索所有未访问位置
                visited = set(self.memory['visited'].keys())
                for cmd in go_cmds:
                    norm = self._normalize(cmd.replace('go to ', ''))
                    if norm not in visited:
                        return cmd
            if rec == 'skip_explore':
                return None  # 目标已找到，转为执行
        
        # Step 1-2: 编码 + 策略匹配
        state = self.get_spatial_state(0, go_cmds)
        yao = self.spatial_encoder.encode(state)
        hex_name, strategy = self.strategy_base.match_strategy(
            yao, self.manual.hexagram_rules)
        
        self.last_hexagram = hex_name
        self.last_strategy = strategy
        
        # Step 3: 根据策略筛选
        if strategy.get('skip_explore'):
            return None  # 让上层执行任务动作
        
        if strategy.get('target_guided'):
            return self._target_guided_select(go_cmds)
        
        if strategy.get('bagua_guided'):
            return self._bagua_guided_select(go_cmds)
        
        # Step 4: 智能候选排序
        return self._smart_select(go_cmds, strategy)
    
    def _target_guided_select(self, go_cmds: List[str]) -> Optional[str]:
        """目标引导：优先去 LLM 提示的含目标物体/工具位置类型"""
        if not self._entity_cache:
            return self._smart_select(go_cmds, {})
        
        hints = self._entity_cache.get('object_hints', {})
        explore_priority = self._entity_cache.get('exploration_priority', [])
        tools = self._entity_cache.get('tools', [])
        visited = set(self.memory['visited'].keys())
        
        # 0. 工具辅助引导：如果 task 需要工具（如 desklamp），优先去工具位置
        if tools:
            tool_hints = {
                'desklamp': ['desk', 'shelf'],
                'floorlamp': ['floor', 'shelf'],
            }
            for tool in tools:
                loc_hints = tool_hints.get(tool, ['desk', 'shelf', 'countertop'])
                for hint in loc_hints:
                    for cmd in go_cmds:
                        norm = self._normalize(cmd.replace('go to ', ''))
                        if hint in norm and norm not in visited:
                            return cmd
        
        # L-1: 如果 recommendation 是 expand_search，强制跳过已访问的 hints 位置
        if self.cognition and self.cognition.recommendation == 'expand_search':
            hint_visited = all(
                any(h in v for v in visited) 
                for h in explore_priority
            )
            if hint_visited:
                # 跳过 hints 中的位置，直接进入 search_anywhere
                unvisited = [c for c in go_cmds 
                           if self._normalize(c.replace('go to ', '')) not in visited]
                if unvisited:
                    return unvisited[0]
        
        # 1. 优先去 exploration_priority 中的位置类型
        for priority_loc in explore_priority:
            for cmd in go_cmds:
                norm = self._normalize(cmd.replace('go to ', ''))
                if priority_loc in norm and norm not in visited:
                    return cmd
        
        # 2. 其次去 hints 中的位置
        for obj, loc_hints in hints.items():
            for hint in loc_hints:
                for cmd in go_cmds:
                    norm = self._normalize(cmd.replace('go to ', ''))
                    if hint in norm and norm not in visited:
                        return cmd
        
        return self._smart_select(go_cmds, {'avoid_recent': 2})
    
    def _bagua_guided_select(self, go_cmds: List[str]) -> Optional[str]:
        """卦象引导：优先去"生"目标物体卦象的位置"""
        parent_bagua = self.spatial_bagua.parent_bagua(self.target_bagua)
        visited = set(self.memory['visited'].keys())
        
        # 优先：父卦位置 + 未访问
        for cmd in go_cmds:
            norm = self._normalize(cmd.replace('go to ', ''))
            loc_bagua = self.spatial_bagua.location_to_bagua(norm)
            if loc_bagua == parent_bagua and norm not in visited:
                return cmd
        
        # 其次：同类卦象 + 未访问
        for cmd in go_cmds:
            norm = self._normalize(cmd.replace('go to ', ''))
            loc_bagua = self.spatial_bagua.location_to_bagua(norm)
            if loc_bagua == self.target_bagua and norm not in visited:
                return cmd
        
        return self._smart_select(go_cmds, {'avoid_recent': 2})
    
    def _smart_select(self, go_cmds: List[str], 
                       strategy: Dict = None) -> Optional[str]:
        """
        智能选择：基于空间记忆 + 常识先验 + 自学习置信度的多维度排序
        
        排序维度:
          1. 常识先验置信度（权重 2.5）— 固化的物体→位置知识 + 场景反馈
          2. 未访问优先（权重 1.5）
          3. 目标物体卦象兼容（权重 0.8）
          4. 物体丰富度（权重 0.3）
          5. 避免最近访问（惩罚 -4.0）
        """
        strategy = strategy or {}
        visited = set(self.memory['visited'].keys())
        avoid_recent = strategy.get('avoid_recent', 2)
        
        # 最近 avoid_recent 步去过的位置
        recent_locs = []
        for a in reversed(self.exploration_history[-avoid_recent:]):
            if a.startswith('go to '):
                recent_locs.append(self._normalize(a.replace('go to ', '')))
        
        scored = []
        for cmd in go_cmds:
            norm = self._normalize(cmd.replace('go to ', ''))
            score = 0.0
            
            # 1. 常识先验置信度（核心改进）
            loc_type = re.sub(r'\s*\d+$', '', norm)
            prior_conf = self._location_confidence.get(loc_type, 0.3)  # 未知类型默认中性置信
            score += prior_conf * 2.5
            
            # 2. 未访问加分（但对低置信度位置降低权重）
            if norm not in visited:
                score += 1.5
            
            # 3. 卦象兼容
            loc_bagua = self.spatial_bagua.location_to_bagua(norm)
            parent = self.spatial_bagua.parent_bagua(self.target_bagua)
            if loc_bagua == parent:
                score += 0.8
            elif loc_bagua == self.target_bagua:
                score += 0.4
            
            # 4. 物体丰富度
            if norm in visited:
                obj_count = len(self.memory['visited'][norm].get('objects', []))
                score += min(obj_count * 0.05, 0.3)
            
            # 5. 避免最近访问（强惩罚）
            if norm in recent_locs:
                score -= 4.0
            
            # 6. 循环检测：如果该位置在最近4步中出现 ≥ 3次 → 额外惩罚
            recent_all = [self._normalize(a.replace('go to ', ''))
                         for a in self.exploration_history[-6:]
                         if a.startswith('go to ')]
            if recent_all.count(norm) >= 3:
                score -= 5.0
            
            scored.append((cmd, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None
    
    def should_explore(self, current_phase: int, 
                        subgoals: List[List[str]]) -> bool:
        """判断当前是否需要空间探索（而非执行任务动作）"""
        if current_phase >= len(subgoals):
            return False
        
        target_actions = subgoals[current_phase]
        
        # go to 阶段总是需要探索
        if 'go to' in target_actions:
            return True
        
        return False
    
    def get_spatial_memory_summary(self) -> str:
        """生成空间记忆的可读摘要"""
        visited = self.memory['visited']
        if not visited:
            return "none"
        
        parts = []
        for loc, info in sorted(visited.items()):
            objs = ', '.join(sorted(info['objects'])[:3])
            if len(info['objects']) > 3:
                objs += f" (+{len(info['objects'])-3})"
            parts.append(f"{loc}({info['bagua']}): [{objs}]")
        return ' | '.join(parts[:5])
    
    # helpers
    def _normalize(self, name: str) -> str:
        return name.strip().lower()
    
    def _count_recent_discoveries(self, steps_back: int) -> int:
        if steps_back > len(self.exploration_history):
            return 0
        # 简化：检查最近访问的位置是否有新物体
        return 0


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    from llm_semantic_guide import LLMSemanticGuide
    
    guide = LLMSemanticGuide()
    explorer = NestedSpatialExplorer(llm_guide=guide)
    
    # Test 1: basic reset and state encoding
    explorer.reset("Put a clean plate on the counter.", "pick_clean_then_place_in_recep")
    print("=== Test 1: Initial State ===")
    print(f"Target objects: {explorer.target_objects}")
    print(f"Target bagua: {explorer.target_bagua}")
    print(f"Parent bagua: {explorer.spatial_bagua.parent_bagua(explorer.target_bagua)}")
    
    state = explorer.get_spatial_state(0, ['go to ' + x for x in 
        ['bed 1','desk 1','shelf 1','countertop 1','cabinet 1','fridge 1']])
    print(f"Spatial state: {state}")
    
    yao = explorer.spatial_encoder.encode(state)
    print(f"Yao vector: {yao}")
    print(f"Values: unknown={yao[0]:.2f} match={yao[1]:.2f} depth={yao[2]:.2f} "
          f"feedback={yao[3]:.2f} progress={yao[4]:.2f} constraint={yao[5]:.2f}")
    
    # Test 2: simulate exploration
    print("\n=== Test 2: Simulated Exploration ===")
    go_cmds = ['go to shelf 1', 'go to shelf 2', 'go to bed 1', 'go to desk 1']
    
    for i, cmd in enumerate(go_cmds):
        target = explorer.select_explore_target(go_cmds)
        print(f"Step {i}: selects {target}, hexagram={explorer.last_hexagram}")
        # Simulate observation
        fake_obs = f"You arrive at {cmd}. You see some objects."
        explorer.record_step(target or cmd, fake_obs)
    
    # Test re-encoding after exploration
    state2 = explorer.get_spatial_state(0, go_cmds)
    yao2 = explorer.spatial_encoder.encode(state2)
    print(f"\nAfter exploration: yao={yao2}")
    print(f"  unknown={yao2[0]:.2f} match={yao2[1]:.2f} depth={yao2[2]:.2f}")
    print(f"  Memory: {explorer.get_spatial_memory_summary()}")
    
    # Test target-guided selection
    print(f"\n  Entity cache: {explorer._entity_cache}")
    selected = explorer.select_explore_target(['go to countertop 1', 'go to bed 1', 'go to shelf 3'])
    print(f"  Target-guided selects: {selected}")
