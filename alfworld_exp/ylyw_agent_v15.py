#!/usr/bin/env python3
"""
YLYW Agent V15 - 纯 obs-only 逐步决策Agent

核心改造:替代 V10 对 admissible_commands 的依赖,
改用 ObsParser + build_yao + fuzzy_decide + pick_action 的纯 obs 驱动架构。

设计:
  1. TASK_PLANS:任务阶段规划(沿用 V10)
  2. ObsParser:从 obs 文本提取状态
  3. build_yao:状态六爻编码
  4. fuzzy_decide:模糊规则 → 意图
  5. pick_action:意图 + obs → 具体动作命令
  6. update:从 obs 文本检测动作结果(不依赖 info)
"""

import re
import sys
import os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'language'))
from typing import List, Dict, Optional, Tuple, Set


# ═══════════════════════════════════════════════════
# 任务类型 → 子目标序列(全局规划)
# ═══════════════════════════════════════════════════

TASK_PLANS = {
    'look_at_obj_in_light': [
        'find_object', 'take_object', 'find_tool', 'use_tool',
    ],
    'pick_and_place_simple': [
        'find_object', 'take_object', 'find_recep', 'put_object',
    ],
    'pick_clean_then_place_in_recep': [
        'find_object', 'take_object', 'find_tool', 'use_tool', 'find_recep', 'put_object',
    ],
    'pick_heat_then_place_in_recep': [
        'find_object', 'take_object', 'find_tool', 'use_tool', 'find_recep', 'put_object',
    ],
    'pick_cool_then_place_in_recep': [
        'find_object', 'take_object', 'find_tool', 'use_tool', 'find_recep', 'put_object',
    ],
    'pick_two_obj_and_place': [
        'find_object', 'take_object', 'find_recep', 'put_object',
        'find_object_2', 'take_object_2', 'find_recep_2', 'put_object_2',
    ],
    'pick_and_place_with_movable_recep': [
        'find_object', 'take_object', 'find_recep', 'take_recep', 'find_final', 'put_object',
    ],
}

TASK_TOOLS = {
    'look_at_obj_in_light': ['desklamp', 'floorlamp'],
    'pick_clean_then_place_in_recep': ['sinkbasin'],
    'pick_heat_then_place_in_recep': ['microwave'],
    'pick_cool_then_place_in_recep': ['fridge'],
}

# 工具→处理动作映射
TOOL_ACTIONS = {
    'sinkbasin': 'clean',
    'microwave': 'heat',
    'fridge': 'cool',
    'desklamp': 'use',
    'floorlamp': 'use',
}


# ═══════════════════════════════════════════════════
# ObsParser:从 obs 文本提取环境状态
# ═══════════════════════════════════════════════════

class ObsParser:
    """从 ALFWorld obs 文本中提取状态"""

    @staticmethod
    def extract_location(obs_text: str, prev_loc: str = "起点") -> str:
        """提取当前位置(raw 带编号)"""
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                return after[:idx].strip() if idx > 0 else after
        return prev_loc

    @staticmethod
    def parse_observation(obs_text: str, prev_loc: str) -> dict:
        """解析完整状态"""
        result = {
            'location': ObsParser.extract_location(obs_text, prev_loc),
            'visible_objects': [],
            'visible_locations': [],
            'doors': {},
            'inventory': [],
        }
        ol = obs_text.strip().lower()
        ol2 = ol  # 用于re.finditer搜索

        # 位置
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                result['location'] = after[:idx].strip() if idx > 0 else after

        # 可见物体(从"on the X, you see Y")
        ol2 = obs_text.lower()
        for m in re.finditer(r'on the (.+), you see (.+?)(?:\.|$)', ol2):
            items = m.group(2).strip()
            if m:
                items = m.group(2).strip()
                for item in re.finditer(r'(?:a |an )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', items):
                    obj = item.group(1).strip()
                    if obj not in ('a', 'an'):
                        result['visible_objects'].append(f"{obj} {item.group(2)}")


        # 容器内物体:"In it, you see ..."
        m2 = re.search(r'in it, you see (.+)', ol)
        if m2:
            items = m2.group(1).strip()
            for item in re.finditer(r'(?:a |an )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', items):
                obj = item.group(1).strip()
                if obj not in ('a', 'an'):
                    result['visible_objects'].append(f"{obj} {item.group(2)}")

        # 初始可见位置列表
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if 'looking quickly around you, you see' in l:
                parts = l.split('you see')[-1].strip().rstrip('.')
                if parts.startswith('a '): parts = parts[2:]
                items = re.split(r', |, and | and ', parts)
                for item in items:
                    item = item.strip().lstrip('a ').lstrip('an ')
                    m = re.match(r'([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', item)
                    if m:
                        name = m.group(1).strip()
                        if name in ('cabinet','countertop','drawer','shelf','desk','lamp',
                                    'coffeemachine','fridge','microwave','sinkbasin','garbagecan',
                                    'bed','sofa','safe','toilet','armchair','diningtable',
                                    'stoveburner','toaster','floorlamp','desk lamp',
                                    'laundryhamper','bathtub','ottoman','cart',
                                    'dresser','tvstand','sidetable','coffeetable',
                                    'handtowelholder','toiletpaperhanger','towelholder',
                                    'panshelf','potdryingrack',):
                            result['visible_locations'].append(f"{name} {m.group(2)}")
                        else:
                            result['visible_objects'].append(f"{name} {m.group(2)}")

        # 容器状态
        for m in re.finditer(r'the ([a-z]+(?:\s+\d+)?) is (closed|open)', ol):
            result['doors'][m.group(1).strip()] = m.group(2).strip()

        # 库存
        if 'you are carrying' in ol:
            inv_text = [l for l in obs_text.split('\n') if 'carrying' in l.lower()]
            if inv_text:
                items = re.findall(r'([a-z]+)\s+(\d+)', inv_text[0].lower())
                result['inventory'] = [f"{n} {i}" for n, i in items]
        if 'you pick up' in ol:
            m = re.search(r'you pick up (?:the |a )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', ol)
            if m:
                obj_full = f"{m.group(1)} {m.group(2)}"
                if obj_full not in result['inventory']:
                    result['inventory'].append(obj_full)

        return result

    @staticmethod
    def norm(s: str) -> str:
        if not s: return ""
        return re.sub(r'\s+\d+$', '', s.strip().lower())

    @staticmethod
    def key(s: str) -> str:
        if not s: return ""
        return s.strip().lower()


