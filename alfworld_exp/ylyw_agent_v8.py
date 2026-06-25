#!/usr/bin/env python3
"""
YLYW Agent V8 — V7 + L0空间态势感知增强

在V7基础上集成L0层的核心能力：
1. NL解析增强：对模糊描述做多候选匹配
2. 空间八卦编码：位置类型→卦象，引导探索
3. 先验置信度衰减：探过的位置降权
4. 目标物体容错：salt/pepper/shaker等近义词扩展匹配
"""
import re, sys, os
from typing import List, Dict, Optional, Set
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_agent_v7 import YLYWAgentV7, TASK_PLANS, TASK_TOOLS, ALL_OBJECTS, ALL_RECEPTACLES
from task_desc_parser import parse_task_desc

# 位置类型→八卦编码（来自ylyw_nested_spatial.py）
LOCATION_TRIGRAMS = {
    'countertop': '坤',  # 承载
    'shelf': '乾',       # 高处
    'desk': '坤',        # 平面
    'cabinet': '震',     # 需开启
    'drawer': '震',      # 需开启
    'sinkbasin': '坎',   # 水
    'fridge': '坎',      # 冷
    'microwave': '离',   # 热
    'stoveburner': '离', # 热
    'coffeemachine': '兑', # 金属器具
    'toaster': '离',     # 热
    'bed': '坤',         # 平面
    'sofa': '坤',        # 平面
    'safe': '艮',        # 静止/封闭
    'garbagecan': '巽',  # 入口
    'toilet': '坎',      # 水
    'bathtubbasin': '坎',# 水
    'dresser': '坤',     # 平面
    'sidetable': '坤',   # 平面
    'coffeetable': '坤', # 平面
    'tvstand': '坤',     # 平面
    'laundryhamper': '巽', # 入口
    'handtowelholder': '艮', # 固定
    'towelholder': '艮', # 固定
    'toiletpaperhanger': '艮', # 固定
}

# 物体常放位置的八卦相生映射
OBJECT_TRIGRAM_AFFINITY = {
    # 物体的八卦属性 → 倾向的位置八卦（相生/同类）
    'mug': ['坤', '兑', '坎'],       # 杯子→平面/金属器具/水
    'cup': ['坤', '兑', '坎'],
    'plate': ['坤', '坎'],           # 盘子→平面/水
    'bowl': ['坤', '坎'],
    'knife': ['坤', '震'],           # 刀→平面/抽屉
    'fork': ['坤', '震'],
    'spoon': ['坤', '震'],
    'book': ['坤', '乾'],            # 书→平面/高处
    'pen': ['坤', '震'],
    'pencil': ['坤', '震'],
    'cd': ['坤', '乾', '震'],
    'alarmclock': ['坤'],
    'cellphone': ['坤'],
    'laptop': ['坤'],
    'vase': ['坤', '乾'],
    'statue': ['坤', '乾'],
    'soapbar': ['坤', '坎'],
    'towel': ['艮'],
    'apple': ['坤', '坎'],           # 水果→平面/冰箱
    'tomato': ['坤', '坎'],
    'potato': ['坤', '坎'],
    'egg': ['坤', '坎'],
    'bread': ['坤', '离'],
    'lettuce': ['坤', '坎'],
    'saltshaker': ['坤', '震'],
    'peppershaker': ['坤', '震'],
    'keychain': ['坤', '震', '艮'],
    'pillow': ['坤'],
    'watch': ['坤', '震', '艮'],
    'creditcard': ['坤', '震'],
    'remotecontrol': ['坤'],
    'toiletpaper': ['艮', '震'],
}

# NL解析的近义词扩展（解决salt shaker=peppershaker等问题）
SYNONYM_GROUPS = {
    'shaker': ['saltshaker', 'peppershaker'],
    'salt': ['saltshaker', 'peppershaker'],
    'pepper': ['peppershaker', 'saltshaker'],
    'soap': ['soapbar', 'soapbottle'],
    'coffee': ['cup', 'mug'],
    'cup': ['cup', 'mug'],
    'mug': ['mug', 'cup'],
    'cloth': ['cloth', 'dishsponge'],
    'rag': ['cloth', 'dishsponge'],
    'disk': ['cd'],
    'disc': ['cd'],
    'key': ['keychain'],
    'keys': ['keychain'],
    'remote': ['remotecontrol'],
    'box': ['box', 'tissuebox'],
    'metal box': ['safe'],  # "Turn on a lamp with a metal box" → safe里的物体?不对,是box
}


