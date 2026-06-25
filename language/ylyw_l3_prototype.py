"""
YLYW L3 词句层：词义模糊隶属度网络 + 句法"意合"解析
基于易理探讨10论文 §3.4

核心能力：
1. 词义组合规则：根据组成字的语义隶属度，推理词义偏移方向
2. 句法"意合"解析：根据词之间的语义亲和度，推断句法结构
3. 整句语义推理：从词义+结构输出句子的完整语义

设计原则：不依赖训练数据，仅用模糊规则进行推理。
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

BAGUA = ["乾","兑","离","震","巽","坎","艮","坤"]

# ============================================================
# 1. L1+L2 复用：获取单字的完整语义信息
# ============================================================

def get_char_semantics(char):
    """获取一个汉字的完整语义信息（L1+L2）"""
    
    # L1: 部首→模糊隶属度
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
        n = len(fuzzy_rads)
        fuzzy_vec = [c/n for c in combined]
    else:
        # 多样化兜底：用字符Unicode作为微弱信号种子
        seed = ord(char) % 8
        fuzzy_vec = [0.02]*8
        fuzzy_vec[seed] = 0.15
        fuzzy_vec[(seed+3)%8] = 0.08
    
    dominant = BAGUA[fuzzy_vec.index(max(fuzzy_vec))]
    confidence = max(fuzzy_vec)
    
    # L2: 知识库查询
    if char in ideograph_kb:
        kb_info = ideograph_kb[char]
        meaning = kb_info["meaning"]
        bagua = kb_info.get("bagua_map", "未知")
        relation = kb_info.get("relation", "未知")
        source = "kb"
    else:
        affinity_bagua = None
        if fuzzy_rads:
            for rad in fuzzy_rads:
                affinity_bagua = radical_fuzzy[rad].get("bagua_affinity")
                if affinity_bagua: break
        meaning = f"({affinity_bagua or dominant}类)" if fuzzy_rads else "[需上下文]"
        bagua = affinity_bagua or dominant
        relation = "未知"
        source = "fuzzy"
    
    return {
        "char": char,
        "radicals": fuzzy_rads,
        "fuzzy_vector": [round(v,3) for v in fuzzy_vec],
        "dominant_bagua": dominant,
        "confidence": round(confidence,3),
        "bagua_affinity": bagua,
        "meaning": meaning,
        "relation": relation,
        "source": source
    }


# ============================================================
# 2. L3 词义组合规则：两个字组成词时的语义偏移
# ============================================================

def combine_semantics(left, right):
    """
    根据两个字的语义隶属度 + 关系类型，推断组合词义。
    返回：词义描述 + 语义偏移方向
    """
    l_fuzzy = left["fuzzy_vector"]
    r_fuzzy = right["fuzzy_vector"]
    l_bagua = left["dominant_bagua"]
    r_bagua = right["dominant_bagua"]
    
    # 语义相关性：两个向量余弦相似度
    dot = sum(l_fuzzy[i]*r_fuzzy[i] for i in range(8))
    norm_l = math.sqrt(sum(v*v for v in l_fuzzy))
    norm_r = math.sqrt(sum(v*v for v in r_fuzzy))
    similarity = dot / (norm_l * norm_r + 1e-9)
    
    l_rel = left["relation"]
    r_rel = right["relation"]
    
    # 规则1: 对立关系（如矛盾、阴阳）
    if similarity < 0.3 and l_bagua != r_bagua:
        # 语义对立→引申为新概念
        # 例: "矛"+"盾" → 对立统一 = 矛盾
        word_type = "对立引申"
        word_semantics = f"由[{left['meaning']}]与[{right['meaning']}]的对立统一产生的引申义"
    
    # 规则2: 高度相似（如同类叠加）
    elif similarity > 0.8:
        word_type = "同义强化"
        word_semantics = f"{left['meaning']}的加强态（与{right['meaning']}叠加）"
    
    # 规则3: 乘承关系（主从关系）
    elif l_rel in ("乘","承") or r_rel in ("乘","承"):
        # 一方主导，另一方辅助
        if l_rel in ("乘","承"):
            word_type = "前主后从"
            word_semantics = f"以[{left['meaning']}]为主导的{right['meaning']}相关概念"
        else:
            word_type = "后主前从"
            word_semantics = f"以[{right['meaning']}]为核心的{left['meaning']}性描述"
    
    # 规则4: 比应关系（并列协调）
    elif l_rel == "比" or r_rel == "比":
        word_type = "并列融合"
        word_semantics = f"[{left['meaning']}]与[{right['meaning']}]的融合态"
    
    # 默认：中等相似→语义微调
    else:
        word_type = "语义微调"
        word_semantics = f"{left['meaning']}方面的{right['meaning']}特征"
    
    return {
        "type": word_type,
        "semantics": word_semantics,
        "similarity": round(similarity, 3),
        "left_dominant": l_fuzzy,
        "right_dominant": r_fuzzy
    }


# ============================================================
# 3. L3 句法"意合"解析
# ============================================================

def parse_sentence(sentence, title=""):
    """
    对文言文句子进行整句语义解析。
    输出：逐字语义 → 词义组合 → 句法关系 → 整句语义
    """
    # 去掉标点
    chars = [c for c in sentence if c not in "，。？！；：""''（）\n\r\t "]
    
    if not chars:
        return []
    
    # Step 1: 逐字L1+L2分析
    char_results = [get_char_semantics(c) for c in chars]
    
    # Step 2: 基于语义隶属度的词分组
    # 简单策略：相邻两个字的语义相似度>0.5则成词
    words = []
    i = 0
    while i < len(char_results):
        if i+1 < len(char_results):
            sim = combine_semantics(char_results[i], char_results[i+1])["similarity"]
            # 如果两字语义亲和度高 → 组成词
            if sim > 0.55:  # 提高阈值，避免弱相关字被强行组词
                combined = combine_semantics(char_results[i], char_results[i+1])
                words.append({
                    "text": chars[i]+chars[i+1],
                    "type": "双字词",
                    "combination": combined
                })
                i += 2
                continue
        # 单字成词
        cr = char_results[i]
        words.append({
            "text": chars[i],
            "type": "单字词",
            "meaning": cr["meaning"],
            "bagua": cr["bagua_affinity"],
            "source": cr["source"]
        })
        i += 1
    
    # Step 3: 句法角色推断（主谓宾的"意合"判定）
    # 文言文典型结构: 主语(人/物名) + [状语] + 谓语(动作/状态) + 宾语
    syntax_roles = []
    for j, w in enumerate(words):
        wtext = w["text"]
        if w["type"] == "单字词":
            first_char = char_results[[c["char"] for c in char_results].index(wtext[0])]
        else:
            first_char = char_results[[c["char"] for c in char_results].index(wtext[0])]
        
        bagua = first_char["bagua_affinity"]
        
        # 主语判定：人/物名词，位于句首
        if j == 0 and any(b in bagua for b in ["亻","乾","坤","人","君","子","民"]):
            role = "主语(施事者)"
        elif any(b in bagua for b in ["亻","人"]) or any(kw in wtext for kw in ["子","人","君","民","吾"]):
            role = "主语" if j < len(words)//2 else "宾语/对象"
        # 谓语判定：动作/状态词
        elif any(b in bagua for b in ["震","彳","辶","扌"]) or any(kw in wtext for kw in ["行","学","习","知","闻","见","改"]):
            role = "谓语(动作)"
        # 状语/修饰
        elif j > 0 and words[j-1]["type"] == "单字词" and first_char["confidence"] > 0.7:
            role = "状语/修饰"
        else:
            role = "宾语/对象"
        
        syntax_roles.append({"word": wtext, "role": role, "bagua": bagua})
    
    # Step 4: 整句语义推理
    # 提取核心谓词和核心主语
    subjects = [s for s in syntax_roles if "主语" in s["role"]]
    predicates = [s for s in syntax_roles if "谓语" in s["role"]]
    objects = [s for s in syntax_roles if "宾语" in s["role"]]
    
    if subjects and predicates:
        main_subj = subjects[0]["word"]
        main_pred = predicates[0]["word"]
        main_obj = objects[0]["word"] if objects else ""
        
        if main_obj:
            sentence_semantics = f"{main_subj}通过{main_pred}而作用于{main_obj}"
        else:
            sentence_semantics = f"{main_subj}的状态/行为是{main_pred}"
    elif predicates:
        sentence_semantics = f"(隐含主语)执行{predicates[0]['word']}"
    else:
        sentence_semantics = f"{' '.join(chars)}——[需更多上下文消歧]"
    
    return {
        "title": title,
        "sentence": sentence,
        "chars": char_results,
        "words": words,
        "syntax": syntax_roles,
        "semantics": sentence_semantics
    }


# ============================================================
# 4. 演示
# ============================================================
if __name__ == '__main__':
    test_sentences = [
        ("《学而》1.1", "学而时习之"),
        ("《学而》1.1", "人不知而不愠"),
        ("《学而》1.2", "孝弟也者其为仁之本与"),
        ("《学而》1.4", "吾日三省吾身"),
        ("《为政》2.11", "温故而知新"),
        ("《为政》2.15", "学而不思则罔"),
        ("《述而》7.22", "三人行必有我师焉"),
        ("《学而》1.1b","有朋自远方来"),
        ("《学而》1.6", "行有余力则以学文"),
    ]
    
    print("="*70)
    print("YLYW L3词句层 — 文言文句法'意合'解析原型")
    print("="*70)
    
    total_kb_hits = 0
    total_chars = 0
    
    for title, sentence in test_sentences:
        result = parse_sentence(sentence, title)
        chars_list = sentence.replace("，","").replace("。","").replace(" ","")
        
        print(f"\n{'─'*70}")
        print(f"📖 {title}: 「{sentence}」")
        print(f"{'─'*70}")
        
        # 逐字语义
        print("  [L1+L2 逐字]:")
        for cr in result["chars"]:
            src_tag = "★" if cr["source"] == "kb" else " "
            print(f"    {src_tag}{cr['char']} → {cr['bagua_affinity']:15} | {cr['meaning'][:30]}")
            if cr["source"] == "kb":
                total_kb_hits += 1
            total_chars += 1
        
        # 词分组
        print("  [L3 词分组]:")
        for w in result["words"]:
            if w["type"] == "双字词":
                c = w["combination"]
                print(f"    「{w['text']}」 ({c['type']}, sim={c['similarity']:.2f}) → {c['semantics'][:50]}")
            else:
                print(f"    「{w['text']}」 (单字) → {w['meaning'][:30]}")
        
        # 句法角色
        print("  [L3 句法角色]:")
        for sr in result["syntax"]:
            print(f"    {sr['word']:<6} → {sr['role']}")
        
        # 整句语义
        print(f"  [整句语义]: {result['semantics']}")
    
    print(f"\n{'='*70}")
    print(f"知识库命中: {total_kb_hits}/{total_chars} ({total_kb_hits*100//total_chars}%)")
    print(f"知识库规模: {len(ideograph_kb)} 字")
    print(f"{'='*70}")
