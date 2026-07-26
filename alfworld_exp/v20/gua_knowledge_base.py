#!/usr/bin/env python3
"""
gua_knowledge_base.py — 词义→八卦隶属度知识库

《说卦传》万物类象思想：
  艮  山 止  果实、静止之物：苹果、柜子、桌子
  坎  水 陷  液体、冷藏：冰箱、水槽、饮料
  离  火 明  光明、热源：台灯、灶台、烹饪相关
  震  雷 动  动作、工具：拿、去、打开、刀叉
  巽  风 入  柔顺、放置：毛巾、布、放
  乾  天 健  刚硬、强力：金属、锅
  兑  悦 口  开口、喜悦：门、窗户
  坤  地 顺  包容、承载：盘子、碗、床

支持运行时学习——每个实例会记录观察到的卦象频率，
运行越多，映射越精准。
"""
from __future__ import annotations
import os, json
from typing import Dict, List, Optional, Tuple

# 八卦数组索引
_GUA_NAMES = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]

def _gua_vec(dom_idx: int, strength: float = 0.85) -> List[float]:
    """生成主导八卦为 dom_idx 的 8 维隶属度向量"""
    v = [0.3] * 8
    v[dom_idx] = strength
    return v

# ══════════════════════════════════════════════════════
# 手工先验映射表（《周易》万物类象）
# ══════════════════════════════════════════════════════
# 用纯符号表示八卦索引

