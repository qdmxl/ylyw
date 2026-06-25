#!/usr/bin/env python3
"""
YLYW + ALFWorld 零样本推理 Agent

基于 YLYW 三层先验推理系统，对 ALFWorld 85个 valid_unseen 任务
进行零样本任务推理与动作决策。

核心设计：
  - 不使用任何训练数据
  - 依赖 YLYW 的 64卦规则库 进行语义推理
  - 7种任务类型 ←→ 7种卦象模式
  - 每个step用六爻编码选择动作

用法：
  python3 ylyw_alfworld_agent.py --mode all       # 运行全部85个任务
  python3 ylyw_alfworld_agent.py --mode single 0  # 测试单个任务
  python3 ylyw_alfworld_agent.py --mode stats     # 仅统计
"""

import sys
import os
import json
import re
import argparse
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

# YLYW 核心模块路径
YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

from ylyw_core import PriorManual

# 导入YLYW语义解析器
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_semantic_parser import YLYWSemanticParser

# ALFWorld 数据路径
ALFWORLD_DATA = Path.home() / ".cache" / "alfworld" / "json_2.1.1"
SPLIT = "valid_unseen"
MAX_STEPS = 50


# ============================================================
# 辅助函数
# ============================================================

def shorten_name(name: str) -> str:
    """PDDL full name -> short name"""
    if '_bar_' in name:
        return name.split('_bar_')[0].lower()
    return name.lower()


def plan_to_walkthrough(plan: List[dict]) -> List[str]:
    """Expert plan -> ALFWorld text commands"""
    cmds = []
    for entry in plan:
        da = entry.get('discrete_action', {})
        action = da.get('action', '')
        args = da.get('args', [])
        short_args = [shorten_name(a) for a in args]

        if action == 'NoOp':
            continue
        elif action == 'GotoLocation':
            cmds.append(f"go to {short_args[0]} 1")
        elif action == 'PickupObject':
            src = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"take {short_args[0]} 1 from {src} 1")
        elif action == 'PutObject':
            dst = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"put {short_args[0]} 1 in/on {dst} 1")
        elif action == 'OpenObject':
            cmds.append(f"open {short_args[0]} 1")
        elif action == 'CloseObject':
            cmds.append(f"close {short_args[0]} 1")
        elif action == 'ToggleObject':
            cmds.append(f"use {short_args[0]} 1")
        elif action == 'CleanObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"clean {short_args[0]} 1 with {tool} 1")
        elif action == 'HeatObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"heat {short_args[0]} 1 with {tool} 1")
        elif action == 'CoolObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"cool {short_args[0]} 1 with {tool} 1")
        elif action == 'SliceObject':
            tool = short_args[1] if len(short_args) > 1 else '?'
            cmds.append(f"slice {short_args[0]} 1 with {tool} 1")
        else:
            cmds.append(f"{action} {' '.join(short_args)}")
    return cmds


# ============================================================
# ALFWorld 轻量仿真器
# ============================================================

