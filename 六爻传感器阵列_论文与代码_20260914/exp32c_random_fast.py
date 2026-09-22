#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp32c_random_fast: random 初始化 ResNet18 的 15 类快速评估
================================================================================
修正 exp32 在 random 模式下的数值病态:
  - 随机 ResNet 经 ReLU 后大量通道为 0 -> 模板 SD 近零 -> 残差爆炸
  - 修正: 对 SD 设下限 (floor=0.1), 并对特征做逐通道归一化
- 单 seed, float32, 逐类及时释放
"""
import os, sys, json, gc, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
import exp31_full15 as E
from sklearn.metrics import roc_auc_score
from torchvision.models import resnet18

SIZE = 256
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])
CATS15 = E.CATS15
RES = E.RES
SD_FLOOR = 0.1


class RandBB:
    def __init__(self, seed=0):
        torch.manual_seed(seed); np.random.seed(seed)
        m = resnet18(weights=None); m.eval()
        self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2 = m.layer2; self.l3 = m.layer3
        for p in self.parameters(): p.requires_grad_(False)
    def parameters(self):
        return list(self.s.parameters()) + list(self.l2.parameters()) + list(self.l3.parameters())
    def forward(self, x):
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
            T = Fm.astype(np.float32); S2 = np.zeros_like(T); n = 1
        else:
            n += 1; d = Fm - T; T = T + d / n; S2 = S2 + d * (Fm - T)
        gc.collect()
    SD = np.sqrt(S2 / max(n - 1, 1))
    SD = np.maximum(SD, SD_FLOOR)          # ★ 防死通道爆炸
    del S2; gc.collect()
    # 六爻分布(子采样)
    szs = []
    for p in tr[::max(1, len(tr)//30)]:
        R = np.abs(feat_map(bb, p) - T) / SD
        R = np.clip(R, 0, 50)              # ★ 防极端值
        szs.append(E.six_sensors(R).reshape(-1, 6))
    sz = np.concatenate(szs, 0); mu = sz.mean(0); sd = sz.std(0) + 1e-3
    te = E.load_split(cat, "test"); Sc, Y = [], []
    for p, d in te:
        R = np.abs(feat_map(bb, p) - T) / SD
        R = np.clip(R, 0, 50)
        Z = np.abs((E.six_sensors(R) - mu) / sd)
        Sc.append(Z.reshape(-1, 6).max(0).max()); Y.append(0 if d == "good" else 1)
    del T; gc.collect()
    return float(roc_auc_score(np.array(Y), np.array(Sc)))


if __name__ == "__main__":
    bb = RandBB(seed=0)
    out = []; t0 = time.time()
    for cat in CATS15:
        auc = run(cat, bb)
        out.append(dict(cat=cat, auc=auc))
        print(f"[{cat}] random AUROC={auc:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    fn = os.path.join(RES, "exp32_ladder15_random.json")
    json.dump(out, open(fn, "w"), ensure_ascii=False, indent=2)
    print(f"\n=== random 15类平均 = {np.mean([r['auc'] for r in out]):.4f} ===")
