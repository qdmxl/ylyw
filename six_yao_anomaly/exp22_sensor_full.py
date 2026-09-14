#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp22: 子路线2 全量运行 (增量 Welford, 省内存) + 少样本曲线
================================================================================
内存策略: 不缓存全部特征图, 用 Welford 在线累计:
  - 模板 T, SD   (逐图累计)
  - 六爻传感器正常分布 mu, sigma (逐图累计)
分辨率: /4 高分辨率 (448,64,64)。
"""
import os, sys, json, argparse, gc
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp20b_sensor_resid as S
from sklearn.metrics import roc_auc_score

CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
SIZE = S.SIZE


def feat_map_hi(path):
    """返回 (448,64,64) float32 高分辨率特征图。"""
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - S._MEAN) / S._STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        bb = S.backbone()
        f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
        tgt = f1.shape[-2:]
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1, f2u, f3u], 1)[0].numpy().astype(np.float32)


class Welford:
    def __init__(self, shape):
        self.n = 0; self.mean = np.zeros(shape, np.float64); self.M2 = np.zeros(shape, np.float64)
    def update(self, x):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.M2 += d * (x - self.mean)
    @property
    def std(self):
        return np.sqrt(self.M2 / max(self.n - 1, 1))


def learn_model(cat, n_train=None):
    tr = [p for p, d in S.load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    T = Welford((448, 64, 64))
    # 六爻分布: 需要先有模板才能算残差 -> 两遍法(第一遍建模板, 第二遍学爻分布)
    for i, p in enumerate(tr):
        T.update(feat_map_hi(p))
        if (i + 1) % 50 == 0:
            gc.collect()
    Tm = T.mean.astype(np.float32); Tsd = T.std.astype(np.float32) + 1e-3
    del T; gc.collect()
    # 第二遍: 学六爻正常分布(在线累计每爻的均值/方差, 按 patch 汇总)
    Y = Welford((6,))
    for i, p in enumerate(tr):
        R = np.abs(feat_map_hi(p) - Tm) / Tsd
        sen = S.six_sensors(R).reshape(-1, 6)
        # 每张图贡献其 patch 的均值与二阶矩(按图聚合, 近似)
        Y.update(sen.mean(0))
        Y.M2 += ((sen - sen.mean(0)) ** 2).sum(0)   # 加入组内方差
        if (i + 1) % 50 == 0:
            gc.collect()
    mu = Y.mean; sd = np.sqrt(Y.M2 / max(Y.n - 1, 1)) + 1e-6
    return Tm, Tsd, mu, sd


def evaluate(cat, Tm, Tsd, mu, sd):
    te = S.load_split(cat, "test")
    Sc, Y = [], []
    for p, d in te:
        R = np.abs(feat_map_hi(p) - Tm) / Tsd
        Z = np.abs((S.six_sensors(R) - mu) / sd)
        Sc.append(Z.reshape(-1, 6).max(0).max()); Y.append(0 if d == "good" else 1)
    return roc_auc_score(np.array(Y), np.array(Sc))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cat", nargs="?", default="all"); ap.add_argument("--n", type=int, default=None)
    a = ap.parse_args()
    cats = CATS if a.cat == "all" else [a.cat]
    out = []
    for cat in cats:
        print(f"[{cat}] 学习(全量) ...", flush=True)
        Tm, Tsd, mu, sd = learn_model(cat, a.n)
        auc = evaluate(cat, Tm, Tsd, mu, sd)
        out.append(dict(cat=cat, auc=float(auc)))
        print(f"[{cat}] 全量 AUROC = {auc:.4f}", flush=True)
        del Tm, Tsd, mu, sd; gc.collect()
    json.dump(out, open(os.path.join(RES, "exp22_sensor_full.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 = {np.mean([r['auc'] for r in out]):.4f}")
