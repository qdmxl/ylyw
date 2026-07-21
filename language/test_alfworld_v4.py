#!/usr/bin/env python3
"""
递归YLYW汉语理解引擎 → ALFWorld 逐步推理（V4）

基于实际环境行为修正：
- take命令必须带from：'take plate 1 from cabinet 1' ✅
- take成功后obs是'You pick up...'，没有'carrying'行
- 拿到的物品会进入隐式inventory，要track
- 清洗前需要先 put X in/on sinkbasin
    
流程：探索→拿物→去sinkbasin→put→clean→take→去countertop→put
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine
engine = HanziEngine(verbose=False)

EN2CN = {
    'plate':'盘子','bowl':'碗','mug':'杯子','apple':'苹果',
    'potato':'土豆','tomato':'番茄','bread':'面包','egg':'鸡蛋',
    'milk':'牛奶','coffee':'咖啡','soap':'肥皂','pencil':'笔',
    'countertop':'柜台','sinkbasin':'水槽','fridge':'冰箱',
    'microwave':'微波炉','cabinet':'柜子','drawer':'抽屉',
    'shelf':'架子','garbagecan':'垃圾桶','desk':'桌子','table':'桌子',
    'desk lamp':'台灯','lamp':'灯','toaster':'烤面包机',
    'coffeemachine':'咖啡机','stoveburner':'灶台','diningtable':'餐桌',
}

def cn(w):
    w2 = re.sub(r'\s+\d+$','',w.strip().lower())
    return EN2CN.get(w2,w)

CURRENT_ENV = None
def get_env():
    global CURRENT_ENV
    if CURRENT_ENV is None:
        from alfworld_official_wrapper import ALFWorldOfficial
        CURRENT_ENV = ALFWorldOfficial()
    return CURRENT_ENV

def parse_task(task_en):
    t = task_en.lower().strip()
    # 提取关键元素
    obj, loc = None, None
    need_clean = bool(re.search(r'clean|wash', t))
    need_heat = bool(re.search(r'heat', t))
    need_cool = bool(re.search(r'cool|chill', t))
    
    # 提取物体
    for oc, oe in [('plate','plate'),('bowl','bowl'),('mug','mug'),('cup','mug'),
                   ('apple','apple'),('potato','potato'),('soap','soap'),
                   ('pencil','pencil'),('coffee','coffee'),('milk','milk'),
                   ('food','food'),('bread','bread'),('egg','egg')]:
        if oc in t: obj = oe; break
    
    # 提取位置
    for lc, le in [('countertop','countertop'),('counter','countertop'),
                   ('cabinet','cabinet'),('shelf','shelf'),('drawer','drawer'),
                   ('desk','desk'),('table','desk'),('dining table','diningtable'),
                   ('garbagecan','garbagecan'),('trash','garbagecan')]:
        if lc in t: loc = le; break
    
    # 中文翻译
    target_en, loc_en = obj, loc
    if need_clean:
        task_cn = f"把{cn(obj or '物品')}洗干净后放到{cn(loc or '柜台')}上"
    elif need_heat:
        task_cn = f"把{cn(obj or '物品')}加热后放到{cn(loc or '柜台')}上"
    elif need_cool:
        task_cn = f"把{cn(obj or '物品')}冷却后放到{cn(loc or '柜台')}里"
    else:
        task_cn = f"把{cn(obj or '物品')}放到{cn(loc or '柜台')}上"
    
    return task_cn, obj, loc, need_clean, need_heat, need_cool

def run_task(game_idx=0, max_steps=30):
    env = get_env()
    obs, info = env.reset(game_idx=game_idx)
    task_desc = info.get('task_desc', '')
    task_cn, target_obj, target_loc, need_clean, need_heat, need_cool = parse_task(task_desc)
    need_preproc = need_clean or need_heat or need_cool
    
    print(f"{'='*65}")
    print(f"  🎯 ALFWorld #{game_idx}: {task_desc}")
    print(f"  📝 中文: {task_cn}")
    print(f"  🎯 目标: 物体={target_obj} 位置={target_loc}")
    print(f"  🔧 预处理: {'清洗' if need_clean else '加热' if need_heat else '冷却' if need_cool else '无'}")
    print(f"{'='*65}\n")
    
    # Phase定义
    P_EXPLORE, P_TAKE, P_GOTO_PREPROC, P_PREPROC, P_RETRIEVE, P_GOTO_TARGET, P_PLACE = range(7)
    phase = P_EXPLORE
    history = []
    
    for step in range(max_steps):
        admissible = info.get('admissible_commands', ['look'])
        
        cmd_types = set()
        for c in admissible:
            cmd_types.add(c.split()[0].lower() if c.split() else '')
        has_take = any(c.startswith('take ') for c in admissible)
        has_put = any(c.startswith('put ') for c in admissible)
        has_open = any(c.startswith('open ') for c in admissible)
        has_close = any(c.startswith('close ') for c in admissible)
        has_clean = any(c.startswith('clean ') for c in admissible)
        has_heat = any(c.startswith('heat ') for c in admissible)
        has_cool = any(c.startswith('cool ') for c in admissible)
        has_goto = any(c.startswith('go to') for c in admissible)
        
        preproc_loc = 'sinkbasin' if need_clean else ('microwave' if need_heat else ('fridge' if need_cool else None))
        
        # ===== 智能phase调整 =====
        if phase == P_EXPLORE:
            if has_take: phase = P_TAKE
        elif phase == P_TAKE:
            # 判断是否已经拿到了：obs中 'You pick up' 或 'pick up'
            if 'pick up' in obs.lower() or 'you take' in obs.lower():
                phase = P_GOTO_PREPROC if need_preproc else P_GOTO_TARGET
        elif phase == P_GOTO_PREPROC:
            # 到达预处理位置后，admissible中会出现 put/clean/heat/cool
            if not has_goto or (preproc_loc and any(preproc_loc in c for c in admissible 
                if any(c.startswith(x) for x in ['put','clean','heat','cool']))):
                phase = P_PREPROC
        elif phase == P_PREPROC:
            # 预处理完成后，没有clean/heat/cool/put命令了
            if not has_clean and not has_heat and not has_cool and not has_put:
                phase = P_RETRIEVE
        elif phase == P_RETRIEVE:
            if has_take:
                phase = P_GOTO_TARGET
            else:
                # 可能需要先open
                pass
        elif phase == P_GOTO_TARGET:
            if target_loc and any(target_loc in c for c in admissible if c.startswith('put ')):
                phase = P_PLACE
            elif not has_goto:
                phase = P_PLACE
        elif phase == P_PLACE:
            pass
        
        # ===== 中文状态 → YLYW理解（用于打印，不用于决策）=====
        obs_lines = [l.strip() for l in obs.split('\n') if l.strip() and 
                     not l.startswith('-') and 'Welcome' not in l]
        cn_state = f"任务：{task_cn}\n上一步：{history[-1] if history else '开始'}"
        cn_state += f"\n当前位置：{obs_lines[0][:50] if obs_lines else '未知'}"
        cn_state += f"\n你手里{'有东西' if 'pick up' in obs.lower() else '没有东西'}"
        
        result = engine.sentence(cn_state)
        verbs = [result['segments'][i] for i in range(len(result['segments'])) 
                 if result['segment_role'][i] == '动作']
        objs = [result['segments'][i] for i in range(len(result['segments'])) 
                if result['segment_role'][i] == '物体']
        
        # ===== 选择动作 =====
        action = pick_action(phase, admissible, target_obj, target_loc, preproc_loc,
                            has_take, has_put, has_open, has_close,
                            has_clean, has_heat, has_cool, has_goto)
        
        # 输出
        phase_names = ['探索','拿物','去预处理','预处理','取出','去目标','放置']
        pn = phase_names[phase] if phase < len(phase_names) else f'P{phase}'
        print(f"  S{step+1:2d}[{pn}] 主卦:{result['main_hexagram']}({result['hexagram_score']:.3f}) 动:{verbs[:2]} 物:{objs[:2]}")
        print(f"       → {action}")
        
        # 执行
        if not action:
            print("  ⚠️  无可用操作")
            break
        obs, info = env.step(action)
        history.append(action)
        
        if info.get('done') and info.get('reward', 0) > 0:
            print(f"\n  ✅ 任务成功！\n")
            break
    
    print(f"{'='*65}")
    print(f"  结果: {'✅ 成功' if (info.get('done') and info.get('reward',0)>0) else '❌ 未完成'}")
    print(f"  动作 ({len(history)}步):")
    for i,a in enumerate(history):
        print(f"    {i+1:2d}. {a}")
    print(f"{'='*65}")
    return history


def pick_action(phase, admissible, target_obj, target_loc, preproc_loc,
                has_take, has_put, has_open, has_close,
                has_clean, has_heat, has_cool, has_goto):
    
    P_EXPLORE, P_TAKE, P_GOTO_PREPROC, P_PREPROC, P_RETRIEVE, P_GOTO_TARGET, P_PLACE = range(7)
    
    if phase == P_EXPLORE:
        if has_take:  # 已经找到物体
            return _take(admissible, target_obj)
        # 优先去有目标物体的位置
        if target_obj and has_goto:
            # 常见存放位置
            for loc_kw in ['cabinet','countertop','shelf','drawer','fridge']:
                for c in admissible:
                    if c.startswith('go to') and loc_kw in c:
                        return c
        if has_goto:
            return _goto(admissible)
        return 'look'
    
    elif phase == P_TAKE:
        if has_take:
            return _take(admissible, target_obj)
        if has_open:
            return _open(admissible)
        if has_goto:
            return _goto(admissible)
        return 'look'
    
    elif phase == P_GOTO_PREPROC:
        if preproc_loc and has_goto:
            for c in admissible:
                if c.startswith('go to') and preproc_loc in c:
                    return c
        return _preproc(admissible, preproc_loc, has_put, has_open, has_close,
                       has_clean, has_heat, has_cool, has_goto)
    
    elif phase == P_PREPROC:
        return _preproc(admissible, preproc_loc, has_put, has_open, has_close,
                       has_clean, has_heat, has_cool, has_goto)
    
    elif phase == P_RETRIEVE:
        if has_take:
            return _take(admissible, target_obj)
        if has_open and preproc_loc:
            for c in admissible:
                if c.startswith('open') and preproc_loc in c:
                    return c
        if has_goto and preproc_loc:
            for c in admissible:
                if c.startswith('go to') and preproc_loc in c:
                    return c
        return 'look'
    
    elif phase == P_GOTO_TARGET:
        if target_loc and has_goto:
            for c in admissible:
                if c.startswith('go to') and target_loc in c:
                    return c
        if has_put:
            return _put(admissible, target_loc)
        if has_goto:
            return _goto(admissible)
        return 'look'
    
    elif phase == P_PLACE:
        if has_open and target_loc:
            for c in admissible:
                if c.startswith('open') and target_loc in c:
                    return c
        if has_put:
            return _put(admissible, target_loc)
        if target_loc and has_goto:
            for c in admissible:
                if c.startswith('go to') and target_loc in c:
                    return c
        return 'look'
    
    return admissible[0] if admissible else 'look'


def _take(admissible, target_obj):
    """拿物体。ALFWorld中带from的格式才是正确的"""
    if target_obj:
        for c in admissible:
            if c.startswith('take ') and target_obj in c.lower():
                return c
    # 随便拿一个
    for c in admissible:
        if c.startswith('take '):
            return c
    return None

def _put(admissible, target_loc):
    if target_loc:
        for c in admissible:
            if c.startswith('put ') and target_loc in c:
                return c
    for c in admissible:
        if c.startswith('put '):
            return c
    return None

def _open(admissible):
    for c in admissible:
        if c.startswith('open '):
            return c
    return None

def _goto(admissible):
    for c in admissible:
        if c.startswith('go to'):
            return c
    return None

def _preproc(admissible, preproc_loc, has_put, has_open, has_close,
             has_clean, has_heat, has_cool, has_goto):
    if preproc_loc:
        # 先放进去
        if has_put:
            for c in admissible:
                if c.startswith('put ') and preproc_loc in c:
                    return c
        # 打开
        if has_open:
            for c in admissible:
                if c.startswith('open ') and preproc_loc in c:
                    return c
        # 执行预处理
        if has_clean:
            for c in admissible:
                if c.startswith('clean '): return c
        if has_heat:
            for c in admissible:
                if c.startswith('heat '): return c
        if has_cool:
            for c in admissible:
                if c.startswith('cool '): return c
        # 关闭
        if has_close:
            for c in admissible:
                if c.startswith('close ') and preproc_loc in c:
                    return c
        # goto
        if has_goto:
            for c in admissible:
                if c.startswith('go to') and preproc_loc in c:
                    return c
    return 'look'

if __name__ == '__main__':
    run_task(0, 25)
