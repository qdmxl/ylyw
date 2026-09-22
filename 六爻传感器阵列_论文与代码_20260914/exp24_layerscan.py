#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp24: 六爻传感器在不同特征层的全类别对比 (找最优层/层融合)
================================================================================
"""
import os, sys, json, gc
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp20b_sensor_resid as S
from sklearn.metrics import roc_auc_score

SIZE = S.SIZE
CATS = ["bottle", "tile", "metal_nut", "toothbrush"]


def feat_layers(path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - S._MEAN) / S._STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        bb = S.backbone(); f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
        return [f1[0].numpy().astype(np.float32), f2[0].numpy().astype(np.float32), f3[0].numpy().astype(np.float32)]


def run(cat, layers, n_train=None, fuse=True):
    tr = [p for p, d in S.load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    # 逐层建模板与六爻分布
    params = []
    for L in layers:
        Fs = [feat_layers(p)[L] for p in tr]
        T = np.mean(Fs, 0); SD = np.std(Fs, 0) + 1e-3
        sz = [S.six_sensors(np.abs(f - T) / SD).reshape(-1, 6) for f in Fs]
        sz = np.concatenate(sz, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-6
        params.append((L, T, SD, mu, sd))
    te = S.load_split(cat, "test")
    Sc, Y = [], []
    for p, d in te:
        layers_f = feat_layers(p)
        score_parts = []
        for (L, T, SD, mu, sd) in params:
            R = np.abs(layers_f[L] - T) / SD
            Z = np.abs((S.six_sensors(R) - mu) / sd)
            score_parts.append(Z.reshape(-1, 6).max(0).max())
        sc = np.mean(score_parts) if fuse else score_parts[-1]
        Sc.append(sc); Y.append(0 if d == "good" else 1)
    return roc_auc_score(np.array(Y), np.array(Sc))


if __name__ == "__main__":
    out = {}
    for cat in CATS:
        out[cat] = {}
        for name, layers in [("L1", [0]), ("L2", [1]), ("L3", [2]), ("L1+L3", [0, 2]), ("L2+L3", [1, 2]), ("L1+L2+L3", [0, 1, 2])]:
            auc = run(cat, layers)
            out[cat][name] = float(auc)
            print(f"[{cat}] {name}: AUROC={auc:.4f}", flush=True)
        print(flush=True)
    json.dump(out, open(os.path.join(RES, "exp24_layer_scan.json"), "w"), ensure_ascii=False, indent=2)
    print("平均:")
    for name in ["L1", "L2", "L3", "L1+L3", "L2+L3", "L1+L2+L3"]:
        print(f"  {name}: {np.mean([out[c][name] for c in CATS]):.4f}")
