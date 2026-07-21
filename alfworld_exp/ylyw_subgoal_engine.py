#!/usr/bin/env python3
"""
YLYW 子目标引擎 — 用 YLYW 六爻架构做任务分解与子目标跟踪

核心思想：
  汉语任务描述 → HanziEngine → 任务六爻向量 T
  T → "太极生两仪"递归分解 → 子目标六爻序列 [S₁, S₂, ..., Sₙ]
  每个子目标 Sᵢ = 任务卦象在阶段 i 的投影
  子目标间转换 = 差距向量 D = Sᵢ - C（C=当前场景六爻）
  五行生克驱动子目标间关系

与 V17 的集成：
  SubgoalEngine.decompose(task_yao, task_type) → subgoal_list
  SubgoalEngine.track(scene_yao, holding, processed) → current_subgoal_idx
  Agent._decide_intent() 中调用 engine 获取 current_subgoal
"""

import sys, os, re, math
from typing import List, Dict, Optional, Tuple
import numpy as np

# ── 路径 ──
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'language'))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, '..'))

from hanzi_engine import HanziEngine
from ylyw_action_primitives import wuxing_shengke

# ═══════════════════════════════════════════════════
# 1. 卦象常量
# ═══════════════════════════════════════════════════

# 子目标类型 → 阶段卦象原型（六爻向量）
# 每个子目标 = 一个六爻模式，不是硬编码规则
SUBGOAL_PROTOTYPES = {
    "探索":    [0.30, 0.05, 0.05, 0.05, 0.50, 0.05],
    "拿取":    [0.50, 0.90, 0.30, 0.50, 0.50, 0.10],
    "去预处理":[0.70, 0.50, 0.10, 0.30, 0.70, 0.10],
    "预处理":  [0.50, 0.50, 0.95, 0.80, 0.40, 0.30],
    "去目标":  [0.70, 0.50, 0.40, 0.30, 0.95, 0.20],
    "放置":    [0.50, 0.50, 0.60, 0.50, 0.80, 0.80],
    "完成":    [0.50, 0.05, 0.50, 0.40, 0.60, 0.95],
    "探索拿取":[0.40, 0.70, 0.20, 0.30, 0.40, 0.10],
    "取第二件":[0.40, 0.70, 0.30, 0.30, 0.40, 0.15],
    "拿一个":  [0.40, 0.80, 0.20, 0.30, 0.40, 0.10],
}

# 任务类型 → 子目标序列种子
# 用"太极生两仪"从这些种子投影到任务六爻空间
TASK_SUBGOAL_SEED = {
    "pick_and_place_simple":         ["拿取", "去目标", "放置", "完成"],
    "pick_clean_then_place_in_recep":["拿取", "去预处理", "预处理", "去目标", "放置", "完成"],
    "pick_heat_then_place_in_recep": ["拿取", "去预处理", "预处理", "去目标", "放置", "完成"],
    "pick_cool_then_place_in_recep": ["拿取", "去预处理", "预处理", "去目标", "放置", "完成"],
    "pick_two_obj_and_place":        ["拿取", "去目标", "放置", "取第二件", "去目标", "放置", "完成"],
    "look_at_obj_in_light":          ["探索", "去目标", "预处理", "完成"],
}

# ═══════════════════════════════════════════════════
# 2. 核心子目标引擎
# ═══════════════════════════════════════════════════

