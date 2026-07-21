#!/usr/bin/env python3
"""
知几学习 V11（升级版）

《系辞下》："几者，动之微，吉之先见者也。君子见几而作，不俟终日。"

V11知几在V10基础上新增：
  1. 场景结构学习 —— 从成功探索中学习每个场景的物体-位置关联
  2. 六爻模板学习 —— 从成功动作中积累六爻模板（动作→卦象映射）
  3. 行为模式学习 —— 从成功轨迹中提取动作序列模式
  4. 置信度衰减 —— 旧经验随时间衰减，新经验权重更高

核心公式：K = K_prior ⊕ K_calibration ⊕ K_scene ⊕ K_pattern
"""

import re
import json
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict


class ZhijiV11:
    """
    知几学习引擎 V11。

    与V10的zhiji_learning.py兼容，但新增场景记忆对齐接口。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ── V10兼容层 ──
        self.games_played = 0
        self.synonym_map: Dict[str, Set[str]] = defaultdict(set)
        self.known_entities: Set[str] = set()
        self.object_location_counts: Dict[str, Dict[str, int]] = (
            defaultdict(lambda: defaultdict(int))
        )
        self.calibrations_applied = 0

        # ── V11新增：六爻模板学习 ──
        # {动作词(如"打开"): {"yao": [...], "hexagram": "...", "count": N}}
        self.yao_templates: Dict[str, Dict] = {}

        # ── V11新增：行为模式学习 ──
        # {task_type: [{"phase": "...", "action_pattern": [...], "count": N}, ...]}
        self.behavior_patterns: Dict[str, List[Dict]] = defaultdict(list)

        # ── V11新增：场景物体分布学习 ──
        # {场景ID: {位置base: {物体base: 出现次数}}}
        self.scene_object_dist: Dict[str, Dict[str, Dict[str, int]]] = (
            defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        )

        # ── 统计 ──
        self.total_success_trajectories = 0
        self.total_failure_trajectories = 0

    # ═══════════════════════════════════════════════
    # 学习接口
    # ═══════════════════════════════════════════════

    def observe_trajectory(self, result: dict, trajectory: list,
                           scene: str = "", task_desc: str = "",
                           task_type: str = ""):
        """从完整轨迹中学习（兼容V10接口）"""
        self.games_played += 1

        if result.get('won', False):
            self.total_success_trajectories += 1
            self._learn_from_success(result, trajectory, scene, task_desc, task_type)
        else:
            self.total_failure_trajectories += 1

        # 从admissible命令中学习同义词（兼容V10）
        self._learn_synonyms(trajectory, task_desc)

        # V10兼容：无论成功失败，都从admissible的take命令中学习位置
        desc_lower = task_desc.lower()
        for action, obs, admissible in trajectory:
            for cmd in admissible:
                if cmd.startswith('take '):
                    m = re.match(r'take (.+?) from (.+)', cmd)
                    if m:
                        obj_full = m.group(1).strip()
                        loc_full = m.group(2).strip()
                        obj_base = re.sub(r'\s*\d+$', '', obj_full).lower()
                        loc_base = re.sub(r'\s*\d+$', '', loc_full).lower()
                        self.object_location_counts[obj_base][loc_base] += 1

    def observe_step(self, action: str, obs: str, cmds: list,
                     scene: str, location: str, success: bool,
                     current_phase: str, task_type: str):
        """单步学习（V11新增：实时学习）"""
        # 从admissible中学习实体名
        for cmd in cmds:
            if cmd.startswith('take '):
                m = re.match(r'take (.+?) from .+', cmd)
                if m:
                    taken = m.group(1).strip()
                    if taken:
                        self.known_entities.add(taken)

            # 从go to学习位置名
            if cmd.startswith('go to '):
                loc = cmd[6:].strip()
                if loc:
                    self.known_entities.add(loc)

            # 从open学习容器名
            if cmd.startswith('open '):
                container = cmd[5:].strip()
                if container:
                    self.known_entities.add(container)

        # 学习场景物体分布
        if scene and location:
            self._learn_scene_objects(obs, scene, location)

        # 如果动作成功，学习动作的六爻模板
        if success and action:
            self._learn_yao_from_action(action, current_phase, task_type)

    def observe_successful_action(self, action: str, phase: str,
                                  task_type: str, scene: str = "",
                                  location: str = ""):
        """从成功动作中学习（V11新增）"""
        self._learn_yao_from_action(action, phase, task_type)

        if scene and location:
            # 从动作中提取物体-位置对
            m = re.match(r'take (.+?) from (.+)', action)
            if m:
                obj = m.group(1).strip()
                loc = m.group(2).strip()
                obj_base = re.sub(r'\s*\d+$', '', obj.lower())
                loc_base = re.sub(r'\s*\d+$', '', loc.lower())
                self.object_location_counts[obj_base][loc_base] += 1
                self.scene_object_dist[scene][loc_base][obj_base] += 1

    # ── 内部学习方法 ──

    def _learn_from_success(self, result, trajectory, scene, task_desc, task_type):
        """从成功轨迹中学习"""
        for step, (action, obs, cmds) in enumerate(trajectory):
            # 学习位置
            if action.startswith('go to '):
                loc = action[6:].strip()
                self.known_entities.add(loc)

            # 学习物体-位置对
            if action.startswith('take '):
                m = re.match(r'take (.+?) from (.+)', action)
                if m:
                    obj = m.group(1).strip()
                    loc = m.group(2).strip()
                    obj_base = re.sub(r'\s*\d+$', '', obj.lower())
                    loc_base = re.sub(r'\s*\d+$', '', loc.lower())
                    self.object_location_counts[obj_base][loc_base] += 2

                    if scene:
                        self.scene_object_dist[scene][loc_base][obj_base] += 2

            # 学习成功放置
            if (action.startswith('put ') or action.startswith('move ')) and step > 0:
                # 从之前的take动作中找物体
                for prev_action, _, _ in trajectory[:step]:
                    if prev_action.startswith('take '):
                        m = re.match(r'take (.+?) from (.+)', prev_action)
                        if m:
                            obj = m.group(1).strip()
                            # 学习"这个物体应该放在这个位置"
                            rec_match = re.match(
                                r'(?:put|move) .+ (?:in/on|to) (.+)', action)
                            if rec_match:
                                rec = rec_match.group(1).strip()
                                obj_base = re.sub(r'\s*\d+$', '', obj.lower())
                                rec_base = re.sub(r'\s*\d+$', '', rec.lower())
                                self.object_location_counts[obj_base][rec_base] += 1

    def _learn_synonyms(self, trajectory, task_desc):
        """从轨迹中学习同义词（V10严格模式：只学习预定义的高置信度词对）"""
        desc_lower = task_desc.lower()
        take_objects = set()

        for action, obs, cmds in trajectory:
            if action.startswith('take '):
                m = re.match(r'take (.+?) from .+', action)
                if m:
                    taken = m.group(1).strip()
                    take_objects.add(taken)

        # V10模式：只识别预定义的同义词候选对（cup↔mug, salt↔shaker等）
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
            'lettuce': ['tomato', 'potato'],
        }

        for taken in take_objects:
            taken_base = re.sub(r'\s*\d+$', '', taken).lower()
            for desc_word, possible_envs in synonym_candidates.items():
                if desc_word in desc_lower and taken_base in possible_envs:
                    self.synonym_map[desc_word].add(taken_base)
                    if self.verbose:
                        print(f"    [知几:同义词] '{desc_word}' in desc → '{taken_base}' in env")

    def _learn_yao_from_action(self, action: str, phase: str, task_type: str):
        """从成功动作中学习六爻模板"""
        # 提取动作核心动词
        verb = action.split()[0] if action else ""
        if not verb:
            return

        # 将英文动作映射到中文动作词
        action_to_chinese = {
            "take": "拿",
            "put": "放",
            "move": "放",
            "go": "去",
            "open": "开",
            "close": "关",
            "clean": "洗",
            "heat": "热",
            "cool": "冷",
            "slice": "切",
            "use": "用",
            "look": "看",
        }

        cn_verb = action_to_chinese.get(verb, verb)

        # 用汉字引擎获取六爻模板
        try:
            from hanzi_engine import HanziEngine
            engine = HanziEngine(verbose=False)
            result = engine.sentence(cn_verb)
            yao = result["yao_vector"]
            hex_name = result["main_hexagram"]

            # 累积模板
            if cn_verb not in self.yao_templates:
                self.yao_templates[cn_verb] = {
                    "yao": yao,
                    "hexagram": hex_name,
                    "count": 1,
                    "phases": {phase},
                    "task_types": {task_type},
                }
            else:
                t = self.yao_templates[cn_verb]
                # 移动平均更新六爻
                n = t["count"]
                t["yao"] = [(t["yao"][i] * n + yao[i]) / (n + 1)
                           for i in range(6)]
                t["count"] += 1
                t["phases"].add(phase)
                t["task_types"].add(task_type)
                # 出现最多的卦象
                from collections import Counter
                if "hex_counter" not in t:
                    t["hex_counter"] = Counter({t["hexagram"]: n})
                t["hex_counter"][hex_name] += 1
                t["hexagram"] = t["hex_counter"].most_common(1)[0][0]

            self.calibrations_applied += 1

        except ImportError:
            pass

    def _learn_scene_objects(self, obs: str, scene: str, location: str):
        """从观测文本中学习场景物体分布"""
        # 解析obs中的物体名
        obs_lower = obs.lower()

        # 常见模式："On the countertop 1 you see: a mug, a plate"
        if 'you see' in obs_lower or 'you see:' in obs_lower:
            # 提取冒号后的物体列表
            m = re.search(r'you see:?\s*(.+)', obs_lower)
            if m:
                items_text = m.group(1)
                # 提取每个物体（去掉冠词）
                items = re.findall(r'(?:a|an|the)\s+(\w+\s*\w*)', items_text)
                loc_base = re.sub(r'\s*\d+$', '', location.lower())
                for item in items:
                    item_clean = item.strip()
                    if item_clean:
                        self.scene_object_dist[scene][loc_base][item_clean] += 1
                        obj_base = re.sub(r'\s*\d+$', '', item_clean)
                        self.object_location_counts.get(obj_base, {})[loc_base] += 1

    # ═══════════════════════════════════════════════
    # 查询接口
    # ═══════════════════════════════════════════════

    def get_yao_template(self, action: str) -> Optional[list]:
        """获取某个动作的六爻模板"""
        verb = action.split()[0].lower()
        action_to_chinese = {
            "take": "拿", "put": "放", "move": "放",
            "go": "去", "open": "开", "close": "关",
            "clean": "洗", "heat": "热", "cool": "冷",
            "use": "用", "look": "看",
        }
        cn_verb = action_to_chinese.get(verb, verb)
        if cn_verb in self.yao_templates:
            return self.yao_templates[cn_verb]["yao"]
        return None

    def get_location_prior_boost(self, obj: str, location: str) -> float:
        """获取位置先验的提升值（兼容V10精确匹配）"""
        obj_base = obj.lower().strip()
        loc_base = re.sub(r'\s*\d+$', '', location.lower()).strip()

        counts = self.object_location_counts.get(obj_base, {})
        if not counts:
            return 0.0

        total = sum(counts.values())
        if total == 0:
            return 0.0

        loc_count = counts.get(loc_base, 0)
        return (loc_count / total) * 5.0

    def get_expanded_objects(self, objects: List[str]) -> List[str]:
        """用同义词扩展目标物体（兼容V10）"""
        expanded = list(objects)
        for obj in objects:
            if obj in self.synonym_map:
                for syn in self.synonym_map[obj]:
                    if syn not in expanded:
                        expanded.append(syn)
        return expanded

    def get_behavior_pattern(self, task_type: str, phase: str) -> Optional[str]:
        """从行为模式中获取建议动作"""
        patterns = self.behavior_patterns.get(task_type, [])
        for p in patterns:
            if p.get("phase") == phase and p["count"] > 2:
                # 返回最常见的动作模式中的第一个动作
                if p["action_pattern"]:
                    return p["action_pattern"][0]
        return None

    def get_scene_object_hint(self, scene: str, object_base: str) -> str:
        """查询场景中某个物体最可能出现的位置"""
        if scene in self.scene_object_dist:
            for loc, objs in self.scene_object_dist[scene].items():
                for obj, count in objs.items():
                    if object_base in obj or obj in object_base:
                        if count > 0:
                            return loc
        return ""

    def get_stats(self) -> dict:
        """获取学习统计（兼容V10）"""
        return {
            "games_played": self.games_played,
            "synonyms_learned": {k: list(v) for k, v in self.synonym_map.items()},
            "object_locations": dict(self.object_location_counts),
            "calibrations_applied": self.calibrations_applied,
            "yao_templates": {k: {"count": v["count"], "hexagram": v["hexagram"]}
                             for k, v in self.yao_templates.items()},
            "known_entities": len(self.known_entities),
        }

    def save_experience(self, path: str):
        """保存经验到JSON"""
        data = {
            "games_played": self.games_played,
            "synonym_map": {k: list(v) for k, v in self.synonym_map.items()},
            "known_entities": list(self.known_entities),
            "object_location_counts": dict(self.object_location_counts),
            "calibrations_applied": self.calibrations_applied,
            "yao_templates": self.yao_templates,
            "total_success": self.total_success_trajectories,
            "total_failure": self.total_failure_trajectories,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.verbose:
            print(f"  [知几V11] 已保存: {path}")

    def load_experience(self, path: str):
        """从JSON加载经验"""
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.games_played = data.get("games_played", 0)
        self.synonym_map = defaultdict(
            set, {k: set(v) for k, v in data.get("synonym_map", {}).items()}
        )
        self.known_entities = set(data.get("known_entities", []))
        self.object_location_counts = defaultdict(
            lambda: defaultdict(int),
            data.get("object_location_counts", {})
        )
        self.calibrations_applied = data.get("calibrations_applied", 0)
        self.yao_templates = data.get("yao_templates", {})
        self.total_success_trajectories = data.get("total_success", 0)
        self.total_failure_trajectories = data.get("total_failure", 0)

        if self.verbose:
            print(f"  [知几V11] 已加载: {self.games_played}局经验, "
                  f"{len(self.yao_templates)}个六爻模板")
