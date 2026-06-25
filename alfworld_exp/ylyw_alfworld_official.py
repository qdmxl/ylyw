#!/usr/bin/env python3
"""
YLYW + ALFWorld 官方仿真器 — 零样本推理 Agent

与 ylyw_alfworld_agent.py 相同的 YLYW 推理逻辑，
但使用官方 AlfredTWEnv 替代轻量仿真器 ALFWorldLight。

用法：
  python3 ylyw_alfworld_official.py --mode all        # 运行全部134个任务
  python3 ylyw_alfworld_official.py --mode single 0   # 测试单个任务
  python3 ylyw_alfworld_official.py --mode stats      # 仅统计
  python3 ylyw_alfworld_official.py --mode single 0 --verbose  # 详细输出
"""

import sys
import os
import json
import argparse
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Dict

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入官方环境适配器
from alfworld_official_wrapper import ALFWorldOfficial

# 复用 YLYWAgent（从原文件导入）
from ylyw_alfworld_agent import (YLYWAgent, MAX_STEPS, plan_to_walkthrough)

SPLIT = "valid_unseen"

# L-2 技能演化（全局实例，跨 game 累积经验）
from skill_evolution_layer import SkillEvolutionLayer, ReflectionType, ReflectionRecord
GLOBAL_SKILL_LAYER = None  # 延迟初始化


def get_skill_layer():
    """获取/初始化全局技能演化层"""
    global GLOBAL_SKILL_LAYER
    if GLOBAL_SKILL_LAYER is None:
        from llm_semantic_guide import LLMSemanticGuide
        GLOBAL_SKILL_LAYER = SkillEvolutionLayer()

        # 从 LLM guide 和 YLYW agent 初始化初始技能
        guide = LLMSemanticGuide()
        initial_templates = {
            'look_at_obj_in_light': [['go to'], ['take'], ['go to'], ['use']],
            'pick_and_place_simple': [['go to'], ['take'], ['go to'], ['put']],
            'pick_clean_then_place_in_recep': [['go to'], ['take'], ['go to'], ['clean'], ['go to'], ['put']],
            'pick_cool_then_place_in_recep': [['go to'], ['take'], ['go to'], ['cool'], ['go to'], ['put']],
            'pick_heat_then_place_in_recep': [['go to'], ['take'], ['go to'], ['heat'], ['go to'], ['put']],
            'pick_two_obj_and_place': [['go to'], ['take'], ['go to'], ['put'], ['go to'], ['take'], ['go to'], ['put']],
        }

        # 从 guide 的知识库提取先验
        prior = {}
        if hasattr(guide, 'object_to_locations'):
            for obj, locs in guide.object_to_locations.items():
                prior[obj] = [(loc, 0.9 - i * 0.1) for i, loc in enumerate(locs[:5])]

        GLOBAL_SKILL_LAYER.init_skill_from_templates(initial_templates, prior)
        GLOBAL_SKILL_LAYER.revision_interval = 5  # 每5次反思修正一次

    return GLOBAL_SKILL_LAYER


def _l2_record_trajectory(task_type: str, task_desc: str,
                           history: List[str], phases: List[int],
                           final_result: str, obs_summaries: List[str]):
    """将一次执行轨迹记录到 L-2 技能演化层（仅收集，不应用）"""
    global GLOBAL_SKILL_LAYER
    if GLOBAL_SKILL_LAYER is None:
        return  # L-2 not initialized yet, skip
    
    trajectory = []
    for i, (action, ph, obs) in enumerate(zip(history, phases, obs_summaries)):
        atype = action.split()[0] if action.split() else 'unknown'
        trajectory.append({
            'step': i, 'phase': ph, 'action': action,
            'action_type': atype, 'obs_summary': obs[:50],
        })

    refs = GLOBAL_SKILL_LAYER.reflect_on_trajectory(task_type, task_desc, trajectory, final_result)
    GLOBAL_SKILL_LAYER.reflection_buffer.extend(refs)
    return refs


# ============================================================
# 适配后的游戏运行函数
# ============================================================

