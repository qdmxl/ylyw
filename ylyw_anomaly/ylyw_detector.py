# -*- coding: utf-8 -*-
"""
ylyw_detector.py: 【检测器层】YLYW 连续爻变判据 vs 统计判据 —— 同口径对比
================================================================================
架构（按马老师最终定位）:
  图像 → 【传感器层】易理抽取器 + 六爻传感器 → (H,W,6) 六爻读数
       → 【检测器层】YLYW 模型：爻变运算(乘/承/比/应/当位得中) → 缺陷判定

本脚本聚焦【检测器层】的公平对比。所有检测器吃**同一份传感器输出**:
  - 六爻读数阵列 yhat(6) (来自六爻传感器, 见 six_sensors)
  - 逐位置 Welford 归一化 (0=正常) → 得到"偏离场" z(6)

对比的检测器:
  D1. welford-max  : 统计基线 —— 逐位置 |z| 取 max (无爻变关系)
  D2. mahalanobis  : 统计基线 —— z 的马氏范数 (含二阶相关)
  D3. ylyw-qual    : 原 YLYW 定性爻变 (YaoRelations, 硬阈值)
  D4. ylyw-cont    : 连续爻变算子 (比/乘/承/应/当位) —— 本文强化版
  D5. ylyw-fuse    : 连续爻变 + 马氏 融合

注: 为公平, 各检测器均在**同一 patch 网格**上取 max 池化做图像级分数。

用法:
  python ylyw_detector.py --cat bottle
  python ylyw_detector.py --all
"""
import os, sys, json, argparse, gc
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__))
YLYW_ROOT = os.path.dirname(BASE)
sys.path.insert(0, YLYW_ROOT)
sys.path.insert(0, os.path.join(YLYW_ROOT, "experiment_phase1"))

from ylyw_core.yao_relations import YaoRelations   # 原 YLYW 定性爻变

_rel = YaoRelations()
SIZE = 256
YANG_POS = {0, 2, 4}
YING_PAIRS = [(0, 3), (1, 4), (2, 5)]


# ---------------- 传感器层：六爻传感器 ----------------
def six_sensors(R):
    C, H, W = R.shape
    Rc = R.max(0)
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


# ---------------- 检测器层：连续爻变算子 ----------------
def yaobian_features(z6):
    """z6: 6 爻的带符号偏离 → 24 维连续爻变量。"""
    y = np.asarray(z6, np.float64)
    bi = np.abs(np.diff(y))
    cheng = np.maximum(y[:-1] - y[1:], 0)
    cheng_s = np.maximum(y[1:] - y[:-1], 0)
    ying = np.abs(np.array([y[a] - y[b] for a, b in YING_PAIRS]))
    dangwei = np.array([abs(y[i] - (1.0 if i in YANG_POS else -1.0)) for i in range(6)])
    return np.concatenate([bi, cheng, cheng_s, ying, dangwei])   # 24


def ylyw_qual(z6):
    """原 YLYW 定性爻变: 把带符号 z6 映射到 [0,1] 再走 YaoRelations, 返回失和度。"""
    v = 1.0 / (1.0 + np.exp(-np.asarray(z6, np.float64)))       # 软映射到 (0,1)
    rep = _rel.analyze(np.clip(v, 0, 1))
    s = np.array([rep.score_dangwei, rep.score_dezhong, rep.score_cheng_cheng,
                  rep.score_bi, rep.score_ying])
    return 1.0 - s.mean()      # 失和度 (越大越异常)


def load_gray(path, size=SIZE):
    im = Image.open(path).convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(im, np.float32) / 255.0


def load_cat(data, cat, split):
    d = os.path.join(data, cat, split); items = []
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


class Welford:
    def __init__(self, shp):
        self.n = 0; self.mean = np.zeros(shp, np.float64); self.M2 = np.zeros(shp, np.float64)
    def update(self, x):
        self.n += 1; d = x - self.mean; self.mean += d / self.n; self.M2 += d * (x - self.mean)
    @property
    def std(self):
        return np.sqrt(self.M2 / max(self.n - 1, 1))


