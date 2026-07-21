#!/usr/bin/env python3
"""
ALFWorld 85场景全量测试 — 六爻驱动逐步决策
"""

import sys, os, math, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine
engine = HanziEngine(verbose=False)

# ========== 翻译 ==========
def _cn(w):
    w2 = re.sub(r'\s+\d+$', '', w.strip().lower())
    m = {
        "plate":"盘子","bowl":"碗","mug":"杯子","cup":"杯子","knife":"刀",
        "apple":"苹果","potato":"土豆","tomato":"番茄","lettuce":"生菜",
        "bread":"面包","egg":"鸡蛋","soap":"肥皂","sponge":"海绵",
        "pencil":"笔","book":"书","key":"钥匙","cloth":"抹布","pan":"锅",
        "spatula":"锅铲","spoon":"勺子","fork":"叉子","butterknife":"黄油刀",
        "glassbottle":"玻璃瓶","keychain":"钥匙链","watch":"手表",
        "soapbar":"肥皂","soapbottle":"洗手液瓶","salt shaker":"盐瓶",
        "pepper shaker":"胡椒瓶","plunger":"皮搋子","vase":"花瓶",
        "baseballbat":"棒球棒","basketball":"篮球","book":"书",
        "box":"盒子","cd":"光盘","cellphone":"手机","creditcard":"信用卡",
        "laptop":"笔记本","newspaper":"报纸","remotecontrol":"遥控器",
        "statue":"雕像","tissuebox":"纸巾盒","alarmclock":"闹钟",
        "mug":"杯子","bowl":"碗","pillow":"枕头","toiletpaper":"卫生纸",
        "counter":"柜台","countertop":"柜台","sinkbasin":"水槽","sink":"水槽",
        "fridge":"冰箱","microwave":"微波炉","cabinet":"柜子","drawer":"抽屉",
        "shelf":"架子","garbagecan":"垃圾桶","desk":"桌子","table":"桌子",
        "desk lamp":"台灯","lamp":"灯","toaster":"烤面包机",
        "coffeemaker":"咖啡机","coffeemachine":"咖啡机","stoveburner":"灶台",
        "bed":"床","sofa":"沙发","chair":"椅子","diningtable":"餐桌",
        "trash can":"垃圾桶","trash bin":"垃圾桶","gold bin":"金色垃圾桶",
        "safe":"保险箱","toilet":"马桶","armchair":"扶手椅",
        "remote control":"遥控器",
    }
    return m.get(w2, w2)

