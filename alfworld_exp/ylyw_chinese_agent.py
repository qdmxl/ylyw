#!/usr/bin/env python3
"""
YLYW 中文 Agent — 通过 ChineseBridge 在 ALFWorld 和 YLYW 之间做中英文翻译

核心流程：
  1. ALFWorld 英文 observation/task_desc/commands → ChineseBridge 翻译为中文
  2. YLYW 基于中文上下文做三步推理（宏观→中观→微观）
  3. YLYW 选出的中文动作 → ChineseBridge 回译为英文 → 执行

用法：
  python3 ylyw_chinese_agent.py --mode single 0   # 测试单个任务
  python3 ylyw_chinese_agent.py --mode all          # 跑全部85个任务
  python3 ylyw_chinese_agent.py --mode compare 0    # 与原版对比
"""

import sys
import os
import json
import re
import argparse
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

# YLYW 核心
YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)
from ylyw_core import PriorManual

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alfworld_agent import ALFWorldLight
from ylyw_semantic_parser import YLYWSemanticParser
from chinese_bridge import ChineseBridge

MAX_STEPS = 50


class YLYWChineseAgent:
    """
    基于 ChineseBridge 的 YLYW 中文 Agent

    三层推理（全部用中文语义）：
      宏观层: 由 LLM 语义解析将中文任务描述映射为7种任务类型
      中观层: 中文化子目标模板
      微观层: 中文化六爻评分 + 语义匹配

    use_oracle_type=False 时完全基于中文语义推断类型
    """

    def __init__(self, verbose=False, use_oracle_type=False):
        self.manual = PriorManual(verbose=False)
        self.semantic_parser = YLYWSemanticParser()
        self.bridge = ChineseBridge()
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type
        self.current_phase = 0
        self.phase_step = 0

        # 中文任务类型映射
        self.CN_TASK_TYPES = {
            'look_at_obj_in_light':           '用光源查看物体',
            'pick_and_place_simple':          '简单取放物品',
            'pick_clean_then_place_in_recep': '清洁后放置物品',
            'pick_cool_then_place_in_recep':  '冷却后放置物品',
            'pick_heat_then_place_in_recep':  '加热后放置物品',
            'pick_two_obj_and_place':         '取两个物品并放置',
            'pick_and_place_with_movable_recep': '使用可移动容器取放物品',
        }

        # 中文动作类型
        self.CN_ACTION_TYPES = {
            'go to': '去', 'take': '拿', 'put': '放',
            'open': '打开', 'close': '关闭',
            'clean': '清洗', 'heat': '加热', 'cool': '冷却',
            'use': '使用', 'toggle': '切换', 'slice': '切片',
            'look': '观察', 'inventory': '查看背包',
        }

    def infer_task_type(self, cn_task_desc: str, ground_truth: str = None) -> str:
        """基于中文任务描述推断任务类型"""
        if self.use_oracle_type and ground_truth:
            return ground_truth

        cn_lower = cn_task_desc.lower()

        # 基于中文关键词的任务类型匹配
        type_keywords = {
            'look_at_obj_in_light': ['看', '检查', '查看', '光源', '灯', 'light'],
            'pick_and_place_simple': ['放', '放进去', '放回', '简单'],
            'pick_clean_then_place_in_recep': ['清洁', '洗', '擦', 'clean'],
            'pick_cool_then_place_in_recep': ['冷却', '冷', 'cool'],
            'pick_heat_then_place_in_recep': ['加热', '热', '微波', 'heat', 'microwave'],
            'pick_two_obj_and_place': ['两', '两个', '二', '双'],
            'pick_and_place_with_movable_recep': ['移动', '可移动', 'movable'],
        }

        scores = {}
        for task_type, kws in type_keywords.items():
            score = sum(1 for kw in kws if kw in cn_lower)
            if score > 0:
                scores[task_type] = score

        if scores:
            best = max(scores, key=scores.get)
            return best

        # fallback: 用英文原文语义解析
        return self.semantic_parser.parse_task_desc(cn_task_desc).get('task_type', 'pick_and_place_simple')

    def infer_subgoals(self, task_type: str, cn_task_desc: str = "") -> List[List[str]]:
        """基于中文的子目标分解"""
        # 中文子目标模板
        cn_templates = {
            'look_at_obj_in_light':           [['去'], ['打开', '去'], ['拿'], ['去'], ['使用']],
            'pick_and_place_simple':          [['去'], ['打开', '去'], ['拿'], ['去'], ['放']],
            'pick_clean_then_place_in_recep': [['去'], ['打开', '去'], ['拿'], ['去'], ['清洗'], ['去'], ['放']],
            'pick_cool_then_place_in_recep':  [['去'], ['打开', '去'], ['拿'], ['去'], ['冷却'], ['去'], ['放']],
            'pick_heat_then_place_in_recep':  [['去'], ['打开', '去'], ['拿'], ['去'], ['加热'], ['去'], ['放']],
            'pick_two_obj_and_place':         [['去'], ['打开', '去'], ['拿'], ['去'], ['放'],
                                                ['去'], ['打开', '去'], ['拿'], ['去'], ['放']],
        }
        return cn_templates.get(task_type, [['去'], ['打开', '去'], ['拿'], ['去'], ['放']])

    def _get_cn_action_type(self, cn_cmd: str) -> str:
        """提取中文命令的动作类型"""
        cn_cmd = cn_cmd.strip().lower()
        for cn_type, cn_verb in self.CN_ACTION_TYPES.items():
            if cn_cmd.startswith(cn_verb):
                return cn_type
        # 回退：用英文查
        en = self.bridge.to_english(cn_cmd)
        for en_verb in self.CN_ACTION_TYPES:
            if en.startswith(en_verb):
                return en_verb
        return 'go to'

    def _extract_cn_entities(self, cn_task_desc: str, task_type: str) -> Dict[str, List[str]]:
        """从中文任务描述提取目标实体"""
        entities = {'objects': [], 'locations': [], 'tools': []}
        cn_lower = cn_task_desc.lower()

        # 物体匹配（中文名）
        for cn_name in self.bridge.OBJ_MAP:
            if cn_name in cn_lower:
                entities['objects'].append(cn_name)

        # 工具匹配
        tool_keywords = {
            '微波炉': 'microwave', '水槽': 'sinkbasin',
            '灶台': 'stoveburner', '灯': 'desklamp',
        }
        for cn_tool in tool_keywords:
            if cn_tool in cn_lower:
                entities['tools'].append(cn_tool)

        return entities

    def select_action(self, cn_cmds: List[str], en_cmds: List[str],
                      current_phase: int, task_type: str,
                      cn_task_desc: str = "") -> Tuple[str, str]:
        """
        微观层：基于中文命令选择动作
        
        返回: (cn_action, en_action)
        """
        subgoals = self.infer_subgoals(task_type, cn_task_desc)
        target_cn_actions = subgoals[current_phase] if current_phase < len(subgoals) else ['去']

        # 1. open优先
        if '打开' in target_cn_actions:
            for cn_c in cn_cmds:
                if cn_c.startswith('打开'):
                    return cn_c, self.bridge.to_english(cn_c)

        # 2. 按目标类型筛选
        candidates = []
        for i, cn_c in enumerate(cn_cmds):
            at = self._get_cn_action_type(cn_c)
            cn_at = self.CN_ACTION_TYPES.get(at, '')
            if cn_at in target_cn_actions or at in target_cn_actions or cn_c.split()[0] in target_cn_actions:
                candidates.append((cn_c, en_cmds[i]))

        if not candidates:
            candidates = list(zip(cn_cmds, en_cmds))

        # 3. 六爻评分（基于中文语义）
        cn_entities = self._extract_cn_entities(cn_task_desc, task_type)

        if candidates:
            best_cn = candidates[0][0]
            best_en = candidates[0][1]
            best_score = -1

            for cn_c, en_c in candidates:
                score = self._chinese_semantic_score(cn_c, cn_task_desc, cn_entities, current_phase, target_cn_actions)
                if score > best_score:
                    best_score = score
                    best_cn, best_en = cn_c, en_c

            return best_cn, best_en

        return cn_cmds[0] if cn_cmds else ('观察', 'look'), en_cmds[0] if en_cmds else 'look'

    def _chinese_semantic_score(self, cn_cmd: str, cn_task: str,
                                 cn_entities: Dict, phase: int,
                                 target_actions: List[str]) -> float:
        """中文语义评分"""
        score = 0.0
        cn_lower = cn_cmd.lower()

        # 动作匹配奖励
        for ta in target_actions:
            if cn_lower.startswith(ta):
                score += 3.0

        # 物体匹配
        for obj in cn_entities.get('objects', []):
            if obj in cn_lower:
                score += 2.0

        # 工具匹配
        for tool in cn_entities.get('tools', []):
            if tool in cn_lower:
                score += 1.5

        # 去目标位置（如果是"去"命令）
        if cn_lower.startswith('去'):
            if cn_entities.get('locations'):
                for loc in cn_entities['locations']:
                    if loc in cn_lower:
                        score += 2.0

        return score

    def update_phase(self, cn_action: str, en_action: str,
                     current_phase: int, action_success: bool) -> int:
        """根据执行结果更新阶段"""
        en_at = self._get_cn_action_type(cn_action)

        # 阶段推进
        subgoals = self.infer_subgoals('dummy')
        if current_phase < 2:  # go to / open 阶段
            if en_at == 'take':
                return current_phase + 1
        elif current_phase < 4:
            if en_at == 'put':
                return current_phase + 1
            elif en_at in ('clean', 'heat', 'cool', 'toggle', 'use'):
                return current_phase + 1

        return current_phase


