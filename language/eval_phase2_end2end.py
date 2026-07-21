#!/usr/bin/env python3
"""
Phase 2: 真实ALFWorld端到端测试 — Obs-only版

核心约束：只能使用obs（观测文本），不能使用admissible_commands。
智能体必须从obs理解环境状态并自主构造动作命令。

架构：
  1. ObsParser: 从obs文本提取位置、物体、环境状态
  2. TaskParser: 从info获取任务参数（这是允许的——来自环境元信息）
  3. YLYWState: 六爻状态构建
  4. FuzzyDecider: 模糊规则 → 意图
  5. ActionFactory: 意图 + obs状态 → 具体动作命令

输出: eval_phase2_results.json
"""

import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfworld_exp'))
from hanzi_engine import HanziEngine
from collections import defaultdict, Counter

from alfworld_official_wrapper import ALFWorldOfficial

engine = HanziEngine(verbose=False)

# ═══════════════════════════════════════════════════
# 预处理位置映射（仅从task_type推断）
# ═══════════════════════════════════════════════════

PREPROC_MAP = {
    'pick_clean_then_place_in_recep': 'sinkbasin',
    'pick_heat_then_place_in_recep': 'microwave',
    'pick_cool_then_place_in_recep': 'fridge',
}

# ═══════════════════════════════════════════════════
# 环境解析器（从obs提取信息）
# ═══════════════════════════════════════════════════

class ObsParser:
    """从观测文本解析状态"""
    
    @staticmethod
    def extract_location(obs_text: str, prev_loc: str = "起点") -> str:
        """从obs提取当前位置（raw，带编号）
        
        Args:
            obs_text: 当前观测文本
            prev_loc: 上一个已知位置（当obs中没有arrive at时保留）
        """
        ol = obs_text.strip().lower()
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                return after[:idx].strip() if idx > 0 else after
        # fallback：如果没有arrive at，说明位置未变，保留上一步位置
        return prev_loc
    
    @staticmethod
    def parse_observation(obs_text: str, prev_loc: str) -> dict:
        """
        从obs解析完整状态。
        返回：{
            'location': 当前位置norm,
            'visible_objects': 当前位可见物体列表,
            'visible_locations': 可去的所有位置列表,
            'doors': 容器及其开关状态,
            'inventory': 库存,
            'action_result': 上一步结果,
        }
        """
        ol = obs_text.strip().lower()
        result = {
            'location': ObsParser.extract_location(obs_text, prev_loc),
            'visible_objects': [],
            'visible_locations': [],
            'doors': {},
            'inventory': [],
            'action_result': '',
        }
        
        # 位置检测——从"you see"后的列表解析所有位置
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            # arrive at行
            if l.startswith('you arrive at'):
                after = l.replace('you arrive at', '').strip()
                idx = after.find('.')
                raw = after[:idx].strip() if idx > 0 else after
                result['location'] = raw
            # on the X, you see Y
            m = re.match(r'on the (.+), you see (.+)', l)
            if m:
                loc_name = m.group(1).strip()
                items = m.group(2).strip()
                # 解析看到的物体
                for item in re.finditer(r'(?:a |an )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', items):
                    obj = item.group(1).strip()
                    if obj not in ('a', 'an'):
                        result['visible_objects'].append(f"{obj} {item.group(2)}")
        
        # 从"you see"行提取所有位置（乘承比应语法）
        see_line = ''
        for line in obs_text.split('\n'):
            l = line.strip().lower()
            if 'looking quickly around you, you see' in l or 'you see' in l:
                see_line = l
                break
        
        if see_line:
            # 解析"you see X, Y, Z."
            parts = see_line.split('you see')[-1].strip().rstrip('.')
            # 清理开头
            if parts.startswith('a '): parts = parts[2:]
            # 按", "和"and "分割
            items = re.split(r', |, and | and ', parts)
            for item in items:
                item = item.strip().lstrip('a ').lstrip('an ')
                # 匹配"word number"格式
                m = re.match(r'([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', item)
                if m:
                    name = m.group(1).strip()
                    num = m.group(2)
                    full = f"{name} {num}"
                    # 区分位置和物体
                    if name in ('cabinet','countertop','drawer','shelf','desk','lamp',
                                'coffeemachine','fridge','microwave','sinkbasin','garbagecan',
                                'bed','sofa','safe','toilet','armchair','diningtable',
                                'stoveburner','toaster','floorlamp','desk lamp'):
                        result['visible_locations'].append(full)
                    else:
                        result['visible_objects'].append(full)
        
        # 库存（从inventory命令的响应中解析）
        if 'you are carrying' in ol:
            carrying_line = [l for l in obs_text.split('\n') if 'carrying' in l.lower()]
            if carrying_line:
                items = re.findall(r'([a-z]+)\s+(\d+)', carrying_line[0].lower())
                result['inventory'] = [f"{n} {i}" for n, i in items]
        
        # pick up检测（take后obs第一行就是You pick up...）
        # ALFWorld中，take后的obs不显示carrying，只显示pick up
        if ol.startswith('you pick up') or 'you pick up' in ol:
            m = re.search(r'you pick up (?:the |a )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)', ol)
            if m:
                obj_full = f"{m.group(1)} {m.group(2)}"
                if obj_full not in result['inventory']:
                    result['inventory'].append(obj_full)
        
        # 容器状态（用re.finditer搜索整段文本，不依赖\n分割）
        ol2 = obs_text.lower()
        for m in re.finditer(r'the ([a-z]+(?:\s+\d+)?) is (closed|open)', ol2):
            result['doors'][m.group(1).strip()] = m.group(2).strip()
        
        return result
    
    @staticmethod
    def norm(s: str) -> str:
        if not s: return ""
        return re.sub(r'\s+\d+$', '', s.strip().lower())
    
    @staticmethod
    def key(s: str) -> str:
        if not s: return ""
        return s.strip().lower()


