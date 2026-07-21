#!/usr/bin/env python3
"""
测试：递归YLYW汉语理解引擎 → ALFWorld任务分解

从ALFWorld中选取典型任务，看汉语理解引擎能否自动分解为子任务序列。

测试用例覆盖6种任务类型：
1. pick_and_place_simple      — 简单取放
2. pick_clean_then_place      — 清洗后放置
3. pick_heat_then_place       — 加热后放置
4. pick_cool_then_place       — 冷却后放置
5. look_at_obj_in_light       — 照明下观察
6. pick_two_obj_and_place     — 取两个物体放置

每个测试包括：
  - 中文任务描述
  - 场景上下文
  - 期望的ALFWorld动作序列（机器可执行）
  - YLYW推理结果
"""

import sys
import os

# 确保可以导入hanzi_engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ================================================================
# ALFWorld任务 → 中文描述
# ================================================================

TEST_TASKS = [
    # ── 类型1: pick_and_place_simple ──
    {
        "id": 1,
        "type": "pick_and_place_simple",
        "scene": "厨房。有一个柜台(counter)、一个桌子(table)、一个冰箱(fridge)。桌子上有一个苹果。",
        "task": "把苹果放到柜台上",
        "task_en": "Put an apple on the counter.",
        "expected_subtasks": [
            "去桌子(go to table)",
            "拿苹果(take apple)",
            "去柜台(go to counter)",
            "放苹果(put apple on counter)",
        ],
    },
    # ── 类型2: pick_clean_then_place ──
    {
        "id": 2,
        "type": "pick_clean_then_place",
        "scene": "厨房。有一个水槽(sinkbasin)、一个柜台(counter)。水槽旁边有一个脏的盘子。",
        "task": "先把脏盘子洗干净，再放到柜台上",
        "task_en": "Wash the dirty plate and put it on the counter.",
        "expected_subtasks": [
            "去水槽(go to sinkbasin)",
            "拿盘子(take plate)",
            "洗盘子(clean plate with sinkbasin)",
            "拿盘子(take plate)",
            "去柜台(go to counter)",
            "放盘子(put plate on counter)",
        ],
    },
    # ── 类型3: pick_heat_then_place ──
    {
        "id": 3,
        "type": "pick_heat_then_place",
        "scene": "厨房。有一个微波炉(microwave)、一个冰箱(fridge)。冰箱里有食物。",
        "task": "把食物加热后放到台子上",
        "task_en": "Heat the food and put it on the counter.",
        "expected_subtasks": [
            "去冰箱(go to fridge)",
            "打开冰箱(open fridge)",
            "拿食物(take food)",
            "去微波炉(go to microwave)",
            "打开微波炉(open microwave)",
            "放食物(put food in microwave)",
            "关闭微波炉(close microwave)",
            "加热食物(heat food with microwave)",
            "打开微波炉(open microwave)",
            "拿食物(take food)",
            "去台子(go to counter)",
            "放食物(put food on counter)",
        ],
    },
    # ── 类型4: pick_cool_then_place ──
    {
        "id": 4,
        "type": "pick_cool_then_place",
        "scene": "厨房。有一个冰箱(fridge)、一个碗柜(cabinet)。柜台上有一杯热咖啡。",
        "task": "把热咖啡冷却后放到碗柜里",
        "task_en": "Cool the hot coffee and put it in the cabinet.",
        "expected_subtasks": [
            "去柜台(go to counter)",
            "拿咖啡(take coffee)",
            "去冰箱(go to fridge)",
            "打开冰箱(open fridge)",
            "放咖啡(put coffee in fridge)",
            "关闭冰箱(close fridge)",
            "冷却咖啡(cool coffee with fridge)",
            "打开冰箱(open fridge)",
            "拿咖啡(take coffee)",
            "去碗柜(go to cabinet)",
            "打开碗柜(open cabinet)",
            "放咖啡(put coffee in cabinet)",
        ],
    },
    # ── 类型5: look_at_obj_in_light ──
    {
        "id": 5,
        "type": "look_at_obj_in_light",
        "scene": "卧室。有一张桌子(desk)、一个台灯(desk lamp)。桌子上有一个杯子。",
        "task": "打开台灯，看看杯子",
        "task_en": "Turn on the desk lamp and look at the mug.",
        "expected_subtasks": [
            "去桌子(go to desk)",
            "打开台灯(turn on desk lamp)",
            "看杯子(examine mug using lamp light)",
        ],
    },
    # ── 类型6: pick_two_obj_and_place ──
    {
        "id": 6,
        "type": "pick_two_obj_and_place",
        "scene": "浴室。有一个垃圾桶(trash can)、一个洗手台。洗手台上有两块肥皂。",
        "task": "把两块肥皂都扔到垃圾桶里",
        "task_en": "Throw both bars of soap in the trash can.",
        "expected_subtasks": [
            "去洗手台(go to sinkbasin)",
            "拿肥皂1(take soap 1)",
            "去垃圾桶(go to trash can)",
            "扔肥皂1(put soap 1 in trash can)",
            "去洗手台(go to sinkbasin)",
            "拿肥皂2(take soap 2)",
            "去垃圾桶(go to trash can)",
            "扔肥皂2(put soap 2 in trash can)",
        ],
    },
    # ── 场景包含 closed container ──
    {
        "id": 7,
        "type": "pick_and_place_simple (closed container)",
        "scene": "客厅。有一个抽屉(drawer)、一个架子(shelf)。抽屉里有一支笔。",
        "task": "把抽屉里的笔拿出来放到架子上",
        "task_en": "Take the pencil from the drawer and put it on the shelf.",
        "expected_subtasks": [
            "去抽屉(go to drawer)",
            "打开抽屉(open drawer)",
            "拿笔(take pencil)",
            "去架子(go to shelf)",
            "放笔(put pencil on shelf)",
        ],
    },
    # ── 复杂指令：包含状语/补语 ──
    {
        "id": 8,
        "type": "pick_clean_then_place (带虚词)",
        "scene": "厨房。水槽(sinkbasin)边有一个脏碗。",
        "task": "把脏碗洗干净后放到架子上",
        "task_en": "Wash the dirty bowl and put it on the shelf.",
        "expected_subtasks": [
            "去水槽(go to sinkbasin)",
            "拿碗(take bowl)",
            "洗碗(clean bowl with sinkbasin)",
            "拿碗(take bowl)",
            "去架子(go to shelf)",
            "放碗(put bowl on shelf)",
        ],
    },
    # ── 跨域场景：ALFWorld中的实际失败场景 ──
    {
        "id": 9,
        "type": "pick_cool_then_place (实际场景)",
        "scene": "厨房。冰箱(fridge)在餐桌旁边。餐桌上有一杯热牛奶。需要把牛奶冷却后放到柜子里。",
        "task": "把热牛奶冷却后放到柜子里",
        "task_en": "Put a chilled milk in the cabinet.",
        "expected_subtasks": [
            "去餐桌(go to table)",
            "拿牛奶(take milk)",
            "去冰箱(go to fridge)",
            "打开冰箱(open fridge)",
            "放牛奶(put milk in fridge)",
            "关闭冰箱(close fridge)",
            "冷却牛奶(cool milk with fridge)",
            "打开冰箱(open fridge)",
            "拿牛奶(take milk)",
            "去柜子(go to cabinet)",
            "打开柜子(open cabinet)",
            "放牛奶(put milk in cabinet)",
        ],
    },
]


