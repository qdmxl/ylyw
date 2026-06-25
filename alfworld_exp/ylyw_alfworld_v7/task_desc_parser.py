#!/usr/bin/env python3
"""
从task_desc自然语言中解析：task_type, target_object, target_receptacle
不使用任何PDDL参数，仅依赖文本匹配规则。
"""
import re
from typing import Tuple, List

# 任务类型关键词
HEAT_KEYWORDS = ['heat', 'warm', 'hot', 'heated', 'cook', 'microwave']
COOL_KEYWORDS = ['cool', 'chill', 'chilled', 'cold', 'freeze', 'frozen', 'refrigerat']
CLEAN_KEYWORDS = ['clean', 'wash', 'rinse', 'rinsed', 'washed', 'cleaned', 'dirty']
LIGHT_KEYWORDS = ['lamp', 'light', 'examine', 'look at', 'turn on']
TWO_KEYWORDS = ['two', 'both', '2']

# 物体词典（英文→标准名）
OBJECT_ALIASES = {
    'alarm clock': 'alarmclock', 'clock': 'alarmclock',
    'apple': 'apple',
    'baseball bat': 'baseballbat', 'bat': 'baseballbat',
    'basketball': 'basketball',
    'book': 'book',
    'bottle': 'bottle',
    'bowl': 'bowl',
    'box': 'box',
    'bread': 'bread', 'loaf': 'bread',
    'butter knife': 'butterknife', 'butterknife': 'butterknife',
    'candle': 'candle',
    'cd': 'cd', 'disc': 'cd',
    'cell phone': 'cellphone', 'cellphone': 'cellphone', 'phone': 'cellphone',
    'cloth': 'cloth',
    'credit card': 'creditcard', 'creditcard': 'creditcard',
    'cup': 'cup', 'coffee': 'cup',
    'dish sponge': 'dishsponge', 'sponge': 'dishsponge',
    'egg': 'egg',
    'fork': 'fork',
    'glass bottle': 'glassbottle',
    'hand towel': 'handtowel', 'handtowel': 'handtowel',
    'kettle': 'kettle',
    'key chain': 'keychain', 'keychain': 'keychain', 'keys': 'keychain', 'key': 'keychain',
    'knife': 'knife',
    'ladle': 'ladle',
    'laptop': 'laptop',
    'lettuce': 'lettuce',
    'mug': 'mug',
    'newspaper': 'newspaper',
    'pan': 'pan',
    'paper towel': 'papertowelroll',
    'pen': 'pen',
    'pencil': 'pencil',
    'pepper shaker': 'peppershaker', 'pepper': 'peppershaker',
    'pillow': 'pillow',
    'plate': 'plate',
    'plunger': 'plunger',
    'pot': 'pot',
    'potato': 'potato',
    'remote control': 'remotecontrol', 'remote': 'remotecontrol',
    'salt shaker': 'saltshaker', 'salt': 'saltshaker', 'shaker': 'saltshaker',
    'scrub brush': 'scrubbrush',
    'soap bar': 'soapbar', 'soap': 'soapbar', 'bar of soap': 'soapbar',
    'spatula': 'spatula',
    'spoon': 'spoon',
    'spray bottle': 'spraybottle',
    'statue': 'statue',
    'teddy bear': 'teddybear',
    'tissue box': 'tissuebox',
    'toilet paper': 'toiletpaper', 'toilet paper roll': 'toiletpaper',
    'tomato': 'tomato',
    'towel': 'towel',
    'vase': 'vase',
    'watch': 'watch',
    'wine bottle': 'winebottle',
}

# 容器词典
RECEP_ALIASES = {
    'bathtub': 'bathtubbasin',
    'bed': 'bed',
    'cabinet': 'cabinet',
    'cart': 'cart',
    'coffee machine': 'coffeemachine', 'coffeemachine': 'coffeemachine', 'coffee maker': 'coffeemachine',
    'coffee table': 'coffeetable', 'coffeetable': 'coffeetable',
    'counter': 'countertop', 'countertop': 'countertop',
    'desk': 'desk',
    'dining table': 'diningtable', 'diningtable': 'diningtable',
    'drawer': 'drawer',
    'dresser': 'dresser',
    'fridge': 'fridge', 'refrigerator': 'fridge',
    'garbage can': 'garbagecan', 'garbage': 'garbagecan', 'trash can': 'garbagecan',
    'trash': 'garbagecan', 'bin': 'garbagecan', 'trash bin': 'garbagecan',
    'hamper': 'laundryhamper',
    'microwave': 'microwave',
    'ottoman': 'ottoman',
    'safe': 'safe',
    'shelf': 'shelf',
    'side table': 'sidetable', 'sidetable': 'sidetable', 'nightstand': 'sidetable',
    'sink': 'sinkbasin', 'sinkbasin': 'sinkbasin',
    'sofa': 'sofa', 'couch': 'sofa',
    'stove': 'stoveburner', 'stoveburner': 'stoveburner',
    'toilet': 'toilet',
    'tv stand': 'tvstand', 'tvstand': 'tvstand',
}