# ═══════════════════════════════════════════════════
# 六爻 + 模糊规则
# ═══════════════════════════════════════════════════

def lsh(x, e=0.35, s=0.15):
    if x <= e-s: return 1.0
    if x >= e+s: return 0.0
    return 1.0-(x-(e-s))/(2*s)

def rsh(x, e=0.45, s=0.15):
    if x >= e+s: return 1.0
    if x <= e-s: return 0.0
    return (x-(e-s))/(2*s)

RULES = [
    ("拿取",     lambda y: lsh(y[0])*rsh(y[1],0.30)*lsh(y[3],0.50)),
    ("取出",     lambda y: lsh(y[0])*rsh(y[1],0.35)*rsh(y[3],0.45)),
    ("放入设备", lambda y: rsh(y[0],0.30)*rsh(y[1],0.45)*lsh(y[3],0.40)),
    ("执行处理", lambda y: lsh(y[0])*rsh(y[1],0.40)*lsh(y[3],0.40)*lsh(y[4],0.30)),
    ("放置",     lambda y: rsh(y[0],0.30)*rsh(y[3],0.45)*rsh(y[1],0.50)*rsh(y[4],0.40)),
    ("去预处理", lambda y: rsh(y[0],0.35)*lsh(y[3],0.40)*lsh(y[1],0.45)),
    ("去目标",   lambda y: rsh(y[0],0.35)*rsh(y[3],0.45)*lsh(y[1],0.50)),
    ("goto探索", lambda y: lsh(y[0])*lsh(y[1],0.50)),
]

def fuzzy(yao):
    bn, ba = "goto探索", 0.0
    for n, fn in RULES:
        a = fn(yao)
        if a > ba: bn, ba = n, a
    return bn, round(ba, 4)


def build_yao(loc_norm: str, has_inv: bool, processed: bool, step: int,
              preproc_en: str, target_norm: str, at_target: bool = False) -> list:
    """
    六爻状态编码（6维连续向量）
    
    爻义：
      初爻(y0): 持有态——0.10空手, 0.70有物未处理, 0.85有物已处理
      二爻(y1): 位置估值——0.10起点, 0.40探索位, 0.60预处理器, 0.85目标位
      三爻(y2): 进度——0.10→0.85随步数增长
      四爻(y3): 预处理态——0.10未处理, 0.15~0.25过渡, 0.60~0.85已处理
      五爻(y4): 目标就绪——0.15未就绪, 0.40到目标, 0.90有物+目标
      上爻(y5): 环境宽松——0.35探索, 0.75关键位置
    """
    y0 = 0.10 if not has_inv else (0.85 if processed else 0.70)
    
    lm = {"起点": 0.10}
    if preproc_en: lm[preproc_en] = 0.60
    if target_norm: lm[target_norm] = 0.85
    for k in ["cabinet","countertop","drawer","shelf","desk","bed","sofa","safe",
              "toilet","armchair","sinkbasin","garbagecan","microwave","fridge",
              "coffeemaker","diningtable","lamp","stoveburner","toaster"]:
        if k not in lm: lm[k] = 0.40
    y1 = lm.get(loc_norm, 0.25)
    if at_target: y1 = max(y1, 0.80)
    
    y2 = min(0.10 + step * 0.07, 0.85)
    
    if not preproc_en:
        y3 = 0.80 if has_inv else 0.10
        y4 = 0.90 if has_inv and at_target else (0.40 if at_target else 0.10)
    else:
        if not has_inv and not processed: y3 = 0.10
        elif has_inv and not processed: y3 = 0.25 if loc_norm == preproc_en else 0.15
        elif not has_inv and processed: y3 = 0.70 if loc_norm == preproc_en else 0.60
        elif has_inv and processed: y3 = 0.85 if loc_norm == preproc_en else 0.80
        else: y3 = 0.10
        
        y4 = 0.15
        if at_target and has_inv and processed: y4 = 0.90
        elif at_target: y4 = 0.40
    
    y5 = 0.75 if loc_norm in ([preproc_en, target_norm] if preproc_en else [target_norm]) else 0.35
    
    return [round(v, 3) for v in [y0, y1, y2, y3, y4, y5]]


