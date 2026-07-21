#!/usr/bin/env python3
"""
意图解码器 — IntentionDecoder

将卦名+六爻向量解码为任务规划意图。

核心设计：
  1. 64卦各有其易理意象，映射到任务决策的"意图"上
  2. 映射表初始基于易理常识设定
  3. 用知几学习机制，从成功/失败经验中自动调整映射权重
  4. 同一卦在不同阶段/场景下可能映射到不同意图（由六爻上下卦调制）

卦→意图的易理基础：
  乾(☰☰): 天行健 → 进取探索
  坤(☷☷): 地势坤 → 等待观察
  屯(☵☳): 刚柔始交 → 启动新阶段
  蒙(☶☵): 童蒙求我 → 尝试/试探
  需(☵☰): 需于沙 → 等待/确认
  讼(☰☵): 天水违行 → 冲突/需调整策略
  师(☷☵): 地水师 → 系统推进
  比(☵☷): 水地比 → 匹配/配对
  ...（完整映射见下表）

输出：
  intent: 规划意图（如 goto_explore / take / put / use_tool / ...）
  confidence: 置信度
  alternative_phases: 备选意图（当主意图不可行时）
"""

import os, sys, json
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

_self_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.dirname(_self_dir)
for d in (os.path.join(_proj_root, 'language'),
          os.path.join(_proj_root, 'api_docs'),
          os.path.join(_proj_root, 'experiment_phase1')):
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from hanzi_engine import BAGUA, _HRULE
    from ylyw_core import Hexagram
    _YLYW_OK = True
except ImportError:
    _YLYW_OK = False


# ══════════════════════════════════════════════════════════════
# 易理→规划意图映射表
# ══════════════════════════════════════════════════════════════

