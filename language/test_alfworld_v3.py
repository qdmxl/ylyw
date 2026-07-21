#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 → ALFWorld 逐步推理（V3修复版）

修复V2的三个关键问题：
1. take命令格式：只输出 "take plate 1"，不带 "from cabinet 1"
2. P3→P4过渡：clean完成后自动进入take阶段
3. 状态感知：根据admissible命令集的变化判断操作是否生效
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine

engine = HanziEngine(verbose=False)

# 翻译表
EN2CN = {
    "plate": "盘子", "bowl": "碗", "mug": "杯子", "apple": "苹果",
    "potato": "土豆", "tomato": "番茄", "bread": "面包", "egg": "鸡蛋",
    "milk": "牛奶", "coffee": "咖啡", "soap": "肥皂", "sponge": "海绵",
    "pencil": "笔", "pen": "笔", "paper": "纸", "book": "书", "key": "钥匙",
    "countertop": "柜台", "sinkbasin": "水槽", "fridge": "冰箱",
    "microwave": "微波炉", "cabinet": "柜子", "drawer": "抽屉",
    "shelf": "架子", "garbagecan": "垃圾桶", "desk": "桌子", "table": "桌子",
    "desk lamp": "台灯", "lamp": "灯", "toaster": "烤面包机",
    "coffeemachine": "咖啡机", "stoveburner": "灶台", "chair": "椅子",
    "diningtable": "餐桌", "sofa": "沙发", "bed": "床",
}
CN2EN = {v: k for k, v in EN2CN.items()}

def cn(w):
    w2 = re.sub(r'\s+\d+$', '', w.strip().lower())
    return EN2CN.get(w2, w)

def en(w):
    return CN2EN.get(w, w)

# ALFWorld环境
CURRENT_ENV = None
def get_env():
    global CURRENT_ENV
    if CURRENT_ENV is None:
        from alfworld_official_wrapper import ALFWorldOfficial
        CURRENT_ENV = ALFWorldOfficial()
    return CURRENT_ENV

def build_state_cn(obs, task_cn, feedback, step_inventory):
    """构建精炼中文状态（只保留YLYW需要的信息）"""
    lines = [f"任务：{task_cn}"]
    lines.append(f"上一步结果：{feedback}")
    
    # 位置
    for l in obs.split('\n'):
        l = l.strip()
        if 'You are' in l:
            cl = l
            for ek, ck in sorted(EN2CN.items(), key=lambda x: -len(x[0])):
                if ek in cl.lower():
                    cl = re.sub(ek, ck, cl, flags=re.I)
            lines.append(f"你在{cl[:60]}")
            break
    
    # 物品
    items = step_inventory
    if items:
        lines.append(f"你手里拿着{'、'.join(cn(i) for i in items)}。")
    else:
        lines.append("你手里没有东西。")
    
    # 关键观察（到达等信息）
    for l in obs.split('\n'):
        l = l.strip()
        if l.startswith('You arrive at'):
            cl = l
            for ek, ck in sorted(EN2CN.items(), key=lambda x: -len(x[0])):
                if ek in cl.lower():
                    cl = re.sub(ek, ck, cl, flags=re.I)
            lines.append(f"{cl[:60]}")
            break
    
    return '\n'.join(lines)

