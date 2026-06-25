#!/usr/bin/env python3
"""
YLYW 中文推理 Agent V4 — 完全中文化 + 丰富特征抽取 + 详细决策输出

核心改动：
  1. 所有语义处理全部用中文（词库、匹配、推理）
  2. 特征抽取从6维扩展到12维（语义+实体+任务+历史+动作候选）
  3. 决策输出详细化（推理链、候选排序、卦象解释、置信度）
  4. 使用官方ALFWorld环境（AlfredTWEnv）

用法：
  python3 ylyw_agent_v4.py --mode single 0
  python3 ylyw_agent_v4.py --mode all
"""

import sys, os, json, re, math, time
from collections import defaultdict, Counter
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# YLYW核心
YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)
from ylyw_core import PriorManual

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ylyw_semantic_parser_cn import YLYWChineseSemanticParser, ACTION_VERBS_CN, OBJECT_NOUNS_CN, LOCATION_NOUNS_CN, TOOL_NOUNS_CN, FUNCTION_WORDS_CN
from chinese_bridge import ChineseBridge

MAX_STEPS = 50

# 动作类型列表（英文，给仿真器用）
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
    'pick_and_place_with_movable_recep': [['go to'], ['take'], ['go to'], ['put']],
}

# 中文子目标名称（用于推理输出）
SUBGOAL_CN_NAMES = {
    'go to': '探索移动',
    'take': '拿取物体',
    'put': '放置物体',
    'open': '打开容器',
    'close': '关闭容器',
    'clean': '清洁物体',
    'heat': '加热物体',
    'cool': '冷却物体',
    'slice': '切割物体',
    'use': '使用工具',
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
    '书架': ['shelf', 'bookshelf'],
    '沙发': ['sofa'],
    '床': ['bed'],
    '保险箱': ['safe'],
    '垃圾桶': ['garbagecan', 'trash', 'garbage', 'bin'],
    '架子': ['shelf'],
    '毛巾': ['towel'],
    '布': ['cloth'],
    '书': ['book'],
    '苹果': ['apple'],
    '土豆': ['potato'],
    '碗': ['bowl'],
    '盘子': ['plate'],
    '锅': ['pan', 'pot'],
    '刀': ['knife'],
    '叉子': ['fork'],
    '勺子': ['spoon'],
    '花瓶': ['vase'],
    '雕像': ['statue'],
    '手机': ['cellphone'],
    '遥控器': ['remotecontrol', 'remote'],
    '钥匙链': ['keychain'],
    '球棒': ['baseballbat', 'bat'],
    '篮球': ['basketball'],
    '笔记本电脑': ['laptop', 'computer'],
    '盒子': ['box'],
    '纸巾盒': ['tissuebox'],
    '光盘': ['cd'],
    '枕头': ['pillow'],
    '马桶': ['toilet'],
    '浴缸': ['bathtub'],
    '烤箱': ['oven'],
    '烤面包机': ['toaster'],
    '咖啡机': ['coffeemachine'],
    '台面': ['countertop', 'counter'],
    '柜台': ['counter'],
    '茶几': ['coffeetable'],
    '餐桌': ['diningtable'],
    '梳妆台': ['dresser'],
}


