#!/usr/bin/env python3
"""
YLYW 语义解析器 for ALFWorld

将文言文L1-L3语义解析架构映射到英文task_desc解析：
  L1: 单词 → 八卦隶属度（动词/名词/工具/位置各有卦象归属）
  L2: 单词间"乘承比应"关系识别
  L3: 功能词驱动语义分块 + 任务类型推断

设计原则：与文言文版本同构——部首(词根)→模糊隶属度→乘承比应→虚词驱动
"""

import sys
import os
import math
import re
import json
from typing import Dict, List, Tuple, Optional

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

from ylyw_core import PriorManual

BAGUA = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]


# ============================================================
# L1: ALFWorld 词汇 → 八卦语义隶属度库
# ============================================================

# 动词(动作)类 → 震卦(动)
ACTION_VERBS = {
    'take', 'pick', 'grab', 'get', 'hold', 'carry',
    'put', 'place', 'drop', 'move', 'set',
    'open', 'close', 'turn', 'use', 'toggle',
    'clean', 'wash', 'rinse', 'scrub', 'wipe', 'washed', 'cleaned', 'rinsed',
    'heat', 'warm', 'cook', 'microwave', 'heated',
    'cool', 'chill', 'freeze', 'refrigerate', 'cooled',
    'slice', 'cut', 'chop', 'dice', 'sliced',
    'look', 'examine', 'find', 'search',
    'go', 'navigate', 'walk',
}

# 物体(名物)类 → 坤卦(承载)
OBJECT_NOUNS = {
    'apple', 'potato', 'lettuce', 'tomato', 'egg', 'bread', 'butter',
    'bowl', 'plate', 'cup', 'mug', 'glass', 'pan', 'pot', 'bottle',
    'knife', 'fork', 'spoon', 'spatula', 'ladle', 'whisk',
    'clock', 'alarmclock', 'watch', 'laptop', 'cellphone', 'remotecontrol',
    'book', 'newspaper', 'magazine', 'pencil', 'pencils', 'pen', 'cd',
    'vase', 'statue', 'tissuebox', 'candle', 'box',
    'keychain', 'creditcard', 'basketball', 'baseball', 'baseballbat', 'bat',
    'towel', 'cloth', 'sponge', 'soap', 'soapbottle', 'spraybottle', 'scrubbrush',
    'salt', 'pepper', 'dishsponge', 'plunger', 'dish',
    'pillow', 'blinds', 'mirror', 'winebottle',
}

# 容器/位置(场所)类 → 艮卦(静止、止于)
LOCATION_NOUNS = {
    'desk', 'table', 'bed', 'drawer', 'cabinet', 'dresser',
    'shelf', 'countertop', 'counter', 'sidetable', 'tvstand',
    'fridge', 'refrigerator', 'microwave', 'toaster', 'coffeemachine',
    'sinkbasin', 'stoveburner', 'stove', 'oven',
    'garbagecan', 'laundryhamper', 'safe',
    'garbage', 'can', 'movable',
    'sofa', 'couch', 'armchair', 'coffeetable', 'diningtable',
    'bathtub', 'toilet', 'ottoman', 'dresser',
    'top',  # countertop拆分后的部分
}

# 光源/工具类 → 离卦(光明、依附)
TOOL_NOUNS = {
    'desklamp', 'floorlamp', 'lamp', 'light',
    'lightswitch', 'television',
}

# 功能词(虚词) → 不参与语义合并
FUNCTION_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but',
    'with', 'from', 'in', 'on', 'to', 'of', 'for',
    'is', 'are', 'was', 'were', 'be',
    'some', 'any', 'all', 'that', 'this', 'it',
    'then', 'now', 'there', 'here',
    's',  # 复数s
}

