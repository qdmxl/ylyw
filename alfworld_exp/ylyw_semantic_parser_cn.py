#!/usr/bin/env python3
"""YLYW Chinese Semantic Parser for ALFWorld using ChineseBridge"""

import sys, os, math, re, json
from typing import Dict, List, Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chinese_bridge import ChineseBridge

YLYW_CORE = os.path.expanduser("~/MXL/科研/ylyw/api_docs")
if YLYW_CORE not in sys.path:
    sys.path.insert(0, YLYW_CORE)
from ylyw_core import PriorManual

BAGUA = ["Qian", "Dui", "Li", "Zhen", "Xun", "Kan", "Gen", "Kun"]
ACTION_VERBS_CN = ["使用", "关", "关上", "关闭", "冲洗", "冷", "冷却", "冷藏", "冻", "切", "切割", "切换", "切片", "切碎", "到", "制冷", "刷", "剁", "前往", "加热", "去", "取", "寻找", "开启", "微波", "打开", "打开开关", "找", "抓起", "拾取", "拿", "拿着", "拿起", "挪", "握住", "搜索", "搬", "擦", "擦拭", "擦洗", "放", "放下", "放入", "放置", "查看", "检查", "洗", "洗涤", "清洁", "清洗", "烤", "热", "烹", "煮", "用", "看", "移动", "观察", "走到", "走进", "进入"]
OBJECT_NOUNS_CN = ["书", "信用卡", "光盘", "刀", "刷子", "勺子", "叉子", "台灯", "咖啡机", "喷壶", "土豆", "奶酪", "布", "平底锅", "手机", "手表", "打蛋器", "报纸", "时钟", "杂志", "杯子", "枕头", "棒球", "棒球棒", "毛巾", "汤勺", "汤匙", "洋葱", "洗碗海绵", "海绵", "灯", "烤面包机", "玻璃杯", "球棒", "瓶子", "生菜", "番茄", "百叶窗", "盐", "盒子", "盘子", "碗", "笔记本电脑", "篮球", "纸巾盒", "肥皂", "肥皂瓶", "胡椒", "花瓶", "苹果", "萝卜", "蜡烛", "遥控器", "酒瓶", "钟", "钢笔", "钥匙链", "铅笔", "铲子", "锅", "镜子", "闹钟", "雕像", "面包", "餐叉", "香蕉", "马桶搋子", "鸡蛋", "黄油"]
LOCATION_NOUNS_CN = ["上面", "书架", "书桌", "保险箱", "冰箱", "凳子", "卧室", "厨房", "可移动", "台面", "咖啡机", "地上", "垃圾", "垃圾桶", "床", "床头柜", "微波炉", "扶手椅", "抽屉", "旁边", "架子", "柜台", "柜子", "桌子", "桌面", "梳妆台", "椅子", "橱柜", "水槽", "沙发", "洗衣篮", "浴缸", "灶", "灶台", "烤箱", "烤面包机", "电视柜", "窗户", "脚凳", "茶几", "躺椅", "里面", "餐桌", "马桶"]
TOOL_NOUNS_CN = ["光源", "台灯", "咖啡机", "开关", "微波炉", "水槽", "灯", "灯光", "灯开关", "灶台", "烤箱", "烤面包机", "电视机", "落地灯"]
FUNCTION_WORDS_CN = ["一", "一个", "一些", "三", "与", "两", "个", "为", "了", "二", "什么", "从", "他", "以", "先", "再", "冷却过的", "冷的", "到", "加热过的", "只", "可以", "和", "在", "她", "它", "它们", "对", "就", "干净的", "张", "怎么", "或", "把", "是", "有", "清洁过的", "热的", "然后", "用", "的", "给", "能", "被", "要", "这个", "那个"]
WORD_CLASS_VECTORS = {"action": [0.2, 0.3, 0.4, 0.85, 0.5, 0.3, 0.2, 0.1], "object": [0.3, 0.4, 0.3, 0.2, 0.3, 0.4, 0.4, 0.85], "location": [0.2, 0.3, 0.2, 0.1, 0.2, 0.3, 0.85, 0.3], "tool": [0.3, 0.4, 0.85, 0.2, 0.3, 0.2, 0.1, 0.2], "function": [0.5, 0.5, 0.4, 0.3, 0.8, 0.4, 0.3, 0.3], "unknown": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]}
CN_TASK_KEYWORDS = {"look_at_obj_in_light": ["灯", "lamp", "light", "看", "检查", "examine", "光源"], "pick_clean_then_place_in_recep": ["clean", "wash", "清洁", "清洗", "洗", "擦", "rinse", "washing"], "pick_heat_then_place_in_recep": ["heat", "加热", "热", "microwave", "cook", "warm", "微波"], "pick_cool_then_place_in_recep": ["cool", "冷却", "冷", "chill", "fridge", "冷藏"], "pick_two_obj_and_place": ["two", "两个", "both"], "pick_and_place_with_movable_recep": ["movable", "移动", "可移动"]}
ALL_CN_WORDS = ["一", "一个", "一些", "三", "上面", "与", "两", "个", "为", "书", "书架", "书桌", "了", "二", "什么", "从", "他", "以", "使用", "保险箱", "信用卡", "先", "光源", "光盘", "关", "关上", "关闭", "再", "冰箱", "冲洗", "冷", "冷却", "冷却过的", "冷的", "冷藏", "冻", "凳子", "刀", "切", "切割", "切换", "切片", "切碎", "到", "制冷", "刷", "刷子", "剁", "前往", "加热", "加热过的", "勺子", "卧室", "厨房", "去", "叉子", "取", "只", "可以", "可移动", "台灯", "台面", "和", "咖啡机", "喷壶", "土豆", "在", "地上", "垃圾", "垃圾桶", "奶酪", "她", "它", "它们", "对", "寻找", "就", "布", "干净的", "平底锅", "床", "床头柜", "开关", "开启", "张", "微波", "微波炉", "怎么", "或", "手机", "手表", "打开", "打开开关", "打蛋器", "扶手椅", "找", "把", "抓起", "报纸", "抽屉", "拾取", "拿", "拿着", "拿起", "挪", "握住", "搜索", "搬", "擦", "擦拭", "擦洗", "放", "放下", "放入", "放置", "旁边", "时钟", "是", "有", "杂志", "杯子", "枕头", "架子", "柜台", "柜子", "查看", "桌子", "桌面", "梳妆台", "检查", "棒球", "棒球棒", "椅子", "橱柜", "毛巾", "水槽", "汤勺", "汤匙", "沙发", "洋葱", "洗", "洗涤", "洗碗海绵", "洗衣篮", "浴缸", "海绵", "清洁", "清洁过的", "清洗", "灯", "灯光", "灯开关", "灶", "灶台", "烤", "烤箱", "烤面包机", "热", "热的", "烹", "然后", "煮", "玻璃杯", "球棒", "瓶子", "生菜", "用", "电视机", "电视柜", "番茄", "百叶窗", "的", "盐", "盒子", "盘子", "看", "碗", "移动", "窗户", "笔记本电脑", "篮球", "纸巾盒", "给", "肥皂", "肥皂瓶", "胡椒", "能", "脚凳", "花瓶", "苹果", "茶几", "萝卜", "落地灯", "蜡烛", "被", "要", "观察", "走到", "走进", "躺椅", "这个", "进入", "遥控器", "那个", "酒瓶", "里面", "钟", "钢笔", "钥匙链", "铅笔", "铲子", "锅", "镜子", "闹钟", "雕像", "面包", "餐叉", "餐桌", "香蕉", "马桶", "马桶搋子", "鸡蛋", "黄油"]