def parse_task_desc(task_desc: str) -> dict:
    """
    从自然语言task_desc中解析任务类型、目标物体、目标容器。
    不使用任何PDDL参数。
    
    Returns:
        {
            'task_type': str,
            'target_objects': List[str],
            'target_receps': List[str],
        }
    """
    desc = task_desc.lower().strip()
    
    # 1. 推断任务类型
    task_type = _infer_task_type(desc)
    
    # 2. 提取目标物体
    objects = _extract_objects(desc, task_type)
    
    # 3. 提取目标容器
    receps = _extract_receps(desc, task_type)
    
    return {
        'task_type': task_type,
        'target_objects': objects,
        'target_receps': receps,
    }


def _infer_task_type(desc: str) -> str:
    """推断任务类型"""
    has_two = any(kw in desc for kw in TWO_KEYWORDS)
    # "rolls" 复数也算two
    if 'rolls' in desc or 'pieces' in desc or 'sets' in desc:
        has_two = True
    
    has_light = any(kw in desc for kw in LIGHT_KEYWORDS)
    
    # cool/chill 优先于 heat（因为"chilled X in microwave"是cool不是heat）
    has_cool = any(kw in desc for kw in COOL_KEYWORDS)
    
    # heat: 仅当有heat关键词且没有cool关键词时
    has_heat = any(kw in desc for kw in HEAT_KEYWORDS) and not has_cool
    
    # clean: 包括 sink/fill/water/wet 等暗示清洗的词
    has_clean = any(kw in desc for kw in CLEAN_KEYWORDS)
    if not has_clean:
        # "fill", "water", "wet", "sink" 在动作语境中意味着clean
        clean_implicit = ['fill', 'water', 'wet', 'rinse']
        # "put X in sink" 不算，但 "fill in sink" / "from sink" 算
        if any(kw in desc for kw in clean_implicit):
            has_clean = True
        # "knife in the sink before" = clean
        if 'sink' in desc and ('before' in desc or 'then' in desc):
            has_clean = True
    
    # "microwave" 作为目标容器而非操作工具的情况
    # 如果描述是 "put X in the microwave" 且没有明确的heat动词，
    # 可能是 cool+place 或 clean+place（microwave只是放置位置）
    microwave_as_recep = ('microwave' in desc and 
                          'in the microwave' in desc and
                          not any(kw in desc for kw in ['heat', 'warm', 'hot', 'cook', 'heated']))
    if microwave_as_recep:
        has_heat = False
    
    # 优先级判断
    if has_two:
        return 'pick_two_obj_and_place'
    if has_light and not has_clean and not has_heat and not has_cool:
        return 'look_at_obj_in_light'
    if has_cool:
        return 'pick_cool_then_place_in_recep'
    if has_clean:
        return 'pick_clean_then_place_in_recep'
    if has_heat:
        return 'pick_heat_then_place_in_recep'
    return 'pick_and_place_simple'


def _extract_objects(desc: str, task_type: str) -> List[str]:
    """从描述中提取目标物体"""
    objects = []
    
    # 按长度排序（优先匹配长的，如"salt shaker"优先于"salt"）
    sorted_aliases = sorted(OBJECT_ALIASES.keys(), key=len, reverse=True)
    
    for alias in sorted_aliases:
        if alias in desc:
            obj = OBJECT_ALIASES[alias]
            if obj not in objects:
                objects.append(obj)
                # 一般只需要一个目标物体（pick_two也是同一种物体两个）
                if len(objects) >= 1:
                    break
    
    # 如果没找到，尝试更宽松匹配
    if not objects:
        # 从desc中提取名词（简单启发式）
        words = desc.split()
        for w in words:
            w_clean = w.strip('.,!?')
            if w_clean in OBJECT_ALIASES:
                objects.append(OBJECT_ALIASES[w_clean])
                break
    
    return objects


def _extract_receps(desc: str, task_type: str) -> List[str]:
    """从描述中提取目标容器"""
    receps = []
    
    # 对look_at_obj_in_light不需要容器（工具是lamp）
    if task_type == 'look_at_obj_in_light':
        return []
    
    # 按长度排序
    sorted_aliases = sorted(RECEP_ALIASES.keys(), key=len, reverse=True)
    
    for alias in sorted_aliases:
        if alias in desc:
            rec = RECEP_ALIASES[alias]
            # 排除工具类容器（它们不是目标）
            if task_type == 'pick_clean_then_place_in_recep' and rec == 'sinkbasin':
                continue
            if task_type == 'pick_heat_then_place_in_recep' and rec == 'microwave':
                continue
            if task_type == 'pick_cool_then_place_in_recep' and rec == 'fridge':
                continue
            if rec not in receps:
                receps.append(rec)
                if len(receps) >= 1:
                    break
    
    return receps


# ====== 测试 ======
if __name__ == '__main__':
    import json
    with open('ylyw_agent_v6_results.json') as f:
        d = json.load(f)
    
    correct_type = 0
    correct_obj = 0
    correct_rec = 0
    total = len(d['results'])
    
    for r in d['results']:
        desc = r['task_desc']
        real_type = r['task_type_real']
        
        parsed = parse_task_desc(desc)
        
        # 类型准确率
        if parsed['task_type'] == real_type:
            correct_type += 1
        else:
            print(f"TYPE MISMATCH: '{desc.strip()}' → parsed={parsed['task_type']} real={real_type}")
    
    print(f'\n任务类型准确率: {correct_type}/{total} = {correct_type/total*100:.1f}%')