# ================================================================
# 评估：YLYW引擎输出 → 动作序列映射
# ================================================================

def task_to_actions(task_desc: str, scene: str) -> list:
    """
    核心：将汉字引擎的输出映射为ALFWorld可执行的动作序列。

    基于YLYW的卦象推理，构造任务分解。
    输入：任务描述 + 场景上下文
    输出：有序的动作列表
    """
    result = engine.sentence(task_desc)

    # 从卦象推理出任务类型
    hexagram = result["main_hexagram"]
    segments = result["segments"]
    rels = result["mutua_relations"]
    interpretation = result["interpretation"]

    # 卦象 → 任务类型映射
    HEAT_HEX = {"离", "火风鼎", "火天大有", "火地晋", "天火同人"}
    COOL_HEX = {"坎", "水", "水天需", "水地比", "天水讼"}
    CLEAN_HEX = {"坎", "水", "水山蹇", "水风井"}
    LOOK_HEX = {"离", "明", "火"}
    OPEN_HEX = {"兑", "天泽履", "泽天夬"}
    CLOSE_HEX = {"艮", "山"}
    PLACE_HEX = {"坤", "地", "山天大畜"}

    actions = []

    def get_objects(result) -> list:
        """从分词结果提取物体名词"""
        objs = []
        for i, seg in enumerate(result["segments"]):
            role = result["segment_role"][i]
            if role == "物体":
                objs.append(seg)
        return objs

    def get_verbs(result) -> list:
        """提取动作动词"""
        verbs = []
        for i, seg in enumerate(result["segments"]):
            role = result["segment_role"][i]
            if role == "动作":
                verbs.append(seg)
        return verbs

    objects = get_objects(result)
    verbs = get_verbs(result)

    # 解析scene提取位置信息
    known_locations = []
    for loc_key in ["柜台","桌子","冰箱","水槽","微波","碗柜","柜子","架子","抽屉","台子","餐桌","洗手台","垃圾桶"]:
        if loc_key in scene:
            known_locations.append(loc_key)

    # === 生成动作序列 ===
    # 规则引擎：基于动词和物体生成ALFWorld动作

    verb_actions = {
        "拿": "take", "取": "take", "拿取": "take",
        "放": "put", "放回": "put", "放入": "put", "放到": "put",
        "洗": "clean", "清洗": "clean", "清洁": "clean",
        "热": "heat", "加热": "heat",
        "冷": "cool", "冷却": "cool",
        "看": "examine", "查看": "examine", "检查": "examine",
        "打开": "open", "开": "open",
        "关闭": "close", "关": "close", "关上": "close",
        "扔": "put", "丢": "put",
        "找": "find", "寻找": "find",
    }

    # 确定目标物体
    target_obj = objects[0] if objects else "物体"

    # 查找目标位置
    target_loc = None
    for rel in rels:
        if "放" in rel["to"] or "到" in rel["to"] or "里" in rel["to"]:
            for loc in known_locations:
                if loc in rel["to"]:
                    target_loc = loc
                    break
    if not target_loc:
        # 尝试从rels推断目标位置
        for seg in reversed(result["segments"]):
            for loc in known_locations:
                if loc in seg:
                    target_loc = loc
                    break
            if target_loc:
                break

    # 确定起始位置
    start_loc = None
    for rel in rels:
        if "从" in rel.get("from", "") or "里" in rel.get("from", ""):
            for loc in known_locations:
                if loc in rel["from"]:
                    start_loc = loc
                    break

    # === 构造动作序列 ===
    # 1. 先找出物体（如果不在视野中）
    # 2. 如果需要操作，先找到对应位置
    # 3. 执行清洗/加热/冷却
    # 4. 移动并放置

    # 判断是否有预处理（洗/热/冷）
    has_preprocess = any(v in ("洗","清洗","清洁","热","加热","冷","冷却") for v in verbs)
    # 判断是打开还是关闭
    is_open = any(v in ("打开","开") for v in verbs)
    is_close = any(v in ("关闭","关","关上") for v in verbs)
    # 判断是否包含"找"
    need_find = any(v in ("找","寻找") for v in verbs)
    # 判断是否为观察任务
    is_look = any(v in ("看","查看","检查","瞧瞧") for v in verbs) or any(h in hexagram for h in LOOK_HEX)
    # 判断是取两个还是多个
    is_two = "两" in task_desc or "二" in task_desc or "两个" in task_desc

    # 先找物体（如果需要）
    if not start_loc and known_locations:
        start_loc = known_locations[0]

    # 动作生成核心逻辑
    if is_look:
        # 观察任务
        actions.append(f"go to {known_locations[0]}" if known_locations else "go to desk")
        # 如果是灯，先打开
        if any(h in hexagram for h in ["离"]):
            actions.append("turn on lamp")
        actions.append(f"examine {target_obj}")

    elif is_open:
        # 打开任务
        actions.append(f"go to {target_loc or known_locations[0]}")
        actions.append(f"open {target_loc or 'container'}")

    elif is_close:
        # 关闭任务
        actions.append(f"go to {target_loc or known_locations[0]}")
        actions.append(f"close {target_loc or 'container'}")

    elif has_preprocess:
        # 清洗/加热/冷却 + 放置
        # 确定预处理类型
        preproc_type = None
        for v in verbs:
            if v in ("洗","清洗","清洁"):
                preproc_type = "clean"
                break
            elif v in ("热","加热"):
                preproc_type = "heat"
                break
            elif v in ("冷","冷却"):
                preproc_type = "cool"
                break

        preproc_loc_map = {
            "clean": "sinkbasin",
            "heat": "microwave",
            "cool": "fridge",
        }
        preproc_loc = preproc_loc_map.get(preproc_type, "sinkbasin")

        # 1. 去拿物体
        if start_loc:
            actions.append(f"go to {start_loc}")
            if "抽屉" in scene or "柜" in scene:
                if start_loc == "抽屉" or start_loc == "柜子":
                    actions.append(f"open {start_loc}")
        actions.append(f"take {target_obj}")

        # 2. 去预处理
        actions.append(f"go to {preproc_loc}")
        actions.append(f"put {target_obj} in/on {preproc_loc}")

        if preproc_type == "cool":
            actions.append(f"close {preproc_loc}")  # 关闭冰箱门
            actions.append(f"cool {target_obj} with {preproc_loc}")
            actions.append(f"open {preproc_loc}")
        elif preproc_type == "heat":
            actions.append(f"close {preproc_loc}")  # 关闭微波炉门
            actions.append(f"heat {target_obj} with {preproc_loc}")
            actions.append(f"open {preproc_loc}")
        else:
            actions.append(f"clean {target_obj} with {preproc_loc}")

        actions.append(f"take {target_obj} from {preproc_loc}")

        # 3. 去目标位置放置
        if target_loc:
            actions.append(f"go to {target_loc}")
            # 检查目标容器是否需要打开
            if any(c in str(target_loc) for c in ["柜","屉"]):
                actions.append(f"open {target_loc}")
            actions.append(f"put {target_obj} in/on {target_loc}")
        else:
            actions.append(f"put {target_obj} in/on counter")

    else:
        # 简单取放
        if is_two:
            # 取两个物体
            for i in range(1, 3):
                obj_i = f"{target_obj}_{i}"
                if start_loc:
                    actions.append(f"go to {start_loc}")
                actions.append(f"take {obj_i}")
                if target_loc:
                    actions.append(f"go to {target_loc}")
                    actions.append(f"put {obj_i} in/on {target_loc}")
                else:
                    actions.append(f"put {obj_i} in/on bin")
        else:
            # 简单取放
            if start_loc:
                actions.append(f"go to {start_loc}")
                # 如果在容器中，先打开
                if any(c in str(start_loc) for c in ["抽屉","柜"]):
                    actions.append(f"open {start_loc}")
            actions.append(f"take {target_obj}")
            if target_loc:
                actions.append(f"go to {target_loc}")
                # 目标容器可能需要打开
                if any(c in str(target_loc) for c in ["柜","屉","箱"]):
                    actions.append(f"open {target_loc}")
                actions.append(f"put {target_obj} in/on {target_loc}")
            else:
                actions.append(f"go to counter")
                actions.append(f"put {target_obj} on counter")

    return actions, result


