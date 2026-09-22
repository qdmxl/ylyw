#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_semantic_capacity.py — 语义引擎理解能力全景评测（摸底短板）

目的：在"提升引擎理解能力"之前，先量化当前各层能力的真实水平，定位短板。

5 个评测维度：
  L1 字层·部首语义  : 部首字符 → 应映射卦 是否正确（氵→坎, 灬→离, 钅→乾, 土→坤...）
  L2 字层·义旁语义  : 义旁独体字（江/河→坎, 烛/灯→离）是否命中正确卦
  L3 词层·实体消歧  : 命名实体(宝玉等)是否被中立化(不误判为金石/火)
  L4 词层·时间消歧  : 时间词(日/时)是否避开了"日=火"的字面误判
  L5 句层·语境判别  : 含某卦词的句子，句胞语义能否判出该卦（复用 v7 度量）
  L6 可学习性      : H 权重能否随"成败反馈"校准（真学习 vs 静态规则）

输出：每维得分 + 短板标注。
"""
import re, sys, math, random
from collections import Counter, defaultdict

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(1)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

_YAO = {}
def _sem(w):
    if w not in _YAO: _YAO[w] = NG.word_sem_yao(w)
    return _YAO[w]

BAGUA = dict(NG.YAO_BY_BAGUA)
def mu_of(v): return sum(v)/len(v) if v else 0.0
def delta_of(v):
    if not v: return [0.0]*6
    m=sum(v)/len(v); return [x-m for x in v]
def norm(v): return math.sqrt(sum(x*x for x in v)) or 1e-9
def cos_dir(a,b):
    da,db=delta_of(a),delta_of(b); na,nb=norm(da),norm(db)
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(da,db))/(na*nb)
def score_env(v,bg):
    if bg=="乾": return mu_of(v)-0.5
    if bg=="坤": return 0.5-mu_of(v)
    return cos_dir(v,BAGUA[bg])
def guess_env(env):
    if not env: return None
    return max(BAGUA, key=lambda b: score_env(env,b))
def ctx_env(s):
    toks=[]
    for w in re.findall(r"[\u4e00-\u9fff]{1,4}", s):
        y=_sem(w)
        if y is not None and y!=NG.NEUTRAL_YAO: toks.append(y)
    if not toks: return None
    return [sum(x[i] for x in toks)/len(toks) for i in range(6)]

def ctx_env_nested(eng, words):
    """用引擎嵌套自生成接口(process_sentence_words)产生句胞语义爻。"""
    r = eng.process_sentence_words(words)
    return r["sent_yao"]
def is_entity(w): return NG.is_entity_word(w)
def is_time(w): return w in NG.TIME_WORDS

def to_bagua(yao):
    """六爻向量 → 最匹配的八卦（用卦判度量）"""
    if not yao: return None
    return max(BAGUA, key=lambda b: score_env(yao,b))

report = {}
def section(title):
    print("\n"+"═"*62); print(title); print("═"*62)

# ═══ L1 部首字符 → 卦 ═══
section("L1 字层·部首字符映射（部首 → 应映射卦）")
L1 = {("氵", "坎"), ("水","坎"), ("灬","离"), ("火","离"), ("木","巽"),
      ("钅","乾"), ("金","乾"), ("土","坤"), ("石","艮"), ("山","艮")}
ok=tot=0
for ch, expect in L1:
    y = NG._radical_yao(ch)
    g = to_bagua(y) if y else None
    hit = (g==expect)
    ok+=hit; tot+=1
    print(f"  {ch}(含部首)→{y and to_bagua(y)}  期望{expect}  {'✓' if hit else '✗'}")
report["L1"] = (ok,tot)

# ═══ L2 义旁独体字 → 卦 ═══
section("L2 字层·义旁独体字映射（江/河→坎, 烛/灯→离, 金/银→乾...）")
# 以词内成分为主（单字直接用部首语义）
WORDS_EXPECT = {
    "坎":["江","河","海","溪","泉","雨","泪","潮","浪","汤"],
    "离":["烛","灯","焰","炎","晴","晖","照","星"],
    "巽":["树","林","枝","森","梁","柱","桌","椅","梅","松"],
    "乾":["银","钱","铜","锡","铃","珠","宝","玉"],
    "坤":["地","城","墙","埃","址","壤","尘"],
    "艮":["石","峰","峦","峻","岩","岭","岗"],
}
ok=tot=0
for bg, ws in WORDS_EXPECT.items():
    for w in ws:
        yw = _sem(w)
        g2 = to_bagua(yw) if yw else None
        hit=(g2==bg)
        ok+=hit; tot+=1
        if not hit:
            print(f"  ✗ {w}→{g2}  期望{bg}")
report["L2_错例"]=tot-ok
report["L2"]=(ok,tot)

# ═══ L3 实体消歧 ═══
section("L3 词层·命名实体是否中立化（宝玉≠金石, 黛玉不偏水）")
ENTITY = ["宝玉","黛玉","宝钗","湘云","凤姐","袭人","晴雯"]
ok=tot=0
for w in ENTITY:
    is_ent = NG.is_entity_word(w)
    y = NG.word_sem_yao(w)
    neutral = (y == list(NG.NEUTRAL_YAO)) if y is not None else False
    hit = is_ent and neutral
    ok+=hit; tot+=1
    print(f"  {w}: 实体={is_ent} 中立={neutral} {'✓' if hit else '✗'}")
report["L3"]=(ok,tot)

# ═══ L4 时间词消歧 ═══
section("L4 词层·时间词避开'日=火'字面误判")
TIME=["日","时","时刻","晨","昏","夜","年","月","岁"]
ok=tot=0
for w in TIME:
    is_t = w in NG.TIME_WORDS
    y=NG.word_sem_yao(w)
    g = to_bagua(y) if y else None
    not_fire = (g!="离")   # "日"不应被卦判为离(火)
    hit = is_t and (y is not None) and not_fire
    ok+=hit; tot+=1
    print(f"  {w}: 时间词={is_t} 卦判={g} 避火({'✓' if not_fire else '✗'}) {'✓' if hit else '✗'}")
report["L4"]=(ok,tot)

# ═══ L5 句层语境判别（复用v7） ═══
section("L5 句层·含卦词语境判别（含词句→句胞→判卦 vs 挖词）")
L5_WORDS={
 "坎":["水","雨","泪","江","河","海","溪","泉","潮","浪"],
 "离":["火","烛","灯","焰","热","炎","晴","照"],
 "巽":["树","林","枝","森","梁","柱","桌","椅"],
 "乾":["金","银","钱","珠","宝","玉","铁"],
 "坤":["地","城","墙","尘","壤"],
 "艮":["山","石","峰","峦","峻","岭","岩"],
}
overall_ok=overall_tot=0
for bg,ws in L5_WORDS.items():
    ok=tot=0
    for w in ws:
        ss=[s for s in sents if w in s and len(s)<60]
        random.shuffle(ss)
        for s in ss[:40]:
            g=guess_env(ctx_env(s.replace(w,"")))
            if g: tot+=1; overall_tot+=1
            if g==bg: ok+=1; overall_ok+=1
    acc=ok/max(tot,1)
    print(f"  {bg}: {ok}/{tot} = {acc*100:.0f}%")
    report.setdefault(f"L5_{bg}",(ok,tot))
print(f"  句层合计: {overall_ok}/{overall_tot} = {overall_ok/max(overall_tot,1)*100:.0f}% (随机12.5%)")
report["L5"]=(overall_ok,overall_tot)

# ── L5b 嵌套自生成版：用引擎 process_sentence_words 产生句胞语义 ──
print("\n  ── L5b 嵌套自生成版（引擎 process_sentence_words 产生句胞）──")
from collections import Counter as _C
big=_C()
import io
_all=open(TXT,encoding="utf-8").read()
for m in re.findall(r"[\u4e00-\u9fff]{2}", _all): big[m]+=1
common=[w for w,c in big.most_common(2000) if c>=30]
SEGK=set(NG.ENTITY_WORDS)|set(common)
def seg(s):
    i=0; out=[]
    while i<len(s):
        m=None
        for ln in range(min(4,len(s)-i),0,-1):
            w=s[i:i+ln]
            if w in SEGK: m=w; break
        if m: out.append(m); i+=len(m)
        else: out.append(s[i]); i+=1
    return out
eng_nest=NG(max_cells=20000, seed=0)
nested_ok=nested_tot=0
nested_per={}
for bg,wsl in L5_WORDS.items():
    ok=tot=0
    for w in wsl:
        ss=[s for s in sents if w in s and len(s)<60]
        random.shuffle(ss)
        for s in ss[:40]:
            sent_yao=ctx_env_nested(eng_nest, seg(s.replace(w,"")))
            g=guess_env(sent_yao)
            if g: tot+=1; nested_tot+=1
            if g==bg: ok+=1; nested_ok+=1
    nested_per[bg]=(ok,tot)
    if tot: print(f"   {bg}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%")
nacc=nested_ok/max(nested_tot,1)
print(f"   嵌套句层合计: {nested_ok}/{nested_tot} = {nacc*100:.0f}% (随机12.5%)  ← 改造后")
report["L5b"]=(nested_ok,nested_tot)
report["L5b_各卦"]=nested_per

# ═══ L6 可学习性：H 权重能否随反馈校准 ═══
section("L6 可学习性：H权重随成败反馈校准（真学习 vs 静态规则）")
# 构造：给常被错判的卦，反复"喂对/喂错"，看 theta 是否调整
eng=NG(seed=2)
# 用坎卦样例训练
def feed_batch(wins_n, losses_n, yao):
    cell = eng.ensure_word_cell("__t")
    for _ in range(wins_n):
        eng.commit([cell], won=True, yao_for_cell={"__t": yao})
    for _ in range(losses_n):
        eng.commit([cell], won=False, yao_for_cell={"__t": yao})
    return dict(cell.theta_dict())
kan_yao = NG.word_sem_yao("水")
before = feed_batch(0,0,kan_yao)
after_win = feed_batch(5,0,kan_yao)
after_mix = feed_batch(5,3,kan_yao)
max_shift = max(abs(after_win[k]-before[k]) for k in before)
has_shifted = max_shift > 1e-4
print(f"  训练前 θ={before}")
print(f"  赢5局后 θ={after_win}")
print(f"  赢5输3后 θ={after_mix}")
print(f"  最大权重漂移={max_shift:.4f} → H可学习={'✓ 有' if has_shifted else '✗ 无(静态)'}")
report["L6"]=(1 if has_shifted else 0,1)

# ═══ 汇总表 ═══
section("能力评测汇总")
layers = [
    ("L1 部首字符→卦",  report["L1"]),
    ("L2 义旁字→卦",    report["L2"]),
    ("L3 实体中立化",    report["L3"]),
    ("L4 时间词避火",    report["L4"]),
    ("L5 句层语境判别",  report["L5"]),
    ("L6 H可学习性",     report["L6"]),
]
for name, (ok,tot) in layers:
    print(f"  {name:<16}: {ok}/{tot} = {ok/max(tot,1)*100:.0f}%")
