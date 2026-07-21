#!/usr/bin/env python3

"""

YLYW Agent V17 - 动作原语库集成版



在 V16 基础上将 ActionPrimitiveAdapter 集成到动作选择层,

用卦象驱动的六爻映射取代硬编码的 pick_action()。



核心变更:

  V16:  intent → pick_action(硬编码) → ALFWorld cmd

  V17:  intent → 动作卦象 → ActionPrimitiveAdapter → ALFWorld cmd



保留:

  - HanziEngine 任务理解(A层)

  - HanziEngine 场景记忆更新(B层)

  - 意图涌现(C层)- 但意图词现在映射到适配器

"""



import re

import os as _os

import sys

sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'language'))

sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))

from typing import List, Dict, Optional, Tuple

import functools

import numpy as np



from hanzi_engine import HanziEngine

from ylyw_action_primitives import (

    ActionPrimitiveAdapter, SceneState, ACTION_PRIMITIVES,

    RECEPTACLE_NAMES, ITEM_NAMES,

    list_all_action_types, get_action_type_by_gua, get_gua_by_action_type,

    ExplorationMemory, rank_exploration_targets,

)

# ══ 注意力机制模块（LLM语义引导 + 空间探索层） ══
from llm_semantic_guide import LLMSemanticGuide
from spatial_exploration_layer import SpatialExplorationLayer, SpatialMemory, LOCATION_BAGUA, OBJECT_BAGUA, BAGUA_GENERATION

# ══ YLYW 子目标引擎（六爻驱动的任务分解） ══
from ylyw_subgoal_engine import SubgoalEngine, ChineseIntentParser, EnhancedAttention

_ENGINE = None

_ADAPTER = None



def _get_engine():

    global _ENGINE

    if _ENGINE is None:

        _ENGINE = HanziEngine(verbose=False)

    return _ENGINE



def _get_adapter():

    global _ADAPTER

    if _ADAPTER is None:

        _ADAPTER = ActionPrimitiveAdapter()

    return _ADAPTER





# ═══════════════════════════════════════════════════

# ObsParser: 从 obs 提取结构化信息

# ═══════════════════════════════════════════════════



class ObsParser:

    """从 ALFWorld obs 文本提取结构化信息"""



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

                        # 容器名称集合

                        if name in RECEPTACLE_NAMES:

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

# 工具映射表(保留中英互查,供任务解析用)

# ═══════════════════════════════════════════════════



EN2CN_LOC_FULL = {

    'countertop':'柜台','counter':'柜台','cabinet':'柜子','drawer':'抽屉',

    'shelf':'架子','desk':'桌子','sinkbasin':'水槽','fridge':'冰箱',

    'microwave':'微波炉','garbagecan':'垃圾桶','garbage':'垃圾桶',

    'trash':'垃圾桶','bin':'垃圾桶','safe':'保险箱',

    'bed':'床','sofa':'沙发','toilet':'马桶','armchair':'扶手椅',

    'desklamp':'台灯','floorlamp':'落地灯','lamp':'灯',

    'diningtable':'餐桌','coffeemachine':'咖啡机',

    'stoveburner':'灶台','toaster':'烤面包机','bathtub':'浴缸',

}



