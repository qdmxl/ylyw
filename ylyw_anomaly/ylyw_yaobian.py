# -*- coding: utf-8 -*-
"""
ylyw_yaobian.py: 连续爻变算子 —— 让 YLYW 能捕捉"细微波动"
================================================================================
问题: 原 YaoRelations 用硬阈值 0.5 判定阴阳, 只保留"符号", 丢弃幅值。
      实测: yao=[0.51,0.49,...] 与 [0.90,0.10,...] 评分完全相同 → 无法捕捉细微波动。

马老师的洞见: YLYW 应利用【爻变运算】捕捉【细微波动】判断缺陷。
→ 因此需要把 乘/承/比/应 从"定性"升级为"定量(连续)"形式:

  设 6 爻读数为 y_0..y_5 ∈ R (已逐位置标准化, 0=正常均值)。

  ● 比 (相邻关系)   : 相邻爻之差的连续度量
        B_i = |y_{i+1} - y_i|          (相邻波动; 缺陷常在相邻爻间出现突变)
  ● 乘/承 (上下压制) : 方向性不对称项
        C_i = max(y_i - y_{i+1}, 0)    (下强上弱=乘, 逆)
        Ch_i= max(y_{i+1} - y_i, 0)    (下弱上强=承, 顺)
  ● 应 (初-四/二-五/三-上) : 远程呼应之差
        Y_j = |y_{u_j} - y_{l_j}|      (三对应位的失谐)
  ● 当位 (奇偶位阴阳失配) : 与理想阴阳符号的偏离
        D_i = |y_i - s_i|,  s_i=+1(阳位期望) / -1(阴位期望)

  全部为连续量, 对细微波动敏感; 缺陷 = 这些关系量的异常增大。

判据(无监督): 学正常图上每个爻变量的 Welford 分布, 测试取标准化 max。

对比:
  raw6     : 6 个传感器读数残差 (基线)
  ylyw-cont: 连续爻变算子 (本文强化 YLYW)
  fusion   : 拼接

用法:
  python ylyw_yaobian.py --cat bottle
  python ylyw_yaobian.py --all
"""
import os, sys, json, argparse, gc
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__))
YLYW_ROOT = os.path.dirname(BASE)
sys.path.insert(0, YLYW_ROOT)
sys.path.insert(0, os.path.join(YLYW_ROOT, "experiment_phase1"))

SIZE = 256
YANG_POS = {0, 2, 4}       # 初/三/五 为阳位
YING_PAIRS = [(0, 3), (1, 4), (2, 5)]   # 初-四/二-五/三-上


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


def yaobian_features(yao6):
    """连续爻变算子: 输入 6 爻(可正可负, 已标准化) → 关系特征向量。

    注意: 这里 yao6 是**偏离正常均值的方向**(带符号), 不再是 [0,1]。
    """
    y = np.asarray(yao6, np.float64)
    bi = np.abs(np.diff(y))                          # 比: 相邻波动 (5)
    cheng = np.maximum(y[:-1] - y[1:], 0)            # 乘 (5)
    cheng_s = np.maximum(y[1:] - y[:-1], 0)          # 承 (5)
    ying = np.abs(np.array([y[a] - y[b] for a, b in YING_PAIRS]))  # 应 (3)
    dangwei = np.array([abs(y[i] - (1.0 if i in YANG_POS else -1.0))
                        for i in range(6)])          # 当位失配 (6)
    return np.concatenate([bi, cheng, cheng_s, ying, dangwei])     # 24


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
    tr = load_cat(data, cat, "train")
    te = load_cat(data, cat, "test")
    if not tr or not te:
        return None

    g0 = load_gray(tr[0][0]); H, W = g0.shape
    Tg = Welford((H, W))
    for p, _ in tr:
        Tg.update(load_gray(p))
    # 模板: 均值 + 标准差 (像素级). yao 用"标准化偏离"(带符号) → 天然以 0 为中心
    mu = Tg.mean.astype(np.float32); sd = Tg.std.astype(np.float32) + 1e-3

    def patches(path):
        g = load_gray(path)
        R = (g - mu) / sd                              # 带符号! 不再是 |·|
        R = ndimage.gaussian_filter(R, 2.0)
        yhat = six_sensors(R[None])                    # (H,W,6)
        ys = list(range(0, H - patch + 1, stride)) or [0]
        xs = list(range(0, W - patch + 1, stride)) or [0]
        raw, rel = [], []
        for yy in ys:
            for xx in xs:
                blk = yhat[yy:yy+patch, xx:xx+patch].reshape(-1, 6).mean(0)  # 用均值(带符号)保细微
                raw.append(blk)
                rel.append(yaobian_features(blk))
        return np.array(raw, np.float32), np.array(rel, np.float32)

    r0, q0 = patches(tr[0][0]); P = r0.shape[0]
    Wr = Welford((P, 6)); Wq = Welford((P, 24))
    for p, _ in tr:
        r, q = patches(p)
        if r.shape[0] != P:
            continue
        Wr.update(r); Wq.update(q); gc.collect()
    mr, sr = Wr.mean, Wr.std + 1e-6
    mq, sq = Wq.mean, Wq.std + 1e-6

    keys = ["raw6", "ylyw-cont", "fusion"]
    sc = {k: [] for k in keys}; lab = []
    for p, d in te:
        r, q = patches(p)
        if r.shape[0] != P:
            for k in keys: sc[k].append(0.0)
            lab.append(0 if d == "good" else 1); continue
        zr = np.abs((r - mr) / sr)
        zq = np.abs((q - mq) / sq)
        sc["raw6"].append(float(zr.max()))
        sc["ylyw-cont"].append(float(zq.max()))
        sc["fusion"].append(float(max(zr.max(), zq.max())))
        lab.append(0 if d == "good" else 1)
    lab = np.array(lab)
    out = {"cat": cat, "n_test": len(te)}
    for k in keys:
        out[k] = float(roc_auc_score(lab, sc[k])) if len(set(lab)) > 1 else None
    if verbose:
        print(f"[{cat:12s}] " + "  ".join(f"{k}={out[k]:.4f}" for k in keys))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--patch", type=int, default=64)
    ap.add_argument("--stride", type=int, default=32)
    ap.add_argument("--data", default="/home/lijinhan/MXL/mvtec_full")
    ap.add_argument("--out", default=os.path.join(BASE, "results", "ylyw_yaobian.json"))
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
        avg = {k: float(np.mean([r[k] for r in res if r[k] is not None]))
               for k in ["raw6", "ylyw-cont", "fusion"]}
        print(f"\n=== 平均 AUROC ({len(res)} 类) ===")
        for k, v in avg.items():
            print(f"  {k:10s}: {v:.4f}")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"per_cat": res, "avg": avg, "patch": args.patch, "stride": args.stride},
                  open(args.out, "w"), ensure_ascii=False, indent=2)
        print("saved:", args.out)


if __name__ == "__main__":
    main()