# ═══════════════════════════════════════════════════
# 动作工厂（从意图+obs状态生成动作）
# ═══════════════════════════════════════════════════

def pick_action(intent: str, obs_state: dict, task_info: dict,
                visited_keys: set, last_action: str) -> str:
    """
    核心动作生成函数——仅依赖obs_state和任务元信息。
    规则：
      - 只能用obs中看到的信息构造动作
      - 只能推断动作是否成功（从下一次obs）
      - 不能假设admissible列表
    """
    loc_raw = obs_state['location']
    loc_norm = ObsParser.norm(loc_raw)
    inv = obs_state['inventory']
    vis_locs = obs_state['visible_locations']
    vis_objs = obs_state['visible_objects']
    doors = obs_state['doors']
    
    pddl = task_info.get('pddl_params', {})
    obj_en = (pddl.get('object_full', '') or pddl.get('object', '')).lower()
    target_en = (pddl.get('parent_full', '') or pddl.get('parent', '')).lower()
    target_norm = ObsParser.norm(target_en)
    pp = PREPROC_MAP.get(task_info.get('task_type', ''), '')
    
    # === goto探索：去一个没去过的位置 ===
    if intent == "goto探索":
        unvisited = [l for l in vis_locs if ObsParser.key(l) not in visited_keys
                     and ObsParser.norm(l) not in (ObsParser.norm(target_en) if target_en else '',
                                                  ObsParser.norm(pp) if pp else '')]
        if unvisited:
            return f"go to {unvisited[0]}"
        # vis_locs为空（已经在一个非起点位置），尝试构造go to target/preproc
        if target_en and ObsParser.key(f'{target_en} 1') not in visited_keys:
            return f"go to {target_en} 1"
        if pp and ObsParser.key(f'{pp} 1') not in visited_keys:
            return f"go to {pp} 1"
        # 到场景中常见的其他位置
        for loc_candidate in [f'cabinet {i}' for i in range(6, 0, -1)]:
            if ObsParser.key(loc_candidate) not in visited_keys:
                return f"go to {loc_candidate}"
        for loc_candidate in [f'countertop {i}' for i in range(1, 4)]:
            if ObsParser.key(loc_candidate) not in visited_keys:
                return f"go to {loc_candidate}"
        for loc_candidate in [f'drawer {i}' for i in range(1, 4)]:
            if ObsParser.key(loc_candidate) not in visited_keys:
                return f"go to {loc_candidate}"
        for loc_candidate in [f'shelf {i}' for i in range(1, 4)]:
            if ObsParser.key(loc_candidate) not in visited_keys:
                return f"go to {loc_candidate}"
        # 都试过了，去目标位
        if target_en:
            return f"go to {target_en} 1"
        if pp:
            return f"go to {pp} 1"
        return "look"
    
    # === 拿取 ===
    if intent == "拿取":
        # 检查当前位置是否有closed的容器需要open
        for loc_name, door_state in doors.items():
            if door_state == 'closed' and loc_name in loc_raw:
                return f"open {loc_name}"
        if not vis_objs:
            # 所有容器都打开了但还没看到物体，继续探索
            return pick_action("goto探索", obs_state, task_info, visited_keys, last_action)
        # 搜寻目标物体
        target_objs = [o for o in vis_objs if obj_en in o.lower()] if obj_en else vis_objs
        if target_objs:
            obj = target_objs[0]
            if loc_raw and loc_raw != "起点":
                return f"take {obj} from {loc_raw}"
            return f"take {obj}"
        # 看见物体但没找到目标物体，先随便拿一个
        if vis_objs:
            obj = vis_objs[0]
            if loc_raw and loc_raw != "起点":
                return f"take {obj} from {loc_raw}"
            return f"take {obj}"
        return "look"
    
    # === 取出（从预处理设备）===
    if intent == "取出":
        # 从preproc取出
        if pp:
            for o in vis_objs:
                if pp in o.lower() or obj_en in o.lower():
                    if loc_raw != "起点":
                        return f"take {o} from {loc_raw}"
                    return f"take {o}"
        # 没看到物体，可能在封闭容器里
        for loc_name, state in doors.items():
            if state == 'closed':
                return f"open {loc_name}"
        return "look"
    
    # === 去预处理位置 ===
    if intent == "去预处理":
        # 直接从记忆中的预处理位置构造go to命令（不依赖vis_locs）
        if pp:
            # pp可能是'sinkbasin'，构造'sinkbasin 1'
            return f"go to {pp} 1"
        if vis_locs:
            return f"go to {vis_locs[0]}"
        return "look"
    
    # === 放入设备 ===
    if intent == "放入设备":
        if inv:
            obj = inv[0]
            if pp:
                return f"put {obj} in/on {pp}"
            return f"put {obj} in/on {loc_raw}"
        # 空手尝试先open设备
        for loc_name, door_state in doors.items():
            if door_state == 'closed' and pp and pp in loc_name:
                return f"open {loc_name}"
        return "look"
    
    # === 执行处理 ===
    if intent == "执行处理":
        task_pp = task_info.get('task_type', '')
        if 'clean' in task_pp:
            return "clean"
        elif 'heat' in task_pp:
            return "heat"
        elif 'cool' in task_pp:
            return "cool"
        if pp == 'sinkbasin':
            return "clean"
        elif pp == 'microwave':
            return "heat"
        elif pp == 'fridge':
            return "cool"
        return "look"
    
    # === 去目标位置 ===
    if intent == "去目标":
        if target_en:
            target_key = target_en.replace('_', '').replace(' ', '')
            for l in vis_locs:
                if target_key in l.lower().replace(' ', '').replace('_', ''):
                    return f"go to {l}"
            # 不在vis_locs中，直接构造
            return f"go to {target_en} 1"
        if vis_locs:
            return f"go to {vis_locs[0]}"
        return "look"
    
    # === 放置 ===
    if intent == "放置":
        if inv:
            obj = inv[0]
            if target_en:
                return f"put {obj} in/on {target_en} 1"
            return f"put {obj} in/on {loc_raw}"
        for loc_name, door_state in doors.items():
            if door_state == 'closed' and target_en and target_en in loc_name:
                return f"open {loc_name}"
        return "look"
    
    return "look"


