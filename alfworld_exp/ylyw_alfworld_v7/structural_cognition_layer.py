#!/usr/bin/env python3
"""
YLYW 结构化认知层 (L-1: Structural Cognition Layer)

哲学基础:
  《周易·系辞》:"易与天地准，故能弥纶天地之道。仰以观于天文，俯以察于地理，是故知幽明之故。"

  空间探索(L0)回答"往哪走"，结构化认知(L-1)回答"这个环境本身是否满足任务需求"。

  三个核心能力:
    1. 环境结构推断 — 从已探索位置类型，推断场景的整体结构
    2. 常识预期验证 — 将常识先验（plate→countertop/shelf）与环境发现进行对比
    3. 任务可行性判断 — 判断当前场景是否支持完成目标任务

  卦象编码 (将认知状态映射到64卦):
    睽卦䷥ — 经验与预期矛盾（常识说plate在shelf，但shelf没有plate）
    困卦䷮ — 围困不得出（所有候选位置探索完毕，无目标物体）
    蹇卦䷦ — 前路艰难（部分位置未探索，但类型不匹配任务需求）
    解卦䷧ — 困难解除（刚找到目标物体或工具）
    渐卦䷴ — 渐进探索（逐步排除低概率位置类型）
    既济卦䷾ — 完成在望（目标+工具都就位，只剩执行）
    未济卦䷿ — 事未成（任务所需环境结构缺失，无法完成）
    艮卦䷳ — 知止不殆（主动承认不可达，停止探索）

  在整体架构中的位置:
    L-1 (此层) ← 结构化认知，判断"能不能做"
    L0          ← 空间态势感知，决定"哪里去找"
    L1-L3       ← YLYW核心，执行"怎么拿"
"""

import sys
import os
import re
from typing import Dict, Set, List, Tuple, Optional
from enum import Enum

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

from ylyw_core import PriorManual


# ============================================================
# 认知状态 → 卦象映射
# ============================================================

class CognitionHexagram(Enum):
    """结构化认知卦象"""
    KUI = '睽'        # ䷥ 乖离 — 经验与现实矛盾
    KUN = '困'        # ䷮ 困境 — 所有位置探索完毕无目标
    JIAN = '蹇'       # ䷦ 艰难 — 部分未探索但类型不匹配
    XIE = '解'        # ䷧ 解除 — 刚找到关键物体/工具
    JIAN_GUA = '渐'   # ䷴ 渐进 — 逐步排除中
    JIJI = '既济'     # ䷾ 完成 — 目标+工具就位
    WEIJI = '未济'    # ䷿ 未成 — 环境不满足任务需求
    GEN = '艮'        # ䷳ 知止 — 主动停止，承认不可达


