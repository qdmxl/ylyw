#!/usr/bin/env python3
"""
YLYW 深度中文推理 Agent — 第三版

核心：YLYW 的三层推理完全基于中文语义运行
  L1 八卦基元 → 中文词分类 → 卦象隶属
  L2 六爻编码 → 中文语义评分 + 中英实体映射
  L3 卦象匹配 → 中文动作选择

使用 ylyw_semantic_parser_cn.py 替代原版英文语义解析器

用法：
  python3 ylyw_chinese_v3.py --mode single 0
  python3 ylyw_chinese_v3.py --mode all
"""

import sys
import os
import json
import re
import argparse
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)
from ylyw_core import PriorManual

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_semantic_parser_cn import YLYWChineseSemanticParser
from chinese_bridge import ChineseBridge

# 从原版导入 ALFWorldLight 和辅助函数
from ylyw_alfworld_agent import ALFWorldLight, MAX_STEPS, plan_to_walkthrough


# ============================================================
# 中文YLYW Agent — 完全基于中文语义
# ============================================================

class YLYWChineseV3Agent:
    """
    基于中文语义的 YLYW Agent

    三层推理全部使用中文：
      宏观层: 中文任务描述 → 关键词匹配 → 7种任务类型
      中观层: 中文子目标模板
      微观层: 中文命令六爻评分 + 中英文实体映射
    """

    # 动作类型 → 中文前缀映射
    CN_ACTION_PREFIX = {
        'go to': '去', 'take': '拿', 'put': '放',
        'open': '打开', 'close': '关闭',
        'clean': '清洗', 'heat': '加热', 'cool': '冷却',
        'use': '使用', 'toggle': '使用', 'slice': '切片',
        'look': '观察', 'inventory': '查看背包', 'help': '帮助',
    }

    # 英文动作类型 → 中文
    EN_TO_CN_TYPE = {
        'go to': '去', 'take': '拿', 'put': '放',
        'open': '打开', 'close': '关闭', 
        'clean': '清洗', 'heat': '加热', 'cool': '冷却',
        'use': '使用', 'slice': '切片',
        'look': '观察', 'inventory': '查看背包',
    }

    def __init__(self, verbose=False, use_oracle_type=False):
        self.manual = PriorManual(verbose=False)
        self.cn_parser = YLYWChineseSemanticParser()
        self.bridge = ChineseBridge()
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type
        self.current_phase = 0
        self.phase_step = 0

    def infer_task_type(self, task_desc: str, ground_truth: str = None) -> str:
        """基于中文推断任务类型"""
        if self.use_oracle_type and ground_truth:
            self._last_cn_result = self.cn_parser.parse_task_desc(task_desc)
            return ground_truth
        result = self.cn_parser.parse_task_desc(task_desc)
        self._last_cn_result = result
        return result['task_type']

    def infer_subgoals(self, task_type: str, cn_task_desc: str = "") -> List[List[str]]:
        """中文子目标模板"""
        templates = {
            'look_at_obj_in_light':           [['去'], ['拿'], ['去'], ['使用']],
            'pick_and_place_simple':          [['去'], ['拿'], ['去'], ['放']],
            'pick_clean_then_place_in_recep': [['去'], ['拿'], ['去'], ['清洗'], ['去'], ['放']],
            'pick_cool_then_place_in_recep':  [['去'], ['拿'], ['去'], ['冷却'], ['去'], ['放']],
            'pick_heat_then_place_in_recep':  [['去'], ['拿'], ['去'], ['加热'], ['去'], ['放']],
            'pick_two_obj_and_place':         [['去'], ['拿'], ['去'], ['放'], ['去'], ['拿'], ['去'], ['放']],
        }
        return templates.get(task_type, [['去'], ['打开','去'], ['拿'], ['去'], ['放']])

    def _get_en_action_type(self, cmd: str) -> str:
        """从英文命令提取action type"""
        cmd_lower = cmd.strip().lower()
        for en_type, cn_pref in self.CN_ACTION_PREFIX.items():
            if cmd_lower.startswith(en_type) or cmd_lower.startswith(cn_pref):
                return en_type
        # 中文前缀回退
        for en_type, cn_pref in self.CN_ACTION_PREFIX.items():
            if cn_pref in cmd_lower:
                return en_type
        return 'go to'

    def _extract_cn_entities_from_result(self, task_type: str) -> Dict:
        """从中文解析结果提取实体"""
        result = getattr(self, '_last_cn_result', None)
        if result and 'inferred_args' in result:
            return result['inferred_args']
        return {'objects': [], 'locations': [], 'tools': []}

    # 中→英手工映射补充
    _CN_EXTRA_MAP = {
        '灯': ['desklamp', 'floorlamp', 'lamp'],
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
        '垃圾桶': ['garbagecan', 'trash', 'garbage'],
        '架子': ['shelf'],
        '毛巾': ['towel'],
        '布': ['cloth'],
        '海绵': ['sponge'],
        '肥皂': ['soap'],
        '书': ['book'],
        '苹果': ['apple'],
        '土豆': ['potato'],
        '鸡蛋': ['egg'],
        '面包': ['bread'],
        '碗': ['bowl'],
        '盘子': ['plate'],
        '锅': ['pan', 'pot'],
        '锅': ['pot'],
        '刀': ['knife'],
        '叉子': ['fork'],
        '勺子': ['spoon'],
        '花瓶': ['vase'],
        '雕像': ['statue'],
        '手机': ['cellphone'],
        '遥控器': ['remotecontrol', 'remote'],
        '钥匙链': ['keychain'],
        '信用卡': ['creditcard'],
        '球棒': ['baseballbat', 'bat'],
        '棒球棒': ['baseballbat'],
        '篮球': ['basketball'],
        '枕头': ['pillow'],
        '笔记本电脑': ['laptop'],
        '盒子': ['box'],
        '蜡烛': ['candle'],
        '纸巾盒': ['tissuebox'],
        '光盘': ['cd'],
        '报纸': ['newspaper'],
        '笔记本电脑': ['laptop', 'computer'],
        '马桶搋子': ['plunger'],
        '盐': ['salt'],
        '胡椒': ['pepper'],
        '马桶': ['toilet'],
        '浴缸': ['bathtub'],
        '烤箱': ['oven'],
        '烤面包机': ['toaster'],
        '咖啡机': ['coffeemachine'],
        '台面': ['countertop', 'counter'],
        '柜台': ['counter'],
        '茶几': ['coffeetable'],
        '餐桌': ['diningtable'],
        '床头柜': ['sidetable'],
        '电视柜': ['tvstand'],
        '梳妆台': ['dresser'],
        '洗衣机': ['laundryhamper'],
    }

    def _cn_entity_match_score(self, en_cmd: str, cn_entities: Dict) -> float:
        """中英文实体匹配：检查英文命令中是否包含中文实体对应的英文名"""
        score = 0.0
        cmd_lower = en_cmd.lower()
        
        for obj in cn_entities.get('objects', []):
            # 中文物体名 → 英文名
            en_name = self.bridge.OBJ_MAP.get(obj, '')
            extra_names = self._CN_EXTRA_MAP.get(obj, [])
            all_names = [en_name] + extra_names if en_name else extra_names
            for en in all_names:
                if en and en in cmd_lower:
                    score += 2.0
                    break
            # 也直接用中文名匹配
            if obj in cmd_lower:
                score += 2.0

        for loc in cn_entities.get('locations', []):
            en_name = self.bridge.OBJ_MAP.get(loc, '')
            extra_names = self._CN_EXTRA_MAP.get(loc, [])
            all_names = [en_name] + extra_names if en_name else extra_names
            for en in all_names:
                if en and en in cmd_lower:
                    score += 1.5
                    break
            if loc in cmd_lower:
                score += 1.5

        for tool in cn_entities.get('tools', []):
            en_name = self.bridge.OBJ_MAP.get(tool, '')
            extra_names = self._CN_EXTRA_MAP.get(tool, [])
            all_names = [en_name] + extra_names if en_name else extra_names
            for en in all_names:
                if en and en in cmd_lower:
                    score += 2.0
                    break
            if tool in cmd_lower:
                score += 2.0

        return score

    def select_action(self, admissible_commands: List[str],
                      current_phase: int, task_type: str,
                      history: List[str],
                      task_desc: str = "") -> str:
        """基于中文语义的动作选择"""
        subgoals = self.infer_subgoals(task_type)
        target_actions = subgoals[current_phase] if current_phase < len(subgoals) else ['去']

        cn_entities = self._extract_cn_entities_from_result(task_type)

        # 1. 自动Open探测：在任何go to后，如果可选命令中有open且还没做过
        open_cmds = [c for c in admissible_commands if c.startswith('open ')]
        if open_cmds and '去' in target_actions:
            # 在go to阶段，如果有open命令，先打开看看
            recent = history[-5:] if len(history) >= 5 else history
            recent_opens = [h for h in recent if h.startswith('open ')]
            if len(recent_opens) < len(open_cmds):
                # 还有没开过的容器
                unopened = [c for c in open_cmds if c not in recent]
                if unopened:
                    return unopened[0]

        # 2. 按目标类型筛选
        typed_cmds = []
        for cmd in admissible_commands:
            at = self._get_en_action_type(cmd)
            cn_at = self.EN_TO_CN_TYPE.get(at, '')
            if cn_at in target_actions:
                typed_cmds.append(cmd)

        candidates = typed_cmds if typed_cmds else admissible_commands

        # 3. 目标动作优先
        target_only = []
        for cmd in candidates:
            at = self._get_en_action_type(cmd)
            cn_at = self.EN_TO_CN_TYPE.get(at, '')
            if cn_at in target_actions:
                target_only.append(cmd)
        if target_only:
            candidates = target_only

        # 4. 停留在go to阶段的特别处理
        if len(set(history[-10:])) <= 2 and current_phase <= 1:
            # 原地打转 → 尝试所有go to中未被探索的位置
            explored = set(h for h in history if h.startswith('go to'))
            go_cmds = [c for c in candidates if c.startswith('go to')]
            unexplored = [c for c in go_cmds if c not in explored]
            if unexplored:
                # 优先选匹配中文实体的
                best_cmd = None
                best_score = -1
                for c in unexplored:
                    s = self._cn_entity_match_score(c, cn_entities)
                    if s > best_score:
                        best_score = s
                        best_cmd = c
                if best_cmd:
                    return best_cmd

        # 5. 评分：中英文实体匹配 + 六爻
        best_cmd = candidates[0] if candidates else admissible_commands[0]
        best_score = -1

        for cmd in candidates:
            score = 0.0
            at = self._get_en_action_type(cmd)

            # 中文实体匹配
            score += self._cn_entity_match_score(cmd, cn_entities) * 2.0

            # 英文原版语义匹配（兜底）
            if hasattr(self, '_last_cn_result') and self._last_cn_result:
                desc_lower = self._last_cn_result.get('cn_task_desc', task_desc).lower()
            else:
                desc_lower = task_desc.lower()
            
            # 任务描述中的英文词重叠
            desc_en_words = set(re.findall(r'[a-zA-Z]+', desc_lower))
            cmd_en_words = set(re.findall(r'[a-zA-Z]+', cmd.lower()))
            overlap = len(desc_en_words & cmd_en_words) * 0.3
            score += overlap

            # YLYW 六爻评分
            features = self._cmd_to_features(cmd, at, current_phase, task_type)
            perception = self.manual.perceive_and_encode(features)
            yaos = perception['yao_vector']

            # 六爻与中文实体的匹配度
            if cn_entities:
                yao_weight = 0.3
            else:
                yao_weight = 0.5

            score += perception['hexagram_match_score'] * yao_weight

            if score > best_score:
                best_score = score
                best_cmd = cmd

        return best_cmd

    def _cmd_to_features(self, cmd: str, action_type: str,
                          current_phase: int, task_type: str) -> Dict:
        """命令 → 六爻特征向量"""
        base = {
            'stability': 0.4, 'roll_tendency': 0.3,
            'strength_needed': 0.3, 'fragility': 0.3,
            'task_priority': 0.5, 'reachability': 0.5,
        }

        if action_type == 'go to':
            base.update({'stability': 0.5, 'task_priority': 0.6, 'reachability': 0.8})
        elif action_type == 'take':
            base.update({'stability': 0.3, 'strength_needed': 0.5, 'task_priority': 0.8, 'reachability': 0.7})
        elif action_type == 'put':
            base.update({'stability': 0.6, 'task_priority': 0.7, 'reachability': 0.6})
        elif action_type == 'open':
            base.update({'stability': 0.4, 'fragility': 0.3, 'task_priority': 0.6})
        elif action_type in ('clean', 'heat', 'cool', 'slice'):
            base.update({'stability': 0.4, 'fragility': 0.4, 'task_priority': 0.5})
        elif action_type == 'use' or action_type == 'toggle':
            base.update({'stability': 0.4, 'task_priority': 0.6})

        # 阶段影响
        if current_phase <= 1:
            base['reachability'] *= 1.2
        elif current_phase <= 3:
            base['task_priority'] *= 1.3
        elif current_phase >= 4:
            base['task_priority'] *= 1.5

        return base

    def update_phase(self, action: str, current_phase: int, action_success: bool) -> int:
        """根据动作类型和已执行序列推进阶段"""
        at = self._get_en_action_type(action)

        # 阶段推进规则:
        # phase 0: 初始go to → 拿到物体(take)后推进
        # phase 1: 拿了物体后 → go to到达目标位置后推进
        # phase 2+: 执行最终动作
        
        if at == 'take' and action_success:
            return current_phase + 1
        elif at == 'go to' and current_phase == 1:
            # 拿了物体后，再go to一次就推进
            return current_phase + 1
        elif at in ('put', 'use', 'toggle', 'clean', 'heat', 'cool', 'slice') and current_phase >= 2:
            return current_phase + 1

        return current_phase


