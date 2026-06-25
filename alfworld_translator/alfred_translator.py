#!/usr/bin/env python3
"""
ALFWorld 即时翻译层 (Zero-Intrusion Translation Layer)
=======================================================
在 YLYW Agent（中文）和 ALFWorld 仿真器（英文）之间实现双向文本翻译。
不改动 ALFWorld 任何源码，只在外层包装。

设计原则：
- 观察输出（英文→中文）：Agent 看到的是中文世界
- 动作输入（中文→英文）：Agent 用中文发出命令，翻译层转成英文发给仿真器
- 如果不确定怎么翻译某条命令，退回英文原文（不丢信息）
"""

import re
from typing import Dict, List, Tuple, Optional


# ============================================================================
# 1. 物体词典（英文 → 中文）
# ============================================================================

OBJECT_DICT: Dict[str, str] = {
    # 家具/容器
    'cabinet': '柜子', 'drawer': '抽屉', 'shelf': '架子', 'desk': '书桌',
    'dresser': '梳妆台', 'safe': '保险箱', 'bed': '床', 'cart': '推车',
    'sofa': '沙发', 'armchair': '扶手椅', 'ottoman': '脚凳', 'chair': '椅子',
    'footstool': '脚凳', 'tvstand': '电视柜', 'diningtable': '餐桌',
    'coffeetable': '咖啡桌', 'sidetable': '边桌', 'countertop': '台面',
    'sink': '水槽', 'sinkbasin': '水槽盆', 'bathtub': '浴缸', 'bathtubbasin': '浴缸盆',
    'toilet': '马桶', 'garbagecan': '垃圾桶', 'fridge': '冰箱',
    'microwave': '微波炉', 'coffeemachine': '咖啡机', 'toaster': '烤面包机',
    'stoveburner': '炉灶', 'stoveknob': '炉灶旋钮',
    'towelholder': '毛巾架', 'handtowelholder': '擦手巾架',
    'toiletpaperhanger': '厕纸架', 'paintinghanger': '画架',
    # 物体
    'alarmclock': '闹钟', 'apple': '苹果', 'baseballbat': '棒球棍',
    'basketball': '篮球', 'book': '书', 'boots': '靴子', 'bowl': '碗',
    'box': '盒子', 'bread': '面包', 'butterknife': '黄油刀',
    'candle': '蜡烛', 'cd': 'CD', 'cellphone': '手机',
    'cloth': '抹布', 'creditcard': '信用卡', 'cup': '杯子',
    'curtains': '窗帘', 'blinds': '百叶窗', 'desklamp': '台灯',
    'dishsponge': '洗碗海绵', 'egg': '鸡蛋', 'floorlamp': '落地灯',
    'fork': '叉子', 'glassbottle': '玻璃瓶', 'handtowel': '擦手巾',
    'houseplant': '盆栽', 'kettle': '水壶', 'keychain': '钥匙链',
    'knife': '刀', 'ladle': '长柄勺', 'laptop': '笔记本电脑',
    'laundryhamper': '洗衣篮', 'laundryhamperlid': '洗衣篮盖',
    'lettuce': '生菜', 'lightswitch': '电灯开关',
    'mirror': '镜子', 'mug': '马克杯', 'newspaper': '报纸',
    'painting': '画', 'pan': '平底锅', 'papertowel': '纸巾',
    'papertowelroll': '纸巾卷', 'pen': '笔', 'pencil': '铅笔',
    'peppershaker': '胡椒瓶', 'pillow': '枕头', 'plate': '盘子',
    'plunger': '搋子', 'poster': '海报', 'pot': '锅',
    'potato': '土豆', 'remotecontrol': '遥控器',
    'saltshaker': '盐瓶', 'scrubbrush': '刷子',
    'showerdoor': '淋浴门', 'showerglass': '淋浴玻璃',
    'soapbar': '肥皂', 'soapbottle': '沐浴露', 'spatula': '锅铲',
    'spoon': '勺子', 'spraybottle': '喷壶', 'statue': '雕像',
    'teddybear': '泰迪熊', 'television': '电视', 'tennisracket': '网球拍',
    'tissuebox': '纸巾盒', 'toiletpaper': '厕纸', 'toiletpaperroll': '厕纸卷',
    'tomato': '番茄', 'towel': '毛巾', 'vase': '花瓶',
    'watch': '手表', 'wateringcan': '洒水壶', 'window': '窗户',
    'winebottle': '酒瓶',
    # ALFRED 物体（首字母大写也支持，运行时 lower 处理）
    # 状态词（用于 examine 反馈）
    'clean': '干净的', 'hot': '热的', 'cold': '冷的', 'cool': '凉的', 'sliced': '切好的',
}