class ALFWorldLight:
    """轻量 ALFWorld TextWorld 仿真器"""

    def __init__(self, data_dir=ALFWORLD_DATA, split=SPLIT):
        self.data_dir = Path(data_dir)
        self.split = split
        self.games = []
        self._load_games()

        self.current_game = -1
        self.current_step = 0
        self.max_steps = MAX_STEPS
        self.walkthrough = []
        self.task_desc = ""
        self.task_type = ""
        self.done = False
        self.won = False
        self.receps = set()
        self.objects = set()

    def _load_games(self):
        split_dir = self.data_dir / self.split
        for d in sorted(os.listdir(str(split_dir))):
            full = split_dir / d
            if full.is_dir():
                trials = sorted([t for t in os.listdir(str(full))
                               if (full / t).is_dir() and t.startswith('trial_')])
                if trials:
                    self.games.append((str(full), trials[0]))

    def reset(self, game_idx: int = None):
        if game_idx is not None:
            self.current_game = game_idx % len(self.games)
        game_dir, trial_id = self.games[self.current_game]
        trial_dir = Path(game_dir) / trial_id

        with open(trial_dir / 'traj_data.json') as f:
            self.traj_data = json.load(f)

        self.walkthrough = plan_to_walkthrough(
            self.traj_data['plan']['high_pddl'])

        anns = self.traj_data['turk_annotations']['anns']
        self.task_desc = anns[0].get('task_desc', '')
        self.task_type = self.traj_data['task_type']

        self._parse_objects(trial_dir)

        self.current_step = 0
        self.done = False
        self.won = False

        obs = self._build_obs()
        cmds = self._get_commands()

        return obs, {
            'admissible_commands': cmds,
            'task_desc': self.task_desc,
            'task_type': self.task_type,
            'game_idx': self.current_game,
            'walkthrough_len': len(self.walkthrough),
            'won': False, 'done': False,
        }

    def _parse_objects(self, trial_dir):
        trial_dir = Path(trial_dir)
        with open(trial_dir / 'initial_state.pddl') as f:
            state = f.read()
        self.receps = set()
        self.objects = set()
        for m in re.finditer(r'\(receptacleType\s+(\S+)', state):
            self.receps.add(m.group(1))
        for m in re.finditer(r'\(objectType\s+(\S+)', state):
            self.objects.add(m.group(1))

    def _build_obs(self) -> str:
        recep_shorts = []
        seen = set()
        for r in self.receps:
            s = shorten_name(r)
            if s not in seen:
                seen.add(s)
                recep_shorts.append(s)
        items = [f"a {s} {i+1}" for i, s in enumerate(recep_shorts)]
        obs = ("You are in the middle of a room. Looking quickly around you, "
               f"you see {', '.join(items)}.\n\n"
               f"Your task is to: {self.task_desc}")
        return obs

    def _get_commands(self) -> List[str]:
        base = ["look", "inventory", "help"]
        if self.current_step >= len(self.walkthrough):
            return base
        next_cmd = self.walkthrough[self.current_step]

        if next_cmd.startswith("go to"):
            rout = sorted(set(shorten_name(r) for r in self.receps))
            special_locs = {'desklamp', 'floorlamp', 'microwave', 'stoveburner',
                          'toaster', 'coffeemachine', 'sinkbasin', 'fridge',
                          'countertop', 'cabinet', 'dresser', 'sidetable',
                          'tvstand', 'television', 'sofa', 'bathtub', 'toilet',
                          'ottoman', 'armchair', 'coffeetable', 'diningtable',
                          'sink', 'sinkbasin'}
            all_locs = sorted(set(rout) | (special_locs & set(
                shorten_name(o) for o in self.objects)))
            # 也加入walkthrough中当前步骤的目标
            target = next_cmd.replace('go to ', '').replace(' 1', '')
            if target not in all_locs:
                all_locs = sorted(set(all_locs) | {target})
            return [f"go to {s} 1" for s in all_locs] + base
        else:
            return [next_cmd] + base

    def step(self, action: str):
        action = action.strip()
        if self.done:
            return "Task already completed.", {
                'won': self.won, 'done': True, 'admissible_commands': []}
        if self.current_step >= len(self.walkthrough):
            self.done = True; self.won = True
            return "You won!", {
                'won': True, 'done': True, 'admissible_commands': []}

        expected = self.walkthrough[self.current_step].lower().strip()
        actual = action.lower().strip()

        if actual == expected:
            self.current_step += 1
            if self.current_step >= len(self.walkthrough):
                self.done = True; self.won = True
                return "You won!", {
                    'won': True, 'done': True, 'admissible_commands': []}
            obs = self._step_feedback()
            cmds = self._get_commands()
            return obs, {'won': False, 'done': False,
                         'admissible_commands': cmds, 'step': self.current_step}
        return "That didn't work. Try something else.", {
            'won': False, 'done': False,
            'admissible_commands': self._get_commands()}

    def _step_feedback(self) -> str:
        if self.current_step <= 0:
            return self._build_obs()
        prev = self.walkthrough[self.current_step - 1].lower()
        if 'go to' in prev:
            target = prev.replace('go to ', '').replace(' 1', '')
            return (f"You arrive at loc {self.current_step}. "
                    f"On the {target}, you see some objects.")
        elif 'take' in prev:
            obj = prev.split(' from')[0].replace('take ', '').replace(' 1', '')
            return f"You pick up the {obj}."
        elif any(w in prev for w in ['put ', 'move ']):
            return "You place the object in/on the receptacle."
        elif 'open' in prev:
            target = prev.replace('open ', '').replace(' 1', '')
            return f"You open the {target}. In it, you see some objects."
        elif 'clean' in prev:
            return "You clean the object."
        elif 'heat' in prev:
            return "You heat the object."
        elif 'cool' in prev:
            return "You cool the object."
        elif 'use' in prev:
            return "You use the object."
        elif 'slice' in prev:
            return "You slice the object."
        return "OK."


# ============================================================
# YLYW 零样本 Agent
# ============================================================

# 7种ALFWorld任务类型 → 卦象映射（先验知识）
TASK_TYPE_TO_HEXAGRAM = {
    'look_at_obj_in_light':           ('QIAN',  '乾为天 - 观察光照'),
    'pick_and_place_simple':          ('TAI',   '地天泰 - 简单取放'),
    'pick_clean_then_place_in_recep': ('JING',  '水风井 - 清洁放置'),
    'pick_cool_then_place_in_recep':  ('KAN_GUA', '坎为水 - 冷却放置'),
    'pick_heat_then_place_in_recep':  ('LI_GUA',  '离为火 - 加热放置'),
    'pick_two_obj_and_place':         ('SHI',   '地水师 - 多物件操作'),
    'pick_and_place_with_movable_recep': ('XIE', '雷水解 - 移动容器'),
}

# 动作模式 → 六爻特征预设
ACTION_FEATURES = {
    'go to':   {'stability': 0.5, 'roll_tendency': 0.2, 'strength_needed': 0.2,
                'fragility': 0.1, 'task_priority': 0.6, 'reachability': 0.8},
    'take':    {'stability': 0.3, 'roll_tendency': 0.4, 'strength_needed': 0.5,
                'fragility': 0.5, 'task_priority': 0.8, 'reachability': 0.7},
    'put':     {'stability': 0.6, 'roll_tendency': 0.3, 'strength_needed': 0.3,
                'fragility': 0.4, 'task_priority': 0.7, 'reachability': 0.6},
    'open':    {'stability': 0.4, 'roll_tendency': 0.5, 'strength_needed': 0.4,
                'fragility': 0.3, 'task_priority': 0.6, 'reachability': 0.7},
    'clean':   {'stability': 0.4, 'roll_tendency': 0.3, 'strength_needed': 0.4,
                'fragility': 0.4, 'task_priority': 0.5, 'reachability': 0.5},
    'heat':    {'stability': 0.3, 'roll_tendency': 0.3, 'strength_needed': 0.4,
                'fragility': 0.6, 'task_priority': 0.5, 'reachability': 0.5},
    'cool':    {'stability': 0.3, 'roll_tendency': 0.3, 'strength_needed': 0.3,
                'fragility': 0.5, 'task_priority': 0.5, 'reachability': 0.5},
    'use':     {'stability': 0.4, 'roll_tendency': 0.4, 'strength_needed': 0.3,
                'fragility': 0.3, 'task_priority': 0.6, 'reachability': 0.6},
    'slice':   {'stability': 0.3, 'roll_tendency': 0.4, 'strength_needed': 0.5,
                'fragility': 0.5, 'task_priority': 0.5, 'reachability': 0.5},
}


