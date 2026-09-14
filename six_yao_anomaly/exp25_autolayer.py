#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp25: 自适应层加权 (无监督, 自动选"最敏感层")
================================================================================
思路: 不用人工指定 L1+L3, 而是从正常样本自动学每层权重。
  敏感度(无监督代理): 该层六爻读数在正常样本上的【信噪比】
    - 正常方差小(稳定)  -> 该层对偏离更敏感
    - 但需避免"零方差死层"
  设计: 每层算六爻 z 分数后, 以该层"六爻正常方差的逆"作为权重 w_L,
        图像分数 = sum_L w_L * (该层最偏 patch 的 z)
  并用正常样本的"层间可分性"校准。
"""
import os, sys, json
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


def layer_params(cat, L, tr):
    Fs = [feat_layers(p)[L] for p in tr]
    T = np.mean(Fs, 0); SD = np.std(Fs, 0) + 1e-3
    sz = np.concatenate([S.six_sensors(np.abs(f - T) / SD).reshape(-1, 6) for f in Fs], 0)
    mu = sz.mean(0); sd = sz.std(0) + 1e-6
    # 无监督敏感度: 每爻"动态范围/正常方差" -> 稳定且有力的层更敏感
    rng = np.percentile(sz, 99, 0) - np.percentile(sz, 1, 0)
    sens = rng / (sd + 1e-9)
    return T, SD, mu, sd, sens


def per_patch_yao_z(path, T, SD, mu, sd):
    F = feat_layers(path)[0] if False else None  # placeholder
    return None


def run(cat, weight_mode="auto"):
    tr_all = [p for p, d in S.load_split(cat, "train")]
    tr = tr_all[:150]
    params = []
    for L in [0, 1, 2]:
        T, SD, mu, sd, sens = layer_params(cat, L, tr)
        params.append((L, T, SD, mu, sd, sens))
    # 层权重: 该层六爻敏感度之和 归一化
    if weight_mode == "auto":
        raw = np.array([p[5].sum() for p in params])
        w = raw / raw.sum()
    elif weight_mode == "uniform":
        w = np.ones(3) / 3
    elif weight_mode == "L3only":
        w = np.array([0, 0, 1.0])
    te = S.load_split(cat, "test")
    Sc, Y = [], []
    for p, d in te:
        layers_f = feat_layers(p)
        score = 0.0
        for k, (L, T, SD, mu, sd, sens) in enumerate(params):
            R = np.abs(layers_f[L] - T) / SD
            Z = np.abs((S.six_sensors(R) - mu) / sd)          # (HW,6)
            sc_L = Z.reshape(-1, 6).max(0).max()               # 该层最偏
            score += w[k] * sc_L
        Sc.append(score); Y.append(0 if d == "good" else 1)
    return roc_auc_score(np.array(Y), np.array(Sc)), w.tolist()


if __name__ == "__main__":
    for mode in ["uniform", "L3only", "auto"]:
        print(f"=== 模式: {mode} ===")
        out = {}
        for cat in CATS:
            auc, w = run(cat, mode)
            out[cat] = float(auc)
            print(f"  [{cat}] AUROC={auc:.4f}  层权重={[round(x,3) for x in w]}", flush=True)
        print(f"  平均 = {np.mean(list(out.values())):.4f}\n", flush=True)