# ═══════════════════════════════════════════════════
# 六爻 + 模糊推理(与 V14 一致)
# ═══════════════════════════════════════════════════

def lsh(x, e=0.35, s=0.15):
    if x <= e-s: return 1.0
    if x >= e+s: return 0.0
    return 1.0-(x-(e-s))/(2*s)

def rsh(x, e=0.45, s=0.15):
    if x >= e+s: return 1.0
    if x <= e-s: return 0.0
    return (x-(e-s))/(2*s)

RULES = [
    # 优先级:拿取 > 放置 > 取出 > 放入设备 > 执行处理 > 去预处理 > 去目标 > 探索
    ("拿取",     lambda y: lsh(y[0])*rsh(y[1],0.30)*lsh(y[3],0.50)),
    ("放置",     lambda y: rsh(y[0],0.30)*rsh(y[3],0.45)*rsh(y[1],0.50)*rsh(y[4],0.40)),
    ("取出",     lambda y: lsh(y[0])*rsh(y[1],0.35)*rsh(y[3],0.45)),
    ("放入设备", lambda y: rsh(y[0],0.30)*rsh(y[1],0.45)*lsh(y[3],0.40)),
    ("执行处理", lambda y: lsh(y[0])*rsh(y[1],0.40)*lsh(y[3],0.40)*lsh(y[4],0.30)),
    ("去预处理", lambda y: rsh(y[0],0.35)*lsh(y[3],0.40)*lsh(y[1],0.45)),
    ("去目标",   lambda y: rsh(y[0],0.35)*rsh(y[3],0.45)*lsh(y[1],0.50)),
    ("goto探索", lambda y: lsh(y[0])*lsh(y[1],0.50)),
]

def fuzzy_decide(yao):
    bn, ba = "goto探索", 0.0
    for n, fn in RULES:
        a = fn(yao)
        if a > ba: bn, ba = n, a
    return bn, round(ba, 4)


def build_yao(loc_norm: str, has_inv: bool, processed: bool, step: int,
              preproc_en: str, target_norm: str, at_target: bool = False) -> list:
    y0 = 0.10 if not has_inv else (0.85 if processed else 0.70)
    lm = {"起点": 0.10}
    if preproc_en: lm[preproc_en] = 0.60
    if target_norm: lm[target_norm] = 0.85
    for k in ["cabinet","countertop","drawer","shelf","desk","bed","sofa","safe",
              "toilet","armchair","sinkbasin","garbagecan","microwave","fridge",
              "coffeemaker","diningtable","lamp","stoveburner","toaster"]:
        if k not in lm: lm[k] = 0.40
    y1 = lm.get(loc_norm, 0.25)
    if at_target: y1 = max(y1, 0.80)
    y2 = min(0.10 + step * 0.06, 0.85)
    if not preproc_en:
        y3 = 0.80 if has_inv else 0.10
        y4 = 0.90 if has_inv and at_target else (0.40 if at_target else 0.10)
    else:
        if not has_inv and not processed: y3 = 0.10
        elif has_inv and not processed: y3 = 0.25 if loc_norm == preproc_en else 0.15
        elif not has_inv and processed: y3 = 0.70 if loc_norm == preproc_en else 0.60
        elif has_inv and processed: y3 = 0.85 if loc_norm == preproc_en else 0.80
        else: y3 = 0.10
        y4 = 0.15
        if at_target and has_inv and processed: y4 = 0.90
        elif at_target: y4 = 0.40
    y5 = 0.75 if loc_norm in ([preproc_en, target_norm] if preproc_en else [target_norm]) else 0.35
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


# ═══════════════════════════════════════════════════
# 动作构造(从意图 + obs 状态 → 具体 ALFWorld 命令)
# ═══════════════════════════════════════════════════