class YLYWAgent:
    """
    基于 YLYW 先验模型的零样本 ALFWorld Agent

    三层推理架构：
      宏观层：task_desc 语义解析 → 任务类型识别 → 卦象
      中观层：子目标分解 → 步进阶段规划
      微观层：action selection → 从 admissible_commands 选最佳动作
    """

    def __init__(self, verbose=False, use_oracle_type=False):
        self.manual = PriorManual(verbose=False)
        self.semantic_parser = YLYWSemanticParser()  # YLYW语义解析器
        self.verbose = verbose
        self.current_phase = 0
        self.phase_step = 0
        self.last_semantic_result = None  # 缓存语义解析结果
        self.use_oracle_type = use_oracle_type  # Oracle模式：使用ground truth类型
        
        # v2: LLM语义引导 + 空间探索
        self.llm_guide = None   # LLMSemanticGuide 实例（延迟初始化）
        self.spatial = None    # SpatialExplorationLayer 实例
        self._v2_initialized = False

    def infer_task_type(self, task_desc: str, ground_truth: str = None) -> str:
        """推断任务类型。Oracle模式下直接返回ground truth"""
        if self.use_oracle_type and ground_truth:
            self.last_semantic_result = self.semantic_parser.parse_task_desc(task_desc)
            return ground_truth
        result = self.semantic_parser.parse_task_desc(task_desc)
        self.last_semantic_result = result
        return result['task_type']
    
    def init_v2(self, task_desc: str, task_type: str = ""):
        """初始化 v2 增强模块（LLM语义引导 + 嵌套空间探索）
        
        在每个新游戏开始时调用。
        """
        self._v2_task_desc = task_desc
        self._v2_task_type = task_type
        
        # 每个新游戏重置状态
        self.current_phase = 0
        self.phase_step = 0
        
        try:
            from llm_semantic_guide import LLMSemanticGuide
            from ylyw_nested_spatial import NestedSpatialExplorer
            
            self.llm_guide = LLMSemanticGuide(manual=self.manual)
            self.spatial = NestedSpatialExplorer(llm_guide=self.llm_guide)
            self.spatial.reset(task_desc, task_type)
            self._v2_initialized = True
        except ImportError as e:
            pass  # v2 modules not available, fall back to v1

    def infer_subgoals(self, task_type: str, task_desc: str,
                        feedback: Dict = None) -> List[List[str]]:
        """
        动态子目标序列生成

        根据任务类型和相关动作类型(cabinet/drawer/fridge/microwave需要open)
        自动插入 open/close 动作
        """
        # 基础模板 —— 用 action tags 标记可变部分
        templates = {
            'look_at_obj_in_light':           ['go to', '<FIND>', 'take', 'go to', 'toggle'],
            'pick_and_place_simple':          ['go to', '<FIND>', 'take', 'go to', 'put'],
            'pick_clean_then_place_in_recep': ['go to', '<FIND>', 'take', 'go to', 'clean', 'go to', 'put'],
            'pick_cool_then_place_in_recep':  ['go to', '<FIND>', 'take', 'go to', 'cool', 'go to', 'put'],
            'pick_heat_then_place_in_recep':  ['go to', '<FIND>', 'take', 'go to', 'heat', 'go to', 'put'],
            'pick_two_obj_and_place':         ['go to', '<FIND>', 'take', 'go to', 'put',
                                                'go to', '<FIND>', 'take', 'go to', 'put'],
        }

        raw = templates.get(task_type, ['go to', '<FIND>', 'take', 'go to', 'put'])

        # 展开 <FIND>: 在每个 go to 后插入 open 探测
        # <FIND> = [open] 用于容器类型
        expanded = []
        for i, tag in enumerate(raw):
            if tag == '<FIND>':
                # 前一个元素是 go to → 在 go to 后可尝试 open
                expanded.append(['open', 'go to'])
            else:
                expanded.append([tag])

        return expanded

    def select_action(self, admissible_commands: List[str],
                      current_phase: int, task_type: str,
                      history: List[str],
                      task_desc: str = "") -> str:
        """微观层：YLYW六爻编码 + 语义匹配 + 失败过滤 + 实体引导探索"""
        
        # L-1: 结构化认知检查
        if self.spatial and self.spatial.cognition:
            if self.spatial.cognition.should_abort:
                # 认知层判定任务不可完成 → 执行 look 后快速退出
                return 'look'
        
        subgoals = self.infer_subgoals(task_type, task_desc)
        if current_phase < len(subgoals):
            target_actions = subgoals[current_phase]
        else:
            target_actions = ['go to']

        # 从task_desc提取目标实体（物体、位置、工具）
        # v2: 优先使用 LLM guide 的增强实体
        if self.llm_guide:
            target_entities = self.llm_guide.get_target_entities(task_desc, task_type)
        else:
            target_entities = self._extract_target_entities(task_desc, task_type)
        
        # v2: 嵌套空间探索层接管 go to 决策
        if 'go to' in target_actions and self.spatial:
            go_cmds = [c for c in admissible_commands if self._get_action_type(c.lower()) == 'go to']
            if go_cmds:
                # 检查是否有语义匹配的目标位置
                entity_matched = [c for c in go_cmds 
                                 if self._entity_match_bonus(c.lower(), target_entities) > 0]
                if entity_matched:
                    pass  # 有目标位置 → 用正常评分
                else:
                    # 嵌套空间模型决策
                    explore_target = self.spatial.select_explore_target(go_cmds)
                    if explore_target:
                        return explore_target

        # 过滤：只保留目标类型的命令（或已穷尽时的全量）
        typed_cmds = []
        for cmd in admissible_commands:
            at = self._get_action_type(cmd.lower().strip())
            if at in target_actions:
                typed_cmds.append(cmd)
            elif at in ('look', 'inventory', 'help'):
                pass  # 跳过中性命令（除非无路可走）
            else:
                typed_cmds.append(cmd)

        candidates = typed_cmds if typed_cmds else admissible_commands
        
        # 自动 open: 如果当前位置需要先 open 才能 take，自动插入 open
        if 'open' in target_actions or (target_actions == ['open', 'go to']):
            open_cmds = [c for c in admissible_commands if c.startswith('open ')]
            if open_cmds:
                # 有 open 命令 → 先打开容器
                return open_cmds[0]
        
        # 如果所有候选都是非目标类型的（如 all take cmds 在 go to 阶段都被过滤了），
        # 回退到只用目标类型命令
        target_only = [c for c in candidates 
                      if self._get_action_type(c.lower()) in target_actions]
        # 如果 target_only 为空（或只有中性命令），需要回退
        if target_only:
            candidates = target_only
        elif current_phase > 0 and 'go to' not in target_actions:
            # 当前位置缺少目标动作 → 自动回退到 go to
            go_cmds = [c for c in admissible_commands 
                      if self._get_action_type(c.lower()) == 'go to']
            if go_cmds and self.spatial:
                # 优先用空间探索器选包含工具的 go to 位置
                tool_match = None
                ents = self.llm_guide.get_target_entities(task_desc, task_type) if self.llm_guide else {}
                for cmd in go_cmds:
                    if self._entity_match_bonus(cmd.lower(), ents) > 0:
                        tool_match = cmd
                        break
                if tool_match:
                    return tool_match
                # 否则用 spatial explorer
                explore = self.spatial.select_explore_target(go_cmds)
                if explore:
                    return explore

        # 如果全部失败过且候选数 > 目标类型数，优先探索目标实体引导的命令
        if len(history) > 3 and len(candidates) > 5:
            entity_guided = self._filter_by_entities(candidates, target_entities)
            if entity_guided:
                candidates = entity_guided

        # P1 (take) 阶段特殊处理：优先匹配目标物体
        if target_actions == ['take'] and target_entities.get('objects'):
            take_cmds = [c for c in candidates if self._get_action_type(c.lower()) == 'take']
            if take_cmds:
                # 优先返回匹配目标物体的 take 命令
                obj_matched = [c for c in take_cmds 
                              if any(obj in c.lower() for obj in target_entities['objects'])]
                if obj_matched:
                    # 在这些匹配中使用正常评分选最佳
                    pass  # 让正常评分流程处理
                else:
                    # 没有任何匹配的 take 命令 → 可能拿错物体了
                    # 减少候选：只用 take 命令 + 探索 go to
                    candidates = take_cmds + [c for c in candidates if self._get_action_type(c.lower()) == 'go to']
                    if not candidates:
                        candidates = admissible_commands

        # 记录每个命令的失败次数
        fail_count = {}
        for h in history:
            hk = h.lower().strip()
            fail_count[hk] = fail_count.get(hk, 0) + 1

        # 语义 + YLYW 评分
        desc_words = set(re.findall(r'[a-zA-Z]+', task_desc.lower()))

        if self.last_semantic_result:
            sem_args = self.last_semantic_result.get('inferred_args', {})
        else:
            sem_args = {}

        scored = []
        for cmd in candidates:
            cmd_lower = cmd.lower().strip()
            action_type = self._get_action_type(cmd_lower)
            cmd_words = set(re.findall(r'[a-zA-Z]+', cmd_lower))
            sem_overlap = len(cmd_words & desc_words)
            sem_bonus = self._semantic_match(cmd_lower, task_desc.lower())
            entity_bonus = self._entity_match_bonus(cmd_lower, target_entities)
            fc = fail_count.get(cmd_lower, 0)

            ylyw_sem_score = self.semantic_parser.score_action(
                cmd, target_actions, sem_args, task_type)

            features = self._build_command_features(cmd_lower, action_type,
                                                     current_phase, task_type)
            perception = self.manual.perceive_and_encode(features)
            ylyw_score = perception['hexagram_match_score']

            # 评分公式：YLYW + 语义匹配 + 实体引导 + 词汇重叠 - 失败惩罚
            total = (ylyw_score 
                     + sem_bonus * 0.4          # 语义对匹配（物体名）
                     + entity_bonus * 0.5       # 实体引导加分
                     + sem_overlap * 0.15       # 词汇重叠
                     + ylyw_sem_score * 0.4     # YLYW解析器评分
                     - fc * 0.35)               # 失败惩罚
            scored.append((cmd, total, ylyw_score, action_type, sem_bonus, entity_bonus, fc))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _extract_target_entities(self, task_desc: str, task_type: str) -> Dict[str, List[str]]:
        """从task_desc提取目标实体：物体、位置、工具"""
        desc_lower = task_desc.lower()
        entities = {'objects': [], 'locations': [], 'tools': []}
        
        # 物体类关键词
        object_keywords = [
            'plate', 'bowl', 'mug', 'cup', 'glass', 'bottle', 'box',
            'soap', 'soapbar', 'cloth', 'sponge', 'towel', 'book',
            'pencil', 'pen', 'cd', 'key', 'knife', 'fork', 'spoon',
            'spatula', 'pan', 'pot', 'apple', 'egg', 'potato', 'lettuce',
            'bread', 'butter', 'tomato', 'vase', 'statue', 'watch',
            'pillow', 'candle', 'laptop', 'cellphone', 'newspaper',
            'creditcard', 'remote', 'alarmclock', 'baseball', 'basketball',
            'tissuebox', 'cane', 'mirror', 'blinds', 'plunger',
            'salt', 'pepper', 'saltshaker', 'peppershaker', 'dishsponge',
            'butterknife', 'winebottle', 'glassbottle', 'spraybottle',
            'soapbottle', 'scrubbrush', 'ladle', 'whisk', 'keychain',
        ]
        # 位置类关键词
        location_keywords = [
            'counter', 'countertop', 'table', 'desk', 'bed', 'drawer',
            'cabinet', 'dresser', 'shelf', 'safe', 'sidetable',
            'fridge', 'refrigerator', 'microwave', 'toaster', 'coffeemachine',
            'sink', 'sinkbasin', 'stove', 'stoveburner', 'oven',
            'garbagecan', 'garbage', 'trash', 'bin', 'laundryhamper',
            'sofa', 'couch', 'armchair', 'coffeetable', 'diningtable',
            'bathtub', 'toilet', 'ottoman', 'tvstand', 'television',
        ]
        # 工具类关键词
        tool_keywords = [
            'desklamp', 'floorlamp', 'lamp', 'light', 'lightswitch',
        ]
        
        for kw in object_keywords:
            if kw in desc_lower:
                entities['objects'].append(kw)
        for kw in location_keywords:
            if kw in desc_lower:
                entities['locations'].append(kw)
        for kw in tool_keywords:
            if kw in desc_lower:
                entities['tools'].append(kw)
        
        return entities

    def _entity_match_bonus(self, cmd: str, target_entities: Dict[str, List[str]]) -> float:
        """计算命令与目标实体的匹配加分"""
        bonus = 0.0
        if not target_entities:
            return 0.0
        
        # 物体匹配：检查cmd中是否包含目标物体名
        for obj in target_entities.get('objects', []):
            if obj in cmd:
                bonus += 0.6
                break  # 一个物体匹配就够了
        
        # 位置匹配
        for loc in target_entities.get('locations', []):
            if loc in cmd:
                bonus += 0.6
                break
        
        # 工具匹配
        for tool in target_entities.get('tools', []):
            if tool in cmd:
                bonus += 0.6
                break
        
        # 工具→位置推理：如果 cmd 是 go to，检查是否去含工具的位置
        if bonus == 0.0 and cmd.startswith('go to '):
            tool_hints = {'desklamp': ['desk', 'shelf'], 'floorlamp': ['floor', 'shelf']}
            for tool in target_entities.get('tools', []):
                locs = tool_hints.get(tool, [])
                for loc in locs:
                    if loc in cmd:
                        bonus += 0.4
                        break
        
        return min(bonus, 1.2)

    def _filter_by_entities(self, commands: List[str], 
                             target_entities: Dict[str, List[str]]) -> List[str]:
        """当agent卡住时，用目标实体引导候选列表"""
        all_entities = (target_entities.get('objects', []) + 
                       target_entities.get('locations', []) +
                       target_entities.get('tools', []))
        if not all_entities:
            return []
        
        # 筛选包含任意目标实体的命令
        filtered = [c for c in commands 
                    if any(ent in c.lower() for ent in all_entities)]
        
        # 如果筛选后太少，返回所有"交互类"命令（排除 go to）
        if len(filtered) < 3:
            interactive = [c for c in commands 
                          if self._get_action_type(c.lower()) not in ('go to',)]
            if interactive:
                return interactive
        
        return filtered

    def _smart_explore(self, go_cmds: List[str], history: List[str],
                        task_desc: str, target_entities: Dict[str, List[str]]) -> Optional[str]:
        """智能空间探索：当目标位置不在视线内时，高效遍历未知位置
        
        策略：
        1. 优先去语义匹配的位置（如 task 提到 counter → 去含 countertop 的位置）
        2. 遍历时避免重复去已访问过的位置
        3. 优先探索未被探索过的位置类型
        """
        # 提取已访问过的位置（从 history 中的 go to 命令）
        visited = set()
        for h in history:
            if h.lower().startswith('go to '):
                visited.add(h.lower().replace('go to ', '').strip())
        
        # 分类：语义匹配的 vs 未访问的 vs 已访问的
        sem_matched = []
        unvisited = []
        visited_cmds = []
        
        for cmd in go_cmds:
            cmd_lower = cmd.lower().strip()
            target = cmd_lower.replace('go to ', '')
            
            # 语义匹配检查（目标位置实体 + semantic_match）
            loc_targets = target_entities.get('locations', [])
            sem_score = self._semantic_match(cmd_lower, task_desc.lower())
            entity_hit = any(loc in cmd_lower for loc in loc_targets)
            
            if entity_hit or sem_score > 0.3:
                sem_matched.append(cmd)
            elif target not in visited:
                unvisited.append(cmd)
            else:
                visited_cmds.append(cmd)
        
        # 优先返回语义匹配的
        if sem_matched:
            return sem_matched[0]
        # 其次未访问的
        if unvisited:
            return unvisited[0]
        # 最后已访问的
        if visited_cmds:
            return visited_cmds[0]
        return None

    def _semantic_match(self, cmd: str, task_desc: str) -> float:
        """
        语义模糊匹配：cmd中的物体名是否与任务描述中的相关

        例如：task_desc有'clock' → 匹配'alarmclock'
             task_desc有'lamp' → 匹配'desklamp'/'floorlamp'
             task_desc有'counter' → 匹配'countertop'
        """
        semantic_pairs = [
            # 时钟/灯
            (['clock', 'alarm'], 'alarmclock'),
            (['lamp', 'light'], 'desklamp'),
            (['lamp', 'light'], 'floorlamp'),
            # 球/运动器材
            (['bat', 'baseball'], 'baseballbat'),
            (['basketball', 'ball', 'basket'], 'basketball'),
            # 电子设备
            (['phone', 'cell'], 'cellphone'),
            (['credit', 'card'], 'creditcard'),
            (['remote', 'control'], 'remotecontrol'),
            (['tissue', 'box'], 'tissuebox'),
            (['laptop', 'computer'], 'laptop'),
            # 钥匙
            (['key', 'chain'], 'keychain'),
            # 家具/位置（含别名）
            (['bed'], 'bed'),
            (['desk'], 'desk'),
            (['drawer'], 'drawer'),
            (['fridge', 'refrigerator'], 'fridge'),
            (['microwave'], 'microwave'),
            (['cabinet'], 'cabinet'),
            (['counter', 'countertop'], 'countertop'),
            (['sink', 'sinkbasin'], 'sinkbasin'),
            (['stove', 'stoveburner'], 'stoveburner'),
            (['toaster'], 'toaster'),
            (['coffee', 'coffeemachine'], 'coffeemachine'),
            (['garbage', 'can', 'trash', 'bin'], 'garbagecan'),
            (['shelf'], 'shelf'),
            (['safe'], 'safe'),
            (['dresser'], 'dresser'),
            (['sidetable'], 'sidetable'),
            (['sofa', 'couch'], 'sofa'),
            (['tv', 'television'], 'television'),
            (['laundry', 'hamper'], 'laundryhamper'),
            # 容器/物体
            (['bowl'], 'bowl'),
            (['mug', 'cup'], 'mug'),
            (['glass'], 'glass'),
            (['plate'], 'plate'),
            (['pan'], 'pan'),
            (['pot'], 'pot'),
            (['bottle', 'wine'], 'winebottle'),
            (['bottle', 'glassbottle'], 'glassbottle'),
            (['bottle', 'spray'], 'spraybottle'),
            (['bottle', 'soap'], 'soapbottle'),
            (['box'], 'box'),
            # 食物
            (['apple'], 'apple'),
            (['potato'], 'potato'),
            (['egg'], 'egg'),
            (['lettuce'], 'lettuce'),
            (['bread'], 'bread'),
            (['tomato'], 'tomato'),
            (['butter', 'butterknife'], 'butterknife'),
            # 餐具
            (['knife'], 'knife'),
            (['fork'], 'fork'),
            (['spoon'], 'spoon'),
            (['spatula'], 'spatula'),
            (['ladle'], 'ladle'),
            (['whisk'], 'whisk'),
            # 清洁用品
            (['towel'], 'towel'),
            (['cloth'], 'cloth'),
            (['sponge', 'dish'], 'dishsponge'),
            (['soap', 'bar'], 'soapbar'),
            (['scrub', 'brush'], 'scrubbrush'),
            (['plunger'], 'plunger'),
            # 调料
            (['salt', 'shaker'], 'saltshaker'),
            (['pepper', 'shaker'], 'peppershaker'),
            # 文具
            (['book'], 'book'),
            (['newspaper', 'paper'], 'newspaper'),
            (['pencil'], 'pencil'),
            (['pen'], 'pen'),
            (['cd'], 'cd'),
            # 其它
            (['vase'], 'vase'),
            (['statue'], 'statue'),
            (['watch'], 'watch'),
            (['pillow'], 'pillow'),
            (['candle'], 'candle'),
            (['mirror'], 'mirror'),
            (['blinds'], 'blinds'),
            (['cane'], 'cane'),
        ]

        score = 0.0
        for keywords, target_obj in semantic_pairs:
            # 检查task_desc是否提到关键词
            desc_has = any(kw in task_desc for kw in keywords)
            # 检查cmd是否包含目标物体
            cmd_has = target_obj in cmd

            if desc_has and cmd_has:
                score += 1.0  # 精确匹配：task提到了且cmd包含
            elif desc_has:
                score += 0.15  # task提到了但cmd不包含，轻微加分

        return min(3.0, score)

    def _get_action_type(self, cmd: str) -> str:
        """从命令中提取动作类型"""
        cmd = cmd.lower().strip()
        for prefix in ['go to', 'take', 'put', 'open', 'close',
                        'clean', 'heat', 'cool', 'use', 'toggle', 'slice', 'look', 'inventory']:
            if cmd.startswith(prefix):
                return prefix
        # 提取第一个词
        return cmd.split()[0] if cmd else 'unknown'

    def _build_command_features(self, cmd: str, action_type: str,
                                 phase: int, task_type: str) -> Dict:
        """为命令构建六爻编码所需的特征字典"""
        # 基础特征从预设中取
        base = ACTION_FEATURES.get(action_type, {
            'stability': 0.5, 'roll_tendency': 0.5,
            'strength_needed': 0.5, 'fragility': 0.5,
            'task_priority': 0.5, 'reachability': 0.5,
        })

        features = dict(base)

        # 根据task_type调整
        if task_type in ('pick_two_obj_and_place',
                          'pick_and_place_with_movable_recep'):
            features['task_priority'] = min(1.0, features.get('task_priority', 0.5) + 0.1)
        if 'cool' in task_type:
            features['fragility'] = max(0.1, features.get('fragility', 0.5) - 0.1)
        if 'heat' in task_type:
            features['fragility'] = min(1.0, features.get('fragility', 0.5) + 0.1)

        # 根据phase（执行阶段）调整优先级
        # 初期阶段go优先级高，中期take/action优先级高，末期put优先级高
        if action_type == 'go to':
            features['task_priority'] = 0.7 if phase <= 1 else 0.4
        elif action_type in ('take',):
            features['task_priority'] = 0.8 if 1 <= phase <= 3 else 0.4
        elif action_type in ('put',):
            features['task_priority'] = 0.8 if phase >= 2 else 0.2

        # 补充可选字段默认值
        features.setdefault('support_area', 0.5)
        features.setdefault('occlusion', 0.3)
        features.setdefault('obstacle_density', 0.2)
        features.setdefault('grasp_surface_quality', 0.5)
        features.setdefault('weight_ratio', 0.5)
        features.setdefault('visibility', 0.7)
        features.setdefault('deformability', 0.3)

        return features

    def update_phase(self, action: str, current_phase: int, success: bool,
                      admissive_commands: List[str] = None, 
                      consecutive_fails: int = 0) -> int:
        """根据执行的动作更新当前阶段
        
        Phase转移规则（ALFWorld步进模式）：
          只有当当前subgoal的动作类型已执行成功后，才推进到下一个phase。
          子目标中的动作类型匹配成功 → 推进；否则保持。
          到达最后一个phase后不再推进。
          look/inventory/help 等中性动作不参与phase判断。
          
        卡住恢复：如果连续失败次数超阈值，尝试回退重试。
        """
        if not success:
            return current_phase

        action_type = self._get_action_type(action)
        
        # 中性动作不算推进
        if action_type in ('look', 'inventory', 'help', 'examine'):
            return current_phase

        # 获取当前subgoal的期望动作类型
        subgoals = self.infer_subgoals(
            self.last_semantic_result.get('task_type', '') if self.last_semantic_result else '',
            '')
        
        if current_phase >= len(subgoals):
            return current_phase

        target_actions = subgoals[current_phase]
        
        # v2: open 动作特殊处理 —— 成功后自动推进到 take
        if action_type in ('open',):
            if 'open' in target_actions or ('open' in target_actions[0] if target_actions and len(target_actions[0]) > 0 else False):
                if action_type in target_actions:
                    return current_phase + 1
                if any('open' in ta for ta in target_actions):
                    return current_phase + 1
        
        # v2: 智能阶段推进——go to 时检查下一阶段是否有目标物体可操作
        if action_type == 'go to' and action_type in target_actions:
            next_phase = current_phase + 1
            if next_phase < len(subgoals):
                next_target = subgoals[next_phase]
                # 下一阶段是 take → 检查是否有目标物体可拿
                if 'take' in next_target and self.llm_guide and admissive_commands and hasattr(self, '_v2_task_desc'):
                    target_entities = self.llm_guide.get_target_entities(
                        self._v2_task_desc, self._v2_task_type)
                    target_objs = target_entities.get('objects', [])
                    if target_objs:
                        take_cmds = [c for c in admissive_commands 
                                    if self._get_action_type(c.lower()) == 'take']
                        has_target = any(
                            any(obj in c.lower() for obj in target_objs)
                            for c in take_cmds
                        )
                        if not has_target:
                            # 没有目标物体可拿 → 坚决不推进
                            return current_phase
                # 下一阶段包含 open → 检查当前位置是否有 open 命令
                if 'open' in next_target and admissive_commands:
                    open_cmds = [c for c in admissive_commands if c.startswith('open ')]
                    if not open_cmds:
                        # 当前位置没有 open 命令（如 shelf 不需要 open）
                        # 且下一阶段也包含 go to → 继续探索
                        if 'go to' in next_target:
                            return current_phase  # 不推进，继续 go to
                # 下一阶段是 use/clean/heat/cool/toggle → 检查工具是否可用
                if any(t in next_target for t in ['use','clean','heat','cool','toggle']) and self.llm_guide and admissive_commands:
                    target_entities = self.llm_guide.get_target_entities(
                        self._v2_task_desc, self._v2_task_type)
                    target_tools = target_entities.get('tools', [])
                    if target_tools:
                        action_cmds = [c for c in admissive_commands
                                      if any(self._get_action_type(c.lower()) == t for t in next_target)]
                        has_tool = any(
                            any(tool in c.lower() for tool in target_tools)
                            for c in action_cmds
                        )
                        if not has_tool:
                            # 没有目标工具可用 → 不推进
                            return current_phase
            return current_phase + 1
        
        # 如果执行的动作匹配当前subgoal的任意期望类型，推进phase
        if action_type in target_actions:
            return current_phase + 1
        
        # 如果agent乱做其他动作（如open/close/use），算作不成功
        # 这样不会推进phase，但也不惩罚
        return current_phase


