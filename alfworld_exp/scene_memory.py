#!/usr/bin/env python3
"""
场景记忆模块 (Scene Memory Module)

核心功能：跨局记忆每个场景(floor_plan)的拓扑结构、物体位置、容器状态。
让YLYW Agent V11具备"进过一个场景后，下次再来就知道东西在哪"的能力。

《易·系辞上》："仰以观于天文，俯以察于地理，是故知幽明之故。"
场景记忆就是YLYW的"地理"——对环境的先验知识积累。

设计原则：
  - 所有记忆来自观测(observation)和动作结果
  - 每个场景独立存储（scene = floor_plan）
  - 置信度累积：看到一次 +1，成功操作 +2，失败 -1
  - 记忆可导出/导入（JSON序列化）
"""

import re
import json
import os
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict


class SceneMemory:
    """
    场景记忆引擎。

    记录：
      1. 场景中所有位置(go to目标)的拓扑关系
      2. 每个位置出现过的物体（从take命令和obs中提取）
      3. 可打开的容器
      4. 工具位置（sinkbasin/microwave/fridge等固定设备）
      5. 物体-位置关联的置信度
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ── 场景索引 ──
        # scene_id (floor_plan) → SceneData
        self.scenes: Dict[str, 'SceneData'] = {}

        # ── 跨场景通用知识 ──
        # {物体base: {位置base: 出现次数}}
        self.cross_scene_object_locations: Dict[str, Dict[str, int]] = (
            defaultdict(lambda: defaultdict(int))
        )

        # 当前场景ID
        self.current_scene: Optional[str] = None

    def set_scene(self, scene_id: str):
        """切换到指定场景（如果场景首次进入则自动创建）"""
        if scene_id not in self.scenes:
            self.scenes[scene_id] = SceneData(scene_id, self.verbose)
            if self.verbose:
                print(f"     [场景记忆] 创建新场景: {scene_id}")
        self.current_scene = scene_id

    def get_current(self) -> Optional['SceneData']:
        """获取当前场景数据"""
        if self.current_scene and self.current_scene in self.scenes:
            return self.scenes[self.current_scene]
        return None

    # ── 记录接口 ──

    def observe_location(self, location: str):
        """记录在场景中看到一个位置"""
        scene = self.get_current()
        if scene:
            scene.add_location(location)

    def observe_object_at(self, obj_name: str, location: str, confidence: int = 1):
        """记录物体出现在某位置"""
        scene = self.get_current()
        if scene:
            scene.add_object_at(obj_name, location, confidence)

        # 同时更新跨场景知识
        obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
        loc_base = re.sub(r'\s*\d+$', '', location.lower())
        if obj_base not in self.cross_scene_object_locations:
            self.cross_scene_object_locations[obj_base] = defaultdict(int)
        self.cross_scene_object_locations[obj_base][loc_base] += confidence

    def observe_container_open(self, container: str, location: str):
        """记录容器被打开"""
        scene = self.get_current()
        if scene:
            scene.mark_openable(container, location)

    def observe_tool_location(self, tool: str, location: str):
        """记录工具（固定设备）的位置"""
        scene = self.get_current()
        if scene:
            scene.record_tool_location(tool, location)

    def observe_interaction_result(self, obj: str, location: str, success: bool):
        """记录与某个位置上的物体的交互结果（成功/失败）"""
        if success:
            self.observe_object_at(obj, location, confidence=2)
        else:
            scene = self.get_current()
            if scene:
                scene.add_object_at(obj, location, confidence=-1)

    def observe_explored_location(self, location: str, had_target: bool):
        """记录某个位置是否包含目标物体"""
        scene = self.get_current()
        if scene:
            if had_target:
                scene.mark_target_location(location)
            else:
                scene.mark_empty_location(location)

    # ── 查询接口 ──

    def get_object_locations(self, obj_name: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """查询某个物体最可能出现在哪些位置（按置信度排序）"""
        scene = self.get_current()
        if scene:
            return scene.get_object_locations(obj_name, top_k)

        # 跨场景兜底
        obj_base = re.sub(r'\s*\d+$', '', obj_name.lower())
        if obj_base in self.cross_scene_object_locations:
            locs = sorted(
                self.cross_scene_object_locations[obj_base].items(),
                key=lambda x: -x[1]
            )
            return [(loc, count / max(1, sum(v for _, v in locs)))
                    for loc, count in locs[:top_k]]
        return []

    def get_tool_location(self, tool: str) -> Optional[str]:
        """查询工具位置"""
        scene = self.get_current()
        if scene:
            return scene.get_tool_location(tool)
        return None

    def get_locations_near(self, location: str, radius: int = 1) -> List[str]:
        """查询某个位置附近的其它位置（拓扑相邻）"""
        scene = self.get_current()
        if scene:
            return scene.get_nearby_locations(location, radius)
        return []

    def get_known_openables(self) -> List[str]:
        """返回场景中已知可打开的容器"""
        scene = self.get_current()
        if scene:
            return scene.get_known_openables()
        return []

    def get_all_object_memory(self) -> Dict[str, str]:
        """返回当前场景所有物体记忆"""
        scene = self.get_current()
        if scene:
            return scene.get_all_object_memory()
        return {}

    def get_target_locations(self) -> Set[str]:
        """返回当前场景中标记为有目标的位置"""
        scene = self.get_current()
        if scene:
            return scene.target_locations
        return set()

    def get_empty_locations(self) -> Set[str]:
        """返回当前场景中标记为空的位置"""
        scene = self.get_current()
        if scene:
            return scene.empty_locations
        return set()

    # ── 场景探索辅助 ──

    def score_location_for_target(self, location: str, target_objects: List[str]) -> float:
        """对一个位置评分：该位置有多大可能性包含目标物体"""
        scene = self.get_current()
        if not scene:
            return 0.0

        score = 0.0
        loc_base = re.sub(r'\s*\d+$', '', location.lower())

        # 从场景记忆中找
        for obj in target_objects:
            locs = self.get_object_locations(obj)
            for loc, conf in locs:
                if loc_base in loc or loc in loc_base:
                    score += conf * 2.0

        # 从跨场景通用知识中找
        for obj in target_objects:
            if obj in self.cross_scene_object_locations:
                for loc, count in self.cross_scene_object_locations[obj].items():
                    if loc in loc_base or loc_base in loc:
                        score += count * 0.5

        return score

    def is_empty_location(self, location: str) -> bool:
        """判断某个位置是否已知为空（去过但没有目标物体）"""
        scene = self.get_current()
        if scene:
            return location in scene.empty_locations
        return False

    def has_been_explored(self, location: str) -> bool:
        """判断某个位置是否已经探索过"""
        scene = self.get_current()
        if scene:
            return location in scene.explored_locations
        return False

    # ── 序列化 ──

    def save(self, path: str):
        """保存场景记忆到JSON文件"""
        data = {
            "scenes": {sid: sd.to_dict() for sid, sd in self.scenes.items()},
            "cross_scene": dict(self.cross_scene_object_locations),
            "current_scene": self.current_scene,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.verbose:
            print(f"  [场景记忆] 已保存: {path}")

    def load(self, path: str):
        """从JSON文件加载场景记忆"""
        if not os.path.exists(path):
            if self.verbose:
                print(f"  [场景记忆] 文件不存在，跳过加载: {path}")
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.scenes = {}
        for sid, sd_data in data.get("scenes", {}).items():
            sd = SceneData(sid, self.verbose)
            sd.from_dict(sd_data)
            self.scenes[sid] = sd

        cs_data = data.get("cross_scene", {})
        self.cross_scene_object_locations = defaultdict(
            lambda: defaultdict(int)
        )
        for obj_base, loc_counts in cs_data.items():
            if isinstance(loc_counts, dict):
                self.cross_scene_object_locations[obj_base] = defaultdict(int, loc_counts)
            else:
                self.cross_scene_object_locations[obj_base] = defaultdict(int)
        self.current_scene = data.get("current_scene")

        if self.verbose:
            print(f"  [场景记忆] 已加载: {len(self.scenes)}个场景")


class SceneData:
    """单个场景的数据"""

    def __init__(self, scene_id: str, verbose: bool = False):
        self.scene_id = scene_id
        self.verbose = verbose

        # 所有已知位置
        self.locations: Set[str] = set()

        # {位置: [物体名]} — 物体记忆
        self.location_objects: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # 可打开的容器 {容器名: 位置}
        self.openables: Dict[str, str] = {}

        # 工具位置 {工具名: 位置}
        self.tool_locations: Dict[str, str] = {}

        # 已探索位置
        self.explored_locations: Set[str] = set()

        # 标记为有目标的位置
        self.target_locations: Set[str] = set()

        # 标记为空的位置（去过但没找到目标）
        self.empty_locations: Set[str] = set()

        # 位置拓扑邻接
        self.location_adjacency: Dict[str, Set[str]] = defaultdict(set)

    def add_location(self, location: str):
        self.locations.add(location)

    def add_object_at(self, obj_name: str, location: str, confidence: int = 1):
        # 归一化
        obj_key = re.sub(r'\s*\d+$', '', obj_name.lower()).strip()
        loc_key = re.sub(r'\s*\d+$', '', location.lower()).strip()
        self.location_objects[loc_key][obj_key] += confidence

        # 同时记录正名（带数字的完整名）
        self.location_objects[location][obj_name] += confidence

        # 记录位置
        self.locations.add(location)

    def mark_openable(self, container: str, location: str):
        self.openables[container] = location

    def record_tool_location(self, tool: str, location: str):
        self.tool_locations[tool] = location

    def mark_target_location(self, location: str):
        self.target_locations.add(location)
        self.explored_locations.add(location)
        # 从空位置移除
        self.empty_locations.discard(location)

    def mark_empty_location(self, location: str):
        self.empty_locations.add(location)
        self.explored_locations.add(location)

    def get_object_locations(self, obj_name: str, top_k: int = 3) -> List[Tuple[str, float]]:
        obj_base = re.sub(r'\s*\d+$', '', obj_name.lower()).strip()
        candidates = []

        # 精确匹配
        for loc, objs in self.location_objects.items():
            for o, conf in objs.items():
                if o == obj_name or o == obj_base or obj_base in o or o in obj_base:
                    candidates.append((loc, conf))

        # 按置信度排序
        candidates.sort(key=lambda x: -x[1])
        total_conf = sum(c for _, c in candidates) or 1.0
        return [(loc, c / total_conf) for loc, c in candidates[:top_k]]

    def get_tool_location(self, tool: str) -> Optional[str]:
        return self.tool_locations.get(tool)

    def get_nearby_locations(self, location: str, radius: int = 1) -> List[str]:
        loc_base = re.sub(r'\s*\d+$', '', location.lower()).strip()
        nearby = list(self.location_adjacency.get(loc_base, set()))
        return nearby[:5]

    def get_known_openables(self) -> List[str]:
        return list(self.openables.keys())

    def get_all_object_memory(self) -> Dict[str, str]:
        """返回 {物体名: 位置} 扁平映射"""
        result = {}
        for loc, objs in self.location_objects.items():
            for obj, conf in objs.items():
                if conf > 0:
                    # 优先取置信度高的
                    if obj not in result or conf > self.location_objects[loc].get(result.get(obj, ""), 0):
                        # 简化：取第一个高置信度位置
                        if conf > 0:
                            result[obj] = loc
        return result

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "locations": list(self.locations),
            "location_objects": {k: dict(v) for k, v in self.location_objects.items()},
            "openables": self.openables,
            "tool_locations": self.tool_locations,
            "explored_locations": list(self.explored_locations),
            "target_locations": list(self.target_locations),
            "empty_locations": list(self.empty_locations),
        }

    def from_dict(self, data: dict):
        self.locations = set(data.get("locations", []))
        self.location_objects = defaultdict(
            lambda: defaultdict(int),
            {k: defaultdict(int, v) for k, v in data.get("location_objects", {}).items()}
        )
        self.openables = data.get("openables", {})
        self.tool_locations = data.get("tool_locations", {})
        self.explored_locations = set(data.get("explored_locations", []))
        self.target_locations = set(data.get("target_locations", []))
        self.empty_locations = set(data.get("empty_locations", []))

    def __repr__(self):
        return (f"SceneData({self.scene_id}, "
                f"locations={len(self.locations)}, "
                f"objects={sum(len(v) for v in self.location_objects.values())}, "
                f"explored={len(self.explored_locations)})")
