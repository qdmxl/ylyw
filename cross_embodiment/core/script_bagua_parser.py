#!/usr/bin/env python3
"""
YLYW 汉字→八卦解析器（原型）

将汉语描述/汉字通过部首拆解映射为八卦隶属度，直接喂给YLYW推理引擎。

核心原理：
  - 离合法：汉字分解为部首组件
  - 部首→八卦映射表：每个部首对应1-3个卦的隶属度
  - 汉字结构→爻位关系：左右/上下/内外→比/承/乘
  - 输出：8维八卦隶属度向量（直接替换视觉输入的L1层）

Usage:
    from script_bagua_parser import HanziBaguaParser
    parser = HanziBaguaParser()
    bagua = parser.parse_char('杯')
    print(bagua)  # [0.3, 0.4, ..., 0.2]
"""

import os, sys, json
import numpy as np
from typing import Dict, List, Tuple, Optional

# ============================================================
# 部首→八卦映射表
# 基于214个康熙部首中高频使用的50+个
# 每个部首映射到1-3个卦，隶属度总和不一定=1
# ============================================================

RADICAL_BAGUA_MAP = {
    # ========== 五行类 ==========
    '木': {'XUN': 0.6, 'ZHEN': 0.3},      # 木→巽(渗透/生长)+震(震动)
    '林': {'XUN': 0.7, 'ZHEN': 0.4},      # 双木→更显著的巽
    '森': {'XUN': 0.8, 'ZHEN': 0.5},      # 三木→极其显著的巽+震
    '氵': {'KAN': 0.7, 'KUN': 0.3},       # 水→坎(凹陷/液体)+坤(包容)
    '水': {'KAN': 0.6, 'KUN': 0.4},       # 水→同上
    '冫': {'KAN': 0.5, 'KUN': 0.3},       # 两点水→冰/寒→坎+艮
    '火': {'LI': 0.7, 'LI': 0.3},         # 火→离(脆弱/附着)
    '灬': {'LI': 0.6, 'LI': 0.3},         # 四点底→火
    '土': {'KUN': 0.6, 'GEN': 0.4},       # 土→坤(柔顺)+艮(阻断)
    '金': {'QIAN': 0.7, 'GEN': 0.3},      # 金→乾(刚健)+艮(硬)
    
    # ========== 材质类 ==========
    '石': {'GEN': 0.7, 'QIAN': 0.3},      # 石→艮(阻断/支撑)+乾(坚固)
    '王': {'QIAN': 0.6, 'LI': 0.4},       # 玉→乾(坚固)+离(易碎)
    '玉': {'QIAN': 0.5, 'LI': 0.5},       # 玉→坚固+脆弱并存
    '皿': {'LI': 0.6, 'KAN': 0.5},        # 皿→离(容器/脆弱)+坎(凹陷)
    '缶': {'KAN': 0.6, 'LI': 0.5},        # 缶→陶器→凹陷+脆弱
    '瓦': {'LI': 0.7, 'GEN': 0.3},        # 瓦→脆弱+硬
    '革': {'QIAN': 0.5, 'KUN': 0.5},      # 革→坚固+柔韧（皮革）
    '韦': {'KUN': 0.6, 'XUN': 0.3},       # 韦→熟皮→柔顺
    '糸': {'KUN': 0.7, 'XUN': 0.3},       # 丝→柔顺/缠缚
    '巾': {'KUN': 0.6, 'XUN': 0.3},       # 巾→布料→柔顺
    '衣': {'KUN': 0.6, 'XUN': 0.2},       # 衣→柔顺
    '竹': {'XUN': 0.7, 'ZHEN': 0.3},      # 竹→巽(柔韧/渗透)+震(弹性)
    
    # ========== 动作类 ==========
    '扌': {'ZHEN': 0.6, 'QIAN': 0.4},     # 提手旁→震(手动/操作)+乾(有力)
    '手': {'ZHEN': 0.5, 'QIAN': 0.5},     # 手→同上
    '足': {'ZHEN': 0.7, 'XUN': 0.3},      # 足→震(运动)+巽(渐进)
    '辶': {'ZHEN': 0.6, 'XUN': 0.4},      # 走之底→运动+渐进
    '行': {'ZHEN': 0.5, 'QIAN': 0.4},     # 行→运动+刚健
    '彳': {'ZHEN': 0.5, 'XUN': 0.3},      # 双人旁→移动
    '力': {'QIAN': 0.7, 'ZHEN': 0.3},     # 力→乾(刚健/力量)
    '又': {'ZHEN': 0.5, 'QIAN': 0.3},     # 又→手部动作
    '攵': {'ZHEN': 0.5, 'KAN': 0.3},      # 反文旁→操作/敲击
    
    # ========== 容器/空间类 ==========
    '口': {'DUI': 0.6, 'KUN': 0.3},       # 口→兑(开口/容器)
    '囗': {'GEN': 0.6, 'KUN': 0.4},       # 大口框→艮(包围/阻隔)
    '匚': {'KAN': 0.5, 'GEN': 0.4},       # 左框→凹陷/阻隔
    '凵': {'KAN': 0.6, 'KUN': 0.3},       # 下框→凹陷/包容
    '穴': {'KAN': 0.7, 'GEN': 0.3},       # 穴→凹陷/阻隔
    '厂': {'GEN': 0.5, 'KAN': 0.3},       # 厂→山崖→阻断/凹陷
    '广': {'GEN': 0.5, 'KUN': 0.3},       # 广→房屋→覆盖/包容
    
    # ========== 生活器物类 ==========
    '刀': {'QIAN': 0.6, 'LI': 0.4},       # 刀→刚健+脆弱（锋利）
    '刂': {'QIAN': 0.6, 'LI': 0.4},       # 立刀旁→同上
    '斤': {'QIAN': 0.7, 'GEN': 0.3},       # 斤→斧头→刚健
    '皿': {'KAN': 0.5, 'LI': 0.5},        # 皿→容器（已在上方定义）
    '鼎': {'QIAN': 0.6, 'KAN': 0.4},      # 鼎→坚固+容纳
    '鬲': {'LI': 0.6, 'KAN': 0.5},        # 鬲→陶器→脆弱+容纳
    '酉': {'KAN': 0.5, 'KUN': 0.3},       # 酉→酒→液体+容器
    
    # ========== 自然类 ==========
    '日': {'LI': 0.7, 'QIAN': 0.3},       # 日→离(火/光)+乾(健)
    '月': {'KAN': 0.4, 'KUN': 0.4},       # 月→坎(阴)+坤(柔)
    '山': {'GEN': 0.7, 'KUN': 0.3},       # 山→艮(阻断/支撑)
    '川': {'XUN': 0.5, 'KAN': 0.4},       # 川→水流→巽(渗透)+坎(凹陷)
    '雨': {'KAN': 0.6, 'XUN': 0.4},       # 雨→坎(水)+巽(渗透)
    '云': {'XUN': 0.6, 'KUN': 0.3},       # 云→巽(风/飘散)
    '风': {'XUN': 0.8, 'ZHEN': 0.3},      # 风→巽(渗透)+震(动)
    '气': {'XUN': 0.7, 'QIAN': 0.3},      # 气→巽(渗透)
    '田': {'KUN': 0.5, 'GEN': 0.4},       # 田→坤(地/包容)+艮(界)
    '力': {'QIAN': 0.7, 'ZHEN': 0.3},     # 力→乾(刚健)

    # ========== 人体/感知类 ==========
    '目': {'LI': 0.5, 'DUI': 0.4},        # 目→离(视/明)+兑(观察/开口)
    '耳': {'DUI': 0.5, 'KUN': 0.3},       # 耳→兑(听/开口)
    '舌': {'DUI': 0.6, 'XUN': 0.3},       # 舌→兑(口/说)+巽(入)
    '心': {'KUN': 0.5, 'KAN': 0.4},       # 心→坤(包容)+坎(深)
    '忄': {'KUN': 0.5, 'KAN': 0.3},       # 竖心旁
    '言': {'DUI': 0.7, 'QIAN': 0.3},      # 言→兑(口/表达)
    '讠': {'DUI': 0.6, 'XUN': 0.3},       # 言字旁
    '贝': {'QIAN': 0.5, 'KUN': 0.3},      # 贝→钱→乾(价值)+坤(藏)
    
    # ========== 建筑类 ==========
    '门': {'GEN': 0.6, 'DUI': 0.4},       # 门→艮(阻挡/界)+兑(开口)
    '户': {'GEN': 0.5, 'DUI': 0.4},       # 户→门扇→同上
    '宀': {'KUN': 0.6, 'GEN': 0.3},       # 宝盖头→坤(覆盖/家)+艮(保护)
    '穴': {'KAN': 0.6, 'GEN': 0.4},       # 穴→坎(洞)+艮(壁)
    '尸': {'KUN': 0.5, 'GEN': 0.4},       # 尸→覆盖/遮蔽
    
    # ========== 抽象类 ==========
    '一': {'QIAN': 0.3, 'KUN': 0.3},       # 一→初始/统一
    '二': {'DUI': 0.3, 'KUN': 0.3},       # 二→二元/对立
    '大': {'QIAN': 0.6, 'LI': 0.3},       # 大→乾(大/强)
    '小': {'KUN': 0.4, 'XUN': 0.3},       # 小→坤(柔/小)
    '上': {'QIAN': 0.5, 'LI': 0.3},       # 上→乾(高/上)
    '下': {'KUN': 0.5, 'KAN': 0.3},       # 下→坤(低/下)+坎(陷)
    '中': {'KUN': 0.5, 'GEN': 0.3},       # 中→坤(中央)+艮(界)
}