class SubgoalEngine:
    """
    YLYW 子目标引擎 — 纯六爻框架

    核心运算：
      1. decompose(task_yao) → [subgoal_yao1, subgoal_yao2, ...]
         用"太极生两仪"方式递归分解任务六爻
      2. track(scene_yao, holding, processed) → current_idx
         用状态检测判断进度
    """

    def __init__(self, verbose=False):
        self.verbose = verbose
        self._engine = HanziEngine(verbose=False)

        self.task_yao = [0.5]*6
        self.task_type = ""
        self.subgoal_yaos = []
        self.subgoal_labels = []
        self.current_idx = 0
        self.current_label = ""
        self._taken_count = 0

        # ═══ 反馈机制 ═══
        self._feedback_buffer = []       # 执行反馈历史
        self._consecutive_fails = 0      # 当前子目标连续失败次数
        self._max_fails_for_label = {}   # 每个子目标标签的历史失败容忍度

        # ═══ 知己学习（跨子目标/跨步） ═══
        self._known_failed_actions = []  # 已确认失败的动作
        self._label_skip_count = {}      # 同一标签被跳过次数
        self._completion_history = []    # 完成检测历史（用于判断假完成）

        # ═══ 精细化反馈状态 ═══
        self._failed_locs = {}           # {位置: 失败次数} 同位置不可take计数
        self._failed_devices = set()     # 已确认不可用的设备（sinkbasin/microwave等）
        self._placed_locations = []      # 已尝试放置的位置
        self._failed_place_attempts = 0  # 放置失败次数
        self._preproc_attempted = False  # 是否已尝试过预处理

    # ── 公共接口 ──

    def reset(self, task_type: str, task_yao: list = None, task_cn: str = ""):
        """重置为新的任务，进行太极生两仪分解"""
        self.task_type = task_type
        if task_yao:
            self.task_yao = task_yao
        elif task_cn:
            result = self._engine.sentence(task_cn)
            self.task_yao = result['yao_vector']
        else:
            self.task_yao = [0.5]*6

        self.subgoal_yaos, self.subgoal_labels = self._taiji_decompose(
            self.task_yao, task_type
        )

        self.current_idx = 0
        self.current_label = self.subgoal_labels[0] if self.subgoal_labels else "探索"
        self._taken_count = 0

        if self.verbose:
            print(f"  [子目标引擎] 任务卦={[round(y,2) for y in self.task_yao]}")
            print(f"  [子目标引擎] 分解 → {len(self.subgoal_yaos)} 阶段")
            for i, (lbl, yao) in enumerate(zip(self.subgoal_labels, self.subgoal_yaos)):
                print(f"    [{i}] {lbl}: {[round(y,2) for y in yao]}")

    def track(self, scene_yao: list, holding, processed: bool,
              taken_count: int = 0, scene_obs: str = "") -> Tuple[int, str, list]:
        """
        跟踪当前进度，返回 (current_idx, current_label, subgoal_yao)

        用场景状态检测子目标完成，自动切换到下一个。
        scene_obs 用于 look_at_obj_in_light 等场景感知完成检测。
        """
        if taken_count > 0:
            self._taken_count = max(self._taken_count, taken_count)

        if not self.subgoal_yaos:
            return 0, "探索", SUBGOAL_PROTOTYPES["探索"]

        # ═══ 状态驱动的子目标完成检测 ═══
        # 用 holding/processed/taken_count/scene_obs 做主要判断，
        # 六爻差距做辅助信号
        label = self.subgoal_labels[self.current_idx]
        completed = self._check_complete(
            label, holding, processed, self._taken_count, scene_obs
        )

        if completed:
            if self.current_idx < len(self.subgoal_yaos) - 1:
                self.current_idx += 1
                self.current_label = self.subgoal_labels[self.current_idx]
                if self.verbose:
                    print(f"  [子目标引擎] ✅ {label} 完成 → [{self.current_idx}]{self.current_label}")
            else:
                if self.verbose:
                    print(f"  [子目标引擎] ✅ 全部子目标完成")

        return (self.current_idx,
                self.current_label,
                self.subgoal_yaos[self.current_idx])

    def get_current_subgoal(self) -> Tuple[str, list]:
        """获取当前子目标的 (label, yao)"""
        if not self.subgoal_labels:
            return "探索", SUBGOAL_PROTOTYPES["探索"]
        return (self.subgoal_labels[self.current_idx],
                self.subgoal_yaos[self.current_idx])

    def get_next_subgoal(self) -> Optional[Tuple[str, list]]:
        if self.current_idx + 1 < len(self.subgoal_labels):
            return (self.subgoal_labels[self.current_idx + 1],
                    self.subgoal_yaos[self.current_idx + 1])
        return None

    def get_subgoal_count(self) -> int:
        return len(self.subgoal_labels)

    def get_progress(self) -> float:
        if not self.subgoal_yaos:
            return 0.0
        return self.current_idx / max(len(self.subgoal_yaos) - 1, 1)

    def get_current_intent(self) -> str:
        """
        将当前子目标映射到 V17 的意图词（兼容现有 _intent_to_action）
        映射关系：
          探索/探索拿取/拿一个 → "goto探索"
          拿取/取第二件 → "拿取"
          去预处理 → "去预处理"
          预处理 → "放入设备"
          去目标 → "去目标"
          放置 → "放置"
          完成 → "完成"
        """
        label = self.current_label
        if label in ("探索", "探索拿取", "拿一个"):
            return "goto探索"
        if label in ("拿取", "取第二件"):
            return "拿取"
        if label == "去预处理":
            return "去预处理"
        if label == "预处理":
            return "放入设备"
        if label == "去目标":
            return "去目标"
        if label == "放置":
            return "放置"
        if label == "完成":
            return "完成"
        return "goto探索"

    # ── 太极生两仪分解 ──

    def _taiji_decompose(self, task_yao: list, task_type: str
                         ) -> Tuple[List[list], List[str]]:
        """
        核心："太极生两仪，两仪生四象，四象生八卦"

        步骤：
          1. 取任务类型对应的子目标种子序列
          2. 每个种子映射到原型六爻
          3. 任务六爻 T 投影到各原型方向 → 阶段卦象
          4. 生克平滑相邻阶段
        """
        seeds = TASK_SUBGOAL_SEED.get(task_type,
                                      ["拿取", "去目标", "放置", "完成"])
        n = len(seeds)

        prototype_yaos = []
        for label in seeds:
            if label in SUBGOAL_PROTOTYPES:
                prototype_yaos.append(SUBGOAL_PROTOTYPES[label][:])
            else:
                prototype_yaos.append([0.5]*6)

        subgoal_yaos = []
        t_arr = np.array(task_yao)
        norm_t = np.linalg.norm(t_arr)

        for i, proto in enumerate(prototype_yaos):
            p_arr = np.array(proto)
            norm_p = np.linalg.norm(p_arr)

            # 余弦相似度
            sim = np.dot(t_arr, p_arr) / (norm_p * norm_t + 1e-8)

            # 混合：60% 任务卦象 + 40% 原型 × 相似度
            mix = 0.6 * t_arr + 0.4 * p_arr * sim

            # 阶段调制（前段偏持有，后段偏完成）
            phase = (i + 1) / n
            modulated = [
                max(0.05, min(0.95,
                    mix[0] * (0.8 + 0.2 * phase))),    # 位置动
                max(0.05, min(0.95,
                    mix[1] * (0.7 + 0.3 * (1-phase)))), # 持有
                max(0.05, min(0.95,
                    mix[2] * (0.5 + 0.5 * phase))),     # 处理
                max(0.05, min(0.95, mix[3])),            # 环境
                max(0.05, min(0.95,
                    mix[4] * (0.6 + 0.4 * phase))),     # 目标
                max(0.05, min(0.95,
                    mix[5] * (0.3 + 0.7 * phase))),     # 完成
            ]

            # 生克平滑
            if i > 0:
                prev = subgoal_yaos[-1]
                sk = wuxing_shengke(
                    ''.join('1' if v > 0.5 else '0' for v in prev),
                    ''.join('1' if v > 0.5 else '0' for v in modulated)
                )
                modulated = [max(0.05, min(0.95, v + sk * 0.05))
                             for v in modulated]

            subgoal_yaos.append(modulated)

        return subgoal_yaos, seeds

    # ═══════════════════════════════════════════════════
    # 反馈机制 + 知己学习
    # ═══════════════════════════════════════════════════

    def feed_feedback(self, action: str, obs: str, admissible: list,
                      current_location: str = ""):
        """
        精细化反馈机制。

        分析三种失败模式：
          ① 同位置类型多次可拿不可取 → 跳过
          ② 预处理设备不可用 → 标记跳过
          ③ 放置了但没触发 won → 换位置
        """
        obs_lower = obs.lower() if obs else ""
        action_lower = action.lower() if action else ""
        loc_key = current_location or ""

        # ── 检测失败模式 ──
        nothing_happens = 'nothing happens' in obs_lower or 'you can' in obs_lower
        is_go_to = action.startswith('go to ')
        is_take = action.startswith('take ')
        is_put = action.startswith('put ') or action.startswith('move ')
        is_open = action.startswith('open ')
        is_use = action.startswith('use ')
        is_exam = action.startswith('examine ') or action == 'look'

        # ═══ 模式①：同位置类型反复不可take ═══
        if self.current_label in ("拿取", "探索拿取", "取第二件", "拿一个"):
            if is_go_to:
                target_loc = action[6:].strip()
                loc_base = target_loc.split(' ')[0]
                has_take = any(c.startswith('take ') for c in (admissible or []))
                if not has_take:
                    self._failed_locs[target_loc] = self._failed_locs.get(target_loc, 0) + 1
                    if self._failed_locs[target_loc] >= 2:
                        # 某位置去了2次还不可take → 标记不可用
                        self._known_failed_actions.append(f'skip_loc:{target_loc}')
                        if self.verbose:
                            print(f"  [子目标反馈] 🚫 跳过{target_loc}({self._failed_locs[target_loc]}次无可take)")
                        self._consecutive_fails += 1
                        return "skip_loc"
            elif is_open:
                # open 后检查是否出现了 take 命令
                container = action[5:].strip()
                has_take_now = any(c.startswith('take ') for c in (admissible or []))
                if nothing_happens:
                    # open 了但 nothing happens（可能已经 open 过）
                    self._known_failed_actions.append(f'open_fail:{container}')
                    if self.verbose:
                        print(f"  [子目标反馈] 🚫 open {container} 无效")
            elif is_take and nothing_happens:
                # take 失败（物体不在预期容器中）
                self._known_failed_actions.append(f'take_fail:{action}')
                self._consecutive_fails += 1
                if self.verbose:
                    print(f"  [子目标反馈] ❌ take失败: {action}")
                return "fail_take"

        # ═══ 模式②：预处理设备不可用 ═══
        if self.current_label in ("去预处理", "预处理", "放入设备"):
            if is_use and nothing_happens:
                device = action[4:].strip()
                self._failed_devices.add(device)
                self._preproc_attempted = True
                self._consecutive_fails += 1
                if self.verbose:
                    print(f"  [子目标反馈] ❌ 预处理设备{device}不可用")
                return "fail_device"

        # ═══ 模式③：放置失败（放置了但没won） ═══
        if self.current_label in ("放置", "去目标"):
            if is_put and not nothing_happens:
                # 成功 put 了
                self._placed_locations.append(loc_key)
                self._failed_place_attempts += 1
            elif is_go_to and loc_key:
                target = action[6:].strip()
                target_key = target.lower().strip()
                # 如果已在这个位置放过了但没 won → 标记重复
                if target_key in self._placed_locations:
                    if self._failed_place_attempts >= 2:
                        self._known_failed_actions.append(f'place_again:{target_key}')
                        if self.verbose:
                            print(f"  [子目标反馈] 🚫 已在{target_key}放置过，跳过")
                        self._consecutive_fails += 1
                        return "skip_place"

        # ── 通用失败计数器 ──
        if nothing_happens or (is_go_to and is_take and
                               not any(c.startswith('take ') for c in (admissible or []))):
            self._consecutive_fails += 1
        else:
            # 成功降低连续失败计数
            self._consecutive_fails = max(0, self._consecutive_fails - 1)

        # ── 记录反馈 ──
        self._feedback_buffer.append({
            'action': action,
            'obs': obs_lower[:100],
            'label': self.current_label,
            'idx': self.current_idx,
            'is_fail': nothing_happens,
            'loc': loc_key,
        })

        return "ok"

    def reset_feedback(self):
        """重置反馈状态（跨局时由上层调用）"""
        self._feedback_buffer = []
        self._consecutive_fails = 0
        self._known_failed_actions = []
        self._failed_locs = {}
        self._failed_devices = set()
        self._placed_locations = []
        self._failed_place_attempts = 0
        self._preproc_attempted = False

    def is_location_exhausted(self, loc: str) -> bool:
        """位置是否应该跳过（不可take或已失败过）"""
        for f in self._known_failed_actions:
            if f.startswith('skip_loc:') and loc in f:
                return True
        return False

    def is_device_failed(self, device: str) -> bool:
        """设备是否已被标记不可用"""
        return device in self._failed_devices

    def is_place_repeated(self, loc: str) -> bool:
        """是否已在该位置放置过但没触发won"""
        return loc in self._placed_locations and self._failed_place_attempts >= 2

    def feed_self_knowledge(self):
        """
        知己学习：在同一局内跨子目标复用失败信息。
        """
        pass  # 信息集中在 _failed_locs / _failed_devices 中，直接被上层使用

    def is_stuck(self) -> bool:
        """当前子目标是否卡住"""
        return self._consecutive_fails >= 3

    def get_stuck_info(self) -> dict:
        """卡住信息"""
        return {
            'label': self.current_label,
            'consecutive_fails': self._consecutive_fails,
            'failed_locs': dict(list(self._failed_locs.items())[-5:]),
            'failed_devices': list(self._failed_devices)[-3:],
            'placed_locations': self._placed_locations[-3:],
            'buffer': self._feedback_buffer[-3:] if self._feedback_buffer else [],
        }

    # ── 完成检测 ──

    def _check_complete(self, label: str, holding, processed: bool,
                        taken_count: int, scene_obs: str = "") -> bool:
        """
        状态驱动的完成检测（含反馈感知）。

        反馈感知：连续失败 >= 3 次时阻止完成切换。
        """
        if self._consecutive_fails >= 3:
            if self.verbose:
                print(f"  [子目标检测] 卡住中({self._consecutive_fails}次失败)，阻止{label}完成")
            return False

        if label in ("拿取", "探索拿取", "拿一个", "取第二件"):
            return holding is not None
        if label in ("去预处理", "预处理", "放入设备"):
            return processed
        if label == "去目标":
            return holding is not None
        if label == "放置":
            return holding is None and taken_count >= 1
        if label == "完成":
            recent_fb = self._feedback_buffer[-5:] if self._feedback_buffer else []
            stale_examine = sum(1 for f in recent_fb
                               if f['action'].startswith('examine ') or f['action'] == 'look')
            if stale_examine >= 3:
                self._completion_history.append({'label': '完成', 'false': True, 'stale': stale_examine})
                if self.verbose:
                    print(f"  [子目标检测] 假完成: {stale_examine}次examine/look")
                return False
            return True
        if label == "探索":
            if self.task_type == "look_at_obj_in_light" and scene_obs:
                obs_lower = scene_obs.lower() if scene_obs else ""
                if 'desklamp' in obs_lower or 'lamp -' in obs_lower or \
                   'lamp,' in obs_lower or 'lamp.' in obs_lower:
                    return True
            return False
        return True


