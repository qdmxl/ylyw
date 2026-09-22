#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent_v22.py — V22 知几式可学习H Agent
========================================
在 V21（QYUFScorer 六爻酉演化）基础上，实现论文§6.2限的回应：
让 H 的 5 个权重 (J_adj,J_ying,h_dang,h_zhong,J_comp) 从整局成败经验中
用"知几式频率校准+灵敏度归因"演化（选项B：替换概率输出层加权）。

对比 V21 的 delta：
  - QYUFScorer           → QYUFScorerLearnableH（学习沉入H权重，见 qyuf_learnable_h.py）
  - observe_decision     → record_decision_learn（记录主导候选的灵敏度归因）
  - commit_game          → 由基类链路调用，触发H权重θ的知几校准 + 重建酉算符
其余决策逻辑（_score_all / veto / recovery）完全不变，可公平对比。
"""
from __future__ import annotations
import os, sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "v18"))

from agent_v18 import AgentV18
from v20.qyuf_world_model import QYUFWorldModel

_QYUF_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                        "..", "..", "..", "ylyw", "QYUF", "experiment"))
if _QYUF_ROOT not in sys.path:
    sys.path.insert(0, _QYUF_ROOT)
from qyuf_learnable_h import QYUFScorerLearnableH, LEARNABLE_KEYS
from qyuf_model import QYUF_PARAMS


class AgentV22(AgentV18):
    """V22 知几式可学习H Agent"""

    def __init__(self, log_path=None, verbose=False, ylyw_mode="full", seed=0,
                 alpha: float = 0.0, experience_path: Optional[str] = None,
                 alpha_q: float = 0.08, alpha_s: float = 0.03,
                 exp_note: str = ""):
        self.alpha = alpha
        self.exp_note = exp_note
        self._exp_path = experience_path
        self.alpha_q = alpha_q
        self.alpha_s = alpha_s
        self._won_reported = False
        super().__init__(log_path=log_path, verbose=verbose,
                         ylyw_mode=ylyw_mode, seed=seed)
        self.scorer = QYUFScorerLearnableH(
            params=QYUF_PARAMS.copy(), alpha=self.alpha,
            experience_path=self._exp_path,
            alpha_q=self.alpha_q, alpha_s=self.alpha_s, seed=seed)
        self._learned_games = 0

    def reset_state(self):
        super().reset_state()
        from qyuf_model import QYUF_PARAMS
        self.scorer = QYUFScorerLearnableH(
            params=QYUF_PARAMS.copy(), alpha=getattr(self, 'alpha', 0.0),
            experience_path=getattr(self, '_exp_path', None),
            alpha_q=getattr(self, 'alpha_q', 0.08),
            alpha_s=getattr(self, 'alpha_s', 0.03),
            seed=getattr(self, 'seed', 0))

    def observe_transition(self, action, obs2, admissible_after, won=False):
        if won and not self._won_reported:
            self._won_reported = True
            if hasattr(self.scorer, 'commit_game'):
                self.scorer.commit_game(won=True)
                self._learned_games += 1
        super().observe_transition(action, obs2, admissible_after, won=won)

    def act(self, obs, admissible):
        if hasattr(self, 'scorer') and hasattr(self.scorer, '_last_scores'):
            self.scorer._last_scores = []
        action = super().act(obs, admissible)
        # 记录被选中最优候选的灵敏度归因（知几：记下这一"吉/凶征兆"的H归因）
        if hasattr(self.scorer, 'record_decision_learn'):
            try:
                chosen_cmd = getattr(self, '_decision_logs', [None])
                chosen_cmd = chosen_cmd[-1].get('chosen') if chosen_cmd and chosen_cmd[-1] else None
                if chosen_cmd:
                    cand = self.scorer._score_candidate_dict(
                        chosen_cmd, self.world, self.goal, self._phase())
                    yao = self.scorer.build_yao(
                        self.scorer._parse_action(chosen_cmd), self.world, self.goal, self._phase())
                    self.scorer.record_decision_learn(cand, yao)
            except Exception:
                pass
        return action

    def dump_logs(self, extra=None, final=False):
        if final:
            if hasattr(self.scorer, 'commit_game') and not self._won_reported:
                self.scorer.commit_game(won=False)
                self._learned_games += 1
            self._won_reported = True
            try:
                from v20.gua_knowledge_base import save_knowledge
                save_knowledge()
            except Exception:
                pass
        return super().dump_logs(extra=extra)


if __name__ == "__main__":
    from qyuf_model import QYUF_PARAMS
    agent = AgentV22(verbose=True)
    agent.reset(
        "put a clean apple in fridge",
        "You are in kitchen. You see a counter 1. On the counter 1, you see a apple 1.",
        ["go to counter 1", "go to fridge 1", "go to sinkbasin 1", "look", "inventory"]
    )
    print("=== AgentV22 初始化成功 ===")
    print(f"评分器类型: {type(agent.scorer).__name__}")
    print(f"初始H权重θ: {agent.scorer.theta_dict()}")
