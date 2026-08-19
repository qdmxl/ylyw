#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_bianzheng_v2.py — 统一辨证判别器 v2（一期：病位+八纲+气血津液 一体）

v1诊断（2026-08-16）：
  病位学到的特征是"词含脏字"(心痛/肝气/肺气)PMI虚高，而非真证候词，
  导致"肝郁""痰热壅肺"等真实证候没被识别 → 病位漂移。
  修正：病位复用已验证的词级归脏（v6 10/10思路，证候词→脏，不含脏字）；
        八纲/气血津液用"证候词PMI"按维度并出多标签。

设计（"内在联系不割裂"）：
  同一句 → 病位(五选一) + 八纲(寒/热/虚/实可并) + 气血津液(气/血/痰/湿/水/津可并)
"""
import json, math, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠")

TRAIN = ["corpus_neijing_wenyan.json","corpus_nannjing_wenyan.json","corpus_shanghan_wenyan.json",
    "corpus_jinkui_wenyan.json","corpus_bencao_wenyan.json","corpus_maijing_wenyan.json",
    "corpus_zhenjiu_jia_wenyan.json","corpus_zhenjiu_da_wenyan.json","corpus_zhongcang_wenyan.json",
    "corpus_danxi_wenyan.json","corpus_bingyuan_wenyan.json","corpus_piwei_wenyan.json",
    "corpus_wenbing_wenyan.json"]

Z5 = "心肝脾肺肾"
# 八纲/气血 标签核心字（用于学证候特征）
BAGANG = {"寒":"寒","热":"热","虚":"虚","实":"实"}
QI = {"气虚":"气","血虚":"血","血瘀":"瘀","痰":"痰","湿":"湿","水停":"水","津亏":"津"}
# "实"在古籍常作非辨证义（充实/实际），用代表性证候字锚定：实→ 痞/满/胀/实热/实邪
BAGANG_FIX = {"实": ["实热","实邪","实满","痞","坚满"] }

def load():
    sents=[]
    for f in TRAIN:
        p=os.path.join(HERE,f)
        if os.path.exists(p): sents+=json.load(open(p,encoding="utf-8"))
    return sents

def seg_w(s):
    s=[c if c not in FUNC else '|' for c in s]
    return [x for x in ''.join(s).split('|') if x]

def build(sents):
    N=len(sents)
    docF=Counter(); docC={z:0 for z in Z5}
    for s in sents:
        for z in Z5:
            if z in s: docC[z]+=1
    # 病位: 证候双字词 w; 八纲/气血: 证候双字词 → 核心字 共现
    coZ=defaultdict(Counter)   # 病位: 词→脏
    core_all=set("寒热虚实气血瘀痰湿水津")
    docC2={c:0 for c in core_all}
    coQ=defaultdict(Counter)   # 八纲/气血: 词→核心字
    for s in sents:
        pres=set(c for c in core_all if c in s)
        for c in pres: docC2[c]+=1
        for w in seg_w(s):
            for i in range(len(w)-1):
                big=w[i:i+2]
                if len(set(big))<2:continue
                docF[big]+=1
                for z in Z5:
                    if z in s: coZ[big][z]+=1
                for c in pres:
                    coQ[big][c]+=1
    # 病位特征: 词→脏 PMI (不含脏字的证候词, 已有v6验证)
    featZ={z:{} for z in Z5}
    for w,ctr in coZ.items():
        for z,c in ctr.items():
            if c==0 or docF[w]==0:continue
            pmi=math.log((c/N)/((docF[w]/N)*(docC[z]/N)+1e-12))
            if pmi>2: featZ[z][w]=pmi
    # 八纲/气血特征
    featQ={tag:{} for tag in list(BAGANG)+list(QI)}
    for tag,core in list(BAGANG.items())+list(QI.items()):
        for w,ctr in coQ.items():
            c=ctr.get(core,0)
            if c==0:continue
            if core=="实":  # 多义补救
                if not any(k in w for k in ("实热","实邪","实满","痞","坚")):continue
            pmi=math.log((c/N)/((docF[w]/N)*(docC2[core]/N)+1e-12))
            if pmi>2: featQ[tag][w]=pmi
    return N,featZ,featQ

def judge(sym,featZ,featQ,N):
    zang=Counter(); bag={t:0.0 for t in BAGANG}; qi={t:0.0 for t in QI}
    used=set()
    for w in set(seg_w(sym)):
        for i in range(len(w)-1):
            big=w[i:i+2]
            if len(set(big))<2 or big in used:continue
            used.add(big)
            # 病位
            bz=None;bs=-1e9
            for z in Z5:
                sc=featZ[z].get(big,0)
                if sc>bs:bs=sc;bz=z
            if bz and bs>0: zang[bz]+=bs
            # 八纲
            for t in BAGANG:
                sc=featQ[t].get(big,0)
                if sc>0: bag[t]+=sc
            # 气血
            for t in QI:
                sc=featQ[t].get(big,0)
                if sc>0: qi[t]+=sc
    out={}
    if zang and max(zang.values())>0:
        out["病位"]=max(zang,key=lambda z:zang[z])
    bp=[]
    for a,b in [("寒","热"),("虚","实")]:
        sa,sb=bag[a],bag[b]
        if max(sa,sb)>0: bp.append(a if sa>=sb else b)
    if bp:out["八纲"]=bp
    qq=[t for t,s in qi.items() if s>0]
    if qq:out["气血津液"]=sorted(qq,key=lambda t:-qi[t])[:4]
    return out

if __name__=="__main__":
    sents=load()
    print(f"训练:{len(sents)}句")
    N,featZ,featQ=build(sents)
    print("=== 病位特征词(v6思路,证候→脏) ===")
    for z in Z5:
        print(f"  {z}: "+",".join(list(featZ[z])[:8]))
    print("\n=== 八纲/气血特征词 ===")
    for t in list(BAGANG)+list(QI):
        print(f"  {t}: "+",".join(list(featQ[t])[:8]))
    tests=[
      ("心火·热·津亏","心火亢盛，心烦失眠，口舌生疮，小便黄，口渴咽干"),
      ("肝郁·实","肝郁气滞，胁肋胀痛，善太息，情志抑郁"),
      ("脾虚·气虚","脾气虚，食少腹胀，倦怠乏力，便溏"),
      ("风寒犯肺·寒","风寒犯肺，咳嗽痰白，恶寒发热，鼻塞"),
      ("肾阴虚·虚·津亏","肾阴虚，腰膝酸软，五心烦热，潮热盗汗"),
      ("肝血瘀·血瘀","肝血瘀滞，胁下刺痛，痛处固定，舌紫暗"),
      ("脾虚湿盛·湿·水停","脾虚湿盛，全身浮肿，腹胀，小便不利，苔腻"),
      ("痰热壅肺·痰·热","痰热壅肺，咳嗽痰黄，胸闷气促，发热"),
    ]
    print("\n=== 统一辨证判别 v2 ===")
    for gold,sym in tests:
        r=judge(sym,featZ,featQ,N)
        print(f"  [{gold}] «{sym}»\n      → 病位:{r.get('病位','?')} 八纲:{''.join(r.get('八纲',[]))} 气血:{' '.join(r.get('气血津液',[]))}")