class YLYWAgentV8(YLYWAgentV7):
    """V8: V7 + L0空间探索增强 + NL容错"""

    def __init__(self, verbose=False, use_oracle_type=False):
        super().__init__(verbose=verbose, use_oracle_type=use_oracle_type)
        self.location_confidence = {}  # 位置→置信度（L0自学习）
        self.discovered_objects = {}   # 物体→位置（全局发现记录）

    def reset(self, task_desc, task_type, pddl_params=None, initial_admissible=None):
        """V8: 增强NL解析+空间初始化"""
        # 先调用父类reset
        super().reset(task_desc, task_type, pddl_params, initial_admissible)

        # V8增强1: 目标物体近义词扩展
        expanded = []
        for obj in self.target_objects:
            expanded.append(obj)
            # 检查近义词组
            for key, synonyms in SYNONYM_GROUPS.items():
                if obj == key or key in obj:
                    for s in synonyms:
                        if s not in expanded:
                            expanded.append(s)
        self.target_objects = expanded

        # V8增强2: 从task_desc提取更多候选容器
        desc_lower = task_desc.lower()
        if not self.target_receps:
            # 尝试更宽松的匹配
            for rec_key, rec_aliases in ALL_RECEPTACLES.items():
                for alias in rec_aliases:
                    if alias in desc_lower:
                        if rec_key not in self.target_receps:
                            self.target_receps.append(rec_key)

        # V8增强3: 初始化L0空间置信度
        self.location_confidence = {}
        if initial_admissible:
            for cmd in initial_admissible:
                if cmd.startswith('go to '):
                    loc = cmd[6:].strip()
                    loc_base = re.sub(r'\s*\d+$', '', loc.lower())
                    # 初始置信度基于物体-位置八卦亲和度
                    conf = self._compute_trigram_affinity(loc_base)
                    self.location_confidence[loc] = conf

        self.discovered_objects = {}

        if self.verbose:
            print(f"  V8 enhancements:")
            print(f"    Expanded objects: {self.target_objects}")
            print(f"    Location confidences: { {k:f'{v:.2f}' for k,v in sorted(self.location_confidence.items(), key=lambda x:-x[1])[:5]} }")

    def _compute_trigram_affinity(self, loc_base: str) -> float:
        """计算位置与目标物体的八卦亲和度"""
        loc_trigram = LOCATION_TRIGRAMS.get(loc_base, '坤')
        affinity = 0.5  # 默认

        for obj in self.target_objects:
            obj_trigrams = OBJECT_TRIGRAM_AFFINITY.get(obj, ['坤'])
            if loc_trigram in obj_trigrams:
                affinity = max(affinity, 0.8)  # 八卦相合
            # 也用普通先验
            prior = self._object_location_prior([obj], loc_base)
            affinity = max(affinity, 0.3 + prior * 0.15)

        return min(affinity, 1.0)

    def _act_find(self, cmds, goal, obs):
        """V8: 用L0空间置信度增强探索评分"""
        # 先检记忆
        if goal in ('find_object', 'find_object_2'):
            for obj_name, loc in self.object_memory.items():
                obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
                if obj_base in self.target_objects:
                    go_cmd = f'go to {loc}'
                    if go_cmd in cmds and loc != self.current_location:
                        if self.verbose:
                            print(f"    [V8:memory] know {obj_name} at {loc}")
                        return go_cmd

        go_cmds = [c for c in cmds if c.startswith('go to ')]
        if not go_cmds:
            return self._fallback(cmds)

        if goal in ('find_object', 'find_object_2'):
            targets = self.target_objects
        elif goal == 'find_tool':
            targets = self.target_tools
        elif goal in ('find_recep', 'find_recep_2', 'find_final'):
            targets = self.target_receps
        else:
            targets = self.target_objects

        scored = []
        for cmd in go_cmds:
            loc = cmd[6:].strip().lower()
            loc_base = re.sub(r'\s*\d+$', '', loc)
            score = 0.0

            # 目标匹配
            for t in targets:
                if t == loc_base or t in loc_base or loc_base in t:
                    score += 10.0
                elif t.startswith(loc_base) or loc_base.startswith(t):
                    score += 5.0

            # V8: L0空间置信度
            conf = self.location_confidence.get(cmd[6:].strip(), 0.5)
            score += conf * 3.0

            # 未探索加分
            if cmd[6:].strip() not in self.explored:
                score += 2.0

            # 普通先验
            if goal in ('find_object', 'find_object_2'):
                score += self._object_location_prior(self.target_objects, loc_base)

            # 避免重复
            recent = self.history[-6:]
            if cmd in recent:
                score -= 3.0

            scored.append((score, cmd))

        scored.sort(key=lambda x: -x[0])

        if self.verbose and scored[:3]:
            print(f"    [V8:find] goal={goal}")
            for s, c in scored[:3]:
                loc = c[6:].strip()
                conf = self.location_confidence.get(loc, 0)
                print(f"      {s:5.1f} (conf={conf:.2f}) | {c}")

        return scored[0][1]

    def update(self, action, obs, info):
        """V8: 更新L0空间置信度"""
        super().update(action, obs, info)

        # V8: 探索后降低该位置的置信度（自学习衰减）
        if action.startswith('go to ') and info.get('action_success', True):
            loc = action[6:].strip()
            obs_lower = obs.lower()
            found_target = False
            for obj in self.target_objects:
                if obj in obs_lower:
                    found_target = True
                    break

            if not found_target and loc in self.location_confidence:
                # 衰减：没找到目标物体→降低置信度
                self.location_confidence[loc] *= 0.5
                if self.verbose:
                    print(f"    [V8:L0] {loc} no target → conf={self.location_confidence[loc]:.2f}")

        # 记录发现的物体
        if action.startswith('go to '):
            loc = action[6:].strip()
            take_cmds = [c for c in info.get('admissible_commands', []) if c.startswith('take ')]
            for cmd in take_cmds:
                m = re.match(r'take (.+?) from .+', cmd)
                if m:
                    self.discovered_objects[m.group(1)] = loc

    def _find_target_take(self, cmds):
        """V8: 带近义词的目标匹配"""
        take_cmds = [c for c in cmds if c.startswith('take ')]
        if not take_cmds:
            return None

        # 精确匹配
        for cmd in take_cmds:
            cmd_lower = cmd.lower()
            for obj in self.target_objects:
                if obj in cmd_lower:
                    return cmd

        return None
