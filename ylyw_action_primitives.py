#!/usr/bin/env python3
"""
YLYW 动作原语库 — ALFWorld 六爻映射表 (可执行模块)

将 ALFWorld 的 admissible actions 映射到 YLYW 六爻语义空间，
作为语义推理层(卦象)与执行层(环境API)之间的适配器接口。

用法:
    from ylyw_action_primitives import ACTION_PRIMITIVES, ActionPrimitiveAdapter
"""

from typing import Dict, List, Optional, Tuple
import re


# ════════════════════════════════════════════════════════════
# 1. YLYW 六爻 → ALFWorld 动作映射表
# ════════════════════════════════════════════════════════════

ACTION_PRIMITIVES = {
    # ====== 导航 ======
    "navigate": {
        "pddl": "GotoLocation",
        "gua": "111111",            # 乾 ☰ — 主动运动
        "gua_label": "乾为天",
        "semantic_tags": ["move", "motion", "location_change"],
        "params": ["target_receptacle"],
        "alfworld_template": "go to {target_receptacle} 1",
        "template_variants": [
            "go to {target_receptacle} 1",
            "go to {target_receptacle} 2",
            "go to {target_receptacle}",
        ],
        "description": "导航到目标容器/位置",
    },
    "look": {
        "pddl": None,
        "gua": "101101",            # 离 ☲ — 观察照亮
        "gua_label": "离为火",
        "semantic_tags": ["observe", "perception", "scan"],
        "params": [],
        "alfworld_template": "look",
        "template_variants": ["look"],
        "description": "环视周围环境",
    },
    "inventory": {
        "pddl": None,
        "gua": "011011",            # 巽 ☴ — 入内审视
        "gua_label": "巽为风",
        "semantic_tags": ["check", "self", "possession"],
        "params": [],
        "alfworld_template": "inventory",
        "template_variants": ["inventory"],
        "description": "查看当前持有的物品",
    },

    # ====== 操作 ======
    "pickup": {
        "pddl": "PickupObject",
        "gua": "001001",            # 艮 ☶ — 获取/持取
        "gua_label": "艮为山",
        "semantic_tags": ["grasp", "acquire", "hold"],
        "params": ["target_object", "source_receptacle"],
        "alfworld_template": "take {target_object} 1 from {source_receptacle} 1",
        "template_variants": [
            "take {target_object} 1 from {source_receptacle} 1",
            "take {target_object} 1",
        ],
        "description": "从容器上拿起物体",
    },
    "put": {
        "pddl": "PutObject",
        "gua": "010010",            # 坎 ☵ — 放置归位
        "gua_label": "坎为水",
        "semantic_tags": ["place", "deposit", "release"],
        "params": ["target_object", "destination_receptacle"],
        "alfworld_template": "put {target_object} 1 in/on {destination_receptacle} 1",
        "template_variants": [
            "put {target_object} 1 in/on {destination_receptacle} 1",
            "put {target_object} 1 in {destination_receptacle} 1",
            "put {target_object} 1 on {destination_receptacle} 1",
            "move {target_object} 1 to {destination_receptacle} 1",
        ],
        "description": "将物体放置到容器内/上",
    },
    "open": {
        "pddl": "OpenObject",
        "gua": "011010",            # ䷭ 升卦 — 开启
        "gua_label": "地风升",
        "semantic_tags": ["open", "access", "unlock"],
        "params": ["target_container"],
        "alfworld_template": "open {target_container} 1",
        "template_variants": [
            "open {target_container} 1",
            "open {target_container}",
        ],
        "description": "打开容器（如冰箱、柜子等）",
    },
    "close": {
        "pddl": "CloseObject",
        "gua": "001010",            # ䷏ 豫卦 — 闭合收敛
        "gua_label": "雷地豫",
        "semantic_tags": ["close", "seal", "secure"],
        "params": ["target_container"],
        "alfworld_template": "close {target_container} 1",
        "template_variants": [
            "close {target_container} 1",
            "close {target_container}",
        ],
        "description": "关闭容器",
    },
    "toggle": {
        "pddl": "ToggleObject",
        "gua": "110101",            # ䷥ 睽卦 — 切换状态
        "gua_label": "火泽睽",
        "semantic_tags": ["switch", "toggle", "flip"],
        "params": ["target_device"],
        "alfworld_template": "use {target_device} 1",
        "template_variants": [
            "use {target_device} 1",
            "toggle {target_device} 1",
        ],
        "description": "切换设备开关状态（灯、炉灶等）",
    },

    # ====== 物体变换 ======
    "clean": {
        "pddl": "CleanObject",
        "gua": "010010",            # 坎变 ☵ → ䷜
        "gua_after": "110010",
        "gua_label": "坎为水（变水风井）",
        "semantic_tags": ["wash", "clean", "purify"],
        "params": ["target_object", "tool_receptacle"],
        "alfworld_template": "clean {target_object} 1 with {tool_receptacle} 1",
        "template_variants": [
            "clean {target_object} 1 with {tool_receptacle} 1",
        ],
        "description": "在洗物台清洗物体",
    },
    "heat": {
        "pddl": "HeatObject",
        "gua": "101101",            # 离变 ☲
        "gua_after": "101011",
        "gua_label": "离为火（变火地晋）",
        "semantic_tags": ["heat", "cook", "warm"],
        "params": ["target_object", "appliance"],
        "alfworld_template": "heat {target_object} 1 with {appliance} 1",
        "template_variants": [
            "heat {target_object} 1 with {appliance} 1",
            "microwave {target_object} 1",
        ],
        "description": "加热物体（微波炉/灶台等）",
    },
    "cool": {
        "pddl": "CoolObject",
        "gua": "010010",            # 坎变
        "gua_after": "010110",
        "gua_label": "坎为水（变水地比）",
        "semantic_tags": ["cool", "chill", "refrigerate"],
        "params": ["target_object", "appliance"],
        "alfworld_template": "cool {target_object} 1 with {appliance} 1",
        "template_variants": [
            "cool {target_object} 1 with {appliance} 1",
        ],
        "description": "冷却物体（冰箱等）",
    },
    "slice": {
        "pddl": "SliceObject",
        "gua": "110110",            # 兑 ☱ — 毁折分割
        "gua_label": "兑为泽",
        "semantic_tags": ["cut", "slice", "divide"],
        "params": ["target_object", "tool"],
        "alfworld_template": "slice {target_object} 1 with {tool} 1",
        "template_variants": [
            "slice {target_object} 1 with {tool} 1",
        ],
        "description": "用工具切割物体",
    },
}

# ====== 动作类型索引 ======
ACTION_GUA_MAP: Dict[str, str] = {
    name: defn["gua"] for name, defn in ACTION_PRIMITIVES.items()
}

