#!/usr/bin/env python3
"""
测试 ChineseBridge 集成到 ALFWorld 运行流程

用单个游戏验证翻译桥接层能否正常跑通。
"""
import sys
import os

# YLYW 核心模块路径
YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alfworld_agent import ALFWorldLight
from ylyw_alfworld_agent import YLYWAgent, run_single_game, run_all_games
from chinese_bridge import ChineseBridge

def run_with_bridge(game_idx=0, verbose=True):
    """用ChineseBridge桥接方式运行一个游戏"""
    env = ALFWorldLight()
    agent = YLYWAgent(verbose=False, use_oracle_type=True)
    bridge = ChineseBridge()

    obs, info = env.reset(game_idx=game_idx)
    task_desc = info['task_desc']
    task_type_real = info['task_type']

    if verbose:
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"EN Task: {task_desc}")
        print(f"CN Task: {bridge._translate_task_desc(task_desc)}")
        print()

    # YLYW推断
    inferred_type = agent.infer_task_type(task_desc, ground_truth=task_type_real)
    subgoals = agent.infer_subgoals(inferred_type, task_desc)
    
    current_phase = 0
    history = []
    steps = 0
    won = False
    MAX_STEPS = 50

    while steps < MAX_STEPS:
        # 桥接：翻译observation和commands
        cn_obs = bridge._translate_obs(obs)
        cn_cmds, en_cmds = bridge._translate_commands(
            info.get('admissible_commands', ['look']))

        # YLYW选择动作（喂英文，但用中文辅助显示）
        action_en = agent.select_action(en_cmds, current_phase, inferred_type,
                                        history, task_desc)
        action_cn = bridge.from_english(action_en)

        if verbose:
            print(f"  Step {steps:2d}: phase={current_phase}")
            print(f"    EN commands: {en_cmds[:5]}{'...' if len(en_cmds)>5 else ''}")
            print(f"    CN commands: {cn_cmds[:5]}{'...' if len(cn_cmds)>5 else ''}")
            print(f"    YLYW picks: {action_cn} / {action_en}")

        # 执行动作
        obs, info = env.step(action_en)
        history.append(action_en)
        steps += 1

        # 判断
        action_success = "didn't work" not in obs.lower()
        current_phase = agent.update_phase(action_en, current_phase, action_success)

        if info.get('done'):
            won = info.get('won', False)
            break

    status = "✅ WON" if won else "❌ LOST"
    print(f"\n{status} in {steps} steps")
    return won, steps

def run_ylyw_original(game_idx=0, verbose=True):
    """原版YLYW流程（对照）"""
    env = ALFWorldLight()
    agent = YLYWAgent(verbose=False, use_oracle_type=True)
    
    result = run_single_game(env, agent, game_idx=game_idx, verbose=verbose)
    status = "✅ WON" if result['won'] else "❌ LOST"
    if verbose:
        print(f"\n{status} in {result['steps']} steps")
    return result['won'], result['steps']

def run_with_full_bridge(game_idx=0, verbose=True):
    """
    完整桥接模式：
    1. 翻译所有输入为中文
    2. YLYW基于中文做推理（需要修改YLYW的语义匹配逻辑）
    3. 翻译YLYW输出回英文执行
    
    注意：此模式下YLYW的_semantic_match依赖英文实体名，
    需要将中文命令中的实体先映射为英文再匹配。
    这是一种"混合"模式——对YLYW展示中文，但语义匹配仍基于英文。
    """
    env = ALFWorldLight()
    agent = YLYWAgent(verbose=False, use_oracle_type=True)
    bridge = ChineseBridge()

    obs, info = env.reset(game_idx=game_idx)
    task_desc = info['task_desc']  # 保持英文task_desc供YLYW的内部匹配用
    task_type_real = info['task_type']

    # 中文翻译供显示和上下文
    cn_task = bridge._translate_task_desc(task_desc)
    cn_obs, cn_info = bridge.translate_info(obs, info)

    if verbose:
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"EN Task: {task_desc}")
        print(f"CN Task: {cn_task}")
        print(f"EN Commands: {info['admissible_commands']}")
        print(f"CN Commands: {cn_info['cn_admissible_commands']}")
        print()

    inferred_type = agent.infer_task_type(task_desc, ground_truth=task_type_real)
    subgoals = agent.infer_subgoals(inferred_type, task_desc)

    current_phase = 0
    history = []
    steps = 0
    won = False
    MAX_STEPS = 50

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])

        # YLYW基于英文选动作（底层匹配逻辑不变）
        action = agent.select_action(cmds, current_phase, inferred_type,
                                     history, task_desc)

        # 只是把显示层面的东西翻译成中文
        action_cn = bridge.from_english(action)

        if verbose:
            en_cmds_display = cmds[:4]
            print(f"  Step {steps:2d}: phase={current_phase}")
            print(f"    YLYW picks: {action_cn} / {action}")

        obs, info = env.step(action)
        history.append(action)
        steps += 1

        action_success = "didn't work" not in obs.lower()
        current_phase = agent.update_phase(action, current_phase, action_success)

        if info.get('done'):
            won = info.get('won', False)
            break

    status = "✅ WON" if won else "❌ LOST"
    if verbose:
        print(f"\n{status} in {steps} steps")
    return won, steps


if __name__ == '__main__':
    # 测试原版 vs 桥接版
    print("=" * 60)
    print("测试1: 原版YLYW")
    print("=" * 60)
    w1, s1 = run_ylyw_original(0, verbose=True)

    print("\n" + "=" * 60)
    print("测试2: 带ChineseBridge翻译（YLYW内部仍用英文）")
    print("=" * 60)
    w2, s2 = run_with_full_bridge(0, verbose=True)

    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    print(f"  原版: {'✅' if w1 else '❌'} {s1}步")
    print(f"  桥接: {'✅' if w2 else '❌'} {s2}步")
    print(f"  一致: {'✅' if w1==w2 and s1==s2 else '❌'}")
