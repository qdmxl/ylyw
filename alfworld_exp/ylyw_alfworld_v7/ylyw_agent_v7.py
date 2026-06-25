#!/usr/bin/env python3
"""
YLYW Agent V7 — V5基础上增加open/容器遍历/记忆能力

相比V5 (64.2%) 的改进：
1. open操作：对closed容器先open再look inside，解决找不到物体问题
2. put前自动open：目标容器closed时先open再put
3. 容器遍历：put失败时尝试同类型下一个容器
4. 物体记忆：记住探索中发现的物体位置
5. 步数利用优化：减少无效探索
"""

import re
from typing import List, Dict, Optional, Tuple, Set


# 任务类型 → 子目标序列
TASK_PLANS = {
    'look_at_obj_in_light': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_tool',       # 找到灯
        'use_tool',        # 开灯
    ],
    'pick_and_place_simple': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_recep',      # 找到目标容器
        'put_object',      # 放置
    ],
    'pick_clean_then_place_in_recep': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_tool',       # 找到sinkbasin
        'use_tool',        # clean
        'find_recep',      # 找到目标容器
        'put_object',      # 放置
    ],
    'pick_heat_then_place_in_recep': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_tool',       # 找到microwave
        'use_tool',        # heat
        'find_recep',      # 找到目标容器
        'put_object',      # 放置
    ],
    'pick_cool_then_place_in_recep': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_tool',       # 找到fridge
        'use_tool',        # cool
        'find_recep',      # 找到目标容器
        'put_object',      # 放置
    ],
    'pick_two_obj_and_place': [
        'find_object',     # 找到目标物体 #1
        'take_object',     # 拿起 #1
        'find_recep',      # 找到目标容器
        'put_object',      # 放置 #1
        'find_object_2',   # 找到目标物体 #2
        'take_object_2',   # 拿起 #2
        'find_recep_2',    # 找到目标容器
        'put_object_2',    # 放置 #2
    ],
    'pick_and_place_with_movable_recep': [
        'find_object',     # 找到目标物体
        'take_object',     # 拿起目标物体
        'find_recep',      # 找到目标容器（movable recep）
        'take_recep',      # 拿起容器
        'find_final',      # 找到最终位置
        'put_object',      # 放置
    ],
}

# 任务类型 → 对应的工具/设备
TASK_TOOLS = {
    'look_at_obj_in_light': ['desklamp', 'floorlamp'],
    'pick_clean_then_place_in_recep': ['sinkbasin'],
    'pick_heat_then_place_in_recep': ['microwave'],
    'pick_cool_then_place_in_recep': ['fridge'],
}

# 所有可能的物体名（用于从task_desc中提取）
ALL_OBJECTS = {
    'alarmclock': ['alarm clock', 'clock'],
    'apple': ['apple'],
    'baseballbat': ['baseball bat', 'bat'],
    'basketball': ['basketball'],
    'book': ['book'],
    'bottle': ['bottle'],
    'bowl': ['bowl'],
    'box': ['box'],
    'bread': ['bread'],
    'butterknife': ['butter knife', 'butterknife'],
    'candle': ['candle'],
    'cd': ['cd', 'disc'],
    'cellphone': ['cell phone', 'cellphone', 'phone'],
    'cloth': ['cloth'],
    'creditcard': ['credit card', 'creditcard'],
    'cup': ['cup'],
    'dishsponge': ['dish sponge', 'dishsponge', 'sponge'],
    'egg': ['egg'],
    'fork': ['fork'],
    'glassbottle': ['glass bottle', 'glassbottle'],
    'handtowel': ['hand towel', 'handtowel'],
    'kettle': ['kettle'],
    'keychain': ['keychain', 'key chain'],
    'knife': ['knife'],
    'ladle': ['ladle'],
    'laptop': ['laptop'],
    'lettuce': ['lettuce'],
    'mug': ['mug'],
    'newspaper': ['newspaper'],
    'pan': ['pan'],
    'papertowelroll': ['paper towel', 'papertowelroll'],
    'pen': ['pen'],
    'pencil': ['pencil'],
    'peppershaker': ['pepper shaker', 'peppershaker', 'pepper'],
    'pillow': ['pillow'],
    'plate': ['plate'],
    'plunger': ['plunger'],
    'pot': ['pot'],
    'potato': ['potato'],
    'remotecontrol': ['remote control', 'remotecontrol', 'remote'],
    'saltshaker': ['salt shaker', 'saltshaker', 'salt'],
    'scrubbrush': ['scrub brush', 'scrubbrush'],
    'soapbar': ['soap bar', 'soapbar', 'soap'],
    'soapbottle': ['soap bottle', 'soapbottle'],
    'spatula': ['spatula'],
    'spoon': ['spoon'],
    'spraybottle': ['spray bottle', 'spraybottle'],
    'statue': ['statue'],
    'teddybear': ['teddy bear', 'teddybear'],
    'tissuebox': ['tissue box', 'tissuebox'],
    'toiletpaper': ['toilet paper', 'toiletpaper'],
    'tomato': ['tomato'],
    'towel': ['towel'],
    'vase': ['vase'],
    'watch': ['watch'],
    'winebottle': ['wine bottle', 'winebottle'],
}

