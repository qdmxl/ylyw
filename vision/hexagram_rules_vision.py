"""
视觉六十四卦类别规则 (Vision Hexagram Rules) — L3 层

将64卦映射为8种视觉类别。
每种类别对应一个主导八卦的视觉类型。

视觉类别体系（8类）:
    乾类: 结构/几何 — 建筑、棋盘格、条纹、二维码
    坤类: 平滑/均匀 — 天空、水面、纯色、毛玻璃
    震类: 高对比方向 — 栅栏、百叶窗、木质纹理
    巽类: 细纹理 — 织物、草地、砂纸、树皮
    坎类: 曲线/流动 — 水流、云朵、烟雾、大理石纹
    离类: 亮/辐射 — 灯光、火焰、日出、光斑
    艮类: 块状/厚重 — 砖墙、岩石、积木、文字
    兑类: 反射/高光 — 金属、玻璃、水面倒影、镜面

64卦 → 8类别的策略:
    上卦主导: 下卦为辅，上卦为主
    (上卦反映"表现"，下卦反映"本质")

用法:
    >>> rules = VisionHexagramRules()
    >>> category = rules.lookup(hexagram)
    >>> print(category['visual_class'])
"""

import numpy as np
from typing import Optional


class VisionHexagramRules:
    """
    六十四卦 → 视觉类别查表

    卦象由上下两个八卦组成:
        - 上卦(外卦): 视觉的"表现"——人眼看到的直接印象
        - 下卦(内卦): 视觉的"本质"——图像底层的结构属性

    当前版本: 以上卦为分类主导。
    未来可扩展为上下卦双判定。
    """

    # 六十四卦完整名称
    HEXAGRAM_NAMES = [
        "乾为天", "天泽履", "天火同人", "天雷无妄",
        "天风姤", "天水讼", "天山遁", "天地否",
        "泽天夬", "兑为泽", "泽火革", "泽雷随",
        "泽风大过", "泽水困", "泽山咸", "泽地萃",
        "火天大有", "火泽睽", "离为火", "火雷噬嗑",
        "火风鼎", "火水未济", "火山旅", "火地晋",
        "雷天大壮", "雷泽归妹", "雷火丰", "震为雷",
        "雷风恒", "雷水解", "雷山小过", "雷地豫",
        "风天小畜", "风泽中孚", "风火家人", "风雷益",
        "巽为风", "风水涣", "风山渐", "风地观",
        "水天需", "水泽节", "水火既济", "水雷屯",
        "水风井", "坎为水", "水山蹇", "水地比",
        "山天大畜", "山泽损", "山火贲", "山雷颐",
        "山风蛊", "山水蒙", "艮为山", "山地剥",
        "地天泰", "地泽临", "地火明夷", "地雷复",
        "地风升", "地水师", "地山谦", "坤为地",
    ]

    # 上卦索引: 0=乾, 1=兑, 2=离, 3=震, 4=巽, 5=坎, 6=艮, 7=坤
    # 64卦按传统卦序: 上卦循环 (乾兑离震巽坎艮坤 × 8)
    UPPER_TRIGRAMS = [
        0, 1, 2, 3, 4, 5, 6, 7,  # 乾宫: 乾为天~天地否
        1, 1, 2, 3, 4, 5, 6, 7,  # 兑宫: 泽天夬~泽地萃
        2, 1, 2, 3, 4, 5, 6, 7,  # 离宫: 火天大有~火地晋
        3, 1, 2, 3, 4, 5, 6, 7,  # 震宫: 雷天大壮~雷地豫
        4, 1, 2, 3, 4, 5, 6, 7,  # 巽宫: 风天小畜~风地观
        5, 1, 2, 3, 4, 5, 6, 7,  # 坎宫: 水天需~水地比
        6, 1, 2, 3, 4, 5, 6, 7,  # 艮宫: 山天大畜~山地剥
        7, 1, 2, 3, 4, 5, 6, 7,  # 坤宫: 地天泰~坤为地
    ]

    # 视觉类别定义
    VISUAL_CLASSES = {
        0: {
            'name': '乾类·结构/几何',
            'label': 'geometric',
            'description': '高边缘/高对比/高规整的结构化图案: 建筑、条纹、棋盘格、二维码',
            'examples': ['棋盘格', '条纹', '二维码', '建筑立面', '网格'],
        },
        1: {
            'name': '兑类·反射/高光',
            'label': 'specular',
            'description': '高显著性/低规整度的反射高光: 金属、玻璃、水面倒影',
            'examples': ['金属表面', '玻璃', '水面倒影', '镜面'],
        },
        2: {
            'name': '离类·亮/辐射',
            'label': 'radiant',
            'description': '高显著性/高对比的亮暗辐射: 灯光、火焰、日出、聚光灯',
            'examples': ['灯光', '火焰', '日出', '光斑', '聚光灯'],
        },
        3: {
            'name': '震类·高对比方向',
            'label': 'directional',
            'description': '锐利定向边缘/高对比: 栅栏、百叶窗、木纹、条纹布',
            'examples': ['栅栏', '百叶窗', '木纹', '条纹布', '刷痕'],
        },
        4: {
            'name': '巽类·细纹理',
            'label': 'fine_texture',
            'description': '中等均匀度的细密纹理: 织物、草地、砂纸、树皮、毛发',
            'examples': ['织物', '草地', '砂纸', '树皮', '毛发'],
        },
        5: {
            'name': '坎类·曲线/流动',
            'label': 'flowing',
            'description': '低规整度/曲线为主: 水流、云朵、烟雾、大理石纹',
            'examples': ['水流', '云朵', '烟雾', '大理石纹', '墨迹'],
        },
        6: {
            'name': '艮类·块状/厚重',
            'label': 'blocky',
            'description': '大块几何/低纹理/高规整度: 砖墙、岩石、积木、文字块',
            'examples': ['砖墙', '岩石', '积木', '文字', '块状拼接'],
        },
        7: {
            'name': '坤类·平滑/均匀',
            'label': 'smooth',
            'description': '低边缘/低对比/高均匀度: 天空、水面、纯色、毛玻璃',
            'examples': ['天空', '纯色背景', '毛玻璃', '水面', '渐变'],
        },
    }

    def lookup(self, hexagram_index: int) -> dict:
        """
        查询六十四卦对应的视觉类别

        Args:
            hexagram_index: 0-63 (传统卦序)

        Returns:
            dict with keys: class_id, class_name, label, description, examples,
                           hexagram_name, hexagram_index
        """
        if hexagram_index < 0 or hexagram_index >= 64:
            raise ValueError(f"卦序必须在0-63之间，收到: {hexagram_index}")

        upper = self.UPPER_TRIGRAMS[hexagram_index]
        class_info = dict(self.VISUAL_CLASSES[upper])

        return {
            'hexagram_index': hexagram_index,
            'hexagram_name': self.HEXAGRAM_NAMES[hexagram_index],
            'upper_trigram': upper,
            'class_id': upper,
            'class_name': class_info['name'],
            'label': class_info['label'],
            'description': class_info['description'],
            'examples': class_info['examples'],
        }

    def lookup_by_hexagram(self, hexagram_index: int) -> dict:
        """别称, 与lookup相同"""
        return self.lookup(hexagram_index)

    def get_all_classes(self) -> list[dict]:
        """获取全部8个视觉类别的定义"""
        return [dict(self.VISUAL_CLASSES[i]) for i in range(8)]

    def get_class_stats(self) -> dict:
        """统计每个类别包含的卦象数量"""
        stats = {}
        for i in range(8):
            count = sum(1 for u in self.UPPER_TRIGRAMS if u == i)
            stats[i] = {
                'name': self.VISUAL_CLASSES[i]['name'],
                'count': count,
            }
        return stats