def pick_action(intent: str, obs_state: dict, target_info: dict,
                visited_keys: set, loc_norm: str, holding: Optional[str] = None) -> str:
    """
    根据意图生成具体动作命令。
    完全不使用 admissible_commands。
    """
    loc_raw = obs_state['location']
    # 优先使用agent的holding状态(obs中可能没有carrying信息)
    inv = [holding] if holding else obs_state['inventory']
    vis_objs = obs_state['visible_objects']
    vis_locs = obs_state['visible_locations']
    doors = obs_state['doors']

    obj_en = target_info.get('obj_en', '')
    target_en = target_info.get('target_en', '')
    preproc_en = target_info.get('preproc_en', '')
    task_type = target_info.get('task_type', '')

    # ──── goto探索(系统性搜索所有位置)────
    if intent == "goto探索":
        # 优先使用已知位置列表(所有cabinet/drawer/shelf/countertop)
        known_all = []
        # 位置类型→卦象映射（基于八卦天然语义）
        # 坤(地/载)→承载面；艮(山/止)→容器；坎(水)→水域/冷；离(火/明)→热/光
        location_bagua = {
            'countertop': ['坤'], 'shelf': ['坤'], 'desk': ['坤'],
            'diningtable': ['坤'], 'coffeetable': ['坤'], 'sidetable': ['坤'],
            'cabinet': ['艮'], 'drawer': ['艮'], 'safe': ['艮'],
            'sinkbasin': ['坎'], 'fridge': ['坎'], 'bathtub': ['坎'],
            'microwave': ['离'], 'stoveburner': ['离'], 'toaster': ['离'],
            'desklamp': ['离'], 'floorlamp': ['离'], 'lamp': ['离'],
            'bed': ['震'], 'sofa': ['震'], 'armchair': ['震'],
            'garbagecan': ['坤'], 'laundryhamper': ['坤'],
            'toilet': ['坎'], 'coffeemachine': ['艮'],
        }
        # 基于物体语义推断位置偏好
        obj_en_lower = (obj_en or '').lower()
        obj_bagua_prefs = []
        # 英文物体名→卦象映射（无需HanziEngine，直接用语义映射）
        en_to_bagua = {
            'plate':'坤','bowl':'坤','cup':'坤','mug':'坤','apple':'坤','potato':'坤',
            'tomato':'坤','egg':'坤','bread':'坤','lettuce':'坤','pan':'离','pot':'离',
            'knife':'兑','spoon':'坎','fork':'震','spatula':'震','book':'艮','pencil':'坤',
            'soapbar':'坤','soapbottle':'坤','cloth':'坤','towel':'坤','watch':'坤',
            'bottle':'坤','box':'艮','cd':'艮','newspaper':'坤','laptop':'艮',
            'cellphone':'离','keychain':'坤','remotecontrol':'坎','statue':'艮',
            'vase':'坤','pillow':'坤','candle':'离','milk':'坎','coffee':'离',
        }
        dom = en_to_bagua.get(obj_en_lower, '坤')  # 默认坤
        obj_bagua_prefs.append(dom)
        
        # 按卦象匹配度排序位置优先级
        scored_locs = []
        # 知几位置先验
        zhiji_boosts = obs_state.get('zhiji_boosts', {})
        for prefix, guas in location_bagua.items():
            match_score = 0
            for obg in obj_bagua_prefs:
                if obg in guas:
                    match_score += 3
            # 开放平面优先（直接可见，不需要open）
            if prefix in ('countertop','desk','shelf','diningtable'):
                match_score += 1
            # 容器类需要open，降低优先级
            if prefix in ('cabinet','drawer','safe'):
                match_score += 0
            # 知几位置先验叠加
            if prefix in zhiji_boosts:
                match_score += zhiji_boosts[prefix]
            scored_locs.append((match_score, prefix))
        scored_locs.sort(key=lambda x: -x[0])
        priority_order = [p for _, p in scored_locs]
        
        # 按优先级生成位置列表
        for prefix in priority_order:
            if prefix in ('cabinet',):
                for n in range(6, 0, -1):
                    known_all.append(f"{prefix} {n}")
            elif prefix in ('shelf', 'desk'):
                for n in range(6, 0, -1):
                    known_all.append(f"{prefix} {n}")
            elif prefix in ('drawer',):
                for n in range(3, 0, -1):
                    known_all.append(f"{prefix} {n}")
            elif prefix in ('countertop',):
                for n in range(3, 0, -1):
                    known_all.append(f"{prefix} {n}")
            else:
                for n in range(1, 3):
                    known_all.append(f"{prefix} {n}")
        # 特殊名:desk lamp 和 floor lamp
        known_all.append('desklamp 1')
        known_all.append('lamp 1')
        # 加上当前obs中的可见位置
        known_all += [l for l in vis_locs if l not in known_all]
        # 去目标或预处理
        if target_en:
            for n in range(1, 4):
                target_candidate = f"{target_en} {n}"
                if target_candidate not in known_all:
                    known_all.append(target_candidate)
        if preproc_en:
            preproc_candidate = f"{preproc_en} 1"
            if preproc_candidate not in known_all:
                known_all.append(preproc_candidate)

        # 按顺序找第一个未访问的位置
        for loc_candidate in known_all:
            if ObsParser.key(loc_candidate) not in visited_keys:
                return f"go to {loc_candidate}"

        # 都去过了,去目标或预处理器
        if target_en: return f"go to {target_en} 1"
        if preproc_en: return f"go to {preproc_en} 1"
        if vis_locs: return f"go to {vis_locs[0]}"
        return "look"

    # ──── 拿取 ────
    if intent == "拿取":
        # 检查当前位置容器是否要 open
        loc_base = ObsParser.norm(loc_raw)
        for loc_name, state in doors.items():
            if state == 'closed' and loc_name in loc_raw:
                return f"open {loc_name}"
        # 有可见物体 → 在所有可见物体中搜索匹配目标物体的
        if vis_objs:
            matched_obj = None
            for obj in vis_objs:
                obj_base = ObsParser.norm(obj)
                name_match = False
                if obj_en:
                    name_match = (obj_en in obj_base or obj_base in obj_en)
                if not name_match:
                    # pick_two: 在所有物体中搜索匹配
                    if task_type == 'pick_two_obj_and_place':
                        cn2en_name = {'肥皂':'soapbar','soap':'soapbar','soapbar':'soapbar',
                                      '两块肥皂':'soapbar','肥皂块':'soapbar'}
                        for cn, en in cn2en_name.items():
                            if cn in (obj_en or '') and en in (obj_base or ''):
                                name_match = True
                                break
                        if not name_match:
                            obj_cn = target_info.get('obj_cn', '')
                            for cn, en in cn2en_name.items():
                                if (cn in (obj_cn or '') or cn in (obj_en or '')) and en in (obj_base or ''):
                                    name_match = True
                                    break
                    # look_at: 有标准物体名时才放宽匹配
                    if task_type == 'look_at_obj_in_light':
                        if obj_en and obj_en not in ('灯','光',''):
                            name_match = True
                if name_match:
                    matched_obj = obj
                    break
            if matched_obj:
                if loc_raw and loc_raw != "起点":
                    return f"take {matched_obj} from {loc_raw}"
                return f"take {matched_obj}"
            # 一个都不匹配→继续搜索
            return pick_action("goto探索", obs_state, target_info, visited_keys, loc_norm, holding)
        return pick_action("goto探索", obs_state, target_info, visited_keys, loc_norm, holding)

    # ──── 取出 ────
    if intent == "取出":
        if vis_objs:
            obj = vis_objs[0]
            if loc_raw and loc_raw != "起点":
                return f"take {obj} from {loc_raw}"
            return f"take {obj}"
        # 打开预处理设备
        for loc_name, state in doors.items():
            if state == 'closed' and preproc_en and preproc_en in loc_name:
                return f"open {loc_name}"
        return "look"

    # ──── 去预处理 ────
    if intent == "去预处理":
        if preproc_en:
            return f"go to {preproc_en} 1"
        if vis_locs:
            return f"go to {vis_locs[0]}"
        return "look"

    # ──── 放入设备 ────
    if intent == "放入设备":
        # sinkbasin/fridge/microwave 都不需要先放入,直接处理
        if inv:
            obj = inv[0]
            if preproc_en == 'sinkbasin':
                return f"clean {obj} with {preproc_en} 1"
            elif preproc_en == 'fridge':
                return f"cool {obj} with {preproc_en} 1"
            elif preproc_en == 'microwave':
                return f"heat {obj} with {preproc_en} 1"
            else:
                return f"put {obj} in/on {preproc_en} 1"
        for loc_name, state in doors.items():
            if state == 'closed' and preproc_en and preproc_en in loc_name:
                return f"open {loc_name}"
        return "look"

    # ──── 执行处理 ────
    if intent == "执行处理":
        if task_type == 'look_at_obj_in_light':
            # look_at: 先确保在 desk 1 位置（灯在 desk 1 上）
            loc_base = ObsParser.norm(loc_raw)
            if 'desk 1' not in loc_raw and 'desk 1' not in loc_raw.split():
                for n in [1, 2]:
                    c = f"desk {n}"
                    if ObsParser.key(c) not in visited_keys:
                        return f"go to {c}"
            return "use desklamp 1"
        # ALFWorld 格式: clean <obj> with <tool>
        if inv:
            obj = inv[0]
            if preproc_en:
                action_word = TOOL_ACTIONS.get(preproc_en, 'clean')
                return f"{action_word} {obj} with {preproc_en} 1"
            return "clean"
        for loc_name, state in doors.items():
            if state == 'closed' and preproc_en and preproc_en in loc_name:
                return f"open {loc_name}"
        return "look"

    # ──── 去目标 ────
    if intent == "去目标":
        if task_type == 'look_at_obj_in_light':
            # look_at: 灯在desk上,不是独立位置
            for prefix in ['desk', 'desk']:
                for n in range(1, 4):
                    c = f"{prefix} {n}"
                    if ObsParser.key(c) not in visited_keys:
                        return f"go to {c}"
            if vis_locs: return f"go to {vis_locs[0]}"
            return "look"
        if target_en:
            candidates = [f"{target_en} 1", f"{target_en} 2"]
            for c in candidates:
                if ObsParser.key(c) not in visited_keys:
                    return f"go to {c}"
            return f"go to {candidates[0]}"
        if vis_locs:
            return f"go to {vis_locs[0]}"
        return "look"

    # ──── 放置 ────
    if intent == "放置":
        if inv:
            obj = inv[0]
            if target_en:
                return f"move {obj} to {target_en} 1"
            return f"move {obj} to {loc_raw}"
        for loc_name, state in doors.items():
            if state == 'closed' and target_en and target_en in loc_name:
                return f"open {loc_name}"
        return "look"

    return "look"