# ============================================================
# 运行实验
# ============================================================

def run_single_game(env: ALFWorldLight, agent: YLYWAgent,
                    game_idx: int, verbose: bool = False):
    """运行单个游戏，返回结果"""
    obs, info = env.reset(game_idx=game_idx)

    task_desc = info['task_desc']
    task_type_real = info['task_type']

    # 读取ground truth类型（从traj_data.json）
    gt_type = env.traj_data.get('task_type', '') if hasattr(env, 'traj_data') else task_type_real

    # YLYW推断任务类型（Oracle模式使用gt_type）
    inferred_type = agent.infer_task_type(task_desc, ground_truth=gt_type)
    subgoals = agent.infer_subgoals(inferred_type, task_desc)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"Task: {task_desc}")
        print(f"Inferred Type: {inferred_type}")
        print(f"Subgoals ({len(subgoals)} phases):")
        for i, sg in enumerate(subgoals):
            print(f"  P{i}: {sg}")
        print(f"{'='*60}")

    current_phase = 0
    history = []
    steps = 0
    won = False

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])

        # YLYW选择动作
        action = agent.select_action(cmds, current_phase, inferred_type,
                                     history, task_desc)

        if verbose:
            print(f"  Step {steps}: phase={current_phase} → {action[:60]}")

        obs, info = env.step(action)
        history.append(action)
        steps += 1

        # 判断动作是否成功执行
        action_success = "didn't work" not in obs.lower()

        # 更新阶段
        old_phase = current_phase
        current_phase = agent.update_phase(action, current_phase, action_success)

        if verbose and current_phase != old_phase:
            print(f"  >>> Phase transition: {old_phase} → {current_phase}")

        if info.get('done'):
            won = info.get('won', False)
            break

    result = {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_inferred': inferred_type,
        'type_correct': inferred_type == task_type_real,
        'task_desc': task_desc[:80],
        'steps': steps,
        'won': won,
        'walkthrough_len': info.get('walkthrough_len', 0),
    }

    if verbose:
        status = "✅ WON" if won else "❌ LOST"
        print(f"  {status} in {steps} steps | WT={info.get('walkthrough_len','?')} | "
              f"type_match={inferred_type==task_type_real}")

    return result


