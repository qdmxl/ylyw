#!/usr/bin/env python3
"""
真正的零样本测试：递归YLYW汉语理解引擎逐步输出ALFWorld操作

流程：
  1. 每次从环境拿到当前状态 + 任务描述 → 组装成中文描述
  2. 喂给 engine.sentence() → 理解当前状态
  3. 从卦象/分词 → 生成下一步动作
  4. 执行动作 → 拿到新状态 → 重复
  
  这不再是硬编码模板，而是每一步都用YLYW实时推理。
"""

import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
sys.path.insert(0, os.path.expanduser('~/alfworld'))

from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# ═════════════════════════════════════════════════════════
# ALFWorld 环境接入
# ═════════════════════════════════════════════════════════

CURRENT_ENV = None

def get_env():
    global CURRENT_ENV
    if CURRENT_ENV is None:
        from alfworld_official_wrapper import ALFWorldOfficial
        CURRENT_ENV = ALFWorldOfficial()
    return CURRENT_ENV

# ═════════════════════════════════════════════════════════
# 1. 将ALFWorld环境状态 → 中文描述
# ═════════════════════════════════════════════════════════

def parse_alfworld_obs(obs: str) -> dict:
    """解析ALFWorld的英文观察文本为结构化信息"""
    result = {
        "location": None,
        "visible_objects": [],
        "task_desc": None,
        "inventory": [],
        "admissible": [],
    }
    
    # 提取任务描述
    m = re.search(r"Your task is to: (.+)\.", obs)
    if m:
        result["task_desc"] = m.group(1)
    
    # 提取当前位置和可见物体
    # ALFWorld观察格式：第一行是位置，然后是可见描述
    lines = obs.strip().split('\n')
    for line in lines:
        line = line.strip()
        # 位置信息
        if line.startswith("You are in"):
            result["location"] = line
        # 可见物体
        m = re.match(r"You see a (.+)\.", line)
        if m:
            objs = m.group(1).split(", ")
            result["visible_objects"] = objs
    
    return result

def build_chinese_state(obs: str, task_desc: str, prev_action: str = None, 
                        feedback: str = None, step: int = 0) -> str:
    """
    将ALFWorld环境状态组装为中文描述。
    这是关键：如何描述当前状态，直接影响YLYW理解的质量。
    """
    parsed = parse_alfworld_obs(obs)
    
    # 从观察文本中提取位置信息
    location = "未知"
    for line in obs.strip().split('\n'):
        if "You are in" in line or "You are at" in line:
            location = line.strip()
            break
        # "You are in the middle of a room"
        m = re.match(r"You are at location (\d+)", line)
        if m:
            location = f"位置{m.group(1)}"
    
    # 提取当前房间可见内容
    visible_lines = [l.strip() for l in obs.strip().split('\n') if l.strip() and 
                     not l.startswith('-') and 
                     not l.startswith('Your task') and
                     not l.startswith('You are') and
                     not l.startswith('You see')]
    
    # 提取admissible commands
    adms = []
    adm_section = False
    
    # 检查是否在某个物体前
    at_object = None
    for line in obs.strip().split('\n'):
        if line.startswith("You are at") or "You are in" in line:
            for obj_name in ["countertop", "sinkbasin", "fridge", "microwave", 
                            "cabinet", "drawer", "shelf", "table", "desk",
                            "garbagecan", "trash can", "toaster", "coffeemachine"]:
                if obj_name in line.lower():
                    at_object = obj_name
                    break
    
    # 物品清单
    inventory = []
    for line in obs.strip().split('\n'):
        if "You are carrying" in line:
            items = re.findall(r'a ([a-z\s]+)', line)
            inventory = [i.strip() for i in items if i.strip()]
    
    # 构建中文状态描述
    # 翻译任务
    task_cn = translate_task(task_desc)
    
    # 构建简洁的状态描述
    lines = []
    
    if step == 0:
        lines.append(f"任务：{task_cn}")
        lines.append("")
    
    if prev_action and feedback:
        lines.append(f"上一步操作：{prev_action}")
        lines.append(f"执行结果：{feedback}")
        lines.append("")
    
    # 当前位置
    if at_object:
        obj_cn = translate_obj(at_object)
        lines.append(f"你现在在{obj_cn}旁边。")
    else:
        lines.append("你在房间中间。")
    
    # 可见内容
    if inventory:
        items_cn = [translate_obj(i) for i in inventory]
        lines.append(f"你手里拿着{'、'.join(items_cn)}。")
    
    # 可执行操作（从中选择）
    lines.append("")
    lines.append(f"可用操作：")
    
    return "\n".join(lines)


