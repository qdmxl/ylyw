#!/usr/bin/env python3
"""
动作库驱动的六爻决策 — 跨任务验证

核心架构：
  1. 语义引擎解析任务描述 → 生成动作库（当前场景所有可执行动作的中文描述+卦象）
  2. 六爻模糊推理 → 输出"意图"（拿取/去预处理/放入/处理/取出/去目标/放置）
  3. 在动作库中按意图+卦象匹配度搜索 → 输出具体动作

动作库是与场景绑定的，六爻决策是与场景无关的。
每次进入新任务，语义引擎重新生成动作库。
"""

import sys, os, math, re, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ylyw', 'language'))
from hanzi_engine import HanziEngine, BAGUA

engine = HanziEngine(verbose=False)
engine.action_chars.add('去')

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 工具：位置/物体翻译表（仅用于构建中文动作命令，无匹配作用）
# ============================================================

EN_TO_CN = {
    'cabinet':'柜子','countertop':'柜台','counter':'柜台','sinkbasin':'水槽',
    'fridge':'冰箱','microwave':'微波炉','drawer':'抽屉','shelf':'架子',
    'desk':'桌子','table':'桌子','bed':'床','sofa':'沙发','safe':'保险箱',
    'toilet':'马桶','garbagecan':'垃圾桶','garbage':'垃圾桶','coffeemachine':'咖啡机',
    'toaster':'烤面包机','stoveburner':'灶台','diningtable':'餐桌','armchair':'扶手椅',
    'floorlamp':'落地灯','desklamp':'台灯','lamp':'灯',
    'plate':'盘子','bowl':'碗','mug':'杯子','cup':'杯子','knife':'刀',
    'fork':'叉子','spoon':'勺子','pan':'锅','pot':'锅','spatula':'锅铲',
    'apple':'苹果','potato':'土豆','tomato':'番茄','lettuce':'生菜',
    'bread':'面包','egg':'鸡蛋','soapbar':'肥皂','soap':'肥皂',
    'pencil':'笔','book':'书','keychain':'钥匙链','watch':'手表','vase':'花瓶',
    'cellphone':'手机','remotecontrol':'遥控器','laptop':'笔记本',
    'pillow':'枕头','toiletpaper':'卫生纸',
    'saltshaker':'盐瓶','peppershaker':'胡椒瓶','plunger':'皮搋子',
    'creditcard':'信用卡','cd':'光盘','statue':'雕像','alarmclock':'闹钟',
    'box':'盒子','baseballbat':'棒球棒','basketball':'篮球','newspaper':'报纸',
    'tissuebox':'纸巾盒','sponge':'海绵','cloth':'抹布','towel':'毛巾',
    'alarmclock':'闹钟','vase':'花瓶','newspaper':'报纸','tissuebox':'纸巾盒',
    'spraybottle':'喷瓶','teddybear':'泰迪熊','kettle':'水壶','glassbottle':'玻璃瓶',
    'scrubbrush':'刷子','dishsponge':'洗碗海绵','handtowel':'手巾','papertowelroll':'纸巾卷',
    'potato':'土豆','tomato':'番茄','lettuce':'生菜','bread':'面包','egg':'鸡蛋',
    'apple':'苹果','peppershaker':'胡椒瓶','saltshaker':'盐瓶','soapbottle':'洗手液瓶',
    'winebottle':'酒瓶','butterknife':'黄油刀','ladle':'汤勺','mug':'杯子',
}

# ============================================================
# 动作库生成器 — 从语义引擎的任务解析结果动态生成
# ============================================================

def parse_task(task_cn):
    """语义引擎解析任务描述，提取任务参数"""
    r = engine.sentence(task_cn)
    segs = r['segments']
    roles = r['segment_role']
    rels = r['mutua_relations']
    temporal = engine.parse_temporal(task_cn)
    
    verbs = [segs[i] for i in range(len(segs)) if roles[i] == '动作']
    objects = [segs[i] for i in range(len(segs)) if roles[i] == '物体']
    
    # 任务类型
    verb_text = ' '.join(verbs)
    need_clean = any(w in verb_text for w in ['洗','干净','清洁'])
    need_heat = any(w in verb_text for w in ['加热','热']) and '冷' not in verb_text
    need_cool = any(w in verb_text for w in ['冷却','冷','冰'])
    need_look = any(w in verb_text for w in ['看','照','查看'])
    
    if need_clean: task_type, preproc = '清洗后放置', '水槽'
    elif need_heat: task_type, preproc = '加热后放置', '微波炉'
    elif need_cool: task_type, preproc = '冷却后放置', '冰箱'
    else: task_type, preproc = '取放', None
    
    # 目标物体和目标位置
    loc_keywords = {'柜台','柜子','水槽','冰箱','微波炉','架子','桌子','台子','垃圾桶'}
    target_obj = None
    target_loc = None
    for obj in objects:
        if not any(loc in obj for loc in loc_keywords) and task_type != '冷却后放置':
            target_obj = obj
        else:
            for lk in loc_keywords:
                if lk in obj:
                    target_loc = lk
    
    if not target_obj and objects:
        target_obj = objects[0]
    if not target_loc:
        target_loc = '柜台' if task_type != '冷却后放置' else '柜子'
    
    return {
        'task_type': task_type,
        'target_obj': target_obj,
        'target_loc': target_loc,
        'preproc_loc': preproc,
        'temporal': temporal,
        'verbs': verbs,
    }


