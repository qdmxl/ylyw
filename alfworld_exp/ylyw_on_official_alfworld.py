#!/usr/bin/env python3
"""
YLYW on Official ALFWorld (方案B: per-game env)

使用修复后的 ALFWorldOfficial wrapper，每个游戏创建独立的 TextWorld 环境，
确保 reset(game_idx) 一定加载对应的游戏场景。

用法:
  python3 ylyw_on_official_alfworld.py --mode single --game 0 --verbose
  python3 ylyw_on_official_alfworld.py --mode all --num 134
  python3 ylyw_on_official_alfworld.py --mode all   # 跑全部134个
"""

import sys
import os
import json
import argparse
import time
from collections import defaultdict
from typing import List, Tuple, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alfworld_official_wrapper import ALFWorldOfficial
from ylyw_semantic_parser_cn import YLYWChineseSemanticParser, OBJECT_NOUNS_CN, LOCATION_NOUNS_CN, TOOL_NOUNS_CN
from chinese_bridge import ChineseBridge

MAX_STEPS = 50

# 英文动作类型（AlfredTWEnv输出的命令格式）
ACTION_TYPES = ['go to', 'take', 'put', 'open', 'close',
                'clean', 'heat', 'cool', 'slice', 'use',
                'look', 'inventory', 'examine']

# 中文子目标模板
SUBGOAL_TEMPLATES = {
    'look_at_obj_in_light':           [['go to'], ['take'], ['go to'], ['use']],
    'pick_and_place_simple':          [['go to'], ['take'], ['go to'], ['put']],
    'pick_clean_then_place_in_recep': [['go to'], ['take'], ['go to'], ['clean'], ['go to'], ['put']],
    'pick_cool_then_place_in_recep':  [['go to'], ['take'], ['go to'], ['cool'], ['go to'], ['put']],
    'pick_heat_then_place_in_recep':  [['go to'], ['take'], ['go to'], ['heat'], ['go to'], ['put']],
    'pick_two_obj_and_place':         [['go to'], ['take'], ['go to'], ['put'],
                                        ['go to'], ['take'], ['go to'], ['put']],
    'pick_and_place_with_movable_recep': [['go to'], ['take'], ['go to'], ['take'], ['go to'], ['put']],
}

# 中英文实体映射
CN_EN_MAP = {
    '灯': ['desklamp', 'floorlamp', 'lamp', 'light'],
    '灯光': ['desklamp', 'floorlamp', 'lamp', 'light'],
    '台灯': ['desklamp'],
    '落地灯': ['floorlamp'],
    '微波炉': ['microwave'],
    '冰箱': ['fridge', 'refrigerator'],
    '水槽': ['sinkbasin', 'sink'],
    '灶台': ['stoveburner', 'stove'],
    '时钟': ['clock', 'alarmclock'],
    '杯子': ['mug', 'cup', 'glass'],
    '桌子': ['table', 'desk'],
    '书桌': ['desk'],
    '橱柜': ['cabinet'],
    '抽屉': ['drawer'],
    '瓶子': ['bottle'],
    '书架': ['shelf', 'bookshelf'],
    '沙发': ['sofa'],
    '床': ['bed'],
    '椅子': ['chair'],
    '保险箱': ['safe'],
    '垃圾桶': ['garbagecan', 'trash', 'garbage', 'bin'],
    '架子': ['shelf'],
    '毛巾': ['towel'],
    '布': ['cloth'],
    '海绵': ['sponge'],
    '肥皂': ['soap', 'soapbar'],
    '书': ['book'],
    '苹果': ['apple'],
    '土豆': ['potato'],
    '鸡蛋': ['egg'],
    '面包': ['bread'],
    '碗': ['bowl'],
    '盘子': ['plate'],
    '锅': ['pan', 'pot'],
    '刀': ['knife', 'butterknife'],
    '叉子': ['fork'],
    '勺子': ['spoon'],
    '花瓶': ['vase'],
    '雕像': ['statue'],
    '手机': ['cellphone'],
    '遥控器': ['remotecontrol', 'remote'],
    '钥匙链': ['keychain'],
    '信用卡': ['creditcard'],
    '球棒': ['baseballbat', 'bat'],
    '篮球': ['basketball'],
    '枕头': ['pillow'],
    '笔记本电脑': ['laptop', 'computer'],
    '盒子': ['box'],
    '蜡烛': ['candle'],
    '纸巾盒': ['tissuebox'],
    '光盘': ['cd'],
    '报纸': ['newspaper'],
    '马桶搋子': ['plunger'],
    '盐': ['saltshaker', 'salt'],
    '胡椒': ['peppershaker', 'pepper'],
    '马桶': ['toilet'],
    '浴缸': ['bathtub'],
    '烤箱': ['oven'],
    '烤面包机': ['toaster'],
    '咖啡机': ['coffeemachine'],
    '台面': ['countertop', 'counter'],
    '柜台': ['counter', 'countertop'],
    '茶几': ['coffeetable'],
    '餐桌': ['diningtable'],
    '床头柜': ['sidetable'],
    '电视柜': ['tvstand'],
    '梳妆台': ['dresser'],
    '生菜': ['lettuce'],
    '番茄': ['tomato'],
    '壶': ['kettle'],
    '笔': ['pen', 'pencil'],
    '铲子': ['spatula'],
    '钢丝球': ['scrubbrush'],
    '喷壶': ['spraybottle'],
    '闹钟': ['alarmclock'],
    '泰迪熊': ['teddybear'],
    '手巾': ['handtowel'],
}


