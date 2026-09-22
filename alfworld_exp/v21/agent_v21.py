#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_v21.py — V21 量子-易理 YLYW Agent (QYUF)

核心改进：
  V20: CnWorldModel（汉字+YLYW卦象）← HanziEngine 符号推理
  V21: CnWorldModel + QYUFScorer ← 六爻酉干涉量子演化 (§6.2.1)

变化点：
  agent_v20.py → agent_v21.py:
    - YLYWScorer → QYUFScorer（原L3模板匹配 → 量子酉演化）
    - 知识库 → QYUF量子参数自适应
    - 其余决策逻辑完全不变（可公平对比）
"""
from __future__ import annotations
import os, sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "v18"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_v18 import AgentV18
from v20.qyuf_world_model import QYUFWorldModel

# 引入 QYUF 量子评分器
_QYUF_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                    "ylyw", "QYUF", "experiment"))
if _QYUF_ROOT not in sys.path:
    sys.path.insert(0, _QYUF_ROOT)
from qyuf_model import QYUFScorer, QYUF_PARAMS


class AgentV21(AgentV18):
    """
    V21 量子-易理 Agent
    
    与V20相同的世界模型（CnWorldModel），
    但评分器替换为 QYUFScorer（基于六爻酉演化）。
    """
    
    def __init__(self, log_path=None, verbose=False, ylyw_mode="full", seed=0,
                 alpha: float = 0.0, experience_path: Optional[str] = None,
                 exp_note: str = ""):
        self.alpha = alpha
        self.exp_note = exp_note
        self._exp_path = experience_path
        self._won_reported = False
        super().__init__(log_path=log_path, verbose=verbose, ylyw_mode=ylyw_mode, seed=seed)
        # super().__init__()已经调了reset_state()，现在替换评分器
        self.scorer = QYUFScorer(params=QYUF_PARAMS.copy(), alpha=self.alpha,
                                 experience_path=self._exp_path)
    
    def reset_state(self):
        """覆盖V18：用CnWorldModel + QYUFScorer"""
        self.goal = None
        self.world = QYUFWorldModel()
        self.scorer = QYUFScorer(params=QYUF_PARAMS.copy(),
                                 alpha=getattr(self, 'alpha', 0.0),
                                 experience_path=getattr(self, '_exp_path', None))
        self.step_idx = 0
        self._look_used = 0
        self._decision_logs = []
        self.game_id = None
        self.task_desc = ""
        self._last_scores_reset = False
        self._last_action = None
        self._recoveries = 0
        self._deposited_failed = set()
        self._recep_failed = set()
        self._cmd_count = {}
        self._retry_events = 0
        self._count_bonus = 0
        self._l3_routed = 0
        self._retry_toggle = 0
        self._precomputed_ctx = None
        self._won_reported = False
    
    def observe_transition(self, action, obs2, admissible_after, won=False):
        if won and not self._won_reported:
            self._won_reported = True
            if self.alpha > 0 and hasattr(self.scorer, 'commit_game'):
                self.scorer.commit_game(won=True)
        super().observe_transition(action, obs2, admissible_after, won=won)
        # 负局结束时（done=True且未赢）也提交
        if self._won_reported and hasattr(self.scorer, 'commit_game'):
            pass  # 已提交
    
    def act(self, obs, admissible):
        """覆盖V18 act，在决策前重置评分列表并记录经验"""
        # 每轮决策前重置QYUF评分收集器
        if hasattr(self, 'scorer') and hasattr(self.scorer, '_last_scores'):
            self.scorer._last_scores = []
        action = super().act(obs, admissible)
        if self.alpha > 0 and hasattr(self.scorer, 'observe_decision'):
            try:
                phase = self._phase()
                # 从评分器取dict版本获取卦索引
                cand = self.scorer._score_candidate_dict(action, self.world, self.goal, phase)
                self.scorer.observe_decision(
                    cand['cmd'], self.world, self.goal, phase,
                    chosen_hex=cand['hex_idx'],
                    chosen_score=cand['qyuf_score'],
                    step=self.step_idx, game_id=self.game_id or 0,
                )
            except Exception:
                pass  # 学习失败不影响决策
        return action
    
    def dump_logs(self, extra=None, final=False):
        """保存量子参数和经验"""
        if final:
            if self.alpha > 0 and hasattr(self.scorer, 'commit_game'):
                self.scorer.commit_game(won=False)  # 被截断或done的局
            try:
                from v20.gua_knowledge_base import save_knowledge
                save_knowledge()
            except Exception:
                pass
        return super().dump_logs(extra=extra)


# ══════════════════════════════════════════════════════
# 评估入口
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    agent = AgentV21(verbose=True)
    agent.reset(
        "put a clean apple in fridge",
        "You are in kitchen. You see a counter 1. On the counter 1, you see a apple 1.",
        ["go to counter 1", "go to fridge 1", "go to sinkbasin 1", "look", "inventory"]
    )
    print("=== AgentV21 初始化成功 ===")
    print(f"评分器类型: {type(agent.scorer).__name__}")
    print(f"世界模型类型: {type(agent.world).__name__}")
    print(f"QYUF参数: {agent.scorer.params}")
    
    # 测试评分
    for cmd in ["go to counter 1", "take apple 1 from counter 1", "put apple 1 in/on fridge 1"]:
        cand = agent.score_candidate(cmd)
        print(f"  {cmd:40s} → {cand.hexagram} 分={cand.ylyw_score:.4f}")
