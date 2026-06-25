#!/usr/bin/env python3
"""
YLYW 技能演化层 (L-2: Skill Evolution Layer)

灵感来源: EmbodiSkill (Ju et al., 2026) — Skill-Aware Reflection

核心机制:
  1. Skill-Aware Reflection: 区分缺陷类型
     - SKILL DEFECT:  技能本身有错 → 修正 skill body
     - EXECUTION LAPSE: agent 执行走偏 → 记录到 appendix
     - DISCOVERY:      发现新的有效动作 → 扩充知识库
     - OPTIMIZATION:   发现更优执行路径 → 调整优先级

  2. Evolution Spiral:
     执行 → 反思 → 修正技能 → 下次执行用修正后的技能 → 再执行...

  3. 技能体 (Skill Body) 包含:
     - subgoal 序列模板（action_sequences）
     - 常识先验权重（prior_knowledge）
     - 空间探索策略参数（exploration_params）

  4. 技能附录 (Skill Appendix) 包含:
     - 执行提醒（execution_notes）
     - 失败模式记录（failure_patterns）

YLYW 层次化架构中的位置:
  L-2  技能演化层 (此层)   ← "该怎么改进"
  L-1  结构化认知层          ← "能不能做"
  L0   空间态势感知层        ← "哪里去找"
  L1-3 YLYW 核心三层         ← "怎么执行"
"""

import sys
import os
import re
import json
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# Reflection Types (EmbodiSkill-style)
# ============================================================

class ReflectionType(Enum):
    SKILL_DEFECT = "SKILL_DEFECT"       # 技能本身有缺陷
    EXECUTION_LAPSE = "EXECUTION_LAPSE"  # 执行走偏，技能正确
    DISCOVERY = "DISCOVERY"             # 发现新知识
    OPTIMIZATION = "OPTIMIZATION"       # 发现更优策略


@dataclass
class ReflectionRecord:
    """单条反思记录"""
    ref_type: ReflectionType
    evidence: str           # 轨迹中观察到的事实
    directive: str          # 修正指令
    implicated_content: str  # 涉及到的当前技能内容


# ============================================================
# Skill Body
# ============================================================