# ============================================================
# 汉字结构分析
# ============================================================

# 常用汉字→部首拆解表
CHAR_RADICAL_MAP = {
    # 物体类
    '杯': ('木', '不'),           # 木+不→左右结构
    '碗': ('石', '宛'),           # 石+宛
    '盘': ('皿', '般'),           # 皿+般
    '瓶': ('瓦', '并'),           # 瓦+并
    '罐': ('缶', '雚'),           # 缶+雚
    '壶': ('士', '壸'),           # 士+壸
    '锅': ('金', '呙'),           # 金+呙
    '刀': ('刀', ''),             # 单字刀
    '叉': ('又', '丶'),           # 叉形
    '勺': ('勹', '丶'),           # 勺形
    '筷': ('竹', '快'),           # 竹+快
    '匙': ('匕', '是'),           # 匕+是
    '桌': ('木', '卓'),           # 木+桌
    '椅': ('木', '奇'),           # 木+奇
    '柜': ('木', '巨'),           # 木+巨
    '箱': ('竹', '相'),           # 竹+相
    '篮': ('竹', '监'),           # 竹+监
    '纸': ('糸', '氏'),           # 丝+氏
    '布': ('巾', '父'),           # 巾+父
    '瓷': ('瓦', '次'),           # 瓦+次
    '石': ('石', ''),             # 单字石
    '木': ('木', ''),             # 单字木
    '水': ('水', ''),             # 单字水
    '火': ('火', ''),             # 单字火
    '土': ('土', ''),             # 单字土
    '金': ('金', ''),             # 单字金
    '玉': ('王', '丶'),           # 王加点
    '冰': ('冫', '水'),           # 两点水+水
    '布': ('巾', '父'),           # 巾+父
    '绳': ('糸', '黾'),           # 丝+黾
    '线': ('糸', '戋'),           # 丝+戋
    '带': ('巾', '带'),           # 巾+带
    
    # 动作类
    '拿': ('手', '合'),           # 手+合
    '抓': ('扌', '爪'),           # 提手旁+爪
    '握': ('扌', '屋'),           # 提手旁+屋
    '提': ('扌', '是'),           # 提手旁+是
    '放': ('攵', '方'),           # 反文旁+方
    '推': ('扌', '隹'),           # 提手旁+隹
    '拉': ('扌', '立'),           # 提手旁+立
    '搬': ('扌', '般'),           # 提手旁+般
    '拧': ('扌', '宁'),           # 提手旁+宁
    '转': ('车', '专'),           # 车+专
    '按': ('扌', '安'),           # 提手旁+安
    '压': ('厂', '土'),           # 厂+土
    '切': ('刀', '七'),           # 刀+七
    '割': ('刂', '害'),           # 立刀旁+害
    '敲': ('攵', '高'),           # 反文旁+高
    '打': ('扌', '丁'),           # 提手旁+丁
    
    # 状态/属性类
    '大': ('大', ''),             # 单字大
    '小': ('小', ''),             # 单字小
    '长': ('长', ''),             # 单字长
    '短': ('矢', '豆'),           # 矢+豆
    '重': ('千', '里'),           # 千+里
    '轻': ('车', '工'),           # 车+工
    '硬': ('石', '更'),           # 石+更
    '软': ('车', '欠'),           # 车+欠
    '脆': ('月', '危'),           # 月+危
    '坚': ('土', '𠃊'),           # 土+坚
    '固': ('口', '古'),           # 口+古
    '滑': ('氵', '骨'),           # 水+骨
    '粗': ('米', '且'),           # 米+且
    '细': ('糸', '田'),           # 丝+田
    '薄': ('艹', '溥'),           # 草+溥
    '厚': ('厂', '𠃊'),           # 厂+厚
    
    # 材质描述
    '玻': ('王', '皮'),           # 玉+皮
    '璃': ('王', '离'),           # 玉+离→玻璃=玉+皮+玉+离
    '陶': ('阝', '匋'),           # 左耳旁+匋
    '瓷': ('瓦', '次'),           # 瓦+次
    '橡': ('木', '象'),           # 木+象→橡胶=树木的汁液
    '胶': ('月', '交'),           # 月+交
    '塑': ('土', '朔'),           # 土+朔→塑料
    '纸': ('糸', '氏'),           # 丝+氏
    '皮': ('皮', ''),             # 单字皮
    '布': ('巾', '父'),           # 巾+父
    
    # 综合描述
    '玻': ('王', '皮'),
    '璃': ('王', '离'),
    '橡': ('木', '象'),
    '胶': ('月', '交'),
    '塑': ('土', '朔'),
    '料': ('米', '斗'),
}

