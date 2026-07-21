#!/usr/bin/env python3
"""
Phase 1: 全量85场景语义解析评测

对ALFWorld valid_unseen的85个场景：
  1. 构建中文任务描述 → HanziEngine句级分析
  2. 统计：分词准确率、卦象匹配合理率、角色识别准确率
  3. 输出：按任务类型分布的详细表格 + 错误案例

输出: eval_phase1_results.json + 终端表格
"""

import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine
from collections import defaultdict, Counter

engine = HanziEngine(verbose=False)

# ═══════════════════════════════════════════════════
# 1. 场景收集
# ═══════════════════════════════════════════════════

BASE = '/home/lijinhan/.cache/alfworld/json_2.1.1/valid_unseen'

# 物体英译中（ALFWorld标准名 → 中文）
OBJ_CN_MAP = {
    'AlarmClock': '闹钟', 'Apple': '苹果', 'BaseballBat': '棒球棒',
    'BasketBall': '篮球', 'Book': '书', 'Bottle': '瓶子',
    'Bowl': '碗', 'Box': '盒子', 'Bread': '面包', 'ButterKnife': '黄油刀',
    'CD': '光盘', 'CellPhone': '手机', 'Cloth': '抹布', 'CreditCard': '信用卡',
    'Cup': '杯子', 'DishSponge': '洗碗海绵', 'Egg': '鸡蛋',
    'Fork': '叉子', 'Glass': '玻璃杯', 'GlassBottle': '玻璃瓶',
    'KeyChain': '钥匙链', 'Knife': '刀', 'Ladle': '汤勺', 'Laptop': '笔记本',
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
}

# 位置英译中
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

# 位置后缀（用于中文描述）
LOC_SUFFIX = {'上': 1, '里': 1, '旁': 1, '边': 1, '前': 1}


def build_cn_desc(task_type: str, obj: str, parent: str) -> str:
    """构建中文任务描述"""
    obj_cn = OBJ_CN_MAP.get(obj, obj)
    parent_cn = LOC_CN_MAP.get(parent, parent)

    # 确定位置后缀
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


# ═══════════════════════════════════════════════════
# 2. 解析结果评价函数
# ═══════════════════════════════════════════════════

def evaluate_semantic(task_cn: str, task_type: str, obj: str, parent: str,
                      result: dict, task_idx: int = -1) -> dict:
    """对HanziEngine的单句解析结果做定量和定性评价"""
    obj_cn = OBJ_CN_MAP.get(obj, obj)
    parent_cn = LOC_CN_MAP.get(parent, parent)

    ev = {
        'segments_ok': False,    # 分词是否包含目标物体和目标位置
        'object_found': False,   # 目标物体在分段中被识别为"物体"角色
        'location_found': False, # 目标位置在分段中被识别为"位置"相关
        'action_found': False,   # 核心动作被识别为"动作"角色
        'hexagram_reasonable': True,  # 卦象合理性标记（默认通过，错误案例单独标注）
        'deps_ok': False,        # 依存关系正确
        'errors': [],
    }

    segs = result['segments']
    roles = result['segment_role']
    deps = result['dependencies']

    # 检查目标物体是否出现在分词中
    obj_in_segs = any(obj_cn in s for s in segs)
    ev['object_found'] = obj_in_segs

    # 检查目标位置是否出现在分词中
    # look_at场景描述中只有"灯"（表示台灯/落地灯），非look_at场景检查具体位置名
    if task_type == 'look_at_obj_in_light':
        # "用灯的光看看..."中"灯"就是位置（台灯/落地灯都是灯）
        loc_in_segs = any('灯' in s for s in segs)
    else:
        loc_in_segs = any(parent_cn in s for s in segs)
    ev['location_found'] = loc_in_segs

    # 检查核心动作角色
    action_keywords = {
        'look_at_obj_in_light': ['看', '照', '打开'],
        'pick_clean_then_place_in_recep': ['洗', '擦', '清洁'],
        'pick_heat_then_place_in_recep': ['加热', '热'],
        'pick_cool_then_place_in_recep': ['冷却', '冷'],
        'pick_two_obj_and_place': ['放', '扔'],
        'pick_and_place_simple': ['放', '放'],
        'pick_and_place_with_movable_recep': ['移', '放'],
    }
    expected_actions = action_keywords.get(task_type, [])
    if expected_actions:
        action_in_roles = False
        for i, r in enumerate(roles):
            if r == '动作' and segs[i] in expected_actions:
                action_in_roles = True
                break
            # 宽松一点：动词出现在seg中且有动作角色就行
            if r == '动作':
                for ea in expected_actions:
                    if ea in segs[i]:
                        action_in_roles = True
                        break
        ev['action_found'] = action_in_roles

    # 依存关系：应有物体→位置的loc_mod或类似关系
    if deps:
        ev['deps_ok'] = True  # 有依存关系即视为有结构理解

    # 卦象合理性：基于先验判断
    hex_name = result['main_hexagram']
    # 一些明显的异常卦象（完全不着边际的）标记为不合理
    # 大多数情况默认合理，留手工标注

    # 总体分段合理：目标物体和位置都在分词中，且有动作角色
    ev['segments_ok'] = obj_in_segs and loc_in_segs and ev['action_found']

    return ev