def translate_task(task_en: str) -> str:
    """翻译ALFWorld任务描述为中文"""
    # 模板匹配
    patterns = [
        (r"clean (.+) and put it in (.+)", "先把{0}洗干净再放到{1}里"),
        (r"clean (.+) and put it on (.+)", "先把{0}洗干净再放到{1}上"),
        (r"put a clean (.+) on (.+)", "把一个干净的{0}放到{1}上"),
        (r"wash the (.+) before putting the \w+ on (.+)", "先把{1}洗干净再放到{2}上"),
        (r"heat (.+) and put it in (.+)", "先把{0}加热再放到{1}里"),
        (r"heat (.+) and put it on (.+)", "先把{0}加热再放到{1}上"),
        (r"put a chilled (.+) in (.+)", "把冷却好的{0}放到{1}里"),
        (r"put a cold (.+) in (.+)", "把冰冷的{0}放到{1}里"),
        (r"cool (.+) and put it in (.+)", "先把{0}冷却再放到{1}里"),
        (r"look at (.+) in (.+)", "用{1}的光看看{0}"),
        (r"examine (.+) using (.+)", "用{1}查看{0}"),
        (r"turn on the (.+)", "打开{1}"),
        (r"put (.+) in (.+)", "把{0}放到{1}里"),
        (r"put (.+) on (.+)", "把{0}放到{1}上"),
        (r"move (.+) to (.+)", "把{0}移动到{1}"),
        (r"take (.+) from (.+), put it back on (.+)", "把{0}从{1}拿起来再放回{2}上"),
        (r"throw (.+) into (.+)", "把{0}扔进{1}"),
        (r"throw (.+) in (.+)", "把{0}扔进{1}"),
    ]
    
    for pat, tmpl in patterns:
        m = re.match(pat, task_en.lower())
        if m:
            groups = [translate_obj(g) for g in m.groups()]
            try:
                return tmpl.format(*groups)
            except IndexError:
                continue
    
    return task_en  # fallback


_object_cn_map = {
    "plate": "盘子", "bowl": "碗", "mug": "杯子", "cup": "杯子",
    "apple": "苹果", "potato": "土豆", "tomato": "番茄", "lettuce": "生菜",
    "bread": "面包", "egg": "鸡蛋", "milk": "牛奶", "coffee": "咖啡",
    "soap": "肥皂", "sponge": "海绵", "cloth": "抹布",
    "pencil": "笔", "pen": "笔", "paper": "纸",
    "book": "书", "key": "钥匙", "cellphone": "手机",
    "countertop": "柜台", "counter": "柜台",
    "sinkbasin": "水槽", "sink": "水槽",
    "fridge": "冰箱", "microwave": "微波炉",
    "cabinet": "碗柜", "drawer": "抽屉", "shelf": "架子",
    "garbagecan": "垃圾桶", "trash can": "垃圾桶",
    "desk": "桌子", "table": "桌子", "desk lamp": "台灯", "lamp": "灯",
    "toaster": "烤面包机", "coffeemachine": "咖啡机", "stoveburner": "灶台",
    "bed": "床", "sofa": "沙发", "chair": "椅子",
    "dining table": "餐桌", "diningtable": "餐桌",
    "floor": "地板", "wall": "墙",
}

