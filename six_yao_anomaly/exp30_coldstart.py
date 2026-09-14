#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp30_coldstart.py —— 冷启动污染实验 (产出 Fig.6 数据)
在正常流最前面注入 k 个缺陷样本(k=0,1,2,3,5), 看最终 AUROC 是否受损。
机制: Welford 1/n 遗忘 —— 早期污染被后续正常样本稀释。
用路径A手工六爻引擎 (OnlineEngine)。
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
from sklearn.metrics import roc_auc_score
import online_engine as OE

RES = os.path.join(BASE, "results")
CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
KS = [0, 1, 2, 3, 5]


def eval_cat(cat, k, seed=0):
    rng = np.random.default_rng(seed)
    good = [p for p, d in OE.load_split(cat, "train")]
    test = OE.load_split(cat, "test")
    rng.shuffle(good)
    # 取 k 个缺陷样本放到最前
    defs = [p for p, d in test if d != "good"]
    rng.shuffle(defs)
    front = defs[:k]
    eng = OE.OnlineEngine()
    for p in front:          # 冷启动污染: 缺陷先来
        eng.learn(p)
    for p in good:           # 正常样本随后
        eng.learn(p)
    eng.recalibrate(good[:60])   # 用正常子集校准阈值(与主实验一致)
    y, s = [], []
    for p, d in test:
        y.append(0 if d == "good" else 1); s.append(eng.score(p)[0])
    return roc_auc_score(y, s)


def main():
    out = {}
    for cat in CATS:
        out[cat] = {}
        for k in KS:
            auc = np.mean([eval_cat(cat, k, seed=s) for s in range(1)])
            out[cat][k] = round(float(auc), 4)
            print(f"{cat} k={k}: {auc:.4f}", flush=True)
    json.dump(out, open(os.path.join(RES, "exp30_coldstart.json"), "w"),
              ensure_ascii=False, indent=2)
    print("saved")


if __name__ == "__main__":
    main()
