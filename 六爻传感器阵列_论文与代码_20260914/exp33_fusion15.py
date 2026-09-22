#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp33: 15 类 L1+L3 融合 (论文主结果)
================================================================================
对每类: 分别算 L1 与 L3 的六爻传感器分值(逐图), 归一化后固定权重融合。
融合方式: 各层 z-score 归一化后取 max(或 mean)。选 max(与记忆一致: L1+L3=0.947 最优)。
内存: 增量 Welford, 逐类清零。
"""
import os, sys, json, gc, time
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
import exp31_full15 as E
from sklearn.metrics import roc_auc_score

CATS15 = E.CATS15
RES = E.RES


# 一次遍历同时算 L1+L3，避免两次读图
def two_layer_scores(cat):
    """一次性遍历, 同时得到 L1 与 L3 的 test 分值矩阵。"""
    tr = [p for p, d in E.load_split(cat, "train")]
    # 模板 L1
    T1 = None; S1 = None; n1 = 0
    T3 = None; S3 = None; n3 = 0
    for p in tr:
        im = Image.open(p).convert("RGB").resize((E.SIZE, E.SIZE), Image.BILINEAR)
        a = np.asarray(im).astype(np.float32) / 255.0
        x = (a - E._MEAN) / E._STD
        x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            bb = E.backbone()
            f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
            tgt = f1.shape[-2:]
            F1 = f1[0].numpy().astype(np.float32)
            F3 = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)[0].numpy().astype(np.float32)
        if T1 is None:
            T1 = F1.astype(np.float64); S1 = np.zeros_like(T1); n1 = 1
            T3 = F3.astype(np.float64); S3 = np.zeros_like(T3); n3 = 1
        else:
            n1 += 1; d1 = F1.astype(np.float64) - T1; T1 += d1 / n1; S1 += d1 * (F1 - T1)
            n3 += 1; d3 = F3.astype(np.float64) - T3; T3 += d3 / n3; S3 += d3 * (F3 - T3)
        del F1, F3; gc.collect()
    SD1 = np.sqrt(S1 / max(n1 - 1, 1)) + 1e-3
    SD3 = np.sqrt(S3 / max(n3 - 1, 1)) + 1e-3
    del S1, S3; gc.collect()

    def sensors(F, T, SD):
        R = np.abs(F - T) / SD
        return E.six_sensors(R).reshape(-1, 6)

    # 六爻分布 (子采样)
    sz1, sz3 = [], []
    for p in tr[::max(1, len(tr)//40)]:
        im = Image.open(p).convert("RGB").resize((E.SIZE, E.SIZE), Image.BILINEAR)
        a = np.asarray(im).astype(np.float32) / 255.0
        x = (a - E._MEAN) / E._STD
        x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            bb = E.backbone()
            f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
            tgt = f1.shape[-2:]
            F1 = f1[0].numpy().astype(np.float32)
            F3 = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)[0].numpy().astype(np.float32)
        sz1.append(sensors(F1, T1, SD1)); sz3.append(sensors(F3, T3, SD3))
    sz1 = np.concatenate(sz1, 0); sz3 = np.concatenate(sz3, 0)
    mu1, sd1 = sz1.mean(0), sz1.std(0) + 1e-6
    mu3, sd3 = sz3.mean(0), sz3.std(0) + 1e-6
    del sz1, sz3; gc.collect()

    te = E.load_split(cat, "test"); Sc1, Sc3, Y = [], [], []
    for p, d in te:
        im = Image.open(p).convert("RGB").resize((E.SIZE, E.SIZE), Image.BILINEAR)
        a = np.asarray(im).astype(np.float32) / 255.0
        x = (a - E._MEAN) / E._STD
        x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            bb = E.backbone()
            f1 = bb.s(x); f2 = bb.l2(f1); f3 = bb.l3(f2)
            tgt = f1.shape[-2:]
            F1 = f1[0].numpy().astype(np.float32)
            F3 = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)[0].numpy().astype(np.float32)
        Z1 = np.abs((sensors(F1, T1, SD1) - mu1) / sd1).reshape(-1, 6).max(0).max()
        Z3 = np.abs((sensors(F3, T3, SD3) - mu3) / sd3).reshape(-1, 6).max(0).max()
        Sc1.append(Z1); Sc3.append(Z3)
        Y.append(0 if d == "good" else 1)
    del T1, T3; gc.collect()
    return np.array(Sc1), np.array(Sc3), np.array(Y)


if __name__ == "__main__":
    out = []; t0 = time.time()
    for cat in CATS15:
        s1, s3, Y = two_layer_scores(cat)
        auc1 = float(roc_auc_score(Y, s1)); auc3 = float(roc_auc_score(Y, s3))
        # 秩归一化融合 (无参数, 不依赖 test 分值分布形状)
        from scipy.stats import rankdata
        r1 = rankdata(s1) / len(s1); r3 = rankdata(s3) / len(s3)
        sf = np.maximum(r1, r3)
        aucf = float(roc_auc_score(Y, sf))
        out.append(dict(cat=cat, L1=auc1, L3=auc3, L1L3=aucf))
        print(f"[{cat}] L1={auc1:.4f} L3={auc3:.4f} L1+L3={aucf:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    fn = os.path.join(RES, "exp33_fusion15.json")
    json.dump(out, open(fn, "w"), ensure_ascii=False, indent=2)
    print(f"\n=== 15类平均: L1={np.mean([r['L1'] for r in out]):.4f} "
          f"L3={np.mean([r['L3'] for r in out]):.4f} "
          f"L1+L3={np.mean([r['L1L3'] for r in out]):.4f} ===")
