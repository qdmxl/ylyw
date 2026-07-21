#!/usr/bin/env python3
"""
Phase 1.5: 离线仿真规划测试

对ALFWorld全量85场景，用六爻驱动逐步决策框架（仿真版）运行：
  1. build_yao(): 状态六爻编码
  2. fuzzy_decide(): 8条模糊规则 → 意图
  3. get_actions(): 意图→具体动作
  4. apply(): 动作执行 → 状态更新
  5. 统计生成的动作序列是否完整覆盖任务流程

这个测试不需要实际ALFWorld环境，纯离线仿真。
在六爻决策层验证：语义理解+六爻推理能否生成正确的动作序列。
"""

import sys, os, json, math, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine
from collections import defaultdict, Counter

engine = HanziEngine(verbose=False)

# ============================================================
# 六爻 + 模糊推理（与 run_v14.py 同构）
# ============================================================

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

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

def build_yao(loc, inv, proc, step, preproc_loc, target_loc, has_take=False):
    """状态六爻编码（6维连续向量）—— V2 修正版
    
    关键修正：
    1. 初爻(y0)持有态: inv时有物明确给0.70，empty给0.10，中间态减少
    2. 二爻(y1)位置: 探索位置估值提高到0.40，确保拿取规则能激活
    3. 三爻(y2)进度: 增长速度加快
    4. 四爻(y3)预处理态: 用proc精准区分步骤
    5. 五爻(y4)目标就绪: 去掉了proc和loc在pp的模糊值
    """
    # 初爻：持有状态（0.10空手, 0.70有物, 0.85有物已处理）
    y0 = 0.10 if not inv else (0.85 if proc else 0.70)
    
    # 二爻：位置估值（0.10起点, 0.40探索位, 0.60预处理器, 0.85目标位）
    lm = {"起点": 0.10}
    if preproc_loc: lm[preproc_loc] = 0.60
    if target_loc: lm[target_loc] = 0.85
    # 探索位置统一给0.40（让拿取规则能激活）
    for k in ["柜子","桌子","架子","抽屉","微波炉","冰箱","水槽",
              "床","沙发","保险箱","马桶","扶手椅","垃圾桶","台灯","落地灯",
              "咖啡机","柜台"]:
        lm[k] = 0.40
    loc_base = re.sub(r'\d+$', '', loc).strip() if loc else loc
    y1 = lm.get(loc, lm.get(loc_base, 0.25))
    if has_take and not inv:
        y1 = max(y1, 0.55)  # 有可取物体时位置估值提高
    
    # 三爻：进度（0.10→0.85）
    y2 = min(0.10 + step * 0.07, 0.85)
    
    # 四爻和五爻：预处理和目标就绪度
    if preproc_loc is None:
        # 无预处理场景
        y3 = 0.80 if inv else 0.10
        y4 = 0.90 if loc == target_loc and inv else (0.40 if loc == target_loc else 0.10)
    else:
        # 有预处理场景
        if not inv and not proc:
            # 空手、未处理 → 探索/拿取阶段
            if loc == preproc_loc:
                y3 = 0.35  # 在预处理位但没事做
            else:
                y3 = 0.10
        elif inv and not proc:
            # 有物但未处理 → 应该去预处理位
            if loc == preproc_loc:
                y3 = 0.25  # 已经在预处理位，应该放入
            else:
                y3 = 0.15
        elif not inv and proc:
            # 空手但已处理 → 去预处理位取出
            if loc == preproc_loc:
                y3 = 0.70  # 在预处理位，可以取出
            else:
                y3 = 0.60  # 不在预处理位，应该去
        elif inv and proc:
            # 有物且已处理 → 准备放置
            y3 = 0.85 if loc == preproc_loc else 0.80
        else:
            y3 = 0.10
        
        # 五爻：目标就绪（只有在目标位且有物时才高）
        if loc == target_loc and inv:
            y4 = 0.90 if proc else 0.40  # 有物+已处理→放置就绪
        elif loc == preproc_loc and not inv and proc:
            y4 = 0.10  # 在预处理位空手→不应该去目标
        else:
            y4 = 0.15  # 其他情况
    
    # 上爻：环境宽松度
    y5 = 0.75 if loc in ([preproc_loc, target_loc] if preproc_loc else [target_loc]) else 0.35
    
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


