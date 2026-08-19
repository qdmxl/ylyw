#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_jingui_discriminator.py — 古籍症状判别测试（跨典籍零样本）

核心思路（马老师 2026-08-16 拍板）：
  训练 = 十三经中排除"测试典籍"的其余古籍；
  测试 = 其他古籍里"脏腑→症状"的成说条文（金标准 = 条文自带脏腑），
         检验引擎能否零样本从症状判别脏腑。

测试集（金标准=条文自带脏腑，古籍原文，零人工标注）：
  A. 《诸病源候论》五脏中风条：心中风/肝中风/脾中风/肾中风/肺中风
  B. 《丹溪心法》五脏经见证条：肝/心/脾/肺/肾 经见证

判别器：双字证候词级 PMI + 指别力投票（见注）。
"""
import os, json, math, re, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")
Z5 = "心肝脾肺肾"

def clean_book(path):
    t = open(path, encoding="utf-8", errors="ignore").read()
    t = re.sub(r'<[^>]+>', '', t)
    t = '\n'.join(l.strip() for l in t.split('\n')
                  if l.strip() and not re.match(r'^(书名|作者|朝代|年份)', l.strip()) and l.strip() != '目录')
    t = re.sub(r'属性：?', '', t); t = re.sub(r'\s+', '', t); t = t.replace('∶', '：')
    return t

def extract_zyf():
    """诸病源候论 五脏中风条 → [(脏, 症状句), ...]"""
    t = clean_book(os.path.join(HERE, "医经语料/诸病源候论_原文.txt"))
    items = []
    seen = set()
    for m in re.finditer(r'([心肝脾肺肾])中风，([^。]{8,60})。', t):
        z, sym = m.group(1), m.group(2)
        key = z + sym[:10]
        if key not in seen:
            seen.add(key); items.append((z, sym))
    return items

def extract_danxi():
    """丹溪心法 五脏经见证条 → [(脏, 症状句), ...]"""
    t = clean_book(os.path.join(HERE, "医经语料/丹溪心法_原文.txt"))
    items = []
    seen = set()
    for m in re.finditer(r'([心肝脾肺肾])经见证([^。]{6,60})。', t):
        z, sym = m.group(1), m.group(2)
        key = z + sym[:10]
        if key not in seen:
            seen.add(key); items.append((z, sym))
    return items

def build_train():
    """训练语料: 十三经中排除 诸病源候论/丹溪心法"""
    train_books = [
        ("neijing","corpus_neijing_wenyan.json"), ("nannjing","corpus_nannjing_wenyan.json"),
        ("shanghan","corpus_shanghan_wenyan.json"), ("jinkui","corpus_jinkui_wenyan.json"),
        ("bencao","corpus_bencao_wenyan.json"), ("wenbing","corpus_wenbing_wenyan.json"),
        ("maijing","corpus_maijing_wenyan.json"), ("zhenjiu_jia","corpus_zhenjiu_jia_wenyan.json"),
        ("zhenjiu_da","corpus_zhenjiu_da_wenyan.json"), ("zhongcang","corpus_zhongcang_wenyan.json"),
        ("piwei","corpus_piwei_wenyan.json"),
    ]
    sents = []
    for k, fn in train_books:
        p = os.path.join(HERE, fn)
        if os.path.exists(p): sents.extend(json.load(open(p, encoding="utf-8")))
    return sents

def build_discriminator(sents):
    """双字词级 PMI 判别器"""
    N = len(sents)
    docX = defaultdict(Counter); docF = defaultdict(int); docZ = {z:0 for z in Z5}
    for s in sents:
        for z in Z5:
            if z in s: docZ[z] += 1
        seg = [c if c not in FUNC else '|' for c in s]
        for p in ''.join(seg).split('|'):
            for i in range(len(p)-1):
                w = p[i:i+2]
                if len(set(w)) < 2 or any(c in w for c in '健康'): continue
                docF[w] += 1
                for z in Z5:
                    if z in s: docX[w][z] += 1
    cache = {}
    def wpmi(w, z):
        c = docX[w][z]
        return math.log((c/N)/((docF[w]/N)*(docZ[z]/N)+1e-12)) if c else float('-inf')
    def judge(sym, gap=1.0):
        seg = [c if c not in FUNC else '|' for c in sym]
        scores = {z:0.0 for z in Z5}; used = set()
        for p in ''.join(seg).split('|'):
            for i in range(len(p)-1):
                w = p[i:i+2]
                if len(set(w))<2 or w in used: continue
                used.add(w)
                if w not in cache: cache[w] = {z:wpmi(w,z) for z in Z5}
                vals = sorted((cache[w].get(z,float('-inf')) for z in Z5), reverse=True)
                if vals[0]==float('-inf') or vals[0]<=0: continue
                gapv = vals[0] - vals[1] if len(vals)>1 else 99
                if gapv >= gap:
                    best = Z5[max(range(5), key=lambda i: cache[w][Z5[i]])]
                    scores[best] += vals[0]
        if scores and max(scores.values())>0:
            return max(scores, key=lambda z:scores[z])
        return None
    return judge

def main():
    print("="*70)
    print("古籍症状判别测试（跨典籍零样本）")
    print("="*70)
    train = build_train()
    print(f"训练语料: {len(train)}句 (排除测试典籍)")
    judge = build_discriminator(train)

    sets = [("《诸病源候论》中风条", extract_zyf()),
            ("《丹溪心法》经见证条", extract_danxi())]
    total_ok = total = 0
    for name, items in sets:
        print(f"\n--- {name} ---")
        ok = 0
        for z, sym in items:
            d = judge(sym)
            hit = "✓" if d==z else "✗"
            if hit=="✓": ok+=1; 
            total_ok += (1 if d==z else 0); total += 1
            print(f"  [{z}] «{sym}» → {str(d):<4}{hit}")
        print(f"  正确率: {ok}/{len(items)}")
    print(f"\n总正确率: {total_ok}/{total} = {total_ok/max(total,1)*100:.0f}%")

if __name__ == "__main__":
    main()
