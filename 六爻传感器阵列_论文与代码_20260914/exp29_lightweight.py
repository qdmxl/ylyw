#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp29_lightweight.py —— 轻量化优势实测 (对比 PatchCore / PaDiM / 我们的引擎)
================================================================================
测量维度:
  1. 推理时内存峰值 (RSS 增量, MB)
  2. 单张推理时间 (ms)
  3. 需存储的"正常参考数据"大小 (MB)   ← 记忆库 vs 模板
  4. 模型建立时间 (ms)                 ← 建库时间
  5. 理论 FLOPs 粗估 (可选)
对比对象:
  (a) 我们的六爻传感器引擎 (L1+L3, 在线模板)  ← 仅存模板 T/SD + 6x6 协方差
  (b) C 路线 patch-kNN (PatchCore 风格)       ← 存全部正常 patch 特征
  (c) PaDiM 风格 (每 patch 高斯, 存 mu/cov)   ← 存全部正常 patch 统计量
"""
import os, sys, json, time, gc, resource
import numpy as np
import torch, torch.nn.functional as Fn
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
RES = os.path.join(BASE, "results")
import exp20b_sensor_resid as S
from torchvision.models import resnet18, ResNet18_Weights

SIZE = S.SIZE
CAT = "bottle"   # 代表性类别


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


class BB:
    def __init__(self):
        m = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1); m.eval()
        self.s = torch.nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool, m.layer1)
        self.l2 = m.layer2; self.l3 = m.layer3
    def f(self, x):
        f1 = self.s(x); f2 = self.l2(f1); f3 = self.l3(f2)
        tgt = f1.shape[-2:]
        f2u = Fn.interpolate(f2, size=tgt, mode="bilinear", align_corners=False)
        f3u = Fn.interpolate(f3, size=tgt, mode="bilinear", align_corners=False)
        return torch.cat([f1, f2u, f3u], 1)   # B,448,64,64


def load_img(path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - np.array([0.485,0.456,0.406])) / np.array([0.229,0.224,0.225])
    return torch.from_numpy(x).permute(2,0,1).unsqueeze(0).float()


def main():
    out = {}
    bb = BB()
    tr = [p for p, d in S.load_split(CAT, "train")]
    te = [p for p, d in S.load_split(CAT, "test")][:20]

    # ---------- (a) 我们的引擎: 在线模板 ----------
    gc.collect()
    m0 = rss_mb()
    t0 = time.time()
    T = None; S2 = None; n = 0
    for p in tr:
        with torch.no_grad(): F = bb.f(load_img(p))[0].numpy().astype(np.float64)
        if T is None:
            T = F.copy(); S2 = np.zeros_like(F); n = 1
        else:
            n += 1; d = F - T; T += d/n; S2 += d*(F-T)
    SD = np.sqrt(S2/max(n-1,1)) + 1e-3
    t_build = (time.time()-t0)*1000
    m_build = rss_mb()-m0
    store_a = T.nbytes + SD.nbytes  # 模板+尺度
    # 推理计时
    gc.collect(); t0 = time.time()
    for p in te:
        with torch.no_grad():
            F = bb.f(load_img(p))[0].numpy()
            R = np.abs(F - T) / SD
            _ = S.six_sensors(R)
    t_infer_a = (time.time()-t0)/len(te)*1000
    out["ours_L1L3"] = dict(build_ms=t_build, infer_ms=t_infer_a,
                            store_MB=store_a/1e6, note="仅模板T/SD+6x6协方差")

    # ---------- (b) C 路线 patch-kNN ----------
    gc.collect(); m0 = rss_mb(); t0 = time.time()
    # 仅用前 60 张训练图建库(内存受限), 但按比例估算全量存储
    tr_sub = tr[:60]
    bank = []
    for p in tr_sub:
        with torch.no_grad(): f = bb.f(load_img(p))[0].numpy().astype(np.float32)
        bank.append(f.reshape(f.shape[0], -1).T)   # (4096, 448)
    bank = np.concatenate(bank, 0)
    t_build_b = (time.time()-t0)*1000
    # 按全量训练图数外推存储
    scale = len(tr) / len(tr_sub)
    store_b = bank.nbytes * scale
    out["n_patches_est_full"] = int(bank.shape[0] * scale)
    bnk = bank / (np.linalg.norm(bank, axis=1, keepdims=True)+1e-8)
    t0 = time.time()
    for p in te:
        with torch.no_grad(): f = bb.f(load_img(p))[0].numpy().astype(np.float32)
        q = f.reshape(f.shape[0], -1).T
        qn = q/(np.linalg.norm(q, axis=1, keepdims=True)+1e-8)
        sim = qn @ bnk.T
        _ = np.argpartition(-sim, 5, axis=1)[:, :5]
    t_infer_b = (time.time()-t0)/len(te)*1000
    out["C_patchkNN"] = dict(build_ms=t_build_b*scale, infer_ms=t_infer_b,
                             store_MB=store_b/1e6,
                             n_patches=int(bank.shape[0]*scale),
                             note="全部正常patch特征(外推全量)")

    # ---------- (c) PaDiM 风格 ----------
    gc.collect(); m0 = rss_mb(); t0 = time.time()
    pat = [b.reshape(b.shape[0], -1).T for b in [T]]  # placeholder
    # 逐patch mean/cov: 需要 (P, C) 统计; 这里算 mean 与对角 var (简化PaDiM)
    mu_p = bank.astype(np.float32).mean(0); var_p = bank.astype(np.float32).var(0)+1e-6
    t_build_c = (time.time()-t0)*1000
    store_c = (mu_p.nbytes + var_p.nbytes) * scale
    t0 = time.time()
    for p in te:
        with torch.no_grad(): f = bb.f(load_img(p))[0].numpy().astype(np.float32)
        q = f.reshape(f.shape[0], -1)
        _ = ((q - mu_p)**2 / var_p).sum(1)
    t_infer_c = (time.time()-t0)/len(te)*1000
    out["PaDiM_style"] = dict(build_ms=t_build_c*scale, infer_ms=t_infer_c,
                              store_MB=store_c/1e6, note="逐patch均值/方差(对角简化, 外推全量)")

    json.dump(out, open(os.path.join(RES, "exp29_lightweight.json"), "w"),
              ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
