# -*- coding: utf-8 -*-
"""
ylyw_sensor_input.py: 六爻传感器作为 YLYW 的输入前端 + YLYW 爻变运算判据
================================================================================
马老师指出的正确架构:
    图像 → 六爻传感器 (残差 → 六爻读数)   ← 这是给 YLYW 的【输入】, 不是"重构模块"
         → YLYW 模型 (爻变运算: 乘/承/比/应当位得中)  ← 判据核心
         → 缺陷判定

关键点: YLYW 模型利用【爻变运算】捕捉【细微波动】来判断缺陷。
  传感器把局部残差压成 6 个读数 (初..上), 其中"细微波动"体现为
  六爻之间的**相对关系**(谁压谁、相应不应、当位不当位)——
  这正是原始 YLYW 的 L3 爻位关系运算的用武之地。

对比方案:
  (A) raw6      : 直接用 6 个传感器读数 (标准化残差 max)         —— 基线
  (B) ylyw-rel  : 六爻读数 → YaoRelations → 关系评分异常度        —— YLYW 判据
  (C) fusion    : (A)+(B)

另: 把"细微波动"显式化 —— 传感器读数先做**逐位置 Welford 标准化**, 再送 YLYW,
    使 YLYW 看到的是"偏离正常的程度", 而非原始幅值。

用法:
  python ylyw_sensor_input.py --cat bottle
  python ylyw_sensor_input.py --all --patch 64 --stride 32
"""
import os, sys, json, argparse, gc
import numpy as np
from PIL import Image
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__))
YLYW_ROOT = os.path.dirname(BASE)
sys.path.insert(0, YLYW_ROOT)
sys.path.insert(0, os.path.join(YLYW_ROOT, "experiment_phase1"))

from ylyw_core.yao_relations import YaoRelations   # 原 YLYW 爻变运算

_rel = YaoRelations()
SIZE = 256


# ---------------- 六爻传感器 (来自主项目 exp31, 作为 YLYW 的输入前端) ----------------
def six_sensors(R):
    """R:(C,H,W) 残差场 → (H,W,6) 六爻读数阵列 (初..上)。"""
    C, H, W = R.shape
    Rc = R.max(0)
    bk = ndimage.uniform_filter(Rc, 7)
    Rc_tophat = np.maximum(Rc - bk, 0)
    out = np.zeros((H, W, 6), np.float32)
    out[..., 0] = Rc_tophat                                   # 初: 点/亮峰
    out[..., 1] = np.abs(ndimage.laplace(Rc_tophat))          # 二: 边缘
    gy, gx = np.gradient(Rc)
    out[..., 2] = np.sqrt(gy ** 2 + gx ** 2)                  # 三: 梯度
    out[..., 3] = R.std(0)                                    # 四: 通道离散
    out[..., 4] = Rc_tophat ** 2                              # 五: 强残差
    Bk = ndimage.uniform_filter(Rc ** 2, 5) - ndimage.uniform_filter(Rc, 5) ** 2
    out[..., 5] = np.sqrt(np.maximum(Bk, 0))                  # 上: 局部方差
    return out


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


def ylyw_rel_score(yao6):
    """六爻读数 → YLYW 爻变运算 → 关系异常度 (越小越正常)。
    我们把 6 个关系评分聚合成'失和度': 距离'理想和谐'越远越异常。
    理想和谐: 当位=1, 得中=1, 乘承=1, 比=1, 应=1 → overall=1
    """
    rep = _rel.analyze(np.clip(yao6, 0, 1))
    scores = np.array([rep.score_dangwei, rep.score_dezhong, rep.score_cheng_cheng,
                       rep.score_bi, rep.score_ying], np.float64)
    return scores, rep.score_overall, rep.cheng_count


def run_cat(data, cat, patch=64, stride=32, verbose=True):
    from sklearn.metrics import roc_auc_score
    tr = load_cat(data, cat, "train")
    te = load_cat(data, cat, "test")
    if not tr or not te:
        return None

    # --- 正常模板: 灰度 Welford (像素级) ---
    g0 = load_gray(tr[0][0]); H, W = g0.shape
    Tg = Welford((H, W))
    for p, _ in tr:
        Tg.update(load_gray(p))
    mu = Tg.mean.astype(np.float32); sd = Tg.std.astype(np.float32) + 1e-3

    # --- 正常六爻关系评分分布 (逐 patch 聚合) ---
    def rel_vec(path):
        g = load_gray(path)
        R = np.abs(g - mu) / sd
        R = ndimage.gaussian_filter(R, 2.0)
        yhat = six_sensors(R[None])          # (H,W,6)
        # 逐 patch 取 max 池化得到 6 读数
        C = yhat.shape[-1]
        ys = list(range(0, H - patch + 1, stride)) or [0]
        xs = list(range(0, W - patch + 1, stride)) or [0]
        raw6 = np.array([yhat[y:y+patch, x:x+patch].reshape(-1, C).max(0)
                         for y in ys for x in xs], np.float32)      # (P,6)
        # 每个 patch → YLYW 关系评分
        rels = np.array([ylyw_rel_score(raw6[k])[0] for k in range(len(raw6))], np.float32)
        return raw6, rels

    raw0, rel0 = rel_vec(tr[0][0]); P = raw0.shape[0]
    Wr = Welford((P, 6)); Ws = Welford((P, 5))
    for p, _ in tr:
        raw6, rels = rel_vec(p)
        if raw6.shape[0] != P:
            continue
        Wr.update(raw6); Ws.update(rels)
        gc.collect()
    mr, sr = Wr.mean, Wr.std + 1e-6
    ms, ss = Ws.mean, Ws.std + 1e-6

    keys = ["raw6", "ylyw-rel", "fusion"]
    sc = {k: [] for k in keys}; lab = []
    for p, d in te:
        raw6, rels = rel_vec(p)
        if raw6.shape[0] != P:
            for k in keys: sc[k].append(0.0)
            lab.append(0 if d == "good" else 1); continue
        zr = np.abs((raw6 - mr) / sr)          # 传感器读数异常度
        zs = np.abs((rels - ms) / ss)          # 爻变关系异常度
        sc["raw6"].append(float(zr.max()))
        sc["ylyw-rel"].append(float(zs.max()))
        sc["fusion"].append(float(max(zr.max(), zs.max())))
        lab.append(0 if d == "good" else 1)
    lab = np.array(lab)
    out = {"cat": cat, "patch": patch, "stride": stride, "n_test": len(te)}
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
    ap.add_argument("--out", default=os.path.join(BASE, "results", "ylyw_sensor_input.json"))
    args = ap.parse_args()

    CATS = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
            "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
            "wood", "zipper"]
    cats = CATS if args.all else [args.cat] if args.cat else ["bottle"]
    res = []
    for c in cats:
        r = run_cat(args.data, c, args.patch, args.stride)
        if r:
            res.append(r)
    if res:
        avg = {k: float(np.mean([r[k] for r in res if r[k] is not None]))
               for k in ["raw6", "ylyw-rel", "fusion"]}
        print(f"\n=== 平均 AUROC ({len(res)} 类) ===")
        for k, v in avg.items():
            print(f"  {k:10s}: {v:.4f}")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"per_cat": res, "avg": avg, "patch": args.patch, "stride": args.stride},
                  open(args.out, "w"), ensure_ascii=False, indent=2)
        print("saved:", args.out)


if __name__ == "__main__":
    main()
