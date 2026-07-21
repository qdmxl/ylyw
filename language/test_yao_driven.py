#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 六爻驱动逐步决策

核心：每轮用 engine.sentence() 输出当前状态的六爻向量，
根据六爻的阴阳分布和数值变化，决定当前优先级最高的动作。

六爻语义（语言域）：
  初爻(根基): 手上是否有物品？阴=空手, 阳=有物
  二爻(位置): 是否在目标位置？低=探索中, 高=到位  
  三爻(难度): 任务复杂度感知
  四爻(状态): 物体状态？阴=待处理(脏/冷/生), 阳=已处理(干净/热/熟)
  五爻(重要度): 离完成还有多远？低=前期, 高=收尾
  上爻(环境): 环境是否就绪？阴=需准备, 阳=就绪

动作决策规则（基于六爻状态机）：
  初爻阴(空手) ∩ 四爻阴(待处理) → goto/take 探索拿物
  初爻阳(有物) ∩ 二爻低(未到位) → goto 移动到处理位置
  初爻阳(有物) ∩ 二爻高(已到位) → put/clean/heat/cool 执行处理
  初爻阴(已放下) ∩ 四爻阴(待处理) → clean/heat/cool 处理中
  初爻阴(已放下) ∩ 四爻阳(已处理) → take 取出
  初爻阳(有物) ∩ 五爻高(收尾) → goto 去目标位置
  初爻阳(有物) ∩ 上爻阳(就绪) → put 放置
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."
SCENE = "厨房。有水槽、柜台、柜子、冰箱。水槽边有一个脏盘子。"

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 六爻动作决策表
# ============================================================
# 每个规则：(初爻, 二爻, 三爻, 四爻, 五爻, 上爻) → 动作类型
# None = 不关心该爻值

YAO_RULES = [
    # --- 探索/拿物阶段 ---
    # 空手 ∩ 待处理 → 探索/拿取
    {
        "cond": {"yao0": (0, 0.4), "yao3": (0, 0.4)},  # 初爻阴(空手), 四爻阴(待处理)
        "action": "goto",
        "desc": "空手且物体待处理 → 先去探索找到物体"
    },
    # 空手 ∩ 可拿 → 拿取
    {
        "cond": {"yao0": (0, 0.4), "yao1": (0.5, 1.0)},  # 初爻阴, 二爻阳(到位)
        "action": "take",
        "desc": "空手且已到位 → 拿取物体"
    },
    
    # --- 预处理阶段 ---
    # 有物 ∩ 未到位 → 移动到处理位置
    {
        "cond": {"yao0": (0.5, 1.0), "yao1": (0, 0.4)},  # 初爻阳(有物), 二爻阴(未到位)
        "action": "goto_preproc",
        "desc": "拿着物体但还没到处理位置 → 移动到水槽/微波炉/冰箱"
    },
    # 有物 ∩ 到位 → 放入处理
    {
        "cond": {"yao0": (0.5, 1.0), "yao1": (0.5, 1.0), "yao3": (0, 0.4)},  # 有物, 到位, 待处理
        "action": "put_in",
        "desc": "有物体且已到位且待处理 → 把物体放进去"
    },
    
    # --- 执行处理 ---
    # 已放入 ∩ 待处理 → 执行处理
    {
        "cond": {"yao0": (0, 0.4), "yao3": (0, 0.4), "yao1": (0.5, 1.0)},  # 空手, 待处理, 到位
        "action": "process",
        "desc": "物体已放入且待处理 → 执行清洗/加热/冷却"
    },
    # 已放入 ∩ 处理中(三爻高=难度大)
    {
        "cond": {"yao0": (0, 0.4), "yao2": (0.5, 1.0)},  # 空手, 三爻阳(处理中)
        "action": "process",
        "desc": "处理中 → 继续处理"
    },
    
    # --- 取出阶段 ---
    # 已处理好 ∩ 到位
    {
        "cond": {"yao0": (0, 0.4), "yao3": (0.5, 1.0)},  # 空手, 四爻阳(已处理)
        "action": "take_out",
        "desc": "已处理好 → 取出物体"
    },
    
    # --- 放置阶段 ---
    # 有物 ∩ 未到目标位置
    {
        "cond": {"yao0": (0.5, 1.0), "yao4": (0, 0.4)},  # 有物, 五爻阴(未收尾)
        "action": "goto_target",
        "desc": "拿着已处理的物体 → 走到目标位置"
    },
    # 有物 ∩ 已到目标位置 ∩ 环境就绪
    {
        "cond": {"yao0": (0.5, 1.0), "yao4": (0.5, 1.0)},  # 有物, 五爻阳(收尾)
        "action": "put",
        "desc": "已到目标位置 → 放置物体"
    },
    
    # --- 兜底 ---
    {
        "cond": {"yao4": (0.5, 1.0)},  # 五爻高 → 快完成了
        "action": "goto_target",
        "desc": "接近完成 → 去目标位置或放置"
    },
]


