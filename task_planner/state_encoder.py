#!/usr/bin/env python3
"""
状态编码器 — StateEncoder

将场景状态编码为中文状态词，再通过hanzi_engine做卦爻解码。

核心设计（B方案）：
  每个状态由两个双字词组成：
    - 持有词: "空手" / "持盘" / "洗毕" / "放毕"
    - 位置词: "柜前" / "水槽" / "柜台" / "目标"
  
  两个词分别送入hanzi_engine.word()得到卦象向量，
  再作为句级YLYWLayer的输入做乘承比应推理，得到最终六爻和64卦。

与V14的关键区别：
  V14: 6个手写数值变量 → 自定义模糊规则 → 意图
  本模块: 中文状态词 → hanzi_engine卦爻推理 → 卦名+六爻 → 意图

不依赖admissible_commands，只从obs文本推断状态。
"""

import os, sys, re
from typing import Dict, List, Tuple, Optional, Set

# 确保能导入hanzi_engine和ylyw_core
_self_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.dirname(_self_dir)
for d in (os.path.join(_proj_root, 'language'),
          os.path.join(_proj_root, 'api_docs'),
          os.path.join(_proj_root, 'experiment_phase1')):
    if d not in sys.path:
        sys.path.insert(0, d)

import json
from collections import defaultdict

try:
    from hanzi_engine import HanziEngine, char_to_bagua, YLYWLayer, BAGUA
    _HANZI_OK = True
except ImportError as e:
    _HANZI_OK = False
    print(f"[WARN] hanzi_engine not available: {e}")


# ══════════════════════════════════════════════════════════════
# 状态编码常量
# ══════════════════════════════════════════════════════════════

# 持有状态 → 中文双字词（动作+对象或纯状态）
HOLD_WORDS = {
    'empty':        '空手',    # 空手
    'holding_raw':  '持物',    # 拿着未处理的物体
    'holding_processed': '持净',  # 拿着已处理（洗/热/冷）的物体
    'holding_tool': '持具',    # 拿着工具
    'done':         '毕',     # 已完成（单字兼容）
    'unknown':      '空闲',    # 未知初始状态
}

# 位置类型 → 中文双字词
LOCATION_WORDS = {
    'exploring':    '寻',     # 在探索中（单字）
    'at_tool':      '具处',   # 在工具位置（水槽/微波炉/冰箱）
    'at_target':    '目位',   # 在目标容器位置
    'at_object':    '物旁',   # 在目标物体旁
    'center':       '中央',   # 房间中央（初始位置）
    'unknown':      '未知',   # 位置不明
}

# 处理状态 → 中文双字词
PROCESS_WORDS = {
    'none':         '未',     # 未处理
    'washed':       '已洗',   # 已清洗
    'heated':       '已热',   # 已加热
    'cooled':       '已冷',   # 已冷却
    'n/a':          '毋',     # 不需要处理（单字）
}

# ====== 位置类型与工具类型映射（从 V14 translate 中提炼）======

TOOL_CN_MAP = {
    'sinkbasin': '水槽',
    'microwave': '微波炉',
    'fridge':    '冰箱',
    'desklamp':  '台灯',
    'floorlamp': '落地灯',
    'lamp':      '灯',
}

TARGET_CN_MAP = {
    'countertop':  '柜台',
    'cabinet':     '柜子',
    'drawer':      '抽屉',
    'shelf':       '架子',
    'desk':        '桌子',
    'diningtable': '餐桌',
    'sidetable':   '边桌',
    'coffeetable': '茶几',
    'bed':         '床',
    'sofa':        '沙发',
    'safe':        '保险箱',
    'garbagecan':  '垃圾桶',
    'toilet':      '马桶',
    'bathtubbasin':'浴缸',
    'sinkbasin':   '水槽',
    'microwave':   '微波炉',
    'fridge':      '冰箱',
    'stoveburner': '灶台',
    'ottoman':     '脚凳',
    'tvstand':     '电视柜',
    'dresser':     '梳妆台',
    'laundryhamper':'洗衣篮',
    'cart':        '推车',
    'coffeemachine':'咖啡机',
    'towelholder': '毛巾架',
    'handtowelholder': '手巾架',
    'toiletpaperhanger': '纸架',
}