GUA_ACTION_MAP: Dict[str, str] = {
    defn["gua"]: name for name, defn in ACTION_PRIMITIVES.items()
}

# 添加变爻映射
for name, defn in ACTION_PRIMITIVES.items():
    if "gua_after" in defn:
        GUA_ACTION_MAP[defn["gua_after"]] = name


# ════════════════════════════════════════════════════════════
# 2. 参数类型定义
# ════════════════════════════════════════════════════════════

ACTION_PARAMS = {
    "navigate": {"target_receptacle": "receptacle"},
    "look": {},
    "inventory": {},
    "pickup": {"target_object": "item", "source_receptacle": "receptacle"},
    "put": {"target_object": "item", "destination_receptacle": "receptacle"},
    "open": {"target_container": "receptacle"},
    "close": {"target_container": "receptacle"},
    "toggle": {"target_device": "receptacle"},
    "clean": {"target_object": "item", "tool_receptacle": "receptacle"},
    "heat": {"target_object": "item", "appliance": "receptacle"},
    "cool": {"target_object": "item", "appliance": "receptacle"},
    "slice": {"target_object": "item", "tool": "item"},
}

# ====== 物体类型分类（用于参数填充时的类型校验） ======
RECEPTACLE_NAMES = {
    "cabinet", "drawer", "shelf", "desk", "countertop", "counter",
    "fridge", "microwave", "sinkbasin", "sink", "garbagecan", "garbage", "trash", "bin",
    "safe", "bed", "sofa", "toilet", "diningtable", "armchair",
    "stoveburner", "stove", "bathtub", "desklamp", "lamp",
    "floorlamp", "coffeemachine", "toaster", "tvstand", "sidetable",
    "coffeetable", "laundryhamper", "ottoman", "cart",
    "handtowelholder", "toiletpaperhanger",
}

ITEM_NAMES = {
    "plate", "bowl", "cup", "mug", "glass",
    "apple", "potato", "tomato", "egg", "bread", "lettuce",
    "soapbar", "soap", "knife", "spoon", "fork", "spatula", "pan", "pot",
    "book", "pencil", "paper", "newspaper", "laptop", "cellphone",
    "keychain", "remotecontrol", "statue", "vase", "pillow", "towel", "cloth",
    "watch", "bottle", "box", "cd", "alarmclock",
    "baseballbat", "basketball", "peppershaker", "saltshaker",
    "scrubbrush", "spraybottle", "tissuebox", "toiletpaper",
    "butterknife", "creditcard", "plunger", "soapbottle",
    "candle", "ladle", "kettle", "milk", "coffee", "food",
    "breadsliced", "applesliced", "potatosliced", "tomatosliced",
}

TOOL_LIKE_RECEPTACLES = {
    "sinkbasin": "clean",
    "microwave": "heat",
    "fridge": "cool",
    "stoveburner": "heat",
    "desklamp": "toggle",
    "floorlamp": "toggle",
}

# ====== 英文名称别名映射 ======
ALIAS_EN = {
    "counter": "countertop", "sink": "sinkbasin", "garbage": "garbagecan",
    "trash": "garbagecan", "bin": "garbagecan", "lamp": "desklamp",
    "stove": "stoveburner", "stove burner": "stoveburner",
    "coffee machine": "coffeemachine", "tv stand": "tvstand",
    "side table": "sidetable", "coffee table": "coffeetable",
    "laundry hamper": "laundryhamper", "hand towel holder": "handtowelholder",
    "toilet paper holder": "toiletpaperhanger", "desk lamp": "desklamp",
    "floor lamp": "floorlamp", "mug": "cup", "glass": "cup",
    "cell phone": "cellphone", "remote control": "remotecontrol",
    "alarm clock": "alarmclock", "baseball bat": "baseballbat",
    "basket ball": "basketball", "pepper shaker": "peppershaker",
    "salt shaker": "saltshaker", "scrub brush": "scrubbrush",
    "spray bottle": "spraybottle", "tissue box": "tissuebox",
    "toilet paper": "toiletpaper", "butter knife": "butterknife",
    "credit card": "creditcard", "soap bottle": "soapbottle",
    "hand towel": "handtowel",
}


# ════════════════════════════════════════════════════════════
# 3. 场景状态结构
# ════════════════════════════════════════════════════════════

class SceneState:
    """
    场景状态 — 运行时维护的结构化场景信息
    
    用于从卦象推理到具体动作参数的桥接。
    """
    
    def __init__(self):
        self.location: str = "起点"              # 当前位置
        self.holding: Optional[str] = None        # 当前手持物体
        self.holding_objname: str = ""            # 手持物体对象名(不含序号)
        self.container_states: Dict[str, dict] = {}  # 容器状态
        self.object_properties: Dict[str, dict] = {}  # 物体属性
        self.visited_locations: set = set()       # 已到过的位置
        self.steps_taken: int = 0                 # 已执行步数
        self.task_type: str = ""                  # 当前任务类型
        self.task_desc: str = ""                  # 任务描述
        
        # 推理需要的缓存
        self._target_object: str = ""             # 任务目标物体
        self._target_receptacle: str = ""         # 目标容器
        self._tool_receptacle: str = ""           # 预处理设备
        
        # 跨步记忆
        self._done: bool = False                   # 已完成
        self._processed: bool = False              # 是否已做预处理
        self._opened_containers: set = set()       # 已打开的容器
    
    def update_from_obs(self, obs_text: str, action: str = "") -> bool:
        """从 obs 文本更新状态。返回 True 表示状态有实质性改变"""
        changed = False
        ol = obs_text.lower()
        
        # 位置更新
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                loc = after[:idx].strip() if idx > 0 else after
                if loc != self.location:
                    self.location = loc
                    self.visited_locations.add(loc)
                    changed = True
        
        # 持有更新
        if 'you pick up' in ol or 'you take' in ol:
            m = re.search(r'(?:pick up|take) (?:the |a )?([a-z]+)', ol)
            if m:
                self.holding_objname = m.group(1)
                self.holding = f"{m.group(1)} 1"
                changed = True
        if 'you are carrying' in ol:
            m = re.search(r'you are carrying: (?:a )?([a-z]+)', ol)
            if m:
                self.holding_objname = m.group(1)
                self.holding = f"{m.group(1)} 1"
                changed = True
        if 'put' in ol or 'place' in ol or 'move' in ol:
            if 'you put' in ol or 'you place' in ol or 'you move' in ol:
                if self.holding is not None:
                    self.holding = None
                    self.holding_objname = ""
                    changed = True
        
        # 容器状态
        if 'open' in ol and 'you open' in ol:
            m = re.search(r'open the ([a-z]+)', ol)
            if m:
                container = m.group(1)
                self._opened_containers.add(container)
                changed = True
        if 'close' in ol and 'you close' in ol:
            m = re.search(r'close the ([a-z]+)', ol)
            if m:
                container = m.group(1)
                self._opened_containers.discard(container)
                changed = True
        
        # 预处理状态
        if action:
            if 'clean' in action and 'clean' in ol:
                self._processed = True
                changed = True
            elif 'heat' in action and 'heat' in ol:
                self._processed = True
                changed = True
            elif 'cool' in action and 'cool' in ol:
                self._processed = True
                changed = True
            elif 'use' in action and ('turn on' in ol or 'lamp' in ol):
                self._processed = True
                changed = True
        
        # 完成（放下物体后）
        if self.holding is None and action and ('put' in action or 'move' in action):
            self._done = True
            changed = True
        
        return changed
    
    def resolve_objname(self, raw_name: str) -> str:
        """名称规范化（去序号、别名映射）"""
        name = re.sub(r'\s+\d+$', '', raw_name.strip().lower())
        return ALIAS_EN.get(name, name)
    
    def is_receptacle(self, name: str) -> bool:
        """判断是否为容器类"""
        n = self.resolve_objname(name)
        return n in RECEPTACLE_NAMES
    
    def is_item(self, name: str) -> bool:
        """判断是否为可拿取物体"""
        n = self.resolve_objname(name)
        return n in ITEM_NAMES


