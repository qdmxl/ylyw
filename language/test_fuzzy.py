#!/usr/bin/env python3
"""
六爻决策 — 模糊推理版

核心设计：
  每条规则是一个模糊谓词的组合，输出一个[0,1]的激活度。
  所有规则并行计算，激活度最高的规则决定动作类型。
  规则本身是"软"的——不是if-else，而是隶属度函数。
  
  每个爻值本身就是隶属度，不需要额外映射。
  规则只描述"某个动作的理想六爻模式"，
  当前六爻与哪个模式最匹配，就执行哪个动作。
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ============================================================
# 模糊规则定义
# ============================================================
# 每条规则包含：
#   name: 动作名称
#   match: 对6个爻位的"期望隶属度分布"
#          None = 不关心该爻位
#          函数 = 该爻值越符合期望，值越高(0~1)
#   desc: 描述

def tri(x, center, width):
    """三角隶属度函数：在center处为1，±width处降为0"""
    if x < center - width or x > center + width:
        return 0.0
    return 1.0 - abs(x - center) / width

def gauss(x, center, sigma):
    """高斯隶属度函数"""
    return math.exp(-((x - center) ** 2) / (2 * sigma ** 2))

def left_shoulder(x, edge, slope=0.15):
    """左肩形：x <= edge-slope时=1, x >= edge+slope时=0"""
    if x <= edge - slope: return 1.0
    if x >= edge + slope: return 0.0
    return 1.0 - (x - (edge - slope)) / (2 * slope)

def right_shoulder(x, edge, slope=0.15):
    """右肩形：x >= edge+slope时=1, x <= edge-slope时=0"""
    if x >= edge + slope: return 1.0
    if x <= edge - slope: return 0.0
    return (x - (edge - slope)) / (2 * slope)

# 简化隶属度——直接用爻值本身
# 初爻高=有物, 二爻高=到位, 四爻高=已处理, 五爻高=接近目标

RULES = [
    # 规则1: 空手探索 — 初爻低, 二爻低
    {
        "name": "goto",
        "desc": "空手且不在目标位置→探索",
        "match": lambda y: left_shoulder(y[0], 0.35) * left_shoulder(y[1], 0.40),
    },
    # 规则2: 拿取 — 空手, 到位, 未处理
    {
        "name": "take",
        "desc": "空手到位但物体未处理→拿取",
        "match": lambda y: left_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.35) * left_shoulder(y[3], 0.40),
    },
    # 规则3: 取出 — 空手, 到位, 已处理
    {
        "name": "take_out",
        "desc": "空手到位且已处理好→取出",
        "match": lambda y: left_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.35) * right_shoulder(y[3], 0.45),
    },
    # 规则4: 去预处理位置 — 有物, 未处理, 未到位
    {
        "name": "goto_preproc",
        "desc": "有物体未处理但没到设备旁→去预处理",
        "match": lambda y: right_shoulder(y[0], 0.35) * left_shoulder(y[3], 0.40) * left_shoulder(y[1], 0.45),
    },
    # 规则5: 放入设备 — 有物, 未处理, 已到位
    {
        "name": "put_in",
        "desc": "有物到位且未处理→放入设备",
        "match": lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.45) * left_shoulder(y[3], 0.40),
    },
    # 规则6: 执行处理 — 空手, 到位, 未处理, 低目标
    {
        "name": "process",
        "desc": "已放入设备但未处理→执行处理",
        "match": lambda y: left_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.40) * left_shoulder(y[3], 0.40) * left_shoulder(y[4], 0.30),
    },
    # 规则7: 去目标位置 — 有物, 已处理, 未到位
    {
        "name": "goto_target",
        "desc": "有已处理的物体但没到目标位置→去目标",
        "match": lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * left_shoulder(y[1], 0.50),
    },
    # 规则8: 放置 — 有物, 已处理, 已到位, 目标接近
    {
        "name": "put",
        "desc": "有已处理的物体且已到目标位置→放置",
        "match": lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * right_shoulder(y[1], 0.50) * right_shoulder(y[4], 0.40),
    },
    # 兜底规则：什么都不匹配时用的
    {
        "name": "goto",
        "desc": "兜底→探索",
        "match": lambda y: 0.15,
    },
]


def fuzzy_decide(yao):
    """
    模糊决策：所有规则并行计算激活度，取最高。
    
    输入：6维爻向量 [y0, y1, y2, y3, y4, y5]
    输出：(action_type, activation, reason)
    """
    best_action = "goto"
    best_activation = 0.0
    best_desc = "兜底"
    
    for rule in RULES:
        activation = rule["match"](yao)
        if activation > best_activation:
            best_activation = activation
            best_action = rule["name"]
            best_desc = rule["desc"]
    
    # 激活度太低(<0.3)说明状态模糊，用兜底
    if best_activation < 0.3 and best_action != "goto":
        return ("goto", best_activation, f"模糊({best_activation:.2f})→兜底探索")
    
    return (best_action, best_activation, best_desc)


def build_yao(location, inventory, processed, step, preproc_loc, target_loc):
    """
    状态六爻构造。
    
    关键：每爻的值连续变化，不是跳变。
    初爻(持有)   0.1空手 → 有物时0.6~0.8
    二爻(位置)   连续值映射 0.1~0.9
    三爻(进程)   逐轮递增 0.1~0.85
    四爻(状态)   0.1未处理 → 0.7已处理 → 0.85已取出
    五爻(目标)   0.15~0.85 反映离最终目标多远
    上爻(环境)   位置越接近目标越高 0.3~0.8
    """
    # 初爻：持有状态（连续渐变）
    if inventory:
        if "脏" in inventory or processed == False:
            y0 = 0.40  # 刚拿到的脏物
        elif "干净" in inventory or processed:
            y0 = 0.65  # 已处理好的
        else:
            y0 = 0.55
    else:
        y0 = 0.10  # 空手
    
    # 二爻：位置估值
    loc_map = {"起点": 0.10}
    if preproc_loc:
        loc_map[preproc_loc] = 0.55
    if target_loc:
        loc_map[target_loc] = 0.80
    for k in ["柜子", "桌子", "架子", "抽屉"]:
        if k not in loc_map:
            loc_map[k] = 0.30
    y1 = loc_map.get(location, 0.25)
    
    # 三爻：进度（连续递增）
    y2 = min(0.10 + step * 0.09, 0.85)
    
    # 四爻：物体处理状态
    if processed and location == preproc_loc and not inventory:
        y3 = 0.70  # 已处理好但还在设备里
    elif processed and inventory:
        y3 = 0.85  # 已处理且取出来了
    elif processed:
        y3 = 0.60  # 已处理
    elif not inventory and location == preproc_loc:
        y3 = 0.25  # 放入设备了但还没处理
    else:
        y3 = 0.10  # 未处理
    
    # 五爻：目标接近度
    if location == target_loc and inventory:
        y4 = 0.85  # 到位+有物→可放置
    elif location == target_loc:
        y4 = 0.35  # 到位但无物
    elif location == preproc_loc and not inventory and processed:
        y4 = 0.65  # 已处理好待取出
    elif location == preproc_loc and not inventory and not processed:
        y4 = 0.30  # 在预处理位置但没处理
    elif location == preproc_loc and inventory:
        y4 = 0.15  # 刚拿东西到预处理位置
    else:
        y4 = 0.15  # 探索阶段
    
    # 上爻：环境就绪度
    if location in (preproc_loc, target_loc):
        y5 = 0.75
    elif location == "起点":
        y5 = 0.25
    else:
        y5 = 0.45
    
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


def format_yao(yao):
    return "  ".join(
        f"{n}={yao[i]:.2f}{'━' if yao[i]>=0.5 else '┅'}"
        for i, n in enumerate(["初","二","三","四","五","上"])
    )


# ============================================================
# 仿真环境
# ============================================================

def get_actions(loc, inv, processed, preproc_loc, target_loc):
    acts = []
    if loc == "起点":
        acts = [f"去{target_loc}", f"去{preproc_loc}"]
    elif loc == "柜子":
        if not inv:
            acts = ["拿起脏盘子"]
        # 目标位置也是柜子的特殊情况
        if target_loc == "柜子":
            if inv:
                acts = [f"把东西放到{target_loc}上"]
                acts += [f"去{preproc_loc}"]
                return acts
            acts += [f"去{preproc_loc}"]
            return acts
        acts += [f"去{preproc_loc}", f"去{target_loc}"]
    elif loc == preproc_loc:
        if inv:
            acts = [f"把东西放进{preproc_loc}", f"去{target_loc}"]
        else:
            if processed:
                acts = [f"把东西从{preproc_loc}拿出来"]
            else:
                acts = [f"处理东西"]
            acts += [f"去{target_loc}"]
    elif loc == target_loc:
        if inv:
            acts = [f"把东西放到{target_loc}上"]
        acts += [f"去{preproc_loc}"]
    return acts


def apply(action, loc, inv, processed, preproc_loc, target_loc, action_word, done_word):
    if "拿起" in action and not inv:
        return "柜子", "脏盘子", f"你拿起了脏盘子", False
    elif f"放进{preproc_loc}" in action:
        return preproc_loc, "", f"你把它放进了{preproc_loc}", False
    elif "处理" in action and "从" not in action and "放进" not in action:
        return preproc_loc, "", f"你{done_word}了它", True
    elif "拿出来" in action:
        return preproc_loc, "干净东西", f"你从{preproc_loc}拿出了它", True
    elif f"放到{target_loc}" in action:
        return target_loc, "", f"任务完成！", True
    elif f"去{target_loc}" in action:
        if loc == target_loc:
            return loc, inv, f"你已经在{target_loc}旁了", processed
        return target_loc, inv, f"你走到{target_loc}旁", processed
    elif f"去{preproc_loc}" in action:
        if loc == preproc_loc:
            return loc, inv, f"你已经在{preproc_loc}旁了", processed
        return preproc_loc, inv, f"你走到{preproc_loc}旁", processed
    return loc, inv, "没变化", processed


# ============================================================
# 测试
# ============================================================

TASKS = [
    {
        "name": "清洗后放置",
        "cn": "把盘子洗干净后放到柜台上",
        "preproc_loc": "水槽",
        "action_word": "清洗",
        "done_word": "洗净",
        "target_loc": "柜台",
    },
    {
        "name": "冷却后放置",
        "cn": "把杯子冷却后放到柜子里",
        "preproc_loc": "冰箱",
        "action_word": "冷却",
        "done_word": "冷却",
        "target_loc": "柜子",
    },
]

for task in TASKS:
    print(f"{'='*65}")
    print(f"  {task['name']}: {task['cn']}")
    print(f"  预处理={task['preproc_loc']}, 目标={task['target_loc']}")
    print(f"{'='*65}")
    print()
    
    loc = "起点"
    inv = ""
    fb = ""
    processed = False
    actions = []
    prev_yao = None
    
    for step in range(12):
        yao = build_yao(loc, inv, processed, step, task['preproc_loc'], task['target_loc'])
        action_type, activation, reason = fuzzy_decide(yao)
        
        # 动作映射
        available = get_actions(loc, inv, processed, task['preproc_loc'], task['target_loc'])
        action = None
        mapping = {
            "goto": available,
            "take": [a for a in available if "拿起" in a],
            "goto_preproc": [a for a in available if f"去{task['preproc_loc']}" in a],
            "put_in": [a for a in available if "放进" in a or (f"去{task['preproc_loc']}" in a and inv)],
            "process": [a for a in available if "处理" in a and "拿" not in a and "放" not in a],
            "take_out": [a for a in available if "拿出来" in a],
            "goto_target": [a for a in available if f"去{task['target_loc']}" in a and "放" not in a],
            "put": [a for a in available if "放到" in a and task['target_loc'] in a],
        }
        candidates = mapping.get(action_type, [])
        # 如果精确匹配不到，再放宽
        if not candidates and action_type == "put":
            candidates = [a for a in available if "放到" in a]
        if not candidates and action_type == "goto":
            # 探索阶段先去可能有物体的位置
            candidates = [a for a in available if "柜子" in a or "台" in a] or available
        if not candidates:
            candidates = available
        action = candidates[0] if candidates else None
        
        if not action:
            break
        
        # 输出
        yao_str = format_yao(yao)
        rules_detail = []
        for rule in RULES[:8]:
            act = rule["match"](yao)
            if act > 0.05:
                rules_detail.append(f"{rule['name']}={act:.2f}")
        rules_str = "  ".join(rules_detail)
        
        changes = ""
        if prev_yao:
            diffs = []
            for i in range(6):
                d = yao[i] - prev_yao[i]
                if abs(d) > 0.05:
                    diffs.append(f"{['初','二','三','四','五','上'][i]}{'+' if d>0 else ''}{d:.2f}")
            if diffs:
                changes = " | ".join(diffs)
        
        print(f"  Step{step+1:2d} | {yao_str}")
        if changes:
            print(f"       爻变: {changes}")
        print(f"       规则: {rules_str}")
        print(f"       决策: {action_type}(激活={activation:.3f}) ← {reason}")
        print(f"       → {action}")
        
        loc, inv, fb, processed = apply(action, loc, inv, processed, task['preproc_loc'], task['target_loc'], task['action_word'], task['done_word'])
        actions.append(action)
        prev_yao = yao
        
        if "完成" in fb:
            print(f"       ✅ {fb}")
            print(f"\n  ✅ 任务成功！\n")
            break
        print(f"       {fb}")
        print()
    
    print(f"  动作序列 ({len(actions)}步):")
    for i, a in enumerate(actions):
        print(f"    {i+1:2d}. {a}")
    print()
