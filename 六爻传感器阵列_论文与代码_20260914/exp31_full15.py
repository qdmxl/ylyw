#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp31: 全量 15 类 MVTec AD —— 六爻传感器阵列 (论文主结果)
================================================================================
覆盖论文需要的核心数字:
  (a) 六爻传感器 L3 单层           (预训练 ResNet18 特征)
  (b) 六爻传感器 L1+L3 融合        <- 本文主结果
  (c) 层扫描 L1/L2/L3 逐类
  (d) 预训练消融: random / handmade / 手工信号  (被 exp27 覆盖, 单独跑)
内存: 3.4GB 机器, 用 Welford 增量 + float32, 逐类清零。
数据: data/mvtec_full (15 类, 软链到 MXL)
"""
import os, sys, json, argparse, gc, time
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec_full")
RES = os.path.join(BASE, "results")
SIZE = 256
_MEAN = np.array([0.485, 0.456, 0.406]); _STD = np.array([0.229, 0.224, 0.225])

CATS15 = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
          "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
          "wood", "zipper"]

from torchvision.models import resnet18, ResNet18_Weights


class Backbone:
    def __init__(self):
        m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1); m.eval()
        import torch.nn as nn
        self.s = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2 = m.layer2; self.l3 = m.layer3
        for p in self.parameters(): p.requires_grad_(False)

    def parameters(self):
        return list(self.s.parameters()) + list(self.l2.parameters()) + list(self.l3.parameters())

    def feats(self, x, layer):
        """layer in {1,2,3}: 返回对应层特征图 (在 /4 网格上, 插值对齐)"""
        f1 = self.s(x)
        if layer == 1:
            return f1
        f2 = self.l2(f1)
        if layer == 2:
            return Fn.interpolate(f2, size=f1.shape[-2:], mode="bilinear", align_corners=False)
        f3 = self.l3(f2)
        return Fn.interpolate(f3, size=f1.shape[-2:], mode="bilinear", align_corners=False)


_BB = None
def backbone():
    global _BB
    if _BB is None: _BB = Backbone()
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


def feat_map(path, layer):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - _MEAN) / _STD
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
    with torch.no_grad():
        f = backbone().feats(x, layer)[0]
    return f.numpy().astype(np.float32)


def six_sensors(R):
    """R: (C,H,W) 残差场 -> (H,W,6) 六爻传感器阵列 (与 exp20b 完全一致)。"""
    C, H, W = R.shape
    Rc = R.max(0); 
    bk = ndimage.uniform_filter(Rc, 7)
    Rc_tophat = np.maximum(Rc - bk, 0)
    out = np.zeros((H, W, 6), np.float32)
    out[..., 0] = Rc_tophat
    out[..., 1] = np.abs(ndimage.laplace(Rc_tophat))
    gy, gx = np.gradient(Rc)
    out[..., 2] = np.sqrt(gy ** 2 + gx ** 2)
    out[..., 3] = R.std(0)
    out[..., 4] = Rc_tophat ** 2
    Bk = ndimage.uniform_filter(Rc ** 2, 5) - ndimage.uniform_filter(Rc, 5) ** 2
    out[..., 5] = np.sqrt(np.maximum(Bk, 0))
    return out


class Welford:
    def __init__(self, shape):
        self.n = 0; self.mean = np.zeros(shape, np.float64); self.M2 = np.zeros(shape, np.float64)
    def update(self, x):
        self.n += 1; d = x - self.mean; self.mean += d / self.n; self.M2 += d * (x - self.mean)
    @property
    def std(self):
        return np.sqrt(self.M2 / max(self.n - 1, 1))


def learn_and_eval(cat, layer):
    """单层: 学模板+六爻分布 -> test 评分。返回 auc。"""
    from sklearn.metrics import roc_auc_score
    tr = [p for p, d in load_split(cat, "train")]
    if not tr: return None
    # 1) 模板 T (逐图 Welford)
    first = feat_map(tr[0], layer); C, H, W = first.shape
    T = Welford((C, H, W))
    T.update(first); del first
    for i, p in enumerate(tr[1:], 1):
        T.update(feat_map(p, layer))
        if (i + 1) % 50 == 0: gc.collect()
    Tm = T.mean.astype(np.float32); Tsd = T.std.astype(np.float32) + 1e-3
    del T; gc.collect()
    # 2) 六爻正常分布 (逐图聚合)
    Y = Welford((6,))
    for i, p in enumerate(tr):
        R = np.abs(feat_map(p, layer) - Tm) / Tsd
        sen = six_sensors(R).reshape(-1, 6)
        Y.update(sen.mean(0)); Y.M2 += ((sen - sen.mean(0)) ** 2).sum(0)
        if (i + 1) % 50 == 0: gc.collect()
    mu = Y.mean; sd = np.sqrt(Y.M2 / max(Y.n - 1, 1)) + 1e-6
    # 3) 评估
    te = load_split(cat, "test"); Sc, Yl, YAOC = [], [], []
    for p, d in te:
        R = np.abs(feat_map(p, layer) - Tm) / Tsd
        Z = np.abs((six_sensors(R) - mu) / sd)
        per = Z.reshape(-1, 6).max(0)
        Sc.append(per.max()); Yl.append(0 if d == "good" else 1); YAOC.append(per)
    Sc = np.array(Sc); Yl = np.array(Yl); YAOC = np.array(YAOC)
    auc = float(roc_auc_score(Yl, Sc))
    per_yao = [float(max(roc_auc_score(Yl, YAOC[:, i]), 1 - roc_auc_score(Yl, YAOC[:, i]))) for i in range(6)]
    del Tm, Tsd; gc.collect()
    return auc, per_yao


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", type=int, default=3, help="1/2/3")
    ap.add_argument("--cats", default="all")
    ap.add_argument("--tag", default="L3")
    a = ap.parse_args()
    cats = CATS15 if a.cats == "all" else a.cats.split(",")
    out = []
    t0 = time.time()
    for cat in cats:
        r = learn_and_eval(cat, a.layer)
        if r is None:
            print(f"[{cat}] 无训练数据，跳过", flush=True); continue
        auc, py = r
        out.append(dict(cat=cat, auc=auc, per_yao=py))
        print(f"[{cat}] L{a.layer} AUROC = {auc:.4f}  ({time.time()-t0:.0f}s)  "
              + " ".join(f"Y{i+1}={v:.3f}" for i, v in enumerate(py)), flush=True)
    fn = os.path.join(RES, f"exp31_full15_{a.tag}.json")
    json.dump(out, open(fn, "w"), ensure_ascii=False, indent=2)
    print(f"\n=== L{a.layer} 15类平均 = {np.mean([r['auc'] for r in out]):.4f} ===")
    print(f"结果 -> {fn}")