EN2CN_OBJ_FULL = {

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

# 意图 → 动作卦象映射表

# ═══════════════════════════════════════════════════



INTENT_TO_ACTION_GUA = {

    "goto探索":    "111111",   # 乾 - 主动运动/探索

    "拿取":        "001001",   # 艮 - 获取

    "去预处理":    "111111",   # 乾 - 移动到预处理设备

    "去目标":      "111111",   # 乾 - 移动到目标位置

    "放入设备":    "010010",   # 坎 - 放入设备/处理

    "放置":        "010010",   # 坎 - 放置归位

    "执行处理":    "110101",   # 睽 - 切换/处理

    "完成":        "011011",   # 巽 - 入内审视/确认完成

}



# 意图 → 动作类型名(供适配器直接使用)

INTENT_TO_ACTION_TYPE = {

    "goto探索":    "navigate",

    "拿取":        "pickup",

    "去预处理":    "navigate",

    "去目标":      "navigate",

    "放入设备":    "clean",    # 默认 clean(适配器根据任务类型切换)

    "放置":        "put",

    "执行处理":    "toggle",   # 或根据场景切换

    "完成":        "look",

}





# ═══════════════════════════════════════════════════

# YLYWAgentV17 - 动作原语库集成

# ═══════════════════════════════════════════════════



class YLYWAgentV17:

    """

    V17 Agent: 卦象驱动场景记忆 + 动作原语库适配



    Attributes:

        adapter: ActionPrimitiveAdapter 实例

        scene_state: SceneState 实例(结构化场景状态)

        engine: HanziEngine 实例

    """



    # 位置别名映射：key 是 loc_kw 匹配到的短名，value 是 ALFWorld 实际位置名列表
    POSITION_ALIAS = {
        'counter': ['countertop'],
        'lamp': ['desklamp', 'floorlamp', 'lamp'],
        'trash': ['garbagecan'],
        'bin': ['garbagecan', 'bin'],
        'garbage': ['garbagecan'],
        'sink': ['sinkbasin'],
        'fridge': ['fridge'],
        'microwave': ['microwave'],
        'cabinet': ['cabinet'],
        'cupboard': ['cabinet'],
        'drawer': ['drawer'],
        'shelf': ['shelf'],
        'desk': ['desk'],
        'table': ['diningtable', 'table', 'desk', 'sidetable', 'coffeetable'],
        'sofa': ['sofa', 'armchair'],
        'bed': ['bed'],
        'toilet': ['toilet'],
        'bathtub': ['bathtub'],
        'safe': ['safe'],
    }

    def __init__(self, verbose: bool = False):

        self.verbose = verbose

        self.engine = _get_engine()

        self.adapter = _get_adapter()

        self.scene_state = SceneState()

        # ═══ 注意力机制 Layer 0: LLM 语义引导 ═══
        self._semantic_guide = LLMSemanticGuide()
        self._spatial_explorer = SpatialExplorationLayer(llm_guide=self._semantic_guide)

        # A层: 任务记忆

        self.task_type = ''

        self.task_desc = ''

        self.task_hexagram = '?'

        self.task_yao = [0.5]*6

        self.task_hex64 = [0.0]*64



        # B层: 场景记忆(卦象版本)

        self.scene_hexagram = '?'

        self.scene_yao = [0.5]*6

        self.scene_hex64 = [0.0]*64

        self.scene_memory = []  # 关键场景事件记录



        # 动作相关

        self.holding = None

        self.processed = False

        self.current_location = ''

        self.visited = set()

        self._done_flag = False
        self._stale_completion_count = 0
        self._tried_locs: set = set()  # 已探索过的位置类型（防原地循环）（防止完成→取放→完成循环）

        self.step_count = 0

        self._taken_objects = set()

        # 全局共享 ExplorationMemory（跨局知识积累）
        global _EXPLORATION_MEMORY_SINGLETON
        if '_EXPLORATION_MEMORY_SINGLETON' not in globals() or _EXPLORATION_MEMORY_SINGLETON is None:
            _EXPLORATION_MEMORY_SINGLETON = ExplorationMemory()
        self._exploration_memory = _EXPLORATION_MEMORY_SINGLETON

        # ═══ YLYW 子目标引擎 ═══
        self._subgoal_engine = SubgoalEngine(verbose=False)
        self._enhanced_attention = EnhancedAttention(verbose=False)

        # V6+: 物体位置记忆（从 take/admissible 中提取）
        self.object_memory: Dict[str, str] = {}  # obj_name -> location

        # V6+: open 跟踪
        self.opened_containers: set = set()
        self._pending_open: bool = False  # 刚open了一个容器，等待look inside

        # V6+: 容器遍历跟踪
        self.tried_recep_locs: set = set()
        self.put_attempts: int = 0

        # 中英参数

        self.obj_en = ''

        self.target_en = ''

        self.preproc_en = ''

        self.obj_cn = ''

        self.target_cn = ''



        # 最新 obs 缓存(供决策用)

        self._latest_obs = ''

        self._latest_state = {}

        self._latest_admissible = ['look']

        self.last_action = ''



    # ──── A层: 初始任务理解 ────



    def reset(self, task_desc: str, task_type: str):
        """新任务：注意力机制驱动语义理解"""
        self.task_type = task_type
        # ═══ 注意力机制：重置空间探索层 + LLM语义引导 ═══
        self._spatial_explorer = SpatialExplorationLayer(llm_guide=self._semantic_guide)
        self._spatial_explorer.reset(task_desc, task_type)
        self.task_desc = task_desc
        self.holding = None
        self.processed = False
        self.current_location = ''
        self.visited = {"起点"}
        self._done_flag = False
        self._stale_completion_count = 0
        self.step_count = 0
        self._latest_obs = ''
        self._latest_state = {}
        self._latest_admissible = ['look']
        self.last_action = ''
        self._taken_objects = set()
        # 使用全局 ExplorationMemory 单例（跨局知识积累）
        global _EXPLORATION_MEMORY_SINGLETON
        if '_EXPLORATION_MEMORY_SINGLETON' not in globals() or _EXPLORATION_MEMORY_SINGLETON is None:
            _EXPLORATION_MEMORY_SINGLETON = ExplorationMemory()
        self._exploration_memory = _EXPLORATION_MEMORY_SINGLETON

        # ═══ 重置 YLYW 子目标引擎（复用单例，保留跨局知识） ═══
        if '_SUBGOAL_ENGINE_SINGLETON' not in globals() or \
           '_SUBGOAL_ENGINE_SINGLETON' not in globals() or globals().get('_SUBGOAL_ENGINE_SINGLETON') is None:
            globals()['_SUBGOAL_ENGINE_SINGLETON'] = SubgoalEngine(verbose=False)
        self._subgoal_engine = globals()['_SUBGOAL_ENGINE_SINGLETON']
        self._subgoal_engine.reset_feedback()
        self._enhanced_attention = EnhancedAttention(verbose=False)

        # V6+: 物体位置记忆 + open + 容器遍历
        self.object_memory = {}
        self.opened_containers = set()
        self._pending_open = False
        self.tried_recep_locs = set()
        self.put_attempts = 0

        # 执行反馈缓存（reset 后清空）
        self._last_intent = ''
        self._last_intent_result = ''
        self._last_intent_retry = 0

        # 任务类型推断（保留用于顶层路由）
        desc = task_desc.lower().strip()
        is_light = any(kw in desc for kw in ['lamp','light','examine','look at'])
        is_clean = any(kw in desc for kw in ['clean','wash','rinse','fill'])
        is_heat = any(kw in desc for kw in ['heat','microwave','warm','cook','hot'])
        is_cool = any(kw in desc for kw in ['cool','fridge','chill','cold','freeze'])
        is_two = any(kw in desc for kw in ['two','both','sets'])
        if is_light and not is_clean and not is_heat and not is_cool:
            self.task_type = 'look_at_obj_in_light'
        elif is_two:
            self.task_type = 'pick_two_obj_and_place'
        elif is_clean:
            self.task_type = 'pick_clean_then_place_in_recep'
        elif is_heat:
            self.task_type = 'pick_heat_then_place_in_recep'
        elif is_cool:
            self.task_type = 'pick_cool_then_place_in_recep'
        else:
            self.task_type = 'pick_and_place_simple'

        # ═══ 注意力机制：用 LLM 语义引导增强实体提取 ═══
        guide_entities = self._semantic_guide.get_target_entities(task_desc, self.task_type)
        guide_objects = guide_entities.get('objects', [])
        guide_locations = guide_entities.get('locations', [])
        guide_tools = guide_entities.get('tools', [])

        # 注意力机制：物体→位置关联推理
        self._object_hints = guide_entities.get('object_location_hints', {})
        self._exploration_priority = guide_entities.get('exploration_priority', [])

        # 注意力机制: guide_tools 修复 preproc_en
        tool_names = [t[0] for t in guide_tools]
        if tool_names and (self.task_type == 'look_at_obj_in_light' or 'lamp' in desc or 'light' in desc):
            for tn in ['desklamp', 'floorlamp', 'lightswitch']:
                if tn in tool_names:
                    self.preproc_en = tn
                    break

        if self.verbose:
            print(f"  [注意力] 引导: obj={guide_objects} loc={guide_locations} tool={tool_names}")

        # 直接把关键中英文词构建成中文任务句，送语义引擎
        obj_kw = {'plate':'盘子','bowl':'碗','mug':'杯子','cup':'杯子','coffee':'杯子',
                  'apple':'苹果','potato':'土豆','soap':'肥皂','knife':'刀',
                  'pencil':'铅笔','pillow':'枕头','clock':'闹钟','alarm':'闹钟',
                  'key':'钥匙','box':'盒子','lamp':'灯','light':'灯',
                  'pan':'锅','pot':'锅','spoon':'勺子','fork':'叉子',
                  'towel':'毛巾','book':'书','vase':'花瓶','cellphone':'手机',
                  'tomato':'番茄','egg':'鸡蛋','bread':'面包','lettuce':'生菜',
                  'glass':'杯子','dishsponge':'海绵','soapbar':'肥皂','soapbottle':'洗手液',
                  'toiletpaper':'卫生纸','tissuebox':'纸巾盒','candle':'蜡烛',
                  'ladle':'汤勺','kettle':'水壶','milk':'牛奶','paper':'纸',
                  'laptop':'笔记本','newspaper':'报纸','statue':'雕像','watch':'手表',
                  'remotecontrol':'遥控器','creditcard':'信用卡','pen':'笔',
                  'pillow':'枕头','butterknife':'黄油刀','peppershaker':'胡椒瓶',
                  'saltshaker':'盐瓶','spraybottle':'喷壶','scrubbrush':'刷子',
                  'baseballbat':'棒球棒','basketball':'篮球','food':'食物'}
        proc_kw = {'clean':'洗干净','wash':'洗干净','rinse':'洗干净','fill':'装满',
                   'heat':'加热','microwave':'加热','warm':'加热','cook':'加热','hot':'加热',
                   'cool':'冷却','fridge':'冷却','chill':'冷却','cold':'冷却','freeze':'冷却'}
        # V17⛳: loc_kw 按长词优先 + 别名映射
        # 三要素：匹配 keyword → 找到 ALFWorld 标准容器名（首位）→ 中文名
        # 用 POSITION_ALIAS 确保 'bin'→'garbagecan', 'trash'→'garbagecan' 等
        loc_kw = []
        for alias_en, real_names in self.POSITION_ALIAS.items():
            # real_names[0] 是标准 ALFWorld 容器名
            real_en = real_names[0] if real_names else alias_en
            # 中文照旧
            loc_cn = {'countertop':'柜台','garbagecan':'垃圾桶','desklamp':'灯',
                      'fridge':'冰箱','microwave':'微波炉','shelf':'架子',
                      'drawer':'抽屉','cabinet':'柜子','sinkbasin':'水槽',
                      'desk':'桌子','sofa':'沙发','safe':'保险箱',
                      'diningtable':'餐桌','sidetable':'边桌','coffeetable':'茶几',
                      'bed':'床','toilet':'马桶','bathtub':'浴缸',
                      'armchair':'扶手椅','chair':'椅子','stoveburner':'灶台',
                      'coffeemachine':'咖啡机','handtowelholder':'毛巾架',
                      'laundryhamper':'洗衣篮','tvstand':'电视柜','toaster':'烤面包机',
                      'ottoman':'矮凳','cart':'推车','pan':'锅',
                      'bin':'垃圾桶','lamp':'灯','table':'桌子',
                      'counter':'柜台','sink':'水槽','garbage':'垃圾桶',
                      'trash':'垃圾桶','stove':'灶台','oven':'微波炉',
                      'cupboard':'柜子',
                     }.get(real_en, real_en.replace('_',''))
            loc_kw.append((alias_en, loc_cn, real_en))
        # 按 alias 长度降序排列（长词先匹配）
        loc_kw.sort(key=lambda x: -len(x[0]))
        
        cn_parts = []
        _obj_en_found = ''
        _target_en_found = ''
        _proc_en_found = ''
        for en, cn in obj_kw.items():
            if en in desc:
                cn_parts.append(cn)
                _obj_en_found = en
                self.obj_cn = cn
                break
        for en, cn in proc_kw.items():
            if en in desc:
                cn_parts.append(cn)
                _proc_en_found = en
                break
        # 先把英文描述完整译成中文，让语义引擎理解语义（如"移到别处"、"放到不同位置"）
        # 用物体关键词翻译：找到物体名就翻译描述中的整句
        desc_cn_translated = desc
        for en, cn in obj_kw.items():
            if en in desc:
                # 对整个描述做中英关键词替换
                desc_cn_translated = desc_cn_translated.replace(en, cn)
                break
        for en, cn in proc_kw.items():
            if en in desc:
                desc_cn_translated = desc_cn_translated.replace(en, cn)
                break
        # 特殊短语翻译（"move ... over" → "移动...到别处"）
        if re.search(r'move\s+.*\s+over', desc, re.I):
            desc_cn_translated = desc_cn_translated.replace('over', '到别处')
        if 'different area' in desc.lower() or 'different part' in desc.lower():
            desc_cn_translated += '放到不同位置'
        if 'put it back' in desc.lower():
            desc_cn_translated = desc_cn_translated.replace('put it back', '重新放到')
            desc_cn_translated += '放到另一个地方'
        # 位置匹配：先用 LLM 知识库推测物体可能位置，不单靠词匹配
        # LLMSemanticGuide 的 object_to_locations 能给建议位置
        guide_hints = self._semantic_guide.get_object_hints(desc, _obj_en_found) if _obj_en_found else []
        # loc_kw 现在是 (alias_en, loc_cn, real_en) 三元组  
        # 用词匹配找到目标位置，但不立刻定死——留到后面通过语义引擎的路由决策
        for alias_en, loc_cn, real_en in loc_kw:
            if alias_en in desc:
                cn_parts.append(f'放到{loc_cn}')
                _target_en_found = real_en
                self.target_cn = loc_cn
                break
        # 但如果描述暗示"移到别处"或"不同位置"，用位置变体号推理
        # 这时 target_en 保留，但语义引擎会通过"放到不同位置"理解
        
        if is_light:
            cn_parts.append('用灯看')
        if is_two:
            cn_parts.append('两个')
        
        task_cn = ' '.join(cn_parts) if cn_parts else f'处理{desc[:30]}'
        
        # 送语义引擎
        result = self.engine.sentence(task_cn)
        self.task_hexagram = result['main_hexagram']
        self.task_yao = result['yao_vector']
        self.task_hex64 = result['hex64']

        # ═══ 初始化子目标引擎 ═══
        self._subgoal_engine.reset(self.task_type, self.task_yao, task_cn)
        if self.verbose:
            sg_count = self._subgoal_engine.get_subgoal_count()
            print(f"  [子目标引擎] {sg_count} 阶段分解完成")

        # 场景记忆初始化
        self.scene_state = SceneState()
        self.scene_state.task_type = self.task_type
        self.scene_state.task_desc = task_desc
        self.scene_hexagram = '?'
        self.scene_yao = [0.5]*6
        self.scene_hex64 = [0.0]*64
        self.scene_memory = []

        self._task_desc = task_desc
        self._task_cn = task_cn
        self.obj_en = _obj_en_found
        self.target_en = _target_en_found

        # ═══ 注意力机制：用 LLM 引导结果覆盖硬编码提取（引导优先） ═══
        if guide_objects:
            guide_obj_en = guide_objects[0]
            tool_keywords = ["desklamp", "floorlamp", "lightswitch", "lamp"]
            if guide_obj_en not in tool_keywords:
                self.obj_en = guide_obj_en
            elif guide_obj_en == "lamp" and len(guide_objects) > 1:
                self.obj_en = guide_objects[1]
        if guide_locations and "countertop" in [l[0] for l in guide_locations]:
            # 注意力机制：用引导结果覆盖 target_en
                for _, _, real_en in loc_kw:
                    if real_en == "countertop":
                        self.target_en = real_en
                        break

        # 预处理设备从任务类型推断
        self.preproc_en = ''
        if self.task_type == 'pick_clean_then_place_in_recep':
            self.preproc_en = 'sinkbasin'
        elif self.task_type == 'pick_cool_then_place_in_recep':
            self.preproc_en = 'fridge'
        elif self.task_type == 'pick_heat_then_place_in_recep':
            self.preproc_en = 'microwave'
        elif self.task_type == 'look_at_obj_in_light':
            self.preproc_en = 'desklamp'

        if self.verbose:
            print(f"  [注意力最终] obj_en={self.obj_en} target_en={self.target_en} preproc={self.preproc_en}")
            print(f"  [任务] {task_cn}")
            print(f"  [卦象] {self.task_hexagram} yao={[round(x,2) for x in self.task_yao]}")

    def _update_scene(self, obs: str, action: str):

        """每步 obs → 汉字引擎理解 → 更新场景记忆卦象"""

        state = ObsParser.parse_observation(obs, self.current_location or "起点")

        loc_raw = state['location']

        loc_norm = ObsParser.norm(loc_raw)



        if loc_raw != self.current_location and loc_raw not in ('起点',):

            self.current_location = loc_raw

            self.visited.add(ObsParser.key(loc_raw))



        # 同步 SceneState

        self.scene_state.update_from_obs(obs, action)



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

        loc_cn = EN2CN_LOC_FULL.get(loc_norm, loc_norm)

        parts.append(f'在{loc_cn}')



        if state['visible_objects']:

            obj_cns = []

            for obj in state['visible_objects'][:3]:

                obj_base = ObsParser.norm(obj)

                cn = EN2CN_OBJ_FULL.get(obj_base, obj_base)

                obj_cns.append(cn)

            if obj_cns:

                parts.append(f'看到{"".join(obj_cns)}')



        if took_item:

            obj_base = ObsParser.norm(self.holding) if self.holding else ''

            obj_cn = EN2CN_OBJ_FULL.get(obj_base, obj_base)

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



        scene_text = ','.join(parts)

        if not parts:

            return



        result = self.engine.sentence(scene_text)



        # 方向A: 直接用最新场景帧,不做滑动平均

        self.scene_yao = list(result['yao_vector'])

        self.scene_hex64 = list(result['hex64'])

        self.scene_hexagram = result['main_hexagram']



        self.scene_memory.append({

            'step': self.step_count, 'action': action or '',

            'text': scene_text, 'hexagram': result['main_hexagram'],
            'obs': obs,

        })



        if self.verbose:

            print(f"  [场景] {scene_text}")

            print(f"  [场景卦] {result['main_hexagram']} yao={[round(x,2) for x in result['yao_vector']]}")

            print(f"  [记忆卦] {self.scene_hexagram} yao={[round(x,2) for x in self.scene_yao]}")



    # ──── C层: 意图涌现(结构化状态 + 六爻模式匹配) ────



    # 各意图的六爻模式模板（极端化：用 0.05 和 0.95 拉开区分度）

    # 六爻维度：初爻位置、二爻持有、三爻处理、四爻环境、五爻目标、上爻完成

    INTENT_GUA_PATTERNS = {

        "goto探索":    [0.30, 0.05, 0.05, 0.05, 0.50, 0.05],  # 持有极低、处理极低、完成极低

        "拿取":        [0.50, 0.95, 0.30, 0.50, 0.50, 0.10],  # 持有极高、处理低

        "去预处理":    [0.70, 0.70, 0.10, 0.30, 0.70, 0.10],  # 位置动、持有中、处理极低

        "去目标":      [0.70, 0.70, 0.40, 0.30, 0.95, 0.20],  # 位置动、持有中、目标极高

        "放入设备":    [0.50, 0.70, 0.95, 0.80, 0.40, 0.30],  # 处理极高、环境高

        "放置":        [0.50, 0.70, 0.60, 0.50, 0.80, 0.80],  # 目标高、完成高

        "完成":        [0.50, 0.05, 0.50, 0.40, 0.60, 0.95],  # 持有极低、完成极高

    }



    def _match_intent_by_gua(self, scene_yao: list) -> Tuple[str, float]:

        """六爻欧氏距离匹配 + 排序得分归一化"""

        best_intent = "goto探索"

        best_dist = float('inf')

        # 计算各意图的距离并选最近

        dists = {}

        for intent, pattern in self.INTENT_GUA_PATTERNS.items():

            dist = sum((a - b) ** 2 for a, b in zip(scene_yao, pattern)) ** 0.5

            dists[intent] = dist

            if dist < best_dist:

                best_dist = dist

                best_intent = intent

        # 得分归一化：距离越小得分越高

        max_dist = max(dists.values()) if dists else 1.0

        score = 1.0 - (best_dist / max_dist) if max_dist > 0 else 0.5

        return best_intent, score



    def _decide_intent(self) -> Tuple[str, float]:

        """

        意图涌现：让 YLYW 语义引擎理解完整情景。

        

        将任务描述、场景状态、历史摘要合并为一段情景文本，

        送进 HanziEngine，由它推理出当前意图。

        

        取代了原来结构化状态 + 六爻模式匹配的混合方式。

        """

        if not self.scene_memory:
            return "goto探索", 0.0

        has_inv = bool(self.holding is not None)

        # ═══════════════════════════════════════════════════
        # YLYW 子目标引擎驱动（新增，优先级最高）
        # ═══════════════════════════════════════════════════
        tracker_taken = len(self._taken_objects)
        sg_idx, sg_label, sg_yao = self._subgoal_engine.track(
            self.scene_yao, self.holding, self.processed,
            taken_count=tracker_taken,
            scene_obs=self._latest_obs if hasattr(self, '_latest_obs') else ''
        )
        subgoal_intent = self._subgoal_engine.get_current_intent()

        # ═══ 任务类型顶层路由（特殊任务仍需专用 handler） ═══

        if self.task_type == 'look_at_obj_in_light':
            # look_at 流程: 拿到目标物体 mug → 到 desklamp → use → examine
            if has_inv:
                # 手持物体，目标是到灯的位置
                loc_norm = ObsParser.norm(self.current_location or '')
                if 'desklamp' in loc_norm or 'lamp' in loc_norm or 'desk' in loc_norm:
                    # 在灯附近 → 用灯
                    return "放入设备", 0.0
                return "去目标", 0.0
            # 空手：先判断是否已用过灯
            if self.processed:
                return "完成", 0.0
            # 空手且没用过灯：如果有目标物体 → 拿取
            # 但 lamp 类型不需要拿取（灯是固定设备，不是可拿物体）
            if self.obj_en and self.task_type == 'look_at_obj_in_light' and \
               self.obj_en in ('lamp', 'desklamp', 'floorlamp'):
                # lamp 不需要拿取 → 直接去灯位置 use
                loc_norm = ObsParser.norm(self.current_location or '')
                has_use_cmd = any(c.startswith('use ') for c in (self._latest_admissible or []))
                if 'desklamp' in loc_norm or 'lamp' in loc_norm or has_use_cmd:
                    return "放入设备", 0.0
                return "去目标", 0.0
            if self.obj_en:
                return "拿取", 0.0
            # 没有目标物体（如 'Turn on the desk lamp.'）→ 去灯位置 use
            loc_norm = ObsParser.norm(self.current_location or '')
            has_use_cmd = any(c.startswith('use ') for c in (self._latest_admissible or []))
            if 'desklamp' in loc_norm or 'lamp' in loc_norm or has_use_cmd:
                return "放入设备", 0.0
            return "去目标", 0.0

        

        if self.task_type == 'pick_two_obj_and_place':
            # 完成条件保留（需要 has_put 检查）
            if not has_inv and len(self._taken_objects) >= 2:
                has_put = any('you put' in m.get('obs','').lower() or 'you place' in m.get('obs','').lower() 
                             or 'you move' in m.get('obs','').lower() 
                             for m in self.scene_memory)
                if has_put:
                    return ("完成", 1.0)
            # 子目标引擎驱动
            sg_intent = self._subgoal_engine.get_current_intent()
            sg_label = self._subgoal_engine.current_label
            # 如果子目标引擎说"拿取"但实际已持有 → 用"放置"
            if sg_intent == "拿取" and has_inv:
                return ("放置", 0.8)
            # 取第二件时：增强探索
            if sg_label == "取第二件" and not has_inv:
                # 优先从 object_memory 中查找同类物体
                taken_bases = set()
                for t in self._taken_objects:
                    base = re.sub(r'\s+\d+$', '', t).strip()
                    taken_bases.add(base)
                # 找同类物体的已知位置
                for obj_name, loc in self.object_memory.items():
                    obj_base = re.sub(r'\s+\d+$', '', obj_name.lower()).strip()
                    if obj_base in taken_bases or (self.obj_en and self.obj_en in obj_base):
                        go_cmd = f'go to {loc}'
                        if go_cmd in (self._latest_admissible or []) and                            loc != ObsParser.key(self.current_location or ''):
                            return ("拿取", 0.9)
                # 用知识库推荐同类物体的常见位置
                if self.obj_en:
                    object_kb = getattr(self._enhanced_attention, 'object_kb', {})
                    known_locs = object_kb.get(self.obj_en, [])
                    if known_locs:
                        for known_loc in known_locs:
                            for c in (self._latest_admissible or []):
                                if c.startswith('go to ') and known_loc in c[6:]:
                                    loc_key = ObsParser.key(c[6:])
                                    if loc_key not in self.visited:
                                        return ("探索", 0.9)
                # 无已知位置 → 用增强注意力排序
                go_cmds = [c for c in (self._latest_admissible or []) if c.startswith('go to ')]
                if go_cmds:
                    ranked = self._enhanced_attention.rank_locations(
                        go_cmds, self.obj_en or '', "拿取",
                        {ObsParser.key(v) for v in self.visited}
                    )
                    if ranked:
                        return ("探索", 0.85)
            # 如果子目标说"探索"但已拿过0个且空手 → 应该拿取
            if sg_intent == "goto探索" and len(self._taken_objects) == 0 and not has_inv:
                return ("拿取", 0.8)
            # 执行反馈：连续失败3次 → 切换探索
            if self._last_intent_retry >= 3 and self._last_intent_result == 'FAIL:拿取':
                self._last_intent_retry = 0
                return ("探索", 0.0)
            return (sg_intent, 0.8)

        if self.task_type == "pick_and_place_simple":
            """仅需拿一样物体放置到一个位置（可能是目标位置也可能是其他位置）
            
            严格完成条件：
              1) 空手
              2) 确实拿过目标物体
              3) 确实成功 move/put 到了同类型另一个位置（pd-->pd是无效）
            """
            if not has_inv and len(self._taken_objects) >= 1:
                has_put = any('you put' in m.get('obs','').lower() or 'you place' in m.get('obs','').lower() 
                             or 'you move' in m.get('obs','').lower() 
                             for m in self.scene_memory)
                
                if not has_put:
                    return ("拿取", 0.0)
                
                # has_put == True: 成功 move/put 过
                # 统计连续 take→move 的步数（不计 go to）
                stale_take_move = 0
                for m in reversed(self.scene_memory[-10:]):
                    act = m.get('action','')
                    if act.startswith('take ') or act.startswith('move '):
                        stale_take_move += 1
                    elif act.startswith('go to '):
                        break  # 遇到 go to 说明有新位置探索
                    else:
                        continue
                
                # 检查是否已经在不同编号位置放过了（有 move 到 != 原始 target_en 编号）
                has_moved_to_variant = False
                if self.target_en:
                    loc_base = self.target_en.split(' ')[0]
                    for m in self.scene_memory:
                        act = m.get('action','')
                        if act.startswith('move ') and loc_base in act:
                            target_parts = act.split(' to ')[-1].strip() if ' to ' in act else ''
                            t_parts = target_parts.rsplit(' ', 1)
                            t_num = t_parts[-1] if len(t_parts) > 1 else ''
                            if t_num and t_num.isdigit() and int(t_num) > 1:
                                has_moved_to_variant = True
                                break
                
                # 触发条件：原始循环（stale>=6）或已经在不同编号放过了（但没 won）
                if stale_take_move >= 6 or has_moved_to_variant:
                    # 超过6步原地 take→move 循环 → 用知识库推测其他类型位置
                    guide_hints = self._semantic_guide.get_object_hints(
                        self._task_desc if hasattr(self, '_task_desc') else '', self.obj_en) if self.obj_en else []
                    if guide_hints and self.obj_en:
                        # 把已尝试过的位置和当前 target_en 都标记为已尝试
                        if not hasattr(self, '_tried_locs'):
                            self._tried_locs = set()
                        self._tried_locs.add(self.target_en or '')
                        # 从知识库中找下一个未尝试的位置
                        next_target = None
                        for hint_loc in guide_hints:
                            if hint_loc not in self._tried_locs:
                                next_target = hint_loc
                                break
                        if next_target:
                            self._tried_locs.add(next_target)
                            self.target_en = next_target
                            return ("探索", 0.9)
                        # 所有知识库位置都试过了 → 退回探索
                        return ("探索", 0.85)
                    return ("探索", 0.85)
                
                # 检查最近5步是否有 go to → 到了新位置就尝试拿取
                recent_go_count = sum(1 for m in self.scene_memory[-6:]
                                     if m.get('action','').startswith('go to '))
                if recent_go_count > 0:
                    # 有 go to 动作 → 尝试拿取（带着物体去新位置放）
                    return ("拿取", 0.9)
                
                # 没有 go to → 继续原地尝试
                return ("拿取", 0.0)
            if has_inv:
                return ("放置", 0.0)
            if self._last_intent_retry >= 3 and self._last_intent_result == 'FAIL:拿取':
                self._last_intent_retry = 0
                return ("探索", 0.0)
            return ("拿取", 0.0)

        # ═══════════════════════════════════════════════════
        # 通用任务：子目标引擎驱动（优先级最高）
        # ═══════════════════════════════════════════════════
        # 对于 pick_and_place_simple / pick_clean / pick_cool / pick_heat
        # 子目标引擎已经通过状态检测给出了当前子目标
        if self.task_type in ('pick_and_place_simple',
                              'pick_clean_then_place_in_recep',
                              'pick_heat_then_place_in_recep',
                              'pick_cool_then_place_in_recep'):
            sg_intent = self._subgoal_engine.get_current_intent()
            sg_label = self._subgoal_engine.current_label

            # 但如果子目标引擎说"拿取"但手上有 → 覆盖
            if sg_intent == "拿取" and has_inv:
                if self.preproc_en and not self.processed:
                    return ("去预处理", 0.8)
                return ("去目标", 0.8)

            # 子目标引擎说"goto探索"但场景中有直接可拿的 → 拿取
            if sg_intent == "goto探索" and not has_inv and self.obj_en:
                has_take = any(c.startswith('take ') and self.obj_en in c
                              for c in (self._latest_admissible or []))
                if has_take:
                    return ("拿取", 0.9)

            # 子目标引擎说"完成"但 holding 还在 → 放置
            if sg_intent == "完成" and has_inv:
                return ("放置", 0.8)

            # 子目标引擎说"完成"但环境没给 won → 检测假完成
            # 如果最近10步内有同一位置重复 move → 假完成
            # 或者已经在"完成"意图上循环多次
            if sg_intent == "完成" and not has_inv:
                recent_acts = [m.get('action','') for m in self.scene_memory[-10:]]
                same_place_move = sum(1 for a in recent_acts 
                                     if a.startswith('move ') and self.current_location 
                                     and self.current_location in a)
                if same_place_move >= 2:
                    return ("探索", 0.7)
                # 检测是否一直在 look/examine 但不触发 won
                stale_look = sum(1 for a in recent_acts 
                                if a == 'look' or a.startswith('examine '))
                if stale_look >= 3:
                    # 检查是否有未尝试的目标位置变体
                    if self.target_en:
                        loc_base = self.target_en.split(' ')[0]
                        go_cmds = [c for c in (self._latest_admissible or [])
                                  if c.startswith('go to ') and loc_base in c[6:]]
                        if go_cmds:
                            return ("去目标", 0.8)
                    return ("探索", 0.7)
                # 首次进入"完成"：先 look 确认
                exam_cmds = [c for c in (self._latest_admissible or [])
                            if c.startswith('examine ')]
                if exam_cmds:
                    return ("完成", 0.9)
                # 对 pick_and_place_simple：尝试去其他位置类型放置
                if self.task_type == 'pick_and_place_simple' and has_inv:
                    go_cmds = [c for c in (self._latest_admissible or []) if c.startswith('go to ')]
                    cur_base = (ObsParser.norm(self.current_location or '') or '').split(' ')[0]
                    for c in go_cmds:
                        target_base = c[6:].strip().split(' ')[0]
                        if target_base != cur_base:
                            return ("去目标", 0.8)
                    return ("探索", 0.7)

            # ⭐ 关键修复：如果子目标引擎说"去预处理"但已在预处理设备处
            # 应该改成"放入设备"（执行 clean/cool/heat 命令）
            if sg_intent in ("去预处理", "goto探索") and has_inv and self.preproc_en and not self.processed:
                if self._is_at_preproc():
                    return ("放入设备", 0.9)

            # ⭐ 如果子目标引擎说"去目标"但已在目标位置 → 放置
            if sg_intent == "去目标" and has_inv and self.target_en:
                if self._is_at_target():
                    return ("放置", 0.9)

            # ⭐ 子目标"拿取"空手但有可见的 take 命令
            if sg_intent == "拿取" and not has_inv and self.obj_en:
                has_take = any(c.startswith('take ') and self.obj_en in c.split()[1:2]
                              for c in (self._latest_admissible or []))
                if has_take:
                    return ("拿取", 0.95)
                # 没有 direct take → 优先 open 当前容器
                open_cmds = [c for c in (self._latest_admissible or [])
                            if c.startswith('open ')]
                if open_cmds:
                    # 优先开当前位置的容器
                    cur_loc = ObsParser.norm(self.current_location or '')
                    for oc in open_cmds:
                        container = oc.replace('open ', '').strip()
                        if container not in self.opened_containers:
                            if cur_loc and (cur_loc in container or container in cur_loc):
                                return ("拿取", 0.8)
                    # 第二优先：开任何没开过的容器
                    for oc in open_cmds:
                        container = oc.replace('open ', '').strip()
                        if container not in self.opened_containers:
                            return ("拿取", 0.8)

            # ⭐ 子目标"拿取"空手但 go to 很多步仍不可拿
            # → 用增强注意力推荐有容器的位置
            if sg_intent in ("拿取", "goto探索") and not has_inv:
                recent_steps = [m.get('action','') for m in self.scene_memory[-10:]]
                go_count = sum(1 for a in recent_steps if a.startswith('go to '))
                open_count = sum(1 for a in recent_steps if a.startswith('open '))
                
                # 检测是否在同一位置类型循环
                go_targets = [a[6:].strip() for a in recent_steps if a.startswith('go to ')]
                loc_bases = set(t.split(' ')[0] if ' ' in t else t for t in go_targets)
                
                if len(loc_bases) <= 1 and go_count >= 4 and open_count == 0:
                    # 同一个位置类型循环4次以上且没 open→ 强制去有容器的位置
                    go_cmds = [c for c in (self._latest_admissible or []) if c.startswith('go to ')]
                    container_locs = []
                    other_locs = []
                    for c in go_cmds:
                        loc_name = c[6:].strip()
                        loc_base = loc_name.split(' ')[0]
                        if any(kw in loc_name for kw in ['cabinet','drawer','shelf','fridge',
                                                           'microwave','safe','dresser']):
                            container_locs.append(c)
                        elif loc_base not in loc_bases:
                            other_locs.append(c)
                    
                    # 优先去有容器的位置
                    for target in container_locs + other_locs:
                        target_key = ObsParser.key(target[6:])
                        if target_key not in self.visited:
                            self._tried_locs.add(target_key)
                            return ("goto探索", 0.9)
                    # 都没去过→去任何一个没去过的
                    for c in go_cmds:
                        target_key = ObsParser.key(c[6:])
                        if target_key not in self.visited:
                            return ("goto探索", 0.8)

            return (sg_intent, 0.85)

        # ═══ 构建情境文本，让语义引擎产出"进度差距卦象" ═══

        # 情境卦象 vs 任务卦象 的差距向量 = 当前进度差距

        # 送进语义引擎的情境包含"任务"+"当前状态"+"还差什么"

        context_parts = []

        

        # 任务描述

        if hasattr(self, '_task_cn') and self._task_cn:

            context_parts.append(f'任务是{self._task_cn}')

        elif self.obj_cn and self.target_cn:

            context_parts.append(f'任务是拿{self.obj_cn}放到{self.target_cn}')

        else:

            context_parts.append(f'任务是{self.task_desc[:40]}')

        

        # 当前状态

        loc_cn = EN2CN_LOC_FULL.get(ObsParser.norm(self.current_location or ''), 

                                      self.current_location or '起点')

        status = f'现在在{loc_cn}'

        if has_inv:

            obj_base_cn = EN2CN_OBJ_FULL.get(ObsParser.norm(self.holding), self.holding or '')

            status += f'拿着{obj_base_cn}'

        else:

            status += '空手'

        if self.processed:

            status += '已处理好'

        context_parts.append(status)

        

        # 还差什么

        gap_parts = []

        if not has_inv and self.obj_cn:

            gap_parts.append('还需要找物体')

        elif has_inv and not self.processed and self.preproc_en:

            gap_parts.append('还需要去预处理')

        elif has_inv and self.obj_cn:

            gap_parts.append('还需要去目标位置')

        if gap_parts:

            context_parts.append(''.join(gap_parts))

        

        context_text = '。'.join(context_parts)

        

        # 送进语义引擎，产出"差距卦象"

        result = self.engine.sentence(context_text)

        gap_yao = result['yao_vector']

        gap_hexagram = result['main_hexagram']

        

        # 计算差距卦象 - 任务卦象的差值，作为进度信号

        delta_yao = [gap_yao[i] - self.task_yao[i] for i in range(6)]

        

        # 六爻模式匹配（辅助信号）

        pattern_intent, pattern_score = self._match_intent_by_gua(gap_yao)

        

        if self.verbose:

            print(f"  [情境] {context_text}")

            print(f"  [任务卦] {self.task_hexagram} yao={[round(x,2) for x in self.task_yao]}")

            print(f"  [差距卦] {gap_hexagram} yao={[round(x,2) for x in gap_yao]}")

            print(f"  [差距] d0={delta_yao[0]:.3f} d1={delta_yao[1]:.3f} d2={delta_yao[2]:.3f} "

                  f"d3={delta_yao[3]:.3f} d4={delta_yao[4]:.3f} d5={delta_yao[5]:.3f}")

            print(f"  [模式→意图] {pattern_intent}({pattern_score:.3f})")



        # ═══ 结构化状态主决策（可靠，情境卦象差距作为调试参考） ═══

                # ── 通用完成检测（严格版）──
        # pick_and_place_simple 不在这里检测，由其专用 handler 处理
        # 但所有"完成"意图都需检查是否陷入完成循环
        if not has_inv:
            has_taken = len(self._taken_objects) >= 1
            if has_taken:
                # 对于有预处理的任务（pick_clean/cool/heat）：只允许一次"完成"
                # 第一次"完成"后 set _done_flag=True，后续不再返回完成
                if self.task_type in ('pick_clean_then_place_in_recep',
                                      'pick_heat_then_place_in_recep',
                                      'pick_cool_then_place_in_recep'):
                    if self.processed and not self._done_flag:
                        # 检查最近5步内是否是同一位置 move→take→move 循环
                        recent_acts = [m.get('action','') for m in self.scene_memory[-10:]]
                        same_place_move = sum(1 for a in recent_acts 
                                             if a.startswith('move ') and self.current_location 
                                             and self.current_location in a)
                        if same_place_move >= 2:
                            # 同一位置放了两次 → 不是真正完成
                            self._done_flag = True  # 防再次触发
                            return "探索", 0.8
                        self._done_flag = True
                        return "完成", 0.95
                    if self.processed and self._done_flag:
                        # 已经尝试过"完成"但环境没确认 → 切探索
                        # 尝试不同位置放置
                        return "探索", 0.7
                
                # pick_two_obj: 拿齐2个+空手=完成了
                if self.task_type == 'pick_two_obj_and_place' and len(self._taken_objects) >= 2:
                    if not self._done_flag:
                        self._done_flag = True
                        return "完成", 0.95
                    return "探索", 0.8
                if self.task_type == 'look_at_obj_in_light':
                    if self.processed:
                        self._stale_completion_count += 1
                        return "完成", 0.95
        # ── 非

        if has_inv:
            if self.preproc_en and not self.processed:
                if self._is_at_preproc():
                    return "放入设备", 0.0
                return "去预处理", 0.0
            if self._is_at_target():
                return "放置", 0.0
            # 保险：已经处理过且位置在 target_en 的 alias 范围内时也返回放置
            if self.processed and self.target_en:
                loc_norm = ObsParser.norm(self.current_location or '')
                sn_list = [self.target_en] + self.POSITION_ALIAS.get(self.target_en, [])
                for sn in sn_list:
                    if sn and self._match_position(loc_norm, sn):
                        return "放置", 0.0
            return "去目标", 0.0

        else:

            if self._has_target_in_admissible():

                return "拿取", 0.0

        

        # 空手且无直接目标：探索记忆驱动的主动探索

        # 用 YLYW 探索引擎（卦象匹配 + 记忆 + 知己学习）推荐下步位置

        # 不直接用硬编码的 goto探索，而是生成一个"探索意图卦象"

        if self._latest_admissible:

            admissible_moves = [c for c in self._latest_admissible if c.startswith('go to ')]

            if admissible_moves:

                obj_name = self.obj_en or ''

                ranked = self._exploration_memory.rank_by_affinity(

                    admissible_moves, obj_name, self.visited,

                    current_location=ObsParser.norm(self.current_location or ''),

                    task_yao=self.task_yao)

                

                if ranked:

                    best_cmd = ranked[0][0]

                    best_score = ranked[0][1]

                    

                    if self.verbose:

                        print(f"  [探索] 目标={obj_name} → {best_cmd} ({best_score:.3f})")

                    

                    # 将探索结果包装为意图，传入 _intent_to_action

                    # 用 custom_explore 意图标记，在 _intent_to_action 中识别

                    # 由于 _intent_to_action 不认识 custom_explore，

                    # 在 _fallback_navigate 中直接用记忆排序结果

                    # 这里先返回 goto探索，让 _fallback_navigate 处理

                    pass

        

        # 差距卦象辅助判断（场景记忆 > 3 步后启用）

        if len(self.scene_memory) > 3:

            if delta_yao[5] > 0.15 and delta_yao[1] < -0.10:

                return "完成", delta_yao[5]

        return "goto探索", 0.5



    def _has_target_in_admissible(self) -> bool:

        """检查 admissible 中是否有目标物体的 take 命令（精确匹配 + 排除已拿物体）"""

        if not self.obj_en:

            return False

        for cmd in self._latest_admissible:

            if cmd.startswith('take '):

                parts = cmd.split()

                if len(parts) >= 3:  # take <obj> <num> from <...>

                    obj_with_id = f"{parts[1].strip().lower()} {parts[2].strip()}"  # 'soapbottle 1'

                    obj_class = parts[1].strip().lower()  # 'soapbottle'

                    # obj_en 是目标物体前缀

                    if obj_class.startswith(self.obj_en):

                        # 检查是否已拿过：pick_two_obj_and_place 检查带编号的完整名

                        if self.task_type == 'pick_two_obj_and_place':

                            if obj_with_id not in self._taken_objects:

                                return True

                        else:

                            if obj_class not in self._taken_objects:

                                return True

        return False



    def _is_at_target(self) -> bool:
        loc_norm = ObsParser.norm(self.current_location or '')
        if not self.target_en:
            return False
        if self._match_position(loc_norm, self.target_en):
            return True
        for alias in self.POSITION_ALIAS.get(self.target_en, []):
            if self._match_position(loc_norm, alias):
                return True
        return False

    def _is_at_preproc(self) -> bool:
        loc_norm = ObsParser.norm(self.current_location or '')
        if not self.preproc_en:
            return False
        if self._match_position(loc_norm, self.preproc_en):
            return True
        for alias in self.POSITION_ALIAS.get(self.preproc_en, []):
            if self._match_position(loc_norm, alias):
                return True
        return False

    def _match_position(self, loc_norm: str, pos: str) -> bool:
        if not loc_norm or not pos:
            return False
        # 精确匹配或空格边界匹配
        if loc_norm == pos or loc_norm.endswith(' ' + pos) or loc_norm.startswith(pos + ' '):
            return True
        # 从 loc_norm 中提取 base 名称（去掉空格编号），再做匹配
        # 例：'countertop 1' 的 base 是 'countertop'
        loc_base = loc_norm.split(' ')[0] if ' ' in loc_norm else loc_norm
        if loc_base == pos:
            return True
        # 反过来：pos 的 base 匹配 loc_norm 的 base
        pos_base = pos.split(' ')[0] if ' ' in pos else pos
        return loc_base == pos_base



    def _recent_actions_contain(self, keyword: str, n: int = 5) -> bool:

        """检查最近 n 步的 scene_memory 中是否有包含 keyword 的动作"""

        recent = self.scene_memory[-n:] if len(self.scene_memory) >= n else self.scene_memory

        for m in recent:

            if keyword in m.get('action', ''):

                return True

        return False



    # ──── D层: 意图 → 动作选择(适配器驱动) ────



    def _intent_to_action(self, intent: str, admissible_cmds: List[str]) -> Optional[str]:

        """

        意图 → 动作原语适配器 → ALFWorld admissible command

        

        每个意图有直接的动作生成逻辑，不再完全依赖适配器的状态推测。

        """

        task_info = {

            'obj_en': self.obj_en,

            'target_en': self.target_en,

            'preproc_en': self.preproc_en,

            'task_type': self.task_type,

        }

        loc_norm = ObsParser.norm(self.current_location or '')

        

        # ── 任务类型专用 handler（优先级最高）──

        if self.task_type == 'look_at_obj_in_light':
            return self._handle_look_at_light(intent, admissible_cmds)
        if self.task_type == 'pick_two_obj_and_place':
            return self._handle_two_obj(intent, admissible_cmds)



        if intent == "完成":
            # 已完成意图但环境没给 won
            # 1次 look/examine 后没触发 won → 切探索（避免原地循环）
            # 同时重置 _stale_completion_count 防止连续完成检测
            last_1_stale = any(m.get('action','').startswith('examine ') or m.get('action','') == 'look'
                              for m in self.scene_memory[-1:])
            if not last_1_stale:
                # 首次完成：先 look/examine 确认状态
                exam_cmds = [c for c in admissible_cmds if c.startswith('examine ')]
                if exam_cmds:
                    return exam_cmds[0]
                if 'look' in admissible_cmds:
                    return 'look'
            # 已 look/examine 过或不可用 → 优先目标位置变体（如 desk 2 而不是 desk 1）
            # 到目标位置变体后尝试拿取/放置（pick_and_place_simple 需要不同位置）
            if self.holding:
                cur_loc = ObsParser.norm(self.current_location or '')
                put_cmds = [c for c in admissible_cmds 
                           if c.startswith('move ') and (cur_loc in c or not any(c.startswith('go to ')))]
                if put_cmds:
                    return put_cmds[0]
            else:
                if self.obj_en:
                    take_cmds = [c for c in admissible_cmds 
                                if c.startswith('take ') and c.split()[1].startswith(self.obj_en)]
                    if take_cmds:
                        return take_cmds[0]
                if self.target_en and not self.holding:
                    loc_base = self.target_en.split(' ')[0]
                    target_variants = [c for c in admissible_cmds 
                                       if c.startswith('go to ') and c[6:].startswith(loc_base)]
                    if target_variants:
                        # 不是当前位置的变体
                        cur_loc = ObsParser.norm(self.current_location or '')
                        for v in target_variants:
                            if cur_loc not in v:
                                return v
                        return target_variants[0]
            admissible_moves = [c for c in admissible_cmds if c.startswith('go to ')]
            if admissible_moves:
                # 优先选不在当前循环中的位置
                recent_go = [m.get('action','') for m in self.scene_memory[-6:]
                            if m.get('action','').startswith('go to ')]
                for m in admissible_moves:
                    if m not in recent_go:
                        return m
                return admissible_moves[0]
            return self._fallback_navigate(admissible_cmds)
        # ── 拿取：精确匹配目标物体名 ──
        # ── 拿取：精确匹配目标物体名 ──
        # ── 拿取：精确匹配目标物体名 ──

        if intent == "拿取":

            if self.obj_en:

                # 精确匹配：要求命令中的物体名以 obj_en 开头（单词边界）

                take_cmds = []

                for c in admissible_cmds:

                    if c.startswith('take '):

                        parts = c.split()

                        if len(parts) >= 2:

                            obj_in_cmd = parts[1]

                            if obj_in_cmd.startswith(self.obj_en):

                                take_cmds.append(c)

                if take_cmds:

                    # 偏好最短的物体名（最接近目标）

                    # 例如 soapbar 3 比 soapbottle 1 更接近 soap

                    take_cmds.sort(key=lambda c: len(c.split()[1]))

                    # V17⛳: 如果在当前位置就有 take 命令可用，优先直接拿

                    # 防止明明有直接 take 却先去 open 容器（如 pencil 在 desk 上敞开）

                    current_loc = ObsParser.norm(self.current_location or '')

                    for c in take_cmds:

                        if current_loc in c:

                            return c

                    return take_cmds[0]


            # V17⛳: 先检查 admissible 中是否有直接 take 命令（目标物体可见）

            # 如果目标物体在当前位置可见，不用开任何容器，直接 take

            if self.obj_en:

                direct_take = [c for c in admissible_cmds if c.startswith('take ') and self.obj_en in c]

                if direct_take:

                    # 偏好当前位置的 take

                    cur_loc = ObsParser.norm(self.current_location or '')

                    for c in direct_take:

                        if cur_loc in c:

                            return c

                    return direct_take[0]


            # 没有 take 可用：检查是否有 open 命令（打开当前容器找物体）

            if self.current_location:

                loc_key = ObsParser.key(self.current_location)

                open_cmds = [c for c in admissible_cmds if c.startswith('open ')]

                for oc in open_cmds:

                    container = oc.replace('open ', '').strip()

                    if loc_key and (loc_key in container or container in loc_key):

                        if container not in self.opened_containers:

                            return oc

                # 也 open 其他未开的容器

                for oc in open_cmds:

                    container = oc.replace('open ', '').strip()

                    if container not in self.opened_containers:

                        return oc


            # V6+: 检查 object_memory 中已知的目标物体位置

            if self.obj_en and self.object_memory:

                for obj_name, loc in self.object_memory.items():

                    obj_base = re.sub(r'\s+\d+$', '', obj_name.lower()).strip()

                    if obj_base == self.obj_en or obj_base.startswith(self.obj_en):

                        go_cmd = f'go to {loc}'

                        if go_cmd in admissible_cmds and loc != ObsParser.key(self.current_location or ''):

                            return go_cmd


            # 没有可拿目标 → go to 

            # 如果当前位置类型已访问多次且没有可取物体 → 标记为 exhausted
            cur_loc_key = ObsParser.key(self.current_location or '')
            if cur_loc_key:
                recent_actions = [m.get('action','') for m in self.scene_memory[-8:]] if self.scene_memory else []
                same_type_count = sum(1 for a in recent_actions if a.startswith('go to ') and
                                     cur_loc_key.split(' ')[0] in a[6:])
                if same_type_count >= 2:
                    if not hasattr(self, '_exhausted_locs'):
                        self._exhausted_locs = set()
                    self._exhausted_locs.add(cur_loc_key)

            # 未找到 take 目标，回退探索
            return self._fallback_navigate(admissible_cmds)

        

        # ── 去预处理 / 去目标：导航 ──

        def _expand_target(aliases: set) -> list:
            """V17⛳: 展开候选目标名列表（含别名）"""
            expanded = list(aliases)
            for name in list(aliases):
                for alias_key, real_names in self.POSITION_ALIAS.items():
                    if alias_key in name or name in alias_key:
                        for rn in real_names:
                            if rn not in aliases:
                                expanded.append(rn)
                        break
            return expanded

        if intent == "去预处理":

            if self.preproc_en:

                candidates = _expand_target({self.preproc_en})

                for con in candidates:

                    for i in range(1, 11):

                        c = f"go to {con} {i}"

                        if c in admissible_cmds:

                            return c

                # 模糊匹配

                for ac in admissible_cmds:

                    if ac.startswith('go to '):

                        loc = ac[6:].strip()

                        for con in candidates:

                            if con in loc:

                                return ac

            return self._fallback_navigate(admissible_cmds)

        

        if intent == "去目标":

            if self.target_en:

                candidates = _expand_target({self.target_en})

                for con in candidates:

                    for i in range(1, 11):

                        c = f"go to {con} {i}"

                        if c in admissible_cmds:

                            return c

                for ac in admissible_cmds:

                    if ac.startswith('go to '):

                        for con in candidates:

                            if con in ac:

                                return ac

            return self._fallback_navigate(admissible_cmds)

        

        # ── 放入设备：需要手持物体，在预处理设备旁 ──

        if intent == "放入设备":

            if self.holding and self.preproc_en:

                action_word = TOOL_ACTIONS.get(self.preproc_en, 'clean')

                obj_base = ObsParser.norm(self.holding)

                candidates = [

                    f"{action_word} {self.holding} with {self.preproc_en} 1",

                    f"{action_word} {obj_base} 1 with {self.preproc_en} 1",

                ]

                for c in candidates:

                    if c in admissible_cmds:

                        return c

                # 模糊匹配

                for ac in admissible_cmds:

                    if ac.startswith(action_word + ' '):

                        return ac

            # 不在设备处或没拿东西→先开设备或导航

            open_cmds = [c for c in admissible_cmds if c.startswith('open ')]

            if open_cmds:

                return open_cmds[0]

            return self._fallback_navigate(admissible_cmds)

        

        # ── 放置：手持物体，在目标处 ──

        if intent == "放置":
            
            # 防循环：如果最近一次 move 和当前在同一位置 → 去不同编号目标
            if self.holding:
                last_move_loc = None
                for m in reversed(self.scene_memory):
                    act = m.get('action','')
                    if act.startswith('move '):
                        if ' to ' in act:
                            last_move_loc = act.split(' to ')[-1].strip()  # 'desk 1'
                        break
                    if act.startswith('go to '):
                        break
                cur_loc_norm = ObsParser.norm(self.current_location or '')
                if last_move_loc and cur_loc_norm and (
                    last_move_loc == cur_loc_norm or                     last_move_loc.startswith(cur_loc_norm) or                     last_move_loc.replace(' ','').startswith(cur_loc_norm.replace(' ',''))):
                    # 刚在同一位置放下 → 这次不该放回原位
                    if self.target_en:
                        loc_base = self.target_en.split(' ')[0]
                        target_moves = [c for c in admissible_cmds 
                                       if c.startswith('go to ') and c[6:].startswith(loc_base)]
                        cur_loc_n = ObsParser.norm(self.current_location or '')
                        cur_loc_parts_n = cur_loc_n.rsplit(' ', 1)
                        cur_loc_num_n = cur_loc_parts_n[-1] if len(cur_loc_parts_n) > 1 and cur_loc_parts_n[-1].isdigit() else None
                        for m in target_moves:
                            m_name = m[6:].strip()
                            m_parts = m_name.rsplit(' ', 1)
                            m_num = m_parts[-1] if len(m_parts) > 1 and m_parts[-1].isdigit() else None
                            if cur_loc_num_n is None or m_num != cur_loc_num_n:
                                return m
                    # fall through 继续到正常放置逻辑
            
            if self.holding:

                obj_base = ObsParser.norm(self.holding)

                # 从 admissible 中找 put/move 命令（优先 put）

                for ac in admissible_cmds:

                    if ac.startswith('put '):

                        if obj_base in ac or self.holding in ac:

                            return ac

                    if ac.startswith('move '):

                        if (obj_base in ac or self.holding in ac) and self.target_en in ac:

                            return ac

                # 退一步：只要 put/move 命令

                put_cmd = None

                move_cmd = None

                for ac in admissible_cmds:

                    if ac.startswith('put '):

                        if not put_cmd: put_cmd = ac

                    if ac.startswith('move '):

                        if not move_cmd: move_cmd = ac

                if put_cmd:

                    return put_cmd

                if move_cmd:

                    return move_cmd

            # V6+: 没有 put/move 命令 → 检查是否需要 open 目标容器

            open_cmds = [c for c in admissible_cmds if c.startswith('open ')]

            loc_norm = ObsParser.norm(self.current_location or '')

            if open_cmds:

                for oc in open_cmds:

                    container = oc.replace('open ', '').strip()

                    if container not in self.opened_containers:

                        # open 目标同类容器

                        if self.target_en and (self.target_en in container or container in loc_norm):

                            return oc

                # 任何未开的容器都开一下（当前容器可能是目标容器）

                for oc in open_cmds:

                    container = oc.replace('open ', '').strip()

                    if container not in self.opened_containers:

                        if container == loc_norm or loc_norm in container or container in loc_norm:

                            return oc

                # 随便开一个未开的

                for oc in open_cmds:

                    container = oc.replace('open ', '').strip()

                    if container not in self.opened_containers:

                        return oc

            # V6+: 容器遍历——put 失败，尝试下一个同类位置

            self.tried_recep_locs.add(ObsParser.key(self.current_location or ''))

            self.put_attempts += 1

            if self.target_en:

                candidates = _expand_target({self.target_en})

                admissible_moves = [c for c in admissible_cmds if c.startswith('go to ')]

                # 先找目标类型的下一个编号（含别名）

                for con in candidates:

                    for i in range(1, 11):

                        c = f"go to {con} {i}"

                        if c in admissible_moves:

                            key = ObsParser.key(c[6:])

                            if key not in self.tried_recep_locs:

                                return c

                # 再模糊匹配

                for ac in admissible_moves:

                    loc_key = ObsParser.key(ac[6:])

                    for con in candidates:

                        if con in ac and loc_key not in self.tried_recep_locs:

                            return ac

            # 退到探索

            return self._fallback_navigate(admissible_cmds)

        

        # ── goto探索：先检查当前可开容器，再探索 ──

        # ── 探索（探索意图的通用入口）──
        if intent == "探索":
            # 空手时：先尝试去不同编号目标位置（比原地take更有效）
            if not self.holding:
                # 优先：空手拿目标物体（如果可见）
                if self.obj_en:
                    take_cmds = [c for c in admissible_cmds
                                if c.startswith('take ') and len(c.split()) >= 2 and c.split()[1].startswith(self.obj_en)]
                    if take_cmds:
                        return take_cmds[0]
                # 次优：用物体→位置关联知识推测目标位置
                if self.obj_en:
                    # 从 LLM 语义引导获取物体可能的位置（知识库）
                    guide_hints = self._semantic_guide.get_object_hints(
                        self._task_desc if hasattr(self, '_task_desc') else '', self.obj_en)
                    if guide_hints:
                        # 检查 admissible 中是否有所提示的位置
                        for hint_loc in guide_hints:
                            target_moves = [c for c in admissible_cmds 
                                           if c.startswith('go to ') and c[6:].startswith(hint_loc)]
                            if target_moves:
                                cur_loc = ObsParser.norm(self.current_location or '')
                                cur_loc_parts = cur_loc.rsplit(' ', 1)
                                cur_loc_num = cur_loc_parts[-1] if len(cur_loc_parts) > 1 and cur_loc_parts[-1].isdigit() else None
                                diff_moves = []
                                for m in target_moves:
                                    m_name = m[6:].strip()
                                    m_parts = m_name.rsplit(' ', 1)
                                    m_num = m_parts[-1] if len(m_parts) > 1 and m_parts[-1].isdigit() else None
                                    if cur_loc_num is None or m_num != cur_loc_num:
                                        diff_moves.append(m)
                                if diff_moves:
                                    return diff_moves[0]
                # 第三优：去不同编号目标位置（带物体去放）
                if self.target_en and self.task_type in ('pick_and_place_simple',
                        'pick_clean_then_place_in_recep',
                        'pick_cool_then_place_in_recep',
                        'pick_heat_then_place_in_recep',
                        'pick_two_obj_and_place'):
                    loc_base = self.target_en.split(' ')[0]
                    target_moves = [c for c in admissible_cmds 
                                   if c.startswith('go to ') and c[6:].startswith(loc_base)]
                    if target_moves:
                        cur_loc = ObsParser.norm(self.current_location or '')
                        cur_loc_parts = cur_loc.rsplit(' ', 1)
                        cur_loc_num = cur_loc_parts[-1] if len(cur_loc_parts) > 1 and cur_loc_parts[-1].isdigit() else None
                        for m in target_moves:
                            m_name = m[6:].strip()
                            m_parts = m_name.rsplit(' ', 1)
                            m_num = m_parts[-1] if len(m_parts) > 1 and m_parts[-1].isdigit() else None
                            if cur_loc_num is None or m_num != cur_loc_num:
                                return m
            # 拿着物体 → 找不同位置（所有任务类型）
            if self.holding:
                # 检查不同编号的目标位置（如 desk 2）
                if self.target_en:
                    loc_base = self.target_en.split(' ')[0]
                    target_moves = [c for c in admissible_cmds if c.startswith('go to ') and c[6:].startswith(loc_base)]
                    if target_moves:
                        # 不在当前位置的变体（比较编号，不是子串）
                        cur_loc = ObsParser.norm(self.current_location or '')
                        cur_loc_parts = cur_loc.rsplit(' ', 1)
                        cur_loc_num = cur_loc_parts[-1] if len(cur_loc_parts) > 1 and cur_loc_parts[-1].isdigit() else None
                        for m in target_moves:
                            m_name = m[6:].strip()
                            m_parts = m_name.rsplit(' ', 1)
                            m_num = m_parts[-1] if len(m_parts) > 1 and m_parts[-1].isdigit() else None
                            if cur_loc_num is None or m_num != cur_loc_num:
                                return m
                    # 可用的放置命令（如 move pencil 1 to desk 2）
                    place_cmds = [c for c in admissible_cmds
                                 if c.startswith('move ') and c.split()[-1] != cur_loc.split()[-1]]
                    if place_cmds:
                        return place_cmds[0]
            return self._fallback_navigate(admissible_cmds)

        if intent == "goto探索":

            # 当前所在位置如果有关闭的容器，先尝试打开

            open_cmds = [c for c in admissible_cmds if c.startswith('open ')]

            if open_cmds:

                loc_norm_open = ObsParser.norm(self.current_location or '')

                for oc in open_cmds:

                    if loc_norm_open and loc_norm_open in oc:

                        return oc

                return open_cmds[0]

            return self._fallback_navigate(admissible_cmds)

        

        # ── fallback: 用适配器全链路 ──

        return self._adapter_fallback(intent, admissible_cmds, task_info)



    def _handle_look_at_light(self, intent: str, admissible_cmds: List[str]) -> str:
        """look_at_obj_in_light 专用

        真实流程：拿 mug → 到 desklamp 所在位置 → use desklamp → examine mug
        desklamp 是可 use 的固定物体，不是可拿起的 item。

        关键策略：手持物体后，到达每个新位置都先检查有无 use 命令。
        """
        # 完成意图：先检查是否有 examine 或 look 命令
        if intent == "完成":
            # 连续 look/examine 没触发 won → 尝试探索
            last_3_stale = [m.get('action','') for m in self.scene_memory[-3:]
                            if m.get('action','').startswith('examine ') or m.get('action','') == 'look']
            if len(last_3_stale) >= 2:
                admissible_moves = [c for c in admissible_cmds if c.startswith('go to ')]
                if admissible_moves:
                    return admissible_moves[0]
                return self._fallback_navigate(admissible_cmds)
            exam_cmds = [c for c in admissible_cmds if c.startswith('examine ')]
            if exam_cmds:
                return exam_cmds[0]
            if 'look' in admissible_cmds:
                return 'look'
            return 'look'

        # ═══ 空手时：优先拿目标物体 ═══
        if not self.holding:
            # 对于 look_at 任务：灯不需要拿取
            if self.obj_en in ('lamp', 'desklamp', 'floorlamp'):
                # 灯是固定设备 → 导航到灯处 use
                use_cmds = [c for c in admissible_cmds if c.startswith('use ')]
                if use_cmds:
                    return use_cmds[0]
                return self._fallback_navigate(admissible_cmds)
            # 有 obj_en → 尝试 take（注意力机制确保 obj_en 正确）
            if self.obj_en:
                take_cmds = []
                for c in admissible_cmds:
                    if c.startswith('take '):
                        parts = c.split()
                        if len(parts) >= 2 and parts[1].startswith(self.obj_en):
                            take_cmds.append(c)
                if take_cmds:
                    take_cmds.sort(key=lambda c: len(c.split()[1]))
                    return take_cmds[0]
                # 没有直接 take → open 容器
                open_cmds = [c for c in admissible_cmds if c.startswith('open ')]
                if open_cmds:
                    return open_cmds[0]
                # 没有 open → 探索找物体
                return self._fallback_navigate(admissible_cmds)
            # 没有 obj_en（如 'Turn on the desk lamp.'）→ 直接去灯
            return self._fallback_navigate(admissible_cmds)

        # ═══ 手持物体 ═══
        use_cmds = [c for c in admissible_cmds if c.startswith('use ')]
        if use_cmds:
            # 避免重复 use
            if self._recent_actions_contain('use', n=3):
                # 用完了 → examine
                exam_cmds = [c for c in admissible_cmds if c.startswith('examine ')]
                if exam_cmds:
                    return exam_cmds[0]
                if 'look' in admissible_cmds:
                    return 'look'
            return use_cmds[0]

        # 手持物体但没有 use → 导航到 desklamp 所在位置
        return self._fallback_navigate(admissible_cmds)
    def _handle_two_obj(self, intent: str, admissible_cmds: List[str]) -> str:
        """pick_two_obj_and_place 专用处理
        任务流程：拿第一个目标物体 → 放目标位置 → 拿第二个目标物体 → 放目标位置
        增强：V6 容器遍历 + V6 open 联动 + 精确实例追踪
        """
        # 确定需要的总物体数（默认为 2）
        needed_count = 2  # pick_two_obj_and_place 标准
        # 当前已成功拿到的实例数（pick_two 模式下，_taken_objects 存的是实例全名）
        taken_count = len(self._taken_objects)

        if self.verbose:
            print(f"  [_handle_two_obj] intent={intent}, holding={self.holding}, taken={taken_count}[{self._taken_objects}], proc={self.processed}")

        # ═══ 手持物体：去目标位置放下 ═══
        if self.holding is not None:
            target_name = self.target_en
            # 如果 target_en 没设置，从 task_desc 推断
            if not target_name:
                desc = self.task_desc.lower()
                for kw in ['garbagecan','bin','garbage','trash','sinkbasin',
                           'countertop','counter','shelf','drawer','cabinet',
                           'table','desk','fridge','sink','toilet','sofa',
                           'safe','armchair','bed','bathtub']:
                    if kw in desc:
                        target_name = kw
                        break

            search_names = [target_name] + self.POSITION_ALIAS.get(target_name, []) if target_name else []
            loc_norm = ObsParser.norm(self.current_location or '')

            # 检查是否已在目标位置
            in_target = target_name and self._match_position(loc_norm, target_name)
            if not in_target and target_name:
                for alias in self.POSITION_ALIAS.get(target_name, []):
                    if self._match_position(loc_norm, alias):
                        in_target = True
                        break

            if in_target:
                # 在目标位置：优先 put，其次 move
                put_cmd = None
                move_cmd = None
                for ac in admissible_cmds:
                    if ac.startswith('put '):
                        # 确认 put 的是手中物体
                        obj_base = re.sub(r'\s+\d+$', '', self.holding).strip()
                        if obj_base in ac or self.holding in ac:
                            return ac
                        if not put_cmd:
                            put_cmd = ac
                    if ac.startswith('move '):
                        if not move_cmd:
                            move_cmd = ac
                if put_cmd:
                    return put_cmd
                if move_cmd:
                    return move_cmd

            # 不在目标位置：导航过去
            if target_name:
                # V6+: 先检查当前位置是否有 open 目标容器的命令
                open_cmds = [c for c in admissible_cmds if c.startswith('open ')]
                for oc in open_cmds:
                    container = oc.replace('open ', '').strip()
                    if container not in self.opened_containers and target_name in container:
                        return oc

                # V6+: 如果是 put 阶段且目标容器是 closed，先 open
                for oc in open_cmds:
                    container = oc.replace('open ', '').strip()
                    if container not in self.opened_containers:
                        for sn in search_names:
                            if sn in container:
                                return oc

                # 查找 go to 目标位置
                for ac in admissible_cmds:
                    if ac.startswith('go to '):
                        ac_clean = ac[6:].strip()
                        for sn in search_names:
                            if sn and sn in ac_clean and f' {sn}' in f' {ac_clean}':
                                return ac

                # V6+: 容器遍历——找下一个同类位置
                target_moves = [c for c in admissible_cmds if c.startswith('go to ') and
                                any(sn and sn in c and f' {sn}' in f' {c[6:].strip()}' for sn in search_names)]
                # 排除已尝试过放置的位置
                fresh_moves = [c for c in target_moves if ObsParser.key(c[6:]) not in self.tried_recep_locs]
                if fresh_moves:
                    return fresh_moves[0]

            return self._fallback_navigate(admissible_cmds)

        # ═══ 空手 ═══
        # 已完成条件：拿到的实例数 >= 需要的总数
        if taken_count >= needed_count:
            if self.verbose:
                print(f"  [_handle_two_obj→完成] taken={taken_count}/{needed_count}")
            return "look"

        # 找目标物体拿取
        if self.obj_en:
            target_takes = [c for c in admissible_cmds
                            if c.startswith('take ') and any(
                                p.startswith(self.obj_en) for p in c.split())]
            if target_takes:
                # 排除已拿过的同一个实例
                filtered = []
                for c in target_takes:
                    parts = c.split()
                    inst = f"{parts[1]} {parts[2]}" if len(parts) >= 3 else parts[1]
                    if inst not in self._taken_objects:
                        filtered.append(c)
                if filtered:
                    filtered.sort(key=lambda c: len(c.split()[1]))
                    return filtered[0]

        # 没有直接可拿 → 用 object_memory 找已知同类物体位置
        taken_bases = set()
        for t in self._taken_objects:
            base = re.sub(r'\s+\d+$', '', t).strip()
            taken_bases.add(base)
        for obj_name, loc in self.object_memory.items():
            obj_base = re.sub(r'\s+\d+$', '', obj_name.lower()).strip()
            if obj_base in taken_bases or (self.obj_en and self.obj_en in obj_base):
                go_cmd = f'go to {loc}'
                if go_cmd in admissible_cmds and                    loc != ObsParser.key(self.current_location or ''):
                    return go_cmd

        # 没有直接可拿的 → 尝试 open（V6 风格）
        open_cmds = [c for c in admissible_cmds if c.startswith('open ')]
        if open_cmds:
            loc_norm_open = ObsParser.norm(self.current_location or '')
            for oc in open_cmds:
                container = oc.replace('open ', '').strip()
                if container not in self.opened_containers:
                    return oc
            return open_cmds[0]

        # 增强注意力：用子目标状态+知识库排序导航目标
        go_cmds = [c for c in admissible_cmds if c.startswith('go to ')]
        if go_cmds and self.obj_en:
            ranked = self._enhanced_attention.rank_locations(
                go_cmds, self.obj_en, "拿取",
                {ObsParser.key(v) for v in self.visited}
            )
            if ranked:
                return ranked[0][0]

    # V6+: 常识先验权重表（92.5%验证过）
    OBJECT_LOCATION_PRIORS = {
        'plate': {'countertop':3,'cabinet':2,'diningtable':2,'sinkbasin':1,'drawer':1},
        'bowl': {'countertop':3,'cabinet':2,'diningtable':2,'sinkbasin':1},
        'cup': {'countertop':3,'coffeemachine':3,'cabinet':2,'sinkbasin':1},
        'mug': {'countertop':3,'coffeemachine':3,'desk':2,'shelf':2,'cabinet':1,'sinkbasin':1},
        'apple': {'countertop':3,'fridge':2,'diningtable':2,'garbagecan':1},
        'tomato': {'countertop':3,'fridge':2,'diningtable':2},
        'potato': {'countertop':3,'fridge':2,'sinkbasin':1},
        'egg': {'countertop':3,'fridge':3},
        'bread': {'countertop':3,'diningtable':2,'toaster':2},
        'lettuce': {'countertop':3,'fridge':2},
        'knife': {'countertop':3,'drawer':2},
        'fork': {'countertop':2,'drawer':2,'diningtable':2},
        'spoon': {'countertop':2,'drawer':2},
        'spatula': {'countertop':3,'drawer':2},
        'pan': {'stoveburner':3,'countertop':2},
        'pot': {'stoveburner':3,'countertop':2},
        'kettle': {'stoveburner':3,'countertop':2},
        'soapbar': {'countertop':3,'sinkbasin':2,'bathtubbasin':2,'toilet':1},
        'soapbottle': {'countertop':3,'sinkbasin':2,'cabinet':1},
        'soap': {'countertop':3,'sinkbasin':2,'bathtubbasin':2,'toilet':1,'cabinet':1},
        'book': {'desk':3,'shelf':3,'bed':2,'sidetable':2,'coffeetable':2,'dresser':1},
        'pen': {'desk':3,'drawer':2,'shelf':1},
        'pencil': {'desk':3,'drawer':2,'shelf':1},
        'cd': {'desk':2,'shelf':3,'drawer':2,'dresser':2,'safe':1},
        'alarmclock': {'desk':3,'sidetable':3,'shelf':2,'dresser':2},
        'cellphone': {'desk':3,'sidetable':2,'bed':1,'dresser':1},
        'laptop': {'desk':3,'bed':2,'coffeetable':1},
        'remotecontrol': {'coffeetable':3,'sidetable':2,'sofa':2,'bed':1,'dresser':1},
        'creditcard': {'desk':2,'sidetable':2,'drawer':2,'dresser':2,'shelf':1},
        'keychain': {'desk':2,'sidetable':2,'drawer':2,'dresser':2,'shelf':1,'countertop':1},
        'vase': {'shelf':3,'desk':2,'sidetable':2,'coffeetable':2,'dresser':2,'countertop':2},
        'statue': {'shelf':3,'desk':2,'sidetable':2,'dresser':2},
        'pillow': {'bed':3,'sofa':3,'chair':1},
        'teddybear': {'bed':3,'sofa':2},
        'towel': {'towelholder':3,'countertop':2,'bathtubbasin':1},
        'handtowel': {'handtowelholder':3,'countertop':2},
        'toiletpaper': {'toiletpaperhanger':3,'cabinet':2,'countertop':1},
        'cloth': {'countertop':2,'bathtubbasin':2},
        'spraybottle': {'countertop':3,'cabinet':2,'toilet':1},
        'candle': {'countertop':2,'shelf':2,'bathtubbasin':1},
        'tissuebox': {'sidetable':2,'desk':2,'shelf':2,'toilet':1,'countertop':1},
        'newspaper': {'desk':2,'coffeetable':2,'sidetable':2,'sofa':1,'bed':1},
        'winebottle': {'countertop':3,'fridge':2,'cabinet':1},
        'bottle': {'countertop':3,'shelf':2},
        'glassbottle': {'countertop':3,'shelf':2,'fridge':1},
        'box': {'desk':2,'shelf':2,'dresser':2,'sidetable':1},
        'watch': {'desk':2,'sidetable':2,'dresser':2,'shelf':1},
        'baseballbat': {'bed':2,'desk':1,'dresser':1},
        'basketball': {'bed':1,'desk':1},
        'dishsponge': {'sinkbasin':3,'countertop':2},
        'scrubbrush': {'sinkbasin':3,'countertop':2},
        'sponge': {'sinkbasin':3,'countertop':2},
        'papertowelroll': {'countertop':2,'cabinet':2},
        'toiletpaper': {'toiletpaperhanger':3,'cabinet':2},
        'laundryhamper': {'bed':2,'bathroom':2},
        'garbagecan': {'cabinet':1,'desk':1,'countertop':1},
    }

    def _object_location_prior(self, objects: List[str], location_base: str) -> float:
        """V6: 常识先验——物体在什么位置的概率"""
        score = 0.0
        for obj in objects:
            obj_priors = self.OBJECT_LOCATION_PRIORS.get(obj, {})
            for loc_key, prior_score in obj_priors.items():
                if loc_key in location_base or location_base in loc_key:
                    score += prior_score
        return score


    def _fallback_navigate(self, admissible_cmds: List[str]) -> str:

        """

        V6 混合探索引擎：V6 风格精确搜索，取代 V17 卦象驱动探索。

        

        保留 V17 的卦象做高层意图涌现（_decide_intent），

        但底层导航用 V6 的启发式搜索：常识先验 + 未探索优先 + 物体记忆 + 容器遍历。

        """

        # ═══ 注意力机制 Layer S: 空间探索层引导（优先级最高） ═══
        # 使用八卦空间映射 + 物体→位置关联推理，直接选择探索目标
        go_cmds = [c for c in admissible_cmds if c.startswith('go to ')]
        if go_cmds:
            # 记录当前位置到空间探索层
            if self.current_location:
                loc_key = ObsParser.key(self.current_location)
                self._spatial_explorer.memory.record_visit(loc_key, [], "")

            # 构建历史动作列表（用于循环检测）
            history = [m.get('action', '') for m in self.scene_memory]

            # 空间探索层选择下一个探索目标
            spatial_target = self._spatial_explorer.select_explore_target(go_cmds, history)
            if spatial_target:
                if self.verbose:
                    print(f"  [空间八卦] 探索目标: {spatial_target}")
                return spatial_target

        # ═══ 注意力机制：空间探索层回退 → V6 精确搜索 ═══

        # ── 第0步：有直接 take 命令（目标物体在当前位置可见）──

        if self.obj_en:

            direct_take = [c for c in admissible_cmds if c.startswith('take ') and self.obj_en in c]

            if direct_take:

                return direct_take[0]


        # ── 第1步：有未 open 的容器（仅当前位置的容器优先）──

        open_cmds = [c for c in admissible_cmds if c.startswith('open ')]

        if open_cmds and self.current_location:

            loc_norm_open = ObsParser.norm(self.current_location or '')

            for oc in open_cmds:

                container = oc.replace('open ', '').strip()

                if container not in self.opened_containers:

                    if loc_norm_open in container or container in loc_norm_open:

                        return oc


        # ── 第2步：物体记忆回访（V6 精确模式）──

        admissible_moves = [c for c in admissible_cmds if c.startswith('go to ')]

        if not admissible_moves:

            if self.obj_en:

                take_cmds = [c for c in admissible_cmds if c.startswith('take ') and self.obj_en in c]

                if take_cmds:

                    return take_cmds[0]

            if 'look' in admissible_cmds:

                return 'look'

            return admissible_cmds[0] if admissible_cmds else 'look'


        # ── 第3步：增强注意力 + V6 混合排序（子目标驱动 + 容器感知 + 知识库）──

        # 获取子目标引擎的当前子目标
        sg_label = self._subgoal_engine.current_label if hasattr(self, '_subgoal_engine') and self._subgoal_engine else '探索'
        sg_intent = self._subgoal_engine.get_current_intent() if hasattr(self, '_subgoal_engine') and self._subgoal_engine else 'goto探索'

        # 用增强注意力给位置排序（含容器开放优先级）
        attention_ranked = self._enhanced_attention.rank_locations(
            admissible_moves, self.obj_en or '', sg_label,
            self.visited, opened_containers=self.opened_containers
        )

        # 结合注意力分数和 V6 分数做混合排序
        targets = []
        if self.obj_en: targets.append(self.obj_en)
        if self.target_en: targets.append(self.target_en)
        if self.preproc_en: targets.append(self.preproc_en)

        scored = []
        for cmd in admissible_moves:
            loc = cmd[6:].strip().lower()
            loc_base = re.sub(r'\s+\d+$', '', loc)
            score = 0.0

            # 注意力分数（0~1 映射到 0~20 分）
            attention_score = 0.0
            for loc_cmd, att_s in attention_ranked:
                if loc_cmd == cmd:
                    attention_score = att_s * 20.0
                    break
            score += attention_score

            # V6: 目标物体位置匹配
            for t in targets:
                if t == loc_base or t in loc_base or loc_base in t:
                    score += 10.0
                elif t.startswith(loc_base) or loc_base.startswith(t):
                    score += 5.0

            # V6: 物体位置先验（常识）
            if self.obj_en:
                score += self._object_location_prior([self.obj_en], loc_base) * 2.0

            # V6: 未访问过加分
            if loc not in self.visited:
                score += 8.0

            # V6: 最近没去过
            recent_actions = [m.get('action','') for m in self.scene_memory[-6:]] if self.scene_memory else []
            if cmd in recent_actions:
                score -= 6.0

            # V6: 物体记忆确认
            if self.obj_en and self.object_memory:
                for obj_name, cached_loc in self.object_memory.items():
                    obj_base = re.sub(r'\s+\d+$', '', obj_name).strip()
                    if obj_base.startswith(self.obj_en) and ObsParser.key(cached_loc) == ObsParser.key(loc):
                        score += 15.0
                        break

            # V6: 容器编号偏好
            m_num = re.search(r'(\d+)$', loc)
            if m_num:
                num = int(m_num.group(1))
                score -= num * 0.5

            # V6: 与当前位置相同 → 避免原地踏步
            if self.current_location and ObsParser.key(loc) == ObsParser.key(self.current_location):
                score -= 20.0

            # ⭐ 增强：已探索完的位置类型降权
            exhausted = getattr(self, '_exhausted_locs', set())
            if loc in exhausted:
                score -= 25.0

            # ⭐ 增强：有未 open 容器的位置优先
            # 通过检查 admissible 中是否有 open 命令来判断
            if hasattr(self, '_latest_admissible') and self._latest_admissible:
                open_targets = [c.replace('open ', '').strip() for c in self._latest_admissible if c.startswith('open ')]
                unopened_targets = [t for t in open_targets if t not in self.opened_containers]
                for ut in unopened_targets:
                    if ut in loc or loc in ut:
                        score += 10.0  # 大加分：这里可以 open 容器
                        break

            # ⭐ 反馈机制：反馈引擎跳过标记为 exhausted 的位置
            if hasattr(self, '_subgoal_engine') and self._subgoal_engine:
                if self._subgoal_engine.is_location_exhausted(loc):
                    score -= 30.0
                # 预处理设备已确认不可用
                if self._subgoal_engine.is_device_failed(loc):
                    score -= 30.0

            # ⭐ 增强：容器类型且小编号优先（便于快速遍历所有容器）
            loc_base = re.sub(r'\s+\d+$', '', loc)
            if loc_base in ('cabinet','drawer','fridge','microwave','safe','dresser','shelf'):
                if loc not in self.visited and loc not in self.opened_containers:
                    score += 12.0  # 未访问的容器位置大加分
                elif loc not in self.opened_containers:
                    score += 5.0   # 访问过但未 open 的容器

            scored.append((score, cmd))

        scored.sort(key=lambda x: -x[0])


        if self.verbose and scored[:3]:

            print(f"  [V6搜索] obj={self.obj_en}")

            for s, c in scored[:3]:

                key = ObsParser.key(c[6:])

                mark = chr(10003) if key in self.visited else ' '

                print(f"    {s:6.1f} {mark} {c}")


        if scored:

            return scored[0][1]


        # V6 final fallback: 未探索的优先

        for ac in admissible_moves:

            key = ObsParser.key(ac[6:])

            if key not in self.visited:

                return ac


        # 最近没去过的

        recent_actions = [m.get('action','') for m in self.scene_memory[-6:]] if self.scene_memory else []

        for ac in admissible_moves:

            if ac not in recent_actions:

                return ac


        if 'look' in admissible_cmds:

            return 'look'

        return admissible_moves[0] if admissible_moves else 'look'





    def _adapter_fallback(self, intent: str, admissible_cmds: List[str],

                          task_info: dict) -> str:

        """适配器全链路 fallback"""

        action_type = INTENT_TO_ACTION_TYPE.get(intent, "navigate")

        if intent == "放入设备" and self.preproc_en:

            action_type = TOOL_ACTIONS.get(self.preproc_en, 'clean')

        if intent == "执行处理" and self.preproc_en:

            action_type = TOOL_ACTIONS.get(self.preproc_en, 'toggle')



        gua = INTENT_TO_ACTION_GUA.get(intent, "111111")



        cmd = self.adapter.decide(gua, self.scene_state, admissible_cmds, task_info)

        if cmd:

            return cmd



        params = self.adapter.fill_params(action_type, self.scene_state, task_info)

        candidates = self.adapter.generate_commands(action_type, params)

        cmd = self.adapter.match_to_admissible(candidates, admissible_cmds)

        if cmd:

            return cmd



        return self._fallback_navigate(admissible_cmds)



    # ──── 主入口 ────



    def act(self, obs: str) -> str:

        """选择下一步动作"""

        self.step_count += 1

        self._latest_obs = obs

        self._latest_state = ObsParser.parse_observation(obs, self.current_location or "起点")





        # 更新 SceneState

        if self.last_action:

            self.scene_state.update_from_obs(obs, self.last_action)

        self.scene_state.steps_taken = self.step_count



        # 更新场景记忆

        if self.last_action:

            self._update_scene(obs, self.last_action)

        else:

            loc_raw = self._latest_state['location']

            if loc_raw != self.current_location and loc_raw not in ('起点',):

                self.current_location = loc_raw

                self.visited.add(ObsParser.key(loc_raw))

            self._update_scene(obs, '')



        # 获取 admissible commands

        # 注意:这里 admissible_cmds 需要从环境传入;act() 需要外部提供

        # 在 run script 中,act() 调用前后获得

        # 我们通过外部传参的方式获取 -- 在 act() 签名中增加



        # 决策意图

        intent, score = self._decide_intent()



        # 生成动作(admissible_cmds 暂时传入空列表,由 run 脚本实际提供)

        loc_norm = ObsParser.norm(self._latest_state.get('location', ''))

        action = self._intent_to_action(intent, self._latest_admissible)



        # ═══ 执行反馈记录 ═══
        if intent != self._last_intent:
            self._last_intent_retry = 0
            self._last_intent_result = ''
        self._last_intent = intent

        # V17⛳: 对特定意图设置执行反馈（基于当前 obs 和状态）
        if intent == "拿取":
            # 没有 take 命令可用=
            has_take = any(c.startswith('take ') for c in self._latest_admissible)
            if not has_take:
                self._last_intent_result = 'FAIL:拿取'
                self._last_intent_retry += 1
            else:
                self._last_intent_result = 'OK'
                self._last_intent_retry = 0

        if self.verbose:
            print(f"  S{self.step_count:2d} [{intent:8s}] hold={bool(self.holding)} proc={self.processed} "
                  f"loc={loc_norm:8s} → {action}")
            if self._last_intent_result.startswith('FAIL'):
                print(f"  [反馈] {self._last_intent_result} retry={self._last_intent_retry}")

        # ═══ 反馈机制：子目标引擎接收执行反馈 ═══
        _fb_action = action
        _fb_obs = self._latest_obs if hasattr(self, '_latest_obs') else ''
        _fb_admissible = self._latest_admissible if hasattr(self, '_latest_admissible') else []
        if hasattr(self, '_subgoal_engine') and self._subgoal_engine:
            self._subgoal_engine.feed_feedback(_fb_action, _fb_obs, _fb_admissible,
                                                 current_location=ObsParser.key(self.current_location)
                                                 if self.current_location else '')

        self.last_action = action
        return action



    def act_with_admissible(self, obs: str, admissible_cmds: List[str]) -> str:

        """带 admissible commands 的动作选择"""

        self._latest_admissible = admissible_cmds

        return self.act(obs)



    def update(self, action: str, obs: str):

        """从 obs 更新状态

        

        注意：holding 的更新完全基于 obs 文本，不依赖 agent 动作记忆。

        防止重复拿放、物体跟踪紊乱。

        """

        self.last_action = action

        self._latest_obs = obs

        self._latest_state = ObsParser.parse_observation(obs, self.current_location or "起点")



        loc = ObsParser.extract_location(obs, self.current_location or "起点")

        if action.startswith('go to '):

            target_raw = action[6:].strip()

            self.visited.add(ObsParser.key(target_raw))
            # ═══ 注意力机制：记录空间探索层 ═══
            import re as _re
            seen_objs = _re.findall(r'([a-zA-Z]+)\s+(\d+)', obs)
            seen_names = [f"{n} {i}" for n, i in seen_objs]
            self._spatial_explorer.memory.record_visit(target_raw, seen_names, obs)

        if loc != self.current_location and loc not in ('起点',):

            self.current_location = loc

            self.visited.add(ObsParser.key(loc))



        # 场景记忆更新（包含了手持检测）

        self._update_scene(obs, action)



        # V6+: 跟踪 open

        obs_lower = obs.lower()

        if action.startswith('open '):

            container = action[5:].strip()

            if 'nothing happens' not in obs_lower and "can't" not in obs_lower:

                self.opened_containers.add(container)

                self._pending_open = True

        elif self._pending_open:

            self._pending_open = False  # 执行open后的下一步复位



        # V6+: 物体位置记忆（从 admissible 命令中提取物体位置）

        if self._latest_admissible and self.current_location:

            for cmd in self._latest_admissible:

                if cmd.startswith('take '):

                    m = re.match(r'take (.+?) from (.+)', cmd)

                    if m:

                        obj_name = m.group(1).strip()

                        loc_key = ObsParser.key(self.current_location)

                        if obj_name not in self.object_memory:

                            self.object_memory[obj_name] = loc_key

        # 从 obs 中也提取可见物体的位置

        if self.current_location:

            ol_lower = obs.lower()

            for m in re.finditer(r'on the (.+?), you see (.+?)(?:\.|$)', ol_lower):

                loc_part = m.group(1).strip()

                obj_part = m.group(2).strip()

                # 只记录容器位置

                RECEPTACLE_KEYWORDS = ['cabinet','drawer','shelf','desk','countertop',

                                       'counter','table','sidetable','coffeetable',

                                       'diningtable','dresser','fridge','microwave',

                                       'sinkbasin','sink','toilet','bathtub','safe',

                                       'garbagecan','sofa','armchair','bed']

                for rk in RECEPTACLE_KEYWORDS:

                    if rk in loc_part:

                        obj_items = re.findall(r'([a-z]+)\s+(\d+)', obj_part)

                        for obj_name, obj_id in obj_items:

                            full = f"{obj_name} {obj_id}"

                            if full not in self.object_memory:

                                self.object_memory[full] = ObsParser.key(loc_part)

                        break



        # 结构化状态：完全基于 obs 文本，不依赖 action 记忆

        ol = obs.lower()

        state = ObsParser.parse_observation(obs, self.current_location or "起点")

        

        # 动作是否成功？

        action_failed = any(kw in ol for kw in ["nothing happens", "can't", "cannot"])


        # 成功拿起

        if 'you pick up' in ol or 'you take' in ol:

            if state['inventory'] and not action_failed:

                self.holding = state['inventory'][0]

                # 记录已拿过这个物体（避免重复拿放同类物体）

                # 对于 pick_two_obj_and_place 需要拿多次同类物体，记录带编号的完整名称

                obj_key = state['inventory'][0]

                if self.task_type == 'pick_two_obj_and_place':

                    # 记录完整名称（含编号），只禁止重复拿同一个实例

                    self._taken_objects.add(obj_key)

                else:

                    # 记录类名，禁止再拿同类任何实例

                    import re as _re

                    obj_base = _re.sub(r'\s+\d+$', '', obj_key).strip()

                    self._taken_objects.add(obj_base)

        # 成功放下 → 清空手持

        elif 'you put' in ol or 'you place' in ol or 'you move' in ol:

            if not action_failed:

                self.holding = None

                # V17⛳: 记录已放置的目标位置，防止同一位置重复拿放

                if self.current_location:

                    self.tried_recep_locs.add(ObsParser.key(self.current_location))

                # V17⛳: 检查是不是真的移动了物体（不是在原地拿放）

                # 如果 obs 说 nothing happens，holding 保持原样

                if self.task_type == 'pick_two_obj_and_place':

                    self.processed = False

                else:

                    self.processed = True

            else:

                # V17⛳: 动作失败（如放回原位），holding 不变，不设 processed

                pass

            # V6+: 记录当前尝试过的放置位置

            if self.current_location:

                self.tried_recep_locs.add(ObsParser.key(self.current_location))

        # 库存检查

        elif 'you are carrying' in ol:

            if state['inventory']:

                self.holding = state['inventory'][0]

            else:

                self.holding = None

        # 失败动作不应改变 holding

        

        # 处理状态更新

        if action.startswith('clean ') and 'clean' in ol:

            self.processed = True

        elif action.startswith('heat ') and 'heat' in ol:

            self.processed = True

        elif action.startswith('cool ') and 'cool' in ol:

            self.processed = True

        elif action.startswith('use ') and ('turn on' in ol or 'lamp' in ol):

            self.processed = True

        

        # ── 探索记忆更新（知己学习） ──

        action_success = True

        for kw in ["nothing happens", "can't", "cannot", "not open"]:

            if kw in ol:

                action_success = False

                break

        loc_key = ObsParser.key(self.current_location or '')

        if loc_key and loc_key not in ('起点', ''):

            # 检查当前位置是否有目标物体被看到/拿到

            obj_found = None

            if action and ('pick up' in ol or 'take' in ol):

                if state.get('inventory'):

                    obj_found = state['inventory'][0]

            self._exploration_memory.record_visit(

                loc_key, obj_found, self.obj_en, action_success)

        

        # 如果是 pick_two_obj_and_place，放完一个后重置 processed 但不重置 holding

        # holding 已经被上面的逻辑更新为 None 了



    def is_done(self, obs: str, info: dict = None) -> bool:

        """判断任务是否完成

        

        优先用 info 中的 won 信号，其次用 obs 文本特征。

        """

        if info and info.get('won', False):

            return True

        ol = obs.lower()

        if 'you win' in ol or 'task done' in ol or 'success' in ol:

            return True

        return False





def clip(v: float, lo: float = 0.05, hi: float = 0.95) -> float:

    return max(lo, min(hi, v))