class ChineseFeatureExtractor:
    """中文特征提取器 — 从任务描述和候选命令提取多样特征"""

    def __init__(self):
        self.bridge = ChineseBridge()
        self.cn_parser = YLYWChineseSemanticParser()
        self.manual = PriorManual(verbose=False)

    def extract_task_features(self, task_desc: str, task_type: str) -> Dict:
        """从中文任务描述提取语义特征"""
        # 中文解析
        cn_result = self.cn_parser.parse_task_desc(task_desc)
        cn_text = cn_result['cn_task_desc']
        word_info = cn_result['words']

        # 词类统计
        total = max(len(word_info), 1)
        action_count = sum(1 for w, c in word_info if c == 'action')
        object_count = sum(1 for w, c in word_info if c == 'object')
        location_count = sum(1 for w, c in word_info if c == 'location')
        tool_count = sum(1 for w, c in word_info if c == 'tool')

        # 实体提取
        args = cn_result['inferred_args']

        # 任务复杂度
        n_subgoals = len(SUBGOAL_TEMPLATES.get(task_type, []))

        features = {
            'action_density': action_count / total,
            'object_density': object_count / total,
            'location_density': location_count / total,
            'tool_density': tool_count / total,
            'entity_total': object_count + location_count + tool_count,
            'n_subgoals': n_subgoals,
            'task_type': task_type,
            'cn_entities': args,
            'cn_text': cn_text,
        }
        return features

    def extract_cmd_features(self, cmd: str, task_features: Dict,
                              phase: int, history: List[str]) -> Dict:
        """提取单个候选命令的特征"""
        cmd_lower = cmd.lower()
        action_type = self._get_action_type(cmd_lower)

        # 1. 中文实体匹配度
        cn_args = task_features.get('cn_entities', {})
        entity_match = 0.0
        matched_entities = []
        for obj in cn_args.get('objects', []):
            en_names = CN_EN_MAP.get(obj, [])
            for en in en_names:
                if en in cmd_lower:
                    entity_match += 2.0
                    matched_entities.append(f"物体:{obj}")
                    break
        for loc in cn_args.get('locations', []):
            en_names = CN_EN_MAP.get(loc, [])
            for en in en_names:
                if en in cmd_lower:
                    entity_match += 1.5
                    matched_entities.append(f"位置:{loc}")
                    break
        for tool in cn_args.get('tools', []):
            en_names = CN_EN_MAP.get(tool, [])
            for en in en_names:
                if en in cmd_lower:
                    entity_match += 2.0
                    matched_entities.append(f"工具:{tool}")
                    break

        # 2. 动作类型匹配度
        subgoals = SUBGOAL_TEMPLATES.get(task_features['task_type'], [['go to']])
        target_actions = subgoals[phase] if phase < len(subgoals) else ['go to']
        action_match = 1.0 if action_type in target_actions else 0.0

        # 3. 历史失败惩罚
        fail_penalty = sum(0.35 for h in history[-10:] if h == cmd)

        # 4. 邻域探索度
        explored_count = sum(1 for h in history if self._get_action_type(h) == action_type)

        # 5. 六爻编码
        ylyw_feats = self._cmd_to_ylyw_features(action_type, phase, task_features)
        perception = self.manual.perceive_and_encode(ylyw_feats)
        ylyw_score = perception['hexagram_match_score']
        hexagram_name = perception['best_hexagram'].name if perception['best_hexagram'] else '无'

        features = {
            'entity_match_score': entity_match,
            'action_match_score': action_match,
            'fail_penalty': fail_penalty,
            'explored_similar': explored_count,
            'ylyw_score': ylyw_score,
            'hexagram': hexagram_name,
            'yao_vector': perception['yao_vector'].tolist(),
            'matched_entities': matched_entities,
            'action_type': action_type,
        }
        return features

    def _get_action_type(self, cmd: str) -> str:
        cmd_lower = cmd.strip().lower()
        for at in ACTION_TYPES:
            if cmd_lower.startswith(at):
                return at
        return 'go to'

    def _cmd_to_ylyw_features(self, action_type: str, phase: int,
                               task_features: Dict) -> Dict:
        """命令→六爻特征向量（扩展版）"""
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
        elif action_type in ('clean', 'heat', 'cool'):
            base.update({'stability': 0.4, 'fragility': 0.4, 'task_priority': 0.5})
        elif action_type == 'use' or action_type == 'toggle':
            base.update({'stability': 0.4, 'task_priority': 0.6})

        # 阶段影响
        n_subgoals = task_features.get('n_subgoals', 4)
        progress = phase / max(n_subgoals, 1)
        base['task_priority'] = min(1.0, base['task_priority'] * (1.0 + progress * 0.5))

        return base

    def aggregate_yao_vector(self, base_features: Dict,
                              task_features: Dict,
                              history: List[str]) -> List[float]:
        """聚合多源特征为6维六爻向量"""
        cn_args = task_features.get('cn_entities', {})
        n_objects = len(cn_args.get('objects', []))
        n_locations = len(cn_args.get('locations', []))
        n_tools = len(cn_args.get('tools', []))
        n_entities = n_objects + n_locations + n_tools

        # 6维向量
        yao = [
            # 初爻(基础稳定性): 实体丰富度
            min(1.0, n_entities / 5.0),
            # 二爻(可达性): 目标位置明确度
            min(1.0, n_locations / 2.0),
            # 三爻(力需求): 任务复杂度
            min(1.0, task_features.get('n_subgoals', 4) / 8.0),
            # 四爻(脆弱性): 已探索比例（探索越多越脆弱，需要收敛）
            min(1.0, len(set(h for h in history)) / 20.0),
            # 五爻(任务优先级): 已经耗时比例
            min(1.0, len(history) / MAX_STEPS),
            # 上爻(环境约束): 已获取物体数
            min(1.0, sum(1 for h in history if self._get_action_type(h) == 'take') / 3.0),
        ]
        return yao


