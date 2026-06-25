#!/usr/bin/env python3
"""
ChineseBridge — ALFWorld ↔ YLYW 中英文翻译桥接层

功能：
  1. 将 ALFWorld 的英文 observation / task_desc / admissible_commands 翻译成中文
  2. 将 YLYW 选择的中文命令翻译回 ALFWorld 可执行的英文命令
  3. 提供中英文对照的上下文供 YLYW 的三层推理使用

用法：
  from chinese_bridge import ChineseBridge
  bridge = ChineseBridge(model="deepseek/deepseek-v4-flash")
  cn_obs, cn_info = bridge.translate(obs, info)
  cn_action = agent.select_action(cn_info['admissible_commands'], ...)
  en_action = bridge.to_english(cn_action)
  obs, info = env.step(en_action)

作者: 马老师课题组
版本: 0.1
"""

import json
import os
import re
from typing import Dict, List, Tuple, Optional


class ChineseBridge:
    """
    ALFWorld ↔ YLYW 翻译桥接层

    使用 LLM API 将英文命令和观察翻译为中文，
    同时维护 英文↔中文 命令映射表以减少重复翻译。

    配置:
      - model: 使用的 LLM 模型，默认 deepseek-v4-flash (便宜)
      - base_url: API 地址
    """

    # 常见 ALFWorld 命令的固定中英文映射（避免每次调用LLM）
    CMD_MAP_CN2EN = {
        # go to
        '去': 'go to',
        '前往': 'go to',
        '走到': 'go to',
        # take
        '拿': 'take',
        '拿起': 'take',
        '取': 'take',
        # put
        '放': 'put',
        '放置': 'put',
        '放入': 'put',
        # open / close
        '打开': 'open',
        '开启': 'open',
        '关闭': 'close',
        '关上': 'close',
        # clean
        '清洁': 'clean',
        '清洗': 'clean',
        '擦拭': 'clean',
        # heat
        '加热': 'heat',
        '热': 'heat',
        # cool
        '冷却': 'cool',
        '制冷': 'cool',
        # use / toggle
        '使用': 'use',
        '打开开关': 'use',
        '切换': 'use',
        # slice
        '切': 'slice',
        '切割': 'slice',
        '切片': 'slice',
        # look / inventory
        '看': 'look',
        '观察': 'look',
        '环顾四周': 'look',
        '查看': 'look',
        '检查': 'look',
        '查看背包': 'inventory',
        '背包': 'inventory',
        '物品栏': 'inventory',
        '帮助': 'help',
    }

    # 常见物体的中英文对照
    OBJ_MAP = {
        '碗': 'bowl',
        '杯子': 'mug',
        '餐叉': 'fork',
        '叉子': 'fork',
        '刀': 'knife',
        '刀子': 'knife',
        '盘子': 'plate',
        '锅': 'pot',
        '平底锅': 'pan',
        '勺子': 'spoon',
        '汤匙': 'spoon',
        '土豆': 'potato',
        '番茄': 'tomato',
        '苹果': 'apple',
        '香蕉': 'banana',
        '鸡蛋': 'egg',
        '面包': 'bread',
        '奶酪': 'cheese',
        '生菜': 'lettuce',
        '洋葱': 'onion',
        '胡椒': 'pepper',
        '萝卜': 'radish',
        '砧板': 'cuttingboard',
        '灶台': 'stoveburner',
        '微波炉': 'microwave',
        '冰箱': 'fridge',
        '洗碗机': 'dishwasher',
        '水槽': 'sinkbasin',
        '橱柜': 'cabinet',
        '抽屉': 'drawer',
        '桌子': 'table',
        '餐桌': 'diningtable',
        '茶几': 'coffeetable',
        '床头柜': 'nightstand',
        '书架': 'shelf',
        '架子': 'shelf',
        '沙发': 'sofa',
        '椅子': 'chair',
        '床': 'bed',
        '台灯': 'desklamp',
        '落地灯': 'floorlamp',
        '闹钟': 'alarmclock',
        '书': 'book',
        '报纸': 'newspaper',
        '笔记本电脑': 'laptop',
        '手机': 'cellphone',
        '遥控器': 'remotecontrol',
        '键': 'key',
        '信用卡': 'creditcard',
        '钢笔': 'pen',
        '铅笔': 'pencil',
        '蜡笔': 'crayon',
        '雕像': 'statue',
        '花瓶': 'vase',
        '毛巾': 'towel',
        '肥皂': 'soap',
        '布': 'cloth',
        '海绵': 'sponge',
        '浴室水槽': 'handsink',
        '桌子': 'desk',
        '柜子': 'cabinet',
        '水龙头': 'faucet',
        '马桶': 'toilet',
        '浴缸': 'bathtub',
        '淋浴': 'shower',
        # === 补齐缺失物体 ===
        '棒球': 'baseball',
        '棒球棒': 'baseballbat',
        '篮球': 'basketball',
        '球棒': 'bat',
        '百叶窗': 'blinds',
        '瓶子': 'bottle',
        '盒子': 'box',
        '黄油': 'butter',
        '蜡烛': 'candle',
        '光盘': 'cd',
        '杯子': 'cup',
        '杯子': 'glass',
        '盘子': 'dish',
        '洗碗海绵': 'dishsponge',
        '钥匙链': 'keychain',
        '汤勺': 'ladle',
        '杂志': 'magazine',
        '镜子': 'mirror',
        '枕头': 'pillow',
        '马桶搋子': 'plunger',
        '盐': 'salt',
        '刷子': 'scrubbrush',
        '肥皂瓶': 'soapbottle',
        '铲子': 'spatula',
        '喷壶': 'spraybottle',
        '纸巾盒': 'tissuebox',
        '手表': 'watch',
        '打蛋器': 'whisk',
        '酒瓶': 'winebottle',
        '鸡': 'egg',    # egg在任务中可能被写为"a egg"
        '土豆': 'potato',
        '番茄': 'tomato',
        '生菜': 'lettuce',
        '面包': 'bread',
        '洋葱': 'onion',
        '胡椒': 'pepper',
        '萝卜': 'radish',
        '香蕉': 'banana',
        '奶酪': 'cheese',
        # === 补齐缺失位置 ===
        '扶手椅': 'armchair',
        '咖啡机': 'coffeemachine',
        '长沙发': 'couch',
        '柜台': 'counter',
        '台面': 'countertop',
        '梳妆台': 'dresser',
        '垃圾桶': 'garbage',
        '垃圾桶': 'garbagecan',
        '洗衣篮': 'laundryhamper',
        '储物凳': 'ottoman',
        '烤箱': 'oven',
        '冰箱': 'refrigerator',
        '保险箱': 'safe',
        '床头柜': 'sidetable',
        '灶台': 'stove',
        '桌子': 'table',
        '烤面包机': 'toaster',
        '电视柜': 'tvstand',
        '咖啡机': 'coffeemachine',
        '椅子': 'chair',
        '书架': 'bookshelf',
        '碗柜': 'cabinet',
        '水槽': 'sink',
        '厨房': 'kitchen',
        '卧室': 'bedroom',
        '窗户': 'window',
        # === 补齐缺失工具 ===
        '灯': 'lamp',
        '落地灯': 'floorlamp',
        '台灯': 'desklamp',
        '灯开关': 'lightswitch',
        '电视机': 'television',
    }
    # 反过来：英文→中文
    OBJ_MAP_EN2CN = {v: k for k, v in OBJ_MAP.items()}
    # 手动补全被覆盖的映射
    OBJ_MAP_EN2CN.update({
        'clock': '时钟',
        'mug': '杯子',
        'cup': '杯子',
        'plate': '盘子',
        'knife': '刀',
        'fridge': '冰箱',
        'desk': '桌子',
        'garbage': '垃圾桶',
        'sinkbasin': '水槽',
        'stoveburner': '灶台',
        'light': '灯',
        'egg': '鸡蛋',
        'spoon': '勺子',
        'fork': '叉子',
        'cabinet': '橱柜',
        'tvstand': '电视柜',
        'pencil': '铅笔',
        'pen': '钢笔',
    })

    def __init__(self, model: str = "deepseek/deepseek-v4-flash",
                 base_url: str = "https://api.deepseek.com/v1",
                 api_key: Optional[str] = None):
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

        # 缓存：session级别的翻译映射
        self._cmd_cache: Dict[str, str] = {}        # en → cn
        self._cmd_cache_rev: Dict[str, str] = {}    # cn → en
        self._obs_cache: Dict[str, str] = {}        # en → cn (截断的obs)

        # 统计
        self.translation_count = 0
        self.cache_hit_count = 0

    # ── 对外接口 ──────────────────────────────────────

    def translate_info(self, obs: str, info: dict) -> Tuple[str, dict]:
        """
        翻译一轮交互结果。

        输入: env.step() 返回的 (obs, info)
        输出: (cn_obs, cn_info)
          cn_info 中新增字段:
            - cn_task_desc: 中文任务描述
            - cn_admissible_commands: 中文可选命令列表
            - en_admissible_commands: 原始英文命令（供to_english使用）
            - _raw_info: 原始英文info
        """
        cn_info = dict(info)  # 浅拷贝
        cn_info['_raw_info'] = info

        # 翻译 task_desc
        task_desc = info.get('task_desc', '')
        if task_desc:
            cn_info['cn_task_desc'] = self._translate_task_desc(task_desc)
        else:
            cn_info['cn_task_desc'] = ''

        # 翻译 admissible_commands
        cmds = info.get('admissible_commands', [])
        cn_cmds, en_cmds = self._translate_commands(cmds)
        cn_info['cn_admissible_commands'] = cn_cmds
        cn_info['en_admissible_commands'] = en_cmds

        # 翻译 observation
        cn_info['cn_observation'] = self._translate_obs(obs) if obs else obs

        return obs, cn_info

    def to_english(self, cn_action: str) -> str:
        """
        将YLYW选出的中文命令翻译回英文。
        """
        cn_action = cn_action.strip().lower()

        # 1. 查缓存
        if cn_action in self._cmd_cache_rev:
            return self._cmd_cache_rev[cn_action]

        # 2. 命令动词映射
        en_verb = None
        cn_verb = None
        for cn_kw, en_v in sorted(self.CMD_MAP_CN2EN.items(), key=lambda x: -len(x[0])):
            if cn_action.startswith(cn_kw):
                cn_verb = cn_kw
                en_verb = en_v
                break

        if en_verb is None:
            # 不认识的中文命令，直接返回原字符串（让仿真器处理）
            return cn_action

        # 3. 提取中文物体/位置名，翻译成英文
        cn_rest = cn_action[len(cn_verb):].strip()
        en_rest = self._cn_entities_to_en(cn_rest)
        
        # 4. 组装英文命令
        if en_verb == 'go to':
            en_action = f"go to {en_rest} 1"
        elif en_verb == 'take':
            # "take obj 1 from loc 1" — 解析中文格式
            en_action = self._build_en_take(en_verb, en_rest, cn_rest)
        elif en_verb == 'put':
            en_action = self._build_en_put(en_verb, en_rest, cn_rest)
        elif en_verb in ('clean', 'heat', 'cool', 'slice'):
            # "clean obj 1 with tool 1"
            en_action = self._build_en_action_with_tool(en_verb, en_rest, cn_rest)
        elif en_verb in ('open', 'close', 'use'):
            en_action = f"{en_verb} {en_rest} 1"
        else:
            en_action = f"{en_verb} {en_rest}"

        # 缓存
        self._cmd_cache_rev[cn_action] = en_action
        return en_action

    def from_english(self, en_cmd: str) -> str:
        """将英文命令转为中文显示（供YLYW上下文使用）"""
        en_cmd = en_cmd.strip().lower()
        if en_cmd in self._cmd_cache:
            return self._cmd_cache[en_cmd]

        cn = self._translate_single_command(en_cmd)
        self._cmd_cache[en_cmd] = cn
        return cn

    # ── 内部翻译逻辑 ──────────────────────────────────

    def _translate_task_desc(self, text: str) -> str:
        """翻译任务描述（轻量级，基于规则+LLM fallback）"""
        # 先尝试基于规则
        cn = self._rule_translate_task(text)
        if cn and len(cn) > 5:
            return cn
        # fallback: LLM翻译
        return self._llm_translate(f"将以下ALFWorld游戏任务描述翻译成中文，保持原意：\n{text}")

    def _translate_commands(self, cmds: List[str]) -> Tuple[List[str], List[str]]:
        """批量翻译命令列表"""
        cn_cmds = []
        en_cmds = list(cmds)
        for c in cmds:
            cn = self._translate_single_command(c)
            cn_cmds.append(cn)
        return cn_cmds, en_cmds

    def _translate_single_command(self, cmd: str) -> str:
        """翻译单个英文命令为中文"""
        cmd_lower = cmd.strip().lower()
        
        # 查缓存
        if cmd_lower in self._cmd_cache:
            self.cache_hit_count += 1
            return self._cmd_cache[cmd_lower]

        self.translation_count += 1

        # 解析命令
        parts = cmd_lower.split()
        if not parts:
            return cmd

        verb = parts[0]
        args = [p for p in parts[1:] if not p.isdigit()]  # 去掉数字参数

        cn = cmd  # fallback
        if verb == 'go' and 'to' in parts:
            target = ' '.join(parts[2:]).replace(' 1', '').strip()
            cn_target = self._en_entity_to_cn(target)
            cn = f"去 {cn_target}"
        elif verb == 'take':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            if 'from' in args:
                from_idx = args.index('from')
                loc = ' '.join(args[from_idx+1:])
                cn_loc = self._en_entity_to_cn(loc)
                cn = f"拿 {cn_obj} 从 {cn_loc}"
            else:
                cn = f"拿 {cn_obj}"
        elif verb == 'put':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            if 'in/on' in args or 'in' in args or 'on' in args:
                prep = 'in/on' if 'in/on' in args else ('in' if 'in' in args else 'on')
                prep_idx = args.index(prep)
                loc = ' '.join(args[prep_idx+1:])
                cn_loc = self._en_entity_to_cn(loc)
                cn = f"放 {cn_obj} 到 {cn_loc}"
            else:
                cn = f"放 {cn_obj}"
        elif verb == 'open':
            target = ' '.join(args)
            cn_target = self._en_entity_to_cn(target)
            cn = f"打开 {cn_target}"
        elif verb == 'close':
            target = ' '.join(args)
            cn_target = self._en_entity_to_cn(target)
            cn = f"关闭 {cn_target}"
        elif verb == 'clean':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            if 'with' in args:
                with_idx = args.index('with')
                tool = ' '.join(args[with_idx+1:])
                cn_tool = self._en_entity_to_cn(tool)
                cn = f"清洗 {cn_obj} 用 {cn_tool}"
            else:
                cn = f"清洗 {cn_obj}"
        elif verb == 'heat':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            if 'with' in args:
                with_idx = args.index('with')
                tool = ' '.join(args[with_idx+1:])
                cn_tool = self._en_entity_to_cn(tool)
                cn = f"加热 {cn_obj} 用 {cn_tool}"
            else:
                cn = f"加热 {cn_obj}"
        elif verb == 'cool':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            cn = f"冷却 {cn_obj}"
        elif verb == 'slice':
            obj = args[0] if args else ''
            cn_obj = self._en_entity_to_cn(obj)
            cn = f"切片 {cn_obj}"
        elif verb == 'use':
            target = ' '.join(args)
            cn_target = self._en_entity_to_cn(target)
            cn = f"使用 {cn_target}"
        elif verb == 'look':
            cn = "观察"
        elif verb == 'inventory':
            cn = "查看背包"
        elif verb == 'help':
            cn = "帮助"
        else:
            cn = cmd  # 保持原样

        self._cmd_cache[cmd_lower] = cn
        self._cmd_cache_rev[cn] = cmd_lower
        return cn

    def _en_entity_to_cn(self, entity: str) -> str:
        """单个英文实体名 → 中文"""
        entity = entity.strip().lower()
        # 去掉末尾数字
        entity_clean = re.sub(r'\s+\d+$', '', entity).strip()
        # 查表
        if entity_clean in self.OBJ_MAP_EN2CN:
            return self.OBJ_MAP_EN2CN[entity_clean]
        # 按个单词查
        words = entity_clean.split()
        cn_words = []
        for w in words:
            if w in self.OBJ_MAP_EN2CN:
                cn_words.append(self.OBJ_MAP_EN2CN[w])
            else:
                cn_words.append(w)
        return ''.join(cn_words)

    def _cn_entities_to_en(self, cn_text: str) -> str:
        """中文实体名（可能多个）→ 英文"""
        cn_text = cn_text.strip()
        for cn_kw, en_v in sorted(self.OBJ_MAP.items(), key=lambda x: -len(x[0])):
            if cn_kw in cn_text:
                cn_text = cn_text.replace(cn_kw, en_v)
                break  # 只替换第一个匹配
        return cn_text

    def _translate_obs(self, obs: str) -> str:
        """翻译observation"""
        # 简单规则翻译
        cn = obs
        cn = cn.replace("You are in the middle of a room.",
                        "你在一间房间的中央。")
        cn = cn.replace("Looking quickly around you, you see",
                        "快速环顾四周，你看到了")
        cn = cn.replace("Your task is to:", "你的任务是：")
        cn = cn.replace("You arrive at", "你到达了")
        cn = cn.replace("On the", "在")
        cn = cn.replace("you see some objects.", "你看到了一些物品。")
        cn = cn.replace("That didn't work. Try something else.",
                        "没有成功。试试别的。")
        cn = cn.replace("You won!", "你赢了！")
        cn = cn.replace("Task already completed.", "任务已完成。")
        cn = cn.replace("You are in the", "你在")
        cn = cn.replace("of the room.", "的房间。")
        cn = cn.replace("Looking quickly around", "快速环顾")
        cn = cn.replace(", around you", "，你")
        return cn

    def _build_en_take(self, verb: str, en_rest: str, cn_rest: str) -> str:
        """组装take命令: take obj 1 from loc 1"""
        # 尝试解析"obj 从 loc"
        if '从' in cn_rest:
            parts = cn_rest.split('从', 1)
            obj = self._cn_entities_to_en(parts[0].strip())
            loc = self._cn_entities_to_en(parts[1].strip())
            return f"take {obj} 1 from {loc} 1"
        return f"take {en_rest} 1 from ? 1"

    def _build_en_put(self, verb: str, en_rest: str, cn_rest: str) -> str:
        """组装put命令: put obj 1 in/on loc 1"""
        if '到' in cn_rest:
            parts = cn_rest.split('到', 1)
            obj = self._cn_entities_to_en(parts[0].strip())
            loc = self._cn_entities_to_en(parts[1].strip())
            return f"put {obj} 1 in/on {loc} 1"
        return f"put {en_rest} 1 in/on ? 1"

    def _build_en_action_with_tool(self, verb: str, en_rest: str, cn_rest: str) -> str:
        """组装带工具的action: verb obj 1 with tool 1"""
        if '用' in cn_rest:
            parts = cn_rest.split('用', 1)
            obj = self._cn_entities_to_en(parts[0].strip())
            tool = self._cn_entities_to_en(parts[1].strip())
            return f"{verb} {obj} 1 with {tool} 1"
        return f"{verb} {en_rest} 1 with ? 1"

    def _rule_translate_task(self, text: str) -> str:
        """规则翻译任务描述"""
        text_lower = text.lower()
        
        # 常见的任务描述模式
        patterns = [
            (r'examine the (\w+) with the (\w+)',
             lambda m: f"用{m.group(2)}检查{m.group(1)}"),
            (r'hold the (\w+) and turn on the (\w+)',
             lambda m: f"拿着{m.group(1)}并打开{m.group(2)}"),
            (r'put a (\w+) in the (\w+)',
             lambda m: f"把一个{m.group(1)}放在{m.group(2)}里"),
            (r'put a (.+?) in (.+)',
             lambda m: f"把{m.group(1)}放在{m.group(2)}里"),
            (r'put two (\w+) in the (\w+)',
             lambda m: f"把两个{m.group(1)}放在{m.group(2)}里"),
            (r'put a (\w+) in a (\w+)',
             lambda m: f"把一个{m.group(1)}放在{m.group(2)}里"),
            (r'clean a (\w+) with a (\w+)',
             lambda m: f"用{m.group(2)}清洗{m.group(1)}"),
            (r'heat a (\w+) with a (\w+)',
             lambda m: f"用{m.group(2)}加热{m.group(1)}"),
            (r'cool a (\w+) with a (\w+)',
             lambda m: f"用{m.group(2)}冷却{m.group(1)}"),
            (r'slice a (\w+) with a (\w+)',
             lambda m: f"用{m.group(2)}切{m.group(1)}"),
            (r'put a (\w+) in the (\w+)',
             lambda m: f"把一个{m.group(1)}放进{m.group(2)}"),
            (r'put a clean (.+?) in (.+)',
             lambda m: f"把清洁过的{m.group(1)}放在{m.group(2)}里"),
            (r'put a hot (.+?) in (.+)',
             lambda m: f"把加热过的{m.group(1)}放在{m.group(2)}里"),
            (r'put a cool (.+?) in (.+)',
             lambda m: f"把冷却过的{m.group(1)}放在{m.group(2)}里"),
            (r'find a (\w+) and put it in the (\w+)',
             lambda m: f"找到一个{m.group(1)}放进{m.group(2)}"),
            (r'take a (\w+) from the (\w+) and put it in (\w+)',
             lambda m: f"从{m.group(2)}拿一个{m.group(1)}放进{m.group(3)}"),
        ]
        
        for pattern, repl in patterns:
            m = re.search(pattern, text_lower)
            if m:
                result = repl(m)
                # 翻译物体名
                for en_obj, cn_obj in self.OBJ_MAP_EN2CN.items():
                    if en_obj in result:
                        result = result.replace(en_obj, cn_obj)
                # 额外的常见单词翻译（先处理组合词）
                extra_words = [
                    ('microwave', '微波炉'), ('sinkbasin', '水槽'), ('stoveburner', '灶台'),
                    ('coffeetable', '茶几'), ('diningtable', '餐桌'), ('coffeemachine', '咖啡机'),
                    ('floorlamp', '落地灯'), ('desklamp', '台灯'), ('alarmclock', '闹钟'),
                    ('cabinet', '柜子'), ('drawer', '抽屉'), ('countertop', '柜台'),
                    ('clock', '时钟'), ('lamp', '灯'), ('light', '灯'),
                    ('table', '桌子'), ('shelf', '架子'), ('fridge', '冰箱'),
                    ('sink', '水槽'), ('stove', '灶台'), ('book', '书'),
                    ('apple', '苹果'), ('egg', '鸡蛋'), ('bread', '面包'),
                    ('butter', '黄油'), ('potato', '土豆'), ('tomato', '番茄'),
                ]
                for en_w, cn_w in extra_words:
                    result = result.replace(en_w, cn_w)
                return result

        return ""  # 无法规则翻译

    def _llm_translate(self, prompt: str) -> str:
        """LLM翻译（备用方案，目前返回空表示未实现）"""
        # 后续可以实现真正的LLM调用
        # 目前优先使用规则翻译
        return ""

    # ── 统计 ──────────────────────────────────────────

    def stats(self) -> dict:
        return {
            'translation_count': self.translation_count,
            'cache_hit_count': self.cache_hit_count,
            'cmd_cache_size': len(self._cmd_cache),
            'cmd_cache_rev_size': len(self._cmd_cache_rev),
        }

    def __repr__(self):
        s = self.stats()
        return (f"ChineseBridge(translations={s['translation_count']}, "
                f"cache_hits={s['cache_hit_count']}, "
                f"cache={s['cmd_cache_size']}en↔{s['cmd_cache_rev_size']}cn)")


