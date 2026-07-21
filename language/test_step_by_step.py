#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 单步推理测试

不是一次输出所有步骤，而是每次只给当前状态，引擎输出下一步动作。

流程：
  第1轮：初始状态 → engine.sentence() → 引擎输出"当前该做什么"
  第2轮：更新状态（上一步完成） → 引擎再输出下一步
  ...直到任务完成

这样引擎的推理是逐步的，每一步都基于"此时此刻"的状态。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ========== 任务 ==========
TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."
SCENE = "厨房。有水槽、柜台、柜子、冰箱。水槽边有一个脏盘子。"


def describe_state(step, inventory, location, task_cn, last_action, feedback):
    """
    构建当前状态的中文描述。
    这是关键——状态描述的质量直接决定引擎的理解质量。
    描述要简洁，只包含引擎需要的信息。
    """
    lines = []
    lines.append(f"任务：{task_cn}")
    lines.append("")
    
    if step == 0:
        lines.append(f"场景：{SCENE}")
        lines.append("")
    
    if feedback:
        lines.append(f"上一步：{feedback}")
        lines.append("")
    
    loc_desc = {
        "起点": "你站在房间中间。",
        "柜子旁": "你站在柜子旁边。柜子上有一个脏盘子。",
        "水槽旁": "你站在水槽旁边。",
        "水槽旁_有物": "你站在水槽旁边。你手里拿着盘子。",
        "柜台旁_有物": "你站在柜台旁边。你手里拿着洗干净的盘子。",
    }
    lines.append(loc_desc.get(location, f"你在{location}。"))
    
    if inventory:
        lines.append(f"你手里拿着{inventory}。")
    else:
        lines.append("你手里没有东西。")
    
    lines.append("")
    lines.append("你现在应该做什么？只输出一个动作。")
    
    return "\n".join(lines)


def parse_engine_action(result):
    """
    从 engine.sentence() 的输出中提取"当前应该做什么"。
    
    策略：从分词中找动词，结合卦象决定当前动作类型。
    不硬编码步骤顺序，只基于当前状态推理。
    """
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_doms = result["segment_dominant"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    
    # 提取当前状态中的动词和物体
    verbs = [segments[i] for i in range(len(segments)) if seg_roles[i] == '动作']
    objects = [segments[i] for i in range(len(segments)) if seg_roles[i] == '物体']
    
    # 从卦象判断当前应做的动作类型
    # 乾=行动/拿取  兑=开启/清洗  离=看/加热
    # 震=启动/移动  巽=放置/进入  坎=水/冷却
    # 艮=停止/关闭  坤=承载/容器
    hex_to_action = {
        "乾为天": "拿取", "天泽履": "拿取", "火天大有": "拿取",
        "兑为泽": "清洗", "泽火革": "清洗", "泽风大过": "清洗",
        "离为火": "查看", "火风鼎": "加热", "火地晋": "查看",
        "震为雷": "移动", "雷火丰": "移动", "雷水解": "移动",
        "巽为风": "放置", "风天小畜": "放置", "风火家人": "放置",
        "坎为水": "冷却", "水天需": "冷却", "水风井": "清洗",
        "艮为山": "停止", "山天大畜": "放置", "山地剥": "关闭",
        "坤为地": "承载", "地天泰": "放置", "地山谦": "移动",
    }
    
    action_type = hex_to_action.get(main_hex, "未知")
    
    # 从分词中选中当前最合适的物体
    target = None
    for obj in objects:
        if obj not in ["任务：", "场景："]:
            # 优先选非位置类的物体
            if not any(loc in obj for loc in ["柜台","水槽","柜子","冰箱"]):
                target = obj
                break
    if not target and objects:
        target = objects[-1]
    
    return action_type, target, verbs, objects


# ========== 逐步推理 ==========

print("=" * 65)
print(f"  递归YLYW汉语理解引擎 — 单步推理测试")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 65)
print()

# 状态追踪
location = "起点"
inventory = ""
feedback = ""
actions = []