# ============================================================
# 运行实验
# ============================================================

def run_single_cn_game(env: ALFWorldLight, agent: YLYWChineseAgent,
                       game_idx: int, verbose: bool = False):
    """中文桥接模式运行单个游戏"""
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info['task_desc']
    task_type_real = info['task_type']

    # 翻译为中文
    cn_task = agent.bridge._translate_task_desc(task_desc) or task_desc
    gt_type = env.traj_data.get('task_type', '') if hasattr(env, 'traj_data') else task_type_real

    # 中文推理
    inferred_type = agent.infer_task_type(task_desc, ground_truth=gt_type)

    if verbose:
        cn_type = agent.CN_TASK_TYPES.get(inferred_type, inferred_type)
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"EN Task: {task_desc}")
        print(f"CN Task: {cn_task}")
        print(f"Inferred Type: {inferred_type} ({cn_type})")
        print(f"{'='*60}")

    current_phase = 0
    history_cn = []
    history_en = []
    steps = 0
    won = False

    while steps < MAX_STEPS:
        # 翻译commands
        cn_cmds, en_cmds = agent.bridge._translate_commands(
            info.get('admissible_commands', ['look']))

        # YLYW中文选择
        cn_action, en_action = agent.select_action(
            cn_cmds, en_cmds, current_phase, inferred_type, cn_task)

        if verbose:
            print(f"  Step {steps:2d}: phase={current_phase} → {cn_action}")

        # 执行（英文）
        obs, info = env.step(en_action)
        history_cn.append(cn_action)
        history_en.append(en_action)
        steps += 1

        # 更新阶段
        action_success = "didn't work" not in obs.lower()
        old_phase = current_phase
        current_phase = agent.update_phase(cn_action, en_action, current_phase, action_success)

        if verbose and current_phase != old_phase:
            print(f"  >>> Phase transition: {old_phase} → {current_phase}")

        if info.get('done'):
            won = info.get('won', False)
            break

    result = {
        'game_idx': game_idx,
        'task_type_real': task_type_real,
        'task_type_inferred': inferred_type,
        'type_correct': inferred_type == task_type_real,
        'task_desc': task_desc[:80],
        'cn_task': cn_task[:80],
        'steps': steps,
        'won': won,
        'walkthrough_len': info.get('walkthrough_len', 0),
    }

    if verbose:
        status = "✅ WON" if won else "❌ LOST"
        print(f"  {status} in {steps} steps")

    return result


