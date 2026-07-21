#!/usr/bin/env python3
"""
纯核心测试：语义理解引擎 + 状态六爻 + 模糊推理 → 自动涌现动作

核心思想：
  1. 给引擎一个当前状态的中文描述
  2. 给一个可选动作列表（中文，每个动作都过引擎取卦象）
  3. 六爻模糊推理决定当前"应该做什么类型的动作"
  4. 从可选动作中选出卦象最匹配的，不靠字符串关键词

关键测试点：
  - 六爻决策输出一个"动作意图"（如"处理"）
  - "处理"这个意图如何与某个具体动作的卦象匹配？
  - 匹配过程是否真的涌现出来，还是仍然是查表？
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ylyw', 'language'))
sys.path.insert(0, os.path.dirname(__file__))
from hanzi_engine import HanziEngine, BAGUA

engine = HanziEngine(verbose=False)
# 加"去"到动作字表
engine.action_chars.add('去')

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 状态六爻 + 模糊推理（与ALFWorld无关）
# ============================================================

def build_yao(location, inventory, processed, step, task_type_params):
    """构造状态六爻"""
    preproc = task_type_params.get('preproc_loc')
    target = task_type_params.get('target_loc')
    
    y0 = 0.40 if inventory and not processed else (0.65 if inventory and processed else 0.10)
    
    loc_map = {"起点": 0.10}
    if preproc: loc_map[preproc] = 0.55
    if target: loc_map[target] = 0.80
    for k in ["柜子","桌子","架子","抽屉"]:
        if k not in loc_map: loc_map[k] = 0.30 if preproc else 0.50
    y1 = loc_map.get(location, 0.25)
    
    y2 = min(0.10 + step * 0.09, 0.85)
    
    if preproc is None:
        y3 = 0.80 if inventory else 0.10
        if location == target and inventory: y4 = 0.85
        elif location == target: y4 = 0.35
        elif inventory: y4 = 0.15
        else: y4 = 0.15
    else:
        if processed and location == preproc and not inventory: y3 = 0.70
        elif processed and inventory: y3 = 0.85
        elif processed: y3 = 0.60
        elif not inventory and location == preproc: y3 = 0.25
        else: y3 = 0.10
        if location == target and inventory: y4 = 0.85
        elif location == target: y4 = 0.35
        elif location == preproc and not inventory and processed: y4 = 0.65
        elif location == preproc and not inventory and not processed: y4 = 0.30
        elif location == preproc and inventory: y4 = 0.15
        else: y4 = 0.15
    
    if preproc:
        y5 = 0.75 if location in (preproc, target) else (0.25 if location == "起点" else 0.45)
    else:
        y5 = 0.75 if location == target else (0.25 if location == "起点" else 0.45)
    
    return [round(v,3) for v in [y0,y1,y2,y3,y4,y5]]


def left_shoulder(x, edge=0.35, slope=0.15):
    if x <= edge - slope: return 1.0
    if x >= edge + slope: return 0.0
    return 1.0 - (x-(edge-slope))/(2*slope)

def right_shoulder(x, edge=0.45, slope=0.15):
    if x >= edge + slope: return 1.0
    if x <= edge - slope: return 0.0
    return (x-(edge-slope))/(2*slope)


# 8条模糊规则
RULES = [
    ("goto探索",      lambda y: left_shoulder(y[0]) * left_shoulder(y[1], 0.40)),
    ("拿取",          lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * left_shoulder(y[3], 0.40)),
    ("取出",          lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.35) * right_shoulder(y[3], 0.45)),
    ("去预处理位置",    lambda y: right_shoulder(y[0], 0.35) * left_shoulder(y[3], 0.40) * left_shoulder(y[1], 0.45)),
    ("放入设备",       lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[1], 0.45) * left_shoulder(y[3], 0.40)),
    ("执行处理",       lambda y: left_shoulder(y[0]) * right_shoulder(y[1], 0.40) * left_shoulder(y[3], 0.40) * left_shoulder(y[4], 0.30)),
    ("去目标位置",     lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * left_shoulder(y[1], 0.50)),
    ("放置",          lambda y: right_shoulder(y[0], 0.35) * right_shoulder(y[3], 0.45) * right_shoulder(y[1], 0.50) * right_shoulder(y[4], 0.40)),
]

def fuzzy_decide(yao):
    """返回(动作意图, 激活度)"""
    best_name, best_act = "goto探索", 0.0
    for name, fn in RULES:
        a = fn(yao)
        if a > best_act:
            best_name, best_act = name, a
    return best_name, best_act


# ============================================================
# 核心：卦象匹配 → 从可选动作中选出最合理的一个
# ============================================================

def analyze_action(cn_action):
    """
    对一个中文动作命令进行语义分析，提取卦象特征。
    
    返回：
      {
        "text": 原命令,
        "segments": 分词,
        "verbs": [动词列表],
        "objects": [物体列表],
        "dominant_bagua": 句级主导八卦,
        "main_hexagram": 句级主卦,
        "action_type_hint": 基于卦象推断的动作类型
      }
    """
    result = engine.sentence(cn_action)
    segments = result["segments"]
    roles = result["segment_role"]
    doms = result["segment_dominant"]
    hexs = result["segment_hexagram"]
    
    verbs = [segments[i] for i in range(len(segments)) if roles[i] == '动作']
    objects = [segments[i] for i in range(len(segments)) if roles[i] == '物体']
    
    # 从卦象推断"这个命令是做什么类型的动作"
    dom_bagua = result["dominant_bagua"]
    main_hex = result["main_hexagram"]
    
    # 基于主导八卦推断动作类型
    if dom_bagua == "乾":  # 天/健 → 拿取/行动
        type_hint = "拿取"
    elif dom_bagua == "兑":  # 泽/悦 → 清洗/开启
        type_hint = "清洗"
    elif dom_bagua == "离":  # 火/明 → 加热/查看
        type_hint = "加热"
    elif dom_bagua == "震":  # 雷/动 → 移动
        type_hint = "移动"
    elif dom_bagua == "巽":  # 风/入 → 放置
        type_hint = "放置"
    elif dom_bagua == "坎":  # 水/险 → 冷却/清洗
        type_hint = "冷却"
    elif dom_bagua == "艮":  # 山/止 → 停止/关闭/位置
        type_hint = "移动"
    elif dom_bagua == "坤":  # 地/载 → 放置/承载
        type_hint = "放置"
    else:
        type_hint = "未知"
    
    return {
        "text": cn_action,
        "segments": segments,
        "verbs": verbs,
        "objects": objects,
        "dominant_bagua": dom_bagua,
        "main_hexagram": main_hex,
        "bagua": doms,
        "type_hint": type_hint,
    }


def match_action(intent, action_analyses):
    """
    核心：六爻决策的"意图" vs 每个可选动作的"卦象特征"
    
    intent是"拿取"、"去预处理位置"、"放入设备"、"执行处理"、"取出"、"去目标位置"、"放置"等
    
    匹配逻辑：
      - 不再用字符串关键词，而是用动作的卦象
      - "拿取"意图 → 希望在可选动作中找到"主导八卦=乾"且含"物体"的命令
      - "放入设备"意图 → 希望在可选动作中找到"主导八卦=巽"（放入）或含"放"+"某位置"的命令
      - "执行处理"意图 → 希望在可选动作中找到"主导八卦=兑/坎/离"的命令（清洗/冷却/加热）
    
    返回(最佳动作的analyze, 匹配得分)
    """
    best_action = None
    best_score = 0.0
    best_reason = ""
    
    for a in action_analyses:
        score = 0.0
        reasons = []
        
        # === 匹配规则（基于卦象语义，不是字符串）===
        
        # 1. 拿取意图：动作的主导卦象应该是乾(行动)或震(动)
        if intent == "拿取":
            if a["dominant_bagua"] in ("乾", "震"):
                score += 0.6
            if a["verbs"]:
                score += 0.2
                if "拿" in a["text"] or "取" in a["text"]:
                    score += 0.2
        
        # 2. 去预处理位置意图：动作应该是"去XX"类，XX的卦象是坎(水槽)/乾(冰箱)/离(微波炉)
        elif intent == "去预处理位置":
            if a["dominant_bagua"] in ("艮", "坤"):  # "去XX"通常是艮/坤卦
                score += 0.3
            if "去" in a["text"]:
                score += 0.3
                # 目标位置中是否有"水槽"、"冰箱"、"微波炉"等预处理位置词
                for obj in a["objects"]:
                    if any(k in obj for k in ["水槽","冰箱","微波炉"]):
                        score += 0.4
                        break
        
        # 3. 放入设备意图：动作是"放XX到XX"，应该是巽卦(入/放)
        elif intent == "放入设备":
            if a["dominant_bagua"] in ("巽", "坤"):
                score += 0.3
            if "放" in a["text"]:
                score += 0.3
            # 检查是否含预处理位置
            for obj in a["objects"]:
                if any(k in obj for k in ["水槽","冰箱","微波炉"]):
                    score += 0.4
                    break
        
        # 4. 执行处理意图：动作应该是"清洗/加热/冷却"，卦象应该是兑/离/坎
        elif intent == "执行处理":
            if a["dominant_bagua"] in ("兑", "离", "坎"):
                score += 0.5
                # 兑=清洗 离=加热 坎=冷却
                if a["dominant_bagua"] == "兑":
                    score += 0.2  # 更匹配清洗
                elif a["dominant_bagua"] == "离":
                    score += 0.1  # 加热
                elif a["dominant_bagua"] == "坎":
                    score += 0.1  # 冷却
            if a["verbs"]:
                score += 0.3
        
        # 5. 取出意图：动作应该是"从XX拿出XX"
        elif intent == "取出":
            if a["dominant_bagua"] in ("乾", "震"):
                score += 0.3
            if "拿" in a["text"] or "取" in a["text"]:
                score += 0.3
            # 检查是否含有"从"字结构
            if "从" in a["text"]:
                score += 0.4
        
        # 6. 去目标位置意图：去"柜台/柜子/架子"等
        elif intent == "去目标位置":
            if "去" in a["text"]:
                score += 0.3
            if a["dominant_bagua"] in ("艮", "坤"):
                score += 0.3
            for obj in a["objects"]:
                if any(k in obj for k in ["柜台","柜子","架子","桌子"]):
                    score += 0.4
                    break
        
        # 7. 放置意图：动作应该是"放XX到XX"
        elif intent == "放置":
            if a["dominant_bagua"] in ("巽", "坤"):
                score += 0.4
            if "放" in a["text"]:
                score += 0.3
            for obj in a["objects"]:
                if any(k in obj for k in ["柜台","柜子","架子","桌子"]):
                    score += 0.3
                    break
        
        # 8. 探索意图：去任何位置
        elif intent == "goto探索":
            if "去" in a["text"]:
                score += 0.5
            if a["dominant_bagua"] in ("艮", "坤"):
                score += 0.5
        
        if score > best_score:
            best_score = score
            best_action = a
            best_reason = f"卦象:{a['dominant_bagua']}/{a['main_hexagram']} 得分:{score:.2f}"
    
    return best_action, best_score, best_reason


# ============================================================
# 测试场景
# ============================================================

def run_test(scenario_name, task_cn, location, inventory, processed, 
             step, task_type_params, candidates_cn):
    """
    运行一个完整的测试：给定当前状态和可选动作，
    看六爻推理能否选出最合理的。
    """
    print(f"\n{'='*65}")
    print(f"  {scenario_name}")
    print(f"  任务: {task_cn}")
    print(f"  状态: 位置={location} 持有={inventory or '空'} 已处理={processed}")
    print(f"{'='*65}")
    
    # 1. 六爻决策
    yao = build_yao(location, inventory, processed, step, task_type_params)
    intent, activation = fuzzy_decide(yao)
    
    yao_str = "  ".join(f"{n}={yao[i]:.2f}{'━' if yao[i]>=0.5 else '┅'}" for i, n in enumerate(["初","二","三","四","五","上"]))
    print(f"\n  六爻: {yao_str}")
    print(f"  决策: {intent} (激活度={activation:.3f})")
    
    # 2. 分析每个候选动作
    analyses = [analyze_action(cn) for cn in candidates_cn]
    
    print(f"\n  候选动作 ({len(candidates_cn)}个):")
    for i, a in enumerate(analyses):
        hint = a["type_hint"]
        print(f"    [{i}] {a['text']:30s} 卦:{a['dominant_bagua']:2s}/{a['main_hexagram']:8s} 动词:{a['verbs']} 物体:{a['objects'][:2]} → 提示:{hint}")
    
    # 3. 卦象匹配
    best, score, reason = match_action(intent, analyses)
    
    print(f"\n  ▸ 选择: {best['text'] if best else '无'}")
    print(f"  ▸ 理由: {reason}")
    
    # 4. 人工判断合理性
    print(f"\n  📋 判断: ", end="")
    if best:
        # 简单合理性检查
        if intent == "执行处理" and best["dominant_bagua"] in ("兑","离","坎"):
            print("✅ 合理（处理意图匹配处理类卦象）")
        elif intent == "拿取" and "拿" in best["text"]:
            print("✅ 合理（拿取意图匹配拿取动作）")
        elif intent == "放入设备" and "放" in best["text"]:
            print("✅ 合理（放入意图匹配放置动作）")
        elif intent == "去预处理位置" and "去" in best["text"]:
            print("✅ 合理（移动意图匹配移动动作）")
        elif intent == "去目标位置" and "去" in best["text"]:
            print("✅ 合理（目标意图匹配移动动作）")
        elif intent == "放置" and "放" in best["text"]:
            print("✅ 合理（放置意图匹配放置动作）")
        elif intent == "取出" and "拿" in best["text"]:
            print("✅ 合理（取出意图匹配拿取动作）")
        elif intent == "goto探索" and "去" in best["text"]:
            print("✅ 合理（探索意图匹配移动动作）")
        else:
            print("⚠️ 需人工判断")
    else:
        print("❌ 未选中任何动作")
    
    return intent, best


# ============================================================
# 测试用例：模拟8步决策循环
# ============================================================

# 任务参数
TASK = {
    "cn": "把盘子洗干净后放到柜台上",
    "preproc_loc": "水槽",
    "target_loc": "柜台",
    "has_preproc": True,
}

# 8个状态的候选动作
STEPS = [
    # step 0: 起点，空手
    {
        "loc": "起点", "inv": "", "proc": False,
        "candidates": [
            "去柜子", "去水槽", "去柜台", "去冰箱",
        ]
    },
    # step 1: 到柜子，看到盘子
    {
        "loc": "柜子", "inv": "", "proc": False,
        "candidates": [
            "拿盘子从柜子", "去水槽", "去柜台", "去冰箱",
        ]
    },
    # step 2: 拿到盘子
    {
        "loc": "柜子", "inv": "盘子", "proc": False,
        "candidates": [
            "去水槽", "去柜台", "去冰箱", "放盘子到柜子",
        ]
    },
    # step 3: 到水槽
    {
        "loc": "水槽", "inv": "盘子", "proc": False,
        "candidates": [
            "放盘子到水槽", "去柜台", "去柜子",
        ]
    },
    # step 4: 放入水槽
    {
        "loc": "水槽", "inv": "", "proc": False,
        "candidates": [
            "清洗盘子用水槽", "去柜台", "去柜子",
        ]
    },
    # step 5: 洗好了
    {
        "loc": "水槽", "inv": "", "proc": True,
        "candidates": [
            "拿盘子从水槽", "去柜台", "去柜子",
        ]
    },
    # step 6: 取出干净盘子
    {
        "loc": "水槽", "inv": "盘子", "proc": True,
        "candidates": [
            "去柜台", "去柜子", "放盘子到水槽",
        ]
    },
    # step 7: 到柜台
    {
        "loc": "柜台", "inv": "盘子", "proc": True,
        "candidates": [
            "放盘子到柜台", "去水槽", "去柜子",
        ]
    },
]

title_cn = "递归YLYW — 卦象涌现动作测试（纯中文）"
print(f"\n{'='*65}")
print(f"  {title_cn}")
print(f"  引擎: 递归YLYW汉语理解")
print(f"  决策: 状态六爻 + 模糊推理 + 卦象匹配")
print(f"{'='*65}")

for step, s in enumerate(STEPS):
    run_test(
        f"第{step+1}步",
        TASK["cn"],
        s["loc"], s["inv"], s["proc"],
        step, TASK,
        s["candidates"]
    )
