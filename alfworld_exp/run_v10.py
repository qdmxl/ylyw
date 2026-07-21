#!/usr/bin/env python3
"""
运行V10 Agent（V9 + 知耻学习 + 爻参数在线微调）

三层学习体系：
- 知几(zhiji): 从成功/所有轨迹中学习同义词/位置先验/场景结构
- 知耻(zhichi): 从失败轨迹中学习错拿排除/否定先验/瓶颈/open优先
- 爻调(yao_tune): 在每局的抓取/释放过程中实时微调爻参数

三者协同：知几(正向先验) + 爻调(局内快速适应) + 知耻(负向记忆)
爻参数是抓取/释放阶段的实时自适应机制。
"""
import sys, os, json, time, argparse, re
from collections import defaultdict

# 确保TMPDIR设置在安全位置（/tmp有usrquota限制导致Disk quota exceeded）
# Python的tempfile.gettempdir()缓存了TMPDIR，所以import前就要设置
import tempfile as _tf
os.environ['TMPDIR'] = f'/home/lijinhan/.tmp_alfworld'
_tf.tempdir = None  # 清除缓存
_tf.gettempdir()  # 重新读取TMPDIR
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

# 同时patch fast_downward.interface.load_lib 禁止往/tmp复制.so
import fast_downward.interface as _fd_intf
import ctypes as _ctypes
_FD_CACHE = [None]
def _patched_fd_load():
    if _FD_CACHE[0] is not None:
        return _FD_CACHE[0]
    so = str(_fd_intf.DOWNWARD_LIB_PATH)
    _fd_intf._lib = _fd_intf.cdll.LoadLibrary(so)
    lib = _fd_intf._lib
    lib.load_sas.argtypes = [_fd_intf.c_char_p]
    lib.load_sas.restype = None
    lib.load_sas_replan.argtypes = [_fd_intf.c_char_p]
    lib.load_sas_replan.restype = None
    lib.cleanup.argtypes = []
    lib.cleanup.restype = None
    lib.get_applicable_operators_count.argtypes = []
    lib.get_applicable_operators_count.restype = _fd_intf.c_int
    lib.get_applicable_operators.argtypes = [_fd_intf.POINTER(_fd_intf.Operator)]
    lib.get_applicable_operators.restype = None
    lib.get_state_size.argtypes = []
    lib.get_state_size.restype = _fd_intf.c_int
    lib.get_state.argtypes = [_fd_intf.POINTER(_fd_intf.Atom)]
    lib.get_state.restype = None
    lib.apply_operator.argtypes = [_fd_intf.c_int, _fd_intf.POINTER(_fd_intf.Atom)]
    lib.apply_operator.restype = _fd_intf.c_int
    lib.check_goal.argtypes = []
    lib.check_goal.restype = _fd_intf.c_bool
    lib.solve.argtypes = [_fd_intf.c_bool]
    lib.solve.restype = _fd_intf.c_bool
    lib.solve_sas.argtypes = [_fd_intf.c_char_p, _fd_intf.c_bool]
    lib.solve_sas.restype = _fd_intf.c_bool
    lib.replan.argtypes = [_fd_intf.c_bool]
    lib.replan.restype = _fd_intf.c_bool
    lib.get_last_plan_length.argtypes = []
    lib.get_last_plan_length.restype = _fd_intf.c_int
    lib.get_last_plan.argtypes = [_fd_intf.POINTER(_fd_intf.Operator)]
    lib.get_last_plan.restype = None
    lib.check_solution.argtypes = [_fd_intf.c_int, _fd_intf.POINTER(_fd_intf.Operator)]
    lib.check_solution.restype = _fd_intf.c_bool
    _FD_CACHE[0] = lib
    return lib
_fd_intf.load_lib = _patched_fd_load

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v10 import YLYWAgentV10
from zhiji_learning import ZhijiLearning
from zhichi_learning import ZhichiLearning
from yao_online_tuner import YaoOnlineTuner

MAX_STEPS = 50


def run_single(env, game_idx, agent, zhiji, zhichi, yao_tuner=None, verbose=False):
    """运行单个游戏，并收集轨迹供知几/知耻/爻调学习"""
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
    # 注入爻参数在线微调器
    agent._yao_tuner = yao_tuner

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


