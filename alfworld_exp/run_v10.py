#!/usr/bin/env python3
"""
运行V10 Agent（V9 + 知耻学习）

知几+知耻学习模式：
- 知几(zhiji): 从所有轨迹中学习同义词/位置先验/场景结构
- 知耻(zhichi): 从失败轨迹中学习错拿排除/否定先验/瓶颈/open优先
两者协同校准先验知识，实现更有效的经验积累。
"""
import sys, os, json, time, argparse, re
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v10 import YLYWAgentV10
from zhiji_learning import ZhijiLearning
from zhichi_learning import ZhichiLearning

MAX_STEPS = 50


def run_single(env, game_idx, agent, zhiji, zhichi, verbose=False):
    """运行单个游戏，并收集轨迹供知几/知耻学习"""
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    scene = info.get('scene', {}).get('floor_plan', '')

    from task_desc_parser import parse_task_desc
    parsed = parse_task_desc(task_desc)
    use_type = parsed['task_type']

    # 注入知几学习引擎
    agent._zhiji = zhiji
    # 注入知耻学习引擎
    agent._zhichi = zhichi

    agent.reset(task_desc=task_desc, task_type=use_type,
                pddl_params=None,
                initial_admissible=info.get('admissible_commands', []))

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"  Desc: {task_desc}")
        print(f"  Targets: obj={agent.target_objects}, rec={agent.target_receps}")
        zhiji_stats = zhiji.get_stats()
        print(f"  知几经验: {zhiji_stats['games_played']}局, "
              f"同义词={len(zhiji_stats['synonyms_learned'])}组, "
              f"校准={zhiji_stats['calibrations_applied']}次")
        zhichi_stats = zhichi.get_stats()
        print(f"  知耻经验: fails={zhichi_stats['failures_observed']}, "
              f"wrong_takes={len(zhichi_stats.get('wrong_take_map', {}))}, "
              f"neg_priors={len(zhichi_stats.get('negative_priors', {}))}")
        print(f"{'='*60}")

    trajectory = []  # 收集轨迹
    won = False
    steps = 0

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])
        action = agent.act(obs, cmds)

        if verbose:
            print(f"  Step {steps:2d} [{agent._current_goal():15s}]: {action}")

        old_obs = obs
        obs, info = env.step(action)
        steps += 1
        won = info.get('won', False)

        # 记录轨迹
        trajectory.append((action, obs, info.get('admissible_commands', [])))

        agent.update(action, obs, info)

        if verbose:
            success = info.get('action_success', True)
            obs_short = obs[:100] if len(obs) > 100 else obs
            print(f"    → {'✓' if success else '✗'} won={won} | {obs_short}")

        if won:
            break

    # 知几学习：从所有轨迹中提取经验
    game_result = {'won': won, 'steps': steps, 'task_type': task_type_real}
    zhiji.observe_trajectory(game_result, trajectory, scene=scene, task_desc=task_desc)

    # 知耻学习：从失败轨迹中提取经验
    if not won:
        agent_state = agent.get_trajectory_state()
        zhichi.observe_failure(game_result, trajectory, agent_state,
                               scene=scene, task_desc=task_desc)

    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_parsed': use_type,
        'type_match': use_type == task_type_real,
        'task_desc': task_desc,
        'scene': scene,
        'steps': steps,
        'won': won,
        'final_phase': agent.phase,
        'plan_len': len(agent.plan),
    }


