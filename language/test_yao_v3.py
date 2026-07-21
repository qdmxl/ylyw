#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 逐步决策 v3

关键洞察：当前engine.sentence()的六爻编码对状态变化不敏感，
因为它的64维映射是基于部首/字义的静态语义，不是基于"状态变化"。

正确的做法是：
  1. 用engine做**语义理解**（分词 + 卦象 + 互卦）——这它做得好
  2. 用**状态变量直接构造六爻** —— 反映实时状态变化
  3. 六爻驱动动作选择 —— 规则匹配

这样各司其职：引擎负责"理解任务语义"，状态六爻负责"感知进度变化"。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."


def build_yao_from_state(location, inventory, processed, step):
    """
    直接从状态变量构造六爻——这才是真正反映状态变化的"爻"。
    
    传统易经：每爻是当前状态的阴阳判断。
    这里：每爻是对应状态维度的归一化值(0~1)，>=0.5为阳。
    
    初爻(根基) = 手上有物品？ 0.1(空) / 0.7(有)
    二爻(位置) = 到处理位置？ 0.1(起点)/0.4(柜子)/0.7(水槽)/0.9(柜台)
    三爻(难度) = 任务进展？ 0.1~0.9 递增
    四爻(状态) = 物体已处理？ 0.2(未处理) / 0.8(已处理)
    五爻(重要度)= 接近完成？ 0.1~0.9 递增
    上爻(环境) = 环境就绪？ 0.3(未就绪) / 0.8(就绪)
    """
    # 初爻：手上是否有东西
    y0 = 0.7 if inventory else 0.1
    
    # 二爻：位置（是否到了该去的地方）
    loc_map = {"起点": 0.1, "柜子": 0.35, "水槽": 0.6, "柜台": 0.85}
    y1 = loc_map.get(location, 0.3)
    
    # 三爻：任务进展（大致的进度）
    progress = min(step / 10, 1.0)  # 0~1递增
    y2 = progress * 0.8 + 0.1
    
    # 四爻：物体是否已处理
    y3 = 0.8 if processed else 0.2
    
    # 五爻：是否接近完成（离放置还有多远）
    # 在柜台旁且有物=最高；起点=最低
    y4 = 0.1
    if location == "柜台" and inventory:
        y4 = 0.85
    elif location == "水槽" and processed and not inventory:
        y4 = 0.6
    elif location == "水槽" and processed:
        y4 = 0.45
    elif location == "柜子":
        y4 = 0.25
    
    # 上爻：环境是否就绪（柜台是否可达、水槽是否可用）
    y5 = 0.8 if location in ("水槽", "柜台") else 0.3
    
    return [y0, y1, y2, y3, y4, y5]


def yao_to_action(yao):
    """
    六爻 → 动作决策。
    
    规则（来自易经爻位语义 + 任务常识）：
      初爻阴(空手) ∩ 二爻低(未到位) → goto 探索
      初爻阴(空手) ∩ 二爻中(到位) ∩ 四爻阴(未处理) → take 拿取
      
      初爻阳(有物) ∩ 四爻阴(未处理) ∩ 二爻中(未到处理位置) → goto_preproc
      初爻阳(有物) ∩ 二爻高(到处理位置) ∩ 四爻阴(未处理) → put_in 放入
      
      初爻阴(已放入) ∩ 四爻阴(未处理) → process 处理
      初爻阴(已放入) ∩ 四爻阳(已处理) → take_out 取出
      
      初爻阳(有物) ∩ 四爻阳(已处理) ∩ 五爻低(未收尾) → goto_target
      初爻阳(有物) ∩ 四爻阳(已处理) ∩ 五爻高(收尾) ∩ 上爻阳(就绪) → put 放置
    """
    y0, y1, y2, y3, y4, y5 = yao
    
    # 空手
    if y0 < 0.5:
        if y1 < 0.5:
            return ("goto", "空手→探索找物体")
        else:
            return ("take", "空手到位→拿取")
    
    # 有物
    if y0 >= 0.5:
        # 物体未处理
        if y3 < 0.5:
            if y1 < 0.5:
                return ("goto_preproc", "有物未处理→去水槽")
            else:
                return ("put_in", "有物到位→放入设备")
        # 物体已处理
        else:
            if y4 < 0.5:
                return ("goto_target", "有物已处理→去柜台")
            else:
                return ("put", "就绪→放置")
    
    return ("goto", "兜底")