@dataclass
class SkillBody:
    """
    可演化的技能体——YLYW 执行层的核心知识

    包含三类知识:
      1. action_sequences: 每种 task_type 的 subgoal 模板
      2. prior_knowledge:  常识先验（物体→位置 → 权重）
      3. exploration_params: 空间探索参数
    """
    # 动作序列模板: task_type → List[subgoal-action-types]
    action_sequences: Dict[str, List[List[str]]] = field(default_factory=dict)

    # 常识先验: object_name → [(location_type, weight), ...]
    prior_knowledge: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)

    # 探索参数
    exploration_params: Dict = field(default_factory=lambda: {
        'unvisited_bonus': 1.5,
        'bagua_compat_bonus': 0.8,
        'prior_confidence_weight': 2.5,
        'abort_threshold_types': 0.75,
        'abort_threshold_steps': 15,
    })

    def to_dict(self) -> Dict:
        return {
            'action_sequences': self.action_sequences,
            'prior_knowledge': {k: v for k, v in self.prior_knowledge.items()},
            'exploration_params': self.exploration_params,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'SkillBody':
        return cls(
            action_sequences=d.get('action_sequences', {}),
            prior_knowledge=d.get('prior_knowledge', {}),
            exploration_params=d.get('exploration_params', {
                'unvisited_bonus': 1.5, 'bagua_compat_bonus': 0.8,
                'prior_confidence_weight': 2.5,
                'abort_threshold_types': 0.75, 'abort_threshold_steps': 15,
            }),
        )


# ============================================================
# Skill Appendix
# ============================================================

@dataclass
class SkillAppendix:
    """
    技能附录：执行提醒 + 失败模式

    不会修改 skill body，但会在执行时被参考
    """
    execution_notes: List[str] = field(default_factory=list)
    failure_patterns: Dict[str, int] = field(default_factory=dict)  # pattern → count

    def add_execution_note(self, note: str):
        """添加强调执行提醒"""
        if note not in self.execution_notes:
            self.execution_notes.append(note)

    def record_failure(self, pattern: str):
        """记录失败模式"""
        self.failure_patterns[pattern] = self.failure_patterns.get(pattern, 0) + 1

    def get_active_notes(self) -> List[str]:
        """获取当前的执行提醒"""
        return self.execution_notes


# ============================================================
# Skill
# ============================================================

@dataclass
class Skill:
    """技能 = SkillBody + SkillAppendix"""
    body: SkillBody
    appendix: SkillAppendix

    def to_dict(self) -> Dict:
        return {
            'body': self.body.to_dict(),
            'appendix': {
                'execution_notes': self.appendix.execution_notes,
                'failure_patterns': dict(self.appendix.failure_patterns),
            },
        }


# ============================================================
# L-2: Skill Evolution Layer
# ============================================================

class SkillEvolutionLayer:
    """
    L-2 技能演化层

    核心方法:
      - reflect_on_trajectory: 对一次执行轨迹进行反思
      - consolidate_and_revise: 积累足够反思后，修正 skill body
      - update_appendix: 修正 skill appendix

    自学习流程:
      1. agent 执行任务 → 产生 trajectory
      2. reflect_on_trajectory → 生成 ReflectionRecord
      3. 积累足够反思 → consolidate_and_revise → 修正 skill body
      4. 修正后的 skill 指导下次执行
    """

    def __init__(self):
        self.skill = Skill(
            body=SkillBody(),
            appendix=SkillAppendix()
        )
        self.reflection_buffer: List[ReflectionRecord] = []
        self.revision_interval = 5  # 每5次反思后修正一次
        self.evolution_round = 0

    def init_skill_from_templates(self, subgoal_templates: Dict[str, List[List[str]]],
                                   prior_knowledge: Dict[str, List[Tuple[str, float]]]):
        """
        从 YLYW 模板和 LLM 知识库初始化 skill body
        """
        self.skill.body.action_sequences = subgoal_templates
        self.skill.body.prior_knowledge = prior_knowledge

    def reflect_on_trajectory(self, task_type: str, task_desc: str,
                               trajectory: List[Dict],
                               final_result: str  # 'won' | 'aborted' | 'timed_out'
                               ) -> List[ReflectionRecord]:
        """
        对单次任务执行轨迹进行技能感知反思

        轨迹格式: [{step, phase, action, obs_summary, admissible_count}, ...]

        反思逻辑（规则驱动，替代 LLM）:
          - 轨迹最后一帧有 take + wrong object → SKILL DEFECT
          - 轨迹中有 go to 但目标位置不在 admissible 中 → SKILL DEFECT
          - 轨迹中有 use/clean/heat/cool 但工具不可用 → SKILL DEFECT
          - 轨迹全程卡在 P0 不推进 → SKILL DEFECT (exploration)
          - 轨迹中有正确 take wrong object → EXECUTION LAPSE
          - 轨迹中 take 失败后持续 go to → EXECUTION LAPSE
          - 轨迹成功但走了不必要的弯路 → OPTIMIZATION
          - 轨迹揭示了新的物体位置附着 → DISCOVERY
        """
        reflections = []

        if not trajectory:
            return reflections

        # 分析轨迹关键事件
        events = self._extract_trajectory_events(trajectory)

        # Reflection 1: 轨迹 succeeded → 检查 OPTIMIZATION/DISCOVERY
        if final_result == 'won':
            ref = self._reflect_success(events, task_type, task_desc)
            if ref:
                reflections.append(ref)
            return reflections

        # Reflection 2: 卡在 phase 0 → 目标物体不可达
        if events.get('stuck_at_phase_0', False) and len(trajectory) >= 8:
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.SKILL_DEFECT,
                evidence=f"Agent stuck at P0 for {len(trajectory)} steps, "
                         f"visited {events.get('unique_locations', 0)} unique locations, "
                         f"no target object found in any of them.",
                directive=f"Increase exploration depth, adjust prior weights, "
                         f"expand search to non-typical locations before aborting",
                implicated_content=f"exploration_params.abort_threshold_steps and prior_knowledge"
            ))

        # Reflection 2b: timed out after exploration → abort came too late
        if final_result == 'timed_out' and events.get('stuck_at_phase_0', False):
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.SKILL_DEFECT,
                evidence=f"Agent exhausted all 50 steps in P0 without finding target",
                directive=f"Reduce abort threshold: if no progress after 20 steps, abort earlier",
                implicated_content=f"exploration_params.abort_threshold_steps"
            ))

        # Reflection 2c: 从失败的轨迹中发现新的物体→位置关联
        if events.get('unique_locations', 0) >= 4:
            # 从 obs 中提取实际看到的物体
            all_objs = set()
            for step in trajectory:
                obs_text = step.get('obs_summary', '')
                objs = re.findall(r'(?:a|an)\|([a-zA-Z]+)', obs_text)
                all_objs.update(objs)
            all_objs_text = ','.join(sorted(all_objs)[:5])
            if all_objs:
                reflections.append(ReflectionRecord(
                    ref_type=ReflectionType.DISCOVERY,
                    evidence=f"Found objects in scene: {all_objs_text}. "
                             f"Target not among them.",
                    directive=f"Record that target object is NOT on these location types. "
                             f"Explore non-standard locations next time.",
                    implicated_content=f"prior_knowledge[target] expansion"
                ))

        # Reflection 2d: 循环检测 → 优化探索
        if events.get('cycle_detected') and events.get('unique_locations', 0) >= 5:
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.OPTIMIZATION,
                evidence=f"Agent visited {events.get('unique_locations', 0)} unique locations "
                         f"but got stuck in a cycle.",
                directive=f"Increase cycle detection penalty, force phase advancement when all locations visited",
                implicated_content="exploration_params.cycle_penalty"
            ))

        # Reflection 3: take 了 wrong object
        if events.get('took_wrong_object'):
            target_obj = events.get('target_object', 'unknown')
            wrong_obj = events.get('wrong_object', 'unknown')
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.EXECUTION_LAPSE,
                evidence=f"Agent took '{wrong_obj}' instead of target '{target_obj}' "
                         f"at step {events.get('wrong_take_step', '?')}",
                directive=f"IMPORTANT: on next execution, check admissible take commands "
                         f"for '{target_obj}' before committing to take action. "
                         f"Do NOT take other objects.",
                implicated_content="execution.appendix.take_precheck"
            ))

        # Reflection 4: phase 3+ stuck → 缺少工具
        if events.get('stuck_at_tool_phase') and events.get('tool_needed'):
            tool = events['tool_needed']
            # SKILL DEFECT: prior_knowledge 缺失 tool→location 映射
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.DISCOVERY,
                evidence=f"Agent needed tool '{tool}' but could not find it. "
                         f"Phase {events.get('stuck_phase', '?')}, "
                         f"took wrong object '{events.get('wrong_object', '?')}'",
                directive=f"Add prior knowledge: {tool} is commonly found on "
                         f"desk, shelf. Add tool-search subgoal before use phase.",
                implicated_content=f"prior_knowledge[{tool}] and action_sequence[{task_type}]"
            ))

        # Reflection 5: 多个位置 visit 后循环 → 探索策略需要优化
        if events.get('cycle_detected') and events.get('unique_locations', 0) >= 5:
            reflections.append(ReflectionRecord(
                ref_type=ReflectionType.OPTIMIZATION,
                evidence=f"Agent visited {events.get('unique_locations', 0)} unique locations "
                         f"but got stuck in a cycle of {events.get('cycle_positions', 2)} positions",
                directive=f"Increase cycle detection penalty, "
                         f"force phase advancement when all locations visited",
                implicated_content="exploration_params.cycle_penalty"
            ))

        return reflections

    def consolidate_and_revise(self) -> Skill:
        """
        积累反思到达阈值后，修正 skill body 并清空 buffer
        """
        if len(self.reflection_buffer) < self.revision_interval:
            return self.skill

        # 按类型分组
        defects = [r for r in self.reflection_buffer
                   if r.ref_type == ReflectionType.SKILL_DEFECT]
        discoveries = [r for r in self.reflection_buffer
                       if r.ref_type == ReflectionType.DISCOVERY]
        optimizations = [r for r in self.reflection_buffer
                         if r.ref_type == ReflectionType.OPTIMIZATION]
        lapses = [r for r in self.reflection_buffer
                  if r.ref_type == ReflectionType.EXECUTION_LAPSE]

        # 修正 skill body（只改 skill body）
        for record in defects + discoveries:
            self._apply_revision(record)

        for record in optimizations:
            self._apply_optimization(record)

        # 修正 skill appendix（不改 body）
        for record in lapses:
            self._update_appendix_from_lapse(record)

        # 清空 buffer，推进演化
        self.reflection_buffer = []
        self.evolution_round += 1

        return self.skill

    def _extract_trajectory_events(self, trajectory: List[Dict]) -> Dict:
        """从轨迹中提取关键事件"""
        events = {
            'stuck_at_phase_0': True,
            'stuck_at_tool_phase': False,
            'took_wrong_object': False,
            'cycle_detected': False,
            'unique_locations': 0,
            'tool_needed': None,
            'target_object': None,
            'wrong_object': None,
            'wrong_take_step': 0,
            'stuck_phase': 0,
        }

        phases_seen = set()
        locations = set()
        action_types_last4 = []
        take_obj = None

        for i, step in enumerate(trajectory):
            ph = step.get('phase', 0)
            action = step.get('action', '')
            atype = step.get('action_type', '')

            phases_seen.add(ph)
            if ph > 0:
                events['stuck_at_phase_0'] = False

            if atype == 'go to':
                loc = action.replace('go to ', '').strip()
                locations.add(loc.split()[-2] if loc.split() and loc.split()[-1].isdigit() else loc)

            if atype == 'take':
                obj = action.replace('take ', '').split(' from ')[0].strip()
                take_obj = obj
                events['target_object'] = take_obj
                # 检查是否是目标物体（需配合外部 knowledge）
                events['wrong_take_step'] = i

            # 循环检测
            if len(action_types_last4) >= 3:
                if action in [t.get('action', '') for t in trajectory[max(0, i-3):i]]:
                    events['cycle_detected'] = True
            action_types_last4.append(atype)
            if len(action_types_last4) > 4:
                action_types_last4.pop(0)

        events['unique_locations'] = len(locations)

        # tool phase stuck?
        if any(ph >= 3 for ph in phases_seen) and \
           not any(step.get('won', False) for step in trajectory):
            events['stuck_at_tool_phase'] = True
            events['stuck_phase'] = max(phases_seen)
            if 'desklamp' in str(trajectory[-1].get('obs_summary', '')) or \
               'use' in str(trajectory[-3:]) or 'clean' in str(trajectory[-3:]):
                events['tool_needed'] = 'desklamp'  # heuristic

        return events

    def _reflect_success(self, events: Dict, task_type: str,
                          task_desc: str) -> Optional[ReflectionRecord]:
        """成功轨迹的反思"""
        # 成功了就没什么需要修正的——但可以提取 DISCOVERY
        return None  # 简化：成功后不进行修正

    def _apply_revision(self, record: ReflectionRecord):
        """将 SKILL DEFECT / DISCOVERY 修正应用到 skill body"""
        body = self.skill.body

        # 修正动作序列: 为需求类型的 subgoal 增加 go to exploration
        if 'action_sequence' in record.implicated_content:
            for task_type in list(body.action_sequences.keys()):
                seq = body.action_sequences[task_type]
                # 如果序列以 ['go to'] 开头且只有一个 go to
                if seq and seq[0] == ['go to'] and seq.count(['go to']) <= 2:
                    # 在第二个 go to 前插入额外探索
                    new_seq = list(seq)
                    # 查找 take 后的 go to
                    for i, sg in enumerate(new_seq):
                        if sg == ['go to'] and i > 0:
                            new_seq.insert(i, ['go to'])
                            break
                    body.action_sequences[task_type] = new_seq

        # 修正先验知识: 更新某物体的 position weights
        if 'prior_knowledge' in record.implicated_content:
            # 从 directive 中解析物体名
            import re
            match = re.search(r'prior_knowledge\[(\w+)\]', record.implicated_content)
            if match:
                obj_name = match.group(1)
                if obj_name not in body.prior_knowledge:
                    body.prior_knowledge[obj_name] = []

        # 修正探索参数
        if 'exploration_params' in record.implicated_content:
            if 'abort' in record.directive.lower():
                body.exploration_params['abort_threshold_steps'] = \
                    min(25, body.exploration_params.get('abort_threshold_steps', 15) + 2)
            if 'cycle' in record.directive.lower():
                body.exploration_params['cycle_penalty'] = 5.0

    def _apply_optimization(self, record: ReflectionRecord):
        """应用 OPTIMIZATION 修正"""
        body = self.skill.body

        if 'cycle' in record.directive.lower():
            body.exploration_params['cycle_penalty'] = \
                body.exploration_params.get('cycle_penalty', 4.0) + 1.0

    def _update_appendix_from_lapse(self, record: ReflectionRecord):
        """从 EXECUTION LAPSE 更新 skill appendix"""
        self.skill.appendix.add_execution_note(record.directive)
        self.skill.appendix.record_failure(record.evidence[:30])

    def get_active_execution_notes(self) -> List[str]:
        """获取当前应被强调的执行提醒"""
        return self.skill.appendix.get_active_notes()

    def get_skill_body(self) -> SkillBody:
        return self.skill.body


