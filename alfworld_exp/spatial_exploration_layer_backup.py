#!/usr/bin/env python3
"""
YLYW 空间探索层 (Spatial Exploration Layer)

将 ALFWorld 物理空间映射到 YLYW 八卦框架中：
  - 8个空间八卦（8宫）：乾(高处/顶层)、坤(地面/底层)、震(动态/可移动)、
    巽(入口/过渡)、坎(含水量/水槽区)、离(光源/明亮区)、
    艮(静止/固定)、兑(金属/器具区)
  
  - 每个已探索位置 → 一个"空间卦象"（其物件布局的八卦特征）
  - 探索策略由卦象关系（相生相克）驱动：
    * 要找金属器具（兑）→ 优先探索离(火克金=附近)、坤(土生金=地面)

多层嵌套架构：
  Layer S (外层): 空间状态管理 + 路径规划
  Layer 0 (引导层): LLM语义引导 → 探索优先级
  Layer 1-3 (核心层): 原有 YLYW 三层推理

空间卦象编码规则：
  一个位置收集的物体类型 → 八卦隶属度向量
  物体多→坤(承载)、光源→离(明)、水→坎(陷)、金属→兑(悦)
"""

import sys
import os
import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

from ylyw_core import PriorManual


# 空间八卦定义：地点类型 → 卦象
LOCATION_BAGUA = {
    # 高处/存储 → 乾(天)
    'shelf': '乾', 'cabinet': '乾', 'dresser': '乾', 'safe': '乾',
    # 地面/承载 → 坤(地)
    'countertop': '坤', 'table': '坤', 'desk': '坤', 'bed': '坤',
    'sidetable': '坤', 'coffeetable': '坤', 'diningtable': '坤',
    'tvstand': '坤', 'sofa': '坤', 'armchair': '坤', 'ottoman': '坤',
    # 动态/可移动 → 震(雷)
    'drawer': '震',
    # 入口/过渡 → 巽(风)
    'doorway': '巽',
    # 含水量 → 坎(水)
    'sinkbasin': '坎', 'fridge': '坎', 'toilet': '坎',
    'bathtub': '坎', 'laundryhamper': '坎',
    # 光源/加热 → 离(火)
    'microwave': '离', 'toaster': '离', 'coffeemachine': '离',
    'stoveburner': '离', 'desklamp': '离', 'floorlamp': '离',
    # 静止/固定 → 艮(山)
    'garbagecan': '艮',
    # 金属/器具 → 兑(泽)
    'drawer': '兑',  # 抽屉也属兑（金属）
}

# 物体类型 → 物品卦象
OBJECT_BAGUA = {
    # 乾(天) → 贵重、高处物品
    'keychain': '乾', 'creditcard': '乾', 'watch': '乾',
    'alarmclock': '乾', 'remotecontrol': '乾',
    # 坤(地) → 承载、大量物品
    'book': '坤', 'newspaper': '坤', 'box': '坤', 'tissuebox': '坤',
    'pillow': '坤', 'candle': '坤',
    # 震(雷) → 运动物品
    'basketball': '震', 'baseballbat': '震',
    # 坎(水) → 液体相关
    'bottle': '坎', 'glass': '坎', 'mug': '坎', 'bowl': '坎',
    'winebottle': '坎', 'glassbottle': '坎', 'spraybottle': '坎',
    'soapbottle': '坎', 'cup': '坎',
    # 离(火) → 加热/光相关
    'laptop': '离', 'cellphone': '离',
    # 艮(山) → 重物/固定物
    'statue': '艮', 'vase': '艮', 'mirror': '艮',
    'cane': '艮', 'plunger': '艮',
    # 兑(泽) → 金属器具
    'knife': '兑', 'fork': '兑', 'spoon': '兑', 'spatula': '兑',
    'pan': '兑', 'pot': '兑', 'plate': '兑', 'ladle': '兑',
    'whisk': '兑', 'butterknife': '兑', 'saltshaker': '兑',
    'peppershaker': '兑', 'scrubbrush': '兑',
    # 巽(风) → 柔软/可变形
    'cloth': '巽', 'towel': '巽', 'soapbar': '巽',
    'sponge': '巽', 'blinds': '巽',
    # 食物
    'apple': '坤', 'potato': '坤', 'egg': '坤',
    'lettuce': '坤', 'bread': '坤', 'tomato': '坤',
}

# 卦象相生关系 (生我者 → 被生者)
# 在空间探索中：要找到 X 类型物体，应该优先探索 "生X" 的卦象区域
BAGUA_GENERATION = {
    '乾': '坤',  # 坤生乾（地面之上才能有贵重物）
    '兑': '坤',  # 坤生兑（台面之上放金属器具）
    '离': '震',  # 震生离（动静生光热）
    '震': '坎',  # 坎生震（水生木，动）
    '巽': '坎',  # 坎生巽（水边有风）
    '坎': '兑',  # 兑生坎（金属生水）
    '艮': '离',  # 离生艮（火生山）
    '坤': '离',  # 离生坤（火生土）
}

