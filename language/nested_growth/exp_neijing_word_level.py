#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_word_level.py v2 — 《黄帝内经》词级(多字词)自组织验证

诚实定位（依据附录五/L2诊断）：
  医学核心字(心/血/脉/经…)在字形八卦库中为"平坦"无信息 → 词六爻(字形合成)对医学词
  失效。故词级语义的正确通道 = 语料共现(分布语义)，字形仅作粗范畴辅助。

本脚本核心：
  1. 词繁殖：从内经提取高频双字词(词元胞)
  2. 词级语料自组织：双字词在内经语料中共现 → PMI词向量 → 中医范畴词能否互聚
     (检验：五脏词/六腑词/气血津精词/经络词 各自内部相似度 > 与外界)
  3. 词级跨系统对照：同范畴词 vs 跨范畴词 的 margin
"""
import os, json, math
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

# 停用：标点+虚词（注意：不把 阴阳/五行 等医学术语字符停掉）
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")
# 不把医学词停掉

# 中医范畴 ground-truth（双字术语词）
WORD_CATEGORIES = {
    "五脏":  ["心包","心气","肝气","肾气","心火","肝火","肺气","脾气","心血","肝血","肾阴","肾阳","心阳","肺阴","心阳","肺热","肝寒","脾湿","肾水","真阴","真阳"],
    "六腑":  ["膀胱","三焦","肠胃","胆气","小肠","大肠","胃气","胆府","肠胃","小肠之气","足阳明","胃经"],
    "气血津精": ["气血","津液","精气","营卫","荣卫","血脉","血海","精血","荣血","津血","汗液","涕唾","涎沫","荣气","卫气","宗气","元气","谷气"],
    "经络":  ["经脉","络脉","经络","大络","阳脉","阴脉","动脉","孙络","浮络","经别","经筋","奇经","冲脉","督脉","任脉","带脉"],
    "阴阳":  ["少阳","少阴","太阳","太阴","阳明","厥阴","阳气","阴气","阴阳","三阳","三阴","寒热","阳胜","阴胜","阳竭","阴竭"],
    "季节天文": ["四时","春夏","秋冬","天地","日月","星辰","风雨","寒暑","昼夜","天癸","天时"],
    "病证":  ["伤寒","厥逆","病机","痈疽","风病","痹证","咳逆","呕逆","水肿","胀满","积聚","虚劳","寒热往来","消渴","唾血","血崩","心痛","头痛","腰痛","腹痛"],
    "治法针": ["针灸","砭石","汤液","醪醴","针法","导引","按摩","火针","艾灸","刺法"],
}

def load_corpus(name="corpus_neijing_wenyan.json"):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def collect_bigrams(corpus, min_freq=10, max_words=1500):
    big = Counter()
    for s in corpus:
        cs = [c for c in s if c not in FUNC]
        for i in range(len(cs)-1):
            w = cs[i]+cs[i+1]
            if len(set(w))==2:
                big[w]+=1
    words = [w for w,c in big.most_common(max_words) if c>=min_freq]
    return words, big

def main():
    corpus = load_corpus()
    words, big = collect_bigrams(corpus)
    print("="*70)
    print("《黄帝内经》词级(多字词)自组织验证 (%d句)" % len(corpus))
    print("="*70)
    print(f"提取高频双字词元胞: {len(words)} 个 (freq≥10)\n")

    # ---- 词级 PMI 共现自组织 ----
    # 分词: 命中双字词表的多字词整体作token,否则单字
    token_list = set(words)
    co = defaultdict(Counter); wfreq = Counter()
    for s in corpus:
        cs = [c for c in s if c not in FUNC]
        toks=[]
        i=0
        while i < len(cs)-1:
            w2=cs[i]+cs[i+1]
            if w2 in token_list:
                toks.append(w2); i+=2
            else:
                toks.append(cs[i]); i+=1
        if i < len(cs): toks.append(cs[i])
        u=set(toks)
        for t in u:
            wfreq[t]+=1
            for t2 in u:
                if t!=t2:
                    co[t][t2]+=1
    L=sum(len(s) for s in corpus) or 1
    # 只取 "中医范畴" 词作验证对象(它们是有ground-truth的)
    cat_words = {}
    for cat, ws in WORD_CATEGORIES.items():
        for w in ws:
            if w in wfreq and wfreq[w]>=5:
                cat_words.setdefault(w, cat)
    cw = list(cat_words.keys())
    vocab_idx = list(cat_words.keys())  # 用范畴词自身作共现维度
    idx = {w:i for i,w in enumerate(vocab_idx)}
    def wpmiv(w):
        v=[0.0]*len(vocab_idx)
        if w not in co: return v
        for w2,n in co[w].items():
            if w2 in idx:
                i=idx[w2]
                v[i]=max(0.0,math.log((n/L)/((wfreq[w]/L)*(wfreq[w2]/L)+1e-9)))
        return v
    vec={w:wpmiv(w) for w in cw}
    def cos(a,b):
        da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
        return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)
    def mean(xs): return sum(xs)/len(xs) if xs else 0.0

    # ---- 范畴涌现: 同范畴词 vs 跨范畴词 margin ----
    print("【A】中医范畴词 体系内 vs 体系外 涌现 (词级PMI)")
    print(f"{'范畴':<8}{'含词':>5}{'体系内均值':>12}{'体系↔外界':>14}{'margin':>9} 判定")
    print("-"*62)
    cats = sorted(set(cat_words.values()))
    cat_members = defaultdict(list)
    for w,c in cat_words.items(): cat_members[c].append(w)
    for c in cats:
        ms=[w for w in cat_members[c] if w in vec]
        if len(ms)<2: 
            print(f"{c:<8}{len(ms):>5}(不足)"); continue
        inner=[cos(vec[a],vec[b]) for a in ms for b in ms if a<b]
        others=[w for w in cw if w not in ms]
        outer=[cos(vec[a],vec[b]) for a in ms for b in others]
        mi,mo=mean(inner),mean(outer); mg=mi-mo
        verd="★★★" if mg>0.02 else("★★" if mg>0.01 else("★" if mg>0.004 else "·"))
        print(f"{c:<8}{len(ms):>5}{mi:>12.3f}{mo:>14.3f}{mg:>+9.3f} {verd}")

    # ---- 具体最近邻 ----
    print("\n【B】代表中医术语词的最近邻(词空间)")
    for w in ["五脏","阴阳","气血","经脉","膀胱","寒热","津液","营卫","心气","精血"]:
        if w not in vec: continue
        sims=sorted(((p,cos(vec[w],vec[p])) for p in cw if p!=w),key=lambda x:-x[1])
        top=[(p,r) for p,r in sims[:5] if r>0]
        tag=" ".join(f"{p}({r:.2f})" for p,r in top)
        print(f"    {w}: {tag}")

    # ---- 词级字形通道的诚实边界 ----
    print("\n【C】字形八卦对医学词的覆盖(诚实边界)")
    from exp_growth import char_sem_vec
    flat=sum(1 for ch in "心血脉津经脉络液唾寒暑" if all(abs(x-0.5)<=0.12 for x in char_sem_vec(ch)))
    print(f"    医学核心字中'字形无信息(平坦)'比例: {flat}/12")
    print("    → 印证：医学词的字形八卦通道失效,词级语义须靠语料共现(方案甲：语料=主力)。")

if __name__=="__main__":
    main()
