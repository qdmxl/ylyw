#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 卦象驱动逐步决策

核心思想：
  每轮给引擎当前状态描述，引擎输出卦象。
  卦象本身就是"当前优先级"——不同卦对应不同动作类型。
  从可选动作中选出与卦象语义最匹配的。

  卦→动作优先级映射（基于易经本义）：
    乾(天/健/动)    → take/拿取
    兑(泽/悦/毁)    → clean/清洗, open/打开  
    离(火/明/热)    → heat/加热, examine/查看
    震(雷/动/起)    → go to/移动, take/拿取
    巽(风/入/散)    → put/放置, move/移动
    坎(水/险/寒)    → cool/冷却, clean/清洗
    艮(山/止/闭)    → close/关闭, stop/停止
    坤(地/顺/载)    → put/放置, 承载
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."
SCENE = "厨房。有水槽、柜台、柜子、冰箱。水槽边有一个脏盘子。"

# ══════════════════════════════════════════════
# 卦象 → 动作优先级映射
# ══════════════════════════════════════════════

BAGUA_ACTION_PRIORITY = {
    # 八卦：每个卦对应的动作类型（按优先级从高到低）
    "乾": ["take", "goto", "open"],          # 天/健 → 行动、拿取
    "兑": ["clean", "open", "examine"],       # 泽/悦 → 清洗、开启
    "离": ["heat", "examine", "turn_on"],     # 火/明 → 加热、查看
    "震": ["goto", "take", "move"],           # 雷/动 → 移动、拿取
    "巽": ["put", "move", "goto"],            # 风/入 → 放置、移动
    "坎": ["cool", "clean", "goto"],          # 水/寒 → 冷却、清洗
    "艮": ["close", "stop", "goto"],          # 山/止 → 关闭、停止
    "坤": ["put", "close", "goto"],           # 地/载 → 放置、承载
}

# 六十四卦到八卦的归卦映射
HEX_TO_BAGUA = {
    "乾为天":"乾","坤为地":"坤","水雷屯":"坎","山水蒙":"艮",
    "水天需":"坎","天水讼":"乾","地水师":"坤","水地比":"坎",
    "风天小畜":"巽","天泽履":"乾","地天泰":"坤","天地否":"乾",
    "天火同人":"乾","火天大有":"离","地山谦":"坤","雷地豫":"震",
    "泽雷随":"兑","山风蛊":"艮","地临":"坤","风地观":"巽",
    "火雷噬嗑":"离","山火贲":"艮","山地剥":"艮","地雷复":"坤",
    "天雷无妄":"乾","山天大畜":"艮","山雷颐":"艮","泽风大过":"兑",
    "坎为水":"坎","离为火":"离","泽山咸":"兑","雷风恒":"震",
    "天山遁":"乾","雷天大壮":"震","火地晋":"离","地火明夷":"坤",
    "风火家人":"巽","火泽睽":"离","水山蹇":"坎","雷水解":"震",
    "山泽损":"艮","风雷益":"巽","泽天夬":"兑","天风姤":"乾",
    "泽地萃":"兑","地风升":"坤","泽水困":"兑","水风井":"坎",
    "泽火革":"兑","火风鼎":"离","震为雷":"震","艮为山":"艮",
    "风山渐":"巽","雷泽归妹":"震","雷火丰":"震","火山旅":"离",
    "巽为风":"巽","兑为泽":"兑","风水涣":"巽","水泽节":"坎",
    "风泽中孚":"巽","雷山小过":"震","水火既济":"坎","火水未济":"离",
}

# ══════════════════════════════════════════════
# 状态描述
# ══════════════════════════════════════════════

def build_state(step, inventory, location, feedback):
    """
    构建当前状态描述。
    长度控制在50字以内，避免分词被无关信息干扰。
    """
    parts = [f"任务：{TASK_CN}"]
    
    if feedback:
        parts.append(f"刚才：{feedback}")
    
    loc_brief = {
        "起点": "你在房间中间。",
        "柜子": "你在柜子旁。",
        "水槽": "你在水槽旁。",
        "柜台": "你在柜台旁。",
    }.get(location, f"你在{location}。")
    parts.append(loc_brief)
    
    if inventory:
        parts.append(f"手上有{inventory}。")
    else:
        parts.append("手上没东西。")
    
    parts.append("下一步做什么？")
    
    return " ".join(parts)


# ══════════════════════════════════════════════
# 核心：卦象 → 动作选择
# ══════════════════════════════════════════════

