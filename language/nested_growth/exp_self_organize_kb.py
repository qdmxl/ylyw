#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp_self_organize_kb.py — 阅读→自组织内建知识库（分布语义聚类+内生词典）

验证马老师核心设想：通过大量阅读，自动整理/内建知识库。
流程：
  1. 语料共现 + PMI → 每个实义字的上下文向量
  2. 层次/谱聚类 → 自动形成"语义群"（内生知识库条目）
  3. 展示每个群的代表字 + 群语义标签（自动给）
  4. 对照 YLYW 部首八卦：检验"语料涌现类" vs "字形先验类" 的互补关系
"""
import os, json, math
from collections import defaultdict, Counter
HERE = os.path.dirname(os.path.abspath(__file__))


def load_corpus():
    return json.load(open(os.path.join(HERE, "corpus_multitopic2.json"), encoding="utf-8"))


def main():
    corpus = load_corpus()
    corpus_len = sum(len(s) for s in corpus)
    co = defaultdict(Counter); freq = Counter()
    for sent in corpus:
        uniq = set(sent)
        for ch in uniq:
            freq[ch] += 1
            for ch2 in uniq:
                if ch != ch2:
                    co[ch][ch2] += 1

    STOP = set("。，；：！？、,.．-—～（）《》“”‘’【】·：/∕") | set(
        "的了在是一和不为有这那与及或用而之其也所中于就如将等从对以可则并后先会着过把被上下由因此也它但很都外内较实指已")
    vocab = [c for c, _ in freq.most_common(400) if c not in STOP]
    n = len(vocab)
    def pmiv(ch):
        v = [0.0]*n
        for i, c in enumerate(vocab):
            p = co[ch].get(c, 0)
            if p:
                v[i] = max(0.0, math.log((p/corpus_len) /
                                         ((freq[ch]/corpus_len)*(freq[c]/corpus_len)+1e-9)))
        return v
    targets = [c for c, f in freq.most_common(160) if f >= 15 and c not in STOP]
    vecs = {ch: pmiv(ch) for ch in targets}

    def cos(a, b):
        da = math.sqrt(sum(x*x for x in a)); db = math.sqrt(sum(y*y for y in b))
        return 0.0 if (da==0 or db==0) else sum(x*y for x,y in zip(a,b))/(da*db)

    # ---- Agglomerative 聚类（平均连接，贪心实现）----
    chars = list(targets)
    clusters = [[c] for c in chars]
    # 预计算相似度矩阵
    sim = {c: {c2: cos(vecs[c], vecs[c2]) for c2 in chars} for c in chars}

    def clus_sim(a, b):  # 平均连接
        s = 0.0; cnt = 0
        for x in a:
            for y in b:
                s += sim[x][y]; cnt += 1
        return s/max(1, cnt)

    merges = []
    active = list(clusters)
    while len(active) > 14:
        best = None; bests = -2
        for i in range(len(active)):
            for j in range(i+1, len(active)):
                s = clus_sim(active[i], active[j])
                if s > bests:
                    bests = s; best = (i, j)
        i, j = best
        # 合并
        newc = active[i] + active[j]
        merges.append((sorted(active[i]), sorted(active[j]), round(bests, 2)))
        rest = [active[k] for k in range(len(active)) if k not in (i, j)]
        active = rest + [newc]

    print(f"自组织语义群（由 {len(chars)} 个实义字经共现聚类得到 {len(active)} 族）:\n")
    # 每族按影响力排，展示 top 成员
    for ci, cl in enumerate(sorted(active, key=len, reverse=True)):
        # 族内中心：选出与其他成员平均相似度最高的字作代表
        center = max(cl, key=lambda x: sum(sim[x][y] for y in cl)/max(1, len(cl)-1))
        print(f"群{ci+1} [{center}]: " + " ".join(cl))

    # ---- 与部首八卦对照 ----
    print("\n=== 对照：语料涌现 vs 部首八卦（YLYW字形先验） ===")
    print("（示例：几个字的 部首八卦主导卦 vs 共现最近邻）")
    from exp_growth import char_sem_vec, BAGUA_NAMES  # 复用
    for ch in ["理", "学", "知", "数", "模", "卦"]:
        if ch not in vecs:
            print(f"  {ch}: (语料中未出现足够次数)")
            continue
        vec = char_sem_vec(ch)
        if any(abs(x-0.5) > 0.12 for x in vec):
            gua = BAGUA_NAMES[max(range(8), key=lambda k: vec[k])]
        else:
            gua = "平坦"
        nn = max((c2 for c2 in chars if c2 != ch), key=lambda c2: sim[ch][c2])
        print(f"  {ch}: 字形部首卦={gua}   语料共现最近={nn}({round(sim[ch][nn],2)})")


if __name__ == "__main__":
    main()