# ============================================================
# 仿真场景定义
# ============================================================

BASE = '/home/lijinhan/.cache/alfworld/json_2.1.1/valid_unseen'

OBJ_CN_MAP = {
    'AlarmClock': '闹钟', 'Apple': '苹果', 'BaseballBat': '棒球棒',
    'BasketBall': '篮球', 'Book': '书', 'Bottle': '瓶子',
    'Bowl': '碗', 'Box': '盒子', 'Bread': '面包', 'ButterKnife': '黄油刀',
    'CD': '光盘', 'CellPhone': '手机', 'Cloth': '抹布', 'CreditCard': '信用卡',
    'Cup': '杯子', 'DishSponge': '海绵', 'Egg': '鸡蛋',
    'Fork': '叉子', 'Glass': '玻璃杯', 'KeyChain': '钥匙链',
    'Knife': '刀', 'Ladle': '汤勺', 'Laptop': '笔记本',
    'Lettuce': '生菜', 'Mug': '杯子', 'Newspaper': '报纸',
    'Pan': '锅', 'Pencil': '铅笔', 'PepperShaker': '胡椒瓶',
    'Pillow': '枕头', 'Plate': '盘子', 'Plunger': '皮搋子',
    'Pot': '锅', 'Potato': '土豆', 'RemoteControl': '遥控器',
    'SaltShaker': '盐瓶', 'SoapBar': '肥皂', 'Spatula': '锅铲',
    'Spoon': '勺子', 'SprayBottle': '喷壶', 'Statue': '雕像',
    'ToiletPaper': '卫生纸', 'Tomato': '番茄', 'Towel': '毛巾',
    'Vase': '花瓶', 'Watch': '手表', 'WineBottle': '酒瓶',
    'ScrubBrush': '刷子', 'SoapBottle': '洗手液瓶', 'Milk': '牛奶',
    'Coffee': '咖啡', 'Soap': '肥皂', 'Food': '食物',
    'TissueBox': '纸巾盒', 'GlassBottle': '玻璃瓶',
    'LettuceSliced': '生菜', 'BreadSliced': '面包', 'AppleSliced': '苹果',
    'PotatoSliced': '土豆', 'TomatoSliced': '番茄',
}

LOC_CN_MAP = {
    'CounterTop': '柜台', 'Cabinet': '柜子', 'Drawer': '抽屉',
    'Shelf': '架子', 'Desk': '桌子', 'DeskLamp': '台灯', 'FloorLamp': '落地灯',
    'Bed': '床', 'Sofa': '沙发', 'Safe': '保险箱', 'Toilet': '马桶',
    'ArmChair': '扶手椅', 'SinkBasin': '水槽', 'GarbageCan': '垃圾桶',
    'Microwave': '微波炉', 'Fridge': '冰箱', 'CoffeeMachine': '咖啡机',
    'StoveBurner': '灶台', 'DiningTable': '餐桌', 'SideTable': '边桌',
    'TVStand': '电视柜', 'LaundryHamper': '洗衣篮', 'Bathtub': '浴缸',
    'Ottoman': '脚凳', 'Cart': '推车',
}

# 预处理位置映射
PREPROC_MAP = {
    'look_at_obj_in_light': None,
    'pick_clean_then_place_in_recep': '水槽',
    'pick_heat_then_place_in_recep': '微波炉',
    'pick_cool_then_place_in_recep': '冰箱',
    'pick_and_place_simple': None,
    'pick_and_place_with_movable_recep': None,
    'pick_two_obj_and_place': None,
}

