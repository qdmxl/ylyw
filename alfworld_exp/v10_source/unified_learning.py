#!/usr/bin/env python3
"""
知几知耻统一学习模块 (Unified Zhiji-Zhichi Learning)

《系辞上》："一阴一阳之谓道。"
知几（阳）与知耻（阴）本为一体，如同阴阳本为一道。
成功与失败作用于同一套先验矩阵，只是更新方向相反。

核心公式：
    K = Ω ⊕ ΔK(trajectory, reward)
    
    reward > 0 → 正向校准（知几：成功强化）
    reward < 0 → 负向校准（知耻：失败抑制）

统一接口：
    learner.observe(trajectory, won, agent_state, scene, task_desc)
    
    won=True  → 知几路径（同义词学习、位置正强化、场景记忆）
    won=False → 知耻路径（错拿排除、位置负强化、瓶颈标记、失败聚类）
    两条路径共享同一套数据结构，更新方向相反。

设计原则：
  - 同一个模型，同一张先验矩阵
  - 奖惩对称：成功+α，失败-β
  - 不使用LLM，纯规则提取
  - 一次观察即校准（"见几而作"/"知耻近乎勇"）
  - 经验持久化（save/load）
"""

import re
import json
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class UnifiedLearning:
    """
    知几知耻统一学习引擎。
    
    同一个模型对成功和失败做对称处理：
      - 成功(won=True)：正向校准先验（知几）
      - 失败(won=False)：负向校准先验（知耻）
    
    内部维护统一的先验矩阵，正负信号在同一张表上更新。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ====== 统计 ======
        self.games_played = 0
        self.games_won = 0
        self.calibrations_applied = 0

        # ====== 统一先验矩阵 ======

        # 1. 同义词映射：desc词 → 环境实体名集合
        #    知几：成功时确认映射（正向）
        #    知耻：失败时无影响（同义词只从成功中学）
        self.synonym_map: Dict[str, Set[str]] = defaultdict(set)
        self.known_entities: Set[str] = set()

        # 2. 位置先验矩阵：物体base → {位置base: score}
        #    知几：成功时发现物体在某位置 → score += α
        #    知耻：失败时去过某位置没找到 → score -= β
        #    统一为一张矩阵，正负方向更新
        self.location_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # 3. 物体匹配矩阵：目标词 → {实体名: score}
        #    知几：成功take正确物体 → 该实体 score += α
        #    知耻：失败错拿物体 → 该实体 score -= β（排除）
        self.object_match_scores: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # 4. 场景记忆（只从成功/中性观察中积累）
        self.scene_object_map: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.scene_openable: Dict[str, Set[str]] = defaultdict(set)
        self.scene_empty_locations: Dict[str, Set[str]] = defaultdict(set)

        # 5. 阶段瓶颈计数：(task_type, phase_name) → 失败次数
        #    知几：成功时不更新
        #    知耻：失败时 += 1
        self.phase_fail_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 6. 失败模式聚类
        self.failure_clusters: Dict[tuple, int] = defaultdict(int)

        # 7. 步数预算建议
        self.step_budget_hints: Dict[str, str] = {}
        self._high_explore_fail: Dict[str, List[int]] = defaultdict(lambda: [0, 0])

    # ====================================================================
    #  统一入口：observe
    # ====================================================================

    def observe(self, trajectory: list, won: bool,
                agent_state: dict = None, scene: str = '',
                task_desc: str = '', task_type: str = ''):
        """
        统一的学习入口。

        同一个接口，根据won的值决定校准方向：
          won=True  → 知几路径（正向校准）
          won=False → 知耻路径（负向校准）

        Args:
            trajectory: [(action, obs, admissible_commands), ...]
            won: 本局是否成功
            agent_state: Agent最终状态（用于失败分析）
            scene: FloorPlan名称
            task_desc: 任务描述
            task_type: 任务类型
        """
        self.games_played += 1
        if won:
            self.games_won += 1

        reward = +1.0 if won else -1.0

        # ====== 共享路径：无论成败都执行 ======
        self._calibrate_from_trajectory(trajectory, reward, scene, task_desc)

        # ====== 知几路径（仅成功时） ======
        if won:
            self._zhiji_success_calibration(trajectory, scene, task_desc)

        # ====== 知耻路径（仅失败时） ======
        if not won and agent_state:
            self._zhichi_failure_calibration(
                trajectory, agent_state, scene, task_desc, task_type
            )

    # ====================================================================
    #  共享路径：对称校准
    # ====================================================================

    def _calibrate_from_trajectory(self, trajectory: list, reward: float,
                                   scene: str, task_desc: str):
        """
        从轨迹中提取通用信号，根据reward正负做对称校准。
        
        reward > 0：看到物体在某位置 → 正强化
        reward < 0：去了某位置没找到 → 负强化（惩罚）
        """
        desc_lower = task_desc.lower()

        for action, obs, admissible in trajectory:
            obs_lower = obs.lower()

            # 从admissible的take命令中提取物体-位置关系
            for cmd in admissible:
                if cmd.startswith('take '):
                    m = re.match(r'take (.+?) from (.+)', cmd)
                    if m:
                        obj_base = re.sub(r'\s*\d+$', '', m.group(1).strip()).lower()
                        loc_base = re.sub(r'\s*\d+$', '', m.group(2).strip()).lower()
                        self.known_entities.add(obj_base)

                        # 位置先验：对称更新
                        # 成功时(reward=+1)：物体在此位置 → +1.0
                        # 失败时(reward=-1)：物体在此位置但最终没赢 → 不惩罚位置（物体确实在那里）
                        if reward > 0:
                            self.location_scores[obj_base][loc_base] += 1.0

                        # 同义词校准（仅从观察中学习，不区分成败）
                        self._calibrate_synonyms(desc_lower, obj_base)

            # 场景记忆（无论成败都记录客观事实）
            if action.startswith('open '):
                container = action[5:].strip()
                if scene:
                    self.scene_openable[scene].add(re.sub(r'\s*\d+$', '', container.lower()))

            if action.startswith('go to '):
                loc = action[6:].strip()
                take_cmds = [c for c in admissible if c.startswith('take ')]
                if not take_cmds and 'nothing' in obs_lower:
                    if scene:
                        self.scene_empty_locations[scene].add(loc)

    # ====================================================================
    #  知几路径：成功时的正向校准
    # ====================================================================

    def _zhiji_success_calibration(self, trajectory: list, scene: str, task_desc: str):
        """
        知几：从成功轨迹中积累正面经验。
        
        "见几而作" —— 从成功中看到征兆，记住正确路径。
        """
        desc_lower = task_desc.lower()

        for action, obs, admissible in trajectory:
            for cmd in admissible:
                if cmd.startswith('take '):
                    m = re.match(r'take (.+?) from (.+)', cmd)
                    if m:
                        obj_full = m.group(1).strip()
                        loc_full = m.group(2).strip()
                        obj_base = re.sub(r'\s*\d+$', '', obj_full).lower()

                        # 场景物体精确位置
                        if scene:
                            self.scene_object_map[scene][obj_base] = loc_full

                        # 物体匹配正强化：如果desc中的词在obj_base中出现
                        for word in desc_lower.split():
                            if word in obj_base or obj_base in word:
                                self.object_match_scores[word][obj_base] += 1.0

    # ====================================================================
    #  知耻路径：失败时的负向校准
    # ====================================================================

    def _zhichi_failure_calibration(self, trajectory: list, agent_state: dict,
                                    scene: str, task_desc: str, task_type: str):
        """
        知耻：从失败轨迹中提取否定性经验。
        
        "知耻近乎勇" —— 承认失败，精确归因，定向修正。
        """
        target_objects = agent_state.get('target_objects', [])
        explored = agent_state.get('explored', set())
        final_phase = agent_state.get('final_phase', -1)
        plan = agent_state.get('plan', [])
        holding = agent_state.get('holding', None)

        target_bases = set()
        for obj in target_objects:
            target_bases.add(re.sub(r'\s*\d+$', '', obj.strip()).lower())

        # L1: 错拿校准 —— 对称负强化物体匹配
        self._calibrate_wrong_takes(trajectory, target_bases, task_desc, plan, final_phase)

        # L2: 否定先验 —— 位置矩阵负强化
        self._calibrate_negative_locations(trajectory, target_bases, explored,
                                           agent_state.get('object_memory', {}),
                                           plan, final_phase)

        # L3: 阶段瓶颈
        phase_name = self._get_phase_name(plan, final_phase)
        if task_type and phase_name:
            self.phase_fail_counts[task_type][phase_name] += 1

        # L4: 步数预算
        self._calibrate_step_budget(task_type, explored, trajectory, target_bases)

        # L5: 失败模式聚类
        obj_found = holding is not None or any(
            obj in str(agent_state.get('object_memory', {}))
            for obj in target_bases
        )
        fp = (task_type, phase_name, scene, obj_found, False)
        self.failure_clusters[fp] += 1

    def _calibrate_wrong_takes(self, trajectory: list, target_bases: set,
                               task_desc: str, plan: list, final_phase: int):
        """
        L1: 错拿校准（睽卦——乖离）
        
        如果plan全部走完但没赢 → 检查take了什么物体
        如果take的物体base不在target中 → 负强化该匹配
        """
        # 仅在post_plan失败时分析
        if final_phase < len(plan):
            return

        for action, obs, admissible in trajectory:
            if action.startswith('take '):
                m = re.match(r'take (.+?) from .+', action)
                if m:
                    taken = re.sub(r'\s*\d+$', '', m.group(1).strip()).lower()
                    # 检查是否为目标物体
                    is_target = any(t in taken or taken in t for t in target_bases)
                    if not is_target:
                        # 错拿：负强化
                        for target in target_bases:
                            if target in taken or taken.startswith(target) or target.startswith(taken[:3]):
                                self.object_match_scores[target][taken] -= 3.0
                                if self.verbose:
                                    print(f"    [统一:L1:睽] 错拿 '{taken}'(目标'{target}') → 负强化-3.0")

    def _calibrate_negative_locations(self, trajectory: list, target_bases: set,
                                      explored: set, object_memory: dict,
                                      plan: list, final_phase: int):
        """
        L2: 否定先验（困卦——穷困）
        
        对失败时探索过的每个位置：如果没发现目标物体 → 位置矩阵负强化
        """
        # 仅在find阶段失败时分析
        is_find_failure = final_phase <= 0 or (
            0 <= final_phase < len(plan) and
            plan[final_phase].strip().lower().startswith('find')
        )
        if not is_find_failure:
            return

        visited = []
        for action, obs, admissible in trajectory:
            if action.startswith('go to '):
                loc_full = action[6:].strip()
                loc_base = re.sub(r'\s*\d+$', '', loc_full).lower()
                visited.append((loc_full, loc_base, admissible))

        for loc_full, loc_base, admissible in visited:
            has_target = False
            for cmd in admissible:
                if cmd.startswith('take '):
                    m_cmd = re.match(r'take (.+?) from .+', cmd)
                    if m_cmd:
                        obj_base = re.sub(r'\s*\d+$', '', m_cmd.group(1).strip()).lower()
                        if obj_base in target_bases:
                            has_target = True
                            break

            if not has_target:
                for target in target_bases:
                    # 位置矩阵负强化
                    self.location_scores[target][loc_base] -= 0.5
                    if self.verbose:
                        score = self.location_scores[target][loc_base]
                        print(f"    [统一:L2:困] '{target}'不在'{loc_base}' → score={score:.1f}")

    def _calibrate_step_budget(self, task_type: str, explored: set,
                               trajectory: list, target_bases: set):
        """L4: 步数预算（节卦——节制）"""
        total_locs = set()
        for action, obs, admissible in trajectory:
            for cmd in admissible:
                if cmd.startswith('go to '):
                    total_locs.add(cmd[6:].strip())

        if not total_locs:
            return

        explore_ratio = len(explored) / len(total_locs) if total_locs else 0
        self._high_explore_fail[task_type][1] += 1

        if explore_ratio > 0.7:
            self._high_explore_fail[task_type][0] += 1
            high_count = self._high_explore_fail[task_type][0]
            total_count = self._high_explore_fail[task_type][1]
            if high_count >= 2 and high_count / total_count > 0.5:
                hint = f"优先open容器(高探索率失败{high_count}/{total_count}次)"
                self.step_budget_hints[task_type] = hint

    # ====================================================================
    #  同义词校准（共享，成败无关）
    # ====================================================================

    def _calibrate_synonyms(self, desc_lower: str, env_entity: str):
        """从desc与环境实体的对比中学习同义词映射"""
        desc_words = re.findall(r'[a-z]+', desc_lower)
        for word in desc_words:
            if word == env_entity:
                continue
            # desc中说"coffee" 但环境实体叫"mug" → 记录同义词
            if (word in env_entity or env_entity in word) and word != env_entity:
                if len(word) >= 3 and len(env_entity) >= 3:
                    self.synonym_map[word].add(env_entity)

    # ====================================================================
    #  查询接口
    # ====================================================================

    def get_expanded_objects(self, nl_objects: List[str]) -> List[str]:
        """用同义词扩展目标物体列表"""
        expanded = list(nl_objects)
        for obj in nl_objects:
            if obj in self.synonym_map:
                for syn in self.synonym_map[obj]:
                    if syn not in expanded:
                        expanded.append(syn)
                        self.calibrations_applied += 1
            # 反向查找
            for desc_word, env_names in self.synonym_map.items():
                if obj in env_names:
                    if desc_word not in expanded:
                        expanded.append(desc_word)
        return expanded

    def get_location_score(self, obj_base: str, loc_base: str) -> float:
        """
        获取物体-位置的统一评分。
        
        正分 = 知几积累的正面先验（物体常在此位置）
        负分 = 知耻积累的否定先验（物体不在此位置）
        返回值可正可负，直接叠加到探索评分中。
        """
        return self.location_scores.get(obj_base, {}).get(loc_base, 0.0)

    def get_object_exclusions(self, target_objects: List[str]) -> Set[str]:
        """
        获取应排除的物体集合（知耻L1的错拿标记）。
        
        物体匹配矩阵中score < -2.0的实体视为应排除。
        """
        exclusions = set()
        for target in target_objects:
            target_key = target.lower()
            if target_key in self.object_match_scores:
                for entity, score in self.object_match_scores[target_key].items():
                    if score <= -2.0:
                        exclusions.add(entity)
        return exclusions

    def get_bottleneck_phases(self, task_type: str) -> List[str]:
        """返回失败次数≥3的瓶颈阶段"""
        bottlenecks = []
        for phase, count in self.phase_fail_counts.get(task_type, {}).items():
            if count >= 3:
                bottlenecks.append(phase)
        return bottlenecks

    def should_prioritize_open(self, task_type: str) -> bool:
        """根据失败经验判断是否应优先open容器"""
        return task_type in self.step_budget_hints

    def get_failure_hint(self, task_type: str, scene: str) -> Optional[str]:
        """获取基于失败模式的建议"""
        hints = []
        if task_type in self.step_budget_hints:
            hints.append(self.step_budget_hints[task_type])
        # 从失败聚类中找高频模式
        for fp, count in self.failure_clusters.items():
            if fp[0] == task_type and count >= 3:
                hints.append(f"高频失败模式: phase={fp[1]}, 次数={count}")
        return "；".join(hints) if hints else None

    def should_skip_location(self, scene: str, location: str) -> bool:
        """根据场景经验判断是否跳过某位置"""
        return location in self.scene_empty_locations.get(scene, set())

    # ====================================================================
    #  辅助方法
    # ====================================================================

    def _get_phase_name(self, plan: List[str], phase_idx: int) -> str:
        if not plan:
            return f'phase_{phase_idx}'
        if 0 <= phase_idx < len(plan):
            parts = plan[phase_idx].strip().split()
            return parts[0].lower() if parts else f'phase_{phase_idx}'
        elif phase_idx >= len(plan):
            return 'post_plan'
        return f'phase_{phase_idx}'

    # ====================================================================
    #  统计
    # ====================================================================

    def get_stats(self) -> dict:
        """统计信息"""
        # 统计正/负分数
        pos_locs = sum(1 for obj in self.location_scores.values()
                       for score in obj.values() if score > 0)
        neg_locs = sum(1 for obj in self.location_scores.values()
                       for score in obj.values() if score < 0)
        exclusions = sum(1 for obj in self.object_match_scores.values()
                         for score in obj.values() if score <= -2.0)

        return {
            'games_played': self.games_played,
            'games_won': self.games_won,
            'calibrations_applied': self.calibrations_applied,
            'synonyms_learned': {k: list(v) for k, v in self.synonym_map.items() if v},
            'location_positive': pos_locs,
            'location_negative': neg_locs,
            'object_exclusions': exclusions,
            'phase_bottlenecks': {
                t: {p: c for p, c in phases.items() if c >= 3}
                for t, phases in self.phase_fail_counts.items()
                if any(c >= 3 for c in phases.values())
            },
            'failure_clusters': len(self.failure_clusters),
        }

    # ====================================================================
    #  经验持久化
    # ====================================================================

    def save_experience(self, path: str):
        """保存全部经验到JSON"""
        data = {
            'version': 2,
            'type': 'unified_zhiji_zhichi',
            'games_played': self.games_played,
            'games_won': self.games_won,
            'calibrations_applied': self.calibrations_applied,
            'synonym_map': {k: list(v) for k, v in self.synonym_map.items()},
            'known_entities': list(self.known_entities),
            'location_scores': {k: dict(v) for k, v in self.location_scores.items()},
            'object_match_scores': {k: dict(v) for k, v in self.object_match_scores.items()},
            'scene_object_map': dict(self.scene_object_map),
            'scene_openable': {k: list(v) for k, v in self.scene_openable.items()},
            'scene_empty_locations': {k: list(v) for k, v in self.scene_empty_locations.items()},
            'phase_fail_counts': {k: dict(v) for k, v in self.phase_fail_counts.items()},
            'step_budget_hints': dict(self.step_budget_hints),
            'failure_clusters': {
                '|'.join(str(x) for x in k): v
                for k, v in self.failure_clusters.items()
            },
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_experience(self, path: str):
        """从JSON加载经验"""
        with open(path) as f:
            data = json.load(f)
        self.games_played = data.get('games_played', 0)
        self.games_won = data.get('games_won', 0)
        self.calibrations_applied = data.get('calibrations_applied', 0)
        for k, v in data.get('synonym_map', {}).items():
            self.synonym_map[k] = set(v)
        self.known_entities = set(data.get('known_entities', []))
        for obj, locs in data.get('location_scores', {}).items():
            for loc, score in locs.items():
                self.location_scores[obj][loc] += score
        for obj, matches in data.get('object_match_scores', {}).items():
            for entity, score in matches.items():
                self.object_match_scores[obj][entity] += score
        for k, v in data.get('scene_object_map', {}).items():
            self.scene_object_map[k].update(v)
        for k, v in data.get('scene_openable', {}).items():
            self.scene_openable[k] = set(v)
        for k, v in data.get('scene_empty_locations', {}).items():
            self.scene_empty_locations[k] = set(v)
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