class StructuralCognitionLayer:
    """
    L-1 结构化认知层

    监视空间探索进展，对环境结构进行元认知推理。

    输入: 空间探索的累积数据
    输出: 认知结论 + 策略建议

    自学习: 每次探索后更新环境结构模型，修正信念
    """

    def __init__(self, manual: PriorManual = None):
        self.manual = manual or PriorManual(verbose=False)

        # 环境模型
        self.explored_types = set()       # 已探索的位置类型
        self.type_objects = {}            # {类型: 物体集合}
        self.found_target = False         # 是否找到目标物体
        self.found_tool = False           # 是否找到工具
        self.steps_since_discovery = 0    # 自上次发现新信息后的步数

        # 任务需求模型
        self.task_type = ""
        self.target_objects = set()
        self.target_tools = set()
        self.expected_locations = set()   # 常识先验中的目标位置类型

        # 推理结果
        self.current_hexagram = None
        self.conclusion = ""
        self.recommendation = ""          # 对上层(L0/序列生成)的建议
        self.task_feasible = True         # 任务是否可完成
        self.should_abort = False         # 是否应放弃

    def reset(self, task_type: str, target_objects: Set[str],
              target_tools: Set[str], expected_locations: Set[str]):
        """重置认知状态"""
        self.explored_types = set()
        self.type_objects = {}
        self.found_target = False
        self.found_tool = False
        self.steps_since_discovery = 0

        self.task_type = task_type
        self.target_objects = target_objects
        self.target_tools = target_tools
        self.expected_locations = expected_locations

        self.current_hexagram = None
        self.conclusion = "任务初始化"
        self.recommendation = ""
        self.task_feasible = True
        self.should_abort = False

    def update(self, location_type: str, objects_found: Set[str],
               total_types_explored: int, total_types_available: int,
               current_phase: int) -> Tuple[str, str, bool]:
        """
        每次探索后更新认知状态

        Args:
            location_type: 刚访问的位置类型 (bed/desk/shelf...)
            objects_found: 在该位置发现的物体名集合
            total_types_explored: 已探索的位置类型总数
            total_types_available: 场景中可用的位置类型总数
            current_phase: 当前 subgoal phase

        Returns:
            (conclusion, recommendation, should_abort)
        """
        # 更新环境模型
        self.explored_types.add(location_type)
        if location_type not in self.type_objects:
            self.type_objects[location_type] = set()
        self.type_objects[location_type] |= objects_found

        # 检查目标物体和工具
        for obj in objects_found:
            obj_clean = re.sub(r'\s*\d+$', '', obj)
            if any(t in obj_clean for t in self.target_objects):
                self.found_target = True
            if any(t in obj_clean for t in self.target_tools):
                self.found_tool = True

        if self.found_target or self.found_tool:
            self.steps_since_discovery = 0
        else:
            self.steps_since_discovery += 1

        # --- 推理 ---

        expected_in_scene = self.expected_locations & self.explored_types
        expected_exhausted = (expected_in_scene and
                              all(loc in self.explored_types for loc in expected_in_scene))

        # all_explored: visited 类型数 >= total 的 85% 且 步数停滞 >= 12
        all_explored = (total_types_explored >= max(1, int(total_types_available * 0.85))
                        and self.steps_since_discovery >= 12)

        # 推理规则
        if self.found_target and self.found_tool:
            # 既济卦䷾ — 所有要素就位
            hexa = CognitionHexagram.JIJI
            self.conclusion = "目标物体和工具都已就位，只需执行剩余动作"
            self.recommendation = "skip_explore"

        elif self.found_target:
            if not self.found_tool and self.steps_since_discovery > 3:
                # 解卦䷧ — 找到目标但找不到工具
                hexa = CognitionHexagram.XIE
                self.conclusion = f"已找到目标物体，但工具({self.target_tools})尚未发现"
                self.recommendation = "search_tool"
            else:
                hexa = CognitionHexagram.JIJI
                self.conclusion = "目标已找到，继续搜索工具"
                self.recommendation = "continue_search"

        elif expected_exhausted and not self.found_target:
            if all_explored:
                # 艮卦䷳ — 全探索完毕，承认不可达
                hexa = CognitionHexagram.GEN
                self.should_abort = True
                self.task_feasible = False
                self.conclusion = (f"所有位置已探索，目标物体({self.target_objects})"
                                   f"不在场景中。任务不可完成。")
                self.recommendation = "abort"
            else:
                # 困卦䷮ — 常识位置探索完毕，仍有希望
                hexa = CognitionHexagram.KUN
                self.conclusion = (f"常识预期位置({expected_in_scene})已探索完毕，"
                                   f"目标物体不在其中，但仍有其他位置待探索")
                self.recommendation = "expand_search"

        elif expected_in_scene and not self.found_target:
            # 渐卦䷴ — 逐步排除常见位置
            hexa = CognitionHexagram.JIAN_GUA
            remaining = expected_in_scene - self.explored_types
            self.conclusion = f"常识位置中还有 {remaining} 待探索，继续逐步检查"
            self.recommendation = "continue_expected"

        elif not expected_in_scene and not self.found_target:
            # 睽卦䷥ — 经验与现实矛盾！
            hexa = CognitionHexagram.KUI
            self.conclusion = (f"目标物体({self.target_objects})的常识位置"
                               f"({self.expected_locations})都不在场景中——"
                               f"需要从非典型位置搜索")
            self.recommendation = "search_anywhere"

        elif not self.found_target and all_explored:
            # 未济卦䷿ — 全探索完毕但不可完成
            hexa = CognitionHexagram.WEIJI
            self.should_abort = True
            self.task_feasible = False
            self.conclusion = "所有位置已探索，任务所需物体不在场景中"
            self.recommendation = "abort"

        else:
            hexa = CognitionHexagram.JIAN
            self.conclusion = "继续探索中..."
            self.recommendation = "continue_search"

        self.current_hexagram = hexa
        return self.conclusion, self.recommendation, self.should_abort

    def get_cognition_yaw(self) -> List[float]:
        """
        将当前认知状态编码为六爻向量(0-1)

        初爻: 目标发现程度 (0=未发现, 1=已发现)
        二爻: 工具发现程度
        三爻: 常识匹配度 (常识位置中多少在场景中)
        四爻: 探索完成度 (已探索/总位置类型数)
        五爻: 信息增益率 (最近有新发现=高, 停滞=低)
        上爻: 可行性 (1=可行, 0=不可行)
        """
        yaw = [0.0] * 6

        yaw[0] = 1.0 if self.found_target else 0.0
        yaw[1] = 1.0 if self.found_tool else 0.0

        matching = self.expected_locations & self.explored_types if self.expected_locations else set()
        yaw[2] = len(matching) / max(1, len(self.expected_locations)) if self.expected_locations else 0.5

        yaw[3] = min(1.0, len(self.explored_types) / 8)  # 8 = typical number of types

        yaw[4] = max(0.0, 1.0 - self.steps_since_discovery / 10)

        yaw[5] = 1.0 if self.task_feasible else 0.0

        return yaw

    def get_status_report(self) -> Dict:
        """生成结构化认知状态报告（用于论文分析）"""
        return {
            'hexagram': self.current_hexagram.value if self.current_hexagram else 'N/A',
            'conclusion': self.conclusion,
            'recommendation': self.recommendation,
            'task_feasible': self.task_feasible,
            'should_abort': self.should_abort,
            'explored_types': list(self.explored_types),
            'expected_locations': list(self.expected_locations),
            'found_target': self.found_target,
            'found_tool': self.found_tool,
            'cognition_yaw': self.get_cognition_yaw(),
        }