# 反向词典（中文 → 英文），自动生成
ZH_TO_EN_OBJECT: Dict[str, str] = {v: k for k, v in OBJECT_DICT.items()}


def translate_object(en_name: str) -> str:
    """将英文物体名翻译为中文"""
    return OBJECT_DICT.get(en_name.lower(), en_name)


def untranslate_object(zh_name: str) -> str:
    """将中文物体名翻回英文"""
    return ZH_TO_EN_OBJECT.get(zh_name, zh_name)


# ============================================================================
# 2. 场景描述模板翻译
# ============================================================================

# 场景描述的模板规则（按优先级排序）
SCENE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # 到达某个家具
    (re.compile(r"You arrive at loc \d+\.\s*"), "你到达了目的地。"),
    # 起始描述
    (re.compile(r"You are in the middle of a room\.\s*Looking quickly around you,?\s*you see (.+)\."),
     "你站在房间中央。环顾四周，你看到了：\\1。"),
    # 面对某个家具
    (re.compile(r"You are facing the (.+)\."),
     "你面前是 \\1。"),
    # 旁边的东西
    (re.compile(r"Next to it, you see (.+)\."),
     "旁边你看到了：\\1。"),
    # 在某个容器上看到东西
    (re.compile(r"On the (.+), you see (.+)\."),
     "在 \\1 上面，你看到了 \\2。"),
    # 容器打开，里面有什么
    (re.compile(r"The (.+) is open\. In it, you see (.+)\."),
     "\\1 是开着的。里面有你看到了 \\2。"),
    # 容器关闭
    (re.compile(r"The (.+) is closed\."),
     "\\1 是关着的。"),
    # 你拿起东西
    (re.compile(r"You pick up the (.+) from the (.+)\."),
     "你从 \\2 拿起了 \\1。"),
    # 你放下/移动东西
    (re.compile(r"You move the (.+) to the (.+)\."),
     "你把 \\1 放到了 \\2。"),
    # 你打开容器
    (re.compile(r"You open the (.+)\."),
     "你打开了 \\1。"),
    # 你关上容器
    (re.compile(r"You close the (.+)\."),
     "你关上了 \\1。"),
    # 你清洗物体
    (re.compile(r"You clean the (.+) using the (.+)\."),
     "你用 \\2 清洗了 \\1。"),
    # 你加热物体
    (re.compile(r"You heat the (.+) using the (.+)\."),
     "你用 \\2 加热了 \\1。"),
    # 你冷却物体
    (re.compile(r"You cool the (.+) using the (.+)\."),
     "你用 \\2 冷却了 \\1。"),
    # 你打开/关闭电器
    (re.compile(r"You turn on the (.+)\."),
     "你打开了 \\1。"),
    (re.compile(r"You turn off the (.+)\."),
     "你关上了 \\1。"),
    # 物品检查描述
    (re.compile(r"This is a (.+)\."),
     "这是一个 \\1。"),
    (re.compile(r"There's nothing special about (.+)\."),
     "\\1 看起来没什么特别的。"),
    # 任务描述
    (re.compile(r"Your task is to: (.+)$"),
     "你的任务是：\\1"),
    # 你在背包里
    (re.compile(r"You are carrying: (.+)\."),
     "你正拿着：\\1。"),
    (re.compile(r"You are not carrying anything\."),
     "你手上什么都没有。"),
    # 获胜
    (re.compile(r"You won!"), "🎉 任务完成！"),
    # 欢迎信息
    (re.compile(r"-= Welcome to TextWorld, ALFRED! =-"),
     "-= 欢迎来到 TextWorld, ALFRED! =-"),
]


