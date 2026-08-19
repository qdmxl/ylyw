#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_bianzheng_v3.py — 统一辨证判别器 v3（一期：病位+八纲+气血津液 一体）

v2诊断（2026-08-16）：用**单字核心字**（心/实/虚…）的PMI伴随词学特征，
被多义噪声污染（"心"作中心/人心、"实"作副词、"热"作温热）→ 特征漂移。
v3修正：
  - 病位：直接复用 v6 词级PMI归脏（证候双字词→脏，已验证10/10），不重新学。
  - 八纲/气血：用**成说证候种子**（中医辨证标签本质=一组证候）作先验锚点，
    再经语料**词共现扩展**同义词，双通道判别——符合方案甲"成说先验+语料自组织"。
"""
import json, math, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠")

Z5 = "心肝脾肺肾"
# 八纲/气血津液：成说证候种子（方案甲"成说先验"；中医辨证标签=证候组合）
SEEDS = {
    "寒": ["恶寒","畏寒","肢冷","喜温","面白","寒凝","冷"],
    "热": ["发热","潮热","烦热","口渴","面赤","喜冷","烦渴","热盛"],
    "虚": ["虚弱","亏虚","不足","气短","乏力","倦怠","自汗","消瘦"],
    "实": ["实热","实邪","坚满","痞硬","胀满","结实","积滞"],
    "气虚": ["气短","乏力","懒言","倦怠","自汗","少气","脉弱"],
    "血虚": ["血虚","面白","唇淡","眩晕","心悸","脉细","失血"],
    "血瘀": ["瘀血","刺痛","紫暗","瘀斑","脉涩","固定痛","血瘀"],
    "痰": ["咳痰","痰多","痰鸣","苔腻","头重","胸闷","痰饮"],
    "湿": ["苔腻","身重","困重","便溏","头重","湿盛","水肿"],
    "水停": ["水肿","浮肿","腹水","尿少","小便不利","水泛"],
    "津亏": ["口干","咽干","口渴","舌干","津伤","便干","皮肤干"],
}

def load():
    sents=[]
    for f in ["corpus_neijing_wenyan.json","corpus_nannjing_wenyan.json","corpus_shanghan_wenyan.json",
        "corpus_jinkui_wenyan.json","corpus_bencao_wenyan.json","corpus_maijing_wenyan.json",
        "corpus_zhenjiu_jia_wenyan.json","corpus_zhenjiu_da_wenyan.json","corpus_zhongcang_wenyan.json",
        "corpus_danxi_wenyan.json","corpus_bingyuan_wenyan.json","corpus_piwei_wenyan.json",
        "corpus_wenbing_wenyan.json"]:
        p=os.path.join(HERE,f)
        if os.path.exists(p): sents+=json.load(open(p,encoding="utf-8"))
    return sents

def seg_w(s):
    s=[c if c not in FUNC else '|' for c in s]
    return [x for x in ''.join(s).split('|') if x]

def build(sents):
    N=len(sents)
    docF=Counter(); docZ={z:0 for z in Z5}
    coZ=defaultdict(Counter)              # 病位：证候词→脏
    docS=Counter(); coS=defaultdict(Counter) # 八纲/气血：证候词→标签(用种子词出现代表标签)
    taglist=list(SEEDS)
    for s in sents:
        for z in Z5:
            if z in s: docZ[z]+=1
        pres=set()
        for tag,seeds in SEEDS.items():
            for sd in seeds:
                if sd in s:
                    pres.add(tag); break
        for t in pres: docS[t]+=1
        for w in seg_w(s):
            for i in range(len(w)-1):
                big=w[i:i+2]
                if len(set(big))<2: continue
                docF[big]+=1
                for z in Z5:
                    if z in s: coZ[big][z]+=1
                for t in pres:
                    coS[big][t]+=1
    # 病位特征（v6思路）：证候词→脏
    featZ={z:{} for z in Z5}
    for w,ctr in coZ.items():
        for z,c in ctr.items():
            pmi=math.log((c/N)/((docF[w]/N)*(docZ[z]/N)+1e-12))
            if pmi>1.5: featZ[z][w]=pmi
    # 八纲/气血特征：证候词→标签
    featS={t:{} for t in taglist}
    for w,ctr in coS.items():
        for t,c in ctr.items():
            pmi=math.log((c/N)/((docF[w]/N)*(docS[t]/N)+1e-12))
            if pmi>1.5: featS[t][w]=pmi
    return N,featZ,featS

def judge(sym,featZ,featS,N):
    z=Counter(); bag=Counter(); qi=Counter(); used=set()
    for w in set(seg_w(sym)):
        for i in range(len(w)-1):
            big=w[i:i+2]
            if len(set(big))<2 or big in used: continue
            used.add(big)
            bz=max(featZ,key=lambda zz:featZ[zz].get(big,0)) if featZ else None
            bs=featZ[bz].get(big,0) if bz else 0
            if bs>0: z[bz]+=bs
            for t in featS:
                sc=featS[t].get(big,0)
                if sc<=0: continue
                if t in ("寒","热","虚","实"): bag[t]+=sc
                else: qi[t]+=sc
    out={}
    if z and max(z.values())>0: out["病位"]=max(z,key=lambda zz:z[zz])
    bp=[]
    for a,b in [("寒","热"),("虚","实")]:
        sa,sb=bag[a],bag[b]
        if max(sa,sb)>0: bp.append(a if sa>=sb else b)
    if bp: out["八纲"]=bp
    qq=[t for t,s in qi.items() if s>0]
    if qq: out["气血津液"]=sorted(qq,key=lambda t:-qi[t])[:4]
    return out

if __name__=="__main__":
    sents=load(); print(f"训练:{len(sents)}句")
    N,featZ,featS=build(sents)
    print("=== 八纲/气血 涌现特征(证候→标签) ===")
    for t in list(SEEDS):
        print(f"  {t}: "+",".join(list(featS[t])[:8]))
    tests=[
      ("病位心·热·津亏","心火亢盛，心烦失眠，口舌生疮，小便黄，口渴咽干"),
      ("病位肝·实","肝郁气滞，胁肋胀痛，善太息，情志抑郁"),
      ("病位脾·虚·气虚","脾气虚，食少腹胀，倦怠乏力，便溏"),
      ("病位肺·寒","风寒犯肺，咳嗽痰白，恶寒发热，鼻塞"),
      ("病位肾·虚·津亏","肾阴虚，腰膝酸软，五心烦热，潮热盗汗"),
      ("病位肝·血瘀","肝血瘀滞，胁下刺痛，痛处固定，舌紫暗"),
      ("病位脾·湿·水停","脾虚湿盛，全身浮肿，腹胀，小便不利，苔腻"),
      ("病位肺·痰·热","痰热壅肺，咳嗽痰黄，胸闷气促，发热"),
    ]
    print("\n=== 统一辨证判别 v3 ===")
    correct=0
    for gold,sym in tests:
        r=judge(sym,featZ,featS,N)
        gz=gold.split("·")[1].replace("病位","")
        hz="✓" if r.get("病位","?")==gz else "✗"
        if hz=="✓":correct+=1
        print(f"  [{gold}] «{sym}»\n      → {r}")
    print(f"\n病位正确: {correct}/{len(tests)}")