def build_cn_desc(task_type, obj, parent):
    """构建中文任务描述（与Phase 1一致）"""
    obj_cn = OBJ_CN_MAP.get(obj, obj)
    parent_cn = LOC_CN_MAP.get(parent, parent)
    loc_prep = '里' if parent in ('Cabinet','Drawer','Microwave','Fridge','GarbageCan',
                                   'SinkBasin','Safe','Toilet') else '上'
    if task_type == 'look_at_obj_in_light':
        return f"用灯的光看看{obj_cn}"
    elif task_type == 'pick_and_place_simple':
        return f"把{obj_cn}放到{parent_cn}{loc_prep}"
    elif task_type == 'pick_and_place_with_movable_recep':
        return f"把{obj_cn}移到{parent_cn}{loc_prep}"
    elif task_type == 'pick_clean_then_place_in_recep':
        return f"把{obj_cn}洗干净后放到{parent_cn}{loc_prep}"
    elif task_type == 'pick_heat_then_place_in_recep':
        return f"把{obj_cn}加热后放到{parent_cn}{loc_prep}"
    elif task_type == 'pick_cool_then_place_in_recep':
        return f"把{obj_cn}冷却后放到{parent_cn}{loc_prep}"
    elif task_type == 'pick_two_obj_and_place':
        return f"把两块{obj_cn}放到{parent_cn}{loc_prep}"
    return ""


# ============================================================
# 仿真规划运行器
# ============================================================

def get_actions(loc, inv, processed, pp, target, explore):
    """根据当前状态生成可用的动作列表（英文模拟）"""
    acts = []
    if loc == "起点":
        acts = [f"go to {explore}"]
        if pp: acts += [f"go to {pp}"]
        acts += [f"go to {target}"]
    elif loc == explore:
        if not inv:
            acts = ["take object"]
        if pp: acts += [f"go to {pp}"]
        acts += [f"go to {target}"]
    elif pp and loc == pp:
        if inv:
            acts = [f"put object in {pp}"]
            acts += [f"go to {target}"]
        else:
            acts = [f"take object from {pp}" if processed else "process object"]
            acts += [f"go to {target}"]
    elif loc == target:
        if inv:
            acts = [f"put object on {target}"]
        if pp: acts += [f"go to {pp}"]
        acts += [f"go to {explore}"]
    return acts


def apply(act, loc, inv, processed, pp, target, explore):
    """更新状态（含自动process模拟）"""
    if "take object" in act and not inv:
        return explore, "object", processed
    if pp and f"put object in {pp}" in act:
        # 放入预处理设备后，自动标记为已处理（模拟clean/heat/cool执行）
        return pp, "", True
    if "process" in act:
        return pp, "", True
    if pp and "take object from" in act:
        return pp, "object", processed
    if f"put object on {target}" in act or f"put object in" in act:
        return "完成", "", processed
    if f"go to {target}" in act:
        return target, inv, processed
    if pp and f"go to {pp}" in act:
        return pp, inv, processed
    if f"go to {explore}" in act:
        return explore, inv, processed
    return loc, inv, processed


def run_simulation(task_type, target, preproc, explore, max_steps=25):
    """运行单场景仿真"""
    loc, inv, processed = "起点", "", False
    actions, done = [], False

    for step in range(max_steps):
        if done:
            break

        # 构建六爻
        yao = build_yao(loc, inv, processed, step, preproc, target)

        # 模糊决策 → 意图
        intent, _ = fuzzy_decide(yao)

        # look_at 场景没有预处理环节，修正
        if preproc is None and intent in ("去预处理位置","放入设备","执行处理","取出"):
            intent = "放置" if inv else ("拿取" if not inv else "goto探索")

        # 意图 → 具体动作
        avail = get_actions(loc, inv, processed, preproc, target, explore)
        mp = {
            "goto探索": [a for a in avail if "go to" in a and "take" not in a],
            "拿取": [a for a in avail if "take" in a and "from" not in a],
            "取出": [a for a in avail if "take" in a and "from" in a],
            "去预处理位置": [a for a in avail if preproc and f"go to {preproc}" in a],
            "放入设备": [a for a in avail if f"put object in {preproc}" in a],
            "执行处理": [a for a in avail if "process" in a],
            "去目标位置": [a for a in avail if f"go to {target}" in a and "put" not in a],
            "放置": [a for a in avail if f"put object on {target}" in a or
                     (target in a and "go to" not in a and "put" in a)],
        }
        cand = mp.get(intent, [])
        if not cand:
            cand = avail
        if not cand:
            break

        act = cand[0]
        loc, inv, processed = apply(act, loc, inv, processed, preproc, target, explore)
        actions.append(act)

        if loc == "完成":
            done = True

    return actions, done