class YLYWChineseSemanticParser:
    """YLYW Chinese semantic parser using ChineseBridge for EN->CN translation"""

    def __init__(self):
        self.manual = PriorManual(verbose=False)
        self.bridge = ChineseBridge()
        # Load API key from openclaw config
        self._llm_api_key = ""
        try:
            cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
            if os.path.exists(cfg_path):
                with open(cfg_path) as _f:
                    _cfg = json.load(_f)
                _k = _cfg.get("models",{}).get("providers",{}).get("deepseek",{}).get("apiKey","")
                if _k: self._llm_api_key = _k
        except Exception:
            self._llm_api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    PROMPT_TEMPLATE = "Translate this ALFWorld game task to Chinese, using only these Chinese words for matching items:\n\n\u7269\u4f53: \u4e66, \u4fe1\u7528\u5361, \u5149\u76d8, \u5200, \u5237\u5b50, \u52fa\u5b50, \u53c9\u5b50, \u53f0\u706f, \u5496\u5561\u673a, \u55b7\u58f6, \u571f\u8c46, \u5976\u916a, \u5e03, \u5e73\u5e95\u9505, \u624b\u673a, \u624b\u8868, \u6253\u86cb\u5668, \u62a5\u7eb8, \u65f6\u949f, \u6742\u5fd7, \u676f\u5b50, \u6795\u5934, \u68d2\u7403, \u68d2\u7403\u68d2, \u6bdb\u5dfe, \u6c64\u52fa, \u6c64\u5319, \u6d0b\u8471, \u6d17\u7897\u6d77\u7ef5, \u6d77\u7ef5, \u706f, \u70e4\u9762\u5305\u673a, \u73bb\u7483\u676f, \u7403\u68d2, \u74f6\u5b50, \u751f\u83dc, \u756a\u8304, \u767e\u53f6\u7a97, \u76d0, \u76d2\u5b50, \u76d8\u5b50, \u7897, \u7b14\u8bb0\u672c\u7535\u8111, \u7bee\u7403, \u7eb8\u5dfe\u76d2, \u80a5\u7682, \u80a5\u7682\u74f6, \u80e1\u6912, \u82b1\u74f6, \u82f9\u679c, \u841d\u535c, \u8721\u70db, \u9065\u63a7\u5668, \u9152\u74f6, \u949f, \u94a2\u7b14, \u94a5\u5319\u94fe, \u94c5\u7b14, \u94f2\u5b50, \u9505, \u955c\u5b50, \u95f9\u949f, \u96d5\u50cf, \u9762\u5305, \u9910\u53c9, \u9999\u8549, \u9a6c\u6876\u640b\u5b50, \u9e21\u86cb, \u9ec4\u6cb9\n\u4f4d\u7f6e: \u4e0a\u9762, \u4e66\u67b6, \u4e66\u684c, \u4fdd\u9669\u7bb1, \u51b0\u7bb1, \u51f3\u5b50, \u5367\u5ba4, \u53a8\u623f, \u53ef\u79fb\u52a8, \u53f0\u9762, \u5496\u5561\u673a, \u5730\u4e0a, \u5783\u573e, \u5783\u573e\u6876, \u5e8a, \u5e8a\u5934\u67dc, \u5fae\u6ce2\u7089, \u6276\u624b\u6905, \u62bd\u5c49, \u65c1\u8fb9, \u67b6\u5b50, \u67dc\u53f0, \u67dc\u5b50, \u684c\u5b50, \u684c\u9762, \u68b3\u5986\u53f0, \u6905\u5b50, \u6a71\u67dc, \u6c34\u69fd, \u6c99\u53d1, \u6d17\u8863\u7bee, \u6d74\u7f38, \u7076, \u7076\u53f0, \u70e4\u7bb1, \u70e4\u9762\u5305\u673a, \u7535\u89c6\u67dc, \u7a97\u6237, \u811a\u51f3, \u8336\u51e0, \u8eba\u6905, \u91cc\u9762, \u9910\u684c, \u9a6c\u6876\n\u5de5\u5177: \u5149\u6e90, \u53f0\u706f, \u5496\u5561\u673a, \u5f00\u5173, \u5fae\u6ce2\u7089, \u6c34\u69fd, \u706f, \u706f\u5149, \u706f\u5f00\u5173, \u7076\u53f0, \u70e4\u7bb1, \u70e4\u9762\u5305\u673a, \u7535\u89c6\u673a, \u843d\u5730\u706f\n\nRules: output only Chinese translation, no explanation.\nUse listed words when describing matching items.\nExamples:\n'Hold the clock and turn on the lamp.' -> '\u62ff\u7740\u65f6\u949f\u5e76\u6253\u5f00\u53f0\u706f'\n'put a mug in the coffee table' -> '\u628a\u676f\u5b50\u653e\u5728\u8336\u51e0\u4e0a'\n'clean a potato with the sinkbasin' -> '\u7528\u6c34\u69fd\u6e05\u6d17\u571f\u8c46'\n'Look at a basketball in the lamp light.' -> '\u5728\u706f\u5149\u4e0b\u770b\u7bee\u7403'\n\nText: "

    def _llm_translate(self, text: str) -> str:
        """LLM translation with vocabulary constraints"""
        if not self._llm_api_key:
            return ""
        try:
            import urllib.request
            prompt = self.PROMPT_TEMPLATE + text
            data = json.dumps({
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 100,
            }).encode()
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=data,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + self._llm_api_key},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def en_task_to_cn(self, task_desc: str) -> str:
        """English to Chinese using LLM translation (primary)"""
        # Try LLM first
        llm = self._llm_translate(task_desc)
        if llm:
            return llm
        # Fallback: ChineseBridge rule-based
        cn = self.bridge._translate_task_desc(task_desc)
        if cn and len(cn) > 3:
            return cn
        # Last fallback
        return task_desc

    def classify_word(self, word: str) -> Tuple[str, list]:
        """Classify Chinese word into category"""
        wl = word.strip()
        if wl in FUNCTION_WORDS_CN:
            return ("function", WORD_CLASS_VECTORS["function"])
        elif wl in ACTION_VERBS_CN:
            return ("action", WORD_CLASS_VECTORS["action"])
        elif wl in TOOL_NOUNS_CN:
            return ("tool", WORD_CLASS_VECTORS["tool"])
        elif wl in LOCATION_NOUNS_CN:
            return ("location", WORD_CLASS_VECTORS["location"])
        elif wl in OBJECT_NOUNS_CN:
            return ("object", WORD_CLASS_VECTORS["object"])
        else:
            for loc in sorted(LOCATION_NOUNS_CN, key=len, reverse=True):
                if loc in wl: return ("location", WORD_CLASS_VECTORS["location"])
            for obj in sorted(OBJECT_NOUNS_CN, key=len, reverse=True):
                if obj in wl: return ("object", WORD_CLASS_VECTORS["object"])
            for act in sorted(ACTION_VERBS_CN, key=len, reverse=True):
                if wl.startswith(act): return ("action", WORD_CLASS_VECTORS["action"])
            return ("unknown", WORD_CLASS_VECTORS["unknown"])

    def word_relation(self, c1: str, c2: str) -> str:
        """Semantic relation between word classes"""
        if c1 == "function" or c2 == "function": return "boundary"
        if c1 == "action" and c2 in ("object","location","tool"): return "cheng"
        if c1 in ("object","location","tool") and c2 == "action": return "cheng_ni"
        if c1 == "object" and c2 == "location": return "ying"
        if c1 in ("object","location","tool") and c2 in ("object","location","tool"): return "bi"
        if c1 == "tool" and c2 == "object": return "ying"
        return "unknown"

    def tokenize_cn(self, text: str) -> list:
        """Chinese word segmentation"""
        if not text: return []
        tokens = text.split()
        result = []
        for token in tokens:
            i = 0
            while i < len(token):
                matched = False
                for length in range(min(4, len(token)-i), 0, -1):
                    word = token[i:i+length]
                    if word in ALL_CN_WORDS or length == 1:
                        result.append(word); i += length; matched = True; break
                if not matched: result.append(token[i]); i += 1
        return result

    def parse_task_desc(self, task_desc: str, is_cn: bool = False) -> dict:
        """Parse English/Chinese task description into YLYW Chinese semantic analysis"""
        cn_text = task_desc if is_cn else self.en_task_to_cn(task_desc)
        raw_tokens = self.tokenize_cn(cn_text)
        word_info = [{"word": w, "class": self.classify_word(w)[0]} for w in raw_tokens]
        
        ci = [i for i, wi in enumerate(word_info) if wi["class"] != "function"]
        relations = []
        for k in range(len(ci)-1):
            i, j = ci[k], ci[k+1]
            r = self.word_relation(word_info[i]["class"], word_info[j]["class"])
            relations.append((i, j, r))
        
        chunks, cur = [], []
        for wi in word_info:
            if wi["class"] == "function":
                if cur: chunks.append(cur); cur = []
            else: cur.append(wi)
        if cur: chunks.append(cur)
        
        task_type = self._infer_task_type(word_info, cn_text)
        args = self._infer_args(word_info)
        ylyw = self._ylyw_encode(word_info, task_type)
        
        return {
            "task_type": task_type,
            "cn_task_desc": cn_text,
            "words": [(wi["word"], wi["class"]) for wi in word_info],
            "chunks": [[w["word"] for w in c] for c in chunks],
            "inferred_args": args,
            "ylyw_features": ylyw,
        }

    def _infer_task_type(self, word_info, cn_text: str) -> str:
        """Infer task type using Chinese keywords"""
        text = " ".join(wi["word"] for wi in word_info)
        for task_type, kws in CN_TASK_KEYWORDS.items():
            for kw in kws:
                if kw in text or kw in cn_text.lower():
                    return task_type
        return "pick_and_place_simple"

    def _infer_args(self, word_info) -> dict:
        """Extract Chinese entities from words"""
        objs, locs, tools = [], [], []
        for wi in word_info:
            c = wi["class"]
            if c == "object": objs.append(wi["word"])
            elif c == "location": locs.append(wi["word"])
            elif c == "tool": tools.append(wi["word"])
        return {"objects": objs[:5], "locations": locs[:3], "tools": tools[:3]}

    def _ylyw_encode(self, word_info, task_type: str) -> dict:
        if not word_info:
            return {"yao_vector": [0.5]*6, "hexagram": None, "score": 0.0}
        feats = {"stability": 0.4, "roll_tendency": 0.3,
                 "strength_needed": 0.3, "fragility": 0.3,
                 "task_priority": 0.5, "reachability": 0.5}
        p = self.manual.perceive_and_encode(feats)
        return {"yao_vector": p["yao_vector"].tolist(),
                "hexagram": p["best_hexagram"].name if p["best_hexagram"] else None,
                "score": p["hexagram_match_score"]}

    def score_action(self, cn_cmd: str, target_actions: list,
                     inferred_args: dict, task_type: str,
                     cn_task_desc: str = "") -> float:
        score = 0.0
        cmd = cn_cmd.lower()
        for ta in target_actions:
            if cmd.startswith(ta): score += 1.0
        for obj in inferred_args.get("objects", []):
            if obj in cmd: score += 0.6
        for loc in inferred_args.get("locations", []):
            if loc in cmd: score += 0.5
        for tool in inferred_args.get("tools", []):
            if tool in cmd: score += 0.8
        return score