# 64卦 → 主意图（初始映射）
# 每个条目：(卦名, 主意图, 备选意图, 适用条件描述)
HEXAGRAM_INTENT_MAP = {
    # ── 进取/探索类 ──
    '乾为天':       ('goto_explore',       ['look_around'],        '天行健，君子以自强不息'),
    '屯':           ('goto_explore',       ['open_container'],     '刚柔始交而难生，启动探索'),
    '蒙':           ('look_around',        ['goto_explore'],       '童蒙求我，试探环境'),
    '需':           ('goto_target',        ['wait_confirm'],        '需于沙，需要前往目标位置'),
    '小畜':         ('goto_explore',       ['look_around'],        '风行天上，蓄势待发'),
    '履':           ('goto_explore',       ['open_container'],     '履虎尾，小心前行'),
    '泰':           ('goto_explore',       ['goto_target'],        '天地交泰，顺利前进'),
    '大畜':         ('goto_explore',       ['open_container'],     '蓄积力量，继续探索'),
    '颐':           ('wait_confirm',       ['look_around'],        '颐养，观察情况'),

    # ── 拿取类 ──
    '大有':         ('take_object',        ['goto_object'],        '火天大有，收获之时'),
    '大壮':         ('take_object',        ['goto_explore'],       '雷天大壮，进取有得'),
    '晋':           ('take_object',        ['goto_target'],        '火地晋，前进有获'),
    '同人':         ('take_object',        ['goto_explore'],       '天火同人，协同得物'),
    '随':           ('take_object',        ['goto_object'],        '泽雷随，顺势取物'),
    '无妄':         ('take_object',        ['goto_explore'],       '天雷无妄，顺其自然取物'),

    # ── 工具/处理类 ──
    '坎为水':       ('goto_tool',          ['use_tool'],           '坎为水，水流趋下，去寻找工具'),
    '水风井':       ('goto_tool',          ['use_tool'],           '木上有水，井养之物'),
    '水火既济':     ('use_tool',           ['goto_tool'],          '事已成，处理完成'),
    '火风鼎':       ('use_tool',           ['goto_tool'],          '以木巽火，烹饪之象'),
    '泽火革':       ('use_tool',           ['goto_tool'],          '变革更新，处理进行'),

    # ── 放置类 ──
    '艮为山':       ('put_object',         ['goto_target'],        '艮为山，止于当止'),
    '渐':           ('goto_target',        ['put_object'],         '风山渐，渐进至目的地'),
    '归妹':         ('put_object',         ['goto_target'],        '雷泽归妹，物有所归'),
    '旅':           ('goto_target',        ['put_object'],         '火山旅，移动至目标'),
    '节':           ('put_object',         ['goto_target'],        '水泽节，节制放置'),

    # ── 停驻/等待类 ──
    '坤为地':       ('wait_confirm',       ['look_around'],        '地势坤，静待其变'),
    '豫':           ('wait_confirm',       ['look_around'],        '雷出地奋，预备观望'),
    '临':           ('look_around',        ['wait_confirm'],       '地泽临，靠近观察'),
    '观':           ('look_around',        ['wait_confirm'],       '风地观，仔细观察'),
    '明夷':         ('wait_confirm',       ['goto_explore'],       '明入地中，暂避锋芒'),
    '遁':           ('goto_explore',       ['wait_confirm'],       '天山遁，退避调整'),

    # ── 打开/检查容器类 ──
    '解':           ('open_container',     ['look_around'],        '雷水解，解除封闭'),
    '升':           ('open_container',     ['goto_explore'],       '地风升，逐步上升打开'),
    '鼎':           ('open_container',     ['take_object'],        '火风鼎，待开之物'),
    '震为雷':       ('open_container',     ['goto_explore'],       '震来虩虩，需要打开'),

    # ── 策略调整/退避类 ──
    '讼':           ('adjust_strategy',    ['goto_explore'],       '天水违行，策略冲突'),
    '师':           ('adjust_strategy',    ['goto_explore'],       '地水师，需要系统化推进'),
    '比':           ('take_object',        ['goto_object'],        '水地比，匹配对应'),
    '否':           ('adjust_strategy',    ['wait_confirm'],       '天地不交，此路不通'),
    '谦':           ('wait_confirm',       ['goto_explore'],       '地山谦，低调行事'),
    '蛊':           ('adjust_strategy',    ['look_around'],        '山风蛊，事有腐败需更改'),
    '剥':           ('adjust_strategy',    ['goto_explore'],       '山地剥，此路径已剥落'),
    '复':           ('goto_explore',       ['look_around'],        '地雷复，从头再来'),
    '大过':         ('adjust_strategy',    ['open_container'],     '泽风大过，超出常态需调整'),
    '咸':           ('take_object',        ['goto_object'],        '泽山咸，感应得物'),
    '恒':           ('goto_target',        ['put_object'],         '雷风恒，持之以恒'),
    '睽':           ('adjust_strategy',    ['goto_explore'],       '火泽睽，乖离需调整'),
    '蹇':           ('adjust_strategy',    ['goto_explore'],       '水山蹇，前路艰难'),
    '损':           ('adjust_strategy',    ['goto_explore'],       '山泽损，损失需规避'),
    '益':           ('goto_explore',       ['take_object'],        '风雷益，增益之时'),
    '夬':           ('take_object',        ['goto_explore'],       '泽天夬，果断决断'),
    '姤':           ('goto_explore',       ['open_container'],     '天风姤，不期而遇'),
    '萃':           ('goto_target',        ['put_object'],         '泽地萃，聚集于目标'),
    '升':           ('goto_target',        ['put_object'],         '地风升，上升至目的'),
    '困':           ('adjust_strategy',    ['open_container'],     '泽水困，困而求变'),
    '井':           ('goto_tool',          ['use_tool'],           '木上有水，井养不穷'),
    '革':           ('use_tool',           ['goto_tool'],          '泽火革，变革处理'),
    '鼎':           ('use_tool',           ['goto_tool'],          '火风鼎，鼎烹饪'),

    # ── 完成类 ──
    '既济':         ('task_done',          ['confirm'],            '事已成，任务完成'),
    '未济':         ('adjust_strategy',    ['goto_explore'],       '火水未济，尚未完成需继续'),

    # ── 已处理+在目标位置 → 放置 ──
    '山天大畜':     ('goto_explore',       ['goto_target'],        '蓄积力量，优先探索但可转到目标'),
    '泽天夬':       ('put_object',         ['goto_target'],        '泽天夬，果断决断放置'),
    '雷天大壮':     ('put_object',         ['goto_target'],        '雷天大壮，进取放置'),
    '火天大有':     ('take_object',         ['goto_object'],        '火天大有，收获取物'),
    '离为火':       ('use_tool',          ['goto_tool'],        '离火附着，附着于当前位置使用工具'),
    '天火同人':     ('goto_object',        ['take_object'],        '天火同人，协同取物'),
    '泽火革':       ('use_tool',           ['goto_tool'],          '变革处理'),
    '火泽睽':       ('adjust_strategy',    ['goto_explore'],       '乖离需调整'),
    '天地否':       ('adjust_strategy',    ['goto_explore'],       '此路不通需调整'),

    # ── 综合/情境类 ──
    '家人':         ('look_around',        ['wait_confirm'],       '风火家人，安于现状'),
    '丰':           ('take_object',        ['put_object'],         '雷火丰，丰盛有得'),
    '巽为风':       ('goto_explore',       ['open_container'],     '随风巽，顺势探访'),
    '兑为泽':       ('look_around',        ['wait_confirm'],       '丽泽兑，交流沟通'),
    '涣':           ('goto_explore',       ['goto_target'],        '风水涣，涣散重聚'),
    '中孚':         ('wait_confirm',       ['look_around'],        '风泽中孚，诚信等待'),
    '小过':         ('adjust_strategy',    ['goto_explore'],       '雷山小过，小有过失'),
    '归妹':         ('put_object',         ['goto_target'],        '雷泽归妹，归于其所'),
    '丰':           ('put_object',         ['goto_target'],        '雷火丰，丰富放置'),
}

