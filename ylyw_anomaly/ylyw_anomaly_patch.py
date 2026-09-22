# -*- coding: utf-8 -*-
"""
ylyw_anomaly_patch.py: 用原 YLYW 模型做**逐 patch** 异常检测 (无监督)
================================================================================
动机: ylyw_anomaly.py 用**全图**6维视觉特征, 是图像级统计量, 对缺陷定位不敏感
(AUROC~0.66)。本脚本改为把图像切 patch, 每个 patch 走同一套 YLYW 管线:
    patch → VisualFeatureExtractor(6维) → 六爻 → 承乘比应评分
然后在 patch 网格上取最大残差作图像级分数 (与六爻传感器阵列同一范式)。

对比 diag:
  (a) feat-resid : patch 6维视觉特征残差
  (b) yao-resid  : patch 六爻残差
  (c) chengcheng : patch 乘承比应关系评分残差
  (d) fusion     : 拼接

用法:
  python ylyw_anomaly_patch.py --cat bottle --stride 32 --patch 64
  python ylyw_anomaly_patch.py --all
"""
import os, sys, json, argparse, gc
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
YLYW_ROOT = os.path.dirname(BASE)
sys.path.insert(0, YLYW_ROOT)
sys.path.insert(0, os.path.join(YLYW_ROOT, "experiment_phase1"))

from vision.feature_extractor_vision import VisualFeatureExtractor       # noqa: E402
from vision.trigram_base_vision import VisualTrigramBase, FEATURE_NAMES  # noqa: E402
from vision.yao_encoder_vision import VisualYaoEncoder                   # noqa: E402
from ylyw_core.yao_relations import YaoRelations                         # noqa: E402

SIZE = 256
_fe = VisualFeatureExtractor()
_tb = VisualTrigramBase()
_ye = VisualYaoEncoder()
_rel = YaoRelations()


def load_img(path, size=SIZE):
    im = Image.open(path).convert("RGB").resize((size, size), Image.BILINEAR)
    return np.asarray(im, dtype=np.uint8)


def patch_descriptors(img, patch, stride):
    """滑窗 → patches; 每 patch 出 (6维特征, 6爻, 关系6评分)。"""
    H, W = img.shape[:2]
    F, Y, S = [], [], []
    ys = list(range(0, H - patch + 1, stride))
    xs = list(range(0, W - patch + 1, stride))
    if not ys or not xs:
        ys, xs = [0], [0]
    for y in ys:
        for x in xs:
            p = img[y:y + patch, x:x + patch]
            vf = _fe.extract(p)
            f6 = np.array([vf[n] for n in FEATURE_NAMES], np.float64)
            yao = _ye.encode(vf).astype(np.float64)
            rep = _rel.analyze(yao)
            sc = np.array([rep.score_overall, rep.score_dangwei, rep.score_dezhong,
                           rep.score_cheng_cheng, rep.score_bi, rep.score_ying], np.float64)
            F.append(f6); Y.append(yao); S.append(sc)
    return np.array(F), np.array(Y), np.array(S), len(ys), len(xs)


class Welford:
    def __init__(self, d):
        self.n = 0; self.mean = np.zeros(d, np.float64); self.M2 = np.zeros(d, np.float64)
    def update(self, x):
        self.n += 1; d = x - self.mean; self.mean += d / self.n; self.M2 += d * (x - self.mean)
    @property
    def std(self):
        return np.sqrt(self.M2 / max(self.n - 1, 1))


def load_split(data, cat, split):
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


def run_cat(data, cat, patch=64, stride=32, verbose=True, max_train=40):
    from sklearn.metrics import roc_auc_score
    tr = load_split(data, cat, "train")
    te = load_split(data, cat, "test")
    if not tr or not te:
        return None

    # 学 patch 正常分布 (每个空间位置独立 Welford: 用第一次图像的网格形状)
    img0 = load_img(tr[0][0])
    F0, Y0, S0, ny, nx = patch_descriptors(img0, patch, stride)
    C = ny * nx
    WF = Welford((C, 6)); WY = Welford((C, 6)); WS = Welford((C, 6))
    for i, (p, _) in enumerate(tr[:max_train]):
        F, Y, S, _, _ = patch_descriptors(load_img(p), patch, stride)
        if len(F) != C:
            continue
        WF.update(F); WY.update(Y); WS.update(S)
        if (i + 1) % 10 == 0:
            gc.collect()
    muf, sdf = WF.mean, WF.std + 1e-6
    muy, sdy = WY.mean, WY.std + 1e-6
    mus, sds = WS.mean, WS.std + 1e-6

    keys = ["feat", "yao", "chengcheng", "fusion"]
    sc = {k: [] for k in keys}; lab = []
    for p, d in te:
        F, Y, S, _, _ = patch_descriptors(load_img(p), patch, stride)
        if len(F) != C:
            sc["feat"].append(0.0); sc["yao"].append(0.0)
            sc["chengcheng"].append(0.0); sc["fusion"].append(0.0)
            lab.append(0 if d == "good" else 1); continue
        rf = np.abs((F - muf) / sdf)
        ry = np.abs((Y - muy) / sdy)
        rs = np.abs((S - mus) / sds)
        sc["feat"].append(float(rf.max()))
        sc["yao"].append(float(ry.max()))
        sc["chengcheng"].append(float(rs.max()))
        sc["fusion"].append(float(np.concatenate([rf, ry, rs], 1).max()))
        lab.append(0 if d == "good" else 1)
    lab = np.array(lab)
    out = {"cat": cat, "patch": patch, "stride": stride, "n_train": len(tr), "n_test": len(te)}
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
    ap.add_argument("--out", default=os.path.join(BASE, "results", "ylyw_anomaly_patch.json"))
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
               for k in ["feat", "yao", "chengcheng", "fusion"]}
        print(f"\n=== 平均 AUROC ({len(res)} 类, patch={args.patch}, stride={args.stride}) ===")
        for k, v in avg.items():
            print(f"  {k:12s}: {v:.4f}")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"per_cat": res, "avg": avg, "patch": args.patch, "stride": args.stride},
                  open(args.out, "w"), ensure_ascii=False, indent=2)
        print("saved:", args.out)


if __name__ == "__main__":
    main()
