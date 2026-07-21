#!/usr/bin/env python3
"""
YLYW Agent V16 - 卦象驱动场景记忆 + 零样本逐步决策

核心改造:
  1. 初始任务理解 → 任务卦象(持久记忆)
  2. 每步 obs → HanziEngine → 场景卦象(持续累积)
  3. 任务卦象 vs 场景卦象的差距 → 涌现下步意图

不再需要:
  - build_yao(硬编码6维)
  - fuzzy_decide(8条规则)
  - TASK_PLANS(阶段列表)
  - _advance_phase(阶段推进)
"""

import re
import os as _os
import sys
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'language'))
from typing import List, Dict, Optional, Tuple
import numpy as np

from hanzi_engine import HanziEngine

_ENGINE = None

def _get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = HanziEngine(verbose=False)
    return _ENGINE


# ═══════════════════════════════════════════════════
# ObsParser: 从 obs 提取结构化信息
# ═══════════════════════════════════════════════════

class ObsParser:
    """从 ALFWorld obs 文本提取结构化状态（保留供动作构造使用）"""

    @staticmethod
    def extract_location(obs_text: str, prev_loc: str = "起点") -> str:
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                return after[:idx].strip() if idx > 0 else after
        return prev_loc

    @staticmethod
    def parse_observation(obs_text: str, prev_loc: str) -> dict:
        result = {
            'location': ObsParser.extract_location(obs_text, prev_loc),
            'visible_objects': [],
            'visible_locations': [],
            'doors': {},
            'inventory': [],
        }
        ol = obs_text.strip().lower()

        # 位置
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                result['location'] = after[:idx].strip() if idx > 0 else after

        # 可见物体
        for m in re.finditer(r'on the (.+?), you see (.+?)(?:\.|$)', ol):
            items = m.group(2).strip()
            for item in re.finditer(r'(?:a |an )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', items):
                obj = item.group(1).strip()
                if obj not in ('a', 'an'):
                    result['visible_objects'].append(f"{obj} {item.group(2)}")

        # 容器内物体
        m2 = re.search(r'in it, you see (.+)', ol)
        if m2:
            items = m2.group(1).strip()
            for item in re.finditer(r'(?:a |an )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', items):
                obj = item.group(1).strip()
                if obj not in ('a', 'an'):
                    result['visible_objects'].append(f"{obj} {item.group(2)}")

        # 初始位置
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
                                    'tvstand','sidetable','coffeetable',
                                    'handtowelholder','toiletpaperhanger',):
                            result['visible_locations'].append(f"{name} {m.group(2)}")

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
# 任务参数提取（英文→中文→英文 映射）
# ═══════════════════════════════════════════════════

CN_EN_LOC = {
    '柜台':'countertop', '柜子':'cabinet', '抽屉':'drawer',
    '架子':'shelf', '桌子':'desk', '水槽':'sinkbasin',
    '冰箱':'fridge', '微波炉':'microwave', '垃圾桶':'garbagecan',
    '床':'bed', '沙发':'sofa', '保险箱':'safe', '马桶':'toilet',
    '扶手椅':'armchair', '台灯':'desklamp', '落地灯':'floorlamp',
    '灯':'desklamp', '餐桌':'diningtable', '灶台':'stoveburner',
    '咖啡机':'coffeemachine', '烤面包机':'toaster',
    '垃圾桶':'garbagecan',
}