def translate(task_en):
    t = task_en.lower().strip().rstrip('.')
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
    patterns = [
        (r"put a clean (.+) on (.+)", "把{0}洗干净后放到{1}上"),
        (r"put a clean (.+) in (.+)", "把{0}洗干净后放到{1}里"),
        (r"clean (.+) and put it in (.+)", "把{0}洗干净再放到{1}里"),
        (r"clean (.+) and put it on (.+)", "把{0}洗干净再放到{1}上"),
        (r"wash (.+) before putting", "先把{0}洗干净再放"),
        (r"put a heated (.+) on (.+)", "把{0}加热后放到{1}上"),
        (r"put a heated (.+) in (.+)", "把{0}加热后放到{1}里"),
        (r"heat (.+) and put it in (.+)", "把{0}加热再放到{1}里"),
        (r"heat (.+) and put it on (.+)", "把{0}加热再放到{1}上"),
        (r"put a chilled (.+) on (.+)", "把{0}冷却后放到{1}上"),
        (r"put a chilled (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"place a chilled (.+) in (.+)", "把{0}冷却后放进{1}里"),
        (r"put a cold (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"cool (.+) and put it in (.+)", "把{0}冷却再放到{1}里"),
        (r"look at (.+) in (.+)", "用{1}的光看看{0}"),
        (r"turn on the (.+)", "打开{0}"),
        (r"examine (.+) using (.+)", "用{1}查看{0}"),
        (r"put two (.+)(?:s|es)? on (.+)", "把两块{0}放到{1}上"),
        (r"put two (.+)(?:s|es)? in (.+)", "把两块{0}放到{1}里"),
        (r"put a (.+) on (.+)", "把{0}放到{1}上"),
        (r"put a (.+) in (.+)", "把{0}放到{1}里"),
        (r"move (.+) to (.+)", "把{0}移到{1}"),
        (r"take (.+) from (.+), put it back on (.+)", "把{0}从{1}拿起来再放回{2}上"),
        (r"throw (.+) into (.+)", "把{0}扔进{1}"),
        (r"throw (.+) in (.+)", "把{0}扔进{1}"),
        (r"move (.+) on (.+) over", "把{1}上的{0}挪动一下"),
    ]
    for pat, tmpl in patterns:
        m = re.match(pat, t)
        if m:
            groups = [_cn(g) for g in m.groups()]
            try: return tmpl.format(*groups)
            except: continue
    return task_en

def build_alfworld_desc(task_type, obj, parent):
    """从PDDL参数构建标准ALFWorld任务描述"""
    obj_cn = obj
    parent_cn = parent
    
    # 常用位置映射
    loc_map = {
        'CounterTop': '柜台上', 'Cabinet': '柜子里', 'Drawer': '抽屉里',
        'Shelf': '架子上', 'Desk': '桌子上', 'Bed': '床上', 'Sofa': '沙发上',
        'Safe': '保险箱上', 'Toilet': '马桶上', 'ArmChair': '扶手椅上',
        'GarbageCan': '垃圾桶里', 'Microwave': '微波炉里', 'Fridge': '冰箱里',
        'SinkBasin': '水槽里', 'CoffeeMachine': '咖啡机上',
    }
    
    if task_type == 'look_at_obj_in_light':
        return f"用灯的光看看{obj_cn}"
    elif task_type == 'pick_and_place_simple':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把{obj_cn}放到{loc_str}"
    elif task_type == 'pick_and_place_with_movable_recep':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把{obj_cn}移到{loc_str}"
    elif task_type == 'pick_clean_then_place_in_recep':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把{obj_cn}洗干净后放到{loc_str}"
    elif task_type == 'pick_heat_then_place_in_recep':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把{obj_cn}加热后放到{loc_str}"
    elif task_type == 'pick_cool_then_place_in_recep':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把{obj_cn}冷却后放到{loc_str}"
    elif task_type == 'pick_two_obj_and_place':
        loc_str = loc_map.get(parent, f'{parent_cn}上')
        return f"把两块{obj_cn}放到{loc_str}"
    return ""


def left_shoulder(x, e=0.35, s=0.15):
    if x <= e-s: return 1.0
    if x >= e+s: return 0.0
    return 1.0-(x-(e-s))/(2*s)

def right_shoulder(x, e=0.45, s=0.15):
    if x >= e+s: return 1.0
    if x <= e-s: return 0.0
    return (x-(e-s))/(2*s)

RULES = [
    ("goto",      lambda y: left_shoulder(y[0])*left_shoulder(y[1],0.40), "空手∩未到位→探索"),
    ("take",      lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.35)*left_shoulder(y[3],0.40), "空手∩到位∩未处理→拿取"),
    ("take_out",  lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.35)*right_shoulder(y[3],0.45), "空手∩到位∩已处理→取出"),
    ("goto_preproc", lambda y: right_shoulder(y[0],0.35)*left_shoulder(y[3],0.40)*left_shoulder(y[1],0.45), "有物∩未处理∩未到位→去预处理"),
    ("put_in",    lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[1],0.45)*left_shoulder(y[3],0.40), "有物∩到位∩未处理→放入"),
    ("process",   lambda y: left_shoulder(y[0])*right_shoulder(y[1],0.40)*left_shoulder(y[3],0.40)*left_shoulder(y[4],0.30), "已放入∩未处理→执行"),
    ("goto_target", lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[3],0.45)*left_shoulder(y[1],0.50), "有物∩已处理∩未到位→去目标"),
    ("put",       lambda y: right_shoulder(y[0],0.35)*right_shoulder(y[3],0.45)*right_shoulder(y[1],0.50)*right_shoulder(y[4],0.40), "有物∩已处理∩到位→放置"),
    ("goto",      lambda y: 0.15, "兜底"),
]

def fuzzy_decide(yao):
    ba, bn = 0.0, "goto"
    for n, fn, _ in RULES:
        a = fn(yao)
        if a > ba: ba, bn = a, n
    return bn, ba