def translate_observation(obs: str) -> str:
    """
    将英文观察翻译为中文。
    对每一行分别匹配模板，未匹配的行保留原样但替换物体名。
    """
    if not obs:
        return obs

    translated_lines = []
    for line in obs.strip().split('\n'):
        line = line.strip()
        if not line:
            translated_lines.append('')
            continue

        matched = False
        for pattern, template in SCENE_PATTERNS:
            m = pattern.search(line)
            if m:
                # 用匹配组填充模板
                result = template
                for i, group in enumerate(m.groups()):
                    # 对每个捕获组进行物体名翻译
                    translated_group = _translate_phrase(group)
                    result = result.replace(f'\\{i+1}', translated_group)
                translated_lines.append(result)
                matched = True
                break

        if not matched:
            # 没有匹配模板，逐词翻译物体名
            translated_lines.append(_translate_phrase(line))

    return '\n'.join(translated_lines)


def _translate_phrase(phrase: str) -> str:
    """对短语中的物体名进行翻译，保留数字 ID 和其他词"""
    # 先处理 "a/an object_name number" 的模式
    # 例如 "a alarmclock 2" → "闹钟 2"
    result = re.sub(
        r'\b(a|an)\s+(\w+)(\s+\d+)?',
        lambda m: translate_object(m.group(2)) + (m.group(3) or ''),
        phrase,
        flags=re.IGNORECASE
    )
    # 处理列表中的物体名（没有 a/an 的情况）
    # 例如 "alarmclock 2, book 1" → "闹钟 2, 书 1"
    result = re.sub(
        r'\b([a-zA-Z]\w+)(\s+\d+)?(,|\s+and\s+|$)',
        lambda m: (translate_object(m.group(1)) if m.group(1).lower() in OBJECT_DICT
                   else m.group(1)) + (m.group(2) or '') + (m.group(3) if m.group(3) else ''),
        result
    )

    # 替换常见介词
    result = result.replace(' in/on the ', ' 在 ')
    result = result.replace(' in the ', ' 在 ')
    result = result.replace(' on the ', ' 在 ')
    result = result.replace(' from the ', ' 从 ')
    result = result.replace(' with the ', ' 用 ')
    result = result.replace(' to the ', ' 到 ')

    return result


# ============================================================================
# 3. 动作命令翻译（中文 → 英文）
# ============================================================================