def run_single_game_official(env: ALFWorldOfficial, agent: YLYWAgent,
                              game_idx: int, verbose: bool = False) -> Dict:
    """使用官方仿真器运行单个游戏"""
    obs, info = env.reset(game_idx=game_idx)

    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')

    # YLYW 推断任务类型
    inferred_type = agent.infer_task_type(task_desc, ground_truth=task_type_real)
    subgoals = agent.infer_subgoals(inferred_type, task_desc)
    
    # v2: 初始化增强模块
    agent.init_v2(task_desc, inferred_type)
    if verbose:
        print(f"  [v2] spatial={agent.spatial is not None}, llm_guide={agent.llm_guide is not None}")

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"Task: {task_desc}")
        print(f"Inferred Type: {inferred_type}")
        print(f"Subgoals ({len(subgoals)} phases):")
        for i, sg in enumerate(subgoals):
            print(f"  P{i}: {sg}")
        print(f"{'='*60}")

    current_phase = 0
    history = []
    steps = 0
    won = False
    consecutive_fails = 0
    stuck_count = 0  # Track how long agent has been stuck

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])

        # 卡住检测：如果在某phase停留超过5步，尝试回退到上一phase
        # (暂时禁用 — 由 v2 update_phase 智能管理)
        # if stuck_count > 5 and current_phase > 0:
        #     if verbose:
        #         print(f"  ⚠ Stuck at P{current_phase}, rolling back to P{current_phase-1}")
        #     current_phase -= 1
        #     stuck_count = 0
        
        # 如果卡住了（consecutive_fails > 8），回退到 go to 阶段重新探索
        # (暂时禁用)
        # if consecutive_fails > 8 and current_phase > 0:
        #     if verbose:
        #         print(f"  ⚠ Too many consecutive fails, resetting to exploration")
        #     current_phase = 0
        #     stuck_count = 0
        #     consecutive_fails = 0

        # YLYW 选择动作
        action = agent.select_action(cmds, current_phase, inferred_type,
                                     history, task_desc)

        if verbose:
            print(f"  Step {steps}: P{current_phase} [{len(cmds)} cmds, fails={consecutive_fails}] → {action[:70]}")

        obs, info = env.step(action)
        history.append(action)
        steps += 1
        
        # v2: 记录空间探索
        if agent.spatial:
            agent.spatial.record_step(action, obs)

        # 判断动作是否成功
        action_success = info.get('action_success', True)
        
        # 追踪连续失败/卡住
        if action_success:
            consecutive_fails = 0
        else:
            consecutive_fails += 1
        
        # 追踪同phase停留
        old_phase = current_phase
        # 更新 cmds 为当前位置的 admissible（v2 update_phase 需要）
        cmds = info['admissible_commands']
        current_phase = agent.update_phase(action, current_phase, action_success, cmds)
        
        if current_phase == old_phase:
            stuck_count += 1
        else:
            stuck_count = 0

        if verbose and current_phase != old_phase:
            print(f"  >>> Phase: {old_phase} → {current_phase}")
        if verbose and not action_success:
            print(f"  ✗ Action failed")

        if info.get('done'):
            won = info.get('won', False)
            break

    result = {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_inferred': inferred_type,
        'type_correct': inferred_type == task_type_real,
        'task_desc': task_desc[:80],
        'steps': steps,
        'won': won,
        'walkthrough_len': info.get('walkthrough_len', 0),
    }

    # L-2: 记录轨迹到技能演化层（收集模式，不立即应用）
    final_state = 'won' if won else ('aborted' if agent.spatial and agent.spatial.cognition and agent.spatial.cognition.should_abort else 'timed_out')
    obs_summaries = [''] * len(history)
    _l2_record_trajectory(
        task_type_real, task_desc, history,
        [0] * len(history),
        final_state, obs_summaries
    )

    if verbose:
        status = "✅ WON" if won else "❌ LOST"
        print(f"  {status} in {steps} steps | "
              f"type_match={inferred_type == task_type_real}")

    return result