def choose_action_by_bagua(result, available_actions):
    """
    根据句级主卦的归卦，决定从available_actions中选哪个。
    
    输入：
      result: engine.sentence()的输出
      available_actions: 当前可做的动作列表
    
    决策：
      1. 主卦 → 归到八卦（如"泽风大过"→兑）
      2. 八卦 → 优先级动作类型列表
      3. 从available_actions中匹配最优先的动作类型
    """
    main_hex = result["main_hexagram"]
    dom_bagua = result["dominant_bagua"]
    
    # 归卦（优先用64→8映射，兜底用dominant_bagua）
    bagua = HEX_TO_BAGUA.get(main_hex, dom_bagua)
    
    # 获取该卦对应的动作优先级
    priorities = BAGUA_ACTION_PRIORITY.get(bagua, ["goto", "take", "put"])
    
    # 从available_actions中按优先级匹配
    action_type_map = {
        "take": ["拿", "take", "取"],
        "put": ["放", "put", "放回", "放入"],
        "clean": ["洗", "clean", "清洗"],
        "heat": ["热", "heat", "加热"],
        "cool": ["冷", "cool", "冷却"],
        "goto": ["去", "go to", "走到", "到"],
        "open": ["打开", "open", "开"],
        "close": ["关闭", "close", "关"],
        "examine": ["看", "examine", "查看", "检查"],
        "turn_on": ["打开", "turn on", "开灯"],
        "move": ["移动", "move", "挪"],
    }
    
    # 按优先级遍历
    for prio_action in priorities:
        keywords = action_type_map.get(prio_action, [prio_action])
        for action in available_actions:
            for kw in keywords:
                if kw in action:
                    return action, prio_action, bagua
    
    # 兜底
    return available_actions[0] if available_actions else "等待指令", "unknown", bagua


# ══════════════════════════════════════════════
# 主循环
# ══════════════════════════════════════════════

print("=" * 65)
print(f"  卦象驱动逐步决策 — 递归YLYW汉语理解引擎")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 65)
print()

# 模拟环境：状态追踪
location = "起点"
inventory = ""
feedback = ""
all_actions = []

# 每轮可用的动作（模拟admissible commands）
def get_available_actions(loc, inv):
    """基于当前位置和物品情况，给出可选动作"""
    actions = []
    if loc == "起点":
        actions = ["去柜子", "去水槽", "去柜台", "去冰箱"]
    elif loc == "柜子":
        if not inv:
            actions = ["拿起盘子", "去水槽", "去柜台", "去冰箱"]
        else:
            actions = ["去水槽", "去柜台", "去冰箱"]
    elif loc == "水槽":
        if inv:
            actions = ["把盘子放进水槽", "去柜子", "去柜台", "去冰箱"]
        else:
            actions = ["清洗盘子", "把盘子拿出来", "去柜子", "去柜台"]
    elif loc == "柜台":
        if inv:
            actions = ["把盘子放到柜台上", "去水槽", "去柜子"]
        else:
            actions = ["去水槽", "去柜子", "去冰箱"]
    return actions

# 执行动作后的状态更新
def apply_action(action, loc, inv):
    """模拟动作执行后的状态变化"""
    if "拿起" in action:
        return loc, "盘子", "你拿起了盘子"
    elif "放进水槽" in action:
        return "水槽", "", "你把盘子放进水槽"
    elif "清洗" in action and "从" not in action:
        return "水槽", "", "你洗干净了盘子"
    elif "拿出来" in action or "拿出" in action:
        return "水槽", "干净的盘子", "你拿出了干净的盘子"
    elif "放到柜台" in action:
        return "柜台", "", "任务完成！"
    elif "去柜子" in action:
        return "柜子", inv, "你走到柜子旁"
    elif "去水槽" in action:
        return "水槽", inv, "你走到水槽旁"
    elif "去柜台" in action:
        return "柜台", inv, "你走到柜台旁"
    elif "去冰箱" in action:
        return "冰箱", inv, "你走到冰箱旁"
    return loc, inv, "没变化"


for step in range(12):
    print(f"─── 第 {step+1} 步 ───")
    
    # 当前状态描述
    state = build_state(step, inventory, location, feedback)
    print(f"  📋 状态: {state}")
    
    # YLYW理解
    result = engine.sentence(state)
    main_hex = result["main_hexagram"]
    dom_bagua = result["dominant_bagua"]
    hex_score = result["hexagram_score"]
    
    # 归卦
    bagua = HEX_TO_BAGUA.get(main_hex, dom_bagua)
    priorities = BAGUA_ACTION_PRIORITY.get(bagua, ["goto"])
    
    print(f"  🔮 主卦: {main_hex}({hex_score:.3f}) → 归卦: {bagua}")
    print(f"    卦→动作优先级: {' > '.join(priorities)}")
    
    # 分词（看引擎是否理解当前状态）
    segments = result["segments"]
    verbs = [segments[i] for i in range(len(segments)) if result['segment_role'][i] == '动作']
    objs = [segments[i] for i in range(len(segments)) if result['segment_role'][i] == '物体']
    print(f"  📝 分词动词={verbs[:3]} 物体={objs[:3]}")
    
    # 可选动作
    available = get_available_actions(location, inventory)
    print(f"  📋 可选: {available}")
    
    # 卦象选择动作
    action, action_type, chosen_bagua = choose_action_by_bagua(result, available)
    print(f"  🤖 卦{chosen_bagua}→{action_type}→动作: {action}")
    
    # 执行
    location, inventory, feedback = apply_action(action, location, inventory)
    all_actions.append(action)
    print(f"  📊 结果: {feedback}")
    print(f"    位置={location} 物品={inventory or '空'}")
    
    if "完成" in feedback:
        print(f"\n  ✅ 任务完成！")
        break
    
    print()

print(f"\n{'='*65}")
print(f"  最终动作序列 ({len(all_actions)}步):")
for i, a in enumerate(all_actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*65}")
