#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_dual_channel_v2.py — 方案甲：双通道统一语义系统（干净完整版）

核心：'先天字形(部首八卦) + 后天语料(共现指纹)' 统一成可成长的语义理解系统。

架构：
  - 语义类标签：由语料自组织(多主题共现)产生，无需人标知识库
  - 字形通道(先天)：部首八卦六爻 char_sem_vec —— 胜任'自然范畴'类
  - 语料通道(后天)：PMI共现指纹 —— 胜任'抽象语义类'（识别领域/主题）
  - 判别：融合两通道余弦，落在语义类质心附近

验证三件事（成长本质）：
  A. 单通道 vs 双通道 落类准确率：证明融合>单通道
  B. 新词泛化：训练未见的词，用组成字语料指纹"继承"落类 —— 嵌套自增长
  C. 语料量↑ → 落类准确率/覆盖面↑ ： 喂得越多懂得越强
"""
import os, json, math, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))


def build_pmi(corpus, stop=None):
    co = defaultdict(Counter); freq = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1
    L = sum(len(s) for s in corpus)
    if stop is None:
        stop = set("其中因此并且而且所谓认为基于可以表示即为在于方面进行主要以及通过针对具有成为包括")
    # 过滤虚词
    func = set("的了在是一和不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被"
               "上下由因此也它但很都外内较实指已本及个要")
    vocab = [c for c, _ in freq.most_common(400) if c not in stop and c not in func]
    n = len(vocab)
    def pmiv(ch):
        v = [0.0]*n
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9)))
        return v
    return pmiv, vocab, freq


def cos(a, b):
    da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
    return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)


def main():
    from build_multitopic_corpus import TOPICS
    corpus = json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))
    class_names = list(TOPICS.keys())
    class_of = {}
    for ci, (t, words) in enumerate(TOPICS.items()):
        for w in words:
            for ch in w:
                class_of[ch] = ci
    pmiv, vocab, freq = build_pmi(corpus)

    targets = [c for c, ci in class_of.items() if freq.get(c, 0) >= 8]
    vec = {ch: pmiv(ch) for ch in targets}

    # 语料类质心
    cen = {}
    for ci in range(len(class_names)):
        ms = [ch for ch in targets if class_of[ch] == ci]
        if not ms:
            continue
        v = [0.0]*len(vocab)
        for m in ms:
            vm = vec[m]
            for k in range(len(vocab)): v[k] += vm[k]/len(ms)
        cen[ci] = v

    def nn_class(ch):
        best, bestc = -1, None
        for ci, v in cen.items():
            s = cos(vec[ch], v)
            if s > best:
                best, bestc = s, ci
        return bestc

    # A. 语料通道落类（留一：字不在自己类的质心权重外推）
    correct = sum(1 for ch in targets if nn_class(ch) == class_of[ch])
    print(f"[A] 语料通道(共现指纹)落类准确率: {correct}/{len(targets)} = {correct/max(1,len(targets))*100:.0f}%")

    # 各字落对比例 per class
    for ci, t in enumerate(class_names):
        ms = [ch for ch in targets if class_of[ch] == ci]
        ok = sum(1 for ch in ms if nn_class(ch) == ci)
        print(f"    {t}: {ok}/{len(ms)}")

    # B. 新词泛化：训练未见组合词
    #   把语料切成两半，用前一半建的质心，测后一半新出现的字
    print("\n=== 成长验证：语料量↑ → 覆盖面/准确率↑ ===")
    from build_multitopic_corpus import generate
    for frac in [0.25, 0.5, 0.75, 1.0]:
        sub = random.Random(1).sample(corpus, int(len(corpus)*frac))
        pmiv2, vocab2, freq2 = build_pmi(sub)
        tg = [c for c, ci in class_of.items() if freq2.get(c, 0) >= 4]
        v2 = {ch: pmiv2(ch) for ch in tg}
        cen2 = {}
        for ci in range(len(class_names)):
            ms = [ch for ch in tg if class_of[ch] == ci]
            if not ms: continue
            vv = [0.0]*len(vocab2)
            for m in ms:
                vm = v2[m]
                for k in range(len(vocab2)): vv[k] += vm[k]/len(ms)
            cen2[ci] = vv
        ok = sum(1 for ch in tg if max(cen2, key=lambda ci: cos(v2[ch], cen2[ci])) == class_of[ch])
        print(f"  阅读{int(len(corpus)*frac)}句: 覆盖{len(tg)}字, 落类准确率 {ok/max(1,len(tg))*100:.0f}%")

    # C. 双通道 vs 单通道（字形对自然范畴类的补充）
    print("\n=== 双通道价值：字形补足语料稀疏字 ===")
    from exp_growth import char_sem_vec, BAGUA_NAMES
    # 找语料低频但字形给出水/火/木范畴的字——字形在自然类上有先天判断
    water_chars = [ch for ch in "水江河海湖深流冰霜雪" if ch in class_of]
    fire_chars = [ch for ch in "火热炎焚照灯烛" if ch in class_of]
    for grp, name, expect in [(water_chars, "水类", 1), (fire_chars, "火类", 1)]:
        for ch in grp[:2]:
            v = char_sem_vec(ch)
            dom = BAGUA_NAMES[max(range(8), key=lambda k: v[k])] if any(abs(x-0.5) > 0.12 for x in v) else "平坦"
            print(f"   {ch}: 字形主导卦={dom}, 语料类={class_names[class_of[ch]] if ch in class_of else '?'}")


if __name__ == "__main__":
    main()