def run_all(env, agent, zhiji, zhichi, yao_tuner=None, verbose=False, max_games=0, output_file='ylyw_agent_v10_results.json'):
    """顺序执行全部游戏（知几+知耻+爻调学习模式）"""
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    results = []
    start = time.time()

    print(f"\nYLYW Agent V10 (知几+知耻+爻调) — {n} games")
    print("=" * 60)

    for i in range(n):
        try:
            r = run_single(env, i, agent, zhiji, zhichi, yao_tuner=yao_tuner, verbose=verbose)
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
    print(f"  V10 Results (知几+知耻+爻调)")
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

    # 爻参数统计
    if yao_tuner is not None:
        yao_stats = yao_tuner.get_stats()
        rcp = yao_stats.get('release_confidence_pairs', {})
        print(f"\n  爻参数在线微调统计:")
        print(f"    释放爻正分对数: {rcp.get('positive', 0)}")
        print(f"    释放爻负分对数: {rcp.get('negative', 0)}")
        print(f"    释放爻排除对数: {rcp.get('blocked', 0)}")
        print(f"    抓持爻对数: {yao_stats.get('take_confidence_pairs', 0)}")
        rfc = yao_stats.get('release_fail_counts', {})
        if rfc:
            print(f"    释放累计失败: {len(rfc)}对")
            for k, v in sorted(rfc.items(), key=lambda x: -x[1])[:5]:
                print(f"      {k} × {v}次")
        rsc = yao_stats.get('release_success_counts', {})
        if rsc:
            print(f"    释放累计成功: {len(rsc)}对")
            for k, v in sorted(rsc.items(), key=lambda x: -x[1])[:5]:
                print(f"      {k} × {v}次")

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
    parser.add_argument('--save-yao', type=str, default='',
                        help='实验后保存爻参数经验(生成 PREFIX_yao.json)')
    parser.add_argument('--load-yao', type=str, default='',
                        help='实验前加载爻参数经验(读取 PREFIX_yao.json)')
    args = parser.parse_args()

    print("Creating env...")
    env = ALFWorldOfficial(split="valid_unseen")
    agent = YLYWAgentV10(verbose=args.verbose, use_oracle_type=False)
    zhiji = ZhijiLearning(verbose=args.verbose)
    zhichi = ZhichiLearning(verbose=args.verbose)
    yao_tuner = YaoOnlineTuner(verbose=args.verbose)

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
    
    # 加载爻参数经验
    if args.load_yao:
        import os
        yao_path = f'{args.load_yao}_yao.json'
        if os.path.exists(yao_path):
            yao_tuner.load_experience(yao_path)
            print(f"  ✅ 加载爻参数经验: {yao_path}")
        else:
            print(f"  ⚠️ 爻参数经验文件不存在: {yao_path}")
    
    # 用知几经验播种爻参数（跨局经验→初始爻参数，只在首次运行前做一次）
    if not args.load_yao:
        seed_count = 0
        for obj_base, loc_counts in zhiji.object_location_counts.items():
            total = sum(loc_counts.values())
            if total == 0:
                continue
            for loc_base, count in loc_counts.items():
                ratio = count / total
                if ratio >= 0.3:
                    current = yao_tuner.get_release_score(obj_base, loc_base)
                    if current == 0.0:
                        boost = 1.0 + ratio * 2.0
                        yao_tuner.release_confidence[obj_base][loc_base] += boost
                        seed_count += 1
                    elif current < 0:
                        boost = ratio * 2.0
                        yao_tuner.release_confidence[obj_base][loc_base] += boost
                        seed_count += 1
        if seed_count > 0 and args.verbose:
            print(f"  🌱 知几经验播种 {seed_count} 个爻参数")

    if args.mode == 'single':
        r = run_single(env, args.game, agent, zhiji, zhichi, yao_tuner=yao_tuner, verbose=True)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        run_all(env, agent, zhiji, zhichi, yao_tuner=yao_tuner, verbose=args.verbose,
                max_games=args.num if args.num > 0 else 0,
                output_file=args.output)

    # 保存经验
    if args.save_exp:
        zhiji.save_experience(f'{args.save_exp}_zhiji.json')
        zhichi.save_experience(f'{args.save_exp}_zhichi.json')
        print(f"  ✅ 经验已保存: {args.save_exp}_zhiji.json, {args.save_exp}_zhichi.json")
    if args.save_yao:
        yao_tuner.save_experience(f'{args.save_yao}_yao.json')
        print(f"  ✅ 爻参数已保存: {args.save_yao}_yao.json")

    env.close()