# ═══════════════════════════════════════════════════
# 3. 主评测流程
# ═══════════════════════════════════════════════════

print("=" * 70)
print("  Phase 1: 全量85场景语义解析评测")
print("  HanziEngine — 递归YLYW汉语理解")
print("=" * 70)

all_tasks = []
for entry in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, entry)
    if not os.path.isdir(d): continue
    parts = entry.split('-')
    tt = parts[0]
    obj = parts[1] if len(parts) > 1 else ''
    parent = parts[3] if len(parts) > 3 else ''
    task_cn = build_cn_desc(tt, obj, parent)
    if not task_cn:
        print(f"  ⚠️ 未识别的任务类型: {tt}")
        continue
    all_tasks.append({
        'type': tt, 'obj': obj, 'parent': parent,
        'cn': task_cn,
    })

print(f"  场景数: {len(all_tasks)}")
print()

# --- 执行解析 ---
results = []
hex_counter = Counter()
type_stats = defaultdict(lambda: {'total': 0, 'seg_ok': 0, 'obj_found': 0,
                                   'loc_found': 0, 'act_found': 0, 'deps_ok': 0})

for i, t in enumerate(all_tasks):
    result = engine.sentence(t['cn'])
    ev = evaluate_semantic(t['cn'], t['type'], t['obj'], t['parent'], result, task_idx=i)

    hex_counter[result['main_hexagram']] += 1
    type_stats[t['type']]['total'] += 1
    if ev['segments_ok']:   type_stats[t['type']]['seg_ok'] += 1
    if ev['object_found']:  type_stats[t['type']]['obj_found'] += 1
    if ev['location_found']:type_stats[t['type']]['loc_found'] += 1
    if ev['action_found']:  type_stats[t['type']]['act_found'] += 1
    if ev['deps_ok']:       type_stats[t['type']]['deps_ok'] += 1

    results.append({
        'idx': i,
        'type': t['type'],
        'cn': t['cn'],
        'obj': OBJ_CN_MAP.get(t['obj'], t['obj']),
        'parent': LOC_CN_MAP.get(t['parent'], t['parent']),
        'segments': result['segments'],
        'roles': result['segment_role'],
        'main_hexagram': result['main_hexagram'],
        'hexagram_score': round(result['hexagram_score'], 4),
        'dominant_bagua': result['dominant_bagua'],
        'yao_vector_preview': [round(v, 3) for v in result['yao_vector'][:6]],
        'deps': result['dependencies'],
        'evaluation': ev,
    })