_HANDCRAFTED: Dict[str, Tuple[int, List[float]]] = {
    # ── 艮（1=山=止=稳固静止）──
    # 果实类
    "苹果": (6, _gua_vec(6)),
    "番茄": (6, _gua_vec(6)),
    "土豆": (6, _gua_vec(6)),
    "洋葱": (6, _gua_vec(6)),
    "胡椒": (6, _gua_vec(6)),
    "萝卜": (6, _gua_vec(6)),
    "茄子": (6, _gua_vec(6)),
    "玉米": (6, _gua_vec(6)),
    "南瓜": (6, _gua_vec(6)),
    "橙子": (6, _gua_vec(6)),
    "香蕉": (6, _gua_vec(6)),
    "柠檬": (6, _gua_vec(6)),
    "草莓": (6, _gua_vec(6)),
    "葡萄": (6, _gua_vec(6)),
    "西瓜": (6, _gua_vec(6)),
    "桃子": (6, _gua_vec(6)),
    "芒果": (6, _gua_vec(6)),
    "梨": (6, _gua_vec(6)),
    "樱桃": (6, _gua_vec(6)),
    "李子": (6, _gua_vec(6)),
    "杏": (6, _gua_vec(6)),
    "红枣": (6, _gua_vec(6)),
    # 静态家具
    "桌子": (6, _gua_vec(6)),
    "台": (6, _gua_vec(6)),
    "柜台": (6, _gua_vec(6)),
    "柜": (6, _gua_vec(6)),
    "橱柜": (6, _gua_vec(6)),
    "抽屉": (6, _gua_vec(6)),
    "书": (6, _gua_vec(6, 0.7)),
    "书桌": (6, _gua_vec(6)),
    "架子": (6, _gua_vec(6)),
    "货架": (6, _gua_vec(6)),
    "梳妆台": (6, _gua_vec(6)),
    "边桌": (6, _gua_vec(6)),
    "咖啡桌": (6, _gua_vec(6)),
    "床头柜": (6, _gua_vec(6)),
    # 器皿
    "杯子": (6, _gua_vec(6)),
    "花瓶": (6, _gua_vec(6)),
    "罐子": (6, _gua_vec(6)),
    "箱子": (6, _gua_vec(6)),
    "盒子": (6, _gua_vec(6)),
    "保险箱": (6, _gua_vec(6)),

    # ── 坤（7=地=顺=包容承载）──
    "鸡蛋": (7, _gua_vec(7)),
    "面包": (7, _gua_vec(7)),
    "土豆": (7, _gua_vec(7)),  # also 艮
    "盘子": (7, _gua_vec(7)),
    "碗": (7, _gua_vec(7)),
    "盆": (7, _gua_vec(7)),
    "床": (7, _gua_vec(7)),
    "沙发": (7, _gua_vec(7)),
    "扶手椅": (7, _gua_vec(7)),
    "脚凳": (7, _gua_vec(7)),
    "地毯": (7, _gua_vec(7)),
    "垫子": (7, _gua_vec(7)),
    "枕头": (7, _gua_vec(7)),
    "布料": (7, _gua_vec(7)),
    "衣服": (7, _gua_vec(7)),
    "布料": (7, _gua_vec(7)),
    "包": (7, _gua_vec(7)),
    "手提箱": (7, _gua_vec(7)),
    "袋子": (7, _gua_vec(7)),
    "垃圾桶": (7, _gua_vec(7, 0.65)),
    "洗衣篮": (7, _gua_vec(7)),

    # ── 离（2=火=明=热源/光亮）──
    "灯": (2, _gua_vec(2)),
    "台灯": (2, _gua_vec(2)),
    "地灯": (2, _gua_vec(2)),
    "蜡烛": (2, _gua_vec(2)),
    "灶台": (2, _gua_vec(2)),
    "炉": (2, _gua_vec(2)),
    "烤箱": (2, _gua_vec(2)),
    "微波炉": (2, _gua_vec(2)),
    "烤面包机": (2, _gua_vec(2)),
    "咖啡机": (2, _gua_vec(2)),
    "电视": (2, _gua_vec(2)),
    "电脑": (2, _gua_vec(2)),
    "手机": (2, _gua_vec(2)),
    "屏幕": (2, _gua_vec(2)),
    "厨房": (2, _gua_vec(2)),
    "烹饪": (2, _gua_vec(2)),
    "加热": (2, _gua_vec(2)),
    "热": (2, _gua_vec(2)),
    "火": (2, _gua_vec(2)),

    # ── 坎（5=水=陷=液体/冷藏）──
    "冰箱": (5, _gua_vec(5)),
    "冰": (5, _gua_vec(5)),
    "水槽": (5, _gua_vec(5)),
    "水": (5, _gua_vec(5)),
    "水池": (5, _gua_vec(5)),
    "浴缸": (5, _gua_vec(5)),
    "马桶": (5, _gua_vec(5)),
    "饮料": (5, _gua_vec(5)),
    "汤": (5, _gua_vec(5)),
    "牛奶": (5, _gua_vec(5)),
    "水": (5, _gua_vec(5)),
    "酒": (5, _gua_vec(5)),
    "清洗": (5, _gua_vec(5)),
    "洗": (5, _gua_vec(5)),
    "冷却": (5, _gua_vec(5)),
    "冷": (5, _gua_vec(5)),
    "冰镇": (5, _gua_vec(5)),

    # ── 震（3=雷=动=工具/动作）──
    # 动词
    "去": (3, _gua_vec(3)),
    "走": (3, _gua_vec(3)),
    "拿": (3, _gua_vec(3)),
    "取": (3, _gua_vec(3)),
    "抓": (3, _gua_vec(3)),
    "打开": (3, _gua_vec(3)),
    "开": (3, _gua_vec(3)),
    "移动": (3, _gua_vec(3)),
    "推动": (3, _gua_vec(3)),
    "拉动": (3, _gua_vec(3)),
    "使用": (3, _gua_vec(3)),
    # 工具
    "叉": (3, _gua_vec(3)),
    "叉子": (3, _gua_vec(3)),
    "刀": (3, _gua_vec(3)),
    "勺子": (3, _gua_vec(3)),
    "匙": (3, _gua_vec(3)),
    "工具": (3, _gua_vec(3)),
    "锤子": (3, _gua_vec(3)),
    "螺丝刀": (3, _gua_vec(3)),
    "钥匙": (3, _gua_vec(3)),
    "钟": (3, _gua_vec(3)),

    # ── 巽（4=风=入=柔顺/放置）──
    "放": (4, _gua_vec(4)),
    "放置": (4, _gua_vec(4)),
    "毛巾": (4, _gua_vec(4)),
    "布": (4, _gua_vec(4)),
    "抹布": (4, _gua_vec(4)),
    "海绵": (4, _gua_vec(4)),
    "纸": (4, _gua_vec(4)),
    "纸巾": (4, _gua_vec(4)),
    "窗帘": (4, _gua_vec(4)),
    "绳": (4, _gua_vec(4)),
    "线": (4, _gua_vec(4)),
    "毛": (4, _gua_vec(4)),
    "羽毛": (4, _gua_vec(4)),

    # ── 乾（0=天=健=刚硬/金属）──
    "锅": (0, _gua_vec(0)),
    "刀": (0, _gua_vec(0)),  # also 震
    "金属": (0, _gua_vec(0)),
    "铁": (0, _gua_vec(0)),
    "钢": (0, _gua_vec(0)),
    "硬币": (0, _gua_vec(0)),
    "钥匙": (0, _gua_vec(0)),
    "钉子": (0, _gua_vec(0)),
    "锁": (0, _gua_vec(0)),
    "汽车": (0, _gua_vec(0)),
    "自行车": (0, _gua_vec(0)),

    # ── 兑（1=悦=口=开口）──
    "门": (1, _gua_vec(1)),
    "窗户": (1, _gua_vec(1)),
    "窗": (1, _gua_vec(1)),
    "口": (1, _gua_vec(1)),
    "嘴": (1, _gua_vec(1)),
    "喇叭": (1, _gua_vec(1)),
    "铃": (1, _gua_vec(1)),
    "乐器": (1, _gua_vec(1)),
    "镜子": (1, _gua_vec(1)),
    "微笑": (1, _gua_vec(1)),

    # ── 特殊概念 ──
    "关闭": (6, _gua_vec(6)),
    "关": (6, _gua_vec(6)),
    "停止": (6, _gua_vec(6)),
    "休息": (7, _gua_vec(7)),
    "看": (2, _gua_vec(2)),
    "观察": (2, _gua_vec(2)),
    "检查": (2, _gua_vec(2)),
    "检查": (2, _gua_vec(2)),
}