# ════════════════════════════════════════════════════════════
# 4. 适配器：YLYW 卦象推理 → ALFWorld 命令
# ════════════════════════════════════════════════════════════

class ActionPrimitiveAdapter:
    """
    YLYW 六爻推理 ↔ ALFWorld admissible actions 的适配器
    
    YLYW 引擎输出卦象向量（如 "111111"），由本适配器
    匹配到具体动作类型并填充参数，最终生成 admissible command。
    """
    
    def __init__(self, primitives: dict = None):
        self.primitives = primitives or ACTION_PRIMITIVES
    
    # ──── 卦象匹配 ────
    
    def match_action_by_gua(self, gua: str) -> Optional[str]:
        """六爻字符串 → 动作类型名（精确匹配）"""
        if gua in GUA_ACTION_MAP:
            return GUA_ACTION_MAP[gua]
        return None
    
    def match_action_by_gua_fuzzy(self, gua: str, threshold: float = 0.6) -> List[Tuple[str, float]]:
        """六爻字符串 → 动作类型名（模糊匹配，含变爻）"""
        results = []
        for name, defn in self.primitives.items():
            score = self._gua_similarity(gua, defn["gua"])
            if score >= threshold:
                results.append((name, score))
            if "gua_after" in defn:
                score2 = self._gua_similarity(gua, defn["gua_after"])
                if score2 >= threshold:
                    results.append((name, score2))
        results.sort(key=lambda x: -x[1])
        return results
    
    def match_action_by_tags(self, tags: List[str]) -> List[Tuple[str, int]]:
        """按语义标签匹配动作"""
        results = []
        for name, defn in self.primitives.items():
            matches = sum(1 for t in tags if t in defn["semantic_tags"])
            if matches > 0:
                results.append((name, matches))
        results.sort(key=lambda x: -x[1])
        return results
    
    def _gua_similarity(self, g1: str, g2: str) -> float:
        """六爻相似度：相同位置相同爻的比例"""
        if not g1 or not g2 or len(g1) != len(g2):
            return 0.0
        matches = sum(1 for a, b in zip(g1, g2) if a == b)
        return matches / len(g1)
    
    # ──── 参数填充 ────
    
    def fill_params(self, action_type: str, scene: SceneState,
                    task_info: dict = None) -> dict:
        """
        根据场景状态填充动作参数。
        参数 key 名称与 template_variants 中的占位符一致。
        
        Args:
            action_type: 动作类型名 (如 "pickup", "put", "navigate")
            scene: 当前场景状态
            task_info: 任务信息（含 obj_en, target_en, preproc_en 等）
        
        Returns:
            params dict，用于 template_variant 的 format
        """
        params = {}
        action_def = self.primitives.get(action_type, {})
        param_spec = action_def.get("params", [])
        
        for pname in param_spec:
            if pname == "target_receptacle":
                # 导航目标：优先任务目标，其次探索
                if task_info and task_info.get("target_en"):
                    params[pname] = task_info["target_en"]
                elif task_info and task_info.get("preproc_en"):
                    params[pname] = task_info["preproc_en"]
                else:
                    params[pname] = "cabinet"
            
            elif pname == "target_object":
                if task_info and task_info.get("obj_en"):
                    params[pname] = task_info["obj_en"]
                elif scene.holding_objname:
                    params[pname] = scene.holding_objname
                else:
                    params[pname] = "object"
            
            elif pname == "source_receptacle":
                # 从当前位置取
                loc_resolved = scene.resolve_objname(scene.location)
                if loc_resolved in RECEPTACLE_NAMES:
                    params[pname] = loc_resolved
                elif task_info and task_info.get("target_en"):
                    params[pname] = task_info["target_en"]
                else:
                    params[pname] = "countertop"
            
            elif pname == "destination_receptacle":
                if task_info and task_info.get("target_en"):
                    params[pname] = task_info["target_en"]
                elif scene.holding and scene.is_receptacle(scene.location):
                    params[pname] = scene.location
                else:
                    params[pname] = "countertop"
            
            elif pname == "target_container":
                # 找最近的关门容器
                if scene._opened_containers:
                    for c in ["fridge", "cabinet", "drawer", "microwave"]:
                        if c in scene.visited_locations or True:
                            params[pname] = c
                            break
                else:
                    params[pname] = "fridge"
            
            elif pname in ("tool_receptacle", "appliance"):
                if task_info and task_info.get("preproc_en"):
                    params[pname] = task_info["preproc_en"]
                else:
                    params[pname] = "sinkbasin"
            
            elif pname == "tool":
                params[pname] = "knife"
            
            elif pname == "target_device":
                if task_info and task_info.get("preproc_en"):
                    params[pname] = task_info["preproc_en"]
                else:
                    params[pname] = "desklamp"
        
        return params
    
    # ──── 命令生成与匹配 ────
    
    def generate_commands(self, action_type: str, params: dict) -> List[str]:
        """
        从动作类型 + 参数生成候选命令列表。
        
        Returns:
            候选 ALFWorld 命令字符串列表（由泛到专排序）
        """
        action_def = self.primitives.get(action_type, {})
        variants = action_def.get("template_variants", [])
        
        candidates = []
        for template in variants:
            try:
                cmd = template.format(**params)
                candidates.append(cmd)
            except KeyError:
                continue
        
        return candidates
    
    def match_to_admissible(self, candidates: List[str],
                            admissible_cmds: List[str]) -> Optional[str]:
        """
        从候选命令列表中匹配 admissible 列表中的实际可用命令。
        支持容错匹配（忽略数字差异）。
        
        Args:
            candidates: 候选命令列表（按优先级排序）
            admissible_cmds: 环境提供的可用命令列表
        
        Returns:
            匹配到的命令，None 表示无匹配
        """
        ad_set = set(admissible_cmds)
        
        # 1. 精确匹配
        for cmd in candidates:
            if cmd in ad_set:
                return cmd
        
        # 2. 去数字模糊匹配
        def strip_nums(s: str) -> str:
            return re.sub(r'\s+\d+(\s|$)', ' ', s).strip()
        
        ad_pool = {strip_nums(c): c for c in admissible_cmds}
        
        for cmd in candidates:
            stripped = strip_nums(cmd)
            if stripped in ad_pool:
                return ad_pool[stripped]
        
        # 3. 前缀匹配（动作动词 + 第一个参数）
        cmd_parts = candidates[0].split() if candidates else []
        if len(cmd_parts) >= 2:
            verb = cmd_parts[0]
            obj = cmd_parts[1]
            for ac in admissible_cmds:
                ac_parts = ac.split()
                if len(ac_parts) >= 2 and ac_parts[0] == verb and ac_parts[1] == obj:
                    return ac
        
        return None
    
    def decide(self, gua: str, scene: SceneState, admissible_cmds: List[str],
               task_info: dict = None) -> Optional[str]:
        """
        六爻驱动的完整决策链路。
        
        Args:
            gua: YLYW 推理输出的六爻向量 (如 "111111" 或六爻列表构成的推测)
            scene: 当前场景状态
            admissible_cmds: 环境提供的 admissible commands
            task_info: 任务参数信息
        
        Returns:
            应执行的 ALFWorld 命令字符串，None 表示无法生成
        """
        # 1. 卦象 → 动作类型
        action_type = self.match_action_by_gua(gua)
        if not action_type:
            fuzzy = self.match_action_by_gua_fuzzy(gua, threshold=0.4)
            if not fuzzy:
                return None
            action_type = fuzzy[0][0]
        
        # 2. 参数填充
        params = self.fill_params(action_type, scene, task_info)
        
        # 3. 生成候选命令
        candidates = self.generate_commands(action_type, params)
        if not candidates:
            return None
        
        # 4. 匹配 admissible
        return self.match_to_admissible(candidates, admissible_cmds)
    
    # ──── 从场景状态直接推测动作 ────
    
    def suggest_action_from_state(self, scene: SceneState,
                                   task_info: dict = None,
                                   admissible_cmds: List[str] = None) -> str:
        """
        从场景状态的语义直接推测下一步动作（兼容阶段）。
        用于 HanziEngine 理解场景文本后，基于词义推测的最终映射。
        
        Args:
            scene: 当前场景状态
            task_info: 任务参数信息
            admissible_cmds: admissible commands
        
        Returns:
            推荐的动作命令
        """
        # 如果已完成，等胜利
        if scene._done:
            return "look"
        
        # 手持物体 → 有物待处理
        if scene.holding is not None:
            if not scene._processed:
                # 需要预处理
                if task_info and task_info.get("preproc_en"):
                    preproc = task_info["preproc_en"]
                    # 如果已在预处理设备处
                    if preproc in scene.resolve_objname(scene.location) or \
                       preproc in scene.location.lower():
                        # 生成对应处理动作
                        action_word = TOOL_LIKE_RECEPTACLES.get(preproc, "clean")
                        cmd = f"{action_word} {scene.holding} with {preproc}"
                        if admissible_cmds:
                            return self.match_to_admissible([cmd], admissible_cmds) or cmd
                        return cmd
                    # 不在预处理处 → navigate
                    cmd = f"go to {preproc} 1"
                    if admissible_cmds:
                        return self.match_to_admissible([cmd], admissible_cmds) or cmd
                    return cmd
                # 无预处理要求 → 直接去目标
                if task_info and task_info.get("target_en"):
                    cmd = f"go to {task_info['target_en']} 1"
                    if admissible_cmds:
                        return self.match_to_admissible([cmd], admissible_cmds) or cmd
                    return cmd
            else:
                # 已预处理 → 去目标放置
                if task_info and task_info.get("target_en"):
                    target = task_info["target_en"]
                    if target in scene.resolve_objname(scene.location) or \
                       target in scene.location.lower():
                        cmd = f"put {scene.holding} in/on {target} 1"
                        if admissible_cmds:
                            return self.match_to_admissible([cmd], admissible_cmds) or cmd
                        return cmd
                    cmd = f"go to {target} 1"
                    if admissible_cmds:
                        return self.match_to_admissible([cmd], admissible_cmds) or cmd
                    return cmd
        
        # 空手 → 探索找物体
        if task_info and task_info.get("preproc_en"):
            cmd = f"go to {task_info['preproc_en']} 1"
            if admissible_cmds:
                return self.match_to_admissible([cmd], admissible_cmds) or cmd
            return cmd
        
        if task_info and task_info.get("obj_en"):
            # 尝试在可见物体中匹配目标
            vis = [c for c in admissible_cmds if c.startswith("take ") or c.startswith("go to ")]
            if vis:
                return vis[0]
        
        return "look"
    
    def resolve_to_admissible(self, cmd: str, admissible_cmds: List[str]) -> Optional[str]:
        """通用：手动构造的 cmd 精确/模糊匹配到 admissible"""
        return self.match_to_admissible([cmd], admissible_cmds)