# 英文位置名 → 中文（用于从obs解析）
EN_LOC_CN = {**TARGET_CN_MAP, **{
    # 补充更多可能的映射
    'cabinet': '柜子',
    'counter': '柜台',
    'sink': '水槽',
    'fridge': '冰箱',
    'microwave': '微波炉',
    'stove': '灶台',
    'shelf': '架子',
    'drawer': '抽屉',
    'desk': '桌子',
    'table': '桌子',
    'bed': '床',
    'sofa': '沙发',
    'safe': '保险箱',
    'toilet': '马桶',
    'garbage': '垃圾桶',
    'trash': '垃圾桶',
    'bin': '垃圾桶',
    'hamper': '洗衣篮',
    'ottoman': '脚凳',
    'cart': '推车',
}}

# 英文物体名 → 中文
EN_OBJ_CN = {
    'plate': '盘子', 'bowl': '碗', 'mug': '杯子', 'cup': '杯子',
    'knife': '刀', 'fork': '叉子', 'spoon': '勺子',
    'pan': '锅', 'pot': '锅', 'spatula': '锅铲',
    'apple': '苹果', 'potato': '土豆', 'tomato': '番茄',
    'lettuce': '生菜', 'bread': '面包', 'egg': '鸡蛋',
    'soap': '肥皂', 'soapbar': '肥皂', 'towel': '毛巾',
    'cloth': '抹布', 'sponge': '海绵', 'dishsponge': '洗碗海绵',
    'handtowel': '手巾', 'papertowelroll': '纸卷',
    'glassbottle': '玻璃瓶', 'winebottle': '酒瓶',
    'bottle': '瓶子', 'kettle': '水壶',
    'book': '书', 'pen': '笔', 'pencil': '铅笔',
    'keychain': '钥匙链', 'watch': '手表', 'cellphone': '手机',
    'remotecontrol': '遥控器', 'laptop': '笔记本',
    'pillow': '枕头', 'teddybear': '泰迪熊',
    'vase': '花瓶', 'statue': '雕像', 'cd': '光盘',
    'alarmclock': '闹钟', 'newspaper': '报纸',
    'tissuebox': '纸巾盒', 'box': '盒子',
    'baseballbat': '棒球棒', 'basketball': '篮球',
    'creditcard': '信用卡', 'candle': '蜡烛',
    'peppershaker': '胡椒瓶', 'saltshaker': '盐瓶',
    'scrubbrush': '刷子', 'plunger': '皮搋子',
    'spraybottle': '喷瓶', 'soapbottle': '洗手液瓶',
    'toiletpaper': '卫生纸', 'butterknife': '黄油刀',
    'ladle': '汤勺', 'cloth': '布', 'mug': '杯子',
    'tomato': '番茄', 'potato': '土豆', 'lettuce': '生菜',
}


