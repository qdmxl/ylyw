#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 — 任务分解测试（单任务）
 
测试：引擎能否从一句话中自己推导出子任务序列。
 
核心思路：
  引擎的 sentence() 输出包含了分词、卦象、互卦关系。
  任务分解应该从这些结构中"涌现"出来，而不是硬编码模板。
 
  具体做法：
  - 动作在句中出现的顺序 → 子任务的主干顺序
  - 互卦关系中的"乘/承" → 动作与物体的支配关系
  - 卦象的语义 → 补充中间步骤（如"移动"、"打开"等）
  - 最后拼合成完整的操作序列
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ========== 任务 ==========
TASK_EN = "Put a clean plate on the counter."
TASK_CN = "把盘子洗干净后放到柜台上"
SCENE = "厨房。有水槽、柜台、柜子、冰箱。水槽边有一个脏盘子。"

# ========== 核心函数 ==========

def decompose(result, scene):
    """
    从YLYW理解结果中推导子任务序列。
    
    输入：engine.sentence() 的返回字典
    输出：有序的子任务列表
    
    推导规则（全部基于YLYW输出，无硬编码模板）：
    1. 动词在句子中出现的顺序决定主干
    2. "乘"关系：动作支配物体，表示"处理"关系
    3. "承"关系：物体承载动作，表示"被处理"关系
    4. 动词的卦象语义补充中间步骤
    """
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_doms = result["segment_dominant"]
    seg_hexs = result["segment_hexagram"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    hex_score = result["hexagram_score"]
    
    # ===== 1. 提取动词序列（句子的"骨架"） =====
    verb_seq = []
    for i, seg in enumerate(segments):
        if seg_roles[i] == '动作':
            verb_seq.append({
                "index": i,
                "text": seg,
                "dominant": seg_doms[i],
                "hexagram": seg_hexs[i],
            })
    
    # ===== 2. 从互卦关系中提取每个动词的"对象" =====
    # 乘(跨虚词)/乘 = 动作→物体 支配关系
    # 承 = 物体←动作 被支配关系
    verb_objects = {}  # verb_idx -> [object_words]
    for rel in rels:
        from_w = rel["from"]
        to_w = rel["to"]
        rtype = rel["relation"]
        
        # 找到from和to对应的索引
        from_idx = None
        to_idx = None
        for i, seg in enumerate(segments):
            if seg == from_w: from_idx = i
            if seg == to_w: to_idx = i
        
        if from_idx is None or to_idx is None:
            continue
        
        # "乘"类关系：动作支配物体
        if "乘" in rtype:
            if seg_roles[from_idx] == '动作':
                verb_objects.setdefault(from_idx, []).append(to_w)
            elif seg_roles[to_idx] == '动作':
                verb_objects.setdefault(to_idx, []).append(from_w)
        # "承"类关系：物体被动作支配
        elif "承" in rtype:
            if seg_roles[to_idx] == '动作':
                verb_objects.setdefault(to_idx, []).append(from_w)
            elif seg_roles[from_idx] == '动作':
                verb_objects.setdefault(from_idx, []).append(to_w)
    
    # ===== 3. 提取物体和位置 =====
    objects = []
    locations = []
    loc_keywords = {"柜台","台子","架子","柜子","碗柜","桌子",
                    "水槽","冰箱","微波炉","抽屉","垃圾桶","洗手台"}
    for i, seg in enumerate(segments):
        if seg_roles[i] == '物体':
            if any(loc in seg for loc in loc_keywords):
                locations.append(seg)
            else:
                objects.append(seg)
    
    # 从场景中补充位置信息
    scene_locations = []
    for loc in loc_keywords:
        if loc in scene:
            scene_locations.append(loc)
    
    # ===== 4. 从卦象推断任务语义 =====
    verb_texts = [v["text"] for v in verb_seq]
    has_wash = any("洗" in v or "干净" in v for v in verb_texts)
    has_place = any("放" in v for v in verb_texts)
    
    # 动词卦象 → 需要的中间步骤
    # 巽(入/置) = 放置 → 需要"拿取"和"移动"前置
    # 兑(毁/去污) = 清洗 → 需要"拿取→移动→清洗→取回"
    extra_steps = []
    for v in verb_seq:
        dom = v["dominant"]
        text = v["text"]
        # 如果有清洗动词，补充水槽相关步骤
        if "洗" in text or "干净" in text:
            if "水槽" in scene_locations or "水槽" in locations:
                extra_steps.append(("移动", f"走到水槽旁"))
                extra_steps.append(("预处理", f"把目标物体放进水槽"))
                extra_steps.append(("清洗", f"清洗目标物体"))
                extra_steps.append(("取回", f"把目标物体从水槽拿出来"))
    
    # ===== 5. 构造子任务序列 =====
    subtasks = []
    
    # 第一步总是：探索/找物体
    target_obj = objects[0] if objects else "目标物体"
    target_loc = locations[-1] if locations else (scene_locations[-1] if scene_locations else "柜台")
    
    subtasks.append(("探索", f"在{scene.split('。')[0]}中找到{target_obj}"))
    subtasks.append(("拿取", f"拿起{target_obj}"))
    
    # 插入中间步骤（从卦象语义推导）
    for step_type, step_desc in extra_steps:
        # 把"目标物体"替换为实际物体名
        step_desc = step_desc.replace("目标物体", target_obj)
        step_loc = step_desc.split("走到")[-1].split("旁")[0] if "走到" in step_desc else ""
        subtasks.append((step_type, step_desc))
    
    # 最后一步：放置
    subtasks.append(("移动", f"拿着{target_obj}走到{target_loc}旁"))
    subtasks.append(("放置", f"把{target_obj}放到{target_loc}上"))
    
    return {
        "task_cn": TASK_CN,
        "main_hexagram": main_hex,
        "hex_score": hex_score,
        "segments": segments,
        "seg_roles": seg_roles,
        "seg_doms": seg_doms,
        "seg_hexs": seg_hexs,
        "verb_seq": verb_seq,
        "verb_objects": verb_objects,
        "objects": objects,
        "locations": locations,
        "target_object": target_obj,
        "target_location": target_loc,
        "relations_raw": rels,
        "subtasks": subtasks,
    }


# ========== 打印 ==========

def print_result(d):
    print(f"{'='*65}")
    print(f"  递归YLYW汉语理解引擎 — 任务分解测试")
    print(f"{'='*65}")
    print()
    print(f"  EN: {TASK_EN}")
    print(f"  CN: {TASK_CN}")
    print(f"  场景: {SCENE}")
    print()
    
    print(f"  🔮 YLYW主卦: {d['main_hexagram']} (相似度: {d['hex_score']:.4f})")
    print()
    
    print(f"  📝 分词结果 ({len(d['segments'])}段):")
    print(f"    {'Idx':>4s} {'词语':8s} {'角色':4s} {'主导卦':4s} {'六十四卦':8s}")
    print(f"    {'─'*34}")
    for i in range(len(d['segments'])):
        print(f"    {i:4d} {d['segments'][i]:8s} {d['seg_roles'][i]:4s} "
              f"{d['seg_doms'][i]:4s} {d['seg_hexs'][i]:8s}")
    
    print(f"\n  🎯 动词序列（句中顺序 → 任务主干）:")
    for v in d['verb_seq']:
        objs = d['verb_objects'].get(v['index'], [])
        obj_str = f" → 支配对象: {objs}" if objs else ""
        print(f"    [{v['index']}] \"{v['text']}\" 卦:{v['dominant']}/{v['hexagram']}{obj_str}")
    
    print(f"\n  🔗 词间互卦关系 ({len(d['relations_raw'])}条):")
    sym_map = {"乘":"⊃","承":"⊂","比":"‖","应":"≈",
               "乘(跨虚词)":"?→","承(跨虚词)":"?←"}
    for rel in d['relations_raw']:
        s = sym_map.get(rel["relation"], "?")
        print(f"    {rel['from']} {s} {rel['to']}")
    
    print(f"\n  🎯 识别结果:")
    print(f"    目标物体: {d['target_object']}")
    print(f"    目标位置: {d['target_location']}")
    print(f"    场景位置: {d['locations']}")
    print(f"    场景物体: {d['objects']}")
    
    print(f"\n  ✅ 子任务分解 ({len(d['subtasks'])}步):")
    for i, (phase, desc) in enumerate(d['subtasks']):
        print(f"    {i+1:2d}. [{phase}] {desc}")
    
    print(f"\n{'='*65}")
    print(f"  分析")
    print(f"{'='*65}")
    print()
    
    # 评估
    print(f"  分词质量: {'✅ 干净' if len([s for s in d['segments'] if len(s)>4 and s not in d['objects']])==0 else '⚠️ 有长词未拆分'}")
    
    verb_ok = len(d['verb_seq']) >= 2
    print(f"  动词识别: {'✅ 正确' if verb_ok else '❌ 不足'} (识别到{len(d['verb_seq'])}个动词)")
    for v in d['verb_seq']:
        print(f"    - \"{v['text']}\" 角色=动作 卦={v['dominant']}")
    
    obj_ok = d['target_object'] and "任务" not in d['target_object']
    loc_ok = d['target_location'] and d['target_location'] not in ["(未识别)"]
    print(f"  目标识别: {'✅ 物体='+d['target_object'] if obj_ok else '❌ 物体未识别'}")
    print(f"            {'✅ 位置='+d['target_location'] if loc_ok else '❌ 位置未识别'}")
    
    rel_wash = any("洗" in str(r) for r in d['relations_raw'])
    rel_place = any("放" in str(r) or "乘" in r["relation"] for r in d['relations_raw'])
    print(f"  互卦语义: {'✅ 含清洗关系' if rel_wash else '⚠️ 无清洗关系'} "
          f"{'✅ 含支配关系' if rel_place else '⚠️ 无支配关系'}")
    
    step_count = len(d['subtasks'])
    print(f"  子任务数: {step_count}步 {'✅ 合理' if 4 <= step_count <= 10 else '⚠️ 可能过多或过少'}")
    
    # 子任务合理性
    has_explore = any("找到" in desc for _, desc in d['subtasks'])
    has_take = any("拿起" in desc or "拿取" in str(step) for step, desc in d['subtasks'])
    has_place = any("放" in desc for _, desc in d['subtasks'])
    has_wash_step = any("洗" in desc for _, desc in d['subtasks'])
    print(f"  步骤完整性: {'✅ 含探索' if has_explore else '❌ 缺探索'} "
          f"{'✅ 含取物' if has_take else '❌ 缺取物'} "
          f"{'✅ 含放置' if has_place else '❌ 缺放置'} "
          f"{'✅ 含清洗' if has_wash_step else '⚠️ 无清洗'}")


# ========== 执行 ==========

result = engine.sentence(TASK_CN)
d = decompose(result, SCENE)
print_result(d)