class YLYWChineseV4Agent:
    """
    YLYW 中文推理 Agent V4

    完全中文化 + 丰富特征 + 详细推理输出
    """

    def __init__(self, verbose=False, use_oracle_type=True):
        self.verbose = verbose
        self.use_oracle_type = use_oracle_type
        self.cn_parser = YLYWChineseSemanticParser()
        self.feature_extractor = ChineseFeatureExtractor()
        self.manual = PriorManual(verbose=False)
        self.current_phase = 0

    def infer_task_type(self, task_desc: str, ground_truth: str = None) -> str:
        """推断任务类型"""
        if self.use_oracle_type and ground_truth:
            self._task_features = self.feature_extractor.extract_task_features(task_desc, ground_truth)
            return ground_truth
        result = self.cn_parser.parse_task_desc(task_desc)
        tt = result['task_type']
        self._task_features = self.feature_extractor.extract_task_features(task_desc, tt)
        return tt

    def infer_subgoals(self, task_type: str) -> List[List[str]]:
        return SUBGOAL_TEMPLATES.get(task_type, [['go to'], ['take'], ['go to'], ['put']])

    def _get_action_type(self, cmd: str) -> str:
        cmd_lower = cmd.strip().lower()
        for at in ACTION_TYPES:
            if cmd_lower.startswith(at):
                return at
        return 'go to'

    def decide(self, admissible_commands: List[str],
               current_phase: int, task_type: str,
               history: List[str], task_desc: str = "") -> Dict:
        """
        中文推理决策主函数

        Returns:
            dict: {
                'action': str,           # 选择的英文动作
                'cn_action': str,        # 中文动作描述
                'reasoning': {...},      # 完整推理链
                'confidence': float,     # 置信度
            }
        """
        # 1. 任务特征提取
        task_features = getattr(self, '_task_features', {})
        if not task_features:
            task_features = self.feature_extractor.extract_task_features(task_desc, task_type)
            self._task_features = task_features

        cn_entities = task_features.get('cn_entities', {})
        subgoals = self.infer_subgoals(task_type)
        target_actions = subgoals[current_phase] if current_phase < len(subgoals) else ['go to']

        # 2. 聚合六爻向量（全局状态）
        global_yao = self.feature_extractor.aggregate_yao_vector(
            {}, task_features, history)

        # 3. 对每个候选命令评分
        candidates_scored = []
        for cmd in admissible_commands:
            cf = self.feature_extractor.extract_cmd_features(
                cmd, task_features, current_phase, history)
            total = (cf['entity_match_score'] * 2.0 +
                     cf['action_match_score'] * 3.0 +
                     cf['ylyw_score'] * 2.0 -
                     cf['fail_penalty'] +
                     cf['explored_similar'] * 0.1)
            candidates_scored.append({
                'cmd': cmd,
                'total_score': total,
                'entity_match': cf['entity_match_score'],
                'action_match': cf['action_match_score'],
                'ylyw_score': cf['ylyw_score'],
                'hexagram': cf['hexagram'],
                'yao_vector': cf['yao_vector'],
                'matched_entities': cf['matched_entities'],
                'action_type': cf['action_type'],
            })

        # 4. 排序选最佳
        candidates_scored.sort(key=lambda x: x['total_score'], reverse=True)
        best = candidates_scored[0] if candidates_scored else {}

        # 5. 中文动作名
        cn_action = self._cmd_to_cn(best.get('cmd', 'look'))
        phase_name = SUBGOAL_CN_NAMES.get(target_actions[0] if target_actions else '', '未知')
        target_actions_cn = [SUBGOAL_CN_NAMES.get(a, a) for a in target_actions]

        # 6. 构建推理链
        reasoning = {
            'phase': current_phase,
            'phase_goal': phase_name,
            'target_actions': target_actions_cn,
            'cn_task': task_features.get('cn_text', ''),
            'target_entities': cn_entities,
            'global_state_yao': global_yao,
            'candidates_ranked': candidates_scored[:5],
            'selected_cmd': best.get('cmd', ''),
            'selected_reason': self._build_reason(best, current_phase, history),
        }

        # 7. 置信度
        confidence = best.get('total_score', 0) / 15.0 if candidates_scored else 0.0
        confidence = min(1.0, max(0.0, confidence))

        return {
            'action': best.get('cmd', admissible_commands[0] if admissible_commands else 'look'),
            'cn_action': cn_action,
            'reasoning': reasoning,
            'confidence': confidence,
        }

    def _cmd_to_cn(self, cmd: str) -> str:
        """英文命令→中文描述"""
        at = self._get_action_type(cmd)
        return SUBGOAL_CN_NAMES.get(at, cmd)

    def _build_reason(self, best_candidate: Dict, phase: int, history: List[str]) -> str:
        """构建选择理由"""
        if not best_candidate:
            return '无可用候选动作'
        reasons = []
        if best_candidate.get('entity_match', 0) > 0:
            entities = best_candidate.get('matched_entities', [])
            reasons.append(f"匹配到中文实体: {', '.join(entities[:3])}")
        if best_candidate.get('action_match', 0) > 0:
            reasons.append(f"动作类型匹配当前阶段目标")
        if best_candidate.get('ylyw_score', 0) > 0.5:
            reasons.append(f"YLYW卦象匹配: {best_candidate.get('hexagram', '?')} (得分{best_candidate['ylyw_score']:.2f})")
        if not reasons:
            reasons.append('常规探索')
        return '; '.join(reasons)

    def update_phase(self, action: str, current_phase: int) -> int:
        """根据动作推进阶段"""
        at = self._get_action_type(action)
        if at == 'take':
            return current_phase + 1
        if at in ('put', 'use', 'clean', 'heat', 'cool', 'slice') and current_phase >= 2:
            return current_phase + 1
        return current_phase

    def run_game(self, env, config, game_idx: int, verbose: bool = False) -> Dict:
        """在AlfredTWEnv上运行一个游戏"""
        game_file = env.game_files[game_idx]
        game_dir = os.path.dirname(game_file)
        with open(os.path.join(game_dir, 'traj_data.json')) as f:
            traj_data = json.load(f)

        task_desc = traj_data['turk_annotations']['anns'][0].get('task_desc', '')
        task_type_real = traj_data.get('task_type', '')
        gt_type = task_type_real if self.use_oracle_type else None

        inferred_type = self.infer_task_type(task_desc, ground_truth=gt_type)
        cn_text = self._task_features.get('cn_text', task_desc)

        if verbose:
            print(f"\n{'='*60}")
            print(f"Game #{game_idx}: {task_type_real}")
            print(f"EN: {task_desc}")
            print(f"CN: {cn_text}")
            print(f"Type: {inferred_type}")
            print(f"Entities: {self._task_features.get('cn_entities', {})}")
            print(f"Subgoals: {len(SUBGOAL_TEMPLATES.get(inferred_type, []))} phases")
            print(f"{'='*60}")

        # 初始化官方环境
        gym_env = env.init_env(batch_size=1)
        obs, info = gym_env.reset()
        if isinstance(obs, tuple):
            obs = obs[0]
        if isinstance(info, dict) and 'admissible_commands' in info:
            cmds = info['admissible_commands']
            if isinstance(cmds, list) and cmds and isinstance(cmds[0], list):
                cmds = cmds[0]
        elif isinstance(info, list) and info:
            info = info[0]
            cmds = info.get('admissible_commands', ['look'])
        else:
            cmds = ['look']

        if verbose:
            print(f"初始观察: {obs[:150]}...")
            print(f"初始可选命令({len(cmds)}): {cmds[:6]}...")

        current_phase = 0
        history = []
        steps = 0
        won = False
        decisions = []

        while steps < MAX_STEPS:
            # 获取admissible_commands
            cmds = info.get('admissible_commands', ['look'])
            if isinstance(cmds, list) and cmds and isinstance(cmds[0], list):
                cmds = cmds[0]

            # 中文推理决策
            decision = self.decide(cmds, current_phase, inferred_type,
                                    history, task_desc)
            action = decision['action']
            decisions.append(decision)

            if verbose:
                d = decision
                print(f"\n  Step {steps:2d}: phase={current_phase}")
                print(f"    选择: {action}  ({d['cn_action']})")
                print(f"    信心: {d['confidence']:.2f}")
                if d['reasoning']['selected_reason']:
                    print(f"    理由: {d['reasoning']['selected_reason']}")
                if d['reasoning']['candidates_ranked']:
                    top3 = d['reasoning']['candidates_ranked'][:3]
                    top3_str = [(c['cmd'], round(c['total_score'], 1)) for c in top3]
                    print(f"    Top3: {top3_str}")

            # 执行动作
            obs, _, done_flag, info = gym_env.step([action])
            history.append(action)
            steps += 1

            if isinstance(info, list) and info:
                info = info[0]

            if info.get('won'):
                # won可能是列表
                if isinstance(info['won'], list):
                    won = info['won'][0]
                else:
                    won = info['won']
                if won:
                    break

            current_phase = self.update_phase(action, current_phase)

        gym_env.close()

        result = {
            'game_idx': game_idx,
            'task_type_real': task_type_real,
            'task_type_inferred': inferred_type,
            'type_correct': inferred_type == task_type_real,
            'task_desc': task_desc[:80],
            'cn_task': cn_text[:80],
            'steps': steps,
            'won': won,
            'decisions': decisions[:10],  # 保存前10步的推理
            'confidence_avg': sum(d['confidence'] for d in decisions) / len(decisions) if decisions else 0,
        }

        if verbose:
            print(f"\n  {'WON' if won else 'LOST'} in {steps} steps")
            print(f"  Avg confidence: {result['confidence_avg']:.2f}")

        return result


