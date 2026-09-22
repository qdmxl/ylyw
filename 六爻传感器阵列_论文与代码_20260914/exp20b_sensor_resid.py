#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp20b: 子路线2 (修正) —— 残差 + 六爻传感器阵列 (无 kNN / 无 memory bank)
================================================================================
关键修正: 六爻传感器读的是"相对正常模板的残差", 而非特征图上的局部算子。
  正常模板 T = mean(正常样本特征图)  —— 只是均值, 不是 memory bank。
  残差场 R = |F - T| / SD
六爻传感器(逐 patch 读 R):
  初(点): 残差峰值    二(频): 残差空间高频    三(梯): 残差梯度
  四(分布): 残差通道分散  五(色/通道): 通道维极值  六(形): 残差局部聚集
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
        # 统一到 /4 高分辨率 (64x64) —— 保留细划痕
        tgt = f1.shape[-2:]
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1, f2u, f3u], 1)   # B,448,64,64


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
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = backbone()(x)[0]
    return f.numpy().astype(np.float32)


def six_sensors(R):
    """R: (C,32,32) 残差场 -> (32,32,6) 六爻传感器阵列。"""
    from scipy import ndimage
    C, H, W = R.shape
    Rc = R.max(0)                      # 通道最大
    Rm = R.mean(0)                     # 通道均值
    # 局部背景减除(top-hat): 突出"绝对小但相对突出"的局部峰 -> 细划痕
    bk = ndimage.uniform_filter(Rc, 7)
    Rc_tophat = np.maximum(Rc - bk, 0)
    out = np.zeros((H, W, 6))
    out[..., 0] = Rc_tophat                                 # 初: 局部峰(top-hat, 突出细点/划痕)
    out[..., 1] = np.abs(ndimage.laplace(Rc_tophat))        # 二: 残差高频
    gy, gx = np.gradient(Rc)
    out[..., 2] = np.sqrt(gy ** 2 + gx ** 2)                # 三: 残差梯度
    out[..., 3] = R.std(0)                                  # 四: 通道分散(分布)
    out[..., 4] = Rc_tophat ** 2                            # 五: 通道能量(局部)
    Bk = ndimage.uniform_filter(Rc ** 2, 5) - ndimage.uniform_filter(Rc, 5) ** 2
    out[..., 5] = np.sqrt(np.maximum(Bk, 0))                # 六: 局部聚集
    return out


def build_template(cat, n_train=None):
    tr = [p for p, d in load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    Fs = [feat_map(p) for p in tr]
    T = np.mean(Fs, 0)
    SD = np.std(Fs, 0) + 1e-3
    return T, SD


def run(cat, n_train=None, agg="max"):
    from sklearn.metrics import roc_auc_score
    T, SD = build_template(cat, n_train)
    # 正常: 学每爻在 patch 上的分布
    tr = [p for p, d in load_split(cat, "train")]
    if n_train: tr = tr[:n_train]
    sz = []
    for p in tr:
        R = np.abs(feat_map(p) - T) / SD
        sz.append(six_sensors(R).reshape(-1, 6))
    sz = np.concatenate(sz, 0)
    mu = sz.mean(0); sd = sz.std(0) + 1e-6
    te = load_split(cat, "test")
    S, Y, YAOC = [], [], []
    for p, d in te:
        R = np.abs(feat_map(p) - T) / SD
        Z = np.abs((six_sensors(R) - mu) / sd)
        per = Z.reshape(-1, 6).max(0)
        sc = per.max() if agg == "max" else per.mean()
        S.append(sc); Y.append(0 if d == "good" else 1); YAOC.append(per)
    S = np.array(S); Y = np.array(Y); YAOC = np.array(YAOC)
    auc = roc_auc_score(Y, S)
    per_yao = [max(roc_auc_score(Y, YAOC[:, i]), 1 - roc_auc_score(Y, YAOC[:, i])) for i in range(6)]
    print(f"[{cat}] 残差+六爻传感器 AUROC = {auc:.4f}")
    print(f"    各爻AUROC: " + " ".join(f"Y{i+1}={a:.3f}" for i, a in enumerate(per_yao)))
    return dict(cat=cat, auc=float(auc), per_yao=[float(a) for a in per_yao])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cat", nargs="?", default="all")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--agg", default="max")
    a = ap.parse_args()
    cats = ["bottle", "tile", "metal_nut", "toothbrush"] if a.cat == "all" else [a.cat]
    out = [run(c, a.n, a.agg) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp20b_sensor_resid.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 AUROC = {np.mean([r['auc'] for r in out]):.4f}")

# ===== 分辨率对照: 低分辨率(/8, 32x32) vs 高分辨率(/4, 64x64) =====
# 通过环境变量 YAOHI 控制 Backbone.forward 的目标分辨率(见下)