# 汉字结构分类
STRUCTURE_TYPES = {
    '左右': ['杯', '碗', '瓶', '罐', '锅', '筷', '椅', '柜', '箱', '篮',
             '纸', '绳', '线', '抓', '握', '提', '推', '拉', '搬', '拧',
             '按', '切', '割', '敲', '打', '短', '轻', '软', '脆', '滑',
             '粗', '细', '薄', '玻', '璃', '陶', '瓷', '胶', '塑', '料'],
    '上下': ['盘', '瓷', '盒', '拿', '放', '坚', '固', '厚', '电'],
    '内外': ['围', '圈', '囚', '国', '园'],
    '单字': ['大', '小', '水', '火', '土', '金', '木', '石', '玉', '刀',
             '叉', '勺', '皮', '布', '长'],
}

# ============================================================
# 核心解析器
# ============================================================

BAGUA_NAMES = ['QIAN', 'KUN', 'ZHEN', 'XUN', 'KAN', 'LI', 'GEN', 'DUI']
BAGUA_ORDER = {'QIAN': 0, 'KUN': 1, 'ZHEN': 2, 'XUN': 3, 'KAN': 4, 'LI': 5, 'GEN': 6, 'DUI': 7}

class HanziBaguaParser:
    """
    汉字→八卦隶属度解析器
    
    功能：
      1. 输入单个汉字 → 拆部首 → 查映射 → 输出8维隶属度
      2. 输入词语/短句 → 分词 → 逐字解析 → 融合 → 输出
    """

    def __init__(self, radical_map: Optional[Dict] = None,
                 char_map: Optional[Dict] = None):
        self.radical_map = radical_map or RADICAL_BAGUA_MAP
        self.char_map = char_map or CHAR_RADICAL_MAP
        self._last_debug = []

    def parse_char(self, char: str) -> np.ndarray:
        """
        解析单个汉字，输出8维八卦隶属度

        Args:
            char: 单个汉字

        Returns:
            bagua: (8,) ndarray, [乾,坤,震,巽,坎,离,艮,兑]
        """
        self._last_debug = []
        
        if char in self.char_map:
            r1, r2 = self.char_map[char]
            radicals = [r for r in [r1, r2] if r]
        else:
            # 不在拆字表中，尝试直接查部首映射
            radicals = [char] if char in self.radical_map else []
        
        if not radicals:
            # 未知汉字，返回中性隶属度
            self._last_debug.append(f"'{char}': 未知, 返回中性")
            return np.array([0.5] * 8)

        # 累计各卦隶属度
        bagua = np.zeros(8)
        n_valid = 0
        
        for radical in radicals:
            if radical in self.radical_map:
                mappings = self.radical_map[radical]
                for gua_name, value in mappings.items():
                    idx = BAGUA_ORDER[gua_name]
                    bagua[idx] += value
                n_valid += 1
                self._last_debug.append(
                    f"  部首'{radical}': {dict((k,round(v,2)) for k,v in mappings.items())}"
                )
            elif len(radical) == 1:
                # 尝试直接作为部首
                self._last_debug.append(f"  部首'{radical}': 未知部首")
        
        if n_valid > 0:
            bagua = bagua / n_valid  # 平均归一化
        else:
            bagua = np.array([0.5] * 8)
        
        # 截断到[0,1]
        bagua = np.clip(bagua, 0, 1)
        
        self._last_debug.append(f"  → 八卦: {np.round(bagua, 3)}")
        return bagua

    def parse_text(self, text: str) -> np.ndarray:
        """
        解析一段汉语文本（可能含多个字），加权融合输出八卦隶属度

        Args:
            text: 汉语描述，如"玻璃杯"、"轻轻拿起"

        Returns:
            bagua: (8,) ndarray
        """
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']  # 只保留汉字
        
        if not chars:
            return np.array([0.5] * 8)
        
        total_bagua = np.zeros(8)
        total_weight = 0
        
        for char in chars:
            b = self.parse_char(char)
            # 权重：部首越多、越明确则权重越高
            weight = 1.0
            if char in self.char_map:
                r1, r2 = self.char_map[char]
                weight = 1.0 + 0.3 * sum(1 for r in [r1, r2] if r and r in self.radical_map)
            total_bagua += b * weight
            total_weight += weight
        
        bagua = total_bagua / max(total_weight, 1)
        return np.clip(bagua, 0, 1)

    def explain(self):
        """打印上次解析的调试信息"""
        for line in self._last_debug:
            print(line)

    def get_bagua_dict(self, bagua: np.ndarray) -> Dict[str, float]:
        """转为卦名→隶属度的字典格式"""
        return {name: float(bagua[BAGUA_ORDER[name]]) for name in BAGUA_NAMES}


