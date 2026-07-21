#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 六爻驱动逐步决策 v2

关键改进：去掉状态描述中的固定任务文本，只保留当前时刻的动态信息。
让六爻真正反映"状态变化"而非"一句话的静态语义"。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 状态描述构建（关键改进）
# ============================================================

def build_state(location, inventory, feedback, step=0):
    """
    构建"纯粹"的当前状态描述——只包含此时此刻的信息。
    
    不带"任务：xxx"这样的固定文本，因为那会污染六爻编码。
    状态描述应该只包含：
    - 当前位置（精简）
    - 手上有什么
    - 刚才发生了什么
    """
    # 位置描述（极精简，控制在10字以内）
    loc_map = {
        "起点": "房间中间",
        "柜子": "柜子旁",
        "水槽": "水槽旁",
        "柜台": "柜台旁",
    }
    loc_str = loc_map.get(location, location)
    
    # 物品描述
    inv_str = f"手拿{inventory}" if inventory else "空手"
    
    # 上一步反馈（精简）
    fb_map = {
        "": "",
        "你拿起了脏盘子": "刚拿了脏盘子",
        "你把脏盘子放进了水槽": "刚把盘子放入水槽",
        "你把盘子洗干净了": "盘子已洗净",
        "你从水槽拿出了干净盘子": "刚取出干净盘子",
        "你走到柜子旁": "到柜子",
        "你走到水槽旁": "到水槽",
        "你走到柜台旁": "到柜台",
    }
    fb = fb_map.get(feedback, feedback[:8] if feedback else "")
    
    # 拼接——极简短，不超过30字
    parts = [loc_str, inv_str]
    if fb:
        parts.append(fb)
    
    return "，".join(parts) + "。下一步？"


# ============================================================
# 六爻动作决策
# ============================================================

YAO_RULES = [
    # 空手 → 去最近的有物体位置
    {"cond": {"yao0": (0.0, 0.45)}, "action": "goto", "desc": "空手→探索"},
    # 空手且到位 → 拿取
    {"cond": {"yao0": (0.0, 0.45), "yao1": (0.50, 1.0)}, "action": "take", "desc": "空手到位→拿取"},
    # 有物且未到位处理位置 → 去预处理位置
    {"cond": {"yao0": (0.50, 1.0), "yao4": (0.0, 0.45)}, "action": "goto_preproc", "desc": "有物未处理→去水槽"},
    # 有物且到位 → 放入设备
    {"cond": {"yao0": (0.50, 1.0), "yao1": (0.50, 1.0), "yao4": (0.0, 0.45)}, "action": "put_in", "desc": "有物到位→放入"},
    # 空手且到位处理位置 → 执行处理
    {"cond": {"yao0": (0.0, 0.45), "yao1": (0.50, 1.0), "yao3": (0.0, 0.50)}, "action": "process", "desc": "空手到位→处理"},
    # 空手且已处理 → 取出
    {"cond": {"yao0": (0.0, 0.45), "yao3": (0.50, 1.0)}, "action": "take_out", "desc": "已处理→取出"},
    # 有物且到收尾 → 去目标位置
    {"cond": {"yao0": (0.50, 1.0), "yao4": (0.50, 1.0)}, "action": "goto_target", "desc": "有物收尾→去柜台"},
    # 有物且环境就绪 → 放置
    {"cond": {"yao0": (0.50, 1.0), "yao5": (0.50, 1.0)}, "action": "put", "desc": "就绪→放置"},
]


def yao_to_action(yao_vector, bagua):
    """根据六爻匹配动作规则"""
    y = yao_vector[:6] if len(yao_vector) >= 6 else yao_vector + [0.5]*(6-len(yao_vector))
    
    yao = {}
    for i in range(6):
        yao[f"yao{i}"] = y[i]
    
    for rule in YAO_RULES:
        match = True
        for key, (lo, hi) in rule["cond"].items():
            val = yao.get(key, 0.5)
            if val < lo or val > hi:
                match = False
                break
        if match:
            return rule["action"], rule["desc"]
    
    return "goto", f"归卦{bagua}"


