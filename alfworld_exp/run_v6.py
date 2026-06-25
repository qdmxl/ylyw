#!/usr/bin/env python3
"""
运行 YLYW Agent V6 on 官方 ALFWorld (方案B wrapper)

用法:
  python3 run_v5.py --mode single --game 0 --verbose
  python3 run_v5.py --mode all
  python3 run_v5.py --mode all --num 20
"""

import sys
import os
import json
import argparse
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v6 import YLYWAgentV6

MAX_STEPS = 50


def run_single_game(env: ALFWorldOfficial, game_idx: int,
                    agent: YLYWAgentV6, verbose: bool = False) -> dict:
    """运行单个游戏"""
    obs, info = env.reset(game_idx=game_idx)

    task_desc = info.get('task_desc', '')
    task_type = info.get('task_type', '')
    scene = info.get('scene', {})
    pddl_params = info.get('pddl_params', {})

    # 如果不用oracle，需要自己推断task_type（这里先用oracle）
    if not agent.use_oracle_type:
        # TODO: 推断
        pass

    agent.reset(
        task_desc=task_desc,
        task_type=task_type,
        pddl_params=pddl_params,
        initial_admissible=info.get('admissible_commands', []),
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type}")
        print(f"  Desc: {task_desc}")
        print(f"  Scene: {scene.get('floor_plan')} (#{scene.get('scene_num')})")
        print(f"  PDDL: {pddl_params}")
        print(f"{'='*60}")
        print(f"  Obs: {obs[:200]}...")

    won = False
    steps = 0

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])

        action = agent.act(obs, cmds)

        if verbose:
            print(f"  Step {steps:2d} [phase={agent.phase}/{len(agent.plan)}"
                  f" {agent._current_goal():15s}]: {action}")

        obs, info = env.step(action)
        steps += 1

        won = info.get('won', False)

        agent.update(action, obs, info)

        if verbose:
            success = info.get('action_success', True)
            obs_short = obs[:120] if len(obs) > 120 else obs
            print(f"    → {'✓' if success else '✗'} won={won} | {obs_short}")

        if won:
            break

    if verbose:
        print(f"\n  {'✅ WON' if won else '❌ LOST'} in {steps} steps"
              f" (holding: {agent.holding})")

    return {
        'game_idx': game_idx,
        'task_type_real': task_type,
        'type_correct': True,  # oracle mode
        'task_desc': task_desc,
        'scene': scene.get('floor_plan', ''),
        'steps': steps,
        'won': won,
        'final_phase': agent.phase,
        'plan_len': len(agent.plan),
    }


def run_all(env: ALFWorldOfficial, agent: YLYWAgentV6,
            verbose: bool = False, max_games: int = 0):
    """跑全部游戏"""
    n = env.num_games
    if 0 < max_games < n:
        n = max_games

    results = []
    print(f"\n{'='*60}")
    print(f"YLYW Agent V6 — {n}/{env.num_games} games (方案B)")
    print(f"{'='*60}")
    start = time.time()

    for i in range(n):
        try:
            result = run_single_game(env, i, agent, verbose=verbose)
        except Exception as e:
            print(f"  ⚠️ Game {i} error: {e}")
            import traceback
            traceback.print_exc()
            result = {
                'game_idx': i, 'task_type_real': 'error',
                'type_correct': False, 'task_desc': str(e),
                'steps': 0, 'won': False, 'error': str(e),
            }
        results.append(result)

        wins = sum(1 for r in results if r['won'])
        elapsed = time.time() - start
        tt = result.get('task_type_real', '?')
        ph = f"ph={result.get('final_phase',0)}/{result.get('plan_len',0)}"
        print(f"  [{i+1:3d}/{n}] Game {i:3d}: {'✅' if result['won'] else '❌'} "
              f"({tt:45s}) {result.get('steps',0):2d}步 {ph:8s} "
              f"[{wins}/{i+1}={wins/(i+1)*100:.1f}%] [{elapsed:.0f}s]")

    elapsed = time.time() - start
    total_wins = sum(1 for r in results if r['won'])
    total_steps = sum(r.get('steps', 0) for r in results)

    print(f"\n{'='*60}")
    print(f"  YLYW Agent V6 Results")
    print(f"{'='*60}")
    print(f"  Total:      {len(results)}")
    print(f"  Won:        {total_wins}")
    print(f"  Success:    {total_wins/len(results)*100:.1f}%")
    print(f"  Avg Steps:  {total_steps/len(results):.1f}")
    print(f"  Elapsed:    {elapsed:.1f}s")

    by_type = defaultdict(list)
    for r in results:
        by_type[r.get('task_type_real', 'unknown')].append(r)
    print(f"\n  By Task Type:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        ts = sum(r.get('steps', 0) for r in rs)
        avg_phase = sum(r.get('final_phase', 0) for r in rs) / len(rs)
        avg_plan = sum(r.get('plan_len', 0) for r in rs) / len(rs)
        print(f"    {t:45s}: {tw:2d}/{len(rs):2d} ({tw/len(rs)*100:5.1f}%) "
              f"avg={ts/len(rs):.1f}步 phase={avg_phase:.1f}/{avg_plan:.0f}")

    # 保存
    output = {
        'config': {
            'model': 'YLYW Agent V6 (admissible-driven)',
            'simulator': 'AlfredTWEnv + per-game env (方案B)',
            'split': env.split,
            'max_steps': MAX_STEPS,
            'agent_type': 'YLYWAgentV6',
        },
        'metrics': {
            'total_tasks': len(results),
            'won': total_wins,
            'lost': len(results) - total_wins,
            'success_rate': total_wins / len(results),
            'avg_steps': total_steps / len(results),
            'elapsed_seconds': elapsed,
        },
        'by_task_type': {
            t: {
                'total': len(rs),
                'won': sum(1 for r in rs if r['won']),
                'rate': sum(1 for r in rs if r['won']) / len(rs),
                'avg_steps': sum(r.get('steps', 0) for r in rs) / len(rs),
            }
            for t, rs in sorted(by_type.items())
        },
        'results': results,
    }

    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'ylyw_agent_v6_results.json')
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {outfile}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW Agent V6')
    parser.add_argument('--mode', default='single', choices=['single', 'all'])
    parser.add_argument('-n', '--num', type=int, default=0)
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--no-oracle', action='store_true')
    args = parser.parse_args()

    print("Creating ALFWorld environment (方案B)...")
    env = ALFWorldOfficial(split="valid_unseen")
    agent = YLYWAgentV6(verbose=args.verbose,
                        use_oracle_type=not args.no_oracle)

    if args.mode == 'single':
        result = run_single_game(env, args.game, agent, verbose=True)
        print(f"\n{json.dumps(result, indent=2, ensure_ascii=False)}")
    elif args.mode == 'all':
        run_all(env, agent, verbose=args.verbose,
                max_games=args.num if args.num > 0 else 0)

    env.close()
