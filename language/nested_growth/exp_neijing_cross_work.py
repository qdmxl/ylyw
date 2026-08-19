#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_cross_work.py — 测试4：跨典籍零样本泛化（内经→伤寒论）

核心问题：用《黄帝内经》训练的脏腑语义指纹,能否零样本理解《伤寒论》的六经辨证？
（内经=上古典籍; 伤寒论=张仲景东汉, 不同作者/表述/侧重, 故为真"跨典籍"）

零样本方法：
  1) 只在《内经》上构建 脏腑字(心肝脾肺肾/胃胆膀胱小肠大肠三焦) PMI 指纹
  2) 对伤寒论每条条文, 用内经词表计算出"句向量", 判它的最近脏腑(top2)
  3) 金标准 = 经典六经归经; 对比 随机基线 与 自训自测上界
"""
import os, json, math, re, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")

ZANG = "心肝脾肺肾胃胆膀胱小肠大肠三焦"
TRUE = {
    "太阳": ["膀胱","小肠"], "阳明": ["胃","大肠"], "少阳": ["胆","三焦"],
    "太阴": ["脾"], "少阴": ["肾","心"], "厥阴": ["肝"],
}

def load_corpus(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def build_pmi(corpus, maxvocab=320):
    co=defaultdict(Counter); freq=Counter(); docf=Counter()
    for s in corpus:
        u=set(s)
        for ch in u:
            if ch in FUNC: continue
            freq[ch]+=1
            for ch2 in u:
                if ch2 in FUNC: continue
                if ch!=ch2: co[ch][ch2]+=1; docf[ch2]+=1
    L=sum(len(s) for s in corpus) or 1
    vocab=[c for c,_ in freq.most_common(600) if c not in FUNC][:maxvocab]
    idf={c:max(1.0,math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v=[0.0]*len(vocab); fch=freq[ch]
        for i,c in enumerate(vocab):
            p=co[ch].get(c,0)
            if p: v[i]=max(0.0,math.log((p/L)/((fch/L)*(freq[c]/L)+1e-9)))*idf[c]
        return v
    return pmiv, vocab

def cos(a,b):
    da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
    return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)

def parse_shanghan():
    t=open(os.path.join(HERE,"伤寒论_原文.txt"),encoding="utf-8",errors="ignore").read()
    t=re.sub(r'<[^>]+>','',t)
    t='\n'.join(l.strip() for l in t.split('\n') if l.strip() and not re.match(r'^(书名|作者|朝代|年份)',l.strip()) and l.strip()!='目录')
    t=re.sub(r'属性：?','',t); t=re.sub(r'\s+','',t); t=t.replace('∶','：')
    items=[x for x in re.split(r'(?<=\d)．|(?<=\d)\.', t) if len(x)>10]
    groups=defaultdict(list)
    for it in items:
        m=re.match(r'^(太阳|阳明|少阳|太阴|少阴|厥阴)',it)
        if m: groups[m.group(1)].append(it)
    return groups, items

def sentence_sim(s, pmiv, vocab, cache):
    """句向量(内经词表解读) 与 各脏腑向量 的相似度; 返回 {脏腑:sim}"""
    v=[0.0]*len(vocab); used=0
    for ch in set(s):
        if ch in FUNC: continue
        if ch not in cache:
            try: cache[ch]=pmiv(ch)
            except Exception: cache[ch]=None
        tv=cache[ch]
        if tv:
            for k in range(len(v)): v[k]+=tv[k]
            used+=1
    if not used: return None
    norm=math.sqrt(sum(x*x for x in v)) or 1
    vs=[x/norm for x in v]
    return {z: cos(vs, pmiv(z)) for z in ZANG}

def main():
    neijing=load_corpus("corpus_neijing_wenyan.json")
    groups, all_items = parse_shanghan()
    print("="*74)
    print("测试4：跨典籍零样本泛化（《黄帝内经》→《伤寒论》）")
    print("="*74)
    print(f"内经训练 {len(neijing)}句 | 伤寒论条文 {len(all_items)}条")
    pmiv, vocab = build_pmi(neijing)
    cache={}

    used_groups={g:ss for g,ss in groups.items() if len(ss)>=3}
    print("\n【零样本归经】(内经指纹解读伤寒条文,top2判脏腑)")
    total=0; correct=0
    print(f"{'六经':<6}{'条文':>5}{'命中':>6}{'正确率':>9}  真实归经")
    per={}
    for mer, ss in used_groups.items():
        truth=TRUE[mer]; hit=0
        for s in ss:
            sims=sentence_sim(s, pmiv, vocab, cache)
            if sims is None: continue
            top2=sorted(sims, key=lambda k:-sims[k])[:2]
            if any(p in truth for p in top2): hit+=1
            total+=1
        acc=hit/len(ss)
        per[mer]=(hit,len(ss))
        correct+=hit
        print(f"{mer:<6}{len(ss):>5}{hit:>6}{acc*100:>8.0f}%  {'/'.join(truth)}")
    print(f"\n  → 零样本总体: {correct}/{total} = {correct/total*100:.0f}%")

    # 随机基线
    rnd=random.Random(0)
    r_hit=0
    for mer, ss in used_groups.items():
        truth=TRUE[mer]
        for s in ss:
            p=rnd.sample(list(ZANG),2)
            if any(x in truth for x in p): r_hit+=1
    print(f"  随机基线(top2 from 11脏腑): {r_hit}/{total} = {r_hit/total*100:.0f}%")

    # 上界: 伤寒自训
    print("\n【上界对照: 伤寒论自训自测】(非严格,句含目标脏腑字即中)")
    pmiv_sh, _ = build_pmi(all_items)
    hl=0
    for mer, ss in used_groups.items():
        truth=TRUE[mer]
        for s in ss:
            if any(z in s for z in truth): hl+=1
    print(f"  句内直含脏腑字命中: {hl}/{total} = {hl/total*100:.0f}%")

    print("\n"+"="*74)
    print("结论判定: 零样本正确率 vs 随机基线(2/11≈18%)。")
    print("若显著高于基线 → 内经语义体系成功跨典籍泛化到伤寒论。")

if __name__=="__main__":
    main()
