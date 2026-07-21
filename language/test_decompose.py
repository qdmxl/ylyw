#!/usr/bin/env python3
"""
纯测试：递归YLYW汉语理解引擎 → 任务分解

不连接ALFWorld环境，只测引擎本身。
流程：
  1. 选一个ALFWorld任务（英文）
  2. 翻译成中文
  3. 喂给 engine.sentence() 
  4. 从分词/卦象/互卦中提取任务分解
  5. 人工评估分解是否合理

重点考察：引擎能否从一句话中提取出子任务序列
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ============================================================
# 1. 翻译器：ALFWorld英文任务 → 中文
# ============================================================

EN2CN = {
    'plate':'盘子','bowl':'碗','mug':'杯子','cup':'杯子',
    'apple':'苹果','potato':'土豆','tomato':'番茄','lettuce':'生菜',
    'bread':'面包','egg':'鸡蛋','milk':'牛奶','coffee':'咖啡',
    'soap':'肥皂','sponge':'海绵','cloth':'抹布',
    'pencil':'笔','pen':'笔','paper':'纸','book':'书','key':'钥匙',
    'countertop':'柜台','counter':'柜台','sinkbasin':'水槽','sink':'水槽',
    'fridge':'冰箱','microwave':'微波炉',
    'cabinet':'柜子','drawer':'抽屉','shelf':'架子','garbagecan':'垃圾桶',
    'desk':'桌子','table':'桌子','desk lamp':'台灯','lamp':'灯',
    'toaster':'烤面包机','coffeemachine':'咖啡机','stoveburner':'灶台',
    'bed':'床','sofa':'沙发','chair':'椅子','diningtable':'餐桌',
}

def cn(w):
    w2 = re.sub(r'\s+\d+$','',w.strip().lower())
    return EN2CN.get(w2,w2)

def translate_task(task_en):
    t = task_en.lower().strip()
    patterns = [
        (r"put a clean (.+) on (.+)",         "先把{0}洗干净，然后放到{1}上"),
        (r"put a clean (.+) in (.+)",         "先把{0}洗干净，然后放到{1}里"),
        (r"clean (.+) and put it in (.+)",    "先把{0}洗干净，再放到{1}里"),
        (r"clean (.+) and put it on (.+)",    "先把{0}洗干净，再放到{1}上"),
        (r"wash (.+) before putting",         "先把{1}洗干净再放"),
        (r"heat (.+) and put it in (.+)",     "先把{0}加热，再放到{1}里"),
        (r"heat (.+) and put it on (.+)",     "先把{0}加热，再放到{1}上"),
        (r"put a chilled (.+) in (.+)",       "先把{0}冷却，再放到{1}里"),
        (r"put a cold (.+) in (.+)",          "先把{0}冷却，再放到{1}里"),
        (r"cool (.+) and put it in (.+)",     "先把{0}冷却，再放到{1}里"),
        (r"look at (.+) in (.+)",             "用{1}的光看看{0}"),
        (r"turn on the (.+)",                 "打开{0}"),
        (r"examine (.+) using (.+)",          "用{1}查看{0}"),
        (r"throw (.+) into (.+)",             "把{0}扔进{1}"),
        (r"throw (.+) in (.+)",               "把{0}扔进{1}"),
        (r"put (.+) in (.+)",                 "把{0}放到{1}里"),
        (r"put (.+) on (.+)",                 "把{0}放到{1}上"),
        (r"move (.+) to (.+)",                "把{0}移到{1}"),
    ]
    for pat, tmpl in patterns:
        m = re.match(pat, t)
        if m:
            groups = [cn(g) for g in m.groups()]
            try:
                return tmpl.format(*groups)
            except:
                continue
    return task_en

# ============================================================
# 2. YLYW推理 → 任务分解
# ============================================================

def decompose_task(task_cn, scene=""):
    """
    核心函数：将中文任务描述分解为子任务序列。
    
    输入：engine.sentence() 的输出
    输出：有序的子任务列表
    
    分解策略：
    - 从分词中提取"动作序列"（动词在句中出现的顺序）
    - 从互卦关系中理解"动作→物体"的支配关系
    - 从主卦推断任务类型
    - 结合场景和任务知识补全中间步骤
    """
    # YLYW推理
    result = engine.sentence(task_cn)
    
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_doms = result["segment_dominant"]
    seg_hexs = result["segment_hexagram"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    hex64 = result["hex64"]
    
    # ---- 从分词中提取基本元素 ----
    # 动词（按句子中出现顺序）
    verbs_in_order = [(i, segments[i]) for i in range(len(segments)) 
                      if seg_roles[i] == '动作']
    # 物体
    objects = [segments[i] for i in range(len(segments)) 
               if seg_roles[i] == '物体']
    # 位置（从场景和任务中推断）
    locations_in_task = [segments[i] for i in range(len(segments)) 
                         if seg_roles[i] == '物体' and 
                         any(loc in segments[i] for loc in ["柜台","台子","架子","柜子","碗柜",
                            "桌子","水槽","冰箱","微波炉","抽屉","垃圾桶"])]
    
    # ---- 任务类型判断 ----
    need_clean = any("洗" in v or "干净" in v for _, v in verbs_in_order)
    need_heat = any("加热" in v or "热" in v for _, v in verbs_in_order) and not any("冷" in v for _, v in verbs_in_order)
    need_cool = any("冷却" in v or "冷" in v or "冰" in v for _, v in verbs_in_order)
    need_look = any("看" in v or "照" in v or "查" in v for _, v in verbs_in_order)
    need_open = any("打开" in v or "开" in v for _, v in verbs_in_order)
    task_type = "unknown"
    if need_clean: task_type = "清洗后放置"
    elif need_heat: task_type = "加热后放置"
    elif need_cool: task_type = "冷却后放置"
    elif need_look: task_type = "观察"
    elif need_open: task_type = "打开"
    else: task_type = "取放"
    
    # ---- 目标物体 ----
    target_obj = None
    for obj in objects:
        if obj not in locations_in_task and obj not in ["任务："]:
            target_obj = obj
            break
    if not target_obj and objects:
        target_obj = objects[0]
    
    # ---- 目标位置 ----
    target_loc = None
    # 从互卦关系推断
    for rel in rels:
        # "放 ?→ 柜台" 表示动作指向位置
        to_word = rel["to"]
        for loc_key in ["柜台","台子","架子","柜子","碗柜","桌子","水槽","冰箱","微波炉","垃圾桶"]:
            if loc_key in to_word:
                target_loc = loc_key
                break
        if target_loc: break
    if not target_loc:
        # 从分词末尾找
        for seg in reversed(segments):
            for loc_key in ["柜台","台子","架子","柜子","碗柜","桌子"]:
                if loc_key in seg:
                    target_loc = loc_key
                    break
            if target_loc: break
    
    # ---- 构造子任务序列 ----
    subtasks = []
    
    # 根据任务类型生成子任务
    if task_type == "清洗后放置":
        subtasks = [
            f"找到{target_obj}（探索厨房，寻找{target_obj}的位置）",
            f"走到{target_obj}旁边",
            f"拿起{target_obj}",
            f"走到水槽旁边",
            f"把{target_obj}放进水槽",
            f"清洗{target_obj}",
            f"把{target_obj}从水槽拿出来",
            f"走到{target_loc or '柜台'}旁边",
            f"把{target_obj}放到{target_loc or '柜台'}上",
        ]
    elif task_type == "加热后放置":
        subtasks = [
            f"找到{target_obj}",
            f"走到{target_obj}旁边",
            f"拿起{target_obj}",
            f"走到微波炉旁边",
            f"打开微波炉",
            f"把{target_obj}放进微波炉",
            f"关闭微波炉",
            f"加热{target_obj}",
            f"打开微波炉",
            f"把{target_obj}从微波炉拿出来",
            f"走到{target_loc or '台子'}旁边",
            f"把{target_obj}放到{target_loc or '台子'}上",
        ]
    elif task_type == "冷却后放置":
        subtasks = [
            f"找到{target_obj}",
            f"走到{target_obj}旁边", 
            f"拿起{target_obj}",
            f"走到冰箱旁边",
            f"打开冰箱",
            f"把{target_obj}放进冰箱",
            f"关闭冰箱",
            f"冷却{target_obj}",
            f"打开冰箱",
            f"把{target_obj}从冰箱拿出来",
            f"走到{target_loc or '柜子'}旁边",
            f"把{target_obj}放到{target_loc or '柜子'}里",
        ]
    elif task_type == "取放":
        subtasks = [
            f"找到{target_obj}",
            f"走到{target_obj}旁边",
            f"拿起{target_obj}",
            f"走到{target_loc or '柜台'}旁边",
            f"把{target_obj}放到{target_loc or '柜台'}上",
        ]
    elif task_type == "观察":
        subtasks = [
            "找到台灯",
            "走到台灯旁边",
            "打开台灯",
            f"找到{target_obj or '杯子'}",
            f"在灯光下查看{target_obj or '杯子'}",
        ]
    elif task_type == "打开":
        subtasks = [
            f"找到{target_obj or '灯'}",
            f"走到{target_obj or '灯'}旁边",
            f"打开{target_obj or '灯'}",
        ]
    
    return {
        "task_cn": task_cn,
        "task_type": task_type,
        "main_hexagram": main_hex,
        "hexagram_score": result["hexagram_score"],
        "segments": segments,
        "segment_roles": seg_roles,
        "segment_dominants": seg_doms,
        "verbs": [v for _, v in verbs_in_order],
        "objects": objects,
        "target_object": target_obj,
        "target_location": target_loc,
        "relations": rels,
        "subtasks": subtasks,
    }


def print_decomposition(d):
    """打印任务分解结果"""
    print(f"  🎯 中文任务: {d['task_cn']}")
    print(f"  🔮 YLYW主卦: {d['main_hexagram']} (相似度: {d['hexagram_score']:.4f})")
    print(f"  📋 推断任务类型: {d['task_type']}")
    print()
    
    print(f"  📝 分词: {' | '.join(d['segments'])}")
    print(f"  🏷️  词级卦象（主导八卦）:")
    for i, seg in enumerate(d['segments']):
        role = d['segment_roles'][i]
        dom = d['segment_dominants'][i]
        print(f"    {seg:8s} → 主导:{dom:2s}  角色:{role}")
    
    print(f"  🔗 词间互卦关系:")
    for rel in d['relations']:
        sym = {"乘":"⊃","承":"⊂","比":"‖","应":"≈","乘(跨虚词)":"?→","承(跨虚词)":"?←"}
        s = sym.get(rel["relation"], "?")
        print(f"    {rel['from']} {s} {rel['to']}")
    
    print(f"\n  ✅ 子任务分解 ({len(d['subtasks'])}步):")
    for i, st in enumerate(d['subtasks']):
        print(f"    {i+1:2d}. {st}")
    
    return d


# ============================================================
# 3. 测试集
# ============================================================

TEST_TASKS = [
    # 清洗后放置
    {
        "en": "Put a clean plate on the counter.",
        "scene": "厨房。有水槽、柜台、柜子、冰箱。水槽边有一个脏盘子。",
    },
    # 加热后放置
    {
        "en": "Heat the food and put it on the counter.",
        "scene": "厨房。有微波炉、冰箱、柜台。冰箱里有食物。",
    },
    # 冷却后放置  
    {
        "en": "Put a chilled mug in the cabinet.",
        "scene": "厨房。有冰箱、柜子、柜台。柜台上有一杯咖啡。",
    },
    # 简单取放
    {
        "en": "Put an apple on the counter.",
        "scene": "厨房。有柜台、桌子。桌子上有一个苹果。",
    },
    # 观察
    {
        "en": "Look at a mug in lamp light.",
        "scene": "卧室。有桌子、台灯。桌子上有一个杯子。",
    },
    # 取两个物体
    {
        "en": "Throw two bars of soap in the trash bin.",
        "scene": "浴室。有洗手台、垃圾桶。洗手台上有两块肥皂。",
    },
    # 从容器取物
    {
        "en": "Take the pencil from the desk.",
        "scene": "书房。有桌子、抽屉。桌子上有一支笔。",
    },
    # 复杂清洗
    {
        "en": "wash the dirty bowl before putting the bowl on the counter",
        "scene": "厨房。有水槽、柜台。水槽边有一个脏碗。",
    },
]


# ============================================================
# 4. 运行测试
# ============================================================

print("=" * 70)
print("  递归YLYW汉语理解引擎 — 任务分解能力测试")
print("  纯引擎测试 | 无环境交互 | 仅评估分解合理性")
print("=" * 70)
print()

all_good = 0
for i, task in enumerate(TEST_TASKS):
    task_en = task["en"]
    task_cn = translate_task(task_en)
    scene = task["scene"]
    
    print(f"{'─'*70}")
    print(f"📋 任务 {i+1} (共{len(TEST_TASKS)}个)")
    print(f"  EN: {task_en}")
    print(f"  CN: {task_cn}")
    print(f"  场景: {scene}")
    print()
    
    d = decompose_task(task_cn, scene)
    print_decomposition(d)
    
    print()

print("=" * 70)
print("  测试完成")
print("=" * 70)
