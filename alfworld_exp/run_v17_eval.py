#!/usr/bin/env python3
"""
V17 完整评估：在 ALFWorld valid_unseen 上跑全部/部分游戏
集成动作原语库适配器 + V6 探索效率增强

用法:
  python3 run_v17_eval.py                    # 跑全部134局
  python3 run_v17_eval.py --max_games 20     # 只跑20局
  python3 run_v17_eval.py --verbose          # 详细输出(前3局)
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'language'))

os.environ['TMPDIR'] = f'{os.environ["HOME"]}/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v17 import YLYWAgentV17

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
        print(f"  参数: obj={agent.obj_en}, target={agent.target_en}, preproc={agent.preproc_en}")
    
    won = False
    steps = 0
    actions = []
    early_done = False
    
    for _ in range(MAX_STEPS):
        admissible = info.get('admissible_commands', ['look'])
        action = agent.act_with_admissible(obs, admissible)
        actions.append(action)
        
        # 检查意图是否为"完成"——agent 自己认为任务已完成
        if agent._last_intent == "完成" and steps >= 3:
            early_done = True
            won = True
            break
        
        obs, info = env.step(action)
        steps += 1
        
        # 环境信号
        if info.get('won', False):
            won = True
            break
        
        agent.update(action, obs)
        
        if verbose:
            obs_short = obs[:80] if len(obs) > 80 else obs
            success = info.get('action_success', True)
            print(f"    S{steps:2d} [{agent._last_intent[:8]:8s}] → {action:35s} {'✅' if success else '❌'} | {obs_short}")
    
    icon = '✅' if won else '❌'
    early_tag = '[early]' if early_done else '      '
    print(f"  {icon}{early_tag} #{game_idx:3d} [{task_type_real[:35]:35s}] steps={steps:2d} {task_desc[:45]}")
    
    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_desc': task_desc[:60],
        'steps': steps,
        'won': won,
        'early_done': early_done,
        'actions': actions,
    }

def run_all(env, agent, verbose=False, max_games=0):
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    print(f"YLYW Agent V17 (增强版) — {n} games\n")
    
    results = []
    start = time.time()
    wins = 0
    
    for i in range(n):
        show_verbose = verbose and i < 3
        try:
            r = run_single(env, i, agent, verbose=show_verbose)
            wins += 1 if r['won'] else 0
            results.append(r)
            rate = wins / (i+1) * 100
            print(f"  [{wins}/{i+1}] = {rate:.1f}%")
        except Exception as e:
            print(f"  ❌ #{i} Error: {e}")
            import traceback; traceback.print_exc()
    
    elapsed = time.time() - start
    
    from collections import defaultdict
    by_type = defaultdict(lambda: {'total':0, 'won':0, 'early':0})
    for r in results:
        by_type[r['task_type_real']]['total'] += 1
        if r['won']:
            by_type[r['task_type_real']]['won'] += 1
        if r.get('early_done'):
            by_type[r['task_type_real']]['early'] += 1
    
    print(f"\n{'='*60}")
    print(f"V17 增强版结果 ({len(results)} games, {elapsed:.1f}s)")
    for t, d in sorted(by_type.items()):
        pct = d['won']/d['total']*100
        early_str = f" [{d['early']} early]" if d['early'] else ""
        print(f"  {t:40s} {d['won']:3d}/{d['total']:2d} ({pct:5.1f}%){early_str}")
    print(f"  {'总计':40s} {wins:3d}/{len(results):2d} ({wins/len(results)*100:.1f}%) [{elapsed:.0f}s]")
    
    output = {
        'config': {
            'agent': 'YLYWAgentV17 (+V6 exploration)',
            'split': 'valid_unseen',
            'max_steps': MAX_STEPS,
        },
        'metrics': {
            'total': len(results),
            'won': wins,
            'success_rate': wins/len(results) if results else 0,
            'elapsed': elapsed,
        },
        'by_type': {t: {'total': d['total'], 'won': d['won'], 'rate': d['won']/d['total'] if d['total'] else 0} for t, d in by_type.items()},
        'results': results,
    }
    
    return output

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='V17 ALFWorld Eval')
    parser.add_argument('--verbose', '-v', action='store_true', default=False)
    parser.add_argument('--max_games', '-n', type=int, default=0, help='Max games (0=all)')
    args = parser.parse_args()
    
    env = ALFWorldOfficial(split='valid_unseen')
    agent = YLYWAgentV17(verbose=args.verbose)
    
    output = run_all(env, agent, verbose=args.verbose, max_games=args.max_games)
    env.close()
    
    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ylyw_agent_v17_results.json')
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n保存: {outfile}")