# ================================================================
# 主测试循环
# ================================================================

def evaluate(actions, expected):
    """评估生成的action序列是否覆盖了期望的关键步骤"""
    exp_set = set(expected)
    act_set = set(actions)
    overlap = exp_set & act_set
    coverage = len(overlap) / len(exp_set) * 100 if exp_set else 0
    missing = exp_set - act_set
    extra = act_set - exp_set
    return coverage, missing, extra


print("=" * 70)
print("  递归YLYW 汉语理解引擎 — ALFWorld任务规划测试")
print("=" * 70)
print()

total_score = 0
for task in TEST_TASKS:
    task_id = task["id"]
    task_type = task["type"]
    scene = task["scene"]
    task_desc = task["task"]
    expected = task["expected_subtasks"]

    print("-" * 70)
    print(f"📋 任务{task_id}: [{task_type}]")
    print(f"   场景: {scene}")
    print(f"   指令: {task_desc}")
    print()

    # YLYW推理
    actions, result = task_to_actions(task_desc, scene)

    # 打印YLYW推理结果
    print(f"  🔮 YLYW句级主卦: {result['main_hexagram']} ({result['hexagram_score']:.3f})")
    print(f"  📝 分词: {' | '.join(result['segments'])}")
    print(f"  🏷️  词卦: ", end="")
    for i, seg in enumerate(result["segments"]):
        print(f"{seg}[{result['segment_dominant'][i]}]", end=" ")
    print()
    print(f"  🔗 词间互卦: ", end="")
    for rel in result["mutua_relations"][:3]:
        print(f"{rel['from']}{rel['relation'].replace('(跨虚词)','')}{rel['to']}", end=" ")
    print()
    print(f"  📊 六爻: ", end="")
    for v in result["yao_vector"]:
        print(f"{v:.3f}", end=" ")
    print()

    # 期望vs实际
    print(f"\n  ✅ 期望动作序列 ({len(expected)}步):")
    for i, a in enumerate(expected):
        print(f"    {i+1}. {a}")
    print(f"\n  🤖 YLYW生成的ALFWorld动作 ({len(actions)}步):")
    for i, a in enumerate(actions):
        print(f"    {i+1}. {a}")

    # 评估
    coverage, missing, extra = evaluate(actions, expected)
    print(f"\n  📈 覆盖率: {coverage:.0f}%")
    if missing:
        print(f"  ⚠️  缺失: {missing}")
    if extra:
        print(f"  📌 额外: {extra}")

    total_score += coverage

    print()

print("=" * 70)
avg_score = total_score / len(TEST_TASKS)
print(f"📊 平均覆盖率: {avg_score:.1f}%")
print(f"📊 总任务数: {len(TEST_TASKS)}")
print(f"📊 通过(≥60%): {sum(1 for t in TEST_TASKS if evaluate(task_to_actions(t['task'], t['scene'])[0], t['expected_subtasks'])[0] >= 60)}/{len(TEST_TASKS)}")
print("=" * 70)
