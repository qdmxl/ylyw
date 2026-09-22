#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全量语料内化验证 (先天→后天) — 红楼梦全文 10.5万句
验证目的(马老师): 扩大语料内化, 验证"先天种子→后天成型"机制整体健康度。
评测点:
  1. coverage:  多少单字被语料实际教育到(encounters>0)
  2. 主导稳定:  水火木金雨爱等核心字主导是否随语料保持/修正正确
  3. 熵收敛:    读语料越多, 熵是否在中间区间收敛(不弥散到6, 不单极→0)
  4. 后天修正:  是否有初始错→语料修正的成功案例(如'心'是否从乾往真实取向走)
  5. 缺席字回归:  '点''电'等早期缺席字在大语料中形成取向否
"""
import sys, time, json
import numpy as np
from collections import Counter

sys.path.insert(0, ".")
from engine64q import Engine64Q
from corpus_learn64 import load_hlm, split_sentences
from bagua64 import top_k, BAGUA_INDEX

HLM = "红楼梦_全文.txt"
CORE = ["水", "火", "木", "金", "雨", "爱", "心", "明", "山", "石", "海", "天", "情", "思", "走", "跳"]


def report(eng, label):
    print(f"\n{'='*60}\n[{label}]\n{'='*60}")
    # 覆盖率
    seen = sum(1 for c in eng.cells.values() if c.encounters > 0)
    ncell = len(eng.cells)
    print(f"词胞总数:{ncell}  被语料教育过(enc>0):{seen}({seen/max(1,ncell):.1%})  累计context:{sum(c.encounters for c in eng.cells.values())}")
    # 核心字
    print("核心字主导(熵|主导卦|概率|enc):")
    for w in CORE:
        if w not in eng.cells:
            print(f"  {w}: (未生成)"); continue
        c = eng.cells[w]
        d = c.psi_dist(); h = float(-np.sum(d*np.log2(d+1e-12)))
        gi, gn, gp = c.dom()
        print(f"  {w}: 熵{h:.2f} | {gn}({gp:.2f}) enc={c.encounters}")
    # 熵分布统计
    ents = [-float(np.sum(c.psi_dist()*np.log2(c.psi_dist()+1e-12))) for c in eng.cells.values() if c.encounters>0]
    if ents:
        ents=np.array(ents)
        print(f"\n熵分布(被教育字): 均值{ents.mean():.2f} 中位{np.median(ents):.2f} "
              f"<3bit:{np.mean(ents<3)*100:.0f}% 3-5bit:{np.mean((ents>=3)&(ents<=5))*100:.0f}% >5bit:{np.mean(ents>5)*100:.0f}%")


def main():
    eng = Engine64Q(seed=0, prior_decay=40)
    eng.load_quantum_seed()
    # 预建核心词胞(观察进化)
    for w in CORE:
        eng.ensure_word(w)
    print("词典种子已载入: ", end="")
    for w in ["水", "火", "心", "点", "明", "山"]:
        eng.ensure_word(w)
        gi, gn, gp = eng.cells[w].dom()
        print(f"{w}:{gn}({gp:.2f})", end="  ")
    print()

    report(eng, "初始(纯先天种子)")

    # 分块读全量, 每5000句存一次快照观察趋势
    raw = open(HLM, encoding="utf-8").read()
    full = split_sentences(raw)
    total = len(full)
    t0 = time.time()
    chunks = np.array_split(np.arange(total), max(1, total // 8000))
    done = 0
    for ci, idx in enumerate(chunks):
        for i in idx:
            s = full[i]
            if not s:
                continue
            eng.learn_sentence(s)
            done += 1
        print(f"...已读 {done}/{total} 句 ({time.time()-t0:.0f}s, "
              f"{done/max(1,time.time()-t0):.0f}句/s)", flush=True)
        if ci == 0 or ci == len(chunks)//2 or ci == len(chunks)-1:
            pass  # 中途不打印统计, 结尾统一看
    report(eng, f"通读全量 {done} 句")

    # 保存演化后态
    st = {}
    for w, c in eng.cells.items():
        if c.encounters > 0:
            d = c.psi_dist(); gi, gn, gp = c.dom()
            st[w] = {"gua": gn, "p": round(gp, 3), "enc": c.encounters,
                     "ent": round(float(-np.sum(d*np.log2(d+1e-12))), 2)}
    with open("corpus_evolved_full.json", "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    print(f"\n已保存 corpus_evolved_full.json ({len(st)} 字演化状态)")


if __name__ == "__main__":
    main()
