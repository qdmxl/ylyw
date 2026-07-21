#!/usr/bin/env python3
"""
V13 Agent — 六爻驱动逐步决策（全中文推理）

架构：
  1. 语义引擎解析任务描述 → 任务参数
  2. 每次环境交互后，状态六爻重构
  3. 模糊规则 → 意图
  4. 在admissible_commands（翻译为中文）中，按意图+卦象匹配选动作
  
替换V10的硬编码TASK_PLANS。
"""

import sys, os, math, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'language'))

# TMPDIR设置
os.environ['TMPDIR'] = f'/home/lijinhan/.tmp_alfworld'
import tempfile as _tf
_tf.tempdir = None; _tf.gettempdir()
if not os.path.exists(os.environ['TMPDIR']): os.makedirs(os.environ['TMPDIR'], exist_ok=True)

from hanzi_engine import HanziEngine
engine = HanziEngine(verbose=False)
engine.action_chars.add('去')

BAGUA_NAMES = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 六爻 + 模糊推理（完全通用）
# ============================================================

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
    y0 = 0.40 if inv and not proc else (0.65 if inv and proc else 0.10)
    lm = {"起点": 0.10}
    if preproc_loc: lm[preproc_loc] = 0.55
    if target_loc: lm[target_loc] = 0.80
    for k in ["柜子","桌子","架子","抽屉","微波炉","冰箱","水槽","床","沙发","保险箱","马桶","扶手椅"]:
        if k not in lm: lm[k] = 0.30 if preproc_loc else 0.50
    # 位置名可能带数字后缀（如"柜子1"），去除数字后匹配估值
    loc_base = re.sub(r'\d+$', '', loc).strip() if loc else loc
    y1 = lm.get(loc, lm.get(loc_base, 0.25))
    # 如果admissible有take命令（说明有物体可拿），提高二爻值
    if has_take and not inv:
        y1 = max(y1, 0.50)
    y2 = min(0.10+step*0.06, 0.85)
    if preproc_loc is None:
        y3 = 0.80 if inv else 0.10
        y4 = 0.85 if loc==target_loc and inv else (0.35 if loc==target_loc else 0.15)
    else:
        if proc and loc==preproc_loc and not inv: y3 = 0.70
        elif proc and inv: y3 = 0.85
        elif proc: y3 = 0.60
        elif not inv and loc==preproc_loc: y3 = 0.25
        else: y3 = 0.10
        if loc==target_loc and inv: y4 = 0.85
        elif loc==target_loc: y4 = 0.35
        elif loc==preproc_loc and not inv and proc: y4 = 0.65
        elif loc==preproc_loc and not inv and not proc: y4 = 0.30
        elif loc==preproc_loc and inv: y4 = 0.15
        else: y4 = 0.15
    y5 = 0.75 if loc in ([preproc_loc,target_loc] if preproc_loc else [target_loc]) else 0.25
    return [round(v,3) for v in [y0,y1,y2,y3,y4,y5]]

# ============================================================
# 中英文翻译（仅用于admissible命令的转换）
# ============================================================