# ═══════════════════════════════════════════════════
# 单场景运行
# ═══════════════════════════════════════════════════

def run_task(env, game_idx: int, max_steps: int = 50) -> tuple:
    """运行单个ALFWorld任务（obs-only）"""
    obs, info = env.reset(game_idx)
    task_type = info.get("task_type", "")
    pddl = info.get("pddl_params", {})
    pp = PREPROC_MAP.get(task_type, "")
    target_en = (pddl.get("parent_full", "") or pddl.get("parent", "")).lower()
    target_norm = ObsParser.norm(target_en)
    obj_en = (pddl.get("object_full", "") or pddl.get("object", "")).lower()
    
    loc_raw = "起点"
    loc_norm = "起点"
    inventory = []  # 当前obs中解析到的库存
    last_known_inv = []  # 追踪的库存状态（跨步骤维持）
    processed = False
    actions = []
    intents = []
    visited_keys = set()
    visited_keys.add(ObsParser.key("起点"))
    
    for step in range(max_steps):
        # 解析obs
        obs_state = ObsParser.parse_observation(obs, loc_raw)
        loc_raw = obs_state["location"]
        loc_norm = ObsParser.norm(loc_raw)
        visited_keys.add(ObsParser.key(loc_raw))
        
        # 库存：obs中如果有carrying信息，用obs的；否则沿用last_known_inv
        inventory = obs_state["inventory"] if obs_state["inventory"] else last_known_inv
        
        # pick up检测（从obs中识别）——更新last_known
        ol = obs.lower()
        if ol.startswith("you pick up") or "you pick up" in ol:
            m = re.search(r"you pick up (?:the |a )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)", ol)
            if m and not any(inventory):
                obj_full = f"{m.group(1)} {m.group(2)}"
                inventory = [obj_full]
                last_known_inv = [obj_full]
        
        # put后清空
        if actions and inventory:
            la = actions[-1]
            if la.startswith("put ") and ("you put" in ol or "you place" in ol):
                inventory = []
                last_known_inv = []
                if pp and pp in la.lower(): processed = True
        
        # 更新处理状态
        if actions:
            la = actions[-1]
            if la.startswith("clean ") and "clean" in ol: processed = True; inventory = []
            elif la.startswith("heat ") and "heat" in ol: processed = True; inventory = []
            elif la.startswith("cool ") and "cool" in ol: processed = True; inventory = []
        
        # 更新last_known：当inventory有货时同步
        if inventory:
            last_known_inv = inventory[:]
        # take后且执行成功：确认库存
        if actions and not inventory:
            la = actions[-1]
            if la.startswith("take ") and "pick up" in ol:
                m = re.search(r"you pick up (?:the |a )?([a-z]+(?:\s+[a-z]+)?)\s+(\d+)", ol)
                if m:
                    obj_full = f"{m.group(1)} {m.group(2)}"
                    inventory = [obj_full]
                    last_known_inv = [obj_full]
        
        at_target = bool(target_norm and target_norm in loc_norm)
        
        yao = build_yao(loc_norm, bool(inventory), processed, step,
                        pp, target_norm, at_target)
        intent, score = fuzzy(yao)
        intents.append(intent)
        
        if not pp and intent in ("去预处理", "放入设备", "执行处理", "取出"):
            intent = "放置" if inventory else ("拿取" if not inventory else "goto探索")
        
        # 将修正后的inventory写回obs_state（pick_action从obs_state读取库存）
        obs_state["inventory"] = inventory
        
        action = pick_action(intent, obs_state, info, visited_keys,
                             actions[-1] if actions else "")
        
        obs, info = env.step(action)
        actions.append(action)
        
        if info.get("won") or (info.get("done") and info.get("score", 0) > 0):
            return actions, intents, True, step + 1
        if info.get("done"):
            return actions, intents, False, step + 1
    
    return actions, intents, False, max_steps