def run_task(game_idx=0, max_steps=30):
    env = get_env()
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get("task_desc", "")
    
    # 任务翻译
    task_cn = translate_task_cn(task_desc)
    
    print(f"{'='*65}")
    print(f"  🎯 ALFWorld #{game_idx}: {task_desc}")
    print(f"  📝 中文: {task_cn}")
    print(f"{'='*65}")
    print()
    
    # 状态
    phase = 0          # 0:探索 1:拿物 2:去预处理 3:预处理 4:取出 5:去目标 6:放置
    history = []
    phase_stuck = 0
    
    inventory = []  # 全局追踪
    
    for step in range(max_steps):
        # 提取库存：ALFWorld的carrying信息不总是出现在obs中
        # 从
        
        admissible = info.get('admissible_commands', ['look'])
        
        # —— 智能phase管理 ——
        # 根据admissible命令推断当前应该做什么
        cmd_set = set(c.split()[0].lower() if c.split() else '' for c in admissible)
        has_take = any(c.startswith('take ') for c in admissible)
        has_put = any(c.startswith('put ') for c in admissible)
        has_open = any(c.startswith('open ') for c in admissible)
        has_close = any(c.startswith('close ') for c in admissible)
        has_clean = any(c.startswith('clean ') for c in admissible)
        has_heat = any(c.startswith('heat ') for c in admissible)
        has_cool = any(c.startswith('cool ') for c in admissible)
        has_goto = any(c.startswith('go to') for c in admissible)
        
        # 自动phase推进（不依赖分词，依赖环境信号）
        need_clean = '洗' in task_cn or '干净' in task_cn
        need_heat = '加热' in task_cn or '热' in task_cn
        need_cool = '冷却' in task_cn or '冷' in task_cn
        need_preproc = need_clean or need_heat or need_cool
        
        # 目标物体和位置
        target_obj = None
        for oc, oe in [("盘子","plate"),("碗","bowl"),("杯子","mug"),("苹果","apple"),
                       ("牛奶","milk"),("咖啡","coffee"),("肥皂","soap"),("笔","pencil"),
                       ("食物","food")]:
            if oc in task_cn: target_obj = oe; break
        
        target_loc = None
        for lc, le in [("柜台","countertop"),("台子","countertop"),("架子","shelf"),
                       ("柜子","cabinet"),("碗柜","cabinet"),("桌子","desk"),
                       ("餐桌","diningtable")]:
            if lc in task_cn: target_loc = le; break
        
        preproc_loc = "sinkbasin" if need_clean else ("microwave" if need_heat else ("fridge" if need_cool else None))
        
        # ===== Phase 自动调整 =====
        if phase == 0:
            if has_take: phase = 1
        elif phase == 1:  # 拿物
            if inventory:  # 已经拿到了
                phase = 2 if need_preproc else 5
                phase_stuck = 0
        elif phase == 2:  # 去预处理
            if not has_goto or (preproc_loc and any(preproc_loc in c for c in admissible if c.startswith('clean') or c.startswith('put') or c.startswith('heat') or c.startswith('cool'))):
                phase = 3
                phase_stuck = 0
        elif phase == 3:  # 预处理
            if need_clean and not has_clean and not has_put:
                phase = 4
                phase_stuck = 0
            elif need_heat and not has_heat:
                phase = 4
                phase_stuck = 0
            elif need_cool and not has_cool:
                phase = 4
                phase_stuck = 0
            elif not need_preproc:
                phase = 5
                phase_stuck = 0
        elif phase == 4:  # 取出
            if inventory:
                phase = 5
                phase_stuck = 0
        elif phase == 5:  # 去目标
            if has_put and target_loc and any(target_loc in c for c in admissible):
                phase = 6
                phase_stuck = 0
            elif not has_goto:
                phase = 6
                phase_stuck = 0
        elif phase == 6:  # 放置
            pass
        
        # ===== 构建中文状态 → YLYW推理 =====
        feedback = history[-1] if history else "开始"
        cn_state = build_state_cn(obs, task_cn, feedback, inventory)
        result = engine.sentence(cn_state)
        
        verbs = [result['segments'][i] for i in range(len(result['segments'])) 
                 if result['segment_role'][i] == '动作']
        objs = [result['segments'][i] for i in range(len(result['segments'])) 
                if result['segment_role'][i] == '物体']
        
        # ===== YLYW + Phase → 选择动作 =====
        action = choose_action(phase, admissible, inventory, target_obj, target_loc,
                               preproc_loc, has_take, has_put, has_open, has_close,
                               has_clean, has_heat, has_cool, has_goto,
                               history, result)
        
        # 打印
        phase_names = ["探索","拿物","去预处理","预处理","取出","去目标","放置"]
        pname = phase_names[phase] if phase < len(phase_names) else f"P{phase}"
        print(f"  Step{step+1:2d} [{pname}] ", end="")
        print(f"主卦:{result['main_hexagram']}({result['hexagram_score']:.3f}) ", end="")
        print(f"动词:{verbs[:2]} 物体:{objs[:2]}")
        print(f"    → {action}")
        
        # 执行
        obs, info = env.step(action)
        history.append(action)
        
        # 检查成功
        if info.get('done') and info.get('reward', 0) > 0:
            print(f"  ✅ 任务成功完成！\n")
            break
    
    print(f"\n{'='*65}")
    print(f"  结果: {'✅ 成功' if (info.get('done') and info.get('reward', 0) > 0) else '❌ 未完成'}")
    print(f"  动作序列 ({len(history)}步):")
    for i, a in enumerate(history):
        print(f"    {i+1:2d}. {a}")
    print(f"{'='*65}")
    return history


