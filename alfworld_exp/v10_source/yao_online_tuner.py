#!/usr/bin/env python3
"""
爻参数在线微调模块 (Yao Parameter Online Tuner)

《系辞》："爻者，言乎变者也。" —— 爻的本质是在变化中不断校准。

核心问题：
  知几+知耻学习只在整局结束后才做一次校准，缺少"局内实时微调"。
  特别是在抓取(take)→释放(put)的握持链中：
    1. 先拿了物体A → 环境状态变了
    2. 找到容器B → 尝试释放
    3. 释放失败了 → 需要立即微调"放什么、放哪里、怎么放"的爻参数
  如果等到整局跑完再校准，这局剩下的步骤已经白白浪费了。

核心公式：
  Yao_θ(t+1) = Yao_θ(t) + α × ∇_θ(action_feedback)
  
  其中：
    Yao_θ = 爻参数向量（每类物体×每类容器的释放置信度矩阵）
    α = 学习率（局内0.1-0.3，快速适应；跨局经验融合时0.01-0.05，稳定积累）
    action_feedback = 从动作成功/失败中提取的梯度

设计原则：
  - 纯规则，无LLM
  - 一次失败立即微调（"见几而作"）
  - 成功强化、失败惩罚
  - 释放爻参数：物体→容器匹配的置信度
  - 抓持爻参数：物体→位置的置信度

对比知几/知耻：
  知几(zhiji)   = 跨局正向校准 + 局部先验
  知耻(zhichi)  = 跨局负向校准 + 失败记忆
  爻调(yao_tune)= 局内在线微调 + 实时反馈
  知几+知耻+爻调 → 完整的三层学习体系
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict


class YaoOnlineTuner:
    """
    爻参数在线微调器。
    
    维护一组在每一局内实时更新的参数矩阵：
      - take_confidence: 物体类型 → 在该位置的可拿置信度（抓持爻）
      - release_confidence: 物体类型 → 目标容器类型的可放置信度（释放爻）
      - container_preference: 物体类型 → 容器类型（含子类型）的匹配倾向（容器爻）
    
    每次动作后立即更新，同一局内反复失败会快速调整。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # ====== 释放爻矩阵 ======
        # release_confidence[obj_base][rec_base] = score
        # score > 0: 认为该物体可以放到该容器
        # score < 0: 经验表明该物体不适合放该容器（或容器不适合该物体类型）
        # 初始值+2.0（适度乐观），每次失败-3.0（快速惩罚）
        self.release_confidence: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # ====== 抓持爻矩阵 ======
        # take_confidence[obj_base][loc_base] = score
        # 初始值0.0，成功take +2.0，该位置没找到目标物体 -1.0
        self.take_confidence: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # ====== 容器优先爻 ======
        # container_preference[obj_base][rec_full] = score  (含编号的完整名)
        # 比release_confidence更细粒度：针对具体容器（如 countertop 1 vs countertop 2）
        self.container_preference: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # ====== 在线统计 ======
        self._release_fail_count: Dict[tuple, int] = defaultdict(int)   # (obj_base, rec_base) → 失败次数
        self._release_success_count: Dict[tuple, int] = defaultdict(int) # (obj_base, rec_base) → 成功次数
        self._holding_history: List[Tuple[str, bool]] = []  # (action, success) 用于追踪抓-放链

        # 学习率
        self.alpha_take_success = 3.0     # 拿成功增益（加大正向）
        self.alpha_take_fail = -1.5       # 拿失败惩罚（略加）
        self.alpha_release_success = 5.0  # 放成功增益（大幅提升，让成功的经验更突出）
        self.alpha_release_fail = -8.0    # 放失败惩罚（大幅提升，一次失败=大幅降低信心）
        self.alpha_release_retry = -12.0  # 同组合多次失败加重惩罚（强烈阻止）

        # 阈值
        self.release_threshold = -3.0     # 低于此值则不再尝试该(物体,容器)组合

    def reset_online_state(self):
        """
        新一局开始时重置跟踪状态。
        注意：不重置爻参数矩阵，跨局积累的经验继续使用。
        """
        self._release_fail_count.clear()
        self._release_success_count.clear()
        self._holding_history.clear()

    # ====================================================================
    #  抓持爻（Take）更新
    # ====================================================================

    def observe_take_success(self, obj_base: str, loc_base: str):
        """
        抓持成功：更新抓持爻置信度。
        
        爻辞隐喻：☲ 离卦 —— 附着得位，所取即所得。
        """
        self.take_confidence[obj_base][loc_base] += self.alpha_take_success
        self._holding_history.append((f"take_{obj_base}", True))

        if self.verbose:
            score = self.take_confidence[obj_base][loc_base]
            print(f"    [爻调:抓持] ✓ take {obj_base}@{loc_base} → 置信度={score:.1f}")

    def observe_take_miss(self, obj_base: str, loc_base: str):
        """
        抓持缺失：去了某位置但没找到目标物体。
        
        爻辞隐喻：☵ 坎卦 —— 陷于险中，所寻不在此处。
        """
        self.take_confidence[obj_base][loc_base] += self.alpha_take_fail

        if self.verbose:
            score = self.take_confidence[obj_base][loc_base]
            print(f"    [爻调:抓持] ✗ {obj_base} not at {loc_base} → 置信度={score:.1f}")

    # ====================================================================
    #  释放爻（Release）更新
    # ====================================================================

    def observe_release_fail(self, obj_base: str, rec_base: str, rec_full: str = ''):
        """
        释放失败：尝试放物体到容器但失败。
        
        爻辞隐喻：☱ 兑卦 —— 口毁兑折，所放不得其所。
        
        Args:
            obj_base: 物体base名 (e.g., "plate")
            rec_base: 容器base名 (e.g., "countertop")
            rec_full: 容器全名 (e.g., "countertop 1")，用于细粒度调整
        """
        key = (obj_base, rec_base)
        self._release_fail_count[key] += 1
        fail_count = self._release_fail_count[key]

        # 基础惩罚
        penalty = self.alpha_release_fail

        # 同组合多次失败加重惩罚（爻的迭加效应）
        if fail_count >= 3:
            penalty = self.alpha_release_retry

        # 更新释放爻矩阵
        self.release_confidence[obj_base][rec_base] += penalty

        # 如果指定了具体容器，也微调细粒度偏好
        if rec_full:
            self.container_preference[obj_base][rec_full] += penalty

        if self.verbose:
            score = self.release_confidence[obj_base][rec_base]
            print(f"    [爻调:释放] ✗ put {obj_base}→{rec_base}(#{fail_count}次) → 置信度={score:.1f}")

    def observe_release_success(self, obj_base: str, rec_base: str, rec_full: str = ''):
        """
        释放成功。
        
        爻辞隐喻：☶ 艮卦 —— 止得其位，所放恰如其分。
        """
        key = (obj_base, rec_base)
        self._release_success_count[key] += 1

        # 成功强力正强化
        self.release_confidence[obj_base][rec_base] += self.alpha_release_success

        # 细粒度偏好正强化
        if rec_full:
            self.container_preference[obj_base][rec_full] += self.alpha_release_success

        # 释放成功后清零该组合的失败计数（重获信心）
        if key in self._release_fail_count:
            self._release_fail_count[key] = 0

        if self.verbose:
            score = self.release_confidence[obj_base][rec_base]
            print(f"    [爻调:释放] ✓ put {obj_base}→{rec_base} → 置信度={score:.1f}")

    def observe_release_open_before(self, rec_base: str, success: bool):
        """
        释放前的open操作反馈。
        
        如果open了一个容器然后成功放了 → open该容器类型的置信度增加
        如果open了但放不进 → 该容器open后仍然不适合
        """
        if success:
            # open成功但没有直接放成功，只是中间状态
            pass

    # ====================================================================
    #  查询接口
    # ====================================================================

    def get_release_score(self, obj_base: str, rec_base: str) -> float:
        """
        获取释放爻评分。
        
        正分越高 → 越有信心尝试该组合
        负分越低 → 越应避免该组合
        
        Returns:
            float: 释放置信度评分（可正可负）
        """
        score = self.release_confidence.get(obj_base, {}).get(rec_base, 0.0)
        return score

    def get_release_ranked(self, obj_base: str, available_recs: List[str], 
                            cmds: List[str] = None) -> List[Tuple[float, str]]:
        """
        对候选容器按释放爻置信度排序。
        
        Args:
            obj_base: 当前手持物体的base名
            available_recs: 可用的容器base列表（agent的 target_receps）
            cmds: admissible_commands（用于解析具体的容器编号）
            
        Returns:
            [(score, rec_full_or_base), ...] 按分数降序排列
        """
        scored = []

        for rec in available_recs:
            # base级别评分（不含编号）
            base_score = self.release_confidence.get(obj_base, {}).get(rec, 0.0)

            # 如果初始值为0，给一个轻度乐观初始值
            if base_score == 0.0:
                base_score = 1.0  # 轻微乐观，但低于成功经验

            # 检查是否低于排除阈值
            if base_score <= self.release_threshold:
                continue  # 不推荐

            scored.append((base_score, rec))

        # 如果有admissible_commands，尝试解析具体容器编号做细粒度排序
        if cmds:
            put_cmds = [c for c in cmds if c.startswith('move ') or c.startswith('put ')]
            for cmd in put_cmds:
                # 解析 "put plate 1 in/on countertop 1" 或 "put plate 1 on countertop 1" 
                # 或 "move plate 1 to countertop 1"
                m = re.match(r'(?:put|move) .+ (?:in|on|to) (.+)', cmd.lower())
                if m:
                    rec_full = m.group(1).strip()
                    rec_full_base = re.sub(r'\s*\d+$', '', rec_full)
                    if rec_full_base in [r.lower() for r in available_recs]:
                        # 细粒度偏好
                        fine_score = self.container_preference.get(obj_base, {}).get(rec_full, 0.0)
                        combined = base_score + fine_score * 0.3  # 细粒度作为权重加成
                        scored.append((combined, rec_full))

        # 去重 + 排序
        seen = set()
        unique_scored = []
        for score, name in sorted(scored, key=lambda x: -x[0]):
            if name not in seen:
                seen.add(name)
                unique_scored.append((score, name))

        # 防止所有候选都被排除——如果所有候选都低于阈值，放宽阈值
        # 用评分最高的候选（即使未过阈值也返回一个）
        if not unique_scored and scored:
            scored.sort(key=lambda x: -x[0])
            unique_scored = [(scored[0][0], scored[0][1])]
            if self.verbose:
                print(f"    [爻调:释放排序] 全部排除，放宽选择 {scored[0]}")

        if self.verbose and unique_scored:
            print(f"    [爻调:释放排序] obj={obj_base}")
            for s, r in unique_scored[:3]:
                print(f"      {s:5.1f} | {r}")

        return unique_scored

    def get_take_confidence(self, obj_base: str, loc_base: str) -> float:
        """获取抓持爻置信度（某物体在某位置的可拿程度）"""
        return self.take_confidence.get(obj_base, {}).get(loc_base, 0.0)

    def is_release_blocked(self, obj_base: str, rec_base: str) -> bool:
        """
        检查某(物体,容器)组合是否被释放爻排除。
        
        当释放置信度低于阈值时返回True，表示不应再尝试。
        """
        score = self.release_confidence.get(obj_base, {}).get(rec_base, 0.0)
        return score <= self.release_threshold

    def get_release_fail_count(self, obj_base: str, rec_base: str) -> int:
        """获取(物体,容器)组合的累计失败次数（含当前局内）"""
        return self._release_fail_count.get((obj_base, rec_base), 0)

    # ====================================================================
    #  跨局经验融合
    # ====================================================================

    def merge_episode_experience(self):
        """
        将当前局的在线经验融入长期矩阵（降低学习率，防止过拟合）。
        
        每次局结束时调用。
        """
        # 待实现：局结束时的经验蒸馏
        # 当前设计：release_confidence 和 take_confidence 本身持久化，局内局部调整在reset时可以选择保留
        pass

    # ====================================================================
    #  统计
    # ====================================================================

    def get_stats(self) -> dict:
        """统计信息"""
        # 正分/负分计数
        pos_release = sum(1 for obj in self.release_confidence.values()
                          for score in obj.values() if score > 0)
        neg_release = sum(1 for obj in self.release_confidence.values()
                          for score in obj.values() if score < 0)
        blocked_pairs = sum(1 for obj in self.release_confidence.values()
                            for score in obj.values() if score <= self.release_threshold)

        return {
            'release_confidence_pairs': {
                'positive': pos_release,
                'negative': neg_release,
                'blocked': blocked_pairs,
            },
            'take_confidence_pairs': len(self.take_confidence),
            'release_fail_counts': {
                str(k): v for k, v in self._release_fail_count.items() if v > 0
            },
            'release_success_counts': {
                str(k): v for k, v in self._release_success_count.items() if v > 0
            },
        }

    # ====================================================================
    #  经验持久化
    # ====================================================================

    def save_experience(self, path: str):
        """保存爻参数经验"""
        import json
        data = {
            'version': 1,
            'type': 'yao_online_tuner',
            'release_confidence': {k: dict(v) for k, v in self.release_confidence.items()},
            'take_confidence': {k: dict(v) for k, v in self.take_confidence.items()},
            'container_preference': {k: dict(v) for k, v in self.container_preference.items()},
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_experience(self, path: str):
        """加载爻参数经验"""
        import json
        with open(path) as f:
            data = json.load(f)
        for obj, recs in data.get('release_confidence', {}).items():
            for rec, score in recs.items():
                self.release_confidence[obj][rec] += score
        for obj, locs in data.get('take_confidence', {}).items():
            for loc, score in locs.items():
                self.take_confidence[obj][loc] += score
        for obj, recs in data.get('container_preference', {}).items():
            for rec, score in recs.items():
                self.container_preference[obj][rec] += score