# ============================================================
# 集成到 NestedSpatialExplorer
# ============================================================

def integrate_with_nested_spatial():
    """
    将 L-1 认知层集成到 NestedSpatialExplorer 中的方法:
    在 select_explore_target() 中，先查询 L-1 的 recommendation。
    如果 recommendation == 'abort' → 放弃探索，快速退出
    如果 recommendation == 'search_anywhere' → 忽略常识先验，均匀搜索
    """
    pass


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    from llm_semantic_guide import LLMSemanticGuide

    guide = LLMSemanticGuide()

    # Test 1: Game 6 (look_at_obj_in_light — 能找到 target+tool)
    print("=== Test 1: Game 6 scene (mug in desk, desklamp in desk) ===")
    cog = StructuralCognitionLayer()
    cog.reset('look_at_obj_in_light',
              target_objects={'mug'},
              target_tools={'desklamp'},
              expected_locations={'countertop', 'shelf', 'desk', 'coffeemachine'})

    # 模拟探索: desk 1(有 desklamp), desk 2(有 mug)
    report = cog.update('desk', {'creditcard', 'laptop', 'desklamp'},
                       1, 7, 0)
    print(f"  Step1 (desk, has desklamp): {cog.conclusion}")
    print(f"    hexagram={cog.current_hexagram.value}, should_abort={cog.should_abort}")

    report = cog.update('desk', {'alarmclock', 'mug', 'book'},
                       2, 7, 1)
    print(f"  Step2 (desk2, has mug): {cog.conclusion}")
    print(f"    hexagram={cog.current_hexagram.value}, should_abort={cog.should_abort}")
    print(f"    yaw={[f'{y:.2f}' for y in cog.get_cognition_yaw()]}")
    print()

    # Test 2: Game 1 (plate not in room — 应该触发 睽卦/艮卦)
    print("=== Test 2: Game 1 scene (plate not in this room) ===")
    cog2 = StructuralCognitionLayer()
    cog2.reset('pick_clean_then_place_in_recep',
               target_objects={'plate'},
               target_tools={'sinkbasin'},
               expected_locations={'countertop', 'cabinet', 'shelf', 'table'})

    scene_types = ['shelf', 'shelf', 'bed', 'desk', 'desk',
                   'drawer', 'drawer', 'garbagecan', 'laundryhamper', 'safe']
    for i, loc_type in enumerate(scene_types):
        report = cog2.update(loc_type, {'pen', 'book'}, i+1, len(set(scene_types)), 0)
        if i in [1, 4, 9]:
            print(f"  Step{i} ({loc_type}): [{cog2.current_hexagram.value}] {cog2.conclusion[:60]}")
            print(f"    recommendation={cog2.recommendation}, should_abort={cog2.should_abort}")

    print(f"  Final: [{cog2.current_hexagram.value}] {cog2.conclusion}")
    print(f"  should_abort={cog2.should_abort}, feasible={cog2.task_feasible}")
    print()

    # Test 3: Game 5 (soapbar, garbagecan in scene but no soapbar there)
    print("=== Test 3: Game 5 scene (soapbar hints → garbagecan is in scene) ===")
    cog3 = StructuralCognitionLayer()
    cog3.reset('pick_two_obj_and_place',
               target_objects={'soapbar'},
               target_tools=set(),
               expected_locations={'garbagecan', 'countertop', 'sinkbasin', 'cabinet'})

    scene_types3 = ['garbagecan', 'bed', 'desk', 'desk', 'drawer',
                    'drawer', 'drawer', 'drawer', 'drawer', 'drawer',
                    'laundryhamper', 'safe', 'shelf']
    for i, loc_type in enumerate(scene_types3):
        cog3.update(loc_type, {'pen', 'book'}, i+1, len(set(scene_types3)), 0)

    print(f"  Final: [{cog3.current_hexagram.value}] {cog3.conclusion}")
    print(f"  should_abort={cog3.should_abort}, feasible={cog3.task_feasible}")
    print(f"  yaw={[f'{y:.2f}' for y in cog3.get_cognition_yaw()]}")
    print()

    print("=== Reports ===")
    print(f"  Test2: {cog2.get_status_report()['hexagram']} → {cog2.conclusion}")
    print(f"  Test3: {cog3.get_status_report()['hexagram']} → {cog3.conclusion}")