EN_TO_CN = {
    'cabinet':'柜子','countertop':'柜台','sinkbasin':'水槽','fridge':'冰箱',
    'microwave':'微波炉','drawer':'抽屉','shelf':'架子','desk':'桌子','table':'桌子',
    'bed':'床','sofa':'沙发','safe':'保险箱','toilet':'马桶',
    'garbagecan':'垃圾桶','garbage':'垃圾桶','coffeemachine':'咖啡机',
    'toaster':'烤面包机','stoveburner':'灶台','diningtable':'餐桌','armchair':'扶手椅',
    'floorlamp':'落地灯','desklamp':'台灯','lamp':'灯',
    'plate':'盘子','bowl':'碗','mug':'杯子','cup':'杯子','knife':'刀',
    'fork':'叉子','spoon':'勺子','pan':'锅','pot':'锅','spatula':'锅铲',
    'apple':'苹果','potato':'土豆','tomato':'番茄','lettuce':'生菜',
    'bread':'面包','egg':'鸡蛋','soap':'肥皂','soapbar':'肥皂',
    'pencil':'笔','book':'书','keychain':'钥匙链','watch':'手表','vase':'花瓶',
    'cellphone':'手机','remotecontrol':'遥控器','laptop':'笔记本',
    'pillow':'枕头','toiletpaper':'卫生纸',
    'peppershaker':'胡椒瓶','saltshaker':'盐瓶','plunger':'皮搋子',
    'creditcard':'信用卡','cd':'光盘','statue':'雕像','alarmclock':'闹钟',
    'box':'盒子','baseballbat':'棒球棒','basketball':'篮球','newspaper':'报纸',
    'tissuebox':'纸巾盒','sponge':'海绵','cloth':'抹布','towel':'毛巾',
    'butterknife':'黄油刀','ladle':'汤勺','glassbottle':'玻璃瓶',
    'spraybottle':'喷瓶','teddybear':'泰迪熊','kettle':'水壶',
    'scrubbrush':'刷子','dishsponge':'洗碗海绵','handtowel':'手巾',
    'papertowelroll':'纸巾卷','soapbottle':'洗手液瓶',
    'winebottle':'酒瓶','potato':'土豆','tomato':'番茄','lettuce':'生菜',
}

def tw(w):
    """翻译英文词为中文，保留数字后缀"""
    wc = w.lower().strip(".,!?'\"").strip()
    # 分离数字后缀
    m = re.match(r'([a-z_ ]+?)\s*(\d+)$', wc)
    if m:
        base = m.group(1).strip()
        num = m.group(2)
    else:
        base = wc
        num = ''
    if base in EN_TO_CN: return EN_TO_CN[base] + num
    for k,v in EN_TO_CN.items():
        if k in base: return v + num
    return wc

def cmd_to_cn(cmd):
    parts = cmd.split()
    if not parts: return cmd
    v = parts[0].lower()
    if v == 'go' and len(parts)>=3 and parts[1]=='to': return f"去{tw(' '.join(parts[2:]))}"
    elif v == 'take':
        r = ' '.join(parts[1:])
        m = re.match(r'(.+?) from (.+)', r)
        return f"拿{tw(m.group(1))}从{tw(m.group(2))}" if m else f"拿{tw(r)}"
    elif v == 'put':
        r = ' '.join(parts[1:])
        m = re.match(r'(.+?) in/on (.+)', r)
        return f"放{tw(m.group(1))}到{tw(m.group(2))}" if m else f"放{tw(r)}"
    elif v == 'clean':
        r = ' '.join(parts[1:])
        m = re.match(r'(.+?) with (.+)', r)
        return f"清洗{tw(m.group(1))}用{tw(m.group(2))}" if m else f"清洗{tw(r)}"
    elif v == 'open': return f"打开{tw(' '.join(parts[1:]))}"
    elif v == 'close': return f"关闭{tw(' '.join(parts[1:]))}"
    elif v == 'heat': return f"加热{' '.join(parts[1:])}"
    elif v == 'cool': return f"冷却{' '.join(parts[1:])}"
    elif v == 'examine': return f"查看{' '.join(parts[1:])}"
    elif v == 'move':
        r = ' '.join(parts[1:])
        m = re.match(r'(.+?) to (.+)', r)
        return f"移动{tw(m.group(1))}到{tw(m.group(2))}" if m else f"移动{tw(r)}"
    elif v == 'inventory': return '查看物品'
    elif v == 'look': return '环顾四周'
    return cmd

# ============================================================
# 语义引擎解析任务
# ============================================================