def run_all_games(env, config, agent: YLYWChineseV4Agent,
                  verbose=False, max_games=0):
    """跑全部游戏"""
    results = []
    n = len(env.game_files)
    if max_games > 0:
        n = min(n, max_games)

    print(f"\n运行 {n}/{len(env.game_files)} 个游戏 (YLYW中文V4) ...")
    start = time.time()

    for i in range(n):
        result = agent.run_game(env, config, i, verbose=verbose)
        results.append(result)
        wins = sum(1 for r in results if r['won'])
        elapsed = time.time() - start
        avg_conf = sum(r['confidence_avg'] for r in results) / len(results)
        print(f"  [{i+1}/{n}] Game {i}: {'WON' if result['won'] else 'LOST'} "
              f"({result['task_type_real']:35s}) {result['steps']}步 "
              f"[累计: {wins}/{i+1} = {wins/(i+1)*100:.1f}%] "
              f"[conf:{result['confidence_avg']:.2f}] [{elapsed:.0f}s]")

    elapsed = time.time() - start
    total_wins = sum(1 for r in results if r['won'])
    total_steps = sum(r['steps'] for r in results)

    print(f"\n{'='*60}")
    print(f"  YLYW ALFWorld V4 Results")
    print(f"{'='*60}")
    print(f"  Total:   {len(results)}")
    print(f"  Won:     {total_wins}")
    print(f"  Rate:    {total_wins/len(results)*100:.1f}%")
    print(f"  Avg Ste: {total_steps/len(results):.1f}")
    print(f"  Avg Con: {sum(r['confidence_avg'] for r in results)/len(results):.2f}")
    print(f"  Elapsed: {elapsed:.1f}s")

    by_type = defaultdict(list)
    for r in results:
        by_type[r['task_type_real']].append(r)
    print(f"\n  By Task Type:")
    for t, rs in sorted(by_type.items()):
        tw = sum(1 for r in rs if r['won'])
        ts = sum(r['steps'] for r in rs)
        print(f"    {t:40s}: {tw}/{len(rs)} ({tw/len(rs)*100:.1f}%) avg={ts/len(rs):.1f}步")

    return results