# ============================================================
# 快捷函数：直接与YLYW推理引擎对接
# ============================================================

def hanzi_to_bagua(text: str) -> np.ndarray:
    """汉字描述 → 8维八卦隶属度（快捷接口）"""
    parser = HanziBaguaParser()
    return parser.parse_text(text)

def hanzi_to_strategy(text: str, body_type='arm6_hand'):
    """
    汉字描述直接 → YLYW推理策略
    
    完整链路：汉字 → 八卦 → 六爻 → 卦象匹配 → 策略

    Args:
        text: 汉语描述，如"玻璃杯"、"厚重铁块"
        body_type: 机器人本体类型

    Returns:
        strategy dict
    """
    from core.cross_body_infer import CrossBodyInfer, trigram_base, hexagram_base
    
    # 第一步：汉字→八卦隶属度
    parser = HanziBaguaParser()
    bagua = parser.parse_text(text)
    
    # 第二步：直接作为L1八卦隶属度，走L2→L3链路
    # 这里需要body_config来编码六爻
    if body_type == 'arm6_hand':
        from bodies.body_arm6_hand import Arm6HandConfig
        config = Arm6HandConfig()
    elif body_type == 'shadow_hand_3axis':
        from bodies.body_shadow_hand import ShadowHand3AxisConfig
        config = ShadowHand3AxisConfig()
    else:
        from bodies.body_arm6_hand import Arm6HandConfig
        config = Arm6HandConfig()
    
    # 模拟obs（因为六爻编码需要obs中的物理特征）
    obs = {}
    
    # 用八卦本身反推物理特征（这个映射需要设计）
    # 简单版本：直接用八卦隶属度做六爻编码的bias
    yao = config.encode_yao(bagua, obs)
    
    # L3匹配
    best_hexagram, score = hexagram_base.get_best_hexagram(yao)
    rule = hexagram_base.get_rule(best_hexagram)
    gs = rule.get('grasp_strategy', {})
    
    strategy = {
        'bagua': bagua,
        'yao': yao,
        'hexagram': best_hexagram,
        'hexagram_name': best_hexagram.name if best_hexagram else '未知',
        'match_score': score,
        'strategy_type': gs.get('type', 'standard_grasp'),
        'description': rule.get('description', ''),
    }
    
    return strategy


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    print("=" * 65)
    print("YLYW 汉字→八卦解析器 原型测试")
    print("=" * 65)
    
    parser = HanziBaguaParser()
    
    test_cases = [
        '杯', '碗', '瓶', '锅', '刀',
        '玻璃杯', '瓷碗', '铁锅', '塑料瓶',
        '拿', '抓', '提', '放',
        '轻轻拿起', '用力握紧', '小心放下',
        '大', '重', '脆', '硬', '滑',
    ]
    
    for text in test_cases:
        bagua = parser.parse_text(text)
        bagua_dict = parser.get_bagua_dict(bagua)
        # 取top3卦
        sorted_gua = sorted(bagua_dict.items(), key=lambda x: -x[1])[:3]
        gua_str = ' + '.join(f'{n}({v:.2f})' for n, v in sorted_gua if v > 0.3)
        print(f"  '{text:6s}' → {gua_str}")


