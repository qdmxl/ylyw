#!/usr/bin/env python3
"""
V19 Agent — 继承V18的AgentV18，在stuck恢复点增加易理诊断分支

核心改动：
  在productive(alive)为空触发recovery时，
  先调用 V19YLYWScorer.diagnose() 做爻位关系分析，
  根据诊断结果选择不同的恢复策略，而非一刀切frontier重置。
"""

import sys, os, copy, random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'v18'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from agent_v18 import AgentV18
from v19_scorer import V19YLYWScorer

_INFO_VERBS = {'look', 'examine', 'inventory'}

class AgentV19(AgentV18):
    """
    V19 Agent: V18底座 + 易理诊断的stuck恢复
    """
    
    def __init__(self, log_path=None, verbose=False, ylyw_mode="full", seed=0, alpha=0.3):
        super().__init__(log_path=log_path, verbose=verbose, ylyw_mode="linear", seed=seed)
        # 用V19评分器取代V18
        self.scorer = V19YLYWScorer(mode=ylyw_mode, alpha=alpha)
        self._ylyw_mode = ylyw_mode
        self._last_diagnosis = None
        self._just_force_acted = False  # 避免同一步连续强制动作
        self._precomputed_ctx = None  # 当前step预计算的卦象上下文
        
    def _score_all(self, admissible, phase):
        """
        覆盖V18._score_all：利用预计算上下文加速，避免每candidate重复感知
        """
        # 每步首次调用时预计算情境卦象
        if self._precomputed_ctx is None:
            self._precomputed_ctx = self.scorer.precompute_context(self.world, self.goal, phase)
        cands = []
        for cmd in admissible:
            if cmd == "help":
                continue
            c = self.scorer.score_candidate(cmd, self.world, self.goal, phase,
                                              precomputed=self._precomputed_ctx)
            vetoed, reason = self._veto(c, phase)
            c.vetoed = vetoed
            c.veto_reason = reason
            cands.append(c)
        return cands
        
    def reset_state(self):
        """覆盖V18 reset_state，确保V19字段也重置"""
        super().reset_state()
        self._just_force_acted = False
        self._last_diagnosis = None
    
    def act(self, obs: str, admissible: List[str]) -> str:
        """覆盖V18的act，在recovery点插入易理诊断"""
        # 新步开始时清空预计算缓存，确保重新感知当前情境
        self._precomputed_ctx = None
        # 复用V18的逻辑但保留自己的recovery
        return self._act_with_ylyw_recovery(obs, admissible)
    
    def _act_with_ylyw_recovery(self, obs, admissible):
        """带有易理诊断的act"""
        self.step_idx += 1  # V18在act入口自增
        # === V18原始逻辑（简化版）===
        g = self.goal
        phase = self._phase()
        phase = self._maybe_retry(phase, admissible)
        
        cands = self._score_all(admissible, phase)
        alive = [c for c in cands if not c.vetoed]
        
        def productive(cs):
            return [c for c in cs if c.parsed["verb"] not in _INFO_VERBS]
        
        # === V19：易理诊断的stuck恢复 ===
        # 如果上一步已经强制动作（如look_fix），跳过recovery，等环境返回
        if self._just_force_acted:
            self._just_force_acted = False
            # 但继续normal pool选动作
        elif not productive(alive) and self._recoveries < 6:
            self._recoveries += 1
            
            # 易理诊断
            diagnosis, suggestion = self.scorer.stuck_advice(
                self.world, self.goal, phase
            )
            self._last_diagnosis = (diagnosis, suggestion)
            
            if self.verbose:
                print(f"  [V19诊断] {diagnosis} | {suggestion or 'frontier恢复'}")
            
            if diagnosis == 'external_resistance':
                # 外部阻力大：不要重置全部，而是优先开容器
                for r in self.world.receps.values():
                    if not r.searched:
                        r.searched = False  # 保留未search的
                    else:
                        r.searched = True   # 已搜索的不动
                # 强制开放所有已知未开容器
                self._force_open_containers()
                
            elif diagnosis == 'strategy_mismatch':
                # 策略不匹配：切换目标方向
                # 清空搜索标记，强制从另一方向开始
                for r in self.world.receps.values():
                    r.searched = False
                    r.exhausted = False
                self.world.failed_sa.clear()
                # 减少已拿物品计数：给agent一次重试机会
                if self._recoveries <= 3:
                    phase['searching'] = True
                    
            elif diagnosis == 'lost_direction':
                # 方向迷茫：扩大搜索范围，降低目标约束
                for r in self.world.receps.values():
                    r.searched = False
                    r.exhausted = False
                # 引入随机偏移
                self._cmd_count.clear()
                
            elif diagnosis == 'attention_mismatch':
                # 注意力偏差：强制look一次重新评估
                # 重置stale但不重置frontier
                look_cmds = [c for c in admissible if c.startswith('look ')]
                if look_cmds:
                    cand = self.scorer.score_candidate(
                        look_cmds[0], self.world, self.goal, phase
                    )
                    cand.vetoed = False
                    phase = self._phase()
                    cands = self._score_all(admissible, phase)
                    alive = [c for c in cands if not c.vetoed]
            
            elif diagnosis == 'look_task_fix':
                # look_at灯任务：强制use命令优先
                # 检查是否有use命令在admissible中
                use_cmds = [c for c in admissible if c.startswith('use ')]
                if use_cmds:
                    # 直接选use命令，跳过评分
                    best_cmd = use_cmds[0]
                    from ylyw_scorer import Candidate, parse_action
                    parsed = parse_action(best_cmd)
                    best = Candidate(best_cmd, parsed, yao=[0.5]*6,
                                      ylyw_score=1.0, linear_score=1.0)
                    if self.verbose:
                        print(f'  [V19-look_fix] 强制使用: {best_cmd}')
                    self._decision_logs.append({
                        'step': self.step_idx, 'v19_diagnosis': ('look_task_fix', use_cmds[0]),
                        'chosen': best_cmd, 'chosen_hex': '', 'chosen_hex_cn': ''
                    })
                    self._just_force_acted = True
                    return best_cmd
                # 没有use命令→需要先走到灯的位置
                # 检查admissible中是否有灯的go命令
                lamp_go = [c for c in admissible if 'desklamp' in c or 'lamp' in c]
                if lamp_go:
                    best_cmd = lamp_go[0]
                    from ylyw_scorer import Candidate, parse_action
                    parsed = parse_action(best_cmd)
                    best = Candidate(best_cmd, parsed, yao=[0.5]*6,
                                      ylyw_score=1.0, linear_score=1.0)
                    if self.verbose:
                        print(f'  [V19-look_fix] 强制去灯: {best_cmd}')
                    self._decision_logs.append({
                        'step': self.step_idx, 'v19_diagnosis': ('look_task_fix', best_cmd),
                        'chosen': best_cmd, 'chosen_hex': '', 'chosen_hex_cn': ''
                    })
                    self._just_force_acted = True
                    return best_cmd
                # 降落：V18原始
                for r in self.world.receps.values():
                    r.searched = False
                    r.exhausted = False
                self.world.failed_sa.clear()
                
            elif diagnosis == 'stagnant_perception':
                # 感知退化：用随机探索打破
                explore_cmds = [c for c in admissible if c.startswith('go to ')]
                if explore_cmds:
                    import random
                    best_cmd = random.choice(explore_cmds)
                    from ylyw_scorer import Candidate, parse_action
                    parsed = parse_action(best_cmd)
                    best = Candidate(best_cmd, parsed, yao=[0.5]*6,
                                      ylyw_score=0.5, linear_score=0.5)
                    if self.verbose:
                        print(f'  [V19-stagnant] 随机探索: {best_cmd}')
                    self._decision_logs.append({
                        'step': self.step_idx, 'v19_diagnosis': ('stagnant_perception', best_cmd),
                        'chosen': best_cmd, 'chosen_hex': '', 'chosen_hex_cn': ''
                    })
                    self._just_force_acted = True
                    return best_cmd
                for r in self.world.receps.values():
                    r.searched = False
                    r.exhausted = False
                self.world.failed_sa.clear()
                
            else:  # frontier_exhausted / 默认
                # V18原始逻辑
                for r in self.world.receps.values():
                    r.searched = False
                    r.exhausted = False
                self.world.failed_sa.clear()
            
            # 重新评分
            phase = self._phase()
            cands = self._score_all(admissible, phase)
            alive = [c for c in cands if not c.vetoed]
        
        # === V18剩余逻辑（不变）===
        prod = productive(alive)
        pool = prod if prod else (alive if alive else cands)
        best = max(pool, key=lambda c: c.ylyw_score)
        
        if best.parsed["verb"] == "look":
            self._look_used += 1
        self._cmd_count[best.cmd] = self._cmd_count.get(best.cmd, 0) + 1
        
        # decision log
        ranked = sorted(cands, key=lambda c: c.ylyw_score, reverse=True)
        rec = {
            "step": self.step_idx,
            "game_id": self.game_id,
            "phase": {k: v for k, v in phase.items()},
            "goal": self.goal.as_dict(),
            "location": self.world.location,
            "chosen": best.cmd,
            "chosen_hex": best.hexagram,
            "chosen_hex_cn": best.hex_cn,
            "n_candidates": len(cands),
            "n_alive": len(alive),
            "candidates": [c.log() for c in ranked[:12]],
            "v19_diagnosis": self._last_diagnosis,
        }
        self._decision_logs.append(rec)
        if self.verbose:
            print(f"[{self.step_idx}] {best.cmd}  <{best.hex_cn}> "
                  f"score={best.ylyw_score:.3f} alive={len(alive)}/{len(cands)} "
                  f"[v19:{self._last_diagnosis[0] if self._last_diagnosis else 'none'}]")
        return best.cmd
    
    def _force_open_containers(self):
        """优先打开已知未开容器"""
        for r in self.world.receps.values():
            if hasattr(r, 'is_open') and not r.is_open and r.visited:
                # 标记为可尝试打开
                r.exhausted = False
                if r.visited and not r.searched:
                    r.searched = False  # 允许尝试


def test_agent_v19():
    """快速测试V19 Agent能否在环境中运行"""
    import os
    os.environ['ALFWORLD_DATA'] = os.path.expanduser('~/.cache/alfworld')
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    from alfworld_official_wrapper import ALFWorldOfficial
    
    env = ALFWorldOfficial(split='valid_unseen')
    agent = AgentV19(log_path=None, verbose=True, alpha=0.3)
    
    obs, info = env.reset(game_idx=0)
    adm = info.get('admissible_commands', ['look'])
    agent.reset(info.get('task_desc', ''), obs, adm, game_id=0)
    
    won = False
    for step in range(50):
        action = agent.act(obs, adm)
        obs, info = env.step(action)
        won = bool(info.get('won', False))
        adm = info.get('admissible_commands', ['look'])
        agent.observe_transition(action, obs, adm, won=won)
        if won or info.get('done', False):
            break
    
    print(f"Game 0: {'WON' if won else 'LOST'}")
    return won


if __name__ == "__main__":
    test_agent_v19()