def make_config(data_path=None):
    """AlfredTWEnv配置"""
    if data_path is None:
        from alfworld.info import ALFWORLD_DATA
        data_path = os.path.join(ALFWORLD_DATA, 'json_2.1.1')
    return {
        'env': {
            'task_types': [1, 2, 3, 4, 5, 6, 7],
            'goal_desc_human_anns_prob': 0,
            'domain_randomization': False,
            'expert_type': 'handcoded',
        },
        'dataset': {
            'eval_ood_data_path': os.path.join(data_path, 'valid_unseen'),
            'num_eval_games': 0,
        },
        'general': {
            'training_method': 'dagger',
        },
        'dagger': {
            'training': {'max_nb_steps_per_episode': MAX_STEPS},
        },
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='single', choices=['single', 'all', 'debug'])
    parser.add_argument('-n', '--num', type=int, default=1)
    parser.add_argument('--game', type=int, default=0)
    parser.add_argument('--verbose', action='store_true', default=True)
    args = parser.parse_args()

    import alfworld.agents.environment as environment

    config = make_config()
    print("Creating AlfredTWEnv...")
    env = environment.get_environment('AlfredTWEnv')(config, train_eval="eval_out_of_distribution")
    print(f"Loaded {len(env.game_files)} game files")

    agent = YLYWChineseV4Agent(verbose=args.verbose, use_oracle_type=True)

    if args.mode == 'single':
        agent.run_game(env, config, args.game, verbose=True)
    elif args.mode == 'all':
        run_all_games(env, config, agent, verbose=False,
                      max_games=args.num if args.num > 1 else 0)
    elif args.mode == 'debug':
        # debug模式：只测试特征提取
        game_file = env.game_files[args.game]
        game_dir = os.path.dirname(game_file)
        with open(os.path.join(game_dir, 'traj_data.json')) as f:
            traj_data = json.load(f)
        task_desc = traj_data['turk_annotations']['anns'][0].get('task_desc', '')
        task_type_real = traj_data.get('task_type', '')
        print(f"\nGame {args.game}: {task_type_real}")
        print(f"Task: {task_desc}")
        print(f"\n中文特征提取:")
        feat = agent.feature_extractor.extract_task_features(task_desc, task_type_real)
        print(f"  CN: {feat['cn_text']}")
        print(f"  Entities: {feat['cn_entities']}")
        print(f"  Action density: {feat['action_density']:.2f}")
        print(f"  Object density: {feat['object_density']:.2f}")
        print(f"  Location density: {feat['location_density']:.2f}")
        print(f"  N subgoals: {feat['n_subgoals']}")
        print(f"\n聚合六爻向量:")
        yao = agent.feature_extractor.aggregate_yao_vector({}, feat, [])
        print(f"  {[f'{v:.2f}' for v in yao]}")
