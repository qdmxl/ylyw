#!/usr/bin/env python3
"""
V16 快速测试：在 ALFWorld valid_unseen 上跑少量场景
"""
import sys, os, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'language'))

os.environ['TMPDIR'] = f'{os.environ["HOME"]}/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v16 import YLYWAgentV16

MAX_STEPS = 50


def run_single(env, game_idx, agent, verbose=False):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    
    agent.reset(task_desc=task_desc, task_type=task_type_real)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_desc}")
        print(f"  Type: {task_type_real}")
        print(f"  卦象: {agent.task_hexagram} yao={[round(x,2) for x in agent.task_yao]}")
        print(f"  参数: obj={agent.obj_en}, target={agent.target_en}, preproc={agent.preproc_en}")
    
    won = False
    steps = 0
    actions = []
    
    for _ in range(MAX_STEPS):
        action = agent.act(obs)
        actions.append(action)
        
        obs, info = env.step(action)
        steps += 1
        won = info.get('won', False)
        
        agent.update(action, obs)
        
        if verbose:
            obs_short = obs[:80] if len(obs) > 80 else obs
            print(f"    → {action:35s} {'✅' if info.get('action_success',True) else '❌'} | {obs_short}")
        
        if won:
            break
    
    icon = '✅' if won else '❌'
    print(f"  {icon} #{game_idx:3d} [{task_type_real[:35]:35s}] steps={steps:2d} {task_desc[:45]}")
    
    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_desc': task_desc,
        'steps': steps,
        'won': won,
        'actions': actions,
    }


def run_all(env, agent, verbose=False, max_games=0):
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    print(f"YLYW Agent V16 — {n} games\n")
    
    results = []
    start = time.time()
    wins = 0
    
    for i in range(n):
        try:
            r = run_single(env, i, agent, verbose=verbose)
            wins += 1 if r['won'] else 0
            results.append(r)
            print(f"  [{wins}/{i+1}={wins/(i+1)*100:.1f}%]")
        except Exception as e:
            print(f"  ❌ #{i} Error: {e}")
            import traceback; traceback.print_exc()
    
    elapsed = time.time() - start
    
    from collections import defaultdict
    by_type = defaultdict(lambda: {'total':0, 'won':0})
    for r in results:
        by_type[r['task_type_real']]['total'] += 1
        if r['won']: by_type[r['task_type_real']]['won'] += 1
    
    print(f"\n{'='*60}")
    print(f"V16 结果 ({len(results)} games, {elapsed:.1f}s)")
    for t, d in sorted(by_type.items()):
        pct = d['won']/d['total']*100
        print(f"  {t:40s} {d['won']:3d}/{d['total']:2d} ({pct:5.1f}%)")
    print(f"  {'总计':40s} {wins:3d}/{len(results):2d} ({wins/len(results)*100:.1f}%)")
    
    output = {'agent':'YLYWAgentV16','total':len(results),'won':wins,'rate':wins/len(results),
              'elapsed':elapsed,'by_type':{t:{'total':d['total'],'won':d['won']} for t,d in by_type.items()},
              'results':results}
    
    return output


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--max_games', type=int, default=5)
    args = parser.parse_args()
    
    env = ALFWorldOfficial(split='valid_unseen')
    agent = YLYWAgentV16(verbose=args.verbose)
    
    output = run_all(env, agent, verbose=args.verbose, max_games=args.max_games)
    env.close()
    
    # 保存结果
    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ylyw_agent_v16_results.json')
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n保存: {outfile}")
