#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp28_subtype.py -- 各缺陷子类 AUROC 分解 (C 路线 patch-kNN)
================================================================================
"""
import os, sys, json
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp17_patchknn as P
from sklearn.metrics import roc_auc_score

CATS = ["bottle", "tile", "metal_nut", "toothbrush"]


def feat(path):
    im = Image.open(path).convert("RGB").resize((P.SIZE, P.SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32)/255.0
    x = (a - P._MEAN)/P._STD
    x = torch.from_numpy(x).permute(2,0,1).unsqueeze(0).float()
    with torch.no_grad():
        f = P.backbone()(x)[0].numpy().astype(np.float32)
    return f  # (448,32,32)


def patch_scores(train_feats, test_feats, k=5, max_bank=6000):
    """test 每个 patch 到 train 库的 kNN 距离; 返回图像级 max。内存受限: 限制库大小。"""
    tr = np.concatenate([f.reshape(f.shape[0], -1).T for f in train_feats], 0)  # (N, C)
    if tr.shape[0] > max_bank:
        rng = np.random.default_rng(0)
        tr = tr[rng.choice(tr.shape[0], max_bank, replace=False)]
    trn = tr / (np.linalg.norm(tr, axis=1, keepdims=True)+1e-8)
    out = []
    for tf in test_feats:
        q = tf.reshape(tf.shape[0], -1).T  # (P, C)
        qn = q / (np.linalg.norm(q, axis=1, keepdims=True)+1e-8)
        sim = qn @ trn.T            # (P, N)
        idx = np.argpartition(-sim, k, axis=1)[:, :k]
        d = 1 - np.take_along_axis(sim, idx, axis=1).mean(1)
        out.append(d.max())
    return np.array(out)


def main(cat):
    tr = [p for p, d in P.load_split(cat, "train")]
    te = P.load_split(cat, "test")
    trf = [feat(p) for p in tr]
    sc = {}; lab = {}
    for p, d in te:
        s = patch_scores(trf, [feat(p)])[0]
        sc.setdefault(d, []).append(s)
    gs = np.array(sc.get("good", []))
    res = {}
    for d, v in sc.items():
        if d == "good": continue
        y = np.concatenate([np.zeros(len(gs)), np.ones(len(v))])
        s = np.concatenate([gs, v])
        res[d] = float(roc_auc_score(y, s))
    return res


if __name__ == "__main__":
    out = {}
    for cat in CATS:
        r = main(cat)
        out[cat] = r
        print(f"[{cat}] " + "  ".join(f"{k}={v:.3f}" for k, v in r.items()), flush=True)
    json.dump(out, open(os.path.join(RES, "exp28_subtype.json"), "w"), ensure_ascii=False, indent=2)
    print("saved json")