# ═══════════════════════════════════════════════════
# YLYWAgentV15
# ═══════════════════════════════════════════════════

class YLYWAgentV15:
    """
    纯 obs-only 逐步决策 Agent。

    核心设计:
      1. TASK_PLANS 阶段规划(宽泛指导,可动态偏离)
      2. ObsParser 从 obs 提取状态
      3. build_yao + fuzzy_decide + pick_action 每步闭环决策
      4. update 从 obs 检测动作结果
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # 任务信息
        self.task_type = ''
        self.target_objects: List[str] = []
        self.target_receps: List[str] = []
        self.target_tools: List[str] = []

        # 阶段规划
        self.plan: List[str] = []
        self.phase = 0

        # 状态追踪
        self.holding: Optional[str] = None
        self.processed = False
        self.current_location = ''
        self.visited: Set[str] = set()
        self.opened_containers: Set[str] = set()
        self.last_action = ''
        self.step_count = 0

        # 滞后检测:从 obs 文本检测动作结果
        self._pending_process = False
        self._pending_put = False
        self._zhiji = None  # 知几学习引擎

    def set_zhiji(self, zhiji):
        """注入知几学习引擎"""
        self._zhiji = zhiji

    def reset(self, task_desc: str, task_type: str):
        """新游戏--使用HanziEngine中文理解解析任务"""
        self.task_type = task_type
        self.task_desc = task_desc
        self.plan = list(TASK_PLANS.get(task_type,
                         ['find_object', 'take_object', 'find_recep', 'put_object']))
        self.phase = 0
        self.holding = None
        self.processed = False
        self.current_location = ''
        self.visited = set()
        self.visited.add("起点")
        self.opened_containers = set()
        self.last_action = ''
        self.step_count = 0
        self._pending_process = False
        self._pending_put = False
        self._known_locations = []  # 初始可见位置列表(持久记忆)
        self._is_two_task = False  # 是否是pick_two任务
        self._placed_count = 0  # 已放置物体计数(pick_two用)

        # ═══ 核心改造:用HanziEngine中文替代task_desc_parser英文规则 ═══
        self._parse_task_with_hanzi(task_desc, task_type)

        # 生成 target_info
        self._build_target_info()

    def _task_en_to_cn_params(self, task_en: str) -> tuple:
        """
        从英文 task_desc 提取关键参数并翻译为中文。
        返回 (task_cn, obj_cn, loc_cn, preproc_cn, task_type_cn)
        """
        desc = task_en.lower().strip()

        # 物体和容器词典(保持原样)
        en2cn_obj = {
            'plate':'盘子','bowl':'碗','cup':'杯子','mug':'杯子',
            'apple':'苹果','potato':'土豆','tomato':'番茄',
            'egg':'鸡蛋','bread':'面包','lettuce':'生菜',
            'soap':'肥皂','soapbar':'肥皂','sponge':'海绵',
            'knife':'刀','spoon':'勺子','fork':'叉子','spatula':'锅铲',
            'pan':'锅','pot':'锅','book':'书','pencil':'铅笔',
            'pen':'铅笔','newspaper':'报纸','laptop':'笔记本',
            'cellphone':'手机','keychain':'钥匙链',
            'remotecontrol':'遥控器','statue':'雕像','vase':'花瓶',
            'pillow':'枕头','towel':'毛巾','cloth':'抹布','watch':'手表',
            'bottle':'瓶子','box':'盒子','cd':'光盘','glassbottle':'玻璃瓶',
            'winebottle':'酒瓶','alarmclock':'闹钟','baseballbat':'棒球棒',
            'basketball':'篮球','dishsponge':'洗碗海绵',
            'peppershaker':'胡椒瓶','saltshaker':'盐瓶','scrubbrush':'刷子',
            'spraybottle':'喷壶','tissuebox':'纸巾盒','toiletpaper':'卫生纸',
            'butterknife':'黄油刀','creditcard':'信用卡','plunger':'皮搋子',
            'soapbottle':'洗手液瓶','candle':'蜡烛','statue':'雕像',
            'ladle':'汤勺','kettle':'水壶','milk':'牛奶','coffee':'咖啡',
            'breadsliced':'面包','applesliced':'苹果','potatosliced':'土豆',
            'tomatosliced':'番茄','lettucesliced':'生菜','food':'食物',
        }
        en2cn_loc = {
            'countertop':'柜台','cabinet':'柜子','drawer':'抽屉',
            'shelf':'架子','desk':'桌子','bed':'床','sofa':'沙发',
            'safe':'保险箱','toilet':'马桶','sinkbasin':'水槽',
            'sink':'水槽','fridge':'冰箱','microwave':'微波炉',
            'garbagecan':'垃圾桶','garbage':'垃圾桶','trash':'垃圾桶',
            'bin':'垃圾桶','coffeemachine':'咖啡机','diningtable':'餐桌',
            'desk lamp':'台灯','desk l':'台灯','floorlamp':'落地灯',
            'lamp':'灯','coffeetable':'咖啡桌','stoveburner':'灶台',
            'toaster':'烤面包机','bathtub':'浴缸','armchair':'扶手椅',
            'laundryhamper':'洗衣篮','ottoman':'脚凳','cart':'推车',
            'tvstand':'电视柜','sidetable':'边桌','drier':'烘干机',
        }
        en2cn_verb = {
            'clean':'洗干净','wash':'洗干净','rinse':'洗干净',
            'heat':'加热','warm':'加热','cook':'加热',
            'cool':'冷却','chill':'冷却','chilled':'冷却','freeze':'冷却',
            'look at':'看看','examine':'看看','turn on':'打开灯',
            'put':'','place':'','move':'',
        }

        # 提取物体名
        obj_cn = ''
        loc_cn = ''
        for en, cn in sorted(en2cn_obj.items(), key=lambda x: -len(x[0])):
            if en in desc:
                obj_cn = cn
                break

        # 提取位置名(注意sinkbasin和sink都要匹配,优先长词)
        for en, cn in sorted(en2cn_loc.items(), key=lambda x: -len(x[0])):
            if en in desc:
                loc_cn = cn
                break

        # 提取动词
        action_cn = ''
        for en, cn in sorted(en2cn_verb.items(), key=lambda x: -len(x[0])):
            if en in desc and cn:
                action_cn = cn
                break

        # 检测是否为two
        self._is_two_task = any(kw in desc for kw in ['two','both','2'])
        has_two = self._is_two_task
        two_str = '两块' if has_two else ''

        # 检测灯
        has_lamp = any(kw in desc for kw in ['lamp','light','examine','look at'])

        loc_prep = '里' if any(k in desc for k in ['cabinet','drawer','microwave','fridge','garbagecan',
                                                    'sinkbasin','safe','toilet']) else '上'

        # 构建中文任务描述
        if has_lamp and not any(kw in desc for kw in ['clean','wash','rinse','heat','cook','cool','chill']):
            # 找灯的物体名(可能是cellphone/mug/book等)
            lamp_obj = obj_cn
            if not lamp_obj:
                # 从英文描述提取(examine/look at A using lamp)
                m = re.search(r'(?:examine|look at)\s+(?:a |an |the )?([a-z]+)', desc)
                if m:
                    lamp_obj = m.group(1)
                    # 翻译为中文
                    for en, cn in sorted(en2cn_obj.items(), key=lambda x: -len(x[0])):
                        if en in lamp_obj:
                            lamp_obj = cn
                            break
            if lamp_obj:
                task_cn = f'用灯的光看看{lamp_obj}'
            else:
                task_cn = f'看看灯'
        elif action_cn:
            task_cn = f'把{two_str}{obj_cn}{action_cn}后放到{loc_cn}{loc_prep}'
        elif has_two:
            task_cn = f'把{two_str}{obj_cn}放到{loc_cn}{loc_prep}'
        else:
            task_cn = f'把{obj_cn}放到{loc_cn}{loc_prep}'

        return task_cn, obj_cn, loc_cn, action_cn, has_two, has_lamp

    def _parse_task_with_hanzi(self, task_desc: str, task_type: str):
        """
        用HanziEngine中文理解解析任务参数。
        替代原来的 task_desc_parser(英文规则匹配)。

        两步:
          1. 从英文task_desc提取关键参数(物体、位置、动作)→ 翻译为中文
          2. HanziEngine理解中文任务描述 → 提取语义信息
        """
        # Step 1: 英文→中文参数提取
        task_cn, obj_cn, loc_cn, action_cn, has_two, has_lamp = self._task_en_to_cn_params(task_desc)

        # 保存中文参数
        self._obj_cn = obj_cn
        self._loc_cn = loc_cn
        self._action_cn = action_cn

        # Step 2: HanziEngine中文理解
        from hanzi_engine import HanziEngine
        engine = HanziEngine(verbose=False)
        result = engine.sentence(task_cn)

        segs = result['segments']
        roles = result['segment_role']
        main_hex = result['main_hexagram']
        dominant = result['dominant_bagua']

        # Step 3: 从中文理解结果中提取目标物体和位置
        loc_keywords = {'柜台','柜子','水槽','冰箱','微波炉','架子','桌子','台子',
                        '垃圾桶','床','沙发','保险箱','马桶','扶手椅','抽屉',
                        '台灯','落地灯','咖啡机','餐桌','灶台'}

        self.target_objects = []
        self.target_receps = []

        for i, seg in enumerate(segs):
            role = roles[i]
            if role == '物体':
                is_loc = any(lk in seg for lk in loc_keywords)
                if is_loc:
                    loc_clean = seg
                    for sfx in ['上','里','下','旁','边']:
                        if loc_clean.endswith(sfx):
                            loc_clean = loc_clean[:-len(sfx)]
                            break
                    self.target_receps.append(loc_clean)
                else:
                    self.target_objects.append(seg)

        # 用英文提取的作为后备/修正
        if obj_cn and (not self.target_objects or self.target_objects[0] in ('灯','光')):
            self.target_objects = [obj_cn]
        if loc_cn and (not self.target_receps or self.target_receps[0] != loc_cn):
            if loc_cn not in self.target_receps:
                self.target_receps.append(loc_cn)
        
        # 知几学习：用积累的同义词扩展目标物体
        if hasattr(self, '_zhiji') and self._zhiji is not None:
            expanded = self._zhiji.get_expanded_objects(self.target_objects)
            if expanded != self.target_objects:
                if self.verbose:
                    print(f"  [知几] 目标扩展: {self.target_objects} → {expanded}")
                self.target_objects = expanded
        
        # Step 4: 任务类型推断
        verb_text = ''.join([segs[i] for i in range(len(segs)) if roles[i] == '动作'])
        need_clean = any(w in verb_text for w in ['洗','干净','清'])
        need_heat = any(w in verb_text for w in ['热','加']) and '冷' not in verb_text
        need_cool = any(w in verb_text for w in ['冷','冰','凉'])
        need_light = has_lamp and not need_clean and not need_heat and not need_cool

        if has_two: self.task_type = 'pick_two_obj_and_place'
        elif need_light: self.task_type = 'look_at_obj_in_light'
        elif need_clean: self.task_type = 'pick_clean_then_place_in_recep'
        elif need_heat: self.task_type = 'pick_heat_then_place_in_recep'
        elif need_cool: self.task_type = 'pick_cool_then_place_in_recep'
        elif dominant == '离': self.task_type = 'pick_heat_then_place_in_recep'
        elif dominant == '坎': self.task_type = 'pick_cool_then_place_in_recep'
        elif dominant == '兑': self.task_type = 'pick_clean_then_place_in_recep'
        else: self.task_type = task_type

        self.target_tools = list(TASK_TOOLS.get(self.task_type, []))

        if self.verbose:
            print(f"  [Hanzi] 中文: {task_cn}")
            print(f"  [Hanzi] 分词: {segs}")
            print(f"  [Hanzi] 角色: {roles}")
            print(f"  [Hanzi] 卦象: {main_hex}({dominant})")
            print(f"  [Hanzi] 物体: {self.target_objects}, 位置: {self.target_receps}")
            print(f"  [Hanzi] 类型: {self.task_type}")

    def _build_target_info(self):
        """构造 target_info 字典(中→英映射)"""
        # 中文→英文位置映射
        cn2en_loc = {
            '柜台':'countertop', '柜子':'cabinet', '抽屉':'drawer',
            '架子':'shelf', '桌子':'desk', '水槽':'sinkbasin',
            '冰箱':'fridge', '微波炉':'microwave', '垃圾桶':'garbagecan',
            '床':'bed', '沙发':'sofa', '保险箱':'safe', '马桶':'toilet',
            '扶手椅':'armchair', '台灯':'desklamp', '落地灯':'floorlamp',
            '咖啡机':'coffeemachine', '餐桌':'diningtable', '灶台':'stoveburner',
        }
        # 中文→英文物体映射
        cn2en_obj = {
            '盘子':'plate', '碗':'bowl', '杯子':'mug',
            '苹果':'apple', '土豆':'potato', '番茄':'tomato',
            '鸡蛋':'egg', '面包':'bread', '生菜':'lettuce',
            '肥皂':'soapbar', '海绵':'dishsponge', '刀':'knife',
            '勺子':'spoon', '叉子':'fork', '锅铲':'spatula',
            '锅':'pan', '书':'book', '铅笔':'pencil',
            '报纸':'newspaper', '笔记本':'laptop', '手机':'cellphone',
            '钥匙链':'keychain', '遥控器':'remotecontrol',
            '雕像':'statue', '花瓶':'vase', '枕头':'pillow',
            '毛巾':'towel', '抹布':'cloth', '手表':'watch',
            '瓶子':'bottle', '盒子':'box', '光盘':'cd',
            '玻璃瓶':'glassbottle', '酒瓶':'winebottle',
            '闹钟':'alarmclock', '棒球棒':'baseballbat',
            '篮球':'basketball', '洗碗海绵':'dishsponge',
            '胡椒瓶':'peppershaker', '盐瓶':'saltshaker',
            '刷子':'scrubbrush', '喷壶':'spraybottle',
            '纸巾盒':'tissuebox', '卫生纸':'toiletpaper',
            '黄油刀':'butterknife', '信用卡':'creditcard',
            '皮搋子':'plunger', '洗手液瓶':'soapbottle',
        }

        preproc_en = ''
        if self.task_type == 'pick_clean_then_place_in_recep':
            preproc_en = 'sinkbasin'
        elif self.task_type == 'pick_heat_then_place_in_recep':
            preproc_en = 'microwave'
        elif self.task_type == 'pick_cool_then_place_in_recep':
            preproc_en = 'fridge'

        # 将中文位置/物体名映射为英文
        # 优先从英文task_desc中提取原始英文名(更准确)
        target_en = ''
        obj_en = ''
        desc_lower = self.task_desc.lower()

        # 英文物体名提取
        en2en_obj = {'plate':'plate','bowl':'bowl','cup':'cup','mug':'mug',
                     'apple':'apple','potato':'potato','tomato':'tomato',
                     'egg':'egg','bread':'bread','lettuce':'lettuce',
                     'soap':'soapbar','soapbar':'soapbar','sponge':'dishsponge',
                     'knife':'knife','spoon':'spoon','fork':'fork','spatula':'spatula',
                     'pan':'pan','pot':'pot','book':'book','pencil':'pencil',
                     'pen':'pencil','newspaper':'newspaper','laptop':'laptop',
                     'cellphone':'cellphone','keychain':'keychain',
                     'remotecontrol':'remotecontrol','statue':'statue','vase':'vase',
                     'pillow':'pillow','towel':'towel','cloth':'cloth','watch':'watch',
                     'bottle':'bottle','box':'box','cd':'cd',
                     'winebottle':'winebottle','alarmclock':'alarmclock',
                     'baseballbat':'baseballbat','basketball':'basketball',
                     'peppershaker':'peppershaker','saltshaker':'saltshaker',
                     'scrubbrush':'scrubbrush','spraybottle':'spraybottle',
                     'tissuebox':'tissuebox','toiletpaper':'toiletpaper',
                     'butterknife':'butterknife','creditcard':'creditcard',
                     'plunger':'plunger','toaster':'toaster','candle':'candle',
                     'glassbottle':'glassbottle',
                     'milk':'milk','coffee':'coffee','food':'food',
                     'lettuce sliced':'lettuce','lettucesliced':'lettuce',
                     'bread sliced':'bread','breadsliced':'bread',
                     'potato sliced':'potato','potatosliced':'potato',
                     'tomato sliced':'tomato','tomatosliced':'tomato',
                     'apple sliced':'apple','applesliced':'apple',
                     'papers':'newspaper','rolls':'papertowelroll',
                     'pencil':'pencil','pen':'pencil','cloth':'cloth',
                     'soapbottle':'soapbottle','handtowel':'handtowel',
                     'laundryhamper':'laundryhamper','ladle':'ladle',
                     'kettle':'kettle','dishsponge':'dishsponge',
        }
        for en, std in sorted(en2en_obj.items(), key=lambda x: -len(x[0])):
            if en in desc_lower:
                obj_en = std
                break

        en2en_loc = {'countertop':'countertop','counter':'countertop','cabinet':'cabinet','drawer':'drawer',
                     'shelf':'shelf','desk':'desk','sinkbasin':'sinkbasin',
                     'fridge':'fridge','microwave':'microwave','garbagecan':'garbagecan',
                     'bed':'bed','sofa':'sofa','safe':'safe','toilet':'toilet',
                     'armchair':'armchair','desklamp':'desklamp','desk lamp':'desklamp',
                     'floorlamp':'floorlamp','lamp':'desklamp','desk lamp':'desklamp',
                     'desklamp':'desklamp','coffeemachine':'coffeemachine',
                     'diningtable':'diningtable','stoveburner':'stoveburner',
                     'sink':'sinkbasin','trash':'garbagecan','trashcan':'garbagecan',
                     'bin':'garbagecan','garbage':'garbagecan','sidetable':'sidetable',
                     'coffeetable':'coffeetable','tvstand':'tvstand','bathtub':'bathtub',
                     'laundryhamper':'laundryhamper','ottoman':'ottoman','cart':'cart',
                     'gold':'garbagecan',
        }
        for en, std in sorted(en2en_loc.items(), key=lambda x: -len(x[0])):
            if en in desc_lower:
                target_en = std
                break

        # 兜底:用cn→en映射
        if not obj_en and self.target_objects:
            obj_en = cn2en_obj.get(self.target_objects[0], self.target_objects[0])
        if not target_en and self.target_receps:
            target_en = cn2en_loc.get(self.target_receps[0], self.target_receps[0])

        self.target_info = {
            'obj_en': obj_en,
            'obj_cn': self.target_objects[0] if self.target_objects else '',
            'target_en': target_en,
            'target_cn': self.target_receps[0] if self.target_receps else '',
            'preproc_en': preproc_en,
            'task_type': self.task_type,
        }

    def update(self, action: str, obs: str):
        """从 obs 文本更新状态"""
        self.last_action = action
        ol = obs.lower()

        # 位置
        loc = ObsParser.extract_location(obs, self.current_location)
        # 如果是go to动作,即使extract失败也要把目标位置加入visited
        if action.startswith('go to '):
            target_raw = action[6:].strip()
            self.visited.add(ObsParser.key(target_raw))
        if loc != self.current_location and loc not in ('起点',):
            self.current_location = loc
            self.visited.add(ObsParser.key(loc))

        # 库存:从 obs 中检测
        state = ObsParser.parse_observation(obs, self.current_location or "起点")
        inv = state['inventory']
        if inv:
            self.holding = inv[0]

        # 动作结果检测
        if action.startswith('take '):
            if 'pick up' in ol or 'you take' in ol:
                # 从 obs 提取拿到的物体名
                m = re.search(r'you pick up (?:the |a )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', ol)
                if m:
                    self.holding = f"{m.group(1)} {m.group(2)}"
                else:
                    # 从动作命令中提取
                    m2 = re.search(r'take (.+?) from', action)
                    if m2:
                        self.holding = m2.group(1).strip()

        if action.startswith('open '):
            container = action[5:].strip()
            if 'open' in ol:
                self.opened_containers.add(container)

        # put/move 结果检测
        if action.startswith('put ') or action.startswith('move '):
            if 'you put' in ol or 'you place' in ol or 'you move' in ol:
                self.holding = None
                # 如果是放入预处理设备,标记为已处理
                ti = self.target_info
                if ti.get('preproc_en', '') and ti['preproc_en'] in action.lower():
                    self.processed = True

        # 处理动作结果检测
        if action.startswith('clean ') or action.startswith('heat ') or action.startswith('cool '):
            if 'clean' in ol or 'heat' in ol or 'cool' in ol:
                self.processed = True
                # 处理后物体还在手上
                if not self.holding:
                    m = re.search(r'(?:clean|heat|cool) (.+?) with', action)
                    if m:
                        self.holding = m.group(1).strip()

        # 推进阶段
        self._advance_phase(action, obs)

    def _advance_phase(self, action: str, obs: str):
        """基于动作结果推进阶段"""
        if self.phase >= len(self.plan):
            return
        current_goal = self.plan[self.phase]
        ol = obs.lower()

        # find 阶段: 到达目标位置或看到目标物体
        if current_goal.startswith('find_'):
            if action.startswith('go to '):
                loc = action[6:].strip().lower()
                loc_base = ObsParser.norm(loc)

                targets = self.target_objects if 'object' in current_goal else \
                          self.target_tools if current_goal == 'find_tool' else \
                          self.target_receps
                for t in targets:
                    if t in ol or (loc_base and (t == loc_base or t in loc_base or loc_base in t)):
                        self.phase += 1
                        if self.verbose:
                            print(f"    [advance] {current_goal} → phase {self.phase}")
                        return

        # take 阶段: 拿取成功
        elif current_goal.startswith('take_'):
            if action.startswith('take ') and ('pick up' in ol or 'you take' in ol):
                self.phase += 1
                if self.verbose:
                    print(f"    [advance] {current_goal} → phase {self.phase}")

        # use_tool 阶段: 处理成功
        elif current_goal == 'use_tool':
            if any(action.startswith(p) for p in ('clean ', 'heat ', 'cool ')):
                if 'clean' in ol or 'heat' in ol or 'cool' in ol:
                    self.phase += 1
                    if self.verbose:
                        print(f"    [advance] {current_goal} → phase {self.phase}")

        # put 阶段: 放置成功
        elif current_goal.startswith('put_'):
            if action.startswith('put ') or action.startswith('move '):
                if 'you put' in ol or 'you place' in ol or 'you move' in ol:
                    self.phase += 1
                    if self.verbose:
                        print(f"    [advance] {current_goal} → phase {self.phase}")

    def act(self, obs: str) -> str:
        """选择下一步动作(纯 obs-only)"""
        self.step_count += 1
        state = ObsParser.parse_observation(obs, self.current_location or "起点")
        loc_raw = state['location']
        loc_norm = ObsParser.norm(loc_raw)

        # 记忆初始可见位置(用于系统性搜索)
        if state['visible_locations'] and not self._known_locations:
            # 按合理搜索优先级排序:shelf/desk/cabinet > drawer/bed/sofa > 其他
            priority = ['shelf','desk','cabinet','countertop','drawer','bed','sofa',
                        'safe','garbagecan','laundryhamper','bathtub','armchair']
            scored = []
            for loc in state['visible_locations']:
                base = ObsParser.norm(loc)
                p = 0
                for pi, prefix in enumerate(priority):
                    if prefix in base:
                        p = (len(priority) - pi) * 10
                        break
                scored.append((p, loc))
            scored.sort(key=lambda x: -x[0])
            self._known_locations = [loc for _, loc in scored]

        # 从 obs 更新 holding（如果obs携带了库存信息则更新，否则保留上一步值）
        if state['inventory']:
            self.holding = state['inventory'][0]
        # 同样检测move/put的结果来清理holding（防止update还没被调用）
        ol_now = obs.lower()
        if self.last_action and (self.last_action.startswith('move ') or self.last_action.startswith('put ')):
            if 'you move' in ol_now or 'you put' in ol_now or 'you place' in ol_now:
                self.holding = None
                self._placed_count += 1

        # 构建六爻
        ti = self.target_info
        at_target = bool(ti.get('target_en','') and ti['target_en'] in loc_norm)
        yao = build_yao(loc_norm, bool(self.holding), self.processed, self.step_count,
                        ti.get('preproc_en',''), ti.get('target_en',''), at_target)
        intent, score = fuzzy_decide(yao)

        # 意图修正：位置逻辑检查
        pp = ti.get('preproc_en','')
        tg = ti.get('target_en','')
        # 在target位置但没处理→应该去预处理位置
        if pp and pp != tg and self.holding and not self.processed:
            if intent in ("放置","去目标","执行处理","放入设备"):
                if loc_norm != pp:
                    intent = "去预处理"
        
        # 无预处理场景修正
        # pick_two: 放完一块后继续搜索第二块
        if self.task_type == 'pick_two_obj_and_place' and self._placed_count >= 1 and not self.holding:
            # 有可见物体优先拿
            if state.get('visible_objects'):
                intent = "拿取"
            elif intent in ("放置","去目标"):
                intent = "goto探索"
        
        if not pp:
            if self.task_type == 'look_at_obj_in_light':
                # look_at: 找到物体后去desk→use desklamp
                obj_en = ti.get('obj_en','')
                # 如果物体名在标准物体MAP中（英文）或为空→可能要拿物体
                is_direct_lamp = (not obj_en or obj_en in ('灯','光'))
                if is_direct_lamp:
                    # 直接开灯任务：在desk位置先拿可见物体，再到desk 1执行
                    if not self.holding:
                        if 'desk' in loc_norm:
                            # 在desk上，先拿所有可见物体
                            intent = "拿取"
                        else:
                            intent = "goto探索"
                    else:
                        intent = "执行处理"
                else:
                    # 有目标物体（如mug）：先找物体
                    if intent in ("去预处理","放入设备","取出"):
                        intent = "执行处理" if self.holding else ("拿取" if not self.holding else "goto探索")
                    if self.holding and ('desk' in loc_norm or 'lamp' in loc_norm):
                        intent = "执行处理"
            elif intent in ("去预处理","放入设备","执行处理","取出"):
                intent = "放置" if self.holding else ("拿取" if not self.holding else "goto探索")

        # 检查是否需要 open(覆盖六爻决策)
        # 当前位有closed容器 → 任何阶段都优先open
        open_cmds = [l for l, s in state['doors'].items() if s == 'closed' and l in loc_raw]
        for l, s in state['doors'].items():
            if s == 'closed':
                # 检查这个容器是否就是当前位置或当前位置的一部分
                if l in loc_raw or l in loc_norm or loc_norm in l:
                    open_cmds.append(l)
                    break
        if open_cmds and not state['visible_objects']:
            return f"open {open_cmds[0]}"

        # 知几位置先验叠加：在state中注入位置偏好供pick_action使用
        zhiji_boosts = {}
        if hasattr(self, '_zhiji') and self._zhiji is not None and ti.get('obj_en',''):
            obj_base = ti.get('obj_en','').lower()
            for rec_base in ['countertop','cabinet','drawer','shelf','desk','bed','sofa',
                             'sinkbasin','fridge','microwave','garbagecan','safe',
                             'diningtable','coffeemachine']:
                boost = self._zhiji.get_location_prior_boost(obj_base, rec_base)
                if boost > 0:
                    zhiji_boosts[rec_base] = boost
                    if self.verbose:
                        print(f"    [知几] {obj_base}→{rec_base}: +{boost:.1f}")
        state['zhiji_boosts'] = zhiji_boosts
        
        # 如果已知初始位置列表且got探索→优先使用
        action = None
        if intent == "goto探索" and self._known_locations:
            for loc in self._known_locations:
                if ObsParser.key(loc) not in self.visited:
                    action = f"go to {loc}"
                    break

        if action is None:
            action = pick_action(intent, state, ti, self.visited, loc_norm, self.holding)

        if self.verbose:
            yao_str = " ".join(f"{v:.2f}" for v in yao)
            print(f"  S{self.step_count:2d} [{self._current_goal():15s}] {intent:8s}({score:.2f}) "
                  f"yao=({yao_str}) loc={ObsParser.norm(loc_raw):8s} "
                  f"hold={bool(self.holding)} proc={self.processed} → {action}")

        self._last_state = state
        return action

    def _current_goal(self) -> str:
        if self.phase < len(self.plan):
            return self.plan[self.phase]
        return 'done'
