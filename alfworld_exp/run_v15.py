#!/usr/bin/env python3
"""
Run V15 + 知几学习: 纯 obs-only 逐步决策 + 跨局经验积累
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'language'))

os.environ['TMPDIR'] = f'/home/lijinhan/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']): os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from alfworld_official_wrapper import ALFWorldOfficial
from task_desc_parser import parse_task_desc
from ylyw_agent_v15 import YLYWAgentV15
from zhiji_learning import ZhijiLearning

MAX_STEPS = 50


def run_single(env, game_idx, agent, zhiji, verbose=False):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    scene = info.get('scene', {}).get('floor_plan', '')
    
    parsed = parse_task_desc(task_desc)
    use_type = parsed['task_type']
    
    # 注入知几
    agent.set_zhiji(zhiji)
    
    agent.reset(task_desc=task_desc, task_type=use_type)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"  Desc: {task_desc}")
        print(f"  Targets: obj={agent.target_objects}, rec={agent.target_receps}, tools={agent.target_tools}")
        print(f"  Plan: {agent.plan}")
        if zhiji.synonym_map:
            print(f"  知几经验: {len(zhiji.synonym_map)}组同义词, {zhiji.games_played}局")
    
    won = False
    steps = 0
    trajectory = []
    actions = []
    
    for _ in range(MAX_STEPS):
        action = agent.act(obs)
        actions.append(action)
        
        obs, info = env.step(action)
        steps += 1
        won = info.get('won', False)
        
        # 收集轨迹（用于知几学习）
        trajectory.append((action, obs, info.get('admissible_commands', [])))
        
        agent.update(action, obs)
        
        if verbose:
            obs_short = obs[:80] if len(obs) > 80 else obs
            print(f"    → {'✅' if info.get('action_success', True) else '❌'} won={won} | {obs_short}")
        
        if won:
            break
    
    # 知几学习：从轨迹中提取经验
    try:
        game_result = {'won': won, 'steps': steps, 'task_type': task_type_real}
        zhiji.observe_trajectory(game_result, trajectory, scene=scene, task_desc=task_desc)
    except Exception as e:
        if verbose:
            print(f"    [知几错误] {e}")
    
    if verbose and zhiji.calibrations_applied > 0:
        stats = zhiji.get_stats()
        print(f"  知几: 局{zhiji.games_played}, 同义词{len(stats['synonyms_learned'])}组, 校准{stats['calibrations_applied']}次")
    
    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_parsed': use_type,
        'type_match': use_type == task_type_real,
        'task_desc': task_desc,
        'steps': steps,
        'won': won,
        'final_phase': agent.phase,
        'plan_len': len(agent.plan),
        'actions': actions,
    }


def run_all(env, agent, zhiji, verbose=False, max_games=0):
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    print(f"YLYW Agent V15(知几学习) — {n} games\n")
    
    if zhiji.games_played > 0:
        stats = zhiji.get_stats()
        print(f"  已有知几经验: {zhiji.games_played}局, {len(stats['synonyms_learned'])}组同义词")
    
    results = []
    start = time.time()
    wins = 0
    
    for i in range(n):
        try:
            r = run_single(env, i, agent, zhiji, verbose=verbose)
            wins += 1 if r['won'] else 0
            icon = '✅' if r['won'] else '❌'
            print(f"  {icon} #{i:3d} [{r['task_type_real'][:35]:35s}] steps={r['steps']:2d} "
                  f"[{wins}/{i+1}={wins/(i+1)*100:.1f}%] {r['task_desc'][:40]}")
            results.append(r)
        except Exception as e:
            print(f"  ❌ #{i:3d} Error: {e}")
            import traceback; traceback.print_exc()
    
    elapsed = time.time() - start
    
    from collections import defaultdict
    by_type = defaultdict(lambda: {'total':0,'won':0})
    for r in results:
        by_type[r['task_type_real']]['total'] += 1
        if r['won']: by_type[r['task_type_real']]['won'] += 1
    
    # 知几统计
    zhiji_stats = zhiji.get_stats()
    
    print(f"\n{'='*60}")
    print(f"V15+知几 结果 ({len(results)} games, {elapsed:.1f}s)")
    print(f"知几: {zhiji.games_played}局, {len(zhiji_stats['synonyms_learned'])}组同义词, "
          f"{zhiji_stats['calibrations_applied']}次校准")
    for t, d in sorted(by_type.items()):
        pct = d['won']/d['total']*100
        print(f"  {t:40s} {d['won']:3d}/{d['total']:2d} ({pct:5.1f}%)")
    print(f"  {'总计':40s} {wins:3d}/{len(results):2d} ({wins/len(results)*100:.1f}%)")
    
    output = {'agent':'YLYWAgentV15_zhiji','total':len(results),'won':wins,'rate':wins/len(results),
              'elapsed':elapsed,
              'zhiji_stats': {k: list(v) if isinstance(v, set) else v for k, v in zhiji_stats.items()},
              'by_type':{t:{'total':d['total'],'won':d['won']} for t,d in by_type.items()},
              'results':results}
    with open('ylyw_agent_v15_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n保存: ylyw_agent_v15_results.json")
    
    return output


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--max_games', type=int, default=0)
    args = parser.parse_args()
    
    env = ALFWorldOfficial(split='valid_unseen')
    agent = YLYWAgentV15(verbose=args.verbose)
    zhiji = ZhijiLearning(verbose=args.verbose)
    
    run_all(env, agent, zhiji, verbose=args.verbose, max_games=args.max_games if args.max_games > 0 else 0)
    env.close()