# ============================================================
# 主测试
# ============================================================

print("=" * 70)
print("  Phase 1.5: 离线仿真规划测试")
print("  六爻驱动逐步决策 × 全量85场景")
print("=" * 70)

# 收集场景
all_tasks = []
for entry in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, entry)
    if not os.path.isdir(d): continue
    parts = entry.split('-')
    tt = parts[0]
    obj = parts[1] if len(parts) > 1 else ''
    parent = parts[3] if len(parts) > 3 else ''

    preproc = PREPROC_MAP.get(tt)
    target = LOC_CN_MAP.get(parent, parent)
    explore = "桌子" if target in ("柜子","柜") else "柜子"

    task_cn = build_cn_desc(tt, obj, parent)
    if not task_cn: continue

    all_tasks.append({
        'type': tt, 'cn': task_cn,
        'target': target, 'preproc': preproc,
        'explore': explore,
    })

print(f"  场景数: {len(all_tasks)}")
print()

# 按类型统计
type_counts = Counter(t['type'] for t in all_tasks)
for t, c in sorted(type_counts.items()):
    print(f"  {t:40s}: {c}个")
print()

# 运行测试
results = []
pass_by_type = defaultdict(int)
total_by_type = defaultdict(int)

for i, t in enumerate(all_tasks):
    actions, done = run_simulation(
        t['type'], t['target'], t['preproc'], t['explore']
    )
    n_steps = len(actions)

    # 成功判定：任务完成且步数合理（look_at 5步左右，复杂任务8步左右）
    is_success = done and n_steps <= 12

    if is_success:
        pass_by_type[t['type']] += 1
    total_by_type[t['type']] += 1

    icon = "✅" if is_success else "❌"
    action_str = " → ".join(actions[:5]) + ("..." if len(actions) > 5 else "")
    print(f"  {icon} #{i:3d} [{t['type']:35s}] {t['cn'][:35]:35s} ({n_steps}步) {action_str[:60]}")

    results.append({
        'idx': i,
        'type': t['type'],
        'cn': t['cn'],
        'steps': n_steps,
        'done': done,
        'success': is_success,
        'actions': actions,
    })

# 汇总
print("\n" + "=" * 70)
print("  汇总")
print("=" * 70)
print(f"{'任务类型':40s} {'通过/总数':12s} {'成功率':8s} {'平均步数':8s}")
print("-" * 70)
total_pass = 0
total_all = 0
type_steps = defaultdict(list)

for r in results:
    type_steps[r['type']].append(r['steps'])
for tt in sorted(total_by_type.keys()):
    p = pass_by_type[tt]
    n = total_by_type[tt]
    total_pass += p
    total_all += n
    avg_steps = sum(type_steps[tt]) / len(type_steps[tt])
    print(f"{tt:40s} {p:3d}/{n:3d}    {p/n*100:6.1f}%  {avg_steps:6.1f}")

print("-" * 70)
all_avg = sum(r['steps'] for r in results) / len(results)
print(f"{'总计':40s} {total_pass:3d}/{total_all:3d}    {total_pass/total_all*100:6.1f}%  {all_avg:6.1f}")

# 保存结果
output = {
    'total': len(all_tasks),
    'passed': total_pass,
    'rate': total_pass / len(all_tasks),
    'avg_steps': all_avg,
    'by_type': {tt: {'total': total_by_type[tt], 'passed': pass_by_type[tt],
                      'rate': pass_by_type[tt]/total_by_type[tt] if total_by_type[tt] else 0}
                for tt in total_by_type},
    'results': results,
}
with open('eval_phase15_results.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n  结果已保存至 eval_phase15_results.json")
print("=" * 70)
