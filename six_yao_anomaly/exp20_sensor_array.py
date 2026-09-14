#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp20: 子路线2 —— 局部六爻传感器阵列 (无 kNN / 无 memory bank)
================================================================================
思路(马老师): ResNet 特征 + 局部峰值 作为"六爻传感器的读数", 用易理框架判异常。
实现:
  1) 每张图 -> ResNet 多尺度特征图 (448,32,32);
  2) 对每个 patch, 用局部窗口算六爻传感器读数(点/频/梯/分布/色/形), 得 (32,32,6);
  3) 正常样本: 学每爻在 patch 上的分布 (mu, sigma) —— 在线可分;
  4) 异常: 每 patch 的六爻 z 偏离 |z|, 全图取"最偏 patch"的聚合 -> 图像分数;
  5) 不用 kNN, 不用 memory bank, 纯六爻传感器阵列。
"""
import os, sys, json, argparse
import numpy as np
import torch, torch.nn as nn
import torch.nn.functional as Fn
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES = os.path.join(BASE, "results")
SIZE = 256
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])


class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1); m.eval()
        self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2 = m.layer2; self.l3 = m.layer3
    def forward(self, x):
        f1 = self.s(x); f2 = self.l2(f1); f3 = self.l3(f2)
        f1u = Fn.interpolate(f1, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        return torch.cat([f1u, f2, f3u], 1)   # B,448,32,32


_BB = None
def backbone():
    global _BB
    if _BB is None:
        _BB = Backbone()
        for p in _BB.parameters(): p.requires_grad_(False)
    return _BB


def load_split(cat, split):
    d = os.path.join(DATA, cat, split); items = []
    if not os.path.isdir(d): return items
    for defect in sorted(os.listdir(d)):
        dd = os.path.join(d, defect)
        if not os.path.isdir(dd): continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                items.append((os.path.join(dd, f), defect))
    return items


def feat_map(path):
    """返回 (448,32,32) 预训练特征图。"""
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = backbone()(x)[0]
    return f.numpy()


# ---------- 六爻传感器: 对特征图逐 patch 计算 6 类读数 ----------
def six_sensor_map(F):
    """F: (448,32,32) 特征图 -> (32,32,6) 六爻传感器阵列。
    六爻语义(在特征空间):
      初(点): 局部峰响应(max-pool 后减均值)
      二(频): 空间高频(拉普拉斯)
      三(梯): 梯度幅值
      四(分布): 与全图均值的偏离
      五(色): 通道维度的能量
      六(形): 局部方差(结构复杂度)
    """
    from scipy import ndimage
    C, H, W = F.shape
    # 通道聚合: 取通道能量 + 通道最大
    E = np.sqrt((F ** 2).sum(0))          # (H,W) 能量(色/通道)
    Mx = F.max(0)                          # (H,W) 通道最大
    G = F.mean(0)                          # (H,W) 平均激活
    out = np.zeros((H, W, 6))
    # 初(点): 局部峰 = 与局部均值的正差
    lm = ndimage.uniform_filter(Mx, 5)
    out[..., 0] = np.maximum(Mx - lm, 0)
    # 二(频): 拉普拉斯
    out[..., 1] = np.abs(ndimage.laplace(G))
    # 三(梯): 梯度幅值
    gy, gx = np.gradient(G)
    out[..., 2] = np.sqrt(gy ** 2 + gx ** 2)
    # 四(分布): 偏离全图均值
    out[..., 3] = np.abs(Mx - Mx.mean())
    # 五(色/通道): 通道能量
    out[..., 4] = E
    # 六(形): 局部方差
    out[..., 5] = np.sqrt(np.maximum(ndimage.uniform_filter(G ** 2, 5) - ndimage.uniform_filter(G, 5) ** 2, 0))
    return out


def score_and_explain(path, mu, sd, agg="max"):
    """mu,sd: 每爻的正常分布 (6,). 返回图像异常分数 + 各爻贡献。"""
    S = six_sensor_map(feat_map(path))        # (32,32,6)
    Z = np.abs((S - mu) / sd)                  # 每 patch 每爻 z
    # 图像分数: 每个爻上取最偏离 patch, 再聚合
    per_yao = Z.reshape(-1, 6).max(0)          # (6,) 每爻的最强响应
    if agg == "max":
        sc = per_yao.max()
    elif agg == "mean":
        sc = per_yao.mean()
    elif agg == "top2":
        sc = np.sort(per_yao)[-2:].mean()
    return sc, per_yao


def run(cat, agg="max", n_train=None):
    from sklearn.metrics import roc_auc_score
    tr = [p for p, d in load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    # 学每爻正常分布(在正常样本的所有 patch 上)
    allz = []
    for p in tr:
        allz.append(six_sensor_map(feat_map(p)).reshape(-1, 6))
    allz = np.concatenate(allz, 0)
    mu = allz.mean(0); sd = allz.std(0) + 1e-6
    te = load_split(cat, "test")
    S, Y, YAO = [], [], []
    for p, d in te:
        sc, py = score_and_explain(p, mu, sd, agg)
        S.append(sc); Y.append(0 if d == "good" else 1); YAO.append(py)
    S = np.array(S); Y = np.array(Y); YAO = np.array(YAO)
    auc = roc_auc_score(Y, S)
    per_yao_auc = [max(roc_auc_score(Y, YAO[:, i]), 1 - roc_auc_score(Y, YAO[:, i])) for i in range(6)]
    print(f"[{cat}] 局部六爻传感器(agg={agg}) AUROC = {auc:.4f}")
    print(f"    各爻AUROC: " + " ".join(f"Y{i+1}={a:.3f}" for i, a in enumerate(per_yao_auc)))
    return dict(cat=cat, auc=float(auc), per_yao=[float(a) for a in per_yao_auc])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cat", nargs="?", default="all")
    ap.add_argument("--agg", default="max")
    ap.add_argument("--n", type=int, default=None)
    a = ap.parse_args()
    cats = ["bottle", "tile", "metal_nut", "toothbrush"] if a.cat == "all" else [a.cat]
    out = [run(c, a.agg, a.n) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp20_sensor_array.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 AUROC = {np.mean([r['auc'] for r in out]):.4f}")
