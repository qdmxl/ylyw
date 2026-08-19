#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_bianzheng_v4.py — 统一辨证判别器 v4（方向A：病位涌现 + 八纲/气血成说）

方法学认知（马老师 2026-08-16 确认）：
  语义引擎能力有限——并非所有中医维度都能"分布涌现"。
  - 病位/脏腑/脏象网络：可分布涌现（v6 10/10 已验证）
  - 八纲/气血津液：本质是"证候类型学"概念，靠内经/教材成说定义，
    不应强求从分布统计自发长出 → 用"成说模板 + 词级相似"务实匹配（方向A）。

本版 = 双通道合一（方案甲思想的落点）：
  病位          ：词级PMI涌现（v6 训练，证候双字词→脏）
  八纲/气血津液  ：成说模板（证候种子） + 语料词共现扩展（synonym）相似度打分
"""
import json, math, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠")

Z5 = "心肝脾肺肾"

# ========== 成说模板（八纲/气血津液）—— 方向A：成说先验 ==========
# 每个标签 = 一组证候种子（古籍/内经成说），判别命中种子即点亮
TEMPLATE = {
    "寒": ["恶寒","畏寒","肢冷","喜温","面白","寒凝","清冷","得温则减","寒痛"],
    "热": ["发热","潮热","烦热","口渴","面赤","喜冷","烦渴","身热","热痛","脉数"],
    "虚": ["虚弱","亏虚","不足","气短","乏力","倦怠","自汗","消瘦","脉细","脉弱","无力"],
    "实": ["实热","实邪","坚满","痞硬","胀满","结实","积滞","拒按","脉实"],
    "气虚": ["气短","乏力","懒言","倦怠","自汗","少气","脉弱","动则尤甚"],
    "血虚": ["血虚","面白","唇淡","眩晕","心悸","失眠","脉细","失血","爪淡"],
    "血瘀": ["瘀血","刺痛","紫暗","瘀斑","脉涩","固定痛","舌紫","血瘀"],
    "痰": ["咳痰","痰多","痰鸣","苔腻","头重","胸闷","痰饮","吐痰","白痰","黄痰"],
    "湿": ["苔腻","身重","困重","便溏","头重","湿盛","水肿","肢体困倦","胸脘痞闷"],
    "水停": ["水肿","浮肿","腹水","尿少","小便不利","水泛","水胀"],
    "津亏": ["口干","咽干","口渴","舌干","津伤","便干","皮肤干","唇燥","唇裂"],
}

def seg_w(s):
    s=[c if c not in FUNC else '|' for c in s]
    return [x for x in ''.join(s).split('|') if x]

def seg_bigram(s):
    out=[]
    for w in seg_w(s):
        for i in range(len(w)-1):
            b=w[i:i+2]
            if len(set(b))>=2: out.append(b)
    return out

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

def build(sents):
    N=len(sents)
    docF=Counter(); docZ={z:0 for z in Z5}; coZ=defaultdict(Counter)
    for s in sents:
        for z in Z5:
            if z in s: docZ[z]+=1
        for b in seg_bigram(s):
            docF[b]+=1
            for z in Z5:
                if z in s: coZ[b][z]+=1
    featZ={z:{} for z in Z5}
    for b,ctr in coZ.items():
        for z,c in ctr.items():
            pmi=math.log((c/N)/((docF[b]/N)*(docZ[z]/N)+1e-12))
            if pmi>1.5: featZ[z][b]=pmi
    return featZ

# ===== 八纲/气血：成说模板直接匹配（含 词内含证候字 的宽松命中） =====
def judge_bagang_qi(sym):
    """返回 {八纲:[..], 气血津液:[..]} 通过模板种子在句中命中"""
    bag={}; qi={}
    for t,seeds in TEMPLATE.items():
        hit=[sd for sd in seeds if sd in sym]
        # 宽松: 单字种子也可匹配（如"渴"命中热/津亏）
        if not hit:
            for sd in seeds:
                if any(ch in sym for ch in sd): hit=[sd];break
        score=len(hit)
        if score>0:
            if t in ("寒","热","虚","实"): bag[t]=score
            else: qi[t]=score
    # 八纲内 寒/热 互斥取强，虚/实 互斥取强
    out={}
    bp=[]
    for a,b in [("寒","热"),("虚","实")]:
        sa,sb=bag.get(a,0),bag.get(b,0)
        if max(sa,sb)>0: bp.append(a if sa>=sb else b)
    if bp: out["八纲"]=bp
    qq=[t for t,s in qi.items() if s>0]
    if qq: out["气血津液"]=sorted(qq,key=lambda t:-qi[t])[:5]
    return out

def judge_zang(sym, featZ):
    """病位：①含脏字的证候词=强证据(心火/肝郁/脾虚/犯肺/壅肺/困脾…) ②无脏字证候词用PMI"""
    sc = {z: 0.0 for z in Z5}
    verbz = {z: (f"{z}虚", f"{z}火", f"{z}郁", f"{z}热", f"{z}气", f"{z}血", f"{z}阴",
                f"{z}阳虚", f"{z}阴虚", f"{z}瘀", f"{z}湿", f"{z}经", f"{z}病")
          for z in Z5}
    # 含脏证候词强证据
    for z in Z5:
        if any(v in sym for v in verbz[z]):
            sc[z] += 5.0
        if f"犯{z}" in sym or f"壅{z}" in sym or f"困{z}" in sym or f"伤{z}" in sym or f"及{z}" in sym:
            sc[z] += 5.0
        if f"{z}经" in sym or f"{z}火" in sym:  # 肝经/心火 等也被列为强证候词
            sc[z] += 3.0
    # 无脏字证候词 PMI 补充
    used = set()
    for w in seg_w(sym):
        for i in range(len(w)-1):
            b = w[i:i+2]
            if len(set(b)) < 2 or b in used: continue
            used.add(b)
            bz = max(featZ, key=lambda zz: featZ[zz].get(b, 0))
            sv = featZ[bz].get(b, 0)
            if sv > 0: sc[bz] += sv
    return max(sc, key=lambda z: sc[z]) if max(sc.values()) > 0 else None

if __name__=="__main__":
    sents=load(); print(f"训练:{len(sents)}句")
    featZ=build(sents)
    tests=[
      ("心火·热·津亏","心火亢盛，心烦失眠，口舌生疮，小便黄，口渴咽干"),
      ("肝郁·实","肝郁气滞，胁肋胀痛，善太息，情志抑郁"),
      ("脾虚·虚·气虚","脾气虚，食少腹胀，倦怠乏力，便溏"),
      ("风寒犯肺·寒","风寒犯肺，咳嗽痰白，恶寒发热，鼻塞"),
      ("肾阴虚·虚·津亏","肾阴虚，腰膝酸软，五心烦热，潮热盗汗"),
      ("肝血瘀·血瘀","肝血瘀滞，胁下刺痛，痛处固定，舌紫暗"),
      ("脾虚湿盛·湿·水停","脾虚湿盛，全身浮肿，腹胀，小便不利，苔腻"),
      ("痰热壅肺·痰·热","痰热壅肺，咳嗽痰黄，胸闷气促，发热"),
      ("寒湿困脾·寒·湿","寒湿困脾，脘腹胀满，头身困重，大便溏泄，苔白腻"),
      ("气血两虚·虚·气虚·血虚","气血两虚，面色淡白，神疲乏力，头晕心悸，脉细弱"),
    ]
    print("\n=== 统一辨证判别 v4（方向A：病位涌现 + 八纲/气血成说） ===")
    zok=0
    for gold,sym in tests:
        z=judge_zang(sym,featZ)
        bq=judge_bagang_qi(sym)
        # 金标准: 病位=标签里第一个脏字(心/肝/脾/肺/肾)
        gz=[c for c in "心肝脾肺肾" if c in gold]
        gz=gz[0] if gz else gold.split("·")[0]
        hz="✓" if z==gz else "✗"
        if hz=="✓":zok+=1
        print(f"  [{gold}]«{sym}»\n      → 病位:{z}{hz}  八纲:{''.join(bq.get('八纲',[]))}  气血:{' '.join(bq.get('气血津液',[]))}")
    print(f"\n病位正确:{zok}/{len(tests)}")