class YLYWOfficialAgent:
    """在官方ALFWorld上运行的YLYW中文Agent"""

    def __init__(self, verbose=False, use_oracle_type=True):
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type
        self.cn_parser = YLYWChineseSemanticParser()
        self.current_phase = 0
        self._cn_result = None
        self._target_objects_en = []  # 从task_desc解析出的英文目标物体
        self._target_recep_en = []    # 从task_desc解析出的英文目标容器
        self._visited_locations = set()  # 已访问位置
        self._failed_actions = []     # 失败的动作记录

    def infer_task_type(self, task_desc: str, ground_truth: str = None) -> str:
        """推断任务类型"""
        if self.use_oracle_type and ground_truth:
            self._cn_result = self.cn_parser.parse_task_desc(task_desc)
            self._extract_english_targets(task_desc, ground_truth)
            return ground_truth
        result = self.cn_parser.parse_task_desc(task_desc)
        self._cn_result = result
        inferred = result['task_type']
        self._extract_english_targets(task_desc, inferred)
        return inferred

    def _extract_english_targets(self, task_desc: str, task_type: str):
        """从英文task_desc中直接提取目标物体和容器名"""
        desc_lower = task_desc.lower()
        self._target_objects_en = []
        self._target_recep_en = []

        # 常见物体名
        all_objects = [
            'alarmclock', 'apple', 'baseballbat', 'basketball', 'book', 'bottle',
            'bowl', 'box', 'bread', 'butterknife', 'candle', 'cd', 'cellphone',
            'cloth', 'creditcard', 'cup', 'dishsponge', 'egg', 'fork', 'glassbottle',
            'handtowel', 'kettle', 'keychain', 'knife', 'ladle', 'laptop', 'lettuce',
            'mug', 'newspaper', 'pan', 'papertowelroll', 'pen', 'pencil',
            'peppershaker', 'pillow', 'plate', 'plunger', 'pot', 'potato',
            'remotecontrol', 'saltshaker', 'scrubbrush', 'soapbar', 'soap',
            'spatula', 'spoon', 'spraybottle', 'statue', 'teddybear',
            'tissuebox', 'toiletpaper', 'tomato', 'towel', 'vase', 'watch',
            'winebottle',
        ]
        # 常见容器/位置
        all_receps = [
            'bathtub', 'bathtubbasin', 'bed', 'cabinet', 'cart', 'coffeemachine',
            'coffeetable', 'countertop', 'counter', 'desk', 'diningtable',
            'drawer', 'dresser', 'fridge', 'garbagecan', 'laundryhamper',
            'microwave', 'ottoman', 'safe', 'shelf', 'sidetable', 'sinkbasin',
            'sink', 'sofa', 'stoveburner', 'toilet', 'toilettable', 'tvstand',
        ]

        # 简单模式匹配
        for obj in all_objects:
            # 处理task_desc中的变体 (e.g., "soap bar" → "soapbar")
            if obj in desc_lower or obj.replace('bar', ' bar') in desc_lower:
                self._target_objects_en.append(obj)
            # 特殊处理: "clock" → "alarmclock"
            if obj == 'alarmclock' and 'clock' in desc_lower:
                if 'alarmclock' not in self._target_objects_en:
                    self._target_objects_en.append('alarmclock')
            if obj == 'remotecontrol' and 'remote' in desc_lower:
                if 'remotecontrol' not in self._target_objects_en:
                    self._target_objects_en.append('remotecontrol')

        for rec in all_receps:
            if rec in desc_lower or rec.replace('can', ' can') in desc_lower:
                self._target_recep_en.append(rec)
            if rec == 'garbagecan' and ('trash' in desc_lower or 'garbage' in desc_lower or 'bin' in desc_lower):
                if 'garbagecan' not in self._target_recep_en:
                    self._target_recep_en.append('garbagecan')
            if rec == 'countertop' and 'counter' in desc_lower:
                if 'countertop' not in self._target_recep_en:
                    self._target_recep_en.append('countertop')

    def reset_for_game(self):
        """每个游戏开始前重置Agent状态"""
        self.current_phase = 0
        self._visited_locations = set()
        self._failed_actions = []

    def _get_action_type(self, cmd: str) -> str:
        cmd_lower = cmd.strip().lower()
        for at in ACTION_TYPES:
            if cmd_lower.startswith(at):
                return at
        return ''

    def _entity_match_score(self, cmd: str) -> float:
        """计算命令与目标实体的匹配度（直接用英文匹配）"""
        score = 0.0
        cmd_lower = cmd.lower()

        # 英文目标物体匹配
        for obj in self._target_objects_en:
            if obj in cmd_lower:
                score += 3.0
            # 处理带数字后缀的情况: "plate 1" 包含 "plate"
            obj_base = obj.rstrip('0123456789 ')
            if obj_base and obj_base in cmd_lower:
                score += 2.0

        # 英文目标容器匹配
        for rec in self._target_recep_en:
            if rec in cmd_lower:
                score += 2.5
            rec_base = rec.rstrip('0123456789 ')
            if rec_base and rec_base in cmd_lower:
                score += 1.5

        # 中文实体匹配（补充）
        cn_args = (self._cn_result or {}).get('inferred_args', {})
        for obj in cn_args.get('objects', []):
            en_names = CN_EN_MAP.get(obj, [])
            for en in en_names:
                if en in cmd_lower:
                    score += 1.0
        for loc in cn_args.get('locations', []):
            en_names = CN_EN_MAP.get(loc, [])
            for en in en_names:
                if en in cmd_lower:
                    score += 0.8
        for tool in cn_args.get('tools', []):
            en_names = CN_EN_MAP.get(tool, [])
            for en in en_names:
                if en in cmd_lower:
                    score += 1.0

        return score

    def select_action(self, admissible_commands: List[str],
                      task_type: str, obs: str = "",
                      task_desc: str = "") -> str:
        """基于YLYW的动作选择"""
        subgoals = SUBGOAL_TEMPLATES.get(task_type,
                    [['go to'], ['take'], ['go to'], ['put']])

        phase = self.current_phase
        target_actions = subgoals[phase] if phase < len(subgoals) else ['go to']

        # 第一步：筛选匹配当前阶段的动作类型
        candidates = [c for c in admissible_commands
                      if self._get_action_type(c) in target_actions]

        # 如果没有匹配的候选，放宽到所有非look/inventory命令
        if not candidates:
            candidates = [c for c in admissible_commands
                          if self._get_action_type(c) not in ('look', 'inventory', 'examine', '')]
        if not candidates:
            candidates = admissible_commands

        # 第二步：评分排序
        scored = []
        for cmd in candidates:
            score = self._entity_match_score(cmd)
            at = self._get_action_type(cmd)

            # 动作类型匹配加分
            if at in target_actions:
                score += 1.0

            # 避免重复失败
            if cmd in self._failed_actions[-10:]:
                score -= 3.0

            # 避免重复访问已探索的位置（go to 阶段）
            if at == 'go to':
                loc = cmd.lower().replace('go to ', '').strip()
                if loc in self._visited_locations:
                    score -= 1.0

            # 阶段特化逻辑
            if phase == 0:
                # 第一步：去找目标物体 → 优先匹配物体所在位置
                pass  # 已由 _entity_match_score 处理
            elif at == 'take':
                # take 阶段：匹配目标物体名
                for obj in self._target_objects_en:
                    obj_base = obj.rstrip('0123456789 ')
                    if obj_base in cmd.lower():
                        score += 5.0
                        break
            elif at in ('put', 'move'):
                # put 阶段：优先匹配目标容器
                for rec in self._target_recep_en:
                    rec_base = rec.rstrip('0123456789 ')
                    if rec_base in cmd.lower():
                        score += 5.0
                        break
            elif at == 'use':
                # use 阶段（灯等工具）
                for en_list in [CN_EN_MAP.get('灯', []), CN_EN_MAP.get('台灯', [])]:
                    for en in en_list:
                        if en in cmd.lower():
                            score += 5.0
            elif at in ('clean', 'heat', 'cool'):
                # 操作阶段：匹配目标物体
                for obj in self._target_objects_en:
                    obj_base = obj.rstrip('0123456789 ')
                    if obj_base in cmd.lower():
                        score += 5.0
                        break

            scored.append((score, cmd))

        scored.sort(key=lambda x: -x[0])

        if self.verbose and scored:
            top3 = scored[:3]
            print(f"      Phase {phase}, target_actions={target_actions}")
            for s, c in top3:
                print(f"        {s:5.1f} | {c}")

        return scored[0][1] if scored else admissible_commands[0]

    def update_phase(self, action: str, obs: str, action_success: bool):
        """根据动作结果更新阶段"""
        at = self._get_action_type(action)

        if not action_success:
            self._failed_actions.append(action)
            return

        # 记录已访问位置
        if at == 'go to':
            loc = action.lower().replace('go to ', '').strip()
            self._visited_locations.add(loc)

        # 阶段推进逻辑
        subgoals = SUBGOAL_TEMPLATES.get(self._current_task_type,
                    [['go to'], ['take'], ['go to'], ['put']])
        if self.current_phase >= len(subgoals):
            return

        expected = subgoals[self.current_phase]

        if at in expected:
            # 对 go to 阶段：只有到达了"有用"的地方才推进
            if at == 'go to':
                obs_lower = obs.lower()
                # 如果观测中提到了目标物体，说明到了正确位置
                relevant = False
                for obj in self._target_objects_en:
                    obj_base = obj.rstrip('0123456789 ')
                    if obj_base in obs_lower:
                        relevant = True
                        break
                for rec in self._target_recep_en:
                    rec_base = rec.rstrip('0123456789 ')
                    if rec_base in obs_lower:
                        relevant = True
                        break
                # 灯、水槽、微波炉等工具位置
                tool_keywords = ['desklamp', 'floorlamp', 'sinkbasin', 'microwave',
                                 'fridge', 'stoveburner']
                for tk in tool_keywords:
                    if tk in obs_lower:
                        relevant = True
                        break
                if relevant:
                    self.current_phase += 1
                # 如果不相关，不推进（继续探索）
            else:
                # take/put/clean/heat/cool/use — 成功即推进
                self.current_phase += 1