# ============================================================
# 运行
# ============================================================

def run_single_game(env: ALFWorldLight, agent: YLYWChineseV3Agent,
                    game_idx: int, verbose: bool = False):
    """运行单个游戏"""
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info['task_desc']
    task_type_real = info['task_type']

    gt_type = env.traj_data.get('task_type', '') if hasattr(env, 'traj_data') else task_type_real
    inferred_type = agent.infer_task_type(task_desc, ground_truth=gt_type)

    # 中文解析结果
    cn_result = getattr(agent, '_last_cn_result', None)
    cn_task = cn_result['cn_task_desc'] if cn_result else task_desc

    if verbose:
        print(f"\n{'='*60}")
        print(f"Game #{game_idx}: {task_type_real}")
        print(f"EN: {task_desc}")
        print(f"CN: {cn_task}")
        print(f"Type: {inferred_type}")
        if cn_result:
            args = cn_result['inferred_args']
            print(f"Entities: 物体={args['objects']} 位置={args['locations']} 工具={args['tools']}")
        print(f"{'='*60}")

    current_phase = 0
    history = []
    steps = 0
    won = False

    while steps < MAX_STEPS:
        cmds = info.get('admissible_commands', ['look'])
        action = agent.select_action(cmds, current_phase, inferred_type,
                                     history, task_desc)

        if verbose:
            print(f"  Step {steps:2d}: phase={current_phase} → {action}")

        obs, info = env.step(action)
        history.append(action)
        steps += 1

        action_success = "didn't work" not in obs.lower()
        current_phase = agent.update_phase(action, current_phase, action_success)

        if verbose and current_phase != current_phase:
            pass

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