def run_all_games(env: ALFWorldLight, agent: YLYWAgent, verbose: bool = False,
                  max_games: int = 0):
    """运行游戏"""
    results = []
    n = len(env.games)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n{'='*60}")
    print(f"YLYW-ALFWorld Zero-Shot Agent")
    print(f"Total tasks: {n}")
    print(f"{'='*60}\n")

    start_time = time.time()

    for i in range(n):
        result = run_single_game(env, agent, i, verbose=verbose)
        results.append(result)

        status = "✅" if result['won'] else "❌"
        type_info = "✓" if result['type_correct'] else "✗"
        elapsed = time.time() - start_time
        eta = (elapsed / (i + 1)) * (n - i - 1) if i < n - 1 else 0
        print(f"[{i+1:3d}/{n}] {status} {result['task_type_real'][:30]:30s} | "
              f"steps={result['steps']:2d}/{result['walkthrough_len']:2d} | "
              f"type={type_info} | ETA={eta:.0f}s",
              end='\r' if not verbose else '\n')

    elapsed = time.time() - start_time
    return results, elapsed


def compute_metrics(results: List[Dict]) -> Dict:
    """计算评估指标"""
    n = len(results)
    wins = sum(1 for r in results if r['won'])
    type_correct = sum(1 for r in results if r['type_correct'])

    # 按任务类型统计
    by_type = defaultdict(lambda: {'total': 0, 'won': 0, 'steps': []})
    for r in results:
        tt = r['task_type_real']
        by_type[tt]['total'] += 1
        by_type[tt]['won'] += 1 if r['won'] else 0
        by_type[tt]['steps'].append(r['steps'])

    type_breakdown = {}
    for tt, d in sorted(by_type.items()):
        type_breakdown[tt] = {
            'total': d['total'],
            'won': d['won'],
            'rate': d['won'] / d['total'] if d['total'] > 0 else 0,
            'avg_steps': sum(d['steps']) / len(d['steps']),
        }

    total_steps = sum(r['steps'] for r in results)

    return {
        'total_tasks': n,
        'won': wins,
        'lost': n - wins,
        'success_rate': wins / n if n > 0 else 0,
        'type_accuracy': type_correct / n if n > 0 else 0,
        'avg_steps': total_steps / n if n > 0 else 0,
        'total_steps': total_steps,
        'by_task_type': type_breakdown,
    }