# ============================================================
# 集成到 YLYW Agent 的方法
# ============================================================

def apply_skill_to_agent(agent, skill_body: SkillBody):
    """
    将演化后的 skill body 应用到 agent 上

    修改:
      - agent.infer_subgoals → 使用 skill_body.action_sequences
      - agent.spatial._prior_weights → 使用 skill_body.prior_knowledge
      - agent 的 exploration params → 使用 skill_body.exploration_params
    """
    if not agent or not skill_body:
        return

    # 1. 动作序列
    if skill_body.action_sequences:
        agent._evolved_action_sequences = skill_body.action_sequences

    # 2. 先验知识
    if skill_body.prior_knowledge and hasattr(agent, 'llm_guide') and agent.llm_guide:
        for obj, entries in skill_body.prior_knowledge.items():
            if hasattr(agent.llm_guide, 'object_to_locations'):
                agent.llm_guide.object_to_locations[obj] = [loc for loc, _ in entries]

    # 3. 探索参数
    if skill_body.exploration_params and hasattr(agent, 'spatial') and agent.spatial:
        for k, v in skill_body.exploration_params.items():
            if hasattr(agent.spatial, k):
                setattr(agent.spatial, k, v)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 初始化 skill from templates
    layer = SkillEvolutionLayer()

    subgoal_templates = {
        'look_at_obj_in_light': [['go to'], ['take'], ['go to'], ['use']],
        'pick_clean_then_place_in_recep': [['go to'], ['take'], ['go to'], ['clean'], ['go to'], ['put']],
    }

    prior_knowledge = {
        'plate': [('countertop', 1.0), ('cabinet', 0.9), ('shelf', 0.85), ('table', 0.8)],
        'mug': [('countertop', 1.0), ('shelf', 0.9), ('coffeemachine', 0.85), ('desk', 0.8)],
        'knife': [('countertop', 1.0), ('drawer', 0.95), ('table', 0.85)],
    }

    layer.init_skill_from_templates(subgoal_templates, prior_knowledge)
    print(f"Initial skill: {layer.skill.body.action_sequences}")
    print(f"Initial prior: {dict(list(layer.skill.body.prior_knowledge.items())[:2])}")

    # 模拟第一条轨迹: 卡在 P0，找不到 plate
    traj1 = [
        {'step': 0, 'phase': 0, 'action': 'go to shelf 1', 'action_type': 'go to', 'obs_summary': 'no plate'},
        {'step': 1, 'phase': 0, 'action': 'go to shelf 2', 'action_type': 'go to', 'obs_summary': 'no plate'},
        {'step': 2, 'phase': 0, 'action': 'go to bed 1', 'action_type': 'go to', 'obs_summary': 'no plate'},
        {'step': 3, 'phase': 0, 'action': 'go to desk 1', 'action_type': 'go to', 'obs_summary': 'no plate'},
        {'step': 4, 'phase': 1, 'action': 'take creditcard 1 from desk 1', 'action_type': 'take', 'obs_summary': 'took creditcard'},
        {'step': 5, 'phase': 3, 'action': 'go to drawer 1', 'action_type': 'go to', 'obs_summary': 'stuck'},
        {'step': 6, 'phase': 3, 'action': 'go to drawer 2', 'action_type': 'go to', 'obs_summary': 'stuck'},
        {'step': 7, 'phase': 3, 'action': 'go to drawer 1', 'action_type': 'go to', 'obs_summary': 'cycle'},
        {'step': 8, 'phase': 3, 'action': 'go to drawer 2', 'action_type': 'go to', 'obs_summary': 'cycle'},
        {'step': 9, 'phase': 3, 'action': 'go to garbagecan 1', 'action_type': 'go to', 'obs_summary': 'aborted'},
        {'step': 10, 'phase': 3, 'action': 'go to laundryhamper 1', 'action_type': 'go to', 'obs_summary': 'aborted'},
    ]

    # 对每条轨迹进行反思
    refs = layer.reflect_on_trajectory(
        'pick_clean_then_place_in_recep',
        'Put a clean plate on the counter.',
        traj1, 'aborted')

    for r in refs:
        print(f"\nReflection: {r.ref_type.value}")
        print(f"  Evidence: {r.evidence}")
        print(f"  Directive: {r.directive}")
        print(f"  Implicated: {r.implicated_content}")

    layer.reflection_buffer.extend(refs)

    # 模拟第二条轨迹
    traj2 = [
        {'step': 0, 'phase': 0, 'action': 'go to shelf 1', 'action_type': 'go to'},
        {'step': 1, 'phase': 0, 'action': 'go to shelf 2', 'action_type': 'go to'},
        {'step': 2, 'phase': 0, 'action': 'go to desk 1', 'action_type': 'go to'},
    ]
    refs2 = layer.reflect_on_trajectory(
        'pick_clean_then_place_in_recep',
        'Put a clean plate on the counter.',
        traj2, 'timed_out')
    layer.reflection_buffer.extend(refs2)

    # 模拟达到阈值
    for _ in range(3):
        refs3 = layer.reflect_on_trajectory(
            'pick_clean_then_place_in_recep',
            'Put a clean plate on the counter.',
            traj1, 'aborted')
        layer.reflection_buffer.extend(refs3)

    assert len(layer.reflection_buffer) >= 5, f"Buffer = {len(layer.reflection_buffer)}"

    # 修正
    skill = layer.consolidate_and_revise()

    print(f"\n=== After Evolution Round {layer.evolution_round} ===")
    print(f"Abort threshold: {skill.body.exploration_params.get('abort_threshold_steps')}")
    print(f"Action sequences: {skill.body.action_sequences}")
    print(f"Appendix notes: {skill.appendix.execution_notes}")
