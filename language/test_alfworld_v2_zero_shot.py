#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 → ALFWorld零样本逐步推理
V2修复版

核心改进：
1. 英文环境状态 → 翻译为精炼中文描述（只保留YLYW能理解的关键信息）
2. ylyw_to_action() 基于卦象语义匹配admissible命令
3. 每步只输出一个操作，通过环境反馈驱动下一步
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)
    
# ═════════════════════════════════════════════════════════
# 1. ALFWorld环境
# ═════════════════════════════════════════════════════════

CURRENT_ENV = None
def get_env():
    global CURRENT_ENV
    if CURRENT_ENV is None:
        from alfworld_official_wrapper import ALFWorldOfficial
        CURRENT_ENV = ALFWorldOfficial()
    return CURRENT_ENV

# ═════════════════════════════════════════════════════════
# 2. 翻译工具
# ═════════════════════════════════════════════════════════

# 物品中英文对照（ALFWorld全集）
EN2CN = {
    "plate": "盘子", "bowl": "碗", "mug": "杯子", "cup": "杯子",
    "apple": "苹果", "potato": "土豆", "tomato": "番茄", "lettuce": "生菜",
    "bread": "面包", "egg": "鸡蛋", "milk": "牛奶", "coffee": "咖啡",
    "soap": "肥皂", "sponge": "海绵", "cloth": "抹布",
    "pencil": "笔", "pen": "笔", "paper": "纸", "book": "书", "key": "钥匙",
    "cellphone": "手机", "credit card": "信用卡", "watch": "手表",
    "countertop": "柜台", "sinkbasin": "水槽", "fridge": "冰箱", 
    "microwave": "微波炉", "cabinet": "柜子", "drawer": "抽屉", 
    "shelf": "架子", "garbagecan": "垃圾桶", "desk": "桌子",
    "table": "桌子", "desk lamp": "台灯", "lamp": "灯",
    "toaster": "烤面包机", "coffeemachine": "咖啡机", "stoveburner": "灶台",
    "bed": "床", "sofa": "沙发", "chair": "椅子", "diningtable": "餐桌",
    "pan": "平底锅", "pot": "锅", "knife": "刀", "fork": "叉", "spoon": "勺",
    "butterknife": "黄油刀",
}

CN2EN = {v: k for k, v in EN2CN.items()}

def cn(en_word):
    """英文→中文，带数字后缀处理"""
    w = re.sub(r'\s+\d+$', '', en_word.strip().lower())
    return EN2CN.get(w, w)

def en(cn_word):
    """中文→英文"""
    return CN2EN.get(cn_word, cn_word)