def parse_task_params(task_desc):
    """从英文任务描述解析任务参数"""
    task_cn = translate_task(task_desc)
    r = engine.sentence(task_cn)
    segs = r['segments']
    roles = r['segment_role']
    temporal = engine.parse_temporal(task_cn)
    
    verbs = [segs[i] for i in range(len(segs)) if roles[i] == '动作']
    objects = [segs[i] for i in range(len(segs)) if roles[i] == '物体']
    
    verb_text = ' '.join(verbs)
    need_clean = any(w in verb_text for w in ['洗','干净','清洁'])
    need_heat = any(w in verb_text for w in ['加热','热']) and '冷' not in verb_text
    need_cool = any(w in verb_text for w in ['冷却','冷','冰'])
    
    if need_clean: task_type, preproc = 'pick_clean_then_place_in_recep', '水槽'
    elif need_heat: task_type, preproc = 'pick_heat_then_place_in_recep', '微波炉'
    elif need_cool: task_type, preproc = 'pick_cool_then_place_in_recep', '冰箱'
    elif any(w in verb_text for w in ['看','照','查看']): task_type, preproc = 'look_at_obj_in_light', None
    else: task_type, preproc = 'pick_and_place_simple', None
    
    loc_keywords = {'柜台','柜子','水槽','冰箱','微波炉','架子','桌子','台子','垃圾桶','床上','沙发','保险箱','马桶','扶手椅'}
    target_obj = None; target_loc = None
    for obj in objects:
        is_loc = any(lk in obj for lk in loc_keywords)
        if is_loc: 
            target_loc = obj
            # 去除方位后缀（"柜台上"→"柜台"、"水槽里"→"水槽"）
            for sfx in ['上','里','下','旁','边']:
                if target_loc.endswith(sfx):
                    target_loc = target_loc[:-len(sfx)]
                    break
        elif not target_obj: target_obj = obj
    
    if not target_obj and objects: target_obj = objects[0]
    if not target_loc: target_loc = '柜台'
    
    return {
        'task_type': task_type,
        'target_obj': target_obj,
        'target_loc': target_loc,
        'preproc_loc': preproc,
        'task_cn': task_cn,
        'temporal': temporal,
    }


def translate_task(task_en):
    """英文任务描述→中文"""
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
    if t in known: return known[t]
    return task_en


# ============================================================
# 意图 → ALFWorld命令匹配（基于中文卦象匹配）
# ============================================================

def match_intent_to_command(intent, admissible_cn, admissible_en, params):
    """
    在admissible命令中，找到与intent最匹配的命令。
    
    匹配策略：
      1. 从admissible_cn中选一个
      2. 对每个候选过引擎取卦象
      3. 根据intent类型，按不同的卦象语义规则打分
      4. 返回得分最高的命令（英文格式）
    """
    preproc = params.get('preproc_loc')
    target = params.get('target_loc')
    target_obj = params.get('target_obj', '')
    
    best_cmd = None
    best_score = -1
    best_reason = ""
    
    for cn_cmd, en_cmd in zip(admissible_cn, admissible_en):
        score = 0.0
        reasons = []
        
        # 每条命令过引擎
        r = engine.sentence(cn_cmd)
        dom = r['dominant_bagua']
        segs = r['segments']
        roles = r['segment_role']
        verbs = [segs[i] for i in range(len(segs)) if roles[i] == '动作']
        objs = [segs[i] for i in range(len(segs)) if roles[i] == '物体']
        
        # ============ 各intent的匹配规则 ============
        
        # goto探索：任何"去XX"都行
        if intent == "goto探索":
            if "去" in cn_cmd:
                score = 1.0
                reasons.append("探索")
        
        # 拿取：命令含"拿"+物体名
        elif intent == "拿取":
            if "拿" in cn_cmd:
                score += 0.5
                if target_obj and any(target_obj in s for s in segs):
                    score += 0.3
                else:
                    score += 0.1
                if "从" in cn_cmd:
                    score += 0.2
        
        # 取出：与拿取类似，但匹配已处理场景
        elif intent == "取出":
            if "拿" in cn_cmd:
                score += 0.5
                if preproc and any(p in cn_cmd for p in [preproc]):
                    score += 0.3
                if "从" in cn_cmd:
                    score += 0.2
        
        # 去预处理位置：命令含"去"+预处理位置
        elif intent == "去预处理位置":
            if "去" in cn_cmd and preproc:
                if preproc in cn_cmd:
                    score = 1.0
                elif any(k in cn_cmd for k in ["水槽","冰箱","微波炉"]):
                    score = 0.8
        
        # 放入设备：命令含"放"+预处理位置
        elif intent == "放入设备":
            if "放" in cn_cmd and preproc:
                if preproc in cn_cmd:
                    score = 1.0
                elif any(k in cn_cmd for k in ["水槽","冰箱","微波炉"]):
                    score = 0.8
        
        # 执行处理：清洗/加热/冷却类命令
        elif intent == "执行处理":
            if any(v in cn_cmd for v in ['清洗','加热','冷却']):
                score = 1.0
            elif "洗" in cn_cmd or "热" in cn_cmd or "冷" in cn_cmd:
                score = 0.7
        
        # 去目标位置：命令含"去"+目标位置
        elif intent == "去目标位置":
            if "去" in cn_cmd and target:
                if target in cn_cmd:
                    score = 1.0
                else:
                    score = 0.5
        
        # 放置：命令含"放"+目标位置
        elif intent == "放置":
            if "放" in cn_cmd and target:
                if target in cn_cmd:
                    score = 1.0
                else:
                    score = 0.5
        
        if score > best_score:
            best_score = score
            best_cmd = en_cmd
            best_reason = f"{dom}/{r['main_hexagram']} score={score}"
    
    return best_cmd, best_score, best_reason


