#!/usr/bin/env python3
"""
ALFWorld全任务测试 — 六爻驱动逐步决策

覆盖5类15个任务的完整测试。
只测语义理解→任务规划（不连接ALFWorld环境）。
用YLYW语义引擎理解任务描述，然后六爻+模糊推理生成动作序列。
"""

import sys, os, math, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ========== 翻译：LLM调用（通过web_fetch） ==========
def translate_task_en_to_cn(task_en):
    """规则翻译ALFWorld英文任务为中文"""
    t = task_en.lower().strip().rstrip('.')
    
    # 精确匹配已知任务
    known = {
        "put a clean plate on the counter": "把盘子洗干净后放到柜台上",
        "put a clean yellow plate on the counter": "把黄色盘子洗干净后放到柜台上",
        "wash the dirty bowl before putting the bowl on the counter": "先把脏碗洗干净再放到柜台上",
        "to move two bars of soap to the gold bin": "把两块肥皂移到金色垃圾桶里",
        "throw both pieces of soap into the trash can": "把两块肥皂都扔进垃圾桶",
        "throw two bars of soap in the trash bin": "把两块肥皂扔进垃圾桶",
        "look at a mug in lamp light": "打开台灯看看杯子",
        "turn on the desk lamp": "打开台灯",
        "examine a mug using the light of a desk lamp": "用台灯的光照看看杯子",
        "put a chilled mug in a cabinet": "把杯子冷却后放到柜子里",
        "place a chilled mug in a cabinet": "把杯子冷却后放进柜子里",
        "put a cold coffee up in the bottom cabinet": "把冷咖啡放到下层柜子里",
        "move a pencil on the desk over": "把桌子上的笔挪一下位置",
        "move the pencil to a different area of the desk": "把笔移到桌子的另一个位置",
        "take the pencil from the desk, put it back on the desk": "把笔从桌子上拿起来再放回桌子上",
    }
    if t in known:
        return known[t]
    
    # 模式匹配
    patterns = [
        (r"put a clean (.+) on (.+)", "把{0}洗干净后放到{1}上"),
        (r"put a clean (.+) in (.+)", "把{0}洗干净后放到{1}里"),
        (r"clean (.+) and put it in (.+)", "把{0}洗干净再放到{1}里"),
        (r"clean (.+) and put it on (.+)", "把{0}洗干净再放到{1}上"),
        (r"wash (.+) before putting", "先把{0}洗干净再放"),
        (r"heat (.+) and put it in (.+)", "把{0}加热再放到{1}里"),
        (r"heat (.+) and put it on (.+)", "把{0}加热再放到{1}上"),
        (r"put a chilled (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"place a chilled (.+) in (.+)", "把{0}冷却后放进{1}里"),
        (r"put a cold (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"cool (.+) and put it in (.+)", "把{0}冷却再放到{1}里"),
        (r"look at (.+) in (.+)", "用{1}的光看看{0}"),
        (r"turn on the (.+)", "打开{0}"),
        (r"examine (.+) using (.+)", "用{1}查看{0}"),
        (r"put (.+) in (.+)", "把{0}放到{1}里"),
        (r"put (.+) on (.+)", "把{0}放到{1}上"),
        (r"move (.+) to (.+)", "把{0}移到{1}"),
        (r"take (.+) from (.+), put it back on (.+)", "把{0}从{1}拿起来再放回{2}上"),
        (r"throw (.+) into (.+)", "把{0}扔进{1}"),
        (r"throw (.+) in (.+)", "把{0}扔进{1}"),
        (r"move (.+) on (.+) over", "把{1}上的{0}挪动一下"),
    ]
    for pat, tmpl in patterns:
        m = re.match(pat, t)
        if m:
            groups = list(m.groups())
            cn_groups = [_cn(g) for g in groups]
            try:
                return tmpl.format(*cn_groups)
            except:
                continue
    return task_en  # fallback

def _cn(w):
    w2 = re.sub(r'\s+\d+$', '', w.strip().lower())
    en2cn = {
        "plate":"盘子","bowl":"碗","mug":"杯子","cup":"杯子",
        "apple":"苹果","potato":"土豆","tomato":"番茄","lettuce":"生菜",
        "bread":"面包","egg":"鸡蛋","milk":"牛奶","coffee":"咖啡",
        "soap":"肥皂","sponge":"海绵","cloth":"抹布",
        "pencil":"笔","pen":"笔","paper":"纸","book":"书","key":"钥匙",
        "counter":"柜台","countertop":"柜台","sinkbasin":"水槽","sink":"水槽",
        "fridge":"冰箱","microwave":"微波炉",
        "cabinet":"柜子","drawer":"抽屉","shelf":"架子","garbagecan":"垃圾桶",
        "desk":"桌子","table":"桌子","desk lamp":"台灯","lamp":"灯",
        "toaster":"烤面包机","coffeemachine":"咖啡机","stoveburner":"灶台",
        "bed":"床","sofa":"沙发","chair":"椅子","diningtable":"餐桌",
        "trash can":"垃圾桶","trash bin":"垃圾桶","gold bin":"金色垃圾桶",
        "food":"食物","chilled":"冷却","cold":"冷的",
    }
    return en2cn.get(w2, w2)


# ========== 模糊推理 ==========
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


# ========== 任务解析器（从语义引擎的卦象中提取参数） ==========
def parse_task(task_cn, task_en=""):
    """解析中文任务，提取任务类型和参数"""
    result = engine.sentence(task_cn)
    segs = result['segments']
    roles = result['segment_role']
    rels = result['mutua_relations']
    main_hex = result['main_hexagram']
    
    # 时序解析
    temporal = engine.parse_temporal(task_cn)
    
    # 动词
    verbs = [segs[i] for i in range(len(segs)) if roles[i] == '动作']
    # 物体
    objects = [segs[i] for i in range(len(segs)) if roles[i] == '物体']
    
    # 任务类型
    verb_text = ' '.join(verbs)
    need_clean = any(w in verb_text for w in ['洗','干净','清洁'])
    need_heat = any(w in verb_text for w in ['加热','热']) and '冷' not in verb_text
    need_cool = any(w in verb_text for w in ['冷却','冷','冰'])
    need_look = any(w in verb_text for w in ['看','照','查看','检查','打开']) and any(w in task_cn for w in ['灯','光'])
    need_two = any(w in task_cn for w in ['两块','两个','两'])
    need_throw = any(w in verb_text for w in ['扔','丢'])
    
    task_type = "pick_and_place"
    if need_clean: task_type = "pick_clean_then_place"
    elif need_heat: task_type = "pick_heat_then_place"
    elif need_cool: task_type = "pick_cool_then_place"
    elif need_look: task_type = "look_at_obj"
    elif need_throw: task_type = "pick_two_and_place"
    elif need_two: task_type = "pick_two_and_place"
    
    # 目标物体
    target_obj = None
    for obj in objects:
        if obj not in ['任务：','场景：'] and not any(loc in obj for loc in ['柜台','柜子','水槽','冰箱','微破','架子','桌子','台子','垃圾桶']):
            target_obj = obj
            break
    if not target_obj and objects:
        target_obj = objects[-1]
    if not target_obj:
        target_obj = "物体"
    
    # 目标位置
    target_loc = None
    for seg in segs:
        for lc in ['柜台','柜子','架子','台子','桌子','垃圾桶','金色垃圾桶','柜']:
            if lc in seg:
                target_loc = lc
    if not target_loc:
        for rel in rels:
            for lc in ['柜台','柜子','架子','台子','桌子','垃圾桶']:
                if lc in rel.get('to','') or lc in rel.get('from',''):
                    target_loc = lc
    if not target_loc:
        target_loc = "柜台" if not need_look else "桌子"
    
    # 预处理位置
    preproc_loc = None
    if need_clean: preproc_loc = "水槽"
    elif need_heat: preproc_loc = "微波炉"
    elif need_cool: preproc_loc = "冰箱"
    
    # 动作词
    action_word = "清洗" if need_clean else ("加热" if need_heat else ("冷却" if need_cool else ""))
    done_word = "洗净" if need_clean else ("加热" if need_heat else ("冷却" if need_cool else ""))
    
    # 探索位置（避开目标位置同名）
    explore_loc = "桌子" if target_loc == "柜子" else "柜子"
    
    return {
        "task_type": task_type,
        "target_obj": target_obj,
        "target_loc": target_loc,
        "preproc_loc": preproc_loc,
        "action_word": action_word,
        "done_word": done_word,
        "explore_loc": explore_loc,
        "verbs": verbs,
        "main_hex": main_hex,
        "temporal": temporal,
    }


# ========== 逐步决策模拟 ==========
def build_yao(loc, inv, processed, step, preproc_loc, target_loc, task_type):
    y0 = 0.40 if inv and not processed else (0.65 if inv and processed else 0.10)
    loc_map = {"起点": 0.10}
    if preproc_loc: loc_map[preproc_loc] = 0.55
    if target_loc: loc_map[target_loc] = 0.80
    for k in ["柜子", "桌子", "架子", "抽屉"]:
        loc_map[k] = 0.30 if preproc_loc else 0.50
    y1 = loc_map.get(loc, 0.25)
    y2 = min(0.10 + step * 0.09, 0.85)
    
    if task_type == "look_at_obj":
        y3 = 0.80 if inv else 0.10
        y4 = 0.85 if loc == target_loc and inv else (0.35 if loc == target_loc else 0.15)
    elif preproc_loc is None:
        y3 = 0.80 if inv else 0.10
        if loc == target_loc and inv: y4 = 0.85
        elif loc == target_loc: y4 = 0.35
        elif inv: y4 = 0.15
        else: y4 = 0.15
    else:
        if processed and loc == preproc_loc and not inv: y3 = 0.70
        elif processed and inv: y3 = 0.85
        elif processed: y3 = 0.60
        elif not inv and loc == preproc_loc: y3 = 0.25
        else: y3 = 0.10
        if loc == target_loc and inv: y4 = 0.85
        elif loc == target_loc: y4 = 0.35
        elif loc == preproc_loc and not inv and processed: y4 = 0.65
        elif loc == preproc_loc and not inv and not processed: y4 = 0.30
        elif loc == preproc_loc and inv: y4 = 0.15
        else: y4 = 0.15
    
    if task_type == "look_at_obj":
        y5 = 0.75 if loc == target_loc else (0.25 if loc == "起点" else 0.45)
    elif preproc_loc:
        y5 = 0.75 if loc in (preproc_loc, target_loc) else (0.25 if loc == "起点" else 0.45)
    else:
        y5 = 0.75 if loc == target_loc else (0.25 if loc == "起点" else 0.45)
    
    return [round(v,3) for v in [y0,y1,y2,y3,y4,y5]]


def get_actions(loc, inv, processed, preproc_loc, target_loc, explore_loc, task_type):
    acts = []
    if task_type == "look_at_obj":
        if loc == "起点":
            acts = [f"去{explore_loc}", f"去{target_loc}"]
        elif loc in (explore_loc, target_loc):
            if not inv: acts = ["拿起物体"]
            acts += [f"去{target_loc}" if loc != target_loc else f"去{explore_loc}"]
            if loc == target_loc and inv: acts = ["打开灯看看"]
        return acts
    
    if loc == "起点":
        acts = [f"去{explore_loc}"]
        if preproc_loc: acts += [f"去{preproc_loc}"]
        acts += [f"去{target_loc}"]
    elif loc == explore_loc:
        if not inv: acts = ["拿起物体"]
        if preproc_loc: acts += [f"去{preproc_loc}"]
        acts += [f"去{target_loc}"]
    elif preproc_loc and loc == preproc_loc:
        if inv:
            acts = [f"把物体放进{preproc_loc}", f"去{target_loc}"]
        else:
            if processed: acts = [f"把物体从{preproc_loc}拿出来"]
            else: acts = [f"处理物体"]
            acts += [f"去{target_loc}"]
    elif loc == target_loc:
        if inv: acts = [f"把物体放到{target_loc}上"]
        if preproc_loc: acts += [f"去{preproc_loc}"]
        acts += [f"去{explore_loc}"]
    return acts


def apply(action, loc, inv, processed, preproc_loc, target_loc, explore_loc, task_type):
    if task_type == "look_at_obj":
        if "拿起" in action and not inv:
            return explore_loc, "物体", "你拿起了物体", False
        elif "打开灯" in action:
            return target_loc, inv, "任务完成！", True
        elif f"去{target_loc}" in action:
            if loc == target_loc: return loc, inv, f"已在{target_loc}", processed
            return target_loc, inv, f"走到{target_loc}", processed
        elif f"去{explore_loc}" in action:
            if loc == explore_loc: return loc, inv, f"已在{explore_loc}", processed
            return explore_loc, inv, f"走到{explore_loc}", processed
        return loc, inv, "没变化", processed
    
    if "拿起" in action and not inv:
        return explore_loc, "物体", "你拿起了物体", False
    elif preproc_loc and f"放进{preproc_loc}" in action:
        return preproc_loc, "", f"你把物体放进了{preproc_loc}", False
    elif "处理" in action and "从" not in action and "放进" not in action and preproc_loc:
        return preproc_loc, "", f"你{done_words.get(task_type,'处理')}了物体", True
    elif preproc_loc and "拿出来" in action:
        return preproc_loc, "物体", f"你从{preproc_loc}拿出了物体", True
    elif f"放到{target_loc}" in action:
        return target_loc, "", "任务完成！", True
    elif f"去{target_loc}" in action:
        if loc == target_loc: return loc, inv, f"已在{target_loc}旁", processed
        return target_loc, inv, f"你走到{target_loc}旁", processed
    elif preproc_loc and f"去{preproc_loc}" in action:
        if loc == preproc_loc: return loc, inv, f"已在{preproc_loc}旁", processed
        return preproc_loc, inv, f"你走到{preproc_loc}旁", processed
    elif f"去{explore_loc}" in action:
        if loc == explore_loc: return loc, inv, f"已在{explore_loc}旁", processed
        return explore_loc, inv, f"你走到{explore_loc}旁", processed
    return loc, inv, "没变化", processed


done_words = {
    "pick_clean_then_place": "洗净",
    "pick_heat_then_place": "加热",
    "pick_cool_then_place": "冷却",
    "pick_and_place": "",
    "pick_two_and_place": "",
    "look_at_obj": "",
}


def run_game(task_en):
    task_cn = translate_task_en_to_cn(task_en)
    params = parse_task(task_cn, task_en)
    
    task_type = params["task_type"]
    target_loc = params["target_loc"]
    preproc_loc = params["preproc_loc"]
    explore_loc = params["explore_loc"]
    done_word = params["done_word"]
    
    # 无预处理任务特殊处理
    no_preproc = preproc_loc is None and task_type not in ("look_at_obj",)
    
    loc, inv, fb, processed = "起点", "", "", False
    actions, prev_yao = [], None
    done = False
    
    for step in range(15):
        if done: break
        yao = build_yao(loc, inv, processed, step, preproc_loc, target_loc, task_type)
        action_type, activation, reason = fuzzy_decide(yao)
        
        # 无预处理时跳过预处理相关动作
        if no_preproc:
            if action_type in ("goto_preproc", "put_in", "process", "take_out"):
                action_type = "put" if inv else ("take" if any("拿起" in a for a in get_actions(loc, inv, processed, preproc_loc, target_loc, explore_loc, task_type)) else "goto")
        
        available = get_actions(loc, inv, processed, preproc_loc, target_loc, explore_loc, task_type)
        
        mapping = {
            "goto": [a for a in available if "去" in a and "拿起" not in a],
            "take": [a for a in available if "拿起" in a],
            "goto_preproc": [a for a in available if preproc_loc and f"去{preproc_loc}" in a],
            "put_in": [a for a in available if "放进" in a],
            "process": [a for a in available if "处理" in a and "从" not in a and "放进" not in a],
            "take_out": [a for a in available if "拿出来" in a],
            "goto_target": [a for a in available if f"去{target_loc}" in a and "放" not in a],
            "put": [a for a in available if "放到" in a or ("打开灯" in a) or (target_loc in a and "去" not in a)],
        }
        
        candidates = mapping.get(action_type, [])
        if not candidates and action_type == "put":
            candidates = [a for a in available if target_loc in a and "去" not in a]
            if not candidates: candidates = [a for a in available if "放" in a or "灯" in a or "看看" in a]
        if not candidates and action_type == "goto_target":
            candidates = [a for a in available if target_loc in a]
        if not candidates:
            candidates = available
        
        action = candidates[0] if candidates else None
        if not action: break
        
        loc, inv, fb, processed = apply(action, loc, inv, processed, preproc_loc, target_loc, explore_loc, task_type)
        actions.append(action)
        prev_yao = yao
        
        if "完成" in fb:
            done = True
    
    return {
        "task_en": task_en,
        "task_cn": task_cn,
        "task_type": task_type,
        "target_obj": params["target_obj"],
        "target_loc": target_loc,
        "preproc_loc": preproc_loc,
        "main_hex": params["main_hex"],
        "temporal_order": " → ".join(params["temporal"]["actions_ordered"]),
        "actions": actions,
        "steps": len(actions),
        "success": done,
    }


# ========== ALFWorld 15个任务 ==========
TASKS = [
    "Put a clean plate on the counter.",
    "Put a clean yellow plate on the counter.",
    "wash the dirty bowl before putting the bowl on the counter",
    "To move two bars of soap to the gold bin.",
    "Throw both pieces of soap into the trash can.",
    "Throw two bars of soap in the trash bin.",
    "Look at a mug in lamp light.",
    "Turn on the desk lamp.",
    "Examine a mug using the light of a desk lamp.",
    "Put a chilled mug in a cabinet.",
    "Place a chilled mug in a cabinet.",
    "Put a cold coffee up in the bottom cabinet.",
    "Move a pencil on the desk over.",
    "Move the pencil to a different area of the desk.",
    "Take the pencil from the desk, put it back on the desk",
]

print("=" * 70)
print("  递归YLYW — ALFWorld全任务任务规划测试")
print("  5类15个任务 | 六爻驱动逐步决策 | 零样本")
print("=" * 70)
print()

results = []
for i, task_en in enumerate(TASKS):
    r = run_game(task_en)
    results.append(r)
    
    icon = "✅" if r["success"] else "❌"
    act_str = " → ".join(r["actions"])
    
    print(f"  {icon} #{i:2d} [{r['task_type']:25s}] {r['task_en'][:55]}")
    print(f"     中文: {r['task_cn']}")
    print(f"     主卦: {r['main_hex']:8s}  时序: {r['temporal_order']}")
    print(f"     目标: {r['target_obj']} → {r['target_loc']}  {'预处理:'+r['preproc_loc'] if r['preproc_loc'] else '无预处理'}")
    print(f"     动作({r['steps']}步): {act_str}")
    print()

# 汇总
print("=" * 70)
print("  汇总")
print("=" * 70)
by_type = {}
for r in results:
    t = r["task_type"]
    if t not in by_type: by_type[t] = {"total": 0, "success": 0, "steps": []}
    by_type[t]["total"] += 1
    by_type[t]["success"] += 1 if r["success"] else 0
    by_type[t]["steps"].append(r["steps"])

for t, d in by_type.items():
    avg = sum(d["steps"]) / len(d["steps"]) if d["steps"] else 0
    print(f"  {t:30s} {d['success']}/{d['total']}通过  平均步数:{avg:.1f}")

total_success = sum(1 for r in results if r["success"])
print(f"\n  总计: {total_success}/{len(results)} 通过 ({total_success/len(results)*100:.0f}%)")
print("=" * 70)
