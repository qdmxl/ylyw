"""
YLYW L3 词句层 v2 — 重构词分组逻辑

问题诊断：
  1. 8维模糊向量集中在乾/兑/离少数维度，sim≈0.85-0.99普遍，阈值失效
  2. 虚词被当做实词与其他字组词（"学而"被误判为同义词）
  3. 仅靠向量相似度无法区分文言文词边界

解决方案：
  1. 虚词分离：虚词独立标注，不参与实词分组
  2. 三通道并行判定：语义亲和度 + 句法角色兼容 + 词典匹配
  3. 最小词长偏好：实词优先单字，仅强信号才合并为双字词
  4. 句法驱动的词边界：连词/副词/语气词天然作为词边界
"""

import json, os, math, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from hanzi_decomposition import HANZI_DECOMPOSITION
from decomp_to_fuzzy_map import DECOMP_TO_FUZZY_RADICAL

with open(os.path.join(BASE, 'radical_fuzzy_base.json'), 'r', encoding='utf-8') as f:
    radical_fuzzy = json.load(f)
with open(os.path.join(BASE, 'ideograph_knowledge_base.json'), 'r', encoding='utf-8') as f:
    ideograph_kb = json.load(f)
with open(os.path.join(BASE, 'function_words.json'), 'r', encoding='utf-8') as f:
    function_words = json.load(f)
with open(os.path.join(BASE, 'classical_bigrams.json'), 'r', encoding='utf-8') as f:
    bigram_data = json.load(f)
    BIGRAM_POSITIVE = set(bigram_data["positive"])
    BIGRAM_NEGATIVE = set(bigram_data["negative"])
    BIGRAM_DEFS = bigram_data["definitions"]

BAGUA = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 1. 角色分类系统（替代单纯向量相似度）
# ============================================================

# 每个汉字在句中的角色分类
ROLE_CATEGORIES = {
    "虚词-连词": ["而", "与", "则", "且", "虽", "然", "因", "故"],
    "虚词-副词": ["不", "勿", "未", "必", "亦", "皆", "非", "弗", "毋"],
    "虚词-介词": ["于", "以", "自", "从", "为", "由", "在"],
    "虚词-助词": ["之", "也", "矣", "乎", "焉", "者", "所", "诸", "耳"],
    "虚词-代词": ["其", "吾", "我", "汝", "尔", "彼", "此", "是", "何"],
    "虚词-语气": ["乎", "哉", "耶", "与", "夫"],
    "实词-动作": [],  # 动态填充
    "实词-名物": [],  # 动态填充
    "实词-性状": [],  # 动态填充
    "实词-数量": [],  # 动态填充
}

def classify_char(char):
    """对汉字进行角色分类（v3: 增加存在动词类和更精细的判定）"""
    kb_info = ideograph_kb.get(char, {})
    fw_info = function_words.get(char, {})
    
    # 检查虚词
    role = fw_info.get("role", "")
    if role:
        if role == "副词": return "虚词-副词"
        if role == "连词": return "虚词-连词"
        if role in ("介词", "助动词"): return "虚词-介词"
        if role in ("助词", "语气词", "兼词"): return "虚词-助词"
        if role == "代词": return "虚词-代词"
    
    # 检查实词
    bagua = kb_info.get("bagua_map", "")
    meaning = kb_info.get("meaning", "")
    
    # 存在动词（特殊类）: 有/无/在/存
    if char in "有无在存":
        return "实词-存在"
    
    # 数量类（在动作之前判定）
    if char in "一二三四五六七八九十百千万":
        return "实词-数量"
    if meaning and any(kw in meaning[:3] for kw in ["三才","众多","几个"]):
        return "实词-数量"
    
    # 动作类
    action_keywords = ["行走","推拉","学习","知道","听闻","看见","观察","寻求","获取",
                       "教学","改变","反省","观察","思考","忘记","忍耐","作为","饮食","说话"]
    action_chars = "行走推拉学习知闻见观求取教改省察思忘忍为饮食说"
    if any(kw[:2] in meaning[:4] for kw in action_keywords) or char in action_chars:
        if char not in "有知温故新远":  # 排除多义字
            return "实词-动作"
    if any(b in bagua for b in ["震","彳","辶"]) and char not in "远近来归":
        return "实词-动作"
    if any(b in bagua for b in ["扌"]) and char not in "把持推拉打":
        return "实词-动作"
    
    # 性状/状态类（提高优先级）
    trait_keywords = ["温和","崭新","故事","遥远","远近","大小","善美","好","新旧","故旧",
                      "富贵","贫穷","轻重","光明","仁爱","正义","礼仪","诚信","正直"]
    if any(kw[:2] in meaning[:4] for kw in trait_keywords):
        return "实词-性状"
    # 常见的文言性状字
    if char in "温故新旧远近大小美善富贵贫轻重明仁礼信义":
        return "实词-性状"
    
    # 名物类
    if any(kw in meaning for kw in ["人","子","君","民","王","父","母","朋","友",
                                     "山","水","日","月","天","地","身","心","目",
                                     "兄弟","臣","众"]):
        return "实词-名物"
    if any(b in bagua for b in ["坤","艮","土","石"]) and "材料" not in meaning:
        return "实词-名物"
    
    # 默认：根据八卦偏向判断
    if "震" in bagua or "扌" in bagua or "辶" in bagua:
        return "实词-动作"
    if "离" in bagua or "火" in bagua:
        return "实词-性状"
    
    return "实词-名物"


