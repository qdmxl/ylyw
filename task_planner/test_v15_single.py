#!/usr/bin/env python3
"""
V15 单局测试 — 用 YLYWTaskPlanner 跑一个 ALFWorld 任务

完全不用 admissible_commands，所有信息从 obs 文本解析。
"""

import sys, os, json

# 路径顺序关键：ylyw_core > language > task_planner > alfworld
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_self_dir = os.path.join(_root, 'task_planner')
for d in (_self_dir,  # 优先于alfworld_exp（防止旧ylyw_task_planner.py冲突）
          os.path.join(_root, 'api_docs'),
          os.path.join(_root, 'experiment_phase1'),
          os.path.join(_root, 'language'),
          os.path.join(_root, 'alfworld_exp')):
    if d not in sys.path:
        sys.path.insert(0, d)

os.environ['TMPDIR'] = '/home/lijinhan/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None
_tf.gettempdir()

from alfworld_official_wrapper import ALFWorldOfficial
# 强制重新加载所有task_planner模块（防止旧pyc干扰）
for mod in list(sys.modules.keys()):
    fn = getattr(sys.modules[mod], '__file__', '') or ''
    if 'task_planner' in fn:
        del sys.modules[mod]

from ylyw_task_planner import YLYWTaskPlanner


def run_single_game(env, game_idx, planner, verbose=True):
    """跑一局，完全不用 admissible_commands"""
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type = info.get('task_type', '')
    initial_obs = obs  # 保存初始obs

    if verbose:
        print(f"\n{'='*60}")
        print(f"游戏 #{game_idx}")
        print(f"任务: {task_desc}")
        print(f"类型: {task_type}")
        print(f"{'='*60}")

    planner.reset(task_desc, task_type, initial_obs)

    won = False
    steps = 0
    last_action = ''

    for s in range(50):
        # 规划器决定动作
        action = planner.step(obs, last_action, True)
        
        if verbose:
            print(f"  [{s}] → {action}")

        # 执行动作
        obs, info = env.step(action)
        steps += 1
        last_action = action

        # 检查结果
        won = info.get('won', False)
        action_success = info.get('action_success', True)
        
        # 更新规划器中的状态（反馈真实结果）
        # step()内部会调用encoder和generator的update，
        # 但需要把真实的action_success传回去
        # 当前设计下一步的step()会用上一步的action_success
        # 所以只需要把action_success记录下来供下一步用

        if verbose:
            status = '✅' if action_success else '❌'
            obs_short = obs[:80].replace('\n', ' ')
            print(f"        {status} won={won} | {obs_short}")

        if won:
            if verbose:
                print(f"\n  ✅ 任务完成！{steps}步")
            break

    planner.observe_episode_result(won)

    return {
        'game_idx': game_idx,
        'task_desc': task_desc,
        'task_type': task_type,
        'won': won,
        'steps': steps,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=int, default=0, help='游戏编号')
    parser.add_argument('--verbose', action='store_true', default=True)
    args = parser.parse_args()

    print("创建环境...")
    env = ALFWorldOfficial(split='valid_unseen')
    planner = YLYWTaskPlanner(verbose=args.verbose)

    print(f"运行游戏 #{args.game}...")
    result = run_single_game(env, args.game, planner, verbose=args.verbose)

    print(f"\n{'='*60}")
    icon = '✅' if result['won'] else '❌'
    print(f"{icon} 游戏 #{result['game_idx']}: {result['task_desc']}")
    print(f"   结果: {'成功' if result['won'] else '失败'} ({result['steps']}步)")
    print(f"{'='*60}")

    env.close()


if __name__ == '__main__':
    main()
