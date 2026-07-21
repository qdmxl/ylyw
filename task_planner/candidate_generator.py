#!/usr/bin/env python3
"""
候选动作生成器 — CandidateGenerator

从obs文本解析候选动作，完全替代admissible_commands。

职责：
  1. 从环境返回的obs文本中，解析出当前可执行的动作候选
  2. 根据意图(intent)从候选中选择最优动作
  3. 不依赖任何环境透传的结构化信息（admissible_commands / pddl_params）

解析策略：
  - go to位置：从初始obs的场景描述中提取所有家具+编号
  - take物体：从"On the X, you see a Y, ..." 中提取
  - open容器：从"a X (closed)"标记中提取
  - put/move：根据手持物体和当前位置的容器名称构造
  - use工具：根据任务类型和当前位置构造
"""

import os, sys, re
from typing import Dict, List, Tuple, Optional, Set

_self_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.dirname(_self_dir)
for d in (os.path.join(_proj_root, 'language'),
          os.path.join(_proj_root, 'api_docs'),
          os.path.join(_proj_root, 'experiment_phase1')):
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from hanzi_engine import BAGUA
except ImportError:
    pass


# 英文位置名（用于从obs提取）
LOCATION_NAMES = {
    'cabinet', 'countertop', 'drawer', 'shelf', 'desk', 'diningtable',
    'sidetable', 'coffeetable', 'bed', 'sofa', 'safe', 'garbagecan',
    'toilet', 'bathtubbasin', 'sinkbasin', 'microwave', 'fridge',
    'stoveburner', 'ottoman', 'tvstand', 'dresser', 'laundryhamper',
    'cart', 'coffeemachine', 'towelholder', 'handtowelholder',
    'toiletpaperhanger', 'floorlamp', 'desklamp', 'lamp',
}

# 物体名（用于从obs提取）
OBJECT_NAMES = {
    'plate', 'bowl', 'mug', 'cup', 'knife', 'fork', 'spoon',
    'pan', 'pot', 'spatula', 'apple', 'potato', 'tomato', 'lettuce',
    'bread', 'egg', 'soap', 'soapbar', 'towel', 'handtowel',
    'cloth', 'sponge', 'dishsponge', 'papertowelroll',
    'glassbottle', 'winebottle', 'bottle', 'kettle',
    'book', 'pen', 'pencil', 'keychain', 'watch', 'cellphone',
    'remotecontrol', 'laptop', 'pillow', 'teddybear',
    'vase', 'statue', 'cd', 'alarmclock', 'newspaper',
    'tissuebox', 'box', 'baseballbat', 'basketball',
    'creditcard', 'candle', 'peppershaker', 'saltshaker',
    'scrubbrush', 'plunger', 'spraybottle', 'soapbottle',
    'toiletpaper', 'butterknife', 'ladle',
}

# 容器名（可以open/close的）
OPENABLE_NAMES = {
    'cabinet', 'drawer', 'fridge', 'microwave', 'safe',
    'laundryhamper', 'box',
}