# ============================================================
# 2. L1+L2字符语义提取（简化版）
# ============================================================

def get_char_info(char):
    """返回字符的完整L1+L2信息"""
    raw_comps = HANZI_DECOMPOSITION.get(char, [])
    fuzzy_rads = []
    for c in raw_comps:
        mapped = DECOMP_TO_FUZZY_RADICAL.get(c)
        if mapped and mapped in radical_fuzzy and mapped not in fuzzy_rads:
            fuzzy_rads.append(mapped)
    
    if fuzzy_rads:
        combined = [0.0]*8
        for rad in fuzzy_rads:
            mem = radical_fuzzy[rad]["membership"]
            for j in range(8): combined[j] += mem[j]
        fuzzy_vec = [c/len(fuzzy_rads) for c in combined]
    else:
        seed = ord(char) % 8
        fuzzy_vec = [0.02]*8
        fuzzy_vec[seed] = 0.15
        fuzzy_vec[(seed+3)%8] = 0.08
    
    dominant = BAGUA[fuzzy_vec.index(max(fuzzy_vec))]
    kb_info = ideograph_kb.get(char, {})
    meaning = kb_info.get("meaning", f"({dominant}类)")
    bagua = kb_info.get("bagua_map", dominant)
    relation = kb_info.get("relation", "未知")
    role = classify_char(char)
    
    return {
        "char": char, "fuzzy_vector": fuzzy_vec, "dominant_bagua": dominant,
        "bagua": bagua, "meaning": meaning, "relation": relation, "role": role
    }


# ============================================================
# 3. 词分组v2：三通道判定
# ============================================================

def should_merge(left, right):
    """
    三通道+词典判定两个字是否合并为词。
    """
    l_role = left["role"]
    r_role = right["role"]
    bigram = left["char"] + right["char"]
    
    # 通道0：词典权威判断
    if bigram in BIGRAM_NEGATIVE:
        return False  # 反例：词典明确不应合并
    if bigram in BIGRAM_POSITIVE:
        return True   # 正例：词典明确应该合并
    
    # 通道A/B/C：虚词天然边界
    if "虚词" in l_role or "虚词" in r_role:
        return False
    
    # 通道D：实词+实词
    l_subcat = l_role.split("-")[-1]
    r_subcat = r_role.split("-")[-1]
    
    compatible_pairs = [
        ("性状", "名物"), ("名物", "名物"),
        ("数量", "名物"), ("性状", "性状"),
        # 动作+动作仅限极高sim且词典兜底
    ]
    
    if (l_subcat, r_subcat) not in compatible_pairs:
        return False
    
    # 语义亲和度
    l_vec = left["fuzzy_vector"]
    r_vec = right["fuzzy_vector"]
    dot = sum(l_vec[i]*r_vec[i] for i in range(8))
    nl = math.sqrt(sum(v*v for v in l_vec)); nr = math.sqrt(sum(v*v for v in r_vec))
    sim = dot / (nl*nr + 1e-9)
    
    # 收紧阈值：需要>0.88（而非原来的0.75）
    if sim < 0.88:
        return False
    
    # 知识库boost
    l_rel = left["relation"]
    r_rel = right["relation"]
    kb_boost = (l_rel in ("比", "乘") or r_rel in ("比", "乘"))
    
    if sim > 0.90 and kb_boost:
        return True
    if sim > 0.95:
        return True
    
    return False