# ════════════════════════════════════════════════════════════
# 5. 工具函数
# ════════════════════════════════════════════════════════════

def get_action_type_by_gua(gua: str) -> Optional[str]:
    """通过六爻字符串获取动作类型名"""
    if gua in GUA_ACTION_MAP:
        return GUA_ACTION_MAP[gua]
    return None


def get_gua_by_action_type(action_type: str) -> Optional[str]:
    """通过动作类型名获取六爻字符串"""
    defn = ACTION_PRIMITIVES.get(action_type)
    if defn:
        return defn["gua"]
    return None


def list_all_action_types() -> List[str]:
    """列出所有动作类型"""
    return list(ACTION_PRIMITIVES.keys())


def is_admissible_success(obs_text: str) -> bool:
    """从 obs 文本判断上一步动作是否真的成功了"""
    ol = obs_text.lower()
    success_kw = [
        "you arrive", "you pick up", "you take", "you put", "you place",
        "you move", "you open", "you close", "you heat", "you clean",
        "you cool", "you toggle", "you slice", "turn on", "turn off",
    ]
    fail_kw = [
        "nothing happens", "can't", "cannot", "not open", "you don't have",
        "isn't here", "can not", "won't", "you already have",
        "there is nothing else", "that's not a valid",
    ]
    for kw in success_kw:
        if kw in ol:
            return True
    for kw in fail_kw:
        if kw in ol:
            return False
    return True