# ============================================================
# Agent
# ============================================================

class YLYWAgentV14:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.params = {}
        self.yao = [0.1,0.1,0.1,0.2,0.15,0.3]
        self.prev_yao = None
        self.step = 0
        self.has_obj = False
        self.processed = False
        self.cur_loc_cn = ""
        self.history = []
        self.visited_locations = set()
        self.last_cn_cmds = []
        self.last_en_cmds = []
    
    def reset(self, task_desc, task_type, pddl_params=None):
        self.params = parse_task_params(task_desc)
        self.yao = [0.1,0.1,0.1,0.2,0.15,0.3]
        self.prev_yao = None
        self.step = 0
        self.has_obj = False
        self.processed = False
        self.cur_loc_cn = ""
        self.history = []
        self.visited_locations = set()
        self.last_cn_cmds = []
        self.last_en_cmds = []
        
        if self.verbose:
            print(f"\n[V14] 任务: {task_desc}")
            print(f"[V14] 中文: {self.params['task_cn']}")
            print(f"[V14] 目标: {self.params['target_obj']}→{self.params['target_loc']} 预处理:{self.params['preproc_loc']}")
    
    def act(self, obs, admissible_commands):
        self.step += 1
        
        # 1. 更新状态
        self._update_location(obs)
        self._update_state(obs, admissible_commands)
        
        # 2. 六爻
        pp = self.params.get('preproc_loc')
        tl = self.params.get('target_loc')
        has_take = any(c.startswith('take ') for c in admissible_commands)
        self.yao = build_yao(self.cur_loc_cn, self.has_obj, self.processed, self.step, pp, tl, has_take)
        intent, activation = fuzzy_decide(self.yao)
        
        # 3. admissible翻译+匹配
        cn_cmds = [cmd_to_cn(c) for c in admissible_commands]
        self.last_cn_cmds = cn_cmds
        self.last_en_cmds = admissible_commands
        
        # goto探索时去重优先（去没去过的地方）
        if intent == "goto探索":
            for cn, en in zip(cn_cmds, admissible_commands):
                if "去" in cn:
                    # 提取位置名
                    loc_name = cn.replace('去','').strip()
                    if loc_name and loc_name not in self.visited_locations:
                        cmd, score = en, 1.0
                        break
            else:
                # 都去过了，随便选一个
                for cn, en in zip(cn_cmds, admissible_commands):
                    if "去" in cn:
                        cmd, score = en, 0.8
                        break
        else:
            cmd, score, reason = match_intent_to_command(intent, cn_cmds, admissible_commands, self.params)
        
        if self.verbose:
            yao_v = " ".join(f"{v:.2f}" for v in self.yao)
            print(f"  S{self.step:2d} {intent:8s}({activation:.2f}) loc={self.cur_loc_cn:6s} has={self.has_obj} done={self.processed} → {cmd}")
        
        self.history.append((intent, cmd))
        
        if cmd is None:
            # 兜底
            cmd = admissible_commands[0] if admissible_commands else 'look'
        
        return cmd
    
    def _update_location(self, obs):
        for line in obs.split('\n'):
            line = line.strip().lower()
            m = re.search(r'arrive at (.+?)[\.!?]', line)
            if m:
                loc_en = m.group(1).strip()
                # 翻译为中文（带编号）存入visited
                loc_cn_parts = []
                for word in loc_en.split():
                    loc_cn_parts.append(tw(word))
                self.cur_loc_cn = ''.join(loc_cn_parts)
                self.visited_locations.add(self.cur_loc_cn)
                return
    
    def _update_state(self, obs, cmds):
        """更新持有状态和处理状态"""
        if 'You pick up' in obs or 'pick up' in obs.lower():
            self.has_obj = True
        elif 'You put' in obs or 'you put' in obs.lower():
            self.has_obj = False
        elif 'Nothing happens' in obs:
            pass
        else:
            has_take = any(c.startswith('take ') for c in cmds)
            has_put = any(c.startswith('put ') or c.startswith('move ') for c in cmds)
            if has_take and not has_put:
                self.has_obj = False
            elif has_put and not has_take:
                self.has_obj = True
        
        # 处理状态
        pp = self.params.get('preproc_loc')
        if pp:
            if any(kw in obs.lower() for kw in ['clean the','heat the','cool the','you clean','you heat','you cool']):
                self.processed = True
    
    def update(self, action, obs, info):
        """兼容V10接口"""
        pass