# ═══════════════════════════════════════════════════
# 3. 汉语意图解析器
# ═══════════════════════════════════════════════════

class ChineseIntentParser:
    """
    从中文任务描述中提取子目标链。
    动词→卦象映射，不是规则 POS 标注。
    """

    VERB_TO_SUBGOAL = {
        "拿": "拿取", "取": "拿取", "抓": "拿取", "捡": "拿取",
        "找": "探索", "寻": "探索", "搜": "探索",
        "洗": "预处理", "刷": "预处理", "冲": "预处理",
        "热": "预处理", "加": "预处理", "煮": "预处理",
        "冷": "预处理", "冰": "预处理", "冻": "预处理",
        "放": "放置", "摆": "放置", "搁": "放置", "移": "放置",
        "丢": "放置", "扔": "放置", "倒": "放置",
        "看": "完成", "查": "完成", "检": "完成", "观": "完成",
        "到": "去目标", "去": "去目标", "走": "探索",
        "开": "探索", "打": "探索", "翻": "探索",
    }

    def __init__(self, engine=None):
        self._engine = engine or HanziEngine(verbose=False)

    def parse(self, task_cn: str) -> List[str]:
        """从中文任务描述解析出子目标序列。"""
        if not task_cn:
            return []
        verbs = []
        for char in task_cn:
            if char in self.VERB_TO_SUBGOAL:
                sg = self.VERB_TO_SUBGOAL[char]
                if not verbs or verbs[-1] != sg:
                    verbs.append(sg)
        if not verbs:
            result = self._engine.sentence(task_cn)
            yao = result['yao_vector']
            verbs = self._match_by_yao(yao)
        return verbs

    def _match_by_yao(self, yao: list) -> List[str]:
        best_label = "探索"
        best_dist = float('inf')
        for label, proto in SUBGOAL_PROTOTYPES.items():
            dist = sum((a - b) ** 2 for a, b in zip(yao, proto))
            if dist < best_dist:
                best_dist = dist
                best_label = label
        return [best_label]