# ALFWorld 英文类别名映射到汉字（供运行时学习使用）
_ALFWORLD_CLASS_TO_HANZI: Dict[str, str] = {
    # 物体
    "apple": "苹果", "bread": "面包", "egg": "鸡蛋", "potato": "土豆",
    "tomato": "番茄", "lettuce": "青菜", "pepper": "胡椒", "onion": "洋葱",
    "carrot": "萝卜", "eggplant": "茄子", "corn": "玉米", "pumpkin": "南瓜",
    "orange": "橙子", "banana": "香蕉", "lemon": "柠檬", "strawberry": "草莓",
    "grape": "葡萄", "watermelon": "西瓜", "peach": "桃子", "mango": "芒果",
    "pear": "梨", "cherry": "樱桃", "plum": "李子", "apricot": "杏",
    "fork": "叉子", "knife": "刀", "spoon": "勺子",
    "cup": "杯子", "plate": "盘子", "bowl": "碗", "bottle": "瓶子",
    "mug": "马克杯", "glass": "玻璃杯",
    "towel": "毛巾", "sponge": "海绵", "paper": "纸", "tissue": "纸巾",
    "cloth": "布", "soap": "肥皂",
    "book": "书", "pen": "笔", "pencil": "铅笔",
    "cellphone": "手机", "remote": "遥控器", "key": "钥匙",
    "candle": "蜡烛", "vase": "花瓶", "pillow": "枕头",
    "watch": "手表", "wallet": "钱包", "purse": "包",
    # 容器/位置
    "cabinet": "橱柜", "drawer": "抽屉", "countertop": "柜台",
    "coffeetable": "咖啡桌", "sidetable": "边桌",
    "diningtable": "餐桌", "desk": "书桌",
    "dresser": "梳妆台", "shelf": "架子", "bed": "床",
    "sofa": "沙发", "armchair": "扶手椅", "ottoman": "脚凳", "cart": "推车",
    "fridge": "冰箱", "microwave": "微波炉", "stoveburner": "灶台",
    "toaster": "烤面包机", "coffeemachine": "咖啡机",
    "sinkbasin": "水槽", "sink": "水池",
    "garbagecan": "垃圾桶", "laundryhamper": "洗衣篮",
    "safe": "保险箱", "toilet": "马桶",
    "bathtubbasin": "浴缸", "tvstand": "电视柜",
    "handtowelholder": "毛巾架", "towelholder": "毛巾架",
    "toiletpaperhanger": "纸巾架",
    "desklamp": "台灯", "floorlamp": "地灯",
    "box": "箱子",
    # 功能
    "stove": "炉灶",
}


