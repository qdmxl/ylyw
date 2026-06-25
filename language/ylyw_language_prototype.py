"""
YLYW L1 字形层 + L2 字义层 原型系统
基于易理探讨10论文 §3.2-3.3

对输入汉字进行：
  L1: 部首识别 → 模糊语义隶属度向量
  L2: 会意字"乘承比应"关系解析 → 字义推断

演示：处理《论语》经典句子
"""
import json, os, re, math

# ============================================================
# 1. 加载知识库
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, 'radical_fuzzy_base.json'), 'r', encoding='utf-8') as f:
    radical_fuzzy = json.load(f)

with open(os.path.join(BASE, 'ideograph_knowledge_base.json'), 'r', encoding='utf-8') as f:
    ideograph_kb = json.load(f)

from hanzi_decomposition import HANZI_DECOMPOSITION
from decomp_to_fuzzy_map import DECOMP_TO_FUZZY_RADICAL

def detect_radicals(char):
    """检测一个汉字包含的偏旁部首（使用手工拆分表）"""
    raw_comps = HANZI_DECOMPOSITION.get(char, [])
    # 映射到核心19部首
    fuzzy_rads = []
    for c in raw_comps:
        mapped = DECOMP_TO_FUZZY_RADICAL.get(c)
        if mapped and mapped in radical_fuzzy and mapped not in fuzzy_rads:
            fuzzy_rads.append(mapped)
    return fuzzy_rads

def get_char_fuzzy_membership(char):
    """L1层：获取汉字的8维模糊语义隶属度"""
    radicals = detect_radicals(char)
    if not radicals:
        return [0.05] * 8, []
    
    combined = [0.0] * 8
    for rad in radicals:
        mem = radical_fuzzy[rad]["membership"]
        for j in range(8):
            combined[j] += mem[j]
    
    n = len(radicals)
    combined = [c / n for c in combined]
    return combined, radicals


# ============================================================
# 3. L2字义层：会意字"乘承比应"解析
# ============================================================
BAGUA_NAMES = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
RELATION_MEANING = {
    "乘": "上临下：上方部件主导下方",
    "承": "下载上：下方部件支撑上方",
    "比": "并列互助：部件平等协作",
    "应": "内外呼应：内部外部协调"
}

def explain_ideograph(char):
    """L2层：解释一个会意字的部件关系，给出字义推断"""
    if char in ideograph_kb:
        info = ideograph_kb[char]
        return {
            "char": char,
            "components": info["components"],
            "relation": info["relation"],
            "relation_meaning": RELATION_MEANING.get(info["relation"], ""),
            "explanation": info["explanation"],
            "bagua_affinity": info["bagua_map"],
            "meaning": info["meaning"],
            "source": "知识库(先验)"
        }
    
    # 不在知识库中，尝试基于检测到的部首做模糊推断
    _, radicals = get_char_fuzzy_membership(char)
    if radicals:
        return {
            "char": char,
            "components": radicals,
            "relation": "未知(需人工标注)",
            "relation_meaning": "",
            "explanation": f"检测到部首: {', '.join(radicals)}，语义需结合上下文消歧",
            "bagua_affinity": "未知",
            "meaning": f"含部首{radicals[0]}，初步推测语义类别",
            "source": "L1模糊推断(待校准)"
        }
    
    return {
        "char": char,
        "components": [],
        "relation": "未知",
        "explanation": "未检测到已知部首，语义需从上下文统计推断",
        "source": "无先验(需LLM)"
    }


# ============================================================
# 4. 句子级处理：文言文→逐字语义解析
# ============================================================
def process_sentence(sentence, title=""):
    """处理一句文言文，输出逐字解析+完整推理链"""
    chars = list(sentence.replace(" ", "").replace("，", "").replace("。", "").replace("？","").replace("！",""))
    
    results = []
    for char in chars:
        if char in "：；""''（）《》\n\r\t":
            continue
        
        # L1: 获取模糊隶属度
        fuzzy_vec, radicals = get_char_fuzzy_membership(char)
        dominant_idx = fuzzy_vec.index(max(fuzzy_vec))
        dominant_bagua = BAGUA_NAMES[dominant_idx]
        max_membership = fuzzy_vec[dominant_idx]
        
        # L2: 会意字解析
        l2_result = explain_ideograph(char)
        
        results.append({
            "char": char,
            "radicals": radicals,
            "fuzzy_vector": [round(v, 3) for v in fuzzy_vec],
            "dominant_bagua": dominant_bagua,
            "confidence": round(max_membership, 3),
            "l2_explanation": l2_result
        })
    
    return results


# ============================================================
# 5. 演示：处理《论语》经典句子
# ============================================================
if __name__ == '__main__':
    test_sentences = [
        ("《论语·学而》", "学而时习之，不亦说乎"),
        ("《论语·学而》", "有朋自远方来，不亦乐乎"),
        ("《论语·学而》", "人不知而不愠，不亦君子乎"),
        ("《论语·为政》", "温故而知新，可以为师矣"),
        ("《论语·述而》", "三人行，必有我师焉"),
    ]
    
    print("=" * 70)
    print("YLYW 汉语言文字处理原型 — L1字形层 + L2字义层")
    print("基于易理探讨10论文 §3.2-3.3")
    print("=" * 70)
    
    for title, sentence in test_sentences:
        print(f"\n{'─' * 70}")
        print(f"📖 {title}: 「{sentence}」")
        print(f"{'─' * 70}")
        
        results = process_sentence(sentence, title)
        
        for r in results:
            char = r['char']
            rads = r['radicals']
            bagua = r['dominant_bagua']
            conf = r['confidence']
            l2 = r['l2_explanation']
            
            # 简洁输出
            rad_str = f"[{','.join(rads)}]" if rads else "[无部首]"
            kb_tag = "★" if l2['source'] == '知识库(先验)' else "  "
            
            print(f"  {kb_tag} {char} {rad_str:<20} 卦:{bagua}({conf:.2f})  {l2.get('meaning','')[:30]}")
        
        # 汇总统计
        kb_count = sum(1 for r in results if r['l2_explanation']['source'] == '知识库(先验)')
        total = len(results)
        print(f"  ── 知识库覆盖: {kb_count}/{total} ({100*kb_count//total}%)")
    
    print(f"\n{'=' * 70}")
    print(f"知识库规模: {len(ideograph_kb)}个会意字 | 部首库: {len(radical_fuzzy)}个部首")
    print(f"{'=' * 70}")