def generate_action_library(task_params, location_data=None):
    """
    根据任务参数生成当前场景的动作库。
    
    每个动作条目：
      {
        "id": "唯一标识",
        "cn": "中文命令（如"拿盘子从柜子"）",
        "intent": "动作类型（拿取/去预处理/放入/处理/取出/去目标/放置）",
        "bagua": "主导八卦",
        "hexagram": "六十四卦",
        "target": "涉及的目标物体或位置",
        "analysis": engine.sentence()的完整输出
      }
    """
    target_obj = task_params['target_obj'] or '物体'
    target_loc = task_params['target_loc'] or '柜台'
    preproc_loc = task_params['preproc_loc']
    
    # 场景中的可达位置（从location_data获取）
    available_locs = location_data.get('available_locs', ['柜子','水槽','柜台','冰箱','微波炉','架子','桌子','抽屉']) if location_data else ['柜子','水槽','柜台','冰箱','微波炉','架子','桌子','抽屉']
    
    library = []
    
    # === 探索类动作（所有位置都是goto探索）===
    for loc in available_locs:
        cmd = f"去{loc}"
        library.append(_make_entry(cmd, "goto探索", loc))
    
    # === 拿取类动作 ===
    # 从可能的位置拿
    for loc in available_locs[:3]:
        cmd = f"拿{target_obj}从{loc}"
        library.append(_make_entry(cmd, "拿取", target_obj))
    
    # === 去预处理位置（特定位置的goto作为独立intent）===
    if preproc_loc:
        cmd = f"去{preproc_loc}"
        library.append(_make_entry(cmd, "去预处理位置", preproc_loc))
        
        # === 放入设备 ===
        cmd = f"放{target_obj}到{preproc_loc}"
        library.append(_make_entry(cmd, "放入设备", preproc_loc))
        
        # === 执行处理 ===
        if task_params['task_type'] == '清洗后放置':
            cmd = f"清洗{target_obj}用{preproc_loc}"
        elif task_params['task_type'] == '加热后放置':
            cmd = f"加热{target_obj}用{preproc_loc}"
        elif task_params['task_type'] == '冷却后放置':
            cmd = f"冷却{target_obj}用{preproc_loc}"
        else:
            cmd = f"处理{target_obj}用{preproc_loc}"
        library.append(_make_entry(cmd, "执行处理", target_obj))
        
        # === 取出 ===
        cmd = f"拿{target_obj}从{preproc_loc}"
        library.append(_make_entry(cmd, "取出", target_obj))
    else:
        # 无预处理任务直接可放置
        pass
    
    # === 去目标位置 ===
    cmd = f"去{target_loc}"
    library.append(_make_entry(cmd, "去目标位置", target_loc))
    
    # === 放置 ===
    cmd = f"放{target_obj}到{target_loc}"
    library.append(_make_entry(cmd, "放置", target_loc))
    
    # 去重：相同cn但不同intent时保留后者（后面的intent更具体）
    seen = {}  # cn -> 条目
    for entry in library:
        cn = entry['cn']
        if cn not in seen:
            seen[cn] = entry
        else:
            # 相同cn，保留intent更具体的（goto探索 < 去预处理位置 < 去目标位置）
            priority = {'goto探索': 0, '拿取': 1, '取出': 1, '去预处理位置': 2, '放入设备': 3, '执行处理': 4, '去目标位置': 5, '放置': 6}
            old_p = priority.get(seen[cn]['intent'], -1)
            new_p = priority.get(entry['intent'], -1)
            if new_p > old_p:
                seen[cn] = entry
    
    return list(seen.values())