if __name__ == '__main__':
    print("=" * 70)
    print("  Phase 2: 真实ALFWorld端到端测试（Obs-only）")
    print("  递归YLYW + 六爻模糊决策 × valid_unseen")
    print("  约束：仅使用obs文本，不使用admissible_commands")
    print("=" * 70)
    print()
    
    env = ALFWorldOfficial(split='valid_unseen')
    n_games = env.num_games
    print(f"总场景数: {n_games}\n")
    
    pass_by_type = defaultdict(int)
    total_by_type = defaultdict(int)
    step_by_type = defaultdict(list)
    results = []
    
    for i in range(min(10, n_games)):
        actions, intents, success, steps = run_task(env, i)
        tt = env._traj_cache[i]['task_type']
        pass_by_type[tt] += 1 if success else 0
        total_by_type[tt] += 1
        step_by_type[tt].append(steps)
        
        icon = "✅" if success else "❌"
        asum = "→".join(actions[:6]) + ("..." if len(actions) > 6 else "")
        print(f"  {icon} #{i:3d} [{tt:35s}] ({steps:2d}步) {asum}")
        
        results.append({
            'idx': i, 'type': tt,
            'steps': steps, 'success': success,
            'actions': actions, 'intents': intents,
        })
    
    # 汇总
    print("\n" + "=" * 70)
    print("  汇总")
    print("=" * 70)
    total_pass = sum(pass_by_type.values())
    total_all = sum(total_by_type.values())
    
    print(f"{'任务类型':40s} {'通过/总数':12s} {'成功率':8s}")
    print("-" * 60)
    for tt in sorted(pass_by_type.keys()):
        p = pass_by_type[tt]
        n = total_by_type[tt]
        print(f"{tt:40s} {p:3d}/{n:3d}    {p / n * 100:6.1f}%")
    print("-" * 60)
    print(f"{'总计':40s} {total_pass:3d}/{total_all:3d}    {total_pass / total_all * 100:6.1f}%")
    
    # 保存
    output = {
        'total': total_all, 'passed': total_pass,
        'rate': total_pass / total_all if total_all else 0,
        'by_type': {tt: {'total': total_by_type[tt], 'passed': pass_by_type[tt],
                          'rate': pass_by_type[tt] / total_by_type[tt]}
                    for tt in sorted(pass_by_type.keys())},
        'results': results,
    }
    with open('eval_phase2_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n  结果已保存至 eval_phase2_results.json")
    
    env.close()