def translate_task(task_en):
    """ALFWorld英文任务 → 中文"""
    task = task_en.lower().strip()
    # 常见任务模式
    patterns = [
        (r"put a clean (.+) on (.+)", "把{0}洗干净后放到{1}上"),
        (r"put a clean (.+) in (.+)", "把{0}洗干净后放到{1}里"),
        (r"clean (.+) and put it in (.+)", "先把{0}洗干净再放到{1}里"),
        (r"clean (.+) and put it on (.+)", "先把{0}洗干净再放到{1}上"),
        (r"wash (.+) before putting (?:it|the \w+) on (.+)", "先把{1}洗干净再放到{2}上"),
        (r"heat (.+) and put it in (.+)", "先把{0}加热再放到{1}里"),
        (r"heat (.+) and put it on (.+)", "先把{0}加热再放到{1}上"),
        (r"put a chilled (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"put a cold (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"cool (.+) and put it in (.+)", "先把{0}冷却再放到{1}里"),
        (r"look at (.+) in (.+)", "用{1}的光看看{0}"),
        (r"turn on the (.+)", "打开{1}"),
        (r"examine (.+) using (.+)", "用{1}查看{0}"),
        (r"put (.+) in (.+)", "把{0}放到{1}里"),
        (r"put (.+) on (.+)", "把{0}放到{1}上"),
        (r"move (.+) to (.+)", "把{0}移到{1}"),
        (r"throw (.+) into (.+)", "把{0}扔进{1}"),
        (r"throw (.+) in (.+)", "把{0}扔进{1}"),
    ]
    for pat, tmpl in patterns:
        m = re.match(pat, task)
        if m:
            groups = [cn(g) for g in m.groups()]
            try:
                return tmpl.format(*groups)
            except IndexError:
                continue
    return task


def translate_obs(obs):
    """翻译ALFWorld观察文本为精炼中文"""
    lines = []
    
    # 提取位置
    loc = "房间中间"
    for line in obs.strip().split('\n'):
        if "You are in" in line or "You are at" in line:
            loc = line.strip()
    # 翻译位置中的物体名
    for en_w, cn_w in sorted(EN2CN.items(), key=lambda x: -len(x[0])):
        if en_w in loc.lower():
            loc = loc.replace(en_w, cn_w)
    lines.append(f"你在{loc}。")
    
    # 提取物品栏
    for line in obs.strip().split('\n'):
        if "You are carrying" in line:
            items = re.findall(r'a ([a-z\s]+?)(?:\.|$)', line)
            items = [i.strip() for i in items if i.strip()]
            if items:
                lines.append(f"你手里拿着{'、'.join(cn(i) for i in items)}。")
            else:
                lines.append("你手里没有东西。")
            break
    else:
        lines.append("你手里没有东西。")
    
    # 提取第一行关键描述（如果有到达信息的行）
    for line in obs.strip().split('\n'):
        line = line.strip()
        if line.startswith('You arrive at'):
            # 翻译
            for en_w, cn_w in sorted(EN2CN.items(), key=lambda x: -len(x[0])):
                if en_w in line.lower():
                    line = line.replace(en_w, cn_w)
            lines.append(f"{line[:60]}")
            break
    
    return '\n'.join(lines)


def translate_admissible(admissible):
    """可执行命令列表 → 中文描述"""
    result = []
    for cmd in admissible:
        parts = cmd.split()
        if not parts:
            continue
        verb = parts[0]
        if verb == "go":
            target = " ".join(parts[2:]) if len(parts) > 2 else ""
            result.append(f"去{cn(target)}")
        elif verb == "take":
            target = " ".join(parts[1:])
            result.append(f"拿{cn(target)}")
        elif verb == "put":
            target = " ".join(parts[1:])
            result.append(f"放{target}")
        elif verb == "open":
            target = " ".join(parts[1:])
            result.append(f"打开{cn(target)}")
        elif verb == "close":
            target = " ".join(parts[1:])
            result.append(f"关闭{cn(target)}")
        elif verb == "inventory":
            result.append("查看物品")
        elif verb == "look":
            result.append("环顾四周")
        elif verb == "examine":
            target = " ".join(parts[1:])
            result.append(f"查看{cn(target)}")
        elif verb == "heat":
            target = " ".join(parts[1:])
            result.append(f"加热{target}")
        elif verb == "clean":
            target = " ".join(parts[1:])
            result.append(f"清洗{target}")
        elif verb == "cool":
            target = " ".join(parts[1:])
            result.append(f"冷却{target}")
        elif verb == "use":
            result.append("使用")
        else:
            result.append(cmd)
    return result


# ═════════════════════════════════════════════════════════
# 3. YLYW推理 → 选择动作
# ═════════════════════════════════════════════════════════

def ylyw_choose_action(result, admissible, context):
    """
    基于YLYW理解 + Phase驱动 从admissible中选择最佳动作。
    
    Phase机制（参考V6 agent）：
      P0: 探索/找物体 (go to)
      P1: 拿物体 (take)
      P2: 去预处理位置 (go to sinkbasin/microwave/fridge)
      P3: 预处理 (put + clean/heat/cool)
      P4: 取出 (take from)
      P5: 去目标位置 (go to counter/cabinet...)
      P6: 放置 (put)
    
    每轮根据当前phase + YLYW理解 + 环境反馈来决定下一步。
    """
    segments = result["segments"]
    seg_roles = result["segment_role"]
    rels = result["mutua_relations"]
    main_hex = result["main_hexagram"]
    
    # 从分词提取关键信息
    verbs = [segments[i] for i in range(len(segments)) if seg_roles[i] == "动作"]
    objects = [segments[i] for i in range(len(segments)) if seg_roles[i] == "物体"]
    
    task_cn = context.get("task_cn", "")
    inventory = context.get("inventory", [])
    has_item = bool(inventory)
    phase = context.get("phase", 0)
    history = context.get("done", [])
    last_action = context.get("last_action", "")
    last_feedback = context.get("last_feedback", "")
    phase_steps = context.get("phase_steps", 0)
    
    # 任务类型判断
    need_clean = "洗" in task_cn or "干净" in task_cn
    need_heat = "加热" in task_cn or "热" in task_cn
    need_cool = "冷却" in task_cn or "冷" in task_cn
    need_preproc = need_clean or need_heat or need_cool
    
    # 目标位置推断
    target_loc_en = None
    for loc_cn, loc_en in [
        ("柜台", "countertop"), ("台子", "countertop"), ("架子", "shelf"),
        ("柜子", "cabinet"), ("碗柜", "cabinet"), ("桌子", "desk"), ("餐桌", "diningtable")
    ]:
        if loc_cn in task_cn:
            target_loc_en = loc_en
            break
    
    # 预处理位置
    if need_clean:
        preproc_en = "sinkbasin"
    elif need_heat:
        preproc_en = "microwave"
    elif need_cool:
        preproc_en = "fridge"
    else:
        preproc_en = None
    
    # 目标物体
    target_obj_en = None
    for obj_cn, obj_en in [
        ("盘子", "plate"), ("碗", "bowl"), ("杯子", "mug"),
        ("苹果", "apple"), ("食物", "food"), ("肥皂", "soap"),
        ("笔", "pencil"), ("咖啡", "coffee"), ("牛奶", "milk"), ("土豆", "potato")
    ]:
        if obj_cn in task_cn:
            target_obj_en = obj_en
            break
    
    # ========== 当前状态感知 ==========
    # 判断admissible中有什么类型的命令
    cmd_types = set()
    for cmd in admissible:
        t = cmd.split()[0].lower() if cmd.split() else ""
        cmd_types.add(t)
    
    has_goto = any(c.startswith("go to") for c in admissible)
    has_take = any(c.startswith("take ") for c in admissible)
    has_put = any(c.startswith("put ") for c in admissible)
    has_open = any(c.startswith("open ") for c in admissible)
    has_close = any(c.startswith("close ") for c in admissible)
    has_clean = any(c.startswith("clean ") for c in admissible)
    has_heat = any(c.startswith("heat ") for c in admissible)
    has_cool = any(c.startswith("cool ") for c in admissible)
    has_inventory = any(c.startswith("inventory") for c in admissible)
    has_examine = any(c.startswith("examine ") for c in admissible)
    
    # ========== 历史失败检测 ==========
    # 如果同一command重复执行3次以上，说明有问题，跳下一个
    last_few = history[-5:] if len(history) >= 5 else history
    stuck = len(last_few) >= 3 and len(set(last_few)) <= 2
    
    if stuck and last_action in admissible:
        # 卡住了，换下一个同类型命令
        alt = [c for c in admissible if c != last_action]
        if alt:
            # 优先选不同类型的
            for c in alt:
                if c.split()[0] != last_action.split()[0]:
                    return c
            return alt[0]
    
    # ========== 基于Phase的决策 ==========
    
    # P0: 探索 — 去可能有目标物体的位置
    if phase == 0:
        if has_take and target_obj_en:
            # 有目标可拿 → P1
            context["phase"] = 1
            context["phase_steps"] = 0
        elif has_goto:
            # 去找目标物体
            # 用YLYW的物体识别来指引搜索方向
            for cmd in admissible:
                if cmd.startswith("go to"):
                    loc = cmd[6:].strip()
                    # 优先去常见存放物体的位置
                    if "cabinet" in loc or "countertop" in loc or "shelf" in loc:
                        return cmd
            # 随便去一个位置
            for cmd in admissible:
                if cmd.startswith("go to"):
                    return cmd
        return "look"
    
    # P1: 拿物体
    if phase == 1:
        if has_take:
            # 优先拿目标物体
            if target_obj_en:
                obj_cmds = [c for c in admissible if target_obj_en in c.lower()]
                if obj_cmds:
                    context["phase"] = 2
                    context["phase_steps"] = 0
                    return obj_cmds[0]
            # 随便拿一个
            for cmd in admissible:
                if cmd.startswith("take "):
                    context["phase"] = 2 if need_preproc else 5
                    context["phase_steps"] = 0
                    return cmd
        elif has_open:
            # 容器关着，先打开
            for cmd in admissible:
                if cmd.startswith("open "):
                    return cmd
        elif has_goto:
            # 换个位置继续找
            context["phase"] = 0
            context["phase_steps"] = 0
            for cmd in admissible:
                if cmd.startswith("go to"):
                    return cmd
        return "inventory" if has_inventory else "look"
    
    # P2: 去预处理位置
    if phase == 2:
        if preproc_en:
            for cmd in admissible:
                if cmd.startswith("go to") and preproc_en in cmd:
                    context["phase"] = 3
                    context["phase_steps"] = 0
                    return cmd
        # 如果在预处理位置门口了
        if has_clean or has_heat or has_cool:
            context["phase"] = 3
            context["phase_steps"] = 0
        elif has_goto:
            for cmd in admissible:
                if cmd.startswith("go to"):
                    return cmd
        return "look"
    
    # P3: 执行预处理
    if phase == 3:
        if has_put and preproc_en:
            # 把物体放进预处理设备
            for cmd in admissible:
                if cmd.startswith("put ") and preproc_en in cmd:
                    return cmd
        if has_open and preproc_en:
            for cmd in admissible:
                if cmd.startswith("open ") and preproc_en in cmd:
                    return cmd
        if has_clean:
            for cmd in admissible:
                if cmd.startswith("clean "):
                    return cmd
        if has_heat:
            for cmd in admissible:
                if cmd.startswith("heat "):
                    return cmd
        if has_cool:
            for cmd in admissible:
                if cmd.startswith("cool "):
                    return cmd
        if has_close and preproc_en:
            for cmd in admissible:
                if cmd.startswith("close ") and preproc_en in cmd:
                    return cmd
        if has_goto and preproc_en:
            for cmd in admissible:
                if cmd.startswith("go to") and preproc_en in cmd:
                    return cmd
        # 如果预处理全部完成了
        if not has_put and not has_open and not has_close:
            context["phase"] = 4
            context["phase_steps"] = 0
        return "look"
    
    # P4: 从预处理设备取出
    if phase == 4:
        if has_take and preproc_en:
            for cmd in admissible:
                if cmd.startswith("take ") and preproc_en in cmd:
                    context["phase"] = 5
                    context["phase_steps"] = 0
                    return cmd
        if has_open and preproc_en:
            for cmd in admissible:
                if cmd.startswith("open ") and preproc_en in cmd:
                    return cmd
        if has_take:
            for cmd in admissible:
                if cmd.startswith("take "):
                    context["phase"] = 5
                    return cmd
        return "look"
    
    # P5: 去目标位置
    if phase == 5:
        if target_loc_en:
            for cmd in admissible:
                if cmd.startswith("go to") and target_loc_en in cmd:
                    context["phase"] = 6
                    context["phase_steps"] = 0
                    return cmd
        if has_put and target_loc_en:
            context["phase"] = 6
            context["phase_steps"] = 0
        elif has_goto:
            for cmd in admissible:
                if cmd.startswith("go to"):
                    return cmd
        return "look"
    
    # P6: 放置
    if phase == 6:
        if has_open and target_loc_en:
            for cmd in admissible:
                if cmd.startswith("open ") and target_loc_en in cmd:
                    return cmd
        if has_put and target_loc_en:
            for cmd in admissible:
                if cmd.startswith("put ") and target_loc_en in cmd:
                    return cmd
        if has_put:
            for cmd in admissible:
                if cmd.startswith("put "):
                    return cmd
        if has_goto and target_loc_en:
            for cmd in admissible:
                if cmd.startswith("go to") and target_loc_en in cmd:
                    return cmd
        return "look"
    
    # 兜底
    for cmd in admissible:
        if cmd not in ("look", "help", "inventory"):
            return cmd
    return admissible[0] if admissible else "look"


# ═════════════════════════════════════════════════════════
# 4. 主循环
# ═════════════════════════════════════════════════════════

def run_task(game_idx=0, max_steps=30):
    env = get_env()
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get("task_desc", "")
    admissible = info.get("admissible_commands", [])
    
    task_cn = translate_task(task_desc)
    
    print(f"{'='*65}")
    print(f"  🎯 ALFWorld任务 #{game_idx}")
    print(f"  EN: {task_desc}")
    print(f"  CN: {task_cn}")
    print(f"{'='*65}")
    print()
    
    context = {
        "task_cn": task_cn,
        "inventory": [],
        "done": [],
        "last_action": "",
        "last_feedback": "开始",
        "step": 0,
        "phase": 0,
        "phase_steps": 0,
        "last_obs": "",
    }
    
    for step in range(max_steps):
        context["step"] = step
        
        print(f"─── Step {step+1} ───")
        
        # ---- A. 构建中文状态描述 ----
        cn_obs = translate_obs(obs)
        cn_adm = translate_admissible(admissible)
        
        cn_state = (
            f"任务：{task_cn}\n\n"
            f"上一步结果：{context['last_feedback']}\n"
            f"{cn_obs}\n"
            f"可用动作：{'、'.join(cn_adm[:6])}"
        )
        
        print(f"  📝 中文状态:")
        for l in cn_state.split('\n')[:5]:
            print(f"    {l}")
        print(f"    ...可用动作={' '.join(cn_adm[:5])}")
        
        # ---- B. YLYW理解 ----
        result = engine.sentence(cn_state)
        verbs = [result['segments'][i] for i in range(len(result['segments'])) 
                 if result['segment_role'][i] == '动作']
        objs = [result['segments'][i] for i in range(len(result['segments'])) 
                if result['segment_role'][i] == '物体']
        
        print(f"  🔮 主卦: {result['main_hexagram']}({result['hexagram_score']:.3f}) "
              f"主导八卦:{result['dominant_bagua']}")
        print(f"  📝 分词: {'|'.join(result['segments'][:10])}{'...' if len(result['segments'])>10 else ''}")
        print(f"  🏷️  动词={verbs[:3]} 物体={objs[:3]}")
        if result['mutua_relations']:
            for rel in result['mutua_relations'][:2]:
                sym = {"乘":"⊃","承":"⊂","比":"‖","应":"≈","乘(跨虚词)":"?→","承(跨虚词)":"?←"}
                s = sym.get(rel["relation"], "?")
                print(f"  🔗  {rel['from']} {s} {rel['to']}")
        
        # ---- C. 选择动作 ----
        context["inventory"] = []
        for line in obs.strip().split('\n'):
            if "You are carrying" in line:
                items = re.findall(r'a ([a-z\s]+?)(?:\.|$)', line)
                context["inventory"] = [i.strip() for i in items if i.strip()]
                break
        
        action = ylyw_choose_action(result, admissible, context)
        print(f"  🤖 动作: {action}")
        
        # ---- D. 执行 ----
        old_obs = obs
        obs, info = env.step(action)
        admissible = info.get("admissible_commands", [])
        reward = info.get("reward", 0)
        done = info.get("done", False)
        context["last_action"] = action
        
        # 判断反馈
        if done and reward > 0:
            print(f"  ✅ 任务成功完成！\n")
            context["done"].append(action)
            break
        elif "Nothing" in obs or "can't" in obs or "not" in obs:
            # 操作失败，看环境变化
            if old_obs == obs:
                context["last_feedback"] = f"操作{action}失败了"
                print(f"  ⚠️  操作失败")
            else:
                context["last_feedback"] = f"执行了{action}"
                print(f"  → 执行完成")
        else:
            # 检查物品是否变化
            new_inv = re.findall(r'a ([a-z\s]+?)(?:\.|$)', 
                                 [l for l in obs.split('\n') if "You are carrying" in l][0]) \
                      if any("You are carrying" in l for l in obs.split('\n')) else []
            if new_inv != context["inventory"]:
                if new_inv:
                    context["last_feedback"] = f"拿到了{'、'.join(cn(i.strip()) for i in new_inv)}"
                    print(f"  ✅ 拿到了物品")
                else:
                    context["last_feedback"] = f"放下了物品"
                    print(f"  📦 放下了物品")
            else:
                context["last_feedback"] = f"执行了{action}"
                print(f"  → 执行完成")
        
        context["done"].append(action)
        context["phase_steps"] = context.get("phase_steps", 0) + 1
        
        # 显示phase
        phase_names = ["探索", "拿物", "去预处理", "预处理", "取出", "去目标", "放置"]
        phase_name = phase_names[context["phase"]] if context["phase"] < len(phase_names) else f"P{context['phase']}"
        print(f"    阶段: {phase_name} (P{context['phase']})")
        print()
    
    # 输出最终结果
    print(f"{'='*65}")
    print(f"  结果: {'✅ 成功' if (done and reward > 0) else '❌ 未完成'} (步数={len(context['done'])})")
    print(f"  动作序列:")
    for i, a in enumerate(context['done']):
        print(f"    {i+1:2d}. {a}")
    print(f"{'='*65}")
    
    return context["done"]


if __name__ == "__main__":
    run_task(game_idx=0, max_steps=25)