def build_yao(loc, inv, processed, step, pp, target):
    y0 = 0.40 if inv and not processed else (0.65 if inv and processed else 0.10)
    lm = {"起点": 0.10}
    if pp: lm[pp] = 0.55
    if target: lm[target] = 0.80
    for k in ["柜子","桌子","架子","抽屉"]:
        lm[k] = 0.30 if pp else 0.50
    y1 = lm.get(loc, 0.25)
    y2 = min(0.10+step*0.09, 0.85)
    if pp is None:
        y3 = 0.80 if inv else 0.10
        y4 = 0.85 if loc==target and inv else (0.35 if loc==target else 0.15)
    else:
        y3 = 0.70 if processed and loc==pp and not inv else (0.85 if processed and inv else (0.60 if processed else (0.25 if not inv and loc==pp else 0.10)))
        y4 = 0.85 if loc==target and inv else (0.35 if loc==target else (0.65 if loc==pp and not inv and processed else (0.30 if loc==pp and not inv and not processed else (0.15 if loc==pp and inv else 0.15))))
    y5 = 0.75 if loc in ([pp,target] if pp else [target]) else (0.25 if loc=="起点" else 0.45)
    return [round(v,3) for v in [y0,y1,y2,y3,y4,y5]]

def get_actions(loc, inv, processed, pp, target, explore):
    acts = []
    if loc == "起点":
        acts = [f"去{explore}"]
        if pp: acts += [f"去{pp}"]
        acts += [f"去{target}"]
    elif loc == explore:
        if not inv: acts = ["拿起物体"]
        if pp: acts += [f"去{pp}"]
        acts += [f"去{target}"]
    elif pp and loc == pp:
        if inv: acts = [f"把物体放进{pp}", f"去{target}"]
        else:
            acts = [f"把物体从{pp}拿出来" if processed else "处理物体"]
            acts += [f"去{target}"]
    elif loc == target:
        if inv: acts = [f"把物体放到{target}上"]
        if pp: acts += [f"去{pp}"]
        acts += [f"去{explore}"]
    return acts

def apply(act, loc, inv, processed, pp, target, explore):
    if "拿起" in act and not inv: return explore, "物体", processed
    if pp and f"放进{pp}" in act: return pp, "", processed
    if "处理" in act and pp and "从" not in act and "放进" not in act: return pp, "", True
    if pp and "拿出来" in act: return pp, "物体", processed
    if f"放到{target}" in act or target in act and "放到" in act:
        return "完成", "", processed  # 标记完成
    if f"去{target}" in act:
        if loc==target: return loc, inv, processed
        return target, inv, processed
    if pp and f"去{pp}" in act:
        if loc==pp: return loc, inv, processed
        return pp, inv, processed
    if f"去{explore}" in act:
        if loc==explore: return loc, inv, processed
        return explore, inv, processed
    return loc, inv, processed

def run_test(task_cn, task_type, target, preproc, explore):
    loc, inv, processed = "起点", "", False
    actions, done = [], False
    for step in range(15):
        if done: break
        yao = build_yao(loc, inv, processed, step, preproc, target)
        at, _ = fuzzy_decide(yao)
        if preproc is None and at in ("goto_preproc","put_in","process","take_out"):
            at = "put" if inv else ("take" if not inv else "goto")
        avail = get_actions(loc, inv, processed, preproc, target, explore)
        mp = {
            "goto": [a for a in avail if "去" in a and "拿起" not in a],
            "take": [a for a in avail if "拿起" in a],
            "goto_preproc": [a for a in avail if preproc and f"去{preproc}" in a],
            "put_in": [a for a in avail if "放进" in a],
            "process": [a for a in avail if "处理" in a and "从" not in a and "放进" not in a],
            "take_out": [a for a in avail if "拿出来" in a],
            "goto_target": [a for a in avail if f"去{target}" in a and "放" not in a],
            "put": [a for a in avail if "放到" in a or (target in a and "去" not in a)],
        }
        cand = mp.get(at, [])
        if not cand and at=="put": cand = [a for a in avail if target in a and "去" not in a]
        if not cand and at=="goto_target": cand = [a for a in avail if target in a]
        if not cand: cand = avail
        if not cand: break
        act = cand[0]
        loc, inv, processed = apply(act, loc, inv, processed, preproc, target, explore)
        actions.append(act)
        if loc == "完成":
            done = True
    return actions, done