# ════════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# 五行生克辅助（六爻→八卦→五行）
# ════════════════════════════════════════════════════════════

_TRIGRAM_FROM_3YAO = {
    "111": "乾",  # ☰ 天
    "000": "坤",  # ☷ 地
    "001": "震",  # ☳ 雷
    "010": "坎",  # ☵ 水
    "011": "兑",  # ☱ 泽
    "100": "艮",  # ☶ 山
    "101": "离",  # ☲ 火
    "110": "巽",  # ☴ 风
}

_TRIGRAM_WUXING = {
    "乾": "金",
    "兑": "金",
    "离": "火",
    "震": "木",
    "巽": "木",
    "坎": "水",
    "艮": "土",
    "坤": "土",
}

_WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_WUXING_KE    = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def _yao_to_trigrams(yao_str: str):
    """六爻字符串 → (上卦名, 下卦名)"""
    upper = yao_str[:3]
    lower = yao_str[3:]
    return _TRIGRAM_FROM_3YAO.get(upper, "?"), _TRIGRAM_FROM_3YAO.get(lower, "?")


def wuxing_shengke(yao1, yao2: str) -> float:
    """
    计算两个六爻卦的五行生克系数。
    yao1: str (六爻字符串) 或 list (浮点向量)
    yao2: str (六爻字符串)
    用 yao1 的上卦五行为主体，yao2 的下卦五行为客体。
    返回 [-0.2, 0.3] 之间的修正值。
    """
    if isinstance(yao1, (list, tuple)):
        # 用 0.5 阈值将 yao 向量转为六爻字符串  
        yao1 = ''.join('1' if v > 0.5 else '0' for v in yao1[:6])
    up1, _ = _yao_to_trigrams(yao1)
    _, low2 = _yao_to_trigrams(yao2)
    wx1 = _TRIGRAM_WUXING.get(up1, "")
    wx2 = _TRIGRAM_WUXING.get(low2, "")
    if not wx1 or not wx2:
        return 0.0
    # 主体生客体 → 相生 +0.2
    if _WUXING_SHENG.get(wx1) == wx2:
        return 0.20
    # 主体克客体 → 相克 -0.15
    if _WUXING_KE.get(wx1) == wx2:
        return -0.15
    # 客体生主体 → 反向生 +0.10
    if _WUXING_SHENG.get(wx2) == wx1:
        return 0.10
    # 客体克主体 → 反向克 -0.05
    if _WUXING_KE.get(wx2) == wx1:
        return -0.05
    return 0.0


def _get_wuxing_affinity(task_yao: list, loc_gua: str) -> float:
    """任务卦象 vs 位置卦象的五行生克亲和度
    先算六爻相似度加权，再叠加五行生克。
    """
    if not task_yao or len(task_yao) < 6 or not loc_gua:
        return 0.0
    # 六爻相似度：task_yao 的每个维度与 loc_gua 对应位的匹配度
    # 这是 YLYW 语义精度的关键：用连续值而非 0/1 截断
    loc_bits = [int(c) for c in loc_gua]
    sim = sum(1.0 - abs(task_yao[i] - loc_bits[i]) for i in range(6)) / 6.0
    wuxing_bonus = wuxing_shengke(task_yao[:6], loc_gua)  # 仍然需要六爻字符串给五行
    # 综合：相似度 [0,1] * 0.2 + 五行 [-0.15, 0.20]
    return sim * 0.15 + wuxing_bonus * 0.15

if __name__ == "__main__":
    print("=" * 60)
    print("YLYW 动作原语库 — 自检测试")
    print("=" * 60)
    
    adapter = ActionPrimitiveAdapter()
    
    print(f"\n全部动作类型 ({len(ACTION_PRIMITIVES)}):")
    for name, defn in ACTION_PRIMITIVES.items():
        print(f"  {name:12s} gua={defn['gua']} ({defn['gua_label']}) → {defn['alfworld_template'][:50]}")
    
    print(f"\n卦象→动作 映射测试:")
    for name, defn in ACTION_PRIMITIVES.items():
        matched = adapter.match_action_by_gua(defn["gua"])
        print(f"  {defn['gua']} → {matched}")
    
    print(f"\n参数填充测试:")
    scene = SceneState()
    scene.location = "countertop 1"
    scene.holding_objname = "apple"
    scene.holding = "apple 1"
    task_info = {"obj_en": "apple", "target_en": "fridge", "preproc_en": "sinkbasin"}
    
    for action_type in ["pickup", "put", "navigate", "clean", "heat"]:
        params = adapter.fill_params(action_type, scene, task_info)
        cmds = adapter.generate_commands(action_type, params)
        print(f"  {action_type:12s} params={params} → {cmds}")
    
    print(f"\nadmissible 匹配测试:")
    ad = ["go to fridge 1", "take apple 1 from countertop 1", 
          "put apple 1 in/on fridge 1", "clean apple 1 with sinkbasin 1",
          "look", "inventory"]
    for cmd in ["go to fridge 1", "clean apple 1 with sinkbasin 1", "slice apple 1 with knife 1"]:
        match = adapter.match_to_admissible([cmd], ad)
        print(f"  {cmd:45s} → {match}")
    
    print(f"\n全链路测试: navigate → go to")
    result = adapter.decide("111111", scene, ad, task_info)
    print(f"  gua=111111 → {result}")
    
    print(f"\n✅ OK")


# ════════════════════════════════════════════════════════════
# 6. YLYW 探索引擎 — 位置卦象与物体卦象匹配
# ════════════════════════════════════════════════════════════

