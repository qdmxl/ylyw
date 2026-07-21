#!/usr/bin/env python3
"""
V17 干净评估 — 只靠环境 won 信号，无 early_done
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

def run_one(env, game_idx, agent):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    agent.reset(task_desc=task_desc, task_type=task_type_real)
    
    won = False
    actions = []
    
    for _ in range(MAX_STEPS):
        admissible = info.get('admissible_commands', ['look'])
        action = agent.act_with_admissible(obs, admissible)
        actions.append(action)
        
        obs, info = env.step(action)
        
        if info.get('won', False):
            won = True
            break
        
        agent.update(action, obs)
    
    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_desc': task_desc[:60],
        'steps': len(actions),
        'won': won,
        'actions': actions,
    }

if __name__ == '__main__':
    max_games = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    
    env = ALFWorldOfficial(split='valid_unseen')
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    
    agent = YLYWAgentV17(verbose=False)
    
    print(f"V17 干净评估 (仅环境won): {n} games\n{'='*50}")
    
    results = []
    wins = 0
    t0 = time.time()
    
    for i in range(n):
        try:
            r = run_one(env, i, agent)
        except Exception as e:
            print(f"  ERR #{i}: {e}")
            import traceback; traceback.print_exc()
            r = {'game_idx': i, 'task_type_real': 'error', 'task_desc': str(e)[:60], 'steps': 0, 'won': False, 'actions': []}
        
        wins += 1 if r['won'] else 0
        results.append(r)
        
        elapsed = time.time() - t0
        eta = (elapsed / (i+1)) * (n - i - 1) if i < n-1 else 0
        print(f"  [{wins:3d}/{i+1:3d}] #{i:3d} {'✅' if r['won'] else '❌'} [{r['task_type_real'][:30]:30s}] {r['steps']:2d}步 [{elapsed:.0f}s, ETA={eta:.0f}s]")
    
    total_t = time.time() - t0
    
    from collections import defaultdict
    by_type = defaultdict(lambda: [0, 0])
    for r in results:
        by_type[r['task_type_real']][1] += 1
        if r['won']:
            by_type[r['task_type_real']][0] += 1
    
    print(f"\n{'='*60}")
    print(f"V17 干净评估 — {len(results)} games, {total_t:.0f}s")
    for t, (w, ttl) in sorted(by_type.items()):
        print(f"  {t:40s} {w:3d}/{ttl:2d} ({w/ttl*100:5.1f}%)")
    print(f"  {'总计':40s} {wins:3d}/{len(results):2d} ({wins/len(results)*100:.1f}%) [{total_t:.0f}s]")
    
    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ylyw_agent_v17_results.json')
    with open(outfile, 'w') as f:
        json.dump({'total': len(results), 'won': wins, 'rate': wins/len(results) if results else 0,
                    'elapsed': total_t, 'by_type': {t: {'won':w, 'total':ttl} for t,(w,ttl) in by_type.items()},
                    'results': results}, f, indent=2)
    print(f"\n保存: {outfile}")