# ══════════════════════════════════════════════════════
# 运行时学习知识库
# ══════════════════════════════════════════════════════

class GuaKnowledgeBase:
    """词义→八卦隶属度知识库，支持运行时学习与持久化
    
    使用层次：
      L1 → 手工先验映射（_HANDCRAFTED）
      L2 → 英文类别→汉字的映射表
      L3 → 运行时观察积累
      L4 → 默认（坤卦）
    """

    _instance = None  # 单例

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, persist_path: Optional[str] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        # 持久化路径
        if persist_path is None:
            self.persist_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "gua_knowledge.json"
            )
        else:
            self.persist_path = persist_path

        # L1: 手工先验
        self._handcrafted: Dict[str, Tuple[int, List[float]]] = dict(_HANDCRAFTED)

        # L3: 运行时学习统计
        # {hanzi: {"count": N, "gua_counts": [8维数组], "dominant_gua": str, "vec": [8维]}}
        self._learned: Dict[str, dict] = {}

        # L2: 英文→汉字类别映射
        self._class_map: Dict[str, str] = dict(_ALFWORLD_CLASS_TO_HANZI)

        # 加载持久化数据
        self._load()

    # ── 核心查询 ──

    def lookup(self, hanzi: str) -> Optional[Tuple[str, List[float]]]:
        """查询汉字对应的八卦隶属度
        
        返回 (dominant_gua_name, 8维向量) 或 None
        """
        if not hanzi or hanzi.strip() == "":
            return None

        # L1: 精确匹配手工先验（按关键词长度降序，长词优先）
        sorted_kws = sorted(self._handcrafted.items(), key=lambda x: -len(x[0]))
        for kw, (dom_idx, vec) in sorted_kws:
            if kw in hanzi:
                return (_GUA_NAMES[dom_idx], vec)

        # L3: 运行时学习（如果有足够数据）
        if hanzi in self._learned:
            d = self._learned[hanzi]
            if d["count"] >= 2:
                return (d["dominant_gua"], d["vec"])

        # 遍历每个字做查询
        # 拆双字词为单字匹配
        for ch in hanzi:
            for kw, (dom_idx, vec) in sorted_kws:
                if ch == kw and len(kw) == 1:
                    return (_GUA_NAMES[dom_idx], vec)

        return None

    def lookup_by_class(self, cls_name: str) -> Optional[Tuple[str, List[float]]]:
        """按ALFWorld英文类别名查询"""
        hanzi = self._class_map.get(cls_name)
        if hanzi:
            return self.lookup(hanzi)
        return None

    # ── 运行时学习 ──

    def observe(self, hanzi: str, bagua_vec: List[float]):
        """观察到一个汉字被映射到某个矢量，用于积累统计"""
        if not hanzi or hanzi.strip() == "" or len(bagua_vec) != 8:
            return
        if hanzi not in self._learned:
            self._learned[hanzi] = {
                "count": 0,
                "gua_counts": [0.0] * 8,
                "dominant_gua": "坤",
                "vec": [0.3] * 8,
            }
        d = self._learned[hanzi]
        d["count"] += 1
        dom_idx = int(np.argmax(bagua_vec)) if 'numpy' in str(type(bagua_vec)) else _max_idx(bagua_vec)
        d["gua_counts"][dom_idx] += 1.0
        # 滑动平均更新vec
        n = d["count"]
        for i in range(8):
            d["vec"][i] = (d["vec"][i] * (n - 1) + bagua_vec[i]) / n
        # 更新dominant
        d["dominant_gua"] = _GUA_NAMES[_max_idx(d["gua_counts"])]

    def observe_by_class(self, cls_name: str, bagua_vec: List[float]):
        """按英文类别名学习"""
        hanzi = self._class_map.get(cls_name)
        if hanzi:
            self.observe(hanzi, bagua_vec)

    def observe_entity(self, en_id: str, bagua_vec: List[float]):
        """直接按英文实体id（如 'apple 1'）学习"""
        cls = en_id.rsplit(" ", 1)[0] if " " in en_id.strip() else en_id
        self.observe_by_class(cls, bagua_vec)

    # ── 持久化 ──

    def _load(self):
        if not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, encoding='utf-8') as f:
                data = json.load(f)
            learned = data.get("learned", {})
            for k, v in learned.items():
                v["gua_counts"] = [float(x) for x in v.get("gua_counts", [0]*8)]
                v["vec"] = [float(x) for x in v.get("vec", [0.3]*8)]
            self._learned = learned
            custom = data.get("custom_map", {})
            for k, (dom_idx, vec) in custom.items():
                self._handcrafted[k] = (int(dom_idx), [float(x) for x in vec])
        except Exception:
            pass

    def save(self):
        data = {
            "learned": self._learned,
            "custom_map": {k: (int(dom), list(vec)) for k, (dom, vec) in self._handcrafted.items()
                          if k not in _HANDCRAFTED},
        }
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            with open(self.persist_path, "w", encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── 统计查询 ──

    def stats(self) -> dict:
        """知识库统计"""
        return {
            "handcrafted": len(self._handcrafted),
            "learned": len(self._learned),
            "class_map": len(self._class_map),
            "total": len(self._handcrafted) + len(self._learned),
        }

    def list_learned(self, min_count: int = 1) -> List[str]:
        return [k for k, v in self._learned.items() if v["count"] >= min_count]

    # ── 手动扩充 ──

    def add_handcrafted(self, keyword: str, gua_name: str, vec: Optional[List[float]] = None):
        """添加手工先验映射"""
        if gua_name not in _GUA_NAMES:
            raise ValueError(f"gua_name must be in {_GUA_NAMES}")
        dom_idx = _GUA_NAMES.index(gua_name)
        self._handcrafted[keyword] = (dom_idx, vec or _gua_vec(dom_idx))
        self.save()


def _max_idx(lst: list) -> int:
    """纯Python argmax"""
    return max(range(len(lst)), key=lambda i: lst[i])


# ══════════════════════════════════════════════════════
# 便捷函数（供 cn_world_model 引用）
# ══════════════════════════════════════════════════════

_KNOWLEDGE = None

def get_knowledge() -> GuaKnowledgeBase:
    global _KNOWLEDGE
    if _KNOWLEDGE is None:
        _KNOWLEDGE = GuaKnowledgeBase()
    return _KNOWLEDGE


def semantic_lookup(hanzi: str) -> Optional[Tuple[str, List[float]]]:
    """词义→八卦隶属度查询（先验+学习）"""
    return get_knowledge().lookup(hanzi)


def semantic_lookup_class(cls_name: str) -> Optional[Tuple[str, List[float]]]:
    """英文类别名→八卦隶属度"""
    return get_knowledge().lookup_by_class(cls_name)


def observe_learning(hanzi: str, bagua_vec: List[float]):
    """运行时学习一条映射"""
    get_knowledge().observe(hanzi, bagua_vec)


def save_knowledge():
    """持久化所有学习数据"""
    get_knowledge().save()


# ══════════════════════════════════════════════════════
# 单元测试
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    kb = get_knowledge()
    print(f"=== GuaKnowledgeBase 初始化 ===")
    print(f"统计: {kb.stats()}")
    print()
    test_words = ["苹果", "冰箱", "水槽", "台灯", "叉子", "盘子", "毛巾", "门",
                   "抽屉", "锅", "微波炉", "书", "沙发", "去", "拿", "放", "打开"]
    for w in test_words:
        result = kb.lookup(w)
        if result:
            gua, vec = result
            print(f"  {w:5s} → {gua:3s}  {[round(v,2) for v in vec]}")
        else:
            print(f"  {w:5s} → 未找到")

    print()
    # 测试类别映射
    for cls in ["apple", "cabinet", "fridge", "sinkbasin", "desklamp"]:
        result = kb.lookup_by_class(cls)
        if result:
            gua, vec = result
            print(f"  {cls:15s} → {gua:3s}")
        else:
            print(f"  {cls:15s} → 未找到")

    print()
    print("=== 运行时学习测试 ===")
    import numpy as np
    kb.observe("新词", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
    result = kb.lookup("新词")
    print(f"  学习后: {'新词'} -> {result}")
    save_knowledge()
    print("  已持久化")
