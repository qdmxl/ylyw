#!/usr/bin/env python3
"""
V17 诊断实验 — 详细记录每个 game 的动作、意图、状态变化
用于分析失败 root cause，只跑前 N 局
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'language'))

os.environ['TMPDIR'] = f'{os.environ["HOME"]}/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']):
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_agent_v17 import YLYWAgentV17, ObsParser

MAX_STEPS = 50

def diagnose_game(env, game_idx, agent, verbose=False):
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    agent.reset(task_desc=task_desc, task_type=task_type_real)
    
    won = False
    timeline = []
    last_container_tries = {}  # 位置类型 → 尝试次数
    
    for step in range(MAX_STEPS):
        admissible = info.get('admissible_commands', ['look'])
        
        # 记录意图涌现前的状态
        intent_before, confidence = agent._decide_intent()
        
        # 动作选择
        action = agent.act_with_admissible(obs, admissible)
        
        # 更新前的状态快照
        holding_before = agent.holding
        loc_before = agent.current_location
        processed_before = agent.processed
        taken_before = set(agent._taken_objects)
        visited_before = len(agent.visited)
        
        step_info = {
            'step': step,
            'intent': intent_before,
            'confidence': round(confidence, 3),
            'action': action,
            'loc_before': loc_before,
            'holding_before': holding_before,
            'processed_before': processed_before,
            'taken_before': list(taken_before),
            'visited_count': visited_before,
        }
        
        # 环境执行
        obs, info = env.step(action)
        
        # 更新
        agent.update(action, obs)
        
        # 更新后状态
        step_info['holding_after'] = agent.holding
        step_info['loc_after'] = agent.current_location
        step_info['processed_after'] = agent.processed
        step_info['taken_after'] = list(agent._taken_objects)
        
        # 关键事件标记
        events = []
        ol = obs.lower()
        if 'you pick up' in ol or 'you take' in ol:
            events.append('PICK_UP')
        if 'you put' in ol or 'you place' in ol or 'you move' in ol:
            events.append('PUT_DOWN')
        if 'you heat' in ol or 'heat' in ol:
            events.append('HEAT')
        if 'you cool' in ol or 'cool' in ol:
            events.append('COOL')
        if 'you clean' in ol or 'clean' in ol:
            events.append('CLEAN')
        if 'nothing happens' in ol:
            events.append('NOTHING')
        if "can't" in ol or "cannot" in ol:
            events.append('CANT')
        if 'you are carrying nothing' in ol:
            events.append('EMPTY_HAND')
        
        # 跟踪容器尝试
        if action.startswith('go to '):
            loc_type = re.sub(r'\s+\d+$', '', action[6:]).strip()
            if loc_type not in last_container_tries:
                last_container_tries[loc_type] = 0
            # 找出编号
            m = re.search(r'(\d+)$', action[6:])
            num = int(m.group(1)) if m else 1
            last_container_tries[loc_type] = num
        
        # 动作后观察是否有新物体
        visible_objects = []
        for m in re.finditer(r'on the (.+?), you see (.+?)(?:\.|$)', ol):
            visible_objects.append({'container': m.group(1).strip(), 'objects': m.group(2).strip()})
        
        if action.startswith('open '):
            events.append('OPEN')
        if action.startswith('take '):
            events.append('TAKE_CMD')
        
        step_info['events'] = events
        step_info['obs_snippet'] = obs[:120] if verbose else ''
        
        timeline.append(step_info)
        
        if info.get('won', False):
            won = True
            break
    
    # 诊断总结
    summary = {
        'game_idx': game_idx,
        'task_type': task_type_real,
        'task_desc': task_desc,
        'won': won,
        'steps': len(timeline),
        'max_steps': MAX_STEPS,
        'obj_en': agent.obj_en,
        'target_en': agent.target_en,
        'preproc_en': agent.preproc_en,
    }
    
    # 失败分类
    if not won:
        summary['failure_category'] = categorize_failure(timeline, agent, task_type_real)
    
    return summary, timeline


def categorize_failure(timeline, agent, task_type):
    """分类失败模式"""
    # 1. 从未拿过目标物体
    took_anything = any('PICK_UP' in s['events'] for s in timeline)
    if not took_anything:
        # 细分：是没找到物体还是导航瞎逛
        open_attempts = sum(1 for s in timeline if 'OPEN' in s['events'])
        go_to_count = sum(1 for s in timeline if s['action'].startswith('go to '))
        if go_to_count > 20:
            return '探索循环-从未拿过物体(导航过度)'
        elif open_attempts > 5:
            return '探索循环-开了容器但没找到目标物体'
        else:
            return '探索循环-从未拿过物体'
    
    # 2. 拿过但没处理 (heat/cool/clean)
    if task_type in ('pick_heat_then_place_in_recep', 'pick_cool_then_place_in_recep',
                     'pick_clean_then_place_in_recep'):
        processed = any(s['processed_after'] for s in timeline)
        if not processed:
            return '拿了物体但没完成预处理'
    
    # 3. 拿过但没放到目标容器
    put_down = any('PUT_DOWN' in s['events'] for s in timeline)
    if not put_down and took_anything:
        held_at_end = timeline[-1]['holding_after'] is not None
        return '拿了物体但放到游戏结束还没放下'
    
    # 4. pick_two_obj 只拿了一个
    if task_type == 'pick_two_obj_and_place':
        taken_count = len(timeline[-1]['taken_after']) if timeline else 0
        if taken_count < 2:
            return f'两个物体只拿了{taken_count}个'
    
    # 5. 放错位置
    return '其他失败'


if __name__ == '__main__':
    max_games = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 10
    
    env = ALFWorldOfficial(split='valid_unseen')
    n = min(max_games, env.num_games)
    
    agent = YLYWAgentV17(verbose=False)
    
    print(f"V17 诊断实验: {n} games\n{'='*50}")
    
    all_results = {'won': [], 'failed': [], 'summaries': []}
    
    for i in range(n):
        summary, timeline = diagnose_game(env, i, agent)
        all_results['summaries'].append(summary)
        
        if summary['won']:
            all_results['won'].append(summary)
            print(f"  #{i:3d} ✅ [{summary['task_type'][:30]:30s}] {summary['steps']:2d}步")
        else:
            all_results['failed'].append(summary)
            print(f"  #{i:3d} ❌ [{summary['task_type'][:30]:30s}] {summary['steps']:2d}步 → {summary.get('failure_category','?')}")
        
        # 打印失败 game 的详细动作序列
        if not summary['won']:
            print(f"      任务: {summary['task_desc'][:80]}")
            print(f"      目标物体={summary['obj_en']} 目标容器={summary['target_en']} 预处理={summary['preproc_en']}")
            for s in timeline:
                events_str = ' '.join(s['events'])
                if events_str:
                    print(f"      [{s['step']:2d}] {s['intent']:8s} → {s['action']:40s} | {events_str:30s} | hold={s['holding_after']}")
    
    # 汇总
    print(f"\n{'='*60}")
    won_count = len(all_results['won'])
    failed_count = len(all_results['failed'])
    print(f"V17 诊断: {won_count}/{n} = {won_count/n*100:.1f}%")
    
    from collections import Counter
    cats = Counter(s.get('failure_category','?') for s in all_results['failed'])
    print(f"\n失败分类:")
    for cat, cnt in cats.most_common():
        print(f"  {cnt:3d}/{failed_count} ({cnt/failed_count*100:5.1f}%): {cat}")
    
    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ylyw_agent_v17_diagnose.json')
    # 精简 timeline（只保留关键字段）
    for s in all_results['summaries']:
        s.pop('timeline', None)
    with open(outfile, 'w') as f:
        json.dump({'n': n, 'won': won_count, 'failed': failed_count, 
                   'summaries': all_results['summaries']}, f, indent=2, default=str)
    print(f"\n诊断结果保存: {outfile}")
