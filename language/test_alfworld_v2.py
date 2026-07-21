#!/usr/bin/env python3
"""
测试：递归YLYW汉语理解引擎 → ALFWorld任务规划
V2版 — 修正评估逻辑，精确分析推理链质量

不再试图从分词直接映射动作，而是评估引擎的核心能力：
1. 分词是否合理（动词/物体/位置区分）
2. 卦象是否匹配任务类型
3. 互卦关系是否正确捕获语义结构（动作→物体支配关系）
4. 六爻64维分布能否区分不同任务
"""

import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# 64卦名列表（用于显示）
HEX_NAMES = [
    "乾为天","坤为地","水雷屯","山水蒙","水天需","天水讼","地水师","水地比",
    "风天小畜","天泽履","地天泰","天地否","天火同人","火天大有","地山谦","雷地豫",
    "泽雷随","山风蛊","地临","风地观","火雷噬嗑","山火贲","山地剥","地雷复",
    "天雷无妄","山天大畜","山雷颐","泽风大过","坎为水","离为火",
    "泽山咸","雷风恒","天山遁","雷天大壮","火地晋","地火明夷",
    "风火家人","火泽睽","水山蹇","雷水解","山泽损","风雷益",
    "泽天夬","天风姤","泽地萃","地风升","泽水困","水风井",
    "泽火革","火风鼎","震为雷","艮为山","风山渐","雷泽归妹",
    "雷火丰","火山旅","巽为风","兑为泽","风水涣","水泽节",
    "风泽中孚","雷山小过","水火既济","火水未济"
]

# 任务类型 → 期望卦象簇
TASK_HEX_CLUSTERS = {
    "pick_and_place":      {"乾","兑","坤","泽天夬","天泽履","地天泰","天地否"},
    "pick_clean_then":     {"坎","水","水风井","水山蹇","风水涣"},
    "pick_heat_then":      {"离","火","火风鼎","火天大有","天火同人","泽火革"},
    "pick_cool_then":      {"坎","水","水天需","水地比","天水讼"},
    "look_at_obj":         {"离","火","火地晋","离为火"},
    "pick_two":            {"乾","震","山天大畜","天雷无妄"},
}

TEST_TASKS = [
    {
        "id": "T1", "type": "pick_and_place_simple",
        "scene": "厨房。有一个柜台(counter)、一个桌子(table)、一个冰箱(fridge)。桌子上有一个苹果。",
        "task": "把苹果放到柜台上",
        "expected_hex_cluster": "pick_and_place",
        "expected_verbs": ["放","拿","取"],
        "expected_objects": ["苹果","柜台"],
        "expected_relations": ["乘"],  # 动作支配物体
    },
    {
        "id": "T2", "type": "pick_clean_then_place",
        "scene": "厨房。有一个水槽(sinkbasin)、一个柜台(counter)。水槽旁边有一个脏的盘子。",
        "task": "先把脏盘子洗干净，再放到柜台上",
        "expected_hex_cluster": "pick_clean_then",
        "expected_verbs": ["洗","干净","放"],
        "expected_objects": ["盘子","柜台"],
        "expected_relations": ["乘"],
    },
    {
        "id": "T3", "type": "pick_heat_then_place",
        "scene": "厨房。有一个微波炉(microwave)、一个冰箱(fridge)。冰箱里有食物。",
        "task": "把食物加热后放到台子上",
        "expected_hex_cluster": "pick_heat_then",
        "expected_verbs": ["加热","放"],
        "expected_objects": ["食物","台子"],
        "expected_relations": ["乘"],
    },
    {
        "id": "T4", "type": "pick_cool_then_place",
        "scene": "厨房。有一个冰箱(fridge)、一个碗柜(cabinet)。柜台上有一杯热咖啡。",
        "task": "把热咖啡冷却后放到碗柜里",
        "expected_hex_cluster": "pick_cool_then",
        "expected_verbs": ["冷却","放"],
        "expected_objects": ["咖啡","碗柜"],
        "expected_relations": ["乘"],
    },
    {
        "id": "T5", "type": "look_at_obj_in_light",
        "scene": "卧室。有一张桌子(desk)、一个台灯(desk lamp)。桌子上有一个杯子。",
        "task": "打开台灯，看看杯子",
        "expected_hex_cluster": "look_at_obj",
        "expected_verbs": ["打开","看"],
        "expected_objects": ["台灯","杯子"],
        "expected_relations": ["乘","比"],
    },
    {
        "id": "T6", "type": "pick_two_obj_and_place",
        "scene": "浴室。有一个垃圾桶(trash can)、一个洗手台。洗手台上有两块肥皂。",
        "task": "把两块肥皂都扔到垃圾桶里",
        "expected_hex_cluster": "pick_two",
        "expected_verbs": ["扔","放"],
        "expected_objects": ["肥皂","垃圾桶"],
        "expected_relations": ["乘"],
    },
    {
        "id": "T7", "type": "pick_from_closed",
        "scene": "客厅。有一个抽屉(drawer)、一个架子(shelf)。抽屉里有一支笔。",
        "task": "把抽屉里的笔拿出来放到架子上",
        "expected_hex_cluster": "pick_and_place",
        "expected_verbs": ["拿","放","拿出"],
        "expected_objects": ["笔","抽屉","架子"],
        "expected_relations": ["承","乘"],
    },
    {
        "id": "T8", "type": "pick_clean_then_complex",
        "scene": "厨房。水槽(sinkbasin)边有一个脏碗。",
        "task": "把脏碗洗干净后放到架子上",
        "expected_hex_cluster": "pick_clean_then",
        "expected_verbs": ["洗","干净","放"],
        "expected_objects": ["碗","架子"],
        "expected_relations": ["乘"],
    },
    {
        "id": "T9", "type": "pick_cool_then_real",
        "scene": "厨房。冰箱(fridge)在餐桌旁边。餐桌上有一杯热牛奶。",
        "task": "把热牛奶冷却后放到柜子里",
        "expected_hex_cluster": "pick_cool_then",
        "expected_verbs": ["冷却","放"],
        "expected_objects": ["牛奶","柜子"],
        "expected_relations": ["乘"],
    },
]