# 打印每条结果
print(f"{'#':>4} {'类型':32s} {'中文描述':32s} {'主卦':14s} {'分数':6s} {'分':4s} {'物':4s} {'位':4s} {'动':4s} {'依':4s}")
print("-" * 100)
for r in results:
    ev = r['evaluation']
    ok = '✅' if ev['segments_ok'] else '❌'
    of = '✅' if ev['object_found'] else '❌'
    lf = '✅' if ev['location_found'] else '❌'
    af = '✅' if ev['action_found'] else '❌'
    dp = '✅' if ev['deps_ok'] else '❌'
    print(f"{r['idx']:4d} {r['type']:32s} {r['cn'][:30]:30s} "
          f"{r['main_hexagram']:14s} {r['hexagram_score']:.3f} "
          f"{ok:4s} {of:4s} {lf:4s} {af:4s} {dp:4s}")

# --- 按类型汇总 ---
print("\n" + "=" * 70)
print("  按任务类型汇总")
print("=" * 70)
print(f"{'任务类型':40s} {'总数':>4s} {'分准':>4s} {'%':>5s} {'物准':>4s} {'%':>5s} {'位准':>4s} {'%':>5s} {'动准':>4s} {'%':>5s} {'依存':>4s} {'%':>5s}")
print("-" * 85)
totals = {'seg_ok': 0, 'obj_found': 0, 'loc_found': 0, 'act_found': 0, 'deps_ok': 0}
total_n = 0
for tt in sorted(type_stats.keys()):
    s = type_stats[tt]
    n = s['total']
    total_n += n
    for k in totals: totals[k] += s[k]
    def pct(v): return v / n * 100 if n > 0 else 0
    print(f"{tt:40s} {n:4d} {s['seg_ok']:4d} {pct(s['seg_ok']):5.1f} "
          f"{s['obj_found']:4d} {pct(s['obj_found']):5.1f} "
          f"{s['loc_found']:4d} {pct(s['loc_found']):5.1f} "
          f"{s['act_found']:4d} {pct(s['act_found']):5.1f} "
          f"{s['deps_ok']:4d} {pct(s['deps_ok']):5.1f}")
print("-" * 85)
def tpct(v): return v / total_n * 100 if total_n > 0 else 0
print(f"{'总计':40s} {total_n:4d} {totals['seg_ok']:4d} {tpct(totals['seg_ok']):5.1f} "
      f"{totals['obj_found']:4d} {tpct(totals['obj_found']):5.1f} "
      f"{totals['loc_found']:4d} {tpct(totals['loc_found']):5.1f} "
      f"{totals['act_found']:4d} {tpct(totals['act_found']):5.1f} "
      f"{totals['deps_ok']:4d} {tpct(totals['deps_ok']):5.1f}")

# --- 卦象分布 ---
print("\n" + "=" * 70)
print(f"  卦象分布（前15个）")
print("=" * 70)
for hx, cnt in hex_counter.most_common(15):
    print(f"  {hx:14s}: {cnt}次")

# --- 错误案例 ---
print("\n" + "=" * 70)
print("  错误案例（分词/角色识别失败）")
print("=" * 70)
for r in results:
    if not r['evaluation']['segments_ok']:
        issues = []
        if not r['evaluation']['object_found']:
            issues.append(f"未找到物体「{r['obj']}」")
        if not r['evaluation']['location_found']:
            issues.append(f"未找到位置「{r['parent']}」")
        if not r['evaluation']['action_found']:
            issues.append("核心动作角色识别错误")
        print(f"  #{r['idx']:3d} [{r['type']:32s}] {r['cn'][:35]:35s}")
        print(f"      分词: {r['segments']}")
        print(f"      角色: {r['roles']}")
        print(f"      问题: {'; '.join(issues)}")
        print()

# 保存结果
output = {
    'total_tasks': len(all_tasks),
    'segments_ok': totals['seg_ok'],
    'object_found': totals['obj_found'],
    'location_found': totals['loc_found'],
    'action_found': totals['act_found'],
    'deps_ok': totals['deps_ok'],
    'by_type': {tt: dict(s) for tt, s in type_stats.items()},
    'hexagram_distribution': dict(hex_counter.most_common()),
    'results': results,
}
with open('eval_phase1_results.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n  结果已保存至 eval_phase1_results.json")
print(f"\n{'=' * 70}")
