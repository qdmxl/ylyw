#!/usr/bin/env python3
"""V19 完整134局评测"""
import sys, os, json, gc, time

sys.path.insert(0, 'v18')
sys.path.insert(0, 'v19')
os.environ['ALFWORLD_DATA'] = os.path.expanduser('~/.cache/alfworld')

from alfworld_official_wrapper import ALFWorldOfficial
from agent_v19 import AgentV19

env = ALFWorldOfficial(split='valid_unseen')
print('Env ready', flush=True)

results = []
# 如果已有部分结果，从中断点继续
START_FROM = 11
if os.path.exists('v19/results_v19_full.json'):
    try:
        with open('v19/results_v19_full.json') as f:
            existing = json.load(f)
        results = existing['results']
        START_FROM = len(results)
        print(f'从现有结果继续，已有 {START_FROM} 局', flush=True)
    except:
        pass

for gi in range(START_FROM, 134):
    agent = AgentV19(log_path=None, verbose=False, alpha=0.3)
    try:
        obs, info = env.reset(game_idx=gi)
        adm = info.get('admissible_commands', ['look'])
        agent.reset(info.get('task_desc', ''), obs, adm, game_id=gi)
        won = False
        steps = 0
        t0 = time.time()
        for step in range(50):
            if time.time() - t0 > 180:
                print(f'  TIMEOUT gi={gi}', flush=True)
                break
            action = agent.act(obs, adm)
            obs, info = env.step(action)
            won = bool(info.get('won', False))
            adm = info.get('admissible_commands', ['look'])
            agent.observe_transition(action, obs, adm, won=won)
            steps = step + 1
            if won or info.get('done', False):
                break
        dt = time.time() - t0
        results.append({'game_idx': gi, 'won': won, 'steps': steps, 'time': round(dt,1)})
        mark = 'W' if won else 'L'
        print(f'  gi={gi:3d} {mark} s={steps:2d} t={dt:.1f}s', flush=True)
    except Exception as e:
        import traceback; traceback.print_exc()
        results.append({'game_idx': gi, 'won': False, 'steps': 0, 'time': 0})
        print(f'  gi={gi:3d} E: {e}', flush=True)
    finally:
        del agent
        gc.collect()

summary = {'total': 134, 'won': sum(1 for r in results if r['won']), 'results': results}
with open('v19/results_v19_full.json', 'w') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
won_count = summary['won']
print(f'\n=== V19完整134局: {won_count}/134 = {won_count/134*100:.1f}% ===', flush=True)
