#!/usr/bin/env python3
"""
YLYW 任务规划器 — 主模块

整合 StateEncoder + IntentionDecoder + CandidateGenerator 的完整规划循环。

架构：
  1. 从obs文本解析当前状态 → StateEncoder 生成中文状态词 → 卦爻向量
  2. 卦名+六爻 → IntentionDecoder 解码为规划意图
  3. 意图 → 从obs解析的候选中选择动作（不依赖admissible_commands）
  4. 每局结束后，用知几学习机制更新卦→意图映射

与V14的关键区别：
  V14: 自定义6变量+8规则 → 意图 → admissible匹配
  本模块: 汉字卦爻推理 → 卦名+六爻 → 意图 → obs解析的候选匹配
  
V14和V10-V13的所有admissible依赖在此被彻底切断。
"""

import os, sys, json, time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# 确保能导入子模块和hanzi_engine
_module_dir = os.path.dirname(os.path.abspath(__file__))
_lang_dir = os.path.join(os.path.dirname(_module_dir), 'language')
_ylyw_core_dirs = [
    os.path.join(os.path.dirname(_module_dir), 'api_docs'),
    os.path.join(os.path.dirname(_module_dir), 'experiment_phase1'),
]
for d in _ylyw_core_dirs:
    if d not in sys.path:
        sys.path.insert(0, d)
for d in (_lang_dir, _module_dir):
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from hanzi_engine import HanziEngine, BAGUA, _HRULE
    from ylyw_core import Hexagram
    _YLYW_OK = True
except ImportError as e:
    _YLYW_OK = False
    print(f"[WARN] ylyw_core import: {e}")

from state_encoder import StateEncoder, EN_OBJ_CN, EN_LOC_CN, TOOL_CN_MAP
from intention_decoder import IntentionDecoder, INTENT_TYPES
from candidate_generator import CandidateGenerator


