#!/usr/bin/env python3
"""
六爻驱动逐步决策 — 冷却任务测试
测试相同的决策架构能否适配不同任务类型
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ============================================================
# 两个完全不同类型的任务
# ============================================================

TASKS = [
    {
        "name": "清洗后放置",
        "en": "Put a clean plate on the counter.",
        "cn": "把盘子洗干净后放到柜台上",
        "scene": "厨房。有水槽、柜台、柜子、冰箱。",
        "preproc_loc": "水槽",
        "preproc_action": "清洗",
        "preproc_done_word": "洗净",
        "target_loc": "柜台",
        # 预期路径
        "expected": ["探索→柜子", "拿→脏盘子", "goto→水槽", "放入→水槽", "处理→清洗", "取出→盘子", "goto→柜台", "放置→柜台"]
    },
    {
        "name": "冷却后放置",
        "en": "Put a chilled mug in the cabinet.",
        "cn": "把杯子冷却后放到柜子里",
        "scene": "厨房。有冰箱、柜子、柜台。",
        "preproc_loc": "冰箱",
        "preproc_action": "冷却",
        "preproc_done_word": "冷却了",
        "target_loc": "柜子",
        "expected": ["探索→柜子/冰箱", "拿→杯子", "goto→冰箱", "放入→冰箱", "处理→冷却", "取出→杯子", "goto→柜子", "放置→柜子"]
    },
]


def build_state_yao(location, inventory, processed, step, preproc_loc, target_loc):
    """
    六爻构造（与任务类型无关）
    初爻=持有状态  二爻=位置估值  三爻=进度  四爻=处理状态  五爻=目标距离  上爻=环境
    """
    y0 = 0.7 if inventory else 0.1
    
    # 位置估值：预处理位置0.6，目标位置0.85
    loc_map = {"起点": 0.1}
    if preproc_loc:
        loc_map[preproc_loc] = 0.6
    if target_loc:
        loc_map[target_loc] = 0.85
    # 其他位置中间值
    for k in ["柜子", "桌子", "架子", "抽屉"]:
        if k not in loc_map:
            loc_map[k] = 0.35
    
    y1 = loc_map.get(location, 0.3)
    y2 = min(0.1 + step * 0.1, 0.85)
    y3 = 0.8 if processed else 0.2
    
    # 五爻：目标接近度（和目标位置相关）
    if location == target_loc and inventory:
        y4 = 0.85
    elif location == target_loc:
        y4 = 0.4
    elif location == preproc_loc and processed and not inventory:
        y4 = 0.65
    elif location == preproc_loc and not inventory and not processed:
        y4 = 0.35
    elif location == preproc_loc and inventory:
        y4 = 0.2
    else:
        y4 = 0.15
    
    y5 = 0.8 if location in (preproc_loc, target_loc) else 0.3
    
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


def yaos_to_action(yao, prev_yao=None):
    """六爻→动作决策（与任务类型无关的通用规则）"""
    y0, y1, y2, y3, y4, y5 = yao
    
    changes = []
    if prev_yao:
        for i in range(6):
            diff = yao[i] - prev_yao[i]
            if abs(diff) > 0.1:
                direction = "↑" if diff > 0 else "↓"
                changes.append(f"{['初','二','三','四','五','上'][i]}爻{direction}{abs(diff):.2f}")
    
    # 通用决策规则（不依赖任何任务特定信息）
    # 空手 ∩ 未到位 → goto 探索
    if y0 < 0.4 and y1 < 0.5:
        return ("goto", "空手探索→找物体", changes)
    
    # 空手 ∩ 到位 ∩ 未处理 → take 拿取
    if y0 < 0.4 and y1 >= 0.4 and y3 < 0.4:
        return ("take", "已到位→拿取", changes)
    
    # 空手 ∩ 到位 ∩ 已处理 → take_out 取出
    if y0 < 0.4 and y1 >= 0.4 and y3 >= 0.5:
        return ("take_out", "已处理好→取出", changes)
    
    # 有物 ∩ 未处理 ∩ 未到位 → goto 预处理位置
    if y0 >= 0.4 and y3 < 0.4 and y1 < 0.5:
        return ("goto_preproc", "有物→去预处理位置", changes)
    
    # 有物 ∩ 未处理 ∩ 到位 → put_in 放入设备
    if y0 >= 0.4 and y3 < 0.4 and y1 >= 0.5:
        return ("put_in", "有物已到位→放入", changes)
    
    # 空手 ∩ 到位 ∩ 未处理 ∩ 低目标 → process 执行处理
    if y0 < 0.4 and y3 < 0.4 and y1 >= 0.4 and y4 < 0.4:
        return ("process", "已放入→执行处理", changes)
    
    # 有物 ∩ 已处理 ∩ 未到位 → goto_target 去目标位置
    if y0 >= 0.4 and y3 >= 0.5 and y4 < 0.5:
        return ("goto_target", "已处理→去目标位置", changes)
    
    # 有物 ∩ 已处理 ∩ 目标高位 → put 放置
    if y0 >= 0.4 and y3 >= 0.5 and y4 >= 0.5:
        return ("put", "就绪→放置", changes)
    
    return ("goto", "兜底", changes)


def format_yao(yao):
    """六爻可视化"""
    return "  ".join(
        f"{n}={'━' if yao[i]>=0.5 else '┅'}({yao[i]:.2f})"
        for i, n in enumerate(["初","二","三","四","五","上"])
    )


def run_task(task, max_steps=15):
    """运行单个任务的逐步决策"""
    name = task["name"]
    cn = task["cn"]
    en = task["en"]
    scene = task["scene"]
    preproc_loc = task["preproc_loc"]
    preproc_action = task["preproc_action"]
    target_loc = task["target_loc"]
    expected = task["expected"]
    
    print(f"{'='*70}")
    print(f"  📋 {name}")
    print(f"  EN: {en}")
    print(f"  CN: {cn}")
    print(f"  预处理:{preproc_loc}→{preproc_action}  目标:{target_loc}")
    print(f"{'='*70}")
    print()
    
    # 状态
    location = "起点"
    inventory = ""
    feedback = ""
    processed = False
    all_actions = []
    prev_yao = None
    
    for step in range(max_steps):
        # 1. 状态六爻
        yao = build_state_yao(location, inventory, processed, step, preproc_loc, target_loc)
        action_type, reason, changes = yaos_to_action(yao, prev_yao)
        
        # 2. 引擎语义校验
        state = f"位置{location}，{'有'+inventory if inventory else '空手'}，{'已'+preproc_action if processed else '未处理'}"
        result = engine.sentence(state)
        main_hex = result["main_hexagram"]
        dom_bagua = result["dominant_bagua"]
        
        # 3. 动作映射
        available = get_actions(location, inventory, processed, preproc_loc, target_loc, preproc_action)
        
        action = map_action(action_type, available, preproc_loc, target_loc, preproc_action, inventory)
        if not action and available:
            action = available[0]
        if not action:
            break
        
        # 4. 输出
        print(f"  Step{step+1:2d} | {format_yao(yao)}")
        if changes:
            print(f"       | 爻变: {', '.join(changes)}")
        print(f"       | 状态: {location:4s} {inventory or '空手':6s} {'已' if processed else '未'}{preproc_action}")
        print(f"       | 决策: {action_type} ← {reason}")
        print(f"       | 动作: {action}")
        
        # 5. 执行
        location, inventory, feedback, processed = apply(
            action, location, inventory, processed, preproc_loc, target_loc, preproc_action, preproc_action+"了"
        )
        all_actions.append(action)
        prev_yao = yao
        
        if "完成" in feedback:
            print(f"       | ✅ {feedback}")
            print(f"\n  ✅ 任务成功！\n")
            break
        print(f"       | → {feedback}")
        print()
    
    print(f"  动作序列 ({len(all_actions)}步):")
    for i, a in enumerate(all_actions):
        print(f"    {i+1:2d}. {a}")
    print()
    
    return all_actions


# ============================================================
# 通用动作映射和环境模拟
# ============================================================

def map_action(action_type, available, preproc_loc, target_loc, preproc_action, inventory):
    """动作类型 → 具体动作字符串（通用，不针对具体任务）"""
    action_map = {
        "goto": None,
        "take": ["拿起", "拿"],
        "goto_preproc": None,
        "put_in": ["放进", "放入", "放到"],
        "process": ["清洗", "加热", "冷却", "洗", "冻", "冰"],
        "take_out": ["拿出来", "取出"],
        "goto_target": None,
        "put": ["放到", "放回"],
    }
    
    if action_type == "goto":
        for a in available:
            if "柜子" in a:
                return a
        return available[0] if available else None
    
    if action_type == "goto_preproc":
        for a in available:
            if preproc_loc in a and not any(t in a for t in ["拿到", "拿起"]):
                return a
        return available[0] if available else None
    
    if action_type == "goto_target":
        for a in available:
            if target_loc in a and not any(t in a for t in ["拿到", "拿起"]):
                return a
        return available[0] if available else None
    
    for key, keywords in action_map.items():
        if key == action_type and keywords:
            for a in available:
                for kw in keywords:
                    if kw in a:
                        return a
    return None


def get_actions(loc, inv, processed, preproc_loc, target_loc, preproc_action):
    """获取当前可选动作（通用）"""
    acts = []
    if loc == "起点":
        acts = ["去柜子", f"去{preproc_loc}", f"去{target_loc}"]
    elif loc == "柜子":
        if not inv:
            acts = ["拿起脏的"]
        acts += [f"去{preproc_loc}", f"去{target_loc}"]
    elif loc == preproc_loc:
        if inv:
            acts = [f"把东西放到{preproc_loc}里", f"去{target_loc}", "去柜子"]
        else:
            if processed:
                acts = [f"把东西从{preproc_loc}拿出来"]
            else:
                acts = [f"{preproc_action}东西"]
            acts += [f"去{target_loc}", "去柜子"]
    elif loc == target_loc:
        if inv:
            acts = [f"把东西放到{target_loc}里"]
        acts += [f"去{preproc_loc}", "去柜子"]
    return acts


def apply(action, loc, inv, processed, preproc_loc, target_loc, preproc_action, done_word):
    """执行动作（通用）"""
    if "拿起" in action and not inv:
        return "柜子", "目标物", f"你拿起了目标物", False
    elif f"放到{preproc_loc}" in action:
        return preproc_loc, "", f"把目标物放进了{preproc_loc}", False
    elif f"放到{target_loc}" in action:
        return target_loc, "", f"任务完成！你把目标物放到了{target_loc}", True
    elif preproc_action in action and "从" not in action and "放进" not in action:
        return preproc_loc, "", f"你{done_word}目标物", True
    elif "拿出来" in action:
        return preproc_loc, "目标物", f"你从{preproc_loc}拿出了目标物", True
    elif "去柜子" in action:
        return "柜子", inv, "你走到柜子旁", processed
    elif f"去{preproc_loc}" in action:
        return preproc_loc, inv, f"你走到{preproc_loc}旁", processed
    elif f"去{target_loc}" in action:
        return target_loc, inv, f"你走到{target_loc}旁", processed
    return loc, inv, "没变化", processed


# ============================================================
# 运行测试
# ============================================================

for task in TASKS:
    run_task(task)