def run_all_games_official(env_template: ALFWorldOfficial, agent_template: YLYWAgent,
                            verbose: bool = False, max_games: int = 0):
    """运行所有游戏（官方仿真器）。每个 game 独立 env 避免状态污染。"""
    results = []
    n = len(env_template._game_files)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n{'='*60}")
    print(f"YLYW-ALFWorld Official Simulator — Zero-Shot Agent")
    print(f"Total tasks: {n}")
    print(f"{'='*60}\n")

    start_time = time.time()

    for i in range(n):
        # 每个 game 独立 env + 独立 agent
        env = ALFWorldOfficial(split=SPLIT)
        game_agent = YLYWAgent(verbose=verbose, use_oracle_type=agent_template.use_oracle_type)
        result = run_single_game_official(env, game_agent, i, verbose=verbose)
        results.append(result)
        results.append(result)

        status = "✅" if result['won'] else "❌"
        type_info = "✓" if result['type_correct'] else "✗"
        elapsed = time.time() - start_time
        eta = (elapsed / (i + 1)) * (n - i - 1) if i < n - 1 else 0
        print(f"[{i+1:3d}/{n}] {status} "
              f"{result['task_type_real'][:32]:32s} | "
              f"steps={result['steps']:2d} | "
              f"type={type_info} | ETA={eta:.0f}s",
              end='\r' if not verbose else '\n')

    elapsed = time.time() - start_time
    return results, elapsed


def compute_metrics(results: List[Dict]) -> Dict:
    """计算评估指标"""
    n = len(results)
    wins = sum(1 for r in results if r['won'])
    type_correct = sum(1 for r in results if r['type_correct'])

    by_type = defaultdict(lambda: {'total': 0, 'won': 0, 'steps': [], 'type_correct': 0})
    for r in results:
        tt = r['task_type_real']
        by_type[tt]['total'] += 1
        by_type[tt]['won'] += 1 if r['won'] else 0
        by_type[tt]['steps'].append(r['steps'])
        by_type[tt]['type_correct'] += 1 if r['type_correct'] else 0

    type_breakdown = {}
    for tt, d in sorted(by_type.items()):
        type_breakdown[tt] = {
            'total': d['total'],
            'won': d['won'],
            'success_rate': d['won'] / d['total'] if d['total'] > 0 else 0,
            'avg_steps': sum(d['steps']) / len(d['steps']) if d['steps'] else 0,
            'type_accuracy': d['type_correct'] / d['total'] if d['total'] > 0 else 0,
        }

    total_steps = sum(r['steps'] for r in results)
    total_walkthrough = sum(r.get('walkthrough_len', 0) for r in results)

    return {
        'total_tasks': n,
        'won': wins,
        'lost': n - wins,
        'success_rate': wins / n if n > 0 else 0,
        'type_accuracy': type_correct / n if n > 0 else 0,
        'avg_steps': total_steps / n if n > 0 else 0,
        'total_steps': total_steps,
        'avg_walkthrough_len': total_walkthrough / n if n > 0 else 0,
        'by_task_type': type_breakdown,
    }


