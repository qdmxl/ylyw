#!/usr/bin/env python3
"""
YLYW Agent — 基于六十四卦的具身智能决策层
============================================
使用 YLYW 的卦象映射 + 即时翻译层，在 ALFWorld 文本环境中进行中文推理决策。

核心机制：
  1. 中文观察 → 拆字 → 卦象映射 → 8维语义向量
  2. 候选中文动作 → 卦象映射 → 8维语义向量
  3. 卦象匹配：选出与"当前状态+任务目标"最契合的动作
  4. 输出中文决策 → 翻译层转英文 → ALFWorld 执行

不做 LLM 调用，纯 YLYW 符号推理。
"""

import sys
import os
import re
import json
import math
from typing import Dict, List, Tuple, Optional
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alfred_translator import ALFWorldTranslator

# ============================================================================
# 1. 六十四卦基础映射
# ============================================================================

TRIGRAM_MAP = {
    '☰': {'name': '乾', 'element': '天', 'nature': '健', 'embodiment': '动/创/刚'},
    '☱': {'name': '兑', 'element': '泽', 'nature': '悦', 'embodiment': '说/悦/柔'},
    '☲': {'name': '离', 'element': '火', 'nature': '丽', 'embodiment': '明/热/附'},
    '☳': {'name': '震', 'element': '雷', 'nature': '动', 'embodiment': '起/震/生'},
    '☴': {'name': '巽', 'element': '风', 'nature': '入', 'embodiment': '入/散/柔'},
    '☵': {'name': '坎', 'element': '水', 'nature': '陷', 'embodiment': '险/润/下'},
    '☶': {'name': '艮', 'element': '山', 'nature': '止', 'embodiment': '止/静/成'},
    '☷': {'name': '坤', 'element': '地', 'nature': '顺', 'embodiment': '受/载/柔'},
}

# 八卦8维独热索引
TRIGRAM_INDEX = {
    '乾': 0, '兑': 1, '离': 2, '震': 3, '巽': 4, '坎': 5, '艮': 6, '坤': 7
}

