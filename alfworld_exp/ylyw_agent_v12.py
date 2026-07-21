#!/usr/bin/env python3
"""
YLYW Agent V12 — YLYW 零样本任务决策

用YLYW六爻推理替代硬编码TASK_PLANS，实现真正的零样本任务规划。

核心变化：
- 删除了 TASK_PLANS / TASK_TOOLS / ALL_OBJECTS 字典
- 删除了 phase 阶段推进机制
- 用 ylyw_task_planner.YLYWTaskPlanner 每步对所有cmd六爻评分选优
- 保留知几/知耻/爻调/场景记忆经验，作为YLYW评分的子因子
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from ylyw_task_planner import YLYWTaskPlanner

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


class YLYWAgentV12:
    """
    YLYW Agent V12: 用YLYW六爻推理替代硬编码TASK_PLANS，实现零样本任务决策。
    
    核心变化：
    - 消除了硬件编码的计划模板，每步用六爻评估所有可选命令
    - YLYWTaskPlanner 在运行中学习不同动作的适宜性
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

        # V10知耻学习: 当前局内否定记忆 — 去过但没找到目标的位置类型
        self._explored_no_target: Dict[str, Set[str]] = {}  # {loc_base: set(visited_locs)}

        # V10新增：知耻学习状态
        self._zhichi = None
        self._prioritize_open = False
        self._wrong_take_exclusions = set()

        # V11新增：场景记忆
        self._scene_memory = None  # 外部注入
        self._current_scene = ''

        # V11新增：知几V11引擎（含六爻模板+行为模式学习）
        self._zhiji_v11 = None  # 外部注入（与self._zhiji并列，优先使用）

        # V12新增：YLYW任务规划器（替代TASK_PLANS硬编码）
        self._planner = YLYWTaskPlanner(verbose=verbose)
        self._held_object = None  # 当前手持物体（用于planner上下文）
        self._task_planner_started = False

        # 爻参数在线微调
        self._yao_tuner = None  # 外部注入

        self.history: List[str] = []
        self.step_count = 0

    def reset(self, task_desc: str, task_type: str, pddl_params: Dict = None,
              initial_admissible: List[str] = None, scene: str = ''):
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
        self._held_object = None  # V12: 追踪手持物体
        self._task_planner_started = True  # V12: planner就绪

        # V6新增重置
        self.object_memory = {}
        self.opened_containers = set()
        self.current_location = ''
        self.put_attempts = 0
        self.tried_recep_locs = set()
        self._pending_open = False

        # V10重置知耻学习状态
        self._prioritize_open = False
        self._wrong_take_exclusions = set()
        self._explored_no_target = {}  # 当前局内否定记忆清空

        # V11：设置场景记忆
        self._current_scene = scene
        if self._scene_memory and scene:
            self._scene_memory.set_scene(scene)

        # 重置爻参数在线微调状态
        if hasattr(self, '_yao_tuner') and self._yao_tuner is not None:
            self._yao_tuner.reset_online_state()

        # V7: 从task_desc纯NL解析（不使用pddl_params）
        from task_desc_parser import parse_task_desc
        parsed = parse_task_desc(task_desc)
        
        # 如果不用oracle type，用NL解析的type
        if not self.use_oracle_type:
            self.task_type = parsed['task_type']
            task_type = parsed['task_type']
        
        # V12: 不再使用TASK_PLANS硬编码计划
        # 计划由YLYWTaskPlanner每步动态生成
        self.plan = ['dynamic']  # 占位，表示使用动态规划

        # V9: 目标从NL解析获取 + 知几学习校准
        self.target_objects = parsed['target_objects'] if parsed['target_objects'] else []
        self.target_receps = parsed['target_receps'] if parsed['target_receps'] else []
        
        # V9知几学习：用积累的同义词经验扩展目标物体
        if hasattr(self, '_zhiji') and self._zhiji is not None:
            self.target_objects = self._zhiji.get_expanded_objects(self.target_objects)

        # V10知耻学习：用失败经验排除错拿物体
        if hasattr(self, '_zhichi') and self._zhichi is not None:
            exclusions = self._zhichi.get_wrong_take_exclusions(self.target_objects)
            if exclusions and self.verbose:
                print(f"    [知耻:L1] 排除已知错拿: {exclusions}")
            
            # L4: 根据失败经验判断是否优先open
            self._prioritize_open = self._zhichi.should_prioritize_open(task_type)
            
            # L5: 获取失败提示
            hint = self._zhichi.get_failure_hint(task_type, '')
            if hint and self.verbose:
                print(f"    [知耻:L5] 失败提示: {hint}")

        # V12: 从task_desc启发式推断目标工具（替代之前的TASK_TOOLS硬编码）
        self.target_tools = []
        desc_lower = task_desc.lower()
        if any(kw in desc_lower for kw in ['clean', 'wash', 'fill', 'rinse', 'wet', 'sink']):
            self.target_tools.append('sinkbasin')
        if any(kw in desc_lower for kw in ['heat', 'warm', 'hot', 'microwave', 'cook']):
            self.target_tools.append('microwave')
        if any(kw in desc_lower for kw in ['cool', 'chill', 'cold', 'fridge', 'refrigerat']):
            self.target_tools.append('fridge')
        if any(kw in desc_lower for kw in ['light', 'lamp', 'look at', 'examine']):
            self.target_tools.append('desklamp')
            self.target_tools.append('floorlamp')

        # V11：从场景记忆获取已知物体位置
        if hasattr(self, '_scene_memory') and self._scene_memory is not None:
            if self._current_scene:
                scene_objects = self._scene_memory.get_all_object_memory()
                for obj, loc in scene_objects.items():
                    if obj not in self.object_memory:
                        self.object_memory[obj] = loc
                if self.verbose and scene_objects:
                    print(f"    [场景记忆] 已知{len(scene_objects)}个物体位置")

        # 补充从 task_desc 提取（兜底）
        if not self.target_objects:
            self._extract_targets_from_desc()

        # 收集所有可达位置
        if initial_admissible:
            self.all_locations = [cmd.replace('go to ', '')
                                  for cmd in initial_admissible
                                  if cmd.startswith('go to ')]

        if self.verbose:
            print(f"  Agent V12 reset (YLYW零样本):")
            print(f"    Target objects: {self.target_objects}")
            print(f"    Target receps:  {self.target_receps}")
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
                        if rec_base not in (self.target_tools or []):
                            self.target_receps.append(rec_base)
                    break

    def act(self, obs: str, admissible_commands: List[str]) -> str:
        """V12: 用YLYW任务规划器替代硬编码阶段计划"""
        self.step_count += 1

        # 记忆观测中的物体
        self._memorize_objects(obs, admissible_commands)

        # 使用YLYW规划器选择动作
        best_cmd, best_score, reasoning = self._planner.plan(
            task_desc=self.task_desc,
            task_type=self.task_type,
            admissible=admissible_commands,
            current_holding=self._held_object,
            visited_locs=self.visited,
            known_targets=self.target_objects,
            opened_containers=self.opened_containers,
            step_count=self.step_count
        )

        if self.verbose:
            goal_hint = f"(持:{self._held_object or '空手'})"
            print(f"    [YLYW] {goal_hint} 选:{best_cmd} 分:{best_score:.2f}")

        return best_cmd

    def _memorize_objects(self, obs: str, cmds: List[str]):
        """V6: 从观测和take命令中记忆物体位置"""
        if not self.current_location:
            return

        # 从take命令提取可拿物体
        has_target_here = False
        for cmd in cmds:
            if cmd.startswith('take '):
                m = re.match(r'take (.+?) from .+', cmd)
                if m:
                    obj_name = m.group(1).strip()
                    self.object_memory[obj_name] = self.current_location
                    # V11: 同步到场景记忆
                    if hasattr(self, '_scene_memory') and self._scene_memory is not None:
                        self._scene_memory.observe_object_at(obj_name, self.current_location)
                    # 检查是否是目标物体
                    obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
                    if obj_base in self.target_objects:
                        has_target_here = True

        # V11: 记录位置到场景记忆（但不自动提取obs中的物体——避免噪声）
        if hasattr(self, '_scene_memory') and self._scene_memory is not None:
            self._scene_memory.observe_location(self.current_location)

        # V10知耻: 当前局内否定记忆
        # 如果当前位置没有目标物体的take命令，记录为"去过但没找到"
        if not has_target_here and self.phase < len(self.plan) and \
           self.plan[self.phase].startswith('find_object'):
            loc_base = re.sub(r'\s*\d+$', '', self.current_location.lower())
            if loc_base not in self._explored_no_target:
                self._explored_no_target[loc_base] = set()
            self._explored_no_target[loc_base].add(self.current_location)

    def _maybe_open(self, cmds: List[str], current_goal: str, obs: str) -> Optional[str]:
        """V6/V10: 检查是否需要open当前位置的容器"""
        open_cmds = [c for c in cmds if c.startswith('open ')]
        if not open_cmds:
            return None

        # V10: 知耻L4 — 失败经验建议优先open时,扩大open范围
        should_open = (current_goal.startswith('find_') or current_goal.startswith('put_'))
        if hasattr(self, '_prioritize_open') and self._prioritize_open:
            should_open = True  # 任何阶段都尝试open

        if not should_open:
            return None

        for cmd in open_cmds:
            container = cmd.replace('open ', '').strip()
            if container not in self.opened_containers:
                if self.verbose:
                    print(f"    [V10:open] {cmd}")
                return cmd

        return None

    def update(self, action: str, obs: str, info: Dict):
        """更新状态 + YLYW规划器反馈 + 爻参数在线微调"""
        self.history.append(action)
        success = info.get('action_success', True)

        # V12: 给YLYW规划器反馈
        self._planner.observe_step(action, success, self.task_type, self.step_count)

        # V12: 跟踪手持物体
        if action.startswith('take ') and success:
            m = re.match(r'take (.+?) from .+', action)
            if m:
                self._held_object = m.group(1).strip()
        if (action.startswith('put ') or action.startswith('move ')) and success:
            self._held_object = None

        # 跟踪位置
        if action.startswith('go to ') and success:
            loc = action[6:].strip()
            self.explored.add(loc)
            self.current_location = loc

        # V6: 跟踪open
        if action.startswith('open ') and success:
            container = action[5:].strip()
            self.opened_containers.add(container)
            # V11: 同步到场景记忆
            if hasattr(self, '_scene_memory') and self._scene_memory is not None:
                self._scene_memory.observe_container_open(container, self.current_location)

        # ====== 爻参数实时微调 ======
        has_yao = hasattr(self, '_yao_tuner') and self._yao_tuner is not None

        # 抓持爻（Take）反馈
        if action.startswith('take '):
            m = re.match(r'take (.+?) from (.+)', action)
            if m:
                taken = m.group(1).strip()
                taken_loc = m.group(2).strip()
                taken_base = re.sub(r'\s*\d+$', '', taken.lower())
                loc_base = re.sub(r'\s*\d+$', '', taken_loc.lower())
                
                if success:
                    self.holding = taken
                    # 抓持成功：正强化爻参数
                    if has_yao:
                        self._yao_tuner.observe_take_success(taken_base, loc_base)
                # 抓持失败（take但failed）：标记该位置该物体不可拿（负反馈）
                elif has_yao:
                    self._yao_tuner.observe_take_miss(taken_base, loc_base)
        
        # 抓持爻（Take）—— 如果目标物体在当前admissible中但没出现take命令（去了但没有）
        # 这个在_memorize_objects中已经处理，这里不需要重复

        # 释放爻（Put/Move）反馈
        if (action.startswith('put ') or action.startswith('move ')):
            m = re.match(r'(?:put|move) (.+?) (?:in|on|to) (.+)', action.lower())
            if m and self.holding:
                obj_name = m.group(1).strip()
                rec_full = m.group(2).strip()
                obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
                rec_base = re.sub(r'\s*\d+$', '', rec_full.lower())
                
                if success:
                    self.holding = None
                    # 释放成功：正强化爻参数（这个物体放这个容器是对的）
                    if has_yao:
                        self._yao_tuner.observe_release_success(obj_base, rec_base, rec_full)
                else:
                    # 释放失败：负强化爻参数（这个物体不放这个容器）
                    if has_yao:
                        self._yao_tuner.observe_release_fail(obj_base, rec_base, rec_full)
                    
                    # 同时记录到知耻：知耻的错拿排除也需要考虑释放失败
                    # 但知耻是跨局学习，这里只记录到本地状态
                    if has_yao and self.verbose:
                        # 释放失败时，当前局内尝试另一个容器
                        pass
            elif success:
                # put/move success 但没有解析出物体和容器（格式不标准时）
                self.holding = None

        # 遗留跟踪：非爻参数格式的take
        if action.startswith('take ') and success and ' from ' not in action:
            self.holding = action[5:].strip()

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
            elif goal in ('find_recep', 'find_recep_2', 'find_final'):
                score += self._object_location_prior(self.target_receps, loc_base)

            # 知几位置先验校准（跨局统计叠加，覆盖硬编码先验无法覆盖的物体和容器）
            if hasattr(self, '_zhiji') and self._zhiji is not None:
                if goal in ('find_object', 'find_object_2'):
                    for obj in self.target_objects:
                        boost = self._zhiji.get_location_prior_boost(obj, loc_base)
                        if boost > 0:
                            score += boost
                elif goal in ('find_recep', 'find_recep_2', 'find_final'):
                    for rec in self.target_receps:
                        boost = self._zhiji.get_location_prior_boost(rec, loc_base)
                        if boost > 0:
                            score += boost

            # V10知耻学习L2: 否定先验惩罚（跨局经验）
            if hasattr(self, '_zhichi') and self._zhichi is not None:
                if goal in ('find_object', 'find_object_2'):
                    for obj in self.target_objects:
                        penalty = self._zhichi.get_location_penalty(obj, loc_base)
                        score += penalty  # penalty是负值

            # V10知耻: 当前局内否定记忆（去过但没找到目标，强惩罚）
            if goal in ('find_object', 'find_object_2'):
                if loc_base in self._explored_no_target:
                    visited_same_type = self._explored_no_target[loc_base]
                    if loc in visited_same_type:
                        # 这个具体位置已经去过且没有目标 → 强惩罚
                        score -= 8.0
                    elif len(visited_same_type) >= 2:
                        # 同类型的其他位置已经去过2+个都没找到 → 降低优先级
                        score -= 3.0

            # V11: 场景记忆评分（关闭——ALFWorld每个场景不同，场景记忆基本无效）
            # 场景记忆仅用于记录，不用于评分决策

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
            'cloth': {'countertop': 2, 'bathtubbasin': 2, 'sinkbasin': 1, 'handtowelholder': 1, 'cabinet': 1, 'drawer': 1, 'shelf': 1},
            'rag': {'countertop': 2, 'bathtubbasin': 2, 'sinkbasin': 1, 'cabinet': 1, 'drawer': 1, 'shelf': 1},
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
        """在admissible_commands中找take目标物体的命令（V10: 含知耻排除）"""
        take_cmds = [c for c in cmds if c.startswith('take ')]
        if not take_cmds:
            return None

        # V10: 获取知耻排除集
        exclusions = set()
        if hasattr(self, '_zhichi') and self._zhichi is not None:
            exclusions = self._zhichi.get_wrong_take_exclusions(self.target_objects)

        # 精确匹配目标物体
        for cmd in take_cmds:
            cmd_lower = cmd.lower()
            for obj in self.target_objects:
                # "take plate 2 from countertop 2" → 检查 "plate" 在其中
                if obj in cmd_lower:
                    # V10: 检查是否在排除列表中
                    m = re.match(r'take (.+?) from .+', cmd)
                    if m:
                        taken = re.sub(r'\s*\d+$', '', m.group(1).strip().lower())
                        if taken in exclusions:
                            if self.verbose:
                                print(f"    [知耻:L1] 跳过已知错拿: {taken}")
                            continue
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
        """放置物体 (V10+: 爻参数在线微调 + 容器遍历)"""
        holding_base = ''
        if self.holding:
            holding_base = re.sub(r'\s*\d+$', '', self.holding.lower())

        # ---- Step 1: 用爻参数找最优的 put/move 命令 ----
        # 如果有爻参数，用爻参数排序候选容器，优先选置信度高的
        use_yao = (hasattr(self, '_yao_tuner') and self._yao_tuner is not None
                   and holding_base)

        if use_yao:
            # 收集所有可用的 put/move 命令及其容器
            put_candidates = []
            for cmd in cmds:
                if cmd.startswith('move ') or cmd.startswith('put '):
                    m = re.match(r'(?:put|move) .+ (?:in|on|to) (.+)', cmd.lower())
                    if m:
                        rec_full = m.group(1).strip()
                        rec_base = re.sub(r'\s*\d+$', '', rec_full)
                        yao_score = self._yao_tuner.get_release_score(holding_base, rec_base)
                        
                        # 检查是否被释放爻排除（低于阈值则不选）
                        if self._yao_tuner.is_release_blocked(holding_base, rec_base):
                            if self.verbose:
                                print(f"    [爻调:排除] {holding_base}→{rec_base} 已被排除(score={yao_score:.1f})")
                            continue
                        
                        # 爻参数评分作为排序依据
                        put_candidates.append((yao_score, cmd, rec_base, rec_full))
            
            if put_candidates:
                # 按爻参数降序排列
                put_candidates.sort(key=lambda x: -x[0])
                if self.verbose:
                    print(f"    [爻调:put候选] holding={holding_base}")
                    for s, c, rb, rf in put_candidates[:3]:
                        print(f"      {s:5.1f} | {c}")
                return put_candidates[0][1]
        
        # ---- Step 2: 无爻参数或holding_base为空时的原始策略 ----
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

        # ---- Step 3: 尝试open容器 ----
        open_cmds = [c for c in cmds if c.startswith('open ')]
        if open_cmds:
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

        # ---- Step 4: 放置不可用 → 用爻参数选下一个容器 ----
        self.tried_recep_locs.add(self.current_location)
        self.put_attempts += 1

        if self.verbose:
            print(f"    [V6:put] put failed at {self.current_location}, trying next recep")

        # 用爻参数对未尝试的容器排序
        go_cmds = [c for c in cmds if c.startswith('go to ')]
        if use_yao and go_cmds:
            scored_gotos = []
            for cmd in go_cmds:
                loc = cmd[6:].strip()
                loc_base = re.sub(r'\s*\d+$', '', loc.lower())
                if loc not in self.tried_recep_locs:
                    for rec in self.target_receps:
                        if rec in loc_base or loc_base in rec:
                            yao_score = self._yao_tuner.get_release_score(holding_base, rec)
                            scored_gotos.append((yao_score, cmd))
                            break
            if scored_gotos:
                scored_gotos.sort(key=lambda x: -x[0])
                if self.verbose:
                    for s, c in scored_gotos[:3]:
                        print(f"      [爻调:go_to] {s:5.1f} | {c}")
                return scored_gotos[0][1]

        # 无爻参数或没有合适的：找下一个未尝试的同类容器
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

    # ------------------------------------------------------------------
    # V10: 知耻学习辅助接口
    # ------------------------------------------------------------------

    def get_trajectory_state(self) -> dict:
        """导出当前状态供知耻学习分析"""
        state = {
            'target_objects': list(self.target_objects),
            'target_receps': list(self.target_receps),
            'final_phase': self.phase,
            'plan': list(self.plan),
            'explored': list(self.explored),
            'object_memory': dict(self.object_memory),
            'holding': self.holding,
            'history': list(self.history),
        }
        # 添加爻参数统计
        if hasattr(self, '_yao_tuner') and self._yao_tuner is not None:
            state['yao_stats'] = self._yao_tuner.get_stats()
        return state