def run_all_cn_games(env: ALFWorldLight, agent: YLYWChineseAgent,
                     verbose: bool = False, max_games: int = 0):
    """运行全部游戏"""
    results = []
    n = len(env.games)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n运行 {n}/{len(env.games)} 个游戏 (ChineseBridge模式) ...")

    for i in range(n):
        result = run_single_cn_game(env, agent, i, verbose=verbose)
        results.append(result)

        # 实时打印进度
        wins = sum(1 for r in results if r['won'])
        print(f"  [{i+1}/{n}] Game {i}: {'✅' if result['won'] else '❌'} "
              f"({result['task_type_real']:35s}) {result['steps']}步 "
              f"[累计: {wins}/{i+1} = {wins/(i+1)*100:.1f}%]")

    # 汇总
    total_wins = sum(1 for r in results if r['won'])
    total_steps = sum(r['steps'] for r in results)
    type_correct = sum(1 for r in results if r['type_correct'])
    avg_steps = total_steps / len(results) if results else 0

    print(f"\n{'='*60}")
    print(f"结果汇总 (ChineseBridge)")
    print(f"{'='*60}")
    print(f"  总任务: {len(results)}")
    print(f"  成功: {total_wins}")
    print(f"  成功率: {total_wins/len(results)*100:.1f}%")
    print(f"  类型识别准确率: {type_correct/len(results)*100:.1f}%")
    print(f"  平均步数: {avg_steps:.1f}")

    # 按类型分
    by_type = defaultdict(list)
    for r in results:
        by_type[r['task_type_real']].append(r)

    print(f"\n  按任务类型:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        ts = sum(r['steps'] for r in rs)
        print(f"    {t:40s}: {tw}/{len(rs)} ({tw/len(rs)*100:.1f}%) avg={ts/len(rs):.1f}步")

    return results


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW Chinese Agent for ALFWorld')
    parser.add_argument('--mode', type=str, default='single',
                        choices=['single', 'all', 'compare'],
                        help='运行模式')
    parser.add_argument('-n', type=int, default=1,
                        help='游戏数量（all模式）或游戏索引（single/compare模式）')
    parser.add_argument('--verbose', action='store_true', default=True,
                        help='详细输出')
    parser.add_argument('--oracle', action='store_true', default=True,
                        help='使用Oracle类型（真值）')

    args = parser.parse_args()

    env = ALFWorldLight()
    agent = YLYWChineseAgent(verbose=args.verbose, use_oracle_type=args.oracle)

    if args.mode == 'single':
        run_single_cn_game(env, agent, args.n, verbose=True)

    elif args.mode == 'all':
        run_all_cn_games(env, agent, verbose=False, max_games=args.n if args.n > 1 else 0)

    elif args.mode == 'compare':
        print("=== 原版 YLYW ===")
        from ylyw_alfworld_agent import YLYWAgent, run_single_game
        env2 = ALFWorldLight()
        agent2 = YLYWAgent(verbose=False, use_oracle_type=True)
        r1 = run_single_game(env2, agent2, game_idx=args.n, verbose=True)

        print(f"\n=== YLYW ChineseBridge ===")
        env.reset()
        r2 = run_single_cn_game(env, agent, args.n, verbose=True)

        print(f"\n{'='*60}")
        print(f"对比 Game #{args.n}")
        print(f"  原版:   {'✅' if r1['won'] else '❌'} {r1['steps']}步")
        print(f"  中文版: {'✅' if r2['won'] else '❌'} {r2['steps']}步")