# 单词 → 八卦语义隶属度向量(8维)
# 每个词类有固定的基础向量
WORD_CLASS_VECTORS = {
    'action':   [0.2, 0.3, 0.4, 0.85, 0.5, 0.3, 0.2, 0.1],  # 震卦主导
    'object':   [0.3, 0.4, 0.3, 0.2, 0.3, 0.4, 0.4, 0.85],  # 坤卦主导
    'location': [0.2, 0.3, 0.2, 0.1, 0.2, 0.3, 0.85, 0.3],  # 艮卦主导
    'tool':     [0.3, 0.4, 0.85, 0.2, 0.3, 0.2, 0.1, 0.2],  # 离卦主导
    'function': [0.5, 0.5, 0.4, 0.3, 0.8, 0.4, 0.3, 0.3],  # 巽卦主导(入)
}


class YLYWSemanticParser:
    """
    YLYW 三层语义解析器 for ALFWorld task_desc

    架构映射：
      文言文 L1(部首→八卦隶属度) → ALFWorld L1(词类→八卦隶属度)
      文言文 L2(会意字乘承比应)   → ALFWorld L2(单词间语义关系)
      文言文 L3(虚词驱动+三通道)  → ALFWorld L3(功能词驱动分块)
    """

    def __init__(self):
        self.manual = PriorManual(verbose=False)

    # ========================================================
    # L1: 单词 → 八卦隶属度
    # ========================================================

    def classify_word(self, word: str) -> Tuple[str, List[float]]:
        """将单词分类并返回8维八卦语义向量"""
        wl = word.lower().strip()

        if wl in FUNCTION_WORDS:
            return ('function', WORD_CLASS_VECTORS['function'])
        elif wl in ACTION_VERBS:
            return ('action', WORD_CLASS_VECTORS['action'])
        elif wl in TOOL_NOUNS:
            return ('tool', WORD_CLASS_VECTORS['tool'])
        elif wl in LOCATION_NOUNS:
            return ('location', WORD_CLASS_VECTORS['location'])
        elif wl in OBJECT_NOUNS:
            return ('object', WORD_CLASS_VECTORS['object'])
        else:
            # 兜底：尝试字面子串匹配
            for loc in LOCATION_NOUNS:
                if loc in wl:
                    return ('location', WORD_CLASS_VECTORS['location'])
            for obj in OBJECT_NOUNS:
                if obj in wl:
                    return ('object', WORD_CLASS_VECTORS['object'])
            # 默认物体
            return ('unknown', WORD_CLASS_VECTORS['object'])

    # ========================================================
    # L2: 单词间"乘承比应"关系
    # ========================================================

    def word_relation(self, w1: str, c1: str, w2: str, c2: str) -> str:
        """
        判断两个相邻词的语义关系（仅对实词+实词）

        乘: 前者支配后者（动词+宾语如 take clock）
        承: 后者支撑前者（宾语+补语如 clock from desk）
        比: 两者并列（名词+名词如 clock and lamp）
        应: 工具与目标呼应（lamp + light）
        """
        if c1 == 'function' or c2 == 'function':
            return 'boundary'  # 功能词=边界

        # 动词 + 名词 → 乘（动支配名）
        if c1 == 'action' and c2 in ('object', 'location', 'tool'):
            return 'cheng'  # 乘: 动词乘名词
        # 名词 + 动词 → 承（名承载动）
        if c1 in ('object', 'location', 'tool') and c2 == 'action':
            return 'cheng_ni'  # 逆乘（罕见）
        # 名词 + 名词 → 比（并列）或 应（呼应）
        if c1 in ('object',) and c2 in ('location',):
            return 'ying'  # 应: 物体→位置
        if c1 in ('object', 'location', 'tool') and c2 in ('object', 'location', 'tool'):
            return 'bi'  # 比: 并列
        if c1 == 'tool' and c2 in ('object',):
            return 'ying'  # 应: 工具→对象
        if c1 == 'object' and c2 == 'tool':
            return 'ying_ni'  # 逆应: 对象→工具

        return 'unknown'

    # ========================================================
    # L3: 功能词驱动语义分块
    # ========================================================

    def parse_task_desc(self, task_desc: str) -> Dict:
        """
        用YLYW三层语义解析task_desc

        Returns:
            {
                'task_type': 推断的任务类型,
                'words': [(word, class, bagua_dominant), ...],
                'chunks': [语义块],
                'semantic_structure': 语义结构,
                'inferred_args': {推断的关键参数},
            }
        """
        # Tokenize: 拆分连写的复合词
        raw_tokens = re.findall(r'[a-zA-Z]+', task_desc.lower())
        raw_words = []
        for tok in raw_tokens:
            found = False
            for known in sorted(OBJECT_NOUNS | LOCATION_NOUNS | TOOL_NOUNS,
                              key=len, reverse=True):
                if len(known) >= 4 and tok.startswith(known) and tok != known:
                    raw_words.append(known)
                    raw_words.append(tok[len(known):])
                    found = True
                    break
            if not found:
                raw_words.append(tok)

        # L1: 逐词分类
        word_info = []
        for w in raw_words:
            cls, vec = self.classify_word(w)
            dominant = BAGUA[vec.index(max(vec))]
            word_info.append({
                'word': w,
                'class': cls,
                'vector': vec,
                'bagua': dominant,
            })

        # L2: 相邻词关系（功能词作为边界，实词间建立"跳过"关系）
        relations = []
        # 找到所有实词索引
        content_indices = [i for i, wi in enumerate(word_info)
                          if wi["class"] != "function"]
        for k in range(len(content_indices) - 1):
            i = content_indices[k]
            j = content_indices[k + 1]
            w1, c1 = word_info[i]["word"], word_info[i]["class"]
            w2, c2 = word_info[j]["word"], word_info[j]["class"]
            rel = self.word_relation(w1, c1, w2, c2)
            relations.append((i, j, rel))

        # L3: 功能词边界 → 语义分块
        chunks = []
        current_chunk = []
        for wi in word_info:
            if wi['class'] == 'function':
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                # 关键功能词：标记语义角色
            else:
                current_chunk.append(wi)
        if current_chunk:
            chunks.append(current_chunk)

        # 推断任务类型（基于语义结构）
        task_type = self._infer_task_type(word_info, chunks, relations)

        # 推断关键参数（目标物体、目标位置、工具）
        inferred_args = self._infer_args(word_info, chunks, relations)

        # 用YLYW卦象进行整体特征编码
        ylyw_feats = self._ylyw_encode(word_info, task_type)

        return {
            'task_type': task_type,
            'words': [(wi['word'], wi['class'], wi['bagua']) for wi in word_info],
            'chunks': [[w['word'] for w in c] for c in chunks],
            'relations': [(word_info[i]['word'], word_info[j]['word'], r)
                         for i, j, r in relations if r != 'boundary'],
            'inferred_args': inferred_args,
            'ylyw_features': ylyw_feats,
        }

    def _infer_task_type(self, word_info, chunks, relations) -> str:
        """基于YLYW语义解析推断ALFWorld任务类型"""
        words_lower = [wi['word'] for wi in word_info]
        word_class = {wi['word']: wi['class'] for wi in word_info}
        
        # 重建原始task_desc用于phrase匹配
        task_desc_lower = ' '.join(words_lower)

        # 统计乘关系
        cheng_count = sum(1 for i, j, r in relations
                         if r == 'cheng' and word_class.get(word_info[j]['word']) in ('object', 'tool', 'location'))

        # 规则判断
        has_light = any(w in words_lower for w in ('lamp', 'light', 'desklamp', 'floorlamp')) \
                    and any(w in words_lower for w in ('turn', 'use', 'look'))
        has_clean = any(w in words_lower for w in ('clean', 'wash', 'scrub', 'wipe', 'rinse'))
        # 排除"a clean X"模式：clean作为形容词
        if has_clean:
            # 检查clean是否作为动词（前面没有a/the/an等冠词直接修饰）
            clean_verbs = []
            for wi in word_info:
                if wi['word'] in ('clean', 'wash', 'scrub', 'wipe', 'rinse', 'washed', 'cleaned', 'rinsed'):
                    idx = word_info.index(wi)
                    # 如果前面紧邻冠词（a clean X），则clean是形容词，不算
                    if idx > 0 and word_info[idx-1]['word'] in ('a', 'an', 'the'):
                        continue  # 形容词，跳过
                    # 如果是"put a clean"模式
                    if idx > 1 and word_info[idx-2]['word'] in ('put', 'place'):
                        continue  # put a clean → clean是形容词
                    clean_verbs.append(wi['word'])
            has_clean = len(clean_verbs) > 0
        has_cool = any(w in words_lower for w in ('cool', 'chill', 'fridge', 'refrigerator', 'cooled'))
        has_heat = any(w in words_lower for w in ('heat', 'warm', 'cook', 'heated', 'warmed'))
        has_slice = any(w in words_lower for w in ('slice', 'cut', 'chop', 'sliced'))
        has_movable = any(w in words_lower for w in ('movable', 'move')) or \
                      any(phrase in task_desc_lower for phrase in (
                          'with a', 'with the', 'in it', 'inside the',
                          'containing'))
        has_two = ('two' in words_lower or 'both' in words_lower or
                   cheng_count >= 3 or
                   task_desc_lower.count(' and ') >= 1)

        if has_light:
            return 'look_at_obj_in_light'
        elif has_movable:
            return 'pick_and_place_with_movable_recep'
        elif has_clean:
            return 'pick_clean_then_place_in_recep'
        elif has_cool:
            return 'pick_cool_then_place_in_recep'
        elif has_heat:
            return 'pick_heat_then_place_in_recep'
        elif has_slice:
            return 'pick_cool_then_place_in_recep'
        elif has_two:
            return 'pick_two_obj_and_place'
        else:
            return 'pick_and_place_simple'

    def _infer_args(self, word_info, chunks, relations) -> Dict:
        """推断任务的参数"""
        words = [wi['word'] for wi in word_info]

        # 找乘关系中的名词宾语
        cheng_targets = []
        for i, j, r in relations:
            if r == 'cheng':
                w2, c2 = word_info[j]['word'], word_info[j]['class']
                if c2 in ('object', 'tool', 'location'):
                    cheng_targets.append(w2)

        # 找应关系中的目标位置
        ying_targets = []
        for i, j, r in relations:
            if r == 'ying' or r == 'ying_ni':
                w1, w2 = word_info[i]['word'], word_info[j]['word']
                for wi in word_info:
                    if wi['word'] == w2 and wi['class'] == 'location':
                        ying_targets.append(w2)

        return {
            'target_objects': [w for w in cheng_targets
                             if any(wi['word'] == w and wi['class'] in ('object', 'tool')
                                   for wi in word_info)],
            'target_locations': [w for w in ying_targets],
            'tools': [wi['word'] for wi in word_info if wi['class'] == 'tool'],
            'actions': [wi['word'] for wi in word_info if wi['class'] == 'action'],
        }

    def _ylyw_encode(self, word_info, task_type) -> Dict:
        """用YLYW六爻编码对task_desc进行整体语义编码"""
        # 统计词类分布
        class_counts = {'action': 0, 'object': 0, 'location': 0, 'tool': 0, 'function': 0}
        for wi in word_info:
            if wi['class'] in class_counts:
                class_counts[wi['class']] += 1

        n = max(1, len(word_info))

        features = {
            'stability': 0.5 + 0.1 * class_counts['location'] / n,
            'roll_tendency': 0.5 - 0.1 * class_counts['location'] / n,
            'strength_needed': 0.3 + 0.2 * class_counts['action'] / n,
            'fragility': 0.3 + 0.1 * class_counts['object'] / n,
            'task_priority': 0.5,
            'reachability': 0.5 + 0.1 * class_counts['location'] / n,
            'support_area': 0.5,
            'occlusion': 0.3,
            'obstacle_density': 0.2,
            'grasp_surface_quality': 0.5,
            'weight_ratio': 0.5,
            'visibility': 0.7,
            'deformability': 0.3,
        }

        perception = self.manual.perceive_and_encode(features)
        return {
            'yao_vector': perception['yao_vector'].tolist(),
            'dominant_trigram': perception['dominant_trigram'].name,
            'best_hexagram': (perception['best_hexagram'].name
                             if perception['best_hexagram'] else 'NONE'),
            'hexagram_score': perception['hexagram_match_score'],
        }

    def get_suggested_phases(self, task_type: str, inferred_args: Dict) -> List[List[str]]:
        """
        根据语义解析结果，生成优化后的子目标序列
        增加：根据inferred_args中的语义信息优化目标选择
        """
        target_objects = inferred_args.get('target_objects', [])
        target_locations = inferred_args.get('target_locations', [])
        tools = inferred_args.get('tools', [])

        # 标准子目标框架
        if task_type == 'look_at_obj_in_light':
            return [['go to'], ['take'], ['go to'], ['use']]

        elif task_type == 'pick_and_place_simple':
            return [['go to'], ['take'], ['go to'], ['put']]

        elif task_type == 'pick_clean_then_place_in_recep':
            return [['go to'], ['take'], ['go to'], ['clean'], ['go to'], ['put']]

        elif task_type == 'pick_cool_then_place_in_recep':
            return [['go to'], ['take'], ['go to'], ['cool'], ['go to'], ['put']]

        elif task_type == 'pick_heat_then_place_in_recep':
            return [['go to'], ['take'], ['go to'], ['heat'], ['go to'], ['put']]

        elif task_type == 'pick_two_obj_and_place':
            return [['go to'], ['take'], ['go to'], ['put'],
                    ['go to'], ['take'], ['go to'], ['put']]

        elif task_type == 'pick_and_place_with_movable_recep':
            return [['go to'], ['take'], ['go to'], ['put'],
                    ['take'], ['go to'], ['put']]

        else:
            return [['go to'], ['take'], ['go to'], ['put']]

    def score_action(self, cmd: str, target_phase_actions: List[str],
                     inferred_args: Dict, task_type: str) -> float:
        """
        用YLYW语义信息对候选动作评分

        与原先YLYW Agent中的select_action配合使用，
        提供额外的语义评分维度
        """
        cmd_lower = cmd.lower().strip()
        score = 0.0

        # 语义重合: 命令中包含inferred_args中的关键词加分
        for obj in inferred_args.get('target_objects', []):
            if obj in cmd_lower:
                score += 0.8
                break

        for loc in inferred_args.get('target_locations', []):
            if loc in cmd_lower:
                score += 0.6
                break

        for tool in inferred_args.get('tools', []):
            if tool in cmd_lower:
                score += 0.5
                break

        # 动作类型匹配
        for ta in target_phase_actions:
            if cmd_lower.startswith(ta):
                score += 0.4
                break

        return score


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    parser = YLYWSemanticParser()

    test_tasks = [
        "Hold the clock and turn on the lamp.",
        "Put the baseball bat on the bed.",
        "Put a clean mug on the desk.",
        "Put a cool apple in the fridge.",
        "Put a heated potato on the countertop.",
        "Put two pencils in the drawer.",
        "Put a clean sponge in the movable garbage can.",
    ]

    print("=" * 70)
    print("YLYW 语义解析器 for ALFWorld Task Description")
    print("=" * 70)

    for td in test_tasks:
        result = parser.parse_task_desc(td)
        print(f"\n{'─'*60}")
        print(f"Task: {td}")
        print(f"{'─'*60}")
        print(f"  Inferred Type: {result['task_type']}")
        print(f"  Words: {[(w, c, g) for w, c, g in result['words']]}")
        print(f"  Chunks: {result['chunks']}")
        print(f"  Relations: {result['relations']}")
        print(f"  Args: {json.dumps(result['inferred_args'], indent=2)}")
        print(f"  YLYW Hexagram: {result['ylyw_features']['best_hexagram']}")
        print(f"  YLYW Score: {result['ylyw_features']['hexagram_score']:.3f}")