def run_all_games(env, agent, verbose=False, max_games=0):
    """跑全部游戏"""
    results = []
    n = len(env.games)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n运行 {n}/{len(env.games)} 个游戏 (YLYW中文推理V3) ...")
    start = time.time()

    for i in range(n):
        result = run_single_game(env, agent, i, verbose=verbose)
        results.append(result)

        wins = sum(1 for r in results if r['won'])
        elapsed = time.time() - start
        print(f"  [{i+1}/{n}] Game {i}: {'✅' if result['won'] else '❌'} "
              f"({result['task_type_real']:35s}) {result['steps']}步 "
              f"[累计: {wins}/{i+1} = {wins/(i+1)*100:.1f}%] [{elapsed:.0f}s]")

    elapsed = time.time() - start

    from ylyw_alfworld_agent import compute_metrics, print_metrics
    metrics = compute_metrics(results)
    print_metrics(metrics, elapsed)

    return results


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW中文推理V3')
    parser.add_argument('--mode', type=str, default='single',
                        choices=['single', 'all', 'compare'])
    parser.add_argument('-n', '--num', type=int, default=1)
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('--verbose', action='store_true', default=True)
    parser.add_argument('--oracle', action='store_true', default=True)
    args = parser.parse_args()

    env = ALFWorldLight()
    agent = YLYWChineseV3Agent(verbose=args.verbose, use_oracle_type=args.oracle)

    if args.mode == 'single':
        run_single_game(env, agent, args.game, verbose=True)
    elif args.mode == 'all':
        run_all_games(env, agent, verbose=False,
                      max_games=args.num if args.num > 1 else 0)
    elif args.mode == 'compare':
        # 对比原版
        from ylyw_alfworld_agent import YLYWAgent, run_single_game as run_orig
        print("原版 YLYW:")
        r1 = run_orig(ALFWorldLight(), 
            YLYWAgent(verbose=False, use_oracle_type=True), args.game, verbose=True)

        print("\n中文V3 YLYW:")
        r2 = run_single_game(env, agent, args.game, verbose=True)

        print(f"\n{'='*60}")
        print(f"Game #{args.game} 对比:")
        print(f"  原版:  {'✅' if r1['won'] else '❌'} {r1['steps']}步")
        print(f"  中文V3: {'✅' if r2['won'] else '❌'} {r2['steps']}步")
