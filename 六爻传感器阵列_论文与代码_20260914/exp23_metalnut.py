#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp23: metal_nut 冲刺 —— 多尺度六爻传感器 + 诊断
================================================================================
metal_nut 短板(0.846)是细划痕。诊断各缺陷子类在不同特征层的表现,
再设计多尺度传感器融合。
"""
import os, sys, json
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp20b_sensor_resid as S
from sklearn.metrics import roc_auc_score

CAT = "metal_nut"
SIZE = S.SIZE


def feat_multi(path):
    """返回 (l1:64x64, l2:32x32, l3:16x16) 各层特征。"""
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - S._MEAN) / S._STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        bb = S.backbone()
        f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
        return f1[0].numpy().astype(np.float32), f2[0].numpy().astype(np.float32), f3[0].numpy().astype(np.float32)


def sensors_from_resid(R):
    return S.six_sensors(R)


def run_layer(layer=1, pool=0):
    """用单层特征建模板+六爻传感器, 返回各类AUROC + 子类。"""
    tr_all = [p for p, d in S.load_split(CAT, "train")]
    tr = tr_all[:150]   # 省内存
    Fs = [feat_multi(p)[layer - 1] for p in tr]
    if pool:
        Fs = [f[:, ::2, ::2] for f in Fs]
    T = np.mean(Fs, 0); SD = np.std(Fs, 0) + 1e-3
    sz = [sensors_from_resid(np.abs(f - T) / SD).reshape(-1, 6) for f in Fs]
    sz = np.concatenate(sz, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-6
    te = S.load_split(CAT, "test")
    sc = defaultdict(list)
    for p, d in te:
        F = feat_multi(p)[layer - 1]
        if pool: F = F[:, ::2, ::2]
        R = np.abs(F - T) / SD
        Z = np.abs((sensors_from_resid(R) - mu) / sd)
        sc[d].append(Z.reshape(-1, 6).max(0).max())
    gs = np.array(sc["good"])
    res = {}
    for d, v in sc.items():
        if d == "good": continue
        y = np.concatenate([np.zeros(len(gs)), np.ones(len(v))]); s = np.concatenate([gs, v])
        res[d] = roc_auc_score(y, s)
    allS, allY = [], []
    for d, v in sc.items():
        allS += v; allY += [0 if d == "good" else 1 for _ in v]
    return roc_auc_score(np.array(allY), np.array(allS)), res


if __name__ == "__main__":
    print("=== metal_nut 各特征层诊断 ===")
    for layer in [1, 2, 3]:
        auc, sub = run_layer(layer)
        print(f"layer{layer}: 总AUROC={auc:.4f}  子类: " + " ".join(f"{k}={v:.3f}" for k, v in sub.items()), flush=True)