def _make_entry(cmd, intent, target):
    """生成一个动作库条目"""
    r = engine.sentence(cmd)
    return {
        "cn": cmd,
        "intent": intent,
        "bagua": r['dominant_bagua'],
        "hexagram": r['main_hexagram'],
        "target": target,
        "yao": [round(v,3) for v in r['yao_vector'][:6]],
    }


# ============================================================
# 状态六爻 + 模糊推理（完全通用，与任务类型无关）
# ============================================================

def build_yao(location, inventory, processed, step, task_params):
    preproc = task_params.get('preproc_loc')
    target = task_params.get('target_loc')
    
    y0 = 0.40 if inventory and not processed else (0.65 if inventory and processed else 0.10)
    loc_map = {"起点": 0.10}
    if preproc: loc_map[preproc] = 0.55
    if target: loc_map[target] = 0.80
    for k in ["柜子","桌子","架子","抽屉","马桶","保险箱","床","沙发","扶手椅"]:
        if k not in loc_map: loc_map[k] = 0.30 if preproc else 0.50
    y1 = loc_map.get(location, 0.25)
    y2 = min(0.10 + step * 0.09, 0.85)
    
    if preproc is None:
        y3 = 0.80 if inventory else 0.10
        y4 = 0.85 if location==target and inventory else (0.35 if location==target else 0.15)
    else:
        if processed and location==preproc and not inventory: y3 = 0.70
        elif processed and inventory: y3 = 0.85
        elif processed: y3 = 0.60
        elif not inventory and location==preproc: y3 = 0.25
        else: y3 = 0.10
        if location==target and inventory: y4 = 0.85
        elif location==target: y4 = 0.35
        elif location==preproc and not inventory and processed: y4 = 0.65
        elif location==preproc and not inventory and not processed: y4 = 0.30
        elif location==preproc and inventory: y4 = 0.15
        else: y4 = 0.15
    
    y5 = 0.75 if location in ([preproc,target] if preproc else [target]) else 0.25
    return [round(v,3) for v in [y0,y1,y2,y3,y4,y5]]


def left_shoulder(x, e=0.35, s=0.15):
    if x <= e-s: return 1.0
    if x >= e+s: return 0.0
    return 1.0-(x-(e-s))/(2*s)

def right_shoulder(x, e=0.45, s=0.15):
    if x >= e+s: return 1.0
    if x <= e-s: return 0.0
    return (x-(e-s))/(2*s)

RULES = [
    ("goto探索",      lambda y: left_shoulder(y[0])*left_shoulder(y[1],0.40)),
    ("拿取",          lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.35)*left_shoulder(y[3],0.40)),
    ("取出",          lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.35)*right_shoulder(y[3],0.45)),
    ("去预处理位置",    lambda y: right_shoulder(y[0],0.35)*left_shoulder(y[3],0.40)*left_shoulder(y[1],0.45)),
    ("放入设备",       lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[1],0.45)*left_shoulder(y[3],0.40)),
    ("执行处理",       lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.40)*left_shoulder(y[3],0.40)*left_shoulder(y[4],0.30)),
    ("去目标位置",     lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[3],0.45)*left_shoulder(y[1],0.50)),
    ("放置",          lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[3],0.45)*right_shoulder(y[1],0.50)*right_shoulder(y[4],0.40)),
]

def fuzzy_decide(yao):
    best_n, best_a = "goto探索", 0.0
    for n, fn in RULES:
        a = fn(yao)
        if a > best_a: best_n, best_a = n, a
    return best_n, best_a


# ============================================================
# 匹配层：在动作库中搜索最佳动作（完全基于卦象+意图匹配）
# ============================================================

def search_action_library(intent, action_library):
    """
    在动作库中搜索与intent最匹配的动作。
    
    匹配策略：
      1. 首选intent完全匹配的动作条目
      2. 如果有多个同intent的，选第一个（后续可以用卦象相似度排序）
      3. 如果没有完全匹配，走fallback到相近intent
    """
    intent_fallback = {
        "goto探索": ["去预处理位置", "去目标位置", "拿取"],
        "去预处理位置": ["goto探索", "去目标位置"],
        "放入设备": ["放置", "去预处理位置"],
        "执行处理": ["放入设备"],
        "取出": ["拿取", "去预处理位置"],
        "去目标位置": ["goto探索", "去预处理位置"],
        "放置": ["放入设备", "去目标位置"],
    }
    
    # 1. 精确匹配
    exact = [e for e in action_library if e['intent'] == intent]
    if exact:
        return exact[0], 1.0, f"精确匹配:{intent}"
    
    # 2. fallback
    for fb in intent_fallback.get(intent, []):
        fall = [e for e in action_library if e['intent'] == fb]
        if fall:
            return fall[0], 0.7, f"模糊匹配:{intent}→{fb}"
    
    # 3. 兜底
    return action_library[0] if action_library else None, 0.0, "兜底"


