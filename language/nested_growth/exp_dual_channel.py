#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_dual_channel.py — 方案甲：字形(先天) + 语料(后天) 双通道融合
验证双向通路能否统一成可成长语义系统：

设定：
  1. 语料(多主题) → 分布语义自组织 → 语义类标签(6类)  ← 后天涌现的目标，替代人标知识库
  2. 每个字有 字形六爻(部首八卦,先天) + 语料共现指纹(后天)
  3. 判断：融合两通道 → argmax → 语义类

关键验证：
  A. 字形六爻单独：能否先天判对语义类？(应低,因字形不编码抽象词义)
  B. 语料指纹单独：先天判对？(应高,自组织标签从语料来)
  C. 融合(字形+bias校准语料)：能否既保留语料涌现优点,又用字形增强泛化?
  D. 新字泛化：训练未见的新字,如何用字形bias继承判断语义类?  ← 这是'嵌套自增长'的本质

双通道融合设计：
  - 语义类标签 由语料自组织给出（各主题词的目标类）
  - 字形六爻 → 先天猜测语义类（弱）
  - 学习：把每个字的 字形bias 校准到 语料给的语义类 → bias叠加在六爻上
  - 新字：无字形信息 → 用语料指纹最近邻落类；有字形 → 字形bias+语料联合
"""
import os, json, math, random
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))


def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))


def build_pmi(corpus):
    co = defaultdict(Counter); freq = Counter()
    for s in corpus:
        u = set(s)
        for ch in u:
            freq[ch] += 1
            for ch2 in u:
                if ch != ch2:
                    co[ch][ch2] += 1
    L = sum(len(s) for s in corpus)
    STOP = set("。，；：！？、,.．-—～（）《》“”‘’【】·：/∕") | set(
        "其中因此并且而且所谓认为基于可以表示即为在于方面进行主要以及通过针对具有成为包括")
    vocab = [c for c, _ in freq.most_common(400) if c not in STOP]
    n = len(vocab)
    def pmiv(ch):
        v = [0.0]*n
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/L)/((freq[ch]/L)*(freq[c]/L)+1e-9)))
        return v
    return pmiv, vocab, freq


def main():
    corpus = load_corpus()
    pmiv, vocab, freq = build_pmi(corpus)
    # ---- 语义类: 每个主题的词→类号(语料自组织的目标) ----
    # 这里用 TOPICS(自组织源) 作为 ground-truth 类映射, 模拟聚类输出
    from build_multitopic_corpus import TOPICS
    class_of = {}
    class_names = list(TOPICS.keys())
    for i, (t, words) in enumerate(TOPICS.items()):
        for w in words:
            for ch in w:
                class_of.setdefault(ch, i)
    # 高频且已归类且语料出现的字
    targets = [c for c, ci in class_of.items() if freq.get(c, 0) >= 8]
    vec_pmi = {ch: pmiv(ch) for ch in targets}

    def cos(a, b):
        da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
        return 0.0 if (da == 0 or db == 0) else sum(x*y for x, y in zip(a, b))/(da*db)

    # ---- 通道1: 字形六爻先天预测 ----
    from exp_growth import char_sem_vec, BAGUA_NAMES, BAGUA_IDX
    # 字形→语义类: 直接 argmax 六爻 是无类别的, 需一个映射. 这里测: 字形六爻能否区分语义类?
    # 用"多数部首卦"做弱先验不可行. 更公平: 对每个字, 用其字形k近邻(语料指纹)落类,
    # 但落类依赖语料. 所以测纯语料指纹落类 vs 加字形bias.
    # ---- 纯语料指纹: 最近邻落类(留一法) ----
    correct_nn = 0
    for ch in targets:
        knn = max((y for y in targets if y != ch), key=lambda y: cos(vec_pmi[ch], vec_pmi[y]))
        correct_nn += (class_of[knn] == class_of[ch])
    print(f"[A] 纯语料指纹 最近邻落类准确率: {correct_nn}/{len(targets)} = {correct_nn/max(1,len(targets))*100:.0f}%")

    # ---- 字形六爻能提供多少语义类信号? (用 PCA 投影或 与类中心的cos) ----
    # 字形六爻 vs 语料指纹: 二者加权的判别力
    from exp_growth import char_sem_vec
    # 类中心 (语料指纹)
    cen = {}
    for ci in range(len(class_names)):
        members = [ch for ch in targets if class_of[ch] == ci]
        d = len(vec_pmi)
        v = [0.0]*d
        for m in members:
            vm = vec_pmi[m]
            for k in range(d): v[k] += vm[k]/max(1, len(members))
        cen[ci] = v

    # ---- 通道2融合: 字形六爻 + bias(学习) 落类 ----
    # 模拟嵌套: 字有字形六爻(+bias) 和 语料指纹, 二者加权余弦落类
    # 学习bias: 让字形六爻偏置到类方向
    bias = {}
    lr = 0.5
    rnd = random.Random(0)
    rnd.shuffle(targets)
    cut = int(len(targets)*0.7)
    train, test = targets[:cut], targets[cut:]
    # 训练: 对每个训练字, 用 语料指纹 的类中心 校准 该字的 字形六爻bias (继承到新字)
    for ch in train:
        ci = class_of[ch]
        b = bias.get(ch, [0.0]*8)
        # 校准: 若当前字形主导卦判不到类(先天), 加bias
        bias[ch] = b
    # bias 是由"语料类→常见部首卦"统计出的全局映射(可泛化到新字)
    # 统计: 每类里 字的部首主导卦分布 → 字形bias表
    from collections import Counter
    class_dom = {ci: Counter() for ci in range(len(class_names))}
    for ch in targets:
        vec = char_sem_vec(ch)
        if any(abs(x-0.5) > 0.12 for x in vec):
            dom = max(range(8), key=lambda k: vec[k])
            class_dom[class_of[ch]][dom] += 1
    print("\n[字形卦分布 per 语义类] (看字形能否弱区分语义类):")
    for ci in range(len(class_names)):
        print(f"  {class_names[ci]}: {dict(class_dom[ci])}")

if __name__ == "__main__":
    main()
