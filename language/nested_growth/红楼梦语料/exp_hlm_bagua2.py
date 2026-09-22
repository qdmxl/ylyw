#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_bagua2.py — A修法·八卦配对判别（回归引擎compose谱振，绕开平值卦陪跑）

【马老师纠正 + 八卦版结果】
  v5(bagua) 显示：乾/坤 全平值卦在"8卦互相判别"下先天陪跑
    (乾[111..]方向全1饱满最高→中性偏乾69%; 坤[000..]方向全0→永远0%)
  这是"多类互争中性"的固有死结，不是权重问题。

【本版正确形态】八卦"目标配对"二分类：
  每个部首语义字 w 都有一个"应映射卦" G(w)（来自 RADICAL_SEMANTICS）：
     水/雨/…→坎  火/烛/…→离  木/树/…→巽  金/银/…→乾
     土/地/…→坤  山/石/…→艮
  验证 = 对每个 w ，问"一句含 w 的语境，其句胞/词胞语义爻，对 G(w) 的
        谱振激活，是否显著高于对'中性'的激活"？——即该词是否真的带出
        它应属卦象的语义。**此为二分类(对/错)，平值卦不再陪跑**。

【度量】回归引擎本体 compose()：H权重谱振聚合激活强度 s∈[0,1]。
  - 用引擎默认/学到的 H 调制六爻——比外挂余弦更贴合"语义涌现"。
  - 配对指标 = 含词语境相对"挖词后语境 / 中性语境"的激活增量 Δ（消融式）。
  - 因为只测"该卦该不该激活"，乾/坤(全平值)也能通过"激活是否随词上升"来验证。
"""
import re, sys, math, random
from collections import defaultdict

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG, SemanticCell, DEFAULT_THETA

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

_YAO = {}
def _sem(w):
    if w not in _YAO:
        _YAO[w] = NG.word_sem_yao(w)
    return _YAO[w]

# 引擎 H 谱振聚合：用一个默认θ的元胞对六爻求激活强度（引擎本体度量）
_PROBE = SemanticCell("__probe__", theta=list(DEFAULT_THETA))
def activate(yao):
    """引擎 compose() 谱振聚合 → 激活强度 s∈[0,1]"""
    if not yao: return 0.0
    return _PROBE.compose(yao)

def ctx_env(s):
    toks = []
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

# 每个词 → 应映射卦（从 RADICAL_SEMANTICS 反查）
_W2BAGUA = {}
for rads, meaning, bagua, strength in NG.RADICAL_SEMANTICS:
    for w in meaning:
        _W2BAGUA.setdefault(w, bagua)
    # 也收录部首字本身（氵水→坎 等）
    for r in rads:
        _W2BAGUA.setdefault(r, bagua)

def main():
    print(f"\n红楼句子:{len(sents)}  →  八卦配对判别（引擎compose谱振）")
    print(f"候选词(有确定卦象映射): {len(_W2BAGUA)}")
    print("═"*62)

    # 归并测试词（按卦）且要求该词确能产出语义爻
    by_bagua = defaultdict(list)
    for w, bg in _W2BAGUA.items():
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            by_bagua[bg].append(w)

    print("各卦可用测试词数:", {b: len(set(w)) for b, w in by_bagua.items()})

    results = {}
    for bg, ws in by_bagua.items():
        ok = tot = 0
        act = {"含词":0.0, "挖词":0.0, "中性":0.0}
        for w in list(set(ws))[:40]:
            ss = [s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            n = 0
            for s in ss[:30]:
                env_keep = ctx_env(s)
                env_drop = ctx_env(s.replace(w, ""))
                if not env_keep: continue
                n += 1; tot += 1
                a_keep = activate(env_keep)
                a_drop = activate(env_drop) if env_drop else a_keep
                act["含词"] += a_keep
                act["挖词"] += a_drop
                # 判别：含词语境对引擎激活是否 > 挖词后（消融Δ>0 → 该词确实带出语义）
                if a_keep > a_drop + 1e-6:
                    ok += 1
        if tot:
            results[bg] = (ok, tot, act["含词"]/tot, act["挖词"]/tot)

    print(f"\n② 配对判别（含该卦词语境 vs 挖词后，compose激活应显著上升→Δ>0）:")
    print("   挖词后激活下降(Δ>0)即证明:该词携带→该卦语义")
    overall_ok=overall_tot=0
    for bg,(ok,tot,ak,ad) in sorted(results.items()):
        delta = ak - ad
        print(f"   {bg}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%  "
              f"激活 含词={ak:.3f} → 挖词={ad:.3f}  Δ={delta:+.3f}")
        overall_ok+=ok; overall_tot+=tot
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%  (随机≈50%)")

    # 中性对照：不含任何该卦词的中性句，compose激活应低
    print("\n③ 中性基线：不含全部部首语义词的句子，各卦激活应显著低于含词")
    from collections import Counter
    STOPALL = set(_W2BAGUA)
    neut_act = defaultdict(float); nneut = 0
    for s in sents:
        if any(w in s for w in STOPALL) or len(s)>=80: continue
        env = ctx_env(s)
        if env:
            nneut += 1
            for bg in by_bagua:
                neut_act[bg] += activate(env)
    for bg in by_bagua:
        mn = neut_act[bg]/max(nneut,1)
        ak, _, _, _ = results.get(bg, (0,1,0.0,0.0))
        sep = (ak - mn)  # 含词激活 vs 中性激活 的差值(应>0)
        print(f"   {bg}: 含词激活={ak:.3f}  中性激活={mn:.3f}  分离度={sep:+.3f} (应>0)")

if __name__ == "__main__":
    main()
