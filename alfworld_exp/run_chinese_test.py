#!/usr/bin/env python3
"""
用 ChineseBridge 跑 ALFWorld 测试

方案：在原版 YLYWAgent 基础上，注入中文翻译信息
- task_desc → 同时有英文原文和中文翻译
- _extract_target_entities 扩展为同时支持中英文关键词
- admissible_commands 保持英文（仿真器需要英文原命令）
- 显示层面展示中文翻译

用法：
  python3 run_chinese_test.py --mode single 0    # 单任务测试
  python3 run_chinese_test.py --mode all -n 5    # 跑5个任务
"""

import sys
import os
import json
import re
import argparse
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

# YLYW 核心
YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)
from ylyw_core import PriorManual

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 原版agent
from ylyw_alfworld_agent import (
    ALFWorldLight, YLYWAgent, MAX_STEPS, 
    run_single_game, run_all_games, compute_metrics, print_metrics
)
from chinese_bridge import ChineseBridge

# ── 中文增强版 YLYW Agent ───────────────────────────────

class YLYWChineseAwareAgent(YLYWAgent):
    """
    中文感知版 YLYW Agent
    
    继承原版YLYWAgent，在以下方面增加中文支持：
    1. task_desc用ChineseBridge翻译为中文，供_extract_target_entities做中文匹配
    2. admissible_commands用中文显示（底层仍用英文匹配）
    3. _extract_target_entities扩展中英文关键词
    4. 添加中英文物体名映射的语义匹配
    """

    # 中文物体/位置/工具关键词 → 英文名映射
    CN_KEYWORDS = {
        # 物体
        '碗': 'bowl', '杯子': 'mug', '餐叉': 'fork', '叉子': 'fork',
        '刀': 'knife', '刀子': 'knife', '盘子': 'plate', '锅': 'pot',
        '平底锅': 'pan', '勺子': 'spoon', '汤匙': 'spoon',
        '土豆': 'potato', '番茄': 'tomato', '苹果': 'apple',
        '香蕉': 'banana', '鸡蛋': 'egg', '面包': 'bread', '奶酪': 'cheese',
        '生菜': 'lettuce', '洋葱': 'onion', '胡椒': 'pepper',
        '萝卜': 'radish', '闹钟': 'alarmclock',
        '钟': 'clock', '时钟': 'clock',
        '手机': 'cellphone', '笔记本电脑': 'laptop',
        '书': 'book', '遥控器': 'remotecontrol',
        '花瓶': 'vase', '雕像': 'statue',
        '毛巾': 'towel', '肥皂': 'soap',
        # 位置
        '桌子': 'table', '餐桌': 'diningtable', '茶几': 'coffeetable',
        '床头柜': 'nightstand', '书架': 'shelf', '架子': 'shelf',
        '沙发': 'sofa', '椅子': 'chair', '床': 'bed',
        '橱柜': 'cabinet', '抽屉': 'drawer', '冰箱': 'fridge',
        '微波炉': 'microwave', '灶台': 'stoveburner', '水槽': 'sinkbasin',
        '台灯': 'desklamp', '落地灯': 'floorlamp',
        '砧板': 'cuttingboard', '洗碗机': 'dishwasher',
        # 工具
        '灯': 'desklamp', '微波炉': 'microwave', '水槽': 'sinkbasin',
    }

    def __init__(self, verbose=False, use_oracle_type=False):
        super().__init__(verbose=verbose, use_oracle_type=use_oracle_type)
        self.bridge = ChineseBridge()
        self.cn_task_desc = ""

    def infer_task_type(self, task_desc: str, ground_truth: str = None) -> str:
        """推断任务类型（原版逻辑不变）"""
        # 顺便保存中文翻译
        self.cn_task_desc = self.bridge._translate_task_desc(task_desc) or task_desc
        return super().infer_task_type(task_desc, ground_truth)

    def init_v2(self, task_desc: str, task_type: str = ""):
        """初始化v2模块（原版逻辑）"""
        self.cn_task_desc = self.bridge._translate_task_desc(task_desc) or task_desc
        return super().init_v2(task_desc, task_type)

    def _extract_target_entities(self, task_desc: str, task_type: str) -> Dict[str, List[str]]:
        """扩展版实体提取——同时支持中英文"""
        entities = super()._extract_target_entities(task_desc, task_type)

        # 如果已有中文翻译，增加中文关键词匹配
        cn_desc = getattr(self, 'cn_task_desc', '') or task_desc
        cn_lower = cn_desc.lower()

        for cn_kw, en_name in self.CN_KEYWORDS.items():
            if cn_kw in cn_lower and en_name not in entities['objects']:
                # 判断是物体、位置还是工具
                if en_name in ('desklamp', 'floorlamp', 'microwave'):
                    entities['tools'].append(en_name)
                elif en_name in ('table', 'diningtable', 'coffeetable', 'shelf',
                                 'cabinet', 'drawer', 'fridge', 'microwave',
                                 'stoveburner', 'sinkbasin', 'desk', 'bed',
                                 'sofa', 'chair', 'nightstand', 'counter'):
                    entities['locations'].append(en_name)
                else:
                    entities['objects'].append(en_name)

        return entities

    def _entity_match_bonus(self, cmd: str, target_entities: Dict[str, List[str]]) -> float:
        """扩展版实体匹配——支持中英混搭"""
        bonus = super()._entity_match_bonus(cmd, target_entities)
        if bonus > 0:
            return bonus

        # 额外检查中文翻译的实体名在命令中是否匹配
        for cat in ['objects', 'locations', 'tools']:
            for ent in target_entities.get(cat, []):
                if ent in cmd.lower():
                    bonus += 0.6
                    return bonus

        return 0.0


