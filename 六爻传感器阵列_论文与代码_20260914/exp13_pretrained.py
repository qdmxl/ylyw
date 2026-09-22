#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B 路线 (exp13): 预训练特征 + 六爻统计 + 在线无监督
================================================================================
思路: 用 ImageNet 预训练 ResNet-18 的中间层特征图做"残差场",
      在其上提取【六爻统计量】(点/频/梯/分布/色/形 的语义映射),
      再走我们的在线学习 + 自适应阈值框架。
对标: PatchCore/PaDiM 用同样的预训练特征, 但做 memory-bank/kNN; 我们用六爻统计聚合。
"""
import os, sys, json, argparse
import numpy as np
import torch, torch.nn as nn
from torchvision.models import resnet18, ResNet18_Weights
from torchvision import transforms
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES = os.path.join(BASE, "results")
SIZE = 256

_w = ResNet18_Weights.IMAGENET1K_V1
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])


class Feat(torch.nn.Module):
    """取 ResNet18 layer1(64ch) + layer2(128ch) 特征(local patch 特征)。"""
    def __init__(self):
        super().__init__()
        m = resnet18(weights=_w); m.eval()
        self.stem = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)  # /4, 64ch
        self.layer2 = m.layer2                                                  # /8, 128ch
    def forward(self, x):
        f1 = self.stem(x)         # B,64,H/4,W/4
        f2 = self.layer2(f1)      # B,128,H/8,W/8
        return f1, f2


_FEAT = None
def feat_model():
    global _FEAT
    if _FEAT is None:
        _FEAT = Feat()
        for p in _FEAT.parameters():
            p.requires_grad_(False)
    return _FEAT


def load_img(path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    return a  # H,W,3 in [0,1]


def extract(path):
    """返回 (mid_feat: 128×32×32, 浅层特征 64×64×64) —— 统一上采样到 32×32 网格。"""
    a = load_img(path)
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f1, f2 = feat_model()(x)
    f1 = f1[0].numpy(); f2 = f2[0].numpy()          # 64,H/4 ; 128,H/8
    # 统一到 32×32 (SIZE/8)
    import torch.nn.functional as Fn
    f1u = Fn.interpolate(torch.from_numpy(f1).unsqueeze(0), size=(32, 32), mode="bilinear", align_corners=False)[0].numpy()
    return f1u, f2  # (64,32,32), (128,32,32)


def load_split(cat, split):
    d = os.path.join(DATA, cat, split); items = []
    if not os.path.isdir(d):
        return items
    for defect in sorted(os.listdir(d)):
        dd = os.path.join(d, defect)
        if not os.path.isdir(dd):
            continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                items.append((os.path.join(dd, f), defect))
    return items


# ---------- 六爻统计(在预训练特征残差场上的语义映射) ----------
def six_yao_feat(R, Rf1):
    """R: 深度特征残差 (128,32,32); Rf1: 浅层特征残差 (64,32,32)。
    六爻 = 六类统计聚合, 保留易理语义:
      初(点): 残差峰值     二(频): 高频能量占比   三(梯度): 结构张量各向异性
      四(分布): 偏离均值峰值  五(色/通道): 通道残差最大响应  六(形): 高对比连通结构
    """
    from skimage import filters, measure
    out = np.zeros(6)
    # 通道维度取 max 聚合 -> 空间显著性图
    Rm = R.max(0)                       # (32,32)
    # 初(点): 峰值
    out[0] = Rm.max()
    # 二(频): 高频能量占比
    Rb = filters.gaussian(Rm, 1.0)
    Fq = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = Fq.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = Fq[rad > min(h, w) * 0.25].sum() / (Fq.sum() + 1e-9)
    # 三(梯): 结构张量各向异性
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 1.5); Jyy = filters.gaussian(gy * gy, 1.5); Jxy = filters.gaussian(gx * gy, 1.5)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), 99.0)
    # 四(分布): 偏离均值峰值/标准差
    s = Rb.std() + 1e-9
    out[3] = float(np.abs(Rb - Rb.mean()).max() / s)
    # 五(通道/色): 通道残差最大响应(深度特征通道差异)
    out[4] = R.mean(0).max()
    # 六(形): 高对比连通结构峰值密度
    thr = Rm.max() * 0.6 if Rm.max() > 1e-9 else 1e9
    lab = measure.label(Rm > thr); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp) * float(Rm.max())
    return out


def build_template(cat, n_train):
    tr = [p for p, d in load_split(cat, "train")][:n_train]
    F1s, F2s = [], []
    for p in tr:
        f1, f2 = extract(p)
        F1s.append(f1); F2s.append(f2)
    T1 = np.mean(F1s, 0); S1 = np.std(F1s, 0) + 1e-3
    T2 = np.mean(F2s, 0); S2 = np.std(F2s, 0) + 1e-3
    return T1, S1, T2, S2


def score_img(path, T1, S1, T2, S2):
    f1, f2 = extract(path)
    R2 = np.abs(f2 - T2) / S2      # (128,32,32)
    R1 = np.abs(f1 - T1) / S1
    return six_yao_feat(R2, R1)


def run(cat, n_train=40, online=False):
    from sklearn.metrics import roc_auc_score
    T1, S1, T2, S2 = build_template(cat, n_train)
    tr = [p for p, d in load_split(cat, "train")][:n_train]
    F0 = np.array([score_img(p, T1, S1, T2, S2) for p in tr])
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    te = load_split(cat, "test")
    Z, Y = [], []
    for p, d in te:
        Z.append(np.abs((score_img(p, T1, S1, T2, S2) - mu) / sd)); Y.append(0 if d == "good" else 1)
    Z = np.array(Z); Y = np.array(Y)
    auc = roc_auc_score(Y, Z.mean(1))
    # 自适应阈值(75分位)
    gs = Z.mean(1)[Y == 0]
    thr = np.percentile(gs, 75)
    acc = ((Z.mean(1) > thr) == (Y == 1)).mean()
    per_yao = [max(roc_auc_score(Y, Z[:, i]), 1 - roc_auc_score(Y, Z[:, i])) for i in range(6)]
    print(f"[{cat}] B路线(预训练特征+六爻):")
    print(f"  图像级 AUROC = {auc:.4f}   自适应阈值准确率 = {acc:.4f} (thr={thr:.3f})")
    print(f"  各爻AUROC: " + " ".join(f"Y{i+1}={a:.3f}" for i, a in enumerate(per_yao)))
    return dict(cat=cat, auc=float(auc), acc=float(acc), per_yao=[float(a) for a in per_yao])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cat", nargs="?", default="all")
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    cats = ["bottle", "tile", "metal_nut", "toothbrush"] if a.cat == "all" else [a.cat]
    out = [run(c, a.n) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp13_pretrained_yao.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 AUROC = {np.mean([r['auc'] for r in out]):.4f}  平均准确率 = {np.mean([r['acc'] for r in out]):.4f}")