def run_cat(data, cat, patch=64, stride=32, verbose=True):
    from sklearn.metrics import roc_auc_score
    tr = load_cat(data, cat, "train"); te = load_cat(data, cat, "test")
    if not tr or not te:
        return None

    g0 = load_gray(tr[0][0]); H, W = g0.shape
    Tg = Welford((H, W))
    for p, _ in tr:
        Tg.update(load_gray(p))
    mu = Tg.mean.astype(np.float32); sd = Tg.std.astype(np.float32) + 1e-3

    def sensor_patches(path):
        """→ (P,6) 六爻读数; (P,6) 带符号偏离 z; (P,24) 连续爻变量; (P,) 马氏."""
        g = load_gray(path)
        R = (g - mu) / sd
        R = ndimage.gaussian_filter(R, 2.0)
        yhat = six_sensors(R[None])                   # (H,W,6)
        ys = list(range(0, H - patch + 1, stride)) or [0]
        xs = list(range(0, W - patch + 1, stride)) or [0]
        raw = np.zeros((len(ys) * len(xs), 6), np.float32)
        z = np.zeros_like(raw); q = np.zeros((raw.shape[0], 24), np.float32)
        k = 0
        for yy in ys:
            for xx in xs:
                blk = yhat[yy:yy + patch, xx:xx + patch].reshape(-1, 6).mean(0)  # 带符号均值
                raw[k] = np.abs(blk)      # 读数 (幅值) —— 传感器"输出"
                z[k] = blk                # 带符号偏离 —— 送检测器
                q[k] = yaobian_features(blk)
                k += 1
        return raw, z, q

    # 学正常分布
    r0, z0, q0 = sensor_patches(tr[0][0]) if False else sensor_patches(tr[0][0])
    P = r0.shape[0]
    Wr = Welford((P, 6)); Wq = Welford((P, 24)); Wz = Welford((P, 6))
    for p, _ in tr:
        r, z, q = sensor_patches(p)
        if r.shape[0] != P:
            continue
        Wr.update(r); Wq.update(q); Wz.update(z); gc.collect()
    mr, sr = Wr.mean, Wr.std + 1e-6
    mq, sq = Wq.mean, Wq.std + 1e-6

    # 马氏: 用正常 z 的协方差 (对角加载)
    Zr = Wz.mean; cov = np.cov(np.random.randn(6, 6))  # placeholder
    # 重新收集正常 z 估计协方差
    Zs = []
    for p, _ in tr:
        _, z, _ = sensor_patches(p)
        if z.shape[0] == P:
            Zs.append(z)
    Zall = np.vstack(Zs) if Zs else np.zeros((1, 6))
    Cz = np.cov(Zall.T) + np.eye(6) * (0.1 * np.median(np.diag(np.cov(Zall.T))) + 1e-6)
    Cz_inv = np.linalg.pinv(Cz)

    keys = ["D1-welford", "D2-mahal", "D3-ylyw-qual", "D4-ylyw-cont", "D5-fuse"]
    sc = {k: [] for k in keys}; lab = []
    for p, d in te:
        r, z, q = sensor_patches(p)
        if r.shape[0] != P:
            for k in keys: sc[k].append(0.0)
            lab.append(0 if d == "good" else 1); continue
        d1 = np.abs((r - mr) / sr).max()
        d2 = np.sqrt(np.einsum("pi,ij,pj->p", z, Cz_inv, z)).max()
        d3 = np.array([ylyw_qual(zz) for zz in z]).max()
        d4 = np.abs((q - mq) / sq).max()
        d5 = max(d2, d4)
        sc["D1-welford"].append(float(d1)); sc["D2-mahal"].append(float(d2))
        sc["D3-ylyw-qual"].append(float(d3)); sc["D4-ylyw-cont"].append(float(d4))
        sc["D5-fuse"].append(float(d5))
        lab.append(0 if d == "good" else 1)
    lab = np.array(lab)
    out = {"cat": cat, "n_test": len(te)}
    for k in keys:
        out[k] = float(roc_auc_score(lab, sc[k])) if len(set(lab)) > 1 else None
    if verbose:
        print(f"[{cat:12s}] " + "  ".join(f"{k.split('-')[0]}={out[k]:.4f}" for k in keys))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--patch", type=int, default=64)
    ap.add_argument("--stride", type=int, default=32)
    ap.add_argument("--data", default="/home/lijinhan/MXL/mvtec_full")
    ap.add_argument("--out", default=os.path.join(BASE, "results", "ylyw_detector.json"))
    args = ap.parse_args()

    CATS = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
            "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
            "wood", "zipper"]
    cats = CATS if args.all else [args.cat] if args.cat else ["bottle"]
    res = []
    for c in cats:
        r = run_cat(args.data, c, args.patch, args.stride)
        if r: res.append(r)
    if res:
        keys = ["D1-welford", "D2-mahal", "D3-ylyw-qual", "D4-ylyw-cont", "D5-fuse"]
        avg = {k: float(np.mean([r[k] for r in res if r[k] is not None])) for k in keys}
        print(f"\n=== 平均 AUROC ({len(res)} 类) ===")
        for k in keys:
            print(f"  {k:14s}: {avg[k]:.4f}")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"per_cat": res, "avg": avg, "patch": args.patch, "stride": args.stride},
                  open(args.out, "w"), ensure_ascii=False, indent=2)
        print("saved:", args.out)


if __name__ == "__main__":
    main()