# 目标容器名
ALL_RECEPTACLES = {
    'bathtubbasin': ['bathtub', 'bathtubbasin'],
    'bed': ['bed'],
    'cabinet': ['cabinet'],
    'cart': ['cart'],
    'coffeemachine': ['coffee machine', 'coffeemachine'],
    'coffeetable': ['coffee table', 'coffeetable'],
    'countertop': ['counter', 'countertop'],
    'desk': ['desk'],
    'diningtable': ['dining table', 'diningtable'],
    'drawer': ['drawer'],
    'dresser': ['dresser'],
    'fridge': ['fridge', 'refrigerator'],
    'garbagecan': ['garbage can', 'garbagecan', 'trash can', 'trash', 'bin', 'garbage', 'trash bin'],
    'laundryhamper': ['laundry hamper', 'hamper'],
    'microwave': ['microwave'],
    'ottoman': ['ottoman'],
    'safe': ['safe'],
    'shelf': ['shelf'],
    'sidetable': ['side table', 'sidetable', 'nightstand'],
    'sinkbasin': ['sink', 'sinkbasin'],
    'sofa': ['sofa', 'couch'],
    'stoveburner': ['stove', 'stoveburner'],
    'toilet': ['toilet'],
    'tvstand': ['tv stand', 'tvstand'],
}


