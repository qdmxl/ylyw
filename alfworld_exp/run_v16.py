#!/usr/bin/env python3
"""
Run V16 - 卦象驱动场景记忆测试
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'language'))

from ylyw_agent_v16 import YLYWAgentV16

try:
    from alfworld_wrapper import ALFWorldWrapper
except ImportError:
    print("需要 alfworld_wrapper.py（与 run_v15 同目录）")
    sys.exit(1)


def run_single(task_desc: str, task_type: str, verbose: bool = True) -> dict:
    """运行单场游戏"""
    agent = YLYWAgentV16(verbose=verbose)
    env = ALFWorldWrapper()
    
    # 获取游戏
    game_file = env.get_game(task_type)
    if not game_file:
        return {'won': False, 'steps': 0, 'error': 'no_game'}
    
    obs, info = env.reset(game_file)
    agent.reset(task_desc, task_type)
    
    max_steps = 50
    for step in range(1, max_steps + 1):
        action = agent.act(obs)
        
        if verbose:
            print(f"  → {action}")
        
        obs, reward, done, info = env.step([action])
        obs_text = obs[0] if isinstance(obs, (list, tuple)) else obs
        
        if isinstance(obs_text, dict):
            obs_text = obs_text.get('observation', str(obs_text))
        
        agent.update(action, obs_text)
        
        if done or agent.is_done(obs_text):
            if verbose:
                print(f"  {'✅成功' if reward and reward[0] > 0 else '❌失败'} (步数={step})")
            return {'won': bool(reward and reward[0] > 0), 'steps': step}
    
    if verbose:
        print(f"  ❌超时 (步数={max_steps})")
    return {'won': False, 'steps': max_steps}


def run_batch(count: int = 10, task_type: str = None, verbose: bool = False):
    """批量运行"""
    from alfworld_wrapper import ALFWorldWrapper
    env = ALFWorldWrapper()
    
    results = {'total': 0, 'won': 0, 'by_type': {}}
    games = env.list_games(task_type)
    
    if not games:
        print("没有找到游戏")
        return results
    
    print(f"共 {len(games)} 个场景，运行 {min(count, len(games))} 场")
    
    for i, (game, desc, ttype) in enumerate(games[:count]):
        print(f"[{i+1}/{min(count, len(games))}] {desc}")
        
        result = run_single(desc, ttype, verbose=verbose)
        
        results['total'] += 1
        if result['won']:
            results['won'] += 1
        results['by_type'].setdefault(ttype, {'total': 0, 'won': 0})
        results['by_type'][ttype]['total'] += 1
        if result['won']:
            results['by_type'][ttype]['won'] += 1
        
        print(f"  {'✅' if result['won'] else '❌'} ({result['steps']}步) "
              f"累计: {results['won']}/{results['total']} ({results['won']/results['total']*100:.1f}%)")
    
    print(f"\n=== 最终: {results['won']}/{results['total']} ({results['won']/results['total']*100:.1f}%) ===")
    for t, s in sorted(results['by_type'].items()):
        print(f"  {t}: {s['won']}/{s['total']} ({s['won']/s['total']*100:.1f}%)")
    
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=5, help='运行场次')
    parser.add_argument('--type', type=str, default=None, help='任务类型')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    args = parser.parse_args()
    
    run_batch(args.count, args.type, args.verbose)