# 八卦语义方向（每个卦象在语义空间中的基向量）
BAGUA_SEMANTIC_BASES = {
    '乾': [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # 天/创造/主动
    '兑': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # 泽/悦/交流
    '离': [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # 火/明/热/照亮
    '震': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # 雷/动/起/激发
    '巽': [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # 风/入/散/渗透
    '坎': [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],  # 水/险/润/下/流入
    '艮': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # 山/止/成/静止
    '坤': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],  # 地/顺/载/承受
}

# ============================================================================
# 2. 汉字→卦象映射（YLYW 核心）
# ============================================================================

# 每个汉字在会意层面的卦象映射 —— 基于已有的 ideograph_knowledge_base 扩展
CHAR_BAGUA_MAP: Dict[str, str] = {
    # 动词类
    '拿': '震',   # 雷/动 → 取物动作
    '取': '震',   # 同上
    '放': '艮',   # 山/止 → 放置/停止
    '置': '艮',   # 同上
    '去': '震',   # 雷/动 → 移动
    '走': '震',   # 同上
    '到': '艮',   # 山/止 → 到达
    '达': '艮',   # 同上
    '打': '震',   # 雷/动
    '开': '震',   # 雷/动 → 开启
    '关': '艮',   # 山/止 → 关闭
    '闭': '艮',   # 同上
    '洗': '坎',   # 水/润 → 清洗
    '清': '坎',   # 同上
    '热': '离',   # 火/热 → 加热
    '加': '离',   # 同上
    '冷': '坎',   # 水/冷 → 冷却
    '却': '坎',   # 同上
    '用': '兑',   # 泽/悦 → 使用/交流
    '使': '兑',   # 同上
    '看': '离',   # 火/明 → 观察
    '观': '离',   # 同上
    '察': '离',   # 同上
    '查': '离',   # 同上
    '照': '离',   # 同上

    # 容器/位置类
    '桌': '坤',   # 地/承载 → 桌面承载物体
    '柜': '坤',   # 同上
    '抽': '巽',   # 风/入 → 抽屉（拉入拉出）
    '屉': '巽',   # 同上
    '架': '艮',   # 山/止 → 架子（高而止）
    '床': '坤',   # 地/承载
    '冰': '坎',   # 水/冷
    '箱': '坤',   # 地/承载
    '水': '坎',   # 水/润
    '槽': '坎',   # 同上
    '微': '离',   # 火/热
    '波': '离',   # 同上
    '炉': '离',   # 火/热
    '灶': '离',   # 同上
    '灯': '离',   # 火/明
    '台': '坤',   # 地/承载

    # 物体类
    '闹': '震',   # 雷/动 → 闹钟
    '钟': '震',   # 同上
    '苹': '坤',   # 地/生
    '果': '坤',   # 同上
    '面': '坤',   # 地/承载
    '包': '坤',   # 同上
    '鸡': '离',   # 火/热（可加热食物）
    '蛋': '离',   # 同上
    '生': '震',   # 雷/动/生
    '菜': '震',   # 同上
    '番': '离',   # 火/红色
    '茄': '离',   # 同上
    '土': '坤',   # 地
    '豆': '坤',   # 同上
    '刀': '兑',   # 泽/悦 → 工具
    '叉': '兑',   # 同上
    '勺': '兑',   # 同上
    '杯': '坤',   # 地/承载
    '碗': '坤',   # 同上
    '盘': '坤',   # 同上
    '锅': '坤',   # 同上
    '盆': '坤',   # 同上
    '书': '艮',   # 山/止 → 知识
    '笔': '巽',   # 风/入 → 书写
    '纸': '坤',   # 地/承载
    '抹': '坎',   # 水/润 → 抹布
    '布': '坎',   # 同上
    '海': '坎',   # 水
    '绵': '坎',   # 同上
    '肥': '坎',   # 水
    '皂': '坎',   # 同上
    '钥': '兑',   # 泽/开启
    '匙': '兑',   # 同上
    '信': '兑',   # 泽/交流
    '卡': '兑',   # 同上
    '电': '离',   # 火/电
    '视': '离',   # 火/明
    '花': '震',   # 雷/生长
    '瓶': '坤',   # 地/承载
    '罐': '坤',   # 同上
    '桶': '坤',   # 同上
    '篮': '坤',   # 同上
    '盒': '坤',   # 同上
    '球': '震',   # 雷/动
    '熊': '震',   # 雷/动
    '壶': '坤',   # 地/承载

    # 传感器/操作相关的字
    '捡': '震',   # 雷/动
    '移': '震',   # 同上
    '推': '震',   # 同上
    '倒': '巽',   # 风/倒
    '上': '乾',   # 天/上
    '下': '坤',   # 地/下
    '里': '坤',   # 地/内
    '外': '乾',   # 天/外
    '中': '艮',   # 山/中
    '前': '乾',   # 天/前
    '后': '坤',   # 地/后
    '左': '巽',   # 风/左
    '右': '兑',   # 泽/右
}


def char_to_bagua(ch: str) -> Optional[str]:
    """单个汉字 → 卦象"""
    if ch in CHAR_BAGUA_MAP:
        return CHAR_BAGUA_MAP[ch]
    # 尝试使用 ideograph_knowledge_base（如果可用）
    return None


def text_to_bagua_vector(text: str) -> List[float]:
    """
    将中文文本转换为 8 维卦象语义向量。
    对文本中每个汉字，累加其卦象的基向量，最后归一化。
    """
    vec = [0.0] * 8
    count = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':  # 中文字符
            bagua = char_to_bagua(ch)
            if bagua and bagua in BAGUA_SEMANTIC_BASES:
                base = BAGUA_SEMANTIC_BASES[bagua]
                for i in range(8):
                    vec[i] += base[i]
                count += 1

    if count == 0:
        # 没有匹配到任何卦象，返回均匀分布
        return [0.125] * 8

    # 归一化
    total = sum(vec)
    if total > 0:
        vec = [v / total for v in vec]
    else:
        vec = [0.125] * 8

    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """余弦相似度"""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def vector_to_bagua(vec: List[float], top_k: int = 3) -> List[Tuple[str, float]]:
    """将8维向量解释为主要卦象"""
    bagua_names = list(TRIGRAM_INDEX.keys())
    scores = [(bagua_names[i], vec[i]) for i in range(8)]
    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


# ============================================================================
# 3. YLYW 具身智能决策器
# ============================================================================

class YLYWAgent:
    """
    YLYW 具身智能决策器。

    用六十四卦做两件事：
    1. 理解状态：将中文观察分解为卦象向量
    2. 选择动作：将候选动作中文文本转为卦象向量，选出和"状态+目标"最匹配的
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.translator = ALFWorldTranslator(verbose=False)
        self.history: List[Dict] = []
        self.goal_vec: Optional[List[float]] = None

    def perceive(self, zh_obs: str, zh_goal: str = "") -> Dict:
        """
        感知：将中文观察和任务目标转为卦象表征。

        返回感知结果字典：
          - obs_vec: 观察的卦象向量
          - goal_vec: 目标的卦象向量
          - obs_bagua: 观察的主要卦象
          - goal_bagua: 目标的主要卦象
          - key_objects: 场景中的关键物体
          - key_actions: 场景中暗示的动作卦象
        """
        obs_vec = text_to_bagua_vector(zh_obs)
        goal_vec = text_to_bagua_vector(zh_goal) if zh_goal else obs_vec
        self.goal_vec = goal_vec

        obs_bagua = vector_to_bagua(obs_vec)
        goal_bagua = vector_to_bagua(goal_vec)

        # 提取关键物体
        key_objects = []
        for token in re.findall(r'[\u4e00-\u9fff]+', zh_obs):
            for ch in token:
                if ch in CHAR_BAGUA_MAP:
                    key_objects.append(ch)

        result = {
            'obs_vec': obs_vec,
            'goal_vec': goal_vec,
            'obs_bagua': obs_bagua,
            'goal_bagua': goal_bagua,
            'key_objects': Counter(key_objects).most_common(10),
        }

        if self.verbose:
            self._print_perception(result, zh_goal)

        return result

    def _print_perception(self, result: Dict, zh_goal: str):
        print(f"\n{'─'*60}")
        print(f"  🔮 YLYW 卦象感知")
        print(f"{'─'*60}")
        print(f"  任务目标: {zh_goal}")
        print(f"  目标卦象: {' > '.join(f'{b}({s:.2f})' for b,s in result['goal_bagua'])}")
        print(f"  场景卦象: {' > '.join(f'{b}({s:.2f})' for b,s in result['obs_bagua'])}")
        cmap = CHAR_BAGUA_MAP
        objs = ", ".join(f"{k}({cmap.get(k, chr(63))})" for k, _ in result["key_objects"][:8])
        print(f"  关键对象: {objs}")

    def decide(self, zh_commands: List[str], perception: Dict,
               is_first_step: bool = False) -> Tuple[str, str, Dict]:
        """
        决策：从候选中文动作中选出最优动作。

        算法：
        1. 每个候选动作生成卦象向量
        2. 计算 "状态卦象 ⊗ 目标卦象" 与候选卦象的匹配度
        3. 加入启发式偏好（探索 vs 利用）
        4. 返回得分最高的动作
        """
        obs_vec = perception['obs_vec']
        goal_vec = perception['goal_vec']

        if is_first_step:
            # 第一步优先探索（"look"）建立环境认知
            for zh_cmd in zh_commands:
                en_cmd = self.translator.act(zh_cmd)
                if en_cmd == 'look':
                    return zh_cmd, en_cmd, {'reason': '第一步优先环顾四周，建立环境认知', 'score': 1.0}

        # 融合状态+目标向量
        fused_vec = [0.6 * o + 0.4 * g for o, g in zip(obs_vec, goal_vec)]

        # 评分
        scored_actions = []
        for zh_cmd in zh_commands:
            action_vec = text_to_bagua_vector(zh_cmd)

            # 基础匹配度
            sim = cosine_similarity(fused_vec, action_vec)

            # 启发式调整
            en_cmd = self.translator.act(zh_cmd)

            # 加分：与目标卦象的直接匹配
            goal_sim = cosine_similarity(goal_vec, action_vec)
            sim = 0.5 * sim + 0.3 * goal_sim

            # 加分：explore 动作
            if en_cmd in ('look', 'inventory'):
                sim += 0.08

            # 加分：避免重复（简化版）
            if self.history and en_cmd != self.history[-1].get('action', ''):
                sim += 0.05

            # 减分：空动作
            if en_cmd == zh_cmd and re.search(r'[\u4e00-\u9fff]', zh_cmd):
                # 未匹配到英文动作（翻译失败），大幅降分
                sim -= 0.3

            scored_actions.append({
                'zh': zh_cmd,
                'en': en_cmd,
                'score': sim,
                'action_vec': action_vec,
            })

        # 排序
        scored_actions.sort(key=lambda x: -x['score'])
        best = scored_actions[0]

        # 生成推理理由
        action_bagua = vector_to_bagua(best['action_vec'])

        reason = (
            f"状态卦象({', '.join(f'{b}' for b,_ in perception['obs_bagua'][:2])}) "
            f"+ 目标卦象({', '.join(f'{b}' for b,_ in perception['goal_bagua'][:2])}) "
            f"→ 动作卦象({', '.join(f'{b}' for b,_ in action_bagua[:2])}) "
            f"匹配度={best['score']:.3f}"
        )

        if self.verbose:
            self._print_decision(scored_actions, best, reason)

        return best['zh'], best['en'], {'reason': reason, 'score': best['score'],
                                          'all_scores': [(a['zh'], a['score']) for a in scored_actions[:5]]}

    def _print_decision(self, all_actions: List[Dict], best: Dict, reason: str):
        print(f"\n{'─'*60}")
        print(f"  🎯 YLYW 卦象决策")
        print(f"{'─'*60}")
        print(f"  选择: \"{best['zh']}\" (→{best['en']})")
        print(f"  理由: {reason}")
        print(f"\n  动作排名 (Top 5):")
        for i, a in enumerate(all_actions[:5]):
            marker = "⭐" if i == 0 else "  "
            action_bagua = vector_to_bagua(a['action_vec'], top_k=2)
            print(f"  {marker} [{a['score']:.3f}] {a['zh']:24s} "
                  f"卦:{','.join(b for b,_ in action_bagua)} → {a['en']}")

    def record(self, action_en: str, result_zh: str):
        """记录执行结果"""
        self.history.append({
            'action': action_en,
            'result': result_zh,
        })


# ============================================================================
# 4. Demo: YLYW 推理决策流程展示
# ============================================================================

def demo_ylyw_reasoning():
    """
    展示 YLYW Agent 在典型 ALFWorld 场景中的完整推理流程。
    不需要实际运行 ALFWorld，使用模拟的场景数据。
    """
    agent = YLYWAgent(verbose=True)
    translator = agent.translator

    # 模拟一个典型的 ALFWorld 任务场景
    scenarios = [
        {
            'name': '任务1: 清洗长柄勺并放到餐桌上',
            'goal': '把干净的长柄勺放到餐桌',
            'observations': [
                # Step 0: 初始场景
                ("你站在房间中央。环顾四周，你看到了：柜子 1, 架子 2, 抽屉 1, 垃圾桶 1, 微波炉 1, 餐桌 1, 冰箱 1, and 水槽盆 1。",
                 ['去 柜子 1', '去 架子 2', '去 抽屉 1', '去 垃圾桶 1',
                  '去 微波炉 1', '去 餐桌 1', '去 冰箱 1', '去 水槽盆 1',
                  '观察', '查看背包']),
                # Step 1: 走到餐桌
                ("你到达了目的地。在 餐桌 1 上面，你看到了 长柄勺 1, 苹果 1, and 盘子 1。",
                 ['从 餐桌 1 拿 长柄勺 1', '从 餐桌 1 拿 苹果 1',
                  '从 餐桌 1 拿 盘子 1', '去 水槽盆 1', '去 柜子 1',
                  '去 微波炉 1', '观察', '查看背包']),
                # Step 2: 拿到长柄勺后去水槽
                ("你到达了目的地。水槽盆 1 是开着的。",
                 ['用 水槽盆 1 清洗 长柄勺 1', '去 餐桌 1', '去 柜子 1',
                  '去 微波炉 1', '去 冰箱 1', '观察', '查看背包']),
                # Step 3: 洗完回到餐桌
                ("你到达了目的地。",
                 ['把 长柄勺 1 放到 餐桌 1', '去 水槽盆 1', '去 柜子 1',
                  '观察', '查看背包']),
            ],
        },
        {
            'name': '任务2: 用台灯照明查看闹钟',
            'goal': '用台灯照明查看闹钟',
            'observations': [
                # Step 0: 初始
                ("你站在房间中央。环顾四周，你看到了：书桌 1, 架子 1, 边桌 1, and 床 1。",
                 ['去 书桌 1', '去 架子 1', '去 边桌 1', '去 床 1',
                  '观察', '查看背包']),
                # Step 1: 走到书桌
                ("你到达了目的地。在 书桌 1 上面，你看到了 台灯 1, 闹钟 2, 笔 1, and 书 1。",
                 ['从 书桌 1 拿 闹钟 2', '从 书桌 1 拿 台灯 1',
                  '使用 台灯 1', '观察 闹钟 2', '观察', '查看背包']),
                # Step 2: 拿起闹钟到边桌
                ("你到达了目的地。在 边桌 1 上面，你看到了 台灯 1, and 闹钟 1。",
                 ['使用 台灯 1', '观察 闹钟 1', '观察 闹钟 2', '观察', '查看背包']),
            ],
        },
    ]

    for scenario in scenarios:
        print(f"\n{'='*70}")
        print(f"  {scenario['name']}")
        print(f"{'='*70}")

        # 感知目标
        zh_goal = scenario['goal']
        goal_vec = text_to_bagua_vector(zh_goal)

        for step, (zh_obs, zh_cmds) in enumerate(scenario['observations']):
            print(f"\n{'▸'*30}")
            print(f"  第 {step+1} 步")
            print(f"{'▸'*30}")

            # Agent 感知
            perception = agent.perceive(zh_obs, zh_goal)

            # Agent 决策
            zh_chosen, en_chosen, meta = agent.decide(
                zh_cmds, perception,
                is_first_step=(step == 0)
            )

            # 模拟执行
            print(f"\n  ✅ 执行 → \"{zh_chosen}\" ({en_chosen})")

            agent.record(en_chosen, zh_obs)


if __name__ == '__main__':
    demo_ylyw_reasoning()