class YLYWTaskPlanner:
    """
    YLYW 任务规划器主模块。

    一次完整规划循环：
      step(obs) → {
          状态编码 → 卦爻推理 → 意图解码 → 候选生成 → 动作选择
      }

    不依赖admissible_commands，所有信息从obs文本解析。
    纯YLYW决策，无LLM、无外部API。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        if not _YLYW_OK:
            raise ImportError("ylyw_core + hanzi_engine required")

        self.encoder = StateEncoder(verbose=verbose)
        self.decoder = IntentionDecoder(verbose=verbose)
        self.generator = CandidateGenerator(verbose=verbose)

        # 历史记录（用于知几学习）
        self.hexagram_history: List[Tuple[str, List[float], str]] = []
        self.action_history: List[str] = []

        # 当前状态
        self.current_intent = ''
        self.current_hexagram = ''

    def reset(self, task_desc: str, task_type: str = '',
              initial_obs: str = ''):
        """开始新任务"""
        self.encoder.reset(task_desc, task_type, initial_obs)
        self.generator.reset(task_desc, task_type, initial_obs)
        self.hexagram_history = []
        self.action_history = []

        if self.verbose:
            target_obj = self.encoder.target_obj_cn or '?'
            target_loc = self.encoder.target_loc_cn or '?'
            tool_loc = self.encoder.tool_loc_cn or '?'
            print(f"\n[Planner] 新任务: obj={target_obj} "
                  f"loc={target_loc} tool={tool_loc}")
            print(f"[Planner] task_type: {task_type}")

    # ══════════════════════════════════════════════════════════
    # 核心接口
    # ══════════════════════════════════════════════════════════

    def step(self, obs: str, action: str = '',
             action_success: bool = True) -> str:
        """
        一步规划循环。

        Args:
            obs: 环境返回的观测文本
            action: 上一步执行的动作（用于更新状态，首次为空）
            action_success: 上一步是否成功

        Returns:
            下一步动作字符串
        """
        # 1. 更新环境状态
        self.encoder.update_from_obs(obs, action, action_success)
        self.generator.update(obs, action, action_success)
        if action:
            self.action_history.append(action)

        # 2. 编码状态 → 卦爻
        state = self.encoder.encode_state()
        yao = state['yao_vector']
        hexagram = state['hexagram']

        # 3. 解码为意图
        context = {
            'task_type': self.encoder.task_type,
            'step': self.encoder.step,
        }
        intent_result = self.decoder.decode(hexagram, yao, context)
        intent = intent_result['intent']
        self.current_intent = intent
        self.current_hexagram = hexagram

        # 记录历史（包含上一步的动作）
        self.hexagram_history.append((hexagram, yao, intent))

        # 4. 生成候选动作
        candidates = self.generator.get_candidates(obs)

        # 5. 选择动作
        next_action = self.generator.select_action(
            intent, candidates, self.encoder.get_state_summary()
        )

        if self.verbose:
            summary = self.encoder.get_state_summary()
            loc = summary['loc_cn'][:6]
            hold = summary['holding'][:4]
            proc = '✓' if summary['processed'] else '✗'
            step_n = summary['step']
            print(f"  S{step_n:2d} [{loc:6s}] [{hold:4s}][{proc}] "
                  f"卦{intent_result['hexagram_cn']:8s} "
                  f"→ {intent:20s} → {next_action}")

        return next_action

    # ══════════════════════════════════════════════════════════
    # 学习接口
    # ══════════════════════════════════════════════════════════

    def observe_episode_result(self, won: bool):
        """
        从一局结果学习。

        知几机制：
          won=True → 正向强化该局用的卦→意图映射
          won=False → 负向抑制（假设意图选择有误）
        """
        self.decoder.observe_result(
            self.hexagram_history, won, self.encoder.task_type
        )
        if self.verbose:
            print(f"  [Planner] 学习结束: {'✓成功' if won else '✗失败'} "
                  f"({len(self.hexagram_history)}步)")

    def get_stats(self) -> Dict:
        """获取规划器统计"""
        return {
            'steps': self.encoder.step,
            'current_intent': self.current_intent,
            'current_hexagram': self.current_hexagram,
            'state': self.encoder.get_state_summary(),
            'history_len': len(self.hexagram_history),
        }

    def get_state_for_env(self) -> Dict:
        """返回给外部环境使用的状态信息（仅调试用途）"""
        return {
            'planner_intent': self.current_intent,
            'planner_hexagram': self.current_hexagram,
            'encoder_state': self.encoder.get_state_summary(),
        }

    # ══════════════════════════════════════════════════════════
    # 持久化
    # ══════════════════════════════════════════════════════════

    def save_experience(self, path_prefix: str):
        """保存知几学习经验"""
        self.decoder.save_experience(f'{path_prefix}_decoder.json')

    def load_experience(self, path_prefix: str):
        """加载知几学习经验"""
        decoder_path = f'{path_prefix}_decoder.json'
        if os.path.exists(decoder_path):
            self.decoder.load_experience(decoder_path)
            return True
        return False


# ══════════════════════════════════════════════════════════════
# 独立测试
# ══════════════════════════════════════════════════════════════

def test_planner():
    """用模拟obs测试规划器"""
    planner = YLYWTaskPlanner(verbose=True)

    # 模拟初始观测
    initial_obs = """-= Welcome to TextWorld, ALFRED! =-

    You are in the middle of a room. Looking quickly around you,
    you see a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3,
    a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 3,
    a countertop 2, a countertop 1, a drawer 3, a drawer 2,
    a drawer 1, a fridge 1, a garbagecan 1, a microwave 1,
    a shelf 3, a shelf 2, a shelf 1, a sinkbasin 1, a stoveburner 4,
    a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1."""

    task_desc = "Put a clean plate on the counter."
    task_type = "pick_clean_then_place_in_recep"

    planner.reset(task_desc, task_type, initial_obs)

    # 模拟几步
    steps = [
        ("", True, "初始"),
        ("You arrive at countertop 1. On the countertop 1, "
         "you see a apple 2, a dishsponge 2, and a plate 2.", True, "到柜台1"),
        ("You arrive at countertop 2. On the countertop 2, "
         "you see a bread 1, a cellphone 2, a mug 1, and a plate 1.", True, "到柜台2"),
        ("You pick up the plate 1 from the countertop 2.", True, "拿盘子"),
        ("You arrive at sinkbasin 1. On the sinkbasin 1, "
         "you see nothing.", True, "到水槽"),
        ("You clean the plate 1 with sinkbasin 1.", True, "清洗"),
        ("You arrive at countertop 3. On the countertop 3, "
         "you see a potato 1, and a tomato 1.", True, "到柜台3"),
    ]

    last_action = ""
    for obs_text, success, desc in steps:
        action = planner.step(obs_text, last_action, success)
        last_action = action
        print(f"  [{desc}] → {action}")

    # 模拟知几学习
    planner.observe_episode_result(won=True)

    print("\n测试完成。")


if __name__ == '__main__':
    test_planner()