def segment_words(chars_info):
    """
    基于角色分类+三通道判定的词分组。
    返回词序列。
    """
    n = len(chars_info)
    words = []
    i = 0
    
    while i < n:
        if i + 1 < n and should_merge(chars_info[i], chars_info[i+1]):
            # 合并为双字词
            left = chars_info[i]
            right = chars_info[i+1]
            
            # 计算合并后的语义
            l_vec = left["fuzzy_vector"]
            r_vec = right["fuzzy_vector"]
            dot = sum(l_vec[j]*r_vec[j] for j in range(8))
            nl = math.sqrt(sum(v*v for v in l_vec)); nr = math.sqrt(sum(v*v for v in r_vec))
            bigram = left["char"] + right["char"]
            sim = dot / (nl*nr + 1e-9)
            
            # 优先查词典
            if bigram in BIGRAM_DEFS:
                word_type = "词典合成词"
                combined_meaning = BIGRAM_DEFS[bigram]
            elif sim > 0.85:
                word_type = "并列/偏正合成词"
                combined_meaning = f"{left['meaning']}·{right['meaning']}"
            else:
                word_type = "偏正合成词"
                combined_meaning = f"{left['meaning']}的{right['meaning']}"
            
            words.append({
                "text": left["char"] + right["char"],
                "type": word_type,
                "components": [left, right],
                "similarity": round(sim, 3),
                "meaning": combined_meaning
            })
            i += 2
        else:
            # 单字成词
            ci = chars_info[i]
            
            # 虚词标注
            if "虚词" in ci["role"]:
                word_type = f"虚词({ci['role'].split('-')[1]})"
            else:
                word_type = f"实词({ci['role'].split('-')[1]})"
            
            words.append({
                "text": ci["char"],
                "type": word_type,
                "meaning": ci["meaning"],
                "bagua": ci["bagua"],
                "role": ci["role"]
            })
            i += 1
    
    return words


# ============================================================
# 4. 句法分析 + 整句语义
# ============================================================

def analyze_syntax(words):
    """基于词序列推断句法结构（v3: 合成词句法角色 + 数量词处理）"""
    roles = []
    for i, w in enumerate(words):
        wtype = w.get("type", "")
        role_type = w.get("role", "")
        text = w.get("text", "")
        
        # 词典合成词：根据组成推断角色
        if "词典合成词" in wtype or "合成词" in wtype:
            comps = w.get("components", [])
            if comps:
                # 取第一个成分的角色作为合成词的角色
                r0 = comps[0].get("role", "")
                if "性状" in r0:
                    syn_role = "主语/主题" if i == 0 else "宾语/对象"
                elif "数量" in r0:
                    syn_role = "定语(数量)"
                else:
                    syn_role = "主语/主题" if i == 0 else "谓语/宾语"
            else:
                syn_role = "主语/主题" if i == 0 else "谓语/宾语"
            roles.append({"word": text, "role": syn_role, "cat": "合成词"})
            continue
        
        # 数量词
        if "实词-数量" in role_type:
            syn_role = "定语(数量修饰)"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 虚词-代词
        if "虚词-代词" in role_type:
            syn_role = "主语" if i == 0 else "宾语/定语"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 虚词-副词
        if "虚词-副词" in role_type:
            syn_role = "状语(修饰)"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 虚词-连词
        if "虚词-连词" in role_type:
            syn_role = "连接词"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 虚词-介词
        if "虚词-介词" in role_type:
            syn_role = "介词"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 虚词-助词
        if "虚词-助词" in role_type:
            syn_role = "助词(的/停顿/语气)"
            roles.append({"word": text, "role": syn_role, "cat": role_type})
            continue
        
        # 实词：基于位置和类别判定
        if "实词-存在" in role_type:
            syn_role = "谓语(存在)"
        elif "实词-动作" in role_type:
            syn_role = "谓语(动作)" if i > 0 else "话题/主语"
        elif "实词-性状" in role_type:
            syn_role = "谓语(性状)" if i > 0 else "定语/主语"
        elif "实词-名物" in role_type:
            syn_role = "宾语" if i > 0 else "主语"
        else:
            syn_role = "未知"
        
        roles.append({"word": text, "role": syn_role, "cat": role_type})
    
    return roles