# ── 单独测试 ──────────────────────────────────────────

if __name__ == '__main__':
    bridge = ChineseBridge()

    # 测试命令翻译
    test_cmds = [
        "go to counter 1",
        "take mug 1 from counter 1",
        "put mug 1 in/on fridge 1",
        "open cabinet 1",
        "clean potato 1 with sinkbasin 1",
        "heat potato 1 with microwave 1",
        "cool apple 1 with fridge 1",
        "slice tomato 1 with knife 1",
        "use desklamp 1",
        "look",
        "inventory",
    ]

    print("=== 命令翻译测试 ===")
    for cmd in test_cmds:
        cn = bridge.from_english(cmd)
        en_back = bridge.to_english(cn)
        status = "✓" if cmd == en_back else "△"
        print(f"  EN: {cmd}")
        print(f"  CN: {cn}")
        print(f"  →  {status} {en_back}")
        print()

    # 测试任务描述翻译
    tasks = [
        "examine the book with the desklamp",
        "put a mug in the coffee table",
        "put two apples in the fridge",
        "clean a potato with the sinkbasin",
        "heat a egg in the microwave",
    ]
    print("=== 任务描述翻译测试 ===")
    for t in tasks:
        cn = bridge._translate_task_desc(t)
        print(f"  EN: {t}")
        print(f"  CN: {cn}")
        print()