# 意图类型列表（所有可能的输出）
INTENT_TYPES = [
    'goto_explore',      # 去未探索位置
    'goto_object',       # 去目标物体所在位置（已知）
    'goto_tool',         # 去工具位置
    'goto_target',       # 去目标容器位置
    'take_object',       # 拿取目标物体
    'put_object',        # 放置物体到容器
    'use_tool',          # 使用工具（洗/热/冷）
    'open_container',    # 打开容器
    'look_around',       # 环顾/观察
    'wait_confirm',      # 等待/确认
    'adjust_strategy',   # 调整策略
    'task_done',         # 任务完成
    'confirm',           # 确认状态
]


# ══════════════════════════════════════════════════════════════
# 六爻上卦/下卦分裂
# ══════════════════════════════════════════════════════════════

def split_yao_into_trigrams(yao: List[float]) -> Tuple[List[float], List[float]]:
    """
    将六爻分裂为上卦和下卦。
    下卦（内）：初爻、二爻、三爻 → 代表内部状态
    上卦（外）：四爻、五爻、上爻 → 代表外部环境
    """
    if len(yao) >= 6:
        lower = yao[:3]
        upper = yao[3:6]
    else:
        lower = [0.5]*3
        upper = [0.5]*3
    return lower, upper


# ══════════════════════════════════════════════════════════════
# 意图解码器
# ══════════════════════════════════════════════════════════════

