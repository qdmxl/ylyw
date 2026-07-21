#!/usr/bin/env python3
"""
六爻驱动逐步决策 — 跨任务测试

用统一的状态六爻和模糊推理规则，测试三种不同任务：
1. 清洗：把盘子洗干净后放到柜台上（预处理=水槽）
2. 冷却：把杯子冷却后放到柜子里（预处理=冰箱）
3. 加热：把食物加热后放到台子上（预处理=微波炉）
4. 简单取放：把苹果放到柜台上（无预处理）
5. 观察：打开台灯看看杯子

决策层完全通用，只有映射层参数（预处理位置、目标位置）不同。
"""

import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine
engine = HanziEngine(verbose=False)

# ============================================================
# 模糊推理规则（通用，不依赖任务类型）
# ============================================================

def left_shoulder(x, edge=0.35, slope=0.15):
    if x <= edge - slope: return 1.0
    if x >= edge + slope: return 0.0
    return 1.0 - (x - (edge - slope)) / (2 * slope)

def right_shoulder(x, edge=0.45, slope=0.15):
    if x >= edge + slope: return 1.0
    if x <= edge - slope: return 0.0
    return (x - (edge - slope)) / (2 * slope)

RULES = [
    ("goto",      lambda y: left_shoulder(y[0]) * left_shoulder(y[1], 0.40), "空手∩未到位→探索"),
    ("take",      lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * left_shoulder(y[3], 0.40), "空手∩到位∩未处理→拿取"),
    ("take_out",  lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * right_shoulder(y[3], 0.45), "空手∩到位∩已处理→取出"),
    ("goto_preproc", lambda y: right_shoulder(y[0], 0.35) * left_shoulder(y[3], 0.40) * left_shoulder(y[1], 0.45), "有物∩未处理∩未到位→去预处理"),
    ("put_in",    lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.45) * left_shoulder(y[3], 0.40), "有物∩到位∩未处理→放入"),
    ("process",   lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.40) * left_shoulder(y[3], 0.40) * left_shoulder(y[4], 0.30), "已放入∩未处理→执行"),
    ("goto_target", lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * left_shoulder(y[1], 0.50), "有物∩已处理∩未到位→去目标"),
    ("put",       lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * right_shoulder(y[1], 0.50) * right_shoulder(y[4], 0.40), "有物∩已处理∩到位→放置"),
    ("goto",      lambda y: 0.15, "兜底"),
]

def fuzzy_decide(yao):
    best_a, best_n, best_d = 0.0, "goto", "兜底"
    for name, fn, desc in RULES:
        act = fn(yao)
        if act > best_a:
            best_a, best_n, best_d = act, name, desc
    return best_n, best_a, best_d


def build_yao(location, inventory, processed, step, preproc_loc, target_loc):
    """状态六爻构造（通用）
    处理无预处理任务：preproc_loc为None时跳过预处理相关逻辑
    """
    y0 = 0.40 if inventory and not processed else (0.65 if inventory and processed else 0.10)
    loc_map = {"起点": 0.10}
    if preproc_loc: loc_map[preproc_loc] = 0.55
    if target_loc: loc_map[target_loc] = 0.80
    for k in ["柜子", "桌子", "架子", "抽屉"]:
        if k not in loc_map: loc_map[k] = 0.30 if preproc_loc else 0.50
    y1 = loc_map.get(location, 0.25)
    y2 = min(0.10 + step * 0.09, 0.85)
    # 四爻：无预处理任务时，拿到物体即为"已处理"
    if preproc_loc is None:
        y3 = 0.80 if inventory else 0.10  # 有物=已处理
    else:
        if processed and location == preproc_loc and not inventory: y3 = 0.70
        elif processed and inventory: y3 = 0.85
        elif processed: y3 = 0.60
        elif not inventory and location == preproc_loc: y3 = 0.25
        else: y3 = 0.10
    # 五爻：无预处理任务时，拿到物体就直接进入"去目标"阶段
    if preproc_loc is None:
        if location == target_loc and inventory: y4 = 0.85
        elif location == target_loc: y4 = 0.35
        elif inventory: y4 = 0.15
        else: y4 = 0.15
    else:
        if location == target_loc and inventory: y4 = 0.85
        elif location == target_loc: y4 = 0.35
        elif location == preproc_loc and not inventory and processed: y4 = 0.65
        elif location == preproc_loc and not inventory and not processed: y4 = 0.30
        elif location == preproc_loc and inventory: y4 = 0.15
        else: y4 = 0.15
    # 上爻
    if preproc_loc is None:
        y5 = 0.75 if location == target_loc else (0.25 if location == "起点" else 0.45)
    else:
        y5 = 0.75 if location in (preproc_loc, target_loc) else (0.25 if location == "起点" else 0.45)
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