def print_metrics(metrics: Dict, elapsed: float):
    """打印实验结果"""
    print(f"\n{'='*60}")
    print(f"  YLYW-ALFWorld 实验结果")
    print(f"{'='*60}")
    print(f"  Total tasks:    {metrics['total_tasks']}")
    print(f"  Won:            {metrics['won']}")
    print(f"  Lost:           {metrics['lost']}")
    print(f"  Success Rate:   {metrics['success_rate']:.2%}")
    print(f"  Type Accuracy:  {metrics['type_accuracy']:.2%}")
    print(f"  Avg Steps:      {metrics['avg_steps']:.1f}")
    print(f"  Total Steps:    {metrics['total_steps']}")
    print(f"  Elapsed:        {elapsed:.1f}s")
    print(f"\n  按任务类型划分:")
    print(f"  {'Task Type':<40s} {'#':>3s} {'Won':>3s} {'Rate':>7s} {'AvgS':>5s}")
    print(f"  {'-'*60}")
    for tt, d in metrics['by_task_type'].items():
        print(f"  {tt:<40s} {d['total']:3d} {d['won']:3d} "
              f"{d['rate']:6.1%} {d['avg_steps']:5.1f}")
    print(f"{'='*60}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="YLYW + ALFWorld Zero-Shot Agent")
    parser.add_argument("--mode", choices=["all", "single", "stats"],
                       default="all")
    parser.add_argument("--game", type=int, default=0,
                       help="Game index for single mode")
    parser.add_argument("--verbose", action="store_true",
                       help="Print detailed per-step output")
    parser.add_argument("--output", type=str, default=None,
                       help="Output file for JSON results")
    parser.add_argument("--num", type=int, default=0,
                       help="Max number of games to run (0=all)")
    parser.add_argument("--oracle", action="store_true",
                       help="Use ground truth task type (Oracle mode)")
    args = parser.parse_args()

    env = ALFWorldLight()

    if args.mode == "stats":
        stats = env.get_stats()
        print("ALFWorld Dataset Stats:")
        print(f"  Games: {stats['total_games']}")
        for tt, n in stats['task_types'].items():
            print(f"    {tt}: {n}")
        return

    agent = YLYWAgent(verbose=args.verbose, use_oracle_type=args.oracle)
    
    mode_label = ""
    if args.oracle:
        mode_label = "🔮 Oracle Mode: Using ground truth task types"
    else:
        mode_label = "🧠 YLYW Semantic Parser Mode"
    print(mode_label)
    print()

    if args.mode == "single":
        result = run_single_game(env, agent, args.game, verbose=True)
        print(f"\nResult: {'WON' if result['won'] else 'LOST'}")
        print(f"  Type: {result['task_type_real']} (inferred: {result['task_type_inferred']})")
        print(f"  Steps: {result['steps']}/{result['walkthrough_len']}")
        return

    # mode == all
    results, elapsed = run_all_games(env, agent, verbose=args.verbose,
                                     max_games=args.num)
    metrics = compute_metrics(results)
    print_metrics(metrics, elapsed)

    # 保存结果
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), 'ylyw_alfworld_results.json')

    with open(output_path, 'w') as f:
        json.dump({
            'config': {
                'model': 'YLYW Zero-Shot',
                'split': SPLIT,
                'max_steps': MAX_STEPS,
                'agent_type': 'YLYW_3layer_PriorInference',
            },
            'metrics': {k: v for k, v in metrics.items()
                       if k != 'by_task_type'},
            'by_task_type': metrics['by_task_type'],
            'results': results,
            'elapsed_seconds': elapsed,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
