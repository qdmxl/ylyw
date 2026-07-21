# YLYW 动作原语库 — ALFWorld 六爻映射表

> 版本: v1.0
> 说明: 将 ALFWorld 的 admissible actions 映射到 YLYW 六爻语义空间，
> 作为语义推理层(卦象)与执行层(环境API)之间的适配器接口。

---

## 1. 动作类型总览

### 1.1 移动/导航类

| 动作 | PDDL | 六爻编码 | 语义映射 | 卦象 |
|------|------|---------|---------|------|
| go to | GotoLocation | ☰ | 乾为天，主动运动 | `111111` |
| look | — | ☲ | 离为火，观察照亮 | `101101` |

### 1.2 操作类

| 动作 | PDDL | 六爻编码 | 语义映射 | 卦象 |
|------|------|---------|---------|------|
| take | PickupObject | ☶ | 艮为山，获取/持取 | `001001` |
| put | PutObject | ☵ | 坎为水，放置/归位 | `010010` |
| open | OpenObject | ䷭ | 升卦，开启/提升 | `011010` |
| close | CloseObject | ䷏ | 豫卦，闭合/收敛 | `001010` |
| use | ToggleObject | ䷥ | 睽卦，切换/改变状态 | `110101` |

### 1.3 物体变换类

| 动作 | PDDL | 六爻编码 | 语义映射 | 卦象 |
|------|------|---------|---------|------|
| clean | CleanObject | ☵(变) | 坎水变䷜ — 清洗净化 | `010010→110010` |
| heat | HeatObject | ☲(变) | 离火变䷝ — 加热增能 | `101101→101011` |
| cool | CoolObject | ☵(变) | 坎水变䷜ — 降温冷却 | `010010→010110` |
| slice | SliceObject | ☱(变) | 兑为毁折 — 分割劈开 | `110110` |

### 1.4 信息类

| 动作 | PDDL | 六爻编码 | 语义映射 | 卦象 |
|------|------|---------|---------|------|
| inventory | — | ☴ | 巽为风，入内审视 | `011011` |

---

## 2. 动作原语规范定义

```python
ACTION_PRIMITIVES = {
    # ====== 导航 ======
    "navigate": {
        "pddl": "GotoLocation",
        "gua": "111111",           # 乾 ☰
        "semantic_tags": ["move", "motion", "location_change"],
        "params": ["target_receptacle"],
        "alfworld_template": "go to {target} 1",
        "description": "导航到目标容器/位置",
    },
    "look": {
        "pddl": None,              # 环境基础动作
        "gua": "101101",           # 离 ☲
        "semantic_tags": ["observe", "perception", "scan"],
        "params": [],
        "alfworld_template": "look",
        "description": "环视周围环境",
    },
    "inventory": {
        "pddl": None,
        "gua": "011011",           # 巽 ☴
        "semantic_tags": ["check", "self", "possession"],
        "params": [],
        "alfworld_template": "inventory",
        "description": "查看当前持有的物品",
    },

    # ====== 操作 ======
    "pickup": {
        "pddl": "PickupObject",
        "gua": "001001",           # 艮 ☶
        "semantic_tags": ["grasp", "acquire", "hold"],
        "params": ["target_object", "source_receptacle"],
        "alfworld_template": "take {object} 1 from {source} 1",
        "description": "从容器上拿起物体",
    },
    "put": {
        "pddl": "PutObject",
        "gua": "010010",           # 坎 ☵
        "semantic_tags": ["place", "deposit", "release"],
        "params": ["target_object", "destination_receptacle"],
        "alfworld_template": "put {object} 1 in/on {destination} 1",
        "description": "将物体放置到容器内/上",
    },
    "open": {
        "pddl": "OpenObject",
        "gua": "011010",           # ䷭ 升卦
        "semantic_tags": ["open", "access", "unlock"],
        "params": ["target_container"],
        "alfworld_template": "open {target} 1",
        "description": "打开容器（如冰箱、柜子等）",
    },
    "close": {
        "pddl": "CloseObject",
        "gua": "001010",           # ䷏ 豫卦
        "semantic_tags": ["close", "seal", "secure"],
        "params": ["target_container"],
        "alfworld_template": "close {target} 1",
        "description": "关闭容器",
    },
    "toggle": {
        "pddl": "ToggleObject",
        "gua": "110101",           # ䷥ 睽卦
        "semantic_tags": ["switch", "toggle", "flip"],
        "params": ["target_device"],
        "alfworld_template": "use {target} 1",
        "description": "切换设备开关状态（灯、炉灶等）",
    },

    # ====== 物体变换 ======
    "clean": {
        "pddl": "CleanObject",
        "gua": "010010",           # 坎变 ☵ → ䷜
        "gua_after": "110010",
        "semantic_tags": ["wash", "clean", "purify"],
        "params": ["target_object", "tool_receptacle"],
        "alfworld_template": "clean {object} 1 with {tool} 1",
        "description": "在洗物台清洗物体",
    },
    "heat": {
        "pddl": "HeatObject",
        "gua": "101101",           # 离变 ☲
        "gua_after": "101011",
        "semantic_tags": ["heat", "cook", "warm"],
        "params": ["target_object", "appliance"],
        "alfworld_template": "heat {object} 1 with {appliance} 1",
        "description": "加热物体（微波炉/灶台等）",
    },
    "cool": {
        "pddl": "CoolObject",
        "gua": "010010",           # 坎变
        "gua_after": "010110",
        "semantic_tags": ["cool", "chill", "refrigerate"],
        "params": ["target_object", "appliance"],
        "alfworld_template": "cool {object} 1 with {appliance} 1",
        "description": "冷却物体（冰箱等）",
    },
    "slice": {
        "pddl": "SliceObject",
        "gua": "110110",           # 兑 ☱
        "semantic_tags": ["cut", "slice", "divide"],
        "params": ["target_object", "tool"],
        "alfworld_template": "slice {object} 1 with {tool} 1",
        "description": "用工具切割物体",
    },
}
```

