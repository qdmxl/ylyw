#!/usr/bin/env python3
"""
agent_v20.py — V20 汉字YLYW Agent

核心改造：用 cn_world_model.CnWorldModel 替代 V18的 world_model.WorldModel
所有环境状态通过汉字+YLYW卦象表示。

V18 → V20 变化：
  world_model.WorldModel → cn_world_model.CnWorldModel
    - 状态更新：正则解析英文 → YLYW汉字卦象感知
    - 实体表示：Python dataclass → GuaReceptacle/GuaObject（含卦象）
    - 情境理解：无 → 实时卦象计算
    
  其他保持不变（继承V18的决策逻辑）：
    - goal_parser（任务解析，保持英文NL）
    - ylyw_scorer（六爻编码+64卦评分，复用）
    - veto逻辑（失败历史过滤）
    - _phase/_maybe_retry（阶段计算、重试）
"""
from __future__ import annotations
import os, sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "v18"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_v18 import AgentV18
from v20.cn_world_model import CnWorldModel


class AgentV20(AgentV18):
    """
    V20 汉字YLYW Agent
    
    与V18完全相同的决策逻辑，但世界模型替换为CnWorldModel。
    所以agent的act()行为不变，但世界感知方式变为汉字+YLYW卦象。
    """
    
    def __init__(self, log_path=None, verbose=False, ylyw_mode="full", seed=0):
        super().__init__(log_path=log_path, verbose=verbose, ylyw_mode=ylyw_mode, seed=seed)
    
    def reset_state(self):
        """覆盖V18：用CnWorldModel替代WorldModel"""
        self.goal = None
        self.world = CnWorldModel()      # ← 替换为汉字世界模型
        self.step_idx = 0
        self._look_used = 0
        self._decision_logs = []
        self.game_id = None
        self.task_desc = ""
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
    
    def dump_logs(self, extra=None, final=False):
        """覆盖V18：在回放日志末尾保存知识库"""
        if final:
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
    # 简单测试：创建agent并验证接口兼容性
    agent = AgentV20(verbose=True)
    
    # 测试reset
    agent.reset(
        "put a clean apple in fridge",
        "You are in kitchen. You see a counter 1. On the counter 1, you see a apple 1.",
        ["go to counter 1", "go to fridge 1", "go to sinkbasin 1", "go to apple 1", "look", "inventory"]
    )
    
    print("=== AgentV20 初始化成功 ===")
    print(f"世界模型类型: {type(agent.world).__name__}")
    print(f"容器数量: {len(agent.world.receps)}")
    print(f"物体数量: {len(agent.world.objs)}")
    for oid, o in agent.world.objs.items():
        print(f"  物体 {oid}: 汉字={o.hanzi} 卦={o.dom_gua}")
    for rid, r in agent.world.receps.items():
        print(f"  容器 {rid}: 汉字={r.hanzi} 卦={r.dom_gua}")
    gua, yao = agent.world.get_situation_gua()
    print(f"情境卦象: {gua} 六爻={[round(v,2) for v in yao]}")