class YLYWAgentV7:
    """
    YLYW Agent V6: V5 + open能力 + 容器遍历 + 物体记忆
    """

    def __init__(self, verbose: bool = False, use_oracle_type: bool = True):
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type

        # 每局状态
        self.task_type = ''
        self.task_desc = ''
        self.target_objects: List[str] = []   # e.g. ['plate', 'mug']
        self.target_receps: List[str] = []    # e.g. ['countertop', 'cabinet']
        self.target_tools: List[str] = []     # e.g. ['sinkbasin', 'desklamp']
        self.pddl_params: Dict = {}

        self.phase = 0
        self.plan: List[str] = []

        self.visited: Set[str] = set()       # 已访问位置
        self.explored: Set[str] = set()      # 已探索（go to过）的位置
        self.all_locations: List[str] = []   # 所有可达位置（from initial obs）
        self.holding: Optional[str] = None   # 当前手持物体

        # V6新增
        self.object_memory: Dict[str, str] = {}  # 物体名 → 位置 (e.g. 'plate 2' → 'countertop 2')
        self.opened_containers: Set[str] = set()  # 已打开的容器
        self.current_location: str = ''       # 当前所在位置
        self.put_attempts: int = 0            # put尝试次数
        self.tried_recep_locs: Set[str] = set()  # 已尝试放置的容器位置
        self._pending_open = False            # 等待open后查看

        self.history: List[str] = []
        self.step_count = 0

    def reset(self, task_desc: str, task_type: str, pddl_params: Dict = None,
              initial_admissible: List[str] = None):
        """开始新游戏"""
        self.task_desc = task_desc
        self.task_type = task_type
        self.pddl_params = pddl_params or {}
        self.phase = 0
        self.holding = None
        self.visited = set()
        self.explored = set()
        self.history = []
        self.step_count = 0

        # V6新增重置
        self.object_memory = {}
        self.opened_containers = set()
        self.current_location = ''
        self.put_attempts = 0
        self.tried_recep_locs = set()
        self._pending_open = False

        # V7: 从task_desc纯NL解析（不使用pddl_params）
        from task_desc_parser import parse_task_desc
        parsed = parse_task_desc(task_desc)
        
        # 如果不用oracle type，用NL解析的type
        if not self.use_oracle_type:
            self.task_type = parsed['task_type']
            task_type = parsed['task_type']
        
        # 设置计划
        self.plan = list(TASK_PLANS.get(task_type,
                         ['find_object', 'take_object', 'find_recep', 'put_object']))

        # V7: 目标从NL解析获取
        self.target_objects = parsed['target_objects'] if parsed['target_objects'] else []
        self.target_receps = parsed['target_receps'] if parsed['target_receps'] else []

        # 补充从 task_desc 提取（兜底）
        if not self.target_objects:
            self._extract_targets_from_desc()

        # 设置工具
        self.target_tools = list(TASK_TOOLS.get(task_type, []))

        # 收集所有可达位置
        if initial_admissible:
            self.all_locations = [cmd.replace('go to ', '')
                                  for cmd in initial_admissible
                                  if cmd.startswith('go to ')]

        if self.verbose:
            print(f"  Agent V6 reset:")
            print(f"    Target objects: {self.target_objects}")
            print(f"    Target receps:  {self.target_receps}")
            print(f"    Target tools:   {self.target_tools}")
            print(f"    Locations:      {self.all_locations[:10]}...")
            print(f"    Plan: {self.plan}")

    def _extract_targets_from_pddl(self):
        """V7: 不再使用PDDL参数，从task_desc自然语言解析目标"""
        # 使用task_desc_parser进行纯NL解析
        from task_desc_parser import parse_task_desc
        parsed = parse_task_desc(self.task_desc)
        
        # 解析出的目标物体和容器
        if parsed['target_objects']:
            self.target_objects = parsed['target_objects']
        if parsed['target_receps']:
            self.target_receps = parsed['target_receps']
        
        # 如果NL解析出的task_type与oracle不同，以NL为准（去掉oracle依赖）
        if not self.use_oracle_type:
            self.task_type = parsed['task_type']

    def _extract_targets_from_desc(self):
        """从英文task_desc中提取目标物体和容器"""
        desc_lower = self.task_desc.lower()

        # 提取物体
        for obj_base, aliases in ALL_OBJECTS.items():
            for alias in aliases:
                if alias in desc_lower:
                    if obj_base not in self.target_objects:
                        self.target_objects.append(obj_base)
                    break

        # 提取容器
        for rec_base, aliases in ALL_RECEPTACLES.items():
            for alias in aliases:
                if alias in desc_lower:
                    if rec_base not in self.target_receps:
                        # 排除工具类容器（它们不是目标容器）
                        if rec_base not in TASK_TOOLS.get(self.task_type, []):
                            self.target_receps.append(rec_base)
                    break

    def act(self, obs: str, admissible_commands: List[str]) -> str:
        """选择下一步动作"""
        self.step_count += 1

        # V6: 记忆观测中的物体
        self._memorize_objects(obs, admissible_commands)

        if self.phase >= len(self.plan):
            # 计划完成但没赢 → 尝试继续探索
            return self._explore(admissible_commands)

        current_goal = self.plan[self.phase]

        # V6: 如果到达了closed容器，优先open
        open_action = self._maybe_open(admissible_commands, current_goal, obs)
        if open_action:
            return open_action

        # 先检查是否有直接可用的高价值动作
        action = self._check_opportunistic(admissible_commands, current_goal)
        if action:
            if self.verbose:
                print(f"    [opportunistic] {action}")
            return action

        # 根据当前计划阶段选择动作
        if current_goal.startswith('find_'):
            action = self._act_find(admissible_commands, current_goal, obs)
        elif current_goal.startswith('take_'):
            action = self._act_take(admissible_commands, current_goal, obs)
        elif current_goal == 'use_tool':
            action = self._act_use_tool(admissible_commands, obs)
        elif current_goal.startswith('put_'):
            action = self._act_put(admissible_commands, obs)
        else:
            action = self._explore(admissible_commands)

        return action

    def _memorize_objects(self, obs: str, cmds: List[str]):
        """V6: 从观测和take命令中记忆物体位置"""
        if not self.current_location:
            return
        # 从take命令提取可拿物体
        for cmd in cmds:
            if cmd.startswith('take '):
                m = re.match(r'take (.+?) from .+', cmd)
                if m:
                    obj_name = m.group(1).strip()
                    self.object_memory[obj_name] = self.current_location

    def _maybe_open(self, cmds: List[str], current_goal: str, obs: str) -> Optional[str]:
        """V6: 检查是否需要open当前位置的容器"""
        # 如果admissible中有open命令，且当前位置还没open过
        open_cmds = [c for c in cmds if c.startswith('open ')]
        if not open_cmds:
            return None

        # 只在find/put阶段open
        if not (current_goal.startswith('find_') or current_goal.startswith('put_')):
            return None

        # 检查这个容器是否已经open过
        for cmd in open_cmds:
            container = cmd.replace('open ', '').strip()
            if container not in self.opened_containers:
                if self.verbose:
                    print(f"    [V6:open] {cmd}")
                return cmd

        return None

    def update(self, action: str, obs: str, info: Dict):
        """更新状态"""
        self.history.append(action)
        success = info.get('action_success', True)

        # 跟踪位置
        if action.startswith('go to ') and success:
            loc = action[6:].strip()
            self.explored.add(loc)
            self.current_location = loc

        # V6: 跟踪open
        if action.startswith('open ') and success:
            container = action[5:].strip()
            self.opened_containers.add(container)

        # 跟踪手持物品
        if action.startswith('take ') and success:
            # "take plate 2 from countertop 2" → "plate 2"
            m = re.match(r'take (.+?) from .+', action)
            if m:
                self.holding = m.group(1)
            else:
                self.holding = action[5:].strip()

        if (action.startswith('put ') or action.startswith('move ')) and success:
            self.holding = None

        # 自动阶段推进
        self._auto_advance(action, obs, info)

    def _auto_advance(self, action: str, obs: str, info: Dict):
        """基于动作结果自动推进阶段"""
        if self.phase >= len(self.plan):
            return

        current_goal = self.plan[self.phase]
        success = info.get('action_success', True)

        if not success:
            return

        if current_goal.startswith('find_'):
            # find 阶段：到达目标位置就推进
            if action.startswith('go to '):
                loc = action[6:].strip().lower()
                loc_base = re.sub(r'\s*\d+$', '', loc)
                obs_lower = obs.lower()

                if current_goal in ('find_object', 'find_object_2'):
                    # 检查 obs 中是否提到了目标物体
                    for obj in self.target_objects:
                        if obj in obs_lower:
                            self.phase += 1
                            if self.verbose:
                                print(f"    [advance] found {obj} → phase {self.phase}: {self._current_goal()}")
                            return

                elif current_goal == 'find_tool':
                    # 工具位置：只要到达就推进（sinkbasin/fridge/microwave是固定位置）
                    for tool in self.target_tools:
                        if tool in loc_base or loc_base in tool:
                            self.phase += 1
                            if self.verbose:
                                print(f"    [advance] at tool {tool} → phase {self.phase}: {self._current_goal()}")
                            return

                elif current_goal in ('find_recep', 'find_recep_2', 'find_final'):
                    # 到达目标容器就推进
                    for rec in self.target_receps:
                        if loc_base == rec or rec in loc_base or loc_base in rec:
                            self.phase += 1
                            if self.verbose:
                                print(f"    [advance] at recep {rec} → phase {self.phase}: {self._current_goal()}")
                            return

        elif current_goal.startswith('take_'):
            if action.startswith('take ') and success:
                self.phase += 1
                if self.verbose:
                    print(f"    [advance] took → phase {self.phase}: {self._current_goal()}")

        elif current_goal == 'use_tool':
            if any(action.startswith(p) for p in ('clean ', 'heat ', 'cool ', 'use ')) and success:
                self.phase += 1
                if self.verbose:
                    print(f"    [advance] used tool → phase {self.phase}: {self._current_goal()}")

        elif current_goal.startswith('put_'):
            if (action.startswith('put ') or action.startswith('move ')) and success:
                self.phase += 1
                if self.verbose:
                    print(f"    [advance] placed → phase {self.phase}: {self._current_goal()}")

    def _current_goal(self) -> str:
        if self.phase < len(self.plan):
            return self.plan[self.phase]
        return 'done'

    # ------------------------------------------------------------------
    # 机会主义检查：如果admissible_commands中有高价值动作直接执行
    # ------------------------------------------------------------------

    def _check_opportunistic(self, cmds: List[str], current_goal: str) -> Optional[str]:
        """检查是否有可以直接执行的高价值动作"""

        # 如果当前目标是 use_tool，且 admissible 中有 clean/heat/cool/use
        if current_goal == 'use_tool':
            for cmd in cmds:
                if self.task_type == 'pick_clean_then_place_in_recep' and cmd.startswith('clean '):
                    return cmd
                if self.task_type == 'pick_heat_then_place_in_recep' and cmd.startswith('heat '):
                    return cmd
                if self.task_type == 'pick_cool_then_place_in_recep' and cmd.startswith('cool '):
                    return cmd
                if self.task_type == 'look_at_obj_in_light' and cmd.startswith('use '):
                    return cmd

        # 如果当前目标是 put，且 admissible 中有 put/move 到目标容器
        if current_goal.startswith('put_'):
            for cmd in cmds:
                if cmd.startswith('move ') or cmd.startswith('put '):
                    # 检查是否是目标容器
                    for rec in self.target_receps:
                        if rec in cmd.lower():
                            return cmd

        # 如果当前目标是 take，且 admissible 中有 take 目标物体
        if current_goal.startswith('take_'):
            target_take = self._find_target_take(cmds)
            if target_take:
                return target_take

        return None

    # ------------------------------------------------------------------
    # find_* 动作：系统性探索
    # ------------------------------------------------------------------

    def _act_find(self, cmds: List[str], goal: str, obs: str) -> str:
        """找到目标物体/工具/容器"""

        # 确定要找什么
        if goal in ('find_object', 'find_object_2'):
            targets = self.target_objects
        elif goal == 'find_tool':
            targets = self.target_tools
        elif goal in ('find_recep', 'find_recep_2', 'find_final'):
            targets = self.target_receps
        else:
            targets = self.target_objects

        # V6: 检查记忆中是否已知目标物体位置
        if goal in ('find_object', 'find_object_2'):
            for obj_name, loc in self.object_memory.items():
                obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
                if obj_base in targets:
                    # 已知物体位置，直接去
                    go_cmd = f'go to {loc}'
                    if go_cmd in cmds and loc != self.current_location:
                        if self.verbose:
                            print(f"    [V6:memory] know {obj_name} at {loc}")
                        return go_cmd

        go_cmds = [c for c in cmds if c.startswith('go to ')]

        if not go_cmds:
            return self._fallback(cmds)

        # 优先级排序
        scored = []
        for cmd in go_cmds:
            loc = cmd[6:].strip().lower()
            loc_base = re.sub(r'\s*\d+$', '', loc)
            score = 0.0

            # 目标匹配
            for t in targets:
                if t == loc_base or t in loc_base or loc_base in t:
                    score += 10.0
                # 部分匹配 (e.g., "sink" matches "sinkbasin")
                elif t.startswith(loc_base) or loc_base.startswith(t):
                    score += 5.0

            # 未探索加分
            if loc not in self.explored:
                score += 2.0

            # 常识先验（YLYW风格）
            if goal in ('find_object', 'find_object_2'):
                score += self._object_location_prior(self.target_objects, loc_base)

            # 避免反复去同一个地方
            recent = self.history[-6:]
            if cmd in recent:
                score -= 3.0

            scored.append((score, cmd))

        scored.sort(key=lambda x: -x[0])

        if self.verbose and scored[:3]:
            print(f"    [find] goal={goal}, targets={targets}")
            for s, c in scored[:3]:
                print(f"      {s:5.1f} | {c}")

        return scored[0][1]

    def _object_location_prior(self, objects: List[str], location: str) -> float:
        """YLYW 常识先验：物体在什么位置的概率"""
        # 简化的先验知识
        priors = {
            # 厨房物体通常在countertop/cabinet/fridge
            'plate': {'countertop': 3, 'cabinet': 2, 'diningtable': 2, 'sinkbasin': 1, 'drawer': 1},
            'bowl': {'countertop': 3, 'cabinet': 2, 'diningtable': 2, 'sinkbasin': 1},
            'cup': {'countertop': 3, 'coffeemachine': 3, 'cabinet': 2, 'sinkbasin': 1},
            'mug': {'countertop': 3, 'coffeemachine': 3, 'desk': 2, 'shelf': 2, 'cabinet': 1, 'sinkbasin': 1},
            'apple': {'countertop': 3, 'fridge': 2, 'diningtable': 2, 'garbagecan': 1},
            'tomato': {'countertop': 3, 'fridge': 2, 'diningtable': 2},
            'potato': {'countertop': 3, 'fridge': 2, 'sinkbasin': 1},
            'egg': {'countertop': 3, 'fridge': 3},
            'bread': {'countertop': 3, 'diningtable': 2, 'toaster': 2},
            'lettuce': {'countertop': 3, 'fridge': 2},
            'knife': {'countertop': 3, 'drawer': 2},
            'fork': {'countertop': 2, 'drawer': 2, 'diningtable': 2},
            'spoon': {'countertop': 2, 'drawer': 2},
            'spatula': {'countertop': 3, 'drawer': 2},
            'pan': {'stoveburner': 3, 'countertop': 2},
            'pot': {'stoveburner': 3, 'countertop': 2},
            'kettle': {'stoveburner': 3, 'countertop': 2},
            # 卧室/客厅物体
            'book': {'desk': 3, 'shelf': 3, 'bed': 2, 'sidetable': 2, 'coffeetable': 2, 'dresser': 1},
            'pen': {'desk': 3, 'drawer': 2, 'shelf': 1},
            'pencil': {'desk': 3, 'drawer': 2, 'shelf': 1},
            'cd': {'desk': 2, 'shelf': 3, 'drawer': 2, 'dresser': 2, 'safe': 1},
            'alarmclock': {'desk': 3, 'sidetable': 3, 'shelf': 2, 'dresser': 2},
            'cellphone': {'desk': 3, 'sidetable': 2, 'bed': 1, 'dresser': 1},
            'laptop': {'desk': 3, 'bed': 2, 'coffeetable': 1},
            'remotecontrol': {'coffeetable': 3, 'sidetable': 2, 'sofa': 2, 'bed': 1, 'dresser': 1},
            'creditcard': {'desk': 2, 'sidetable': 2, 'drawer': 2, 'dresser': 2, 'shelf': 1},
            'keychain': {'desk': 2, 'sidetable': 2, 'drawer': 2, 'dresser': 2, 'shelf': 1, 'countertop': 1},
            'vase': {'shelf': 3, 'desk': 2, 'sidetable': 2, 'coffeetable': 2, 'dresser': 2, 'countertop': 2},
            'statue': {'shelf': 3, 'desk': 2, 'sidetable': 2, 'dresser': 2},
            'pillow': {'bed': 3, 'sofa': 3, 'chair': 1},
            'teddybear': {'bed': 3, 'sofa': 2},
            # 浴室物体
            'soapbar': {'countertop': 3, 'sinkbasin': 2, 'bathtubbasin': 2, 'toilet': 1},
            'towel': {'towelholder': 3, 'countertop': 2, 'bathtubbasin': 1},
            'handtowel': {'handtowelholder': 3, 'countertop': 2},
            'toiletpaper': {'toiletpaperhanger': 3, 'cabinet': 2, 'countertop': 1},
            'cloth': {'countertop': 2, 'bathtubbasin': 2},
            'spraybottle': {'countertop': 3, 'cabinet': 2, 'toilet': 1},
            'candle': {'countertop': 2, 'shelf': 2, 'bathtubbasin': 1},
            'tissuebox': {'sidetable': 2, 'desk': 2, 'shelf': 2, 'toilet': 1, 'countertop': 1},
            'newspaper': {'desk': 2, 'coffeetable': 2, 'sidetable': 2, 'sofa': 1, 'bed': 1},
            'winebottle': {'countertop': 3, 'fridge': 2, 'cabinet': 1},
            'bottle': {'countertop': 3, 'shelf': 2},
            'glassbottle': {'countertop': 3, 'shelf': 2, 'fridge': 1},
            'soapbottle': {'countertop': 3, 'sinkbasin': 2, 'cabinet': 1},
            'box': {'desk': 2, 'shelf': 2, 'dresser': 2, 'sidetable': 1},
            'watch': {'desk': 2, 'sidetable': 2, 'dresser': 2, 'shelf': 1},
            'baseballbat': {'bed': 2, 'desk': 1, 'dresser': 1},
            'basketball': {'bed': 1, 'desk': 1},
        }

        score = 0.0
        for obj in objects:
            obj_priors = priors.get(obj, {})
            for loc_key, prior_score in obj_priors.items():
                if loc_key in location or location in loc_key:
                    score += prior_score
        return score

    # ------------------------------------------------------------------
    # take_* 动作
    # ------------------------------------------------------------------

    def _act_take(self, cmds: List[str], goal: str, obs: str) -> str:
        """拿起目标物体"""
        # 优先从 admissible 中找 take 目标物体的命令
        target_take = self._find_target_take(cmds)
        if target_take:
            return target_take

        # 当前位置没有目标物体 → 回退到 find 阶段
        if self.verbose:
            print(f"    [take] no target object available, reverting to find")
        # 不推进phase，回到find模式探索
        self.phase -= 1  # 回到 find_object
        return self._act_find(cmds, self.plan[self.phase] if self.phase >= 0 else 'find_object', obs)

    def _find_target_take(self, cmds: List[str]) -> Optional[str]:
        """在admissible_commands中找take目标物体的命令"""
        take_cmds = [c for c in cmds if c.startswith('take ')]
        if not take_cmds:
            return None

        # 精确匹配目标物体
        for cmd in take_cmds:
            cmd_lower = cmd.lower()
            for obj in self.target_objects:
                # "take plate 2 from countertop 2" → 检查 "plate" 在其中
                if obj in cmd_lower:
                    return cmd

        return None

    # ------------------------------------------------------------------
    # use_tool 动作
    # ------------------------------------------------------------------

    def _act_use_tool(self, cmds: List[str], obs: str) -> str:
        """使用工具（clean/heat/cool/use）"""

        # 直接检查 admissible 中是否有对应操作
        if self.task_type == 'pick_clean_then_place_in_recep':
            for cmd in cmds:
                if cmd.startswith('clean '):
                    return cmd
        elif self.task_type == 'pick_heat_then_place_in_recep':
            for cmd in cmds:
                if cmd.startswith('heat '):
                    return cmd
        elif self.task_type == 'pick_cool_then_place_in_recep':
            for cmd in cmds:
                if cmd.startswith('cool '):
                    return cmd
        elif self.task_type == 'look_at_obj_in_light':
            for cmd in cmds:
                if cmd.startswith('use '):
                    return cmd

        # 工具操作不可用 → 需要先去工具位置
        # 回退到 find_tool
        if self.verbose:
            print(f"    [use_tool] tool action not available, reverting to find_tool")
        self.phase -= 1
        return self._act_find(cmds, 'find_tool', obs)

    # ------------------------------------------------------------------
    # put_* 动作
    # ------------------------------------------------------------------

    def _act_put(self, cmds: List[str], obs: str) -> str:
        """放置物体 (V6: 带open和容器遍历)"""
        # 检查 admissible 中是否有 put/move 到目标容器
        for cmd in cmds:
            if cmd.startswith('move ') or cmd.startswith('put '):
                for rec in self.target_receps:
                    if rec in cmd.lower():
                        return cmd

        # 也接受任何 put/move 命令（可能容器名变体）
        put_cmds = [c for c in cmds if c.startswith('move ') or c.startswith('put ')]
        if put_cmds:
            return put_cmds[0]

        # V6: 如果有open命令，可能需要先open才能放进去
        open_cmds = [c for c in cmds if c.startswith('open ')]
        if open_cmds:
            # open目标容器
            for cmd in open_cmds:
                container = cmd.replace('open ', '').strip()
                if container not in self.opened_containers:
                    for rec in self.target_receps:
                        if rec in container.lower():
                            if self.verbose:
                                print(f"    [V6:put] opening {container} before put")
                            return cmd
                    # 当前位置的容器也试试
                    if container not in self.opened_containers:
                        if self.verbose:
                            print(f"    [V6:put] opening {container}")
                        return cmd

        # V6: 放置不可用 → 去下一个同类容器
        self.tried_recep_locs.add(self.current_location)
        self.put_attempts += 1

        if self.verbose:
            print(f"    [V6:put] put failed at {self.current_location}, trying next recep")

        # 找下一个未尝试的同类容器
        go_cmds = [c for c in cmds if c.startswith('go to ')]
        for cmd in go_cmds:
            loc = cmd[6:].strip()
            loc_base = re.sub(r'\s*\d+$', '', loc.lower())
            for rec in self.target_receps:
                if rec in loc_base or loc_base in rec:
                    if loc not in self.tried_recep_locs:
                        return cmd

        # 所有同类容器都试过了 → 扩大搜索
        return self._explore(cmds)

    # ------------------------------------------------------------------
    # 探索 & fallback
    # ------------------------------------------------------------------

    def _explore(self, cmds: List[str]) -> str:
        """系统性探索未访问的位置"""
        go_cmds = [c for c in cmds if c.startswith('go to ')]
        if not go_cmds:
            return self._fallback(cmds)

        # 优先去未探索的位置
        unexplored = [c for c in go_cmds
                      if c[6:].strip() not in self.explored]
        if unexplored:
            return unexplored[0]

        # 全部探索过了 → 去最近没去过的
        not_recent = [c for c in go_cmds
                      if c not in self.history[-6:]]
        if not_recent:
            return not_recent[0]

        return go_cmds[0]

    def _fallback(self, cmds: List[str]) -> str:
        """最后的后备动作"""
        # 优先 look / inventory
        for c in cmds:
            if c == 'look':
                return c
        for c in cmds:
            if c == 'inventory':
                return c
        return cmds[0] if cmds else 'look'