# 动作命令模板（中文模式 → 英文模板）
# 按优先级排序，更具体的模式排在前面
ACTION_TEMPLATES_ZH_TO_EN: List[Tuple[str, str, str, list]] = [
    # 格式：每项 = (中文正则, 英文模板, 描述, [各组含义])
    # 含义：'r'=容器名, 'rid'=容器ID, 'o'=物体名, 'oid'=物体ID
    (r'去\s+(.+?)\s+(\d+)$', 'go to {r} {rid}', '移动到', ['r', 'rid']),
    (r'走到\s+(.+?)\s+(\d+)$', 'go to {r} {rid}', '移动到', ['r', 'rid']),
    (r'从\s+(.+?)\s+(\d+)\s+拿\s+(.+?)\s+(\d+)$', 'take {o} {oid} from {r} {rid}', '拿起', ['r', 'rid', 'o', 'oid']),
    (r'从\s+(.+?)\s+(\d+)\s+取\s+(.+?)\s+(\d+)$', 'take {o} {oid} from {r} {rid}', '拿起', ['r', 'rid', 'o', 'oid']),
    (r'拿起\s+(.+?)\s+(\d+)\s+从\s+(.+?)\s+(\d+)$', 'take {o} {oid} from {r} {rid}', '拿起', ['o', 'oid', 'r', 'rid']),
    (r'把\s+(.+?)\s+(\d+)\s+放到\s+(.+?)\s+(\d+)\s*(里|上)?$', 'move {o} {oid} to {r} {rid}', '放置', ['o', 'oid', 'r', 'rid']),
    (r'把\s+(.+?)\s+(\d+)\s+放进\s+(.+?)\s+(\d+)$', 'move {o} {oid} to {r} {rid}', '放入', ['o', 'oid', 'r', 'rid']),
    (r'放\s+(.+?)\s+(\d+)\s+到\s+(.+?)\s+(\d+)$', 'move {o} {oid} to {r} {rid}', '放置', ['o', 'oid', 'r', 'rid']),
    (r'打开\s+(.+?)\s+(\d+)$', 'open {r} {rid}', '打开容器', ['r', 'rid']),
    (r'关上\s+(.+?)\s+(\d+)$', 'close {r} {rid}', '关上容器', ['r', 'rid']),
    (r'关闭\s+(.+?)\s+(\d+)$', 'close {r} {rid}', '关上容器', ['r', 'rid']),
    (r'用\s+(.+?)\s+(\d+)\s+在\s+(.+?)\s+(\d+)\s*(里)?\s*清洗\s+(.+?)\s+(\d+)$',
     'clean {o} {oid} with {r} {rid}', '清洗', ['r', 'rid', '_s', '_s', 'o', 'oid']),
    (r'用\s+(.+?)\s+(\d+)\s+清洗\s+(.+?)\s+(\d+)$',
     'clean {o} {oid} with {r} {rid}', '清洗', ['r', 'rid', 'o', 'oid']),
    (r'清洗\s+(.+?)\s+(\d+)\s+用\s+(.+?)\s+(\d+)$',
     'clean {o} {oid} with {r} {rid}', '清洗', ['o', 'oid', 'r', 'rid']),
    (r'用\s+(.+?)\s+(\d+)\s+加热\s+(.+?)\s+(\d+)$',
     'heat {o} {oid} with {r} {rid}', '加热', ['r', 'rid', 'o', 'oid']),
    (r'加热\s+(.+?)\s+(\d+)\s+用\s+(.+?)\s+(\d+)$',
     'heat {o} {oid} with {r} {rid}', '加热', ['o', 'oid', 'r', 'rid']),
    (r'用\s+(.+?)\s+(\d+)\s+冷却\s+(.+?)\s+(\d+)$',
     'cool {o} {oid} with {r} {rid}', '冷却', ['r', 'rid', 'o', 'oid']),
    (r'冷却\s+(.+?)\s+(\d+)\s+用\s+(.+?)\s+(\d+)$',
     'cool {o} {oid} with {r} {rid}', '冷却', ['o', 'oid', 'r', 'rid']),
    (r'观察\s+(.+?)\s+(\d+)$', 'examine {o} {oid}', '观察', ['o', 'oid']),
    (r'查看\s+(.+?)\s+(\d+)$', 'examine {o} {oid}', '查看', ['o', 'oid']),
    (r'使用\s+(.+?)\s+(\d+)$', 'use {o} {oid}', '使用', ['o', 'oid']),
    # 简单命令
    (r'^观察$', 'look', '环顾', []),
    (r'^看看$', 'look', '环顾', []),
    (r'^背包$', 'inventory', '查看背包', []),
    (r'^物品$', 'inventory', '查看背包', []),
    (r'^帮助$', 'help', '帮助', []),
    (r'^help$', 'help', '帮助', []),
]


def translate_action(zh_command: str) -> str:
    """
    将中文动作命令翻译为 ALFWorld 可执行的英文命令。
    如果无法匹配任何模板，返回原文。
    """
    cmd = zh_command.strip()

    # 先检查是否是纯英文命令（直接返回）
    if re.match(r'^[a-zA-Z][\sa-zA-Z0-9/]*$', cmd) and not re.search(r'[\u4e00-\u9fff]', cmd):
        return cmd

    for pattern, template, _desc, arg_types in ACTION_TEMPLATES_ZH_TO_EN:
        m = re.match(pattern, cmd)
        if m:
            return _fill_template_with_args(template, m.groups(), arg_types)

    return cmd  # 退回原文


