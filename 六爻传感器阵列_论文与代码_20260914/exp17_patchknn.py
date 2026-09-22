#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp17: patch 级局部评分 (六爻语义保留) —— 冲 SOTA
================================================================================
思路:
  1) 预训练特征图 (ResNet18 layer1/layer2) 逐 patch 取特征向量;
  2) 局部异常评分: 每个 test patch 到"正常 patch 库"的 kNN 距离 (PatchCore 思想);
  3) 六爻语义保留: patch 特征再做六类统计聚合(点/频/梯/分布/色/形),
     并对"异常 patch"叠加六爻描述, 形成"局部-六爻"联合评分。
评估: MVTec 4 类, 全量 train/good 建库, test 评价。
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
    """ResNet18 layer1(/4,64) + layer2(/8,128) + layer3(/16,256) 多尺度特征。"""
    def __init__(self):
        super().__init__()
        m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1); m.eval()
        self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2 = m.layer2; self.l3 = m.layer3
    def forward(self, x):
        f1 = self.s(x); f2 = self.l2(f1); f3 = self.l3(f2)
        # 统一到 /8 分辨率 (32x32)
        f1u = Fn.interpolate(f1, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        # 拼接多尺度: 64+128+256 = 448 通道
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


def features(path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = backbone()(x)[0]                       # 448,32,32
        f = Fn.avg_pool2d(f, 3, stride=1, padding=1)   # 局部平滑, 去噪
    return f.numpy()                               # (448,32,32)


def patch_bank(train_paths, max_patches=40000, seed=0):
    """正常 patch 特征库 (N,448)。"""
    feats = []
    for p in train_paths:
        F = features(p)                            # 448,32,32
        C, H, W = F.shape
        feats.append(F.reshape(C, -1).T)           # (1024,448)
    bank = np.concatenate(feats, 0)                # (n*1024,448)
    rng = np.random.default_rng(seed)
    if len(bank) > max_patches:
        bank = bank[rng.choice(len(bank), max_patches, replace=False)]
    return bank


def knn_score(F, bank, k=3, chunk=4096):
    """每个 patch 到 bank 的 kNN 距离(取第k近)。返回 (H,W) 异常图。"""
    C, H, W = F.shape
    q = F.reshape(C, -1).T                         # (HW,448)
    # 归一化(余弦近似): 用 L2 距离
    bn = (bank ** 2).sum(1)
    out = np.empty(len(q))
    for i in range(0, len(q), chunk):
        qb = q[i:i + chunk]
        d = (qb ** 2).sum(1)[:, None] + bn[None, :] - 2 * qb @ bank.T
        d = np.maximum(d, 0)
        part = np.partition(d, k, axis=1)[:, :k]
        out[i:i + chunk] = np.sqrt(part[:, k - 1])  # 第 k 近
    return out.reshape(H, W)


# ---------- 六爻语义聚合(在 patch 异常图上) ----------
def six_yao_on_map(M, thr_ratio=0.95):
    from skimage import filters, measure
    out = np.zeros(6)
    out[0] = M.max()                                     # 初(点): 最异常点
    Rb = filters.gaussian(M, 1.0)
    Fq = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = Fq.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = Fq[rad > min(h, w) * 0.25].sum() / (Fq.sum() + 1e-9)   # 二(频)
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 1.5); Jyy = filters.gaussian(gy * gy, 1.5); Jxy = filters.gaussian(gx * gy, 1.5)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), 99.0)  # 三(梯)
    s = Rb.std() + 1e-9
    out[3] = float(np.abs(Rb - Rb.mean()).max() / s)      # 四(分布)
    out[4] = M.mean()                                     # 五(色/通道): 平均异常水平
    hot = M > M.max() * thr_ratio
    lab = measure.label(hot); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        out[5] = n * np.mean([p.area for p in per]) * M.max()   # 六(形): 异常区域聚集度
    return out


def run(cat, max_patches=40000, use_six=True, seed=0):
    from sklearn.metrics import roc_auc_score
    tr = [p for p, d in load_split(cat, "train")]
    te = load_split(cat, "test")
    print(f"[{cat}] 建库({len(tr)}张)...", flush=True)
    bank = patch_bank(tr, max_patches, seed)
    print(f"[{cat}] 库大小={len(bank)}", flush=True)
    S, Y = [], []
    for p, d in te:
        F = features(p)
        M = knn_score(F, bank)
        if use_six:
            yao = six_yao_on_map(M)
            # 融合: 局部峰值为主 + 六爻语义的【归一化】修正(避免尺度失衡)
            #   六爻中 初(点)=M.max() 是主信号; 六(形)对聚集型缺陷有增益, 但需归一
            yy = yao.copy()
            yy[5] = np.log1p(yy[5])          # 压缩量级
            z = (yy - yy.mean()) / (yy.std() + 1e-9)
            sc = M.max() + 0.05 * z[5]        # 仅让六(形)微调(可解释: 异常区域聚集度)
        else:
            sc = M.max()
        S.append(sc); Y.append(0 if d == "good" else 1)
    S = np.array(S); Y = np.array(Y)
    auc = roc_auc_score(Y, S)
    print(f"[{cat}] patch级kNN AUROC = {auc:.4f}", flush=True)
    return dict(cat=cat, auc=float(auc))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cat", nargs="?", default="all")
    ap.add_argument("--patches", type=int, default=40000)
    a = ap.parse_args()
    cats = ["bottle", "tile", "metal_nut", "toothbrush"] if a.cat == "all" else [a.cat]
    out = [run(c, a.patches) for c in cats]
    json.dump(out, open(os.path.join(RES, "exp17_patchknn.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n平均 AUROC = {np.mean([r['auc'] for r in out]):.4f}")