CN_EN_OBJ = {
    '盘子':'plate','碗':'bowl','杯子':'cup','苹果':'apple',
    '土豆':'potato','番茄':'tomato','鸡蛋':'egg','面包':'bread',
    '生菜':'lettuce','肥皂':'soapbar','刀':'knife','勺子':'spoon',
    '叉子':'fork','锅铲':'spatula','锅':'pot','书':'book','铅笔':'pencil',
    '报纸':'newspaper','笔记本':'laptop','手机':'cellphone',
    '钥匙链':'keychain','遥控器':'remotecontrol','雕像':'statue',
    '花瓶':'vase','枕头':'pillow','毛巾':'towel','抹布':'cloth',
    '手表':'watch','瓶子':'bottle','盒子':'box','光盘':'cd',
    '闹钟':'alarmclock','棒球棒':'baseballbat','篮球':'basketball',
    '胡椒瓶':'peppershaker','盐瓶':'saltshaker','刷子':'scrubbrush',
    '喷壶':'spraybottle','纸巾盒':'tissuebox','卫生纸':'toiletpaper',
    '黄油刀':'butterknife','信用卡':'creditcard','皮搋子':'plunger',
    '洗手液瓶':'soapbottle','蜡烛':'candle','汤勺':'ladle','水壶':'kettle',
    '牛奶':'milk','咖啡':'coffee','食物':'food',
}

EN_CN_OBJ = {v:k for k,v in CN_EN_OBJ.items()}
EN_CN_LOC = {v:k for k,v in CN_EN_LOC.items()}

EN2CN_LOC = {
    'countertop':'柜台','counter':'柜台','cabinet':'柜子','drawer':'抽屉',
    'shelf':'架子','desk':'桌子','sinkbasin':'水槽','fridge':'冰箱',
    'microwave':'微波炉','garbagecan':'垃圾桶','garbage':'垃圾桶',
    'trash':'垃圾桶','bin':'垃圾桶','safe':'保险箱',
    'bed':'床','sofa':'沙发','toilet':'马桶','armchair':'扶手椅',
    'desklamp':'台灯','floorlamp':'落地灯','lamp':'灯',
    'diningtable':'餐桌','coffeemachine':'咖啡机',
    'stoveburner':'灶台','toaster':'烤面包机','bathtub':'浴缸',
}

EN2CN_OBJ = {
    'plate':'盘子','bowl':'碗','cup':'杯子','mug':'杯子',
    'apple':'苹果','potato':'土豆','tomato':'番茄','egg':'鸡蛋',
    'bread':'面包','soap':'肥皂','soapbar':'肥皂',
    'knife':'刀','spoon':'勺子','fork':'叉子','spatula':'锅铲',
    'pan':'锅','pot':'锅','book':'书','pencil':'铅笔',
    'newspaper':'报纸','laptop':'笔记本','cellphone':'手机',
    'keychain':'钥匙链','remotecontrol':'遥控器','statue':'雕像',
    'vase':'花瓶','pillow':'枕头','towel':'毛巾','cloth':'抹布',
    'watch':'手表','bottle':'瓶子','box':'盒子','cd':'光盘',
    'alarmclock':'闹钟','baseballbat':'棒球棒','peppershaker':'胡椒瓶',
    'saltshaker':'盐瓶','scrubbrush':'刷子','spraybottle':'喷壶',
    'tissuebox':'纸巾盒','toiletpaper':'卫生纸','butterknife':'黄油刀',
    'creditcard':'信用卡','plunger':'皮搋子','soapbottle':'洗手液瓶',
    'candle':'蜡烛','ladle':'汤勺','kettle':'水壶','milk':'牛奶',
    'food':'食物','breadsliced':'面包','applesliced':'苹果',
}

TOOL_ACTIONS = {
    'sinkbasin': 'clean', 'fridge': 'cool', 'microwave': 'heat',
}


# ═══════════════════════════════════════════════════
# 动作构造
# ═══════════════════════════════════════════════════