class StateEncoder:
    """
    状态编码器。

    职责：
      1. 从obs文本解析当前状态（位置、持有、处理、目标）
      2. 将状态编码为中文词（双字/四字）
      3. 通过hanzi_engine做字→词卦爻解码
      4. 输出六爻向量和64卦分布供规划器使用

    不依赖admissible_commands：
      - 位置信息从 obs 中 'You arrive at ...' 或初始场景描述中提取
      - 持有信息从 obs 中 'You pick up ...' / 'You put ...' 推断
      - 处理信息从 obs 中 'You clean ...' / 'You heat ...' / 'You cool ...' 推断
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if not _HANZI_OK:
            raise ImportError("hanzi_engine is required for StateEncoder")
        
        self.engine = HanziEngine(verbose=False)

        # 当前状态
        self.current_loc_en = ''        # 当前位置（英文原始名，如 countertop 1）
        self.current_loc_cn = '未知'    # 当前位置（中文）
        self.current_loc_base = ''      # 当前位置类型（去编号）
        self.holding = ''               # 当前手持物体（英文base名）
        self.holding_cn = ''            # 当前手持物体（中文）
        self.processed = False          # 是否已处理（洗/热/冷）
        self.process_type = 'none'      # 处理类型
        self.task_type = ''             # 任务类型
        self.target_obj = ''            # 目标物体base名
        self.target_obj_cn = ''         # 目标物体中文名
        self.target_loc = ''            # 目标容器base名
        self.target_loc_cn = ''         # 目标容器中文名
        self.tool_loc = ''              # 工具位置base名
        self.tool_loc_cn = ''           # 工具位置中文名
        self.tool_type = ''             # 处理类型工具标识
        self.step = 0
        self.visited_locs: Set[str] = set()
        self.scene_objects: Dict[str, str] = {}  # 物体base → 位置base（从obs积累）
        self.scene_locations: List[str] = []      # 已知可去位置列表（从初始obs提取）
        self.explored_locs: Set[str] = set()      # 已去过位置
        
        # YLYWLayer 用于句级推理（状态词间的乘承比应）
        self.yao_layer = YLYWLayer("state_encoder")

    def reset(self, task_desc: str = '', task_type: str = '',
              initial_obs: str = ''):
        """重置编码器状态"""
        self.current_loc_en = ''
        self.current_loc_cn = '中央'
        self.current_loc_base = ''
        self.holding = ''
        self.holding_cn = ''
        self.processed = False
        self.process_type = 'none'
        self.step = 0
        self.visited_locs = set()
        self.scene_objects = {}
        self.scene_locations = []
        self.explored_locs = set()

        # 从task_desc解析任务参数
        self._parse_task(task_desc, task_type)

        # 从初始obs提取所有可去位置
        if initial_obs:
            self._extract_locations(initial_obs)

    def _parse_task(self, task_desc: str, task_type: str):
        """从任务描述和类型解析目标物体/容器/工具"""
        self.task_type = task_type
        desc_lower = task_desc.lower()

        # 确定工具类型和位置
        if 'clean' in task_type or 'clean' in desc_lower:
            self.tool_type = 'wash'
            self.tool_loc = 'sinkbasin'
            self.tool_loc_cn = '水槽'
        elif 'heat' in task_type or ('heat' in desc_lower and 'cool' not in desc_lower):
            self.tool_type = 'heat'
            self.tool_loc = 'microwave'
            self.tool_loc_cn = '微波炉'
        elif 'cool' in task_type or 'cool' in desc_lower:
            self.tool_type = 'cool'
            self.tool_loc = 'fridge'
            self.tool_loc_cn = '冰箱'
        elif 'light' in task_type or 'lamp' in desc_lower:
            self.tool_type = 'light'
            self.tool_loc = 'desklamp'
            self.tool_loc_cn = '灯'

        # 从task_desc提取目标物体（简化正则匹配）
        # "Put a clean plate on the counter." → 找物体名
        for obj_en, obj_cn in EN_OBJ_CN.items():
            if obj_en in desc_lower:
                self.target_obj = obj_en
                self.target_obj_cn = obj_cn
                break

        # 提取目标容器
        for loc_en, loc_cn in EN_LOC_CN.items():
            if loc_en in desc_lower:
                self.target_loc = loc_en
                self.target_loc_cn = loc_cn
                break

        if self.verbose:
            print(f"  [Encoder] 任务: obj={self.target_obj_cn}, loc={self.target_loc_cn}, tool={self.tool_loc_cn}")

    def _extract_locations(self, obs: str):
        """从初始obs提取所有可去位置（去重）"""
        obs_lower = obs.lower()
        seen = set()
        for line in obs_lower.split('\n'):
            # 用正则提取所有 "a X Y" 格式的家具名
            items = re.findall(r'a (\w+ \d+)', line)
            for item in items:
                item_base = re.sub(r' \d+$', '', item)
                if item_base in EN_LOC_CN:
                    if item not in seen:
                        seen.add(item)
                        self.scene_locations.append(item)
                        if self.verbose:
                            print(f"  [Encoder] 发现位置: {item}")

    def update_from_obs(self, obs: str, action: str, action_success: bool = True):
        """从观测文本更新状态"""
        self.step += 1
        obs_lower = obs.lower()

        # 1. 位置更新
        loc_match = re.search(r'arrive at (.+?)[\.!]', obs_lower)
        if loc_match:
            loc_full = loc_match.group(1).strip()
            loc_base = re.sub(r'\s+\d+$', '', loc_full)
            self.current_loc_en = loc_full
            self.current_loc_base = loc_base
            self.current_loc_cn = EN_LOC_CN.get(loc_base, loc_base)
            self.visited_locs.add(self.current_loc_cn)
            self.explored_locs.add(loc_full)

        # 2. 持有状态更新
        if 'pick up' in obs_lower or 'you pick' in obs_lower:
            obj_match = re.search(r'pick up (?:the )?(.+?)(?: from|$)', obs_lower)
            if obj_match:
                obj = obj_match.group(1).strip()
                obj_base = re.sub(r'\s+\d+$', '', obj)
                self.holding = obj_base
                self.holding_cn = EN_OBJ_CN.get(obj_base, obj_base)
        elif 'you put' in obs_lower or 'you move' in obs_lower:
            self.holding = ''
            self.holding_cn = ''
        elif not action_success and action.startswith('take '):
            self.holding = ''
            self.holding_cn = ''

        # 3. 处理状态更新（只检测动作反馈，不混入任务描述中的关键词）
        # 检测模式："You clean/heat/cool X" 或 "clean/heat/cool the X"（动作执行后的反馈）
        action_processed = False
        if 'you clean' in obs_lower:
            self.processed = True
            self.process_type = 'wash'
            action_processed = True
        if 'you heat' in obs_lower:
            self.processed = True
            self.process_type = 'heat'
            action_processed = True
        if 'you cool' in obs_lower:
            self.processed = True
            self.process_type = 'cool'
            action_processed = True
        # 兜底：如果上一步是clean/heat/cool动作且obs中没有Nothing happens
        if not action_processed and action:
            if action.startswith('clean ') and 'nothing happens' not in obs_lower:
                self.processed = True
                self.process_type = 'wash'
            elif action.startswith('heat ') and 'nothing happens' not in obs_lower:
                self.processed = True
                self.process_type = 'heat'
            elif action.startswith('cool ') and 'nothing happens' not in obs_lower:
                self.processed = True
                self.process_type = 'cool'

        # 4. 从obs中的"you see"部分积累场景物体位置
        see_match = re.search(r'you see (.+?)(?:\.|$)', obs_lower)
        if see_match and self.current_loc_base:
            see_text = see_match.group(1)
            for obj_en, obj_cn in EN_OBJ_CN.items():
                if obj_en in see_text:
                    self.scene_objects[obj_en] = self.current_loc_base

    # ══════════════════════════════════════════════════════════════
    # 核心编码方法
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _loc_match(loc_base: str, target: str) -> bool:
        """精确判断两个位置名是否匹配（防止'counter' in 'countertop'误判）"""
        if not loc_base or not target:
            return False
        loc = loc_base.lower().strip()
        tgt = target.lower().strip()
        # 完全一致
        if loc == tgt:
            return True
        # 一个是另一个的前缀且涉及复合词（如 countertop 含 counter）
        if loc.startswith(tgt) or tgt.startswith(loc):
            # 只有长度差≤2才认为匹配（如 'sink' 匹配 'sinkbasin'）
            return abs(len(loc) - len(tgt)) <= 3
        return False

    def _build_yao_from_state(self) -> List[float]:
        """
        基于任务状态构建有区分度的6维爻向量。

        六爻的易理定位（由任务规划语义决定）：
          初爻: 是否已找到目标物体
          二爻: 是否在工具位置
          三爻: 是否已处理
          四爻: 是否在目标容器位置
          五爻: 是否持有物体
          上爻: 步数进度

        爻值范围0.1-0.9。
        """
        loc_base = (self.current_loc_base or '').strip()

        # 初爻：是否已找到目标物体
        if self.holding and self.target_obj and self.holding == self.target_obj:
            y0 = 0.85      # 已拿着目标物体
        elif self.target_obj and self.target_obj in self.scene_objects:
            y0 = 0.55      # 看到过目标物体但没拿
        else:
            y0 = 0.10      # 还没看到目标

        # 二爻：是否在工具位置
        y1 = 0.85 if self._loc_match(loc_base, self.tool_loc) else 0.15

        # 三爻：是否已处理
        if self.processed:
            y2 = 0.85
        elif self.tool_type and self.tool_type != 'none':
            y2 = 0.10  # 需要处理但还没做
        else:
            y2 = 0.50  # 不需要处理

        # 四爻：是否在目标容器位置
        y3 = 0.85 if self._loc_match(loc_base, self.target_loc) else 0.15

        # 五爻：是否持有物体
        if self.holding:
            y4 = 0.80 if self.holding == self.target_obj else 0.45
        else:
            y4 = 0.10

        # 上爻：步数进度（线性增长，50步上限）
        y5 = min(0.10 + self.step * 0.016, 0.85)

        return [y0, y1, y2, y3, y4, y5]


    def _get_state_chars(self) -> Tuple[str, str]:
        """
        将当前状态编码为两个单字（汉字推理用）。
        
        返回 (动作字, 位置字)：
          动作字：空(探索中) / 取(正在拿) / 洗(正在处理) / 放(完成)
          位置字：寻(探索) / 水(水槽/工具位置) / 柜(目标容器)
        
        每个字都是hanzi_engine中有区分度的单字，
        避免使用'手''前''已''目'等平坦字。
        """
        # 动作字
        if self.processed:
            act_char = '洗'  # 已处理完成
        elif self.holding and self.holding == self.target_obj:
            act_char = '取'  # 已经拿到目标物体
        elif self.holding:
            act_char = '持'  # 拿着某个东西（非目标）
        else:
            act_char = '空'  # 空手

        # 位置字
        loc_base = self.current_loc_base or ''
        if self._loc_match(loc_base, self.tool_loc):
            loc_char = '洗' if self.tool_type == 'wash' else \
                       '水' if self.tool_type == 'heat' else \
                       '冰' if self.tool_type == 'cool' else '寻'
        elif self._loc_match(loc_base, self.target_loc):
            loc_char = '柜'  # 在目标容器位置
        elif self.holding and not self.processed:
            loc_char = '台'  # 在某个位置但没有工具
        else:
            loc_char = '寻'  # 探索中

        return act_char, loc_char

    def encode_state(self) -> Dict:
        """
        将当前状态编码为卦爻表示。

        卦名来自汉字推理（两个单字经YLYWLayer乘承比应）。
        六爻来自状态构建（保证区分度）。
        两者共同组成卦爻一体的完整表示。
        """
        # 1. 汉字推理 → 卦名
        act_char, loc_char = self._get_state_chars()
        
        act_bagua = [float(v) for v in char_to_bagua(act_char)['vector']]
        loc_bagua = [float(v) for v in char_to_bagua(loc_char)['vector']]
        
        roles = ['动作', '物体']
        sentence_result = self.yao_layer.perceive_and_encode(
            [act_bagua, loc_bagua], roles
        )
        hex_name = sentence_result['hexagram']
        hex_score = sentence_result.get('hexagram_score', 0.0)
        hex64 = sentence_result.get('hex64', [0.0]*64)

        # 3. 构建有区分度的六爻向量
        yao = self._build_yao_from_state()

        # 4. 选卦名
        # 以汉字推理的卦名为主，六爻状态只用于边界修正
        all_low = all(v < 0.25 for v in yao)
        
        # 汉字推理结果（优先使用）
        if hex_score > 0.3:
            final_hex = hex_name
            final_score = hex_score
        elif all_low:
            final_hex = '乾为天'
            final_score = 0.9
        else:
            final_hex = '火风鼎'
            final_score = 0.8

        # 六爻状态修正（仅在汉字推理明显偏出时覆盖）
        # 例如：字符'洗+洗'在汉字推理中为雷火丰，
        # 但六爻状态显示已处理+持物时，应该为'需'卦
        if hex_name in ('雷火丰', '泽风大过') and self.processed and self.holding \
           and not self._loc_match(self.current_loc_base, self.target_loc):
            # 已处理但还没到目标位置 → 需卦（需要前往）
            final_hex = '需'
            final_score = 0.90
        elif hex_name in ('雷火丰', '泽风大过') and self.processed and self.holding \
             and self._loc_match(self.current_loc_base, self.target_loc):
            # 已处理+在目标位置+持有 → 泽天夬（放置）
            final_hex = '泽天夬'
            final_score = 0.95

        if self.verbose:
            yao_str = ' '.join(f'{v:.3f}' for v in yao)
            print(f"  [Encoder] {act_char}+{loc_char} → 卦:{hex_name}({hex_score:.2f}) → 选{final_hex}")
            print(f"            六爻:[{yao_str}]")

        return {
            'act_char': act_char,
            'loc_char': loc_char,
            'yao_vector': yao,
            'hexagram': final_hex,
            'hexagram_score': final_score,
            'hex64': hex64,
        }

    def get_state_summary(self) -> Dict:
        """获取状态摘要（用于调试和经验记录）"""
        return {
            'loc_cn': self.current_loc_cn,
            'loc_en': self.current_loc_en,
            'holding': self.holding_cn or '空',
            'processed': self.processed,
            'step': self.step,
            'target_obj': self.target_obj_cn,
            'target_loc': self.target_loc_cn,
            'tool_loc': self.tool_loc_cn,
            'scene_known': len(self.scene_objects),
            'locations_known': len(self.scene_locations),
            'explored': len(self.explored_locs),
        }

    def get_hold_bagua(self) -> List[float]:
        """获取当前持有词的八维卦象（供外部直接使用）"""
        return self.encode_state()['hold_bagua']

    def get_loc_bagua(self) -> List[float]:
        """获取当前位置词的八维卦象"""
        return self.encode_state()['loc_bagua']