# 反查：被X生的卦象（X生谁）
BAGUA_GENERATED_BY = {}
for child, parent in BAGUA_GENERATION.items():
    BAGUA_GENERATED_BY.setdefault(parent, []).append(child)


class SpatialMemory:
    """空间记忆：记录已访问位置及其物体"""
    
    def __init__(self):
        self.visited: Dict[str, Dict] = {}  # location_name → {objects_seen, bagua_type, visit_count}
        self.current_location: str = ""
    
    def record_visit(self, location: str, objects_seen: List[str], obs_text: str = ""):
        """记录一次空间访问"""
        loc_key = self._normalize_name(location)
        if loc_key not in self.visited:
            self.visited[loc_key] = {
                'objects': set(),
                'bagua_type': self._infer_location_bagua(loc_key),
                'visit_count': 0,
            }
        self.visited[loc_key]['objects'].update(objects_seen)
        self.visited[loc_key]['visit_count'] += 1
        self.current_location = loc_key
    
    def _normalize_name(self, name: str) -> str:
        """标准化位置名：bed 1 → bed 1 (保留数字区分同类不同实例)"""
        return name.strip().lower()
    
    def _infer_location_bagua(self, loc: str) -> str:
        """推断位置卦象"""
        for key, bagua in LOCATION_BAGUA.items():
            if key in loc:
                return bagua
        return '坤'  # 默认坤（地面/平坦）
    
    def get_unvisited_preferred(self, available_locations: List[str],
                                  target_obj_bagua: str = "") -> List[str]:
        """
        返回未访问位置，按卦象关联优先级排序
        
        如果已知目标物体卦象：
          优先探索"生该卦象"的区域（如找兑(金属)→优先坤(台面)）
          
        否则：
          优先探索未被访问过的位置
        """
        unvisited = []
        for loc in available_locations:
            norm = self._normalize_name(loc)
            if norm not in self.visited:
                loc_bagua = self._infer_location_bagua(norm)
                unvisited.append((loc, loc_bagua))
        
        if not unvisited:
            return []
        
        # 卦象优先排序
        if target_obj_bagua:
            # 找"生"该卦象的父卦位置
            parent = BAGUA_GENERATION.get(target_obj_bagua, '坤')
            
            def priority(item):
                loc, bagua = item
                score = 0
                if bagua == parent:
                    score += 2  # 父卦（最可能）
                if bagua == target_obj_bagua:
                    score += 1  # 同类也可能
                return -score  # 降序
            
            unvisited.sort(key=priority)
        
        return [loc for loc, _ in unvisited]
    
    def has_target_object(self, obj_name: str) -> Optional[str]:
        """检查是否在某处见过目标物体，返回位置名"""
        for loc, info in self.visited.items():
            for seen_obj in info['objects']:
                if obj_name in seen_obj or seen_obj in obj_name:
                    return loc
        return None