# ============================================================
# 汉字专用六爻编码器
# 直接从八卦隶属度推导六爻，不依赖传感器
# ============================================================

# 八卦→六爻映射权重矩阵 (8×6)
# 行: 乾 坤 震 巽 坎 离 艮 兑
# 列: 初爻(稳定)、二爻(握持力)、三爻(脆弱)、四爻(接触面)、五爻(间隙)、上爻(动态)
BAGUA_TO_YAO_WEIGHTS = np.array([
    # 初 二 三 四 五 上
    [0.9, 0.8, 0.1, 0.3, 0.1, 0.5],  # 乾→刚健→稳定高、握持力高
    [0.7, 0.1, 0.5, 0.7, 0.6, 0.2],  # 坤→柔顺→稳定中、大接触面
    [0.3, 0.2, 0.6, 0.4, 0.5, 0.8],  # 震→扰动→不稳定、动态高
    [0.5, 0.3, 0.4, 0.6, 0.7, 0.6],  # 巽→渗透→间隙中、接触面中
    [0.2, 0.4, 0.3, 0.5, 0.8, 0.4],  # 坎→凹陷→间隙大、不稳定
    [0.3, 0.2, 0.9, 0.3, 0.3, 0.3],  # 离→脆弱→脆弱高、握持力低
    [0.8, 0.7, 0.2, 0.2, 0.1, 0.2],  # 艮→阻断→稳定高、握持力高
    [0.6, 0.1, 0.3, 0.6, 0.4, 0.3],  # 兑→开口→接触面中、脆弱中
])