def run_single_game(env: ALFWorldOfficial, game_idx: int,
                    agent: YLYWOfficialAgent, verbose: bool = False) -> Dict:
    """在官方ALFWorld上运行一个游戏"""
    agent.reset_for_game()

    obs, info = env.reset(game_idx=game_idx)

    task_desc = info.get('task_desc', '')
    task_type_real = info.get('task_type', '')
    scene = info.get('scene', {})
    gt_type = task_type_real if agent.use_oracle_type else None

    inferred_type = agent.infer_task_type(task_desc, ground_truth=gt_type)
    agent._current_task_type = inferred_type  # 供 update_phase 使用

    cn_result = agent._cn_result
    cn_task = cn_result['cn_task_desc'] if cn_result else task_desc

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"  EN: {task_desc}")
        print(f"  CN: {cn_task}")
        print(f"  Scene: {scene.get('floor_plan')} (#{scene.get('scene_num')})")
        print(f"  Inferred type: {inferred_type}")
        print(f"  Target objects: {agent._target_objects_en}")
        print(f"  Target receps: {agent._target_recep_en}")
        print(f"  Admissible ({len(info['admissible_commands'])})")
        print(f"{'='*60}")
        print(f"  Initial obs: {obs[:200]}...")

    history = []
    steps = 0
    won = False

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])

        action = agent.select_action(cmds, inferred_type, obs, task_desc)

        if verbose:
            print(f"  Step {steps:2d} [phase={agent.current_phase}]: {action}")

        obs, info = env.step(action)
        steps += 1
        history.append(action)

        won = info.get('won', False)
        action_success = info.get('action_success', True)

        if verbose:
            print(f"    → success={action_success}, won={won}")
            if len(obs) < 200:
                print(f"    obs: {obs}")
            else:
                print(f"    obs: {obs[:150]}...")

        agent.update_phase(action, obs, action_success)

        if won:
            break

    if verbose:
        print(f"\n  {'✅ WON' if won else '❌ LOST'} in {steps} steps")

    return {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_inferred': inferred_type,
        'type_correct': inferred_type == task_type_real,
        'task_desc': task_desc,
        'cn_task': cn_task[:80] if cn_task else '',
        'scene': scene.get('floor_plan', ''),
        'steps': steps,
        'won': won,
        'history': history,
    }