def pick_action(intent: str, obs_state: dict, target_info: dict,
                visited_keys: set, loc_norm: str, holding: Optional[str] = None) -> str:
    """
    从意图生成 ALFWorld 动作。
    保留为动作层映射（ALFWorld 特定命令格式，非零样本可绕过的部分）。
    """
    loc_raw = obs_state['location']
    inv = [holding] if holding else obs_state['inventory']
    vis_objs = obs_state['visible_objects']
    vis_locs = obs_state['visible_locations']
    doors = obs_state['doors']

    obj_en = target_info.get('obj_en', '')
    target_en = target_info.get('target_en', '')
    preproc_en = target_info.get('preproc_en', '')
    task_type = target_info.get('task_type', '')

    # ──── goto探索 ────
    if intent == "goto探索":
        known_all = []
        location_order = ['cabinet','drawer','shelf','desk','countertop',
                          'fridge','microwave','sinkbasin','garbagecan',
                          'safe','bed','sofa','toilet','diningtable',
                          'stoveburner','bathtub','desklamp','floorlamp']

        for prefix in location_order:
            if prefix in ('cabinet',):
                for n in range(6, 0, -1):
                    known_all.append(f"{prefix} {n}")
            elif prefix in ('shelf','desk'):
                for n in range(6, 0, -1):
                    known_all.append(f"{prefix} {n}")
            elif prefix in ('drawer','countertop'):
                for n in range(3, 0, -1):
                    known_all.append(f"{prefix} {n}")
            else:
                for n in range(1, 3):
                    known_all.append(f"{prefix} {n}")

        known_all += [l for l in vis_locs if l not in known_all]

        if target_en:
            for n in range(1, 4):
                c = f"{target_en} {n}"
                if c not in known_all: known_all.append(c)
        if preproc_en:
            c = f"{preproc_en} 1"
            if c not in known_all: known_all.append(c)

        for loc in known_all:
            if ObsParser.key(loc) not in visited_keys:
                return f"go to {loc}"

        if target_en: return f"go to {target_en} 1"
        if preproc_en: return f"go to {preproc_en} 1"
        if vis_locs: return f"go to {vis_locs[0]}"
        return "look"

    # ──── 拿取 ────
    if intent == "拿取":
        for loc_name, state in doors.items():
            if state == 'closed' and loc_name in loc_raw:
                return f"open {loc_name}"

        if vis_objs:
            matched_obj = None
            for obj in vis_objs:
                obj_base = ObsParser.norm(obj)
                if obj_en and (obj_en in obj_base or obj_base in obj_en):
                    matched_obj = obj
                    break
            if not matched_obj:
                for obj in vis_objs:
                    obj_base = ObsParser.norm(obj)
                    for en in EN2CN_OBJ:
                        if en in obj_en.lower() or obj_en.lower() in en:
                            if en in obj_base or obj_base in en:
                                matched_obj = obj
                                break
                    if matched_obj: break
            if matched_obj:
                if loc_raw and loc_raw != "起点":
                    return f"take {matched_obj} from {loc_raw}"
                return f"take {matched_obj}"
            return pick_action("goto探索", obs_state, target_info, visited_keys, loc_norm, holding)
        return pick_action("goto探索", obs_state, target_info, visited_keys, loc_norm, holding)

    # ──── 去预处理 ────
    if intent == "去预处理":
        if preproc_en:
            return f"go to {preproc_en} 1"
        if vis_locs:
            return f"go to {vis_locs[0]}"
        return "look"

    # ──── 放入设备 ────
    if intent == "放入设备":
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
            return "use desklamp 1"
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
# YLYWAgentV16 - 卦象驱动场景记忆
# ═══════════════════════════════════════════════════

