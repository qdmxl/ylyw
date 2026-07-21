#!/usr/bin/env python3
"""
六爻驱动逐步决策 — 最终版

架构：
  1. 状态六爻（独立构造）：反映实时状态变化，驱动动作选择
  2. 引擎语义层（YLYW）：校验方向，提供卦象和互卦作为决策参考
  3. 爻变检测：记录每轮六爻的变化，发现状态跃迁

这样各司其职——状态六爻负责"感知变化"，引擎负责"理解语义"。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

TASK_CN = "把盘子洗干净后放到柜台上"
TASK_EN = "Put a clean plate on the counter."

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 状态六爻构造
# ============================================================

def build_state_yao(location, inventory, processed, step):
    """
    六爻语义（时序版）：
      初爻(根基) = 当前持有状态   阴=空手(0.1)  阳=有物(0.7)
      二爻(位置) = 当前位置估值   起点(0.1)→柜子(0.35)→水槽(0.6)→柜台(0.85)
      三爻(进程) = 任务进度       0.1~0.9递增
      四爻(状态) = 物体处理状态   阴=未处理(0.2)  阳=已处理(0.8)
      五爻(目标) = 距目标多远     低=前期探索  中=前往目标  高=到达目标  
      上爻(环境) = 环境就绪程度   低=未知环境  高=就绪可操作
    """
    # 初爻
    y0 = 0.7 if inventory else 0.1
    
    # 二爻
    loc_val = {"起点": 0.1, "柜子": 0.35, "水槽": 0.6, "柜台": 0.85}
    y1 = loc_val.get(location, 0.3)
    
    # 三爻（进度递增）
    y2 = min(0.1 + step * 0.1, 0.85)
    
    # 四爻
    y3 = 0.8 if processed else 0.2
    
    # 五爻（目标接近度）
    if location == "柜台" and inventory:
        y4 = 0.85  # 到位+有物→可放置
    elif location == "柜台":
        y4 = 0.4   # 到位但无物
    elif location == "水槽" and processed and not inventory:
        y4 = 0.65  # 已处理待取出→接近完成
    elif location == "水槽" and not inventory and not processed:
        y4 = 0.35  # 在水槽但空手未处理
    elif location == "水槽" and inventory:
        y4 = 0.2   # 刚拿东西到水槽
    else:
        y4 = 0.15  # 探索阶段
    
    # 上爻
    y5 = 0.8 if location in ("水槽", "柜台") else 0.3
    
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


def yaos_to_action(yao, prev_yao=None):
    """
    六爻 → 动作决策（使用规则引擎）
    
    检测爻变来确定状态跃迁。
    """
    y0, y1, y2, y3, y4, y5 = yao
    
    # 爻变检测
    changes = []
    if prev_yao:
        yao_names = ["初","二","三","四","五","上"]
        for i in range(6):
            diff = yao[i] - prev_yao[i]
            if abs(diff) > 0.1:
                direction = "↑" if diff > 0 else "↓"
                changes.append(f"{yao_names[i]}爻{direction}{abs(diff):.2f}")
    
    # --- 决策规则（基于六爻状态机）---
    # 规则1: 空手 ∩ 未到位 → goto 探索
    if y0 < 0.4 and y1 < 0.5:
        return ("goto", "空手探索", changes)
    
    # 规则2: 空手 ∩ 到位 ∩ 未处理 → take 拿取
    if y0 < 0.4 and y1 >= 0.4 and y3 < 0.4:
        return ("take", f"空手到位→拿取", changes)
    
    # 规则3: 空手 ∩ 到位 ∩ 已处理 → take_out 取出
    if y0 < 0.4 and y1 >= 0.4 and y3 >= 0.5:
        return ("take_out", f"空手到位,已处理→取出", changes)
    
    # 规则4: 有物 ∩ 未处理 ∩ 未到位 → goto_preproc 去处理位置
    if y0 >= 0.4 and y3 < 0.4 and y1 < 0.5:
        return ("goto_preproc", f"有物未处理→去水槽", changes)
    
    # 规则5: 有物 ∩ 未处理 ∩ 到位 → put_in 放入设备
    if y0 >= 0.4 and y3 < 0.4 and y1 >= 0.5:
        return ("put_in", f"有物到位→放入处理", changes)
    
    # 规则6: 空手 ∩ 到位 ∩ 未处理 → process 执行处理
    # 注意：这条和规则2冲突，加了一个"刚放下"的条件
    if y0 < 0.4 and y3 < 0.4 and y1 >= 0.4 and y4 < 0.4:
        return ("process", f"已放入→执行处理", changes)
    
    # 规则7: 有物 ∩ 已处理 ∩ 未到位 → goto_target 去目标位置
    if y0 >= 0.4 and y3 >= 0.5 and y4 < 0.5:
        return ("goto_target", f"有物已处理→去柜台", changes)
    
    # 规则8: 有物 ∩ 已处理 ∩ 到位 ∩ 高目标 → put 放置
    if y0 >= 0.4 and y3 >= 0.5 and y4 >= 0.5:
        return ("put", f"就绪→放置", changes)
    
    # 兜底
    return ("goto", f"兜底({y0},{y3})", changes)


# ============================================================
# 仿真环境（模拟动作和状态变化）
# ============================================================

def get_actions(loc, inv, processed):
    """获取当前可选动作"""
    acts = []
    if loc == "起点":
        acts = ["去柜子", "去水槽", "去柜台"]
    elif loc == "柜子":
        if not inv:
            acts = ["拿起脏盘子"]
        acts += ["去水槽", "去柜台"]
    elif loc == "水槽":
        if inv:
            acts = ["把盘子放进水槽", "去柜台", "去柜子"]
        else:
            if processed:
                acts = ["把盘子从水槽拿出来"]
            else:
                acts = ["清洗盘子"]
            acts += ["去柜台", "去柜子"]
    elif loc == "柜台":
        if inv:
            acts = ["把盘子放到柜台上"]
        acts += ["去水槽", "去柜子"]
    return acts


def apply(action, loc, inv, processed):
    if "拿起" in action and "脏" in action:
        return "柜子", "脏盘子", "你拿起了脏盘子", False
    elif "放进水槽" in action:
        return "水槽", "", "你把脏盘子放进了水槽", False
    elif "清洗" in action and "从" not in action:
        return "水槽", "", "你把盘子洗干净了", True
    elif "拿出来" in action or "取出" in action:
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

print("=" * 70)
print("  六爻驱动逐步决策 — 最终版")
print(f"  EN: {TASK_EN}")
print(f"  CN: {TASK_CN}")
print("=" * 70)
print()

location = "起点"
inventory = ""
feedback = ""
processed = False
all_actions = []
prev_yao = None
prev_hex = None

for step in range(15):
    print(f"─── Step {step+1} ───")
    
    # === 1. 状态六爻（反映实时变化）===
    yao = build_state_yao(location, inventory, processed, step)
    action_type, reason, changes = yaos_to_action(yao, prev_yao)
    
    # === 2. 引擎语义校验（用YLYW理解方向）===
    # 给引擎一个精简状态描述，看主卦是否和决策方向一致
    state = f"位置{location}，{'有'+inventory if inventory else '空手'}，{'已处理' if processed else '未处理'}"
    result = engine.sentence(state)
    main_hex = result["main_hexagram"]
    dom_bagua = result["dominant_bagua"]
    
    # 引擎卦象 → 建议动作类型
    hex_action_map = {
        "泽风大过": "process", "兑为泽":"process", "水风井":"process",
        "坎为水":"process", "水天需":"process",
        "乾为天":"take", "天泽履":"take", "火天大有":"take",
        "地天泰":"put", "山天大畜":"put", "山地剥":"close",
        "雷火丰":"goto", "震为雷":"goto",
        "火风鼎":"process", "离为火":"process",
    }
    suggested = hex_action_map.get(main_hex, "goto")
    
    # 引擎建议和六爻决策是否一致
    aligned = (action_type == suggested or 
               (action_type in ("goto","goto_preproc","goto_target") and suggested == "goto") or
               (action_type in ("process","put_in") and suggested == "process") or
               (action_type == "put" and suggested == "put"))
    
    # === 3. 选择具体动作 ===
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
        break
    
    # === 4. 输出 ===
    yao_vis = "  ".join(
        f"{n}={'━' if yao[i]>=0.5 else '┅'}({yao[i]:.2f})"
        for i, n in enumerate(["初","二","三","四","五","上"])
    )
    
    print(f"  📋 状态: {location:4s} | {inventory or '空手':6s} | {'已处理' if processed else '未处理'}")
    print(f"  📊 六爻: {yao_vis}")
    if changes:
        print(f"  🔄 爻变: {', '.join(changes)}")
    print(f"  🔮 引擎: {main_hex}({dom_bagua})→建议{suggested} {'✅' if aligned else '⚠️'}")
    print(f"  🎯 决策: {action_type} → {reason}")
    print(f"  🤖 动作: {action}")
    
    # 执行
    location, inventory, feedback, processed = apply(action, location, inventory, processed)
    all_actions.append(action)
    prev_yao = yao
    prev_hex = main_hex
    print(f"  📌 {feedback}")
    
    if "完成" in feedback:
        print(f"\n  ✅ 任务成功！")
        break
    print()

print(f"\n{'='*70}")
print(f"  动作序列 ({len(all_actions)}步):")
for i, a in enumerate(all_actions):
    print(f"    {i+1:2d}. {a}")
print(f"{'='*70}")