def yao_to_action(yao_vector, bagua, main_hex):
    """
    核心：根据六爻向量 → 选择动作类型。
    
    六爻向量是6维[0,1]值，>=0.5为阳，<0.5为阴。
    每条规则检查特定爻位的阴阳状态，匹配则返回对应动作。
    
    此外，还利用归卦做二次校验。
    """
    # 爻值提取
    y = yao_vector
    if len(y) > 6:
        # 64维时取前6个最大值作为六爻
        sorted_vals = sorted(y, reverse=True)[:6]
        y = sorted_vals
    
    # 构建爻位字典
    yao = {}
    for i in range(min(6, len(y))):
        yao[f"yao{i}"] = y[i]
    
    # 匹配规则
    for rule in YAO_RULES:
        match = True
        for key, (lo, hi) in rule["cond"].items():
            val = yao.get(key, 0.5)
            if val < lo or val > hi:
                match = False
                break
        if match:
            return rule["action"], rule["desc"]
    
    # 兜底：用归卦
    hex_to_action = {
        "乾": "goto", "兑": "process", "离": "process",
        "震": "goto", "巽": "put", "坎": "process",
        "艮": "stop", "坤": "put",
    }
    bagua_idx = BAGUA_NAMES.index(bagua) if bagua in BAGUA_NAMES else -1
    fallback = hex_to_action.get(bagua, "goto")
    return fallback, f"归卦{bagua}兜底"


# 64卦→八卦映射（完整64个）
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


def build_state(step, inventory, location, feedback):
    """构建当前状态描述"""
    loc_brief = {
        "起点": "你在房间中间，四周有柜子、水槽、柜台。",
        "柜子": "你站在柜子旁边。柜子上有一个脏盘子。",
        "水槽": "你站在水槽旁边。",
        "柜台": "你站在柜台旁边。",
    }.get(location, f"你在{location}旁。")
    
    inv_brief = f"你手上拿着{inventory}。" if inventory else "你手上没有东西。"
    
    if feedback:
        return f"任务：{TASK_CN}。刚才：{feedback}。{loc_brief}{inv_brief}现在该做什么？"
    else:
        return f"任务：{TASK_CN}。{loc_brief}{inv_brief}现在该做什么？"


def describe_yao(yao_vector):
    """六爻可视化"""
    y = yao_vector[:6] if len(yao_vector) >= 6 else yao_vector + [0.5]*(6-len(yao_vector))
    labels = ["初(根基)","二(位置)","三(难度)","四(状态)","五(重要)","上(环境)"]
    lines = []
    for i in range(6):
        symbol = "━" if y[i] >= 0.5 else "┅"
        lines.append(f"  {labels[i]}={y[i]:.3f} {symbol}")
    return "\n".join(lines)


# ============================================================
# 模拟环境
# ============================================================

def get_actions(loc, inv):
    """基于当前位置和物品返回可选动作"""
    actions = []
    if loc == "起点":
        actions = ["去柜子", "去水槽", "去柜台"]
    elif loc == "柜子":
        actions = ["拿起脏盘子"] if not inv else []
        actions += ["去水槽", "去柜台"]
    elif loc == "水槽":
        if inv:
            actions = ["把盘子放进水槽", "去柜台", "去柜子"]
        else:
            actions = ["清洗盘子", "把盘子从水槽拿出来", "去柜台", "去柜子"]
    elif loc == "柜台":
        if inv:
            actions = ["把盘子放到柜台上"]
        actions += ["去水槽", "去柜子"]
    return actions


