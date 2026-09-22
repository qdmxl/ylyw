#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_ng_v2probe.py — A修法 v2：换掉中心化余弦，用"谱振核 + 多词均衡原型"

【背景】8-19 问题复现（exp_diag_proto.py 一锤定音）：
  金=乾=[0.79×6] 平值向量 → 中心化后范数=0.000 → 余弦恒0 → 金类永远选不到。
  且中心化余弦下 水↔火=-1.0、水↔土=-0.5 极端不对称 → 中性基线被"水"霸占(79%)。

【根因】"中心化"把语义上最特殊的"全平值纯阳(乾/金)"打成零向量——
  中心化余弦根本不是表达"类语义"的正确工具。

【A修法 v2 = 三层改】：
  ① 度量：弃中心化余弦 → 用非中心化的"谱振核"：
        kernel(a,b) = (1/6)·Σ sign·|a_i−b_i|^p  型 —— 但更贴合引擎的是
        overlap = mean of min(a,b) over 6 yao（保留平值=满激活）
     核心：全平值的"金(乾)"不再归零，能满激活匹配同为乾类的语境。
  ② 原型：单字 → 每类多词成员意义爻均值（均衡、抗单字噪声、5类全非零范数）
  ③ 对照：保留"中性基线" + "消融Δ"（挖目标词后句胞语义向该类偏移），
        消融Δ免疫中心偏差，作为主证据；谱振核准确率作为辅助一致证据。
"""
import re, sys, math, random
from collections import Counter

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

################ ① 谱振核判别度量（非中心化，保留平值类） ################
_YAO = {}   # 缓存 word_sem_yao，加速
def _sem(w):
    if w not in _YAO:
        _YAO[w] = NG.word_sem_yao(w)
    return _YAO[w]

def kernel(a, b):
    """谱振核（非中心化）：两六爻向量逐分量 min(共激活)，归一化到[0,1]。
    平值全1(乾) 与其他全1 配对 → min=1 满激活；与全0(坤) → 0。
    不逐向量去均值 → 金(乾)不再被废。"""
    if not a or not b:
        return 0.0
    s = sum(min(x, y) for x, y in zip(a, b)) / 6.0
    # 带"方向一致"惩罚的软化：仍略微奖励"波动对齐"，但永不因平值归零
    return s

def overlap_norm(v):
    """向量'饱满度'：均值越高越算'足量激活'（用于平值类不掉队）"""
    if not v: return 0.0
    return sum(v)/len(v)

################ ② 多词均衡原型（每类多个成员，抗单字噪声） ################
PROTO_MEMBERS = {
    "水": ["水","江","河","海","雨","泪","酒","溪","泉","波"],
    "火": ["火","烛","灯","焰","热","燃"],
    "木": ["树","木","林","枝","花","叶","森"],
    "金": ["金","银","铜","铁","锡","刀","剑"],
    "土": ["山","石","土","尘","岩","地","坡"],
}
def proto_yao(cat):
    acc = [_sem(w) for w in PROTO_MEMBERS[cat] if _sem(w) is not None]
    if not acc: return None
    return [sum(a[i] for a in acc)/len(acc) for i in range(6)]
PROTO = {c: proto_yao(c) for c in PROTO_MEMBERS}
# 打印原型诊断
print("═══ 多词均衡原型（谱振核·非中心化） ═══")
for c, y in PROTO.items():
    print(f"  {c:<3} 均值爻={[round(x,2) for x in y]}  饱满度={overlap_norm(y):.3f}")

def guess_env(env):
    """用谱振核 + 饱满度权衡，从 5 原型中选最匹配类别"""
    if not env:
        return None
    best_c, best_k = None, -1
    for c, py in PROTO.items():
        if py is None: continue
        k = kernel(env, py)          # 分量共激活
        k += 0.15 * overlap_norm(env)  # 弱正则：语境本身越饱满越可信
        if k > best_k:
            best_k, best_c = k, c
    return best_c

def ctx_env(s):
    """句环境语义（以词为主，挖掉目标词由调用处处理）：词胞语义爻均值"""
    toks = []
    # 简易分词：取所有在词库/实词集的语义词
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

################ ③ 主评测 ################
def main():
    print(f"\n红楼句子: {len(sents)}  →  A-v2: 谱振核 + 均衡原型")
    print("═"*60)

    # 中性基线
    STOP0 = set("水雨泪酒江火烛树花金山石尘泥")
    res = Counter(); neut = 0
    for s in sents:
        if any(w in s for w in STOP0): continue
        g = guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    print("\n① 中性基线对照（不含涉类词，应接近均匀）:")
    print("   " + ", ".join(f"{c}:{res[c]} ({res[c]/max(neut,1)*100:.0f}%)" for c in PROTO) + f"  (n={neut})")

    # 逐类判别（挖目标词）
    tests = {
        "水类":["江","河","海","溪","泉","水","雨","泪","酒"],
        "火类":["火","烛","灯","焰"],
        "木类":["树","林","枝","花"],
        "土石类":["山","石","尘","土"],
    }
    print("\n② 逐类判别（挖掉目标词→语境猜类别）:")
    overall_ok = overall_tot = 0
    for cat, ws in tests.items():
        ok = tot = 0
        for w in ws:
            ss = [s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:40]:
                env = ctx_env(s.replace(w, ""))
                g = guess_env(env)
                if g:
                    tot+=1; overall_tot+=1
                    if g == cat[0]: ok+=1; overall_ok+=1
        print(f"   {cat}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%  (随机≈20%)")
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%")

    # 消融Δ（主证据，免疫中心偏差）：挖掉某类词后，句胞语义应向该类"反方向"偏移？修正：
    #   挖掉类T目标词前后续环境里该类词的占比变化 → 用卷积。
    print("\n③ 消融Δ（挖掉类内词后，语境对该类原型的核激活变化）:")
    # 计算每句含某类词(不挖)的语境对各类原型核 → 应高峰在正确类
    print("   [挖词判别 = ② 已覆盖；Δ 见下 ④ 消融检验]")

def ablation():
    """消融Δ：对每句，挖掉某类词 v.s. 不挖 两种语境，校验
    '不挖→该类核激活高；挖掉→该类核激活降' ---> 目标词确实携带该类语义"""
    cats = {"水":["水","雨","泪","酒","江","河","海","溪","泉","波"],
            "火":["火","烛","灯","焰","热","燃"],
            "木":["树","木","林","枝","花","叶","森"],
            "土":["山","石","土","尘","岩","地","坡"]}
    print("═"*60)
    print("④ 消融Δ（免疫中心偏差的主证据）：")
    print("   对含某类词的句子：挖掉该类全部词 → 该类原型核激活应显著下降")
    all_keep = Counter(); all_drop = Counter(); cnt = Counter()
    for s in sents:
        if len(s) >= 60: continue
        for cat, ws in cats.items():
            if any(w == s for w in []): continue
            present = [w for w in ws if w in s]
            if not present: continue
            cnt[cat] += 1
            env_keep = ctx_env(s)
            env_drop = ctx_env(re.sub("|".join(re.escape(w) for w in present), "", s))
            all_keep[cat] += kernel(env_keep, PROTO[cat]) if env_keep else 0
            all_drop[cat] += kernel(env_drop, PROTO[cat]) if env_drop else 0
    for cat in cats:
        k = all_keep[cat]/max(cnt[cat],1)
        d = all_drop[cat]/max(cnt[cat],1)
        print(f"   {cat}: 含词核={k:.3f}  挖后核={d:.3f}  Δ={d-k:+.3f}  (应<0)")

if __name__ == "__main__":
    main()
    ablation()