# ============================================================
# 模拟环境
# ============================================================

def get_actions(loc, inv, processed=False):
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
            if processed:
                actions = ["把盘子从水槽拿出来"]
            else:
                actions = ["清洗盘子", "清洗盘子"]  # 两个清洗让规则能检出
            actions += ["去柜台", "去柜子"]
    elif loc == "柜台":
        if inv:
            actions = ["把盘子放到柜台上"]
        actions += ["去水槽", "去柜子"]
    return actions


def apply(action, loc, inv, processed):
    if "拿起" in action:
        return "柜子", "脏盘子", "你拿起了脏盘子", False
    elif "放进水槽" in action:
        return "水槽", "", "你把脏盘子放进了水槽", False
    elif "清洗" in action and "从" not in action and "放进" not in action:
        return "水槽", "", "你把盘子洗干净了", True
    elif "拿出来" in action:
        return "水槽", "干净盘子", "你从水槽拿出了干净盘子", True
    elif "放到柜台" in action:
        return "柜台", "", "任务完成！你把干净盘子放到了柜台上", True
    elif "去柜子" in action:
        return "柜子", inv, "你走到柜子旁", processed
    elif "去水槽" in action:
        return "水槽", inv, "你走到水槽旁", processed
    elif "去柜台" in action:
        return "柜台", inv, "你走到柜台旁", processed
    return loc, inv, "没变化", processed


# ============================================================
# 主循环
# ============================================================

print("=" * 65)
print("  六爻驱动逐步决策 v2")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 65)
print()

location = "起点"
inventory = ""
feedback = ""
processed = False
all_actions = []

for step in range(18):
    print(f"─── Step {step+1} ───")
    
    # 状态描述（精简版，无固定任务文本）
    state = build_state(location, inventory, feedback, step)
    print(f"  📋 状态: {state}")
    
    # YLYW理解
    result = engine.sentence(state)
    yao_vector = result["yao_vector"]
    main_hex = result["main_hexagram"]
    hex_score = result["hexagram_score"]
    bagua = result["dominant_bagua"]
    
    # 六爻输出
    y = yao_vector[:6] if len(yao_vector) >= 6 else yao_vector + [0.5]*(6-len(yao_vector))
    labels = ["初","二","三","四","五","上"]
    yao_str = " ".join(f"{labels[i]}={y[i]:.3f}{'━' if y[i]>=0.5 else '┅'}" for i in range(6))
    print(f"  🔮 主卦:{main_hex}({hex_score:.3f}) {yao_str}")
    
    # 六爻决策
    action_type, reason = yao_to_action(yao_vector, bagua)
    available = get_actions(location, inventory, processed)
    
    # 动作类型→具体动作
    action = None
    if action_type == "goto":
        for a in available:
            if "柜子" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "take":
        for a in available:
            if "拿起" in a: action = a; break
        if not action and available: action = available[0]
    elif action_type == "goto_preproc":
        for a in available:
            if "水槽" in a and "去" in a: action = a; break
        if not action and available: action = "去水槽"
    elif action_type == "put_in":
        for a in available:
            if "放进" in a: action = a; break
    elif action_type == "process":
        for a in available:
            if "清洗" in a: action = a; break
    elif action_type == "take_out":
        for a in available:
            if "拿出来" in a: action = a; break
    elif action_type == "goto_target":
        for a in available:
            if "柜台" in a: action = a; break
    elif action_type == "put":
        for a in available:
            if "放到" in a: action = a; break
    
    if not action and available:
        action = available[0]
    if not action:
        action = "等待"
    
    print(f"  🎯 决策:{action_type}({reason}) 可选:{available[:4]}")
    print(f"  🤖 动作: {action}")
    
    # 执行
    location, inventory, feedback, processed = apply(action, location, inventory, processed)
    all_actions.append(action)
    print(f"  📌 结果: {feedback.split('。')[0]}")
    
    if "完成" in feedback:
        print(f"\n  ✅ 任务完成！")
        break
    print()

print(f"\n{'='*65}")
print(f"  动作序列 ({len(all_actions)}步):")
for i, a in enumerate(all_actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*65}")