class CandidateGenerator:
    """
    候选动作生成器。

    每步从obs文本解析候选动作，匹配意图后生成最终动作。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # 任务参数
        self.task_type = ''
        self.target_obj = ''       # 目标物体base名
        self.target_obj_full = ''  # 目标物体全名（含编号，如 'plate 2'）
        self.target_recep = ''     # 目标容器base名
        self.tool_loc = ''         # 工具位置base名

        # 场景信息（从obs积累）
        self.all_locations: List[str] = []   # 所有可去位置列表
        self.current_location: str = ''      # 当前位置全名（如 'countertop 1'）
        self.current_loc_base: str = ''      # 当前位置base名
        self.holding: str = ''               # 手持物体全名
        self.opened_containers: Set[str] = set()
        self.visited_locations: Set[str] = set()
        self.object_locations: Dict[str, str] = {}  # 物体全名→位置全名

        # 可操作状态
        self.at_tool = False
        self.at_target = False
        self.has_object_in_sight = False
        self.objects_at_current: List[str] = []  # 当前位置可取物体名

    def reset(self, task_desc: str = '', task_type: str = '',
              initial_obs: str = ''):
        """重置生成器状态，并从初始obs提取所有位置"""
        self.task_type = task_type
        self.target_obj = ''
        self.target_obj_full = ''
        self.target_recep = ''
        self.tool_loc = ''
        self.all_locations = []
        self.current_location = ''
        self.current_loc_base = ''
        self.holding = ''
        self.opened_containers = set()
        self.visited_locations = set()
        self.object_locations = {}
        self.at_tool = False
        self.at_target = False
        self.has_object_in_sight = False
        self.objects_at_current = []

        # 从task_desc解析
        desc_lower = task_desc.lower()
        for obj in OBJECT_NAMES:
            if obj in desc_lower:
                self.target_obj = obj
                break
        for loc in LOCATION_NAMES:
            if loc in desc_lower:
                self.target_recep = loc
                break

        # 工具位置
        if 'clean' in task_type or ('clean' in desc_lower and 'light' not in task_type):
            self.tool_loc = 'sinkbasin'
        elif 'heat' in task_type:
            self.tool_loc = 'microwave'
        elif 'cool' in task_type:
            self.tool_loc = 'fridge'
        elif 'light' in task_type or 'lamp' in desc_lower:
            self.tool_loc = 'desklamp'

        # 从初始obs提取位置
        if initial_obs:
            obs_lower = initial_obs.lower()
            for line in obs_lower.split('\n'):
                items = re.findall(r'a (\w+ \d+)', line)
                for item in items:
                    item_base = re.sub(r' \d+$', '', item)
                    if item_base in LOCATION_NAMES and item not in self.all_locations:
                        self.all_locations.append(item)

    def update(self, obs: str, action: str = '',
               action_success: bool = True):
        """从观测更新状态"""
        obs_lower = obs.lower()

        # 1. 解析当前位置
        loc_match = re.search(r'arrive at (.+?)[\.!]', obs_lower)
        if loc_match:
            loc_full = loc_match.group(1).strip()
            self.current_location = loc_full
            self.current_loc_base = re.sub(r'\s+\d+$', '', loc_full)
            self.visited_locations.add(loc_full)

            # 检查是否在工具/目标位置（确保有实际匹配才置True）
            if self.tool_loc and self.current_loc_base:
                self.at_tool = (self.tool_loc in self.current_loc_base
                                or self.current_loc_base in self.tool_loc)
            else:
                self.at_tool = False
            if self.target_recep and self.current_loc_base:
                self.at_target = (self.target_recep in self.current_loc_base
                                  or self.current_loc_base in self.target_recep)
            else:
                self.at_target = False

        # 2. 解析当前位置的物体（从"you see"文本）
        if 'you see' in obs_lower or 'on the' in obs_lower:
            # 提取所有"a X"格式的名词
            self.objects_at_current = []
            see_text = obs_lower

            # 提取所有带a/an的物体名
            items = re.findall(r'a ([\w\s]+?)(?=[,.]|\s+and|$)', see_text)
            for item in items:
                item = item.strip()
                # 检查是否是已知物体类型
                item_base = re.sub(r'\s+\d+$', '', item)
                if item_base in OBJECT_NAMES:
                    self.objects_at_current.append(item)
                    self.object_locations[item] = self.current_location

            self.has_object_in_sight = len(self.objects_at_current) > 0

        # 3. 解析初始场景中的所有位置
        for line in obs_lower.split('\n'):
            for loc in LOCATION_NAMES:
                pattern = rf'\b{loc} \d+\b'
                matches = re.findall(pattern, line)
                for m in matches:
                    if m not in self.all_locations:
                        self.all_locations.append(m)

        # 4. 跟踪持有状态
        if 'you pick up' in obs_lower:
            obj_match = re.search(r'(?:pick up|picked up) (?:the )?(.+?)(?: from|$)', obs_lower)
            if obj_match:
                self.holding = obj_match.group(1).strip()
        elif 'you put' in obs_lower or 'you move' in obs_lower:
            self.holding = ''
        elif not action_success and action.startswith('take '):
            self.holding = ''
            self.objects_at_current = []

        # 5. 跟踪open状态
        if action.startswith('open ') and action_success:
            container = action[5:].strip()
            self.opened_containers.add(container)

    # ══════════════════════════════════════════════════════════
    # 候选动作生成
    # ══════════════════════════════════════════════════════════

    def get_candidates(self, obs: str) -> Dict[str, List[str]]:
        """
        从当前状态生成候选动作。

        Returns:
            {
                'go_to': [...],          # 可去位置
                'take': [...],           # 可拿物体
                'open': [...],           # 可开容器
                'close': [...],          # 可关容器
                'put': [...],            # 可放置
                'use_tool': [...],       # 可用工具
                'examine': [...],        # 可查看
                'look': [...],           # 环顾
                'inventory': [...],      # 查看手持
            }
        """
        candidates = {
            'go_to': [],
            'take': [],
            'open': [],
            'close': [],
            'put': [],
            'use_tool': [],
            'examine': [],
            'look': ['look'],
            'inventory': ['inventory'],
        }

        # 1. go to: 所有未去过或已知位置
        for loc in self.all_locations:
            if loc != self.current_location:
                candidates['go_to'].append(f'go to {loc}')

        # 2. take: 当前位置的可取物体
        for obj in self.objects_at_current:
            if not self.holding:
                candidates['take'].append(f'take {obj} from {self.current_location}')

        # 3. open: 当前位置的未打开容器
        # 只要当前位置是可打开的且没打开过，就生成open候选
        if self.current_location:
            curr_base = re.sub(r'\s+\d+$', '', self.current_location)
            if curr_base in OPENABLE_NAMES and self.current_location not in self.opened_containers:
                candidates['open'].append(f'open {self.current_location}')

        # 4. put/move: 有手持物体时，生成到所有可放置位置的put命令
        # 优先使用当前位置的目标容器
        if self.holding:
            # 首先，如果当前位置是目标容器类型，生成到此位置的put
            if self.current_location:
                curr_base = re.sub(r'\s+\d+$', '', self.current_location)
                if curr_base in LOCATION_NAMES:
                    candidates['put'].insert(0, f'move {self.holding} to {self.current_location}')
            # 其他位置候选
            for loc_full in self.all_locations:
                if loc_full != self.current_location:
                    loc_base = re.sub(r'\s+\d+$', '', loc_full)
                    if loc_base in LOCATION_NAMES:
                        candidates['put'].append(f'move {self.holding} to {loc_full}')

        # 5. use_tool: 在工具位置且有手持物体
        if self.holding and self.at_tool:
            if self.tool_loc == 'sinkbasin':
                candidates['use_tool'].append(f'clean {self.holding} with {self.current_location}')
            elif self.tool_loc == 'microwave':
                candidates['use_tool'].append(f'heat {self.holding} with {self.current_location}')
            elif self.tool_loc == 'fridge':
                candidates['use_tool'].append(f'cool {self.holding} with {self.current_location}')
            elif 'lamp' in self.tool_loc:
                candidates['use_tool'].append(f'use {self.current_location}')

        # 6. examine
        for obj in self.objects_at_current:
            candidates['examine'].append(f'examine {obj}')

        return candidates

    def select_action(self, intent: str, candidates: Dict[str, List[str]],
                      state: Dict = None) -> str:
        """
        根据意图从候选中选择最优动作，避免循环和重复决策。
        """
        intent_to_cmd = {
            'goto_explore':    ('go_to',       '前往新位置'),
            'goto_object':     ('go_to',       '前往目标物体位置'),
            'goto_tool':       ('go_to',       '前往工具位置'),
            'goto_target':     ('go_to',       '前往目标容器位置'),
            'take_object':     ('take',        '拿取物体'),
            'put_object':      ('put',         '放置物体'),
            'use_tool':        ('use_tool',    '使用工具'),
            'open_container':  ('open',        '打开容器'),
            'look_around':     ('look',        '环顾四周'),
            'wait_confirm':    ('look',        '观察确认'),
            'adjust_strategy': ('go_to',       '调整策略'),
            'task_done':       ('inventory',   '确认完成'),
            'confirm':         ('inventory',   '确认状态'),
        }

        cmd_type, desc = intent_to_cmd.get(intent, ('go_to', '默认探索'))
        cmd_list = candidates.get(cmd_type, [])

        # 安全规则：空手时禁止put（防止误判）
        if intent == 'put_object' and not self.holding:
            if self.verbose:
                print(f"  [Generator] 空手不能put，改取物")
            if candidates.get('take'):
                return candidates['take'][0]
            intent = 'goto_explore'
            cmd_type = 'go_to'
        
        # 特殊规则：当前位置有closed可打开容器时，优先open
        if intent in ('goto_explore', 'look_around') and self.current_location:
            curr_base = re.sub(r'\s+\d+$', '', self.current_location)
            if (curr_base in OPENABLE_NAMES 
                and self.current_location not in self.opened_containers
                and candidates.get('open')):
                if self.verbose:
                    print(f"  [Generator] 当前位置有可打开容器→open")
                return candidates['open'][0]

        selected = None

        if cmd_list:
            if cmd_type == 'take' and self.target_obj:
                # 优先选目标物体
                target_take = [c for c in cmd_list if self.target_obj in c.lower().split()]
                if target_take:
                    selected = target_take[0]
                else:
                    selected = cmd_list[0] if cmd_list else None
            elif cmd_type == 'put' and self.target_recep:
                # 优先选目标容器的位置
                target_put = [c for c in cmd_list
                              if self.target_recep in c.lower()
                              or self.current_location and self.target_recep in self.current_location.lower()]
                if target_put:
                    selected = target_put[0]
                else:
                    selected = cmd_list[0]
            elif cmd_type == 'go_to':
                # 去重：按未访问优先
                unvisited = [c for c in cmd_list
                             if c.replace('go to ', '').strip() not in self.visited_locations]
                candidates_pool = unvisited if unvisited else cmd_list
                
                # 意图微调：优先匹配目标位置
                if intent == 'goto_tool' and self.tool_loc:
                    tool_cmds = [c for c in candidates_pool
                                 if self.tool_loc in c.replace('go to ','').lower()]
                    if tool_cmds: selected = tool_cmds[0]
                elif intent == 'goto_target' and self.target_recep:
                    target_cmds = [c for c in candidates_pool
                                   if self.target_recep in c.replace('go to ','').lower()]
                    if target_cmds: selected = target_cmds[0]
                elif intent == 'goto_object' and self.object_locations:
                    known_locs = set(self.object_locations.values())
                    known_cmds = [c for c in candidates_pool
                                  if c.replace('go to ','') in known_locs]
                    if known_cmds: selected = known_cmds[0]
                
                if selected is None:
                    selected = candidates_pool[0] if candidates_pool else (cmd_list[0] if cmd_list else None)
            else:
                selected = cmd_list[0] if cmd_list else None

            if self.verbose:
                print(f"  [Generator] {desc} → {selected}")
            return selected

        # 兜底：当前意图不可行时，按意图语义补位
        # use_tool不可行 → 应去工具位置（意图语义补位）
        if intent == 'use_tool' and self.tool_loc:
            tool_candidates = candidates.get('go_to', [])
            tool_matches = [c for c in tool_candidates
                            if self.tool_loc in c.replace('go to ','').lower()]
            if tool_matches:
                if self.verbose:
                    print(f"  [Generator] use_tool兜底→goto_tool({self.tool_loc})")
                return tool_matches[0]
        
        # put_object不可行 → 应去目标容器位置
        if intent == 'put_object' and self.target_recep:
            go_candidates = candidates.get('go_to', [])
            target_matches = [c for c in go_candidates
                              if self.target_recep in c.replace('go to ','').lower()]
            if target_matches:
                if self.verbose:
                    print(f"  [Generator] put_object兜底→goto_target({self.target_recep})")
                return target_matches[0]
        
        # take_object不可行 → 继续探索找物体
        if intent == 'take_object':
            if candidates.get('take'):
                return candidates['take'][0]
            go_candidates = candidates.get('go_to', [])
            # 去已知物体位置
            if self.object_locations:
                known_go = [c for c in go_candidates
                            if c.replace('go to ','') in self.object_locations.values()]
                if known_go:
                    return known_go[0]
            # 否则探索
            unvisited = [c for c in go_candidates
                         if c.replace('go to ','') not in self.visited_locations]
            if unvisited:
                return unvisited[0]
            if go_candidates:
                return go_candidates[0]
        
        # 通用兜底：优先去未访问位置
        fallback_order = ['go_to', 'look', 'open', 'take', 'put']
        for fb_type in fallback_order:
            fb_list = candidates.get(fb_type, [])
            if fb_type == 'go_to' and fb_list:
                # 优先未访问
                unvisited = [c for c in fb_list
                             if c.replace('go to ','') not in self.visited_locations]
                if unvisited:
                    selected = unvisited[0]
                    if self.verbose:
                        print(f"  [Generator] 兜底go_to(未访问) → {selected}")
                    return selected
            if fb_list:
                selected = fb_list[0]
                if self.verbose:
                    print(f"  [Generator] 兜底{fb_type} → {selected}")
                return selected

        # 终极兜底
        if self.verbose:
            print(f"  [Generator] 无候选，返回look")
        return 'look'

    def is_tool_location(self, location: str) -> bool:
        """判断某位置是否是工具位置"""
        if not self.tool_loc or not location:
            return False
        loc_base = re.sub(r'\s+\d+$', '', location)
        return self.tool_loc in loc_base or loc_base in self.tool_loc

    def is_target_location(self, location: str) -> bool:
        """判断某位置是否是目标容器位置"""
        if not self.target_recep or not location:
            return False
        loc_base = re.sub(r'\s+\d+$', '', location)
        return self.target_recep in loc_base or loc_base in self.target_recep
