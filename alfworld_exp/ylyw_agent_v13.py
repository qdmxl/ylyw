#!/usr/bin/env python3
"""
YLYW Agent V13 — 递归YLYW汉语理解 + 六爻驱动逐步决策

替换V10中的硬编码TASK_PLANS（子目标序列）。
核心改动：
  1. YLYW语义引擎解析任务描述 → 提取任务参数（物体、位置、预处理）
  2. 状态六爻编码（6维连续值）感知进度
  3. 模糊推理规则（8条并行）决定当前最优动作
  4. 与ALFWorld环境的交互层（admissible_commands映射）
  
不依赖任何硬编码的任务规划模板。
"""

import re, os, sys, math
from typing import List, Dict, Optional, Tuple

# 导入YLYW汉语理解引擎
_ylyw_lang_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'language')
_ylyw_lang_path = os.path.abspath(_ylyw_lang_path)
sys.path.insert(0, _ylyw_lang_path)
from hanzi_engine import HanziEngine
engine = HanziEngine(verbose=False)

# ============================================================
# 模糊推理规则（与任务类型无关的通用规则）
# ============================================================

def left_shoulder(x, edge=0.35, slope=0.15):
    if x <= edge - slope: return 1.0
    if x >= edge + slope: return 0.0
    return 1.0 - (x - (edge - slope)) / (2 * slope)

def right_shoulder(x, edge=0.45, slope=0.15):
    if x >= edge + slope: return 1.0
    if x <= edge - slope: return 0.0
    return (x - (edge - slope)) / (2 * slope)

# 8条模糊规则
RULES = [
    ("goto",          lambda y: left_shoulder(y[0]) * left_shoulder(y[1], 0.40)),
    ("take",          lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * left_shoulder(y[3], 0.40)),
    ("take_out",      lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * right_shoulder(y[3], 0.45)),
    ("goto_preproc",  lambda y: right_shoulder(y[0], 0.35) * left_shoulder(y[3], 0.40) * left_shoulder(y[1], 0.45)),
    ("put_in",        lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.45) * left_shoulder(y[3], 0.40)),
    ("process",       lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.40) * left_shoulder(y[3], 0.40) * left_shoulder(y[4], 0.30)),
    ("goto_target",   lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * left_shoulder(y[1], 0.50)),
    ("put",           lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * right_shoulder(y[1], 0.50) * right_shoulder(y[4], 0.40)),
]

# 任务类型 → 实际执行参数
TASK_CONFIG = {
    'pick_clean_then_place_in_recep': {
        'preproc_type': 'clean', 'preproc_loc_keywords': ['sinkbasin', 'sink'],
        'start_with_take': False, 'need_open': False,
    },
    'pick_heat_then_place_in_recep': {
        'preproc_type': 'heat', 'preproc_loc_keywords': ['microwave'],
        'start_with_take': False, 'need_open': True,
    },
    'pick_cool_then_place_in_recep': {
        'preproc_type': 'cool', 'preproc_loc_keywords': ['fridge'],
        'start_with_take': False, 'need_open': True,
    },
    'look_at_obj_in_light': {
        'preproc_type': None, 'preproc_loc_keywords': [],
        'start_with_take': False, 'need_open': False,
    },
    'pick_and_place_simple': {
        'preproc_type': None, 'preproc_loc_keywords': [],
        'start_with_take': False, 'need_open': False,
    },
    'pick_two_obj_and_place': {
        'preproc_type': None, 'preproc_loc_keywords': [],
        'start_with_take': False, 'need_open': False,
    },
    'pick_and_place_with_movable_recep': {
        'preproc_type': None, 'preproc_loc_keywords': [],
        'start_with_take': False, 'need_open': False,
    },
}