def _fill_template(template: str, match: re.Match) -> str:
    """旧的兼容接口，现在不再使用"""
    return template

def _fill_template_with_args(template: str, groups: tuple, arg_types: list) -> str:
    """用 arg_types 标注来正确映射：翻译中文物体名→英文，按标签填充"""
    groups_list = list(groups)

    # 翻译中文物体/容器名为英文
    for i, (g, atype) in enumerate(zip(groups_list, arg_types)):
        if g is not None and atype in ('o', 'r') and re.search(r'[\u4e00-\u9fff]', g):
            groups_list[i] = untranslate_object(g)

    # 构建标签→值的映射（跳过 _skip 标签）
    mapping = {}
    for i, atype in enumerate(arg_types):
        if atype.startswith('_skip'):
            continue
        if i < len(groups_list) and groups_list[i] is not None:
            mapping[atype] = groups_list[i]

    # 填充模板
    result = template
    for key, val in mapping.items():
        result = result.replace(f'{{{key}}}', val)

    return result


def translate_admissible_commands(commands: List[str]) -> List[str]:
    """
    翻译可行动作列表（英文 → 中文）。
    用于展示给 Agent 可选动作。
    """
    translated = []
    for cmd in commands:
        translated.append(translate_command_to_zh(cmd))
    return translated


def translate_command_to_zh(en_cmd: str) -> str:
    """将单个英文命令翻译为中文展示"""
    cmd = en_cmd.strip()

    # 简单的命令模板翻译（反向）
    translations = [
        (re.compile(r'^go to (.+)$'), r'去 \1'),
        (re.compile(r'^take (.+) from (.+)$'), r'从 \2 拿 \1'),
        (re.compile(r'^move (.+) to (.+)$'), r'把 \1 放到 \2'),
        (re.compile(r'^put (.+) in/on (.+)$'), r'把 \1 放到 \2 里/上'),
        (re.compile(r'^open (.+)$'), r'打开 \1'),
        (re.compile(r'^close (.+)$'), r'关上 \1'),
        (re.compile(r'^clean (.+) with (.+)$'), r'用 \2 清洗 \1'),
        (re.compile(r'^heat (.+) with (.+)$'), r'用 \2 加热 \1'),
        (re.compile(r'^cool (.+) with (.+)$'), r'用 \2 冷却 \1'),
        (re.compile(r'^examine (.+)$'), r'观察 \1'),
        (re.compile(r'^use (.+)$'), r'使用 \1'),
        (re.compile(r'^look$'), '观察'),
        (re.compile(r'^inventory$'), '查看背包'),
        (re.compile(r'^help$'), '帮助'),
    ]

    for pattern, template in translations:
        m = pattern.match(cmd)
        if m:
            result = template
            for i, g in enumerate(m.groups()):
                result = result.replace(f'\\{i+1}', _translate_phrase(g))
            return result

    # 未匹配则逐词翻译
    return _translate_phrase(cmd)


# ============================================================================
# 4. 任务目标翻译
# ============================================================================

GOAL_TRANSLATIONS: Dict[str, str] = {
    'pick_and_place_simple': '把 {obj} 放到 {recep}',
    'pick_two_obj_and_place': '拿取 {obj} 并放到 {recep}',
    'look_at_obj_in_light': '用 {toggle} 照明查看 {obj}',
    'pick_clean_then_place_in_recep': '把 {obj} 清洗干净后放到 {recep}',
    'pick_heat_then_place_in_recep': '把 {obj} 加热后放到 {recep}',
    'pick_cool_then_place_in_recep': '把 {obj} 冷却后放到 {recep}',
}