# ═══════════════════════════════════════════════════
# 4. 增强注意力
# ═══════════════════════════════════════════════════

class EnhancedAttention:
    """
    联合子目标状态 + 知识库 + 空间的注意力模块。
    """

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.object_kb = {
            'plate': ['countertop', 'cabinet', 'diningtable', 'sinkbasin'],
            'bowl': ['countertop', 'cabinet', 'diningtable', 'sinkbasin'],
            'mug': ['countertop', 'coffeemachine', 'desk', 'shelf', 'cabinet'],
            'soapbar': ['countertop', 'sinkbasin', 'bathtubbasin', 'toilet'],
            'soapbottle': ['countertop', 'sinkbasin', 'cabinet'],
            'apple': ['countertop', 'fridge', 'diningtable'],
            'tomato': ['countertop', 'fridge', 'diningtable'],
            'potato': ['countertop', 'fridge', 'sinkbasin'],
            'egg': ['countertop', 'fridge'],
            'bread': ['countertop', 'diningtable'],
            'pillow': ['bed', 'sofa'],
            'book': ['desk', 'shelf', 'bed', 'sidetable', 'coffeetable'],
            'pencil': ['desk', 'drawer', 'shelf'],
            'pen': ['desk', 'drawer', 'shelf'],
            'keychain': ['desk', 'sidetable', 'drawer', 'dresser'],
            'creditcard': ['desk', 'sidetable', 'drawer', 'dresser'],
            'remotecontrol': ['coffeetable', 'sidetable', 'sofa'],
            'cellphone': ['desk', 'sidetable', 'bed'],
            'towel': ['towelholder', 'countertop', 'bathtubbasin'],
            'toiletpaper': ['toiletpaperhanger', 'cabinet', 'countertop'],
            'vase': ['shelf', 'desk', 'sidetable', 'coffeetable'],
            'statue': ['shelf', 'desk', 'sidetable'],
            'watch': ['desk', 'sidetable', 'dresser', 'shelf'],
            'alarmclock': ['desk', 'sidetable', 'shelf', 'dresser'],
        }

    # ── 容器类型列表（可被 open 的位置）──
    CONTAINER_TYPES = frozenset(['cabinet', 'drawer', 'fridge', 'microwave',
                                  'safe', 'dresser', 'shelf'])
    # ── 开放优先的位置类型（open 后大概率有物体）──
    HIGH_YIELD_CONTAINERS = frozenset(['cabinet', 'drawer', 'fridge', 'safe'])
    # ── 非容器位置（open 命令不会出现）──
    OPENABLE_LOCATIONS = frozenset(['cabinet', 'drawer', 'fridge', 'microwave',
                                     'safe', 'dresser', 'shelf',
                                     'coffeemaker', 'toaster', 'garbagecan'])

    def rank_locations(self, available_locs: List[str], obj_en: str,
                       subgoal_label: str, visited: set,
                       scene_yao: list = None,
                       opened_containers: set = None) -> List[Tuple[str, float]]:
        """
        根据子目标状态和知识库对可用位置排序。

        增强：
          - 在拿取阶段，优先推荐有容器但未 open 的位置（open 后可能找到物体）
          - 知识库优先匹配物体常见位置
          - 已访问位置类型降权，避免循环
          - opened_containers 参数辅助判断哪些容器已开过
        """
        if not available_locs:
            return []

        if opened_containers is None:
            opened_containers = set()

        scores = []
        for loc in available_locs:
            score = 0.5
            loc_name = loc.replace('go to ', '').strip().lower()
            loc_base = loc_name.split(' ')[0] if ' ' in loc_name else loc_name

            # ═══ 1. 子目标状态调制（最高优先级） ═══
            take_labels = {"拿取", "探索拿取", "取第二件", "拿一个", "探索"}
            if subgoal_label in take_labels:
                # 拿取阶段：区分容器 vs 非容器
                if loc_base in self.CONTAINER_TYPES:
                    # 容器位置：未 open 加分，已 open 但没找到物体减分
                    if loc_name not in opened_containers and loc_name not in visited:
                        score += 0.60  # 高优先级：未访问的容器
                    elif loc_name not in opened_containers:
                        score += 0.35  # 访问过但没 open 的容器
                    elif loc_name in opened_containers:
                        score -= 0.10  # 已 open 过的容器不再优先
                    # HIGH_YIELD 再额外加分
                    if loc_base in self.HIGH_YIELD_CONTAINERS:
                        score += 0.10
                else:
                    # 非容器位置（open 命令不会出现）
                    if loc_name not in visited:
                        score += 0.20
                    # countertop/desk 等非容器但可能有物体的位置
                    if loc_base in ('countertop', 'desk', 'sidetable',
                                    'coffeetable', 'bed', 'sofa',
                                    'sinkbasin', 'bathtubbasin',
                                    'diningtable', 'toilet', 'towelholder'):
                        if loc_name not in visited:
                            score += 0.15
            elif subgoal_label in ("去目标", "放置"):
                # 放置阶段：目标类型的容器优先
                if loc_base in self.CONTAINER_TYPES:
                    score += 0.10

            # ═══ 2. 知识库匹配 ═══
            if obj_en and obj_en in self.object_kb:
                for known_loc in self.object_kb[obj_en]:
                    if known_loc in loc_name or known_loc == loc_base:
                        score += 0.30
                        break

            # ═══ 3. 避免同一位置类型循环 ═══
            visited_bases = set(v.split(' ')[0] for v in visited if ' ' in v)
            if loc_base in visited_bases and loc_name in visited:
                score -= 0.12  # 访问过的同类型位置降权

            # ═══ 4. 未访问加分 ═══
            if loc_name not in visited:
                score += 0.15

            scores.append((loc, max(0.0, min(1.0, score))))

        scores.sort(key=lambda x: -x[1])
        return scores

    def get_explore_strategy(self, subgoal_label: str, obj_en: str,
                              visited: set, opened_containers: set) -> str:
        """
        生成探索策略提示词，传递给空间八卦层使用。

        返回: 探索策略描述字符串
        """
        take_labels = {"拿取", "探索拿取", "取第二件", "拿一个", "探索"}
        if subgoal_label not in take_labels:
            return "default"

        # 计算未 open 的容器数量
        unopened_containers = sum(
            1 for loc in visited if loc.split(' ')[0] in self.OPENABLE_LOCATIONS
            and loc not in opened_containers
        )

        if unopened_containers > 0:
            return "open_first"
        if obj_en and obj_en in self.object_kb:
            known = self.object_kb[obj_en]
            if known:
                return f"search_in:{','.join(known)}"
        return "explore_new"