def get_actions(loc, inv, processed):
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
                actions = ["清洗盘子"]
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
        return "水槽", "", "脏盘子放进了水槽", False
    elif "清洗" in action:
        return "水槽", "", "盘子洗干净了", True
    elif "拿出来" in action:
        return "水槽", "干净盘子", "拿出了干净盘子", True
    elif "放到柜台" in action:
        return "柜台", "", "任务完成！", True
    elif "去柜子" in action:
        return "柜子", inv, "到柜子旁", processed
    elif "去水槽" in action:
        return "水槽", inv, "到水槽旁", processed
    elif "去柜台" in action:
        return "柜台", inv, "到柜台旁", processed
    return loc, inv, "没变化", processed


# ============================================================
# 主循环
# ============================================================

print("=" * 65)
print("  逐步决策 v3 — 状态六爻驱动")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 65)
print()

location = "起点"
inventory = ""
feedback = ""
processed = False
all_actions = []

for step in range(15):
    print(f"─── Step {step+1} ───")
    
    # 1. YLYW做语义理解（验证任务方向）
    state = f"任务：{TASK_CN}。现在在{location}，{'有'+inventory if inventory else '空手'}，{'已处理' if processed else '未处理'}。下一步做什么？"
    result = engine.sentence(state)
    main_hex = result["main_hexagram"]
    hex_score = result["hexagram_score"]
    bagua = result["dominant_bagua"]
    
    # 2. 状态六爻（反映实时变化）
    yao = build_yao_from_state(location, inventory, processed, step)
    
    # 3. 六爻驱动决策
    action_type, reason = yao_to_action(yao)
    
    # 4. 选具体动作
    available = get_actions(location, inventory, processed)
    action = None
    if action_type == "goto":
        action = "去柜子" if "去柜子" in available else (available[0] if available else None)
    elif action_type == "take":
        action = "拿起脏盘子" if "拿起脏盘子" in available else None
    elif action_type == "goto_preproc":
        action = "去水槽" if "去水槽" in available else None
    elif action_type == "put_in":
        action = "把盘子放进水槽" if "把盘子放进水槽" in available else None
    elif action_type == "process":
        action = "清洗盘子" if "清洗盘子" in available else None
    elif action_type == "take_out":
        action = "把盘子从水槽拿出来" if "把盘子从水槽拿出来" in available else None
    elif action_type == "goto_target":
        action = "去柜台" if "去柜台" in available else None
    elif action_type == "put":
        action = "把盘子放到柜台上" if "把盘子放到柜台上" in available else None
    
    if not action and available:
        action = available[0]
    if not action:
        action = "等待"
    
    # 输出
    labels = ["初(根基)","二(位置)","三(进展)","四(已处理)","五(收尾)","上(环境)"]
    yao_vis = "  ".join(f"{labels[i]}={'━' if yao[i]>=0.5 else '┅'}({yao[i]:.2f})" for i in range(6))
    print(f"  📋 状态: {location:4s} | {inventory or '空手':6s} | {'已处理' if processed else '未处理'}")
    print(f"  🔮 语义卦: {main_hex}({hex_score:.3f})")
    print(f"  📊 状态六爻:")
    print(f"    {yao_vis}")
    print(f"  🎯 决策: {action_type} ← {reason}")
    print(f"  🤖 动作: {action}")
    
    # 执行
    location, inventory, feedback, processed = apply(action, location, inventory, processed)
    all_actions.append(action)
    print(f"  📌 {feedback}")
    
    if "完成" in feedback:
        print(f"\n  ✅ 任务成功！")
        break
    print()

print(f"\n{'='*65}")
print(f"  动作序列 ({len(all_actions)}步):")
for i, a in enumerate(all_actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*65}")