def choose_action(phase, admissible, inventory, target_obj, target_loc,
                  preproc_loc, has_take, has_put, has_open, has_close,
                  has_clean, has_heat, has_cool, has_goto,
                  history, result):
    """基于Phase + admissible选择动作"""
    
    # 卡住检测：如果同一个命令重复3次
    recent = history[-4:] if len(history) >= 4 else history
    if len(recent) >= 3 and len(set(recent)) <= 2:
        # 换一个不同类型的命令
        last = recent[-1].split()[0] if recent else ''
        alt = [c for c in admissible if not c.startswith(last)]
        if alt: return alt[0]
    
    if phase == 0:  # 探索
        if has_take:
            return take_cmd(admissible, target_obj)
        if has_goto:
            # 优先去厨房区域（cabinet/countertop/sinkbasin）
            for c in admissible:
                for kw in ["cabinet", "countertop", "sinkbasin", "shelf", "fridge"]:
                    if c.startswith("go to") and kw in c:
                        return c
            return admissible[0] if admissible else "look"
        return "look"
    
    elif phase == 1:  # 拿物
        if has_take:
            cmd = take_cmd(admissible, target_obj)
            if cmd: return cmd
            # 没有简单格式的take，看看要不要open或go to
        if has_open:
            for c in admissible:
                if c.startswith("open "): return c
        if has_goto:
            return admissible[0]
        return "look"
    
    elif phase == 2:  # 去预处理
        if preproc_loc and has_goto:
            for c in admissible:
                if c.startswith("go to") and preproc_loc in c:
                    return c
        if has_clean or has_heat or has_cool:
            return process_cmd(admissible, preproc_loc, has_clean, has_heat, has_cool,
                              has_put, has_open, has_close)
        if has_goto:
            return admissible[0]
        return "look"
    
    elif phase == 3:  # 预处理
        return process_cmd(admissible, preproc_loc, has_clean, has_heat, has_cool,
                          has_put, has_open, has_close)
    
    elif phase == 4:  # 取出
        if has_take:
            cmd = take_cmd(admissible, target_obj)
            if cmd: return cmd
        if has_open:
            for c in admissible:
                if c.startswith("open "): return c
        if preproc_loc and has_goto:
            for c in admissible:
                if c.startswith("go to") and preproc_loc in c:
                    return c
        return "look"
    
    elif phase == 5:  # 去目标
        if target_loc and has_goto:
            for c in admissible:
                if c.startswith("go to") and target_loc in c:
                    return c
        if has_put:
            return put_cmd(admissible, target_loc)
        if has_goto:
            return admissible[0]
        return "look"
    
    elif phase == 6:  # 放置
        if has_open:
            for c in admissible:
                if c.startswith("open "): return c
        if has_put:
            return put_cmd(admissible, target_loc)
        if target_loc and has_goto:
            for c in admissible:
                if c.startswith("go to") and target_loc in c:
                    return c
        return "look"
    
    return admissible[0] if admissible else "look"


def take_cmd(admissible, target_obj):
    """
    拿物体。
    ALFWorld实际行为：
      - 'take plate 1' → Nothing happens（不接受）
      - 'take plate 1 from cabinet 1' → 成功（需要from）
    但有些情况下也有简单格式，都试试。
    """
    if target_obj:
        # 优先匹配目标物体的所有take命令
        obj_cmds = [c for c in admissible 
                   if c.startswith("take ") and target_obj in c.lower()]
        if obj_cmds:
            # 优先选带 from 的（ALFWorld多数场景需要这个格式）
            with_from = [c for c in obj_cmds if " from " in c]
            if with_from: return with_from[0]
            return obj_cmds[0]
    
    # 随便拿：优先带from格式
    with_from = [c for c in admissible if c.startswith("take ") and " from " in c]
    if with_from: return with_from[0]
    simple = [c for c in admissible if c.startswith("take ")]
    if simple: return simple[0]
    return None


def put_cmd(admissible, target_loc):
    """放置物体"""
    if target_loc:
        for c in admissible:
            if c.startswith("put ") and target_loc in c:
                return c
    for c in admissible:
        if c.startswith("put "):
            return c
    return "look"


def process_cmd(admissible, preproc_loc, has_clean, has_heat, has_cool,
                has_put, has_open, has_close):
    """预处理操作：按顺序 put → open → clean/heat/cool → close"""
    if preproc_loc:
        if has_put:
            for c in admissible:
                if c.startswith("put ") and preproc_loc in c:
                    return c
        if has_open:
            for c in admissible:
                if c.startswith("open ") and preproc_loc in c:
                    return c
        if has_clean:
            for c in admissible:
                if c.startswith("clean "): return c
        if has_heat:
            for c in admissible:
                if c.startswith("heat "): return c
        if has_cool:
            for c in admissible:
                if c.startswith("cool "): return c
        if has_close:
            for c in admissible:
                if c.startswith("close ") and preproc_loc in c:
                    return c
    return "look"


def translate_task_cn(task_en):
    task = task_en.lower().strip()
    patterns = [
        (r"put a clean (.+) on (.+)", "把{0}洗干净后放到{1}上"),
        (r"put a clean (.+) in (.+)", "把{0}洗干净后放到{1}里"),
        (r"clean (.+) and put it in (.+)", "把{0}洗干净后放到{1}里"),
        (r"clean (.+) and put it on (.+)", "把{0}洗干净后放到{1}上"),
        (r"heat (.+) and put it in (.+)", "把{0}加热后放到{1}里"),
        (r"heat (.+) and put it on (.+)", "把{0}加热后放到{1}上"),
        (r"put a chilled (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"put a cold (.+) in (.+)", "把{0}冷却后放到{1}里"),
        (r"cool (.+) and put it in (.+)", "把{0}冷却后放到{1}里"),
        (r"put (.+) in (.+)", "把{0}放到{1}里"),
        (r"put (.+) on (.+)", "把{0}放到{1}上"),
        (r"throw (.+) into (.+)", "把{0}扔进{1}"),
        (r"throw (.+) in (.+)", "把{0}扔进{1}"),
        (r"look at (.+) in (.+)", "用{1}的光看看{0}"),
        (r"turn on the (.+)", "打开{1}"),
    ]
    for pat, tmpl in patterns:
        m = re.match(pat, task)
        if m:
            groups = [cn(g) for g in m.groups()]
            try:
                return tmpl.format(*groups)
            except: continue
    return task

if __name__ == "__main__":
    run_task(0, 25)
