#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp27: ResNet 预训练到底贡献了什么?
================================================================================
对比 (同一套六爻传感器 + 在线学习):
  B2  ImageNet 预训练 ResNet18  (当前路径B)
  B0  随机初始化 ResNet18       (同结构, 无知识)
  B0f 随机初始化 + 不冻结(仍然只是提取器, 但参数随机)  -- 等价B0
  A1  纯手工固定卷积(Sobel/Gabor, 无学习)
目的: 回答"不用预训练, 只用卷积运算能否达到同样效果"
"""
import os, sys, json
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp20b_sensor_resid as S
from torchvision.models import resnet18, ResNet18_Weights
from sklearn.metrics import roc_auc_score

SIZE = S.SIZE
DATA = S.DATA
CATS = ["bottle", "tile", "metal_nut", "toothbrush"]
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])


class FROZEN:
    """三种骨干: pretrained / random / handcrafted-fixed-conv"""
    def __init__(self, mode="pretrained", seed=0):
        torch.manual_seed(seed); np.random.seed(seed)
        if mode in ("pretrained", "random"):
            m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if mode == "pretrained" else None)
            m.eval()
            self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
            self.l2 = m.layer2; self.l3 = m.layer3
            self.mode = mode
        elif mode == "handmade":
            # 纯手工固定卷积核: 灰度 + Sobel_x + Sobel_y + Laplacian + 2xGaussian-blur
            self.mode = mode
        else:
            raise ValueError(mode)
        for p in self.parameters() if mode != "handmade" else []:
            p.requires_grad_(False)

    def forward(self, x):
        if self.mode == "handmade":
            g = x.mean(1, keepdim=True)               # 灰度 (B,1,H,W)
            sobel_x = torch.tensor([[1,0,-1],[2,0,-2],[1,0,-1]], dtype=torch.float32).view(1,1,3,3)/8
            sobel_y = torch.tensor([[1,2,1],[0,0,0],[-1,-2,-1]], dtype=torch.float32).view(1,1,3,3)/8
            lap = torch.tensor([[0,-1,0],[-1,4,-1],[0,-1,0]], dtype=torch.float32).view(1,1,3,3)
            gx = Fn.conv2d(g, sobel_x, padding=1)
            gy = Fn.conv2d(g, sobel_y, padding=1)
            ll = Fn.conv2d(g, lap, padding=1)
            gb = Fn.avg_pool2d(g, 4)
            gb = Fn.interpolate(gb, size=g.shape[-2:], mode="nearest")
            feat = torch.cat([g, torch.abs(gx), torch.abs(gy), ll, gb], 1)  # (B,5,H,W)
            # 统一通道: 复制到 64 通道便于对齐(或用1x1固定投影)
            return feat.repeat(1, 13, 1, 1)[:, :64]    # (B,64,H,W)
        f1 = self.s(x); f2 = self.l2(f1); f3 = self.l3(f2)
        tgt = f1.shape[-2:]
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1, f2u, f3u], 1)

    def parameters(self):
        if self.mode == "handmade":
            return []
        return list(self.s.parameters()) + list(self.l2.parameters()) + list(self.l3.parameters())


def load_split(cat, split):
    return S.load_split(cat, split)


def feat_map(bb, path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = bb.forward(x)[0]
    return f.numpy().astype(np.float32)


def run(cat, bb, n_train=None):
    tr = [p for p, d in load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    # 增量建模板(内存友好)
    T = None; S2 = None; n = 0
    feats_cache = []
    for p in tr:
        F = feat_map(bb, p)
        if T is None:
            T = F.astype(np.float64); S2 = np.zeros_like(T); n = 1
        else:
            n += 1
            d = F.astype(np.float64) - T
            T += d / n; S2 += d * (F - T)
    SD = np.sqrt(S2 / max(n - 1, 1)) + 1e-3
    # 六爻分布
    szs = []
    for p in tr[::max(1, len(tr)//40)]:
        R = np.abs(feat_map(bb, p) - T) / SD
        szs.append(S.six_sensors(R).reshape(-1, 6))
    sz = np.concatenate(szs, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-6
    te = load_split(cat, "test")
    Sc, Y = [], []
    for p, d in te:
        R = np.abs(feat_map(bb, p) - T) / SD
        Z = np.abs((S.six_sensors(R) - mu) / sd)
        Sc.append(Z.reshape(-1, 6).max(0).max()); Y.append(0 if d == "good" else 1)
    return roc_auc_score(np.array(Y), np.array(Sc))


if __name__ == "__main__":
    modes = ["pretrained", "random", "handmade"]
    out = {}
    for mode in modes:
        bbs = [FROZEN(mode, seed=s) for s in ([0] if mode != "random" else [0, 1, 2])]
        print(f"\n=== 骨干: {mode} ===", flush=True)
        out[mode] = {}
        for cat in CATS:
            aucs = [run(cat, bb) for bb in bbs]
            m = float(np.mean(aucs))
            out[mode][cat] = m
            extra = "" if len(aucs) == 1 else f"  (seeds: {[round(a,3) for a in aucs]})"
            print(f"  [{cat}] AUROC={m:.4f}{extra}", flush=True)
        print(f"  平均 = {np.mean(list(out[mode].values())):.4f}", flush=True)
    json.dump(out, open(os.path.join(RES, "exp27_pretrain_ablation.json"), "w"), ensure_ascii=False, indent=2)
