#!/usr/bin/env python3
"""Debug a single game with verbose output"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'language'))

os.environ['TMPDIR'] = f'{os.environ["HOME"]}/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v17 import YLYWAgentV17

game_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 2

env = ALFWorldOfficial(split='valid_unseen')
agent = YLYWAgentV17(verbose=True)

obs, info = env.reset(game_idx=game_idx)
task_desc = info.get('task_desc', '')
task_type_real = info.get('task_type', '')

agent.reset(task_desc=task_desc, task_type=task_type_real)

print(f"\n{'='*60}")
print(f"Game #{game_idx}: {task_desc}")
print(f"  Type: {task_type_real}")
print(f"  参数: obj={agent.obj_en}, target={agent.target_en}, preproc={agent.preproc_en}")
print(f"{'='*60}")

won = False
for step in range(50):
    admissible = info.get('admissible_commands', ['look'])
    action = agent.act_with_admissible(obs, admissible)
    
    obs, info = env.step(action)
    won = info.get('won', False)
    
    success = info.get('action_success', True)
    obs_short = obs[:100].replace('\n', '|')
    print(f"  S{step+1:2d} → {action:35s} {'✅' if success else '❌'} | {obs_short}")
    
    agent.update(action, obs)
    
    if won:
        print(f"\n  ✅ WON in {step+1} steps!")
        break
else:
    print(f"\n  ❌ LOST in 50 steps")
    print(f"  Final intent: {agent._last_intent}")
    print(f"  holding={agent.holding}, processed={agent.processed}")
    print(f"  taken_objects={agent._taken_objects}")
    print(f"  visited locations: {sorted(agent.visited)[:10]}...")

env.close()