# 每个位置类型的六爻卦象（语义特征）
# 六爻维度：初爻藏纳、二爻可达、三爻显隐、四爻大小、五爻温湿、上爻动静
LOCATION_GUA = {
    "cabinet":       "001010",  # ☷豫 — 藏物、封闭、干燥
    "drawer":        "000010",  # ☰䷖ — 抽屉、浅藏、平开
    "shelf":         "001010",  # ☷䷽ — 展示、存物、可见
    "countertop":    "101010",  # ☲䷾ — 台面、开放、工作
    "desk":          "101010",  # ☲䷾ — 桌面、开放、工作
    "sinkbasin":     "010010",  # ☵䷜ — 水、清洗、湿润
    "fridge":        "010110",  # ☵䷻ — 冷、封闭、冷藏
    "microwave":     "101001",  # ☲䷍ — 热、封闭、加热
    "garbagecan":    "001001",  # ☶䷨ — 收纳、废弃
    "stoveburner":   "101101",  # ☲䷝ — 火、热、烹饪
    "bed":           "001100",  # ☶䷳ — 休息、静止
    "sofa":          "001100",  # ☶䷳ — 休息、坐卧
    "toilet":        "010000",  # ☵䷜ — 水卫、封闭
    "bathtub":       "010001",  # ☵䷾ — 水、大、洗浴
    "desklamp":      "101001",  # ☲䷝ — 灯、光、照明
    "floorlamp":     "101001",  # ☲䷝ — 灯、光、照明
    "tvstand":       "101010",  # ☲䷾ — 台面、放置
    "sidetable":     "101010",  # ☲䷾ — 台面、放置
    "coffeemachine": "101010",  # ☲䷾ — 台面、电器
    "toiletpaperhanger": "001001", # ☶䷨ — 挂放、收纳
    "handtowelholder": "001001",  # ☶䷨ — 挂放、收纳
    "towelholder":   "001001",  # ☶䷨ — 挂放、收纳
    "coffeetable":   "101010",  # ☲䷾ — 台面
    "armchair":      "001100",  # ☶䷳ — 坐具
    "diningtable":   "101010",  # ☲䷾ — 台面
    "laundryhamper": "001001",  # ☶䷨ — 收纳
    "ottoman":       "001100",  # ☶䷳ — 坐具
    "safe":          "001010",  # ☷䷖ — 安全、封闭
    "cart":          "101000",  # ☳䷧ — 移动、开放
}

# 物体类型的六爻卦象（在 YLYW 语义中的特征）
# 六爻维度：初爻大小、二爻材质、三爻形态、四爻用途、五爻温度、上爻状态
OBJECT_GUA = {
    "plate":         "101000",  # 扁、平、瓷、餐具
    "bowl":          "010010",  # 凹、容、器皿
    "cup":           "010101",  # 小、凹、饮具
    "mug":           "001101",  # 杯、陶、饮具
    "glass":         "010010",  # 透明、脆、饮具
    "apple":         "001101",  # 圆、果、生鲜
    "potato":        "001101",  # 实、根茎、生鲜
    "tomato":        "010101",  # 圆、果、生鲜
    "egg":           "001001",  # 小、圆、生鲜
    "bread":         "101001",  # 软、食、烘焙
    "lettuce":       "010001",  # 叶、绿、生鲜
    "soapbar":       "001010",  # 方、固、清洁
    "soapbottle":    "010001",  # 瓶、液、清洁
    "knife":         "001110",  # 长、刃、切割（藏于抽屉）
    "spoon":         "010100",  # 凹、小、餐具
    "fork":          "101100",  # 尖、齿、餐具
    "spatula":       "101010",  # 扁、铲、厨具
    "pan":           "101010",  # 平、锅、厨具
    "pot":           "010010",  # 深、锅、厨具
    "book":          "001010",  # 方、纸、读物
    "pencil":        "101101",  # 长、细、文具
    "towel":         "001010",  # 柔、布、清洁
    "handtowel":     "001010",  # 柔、布、清洁
    "dishsponge":    "010001",  # 软、孔、清洁
    "cloth":         "001010",  # 柔、布、清洁
    "watch":         "001001",  # 小、环、穿戴
    "cellphone":     "010101",  # 方、电、通讯
    "vase":          "010010",  # 高、凹、装饰
    "statue":        "001001",  # 立、固、装饰
    "pillow":        "001001",  # 软、方、卧具
    "laptop":        "101010",  # 扁、电、办公
    "pen":           "101101",  # 长、细、文具
    "creditcard":    "001010",  # 扁、小、薄
    "alarmclock":    "101001",  # 方、电、计时
    "newspaper":     "101000",  # 薄、纸、读物
    "keychain":      "001001",  # 小、环、配饰
    "remotecontrol": "101101",  # 长、电、操控
    "baseballbat":   "101101",  # 长、棒、运动
    "basketball":    "010101",  # 圆、大、运动
    "peppershaker":  "001011",  # 小、调、粉
    "saltshaker":    "001011",  # 小、调、粉
    "scrubbrush":    "101101",  # 长、刷、清洁
    "spraybottle":   "010001",  # 瓶、喷、清洁
    "tissuebox":     "001010",  # 方、纸、柔
    "toiletpaper":   "001010",  # 圆、纸、柔
    "butterknife":   "101010",  # 扁、刃、餐具
    "candle":        "101101",  # 长、烛、光
    "ladle":         "101010",  # 长、勺、厨具
    "kettle":        "010010",  # 深、壶、厨具
    "milk":          "010010",  # 液、白、饮品
    "coffee":        "010001",  # 粉、褐、饮品
    "soap":          "001010",  # 固、清洁（通用）
    "food":          "010101",  # 通用食物
    "breadsliced":   "101001",  # 片、软、食
    "applesliced":   "101001",  # 片、果、食
    "object":        "010101",  # 通用物体
}

# 通用特征：有物体的开放台面 vs 封闭储物空间
OPEN_TYPES = {"shelf", "countertop", "desk", "coffeetable", "diningtable", "sidetable"}
CLOSED_TYPES = {"cabinet", "drawer", "fridge", "microwave", "safe", "box"}


def gua_similarity(g1: str, g2: str) -> float:
    """两个六爻字符串的相似度（相同位置相同爻的比例）"""
    if not g1 or not g2 or len(g1) != len(g2):
        return 0.0
    return sum(1 for a, b in zip(g1, g2) if a == b) / len(g1)


def get_gua_for_receptacle(name: str) -> str:
    """获取容器位置名对应的六爻卦象"""
    name_lower = name.strip().lower()
    # 尝试精确匹配
    if name_lower in LOCATION_GUA:
        return LOCATION_GUA[name_lower]
    # 尝试前缀匹配（如 cabinet 3 → cabinet）
    for key in LOCATION_GUA:
        if name_lower.startswith(key):
            return LOCATION_GUA[key]
    return "101010"  # 默认开放台面


def get_gua_for_object(name: str) -> str:
    """获取物体名对应的六爻卦象"""
    name_lower = name.strip().lower()
    if name_lower in OBJECT_GUA:
        return OBJECT_GUA[name_lower]
    # 前缀匹配（如 apple 2 → apple）
    for key in OBJECT_GUA:
        if name_lower.startswith(key):
            return OBJECT_GUA[key]
    return "010101"  # 默认通用