def run_all(env, agent, zhiji, zhichi, verbose=False, max_games=0, output_file='ylyw_agent_v10_results.json'):
    """顺序执行全部游戏（知几+知耻学习模式）"""
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    results = []
    start = time.time()

    print(f"\nYLYW Agent V10 (知几+知耻学习) — {n} games")
    print("=" * 60)

    for i in range(n):
        try:
            r = run_single(env, i, agent, zhiji, zhichi, verbose=verbose)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = {'game_idx': i, 'task_type_real': 'error', 'won': False,
                 'steps': 0, 'error': str(e)}
            # 即使出错也要更新知几/知耻
        results.append(r)

        wins = sum(1 for x in results if x['won'])
        tt = r.get('task_type_real', '?')
        zhiji_stats = zhiji.get_stats()
        syn_count = len(zhiji_stats['synonyms_learned'])
        cal_count = zhiji_stats['calibrations_applied']
        zhichi_stats = zhichi.get_stats()
        zc_fails = zhichi_stats['failures_observed']
        zc_wt = len(zhichi_stats.get('wrong_take_map', {}))
        print(f"  [{i+1:3d}/{n}] {'✅' if r['won'] else '❌'} ({tt:40s}) "
              f"{r.get('steps',0):2d}步 [{wins}/{i+1}={wins/(i+1)*100:.1f}%] "
              f"知几:syn={syn_count},cal={cal_count} "
              f"知耻:fail={zc_fails},wt={zc_wt}")

    elapsed = time.time() - start
    total_wins = sum(1 for r in results if r['won'])
    type_matches = sum(1 for r in results if r.get('type_match', False))

    print(f"\n{'='*60}")
    print(f"  V10 Results (知几+知耻学习)")
    print(f"{'='*60}")
    print(f"  成功率: {total_wins}/{len(results)} = {total_wins/len(results)*100:.1f}%")
    print(f"  类型准确率: {type_matches}/{len(results)} = {type_matches/len(results)*100:.1f}%")
    print(f"  平均步数: {sum(r.get('steps',0) for r in results)/len(results):.1f}")
    print(f"  耗时: {elapsed:.0f}s")

    # 知几学习统计
    stats = zhiji.get_stats()
    print(f"\n  知几学习统计:")
    print(f"    同义词组: {len(stats['synonyms_learned'])}")
    for k, v in stats['synonyms_learned'].items():
        print(f"      {k} → {v}")
    print(f"    校准应用次数: {stats['calibrations_applied']}")
    print(f"    已知位置经验: {len(stats['object_locations'])}种物体")

    # 知耻学习统计
    zhichi_stats = zhichi.get_stats()
    print(f"\n  知耻学习统计:")
    print(f"    失败分析数: {zhichi_stats['failures_observed']}")
    print(f"    错拿排除映射: {len(zhichi_stats.get('wrong_take_map', {}))}条")
    for k, v in zhichi_stats.get('wrong_take_map', {}).items():
        print(f"      {k} → 排除 {v}")
    print(f"    否定先验: {len(zhichi_stats.get('negative_priors', {}))}条")
    for k, v in zhichi_stats.get('negative_priors', {}).items():
        print(f"      {k} → {v}")
    if 'bottleneck_phases' in zhichi_stats:
        print(f"    瓶颈阶段统计: {zhichi_stats['bottleneck_phases']}")
    if 'open_priority_learned' in zhichi_stats:
        print(f"    open优先学习: {zhichi_stats['open_priority_learned']}")

    # 知耻经验汇总
    print(f"\n  知耻经验: fails_analyzed={zhichi_stats['failures_observed']}, "
          f"wrong_takes={len(zhichi_stats.get('wrong_take_map', {}))}, "
          f"neg_priors={len(zhichi_stats.get('negative_priors', {}))}")

    by_type = defaultdict(list)
    for r in results:
        by_type[r.get('task_type_real', '?')].append(r)
    print(f"\n  按类型:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        print(f"    {t:45s}: {tw:2d}/{len(rs):2d} ({tw/len(rs)*100:5.1f}%)")

    # 保存
    output = {
        'config': {'agent': 'V10', 'zhiji_learning': True, 'zhichi_learning': True, 'pddl': False},
        'metrics': {
            'total': len(results), 'won': total_wins,
            'rate': total_wins / len(results),
            'type_accuracy': type_matches / len(results),
            'elapsed': elapsed,
        },
        'zhiji_stats': stats,
        'zhichi_stats': zhichi_stats,
        'by_task_type': {
            t: {'total': len(rs), 'won': sum(1 for r in rs if r['won']),
                'rate': sum(1 for r in rs if r['won']) / len(rs)}
            for t, rs in sorted(by_type.items())
        },
        'results': results,
    }
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='all', choices=['single', 'all'])
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('-n', '--num', type=int, default=0)
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--save-exp', type=str, default='',
                        help='实验后保存经验到指定前缀(生成 PREFIX_zhiji.json + PREFIX_zhichi.json)')
    parser.add_argument('--load-exp', type=str, default='',
                        help='实验前加载经验(读取 PREFIX_zhiji.json + PREFIX_zhichi.json)')
    parser.add_argument('--output', type=str, default='ylyw_agent_v10_results.json',
                        help='结果输出文件名')
    args = parser.parse_args()

    print("Creating env...")
    env = ALFWorldOfficial(split="valid_unseen")
    agent = YLYWAgentV10(verbose=args.verbose, use_oracle_type=False)
    zhiji = ZhijiLearning(verbose=args.verbose)
    zhichi = ZhichiLearning(verbose=args.verbose)

    # 加载先前积累的经验
    if args.load_exp:
        import os
        zhiji_path = f'{args.load_exp}_zhiji.json'
        zhichi_path = f'{args.load_exp}_zhichi.json'
        if os.path.exists(zhiji_path):
            zhiji.load_experience(zhiji_path)
            print(f"  ✅ 加载知几经验: {zhiji_path} ({zhiji.games_played}局)")
        else:
            print(f"  ⚠️ 知几经验文件不存在: {zhiji_path}")
        if os.path.exists(zhichi_path):
            zhichi.load_experience(zhichi_path)
            print(f"  ✅ 加载知耻经验: {zhichi_path} ({zhichi.failures_observed}局失败)")
        else:
            print(f"  ⚠️ 知耻经验文件不存在: {zhichi_path}")

    if args.mode == 'single':
        r = run_single(env, args.game, agent, zhiji, zhichi, verbose=True)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        run_all(env, agent, zhiji, zhichi, verbose=args.verbose,
                max_games=args.num if args.num > 0 else 0,
                output_file=args.output)

    # 保存经验
    if args.save_exp:
        zhiji.save_experience(f'{args.save_exp}_zhiji.json')
        zhichi.save_experience(f'{args.save_exp}_zhichi.json')
        print(f"  ✅ 经验已保存: {args.save_exp}_zhiji.json, {args.save_exp}_zhichi.json")

    env.close()
