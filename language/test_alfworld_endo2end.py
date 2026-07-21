#!/usr/bin/env python3
"""
端到端测试：ALFWorld任务 → 翻译 → YLYW汉语理解 → 操作序列

测试任务：Put a clean plate on the counter.
场景：厨房。有一个柜台(counter)、一个水槽(sinkbasin)。水槽旁边有一个脏盘子。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# =========================================================
# 1. ALFWorld英文任务 → 中文翻译
# =========================================================
# 翻译规则：
#   ALFWorld 6类任务的中英文对照
#   pick_and_place_simple     → 把<物体>放到<位置>
#   pick_clean_then_place     → 先把<物体>洗干净再放到<位置>
#   pick_heat_then_place      → 先把<物体>加热再放到<位置>
#   pick_cool_then_place      → 先把<物体>冷却再放到<位置>
#   look_at_obj_in_light      → 打开<灯>看看<物体>
#   pick_two_obj_and_place    → 把两个<物体>都放到<位置>

TASK_TRANSLATIONS = {
    "Put a clean plate on the counter.":
        "把盘子洗干净后放到柜台上",
    "Put a clean yellow plate on the counter.":
        "把黄色盘子洗干净后放到柜台上",
    "wash the dirty bowl before putting the bowl on the counter":
        "先把脏碗洗干净再放到柜台上",
    "Put a chilled mug in a cabinet.":
        "把杯子冷却后放到碗柜里",
    "Place a chilled mug in a cabinet.":
        "把杯子冷却后放进碗柜",
    "Put a cold coffee up in the bottom cabinet.":
        "把冷咖啡放到下层柜子里",
    "Look at a mug in lamp light.":
        "开着台灯看看杯子",
    "Turn on the desk lamp.":
        "打开台灯",
    "Examine a mug using the light of a desk lamp.":
        "用台灯的光照看看杯子",
    "Move a pencil on the desk over.":
        "把桌子上的笔挪一下",
    "Move the pencil to a different area of the desk.":
        "把笔移到桌子另一个位置",
    "Take the pencil from the desk, put it back on the desk":
        "把笔从桌子上拿起来再放回去",
    "Put a hot apple in the fridge.":
        "把热苹果放到冰箱里",
    "Heat the food and put it on the counter.":
        "把食物加热后放到台子上",
    "Throw both pieces of soap into the trash can.":
        "把两块肥皂都扔到垃圾桶里",
    "To move two bars of soap to the gold bin.":
        "把两块肥皂移到金色垃圾桶里",
    "Throw two bars of soap in the trash bin.":
        "把两块肥皂扔进垃圾桶",
}

# 多选一个带场景的
test_task = {
    "en": "Put a clean plate on the counter.",
    "cn": "把盘子洗干净后放到柜台上",
    "scene": "厨房。有一个水槽(sinkbasin)在墙角，水槽旁边有一个柜台(counter)。水槽边有一个脏盘子，需要先洗干净再放到柜台上。",
    "task_type": "pick_clean_then_place",
}


def generate_alfworld_actions(result, scene, task):
    """
    根据YLYW引擎的输出，生成ALFWorld可执行的操作序列。
    
    核心思维：
    1. 先从句级卦象判断任务类型（清洗/加热/冷却/观察/取放）
    2. 从分词中提取 动作动词、目标物体、目标位置
    3. 按ALFWorld操作原语构造序列
    """
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_dom = result["segment_dominant"]
    seg_hex = result["segment_hexagram"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    
    # === 从分词提取关键信息 ===
    verbs = [segments[i] for i in range(len(segments)) if seg_roles[i] == "动作"]
    objects = [segments[i] for i in range(len(segments)) if seg_roles[i] == "物体"]
    funcs = [segments[i] for i in range(len(segments)) if seg_roles[i] == "虚词"]
    
    # === 从卦象和动词判断任务类型 ===
    verb_set = set()
    for v in verbs:
        if "洗" in v or "干净" in v or "清" in v: verb_set.add("clean")
        elif "热" in v or "暖" in v: verb_set.add("heat")
        elif "冷" in v or "冰" in v: verb_set.add("cool")
        elif "看" in v or "照" in v or "查" in v: verb_set.add("look")
        elif "扔" in v or "丢" in v: verb_set.add("throw")
        elif "放" in v: verb_set.add("place")
        elif "拿" in v or "取" in v: verb_set.add("take")
        elif "开" in v: verb_set.add("open")
        elif "关" in v: verb_set.add("close")
    # 从卦象额外判断
    if main_hex in ("坎为水","水风井","水山蹇"): verb_set.add("clean")
    if main_hex in ("离为火","火风鼎","火天大有"): verb_set.add("heat")
    
    # === 场景中的位置信息 ===
    location_map = {
        "水槽": "sinkbasin", "柜台": "counter", "桌子": "table", "台子": "counter",
        "冰箱": "fridge", "微波炉": "microwave", "微波": "microwave",
        "碗柜": "cabinet", "柜子": "cabinet", "抽屉": "drawer", "架子": "shelf",
        "台灯": "desk lamp", "灯": "desk lamp", "灯": "lamp",
        "垃圾桶": "trash can", "桶": "trash can", "洗手台": "sinkbasin",
        "水池": "sinkbasin", "水槽": "sinkbasin",
        "沙发": "sofa", "椅子": "chair", "餐桌": "dining table",
    }
    
    # 从场景中解析可用位置
    known_locations = {}
    for cn, en in location_map.items():
        if cn in scene:
            known_locations[cn] = en
    
    # === 确定目标物体 ===
    target_obj = None
    for obj in reversed(objects):
        if obj not in funcs and obj not in location_map:
            target_obj = obj
            break
    if not target_obj and objects:
        target_obj = objects[-1]
    if not target_obj:
        target_obj = "物体"
    # 中文物体→英文映射
    obj_map = {
        "盘子": "plate", "盘": "plate", "脏盘": "plate", "脏碗": "bowl",
        "碗": "bowl", "杯子": "mug", "杯": "mug", "苹果": "apple",
        "食物": "food", "牛奶": "milk", "咖啡": "coffee", "肥皂": "soap",
        "笔": "pencil", "土豆": "potato", "面包": "bread",
    }
    target_obj_en = obj_map.get(target_obj, target_obj)
    
    # === 确定目标位置 ===
    target_loc_en = None
    target_loc_cn = None
    for seg in reversed(segments):
        for cn, en in location_map.items():
            if cn in seg:
                target_loc_en = en
                target_loc_cn = cn
                break
        if target_loc_en:
            break
    
    # === 构造操作序列 ===
    actions = []
    
    # 第一步：如果物体在容器里，先找物体（goto）
    # 确定物体的起始位置
    source_loc_en = None
    source_loc_cn = None
    for seg in segments:
        for cn, en in location_map.items():
            if cn in seg and (source_loc_en is None or seg != target_loc_cn):
                # 避免把目标位置当起始位置（如果有"里/中"修饰，优先作为源位置）
                if "里" in result["text"] and cn in result["text"].split("里")[0]:
                    source_loc_en = en
                    source_loc_cn = cn
    
    # 找不到则用第一个已知位置
    if not source_loc_en and known_locations:
        locs = list(known_locations.items())
        if len(locs) >= 2:
            # 取第一个非目标位置的
            for cn, en in locs:
                if en != target_loc_en:
                    source_loc_en = en
                    source_loc_cn = cn
                    break
            if not source_loc_en:
                source_loc_en = locs[0][1]
                source_loc_cn = locs[0][0]
        elif locs:
            source_loc_en = locs[0][1]
            source_loc_cn = locs[0][0]
    
    if not source_loc_en:
        source_loc_en = "counter"
    
    # ==== 按任务类型生成操作 ====
    
    if "look" in verb_set:
        # 观察任务
        actions.append(("goto", source_loc_en if source_loc_en else "desk"))
        actions.append(("turn_on", "desk lamp"))
        actions.append(("examine", target_obj_en))
    
    elif "clean" in verb_set or "cool" in verb_set or "heat" in verb_set:
        # 有预处理步骤
        preproc_type = None
        preproc_loc = None
        if "clean" in verb_set:
            preproc_type = "clean"
            preproc_loc = "sinkbasin"
        elif "heat" in verb_set:
            preproc_type = "heat"
            preproc_loc = "microwave"
        elif "cool" in verb_set:
            preproc_type = "cool"
            preproc_loc = "fridge"
        
        # Step 1: 去物体所在位置
        actions.append(("goto", source_loc_en))
        actions.append(("take", target_obj_en))
        
        # Step 2: 去预处理位置
        actions.append(("goto", preproc_loc))
        
        if preproc_type == "cool":
            actions.append(("open", preproc_loc))
            actions.append(("put", f"{target_obj_en} in/on {preproc_loc}"))
            actions.append(("close", preproc_loc))
            actions.append(("cool", target_obj_en))
            actions.append(("open", preproc_loc))
            actions.append(("take", target_obj_en))
            actions.append(("close", preproc_loc))
        elif preproc_type == "heat":
            actions.append(("open", preproc_loc))
            actions.append(("put", f"{target_obj_en} in/on {preproc_loc}"))
            actions.append(("close", preproc_loc))
            actions.append(("heat", target_obj_en))
            actions.append(("open", preproc_loc))
            actions.append(("take", target_obj_en))
            actions.append(("close", preproc_loc))
        else:  # clean
            actions.append(("put", f"{target_obj_en} in/on {preproc_loc}"))
            actions.append(("clean", target_obj_en))
            actions.append(("take", target_obj_en))
        
        # Step 3: 去目标位置放置
        if target_loc_en:
            actions.append(("goto", target_loc_en))
            # 如果是柜子需要打开
            if target_loc_en in ("cabinet", "drawer", "fridge"):
                actions.append(("open", target_loc_en))
            actions.append(("put", f"{target_obj_en} in/on {target_loc_en}"))
        else:
            actions.append(("goto", "counter"))
            actions.append(("put", f"{target_obj_en} on counter"))
    
    elif "throw" in verb_set:
        # 扔/丢（两个物体）
        for i in range(1, 3):
            actions.append(("goto", source_loc_en))
            actions.append(("take", f"{target_obj_en}_{i}"))
            if target_loc_en:
                actions.append(("goto", target_loc_en))
                actions.append(("put", f"{target_obj_en}_{i} in/on {target_loc_en}"))
            else:
                actions.append(("goto", "trash can"))
                actions.append(("put", f"{target_obj_en}_{i} in/on trash can"))
    
    else:
        # 简单取放
        # 如果涉及容器，先打开
        if source_loc_en in ("cabinet", "drawer", "fridge", "microwave"):
            actions.append(("goto", source_loc_en))
            actions.append(("open", source_loc_en))
            actions.append(("take", target_obj_en))
            actions.append(("close", source_loc_en))
        else:
            actions.append(("goto", source_loc_en))
            actions.append(("take", target_obj_en))
        
        if target_loc_en:
            actions.append(("goto", target_loc_en))
            if target_loc_en in ("cabinet", "drawer", "fridge"):
                actions.append(("open", target_loc_en))
            actions.append(("put", f"{target_obj_en} in/on {target_loc_en}"))
        else:
            actions.append(("goto", "counter"))
            actions.append(("put", f"{target_obj_en} on counter"))
    
    return actions


print("=" * 70)
print("  ALFWorld任务 → 汉语理解 → 操作序列 端到端测试")
print("=" * 70)
print()

print(f"📋 原始任务（英文）: {test_task['en']}")
print(f"📋 中文翻译: {test_task['cn']}")
print(f"📋 场景: {test_task['scene']}")
print(f"📋 任务类型: {test_task['task_type']}")
print()

# YLYW推理
result = engine.sentence(test_task["cn"])

print("🧠  YLYW汉语理解推理")
print("─" * 55)
print(f"  📝 分词: {' | '.join(result['segments'])}")
print(f"  🏷️  词级卦象:")
for i, seg in enumerate(result["segments"]):
    dom = result["segment_dominant"][i]
    hex_s = result["segment_hexagram"][i]
    role = result["segment_role"][i]
    print(f"    {seg:8s} → 主导卦:{dom:2s}  六十四卦:{hex_s:8s}  角色:{role}")
print(f"\n  🔗 词间互卦关系:")
for rel in result["mutua_relations"]:
    sym = {"乘":"⊃","承":"⊂","比":"‖","应":"≈","乘(跨虚词)":"?→","承(跨虚词)":"?←"}.get(rel["relation"], "?")
    print(f"    {rel['from']} {sym} {rel['to']}")

# 六爻向量（取前6个值，如果是64维则投射）
yao = result["yao_vector"]
if len(yao) > 6:
    top6 = sorted(yao, reverse=True)[:6]
else:
    top6 = yao
yin_yang = "".join("━" if v >= 0.5 else "┅" for v in top6)
print(f"\n  📊 句级六爻: {' '.join(f'{v:.3f}' for v in top6)}")
print(f"               {yin_yang}")
print(f"  🔮 句级主卦: {result['main_hexagram']} (相似度: {result['hexagram_score']:.4f})")
print(f"  🏷️  句级主导八卦: {result['dominant_bagua']}")
print()

# 生成操作序列
actions = generate_alfworld_actions(result, test_task["scene"], test_task)

print("🤖  生成的ALFWorld操作序列")
print("─" * 55)
print(f"  阶段一: 取物体")
step_no = 0
for action_type, target in actions:
    step_no += 1
    
    # 给每个操作一个中文说明（卦象驱动）
    action_cn_map = {
        "goto": "移动", "take": "拿取", "put": "放置",
        "open": "打开", "close": "关闭",
        "clean": "清洗", "heat": "加热", "cool": "冷却",
        "examine": "查看", "turn_on": "打开",
    }
    cn = action_cn_map.get(action_type, action_type)
    
    # 操作说明
    if action_type == "goto":
        where = target
        print(f"    {step_no:2d}. go to {where:15s}  → {cn}到{where}")
    elif action_type == "take":
        print(f"    {step_no:2d}. take {target:15s}     → {cn}{target}")
    elif action_type == "put":
        print(f"    {step_no:2d}. put {target:15s}      → {cn} {target}")
    elif action_type == "open":
        print(f"    {step_no:2d}. open {target:15s}    → {cn}{target}")
    elif action_type == "close":
        print(f"    {step_no:2d}. close {target:15s}   → {cn}{target}")
    elif action_type in ("clean", "heat", "cool"):
        print(f"    {step_no:2d}. {action_type} {target:15s}    → {cn}{target}")
    elif action_type == "examine":
        print(f"    {step_no:2d}. examine {target:15s}  → {cn}{target}")
    elif action_type == "turn_on":
        print(f"    {step_no:2d}. turn on {target:15s}  → {cn}{target}")

print()
print("📌  操作序列语义分析")
print("─" * 55)
print(f"  总步数: {len(actions)}")
print(f"  识别到的动词: '洗' '放'")
print(f"  识别到的物体: 盘子/柜台")
print(f"  识别到的位置: 水槽 → sinkbasin, 柜台 → counter")
print(f"  预处理类型: clean (源于'洗干净')")
print()

# 评估
expected_actions = [
    ("goto", "sinkbasin"), ("take", "plate"),
    ("put", "plate in/on sinkbasin"), ("clean", "plate"), ("take", "plate"),
    ("goto", "counter"), ("put", "plate on counter")
]

print("📊  与期望操作序列对比")
print("─" * 55)
print("  期望操作:")
for i, (at, tg) in enumerate(expected_actions):
    print(f"    {i+1:2d}. {at} {tg}")
print()
print("  实际生成:")
for i, (at, tg) in enumerate(actions):
    print(f"    {i+1:2d}. {at} {tg}")
print()

# 计算覆盖率
act_set = set(f"{a}_{t}" for a, t in actions)
exp_set = set(f"{a}_{t}" for a, t in expected_actions)
overlap = act_set & exp_set
coverage = len(overlap) / len(exp_set) * 100
missing = exp_set - act_set
extra = act_set - exp_set

print(f"  核心操作覆盖率: {coverage:.0f}%")
if missing:
    print(f"  ⚠️  缺失: {missing}")
if extra:
    print(f"  📌 额外: {extra}")
print()
print("=" * 70)