# 字体描述→偏置映射
TEXTURE_BIAS = {
    # 关键词: (初爻偏, 二爻偏, 三爻偏, 四爻偏, 五爻偏, 上爻偏)
    '脆': (0, 0, 0.3, 0, 0, 0),
    '易碎': (0, 0, 0.4, 0, 0, 0),
    '硬': (0.1, 0.1, -0.2, 0, 0, 0),
    '软': (-0.1, -0.1, 0.2, 0.1, 0.1, 0),
    '轻': (0, -0.2, 0, 0, 0, 0.1),
    '重': (0.1, 0.3, 0, 0, 0, -0.1),
    '滑': (-0.1, -0.2, 0, 0, 0.1, 0.1),
    '粗': (0.1, 0, 0, 0.1, -0.1, 0),
    '大': (0.1, 0.1, 0, 0.1, 0, 0),
    '小': (-0.1, -0.1, 0, -0.1, 0, 0),
    '厚': (0.1, 0, 0, 0.2, -0.1, 0),
    '薄': (-0.1, 0, 0.1, -0.1, 0.1, 0),
    '金': (0.2, 0.2, -0.1, 0, 0, 0),
    '铁': (0.2, 0.3, -0.1, 0, 0, 0),
    '木': (0.1, 0, 0.1, 0.1, 0, 0),
    '纸': (-0.1, -0.2, 0.3, 0.2, 0, 0),
    '布': (-0.1, -0.1, 0, 0.3, 0, -0.1),
    '皮': (0, -0.1, 0.2, 0.2, 0, 0),
    '水': (-0.2, -0.1, 0, 0, 0.2, 0.1),
    '油': (-0.2, -0.2, 0, 0, 0.2, 0),
    '冰': (0, 0.1, 0.3, -0.1, 0, 0),
    '热': (0, 0, 0, 0, 0, 0.2),
}