class IntentionDecoder:
    """
    意图解码器：卦名+六爻 → 任务规划意图。

    使用知几学习机制调整初始映射：
      - 每局成功 → 该局用过的卦→意图映射得到正强化
      - 每局失败 → 该局用过的卦→意图映射得到负强化
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        if not _YLYW_OK:
            raise ImportError("ylyw_core is required for IntentionDecoder")

        # 卦→意图的基础映射（从HEXAGRAM_INTENT_MAP加载）
        self.base_map: Dict[str, Tuple[str, List[str]]] = {}
        for hex_name, (main, alts, desc) in HEXAGRAM_INTENT_MAP.items():
            self.base_map[hex_name] = (main, alts)

        # 知几学习的经验权重
        # gua_weights[卦名][意图类型] = 经验权重（正=正向增益，负=负向抑制）
        self.gua_weights: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

        # 卦名 → 中文名查找缓存
        self._hex_name_cache: Dict[str, str] = {}
        for i in range(64):
            try:
                h = Hexagram(i)
                rule = _HRULE.get_rule(h)
                name = rule.get('name', h.name) if rule else h.name
                self._hex_name_cache[h.name] = name
            except:
                pass

    def get_intent_name(self, hex_name: str) -> str:
        """根据英文卦名获取中文卦名"""
        return self._hex_name_cache.get(hex_name, hex_name)

    # ══════════════════════════════════════════════════════════
    # 核心解码接口
    # ══════════════════════════════════════════════════════════

    def decode(self, hexagram: str, yao: List[float],
               context: Dict = None) -> Dict:
        """
        将卦名+六爻解码为规划意图。

        Args:
            hexagram: 卦名（如 'DAGUO', 'QIAN' 等 Hexagram 枚举名）
            yao: 六爻向量（6维浮点数）
            context: 可选上下文信息（任务类型、成功历史等）

        Returns:
            intent: 主意图
            score: 置信度
            alternatives: 备选意图列表（含分数）
            upper_trigram: 上卦（外）
            lower_trigram: 下卦（内）
        """
        # 1. 取中文卦名
        cn_name = self.get_intent_name(hexagram)

        # 2. 基础映射
        main_intent, alt_intents = self.base_map.get(cn_name, ('goto_explore', ['look_around']))

        # 3. 知几加权：用经验权重调整意图得分
        weights = self.gua_weights.get(hexagram, {})
        intent_scores = {}
        for intent in INTENT_TYPES:
            score = 0.0
            if intent == main_intent:
                score = 1.0
            # 备选意图
            for idx, alt in enumerate(alt_intents):
                if intent == alt:
                    boost = 0.7 - idx * 0.15
                    score = max(score, boost)
            # 叠加知几权重（正负）
            score += weights.get(intent, 0.0)
            # 确保有兜底值
            if score > 0:
                intent_scores[intent] = score

        # 4. 如果没有任何有效的意图得分，给默认兜底
        if not intent_scores:
            intent_scores['goto_explore'] = 0.5

        # 5. 排序取最优
        sorted_intents = sorted(intent_scores.items(), key=lambda x: -x[1])

        # 6. 分裂六爻为上卦/下卦
        lower, upper = split_yao_into_trigrams(yao)

        # 7. 尝试用上卦微调意图（外因影响）
        # 上卦对应的三爻方位：四爻=环境是否有利，五爻=是否已到关键位置，上爻=是否超额
        if len(upper) >= 3:
            env_score = sum(upper) / len(upper)
            if env_score > 0.7 and len(sorted_intents) > 1:
                # 环境有利时倾向更进取的意图
                pass
            elif env_score < 0.3 and len(sorted_intents) > 1:
                # 环境不利时倾向保守
                pass

        result = {
            'intent': sorted_intents[0][0],
            'score': sorted_intents[0][1],
            'alternatives': [{'intent': k, 'score': round(v, 3)}
                             for k, v in sorted_intents[:3]],
            'hexagram': hexagram,
            'hexagram_cn': cn_name,
            'lower_trigram': [round(v, 3) for v in lower],
            'upper_trigram': [round(v, 3) for v in upper],
        }

        if self.verbose:
            print(f"  [Decoder] {cn_name:10s} → {result['intent']:20s} "
                  f"(score={result['score']:.3f}) "
                  f"alt={[a['intent'][:8] for a in result['alternatives'][:2]]}")

        return result

    # ══════════════════════════════════════════════════════════
    # 知几学习接口
    # ══════════════════════════════════════════════════════════

    def observe_result(self, hexagram_history: List[Tuple[str, List[float], str]],
                       won: bool, task_type: str = ''):
        """
        从一局的结果中学习卦→意图映射。

        Args:
            hexagram_history: [(卦名, 六爻, 所选意图), ...] 每步的记录
            won: 本局是否成功
            task_type: 任务类型（可选，供分类型学习）
        """
        reward = 1.0 if won else -0.5

        for hex_name, yao, chosen_intent in hexagram_history:
            # 正向/负向调整选中意图的权重
            self.gua_weights[hex_name][chosen_intent] += reward * 0.1

            # 成功时：强化选中意图，抑制未选意图
            if won:
                for intent in INTENT_TYPES:
                    if intent != chosen_intent:
                        self.gua_weights[hex_name][intent] -= 0.01
            # 失败时：抑制选中意图（可能是错的）
            else:
                self.gua_weights[hex_name][chosen_intent] -= 0.2

            # 归一化，防止发散
            for intent in list(self.gua_weights[hex_name].keys()):
                w = self.gua_weights[hex_name][intent]
                if w > 2.0:
                    self.gua_weights[hex_name][intent] = 2.0
                elif w < -1.0:
                    self.gua_weights[hex_name][intent] = -1.0

        if self.verbose:
            print(f"  [Decoder] 学习: {'✓' if won else '✗'} "
                  f"({len(hexagram_history)}步记录)")

    def get_weighted_intent(self, hexagram: str, yao: List[float],
                             default_intent: str = 'goto_explore') -> str:
        """简化接口：只返回最佳意图名"""
        result = self.decode(hexagram, yao)
        return result['intent']

    # ══════════════════════════════════════════════════════════
    # 持久化
    # ══════════════════════════════════════════════════════════

    def save_experience(self, path: str):
        """保存经验权重"""
        data = {
            'gua_weights': {
                k: dict(v) for k, v in self.gua_weights.items()
            }
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_experience(self, path: str):
        """加载经验权重"""
        with open(path) as f:
            data = json.load(f)
        for gua, weights in data.get('gua_weights', {}).items():
            for intent, w in weights.items():
                self.gua_weights[gua][intent] += w


# ══════════════════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════════════════

def test_decoder():
    decoder = IntentionDecoder(verbose=True)

    # 测试几个典型卦
    test_cases = [
        ('QIAN',     [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], '中性探索'),
        ('KUN',      [0.1, 0.1, 0.1, 0.1, 0.1, 0.1], '静待'),
        ('ZHUN',     [0.6, 0.6, 0.3, 0.4, 0.4, 0.2], '启动探索'),
        ('XU',       [0.3, 0.3, 0.3, 0.5, 0.6, 0.4], '等待'),
        ('DAYOU',    [0.7, 0.7, 0.6, 0.5, 0.5, 0.4], '大有收获'),
        ('KAN_GUA',  [0.4, 0.4, 0.3, 0.6, 0.7, 0.3], '坎水寻工具'),
        ('GEN_GUA',  [0.5, 0.6, 0.7, 0.6, 0.7, 0.5], '艮止放置'),
        ('JIJI',     [0.5, 0.5, 0.5, 0.5, 0.5, 0.5], '既济完成'),
    ]

    print("测试64卦→意图解码：")
    print("=" * 60)
    for hex_name, yao, desc in test_cases:
        result = decoder.decode(hex_name, yao)
        cn = result['hexagram_cn']
        intent = result['intent']
        score = result['score']
        lower = result['lower_trigram']
        upper = result['upper_trigram']
        print(f"{desc:10s} {cn:10s} → {intent:20s}({score:.2f}) "
              f"下卦:{lower} 上卦:{upper}")

    # 测试知几学习
    print("\n知几学习测试：")
    history = [('QIAN', [0.6]*6, 'goto_explore'),
               ('DAYOU', [0.7]*6, 'take_object'),
               ('KAN_GUA', [0.5]*6, 'goto_tool'),
               ('JIJI', [0.5]*6, 'use_tool'),
               ('GEN_GUA', [0.6]*6, 'put_object')]
    decoder.observe_result(history, won=True)

    # 再次测试，看权重变化
    print("学习后再次解码：")
    for hex_name, yao, desc in test_cases[:3]:
        result = decoder.decode(hex_name, yao)
        print(f"  {result['hexagram_cn']:10s} → {result['intent']:20s}")


if __name__ == '__main__':
    test_decoder()
