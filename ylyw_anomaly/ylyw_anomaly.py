# -*- coding: utf-8 -*-
"""
ylyw_anomaly: 用原 YLYW 模型做图像异常检测 (无监督)
================================================================================
核心思路: 不新造抽取器, 而是**直接复用 YLYW 原有的视觉管线**:
    图像 → VisualFeatureExtractor (6维视觉特征: 纹理均匀度/边缘清晰度/...)
         → VisualTrigramBase (L1: 8 卦隶属度)
         → VisualYaoEncoder   (L2: 六爻向量)
         → YaoRelations       (L3: 乘承比应当位得中 → 关系评分)

异常检测改造 (无监督, 仅用 train/good):
  1. 正常模板: 6维视觉特征 + 6爻向量 + 八卦隶属度 的 Welford 均值/方差
  2. 残差: r = |f(x) - μ| / σ   (在 6 维特征 / 6 爻 / 8 卦 三个层面)
  3. 判据组合 (对比不同方案):
     (a) feat-resid : 6维视觉特征残差
     (b) yao-resid  : 六爻向量残差
     (c) bagua-resid: 八卦隶属度残差
     (d) chengcheng : YaoRelations 关系评分 (乘承比应当位得中) 的异常度
     (e) fusion     : 上述拼接
  4. 打分: 标准化残差取 max (图像级 AUROC)

用法:
    python ylyw_anomaly.py --cat bottle --data /home/lijinhan/MXL/mvtec_full
    python ylyw_anomaly.py --all --data /home/lijinhan/MXL/mvtec_full
"""
import os, sys, json, argparse, gc
import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
YLYW_ROOT = os.path.dirname(BASE)
sys.path.insert(0, YLYW_ROOT)
sys.path.insert(0, os.path.join(YLYW_ROOT, "experiment_phase1"))

# --- 复用原 YLYW 模型组件 ---
from vision.feature_extractor_vision import VisualFeatureExtractor          # noqa: E402
from vision.trigram_base_vision import VisualTrigramBase, FEATURE_NAMES     # noqa: E402
from vision.yao_encoder_vision import VisualYaoEncoder                      # noqa: E402
from ylyw_core.yao_relations import YaoRelations                            # noqa: E402

SIZE = 256
_fe = VisualFeatureExtractor()
_tb = VisualTrigramBase()
_ye = VisualYaoEncoder()
_rel = YaoRelations()


def load_img(path, size=SIZE):
    im = Image.open(path).convert("RGB")
    im = im.resize((size, size), Image.BILINEAR)
    return np.asarray(im, dtype=np.uint8)


def img_descriptors(path):
    """一张图 → (6维视觉特征, 6爻向量, 8卦隶属度, 乘承比应评分字典)。"""
    img = load_img(path)
    vf = _fe.extract(img)                                   # dict
    f6 = np.array([vf[n] for n in FEATURE_NAMES], np.float64)
    yao = _ye.encode(vf).astype(np.float64)                 # (6,)
    memb = _tb.get_all_memberships(vf).astype(np.float64)   # (8,)
    rep = _rel.analyze(yao)
    scores = np.array([
        rep.score_overall, rep.score_dangwei, rep.score_dezhong,
        rep.score_cheng_cheng, rep.score_bi, rep.score_ying,
    ], np.float64)
    return f6, yao, memb, scores


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


def run_cat(data, cat, verbose=True):
    from sklearn.metrics import roc_auc_score
    tr = load_split(data, cat, "train")
    te = load_split(data, cat, "test")
    if not tr or not te:
        return None

    # ---- 学正常模板 (三个层面 + 关系评分) ----
    Tf, Ty, Tm, Ts = Welford(6), Welford(6), Welford(8), Welford(6)
    for i, (p, _) in enumerate(tr):
        f6, yao, memb, sc = img_descriptors(p)
        Tf.update(f6); Ty.update(yao); Tm.update(memb); Ts.update(sc)
        if (i + 1) % 20 == 0:
            gc.collect()
    muf, sdf = Tf.mean, Tf.std + 1e-6
    muy, sdy = Ty.mean, Ty.std + 1e-6
    mum, sdm = Tm.mean, Tm.std + 1e-6
    mus, sds = Ts.mean, Ts.std + 1e-6

    # ---- 测试打分 ----
    names = ["feat", "yao", "bagua", "chengcheng", "fusion"]
    sc = {k: [] for k in names}
    lab = []
    for p, d in te:
        f6, yao, memb, s = img_descriptors(p)
        rf = np.abs((f6 - muf) / sdf)
        ry = np.abs((yao - muy) / sdy)
        rm = np.abs((memb - mum) / sdm)
        rs = np.abs((s - mus) / sds)
        sc["feat"].append(float(rf.max()))
        sc["yao"].append(float(ry.max()))
        sc["bagua"].append(float(rm.max()))
        sc["chengcheng"].append(float(rs.max()))
        sc["fusion"].append(float(np.concatenate([rf, ry, rm, rs]).max()))
        lab.append(0 if d == "good" else 1)
    lab = np.array(lab)

    out = {"cat": cat, "n_train": len(tr), "n_test": len(te), "n_defect": int(lab.sum())}
    for k in names:
        out[k] = float(roc_auc_score(lab, sc[k])) if len(set(lab)) > 1 else None
    if verbose:
        s = "  ".join(f"{k}={out[k]:.4f}" for k in names if out[k] is not None)
        print(f"[{cat:12s}] {s}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--data", default="/home/lijinhan/MXL/mvtec_full")
    ap.add_argument("--out", default=os.path.join(BASE, "results", "ylyw_anomaly.json"))
    args = ap.parse_args()

    CATS = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
            "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
            "wood", "zipper"]
    cats = CATS if args.all else [args.cat] if args.cat else ["bottle"]
    res = []
    for c in cats:
        r = run_cat(args.data, c)
        if r:
            res.append(r)
    if res:
        avg = {k: float(np.mean([r[k] for r in res if r[k] is not None]))
               for k in ["feat", "yao", "bagua", "chengcheng", "fusion"]}
        print("\n=== 平均 AUROC ({}) ===".format(len(res)))
        for k, v in avg.items():
            print(f"  {k:12s}: {v:.4f}")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump({"per_cat": res, "avg": avg}, open(args.out, "w"),
                  ensure_ascii=False, indent=2)
        print("saved:", args.out)


if __name__ == "__main__":
    main()