---

## 3. 动作类型的参数签名

| 动作 | 参数1 | 参数2 | 可选参数 |
|------|-------|-------|---------|
| navigate | target: receptacle | — | — |
| pickup | object: item | source: receptacle | — |
| put | object: item | destination: receptacle | — |
| open | container: receptacle | — | — |
| close | container: receptacle | — | — |
| toggle | device: receptacle | — | — |
| clean | object: item | tool: receptacle | — |
| heat | object: item | appliance: receptacle | — |
| cool | object: item | appliance: receptacle | — |
| slice | object: item | tool: item | — |

**参数类型说明:**
- `receptacle` = 容器/台面/家具（counter, fridge, sinkbasin, microwave 等）
- `item` = 可拿取物体（apple, plate, knife, potato 等）

---

## 4. 场景状态结构

```python
SceneState = {
    "location": str,                    # 当前位置（当前所在 receptacle 的 short_name）
    "holding": Optional[str],           # 当前手持物体（None 表示空手）
    "receptacle_states": {              # 各容器的状态
        "fridge_1": {
            "open": bool,               # 是否打开
            "toggled_on": bool,         # 是否通电/开启
            "contains": [str],          # 内部物体列表
        },
        ...
    },
    "object_properties": {              # 物体属性
        "apple_1": {
            "cleaned": bool,
            "heated": bool,
            "cooled": bool,
            "sliced": bool,
        },
        ...
    },
    "steps_taken": int,                 # 已执行步数
    "task_type": str,                   # 当前任务类型
    "task_desc": str,                   # 任务描述
}
```

---

## 5. YLYW 状态六爻的构建规则

场景状态的六爻表征 = 融合如下信息的六爻向量：

```
位置爻     : 当前所在位置 → 对应乾卦的某一变爻
持有爻     : 是否有物体在手 → 艮卦的变爻
进度爻     : 任务完成进度 → 坎卦的变爻
环境爻     : 关键容器状态(冰箱门/灶台开关等) → 离卦的变爻
目标爻     : 当前子目标 → 兑卦的变爻
记忆爻     : 近期动作历史摘要 → 巽卦的变爻
```

**示例（做菜的中间步骤）:**

假设当前状态：手持苹果，已清洗，冰箱门开着，位于冰箱前

```
位置爻 = 001 (冰箱)
持有爻 = 100 (手持苹果)
进度爻 = 010 (已清洗，需加热)
环境爻 = 011 (冰箱门开)
目标爻 = 101 (待加热)
记忆爻 = 110 (刚完成清洗)

合成六爻 = 001 100 010 011 101 110
         = ☰ ☶ ☵ ☲ ☱ ☴
         = ䷘ (无妄卦 — 行动合理，但需谨慎)
```

---

## 6. 与 YLYW 引擎的接口

```python
class ActionPrimitiveAdapter:
    """YLYW 六爻推理 ↔ ALFWorld admissible actions 的适配器"""
    
    def __init__(self, primitives: dict = ACTION_PRIMITIVES):
        self.primitives = primitives
    
    def ylyw_decision_to_action(self, gua_vector: str, 
                                scene_state: SceneState,
                                admissible_cmds: List[str]) -> str:
        """
        将 YLYW 推理出的卦象向量转换为 ALFWorld admissible action。
        
        Args:
            gua_vector: YLYW 推理输出的六爻向量 (如 "111111")
            scene_state: 当前场景状态
            admissible_cmds: ALFWorld 环境返回的可用命令列表
        
        Returns:
            选中的 admissible command 字符串
        """
        # 1. 卦象 → 动作类型匹配
        action_type = self._match_gua_to_action(gua_vector)
        
        # 2. 动作类型 → 参数填充
        template = self.primitives[action_type]["alfworld_template"]
        params = self._extract_params(action_type, scene_state)
        candidate = template.format(**params)
        
        # 3. 校验是否在 admissible 列表中
        if candidate in admissible_cmds:
            return candidate
        
        # 4. 如果不在，做模糊匹配（参数号不同等）
        return self._fuzzy_match(candidate, admissible_cmds)
    
    def _match_gua_to_action(self, gua: str) -> str:
        """六爻到动作类型的最优匹配（支持变爻）"""
        best_match = None
        best_score = -1
        for action, defn in self.primitives.items():
            score = self._gua_similarity(gua, defn["gua"])
            if score > best_score:
                best_score = score
                best_match = action
            # 也检查 gua_after（变换后状态）
            if "gua_after" in defn:
                score2 = self._gua_similarity(gua, defn["gua_after"])
                if score2 > best_score:
                    best_score = score2
                    best_match = action
        return best_match
    
    def _gua_similarity(self, g1: str, g2: str) -> float:
        """六爻相似度：相同位置相同爻的比例"""
        if len(g1) != len(g2):
            return 0.0
        matches = sum(1 for a, b in zip(g1, g2) if a == b)
        return matches / len(g1)
```

---

## 7. 后续扩展

- **新环境接入**: 更换动作映射表（如真实机器人 API）
- **动作组合**: 某些高级任务需要动作序列，可以从状态六爻直接推理出动作序列的卦象链
- **参数学习**: 场景中的物体/容器名称可通过语义相似度自动映射，不需手工指定
