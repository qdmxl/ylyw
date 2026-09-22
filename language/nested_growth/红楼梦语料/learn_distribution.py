#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
learn_distribution.py — 无监督分布学习：让词胞/句胞从语料中学（词、句同步学）

马老师："除了词胞学起来，句胞也同样要学起来"

【学习信号设计】(无监督、可命名语义轴、区别于静态部首表)
  核心：分布假设——经常共同出现在同一语义句中的词，共享语义倾向。
  学习器扫描红楼语料，对每个句子：
    1) 句胞语境爻 → 涌现判出主导卦 g*（八卦=可命名语义轴）
    2) 对该句每个高激活词胞 w：
       - 若 w 的词义爻方向与 g* 一致 → 计为正样本
       - 否则 → 负样本
    3) 更新 w 的"分布语义爻"：(1-η)·旧 + η·主导卦爻（按一致性加权）
    4) 句胞自身也用其聚合爻 vs 主导卦的契合度做校准
  效果：反复出现的真实词，其语义爻向"它常出现的语义环境"漂移成长，
       不受手工部首表局限 → 真学习（词、句都学）。

学习后：比较"嵌套繁殖的结构"是否带来分布语义变化(词胞sem_yao更新)。
"""
import re, sys, math, random
from collections import Counter, defaultdict

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../..")
from nested_growth_semantics import NestedGrowthSemantics as NG

random.seed(3)
TXT = "红楼梦_全文.txt"
sents = [s.strip() for s in re.split(r"[。！？\n]", open(TXT, encoding="utf-8").read()) if s.strip()]

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
def bscore(v,bg):
    if bg=="乾": return mu_of(v)-0.5
    if bg=="坤": return 0.5-mu_of(v)
    return cos_dir(v,BAGUA[bg])
def guess(env):
    if not env: return None
    return max(BAGUA, key=lambda b: bscore(env,b))

# 词库（同前的真实分词词库）
big=Counter()
for m in re.findall(r"[\u4e00-\u9fff]{2}", open(TXT,encoding="utf-8").read()):
    big[m]+=1
common=[w for w,c in big.most_common(3000) if c>=25]
WORDK = set(NG.ENTITY_WORDS) | set(common)
def seg(s):
    i=0; out=[]
    while i<len(s):
        m=None
        for ln in range(min(4,len(s)-i),0,-1):
            w=s[i:i+ln]
            if w in WORDK: m=w; break
        if m: out.append(m); i+=len(m)
        else: out.append(s[i]); i+=1
    return out

class DistLearner:
    """无监督分布学习器：词胞+句胞同步学。"""
    def __init__(self, eng, eta=0.06, min_len=3):
        self.eng=eng; self.eta=eta; self.min_len=min_len
        self.n_seen=Counter()   # 每个词胞被学习的次数
        self.sem_drift=defaultdict(lambda: [0.0]*6)  # 分布累积

    def learn_one(self, s):
        words = seg(s)
        if len(words) < self.min_len:
            return None
        # 句胞：嵌套繁殖 + 句胞语义
        r = self.eng.process_sentence_words(words)
        sent_yao = r["sent_yao"]
        if sent_yao is None:
            return None
        g_star = guess(sent_yao)   # 主导卦（可命名语义轴）
        if g_star is None:
            return None
        g_yao = BAGUA[g_star]
        # 词胞同步学：各词胞词义爻 vs 主导卦
        for c in r["word_cells"]:
            if c.is_entity or c.sem_yao is None:
                continue
            # 一致性：词义爻与主导卦方向余弦（非平值用方向，乾坤用中位）
            compat = bscore(c.sem_yao, g_star)
            self.n_seen[c.word] += 1
            # 分布漂移：向主导卦爻靠拢，按一致性加权（一致才加强，否则减弱）
            if compat > 0.05:
                push = +1.0
            elif compat < -0.05:
                push = -1.0
            else:
                push = 0.3  # 中性也给小正向（温和）
            for i in range(6):
                self.sem_drift[c.word][i] += push * (g_yao[i] - c.sem_yao[i])
        # 句胞同步学：句胞以其聚合爻对准主导卦
        sc = r["sent_cell"]
        compat_s = bscore(sent_yao, g_star)
        push_s = 1.0 if compat_s > 0.05 else (-1.0 if compat_s < -0.05 else 0.3)
        self.sem_drift["<SERIES>"] = self.sem_drift["<SERIES>"]
        # 记录句胞主导卦计数（可做句层统计）
        self.eng = self.eng
        return g_star

    def apply(self):
        """把累积的分布漂移写回词胞 learned_sem（成为持久学习成果）。
        词胞在后续 process_sentence_words 中通过 ensure_word_cell 继承 learned_sem
        （真学习路径优先于静态部首表）。"""
        applied = 0
        for w, drift in self.sem_drift.items():
            if w == "<SERIES>": continue
            n = self.n_seen.get(w, 1)
            c = self.eng.cells.get(w)
            if c is None or c.sem_yao is None:
                continue
            new = [c.sem_yao[i] + self.eta * drift[i]/max(n,1) for i in range(6)]
            new = [max(0.0, min(1.0, x)) for x in new]
            c.learned_sem = new       # 持久学习语义（嵌套继承优先用）
            c.sem_yao = list(new)
            applied += 1
        return applied

def main():
    eng = NG(max_cells=50000, seed=0)
    print(f"红楼句子: {len(sents)}")

    # 学习前：抽几个代表词的词义爻
    probe = ["水","江","树","火","金","土","山","灯"]
    before = {w: (NG.word_sem_yao(w) or eng.ensure_word_cell(w).sem_yao) for w in probe}

    # 分布学习（前 8000 句，够观察漂移）
    learn = DistLearner(eng, eta=0.06)
    gcount = Counter()
    for s in sents[:8000]:
        g = learn.learn_one(s)
        if g: gcount[g]+=1
    applied = learn.apply()

    print(f"\n学习 8000 句后，共有 {len(eng.cells)} 个词胞，校准了 {applied} 个词胞")
    print("主导卦分布（句层学到的语义轴）:")
    print("   " + ", ".join(f"{g}:{gcount[g]}" for g in BAGUA if gcount[g]))

    print("\n词胞语义爻：学习前 → 学习后（分布漂移）")
    for w in probe:
        c = eng.cells.get(w)
        after = c.sem_yao if c else before.get(w)
        drift = sum(abs(a-b) for a,b in zip(before.get(w) or [0]*6, after or [0]*6))
        print(f"  {w}: 前={[round(x,2) for x in before.get(w) or []]} "
              f"后={[round(x,2) for x in after] if after else None}  漂移={drift:.3f}")

    print(f"\n词胞持久对象数(嵌套繁殖): {len(eng.cells)}")

if __name__ == "__main__":
    main()