def print_metrics(metrics: Dict, elapsed: float):
    """打印实验结果"""
    print(f"\n{'='*60}")
    print(f"  YLYW-ALFWorld 官方仿真器 实验结果")
    print(f"{'='*60}")
    print(f"  Total tasks:      {metrics['total_tasks']}")
    print(f"  Won:              {metrics['won']}")
    print(f"  Lost:             {metrics['lost']}")
    print(f"  Success Rate:     {metrics['success_rate']:.2%}")
    print(f"  Type Accuracy:    {metrics['type_accuracy']:.2%}")
    print(f"  Avg Steps:        {metrics['avg_steps']:.1f}")
    print(f"  Total Steps:      {metrics['total_steps']}")
    print(f"  Avg WT Len:       {metrics['avg_walkthrough_len']:.1f}")
    print(f"  Elapsed:          {elapsed:.1f}s")
    print(f"\n  按任务类型划分:")
    print(f"  {'Task Type':<42s} {'#':>3s} {'Won':>3s} {'Rate':>7s} {'AvgS':>5s} {'TAcc':>6s}")
    print(f"  {'-'*62}")
    for tt, d in metrics['by_task_type'].items():
        print(f"  {tt:<42s} {d['total']:3d} {d['won']:3d} "
              f"{d['success_rate']:6.1%} {d['avg_steps']:5.1f} "
              f"{d['type_accuracy']:5.1%}")
    print(f"{'='*60}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="YLYW + ALFWorld Official Simulator — Zero-Shot Agent")
    parser.add_argument("--mode", choices=["all", "single", "stats"],
                        default="all")
    parser.add_argument("--game", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--num", type=int, default=0,
                        help="Max number of games (0=all)")
    parser.add_argument("--oracle", action="store_true",
                        help="Use ground truth task type")
    args = parser.parse_args()

    print("Initializing ALFWorld Official Environment...")
    env = ALFWorldOfficial(split=SPLIT)

    if args.mode == "stats":
        stats = env.get_stats()
        print("\nALFWorld Official Dataset Stats:")
        print(f"  Split: {stats['split']}")
        print(f"  Games: {stats['total_games']}")
        for tt, n in sorted(stats['task_types'].items()):
            print(f"    {tt}: {n}")
        return

    agent = YLYWAgent(verbose=args.verbose, use_oracle_type=args.oracle)

    mode_label = "🔮 Oracle Mode" if args.oracle else "🧠 YLYW Semantic Parser Mode"
    print(f"Running in: {mode_label}\n")

    if args.mode == "single":
        result = run_single_game_official(env, agent, args.game, verbose=True)
        print(f"\nResult: {'WON' if result['won'] else 'LOST'}")
        print(f"  Type: {result['task_type_real']} "
              f"(inferred: {result['task_type_inferred']})")
        print(f"  Steps: {result['steps']}/{result['walkthrough_len']}")
        return

    # mode == all
    # 初始化 L-2 技能演化层（提前初始化，跨 game 收集轨迹）
    layer = get_skill_layer()
    print(f"L-2 Skill Evolution: initialized. Prior knowledge entries: {len(layer.skill.body.prior_knowledge)}")
    results, elapsed = run_all_games_official(
        env, agent, verbose=args.verbose, max_games=args.num)
    metrics = compute_metrics(results)
    print_metrics(metrics, elapsed)

    # L-2: 技能演化总结
    layer = get_skill_layer()
    if layer and layer.reflection_buffer:
        print(f"\n=== L-2 Skill Evolution Summary ===")
        print(f"  Trajectories recorded: {len(layer.reflection_buffer)}")
        by_type = {}
        for r in layer.reflection_buffer:
            by_type[r.ref_type.value] = by_type.get(r.ref_type.value, 0) + 1
        for t, c in sorted(by_type.items()):
            print(f"    {t}: {c}")
        
        # 合并演化
        layer.revision_interval = len(layer.reflection_buffer)
        skill = layer.consolidate_and_revise()
        print(f"  Evolution round: {layer.evolution_round}")
        print(f"  Evolved abort_steps: {skill.body.exploration_params.get('abort_threshold_steps')}")
        print(f"  Evolved cycle_penalty: {skill.body.exploration_params.get('cycle_penalty')}")
        print(f"  Appendix notes: {len(skill.appendix.execution_notes)}")

    # 保存结果
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), 'ylyw_alfworld_official_results.json')

    with open(output_path, 'w') as f:
        json.dump({
            'config': {
                'model': 'YLYW Zero-Shot (Official Sim)',
                'simulator': 'AlfredTWEnv (TextWorld 1.7.0)',
                'split': SPLIT,
                'max_steps': MAX_STEPS,
                'agent_type': 'YLYW_3layer_PriorInference',
            },
            'metrics': {k: v for k, v in metrics.items()
                        if k != 'by_task_type'},
            'by_task_type': metrics['by_task_type'],
            'results': results,
            'elapsed_seconds': elapsed,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