# ── 运行 ─────────────────────────────────────────────────

def run_single_cn_game(env, agent, game_idx, verbose=True):
    """用中文感知agent跑一个游戏，同时展示中英文"""
    result = run_single_game(env, agent, game_idx, verbose=False)

    if verbose:
        cn_task = getattr(agent, 'cn_task_desc', '') or result.get('task_desc', '')
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {result['task_type_real']}")
        print(f"EN Task: {result['task_desc']}")
        print(f"CN Task: {cn_task}")
        print(f"Inferred: {result['task_type_inferred']} "
              f"{'✅' if result['type_correct'] else '❌'}")
        print(f"{'='*60}")

        # 回放详细步数（从transcript复原——这里用简化方式）
        print(f"Result: {'✅ WON' if result['won'] else '❌ LOST'} "
              f"in {result['steps']} steps "
              f"(walkthrough={result['walkthrough_len']})")
        print(f"Type match: {result['type_correct']}")

    return result


def run_all_cn_games(env, agent, verbose=False, max_games=0):
    """中文增强模式跑全部游戏"""
    results = []
    n = len(env.games)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n运行 {n}/{len(env.games)} 个游戏 (ChineseBridge增强模式) ...")
    print(f"模型: deepseek-v4-flash | Oracle模式: {agent.use_oracle_type}")

    start = time.time()
    for i in range(n):
        result = run_single_cn_game(env, agent, i, verbose=verbose)
        results.append(result)

        wins = sum(1 for r in results if r['won'])
        elapsed = time.time() - start
        print(f"  [{i+1}/{n}] Game {i}: {'✅' if result['won'] else '❌'} "
              f"({result['task_type_real']:35s}) {result['steps']}步 "
              f"[累计: {wins}/{i+1} = {wins/(i+1)*100:.1f}%] "
              f"[{elapsed:.0f}s]")
    elapsed = time.time() - start

    metrics = compute_metrics(results)
    print_metrics(metrics, elapsed)

    return results


# ── CLI ──────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW ChineseBridge ALFWorld 测试')
    parser.add_argument('--mode', type=str, default='single',
                        choices=['single', 'all', 'compare'])
    parser.add_argument('-n', '--num', type=int, default=1)
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('--verbose', action='store_true', default=True)
    parser.add_argument('--oracle', action='store_true', default=True,
                        help='Oracle模式（使用ground truth类型）')

    args = parser.parse_args()

    env = ALFWorldLight()

    # 原版 vs 中文增强版
    if args.mode == 'compare':
        print("=" * 60)
        print("原版 YLYW Agent")
        print("=" * 60)
        env2 = ALFWorldLight()
        agent_orig = YLYWAgent(verbose=False, use_oracle_type=args.oracle)
        r1 = run_single_game(env2, agent_orig, args.game, verbose=True)

        print(f"\n{'='*60}")
        print("中文增强版 YLYW Agent (ChineseBridge)")
        print("=" * 60)
        env.reset()
        agent_cn = YLYWChineseAwareAgent(verbose=False, use_oracle_type=args.oracle)
        r2 = run_single_cn_game(env, agent_cn, args.game, verbose=True)

        print(f"\n{'='*60}")
        print(f"对比 Game #{args.game}")
        print(f"  原版:   {'✅' if r1['won'] else '❌'} {r1['steps']}步")
        print(f"  中文版: {'✅' if r2['won'] else '❌'} {r2['steps']}步")

    elif args.mode == 'single':
        agent_cn = YLYWChineseAwareAgent(verbose=False, use_oracle_type=args.oracle)
        run_single_cn_game(env, agent_cn, args.game, verbose=True)

    elif args.mode == 'all':
        agent_cn = YLYWChineseAwareAgent(verbose=False, use_oracle_type=args.oracle)
        results = run_all_cn_games(env, agent_cn, verbose=False,
                                    max_games=args.num if args.num > 1 else 0)
