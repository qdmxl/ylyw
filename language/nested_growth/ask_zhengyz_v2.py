#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ask_zhengyz_v2.py — 可问答辨证系统 v2（病名诊断版）

马老师 2026-08-16 决策：
  - v1 输出太low（感冒发烧打喷嚏判成肝，八纲气血空白）
  - 根因=C：缺"白话映射 + 外感/六经辨证 + 常见病病证"
  - 核心升级：**给出病名**，让用户明白是"风寒"还是"风热"

设计：
  1. 白话→医学术语 映射层（发烧→发热、打喷嚏→喷嚏/鼻塞、流鼻涕→流涕、怕冷→恶寒…）
  2. 病名诊断：成说规则 —— 证候组合 → 病名（源自伤寒论/温病条辨/内经成说）
     例：恶寒+发热+无汗+脉浮紧 → 太阳伤寒(风寒表实)
         发热+恶风+有汗+脉缓 → 太阳中风(风寒表虚/营卫不和)
         发热+咽痛+口渴+脉浮数 → 风热表证
  3. 仍输出 病位+八纲+气血津液 多维（保留v1能力），但以**病名为第一输出**
"""
import json, math, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠的")
Z5 = "心肝脾肺肾"

# ===== 1. 白话→医学术语 映射表（绕不开：用户只说白话） =====
BAIHUA = {
    # 白话词 -> 中医证候词
    "发烧": "发热", "发热": "发热", "低烧": "发热", "高烧": "壮热",
    "打喷嚏": "喷嚏", "喷嚏": "喷嚏", "流鼻涕": "流涕", "流清涕": "流涕",
    "流黄涕": "流黄涕", "鼻塞": "鼻塞", "嗓子痛": "咽痛", "喉咙痛": "咽痛",
    "嗓子干": "咽干", "咽喉痛": "咽痛", "怕冷": "恶寒", "发冷": "恶寒",
    "怕风": "恶风", "受凉": "外感", "感冒": "外感", "伤风": "外感",
    "流汗": "汗出", "出汗多": "汗出", "不出汗": "无汗", "老咳嗽": "咳嗽",
    "没劲": "乏力", "没力气": "乏力", "浑身疼": "身痛", "全身疼": "身痛",
    "骨头疼": "骨节疼痛", "头痛": "头痛", "头胀": "头胀", "头晕": "头晕",
    "睡不着": "失眠", "拉肚子": "泄泻", "肚子疼": "腹痛", "心慌": "心悸",
    "喘不上气": "气促", "想吐": "恶心", "手脚冰凉": "肢冷", "口苦": "口苦",
    "没胃口": "纳呆", "吃不下": "纳呆", "便秘": "便秘", "口干": "口干",
    "口渴": "口渴", "眼睛干": "目干", "腰酸": "腰酸", "腿软": "膝软",
}
def map_baihua(sym):
    """白话→术语：按词表替换，返回映射后证候串 + 命中的映射记录"""
    mapped = sym
    hits = []
    # 优先长词
    for w in sorted(BAIHUA, key=len, reverse=True):
        if w in mapped:
            mapped = mapped.replace(w, BAIHUA[w])
            hits.append(f"{w}→{BAIHUA[w]}")
    return mapped, hits

# ===== 2. 病名诊断：成说规则（源自伤寒论/温病/内经） =====
# 每条: 病名 + 必备证候(AND) + 次要证候(OR, 越多越像) + 说明
DISEASES = [
    dict(name="太阳中风（风寒表虚/营卫不和）", must=["恶风","汗出"],
         ors=["发热","头痛","脉缓","鼻鸣"], desc="伤寒论桂枝汤证：太阳中风，发热汗出恶风脉缓",
         zang="肺", bagang=["表","寒"], qi=[]
    ),
    dict(name="太阳伤寒（风寒表实）", must=["恶寒","发热"],
         ors=["无汗","头痛","身痛","骨节疼痛","喘","脉浮紧"], desc="伤寒论麻黄汤证：太阳伤寒，恶寒发热无汗而喘",
         zang="肺", bagang=["表","寒"], qi=[]
    ),
    dict(name="风热表证（风热犯表）", must=["发热"],
         ors=["咽痛","口渴","黄涕","汗出","脉浮数","头胀"], desc="温病：风热之邪犯卫，发热咽痛口渴",
         zang="肺", bagang=["表","热"], qi=[]
    ),
    dict(name="风温（风热伤卫）", must=["发热","恶风"],
         ors=["自汗","身重","多眠睡","咳嗽"], desc="温病条辨：风温为病，脉浮自汗身重",
         zang="肺", bagang=["表","热"], qi=[]
    ),
    dict(name="暑湿（暑温夹湿）", must=["身热"],
         ors=["口渴","汗出","身重","头昏","胸闷","苔腻"], desc="温病条辨：暑温夹湿，身热身重口渴",
         zang="脾", bagang=["热"], qi=["湿"]
    ),
    dict(name="湿温", must=["身热","身重"],
         ors=["头痛","胸痞","舌苔腻","呕恶"], desc="温病条辨：湿温，身热身重胸痞",
         zang="脾", bagang=[], qi=["湿","痰"]
    ),
    dict(name="秋燥", must=["咽干","咳嗽"],
         ors=["口干","鼻干","舌干","无痰"], desc="温病条辨：秋燥伤肺，咽干咳嗽",
         zang="肺", bagang=[], qi=["津亏"]
    ),
]
# 内科常见病名（非外感，但让用户易懂）
DISEASES_INTERNAL = [
    dict(name="心火亢盛", must=["心烦","失眠"],
         ors=["口舌生疮","小便黄","口渴"], desc="心火亢盛，扰乱神明", zang="心", bagang=["热"], qi=[]
    ),
    dict(name="肝郁气滞", must=["太息","胁痛"],
         ors=["胸闷","情志不畅","易怒","脉弦"], desc="肝失疏泄，气机郁滞", zang="肝", bagang=[], qi=[]
    ),
    dict(name="脾虚湿盛", must=["便溏","腹胀"],
         ors=["水肿","苔腻","乏力","食少"], desc="脾失健运，水湿内停", zang="脾", bagang=["虚"], qi=["湿","水停"]
    ),
    dict(name="痰热壅肺", must=["咳嗽","痰"],
         ors=["痰黄","胸闷","气促","发热","咽痛"], desc="痰热互结，壅滞肺气", zang="肺", bagang=["热"], qi=["痰"]
    ),
    dict(name="肾阴虚", must=["腰膝酸软"],
         ors=["五心烦热","潮热","盗汗","耳鸣","口干"], desc="肾阴亏虚，虚热内生", zang="肾", bagang=["虚","热"], qi=["津亏"]
    ),
    dict(name="心血不足", must=["心悸","失眠"],
         ors=["健忘","面色不华","头晕"], desc="心血不足，心神失养", zang="心", bagang=["虚"], qi=["血虚"]
    ),
]

def diagnose_disease(sym_mapped):
    """基于映射后证候, 匹配病名。返回 (病名, 匹配度, 命中证候)"""
    results = []
    for d in DISEASES + DISEASES_INTERNAL:
        must_hit = all(m in sym_mapped for m in d["must"])
        if not must_hit: continue
        or_hit = [o for o in d["ors"] if o in sym_mapped]
        score = len(or_hit) + 3                        # must全中 + or命中
        # 病名成说强调: 命中越多or越确定
        results.append((score, d))
    results.sort(key=lambda x: -x[0])
    return results

def seg_w(s):
    return [x for x in ''.join(c if c not in FUNC else '|' for c in s).split('|') if x]

def build_feat(sents):
    N=len(sents); docF=Counter(); docZ={z:0 for z in Z5}; coZ=defaultdict(Counter)
    for s in sents:
        for z in Z5:
            if z in s: docZ[z]+=1
        for w in seg_w(s):
            for i in range(len(w)-1):
                b=w[i:i+2]
                if len(set(b))<2: continue
                docF[b]+=1
                for z in Z5:
                    if z in s: coZ[b][z]+=1
    featZ={z:{} for z in Z5}
    for b,ctr in coZ.items():
        for z,c in ctr.items():
            pmi=math.log((c/N)/((docF[b]/N)*(docZ[z]/N)+1e-12))
            if pmi>1.2: featZ[z][b]=pmi
    return featZ

def judge_zang(sym,featZ):
    sc={z:0.0 for z in Z5}
    for z in Z5:
        for v in (f"{z}虚",f"{z}火",f"{z}郁",f"{z}热",f"{z}气",f"{z}血",f"{z}阴",f"{z}瘀",f"{z}湿"):
            if v in sym: sc[z]+=5
        for v in (f"犯{z}",f"壅{z}",f"困{z}"):
            if v in sym: sc[z]+=5
    used=set()
    for w in seg_w(sym):
        for i in range(len(w)-1):
            b=w[i:i+2]
            if len(set(b))<2 or b in used: continue
            used.add(b)
            bz=max(featZ,key=lambda zz:featZ[zz].get(b,0)); sv=featZ[bz].get(b,0)
            if sv>0: sc[bz]+=sv
    return max(sc,key=lambda z:sc[z]) if max(sc.values())>0 else None

if __name__=="__main__":
    sents=[]
    for f in ["corpus_neijing_wenyan.json","corpus_shanghan_wenyan.json","corpus_wenbing_wenyan.json","corpus_bingyuan_wenyan.json"]:
        p=os.path.join(HERE,f)
        if os.path.exists(p): sents+=json.load(open(p,encoding="utf-8"))
    featZ=build_feat(sents)
    print("═"*56)
    print("可问答辨证系统 v2 —— 病名诊断版")
    print("输入白话症状即可 → 输出【病名】+病位+八纲+溯源")
    print("═"*56)
    cases=[
      "感冒发烧打喷嚏流鼻涕", "受凉了发烧怕冷不出汗头痛",
      "感冒发烧嗓子疼流黄鼻涕", "发烧怕风一直出汗",
      "腰酸腿软五心烦热盗汗", "心慌睡不着觉头晕",
      "咳嗽痰黄胸闷气促发热", "吃不下饭肚子胀拉肚子浑身没劲",
    ]
    for c in cases:
        mapped,hits=map_baihua(c)
        ds=diagnose_disease(mapped)
        z=judge_zang(mapped,featZ)
        print(f"\n【症状】{c}")
        if hits: print(f"  白话映射：{'，'.join(hits)}")
        if ds:
            sc,d=ds[0]
            print(f"  ▸ 病名诊断：{d['name']}")
            print(f"     依据：{d['desc']}")
            zang_ok = ("✓" if d['zang']==z else f"✗(实际{z})")
            print(f"     病位：{d['zang']}{zang_ok} 八纲：{' '.join(d['bagang'])} 气血：{' '.join(d['qi'])}")
            if len(ds)>1:
                others=[f"{x[1]['name']}({x[0]})" for x in ds[1:3]]
                print(f"     疑似：{'；'.join(others)}")
        else:
            print(f"  ▸ 未能匹配病名（需补充辨证信息） 病位：{z}")