class YLYWAgentV16:
    """
    卦象驱动 Agent: 任务记忆 + 场景记忆 → 卦象差距 → 涌现意图

    Attributes:
        task_hexagram:       任务卦名（持久记忆）
        task_yao:            任务六爻（持久记忆）
        task_hex64:          任务64维卦象
        scene_hexagram:      场景记忆卦名（持续更新）
        scene_yao:           场景记忆六爻（持续更新）
        scene_hex64:         场景64维卦象
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.engine = _get_engine()

        # A层: 任务记忆
        self.task_type = ''
        self.task_desc = ''
        self.task_hexagram = '?'
        self.task_yao = [0.5]*6
        self.task_hex64 = [0.0]*64

        # B层: 场景记忆
        self.scene_hexagram = '?'
        self.scene_yao = [0.5]*6
        self.scene_hex64 = [0.0]*64
        self.scene_memory = []  # 关键场景事件记录

        # 动作相关
        self.holding = None
        self.processed = False
        self.current_location = ''
        self.visited = set()
        self.opened_containers = set()
        self.last_action = ''
        self.step_count = 0
        self._known_locations = []

        # 中英参数
        self.obj_en = ''
        self.target_en = ''
        self.preproc_en = ''
        self.obj_cn = ''
        self.target_cn = ''

    # ──── A层: 初始任务理解 ────

    def reset(self, task_desc: str, task_type: str):
        """新任务——用 HanziEngine 理解任务并记忆卦象"""
        self.task_type = task_type
        self.task_desc = task_desc
        self.holding = None
        self.processed = False
        self.current_location = ''
        self.visited = {"起点"}
        self.opened_containers = set()
        self.last_action = ''
        self.step_count = 0
        self._known_locations = []
        self._done_flag = False

        # A层: 解析任务并记忆卦象
        self._parse_task_with_hanzi(task_desc)

        # B层: 场景记忆初始化为空
        self.scene_hexagram = '?'
        self.scene_yao = [0.5]*6
        self.scene_hex64 = [0.0]*64
        self.scene_memory = []

        if self.verbose:
            print(f"  [任务] {self.obj_cn} → {self.target_cn}")
            print(f"  [卦象] {self.task_hexagram}({self.task_dominant}) yao={[round(x,2) for x in self.task_yao]}")

    def _parse_task_with_hanzi(self, task_desc: str):
        """用汉字引擎理解任务描述，提取参数并记忆卦象"""
        desc = task_desc.lower().strip()

        # 提取英文参数
        obj_en = ''
        loc_en = ''
        # 优先长词匹配
        obj_keys = sorted(EN2CN_OBJ.keys(), key=lambda x: -len(x))
        loc_keys = sorted(EN2CN_LOC.keys(), key=lambda x: -len(x))

        for en in obj_keys:
            if en in desc:
                obj_en = en
                self.obj_cn = EN2CN_OBJ[en]
                obj_start = desc.find(en)
                break
        for en in loc_keys:
            if en in desc:
                loc_en = en
                self.target_cn = EN2CN_LOC[en]
                break

        # 把别名映射为标准ALFWorld位置名
        target_en_raw = loc_en
        alias_map = {'counter':'countertop', 'lamp':'desklamp', 'trash':'garbagecan', 'garbage':'garbagecan', 'bin':'garbagecan'}
        if target_en_raw in alias_map:
            target_en_raw = alias_map[target_en_raw]
        
        self.obj_en = obj_en
        self.target_en = target_en_raw

        # 检测预处理设备/工具
        self.preproc_en = ''
        for kw, tool in [('sinkbasin','sinkbasin'), ('clean','sinkbasin'), ('wash','sinkbasin'),
                         ('microwave','microwave'), ('heat','microwave'),
                         ('fridge','fridge'), ('cool','fridge'), ('chill','fridge'), ('cold','fridge'),
                         ('desk lamp','desklamp'), ('desklamp','desklamp'), ('lamp','desklamp'),
                         ('light','desklamp')]:
            if kw in desc:
                if tool not in ('sinkbasin','microwave','fridge','desklamp'):
                    continue
                if tool == 'desklamp':
                    if any(w in desc for w in ['clean','wash','heat','cool']):
                        continue
                self.preproc_en = tool
                break

        is_light = any(kw in desc for kw in ['lamp','light','examine','look at'])
        is_clean = any(kw in desc for kw in ['clean','wash','rinse'])
        is_heat = any(kw in desc for kw in ['heat','microwave','warm','cook','hot'])
        is_cool = any(kw in desc for kw in ['cool','fridge','chill','cold','freeze'])

        if is_light and not is_clean and not is_heat and not is_cool:
            self.task_type = 'look_at_obj_in_light'
            if not self.preproc_en:
                self.preproc_en = 'desklamp'
        elif is_clean:
            self.task_type = 'pick_clean_then_place_in_recep'
        elif is_heat:
            self.task_type = 'pick_heat_then_place_in_recep'
        elif is_cool:
            self.task_type = 'pick_cool_then_place_in_recep'
        else:
            self.task_type = 'pick_and_place_simple'

        # 构建中文任务描述
        cn_parts = []
        if self.obj_cn:
            cn_parts.append(self.obj_cn)
        if self.preproc_en == 'sinkbasin':
            cn_parts.append('洗干净')
        elif self.preproc_en == 'microwave':
            cn_parts.append('加热')
        elif self.preproc_en == 'fridge':
            cn_parts.append('冷却')
        elif self.preproc_en == 'desklamp' and is_light:
            cn_parts.append('看灯')
        if self.target_cn:
            cn_parts.append(f'放到{self.target_cn}')
        task_cn = ' '.join(cn_parts) if cn_parts else task_desc

        # HanziEngine 理解中文任务
        result = self.engine.sentence(task_cn)

        self.task_hexagram = result['main_hexagram']
        self.task_yao = result['yao_vector']
        self.task_hex64 = result['hex64']
        self.task_dominant = result['dominant_bagua']

        # 缓存任务关键信息
        self._task_cn = task_cn
        self._result_hexagram = '?'  # 当前动作结果卦象
        self._result_yao = [0.5]*6

    # ──── B层: 场景记忆更新 ────

    def _update_scene(self, obs: str, action: str):
        """每步 obs → 汉字引擎理解 → 更新场景记忆卦象"""
        state = ObsParser.parse_observation(obs, self.current_location or "起点")
        loc_raw = state['location']
        loc_norm = ObsParser.norm(loc_raw)

        if loc_raw != self.current_location and loc_raw not in ('起点',):
            self.current_location = loc_raw
            self.visited.add(ObsParser.key(loc_raw))

        took_item = False
        processed_now = False
        placed_now = False

        if action:
            ol = obs.lower()
            if action.startswith('take '):
                if 'you pick up' in ol or 'you take' in ol:
                    took_item = True
                    self.holding = state['inventory'][0] if state['inventory'] else self.holding
            if action.startswith('clean ') and 'clean' in ol:
                processed_now = True
                self.processed = True
            if action.startswith('heat ') and 'heat' in ol:
                processed_now = True
                self.processed = True
            if action.startswith('cool ') and 'cool' in ol:
                processed_now = True
                self.processed = True
            if (action.startswith('put ') or action.startswith('move ')) and \
               ('you put' in ol or 'you place' in ol or 'you move' in ol):
                placed_now = True
                self.holding = None
            if action.startswith('use '):
                if 'turn on' in ol or 'desklamp' in ol or 'lamp' in ol:
                    processed_now = True

        # 构造中文场景描述
        parts = []
        loc_cn = EN2CN_LOC.get(loc_norm, loc_norm)
        parts.append(f'在{loc_cn}')

        # 可见物体（用"有"表示存在，比"看到"更中性，便于汉字引擎区分）
        if state['visible_objects']:
            obj_cns = []
            for obj in state['visible_objects'][:3]:
                obj_base = ObsParser.norm(obj)
                cn = EN2CN_OBJ.get(obj_base, obj_base)
                obj_cns.append(cn)
            if obj_cns:
                parts.append(f'看到{"".join(obj_cns)}')

        if took_item:
            obj_base = ObsParser.norm(self.holding) if self.holding else ''
            obj_cn = EN2CN_OBJ.get(obj_base, obj_base)
            parts.append(f'拿{obj_cn}')
        if processed_now:
            if self.preproc_en == 'sinkbasin':
                parts.append('洗')
            elif self.preproc_en == 'microwave':
                parts.append('热')
            elif self.preproc_en == 'fridge':
                parts.append('冷')
            elif self.preproc_en == 'desklamp':
                parts.append('灯亮')
            else:
                parts.append('好')
        if placed_now:
            parts.append('放')

        scene_text = '，'.join(parts)

        if not parts:
            return

        result = self.engine.sentence(scene_text)

        alpha = 0.5
        if self.scene_hexagram == '?':
            self.scene_yao = list(result['yao_vector'])
            self.scene_hex64 = list(result['hex64'])
            self.scene_hexagram = result['main_hexagram']
        else:
            yao_new = result['yao_vector']
            self.scene_yao = [clip(alpha * yao_new[i] + (1-alpha) * self.scene_yao[i]) for i in range(6)]
            self.scene_hex64 = self.engine.sentence_layer._match_64hexagrams(self.scene_yao)
            h, s = self.engine.sentence_layer._match_hexagram(self.scene_yao)
            self.scene_hexagram = h

        self.scene_memory.append({
            'step': self.step_count, 'action': action or '',
            'text': scene_text, 'hexagram': result['main_hexagram'],
        })

        if self.verbose:
            print(f"  [场景] {scene_text}")
            print(f"  [场景卦] {result['main_hexagram']} yao={[round(x,2) for x in result['yao_vector']]}")
            print(f"  [记忆卦] {self.scene_hexagram} yao={[round(x,2) for x in self.scene_yao]}")

    # ──── C层: 场景依存 → 涌现意图 ────

    def _decide_intent(self) -> Tuple[str, float]:
        """
        从汉字引擎对最新场景文本的理解中涌现意图。
        结合跨步记忆的_done_flag防止重复拿放。
        """
        if not self.scene_memory:
            return "goto探索", 0.0

        # ══ 跨步记忆检查：如果已完成任务的主要目标，等胜利信号 ══
        # 放下东西后手空了→标记完成→不再拿新东西
        if self._done_flag:
            return "goto探索", 0.0

        # 取最新场景文本，送汉字引擎理解
        latest = self.scene_memory[-1]
        scene_text = latest['text']
        result = self.engine.sentence(scene_text)
        segs = result['segments']
        roles = result['segment_role']
        rels = result['mutua_relations']

        # ── 从互卦关系中提取语义角色 ──
        actions, objects, locations = [], [], []

        for rel in rels:
            rtype = rel.get('relation', '')
            fi = rel.get('from', '')
            ti = rel.get('to', '')
            if fi not in segs or ti not in segs:
                continue
            fi_idx = segs.index(fi)
            ti_idx = segs.index(ti)
            if fi_idx >= len(roles) or ti_idx >= len(roles):
                continue

            if '乘' in rtype:
                if roles[fi_idx] == '动作' and roles[ti_idx] in ('物体','状态'):
                    if fi not in actions: actions.append(fi)
                    if ti not in objects: objects.append(ti)
            elif '承' in rtype:
                if roles[fi_idx] in ('物体','状态') and roles[ti_idx] == '动作':
                    if fi not in locations: locations.append(fi)

        for i, seg in enumerate(segs):
            if roles[i] == '动作' and seg not in actions:
                actions.append(seg)
            if roles[i] == '物体' and seg not in objects:
                objects.append(seg)

        has_take = any(w in actions for w in ['拿','拿到','取'])
        has_wash = any(w in actions for w in ['洗','洗干净','清'])
        has_heat = any(w in actions for w in ['热','加热'])
        has_cool = any(w in actions for w in ['冷','冷却'])
        has_place = any(w in actions for w in ['放','放好','放到'])
        has_lamp = any(w in actions for w in ['灯亮','灯开','用灯'])
        has_exist = any(i < len(roles) and '看' in segs[i] and roles[i] == '动作' for i in range(len(segs))) and not has_take

        has_inv = bool(self.holding is not None)
        processed = bool(self.processed)

        # ── 从场景语义涌现意图 ──

        # 检测到完成动作：放、洗、热、冷、灯亮
        # 如果手上空了，标记完成，不再重复拿
        if has_place and not has_inv:
            self._done_flag = True
            return "goto探索", 0.0
        if (has_wash or has_heat or has_cool) and not has_inv:
            self._done_flag = True
            return "goto探索", 0.0
        if has_lamp:
            self._done_flag = True
            return "goto探索", 0.0

        # 看到有物体（没拿）→ 拿取
        if has_exist and objects and not has_inv:
            return "拿取", 0.0

        # falback：结构化状态
        if has_inv and not processed and self.preproc_en:
            if self._is_at_preproc():
                return "放入设备", 0.0
            return "去预处理", 0.0
        if has_inv and processed and self._is_at_target():
            return "放置", 0.0
        if has_inv and self._is_at_target():
            return "放置", 0.0
        if has_inv and processed:
            return "去目标", 0.0
        if has_inv and not processed and self.preproc_en:
            return "去预处理", 0.0
        if has_inv and not processed:
            return "去目标", 0.0

        return "goto探索", 0.0

    def _is_at_target(self) -> bool:
        loc_norm = ObsParser.norm(self.current_location or '')
        return bool(self.target_en and (self.target_en in loc_norm or loc_norm in self.target_en))

    def _is_at_preproc(self) -> bool:
        loc_norm = ObsParser.norm(self.current_location or '')
        return bool(self.preproc_en and (self.preproc_en in loc_norm or loc_norm in self.preproc_en))

    # ──── 动作选择 ────

    def act(self, obs: str) -> str:
        """选择下一步动作"""
        self.step_count += 1

        # 解析当前 obs
        state = ObsParser.parse_observation(obs, self.current_location or "起点")

        # 检测当前 obs 中的关键信息（供 _decide_intent 使用）
        self._see_target_in_latest_obs = False
        self._see_lamp_in_latest_obs = False
        if state['visible_objects']:
            for obj in state['visible_objects']:
                obj_base = ObsParser.norm(obj)
                if self.obj_en:
                    # 宽松匹配：子串匹配
                    if self.obj_en in obj_base or obj_base in self.obj_en:
                        self._see_target_in_latest_obs = True
                    # 尝试英文词典匹配
                    for en, cn in EN2CN_OBJ.items():
                        if en in obj_base or obj_base in en:
                            if self.obj_en in en or en in self.obj_en:
                                self._see_target_in_latest_obs = True
        if 'lamp' in (state.get('location','') or '').lower():
            self._see_lamp_in_latest_obs = True

        # 更新场景记忆
        if self.last_action:
            self._update_scene(obs, self.last_action)
        else:
            loc_raw = state['location']
            if loc_raw != self.current_location and loc_raw not in ('起点',):
                self.current_location = loc_raw
                self.visited.add(ObsParser.key(loc_raw))
            self._update_scene(obs, '')

        # 决策
        intent, score = self._decide_intent()

        # 生成动作
        target_info = {
            'obj_en': self.obj_en,
            'target_en': self.target_en,
            'preproc_en': self.preproc_en,
            'task_type': self.task_type,
        }
        loc_norm = ObsParser.norm(state['location'])
        action = pick_action(intent, state, target_info, self.visited, loc_norm, self.holding)

        if self.verbose:
            print(f"  S{self.step_count:2d} [{intent:8s}] hold={bool(self.holding)} proc={self.processed} "
                  f"loc={loc_norm:8s} 看到目标={self._see_target_in_latest_obs} → {action}")

        self.last_action = action
        return action

    def update(self, action: str, obs: str):
        """从 obs 更新状态（每步调用一次，与 act 互补）"""
        self.last_action = action

        loc = ObsParser.extract_location(obs, self.current_location or "起点")
        if action.startswith('go to '):
            target_raw = action[6:].strip()
            self.visited.add(ObsParser.key(target_raw))
        if loc != self.current_location and loc not in ('起点',):
            self.current_location = loc
            self.visited.add(ObsParser.key(loc))

        # 场景记忆更新
        self._update_scene(obs, action)

        # 结构化状态
        state = ObsParser.parse_observation(obs, self.current_location or "起点")
        if state['inventory']:
            self.holding = state['inventory'][0]

        if action.startswith('put ') or action.startswith('move '):
            if 'you put' in obs.lower() or 'you place' in obs.lower() or 'you move' in obs.lower():
                self.holding = None
                self.processed = True

    def is_done(self, obs: str) -> bool:
        """判断任务是否完成"""
        if 'you win' in obs.lower() or 'task done' in obs.lower() or 'success' in obs.lower():
            return True
        return False


def clip(v: float, lo: float = 0.05, hi: float = 0.95) -> float:
    return max(lo, min(hi, v))