def find_best_location_for_object(obj_name: str,
                                   available_locs: List[str],
                                   visited: set = None) -> Tuple[str, float]:
    """
    根据物体卦象和位置卦象的匹配度，找到最适合寻找该物体的位置。
    
    Args:
        obj_name: 目标物体名
        available_locs: 当前可去的候选位置列表（admissible 中的 go to 命令）
        visited: 已访问过的位置集合
    
    Returns:
        (最佳位置命令字符串, 匹配分数)
    """
    obj_gua = get_gua_for_object(obj_name)
    
    best_loc = None
    best_score = -1.0
    
    for cmd in available_locs:
        if not cmd.startswith('go to '):
            continue
        loc_name = cmd[6:].strip()  # 去掉 "go to "
        loc_base = re.sub(r'\s+\d+$', '', loc_name).strip().lower()
        
        loc_gua = get_gua_for_receptacle(loc_base)
        score = gua_similarity(obj_gua, loc_gua)
        
        # 如果是封闭容器（cabinet/drawer），物体在里面匹配度加成
        if loc_base in CLOSED_TYPES:
            score += 0.1  # 封闭容器更可能藏物体
        
        # 如果已经访问过，稍微降低优先级
        if visited and loc_name.strip().lower() in visited:
            score -= 0.15
        
        # 如果位置名包含物体名（如 sinkbasin 和 dishsponge），加分
        if loc_base in obj_name or obj_name in loc_base:
            score += 0.2
        
        if score > best_score:
            best_score = score
            best_loc = cmd
    
    return (best_loc, best_score)


def rank_exploration_targets(available_locs: List[str],
                              obj_name: str = None,
                              visited: set = None,
                              task_type: str = None) -> List[Tuple[str, float]]:
    """
    对所有候选位置按 YLYW 卦象匹配度排序。
    
    Returns:
        [(命令字符串, 分数)] 按分数降序排列
    """
    results = []
    
    for cmd in available_locs:
        if not cmd.startswith('go to '):
            continue
        loc_name = cmd[6:].strip()
        loc_base = re.sub(r'\s+\d+$', '', loc_name).strip().lower()
        
        # 基础分：用位置本身语义
        loc_gua = get_gua_for_receptacle(loc_base)
        base_score = 0.5  # 默认中等
        
        # 如果有目标物体，用物体卦象匹配位置
        if obj_name:
            obj_gua = get_gua_for_object(obj_name)
            match = gua_similarity(obj_gua, loc_gua)
            base_score = match
        
        # 封闭容器加成
        if loc_base in CLOSED_TYPES:
            base_score += 0.15
        # 开放台面（已暴露物体，再去意义不大）
        elif loc_base in OPEN_TYPES:
            base_score -= 0.05
        
        # 未访问过的位置加分
        if visited and loc_name.strip().lower() not in visited:
            base_score += 0.2
        
        # 带有目标物体名称相关的位置加分
        if obj_name and (obj_name in loc_base or loc_base in obj_name):
            base_score += 0.3
        
        results.append((cmd, round(base_score, 3)))
    
    results.sort(key=lambda x: -x[1])
    return results


def suggest_exploration(available_locs: List[str],
                         obj_name: str,
                         visited: set = None,
                         verbose: bool = False) -> Optional[str]:
    """
    根据 YLYW 卦象匹配推荐探索位置。
    这是 `_fallback_navigate` 的 YLYW 替代方案。
    """
    ranked = rank_exploration_targets(available_locs, obj_name, visited)
    
    if verbose:
        print(f"  [YLYW探索] 目标={obj_name}")
        for cmd, score in ranked[:5]:
            visited_mark = "✓" if visited and cmd[6:].strip().lower() in visited else " "
            print(f"    {visited_mark} {cmd:25s} score={score:.3f}")
    
    if ranked:
        return ranked[0][0]
    return None


# ════════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("YLYW 动作原语库 + 探索引擎 — 自检测试")
    print("=" * 60)
    
    # 测试位置卦象
    print(f"\n位置卦象样例:")
    for name in ["cabinet", "shelf", "fridge", "toilet", "countertop"]:
        gua = get_gua_for_receptacle(name)
        print(f"  {name:15s} → {gua}")
    
    # 测试物体卦象
    print(f"\n物体卦象样例:")
    for name in ["soapbar", "soapbottle", "mug", "plate", "apple"]:
        gua = get_gua_for_object(name)
        print(f"  {name:15s} → {gua}")
    
    # 测试匹配度
    print(f"\n物体→位置匹配度:")
    obj = "soapbar"  # soapbar 卦象 = 001010
    locs = ["cabinet", "drawer", "shelf", "countertop", "toilet", "fridge"]
    for loc in locs:
        sim = gua_similarity(get_gua_for_object(obj), get_gua_for_receptacle(loc))
        print(f"  {obj:10s} → {loc:12s} sim={sim:.3f}")
    
    # 模拟探索排序
    print(f"\n探索排序 (目标=soapbar):")
    ad_moves = [f"go to {l} {i}" for l in ["cabinet", "drawer", "shelf", "countertop", 
                                            "toilet", "garbagecan", "fridge", "bed", "desk"]
                for i in range(1, 2)]
    visited_set = {"cabinet 1", "drawer 1", "bed 1"}
    ranked = rank_exploration_targets(ad_moves, "soapbar", visited_set)
    for cmd, score in ranked[:8]:
        visited_mark = "✓" if visited_set and cmd[6:].strip().lower() in visited_set else " "
        print(f"  {visited_mark} {cmd:25s} {score:.3f}")


# ════════════════════════════════════════════════════════════
# 7. 探索记忆与知己学习
# ════════════════════════════════════════════════════════════