GOAL_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'put a clean sliced (\w+) in the (\w+)'), '把切好并洗干净的 {obj} 放到 {recep}'),
    (re.compile(r'put a clean sliced (\w+) in (\w+)'), '把切好并洗干净的 {obj} 放到 {recep}'),
    (re.compile(r'put a clean (\w+) in the (\w+)'), '把干净的 {obj} 放到 {recep}'),
    (re.compile(r'put a clean (\w+) in (\w+)'), '把干净的 {obj} 放到 {recep}'),
    (re.compile(r'put a hot (\w+) on the (\w+)'), '把加热的 {obj} 放到 {recep} 上'),
    (re.compile(r'put a hot (\w+) in the (\w+)'), '把加热的 {obj} 放到 {recep}'),
    (re.compile(r'put a hot (\w+) in (\w+)'), '把加热的 {obj} 放到 {recep}'),
    (re.compile(r'put a cool (\w+) in the (\w+)'), '把冷却的 {obj} 放到 {recep}'),
    (re.compile(r'put a cool (\w+) in (\w+)'), '把冷却的 {obj} 放到 {recep}'),
    (re.compile(r'put a cold (\w+) in the (\w+)'), '把冷却的 {obj} 放到 {recep}'),
    (re.compile(r'put a cold (\w+) in (\w+)'), '把冷却的 {obj} 放到 {recep}'),
    (re.compile(r'put a sliced (\w+) in the (\w+)'), '把切好的 {obj} 放到 {recep}'),
    (re.compile(r'put a sliced (\w+) in (\w+)'), '把切好的 {obj} 放到 {recep}'),
    (re.compile(r'put two (\w+) in the (\w+)'), '把两个 {obj} 放到 {recep}'),
    (re.compile(r'put two (\w+) in (\w+)'), '把两个 {obj} 放到 {recep}'),
    (re.compile(r'put an? (\w+) in the (\w+)'), '把 {obj} 放到 {recep}'),
    (re.compile(r'put an? (\w+) in (\w+)'), '把 {obj} 放到 {recep}'),
    (re.compile(r'examine an? (\w+) with the (\w+)'), '用 {tool} 照明查看 {obj}'),
]


def translate_goal(goal_text: str) -> str:
    """翻译任务目标"""
    for pattern, template in GOAL_PATTERNS:
        m = pattern.search(goal_text)
        if m:
            result = template
            result = result.replace('{obj}', translate_object(m.group(1)))
            if 'tool' in template and m.lastindex and m.lastindex >= 2:
                result = result.replace('{tool}', translate_object(m.group(2)))
            if 'recep' in template:
                recep_idx = 2 if 'tool' in template else 2
                if m.lastindex and m.lastindex >= recep_idx:
                    result = result.replace('{recep}', translate_object(m.group(recep_idx)))
            return result

    # 未匹配用短语翻译
    return _translate_phrase(goal_text)


# ============================================================================
# 5. 主翻译接口
# ============================================================================

