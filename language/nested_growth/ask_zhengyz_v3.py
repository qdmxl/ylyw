#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ask_zhengyz_v3.py — 可问答辨证系统 v3（涌现判断 + 成说对译）

马老师 2026-08-16 决策（推翻v2手写规则，恢复YLYW涌现）：
  1. 病名判断**不靠手写规则**，靠**语料涌现**：证候词与病名锚的共现分布
  2. 病名标签**用成说**（源于古籍成说/教材对应，非我的发明）
  3. 白话映射表保留为**成说先验通道**（用户口语→术语的词汇桥，方案甲允许）
  4. 病名分两层：涌现层(古籍成说病名) + 对译层(现代常用病名)

双通道（方案甲）：
  - 通道1 语料涌现：病名锚的证候分布向量 由语料共现自动学（恶寒+无汗+脉紧→风寒）
  - 通道2 成说先验：白话映射表 + 古籍病名→现代病名对译表（教材成说）

判别：输入症状 → 白话映射 → 提取证候词 → 与各病名锚向量加和打分 → 取最高古籍病名
      → 成说对译成现代病名，一并输出 病位/八纲/气血津液(保留v1能力)
"""
import json, math, os, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠的")

Z5 = "心肝脾肺肾"

# ===== 成说先验通道 =====
# 1. 白话→医学术语 映射表（词汇桥，非病名判断）
BAIHUA = {
    "发高烧":"壮热","发烧":"发热","低烧":"发热","高烧":"壮热","打喷嚏":"喷嚏","流黄鼻涕":"流黄涕",
    "流清鼻涕":"清涕","流鼻涕":"流涕","流清涕":"清涕","感冒":"外感","受凉":"外感","伤风":"外感",
    "嗓子痛":"咽痛","喉咙痛":"咽痛","咽喉痛":"咽痛","嗓子干":"咽干","怕冷":"恶寒","发冷":"恶寒",
    "怕风":"恶风","不出汗":"无汗","出汗多":"汗出","流汗":"汗出","老咳嗽":"咳嗽","没劲":"乏力",
    "没力气":"乏力","浑身疼":"身痛","全身疼":"身痛","骨头疼":"骨节","腰酸":"腰酸","腿软":"膝软",
    "睡不着":"失眠","心慌":"心悸","拉肚子":"泄泻","肚子疼":"腹痛","喘不上气":"气促","想吐":"恶心",
    "手脚冰凉":"肢冷","口苦":"口苦","没胃口":"纳呆","吃不下":"纳呆","便秘":"便秘","口干":"口干",
    "口渴":"口渴","头晕":"头晕","头痛":"头痛","鼻子堵":"鼻塞","鼻塞":"鼻塞",
}
# 2. 古籍病名 → 现代病名 对译表（教材成说）
TRANSLATE = {
    "太阳伤寒":"风寒感冒（表实）","太阳中风":"风寒感冒（表虚）","风温":"风热感冒（或风温病）",
    "风热":"风热感冒","风寒":"风寒感冒","暑温":"暑湿感冒","湿温":"湿温病（暑湿夹湿）",
    "秋燥":"秋燥感冒","温病":"温病","中寒":"中寒",
}

# ===== 语料涌现通道：病名锚 + 证候词典（成说证候词，非随机切分） =====
SYM = ["恶寒","发热","无汗","汗出","身痛","骨节","头痛","咽痛","口渴","咳嗽","鼻塞","喷嚏",
       "脉浮","脉数","脉紧","脉缓","苔腻","身重","胸痞","下利","面赤","心烦","眩晕","肢冷","自汗","喘"]
# 病名锚（成说高概念标签；证候向量由语料涌现）
ANCHORS = ["风寒","风热","太阳中风","太阳伤寒","风温","暑温","湿温","秋燥"]

def seg_w(s):
    return [x for x in ''.join(c if c not in FUNC else '|' for c in s).split('|') if x]

def load():
    sents = []
    for f in ["corpus_shanghan_wenyan.json","corpus_wenbing_wenyan.json","corpus_neijing_wenyan.json",
              "corpus_jinkui_wenyan.json","corpus_bingyuan_wenyan.json","corpus_danxi_wenyan.json",
              "corpus_piwei_wenyan.json"]:
        p = os.path.join(HERE, f)
        if os.path.exists(p): sents += json.load(open(p, encoding="utf-8"))
    return sents

def docf(sents, w):
    return sum(1 for s in sents if w in s)

def build_anchor_vectors(sents):
    N = len(sents)
    da = {a: docf(sents, a) for a in ANCHORS}
    VEC = {}
    for a in ANCHORS:
        cnt = Counter()
        for s in sents:
            if a not in s: continue
            for w in SYM:
                if w in s: cnt[w] += 1
        vec = {}
        for w, c in cnt.items():
            if c < 2: continue
            pmi = math.log((c/N)/((docf(sents,w)/N)*(da[a]/N)+1e-12))
            if pmi > 0.6: vec[w] = round(pmi, 3)
        VEC[a] = vec
    return VEC

def build_feat_zang(sents):
    N = len(sents); docZ = {z:0 for z in Z5}; docF=Counter(); coZ=defaultdict(Counter)
    for s in sents:
        for z in Z5:
            if z in s: docZ[z]+=1
        for b in seg_w(s):
            for i in range(len(b)-1):
                x=b[i:i+2]
                if len(set(x))<2:continue
                docF[x]+=1
                for z in Z5:
                    if z in s: coZ[x][z]+=1
    feat={z:{} for z in Z5}
    for x,ctr in coZ.items():
        for z,c in ctr.items():
            pmi=math.log((c/N)/((docF[x]/N)*(docZ[z]/N)+1e-12))
            if pmi>1.2: feat[z][x]=pmi
    return feat

def map_baihua(sym):
    m=sym
    for w in sorted(BAIHUA,key=len,reverse=True):
        if w in m: m=m.replace(w,BAIHUA[w])
    return m

def extract_sym(mapped):
    return [w for w in SYM if w in mapped]

def judge_disease(sym_terms, VEC):
    scores={}
    for a,vec in VEC.items():
        sc=0
        for t in sym_terms:
            if t in vec: sc+=vec[t]
        scores[a]=round(sc,2)
    return sorted(scores.items(), key=lambda x:-x[1])

def judge_zang(sym, feat):
    sc={z:0.0 for z in Z5}
    for z in Z5:
        for v in (f"{z}虚",f"{z}火",f"{z}郁",f"{z}热",f"{z}气",f"{z}血",f"{z}阴",f"{z}瘀",f"{z}湿"):
            if v in sym: sc[z]+=5
        for v in (f"犯{z}",f"壅{z}",f"困{z}"):
            if v in sym: sc[z]+=5
    used=set()
    for b in seg_w(sym):
        for i in range(len(b)-1):
            x=b[i:i+2]
            if len(set(x))<2 or x in used:continue
            used.add(x)
            bz=max(feat,key=lambda zz:feat[zz].get(x,0)); sv=feat[bz].get(x,0)
            if sv>0: sc[bz]+=sv
    return max(sc,key=lambda z:sc[z]) if max(sc.values())>0 else None

def render(sym, VEC, feat, verbose=True):
    mapped=map_baihua(sym)
    terms=extract_sym(mapped)
    result=None
    if terms:
        result=judge_disease(terms,VEC)
    zang=judge_zang(mapped,feat)
    print("═"*56)
    print(f"【症状】{sym}")
    if mapped!=sym: print(f"  白话映射→{mapped}")
    top=result[0] if result and result[0][1]>0 else None
    if top:
        gubing,score=top
        modern=TRANSLATE.get(gubing,gubing)
        print(f"  病名诊断（古籍成说）：{gubing}  (得分{score})")
        print(f"  现代名称：{modern}")
        others=[f"{TRANSLATE.get(a,a)}({s})" for a,s in result[1:4] if s>0]
        if others: print(f"  疑似：{'、'.join(others)}")
    else:
        print("  病名诊断：未能明确（症状信息不足，需补充）")
    print(f"  病位倾向：{zang or '未判'}  辨识证候：{','.join(terms) if terms else '—'}")
    if verbose and top:
        gubing,_=top
        hits=[t for t in terms if t in VEC[gubing]]
        if hits: print(f"  归因：{gubing}因「{','.join(hits)}」得分（语料涌现）")
    print()

if __name__=="__main__":
    sents=load()
    print(f"语料:{len(sents)}句（可增量喂书重训）")
    VEC=build_anchor_vectors(sents)
    feat=build_feat_zang(sents)
    print("=== 病名锚 涌现证候向量 ===")
    for a in ANCHORS:
        v=sorted(VEC[a],key=lambda k:-VEC[a][k])[:8]
        print(f"  {a}: "+",".join(f"{k}({VEC[a][k]})" for k in v))
    print()
    print("可问答辨证系统 v3 —— 涌现判断+成说对译")
    print("输入白话症状即可。q退出\n")
    while True:
        try: sym=input("症状> ").strip()
        except EOFError: break
        if not sym: continue
        if sym.lower() in ("q","quit"): break
        render(sym,VEC,feat)
