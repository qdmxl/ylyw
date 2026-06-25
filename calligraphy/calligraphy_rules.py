#!/usr/bin/env python3
"""
YLYW 书法六十四卦规则库

每个卦象关联一个书写策略，包含：
- 主导笔法和替代笔法
- 压力基准和速度范围
- 起收笔形态参数
- 爻位关系如何影响具体执行参数

这是"卦象决定策略类型、爻位关系决定执行参数"在书法域的实现。

六十四卦规则构建逻辑：
- 上卦代表结构类型（字的整体框架）→ 权重 70%
- 下卦代表风格倾向（笔画的执行风格）→ 权重 30%
- 各参数从上下卦的八卦原型加权插值得到
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
import copy


class BrushMethod(Enum):
    """八种笔法（对应八卦）"""
    CENTER_TIP = '中锋'     # 乾：力道均匀，笔尖在笔画中心
    SIDE_TIP = '侧锋'       # 坤：笔锋侧卧，柔和铺展
    LIFT_PRESS = '提按'     # 震：轻重快速交替
    PAUSE_HOLD = '顿笔'     # 艮：停留蓄力
    EXPOSE_TIP = '露锋'     # 离：笔锋外露出尖
    HIDE_TIP = '藏锋'       # 坎：笔锋内敛回锋
    LIGHT_SKIP = '轻灵'     # 兑：轻快短促
    DENSE_CURVE = '绵密'    # 巽：细长柔韧


@dataclass
class StrokeRule:
    """单个笔画的执行规则"""
    brush_method: BrushMethod           # 笔法类型
    pressure_base: float                # 基准压力 [0, 1]
    pressure_variation: float           # 压力变化幅度
    speed_base: float                   # 基准速度 [0, 1]
    
    # 起收笔形态
    start_pressure: float               # 起笔压力（顿笔 = 高）
    end_pressure: float                 # 收笔压力（回锋 = 高，出锋 = 低）
    start_width_ratio: float            # 起笔宽度比
    end_width_ratio: float              # 收笔宽度比
    
    # 运动特征
    approach_speed: float               # 入笔速度
    retreat_speed: float               # 收笔速度
    angle_tolerance: float              # 角度容许偏差
    
    # 爻位关系对参数的影响系数
    yao_coefficients: Dict[str, float] = field(default_factory=dict)
    
    description: str = ""


# ============================================================
# 六十四卦 → 书法策略映射
# ============================================================

class CalligraphyRuleBase:
    """
    书法六十四卦规则库。
    
    每个卦由上下卦组合推导：
    - 上卦代表结构类型（字的整体框架）
    - 下卦代表风格倾向（笔画的执行风格）
    - 规则参数从上下卦的八卦原型加权插值得到
    
    例如：
    - 天山遁(乾上艮下)：上卦乾(刚健方正)→结构规整，下卦艮(稳重)→笔法沉稳
      → brush_method=中锋(乾主导)，pressure_base=0.7*0.7+0.8*0.3=0.73
    
    爻位关系在执行层面的作用：
    - 乘（上覆下）→ 上一笔收笔与下一笔起笔的衔接压力
    - 承（下载上）→ 承笔压力基准调整
    - 比（左右相邻）→ 笔画间距/重心修正
    - 应（上下呼应）→ 对应笔画的风格一致性
    - 当位→ 笔画的执行精度要求
    - 得中→ 笔画粗细/力度的平衡
    """
    
    # ---- 64卦定义（序号, 卦名, 上卦, 下卦）----
    _HEXAGRAMS: List[Tuple[int, str, str, str]] = [
        (1,  '乾为天',    '乾', '乾'),
        (2,  '坤为地',    '坤', '坤'),
        (3,  '水雷屯',    '坎', '震'),
        (4,  '山水蒙',    '艮', '坎'),
        (5,  '水天需',    '坎', '乾'),
        (6,  '天水讼',    '乾', '坎'),
        (7,  '地水师',    '坤', '坎'),
        (8,  '水地比',    '坎', '坤'),
        (9,  '风天小畜',  '巽', '乾'),
        (10, '天泽履',    '乾', '兑'),
        (11, '地天泰',    '坤', '乾'),
        (12, '天地否',    '乾', '坤'),
        (13, '天火同人',  '乾', '离'),
        (14, '火天大有',  '离', '乾'),
        (15, '地山谦',    '坤', '艮'),
        (16, '雷地豫',    '震', '坤'),
        (17, '泽雷随',    '兑', '震'),
        (18, '山风蛊',    '艮', '巽'),
        (19, '地泽临',    '坤', '兑'),
        (20, '风地观',    '巽', '坤'),
        (21, '火雷噬嗑',  '离', '震'),
        (22, '山火贲',    '艮', '离'),
        (23, '山地剥',    '艮', '坤'),
        (24, '地雷复',    '坤', '震'),
        (25, '天雷无妄',  '乾', '震'),
        (26, '山天大畜',  '艮', '乾'),
        (27, '山雷颐',    '艮', '震'),
        (28, '泽风大过',  '兑', '巽'),
        (29, '坎为水',    '坎', '坎'),
        (30, '离为火',    '离', '离'),
        (31, '泽山咸',    '兑', '艮'),
        (32, '雷风恒',    '震', '巽'),
        (33, '天山遁',    '乾', '艮'),
        (34, '雷天大壮',  '震', '乾'),
        (35, '火地晋',    '离', '坤'),
        (36, '地火明夷',  '坤', '离'),
        (37, '风火家人',  '巽', '离'),
        (38, '火泽睽',    '离', '兑'),
        (39, '水山蹇',    '坎', '艮'),
        (40, '雷水解',    '震', '坎'),
        (41, '山泽损',    '艮', '兑'),
        (42, '风雷益',    '巽', '震'),
        (43, '泽天夬',    '兑', '乾'),
        (44, '天风姤',    '乾', '巽'),
        (45, '泽地萃',    '兑', '坤'),
        (46, '地风升',    '坤', '巽'),
        (47, '泽水困',    '兑', '坎'),
        (48, '水风井',    '坎', '巽'),
        (49, '泽火革',    '兑', '离'),
        (50, '火风鼎',    '离', '巽'),
        (51, '震为雷',    '震', '震'),
        (52, '艮为山',    '艮', '艮'),
        (53, '风山渐',    '巽', '艮'),
        (54, '雷泽归妹',  '震', '兑'),
        (55, '雷火丰',    '震', '离'),
        (56, '火山旅',    '离', '艮'),
        (57, '巽为风',    '巽', '巽'),
        (58, '兑为泽',    '兑', '兑'),
        (59, '风水涣',    '巽', '坎'),
        (60, '水泽节',    '坎', '兑'),
        (61, '风泽中孚',  '巽', '兑'),
        (62, '雷山小过',  '震', '艮'),
        (63, '水火既济',  '坎', '离'),
        (64, '火水未济',  '离', '坎'),
    ]
    
    # ---- 书法语义描述（每个64卦一一条，体现卦名与书法语义） ----
    _DESCRIPTIONS: Dict[str, str] = {
        '乾为天':   '中锋直笔，力道均匀。起笔顿而不死，收笔回锋有力。笔正心正，刚健中正。',
        '坤为地':   '侧锋铺毫，顺锋而入。铺毫舒展，起笔轻入，收笔渐出锋。厚德载物，柔顺包容。',
        '水雷屯':   '屯难初创：藏锋起笔慎入，提按间有顿挫，收笔蓄势待发。',
        '山水蒙':   '蒙昧启明：顿笔蓄力，藏锋内收，笔画迟疑中见坚定。',
        '水天需':   '需待时机：藏锋含蓄起笔，中锋行笔稳健，收笔不露锋芒。',
        '天水讼':   '讼争有节：中锋有力，藏锋内敛，起收分明，笔画有争辩之势。',
        '地水师':   '师出以律：侧锋铺毫起势，藏锋收束，笔画严整有序。',
        '水地比':   '比附亲和：藏锋柔入，侧锋铺展，笔画亲近融和。',
        '风天小畜': '小畜积蓄：绵密柔入，中锋渐进，收笔含蓄，力蓄不发。',
        '天泽履':   '履险如夷：中锋稳健，轻灵起笔，收笔果断，步步为营。',
        '地天泰':   '天地交泰：侧锋柔起，中锋通达，笔画舒展流畅，通泰祥和。',
        '天地否':   '否塞不通：中锋刚直，侧锋涩进，笔画闭塞有阻。',
        '天火同人': '同人相亲：中锋大气，露锋呼应，笔画明亮亲和。',
        '火天大有': '大有丰盛：露锋轻快起笔，中锋磅礴行笔，收笔饱满。',
        '地山谦':   '谦逊有节：侧锋柔入，顿笔沉稳，笔画内敛不张扬。',
        '雷地豫':   '豫乐舒展：提按灵动，侧锋铺展，笔画愉悦舒展。',
        '泽雷随':   '随顺自然：轻灵入笔，提按相随，笔画顺势而为。',
        '山风蛊':   '蛊坏整治：顿笔重起，绵密行笔，笔画整顿有力。',
        '地泽临':   '临下亲和：侧锋铺展，轻灵点缀，笔画亲切近人。',
        '风地观':   '观览四方：绵密细入，侧锋铺展，笔画审慎观察。',
        '火雷噬嗑': '噬嗑咬合：露锋切入，提按断连，笔画咬合有力。',
        '山火贲':   '贲饰文采：顿笔凝重，露锋装饰，笔画华美有度。',
        '山地剥':   '剥落凋零：顿笔沉重，侧锋剥离，笔画渐消渐退。',
        '地雷复':   '复归本源：侧锋柔起，提按回复，笔画循环往复。',
        '天雷无妄': '无妄真实：中锋正直，提按自然，笔画不假雕饰。',
        '山天大畜': '大畜厚积：顿笔蓄势，中锋雄浑，笔画积力待发。',
        '山雷颐':   '颐养中和：顿笔稳起，提按有节，笔画滋养从容。',
        '泽风大过': '大过非常：轻灵起笔，绵密过度，笔画超越常规。',
        '坎为水':   '藏锋回锋，内敛含蓄。起笔逆行藏锋，行笔稳重，收笔回锋内收。',
        '离为火':   '露锋出尖，锋芒毕露。起笔轻快，行笔灵动，收笔出锋见尖。',
        '泽山咸':   '咸感相应：轻灵入笔，顿笔感应，笔画相互呼应。',
        '雷风恒':   '恒久不变：提按有常，绵密持续，笔画稳定持久。',
        '天山遁':   '退藏于密：收锋内敛，顿笔稳重，笔画紧凑，重心沉稳。',
        '雷天大壮': '刚健奋发：提按重按，中锋磅礴，笔画舒展有力，气势雄壮。',
        '火地晋':   '晋进向上：露锋明快，侧锋推进，笔画进取向上。',
        '地火明夷': '明夷晦暗：侧锋暗入，露锋收敛，笔画隐忍不露。',
        '风火家人': '家人亲和：绵密柔入，露锋温暖，笔画亲切自然。',
        '火泽睽':   '睽违乖离：露锋尖利，轻灵跳跃，笔画背离不协。',
        '水山蹇':   '蹇难艰行：藏锋深蓄，顿笔阻涩，笔画艰难行进。',
        '雷水解':   '解脱困境：提按破局，藏锋渐释，笔画由紧到松。',
        '山泽损':   '损下益上：顿笔沉抑，轻灵减省，笔画精简克制。',
        '风雷益':   '益增益进：绵密滋养，提按增益，笔画日渐丰盈。',
        '泽天夬':   '夬决果断：轻灵决断，中锋果敢，笔画干净利落。',
        '天风姤':   '姤遇不期：中锋端重，绵密柔遇，笔画邂逅相逢。',
        '泽地萃':   '萃聚精华：轻灵会聚，侧锋融合，笔画聚集凝练。',
        '地风升':   '升进向上：侧锋托举，绵密攀升，笔画节节高升。',
        '泽水困':   '困厄受制：轻灵受限，藏锋困顿，笔画拘束难展。',
        '水风井':   '井养不穷：藏锋深蓄，绵密不绝，笔画源远流长。',
        '泽火革':   '革故鼎新：轻灵破旧，露锋创新，笔画变革有度。',
        '火风鼎':   '鼎立稳重：露锋明丽，绵密稳固，笔画鼎立三方。',
        '震为雷':   '提按变化，轻重交替。起笔重按，行笔提轻，收笔出锋如电。',
        '艮为山':   '顿笔驻留，稳如磐石。起笔重顿蓄力，行笔稳重，收笔驻留。',
        '风山渐':   '循序渐进：绵密徐入，顿笔渐进，笔画缓慢推进。',
        '雷泽归妹': '归妹和合：提按生动，轻灵和悦，笔画归依融合。',
        '雷火丰':   '丰盛盈满：提按饱满，露锋丰盈，笔画充实盛大。',
        '火山旅':   '旅居在外：露锋漂泊，顿笔暂驻，笔画行旅不定。',
        '巽为风':   '绵密弧转，深入顺应。起笔轻入，行笔绵密均匀，收笔顺势回锋。',
        '兑为泽':   '轻灵跳跃，短小精悍。入笔轻快，行笔短促，收笔轻提。',
        '风水涣':   '涣散分离：绵密松散，藏锋涣释，笔画离散不聚。',
        '水泽节':   '节制有度：藏锋约束，轻灵节制，笔画收放有度。',
        '风泽中孚': '中孚诚信：绵密柔入，轻灵悦出，笔画真诚可信。',
        '雷山小过': '小过稍越：提按略过，顿笔稍制，笔画微有过之。',
        '水火既济': '既济功成：藏锋稳入，露锋明出，笔画周全圆满。',
        '火水未济': '未济未成：露锋轻起，藏锋未收，笔画未尽未完。',
    }
    
    # ---- 插值权重 ----
    # 上卦主导结构比例（权重70%），下卦主导风格倾向（权重30%）
    _W_UPPER = 0.70
    _W_LOWER = 0.30
    
    def __init__(self):
        self.rules = self._build_rules()
        # 64卦序号索引：卦名 → 序号
        self._hex_id_map = {name: hid for hid, name, _, _ in self._HEXAGRAMS}
        # 上下卦反查：('乾','艮') → '天山遁'
        self._hex_by_trigrams = {(u, l): name for _, name, u, l in self._HEXAGRAMS}
        # 单字卦名别名兼容：'乾' → '乾为天', '坤' → '坤为地' 等
        _PURE_HEX_NAMES = {'乾': '乾为天', '坤': '坤为地', '震': '震为雷',
                           '艮': '艮为山', '离': '离为火', '坎': '坎为水',
                           '兑': '兑为泽', '巽': '巽为风'}
        self._trigram_alias = _PURE_HEX_NAMES
    
    def _build_trigram_protos(self) -> Dict[str, StrokeRule]:
        """构建8个八卦原型 StrokeRule（不含 description）"""
        protos = {}
        
        # 乾 — 纯阳刚健，中锋直笔
        protos['乾'] = StrokeRule(
            brush_method=BrushMethod.CENTER_TIP,
            pressure_base=0.70,
            pressure_variation=0.10,
            speed_base=0.30,
            start_pressure=0.90,
            end_pressure=0.75,
            start_width_ratio=1.5,
            end_width_ratio=1.3,
            approach_speed=0.15,
            retreat_speed=0.20,
            angle_tolerance=0.05,
        )
        
        # 坤 — 纯阴柔顺，侧锋铺毫
        protos['坤'] = StrokeRule(
            brush_method=BrushMethod.SIDE_TIP,
            pressure_base=0.45,
            pressure_variation=0.20,
            speed_base=0.45,
            start_pressure=0.60,
            end_pressure=0.20,
            start_width_ratio=1.0,
            end_width_ratio=0.3,
            approach_speed=0.30,
            retreat_speed=0.40,
            angle_tolerance=0.15,
        )
        
        # 震 — 雷动电闪，提按变化
        protos['震'] = StrokeRule(
            brush_method=BrushMethod.LIFT_PRESS,
            pressure_base=0.55,
            pressure_variation=0.35,
            speed_base=0.50,
            start_pressure=0.80,
            end_pressure=0.15,
            start_width_ratio=1.3,
            end_width_ratio=0.2,
            approach_speed=0.25,
            retreat_speed=0.60,
            angle_tolerance=0.10,
        )
        
        # 艮 — 山止不动，顿笔驻留
        protos['艮'] = StrokeRule(
            brush_method=BrushMethod.PAUSE_HOLD,
            pressure_base=0.80,
            pressure_variation=0.10,
            speed_base=0.15,
            start_pressure=0.95,
            end_pressure=0.85,
            start_width_ratio=1.8,
            end_width_ratio=1.5,
            approach_speed=0.10,
            retreat_speed=0.10,
            angle_tolerance=0.03,
        )
        
        # 离 — 火明附丽，露锋出尖
        protos['离'] = StrokeRule(
            brush_method=BrushMethod.EXPOSE_TIP,
            pressure_base=0.35,
            pressure_variation=0.25,
            speed_base=0.65,
            start_pressure=0.50,
            end_pressure=0.10,
            start_width_ratio=0.8,
            end_width_ratio=0.15,
            approach_speed=0.40,
            retreat_speed=0.70,
            angle_tolerance=0.12,
        )
        
        # 坎 — 水险内陷，藏锋回锋
        protos['坎'] = StrokeRule(
            brush_method=BrushMethod.HIDE_TIP,
            pressure_base=0.55,
            pressure_variation=0.15,
            speed_base=0.35,
            start_pressure=0.70,
            end_pressure=0.80,
            start_width_ratio=1.2,
            end_width_ratio=1.4,
            approach_speed=0.20,
            retreat_speed=0.15,
            angle_tolerance=0.08,
        )
        
        # 兑 — 悦而轻利，轻灵短促
        protos['兑'] = StrokeRule(
            brush_method=BrushMethod.LIGHT_SKIP,
            pressure_base=0.25,
            pressure_variation=0.15,
            speed_base=0.75,
            start_pressure=0.40,
            end_pressure=0.08,
            start_width_ratio=1.0,
            end_width_ratio=0.1,
            approach_speed=0.50,
            retreat_speed=0.80,
            angle_tolerance=0.20,
        )
        
        # 巽 — 风入无孔，绵密柔韧
        protos['巽'] = StrokeRule(
            brush_method=BrushMethod.DENSE_CURVE,
            pressure_base=0.50,
            pressure_variation=0.15,
            speed_base=0.40,
            start_pressure=0.60,
            end_pressure=0.40,
            start_width_ratio=1.1,
            end_width_ratio=0.8,
            approach_speed=0.25,
            retreat_speed=0.30,
            angle_tolerance=0.08,
        )
        
        return protos
    
    def _build_rules(self) -> Dict[str, StrokeRule]:
        """
        构建完整的六十四卦书法规则库（程序生成 + 加权插值）
        
        每个卦的规则基于上下卦组合推导：
        - 上卦（结构类型）权重 W_UPPER = 70%
        - 下卦（风格倾向）权重 W_LOWER = 30%
        - brush_method 由上卦主导
        - 其他数值参数通过加权平均插值
        """
        protos = self._build_trigram_protos()
        rules = {}
        
        def _interp(up_val: float, lo_val: float) -> float:
            """加权插值"""
            return round(up_val * self._W_UPPER + lo_val * self._W_LOWER, 4)
        
        for hex_id, hex_name, upper, lower in self._HEXAGRAMS:
            up = protos[upper]
            lo = protos[lower]
            
            rule = StrokeRule(
                brush_method=up.brush_method,
                pressure_base=_interp(up.pressure_base, lo.pressure_base),
                pressure_variation=_interp(up.pressure_variation, lo.pressure_variation),
                speed_base=_interp(up.speed_base, lo.speed_base),
                start_pressure=_interp(up.start_pressure, lo.start_pressure),
                end_pressure=_interp(up.end_pressure, lo.end_pressure),
                start_width_ratio=_interp(up.start_width_ratio, lo.start_width_ratio),
                end_width_ratio=_interp(up.end_width_ratio, lo.end_width_ratio),
                approach_speed=_interp(up.approach_speed, lo.approach_speed),
                retreat_speed=_interp(up.retreat_speed, lo.retreat_speed),
                angle_tolerance=_interp(up.angle_tolerance, lo.angle_tolerance),
                description=self._DESCRIPTIONS.get(
                    hex_name,
                    f'{hex_name}：上{up.brush_method.value}下{lo.brush_method.value}。',
                ),
            )
            
            rules[hex_name] = rule
        
        return rules
    
    def get_rule(self, hex_name: str) -> StrokeRule:
        """获取卦象对应的书写规则（按卦名查询，兼容单字八卦名）"""
        # 兼容旧接口：单字八卦名 → 对应纯卦
        if hex_name in self._trigram_alias:
            hex_name = self._trigram_alias[hex_name]
        return self.rules.get(hex_name, self.rules.get('离为火', list(self.rules.values())[0]))
    
    def get_rule_by_trigrams(self, upper: str, lower: str) -> StrokeRule:
        """根据上下卦获取书写规则"""
        hex_name = self._hex_by_trigrams.get((upper, lower))
        if hex_name:
            return self.rules[hex_name]
        return self.get_rule('离为火')
    
    def get_hexagram_id(self, hex_name: str) -> int:
        """获取卦号"""
        return self._hex_id_map.get(hex_name, 0)
    
    def get_all_hexagram_names(self) -> List[str]:
        """返回所有64卦名"""
        return [name for _, name, _, _ in self._HEXAGRAMS]
    
    def print_rule_table(self) -> str:
        """打印完整的64卦规则表（供检查用）"""
        lines = []
        header = f"{'#':>3} {'卦名':<12} {'上卦':<4} {'下卦':<4} {'笔法':<6} {'压力':<6} {'速度':<6} {'起压':<6} {'收压':<6}"
        lines.append(header)
        lines.append("-" * len(header))
        
        for hex_id, hex_name, upper, lower in self._HEXAGRAMS:
            rule = self.rules[hex_name]
            lines.append(
                f"{hex_id:>3} {hex_name:<12} {upper:<4} {lower:<4} "
                f"{rule.brush_method.value:<6} {rule.pressure_base:<6.2f} "
                f"{rule.speed_base:<6.2f} {rule.start_pressure:<6.2f} {rule.end_pressure:<6.2f}"
            )
        
        return "\n".join(lines)
    
    def apply_yao_relations(self, rule: StrokeRule, 
                           relations: Dict[str, float]) -> StrokeRule:
        """
        应用爻位关系修正书写规则。
        
        爻位关系对执行参数的影响：
        - 乘（is_above>0.5）→ 起笔压力 +10%（上覆下，需加重）
        - 承（is_below>0.5）→ 压力基准 +5%（下载上，稳重）
        - 比（is_left/is_right>0.5）→ 角度容许偏差 +20%（相邻需协调）
        - 应（is_aligned>0.5）→ 速度 +10%（呼应则流畅）
        - 接（is_connected>0.5）→ 起笔压力 -10%（交接则轻入）
        """
        r = copy.deepcopy(rule)
        
        if relations.get('above', 0) > 0.5:
            r.start_pressure *= 1.1
        if relations.get('below', 0) > 0.5:
            r.pressure_base *= 1.05
        if relations.get('left', 0) > 0.5 or relations.get('right', 0) > 0.5:
            r.angle_tolerance *= 1.2
        if relations.get('aligned', 0) > 0.5:
            r.speed_base *= 1.1
        if relations.get('connected', 0) > 0.5:
            r.start_pressure *= 0.9
        
        return r
    
    def generate_execution_plan(self, stroke_features, trigram_memberships,
                                relations) -> List[Dict]:
        """
        生成完整的笔画执行计划。
        
        对每个笔画：
        1. 确定主导卦象 → 选择笔法
        2. 查找规则库 → 获取压力/速度/起收笔参数
        3. 应用爻位关系 → 修正参数
        4. 输出完整的执行指令
        
        Returns:
            [{stroke_id, trigram, brush, pressure_base, speed, start_pressure, 
              end_pressure, start_width, end_width, trajectory_params, description}, ...]
        """
        plans = []
        
        for i, f in enumerate(stroke_features):
            # 1. 确定主导卦
            best_tri = max(trigram_memberships, 
                          key=lambda t: trigram_memberships[t][i])
            
            # 2. 获取规则
            rule = self.get_rule(best_tri)
            
            # 3. 应用爻位关系修正
            stroke_relations = {}
            for rel in relations:
                if rel.i == i or rel.j == i:
                    stroke_relations['above'] = max(stroke_relations.get('above', 0), 
                        rel.is_above if rel.i == i else rel.is_below)
                    stroke_relations['below'] = max(stroke_relations.get('below', 0),
                        rel.is_below if rel.i == i else rel.is_above)
                    stroke_relations['left'] = max(stroke_relations.get('left', 0),
                        rel.is_left if rel.i == i else rel.is_right)
                    stroke_relations['right'] = max(stroke_relations.get('right', 0),
                        rel.is_right if rel.i == i else rel.is_left)
                    stroke_relations['connected'] = max(stroke_relations.get('connected', 0),
                        rel.is_connected)
                    stroke_relations['aligned'] = max(stroke_relations.get('aligned', 0),
                        rel.is_aligned)
            
            rule = self.apply_yao_relations(rule, stroke_relations)
            
            # 4. 生成执行指令
            plan = {
                'stroke_id': i,
                'trigram': best_tri,
                'brush_method': rule.brush_method.value,
                'pressure_base': rule.pressure_base,
                'speed': rule.speed_base,
                'start_pressure': rule.start_pressure,
                'end_pressure': rule.end_pressure,
                'start_width': rule.start_width_ratio,
                'end_width': rule.end_width_ratio,
                'angle_tolerance': rule.angle_tolerance,
                'description': rule.description,
            }
            plans.append(plan)
        
        return plans


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    rb = CalligraphyRuleBase()
    
    print("=" * 80)
    print("  YLYW 书法六十四卦规则库")
    print("=" * 80)
    
    # 完整规则表
    print(f"\n{'#'*3} {'卦名':<12} {'上卦':<4} {'下卦':<4} {'笔法':<6} "
          f"{'压力':<6} {'速度':<6} {'起压':<6} {'收压':<6}  description")
    print("-" * 80)
    
    for hex_id, hex_name, upper, lower in rb._HEXAGRAMS:
        rule = rb.rules[hex_name]
        print(
            f"{hex_id:>3} {hex_name:<12} {upper:<4} {lower:<4} "
            f"{rule.brush_method.value:<6} {rule.pressure_base:<6.2f} "
            f"{rule.speed_base:<6.2f} {rule.start_pressure:<6.2f} "
            f"{rule.end_pressure:<6.2f}  {rule.description}"
        )
    
    print(f"\n  总计: {len(rb.rules)} 卦")
    
    # 验证每个64卦是否都有规则
    missing = [name for _, name, _, _ in rb._HEXAGRAMS if name not in rb.rules]
    if missing:
        print(f"\n  ⚠ 缺少: {missing}")
    else:
        print(f"\n  ✓ 64卦规则完整")
    
    # 对特定卦做插值验证
    print("\n" + "=" * 60)
    print("  插值验证")
    print("=" * 60)
    
    test_cases = [
        ('乾为天',   '乾', '乾', '(纯乾)'),
        ('坤为地',   '坤', '坤', '(纯坤)'),
        ('天山遁',   '乾', '艮', '(乾上艮下)'),
        ('雷天大壮', '震', '乾', '(震上乾下)'),
        ('水火既济', '坎', '离', '(坎上离下)'),
        ('火水未济', '离', '坎', '(离上坎下)'),
    ]
    
    for name, u, l, note in test_cases:
        rule = rb.get_rule(name)
        print(f"\n  {name} {note}:")
        print(f"    brush_method = {rule.brush_method.value}")
        print(f"    pressure_base = {rule.pressure_base:.4f}  (上{u}={rb._build_trigram_protos()[u].pressure_base:.2f}, 下{l}={rb._build_trigram_protos()[l].pressure_base:.2f})")
        print(f"    speed_base    = {rule.speed_base:.4f}")
        print(f"    desc: {rule.description}")
    
    # 测试与现有代码的兼容性
    print("\n" + "=" * 60)
    print("  兼容性测试")
    print("=" * 60)
    
    # 测试 get_rule 返回八卦名（旧接口兼容）
    for tri_name in ['乾', '坤', '震', '艮', '离', '坎', '兑', '巽']:
        rule = rb.get_rule(tri_name)
        if rule:
            print(f"  get_rule('{tri_name}') → {rule.brush_method.value} (fallback)")
    
    # 测试 get_rule_by_trigrams
    rule = rb.get_rule_by_trigrams('乾', '艮')
    print(f"\n  get_rule_by_trigrams('乾','艮') → {rule.brush_method.value}, desc: {rule.description}")
    
    print("\n" + "=" * 80)
    print("  测试完成")
    print("=" * 80)