def run_all_games(env: ALFWorldOfficial, agent: YLYWOfficialAgent,
                  verbose: bool = False, max_games: int = 0):
    """跑全部游戏"""
    results = []
    n = env.num_games
    if 0 < max_games < n:
        n = max_games

    print(f"\n{'='*60}")
    print(f"Running {n}/{env.num_games} games on Official ALFWorld (方案B)")
    print(f"{'='*60}")
    start = time.time()

    for i in range(n):
        try:
            result = run_single_game(env, i, agent, verbose=verbose)
        except Exception as e:
            print(f"  ⚠️ Game {i} error: {e}")
            result = {
                'game_idx': i,
                'task_type_real': 'error',
                'task_type_inferred': 'error',
                'type_correct': False,
                'task_desc': str(e),
                'steps': 0,
                'won': False,
                'error': str(e),
            }
        results.append(result)

        wins = sum(1 for r in results if r['won'])
        elapsed = time.time() - start
        print(f"  [{i+1:3d}/{n}] Game {i:3d}: {'✅' if result['won'] else '❌'} "
              f"({result.get('task_type_real','?'):40s}) {result.get('steps',0):2d}步 "
              f"[累计: {wins}/{i+1} = {wins/(i+1)*100:.1f}%] [{elapsed:.0f}s]")

    elapsed = time.time() - start
    total_wins = sum(1 for r in results if r['won'])
    total_steps = sum(r.get('steps', 0) for r in results)
    type_correct = sum(1 for r in results if r.get('type_correct', False))

    print(f"\n{'='*60}")
    print(f"  Official ALFWorld Results (方案B: per-game env)")
    print(f"{'='*60}")
    print(f"  Total:      {len(results)}")
    print(f"  Won:        {total_wins}")
    print(f"  Success:    {total_wins/len(results)*100:.1f}%")
    print(f"  Type Acc:   {type_correct/len(results)*100:.1f}%")
    print(f"  Avg Steps:  {total_steps/len(results):.1f}")
    print(f"  Elapsed:    {elapsed:.1f}s")

    # 按类型统计
    by_type = defaultdict(list)
    for r in results:
        by_type[r.get('task_type_real', 'unknown')].append(r)
    print(f"\n  By Task Type:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        ts = sum(r.get('steps', 0) for r in rs)
        print(f"    {t:45s}: {tw:2d}/{len(rs):2d} ({tw/len(rs)*100:5.1f}%) avg={ts/len(rs):.1f}步")

    # 保存结果
    output = {
        'config': {
            'model': 'YLYW Zero-Shot (Official Sim, 方案B)',
            'simulator': 'AlfredTWEnv + per-game env',
            'split': env.split,
            'max_steps': MAX_STEPS,
            'agent_type': 'YLYWOfficialAgent',
            'oracle_type': agent.use_oracle_type,
        },
        'metrics': {
            'total_tasks': len(results),
            'won': total_wins,
            'lost': len(results) - total_wins,
            'success_rate': total_wins / len(results),
            'type_accuracy': type_correct / len(results),
            'avg_steps': total_steps / len(results),
            'total_steps': total_steps,
            'elapsed_seconds': elapsed,
        },
        'by_task_type': {
            t: {
                'total': len(rs),
                'won': sum(1 for r in rs if r['won']),
                'rate': sum(1 for r in rs if r['won']) / len(rs),
                'avg_steps': sum(r.get('steps', 0) for r in rs) / len(rs),
            }
            for t, rs in sorted(by_type.items())
        },
        'results': [
            {k: v for k, v in r.items() if k != 'history'}
            for r in results
        ],
    }

    outfile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'ylyw_alfworld_official_results_v2.json')
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {outfile}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW on Official ALFWorld (方案B)')
    parser.add_argument('--mode', type=str, default='single', choices=['single', 'all', 'stats'])
    parser.add_argument('-n', '--num', type=int, default=0, help='Max games (0=all)')
    parser.add_argument('--game', type=int, default=0, help='Game index for single mode')
    parser.add_argument('--verbose', '-v', action='store_true', default=False)
    parser.add_argument('--oracle', action='store_true', default=True,
                        help='Use oracle task type (default: True)')
    parser.add_argument('--no-oracle', action='store_true', default=False)
    args = parser.parse_args()

    use_oracle = args.oracle and not args.no_oracle

    print("Creating ALFWorld Official environment (方案B: per-game env)...")
    env = ALFWorldOfficial(split="valid_unseen")

    if args.mode == 'stats':
        stats = env.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        sys.exit(0)

    agent = YLYWOfficialAgent(verbose=args.verbose, use_oracle_type=use_oracle)
    print(f"Agent: oracle_type={use_oracle}")

    if args.mode == 'single':
        result = run_single_game(env, args.game, agent, verbose=True)
        print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False, default=str)}")
    elif args.mode == 'all':
        run_all_games(env, agent, verbose=args.verbose,
                      max_games=args.num if args.num > 0 else 0)

    env.close()
