#!/usr/bin/env python3
"""
知几学习模块 (Zhiji Learning Module)

《系辞下》："知几其神乎！几者，动之微，吉之先见者也。君子见几而作，不俟终日。"

核心公式：K = K_prior ⊕ K_calibration

本模块实现跨游戏的经验积累与先验校准：
  第一层：同义词校准 —— 从admissible中学习环境的实际实体命名
  第二层：位置先验校准 —— 从成功探索中更新物体-位置先验矩阵
  第三层：场景结构校准 —— 从容器交互中学习场景布局规律

设计原则：
  - 不使用LLM，纯规则提取经验
  - 一次观察即校准（"见几而作，不俟终日"）
  - 经验跨游戏复用（同一FloorPlan共享空间经验）
  - 先验只增强不覆盖（K_calibration是校准不是替换）
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class ZhijiLearning:
    """
    知几学习引擎：从执行轨迹中积累经验，校准先验知识。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ====== 第一层：同义词校准 ======
        # desc中的词 → 环境中实际的实体名列表
        # 例: "cup" → ["mug"], "salt" → ["peppershaker", "saltshaker"]
        self.synonym_map: Dict[str, Set[str]] = defaultdict(set)

        # 已知的环境实体名（从admissible中观察到的take命令）
        self.known_entities: Set[str] = set()

        # ====== 第二层：位置先验校准 ======
        # 物体类型 → {位置类型: 发现次数}
        # 例: "plate" → {"countertop": 3, "shelf": 1}
        self.object_location_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 场景(FloorPlan) → 物体 → 具体位置
        self.scene_object_map: Dict[str, Dict[str, str]] = defaultdict(dict)

        # ====== 第三层：场景结构校准 ======
        # 场景 → 需要open的容器集合
        self.scene_openable: Dict[str, Set[str]] = defaultdict(set)

        # 场景 → 位置 → 该位置有什么物体
        self.scene_location_contents: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        # 场景 → 空位置集合（去过但什么都没有）
        self.scene_empty_locations: Dict[str, Set[str]] = defaultdict(set)

        # ====== 统计 ======
        self.games_played = 0
        self.games_won = 0
        self.calibrations_applied = 0

    def observe_trajectory(self, game_result: dict, trajectory: list,
                           scene: str = '', task_desc: str = ''):
        """
        从一局游戏的完整轨迹中提取经验。

        Args:
            game_result: {'won': bool, 'steps': int, 'task_type': str, ...}
            trajectory: [(action, obs, admissible_commands), ...]
            scene: FloorPlan名称
            task_desc: 任务描述
        """
        self.games_played += 1
        if game_result.get('won'):
            self.games_won += 1

        desc_lower = task_desc.lower()

        for action, obs, admissible in trajectory:
            obs_lower = obs.lower()

            # 1. 从admissible中的take命令提取环境实体名
            for cmd in admissible:
                if cmd.startswith('take '):
                    m = re.match(r'take (.+?) from (.+)', cmd)
                    if m:
                        obj_full = m.group(1).strip()  # "mug 1"
                        loc_full = m.group(2).strip()  # "countertop 2"
                        obj_base = re.sub(r'\s*\d+$', '', obj_full).lower()  # "mug"
                        loc_base = re.sub(r'\s*\d+$', '', loc_full).lower()  # "countertop"

                        self.known_entities.add(obj_base)

                        # 同义词校准：desc中说的词 vs 环境中的实体名
                        self._calibrate_synonyms(desc_lower, obj_base)

                        # 位置校准
                        self.object_location_counts[obj_base][loc_base] += 1

                        # 场景校准
                        if scene:
                            self.scene_object_map[scene][obj_base] = loc_full
                            if obj_full not in self.scene_location_contents[scene][loc_full]:
                                self.scene_location_contents[scene][loc_full].append(obj_full)

            # 2. 从open命令学习容器状态
            if action.startswith('open '):
                container = action[5:].strip()
                if scene:
                    self.scene_openable[scene].add(re.sub(r'\s*\d+$', '', container.lower()))

            # 3. 从go to后的空观测学习空位置
            if action.startswith('go to '):
                loc = action[6:].strip()
                take_cmds = [c for c in admissible if c.startswith('take ')]
                if not take_cmds and 'nothing' in obs_lower:
                    if scene:
                        self.scene_empty_locations[scene].add(loc)

    def _calibrate_synonyms(self, desc_lower: str, env_entity: str):
        """
        第一层知几：从"desc中说什么"vs"环境中叫什么"的差异中学习同义词。

        核心逻辑（见几而作）：
          desc说"cup"但环境中只有"mug" → 学到cup→mug
          desc说"salt"但环境中有"peppershaker" → 学到salt→peppershaker
        """
        # 常见的混用对
        synonym_candidates = {
            'cup': ['mug'],
            'coffee': ['mug', 'cup'],
            'mug': ['cup'],
            'salt': ['saltshaker', 'peppershaker'],
            'pepper': ['peppershaker', 'saltshaker'],
            'shaker': ['saltshaker', 'peppershaker'],
            'soap': ['soapbar', 'soapbottle'],
            'rag': ['cloth', 'dishsponge'],
            'cloth': ['cloth', 'dishsponge'],
            'disk': ['cd'],
            'disc': ['cd'],
            'remote': ['remotecontrol'],
            'key': ['keychain'],
            'keys': ['keychain'],
            'phone': ['cellphone'],
            'clock': ['alarmclock'],
            'towel': ['towel', 'handtowel'],
        }

        for desc_word, possible_envs in synonym_candidates.items():
            if desc_word in desc_lower and env_entity in possible_envs:
                self.synonym_map[desc_word].add(env_entity)
                if self.verbose and env_entity != desc_word:
                    print(f"    [知几:同义词] '{desc_word}' in desc → '{env_entity}' in env")

    def get_expanded_objects(self, nl_objects: List[str]) -> List[str]:
        """
        用知几经验扩展目标物体列表。
        K_prior（NL解析结果）⊕ K_calibration（同义词经验）
        """
        expanded = list(nl_objects)

        for obj in nl_objects:
            # 检查同义词映射
            if obj in self.synonym_map:
                for syn in self.synonym_map[obj]:
                    if syn not in expanded:
                        expanded.append(syn)
                        self.calibrations_applied += 1

            # 反向检查：obj可能是某个desc_word的环境名
            for desc_word, env_names in self.synonym_map.items():
                if obj in env_names:
                    for other in env_names:
                        if other not in expanded:
                            expanded.append(other)

        return expanded

    def get_location_prior_boost(self, obj_base: str, loc_base: str) -> float:
        """
        用知几经验增强位置先验。
        返回额外的评分加成（0-5分）。
        """
        counts = self.object_location_counts.get(obj_base, {})
        if not counts:
            return 0.0

        total = sum(counts.values())
        if total == 0:
            return 0.0

        loc_count = counts.get(loc_base, 0)
        # 经验频率 → 评分加成
        return (loc_count / total) * 5.0

    def get_scene_hints(self, scene: str) -> dict:
        """
        获取特定场景的知几经验。
        """
        return {
            'known_objects': dict(self.scene_object_map.get(scene, {})),
            'openable_types': self.scene_openable.get(scene, set()),
            'empty_locations': self.scene_empty_locations.get(scene, set()),
            'location_contents': dict(self.scene_location_contents.get(scene, {})),
        }

    def should_skip_location(self, scene: str, location: str) -> bool:
        """
        根据场景经验判断是否跳过某位置（之前去过且是空的）。
        """
        return location in self.scene_empty_locations.get(scene, set())

    def get_stats(self) -> dict:
        """统计信息"""
        return {
            'games_played': self.games_played,
            'games_won': self.games_won,
            'synonyms_learned': {k: list(v) for k, v in self.synonym_map.items() if v},
            'object_locations': {k: dict(v) for k, v in self.object_location_counts.items()},
            'calibrations_applied': self.calibrations_applied,
            'scenes_known': list(self.scene_object_map.keys()),
        }
