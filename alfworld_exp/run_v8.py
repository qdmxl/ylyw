#!/usr/bin/env python3
"""运行V8 Agent（无PDDL依赖版）"""
import sys, os, json, time, argparse
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v8 import YLYWAgentV8

MAX_STEPS = 50

def run_single(env, game_idx, agent, verbose=False):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    scene = info.get('scene', {})
    
    # V8: 不传pddl_params，task_type用NL解析（或oracle对比）
    if agent.use_oracle_type:
        use_type = task_type_real
    else:
        from task_desc_parser import parse_task_desc
        parsed = parse_task_desc(task_desc)
        use_type = parsed['task_type']
    
    agent.reset(task_desc=task_desc, task_type=use_type,
                pddl_params=None,  # V8: 不传PDDL
                initial_admissible=info.get('admissible_commands', []))
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"  Desc: {task_desc}")
        print(f"  NL parsed type: {use_type}")
        print(f"  Targets: obj={agent.target_objects}, rec={agent.target_receps}")
        print(f"{'='*60}")

    won = False
    steps = 0
    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])
        action = agent.act(obs, cmds)
        if verbose:
            print(f"  Step {steps:2d} [{agent._current_goal():15s}]: {action}")
        obs, info = env.step(action)
        steps += 1
        won = info.get('won', False)
        agent.update(action, obs, info)
        if won:
            break

    return {
        'game_idx': game_idx, 'task_type_real': task_type_real,
        'task_type_parsed': use_type,
        'type_match': use_type == task_type_real,
        'task_desc': task_desc, 'scene': scene.get('floor_plan', ''),
        'steps': steps, 'won': won,
        'final_phase': agent.phase, 'plan_len': len(agent.plan),
    }

def run_all(env, agent, verbose=False, max_games=0):
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    results = []
    start = time.time()
    print(f"\nYLYW Agent V8 (无PDDL) — {n} games")
    print(f"oracle_type={agent.use_oracle_type}")
    print("="*60)

    for i in range(n):
        try:
            r = run_single(env, i, agent, verbose=verbose)
        except Exception as e:
            r = {'game_idx': i, 'task_type_real': 'error', 'won': False, 'steps': 0, 'error': str(e)}
        results.append(r)
        wins = sum(1 for x in results if x['won'])
        tt = r.get('task_type_real', '?')
        print(f"  [{i+1:3d}/{n}] {'✅' if r['won'] else '❌'} ({tt:40s}) {r.get('steps',0):2d}步 [{wins}/{i+1}={wins/(i+1)*100:.1f}%]")

    elapsed = time.time() - start
    total_wins = sum(1 for r in results if r['won'])
    type_matches = sum(1 for r in results if r.get('type_match', False))
    
    print(f"\n{'='*60}")
    print(f"  V8 Results (无PDDL依赖)")
    print(f"{'='*60}")
    print(f"  成功率: {total_wins}/{len(results)} = {total_wins/len(results)*100:.1f}%")
    print(f"  类型准确率: {type_matches}/{len(results)} = {type_matches/len(results)*100:.1f}%")
    print(f"  平均步数: {sum(r.get('steps',0) for r in results)/len(results):.1f}")
    print(f"  耗时: {elapsed:.0f}s")

    by_type = defaultdict(list)
    for r in results:
        by_type[r.get('task_type_real', '?')].append(r)
    print(f"\n  按类型:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        print(f"    {t:45s}: {tw:2d}/{len(rs):2d} ({tw/len(rs)*100:5.1f}%)")

    output = {'config': {'agent': 'V8', 'pddl': False, 'oracle_type': agent.use_oracle_type},
              'metrics': {'total': len(results), 'won': total_wins, 'rate': total_wins/len(results),
                         'type_accuracy': type_matches/len(results), 'elapsed': elapsed},
              'by_task_type': {t: {'total': len(rs), 'won': sum(1 for r in rs if r['won']),
                                   'rate': sum(1 for r in rs if r['won'])/len(rs)}
                              for t, rs in sorted(by_type.items())},
              'results': results}
    outfile = 'ylyw_agent_v8_results.json'
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {outfile}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='all', choices=['single', 'all'])
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('-n', '--num', type=int, default=0)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--no-oracle', action='store_true', help='不用oracle type，完全NL解析')
    args = parser.parse_args()

    print("Creating env...")
    env = ALFWorldOfficial(split="valid_unseen")
    agent = YLYWAgentV8(verbose=args.verbose, use_oracle_type=not args.no_oracle)

    if args.mode == 'single':
        r = run_single(env, args.game, agent, verbose=True)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        run_all(env, agent, verbose=args.verbose, max_games=args.num if args.num > 0 else 0)
    env.close()