def analyze(result):
    """对YLYW推理结果进行结构化分析"""
    text = result["text"]
    segments = result["segments"]
    hex_name = result["main_hexagram"]
    hex_score = result["hexagram_score"]
    hex64 = result["hex64"]
    yao = result["yao_vector"]
    seg_dom = result["segment_dominant"]
    seg_role = result["segment_role"]
    seg_hex = result["segment_hexagram"]
    rels = [r["relation"] for r in result["mutua_relations"]]

    # 提取动词（动作角色词）
    verbs = [segments[i] for i in range(len(segments)) if seg_role[i] == "动作"]
    # 提取物体
    objects = [segments[i] for i in range(len(segments)) if seg_role[i] == "物体"]
    # 提取名词结尾词
    noun_ends = [s for s in segments if s]

    # hex64的top5
    top5 = sorted(range(64), key=lambda i: hex64[i], reverse=True)[:5]
    top5_names = [HEX_NAMES[i] for i in top5]

    # 64维分布的活跃度（>0.4的维度数）
    active_dims = sum(1 for v in hex64 if v > 0.4)

    return {
        "segments": segments,
        "verbs": verbs,
        "objects": objects,
        "dominants": seg_dom,
        "roles": seg_role,
        "segment_hexagrams": seg_hex,
        "hexagram": hex_name,
        "hex_score": hex_score,
        "top5_hexagrams": top5_names,
        "hex64_active_dims": active_dims,
        "relations": rels,
        "yao_summary": f"均值={sum(yao)/len(yao):.3f} 范围=[{min(yao):.3f},{max(yao):.3f}]",
    }

def score(analysis, expected):
    """评分：-2到+10分，每个维度独立打分"""
    scores = {}
    details = []

    # 1. 分词质量 (0-2分)
    segments = analysis["segments"]
    has_verb = any(analysis["verbs"])
    has_obj = any(analysis["objects"])
    seg_quality = 0
    if segments:
        seg_quality += 0.5
    if has_verb:
        seg_quality += 0.5
    if has_obj:
        seg_quality += 0.5
    # 虚词被正确分离（如"把"、"到"、"后"独立成词）
    func_words_found = sum(1 for s in segments if s in "把到的后里上都")
    if func_words_found >= 2:
        seg_quality += 0.5
    scores["分词质量"] = seg_quality
    details.append(f"分词: {segments} | 动词={analysis['verbs']} 物体={analysis['objects']}")

    # 2. 卦象合理性 (0-2分)
    cluster = TASK_HEX_CLUSTERS[expected["expected_hex_cluster"]]
    hex_name = analysis["hexagram"]
    hex_match = 0
    if hex_name in cluster:
        hex_match = 1.5
    # 还检查top5是否命中cluster
    top5_hits = sum(1 for h in analysis["top5_hexagrams"] if h in cluster)
    hex_match += min(top5_hits * 0.25, 0.5)
    scores["卦象匹配度"] = hex_match
    details.append(f"主卦={hex_name}({analysis['hex_score']:.3f}) top5={analysis['top5_hexagrams']}")

    # 3. 动词/物体召回率 (0-2分)
    exp_verbs = set(expected["expected_verbs"])
    exp_objs = set(expected["expected_objects"])
    act_verbs = set(analysis["verbs"])
    act_objs = set(analysis["objects"])
    
    verb_recall = len(exp_verbs & act_verbs) / max(len(exp_verbs), 1)
    obj_recall = len(exp_objs & act_objs) / max(len(exp_objs), 1)
    semantic_score = (verb_recall + obj_recall) * 1.0
    scores["语义召回率"] = semantic_score
    details.append(f"动词命中={act_verbs & exp_verbs}/{exp_verbs} 物体命中={act_objs & exp_objs}/{exp_objs}")

    # 4. 互卦关系捕获 (0-2分)
    rels = analysis["relations"]
    exp_rels = expected.get("expected_relations", [])
    rel_hits = sum(1 for r in exp_rels if any(r in rel_str for rel_str in rels))
    rel_score = rel_hits / max(len(exp_rels), 1) * 2.0
    scores["关系捕获"] = rel_score
    details.append(f"互卦关系={list(set(rels))}")

    # 5. 64维分布区分度 (0-2分)
    active = analysis["hex64_active_dims"]
    # 活跃维度太多(=模糊)、太少(=过聚焦)都不好
    if 8 <= active <= 35:
        diff_score = 2.0
    elif 5 <= active < 8 or 35 < active <= 45:
        diff_score = 1.0
    else:
        diff_score = 0.5
    scores["64维区分度"] = diff_score
    details.append(f"64维活跃维度={active}")

    total = sum(scores.values())
    return total, scores, details