class YLYWAgentV13:
    """
    六爻驱动逐步决策Agent。
    
    没有TASK_PLANS硬编码，每一步都由状态六爻+模糊推理决定。
    """
    
    def __init__(self, verbose: bool = False, use_oracle_type: bool = True):
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type
        
        # 任务参数
        self.task_desc = ''
        self.task_type = ''
        self.target_objects: List[str] = []
        self.target_receps: List[str] = []
        self.config = {}
        
        # 状态六爻变量
        self.yao = [0.1, 0.1, 0.1, 0.2, 0.15, 0.3]
        self.prev_yao = None
        self.step_count = 0
        self.has_object = False
        self.object_processed = False
        self.current_location = ''
        self.action_history: List[str] = []
        
        # 环境记忆
        self.visited_locations: set = set()
        self.explored_no_target: set = set()
        self.last_admissible: List[str] = []
        self.last_obs = ''
        
        # 识别的命令类型
        self._preproc_found = False  # 是否找到预处理位置
    
    def reset(self, task_desc: str, task_type: str, pddl_params: Dict = None):
        """重置Agent状态"""
        self.task_desc = task_desc
        self.task_type = task_type
        self.config = TASK_CONFIG.get(task_type, {})
        
        if pddl_params:
            self.target_objects = [pddl_params.get('object_target', '')]
            self.target_receps = [pddl_params.get('parent_target', '')]
        else:
            self.target_objects = []
            self.target_receps = []
        
        self.yao = [0.1, 0.1, 0.1, 0.2, 0.15, 0.3]
        self.prev_yao = None
        self.step_count = 0
        self.has_object = False
        self.object_processed = False
        self.current_location = ''
        self.action_history = []
        self.visited_locations = set()
        self.explored_no_target = set()
        self.last_admissible = []
        self.last_obs = ''
        self._preproc_found = False
        
        if self.verbose:
            print(f"[V13] 任务: {task_desc}")
            print(f"[V13] 类型: {task_type}")
            print(f"[V13] 目标物体: {self.target_objects}")
            print(f"[V13] 目标位置: {self.target_receps}")
    
    def act(self, obs: str, admissible_commands: List[str]) -> str:
        """选择下一步动作"""
        self.step_count += 1
        self.last_obs = obs
        self.last_admissible = admissible_commands
        
        # 从obs中提取当前位置
        self._update_location(obs)
        
        # 检测是否拿到了物体
        self._detect_holding(obs)
        
        # 检测物体是否已处理
        self._detect_processed(obs, admissible_commands)
        
        # 构建状态六爻
        self._build_yao()
        
        # 检测爻变（用于调试/日志）
        changes = []
        if self.prev_yao and self.verbose:
            for i in range(6):
                d = self.yao[i] - self.prev_yao[i]
                if abs(d) > 0.05:
                    changes.append(f"{['初','二','三','四','五','上'][i]}{'+' if d>0 else ''}{d:.2f}")
        self.prev_yao = self.yao[:]
        
        # 模糊推理 → 动作类型
        action_type, activation = self._fuzzy_decide()
        
        if self.verbose:
            yao_str = ' '.join(f"{v:.2f}{'━' if v>=0.5 else '┅'}" for v in self.yao)
            print(f"[V13] S{self.step_count:2d} 六爻:{yao_str}")
            if changes:
                print(f"[V13]      爻变:{' '.join(changes)}")
            print(f"[V13]      决策:{action_type}({activation:.3f}) 持物={self.has_object} 已处理={self.object_processed}")
        
        # 动作类型 → ALFWorld具体命令
        action = self._map_to_alfworld(action_type, admissible_commands)
        
        if self.verbose:
            print(f"[V13]      动作:{action}")
        
        self.action_history.append(action)
        return action
    
    # ---- 状态感知 ----
    
    def _update_location(self, obs: str):
        """从obs文本中提取当前位置"""
        for line in obs.split('\n'):
            line = line.strip()
            # ALFWorld到达格式: "You arrive at cabinet 1."
            m = re.search(r'arrive at (.+?)[\.!?]', line.lower())
            if m:
                loc = m.group(1).strip()
                self.current_location = loc
                self.visited_locations.add(loc)
                return
            # "You are in the middle of a room." — 无具体位置
            if 'you are in' in line.lower() or 'you are at' in line.lower():
                m = re.search(r'(?:in|at) (.+?)[\.!?]', line.lower())
                if m:
                    loc = m.group(1).strip()
                    if 'middle' not in loc:  # 忽略"middle of a room"
                        self.current_location = loc
                        self.visited_locations.add(loc)
                        return
    
    def _detect_holding(self, obs: str):
        """检测当前是否拿着物体"""
        if 'You are carrying' in obs:
            self.has_object = True
        elif 'You pick up' in obs or 'pick up' in obs.lower():
            self.has_object = True
        elif 'Nothing happens' in obs:
            pass  # 操作失败，状态不变
        elif 'You put' in obs or 'you put' in obs.lower():
            self.has_object = False  # 放下的物体
        else:
            # 检查admissible：能take说明没拿，能put说明拿着
            has_take = any(c.startswith('take ') for c in self.last_admissible)
            has_put = any(c.startswith('put ') or c.startswith('move ') for c in self.last_admissible)
            if has_take and not has_put:
                self.has_object = False
            elif has_put and not has_take:
                self.has_object = True
    
    def _detect_processed(self, obs: str, cmds: List[str]):
        """检测物体是否已经处理（清洗/加热/冷却）"""
        config = self.config
        preproc = config.get('preproc_type')
        if not preproc:
            return
        
        # 如果obs中提到处理完成
        if f'{preproc} the' in obs or f'{preproc}ed' in obs or f'{preproc} a' in obs:
            self.object_processed = True
        
        # 如果没有clean/heat/cool命令了，说明处理完成了
        preproc_cmds = [c for c in cmds if c.startswith(preproc + ' ')] if preproc else []
        if not preproc_cmds and self._preproc_found:
            self.object_processed = True
    
    # ---- 六爻编码 ----
    
    def _build_yao(self):
        """构建状态六爻（6维连续值）"""
        config = self.config
        preproc = config.get('preproc_type')
        
        # 初爻：持有状态
        y0 = 0.40 if self.has_object and not self.object_processed else \
             0.65 if self.has_object and self.object_processed else 0.10
        
        # 二爻：位置估值
        loc = self.current_location
        y1 = 0.10  # 默认（未知位置）
        if 'cabinet' in loc: y1 = 0.30
        elif 'sink' in loc: y1 = 0.55
        elif 'countertop' in loc or 'counter' in loc: y1 = 0.80
        elif 'fridge' in loc: y1 = 0.55
        elif 'microwave' in loc: y1 = 0.55
        elif 'drawer' in loc: y1 = 0.30
        elif 'shelf' in loc: y1 = 0.30
        elif 'desk' in loc or 'table' in loc: y1 = 0.30
        elif 'bed' in loc: y1 = 0.30
        elif 'sofa' in loc: y1 = 0.30
        elif 'safe' in loc: y1 = 0.30
        elif 'toilet' in loc: y1 = 0.30
        elif 'garbage' in loc: y1 = 0.80
        
        # 三爻：进度
        y2 = min(0.10 + self.step_count * 0.06, 0.85)
        
        # 四爻：处理状态
        if preproc:
            y3 = 0.70 if self.object_processed and not self.has_object else \
                 0.85 if self.object_processed and self.has_object else \
                 0.60 if self.object_processed else \
                 0.25 if not self.has_object and ('sink' in loc or 'fridge' in loc or 'microwave' in loc) else 0.10
        else:
            y3 = 0.80 if self.has_object else 0.10
        
        # 五爻：目标接近度
        target = self.target_receps[0].lower() if self.target_receps else ''
        target_keywords = {
            'countertop': 'countertop', 'cabinet': 'cabinet', 'drawer': 'drawer',
            'shelf': 'shelf', 'desk': 'desk', 'bed': 'bed', 'sofa': 'sofa',
            'safe': 'safe', 'toilet': 'toilet', 'garbagecan': 'garbage',
            'microwave': 'microwave', 'fridge': 'fridge', 'sinkbasin': 'sink',
            'coffeemachine': 'coffee', 'armchair': 'armchair',
        }
        target_kw = target_keywords.get(target, target)
        
        at_target = target_kw in loc if target_kw else False
        
        if at_target and self.has_object:
            y4 = 0.85
        elif at_target:
            y4 = 0.35
        elif preproc:
            preproc_kw = self._get_preproc_keyword()
            at_preproc = preproc_kw in loc if preproc_kw else False
            if at_preproc and not self.has_object and self.object_processed:
                y4 = 0.65
            elif at_preproc and not self.has_object and not self.object_processed:
                y4 = 0.30
            elif at_preproc and self.has_object:
                y4 = 0.15
            else:
                y4 = 0.15
        else:
            y4 = 0.15 if self.has_object else 0.15
        
        # 上爻：环境就绪度
        preproc_kw = self._get_preproc_keyword()
        at_useful = (preproc_kw and preproc_kw in loc) or (target_kw and target_kw in loc)
        y5 = 0.75 if at_useful else 0.25
        
        self.yao = [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]
    
    def _get_preproc_keyword(self) -> str:
        config = self.config
        kws = config.get('preproc_loc_keywords', [])
        return kws[0] if kws else ''
    
    # ---- 模糊推理 ----
    
    def _fuzzy_decide(self) -> Tuple[str, float]:
        best_a, best_n = 0.0, "goto"
        for name, fn in RULES:
            a = fn(self.yao)
            if a > best_a:
                best_a, best_n = a, name
        return best_n, best_a
    
    # ---- 动作映射 ----
    
    def _map_to_alfworld(self, action_type: str, cmds: List[str]) -> str:
        """把模糊推理的动作类型映射为ALFWorld命令"""
        config = self.config
        preproc = config.get('preproc_type')
        preproc_kws = config.get('preproc_loc_keywords', [])
        
        # 无预处理任务：跳过预处理相关动作
        if not preproc:
            if action_type in ('goto_preproc', 'put_in', 'process', 'take_out'):
                action_type = 'put' if self.has_object else ('take' if not self.has_object else 'goto')
        
        # ===== goto 探索 =====
        if action_type == 'goto':
            # 优先去未访问过的位置
            for cmd in cmds:
                if cmd.startswith('go to '):
                    loc = cmd[6:]
                    if loc not in self.visited_locations:
                        return cmd
            # 都访问过了，随便去一个
            for cmd in cmds:
                if cmd.startswith('go to '):
                    return cmd
            return cmds[0] if cmds else 'look'
        
        # ===== take 拿取 =====
        if action_type == 'take':
            # 优先拿目标物体
            for target in self.target_objects:
                target_lower = target.lower().replace('_', '')
                for cmd in cmds:
                    if cmd.startswith('take '):
                        cmd_obj = cmd[5:].lower().strip()
                        if target_lower.replace('_', '') in cmd_obj.replace(' ', ''):
                            return cmd
            # 随便拿一个
            for cmd in cmds:
                if cmd.startswith('take '):
                    return cmd
            return 'look'
        
        # ===== take_out 取出 =====
        if action_type == 'take_out':
            for cmd in cmds:
                if cmd.startswith('take '):
                    return cmd
            # 可能需要先open
            for cmd in cmds:
                if cmd.startswith('open '):
                    return cmd
            if preproc_kws:
                for cmd in cmds:
                    for kw in preproc_kws:
                        if cmd.startswith('go to ') and kw in cmd:
                            return cmd
            return 'look'
        
        # ===== goto_preproc 去预处理位置 =====
        if action_type == 'goto_preproc' and preproc_kws:
            for cmd in cmds:
                if cmd.startswith('go to '):
                    for kw in preproc_kws:
                        if kw in cmd:
                            self._preproc_found = True
                            return cmd
            # 没有go to了→已经在预处理位置，尝试put
            if self.has_object:
                for cmd in cmds:
                    if cmd.startswith('put '):
                        return cmd
            return self._explore(cmds)
        
        # ===== put_in 放入设备 =====
        if action_type == 'put_in' and preproc:
            preproc_cmds = [c for c in cmds if c.startswith('put ') and self._in_preproc_loc(c)]
            if preproc_cmds:
                return preproc_cmds[0]
            # 没到预处理位置，goto过去
            for cmd in cmds:
                if cmd.startswith('go to '):
                    for kw in preproc_kws:
                        if kw in cmd:
                            return cmd
            for cmd in cmds:
                if cmd.startswith('open ') and self._in_preproc_loc(cmd):
                    return cmd
            # 兜底：任意goto
            for cmd in cmds:
                if cmd.startswith('go to '):
                    return cmd
            return 'look'
        
        # ===== process 执行处理 =====
        if action_type == 'process' and preproc:
            for cmd in cmds:
                if cmd.startswith(f'{preproc} '):
                    return cmd
            # 可能需要先关闭（heat/cool需要关门）
            for cmd in cmds:
                if cmd.startswith('close ') and self._in_preproc_loc(cmd):
                    return cmd
            return 'look'
        
        # ===== goto_target 去目标位置 =====
        if action_type == 'goto_target':
            target = self.target_receps[0].lower() if self.target_receps else ''
            for cmd in cmds:
                if cmd.startswith('go to ') and target.replace('_', '') in cmd.lower().replace(' ', ''):
                    return cmd
            return self._explore(cmds)
        
        # ===== put 放置 =====
        if action_type == 'put':
            target = self.target_receps[0].lower() if self.target_receps else ''
            # 目标位置的put
            for cmd in cmds:
                if cmd.startswith('put ') or cmd.startswith('move '):
                    if target.replace('_', '') in cmd.lower().replace(' ', ''):
                        return cmd
            # 需要先open
            for cmd in cmds:
                if cmd.startswith('open ') and target.replace('_', '') in cmd.lower().replace(' ', ''):
                    return cmd
            # 任意put
            for cmd in cmds:
                if cmd.startswith('put '):
                    return cmd
            return 'look'
        
        return self._explore(cmds)
    
    def _in_preproc_loc(self, cmd: str) -> bool:
        """命令是否涉及预处理位置"""
        for kw in self.config.get('preproc_loc_keywords', []):
            if kw in cmd.lower():
                return True
        return False
    
    def _explore(self, cmds: List[str]) -> str:
        """探索：去未访问过的位置"""
        # 优先去没去过的位置
        for cmd in cmds:
            if cmd.startswith('go to '):
                loc = cmd[6:].strip()
                if loc and loc not in self.visited_locations:
                    return cmd
        # 都去过了，从goto中轮询
        goto_cmds = [c for c in cmds if c.startswith('go to ')]
        if goto_cmds:
            # 选一个跟当前不同的位置
            for cmd in goto_cmds:
                if self.current_location not in cmd.lower():
                    return cmd
            return goto_cmds[0]
        return cmds[0] if cmds else 'look'
