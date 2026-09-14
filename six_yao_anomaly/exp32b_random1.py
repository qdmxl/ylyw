#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp32: 15 类知识载体阶梯消融 (论文 §6 核心证据)
================================================================================
四种信号源 + 同一套六爻传感器:
  random     随机初始化 ResNet18   (无知识)
  handmade   手工固定卷积 Sobel/Gabor (无学习)
  handyao    手工六爻信号 (Path A 的 6 个像素算子, 无预训练)   -> 由 exp34 单独产出
  pretrained ImageNet ResNet18     (本文主结果)
用法: python exp32_ladder15.py random|handmade|pretrained
"""
import os, sys, json, argparse, gc, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fn
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec_full")
RES = os.path.join(BASE, "results")
import exp31_full15 as E
from torchvision.models import resnet18, ResNet18_Weights
from sklearn.metrics import roc_auc_score

SIZE = 256
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])
CATS15 = E.CATS15


class FROZEN:
    def __init__(self, mode="pretrained", seed=0):
        torch.manual_seed(seed); np.random.seed(seed)
        self.mode = mode
        if mode in ("pretrained", "random"):
            m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if mode == "pretrained" else None)
            m.eval()
            self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
            self.l2 = m.layer2; self.l3 = m.layer3
        for p in self.parameters(): p.requires_grad_(False)

    def parameters(self):
        if self.mode == "handmade": return []
        return list(self.s.parameters()) + list(self.l2.parameters()) + list(self.l3.parameters())

    def forward(self, x):
        if self.mode == "handmade":
            g = x.mean(1, keepdim=True)
            sx = torch.tensor([[1,0,-1],[2,0,-2],[1,0,-1]], dtype=torch.float32).view(1,1,3,3)/8
            sy = torch.tensor([[1,2,1],[0,0,0],[-1,-2,-1]], dtype=torch.float32).view(1,1,3,3)/8
            lap = torch.tensor([[0,-1,0],[-1,4,-1],[0,-1,0]], dtype=torch.float32).view(1,1,3,3)
            gx = Fn.conv2d(g, sx, padding=1); gy = Fn.conv2d(g, sy, padding=1); ll = Fn.conv2d(g, lap, padding=1)
            gb = Fn.avg_pool2d(g, 4); gb = Fn.interpolate(gb, size=g.shape[-2:], mode="nearest")
            feat = torch.cat([g, torch.abs(gx), torch.abs(gy), ll, gb], 1)
            return feat.repeat(1, 13, 1, 1)[:, :64]
        f1 = self.s(x); f2 = self.l2(f1); f3 = self.l3(f2)
        tgt = f1.shape[-2:]
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1, f2u, f3u], 1)


def feat_map(bb, path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = bb.forward(x)[0]
    return f.numpy().astype(np.float32)


def run(cat, bb):
    tr = [p for p, d in E.load_split(cat, "train")]
    if not tr: return None
    T = None; S2 = None; n = 0
    for p in tr:
        Fm = feat_map(bb, p)
        if T is None:
            T = Fm.astype(np.float64); S2 = np.zeros_like(T); n = 1
        else:
            n += 1; d = Fm.astype(np.float64) - T; T += d / n; S2 += d * (Fm - T)
        gc.collect()
    SD = np.sqrt(S2 / max(n - 1, 1)) + 1e-3
    del S2; gc.collect()
    szs = []
    for p in tr[::max(1, len(tr)//40)]:
        R = np.abs(feat_map(bb, p) - T) / SD
        szs.append(E.six_sensors(R).reshape(-1, 6))
    sz = np.concatenate(szs, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-6
    te = E.load_split(cat, "test"); Sc, Y = [], []
    for p, d in te:
        R = np.abs(feat_map(bb, p) - T) / SD
        Z = np.abs((E.six_sensors(R) - mu) / sd)
        Sc.append(Z.reshape(-1, 6).max(0).max()); Y.append(0 if d == "good" else 1)
    del T; gc.collect()
    return float(roc_auc_score(np.array(Y), np.array(Sc)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode"); a = ap.parse_args()
    seeds = [0]
    bbs = [FROZEN(a.mode, seed=s) for s in seeds]
    out = []; t0 = time.time()
    for cat in CATS15:
        aucs = [run(cat, bb) for bb in bbs]
        m = float(np.mean(aucs))
        out.append(dict(cat=cat, auc=m, seeds=aucs))
        print(f"[{cat}] {a.mode} AUROC={m:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    fn = os.path.join(RES, f"exp32_ladder15_{a.mode}.json")
    json.dump(out, open(fn, "w"), ensure_ascii=False, indent=2)
    print(f"\n=== {a.mode} 15类平均 = {np.mean([r['auc'] for r in out]):.4f} ===")
