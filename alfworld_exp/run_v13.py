#!/usr/bin/env python3
"""
运行V13 Agent — 递归YLYW六爻驱动逐步决策

替换V10的硬编码TASK_PLANS，用YLYW语义理解+六爻模糊推理代替。
无学习模块，零样本运行。
"""

import sys, os, json, time
os.environ['TMPDIR'] = f'/home/lijinhan/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None
_tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

# patch fast_downward
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
from ylyw_agent_v13 import YLYWAgentV13

MAX_STEPS = 50

def run_single(env, game_idx, agent, verbose=False):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    
    # 从task_desc解析器获取任务类型（跟V10一样）
    from task_desc_parser import parse_task_desc
    parsed = parse_task_desc(task_desc)
    use_type = parsed['task_type']
    
    # 获取PDDL参数
    pddl = info.get('pddl_params', {})
    
    agent.reset(task_desc=task_desc, task_type=use_type, pddl_params=pddl)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"  Desc: {task_desc}")
        print(f"  Targets: obj={agent.target_objects}, rec={agent.target_receps}")
        print(f"{'='*60}")
    
    won = False
    steps = 0
    
    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])
        action = agent.act(obs, cmds)
        
        if verbose:
            print(f"  Step {steps:2d}: {action}")
        
        obs, info = env.step(action)
        steps += 1
        won = info.get('won', False)
        
        if won:
            break
    
    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_parsed': use_type,
        'task_desc': task_desc,
        'steps': steps,
        'won': won,
    }

def run_all(env, agent, verbose=False, max_games=0, output_file='ylyw_agent_v13_results.json'):
    n = env.num_games if max_games <= 0 else min(max_games, env.num_games)
    results = []
    start = time.time()
    
    print(f"\nYLYW Agent V13 (六爻驱动) — {n} games")
    print("=" * 60)
    
    for i in range(n):
        try:
            result = run_single(env, i, agent, verbose=verbose)
            results.append(result)
            
            icon = '✅' if result['won'] else '❌'
            print(f"  {icon} #{i:3d} [{result['task_type_real'][:30]:30s}] steps={result['steps']:2d}  {result['task_desc'][:50]}")
            
            # 保存中间结果
            if (i + 1) % 10 == 0:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  ❌ #{i:3d} Error: {e}")
            import traceback
            traceback.print_exc()
    
    elapsed = time.time() - start
    won_count = sum(1 for r in results if r['won'])
    total = len(results)
    
    # 按类型统计
    from collections import defaultdict
    by_type = defaultdict(lambda: {'total': 0, 'won': 0})
    for r in results:
        t = r['task_type_real']
        by_type[t]['total'] += 1
        if r['won']:
            by_type[t]['won'] += 1
    
    print(f"\n{'='*60}")
    print(f"V13 结果汇总 ({total} games, {elapsed:.1f}s)")
    print(f"{'='*60}")
    for t, d in sorted(by_type.items()):
        pct = d['won'] / d['total'] * 100 if d['total'] > 0 else 0
        print(f"  {t:35s} {d['won']:3d}/{d['total']:2d} ({pct:5.1f}%)")
    print(f"  {'总计':35s} {won_count:3d}/{total:2d} ({won_count/total*100:.1f}%)")
    
    # 保存结果
    output = {
        'agent': 'YLYWAgentV13',
        'games': total,
        'won': won_count,
        'rate': won_count / total,
        'elapsed': elapsed,
        'by_type': {t: {'total': d['total'], 'won': d['won'], 'rate': d['won']/d['total']} for t, d in by_type.items()},
        'results': results,
    }
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {output_file}")
    
    return output

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    parser.add_argument('--max_games', type=int, default=0, help='最大游戏数')
    parser.add_argument('--output', default='ylyw_agent_v13_results.json', help='输出文件')
    args = parser.parse_args()
    
    env = ALFWorldOfficial()
    agent = YLYWAgentV13(verbose=args.verbose)
    
    run_all(env, agent, verbose=args.verbose, max_games=args.max_games, output_file=args.output)
