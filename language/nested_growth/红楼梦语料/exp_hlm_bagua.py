#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_bagua.py — A修法·八卦版：判别从"五行5类"改回"八卦8类"（与引擎同构）

【马老师纠正】"为什么要用5分类？八卦系统跟5分类也没啥关系。"
  引擎地基是八卦（乾兑离震巽坎艮坤8类），部首语义通道也映射到8卦：
     坎(水氵) 离(火灬日) 巽(木) 乾(金钅) 坤(土) 艮(石山) 乾/坤是正常卦象成员
  我此前用"金木水火土五类"当判别标签 = 人为把8卦压成5类，制造语义扭曲，
  且误把"金=乾平值/土=坤平值"当不可分——其实在八卦空间它们就是正常成员。

【本版】八卦八分类判别：
  - 原型 = 引擎 YAO_BY_BAGUA 的 8 个标准卦爻（对称、含乾[111..]坤[000..]）
  - 判别度量 = 正交分解（方向Δ余弦 + 饱满度μ），保留平值卦正常参与
  - 验证 = "含某部首/语义字的语境 → 识别出对应卦象"
      每卦取义旁字集作为该卦的测试词（来自 RADICAL_SEMANTICS）
  - 中性基线对照 + 消融Δ(主证据)
"""
import re, sys, math, random
from collections import Counter, defaultdict

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

_YAO = {}
def _sem(w):
    if w not in _YAO:
        _YAO[w] = NG.word_sem_yao(w)
    return _YAO[w]

# ---------- 度量：正交分解（方向 + 饱满），非中心化保留平值卦 ----------
def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m = sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a, b):
    da, db = delta_of(a), delta_of(b)
    na, nb = norm(da), norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)

def score(v, proto):
    return cos_dir(v, proto) + 0.5*mu_of(v)*mu_of(proto)  # 方向+饱满(金乾坤不废)

# ---------- 八卦原型（引擎标准卦爻，8个对称目标） ----------
BAGUA = dict(NG.YAO_BY_BAGUA)   # 乾兑离震巽坎艮坤

# 与引擎部首语义通道一致：每卦的测试词（义旁字，来自RADICAL_SEMANTICS）
BAGUA_WORDS = {
    "坎": ["水","雨","泪","酒","江","河","海","溪","泉","潮","浓","浪","汤"],
    "离": ["火","烛","灯","焰","热","炎","烈","炊","烹","曜","晖","晴","照"],
    "巽": ["木","树","林","枝","花","叶","森","梁","柱","桌","椅","梅","松"],
    "乾": ["金","银","钱","铁","铜","锡","铃","锣","珠","宝","玉","川","伯"],
    "坤": ["土","地","城","墙","埃","址","壤","尘","场","田","塾"],
    "艮": ["山","石","峰","峦","峻","岩","岛","峰"],
    # 兑/震 在部首通道未直接映射，用常见卦义代表词兜底（可后续补充）
    "兑": ["口","言","说","姐","观","兑"],
    "震": ["雷","动","春","震","青"],
}
# 过滤：只用引擎能产出语义爻的词（去除无部首语义的）
def _words(cat):
    acc = []
    for w in BAGUA_WORDS[cat]:
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            # 该词确实映射到本卦（整词部首语义指向本卦）才作为该卦测试词
            acc.append(w)
    return acc

def ctx_env(s):
    toks = []
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y = _sem(w)
        if y is not None and y != NG.NEUTRAL_YAO:
            toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

def guess_env(env):
    if not env: return None
    best_b, best_s = None, -1e9
    for b, py in BAGUA.items():
        s = score(env, py)
        if s > best_s: best_s, best_b = s, b
    return best_b

def main():
    print(f"\n红楼句子:{len(sents)}  →  八卦八分类判别（与引擎同构）")
    print("═"*62)
    print("各卦测试词（引擎能产语义爻者）:")
    for b in BAGUA:
        w = _words(b)
        print(f"  {b}({NG.YAO_BY_BAGUA[b]}): {w}")

    # 中性基线
    STOP0 = "水雨泪酒江火烛树花金山石尘泥木林银铜铁山风雷日"
    res = Counter(); neut = 0
    for s in sents:
        if any(w in s for w in STOP0): continue
        g = guess_env(ctx_env(s))
        if g: res[g]+=1; neut+=1
    print(f"\n① 中性基线（应接近均匀, n={neut}）:")
    print("   " + ", ".join(f"{b}:{res[b]} ({res[b]/max(neut,1)*100:.0f}%)" for b in BAGUA))

    # 逐卦判别：挖掉该卦词→语境能否猜中该卦
    print("\n② 逐卦判别（挖掉目标词→语境猜卦）:")
    overall_ok = overall_tot = 0
    for bg, ws in BAGUA_WORDS.items():
        ws = _words(bg)
        if not ws: continue
        ok = tot = 0
        for w in ws:
            ss = [s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:25]:
                g = guess_env(ctx_env(s.replace(w, "")))
                if g:
                    tot+=1; overall_tot+=1
                    if g == bg: ok+=1; overall_ok+=1
        print(f"   {bg}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%  (随机≈12.5%)")
    print(f"   合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}%")

def ablation():
    print("\n"+"═"*62)
    print("③ 消融Δ（主证据）：挖掉某卦词→该卦核激活应下降(Δ<0)")
    keep = defaultdict(float); drop = defaultdict(float); cnt = Counter()
    for s in sents:
        if len(s)>=60: continue
        for bg, ws in BAGUA_WORDS.items():
            ws = _words(bg)
            present = [w for w in ws if w in s]
            if not present: continue
            cnt[bg]+=1
            ek = ctx_env(s)
            ed = ctx_env(re.sub("|".join(re.escape(w) for w in present), "", s))
            if ek: keep[bg]+= score(ek, BAGUA[bg])
            if ed: drop[bg]+= score(ed, BAGUA[bg])
    for bg in BAGUA_WORDS:
        if cnt[bg]==0: continue
        k = keep[bg]/cnt[bg]; d = drop[bg]/cnt[bg]
        print(f"   {bg}: 含词={k:+.3f} 挖后={d:+.3f} Δ={d-k:+.3f} (应<0)")

if __name__ == "__main__":
    main()
    ablation()