def get_actions(loc, inv, processed, preproc_loc, target_loc):
    """获取当前可选动作（通用）
    处理两种特殊情况：
    1. preproc_loc=None → 无预处理，直接取放
    2. target_loc=柜子（与探索位置"柜子"同名）→ 需区分
    """
    explore_loc = "桌子" if target_loc == "柜子" else "柜子"
    
    acts = []
    if loc == "起点":
        if preproc_loc:
            acts = [f"去{explore_loc}", f"去{preproc_loc}"]
        else:
            acts = [f"去{explore_loc}", f"去{target_loc}"]
    elif loc == explore_loc:
        if not inv: acts = ["拿起物体"]
        if preproc_loc:
            acts += [f"去{preproc_loc}"]
        acts += [f"去{target_loc}"]
    elif preproc_loc and loc == preproc_loc:
        if inv:
            acts = [f"把物体放进{preproc_loc}", f"去{target_loc}"]
        else:
            if processed:
                acts = [f"把物体从{preproc_loc}拿出来"]
            else:
                acts = [f"处理物体"]
            acts += [f"去{target_loc}"]
    elif loc == target_loc:
        if inv:
            acts = [f"把物体放到{target_loc}上"]
        if preproc_loc:
            acts += [f"去{preproc_loc}"]
        acts += [f"去{explore_loc}"]
    return acts


def apply(action, loc, inv, processed, preproc_loc, target_loc, action_word, done_word):
    explore_loc = "桌子" if target_loc == "柜子" else "柜子"
    
    if "拿起" in action and not inv:
        return explore_loc, "物体", f"你拿起了物体", False
    elif preproc_loc and f"放进{preproc_loc}" in action:
        return preproc_loc, "", f"你把物体放进了{preproc_loc}", False
    elif "处理" in action and "从" not in action and "放进" not in action and preproc_loc:
        return preproc_loc, "", f"你{done_word}了物体", True
    elif preproc_loc and "拿出来" in action:
        return preproc_loc, "物体", f"你从{preproc_loc}拿出了物体", True
    elif f"放到{target_loc}" in action:
        return target_loc, "", f"任务完成！", True
    elif f"去{target_loc}" in action:
        if loc == target_loc: return loc, inv, f"已经在{target_loc}旁", processed
        return target_loc, inv, f"你走到{target_loc}旁", processed
    elif preproc_loc and f"去{preproc_loc}" in action:
        if loc == preproc_loc: return loc, inv, f"已经在{preproc_loc}旁", processed
        return preproc_loc, inv, f"你走到{preproc_loc}旁", processed
    elif f"去{explore_loc}" in action:
        if loc == explore_loc: return loc, inv, f"已经在{explore_loc}旁", processed
        return explore_loc, inv, f"你走到{explore_loc}旁", processed
    return loc, inv, "没变化", processed