# ═══════════════════════════════════════════════════
# 5. 快速测试
# ═══════════════════════════════════════════════════

if __name__ == '__main__':
    print("YLYW 子目标引擎 — 自测试")
    print("=" * 50)

    engine = SubgoalEngine(verbose=True)
    parser = ChineseIntentParser()
    attention = EnhancedAttention()

    # ── 测试1: pick_clean_then_place_in_recep ──
    print("\n--- 1. 拿盘子洗干净放到柜台 ---")
    task_yao = [0.6, 0.7, 0.3, 0.4, 0.6, 0.2]
    engine.reset("pick_clean_then_place_in_recep", task_yao)

    states = [
        (None, False, 0, "空手"),
        ("plate", False, 0, "拿了盘子"),
        ("plate", True, 0, "洗好了"),
        ("plate", True, 0, "到柜台"),
        (None, True, 0, "放好了"),
    ]
    for step, (h, p, tc, desc) in enumerate(states):
        sy = list(task_yao)
        if h:  sy[1] = 0.85
        else:  sy[1] = 0.05
        if p:  sy[2] = 0.90
        if h is None and p:
            sy[5] = 0.90
        idx, lbl, _ = engine.track(sy, h, p, tc)
        print(f"  步{step}: {desc:12s} → [{idx}] {lbl}")

    # ── 测试2: pick_two_obj_and_place ──
    print("\n--- 2. 拿两个肥皂放到垃圾桶 ---")
    engine.reset("pick_two_obj_and_place", [0.5, 0.6, 0.1, 0.3, 0.5, 0.1])

    states2 = [
        (None, False, 0, "空手"),
        ("soapbar 1", False, 1, "拿了第1个"),
        (None, False, 1, "放了第1个"),
        (None, False, 1, "空手找第2个"),
        ("soapbar 3", False, 2, "拿了第2个"),
        (None, False, 2, "放了第2个"),
    ]
    for step, (h, p, tc, desc) in enumerate(states2):
        sy = [0.5, 0.1 if h is None else 0.85, 0.1, 0.3, 0.5, 0.1]
        if h is None and tc >= 2:
            sy[5] = 0.90
        idx, lbl, _ = engine.track(sy, h, p, tc)
        print(f"  步{step}: {desc:16s} → [{idx}] {lbl}")

    # ── 测试3: get_current_intent 映射 ──
    print("\n--- 3. 意图映射 ---")
    for label in ["探索", "拿取", "取第二件", "去预处理", "预处理",
                   "去目标", "放置", "完成"]:
        engine.current_label = label
        intent = engine.get_current_intent()
        print(f"  {label:8s} → {intent}")

    # ── 测试4: 汉语意图解析 ──
    print("\n--- 4. 汉语意图解析 ---")
    for desc in ["拿盘子放到柜台", "拿两个肥皂扔垃圾桶",
                  "洗一下碗放到架子上", "看看灯"]:
        result = parser.parse(desc)
        print(f"  '{desc}' → {result}")

    # ── 测试5: 增强注意力 ──
    print("\n--- 5. 增强注意力 ---")
    locs = ["go to cabinet 1", "go to drawer 1", "go to countertop 1",
             "go to shelf 1", "go to fridge 1", "go to desk 1"]
    visited = {"cabinet 1", "desk 1"}
    ranked = attention.rank_locations(locs, "plate", "拿取", visited)
    print(f"  拿取盘子时推荐顺序:")
    for loc, sc in ranked[:5]:
        print(f"    {loc:30s} score={sc:.3f}")

    print("\n✅ 子目标引擎测试完毕")