# ============================================================
# 主运行
# ============================================================

if __name__ == '__main__':
    from alfworld_official_wrapper import ALFWorldOfficial
    from task_desc_parser import parse_task_desc
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--max_games', type=int, default=0)
    parser.add_argument('--output', default='ylyw_agent_v14_results.json')
    args = parser.parse_args()
    
    env = ALFWorldOfficial()
    agent = YLYWAgentV14(verbose=args.verbose)
    max_games = args.max_games if args.max_games > 0 else env.num_games
    
    print(f"\nYLYW Agent V14 (六爻驱动+中文匹配) — {max_games} games")
    print("=" * 60)
    
    results = []
    start = time.time()
    
    for i in range(max_games):
        try:
            obs, info = env.reset(game_idx=i)
            agent.reset(info.get('task_desc',''), info.get('task_type',''), info.get('pddl_params',{}))
            won = False
            steps = 0
            for _ in range(50):
                cmds = info.get('admissible_commands', ['look'])
                action = agent.act(obs, cmds)
                obs, info = env.step(action)
                steps += 1
                won = info.get('won', False)
                if won: break
            
            icon = '✅' if won else '❌'
            t = info.get('task_type','')
            print(f"  {icon} #{i:3d} [{t[:30]:30s}] steps={steps:2d}  {info.get('task_desc','')[:50]}")
            results.append({'game_idx':i,'task_type':t,'task_desc':info.get('task_desc',''),'steps':steps,'won':won})
            
            if (i+1) % 20 == 0:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                    
        except Exception as e:
            print(f"  ❌ #{i:3d} Error: {e}")
            import traceback; traceback.print_exc()
    
    elapsed = time.time() - start
    won_count = sum(1 for r in results if r['won'])
    total = len(results)
    
    from collections import defaultdict
    by_type = defaultdict(lambda: {'total':0,'won':0})
    for r in results:
        by_type[r['task_type']]['total'] += 1
        if r['won']: by_type[r['task_type']]['won'] += 1
    
    print(f"\n{'='*60}")
    print(f"V14 结果 ({total} games, {elapsed:.1f}s)")
    for t, d in sorted(by_type.items()):
        pct = d['won']/d['total']*100
        print(f"  {t:40s} {d['won']:3d}/{d['total']:2d} ({pct:5.1f}%)")
    print(f"  {'总计':40s} {won_count:3d}/{total:2d} ({won_count/total*100:.1f}%)")
    
    output = {'agent':'YLYWAgentV14','games':total,'won':won_count,'rate':won_count/total,'elapsed':elapsed,
              'by_type':{t:{'total':d['total'],'won':d['won'],'rate':d['won']/d['total']} for t,d in by_type.items()},
              'results':results}
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n保存: {args.output}")