print("=" * 80)
print("  递归YLYW 汉语理解引擎 — ALFWorld任务规划深度评估")
print("=" * 80)
print()

all_results = []
total_scores = []

for task in TEST_TASKS:
    tid = task["id"]
    ttype = task["type"]
    scene = task["scene"]
    task_desc = task["task"]

    print("-" * 80)
    print(f"📋 {tid}: [{ttype}]")
    print(f"   指令: {task_desc}")
    print()

    result = engine.sentence(task_desc)
    analysis = analyze(result)
    total, scores_dict, details = score(analysis, task)

    # 打印详细结果
    print(f"  🔮 主卦: {analysis['hexagram']} ({result['hexagram_score']:.3f})")
    print(f"  📝 分词: {' | '.join(analysis['segments'])}")
    print(f"  🏷️  词卦: ", end="")
    for i, seg in enumerate(analysis['segments']):
        role = analysis['roles'][i]
        dom = analysis['dominants'][i]
        hex_s = analysis['segment_hexagrams'][i]
        print(f"{seg}[{dom}/{hex_s}/{role[:1]}]", end=" ")
    print()
    print(f"  🔗 互卦: {', '.join(analysis['relations'])}")
    print()

    # 评分详情
    print(f"  📊 评分:")
    for dim, sval in scores_dict.items():
        bar = "█" * int(sval * 5) + "░" * (10 - int(sval * 5))
        print(f"    {dim}: {sval:.1f}/2.0 {bar}")

    dm = details
    if dm:
        print(f"  💬 分析:")
        for d in dm:
            print(f"    {d}")

    print(f"\n  ⭐ 总分: {total:.1f}/10.0")

    all_results.append((tid, task["task"], analysis))
    total_scores.append(total)
    print()

print("=" * 80)
print("  综合统计")
print("=" * 80)
avg = sum(total_scores) / len(total_scores)
print(f"  平均分: {avg:.1f}/10.0")
print(f"  最高分: {max(total_scores):.1f}")
print(f"  最低分: {min(total_scores):.1f}")
print(f"  通过(≥6分): {sum(1 for s in total_scores if s >= 6)}/{len(total_scores)}")
print(f"  优秀(≥8分): {sum(1 for s in total_scores if s >= 8)}/{len(total_scores)}")
print()

if total_scores:
    print("  分任务排名:")
    for tid, s in sorted(zip([t["id"] for t in TEST_TASKS], total_scores), 
                         key=lambda x: x[1], reverse=True):
        bar = "█" * int(s) + "░" * (10 - int(s))
        print(f"    {tid}: {s:.1f}/10.0 {bar}")

print("=" * 80)

# 总体结论
weak_points = []
for task, score_val in zip(TEST_TASKS, total_scores):
    if score_val < 6:
        weak_points.append(task["task"])

print()
print("📌 关键发现:")
print(f"  - 9个ALFWorld任务中，{sum(1 for s in total_scores if s >= 6)}个达到及格线")
if weak_points:
    print(f"  - 弱项任务: {len(weak_points)}个")
    for wp in weak_points:
        print(f"    · {wp}")
print()
print("📌 模型能力总结:")
print("  ✅ 分词：", end="")
if sum(1 for r in all_results if r[2]["verbs"]) >= 7:
    print("动词/物体识别基本正常")
else:
    print("分词精度不足，动词/物体容易误判")
print("  ✅ 卦象推理：", end="")
hex_good = sum(1 for r in all_results if r[2]["hex_score"] > 0.5)
if hex_good >= 7:
    print(f"主卦命中率高({hex_good}/9)")
else:
    print(f"主卦有一定参考价值({hex_good}/9)")
print("  ✅ 语义结构：", end="")
rel_good = sum(1 for r in all_results if len(r[2]["relations"]) >= 2)
if rel_good >= 6:
    print(f"互卦关系捕获了核心语义({rel_good}/9)")
else:
    print(f"互卦关系仍需改进({rel_good}/9)")