# ============================================================
# 测试
# ============================================================

TASKS = [
    {
        "cn": "把盘子洗干净后放到柜台上",
        "state_seq": [
            ("起点", "", False),
            ("柜子", "", False),
            ("柜子", "盘子", False),
            ("水槽", "盘子", False),
            ("水槽", "", False),
            ("水槽", "", True),
            ("水槽", "盘子", True),
            ("柜台", "盘子", True),
        ],
        "location_data": {"available_locs": ["柜子","水槽","柜台","冰箱"]},
    },
    {
        "cn": "把牛奶加热后放到冰箱里",
        "state_seq": [
            ("起点", "", False),
            ("柜子", "", False),
            ("柜子", "牛奶", False),
            ("微波炉", "牛奶", False),
            ("微波炉", "", False),
            ("微波炉", "", True),
            ("微波炉", "牛奶", True),
            ("冰箱", "牛奶", True),
        ],
        "location_data": {"available_locs": ["柜子","微波炉","冰箱","水槽"]},
    },
    {
        "cn": "把杯子冷却后放到柜子里",
        "state_seq": [
            ("起点", "", False),
            ("柜子", "", False),
            ("柜子", "杯子", False),
            ("冰箱", "杯子", False),
            ("冰箱", "", False),
            ("冰箱", "", True),
            ("冰箱", "杯子", True),
            ("柜子", "杯子", True),
        ],
        "location_data": {"available_locs": ["柜子","冰箱","水槽","桌子"]},
    },
    {
        "cn": "把苹果放到桌子上",
        "state_seq": [
            ("起点", "", False),
            ("柜子", "", False),
            ("柜子", "苹果", False),
            ("桌子", "苹果", True),
        ],
        "location_data": {"available_locs": ["柜子","桌子","水槽"]},
    },
]

print("=" * 70)
print("  动作库驱动的六爻决策 — 跨任务涌现测试")
print("=" * 70)

for task in TASKS:
    task_cn = task['cn']
    
    # 1. 语义引擎解析任务
    params = parse_task(task_cn)
    print(f"\n{'─'*70}")
    print(f"  任务: {task_cn}")
    print(f"  语义解析: 类型={params['task_type']} 目标={params['target_obj']}→{params['target_loc']} 预处理={params['preproc_loc']}")
    print(f"  时序: {'→'.join(params['temporal']['actions_ordered'])}")
    
    # 2. 生成动作库
    library = generate_action_library(params, task['location_data'])
    print(f"  动作库 ({len(library)}个):")
    for e in library:
        print(f"    [{e['intent']:8s}] {e['cn']:25s} 卦:{e['bagua']:2s}")
    
    # 3. 逐步决策
    print(f"\n  逐步决策:")
    correct = 0
    total = 0
    for step, (loc, inv, proc) in enumerate(task['state_seq']):
        total += 1
        yao = build_yao(loc, inv, proc, step, params)
        intent, activation = fuzzy_decide(yao)
        action, score, reason = search_action_library(intent, library)
        
        yao_v = "  ".join(f"{['初','二','三','四','五','上'][i]}={yao[i]:.2f}{'━' if yao[i]>=0.5 else '┅'}" for i in range(6))
        action_name = action['cn'] if action else '无'
        
        # 合理性判断
        is_ok = False
        if intent == "goto探索" and "去" in action_name: is_ok = True
        elif intent == "拿取" and "拿" in action_name and proc == False: is_ok = True
        elif intent == "取出" and "拿" in action_name and proc == True: is_ok = True
        elif intent == "去预处理位置" and params['preproc_loc'] in action_name: is_ok = True
        elif intent == "放入设备" and params['preproc_loc'] in action_name: is_ok = True
        elif intent == "执行处理" and ("清洗" in action_name or "加热" in action_name or "冷却" in action_name): is_ok = True
        elif intent == "去目标位置" and params['target_loc'] in action_name: is_ok = True
        elif intent == "放置" and params['target_loc'] in action_name: is_ok = True
        
        icon = "✅" if is_ok else "⚠️"
        if is_ok: correct += 1
        
        print(f"    S{step+1} {icon} {intent:8s}({activation:.2f}) → {action_name:25s}  [{yao_v[:40]}...]")
    
    print(f"    → 合理性: {correct}/{total}")
    print()

print("=" * 70)
print("  测试完成")
print("=" * 70)
