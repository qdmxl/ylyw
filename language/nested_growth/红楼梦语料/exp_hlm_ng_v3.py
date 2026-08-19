#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_hlm_ng_v3.py — 《红楼梦》· 以词为主+以句为主 的词胞/句胞理解试点（马老师三步之步骤3）

原则（马老师）：理解不能只在字层面——词胞自动嵌套生成后以词为主理解，
               句胞生成后以句为主理解。静态“字→卦象”在红楼人名/时间词密集
               下会字义漂移(“宝玉”非金石、“日/时”非火)，故在词级消歧、句级聚合。

测试：挖掉目标词的语境 → 句胞语义 → 候选各类别代表词(词胞语义爻) → 猜中类别。
对比基线：随机(1/5) + 中性语境污染率。
"""
import re, sys, math, random
from collections import Counter

HERE = "./"
sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(0)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

# 词库（实体 + 时间 + 高频双字）
from collections import Counter as _C
big = _C()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT, encoding="utf-8").read()):
    big[m] += 1
common = [w for w, c in big.most_common(3000) if c >= 25]
WORDSET = set(NG.ENTITY_WORDS) | set(NG.TIME_WORDS) | set(common)

def seg(s):
    i = 0; out = []
    while i < len(s):
        m = None
        for ln in range(min(4, len(s)-i), 0, -1):
            w = s[i:i+ln]
            if w in WORDSET:
                m = w; break
        if m:
            out.append(m); i += len(m)
        else:
            out.append(s[i]); i += 1
    return out

PROTO = {"水":"水", "火":"火", "木":"树", "金":"金", "土":"山"}
def center(v): m=sum(v)/len(v); return [x-m for x in v]
def cos_c(a, b):
    a=center(a); b=center(b)
    na=math.sqrt(sum(x*x for x in a)) or 1.0
    nb=math.sqrt(sum(x*x for x in b)) or 1.0
    if na<1e-9 or nb<1e-9: return 0.0
    return sum(x*y for x,y in zip(a,b))/(na*nb)

eng = NG()

def ctx_sem(sentence):
    """句胞语义：分词 → 词胞语义爻聚合（以词为主）。挖掉目标词由其调用处处理。"""
    return eng.process_sentence_words(seg(sentence))["sent_yao"]

def guess(sentence, stop=set()):
    """挖掉 stop 中的目标类别词后，句胞语义最匹配哪个原型类。"""
    toks = [w for w in seg(sentence) if w not in stop]
    sem_yaos = []
    for w in toks:
        y = eng.word_sem_yao(w)
        if y is not None:
            sem_yaos.append(y)
    if not sem_yaos:
        return None
    env = [sum(x[i] for x in sem_yaos)/len(sem_yaos) for i in range(6)]
    return max(PROTO, key=lambda c: cos_c(env, eng.word_sem_yao(PROTO[c])))

def main():
    print(f"红楼句子: {len(sents)}  模式: 词级消歧 + 句胞聚合")
    print("═"*58)
    # ① 中性基线
    STOP0 = set("水雨泪酒江火烛树花金山石尘")
    res = Counter(); neut = 0
    for s in sents:
        if any(w in s for w in STOP0): continue
        g = guess(s, stop=set())
        if g: res[g]+=1; neut+=1
    print("① 中性基线（词级消歧后）：")
    print("   " + ", ".join(f"{c}:{res[c]} ({res[c]/max(neut,1)*100:.0f}%)" for c in PROTO) + f"  (n={neut})")
    # ② 逐类判别
    tests = {
        "水类":["江","河","海","溪","泉","水","雨","泪","酒"],
        "火类":["火","烛","灯","焰"],
        "木类":["树","林","枝","花"],
        "土石类":["山","石","土"],
    }
    print("─"*58)
    print("② 逐类判别（挖掉目标词，句胞语义猜类别）:")
    tot_ok=tot_all=0
    for cat, ws in tests.items():
        ok=tt=0
        for w in ws:
            ss=[s for s in sents if w in s and len(s)<60]
            random.shuffle(ss)
            for s in ss[:40]:
                g = guess(s, stop={w})
                if g:
                    tt+=1; tot_all+=1
                    if g==cat[0]:
                        ok+=1; tot_ok+=1
        print(f"   {cat}: {ok}/{tt} = {ok/max(tt,1)*100:.0f}%  (随机≈20%)")
    print("─"*58)
    print(f"   合计: {tot_ok}/{tot_all} = {tot_ok/max(tot_all,1)*100:.0f}%")

if __name__ == "__main__":
    main()
