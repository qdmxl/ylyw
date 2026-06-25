#!/usr/bin/env python3
"""
知耻学习模块 (Zhichi Learning Module)

《中庸》："知耻近乎勇。" ——从失败中反思修正，方为真勇。

核心公式：K_final = K_prior ⊕ K_zhiji(成功校准) ⊕ K_zhichi(失败校准)

知几(zhiji) = 从微弱信号预见成功（吉之先见者也）
知耻(zhichi) = 从失败中反思修正（知耻近乎勇）
二者构成对偶：知几于微末而趋吉，知耻于败局而避凶。

本模块实现五层失败学习机制：
  L1 错拿校准 —— ☲☱ 睽卦（乖离）：拿错物体的经验排除
  L2 否定先验 —— ☱☵ 困卦（穷困）：去过却找不到目标的负面记忆
  L3 阶段瓶颈 —— ☵☶ 蹇卦（艰难）：反复失败的阶段标记
  L4 步数预算 —— ☵☱ 节卦（节制）：探索预算与策略建议
  L5 失败聚类 —— ☷☲ 明夷卦（前车之鉴）：相同模式的失败归纳

设计原则：
  - 不使用LLM，纯规则提取经验
  - 只从失败(won=False)中学习
  - 经验跨游戏复用
  - 与zhiji_learning对偶互补：知几增益，知耻减损
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class ZhichiLearning:
    """
    知耻学习引擎：从失败轨迹中提取反面经验，校准行为策略。

    与ZhijiLearning构成对偶：
      知几 → 正面校准（看到什么有用 → 加分）
      知耻 → 反面校准（看到什么有害 → 减分/排除）
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ====== L1：错拿校准 —— 睽卦（乖离：拿错物体）======
        # desc中的目标词 → 被错拿的实体名集合
        # 例: "plate" → {"bowl 1", "pan 2"} 表示找plate时拿成了bowl和pan
        self.wrong_take_map: Dict[str, Set[str]] = defaultdict(set)

        # ====== L2：否定先验 —— 困卦（穷困：去了却没有）======
        # 物体base → {位置base: 失败次数}
        # 例: "knife" → {"shelf": 3} 表示3次去shelf找knife都没找到
        self.object_negative_locations: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # ====== L3：阶段瓶颈 —— 蹇卦（艰难：反复卡住）======
        # task_type → {phase_name: 失败次数}
        # 例: "pick_and_place" → {"find_target": 5}
        self.phase_fail_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # ====== L4：步数预算 —— 节卦（节制：探索效率）======
        # task_type → 建议字符串
        self.step_budget_hints: Dict[str, str] = {}

        # 用于L4统计：task_type → (高探索率失败次数, 总失败次数)
        self._high_explore_fail: Dict[str, List[int]] = defaultdict(lambda: [0, 0])

        # ====== L5：失败聚类 —— 明夷卦（前车之鉴：模式归纳）======
        # fingerprint → 出现次数
        # fingerprint = (task_type, final_phase_name, scene, obj_found, tool_found)
        self.failure_clusters: Dict[tuple, int] = defaultdict(int)

        # ====== 统计 ======
        self.failures_observed = 0

    # ====================================================================
    #  主入口：observe_failure
    # ====================================================================

    def observe_failure(self, game_result: dict, trajectory: list,
                        agent_state: dict, scene: str = '', task_desc: str = ''):
        """
        从一局失败的游戏中提取经验。只在won=False时调用。

        Args:
            game_result: {'won': bool, 'steps': int, 'task_type': str, ...}
            trajectory: [(action, obs, admissible_commands), ...]
            agent_state: {
                'target_objects': List[str],   # 目标物体列表
                'target_receps': List[str],    # 目标容器列表
                'final_phase': int,            # 最终阶段编号
                'plan': List[str],             # 计划
                'explored': Set[str],          # 已探索位置
                'object_memory': Dict,         # 已发现物体
                'holding': str,                # 手持物体
                'history': List[str],          # 动作历史
            }
            scene: FloorPlan名称
            task_desc: 任务描述
        """
        if game_result.get('won', False):
            return  # 知耻只从失败中学习

        self.failures_observed += 1
        task_type = game_result.get('task_type', 'unknown')
        target_objects = agent_state.get('target_objects', [])
        target_receps = agent_state.get('target_receps', [])
        final_phase = agent_state.get('final_phase', -1)
        plan = agent_state.get('plan', [])
        explored = agent_state.get('explored', set())
        object_memory = agent_state.get('object_memory', {})
        holding = agent_state.get('holding', '')
        history = agent_state.get('history', [])

        # 推导phase名称
        final_phase_name = self._get_phase_name(plan, final_phase)

        # L1：错拿校准
        self._learn_wrong_takes(trajectory, target_objects, task_desc, plan, final_phase)

        # L2：否定先验
        self._learn_negative_priors(trajectory, target_objects, explored, object_memory,
                                    final_phase, plan)

        # L3：阶段瓶颈
        self._learn_phase_bottleneck(task_type, final_phase_name)

        # L4：步数预算
        self._learn_step_budget(task_type, explored, trajectory, target_objects,
                                object_memory)

        # L5：失败聚类
        self._learn_failure_cluster(task_type, final_phase_name, scene,
                                    target_objects, object_memory, holding)

    # ====================================================================
    #  L1：错拿校准 —— 睽卦（乖离）
    # ====================================================================

    def _learn_wrong_takes(self, trajectory: list, target_objects: List[str],
                           task_desc: str, plan: List[str], final_phase: int):
        """
        L1: 分析"走完了所有phase但未赢"的情况。
        如果agent确实take了某个物体，但该物体不在目标列表中 → 错拿。

        睽卦：火泽相违，所取非所求。
        """
        # 提取目标物体的base name集合
        target_bases = set()
        for obj in target_objects:
            base = re.sub(r'\s*\d+$', '', obj.strip()).lower()
            target_bases.add(base)

        # 也从task_desc中提取可能的目标词
        desc_lower = task_desc.lower()

        # 从轨迹中找到所有实际执行的take动作
        for action, obs, admissible in trajectory:
            if not action.startswith('take '):
                continue

            m = re.match(r'take (.+?) from (.+)', action)
            if not m:
                continue

            taken_full = m.group(1).strip()
            taken_base = re.sub(r'\s*\d+$', '', taken_full).lower()

            # 判断是否错拿：taken的base name不在目标列表中
            if taken_base not in target_bases:
                # 确认obs中没有"Nothing happens"（即确实拿到了）
                if 'nothing happens' in obs.lower():
                    continue

                # 记录错拿：对每个目标物体，记录这个错拿的实体
                for target in target_bases:
                    self.wrong_take_map[target].add(taken_base)

                if self.verbose:
                    print(f"    [知耻:L1:睽] 错拿 '{taken_base}'，目标是 {target_bases}")

    # ====================================================================
    #  L2：否定先验 —— 困卦（穷困）
    # ====================================================================

    def _learn_negative_priors(self, trajectory: list, target_objects: List[str],
                               explored: set, object_memory: dict,
                               final_phase: int, plan: List[str]):
        """
        L2: 分析去过哪些位置但没找到目标物体。
        如果agent在find阶段超时或卡住，记录那些"去过但没有目标物体"的位置类型。

        困卦：泽无水，身陷穷途，所寻不在此处。
        """
        # 判断是否在find阶段(phase 0)失败
        is_find_failure = (final_phase <= 0) or self._is_find_phase(plan, final_phase)

        if not is_find_failure:
            return

        # 目标物体base name
        target_bases = set()
        for obj in target_objects:
            base = re.sub(r'\s*\d+$', '', obj.strip()).lower()
            target_bases.add(base)

        if not target_bases:
            return

        # 从轨迹中提取 agent 访问过的位置
        visited_locations = []
        for action, obs, admissible in trajectory:
            if action.startswith('go to '):
                loc_full = action[6:].strip()
                loc_base = re.sub(r'\s*\d+$', '', loc_full).lower()
                visited_locations.append((loc_full, loc_base, obs, admissible))

        # 对于每个访问过的位置，检查是否有目标物体
        for loc_full, loc_base, obs, admissible in visited_locations:
            # 检查admissible中是否有take目标物体的命令
            has_target = False
            for cmd in admissible:
                if cmd.startswith('take '):
                    m_cmd = re.match(r'take (.+?) from (.+)', cmd)
                    if m_cmd:
                        obj_base = re.sub(r'\s*\d+$', '', m_cmd.group(1).strip()).lower()
                        if obj_base in target_bases:
                            has_target = True
                            break

            # 没有目标物体 → 记录否定先验
            if not has_target:
                for target in target_bases:
                    self.object_negative_locations[target][loc_base] += 1

                    if self.verbose:
                        print(f"    [知耻:L2:困] '{target}' 不在 '{loc_base}'（累计{self.object_negative_locations[target][loc_base]}次）")

    # ====================================================================
    #  L3：阶段瓶颈 —— 蹇卦（艰难）
    # ====================================================================

    def _learn_phase_bottleneck(self, task_type: str, final_phase_name: str):
        """
        L3: 统计每个(task_type, phase_name)的失败频率。

        蹇卦：山上有水，行路艰难，知难而求变。
        """
        if final_phase_name:
            self.phase_fail_counts[task_type][final_phase_name] += 1

            if self.verbose:
                count = self.phase_fail_counts[task_type][final_phase_name]
                print(f"    [知耻:L3:蹇] {task_type}/{final_phase_name} 失败{count}次"
                      f"{'（瓶颈！）' if count >= 3 else ''}")

    # ====================================================================
    #  L4：步数预算 —— 节卦（节制）
    # ====================================================================

    def _learn_step_budget(self, task_type: str, explored: set, trajectory: list,
                           target_objects: List[str], object_memory: dict):
        """
        L4: 分析探索效率，给出策略建议。
        如果失败时已探索 >80% 的位置但没找到目标 → 可能在closed容器中。

        节卦：水泽节，当用有度，探索需知进退。
        """
        self._high_explore_fail[task_type][1] += 1  # 总失败次数

        # 估算总位置数：从轨迹的admissible_commands中提取所有可go to的位置
        all_goto_targets = set()
        for action, obs, admissible in trajectory:
            for cmd in admissible:
                if cmd.startswith('go to '):
                    loc = cmd[6:].strip()
                    all_goto_targets.add(loc)

        if not all_goto_targets:
            return

        explored_set = set(explored) if explored else set()

        # 也统计轨迹中实际go to过的位置
        for action, obs, admissible in trajectory:
            if action.startswith('go to '):
                explored_set.add(action[6:].strip())

        explore_ratio = len(explored_set) / len(all_goto_targets) if all_goto_targets else 0

        # 判断目标物体是否被发现
        target_bases = set()
        for obj in target_objects:
            base = re.sub(r'\s*\d+$', '', obj.strip()).lower()
            target_bases.add(base)

        obj_found = False
        if object_memory:
            for key in object_memory:
                key_base = re.sub(r'\s*\d+$', '', key.strip()).lower()
                if key_base in target_bases:
                    obj_found = True
                    break

        # 高探索率 + 没找到目标 → 可能在容器里
        if explore_ratio > 0.8 and not obj_found:
            self._high_explore_fail[task_type][0] += 1

            high_count = self._high_explore_fail[task_type][0]
            total_count = self._high_explore_fail[task_type][1]

            if high_count >= 2:
                hint = (f"高探索率({high_count}/{total_count}次)仍未找到目标，"
                        f"优先open closed容器（如cabinet、drawer、fridge等）")
                self.step_budget_hints[task_type] = hint

                if self.verbose:
                    print(f"    [知耻:L4:节] {task_type}: {hint}")

    # ====================================================================
    #  L5：失败聚类 —— 明夷卦（前车之鉴）
    # ====================================================================

    def _learn_failure_cluster(self, task_type: str, final_phase_name: str,
                               scene: str, target_objects: List[str],
                               object_memory: dict, holding: str):
        """
        L5: 对失败样本生成fingerprint并聚类，相同模式归为一类。

        明夷卦：地中有火（明入地中），光明受伤，以史为鉴知兴替。
        """
        # 目标物体是否找到
        target_bases = set()
        for obj in target_objects:
            base = re.sub(r'\s*\d+$', '', obj.strip()).lower()
            target_bases.add(base)

        obj_found = False
        if object_memory:
            for key in object_memory:
                key_base = re.sub(r'\s*\d+$', '', key.strip()).lower()
                if key_base in target_bases:
                    obj_found = True
                    break

        # 工具是否找到（如knife用于slice类任务）
        tool_found = holding != '' and holding is not None

        # 生成fingerprint
        fingerprint = (
            task_type,
            final_phase_name or 'unknown',
            scene or 'unknown',
            obj_found,
            tool_found,
        )

        self.failure_clusters[fingerprint] += 1

        if self.verbose:
            count = self.failure_clusters[fingerprint]
            print(f"    [知耻:L5:明夷] 模式{fingerprint} 出现{count}次")

    # ====================================================================
    #  查询接口
    # ====================================================================

    def get_wrong_take_exclusions(self, target_objects: List[str]) -> Set[str]:
        """
        L1查询：返回应该排除的错拿物体base name集合。

        使用方式：在_find_target_take时，如果候选物体的base name在排除集合中，跳过。
        """
        exclusions = set()
        for obj in target_objects:
            base = re.sub(r'\s*\d+$', '', obj.strip()).lower()
            if base in self.wrong_take_map:
                exclusions.update(self.wrong_take_map[base])
        return exclusions

    def get_location_penalty(self, obj_base: str, loc_base: str) -> float:
        """
        L2查询：返回否定先验惩罚值（负值，0到-3）。

        miss_count >= 2 时开始惩罚：
          miss=2 → -1.0
          miss=3 → -1.5
          miss=4 → -2.0
          miss>=5 → -3.0（封顶）

        使用方式：在_act_find的scored评分中调用，叠加到位置得分上。
        """
        obj_key = obj_base.lower()
        loc_key = loc_base.lower()

        neg_locs = self.object_negative_locations.get(obj_key, {})
        miss_count = neg_locs.get(loc_key, 0)

        if miss_count < 2:
            return 0.0

        # 惩罚梯度：miss越多，惩罚越重，封顶-3.0
        penalty = -min(miss_count * 0.5, 3.0)
        return penalty

    def get_bottleneck_phases(self, task_type: str) -> List[str]:
        """
        L3查询：返回失败次数 >= 3 的瓶颈阶段名称列表。
        """
        bottlenecks = []
        phase_counts = self.phase_fail_counts.get(task_type, {})
        for phase_name, count in phase_counts.items():
            if count >= 3:
                bottlenecks.append(phase_name)
        return bottlenecks

    def should_prioritize_open(self, task_type: str) -> bool:
        """
        L4查询：根据失败经验判断是否应优先open容器。

        当高探索率失败次数 >= 2 时返回True。
        """
        stats = self._high_explore_fail.get(task_type, [0, 0])
        return stats[0] >= 2

    def get_failure_hint(self, task_type: str, scene: str) -> Optional[str]:
        """
        L5查询：根据失败模式返回建议。

        查找与当前(task_type, scene)匹配的高频失败模式，返回针对性建议。
        """
        # 找所有匹配(task_type, *, scene, *, *)的失败模式
        matching = {}
        for fp, count in self.failure_clusters.items():
            fp_task, fp_phase, fp_scene, fp_obj_found, fp_tool_found = fp
            if fp_task == task_type and (fp_scene == scene or scene == ''):
                matching[fp] = count

        if not matching:
            return None

        # 取出现次数最多的模式
        top_fp = max(matching, key=matching.get)
        top_count = matching[top_fp]

        if top_count < 2:
            return None  # 单次失败不足以形成模式

        fp_task, fp_phase, fp_scene, fp_obj_found, fp_tool_found = top_fp

        # 生成建议
        hints = []
        if not fp_obj_found:
            hints.append("目标物体难以找到，优先open容器或扩大探索范围")
        if not fp_tool_found:
            if 'slice' in task_type or 'clean' in task_type:
                hints.append("工具未就绪，优先确保工具(knife/sponge等)在手")
        if fp_phase:
            hints.append(f"常在'{fp_phase}'阶段失败({top_count}次)")

        # 补充步数预算建议
        if task_type in self.step_budget_hints:
            hints.append(self.step_budget_hints[task_type])

        return "；".join(hints) if hints else None

    # ====================================================================
    #  统计与辅助
    # ====================================================================

    def get_stats(self) -> dict:
        """统计信息"""
        return {
            'failures_observed': self.failures_observed,
            'wrong_take_map': {k: list(v) for k, v in self.wrong_take_map.items()},
            'negative_locations': {
                obj: dict(locs) for obj, locs in self.object_negative_locations.items()
            },
            'phase_bottlenecks': {
                task: {ph: cnt for ph, cnt in phases.items() if cnt >= 3}
                for task, phases in self.phase_fail_counts.items()
                if any(c >= 3 for c in phases.values())
            },
            'step_budget_hints': dict(self.step_budget_hints),
            'failure_clusters_top': self._get_top_clusters(5),
        }

    def _get_top_clusters(self, n: int = 5) -> List[dict]:
        """返回出现次数最多的n个失败模式"""
        sorted_clusters = sorted(self.failure_clusters.items(),
                                 key=lambda x: x[1], reverse=True)[:n]
        result = []
        for fp, count in sorted_clusters:
            result.append({
                'task_type': fp[0],
                'phase': fp[1],
                'scene': fp[2],
                'obj_found': fp[3],
                'tool_found': fp[4],
                'count': count,
            })
        return result

    def _get_phase_name(self, plan: List[str], phase_idx: int) -> str:
        """从plan列表和phase索引推导阶段名称"""
        if not plan:
            return f'phase_{phase_idx}'

        if 0 <= phase_idx < len(plan):
            phase_str = plan[phase_idx]
            # 从plan字符串中提取简短名称
            # plan通常是 "find target_object" / "take target_object" / "go to recep" 等
            parts = phase_str.strip().split()
            if parts:
                return parts[0].lower()  # "find", "take", "go", "put", "clean", etc.
        elif phase_idx >= len(plan):
            return 'post_plan'  # 走完了所有phase但没赢

        return f'phase_{phase_idx}'

    def _is_find_phase(self, plan: List[str], phase_idx: int) -> bool:
        """判断当前phase是否为find阶段"""
        if not plan or phase_idx < 0:
            return True  # 默认认为是find阶段

        if 0 <= phase_idx < len(plan):
            return plan[phase_idx].strip().lower().startswith('find')

        return False

    # ====== 经验持久化 ======

    def save_experience(self, path: str):
        """将积累的失败经验保存到JSON文件"""
        import json
        data = {
            'version': 1,
            'type': 'zhichi',
            'failures_observed': self.failures_observed,
            'wrong_take_map': {k: list(v) for k, v in self.wrong_take_map.items()},
            'object_negative_locations': {
                k: dict(v) for k, v in self.object_negative_locations.items()
            },
            'phase_fail_counts': {
                k: dict(v) for k, v in self.phase_fail_counts.items()
            },
            'step_budget_hints': dict(self.step_budget_hints),
            'failure_clusters': {
                '|'.join(str(x) for x in k): v
                for k, v in self.failure_clusters.items()
            },
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_experience(self, path: str):
        """从文件加载先前积累的失败经验"""
        import json
        with open(path) as f:
            data = json.load(f)
        self.failures_observed = data.get('failures_observed', 0)
        for k, v in data.get('wrong_take_map', {}).items():
            self.wrong_take_map[k] = set(v)
        for obj, locs in data.get('object_negative_locations', {}).items():
            for loc, cnt in locs.items():
                self.object_negative_locations[obj][loc] += cnt
        for task, phases in data.get('phase_fail_counts', {}).items():
            for ph, cnt in phases.items():
                self.phase_fail_counts[task][ph] += cnt
        self.step_budget_hints.update(data.get('step_budget_hints', {}))
        for k_str, cnt in data.get('failure_clusters', {}).items():
            parts = k_str.split('|')
            if len(parts) == 5:
                fp = (parts[0], parts[1], parts[2],
                      parts[3] == 'True', parts[4] == 'True')
                self.failure_clusters[fp] += cnt
