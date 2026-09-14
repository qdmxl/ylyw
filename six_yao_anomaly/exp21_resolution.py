#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp21: 覆盖层分辨率对照 —— 六爻传感器阵列 (/8 低分辨率 vs /4 高分辨率)
================================================================================
n=60 (适配 3.4GB 内存)。报告两种分辨率下的类别 AUROC, 用于论文消融。
"""
import os, sys, json
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import torch, torch.nn.functional as Fn
import exp20b_sensor_resid as S
from sklearn.metrics import roc_auc_score

CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
N = 60


def feat_map_res(path, hi):
    from PIL import Image
    im = Image.open(path).convert("RGB").resize((S.SIZE, S.SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - S._MEAN) / S._STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        bb = S.backbone()
        m = bb
        f1 = m.s(x); f2 = m.l2(f1); f3 = m.l3(f2)
        if hi:
            tgt = f1.shape[-2:]
        else:
            tgt = f2.shape[-2:]
        f1u = Fn.interpolate(f1, size=tgt, mode="bilinear", align_corners=False)
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1u, f2u, f3u], 1)[0].numpy().astype(np.float32)


def run(cat, hi):
    tr = [p for p, d in S.load_split(cat, "train")][:N]
    Fs = [feat_map_res(p, hi) for p in tr]
    T = np.mean(Fs, 0); SD = np.std(Fs, 0) + 1e-3
    sz = [S.six_sensors(np.abs(f - T) / SD).reshape(-1, 6) for f in Fs]
    sz = np.concatenate(sz, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-6
    te = S.load_split(cat, "test")
    Sc, Y = [], []
    for p, d in te:
        R = np.abs(feat_map_res(p, hi) - T) / SD
        Z = np.abs((S.six_sensors(R) - mu) / sd)
        Sc.append(Z.reshape(-1, 6).max(0).max()); Y.append(0 if d == "good" else 1)
    return roc_auc_score(np.array(Y), np.array(Sc))


if __name__ == "__main__":
    out = {}
    for cat in CATS:
        lo = run(cat, False); hi = run(cat, True)
        out[cat] = dict(lo=float(lo), hi=float(hi))
        print(f"[{cat}] /8低分辨率={lo:.4f}  /4高分辨率={hi:.4f}", flush=True)
    json.dump(out, open(os.path.join(RES, "exp21_resolution.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 /8 = {np.mean([out[c]['lo'] for c in CATS]):.4f}   /4 = {np.mean([out[c]['hi'] for c in CATS]):.4f}")