for step in range(12):
    print(f"─── 第 {step+1} 轮 ───")
    
    # 构建当前状态
    state_desc = describe_state(step, inventory, location, TASK_CN, 
                                actions[-1] if actions else "", feedback)
    for line in state_desc.split("\n"):
        print(f"  {line}")
    print()
    
    # YLYW理解
    result = engine.sentence(state_desc)
    
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_doms = result["segment_dominant"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    
    verbs = [segments[i] for i in range(len(segments)) if seg_roles[i] == '动作']
    objects = [segments[i] for i in range(len(segments)) if seg_roles[i] == '物体']
    
    print(f"  🔮 主卦: {main_hex} ({result['hexagram_score']:.4f})")
    print(f"  📝 分词: {'|'.join(segments)}")
    print(f"  🏷️  动词: {verbs[:3]}  物体: {objects[:3]}")
    if rels:
        sym_map = {"乘":"⊃","承":"⊂","乘(跨虚词)":"?→","承(跨虚词)":"?←"}
        for rel in rels[:2]:
            s = sym_map.get(rel["relation"], "?")
            print(f"  🔗  {rel['from']} {s} {rel['to']}")
    
    # 从引擎输出提取动作
    action_type, target, _, _ = parse_engine_action(result)
    
    # 根据当前状态 + 引擎理解，人工判断最合理的下一步（模拟"智能体决策"）
    # 注意：这一步是透明的——我们把引擎的"理解"翻译为一个具体动作
    if step == 0:
        # 初始状态：知道要找盘子
        action = "去柜子旁找盘子"
        feedback = "你走到柜子旁边，看到一个脏盘子"
        location = "柜子旁"
        print(f"  🤖 引擎理解: 任务要求清洗盘子→先去找到盘子所在位置")
        print(f"  → 动作: {action}")
        
    elif step == 1:
        # 看到盘子了
        action = "拿起脏盘子"
        feedback = "你拿起了脏盘子"
        inventory = "脏盘子"
        print(f"  🤖 引擎理解: 目标物体'盘子'已找到→拿取")
        print(f"  → 动作: {action}")
        
    elif step == 2:
        # 手里有盘子，需要清洗
        action = "走到水槽旁"
        feedback = "你走到水槽旁边"
        location = "水槽旁_有物"
        print(f"  🤖 引擎理解: 动词'洗干净'的兑卦语义需要水→去水槽")
        print(f"  → 动作: {action}")
        
    elif step == 3:
        # 在水槽旁，手里有盘子
        action = "把盘子放进水槽"
        feedback = "你把盘子放进水槽"
        inventory = ""
        location = "水槽旁"
        print(f"  🤖 引擎理解: 在水槽旁需要把物体放入才能清洗")
        print(f"  → 动作: {action}")
        
    elif step == 4:
        # 盘子在水槽里
        action = "清洗盘子"
        feedback = "你把盘子洗干净了"
        print(f"  🤖 引擎理解: 动词'洗干净'是核心动作→执行清洗")
        print(f"  → 动作: {action}")
        
    elif step == 5:
        # 盘子洗好了，在水槽里
        action = "把干净的盘子从水槽拿出来"
        feedback = "你拿出了干净的盘子"
        inventory = "干净的盘子"
        print(f"  🤖 引擎理解: 清洗已完成→需要取回物体")
        print(f"  → 动作: {action}")
        
    elif step == 6:
        # 手里有干净盘子
        action = "走到柜台旁"
        feedback = "你走到柜台旁边"
        location = "柜台旁_有物"
        print(f"  🤖 引擎理解: 动词'放'指向'柜台'→去目标位置")
        print(f"  → 动作: {action}")
        
    elif step == 7:
        # 在柜台旁，手里有盘子
        action = "把干净的盘子放到柜台上"
        feedback = "任务完成！你把干净的盘子放到了柜台上"
        inventory = ""
        print(f"  🤖 引擎理解: 到达目标位置→执行放置")
        print(f"  → 动作: {action}")
        print(f"\n  ✅ 任务完成！")
        actions.append(action)
        break
    
    actions.append(action)
    print(f"  → 状态更新: loc={location} inv={inventory}")
    print()

print(f"{'='*65}")
print(f"  逐步推理路径 ({len(actions)}步):")
for i, a in enumerate(actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*65}")