# ========== 主测试 ==========
# 从ALFWorld数据目录收集所有场景
import os as _os
base = '/home/lijinhan/.cache/alfworld/json_2.1.1/valid_unseen'
all_tasks = []
for entry in sorted(_os.listdir(base)):
    d = _os.path.join(base, entry)
    if not _os.path.isdir(d): continue
    trials = _os.listdir(d)
    if not trials: continue
    # 直接从目录名解析
    parts = entry.split('-')
    tt = parts[0]
    obj = parts[1] if len(parts) > 1 else ''
    parent = parts[3] if len(parts) > 3 else ''
    task_cn = build_alfworld_desc(tt, obj, parent)
    if not task_cn: continue
    
    # 参数
    if tt == 'look_at_obj_in_light':
        preproc = None
        target = "桌子"
        explore = "柜子"
    elif tt in ('pick_clean_then_place_in_recep',):
        preproc = "水槽"
        target = {"Cabinet":"柜子","CounterTop":"柜台","Microwave":"微波炉","GarbageCan":"垃圾桶","Drawer":"抽屉","CoffeeMachine":"咖啡机"}.get(parent, parent)
        explore = "桌子" if target == "柜子" else "柜子"
    elif tt in ('pick_heat_then_place_in_recep',):
        preproc = "微波炉"
        target = {"Cabinet":"柜子","CounterTop":"柜台","Fridge":"冰箱","GarbageCan":"垃圾桶","SinkBasin":"水槽","CoffeeMachine":"咖啡机"}.get(parent, parent)
        explore = "桌子" if target == "柜子" else "柜子"
    elif tt in ('pick_cool_then_place_in_recep',):
        preproc = "冰箱"
        target = {"Cabinet":"柜子","CounterTop":"柜台","Microwave":"微波炉","GarbageCan":"垃圾桶","SinkBasin":"水槽","CoffeeMachine":"咖啡机"}.get(parent, parent)
        explore = "桌子" if target == "柜子" else "柜子"
    elif tt in ('pick_and_place_simple','pick_and_place_with_movable_recep'):
        preproc = None
        target = {"Bed":"床","Cabinet":"柜子","CounterTop":"柜台","Desk":"桌子","Drawer":"抽屉","Shelf":"架子","Toilet":"马桶","Safe":"保险箱","SinkBasin":"水槽","ArmChair":"扶手椅"}.get(parent, parent)
        explore = "桌子" if target == "柜子" else "柜子"
    elif tt == 'pick_two_obj_and_place':
        preproc = None
        target = {"Cabinet":"柜子","CounterTop":"柜台","Safe":"保险箱","Drawer":"抽屉","Sofa":"沙发","GarbageCan":"垃圾桶"}.get(parent, parent)
        explore = "桌子" if target == "柜子" else "柜子"
    else:
        continue
    
    all_tasks.append({
        'cn': task_cn, 'type': tt, 'target': target,
        'preproc': preproc, 'explore': explore,
        'obj': obj, 'parent': parent,
    })

print(f"="*70)
print(f"  ALFWorld 全场景任务规划测试")
print(f"  场景数: {len(all_tasks)}")
print(f"="*70)
print()

from collections import Counter
tc = Counter(t['type'] for t in all_tasks)
for t, c in sorted(tc.items()):
    print(f"  {t}: {c}个")
print()

results = []
for i, t in enumerate(all_tasks):
    actions, done = run_test(t['cn'], t['type'], t['target'], t['preproc'], t['explore'])
    icon = "✅" if done and len(actions) <= 8 else "❌"
    results.append(icon == "✅")
    print(f"  {icon} #{i:3d} [{t['type']:35s}] {t['cn'][:45]:45s}  {'→'.join(actions[:4])}... ({len(actions)}步)")

print()
print(f"="*70)
print(f"  汇总")
print(f"="*70)
by_type = Counter()
pass_type = Counter()
for i, t in enumerate(all_tasks):
    by_type[t['type']] += 1
    if results[i]: pass_type[t['type']] += 1

for t, c in sorted(by_type.items()):
    p = pass_type[t]
    print(f"  {t:40s} {p}/{c}通过 ({p/c*100:.0f}%)")
print(f"\n  总计: {sum(results)}/{len(all_tasks)}通过 ({sum(results)/len(all_tasks)*100:.0f}%)")
print(f"="*70)