def generate_semantics(words, syntax_roles):
    """基于词序列+句法角色生成整句语义（v3: 正确聚合合成词+数量词）"""
    subject_parts = []
    pred_parts = []
    obj_parts = []
    connectives = []
    modifiers = []
    
    for w, sr in zip(words, syntax_roles):
        role = sr["role"]
        text = w["text"]
        meaning = w.get("meaning", text)
        wtype = w.get("type", "")
        
        if "主语" in role:
            subject_parts.append(f"{text}({meaning})" if meaning != text else text)
        elif "谓语" in role:
            pred_parts.append(f"{text}({meaning[:15]})" if meaning != text and len(meaning) < 20 else text)
        elif "宾语" in role:
            obj_parts.append(text)
        elif "定语" in role:
            modifiers.append(f"{text}的")
        elif "状语" in role:
            modifiers.append(text)
        elif "连接词" in role:
            connectives.append(text)
        elif "介词" in role:
            modifiers.append(f"{text}")
        elif "助词" in role:
            pass  # 助词在整句语义中不显式表达
    
    # 组装语义
    parts = []
    
    # 主语部分
    if subject_parts:
        parts.append(' '.join(subject_parts))
    
    # 修饰部分
    if modifiers:
        parts.append('(' + ' '.join(modifiers) + ')')
    
    # 连接词
    if connectives:
        parts.append('[' + ' '.join(connectives) + ']')
    
    # 谓语+宾语
    if pred_parts:
        pred_str = ' '.join(pred_parts)
        if obj_parts:
            parts.append(f'{pred_str} → {" ".join(obj_parts)}')
        else:
            parts.append(pred_str)
    elif obj_parts:
        parts.append('→ ' + ' '.join(obj_parts))
    
    if not parts:
        return "[待更多上下文消歧]"
    
    return ' | '.join(parts)


# ============================================================
# 5. 完整管道
# ============================================================

def parse_sentence_v2(sentence, title=""):
    """完整的L1→L2→词分组→句法→语义管道"""
    chars = [c for c in sentence if c not in "，。？！；：""''（）\n\r\t "]
    if not chars: return None
    
    # L1+L2: 逐字分析
    chars_info = [get_char_info(c) for c in chars]
    
    # 词分组v2
    words = segment_words(chars_info)
    
    # 句法分析
    syntax = analyze_syntax(words)
    
    # 整句语义
    semantics = generate_semantics(words, syntax)
    
    return {
        "title": title, "sentence": sentence,
        "chars": chars_info, "words": words,
        "syntax": syntax, "semantics": semantics
    }


# ============================================================
# 6. 演示
# ============================================================
if __name__ == '__main__':
    tests = [
        ("《学而》1.1",  "学而时习之"),
        ("《学而》1.1b", "人不知而不愠"),
        ("《为政》2.11", "温故而知新"),
        ("《为政》2.15", "学而不思则罔"),
        ("《述而》7.22", "三人行必有我师焉"),
        ("《学而》1.1c", "有朋自远方来"),
        ("《学而》1.2",  "孝弟也者其为仁之本与"),
        ("《学而》1.4",  "吾日三省吾身"),
        ("《学而》1.6",  "行有余力则以学文"),
        ("《为政》2.17", "知之为知之不知为不知"),
    ]
    
    print("="*75)
    print("YLYW L3词句层 v2 — 虚词驱动分词 + 三通道判定")
    print("="*75)
    
    for title, sentence in tests:
        r = parse_sentence_v2(sentence, title)
        if not r: continue
        
        print(f"\n{'─'*75}")
        print(f"📖 {title}: 「{sentence}」")
        print(f"{'─'*75}")
        
        # 角色分类
        print("  [角色分类]:")
        for ci in r["chars"]:
            marker = "虚" if "虚词" in ci["role"] else "实"
            kb_hit = "★" if ci["char"] in ideograph_kb else " "
            print(f"    {kb_hit}{ci['char']:<3} → {ci['role']:<16} | {ci['meaning'][:25]}")
        
        # 词分组
        print("  [词分组]:")
        for w in r["words"]:
            sim_str = f" sim={w.get('similarity',0):.3f}" if "similarity" in w else ""
            print(f"    「{w['text']:<8}」 {w['type']:<20} {sim_str} → {w['meaning'][:40]}")
        
        # 句法
        print("  [句法]:")
        for sr in r["syntax"]:
            print(f"    {sr['word']:<8} → {sr['role']}")
        
        # 整句语义
        print(f"  [整句]: {r['semantics']}")
    
    kb_hits = sum(1 for r in [parse_sentence_v2(s, t) for t,s in tests] if r 
                  for ci in r["chars"] if ci["char"] in ideograph_kb)
    total = sum(len([c for c in s if c not in "，。？！；：""''（）\n\r\t "]) for _,s in tests)
    print(f"\n{'='*75}")
    print(f"知识库命中: {kb_hits}/{total} ({kb_hits*100//total}%)")
    print(f"{'='*75}")