class SpatialExplorationLayer:
    """
    YLYW 空间探索层（Layer S）
    
    在多房间 ALFWorld 环境中管理空间状态和探索策略。
    使用八卦框架编码空间关系和物体分布规律。
    
    设计原则：
      - 与 Layer 1-3 同构：八卦 → 六爻 → 策略
      - 探索策略 = 卦象搜索（根据目标物体卦象决定优先探索区域）
      - 记忆驱动：记录已访问位置避免重复
    """
    
    def __init__(self, llm_guide=None):
        self.manual = PriorManual(verbose=False)
        self.memory = SpatialMemory()
        self.llm_guide = llm_guide  # LLMSemanticGuide 实例
        
        # 探索状态
        self.task_desc = ""
        self.task_type = ""
        self.target_objects = []     # [(name, bagua_type), ...]
        self.target_locations = []   # [(name, bagua_type), ...]
        self.exploration_priority = []  # 优先探索的位置类型列表
    
    def reset(self, task_desc: str, task_type: str = ""):
        """重置探索状态"""
        self.memory = SpatialMemory()
        self.task_desc = task_desc
        self.task_type = task_type
        
        # 从 LLM Guide 获取目标实体
        if self.llm_guide:
            entities = self.llm_guide.get_target_entities(task_desc, task_type)
            self.target_objects = [
                (obj, OBJECT_BAGUA.get(obj, '坤'))
                for obj in entities.get('objects', [])
            ]
            self.target_locations = [
                (loc, LOCATION_BAGUA.get(loc, '坤'))
                for loc in entities.get('locations', [])
            ]
            self.target_tools = [
                (tool, OBJECT_BAGUA.get(tool, '离'))
                for tool in entities.get('tools', [])
            ]
            self.exploration_priority = entities.get('exploration_priority', [])
        else:
            self.target_objects = []
            self.target_locations = []
            self.target_tools = []
            self.exploration_priority = []
    
    def record_step(self, action: str, obs: str):
        """记录每一步的环境反馈，更新空间记忆"""
        action_lower = action.lower().strip()
        
        # 检测 go to 动作
        if action_lower.startswith('go to '):
            location = action_lower.replace('go to ', '')
            # 从 obs 提取看到的物体
            objects_seen = self._extract_objects_from_obs(obs)
            self.memory.record_visit(location, objects_seen, obs)
    
    def _extract_objects_from_obs(self, obs: str) -> List[str]:
        """从观测文本中提取物体名"""
        objects = []
        # 匹配 "a/an X N" 或 "X N" 模式
        patterns = [
            r'a\s+([a-zA-Z]+)\s+\d+',      # a bed 1, a book 1
            r'an\s+([a-zA-Z]+)\s+\d+',     # an apple 1
            r'the\s+([a-zA-Z]+)\s+\d+',    # the desklamp 1
        ]
        for pattern in patterns:
            matches = re.findall(pattern, obs)
            objects.extend(matches)
        return objects
    
    def select_explore_target(self, available_go_cmds: List[str],
                               history: List[str]) -> Optional[str]:
        """
        选择探索目标位置
        
        优先级：
          1. 目标位置语义匹配（如 task 说了 countertop → 优先去）
          2. 目标工具语义匹配（如 task 说了 desklamp → 优先去有 lamp 的位置）
          3. 物体→位置知识库引导（如找 knife → 优先去 countertop/drawer）
          4. 未访问位置卦象引导（如找兑卦物体 → 优先去坤卦区域）
          5. 简单未访问优先
        """
        if not available_go_cmds:
            return None
        
        # 循环检测：最后K个go to动作的目标，检查是否有高频重复
        recent_targets = []
        for h in reversed(history[-8:]):
            if h.lower().startswith('go to '):
                recent_targets.append(h.lower().replace('go to ', '').strip())
        
        def _not_recent_loop(cmd: str) -> bool:
            """检查命令目标是否在最近历史中过度出现"""
            target = cmd.lower().replace('go to ', '').strip()
            # 如果最近2步同一目标 → 可能是死循环
            if len(recent_targets) >= 2 and recent_targets[0] == target and recent_targets[1] == target:
                return False
            # 如果目标在最近8步中出现了4次以上 → 过度访问
            if recent_targets.count(target) >= 4:
                return False
            return True
        
        # 0. 优先匹配目标工具位置
        if self.target_tools:
            for tool_name, _ in self.target_tools:
                tool_hints = {
                    'desklamp': ['desk', 'shelf'],
                    'floorlamp': ['floor', 'shelf'],
                }
                hints = tool_hints.get(tool_name, [])
                tool_matched = []
                for cmd in available_go_cmds:
                    if any(h in cmd.lower() for h in hints):
                        tool_matched.append(cmd)
                if tool_matched:
                    visited = set(self.memory.visited.keys())
                    for cmd in tool_matched:
                        norm = self.memory._normalize_name(cmd.replace('go to ', ''))
                        if norm not in visited and _not_recent_loop(cmd):
                            return cmd
                    for cmd in tool_matched:
                        if _not_recent_loop(cmd):
                            return cmd
        
        # 1. 语义匹配的目标位置
        target_loc_names = [tl[0] for tl in self.target_locations]
        loc_matched = []
        for cmd in available_go_cmds:
            cmd_lower = cmd.lower().replace('go to ', '')
            for tln in target_loc_names:
                if tln in cmd_lower and cmd not in loc_matched:
                    loc_matched.append(cmd)
        if loc_matched:
            visited = set(self.memory.visited.keys())
            for cmd in loc_matched:
                norm = self.memory._normalize_name(cmd.replace('go to ', ''))
                if norm not in visited and _not_recent_loop(cmd):
                    return cmd
            for cmd in loc_matched:
                if _not_recent_loop(cmd):
                    return cmd
        
        # 2. 物体→位置知识库引导
        if self.target_objects and self.llm_guide:
            hints = self.llm_guide.get_object_hints(
                self.task_desc, self.target_objects[0][0])
            hint_matched = []
            for hint in hints:
                for cmd in available_go_cmds:
                    if hint in cmd.lower() and cmd not in hint_matched:
                        hint_matched.append(cmd)
            if hint_matched:
                visited = set(self.memory.visited.keys())
                for cmd in hint_matched:
                    norm = self.memory._normalize_name(cmd.replace('go to ', ''))
                    if norm not in visited and _not_recent_loop(cmd):
                        return cmd
                for cmd in hint_matched:
                    if _not_recent_loop(cmd):
                        return cmd
        
        # 3. 卦象引导的未访问位置
        target_bagua = self.target_objects[0][1] if self.target_objects else ''
        preferred = self.memory.get_unvisited_preferred(
            available_go_cmds, target_bagua)
        if preferred:
            for cmd in preferred:
                if _not_recent_loop(cmd):
                    return cmd
        
        # 4. 简单未访问优先
        visited = set(self.memory.visited.keys())
        for cmd in available_go_cmds:
            norm = self.memory._normalize_name(cmd.replace('go to ', ''))
            if norm not in visited and _not_recent_loop(cmd):
                return cmd
        
        # 5. 兜底：已全部访问但仍在探索 → 检测死循环
        visited = set(self.memory.visited.keys())
        all_visited = all(
            self.memory._normalize_name(c.replace('go to ', '')) in visited
            for c in available_go_cmds
        )
        if all_visited:
            # 所有位置都访问过了 → 尝试选择访问次数最少的
            best = min(available_go_cmds, key=lambda c: self.memory.visited.get(
                self.memory._normalize_name(c.replace('go to ', '')), {}).get('visit_count', 0))
            # 如果该目标在最近2步中已经出现过 → 选下一个
            target = best.lower().replace('go to ', '').strip()
            if len(recent_targets) >= 1 and recent_targets[0] == target:
                # 选另一个（如果只剩1个候选就用它）
                for cmd in available_go_cmds:
                    if cmd != best:
                        return cmd
            return best
        
        # 有未访问但被过滤 → 返回 None
        return None
    
    def should_continue_exploring(self, current_phase: int, 
                                   subgoals: List[List[str]]) -> bool:
        """
        判断是否应继续探索（而非执行当前 subgoal）
        
        当 need_go_to 且还没找到目标物体时，继续探索
        """
        if current_phase >= len(subgoals):
            return False
        
        target_actions = subgoals[current_phase]
        
        # 如果当前是 go to 阶段且还没找到目标位置
        if target_actions == ['go to'] and self.target_locations:
            # 检查已经到过的位置中是否有目标位置
            found_target = False
            for loc_name, _ in self.target_locations:
                for visited_loc in self.memory.visited:
                    if loc_name in visited_loc:
                        found_target = True
                        break
            if not found_target:
                return True  # 还没找到 → 继续探索
        
        return False
    
    def get_spatial_context(self) -> Dict:
        """获取空间上下文（供 select_action 使用）"""
        return {
            'visited_locations': list(self.memory.visited.keys()),
            'current_location': self.memory.current_location,
            'target_objects': [(n, g) for n, g in self.target_objects],
            'target_locations': [(n, g) for n, g in self.target_locations],
            'exploration_priority': self.exploration_priority[:5],
            'visited_count': len(self.memory.visited),
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    from llm_semantic_guide import LLMSemanticGuide
    
    guide = LLMSemanticGuide()
    explorer = SpatialExplorationLayer(llm_guide=guide)
    
    # 测试任务
    explorer.reset("Put a clean plate on the counter.", 
                   "pick_clean_then_place_in_recep")
    
    print("=== Spatial Explorer Test ===")
    print(f"Target Objects: {explorer.target_objects}")
    print(f"Target Locations: {explorer.target_locations}")
    print(f"Exploration Priority: {explorer.exploration_priority[:5]}")
    
    # 模拟环境交互
    print("\n--- Simulating exploration ---")
    
    # Step 1: go to bed
    explorer.record_step("go to bed 1", 
                         "You arrive at bed 1. On the bed 1, you see a book 1, a cellphone 1, a pillow 1.")
    print(f"After visiting bed: {explorer.memory.visited}")
    
    # Step 2: go to desk
    explorer.record_step("go to desk 1",
                         "You arrive at desk 1. On the desk 1, you see a creditcard 1, a laptop 1, a pencil 1.")
    print(f"After visiting desk: {list(explorer.memory.visited.keys())}")
    
    # Select next target
    available = ["go to countertop 1", "go to drawer 1", "go to shelf 1"]
    next_target = explorer.select_explore_target(available, [])
    print(f"\nAvailable go targets: {available}")
    print(f"Explorer selects: {next_target}")
    
    # Test with known object search
    print("\n--- Find knife on desk ---")
    explorer.reset("Look at a mug in lamp light.", "look_at_obj_in_light")
    
    available = ["go to bed 1", "go to desk 1", "go to shelf 1"]
    print(f"Target objects: {explorer.target_objects}")
    print(f"Target bagua: {explorer.target_objects[0][1] if explorer.target_objects else 'N/A'}")
    next_target = explorer.select_explore_target(available, [])
    print(f"Explorer selects: {next_target}")