class ExplorationMemory:
    """
    探索记忆管理器 — 记录每个位置的探索历史，通过知己学习修正位置推荐权重。
    
    核心结构：
      _position_memory: Dict[position_name (str) -> dict]
          每个位置记录：是否访问过、找到的物体列表、在该位置的执行的动作、反馈分数
    
      _class_scores: Dict[class_name (str) -> float]
          每类位置（cabinet/drawer/shelf/...）的全局经验分，基于历史探索结果动态更新
    
      _object_location_affinity: Dict[obj_class (str) -> Dict[loc_class (str), float]]
          物体类 ↔ 位置类的亲和度矩阵，通过知己学习逐步修正
    """
    
    def __init__(self):
        self._position_memory: Dict[str, dict] = {}
        self._class_scores: Dict[str, float] = {}
        self._object_location_affinity: Dict[str, Dict[str, float]] = {}
        
        # 从静态卦象初始化亲和度基线
        self._init_affinity_from_gua()
    
    def _init_affinity_from_gua(self):
        """用静态卦象匹配初始化物体-位置亲和度基线"""
        for obj_name, obj_gua in OBJECT_GUA.items():
            self._object_location_affinity[obj_name] = {}
            for loc_name, loc_gua in LOCATION_GUA.items():
                base = gua_similarity(obj_gua, loc_gua)
                self._object_location_affinity[obj_name][loc_name] = base
    
    def record_visit(self, position: str, obj_found: str = None, 
                     target_obj: str = None, action_success: bool = True):
        """
        记录一次位置访问的结果，更新记忆和亲和度。
        
        Args:
            position: 访问的位置名（如 cabinet 1）
            obj_found: 在该位置找到的物体名（如 soapbar 1），None = 没找到
            target_obj: 正在寻找的目标物体名（如 soapbar）
            action_success: 在该位置执行的动作是否成功
        """
        pos_key = position.strip().lower()
        loc_base = re.sub(r'\s+\d+$', '', pos_key).strip()
        
        # 更新位置记忆
        if pos_key not in self._position_memory:
            self._position_memory[pos_key] = {
                "class": loc_base,
                "visit_count": 0,
                "found_objects": [],
                "success_rate": 0.0,
                "score_delta": 0.0,
                "last_target": None,
            }
        
        mem = self._position_memory[pos_key]
        mem["visit_count"] += 1
        if obj_found:
            obj_base = re.sub(r'\s+\d+$', '', obj_found).strip().lower()
            if obj_base not in mem["found_objects"]:
                mem["found_objects"].append(obj_base)
        
        # 更新成功率
        old_rate = mem["success_rate"]
        mem["success_rate"] = (old_rate * (mem["visit_count"] - 1) + (1.0 if action_success else 0.0)) / mem["visit_count"]
        
        # ── 知己学习：更新物体-位置亲和度 ──
        if target_obj and loc_base in self._object_location_affinity.get(target_obj, {}):
            feedback = 0.1 if obj_found and (not target_obj or target_obj in obj_found) else -0.05
            current = self._object_location_affinity[target_obj][loc_base]
            # 模糊六爻反馈：用小步长修正
            new_val = max(0.0, min(1.0, current + feedback))
            self._object_location_affinity[target_obj][loc_base] = new_val
            mem["score_delta"] += feedback
            
            # 更新类级别经验分
            if loc_base not in self._class_scores:
                self._class_scores[loc_base] = 0.5
            self._class_scores[loc_base] = max(0.0, min(1.0, 
                self._class_scores[loc_base] + feedback * 0.5))
    
    def get_affinity(self, obj_name: str, loc_class: str) -> float:
        """获取物体类与位置类的当前亲和度"""
        if obj_name in self._object_location_affinity:
            if loc_class in self._object_location_affinity[obj_name]:
                return self._object_location_affinity[obj_name][loc_class]
        # fallback: 用静态卦象匹配
        obj_gua = get_gua_for_object(obj_name)
        loc_gua = get_gua_for_receptacle(loc_class)
        return gua_similarity(obj_gua, loc_gua)
    
    def rank_by_affinity(self, available_locs: List[str], 
                          target_obj: str = None,
                          visited: set = None,
                          current_location: str = None,
                          task_yao: list = None) -> List[Tuple[str, float]]:
        """
        基于记忆和亲和度排序候选位置。
        这是 rank_exploration_targets 的记忆增强版本。
        """
        results = []
        
        for cmd in available_locs:
            if not cmd.startswith('go to '):
                continue
            loc_name = cmd[6:].strip()
            loc_base = re.sub(r'\s+\d+$', '', loc_name).strip().lower()
            pos_key = loc_name.strip().lower()
            
            # 基础分：亲和度 + 五行生克
            base_score = 0.5
            if target_obj:
                base_score = self.get_affinity(target_obj, loc_base)
            # ★ 任务卦象与位置卦象的五行生克
            if task_yao and loc_base in LOCATION_GUA:
                wuxing_bonus = _get_wuxing_affinity(task_yao, LOCATION_GUA[loc_base])
                base_score += wuxing_bonus
            
            # 位置记忆修正
            mem = self._position_memory.get(pos_key, None)
            if mem:
                # 访问过且成功率高 → 加分
                if mem["success_rate"] > 0.5 and mem["visit_count"] > 0:
                    base_score += 0.1 * mem["success_rate"]
                # 访问过但什么都没找到 → 减分
                # ★ 重访惩罚指数级：每次 visit_count 累积 -0.25
                if mem["visit_count"] >= 1 and not mem["found_objects"]:
                    base_score -= 0.25 * mem["visit_count"]
                elif mem["visit_count"] >= 1 and mem["found_objects"]:
                    # 即使有找到，重复访问也适度降权（防止在同一处打转）
                    base_score -= 0.15 * (mem["visit_count"] - 1)
                # 之前在这个位置找到过目标同类物体 → 加分
                if target_obj and mem["found_objects"]:
                    for fo in mem["found_objects"]:
                        if fo.startswith(target_obj) or target_obj.startswith(fo):
                            base_score += 0.3
                            break
                # score_delta 累积修正
                base_score += min(0.3, max(-0.3, mem.get("score_delta", 0.0)))
                # ★ 当前所在位置降权（防止在同一个位置反复决策）
                if current_location:
                    cur_key = current_location.strip().lower()
                    if pos_key == cur_key:
                        base_score -= 0.25
            else:
                # 未访问过的位置 → 基础加分（鼓励探索）
                if visited and pos_key not in {v.strip().lower() for v in (visited or set())}:
                    base_score += 0.3  # ★ 从未见过的位置加分翻倍
            
            # 封闭容器（未访问过的）额外加分
            if loc_base in CLOSED_TYPES:
                if not mem or mem["visit_count"] == 0:
                    base_score += 0.30  # ★ +0.15→+0.30
            
            # 类经验分修正
            if loc_base in self._class_scores:
                base_score += (self._class_scores[loc_base] - 0.5) * 0.3
            
            results.append((cmd, round(base_score, 3)))
        
        results.sort(key=lambda x: -x[1])
        return results


# 全局探索记忆实例（单例）
_exploration_memory = ExplorationMemory()

def get_exploration_memory() -> ExplorationMemory:
    """获取全局探索记忆实例"""
    global _exploration_memory
    return _exploration_memory

def ranked_exploration_with_memory(available_locs: List[str],
                                     target_obj: str = None,
                                     visited: set = None,
                                     memory: ExplorationMemory = None,
                                     task_yao: list = None) -> List[Tuple[str, float]]:
    """
    带记忆的探索排序入口。
    
    优先使用 ExplorationMemory（有学习），
    没有记忆实例时降级到静态卦象匹配。
    """
    if memory:
        return memory.rank_by_affinity(available_locs, target_obj, visited, task_yao=task_yao)
    return rank_exploration_targets(available_locs, target_obj, visited)