class ALFWorldTranslator:
    """
    ALFWorld 即时翻译层。

    用法：
        translator = ALFWorldTranslator()
        zh_obs = translator.observe(english_obs)
        en_action = translator.act(chinese_command)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def observe(self, english_obs: str) -> str:
        """将英文观察翻译为中文"""
        zh = translate_observation(english_obs)
        if self.verbose:
            print(f"[Translator] EN → ZH:\n  EN: {english_obs[:200]}...\n  ZH: {zh[:200]}...")
        return zh

    def act(self, chinese_command: str) -> str:
        """将中文命令翻译为英文命令"""
        en = translate_action(chinese_command)
        if self.verbose and en != chinese_command:
            print(f"[Translator] ZH → EN: '{chinese_command}' → '{en}'")
        return en

    def translate_goal(self, goal_text: str) -> str:
        """翻译任务目标"""
        return translate_goal(goal_text)

    def translate_commands(self, commands: List[str]) -> List[str]:
        """翻译可行动作列表"""
        return translate_admissible_commands(commands)


# ============================================================================
# 6. 自测
# ============================================================================

if __name__ == '__main__':
    t = ALFWorldTranslator(verbose=False)

    # 测试场景描述
    print("=" * 60)
    print("测试 1: 场景描述翻译")
    print("=" * 60)
    samples = [
        "You are in the middle of a room. Looking quickly around you, you see a safe 1, a shelf 4, a drawer 2, a bed 1, a desk 1, and a garbagecan 1.",
        "Your task is to: examine an alarmclock with the desklamp.",
        "You arrive at loc 8. On the desk 1, you see a pen 1, a bowl 1, a alarmclock 2, a pencil 2, a pencil 3, a creditcard 3, a book 1, a alarmclock 3, a keychain 3, and a book 2.",
        "You pick up the alarmclock 2 from the desk 1.",
        "You are carrying: a alarmclock 2.",
        "You are not carrying anything.",
        "The cabinet 1 is open. In it, you see a apple 1, a bread 1.",
        "The cabinet 1 is closed.",
        "You move the alarmclock 2 to the sidetable 1.",
        "You clean the ladle 1 using the sinkbasin 1.",
        "You heat the bread 1 using the microwave 1.",
        "You cool the apple 1 using the fridge 1.",
        "You open the drawer 2.",
        "You close the safe 1.",
        "You turn on the desklamp 1.",
        "This is a clean alarmclock.",
        "There's nothing special about alarmclock 1.",
    ]

    for s in samples:
        zh = t.observe(s)
        print(f"EN: {s}")
        print(f"ZH: {zh}")
        print()

    # 测试动作翻译
    print("=" * 60)
    print("测试 2: 动作命令翻译（中文 → 英文）")
    print("=" * 60)
    action_samples = [
        ("去 书桌 1", "go to desk 1"),
        ("从 书桌 1 拿 闹钟 2", "take alarmclock 2 from desk 1"),
        ("把 闹钟 2 放到 边桌 1", "move alarmclock 2 to sidetable 1"),
        ("打开 抽屉 2", "open drawer 2"),
        ("关上 柜子 1", "close cabinet 1"),
        ("用 水槽盆 1 清洗 长柄勺 1", "clean ladle 1 with sinkbasin 1"),
        ("用 微波炉 1 加热 面包 1", "heat bread 1 with microwave 1"),
        ("用 冰箱 1 冷却 苹果 1", "cool apple 1 with fridge 1"),
        ("观察 闹钟 2", "examine alarmclock 2"),
        ("使用 台灯 1", "use desklamp 1"),
        ("观察", "look"),
        ("背包", "inventory"),
        ("帮助", "help"),
    ]

    all_passed = True
    for zh_cmd, expected_en in action_samples:
        result = t.act(zh_cmd)
        status = "✅" if result == expected_en else "❌"
        if result != expected_en:
            all_passed = False
        print(f"{status} ZH: '{zh_cmd}' → EN: '{result}' (期望: '{expected_en}')")

    print()
    if all_passed:
        print("🎉 所有动作翻译测试通过!")
    else:
        print("⚠️ 部分测试失败，请检查")

    # 测试可行动作列表翻译
    print()
    print("=" * 60)
    print("测试 3: 可行动作列表翻译")
    print("=" * 60)
    adm_cmds = ['go to desk 1', 'go to shelf 2', 'inventory', 'look',
                'take alarmclock 2 from desk 1', 'open drawer 1',
                'move alarmclock 2 to sidetable 1', 'use desklamp 1',
                'clean ladle 1 with sinkbasin 1', 'heat bread 1 with microwave 1',
                'cool apple 1 with fridge 1']
    zh_cmds = t.translate_commands(adm_cmds)
    for en, zh in zip(adm_cmds, zh_cmds):
        print(f"  {en:45s} → {zh}")

    # 测试任务目标翻译
    print()
    print("=" * 60)
    print("测试 4: 任务目标翻译")
    print("=" * 60)
    goal_samples = [
        "Your task is to: put a clean ladle in diningtable.",
        "Your task is to: examine an alarmclock with the desklamp.",
        "Your task is to: put a hot bread on the diningtable.",
        "Your task is to: put a cold apple in the fridge.",
        "Your task is to: put two basketball in the box.",
    ]
    for g in goal_samples:
        zh = t.translate_goal(g)
        print(f"EN: {g}")
        print(f"ZH: {zh}")
        print()