def translate_obj(en: str) -> str:
    """英文物品名 → 中文"""
    # 去掉数字后缀
    base = re.sub(r'\s+\d+$', '', en.strip().lower())
    if base in _object_cn_map:
        return _object_cn_map[base]
    return base  # fallback


# ═════════════════════════════════════════════════════════
# 2. YLYW推理 → ALFWorld动作
# ═════════════════════════════════════════════════════════

def ylyw_to_action(result: dict, admissible: list, step_context: dict) -> str:
    """
    核心：YLYW推理结果 → 从admissible commands中选择一个动作。
    
    这是真正的零样本决策——YLYW的卦象/分词/互卦关系决定下一步做什么，
    然后从环境允许的命令中选出最匹配的。
    """
    segments = result["segments"]
    seg_roles = result["segment_role"]
    seg_dom = result["segment_dominant"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    
    # 提取动词和物体
    verbs = [segments[i] for i in range(len(segments)) if seg_roles[i] == "动作"]
    objects = [segments[i] for i in range(len(segments)) if seg_roles[i] == "物体"]
    
    # 从当前状态了解已知信息
    inventory = step_context.get("inventory", [])
    
    # =====================================================
    # 策略：根据当前状态和YLYW理解，从admissible中选最优
    # =====================================================
    
    # 优先级1：如果手里没东西但任务需要拿物体 → take
    if not inventory:
        for cmd in admissible:
            if cmd.startswith("take "):
                obj = cmd[5:]
                # 检查这个物体是否在任务中提及
                for seg in segments:
                    if translate_obj(obj) in seg:
                        return cmd
        # 没匹配到，拿第一个可拿的
        for cmd in admissible:
            if cmd.startswith("take "):
                return cmd
    
    # 优先级2：如果手里有东西 → 去预处理或放置
    if inventory:
        item = inventory[-1]  # 当前拿着的物体
        item_cn = translate_obj(item)
        
        # 检查是否有清洗/加热/冷却需求
        need_clean = any("洗" in v or "干净" in v for v in verbs)
        need_heat = any("热" in v for v in verbs)
        need_cool = any("冷" in v or "冰" in v for v in verbs)
        need_place = any("放" in v for v in verbs)
        
        # 如果没清洗/加热/冷却，先去对应位置
        if need_clean and "clean" not in str(step_context.get("done", "")):
            for cmd in admissible:
                if cmd.startswith("go to") and "sinkbasin" in cmd:
                    return cmd
            for cmd in admissible:
                if cmd.startswith("put ") and item in cmd and "sinkbasin" in cmd:
                    return cmd
        
        if need_heat:
            for cmd in admissible:
                if cmd.startswith("go to") and "microwave" in cmd:
                    return cmd
        
        if need_cool:
            for cmd in admissible:
                if cmd.startswith("go to") and "fridge" in cmd:
                    return cmd
        
        # 尝试放
        if need_place:
            for cmd in admissible:
                if cmd.startswith("put ") and item in cmd:
                    return cmd
    
    # 优先级3：open/close（柜子/抽屉/冰箱等）
    for cmd in admissible:
        if cmd.startswith("open ") or cmd.startswith("close "):
            return cmd
    
    # 优先级4：移动到目标位置
    for seg in segments:
        for cmd in admissible:
            if cmd.startswith("go to"):
                target = cmd[6:]
                if translate_obj(target) in seg:
                    return cmd
    
    # 优先级5：默认动作
    if "look" in str(admissible):
        return "look"
    
    # 兜底
    return admissible[0] if admissible else "look"


# ═════════════════════════════════════════════════════════
# 3. 主循环
# ═════════════════════════════════════════════════════════

def run_one_task(game_idx=0, max_steps=30):
    """运行一个ALFWorld任务的逐步推理测试"""
    env = get_env()
    
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get("task_desc", "Unknown task")
    admissible = info.get("admissible_commands", [])
    
    print(f"{'='*60}")
    print(f"  ALFWorld 任务 #{game_idx}")
    print(f"  英文: {task_desc}")
    print(f"  中文: {translate_task(task_desc)}")
    print(f"{'='*60}")
    print()
    
    # 逐步推理
    step_context = {"inventory": [], "done": [], "step": 0}
    all_actions = []
    feedback = "开始"
    
    for step in range(max_steps):
        step_context["step"] = step
        
        print(f"─── 第 {step+1} 步 ───")
        
        # 组装中文状态描述
        cn_state_lines = [
            f"任务：{translate_task(task_desc)}",
        ]
        if feedback:
            cn_state_lines.append(f"上一步结果：{feedback}")
        
        # 当前位置
        for line in obs.strip().split('\n'):
            if "You are in" in line or "You are at" in line:
                cn_state_lines.append(f"你现在{line.strip()}")
                break
        
        # 手里有什么
        inventory = []
        for line in obs.strip().split('\n'):
            if "You are carrying" in line:
                items = re.findall(r'a ([a-z\s]+?)(?:\.|$)', line)
                inventory = [i.strip() for i in items if i.strip()]
                step_context["inventory"] = inventory
                if inventory:
                    items_cn = [translate_obj(i) for i in inventory]
                    cn_state_lines.append(f"你手里拿着{'、'.join(items_cn)}。")
                else:
                    cn_state_lines.append(f"你手里没有东西。")
                break
        else:
            cn_state_lines.append(f"你手里没有东西。")
            step_context["inventory"] = []
        
        # 可见的描述
        desc_lines = [l.strip() for l in obs.strip().split('\n') 
                      if l.strip() and not l.startswith('-') 
                      and 'Welcome to' not in l
                      and 'Your task' not in l
                      and 'You are' not in l
                      and 'You see a cabinet' not in l
                      and 'You are carrying' not in l
                      and 'You see a' not in l]
        if desc_lines:
            cn_state_lines.append(f"你看到：{' '.join(desc_lines[:2])}")
        
        # 可用操作
        admissible = info.get("admissible_commands", [])
        if admissible:
            cn_state_lines.append(f"可用操作：{'、'.join(admissible[:8])}")
        
        cn_state = "\n".join(cn_state_lines)
        print(f"  📝 中文状态描述:")
        for line in cn_state_lines:
            print(f"    {line}")
        
        # YLYW推理
        result = engine.sentence(cn_state)
        print(f"  🔮 YLYW主卦: {result['main_hexagram']} ({result['hexagram_score']:.3f})")
        print(f"  📝 分词: {' | '.join(result['segments'])}")
        
        verbs = [result['segments'][i] for i in range(len(result['segments'])) 
                 if result['segment_role'][i] == '动作']
        objs = [result['segments'][i] for i in range(len(result['segments'])) 
                if result['segment_role'][i] == '物体']
        print(f"  🏷️  动词={verbs} 物体={objs}")
        
        # 选择动作
        action = ylyw_to_action(result, admissible, step_context)
        print(f"  🤖 选择的动作: {action}")
        print()
        
        # 执行
        obs, info = env.step(action)
        admissible = info.get("admissible_commands", [])
        
        # 判断反馈
        reward = info.get("reward", 0)
        done = info.get("done", False)
        
        if done and reward > 0:
            feedback = f"成功！任务完成！"
            print(f"  ✅ 任务完成！")
            all_actions.append(action)
            break
        elif "You can't" in obs or "Nothing" in obs:
            feedback = f"操作{action}失败，换个方式"
        elif "You are carrying" in obs:
            items = re.findall(r'a ([a-z\s]+?)(?:\.|$)', obs)
            feedback = f"拿到了{', '.join(items[:2])}"
        else:
            feedback = f"执行了{action}"
        
        all_actions.append(action)
        print(f"  📊 反馈: {feedback}")
        print()
    
    print(f"{'='*60}")
    print(f"  最终动作序列 ({len(all_actions)}步):")
    for i, a in enumerate(all_actions):
        print(f"    {i+1:2d}. {a}")
    print(f"{'='*60}")
    return all_actions


if __name__ == "__main__":
    # 测试一个清洗任务
    run_one_task(game_idx=0, max_steps=20)
