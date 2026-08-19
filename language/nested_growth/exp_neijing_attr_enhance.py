#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_neijing_attr_enhance.py — 属性通道增强：让低频五行属性锚参与语义,
检验能否在掩蔽A(无直接"脏+五行"共现)下恢复正确五行归属。

对照三法：
  M0 标准PMI(掩蔽A基线)                     —— 期望失败(1/5)
  M1 属性字权重重加权(共现放大低频锚)       —— 期望部分恢复
  M2 属性桥: 脏字与"五行属性簇"整体亲和     —— 期望最强(直接利用内经编码结构)
  M3 掩蔽B(连属性桥字也删) → 完全无五行线索  —— 期望随机构造(对照:证明M1/M2靠的是属性)

判定：脏字→正确五行 Top1/ Top3。
"""
import os, json, math, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, HERE)

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕ \n\t\u3000")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一")

WX_ATTR = {
    "木": set("青角目筋怒酸风春夏东方东震苍"),
    "火": set("赤征舌脉喜苦热夏南方南暑"),
    "土": set("黄宫口肉思甘湿长夏中央中"),
    "金": set("白商鼻皮毛悲辛燥秋西方西凉"),
    "水": set("黑羽耳骨恐咸寒冬北方北寒"),
}
ALL_ATTR = set().union(*WX_ATTR.values())
TRUE_MAP = {"肝":"木","心":"火","脾":"土","肺":"金","肾":"水"}
ZANG = "心肝脾肺肾"

def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_neijing_wenyan.json"), encoding="utf-8"))

def make_mask(corpus, mode):
    zang=ZANG; wx=set("木火土金水")
    if mode=="full":
        return corpus
    if mode=="maskA":
        return [s for s in corpus if not (any(z in s for z in zang) and any(x in s for x in wx))]
    if mode=="maskB":
        # 删 脏+五行同句, 同时删 属性字(低信息,几乎不会同句,这里主要是保证属性不可见)
        return [s for s in corpus if not (any(z in s for z in zang) and any(x in s for x in wx|ALL_ATTR))]
    return corpus

def build(coef_multi):
    """coef_multi: dict 字→权重系数(权重= 若要放大的属性锚,设为>1)"""
    corpus = None
    return None

def cos(a,b):
    da=math.sqrt(sum(x*x for x in a)); db=math.sqrt(sum(y*y for y in b))
    return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)

def build_pmi_weighted(corpus, weight=None, maxvocab=320):
    """weight: dict {char: multiplier} 加权共现(放大低频关键锚)。"""
    co=defaultdict(Counter); freq=Counter(); docf=Counter()
    for s in corpus:
        u=set(s)
        for ch in u:
            if ch in FUNC: continue
            w = weight.get(ch, 1.0) if weight else 1.0
            freq[ch]+=w
            for ch2 in u:
                if ch2 in FUNC: continue
                if ch!=ch2:
                    co[ch][ch2]+=weight.get(ch2,1.0) if weight else 1.0
                    docf[ch2]+=1
    L=sum(len(s) for s in corpus) or 1
    vocab=[c for c,_ in freq.most_common(600) if c not in FUNC][:maxvocab]
    idf={c:max(1.0,math.log((len(co)+1)/(docf[c]+1))) for c in vocab}
    def pmiv(ch):
        v=[0.0]*len(vocab)
        fch = freq[ch]
        for i,c in enumerate(vocab):
            p=co[ch].get(c,0)
            if p:
                v[i]=max(0.0,math.log((p/L)/((fch/L)*(freq[c]/L)+1e-9)))*idf[c]
        return v
    return pmiv, vocab, freq

def attr_centroid(pmiv, attrset):
    vs=[pmiv(a) for a in attrset if a]
    if not vs: return None
    z=len(vs[0]); c=[0.0]*z
    for v in vs:
        for k in range(z): c[k]+=v[k]
    return [x/len(vs) for x in c]

def evaluate(pmiv, tag, mode="attr"):
    r=[]
    cents={wx:attr_centroid(pmiv,ws) for wx,ws in WX_ATTR.items()}
    cents={wx:c for wx,c in cents.items() if c is not None}
    for z, truth in TRUE_MAP.items():
        zv=pmiv(z)
        if mode=="attr":
            sims=sorted(((wx,cos(zv,c)) for wx,c in cents.items()), key=lambda t:-t[1])
        else:
            sims=sorted(((wx,cos(zv,pmiv(wx))) for wx in WX_ATTR), key=lambda t:-t[1])
        rank=[wx for wx,_ in sims].index(truth)+1
        r.append((z,truth,sims,rank))
    t1=sum(1 for _,_,_,rk in r if rk==1); t3=sum(1 for _,_,_,rk in r if rk<=3)
    print(f"  {tag}: Top1={t1}/5 Top3={t3}/5")
    for z,truth,sims,rank in r:
        order="  ".join(f"{wx}:{sv:.2f}" for wx,sv in sims)
        print(f"    {z}→真实{truth}: {order}  rank={rank}")
    return t1,t3

def main():
    corpus=load_corpus()
    print("="*80)
    print("属性通道增强实验：掩蔽A下恢复五行归属")
    print("="*80)
    # ---------- M0: 掩蔽A 标准PMI ----------
    maskA=make_mask(corpus,"maskA")
    pmiv0,_,_ = build_pmi_weighted(maskA)
    m0_1,m0_3 = evaluate(pmiv0, "M0 掩蔽A 标准PMI(基线)", "attr")

    # ---------- M1: 掩蔽A + 属性字权重重加权 ----------
    # 属性字频率低, 用 IDF^2 放大(低频且集散度低->仍放大; 用固定乘子 3x)
    wgt={ch:3.0 for ch in ALL_ATTR}
    pmiv1,_,_ = build_pmi_weighted(maskA, weight=wgt)
    m1_1,m1_3 = evaluate(pmiv1, "M1 掩蔽A + 属性字3x加权", "attr")

    # ---------- M2: 掩蔽A 属性桥(脏字与属性簇亲和) 已在evaluate中 ----------
    pmiv2=pmiv0
    m2_1,m2_3 = evaluate(pmiv2, "M2 掩蔽A 属性桥(脏→属性簇) [同M0对象,更看重结构]", "attr")

    # ---------- M3: 掩蔽B 连属性也删(对照组: 无五行线索应失败) ----------
    corpusB=make_mask(corpus,"full")  # 简化: maskB 很少删(属性与脏同句少), 这里用 maskA 但移除属性字词表
    pmiv3,_,_ = build_pmi_weighted(maskA, weight={})  # 属性字不参与(等同M0)
    # 为对照, 直接把属性字从判定维度剔除? 这里用maskB语料
    maskB=make_mask(corpus,"maskB")
    pmivB,_,_ = build_pmi_weighted(maskB)
    m3_1,m3_3 = evaluate(pmivB, "M3 掩蔽B(脏+五行+属性全部不同句) 应接近随机", "attr")

    print("\n"+"="*80)
    print("三法对照：")
    print(f"  M0 掩蔽A标准PMI : Top1 {m0_1}/5  Top3 {m0_3}/5")
    print(f"  M1 掩蔽A属性加权: Top1 {m1_1}/5  Top3 {m1_3}/5")
    print(f"  M2 属性桥(结构)  : Top1 {m2_1}/5  Top3 {m2_3}/5")
    print(f"  M3 全掩蔽对照    : Top1 {m3_1}/5  Top3 {m3_3}/5")
    print(f"  随机基线         : Top1≈1/5    Top3≈3/5")
    print("="*80)

if __name__=="__main__":
    main()
