#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exp29b_lightweight.py —— 轻量化实测(分方法独立进程, 防OOM)
用法: python exp29b_lightweight.py {ours|knn|padim}
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
CAT = "bottle"
method = sys.argv[1] if len(sys.argv) > 1 else "ours"


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
        return torch.cat([f1, f2u, f3u], 1)


def load_img(path):
    im = Image.open(path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
    a = np.asarray(im).astype(np.float32) / 255.0
    x = (a - np.array([0.485,0.456,0.406])) / np.array([0.229,0.224,0.225])
    return torch.from_numpy(x).permute(2,0,1).unsqueeze(0).float()


def main():
    bb = BB()
    tr = [p for p, d in S.load_split(CAT, "train")]
    te = [p for p, d in S.load_split(CAT, "test")][:20]
    res = {}

    if method == "ours":
        gc.collect(); m0 = rss_mb(); t0 = time.time()
        T = None; SS = None; n = 0
        for p in tr:
            with torch.no_grad(): F = bb.f(load_img(p))[0].numpy().astype(np.float64)
            if T is None: T = F.copy(); SS = np.zeros_like(F); n = 1
            else:
                n += 1; d = F - T; T += d/n; SS += d*(F-T)
        SD = np.sqrt(SS/max(n-1,1)) + 1e-3
        build = (time.time()-t0)*1000
        store = T.nbytes + SD.nbytes
        gc.collect(); t0 = time.time()
        for p in te:
            with torch.no_grad():
                F = bb.f(load_img(p))[0].numpy(); R = np.abs(F-T)/SD; S.six_sensors(R)
        infer = (time.time()-t0)/len(te)*1000
        res = dict(build_ms=build, infer_ms=infer, store_MB=store/1e6,
                   matrix_mul=None, note="仅模板T/SD")

    elif method == "knn":
        tr_sub = tr[:60]
        scale = len(tr)/len(tr_sub)
        gc.collect(); t0 = time.time()
        bank = []
        for p in tr_sub:
            with torch.no_grad(): f = bb.f(load_img(p))[0].numpy()
            bank.append(f.reshape(f.shape[0], -1).T.astype(np.float32))
        bank = np.concatenate(bank, 0)
        build = (time.time()-t0)*1000*scale
        store = bank.nbytes*scale
        bnk = bank/(np.linalg.norm(bank, axis=1, keepdims=True)+1e-8)
        t0 = time.time()
        for p in te:
            with torch.no_grad(): f = bb.f(load_img(p))[0].numpy()
            q = f.reshape(f.shape[0], -1).T.astype(np.float32)
            qn = q/(np.linalg.norm(q, axis=1, keepdims=True)+1e-8)
            # 分块计算相似度, 避免内存爆炸
            best = np.full(qn.shape[0], -np.inf, dtype=np.float32)
            for s in range(0, bnk.shape[0], 2000):
                sim = qn @ bnk[s:s+2000].T          # (P, chunk)
                best = np.maximum(best, sim.max(1))
        infer = (time.time()-t0)/len(te)*1000
        res = dict(build_ms=build, infer_ms=infer, store_MB=store/1e6,
                   n_patches=int(bank.shape[0]*scale), note="全部正常patch特征")

    elif method == "padim":
        tr_sub = tr[:60]; scale = len(tr)/len(tr_sub)
        gc.collect(); t0 = time.time()
        acc = None; acc2 = None; n = 0
        for p in tr_sub:
            with torch.no_grad(): f = bb.f(load_img(p))[0].numpy()
            q = f.reshape(f.shape[0], -1).T.astype(np.float32)   # (P, C)
            if acc is None: acc = np.zeros_like(q); acc2 = np.zeros_like(q); n = 1
            else:
                n += 1; acc += q; acc2 += q*q
        mu = acc/n; var = acc2/n - mu*mu + 1e-6
        build = (time.time()-t0)*1000*scale
        store = (mu.nbytes+var.nbytes)*scale
        t0 = time.time()
        for p in te:
            with torch.no_grad(): f = bb.f(load_img(p))[0].numpy()
            q = f.reshape(f.shape[0], -1).T.astype(np.float32)
            ((q-mu)**2/var).sum(1)
        infer = (time.time()-t0)/len(te)*1000
        res = dict(build_ms=build, infer_ms=infer, store_MB=store/1e6,
                   n_patches=int(mu.shape[0]*scale), note="逐patch均值/方差(对角)")

    res["peak_rss_MB"] = rss_mb()
    print(json.dumps({method: res}, ensure_ascii=False, indent=2))
    p = os.path.join(RES, f"exp29_{method}.json")
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
