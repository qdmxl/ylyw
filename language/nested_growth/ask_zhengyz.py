#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ask_zhengyz.py — 可问答辨证系统 v1（原型）

马老师 2026-08-16：先实现一个可问答的辨证系统；映射桥以后再做；
系统以后可继续喂其他经典医书（增量重训）。

功能：
  输入症状描述（接受 现代中医辨证式 / 文言 / 夹杂白话）
  → 输出：
     1. 辨证结果：病位(五脏) + 八纲(寒热虚实) + 气血津液
     2. 溯源：每条判据命中的古籍证候词 + 对应内经/典籍成说
     3. 提示 五行传变 相关内经条文（供二期深化）

设计（方案甲双通道 + 可归因军规）：
  - 病位：含脏证候词强证据 + 无脏字证候词词级PMI（分布涌现，附录十一）
  - 八纲/气血：成说模板命中（古籍/内经成说证候种子，附录十一）
  - 溯源：记录每个命中词及其成说模板/出处
"""
import json, math, os, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))

FUNC = set("的了在一是不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已本及个别要与或且如似若并而同又亦乃则皆曰云乎者也夫盖岂哉欤焉所当应使便令或以而于在就是都还又更最很真太非常样怎么哪这和那为因为所以但是然而于是然后『」。，；：！？、,.．-—～（）《》“”‘’【】·：/∕\n\u3000\t")
FUNC |= set("黄帝帝岐伯问曰答说对道称言谈听该把跟比让向从往朝将次再每各某这其此彼这些那个位种样类般更多多少少大小上下左右中前后内体身头手足面目口牙齿舌耳目五六七八九十百千万二三四一三焦膀胱小肠大肠的")

Z5 = "心肝脾肺肾"

# ===== 成说模板（八纲/气血津液）=====
TEMPLATE = {
    "寒":   (["恶寒","畏寒","肢冷","喜温","面白","寒凝","清冷","得温则减","寒痛","形寒"],"寒者热之"),
    "热":   (["发热","潮热","烦热","口渴","面赤","喜冷","烦渴","身热","热痛","脉数","黄","尿黄"],"热者寒之"),
    "虚":   (["虚弱","亏虚","不足","气短","乏力","倦怠","自汗","消瘦","脉细","脉弱","无力"],"虚则补之"),
    "实":   (["实热","实邪","坚满","痞硬","胀满","结实","积滞","拒按","脉实","厌食"],"实则泻之"),
    "气虚": (["气短","乏力","懒言","倦怠","自汗","少气","脉弱","动则尤甚"],""),
    "血虚": (["血虚","面白","唇淡","眩晕","心悸","失眠","脉细","失血","爪淡","头晕"],""),
    "血瘀": (["瘀血","刺痛","紫暗","瘀斑","脉涩","固定痛","舌紫","血瘀","痛处固定"],""),
    "痰":   (["咳痰","痰多","痰鸣","苔腻","头重","胸闷","痰饮","吐痰","白痰","黄痰"],""),
    "湿":   (["苔腻","身重","困重","便溏","头重","湿盛","水肿","肢体困倦","胸脘痞闷"],""),
    "水停": (["水肿","浮肿","腹水","尿少","小便不利","水泛","水胀"],""),
    "津亏": (["口干","咽干","口渴","舌干","津伤","便干","皮肤干","唇燥","唇裂","小便黄"],""),
}

# ===== 各脏 成说要点（溯源展示）=====
ZANG_SAY = {
    "心": "心主神明，主血脉，其华在面，开窍于舌。心火亢盛则心烦失眠口舌生疮。",
    "肝": "肝主疏泄，主藏血，在体合筋，其华在爪，开窍于目。肝郁则胁痛太息。",
    "脾": "脾主运化，主统血，主肌肉四肢，开窍于口。脾虚则食少腹胀便溏。",
    "肺": "肺主气，司呼吸，主宣发肃降，外合皮毛，开窍于鼻。肺病则咳嗽喘促。",
    "肾": "肾主藏精，主水，主纳气，在体合骨生髓，开窍于耳及二阴。肾虚则腰膝酸软。",
}

def seg_w(s):
    s = [c if c not in FUNC else '|' for c in s]
    return [x for x in ''.join(s).split('|') if x]

def load():
    sents = []
    for f in ["corpus_neijing_wenyan.json","corpus_nannjing_wenyan.json","corpus_shanghan_wenyan.json",
        "corpus_jinkui_wenyan.json","corpus_bencao_wenyan.json","corpus_maijing_wenyan.json",
        "corpus_zhenjiu_jia_wenyan.json","corpus_zhenjiu_da_wenyan.json","corpus_zhongcang_wenyan.json",
        "corpus_danxi_wenyan.json","corpus_bingyuan_wenyan.json","corpus_piwei_wenyan.json",
        "corpus_wenbing_wenyan.json"]:
        p = os.path.join(HERE, f)
        if os.path.exists(p): sents += json.load(open(p, encoding="utf-8"))
    return sents

def build_feat(sents):
    N = len(sents)
    docF = Counter(); docZ = {z:0 for z in Z5}; coZ = defaultdict(Counter)
    for s in sents:
        for z in Z5:
            if z in s: docZ[z] += 1
        for w in seg_w(s):
            for i in range(len(w)-1):
                b = w[i:i+2]
                if len(set(b)) < 2: continue
                docF[b] += 1
                for z in Z5:
                    if z in s: coZ[b][z] += 1
    featZ = {z:{} for z in Z5}
    for b, ctr in coZ.items():
        for z, c in ctr.items():
            pmi = math.log((c/N)/((docF[b]/N)*(docZ[z]/N)+1e-12))
            if pmi > 1.2: featZ[z][b] = pmi
    return featZ

# ===== 辨证主函数 =====
def diagnose(sym, featZ):
    """返回完整辨证 + 溯源"""
    res = {"输入": sym, "病位": None, "八纲": [], "气血津液": [],
           "溯源": {"病位": [], "八纲": [], "气血津液": []}}
    # --- 病位 ---
    zsc = {z:0.0 for z in Z5}
    for z in Z5:
        # 强证据：含脏证候词
        for v in (f"{z}虚",f"{z}火",f"{z}郁",f"{z}热",f"{z}气",f"{z}血",f"{z}阴",
                  f"{z}瘀",f"{z}湿",f"{z}阳虚",f"{z}阴虚",f"{z}经",f"{z}病"):
            if v in sym:
                zsc[z] += 5.0
                res["溯源"]["病位"].append(f"「{v}」→{z}（含脏证候词强证据）")
        for v in (f"犯{z}",f"壅{z}",f"困{z}",f"伤{z}",f"及{z}"):
            if v in sym:
                zsc[z] += 5.0
                res["溯源"]["病位"].append(f"「{v}」→{z}（动词+脏强证据）")
    used = set()
    for w in seg_w(sym):
        for i in range(len(w)-1):
            b = w[i:i+2]
            if len(set(b)) < 2 or b in used: continue
            used.add(b)
            bz = max(featZ, key=lambda zz: featZ[zz].get(b,0))
            sv = featZ[bz].get(b,0)
            if sv > 0:
                zsc[bz] += sv
                if zsc[bz] - sv < 5:  # 只在未达强证据时记录PMI溯源
                    res["溯源"]["病位"].append(f"「{b}」→{bz}(PMI {sv:.1f})")
    if zsc and max(zsc.values())>0:
        res["病位"] = max(zsc, key=lambda z: zsc[z])
    # --- 八纲 & 气血津液 ---
    bag = {}; qi = {}
    for tag,(seeds,note) in TEMPLATE.items():
        hit = [sd for sd in seeds if sd in sym]
        if hit:
            if tag in ("寒","热","虚","实"):
                bag[tag] = (len(hit), hit, note)
            else:
                qi[tag] = (len(hit), hit)
    # 八纲互斥
    for a,b in [("寒","热"),("虚","实")]:
        sa = bag.get(a,(0,[]))[0]; sb = bag.get(b,(0,[]))[0]
        if max(sa,sb)>0:
            win = a if sa>=sb else b
            res["八纲"].append(win)
            res["溯源"]["八纲"].append(f"「{win}」命中『{','.join(bag[win][1][:3])}』（{bag[win][2]}）")
    for tag,(cnt,hit) in qi.items():
        res["气血津液"].append(tag)
        res["溯源"]["气血津液"].append(f"「{tag}」命中『{','.join(hit[:3])}』")
    return res

def render(r):
    print("═"*52)
    print(f"【症  状】{r['输入']}")
    print(f"【病  位】{r['病位'] or '未判'} ")
    if r['病位']:
        print(f"           {ZANG_SAY[r['病位']]}")
    print(f"【八  纲】{(' '.join(r['八纲'])) or '—'}")
    print(f"【气血津液】{(' '.join(r['气血津液'])) or '—'}")
    print("─"*52)
    print("【溯源归因】")
    for k in ["病位","八纲","气血津液"]:
        for item in r["溯源"][k][:6]:
            print(f"   {item}")
    print()

if __name__ == "__main__":
    sents = load()
    print(f"语料库：13部 {len(sents)}句（可增量重训：喂新书→build_corpus→重训）")
    featZ = build_feat(sents)
    print("═"*52)
    print("可问答辨证系统 v1 —— 输入症状，输出辨证+溯源")
    print("（支持 现代中医辨证式 / 文言 / 夹杂白话；纯白话映射桥为二期）")
    print("输入症状文字即可辨证；输入 q 退出\n")
    while True:
        try:
            sym = input("症状> ").strip()
        except EOFError:
            break
        if not sym: continue
        if sym.lower() in ("q","quit","exit"):
            print("再见！"); break
        render(diagnose(sym, featZ))