class HanziEncoder:
    """
    从汉字/汉语描述直接推导六爻编码
    不依赖传感器输入，仅基于汉字→八卦→六爻的规则推理
    """

    def __init__(self):
        self.parser = HanziBaguaParser()
        self.weights = BAGUA_TO_YAO_WEIGHTS

    def encode_yao(self, text: str) -> np.ndarray:
        """
        汉字描述 → 6维爻向量

        Args:
            text: 汉字描述，如"玻璃杯"、"厚重铁锅"

        Returns:
            yao: (6,) ndarray, [初,二,三,四,五,上]
        """
        # 第一步：汉字→八卦隶属度
        bagua = self.parser.parse_text(text)
        
        # 第二步：八卦隶属度×权重矩阵 → 原始六爻
        yao = bagua @ self.weights  # (8,) @ (8,6) = (6,)
        
        # 第三步：从文本中提取材质关键词，施加偏置
        for kw, bias in TEXTURE_BIAS.items():
            if kw in text:
                yao += np.array(bias)
                break  # 只取第一个匹配的关键词
        
        # 第四步：截断到[0,1]
        yao = np.clip(yao, 0, 1)
        
        return yao

    def infer_strategy(self, text: str) -> dict:
        """汉字描述 → 卦象匹配 → 策略（完整链路）"""
        yao = self.encode_yao(text)
        best_hex, score = hexagram_base.get_best_hexagram(yao)
        rule = hexagram_base.get_rule(best_hex)
        gs = rule.get('grasp_strategy', {})
        
        return {
            'input_text': text,
            'bagua': self.parser.get_bagua_dict(self.parser.parse_text(text)),
            'yao': yao,
            'hexagram': best_hex,
            'hexagram_name': best_hex.name if best_hex else '未知',
            'match_score': score,
            'strategy_type': gs.get('type', 'standard_grasp'),
            'description': rule.get('description', ''),
        }


# 测试
if __name__ == '__main__':
    print("=" * 65)
    print("YLYW 汉字→八卦→六爻→卦象 全链路测试")
    print("=" * 65)
    
    encoder = HanziEncoder()
    
    test_cases = [
        '玻璃杯', '瓷碗', '铁锅', '塑料瓶', 
        '皮球', '纸箱', '木盒', '石头',
        '水杯', '冰块', '油瓶', '金属块',
    ]
    
    for text in test_cases:
        result = encoder.infer_strategy(text)
        bagua = result['bagua']
        top3 = sorted(bagua.items(), key=lambda x: -x[1])[:3]
        gua_str = ' '.join(f'{n}={v:.2f}' for n,v in top3)
        print(f"  '{text:6s}' → 卦={result['hexagram_name']:6s}({result['match_score']:.2f}) "
              f"策略={result['strategy_type']:25s} yao={np.round(result['yao'],2)}")