def run_task(task):
    name = task["name"]
    cn = task["cn"]
    preproc_loc = task["preproc_loc"]
    action_word = task["action_word"]
    done_word = task["done_word"]
    target_loc = task["target_loc"]
    expect_steps = task.get("expect_steps", 8)

    print(f"{'='*60}")
    print(f"  {name}: {cn}")
    print(f"  预处理={preproc_loc}→{action_word}  目标={target_loc}")
    print(f"{'='*60}")
    
    loc, inv, fb, processed = "起点", "", "", False
    actions, prev_yao = [], None
    
    for step in range(15):
        yao = build_yao(loc, inv, processed, step, preproc_loc, target_loc)
        action_type, activation, reason = fuzzy_decide(yao)
        
        available = get_actions(loc, inv, processed, preproc_loc, target_loc)
        action = None
        # 无预处理任务：跳过预处理相关动作类型
        if preproc_loc is None:
            if action_type in ("goto_preproc", "put_in", "process", "take_out"):
                # 有物时直接去目标，没物时探索/拿取
                if inventory:
                    action_type = "put"
                else:
                    action_type = "take" if "拿起" in str(available) else "goto"
        
        mapping = {
            "goto": [a for a in available if "去" in a and "拿起" not in a],
            "take": [a for a in available if "拿起" in a],
            "goto_preproc": [a for a in available if preproc_loc and f"去{preproc_loc}" in a],
            "put_in": [a for a in available if "放进" in a],
            "process": [a for a in available if "处理" in a and "从" not in a and "放进" not in a],
            "take_out": [a for a in available if "拿出来" in a],
            "goto_target": [a for a in available if f"去{target_loc}" in a and "放" not in a],
            "put": [a for a in available if "放到" in a or (target_loc in a and "去" not in a)],
        }
        candidates = mapping.get(action_type, [])
        # put/goto_target的兜底
        if not candidates and action_type == "put":
            candidates = [a for a in available if target_loc in a and "去" not in a]
        if not candidates and action_type == "goto_target":
            candidates = [a for a in available if target_loc in a]
        if not candidates and action_type == "goto":
            candidates = [a for a in available if "去" in a]
        action = candidates[0] if candidates else (available[0] if available else None)
        if not action: break
        
        yao_str = "  ".join(f"{n}={yao[i]:.2f}{'━' if yao[i]>=0.5 else '┅'}" for i, n in enumerate(["初","二","三","四","五","上"]))
        changes = ""
        if prev_yao:
            diffs = [f"{['初','二','三','四','五','上'][i]}{'+' if yao[i]-prev_yao[i]>0 else ''}{yao[i]-prev_yao[i]:.2f}" 
                     for i in range(6) if abs(yao[i]-prev_yao[i])>0.05]
            if diffs: changes = " | ".join(diffs)
        
        print(f"  S{step+1:2d} {yao_str}")
        if changes: print(f"     爻变: {changes}")
        
        rules_act = [(name, fn(yao)) for name, fn, desc in RULES[:-1] if fn(yao) > 0.05]
        if rules_act: print(f"     规则: {' '.join(f'{n}={a:.2f}' for n,a in sorted(rules_act, key=lambda x:-x[1])[:3])}")
        
        print(f"     → {action_type}({activation:.3f}) {action}")
        
        loc, inv, fb, processed = apply(action, loc, inv, processed, preproc_loc, target_loc, action_word, done_word)
        actions.append(action)
        prev_yao = yao
        
        if "完成" in fb:
            print(f"     ✅ 任务完成！\n")
            break
        print(f"     {fb}")
    
    result = f"{'✅' if '完成' in fb else '❌'} {len(actions)}步"
    print(f"  结果: {result}")
    print(f"  动作序列: {' → '.join(actions)}")
    print()
    return result, actions


# ============================================================
# 5个不同类型任务
# ============================================================

TASKS = [
    {
        "name": "清洗后放置",
        "cn": "把盘子洗干净后放到柜台上",
        "preproc_loc": "水槽", "action_word": "清洗", "done_word": "洗净",
        "target_loc": "柜台", "expect_steps": 8,
    },
    {
        "name": "冷却后放置",
        "cn": "把杯子冷却后放到柜子里",
        "preproc_loc": "冰箱", "action_word": "冷却", "done_word": "冷却",
        "target_loc": "柜子", "expect_steps": 8,
    },
    {
        "name": "加热后放置",
        "cn": "把食物加热后放到台子上",
        "preproc_loc": "微波炉", "action_word": "加热", "done_word": "加热",
        "target_loc": "台子", "expect_steps": 8,
    },
    {
        "name": "简单取放",
        "cn": "把苹果放到柜台上",
        "preproc_loc": None, "action_word": "", "done_word": "",
        "target_loc": "柜台", "expect_steps": 4,
    },
]

print("=" * 60)
print("  六爻驱动逐步决策 — 跨任务测试")
print(f"  语义引擎版本: 递归YLYW")
print(f"  规则数: 8条模糊规则")
print("=" * 60)
print()

results = []
for task in TASKS:
    r, actions = run_task(task)
    results.append((task["name"], r))

print("=" * 60)
print("  汇总")
print("=" * 60)
for name, r in results:
    print(f"  {name:12s} {r}")
print("=" * 60)