def apply(action, loc, inv):
    """执行动作，返回新状态"""
    if "拿起" in action:
        return "柜子", "脏盘子", "你拿起了脏盘子"
    elif "放进水槽" in action:
        return "水槽", "", "你把脏盘子放进了水槽"
    elif "清洗" in action and "从" not in action:
        return "水槽", "", "你把盘子洗干净了"
    elif "拿出来" in action:
        return "水槽", "干净盘子", "你从水槽拿出了干净盘子"
    elif "放到柜台" in action:
        return "柜台", "", "任务完成！你把干净盘子放到了柜台上"
    elif "去柜子" in action:
        return "柜子", inv, "你走到柜子旁"
    elif "去水槽" in action:
        return "水槽", inv, "你走到水槽旁"
    elif "去柜台" in action:
        return "柜台", inv, "你走到柜台旁"
    return loc, inv, "没变化"


# ============================================================
# 主循环
# ============================================================

print("=" * 70)
print("  六爻驱动逐步决策 — 递归YLYW汉语理解引擎")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 70)
print()

location = "起点"
inventory = ""
feedback = ""
all_actions = []
prev_yao = None

for step in range(15):
    print(f"─── 第 {step+1} 步 ───")
    
    # 状态描述
    state = build_state(step, inventory, location, feedback)
    print(f"  📋 状态: {state}")
    
    # YLYW理解
    result = engine.sentence(state)
    yao_vector = result["yao_vector"]
    main_hex = result["main_hexagram"]
    hex_score = result["hexagram_score"]
    bagua = result["dominant_bagua"]
    
    # 归卦
    gui_gua = HEX_TO_BAGUA.get(main_hex, bagua)
    
    # 六爻变化检测
    yao_change = ""
    if prev_yao is not None:
        changes = []
        for i in range(min(6, len(yao_vector), len(prev_yao))):
            diff = abs(yao_vector[i] - prev_yao[i])
            if diff > 0.05:
                symbol = "阳变阴↓" if yao_vector[i] < 0.5 and prev_yao[i] >= 0.5 else \
                         "阴变阳↑" if yao_vector[i] >= 0.5 and prev_yao[i] < 0.5 else \
                         f"浮动{diff:.3f}"
                yao_labels = ["初","二","三","四","五","上"]
                changes.append(f"{yao_labels[i]}爻{symbol}")
        if changes:
            yao_change = " | ".join(changes)
    
    prev_yao = yao_vector[:6].copy() if len(yao_vector) >= 6 else yao_vector.copy()
    
    # 六爻驱动决策
    action_type, reason = yao_to_action(yao_vector, bagua, main_hex)
    
    # 可选动作
    available = get_actions(location, inventory)
    
    # 动作类型 → 具体动作
    action = None
    if action_type == "goto":
        # 去可能有目标物体的位置
        for a in available:
            if "柜子" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "take":
        for a in available:
            if "拿起" in a or "拿" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "goto_preproc":
        for a in available:
            if "水槽" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "put_in":
        for a in available:
            if "放进" in a or "放入" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "process":
        for a in available:
            if "清洗" in a or "洗" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "take_out":
        for a in available:
            if "拿出来" in a or "取出" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "goto_target":
        for a in available:
            if "柜台" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "put":
        for a in available:
            if "放到" in a or "放回" in a: action = a; break
        if not action and available: action = available[0]
    
    if not action and available:
        action = available[0]
    if not action:
        action = "等待"
    
    # 输出
    print(f"  🔮 主卦:{main_hex}({hex_score:.3f})→归卦:{gui_gua}  主导八卦:{bagua}")
    print(f"  📊 六爻:")
    print(describe_yao(yao_vector))
    if yao_change:
        print(f"  🔄 爻变: {yao_change}")
    print(f"  🎯 决策: {action_type} ← {reason}")
    print(f"  🤖 动作: {action}")
    
    # 执行
    location, inventory, feedback = apply(action, location, inventory)
    all_actions.append(action)
    print(f"  📌 结果: {feedback.split('。')[0]}")
    print(f"     位置={location} 物品={inventory or '空'}")
    
    if "完成" in feedback:
        print(f"\n  ✅ 任务成功完成！")
        break
    
    print()

print(f"\n{'='*70}")
print(f"  动作序列 ({len(all_actions)}步):")
for i, a in enumerate(all_actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*70}")
