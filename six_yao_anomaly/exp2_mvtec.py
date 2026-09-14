#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(真实数据): MVTec AD 上的 YLYW 易理加权异常检测
================================================================================
任务: 无监督工业异常检测(MVTec AD 标准范式)
  - 训练集只有 good(正常) 样本 -> 建立"正常卦象"统计基线
  - 测试集含 good + 各类缺陷 -> 检测异常

流程(CNN特征 -> 六爻 -> 易理加权 -> 异常分数):
  1. 图像特征提取: 对每张图提取可解释的局部特征(亮度/纹理/边缘/颜色)网格
  2. 六爻模糊编码: 把特征偏离正常基线的程度映射为 6 爻倾向 z ∈ R^6
     - 每一爻对应一类"象"(整体/局部/结构/纹理/色偏/边缘)
  3. 卦象似然: base(q) = 六爻独立伯努利乘积
  4. 易理加权: P(q) = base(q)·exp(-λU(q))/Z
  5. 异常分数: 多种定义比较
     S_ylyw = 失和卦质量 = Σ_{q∈ANOMALOUS} P(q)
     S_base = Σ_{q∈ANOMALOUS} base(q)         (无易理先验基线)

对比基线:
  B1 观测法: 直接 base 分布的失和卦质量
  B2 马氏距离: 特征偏离正常均值的马氏距离(经典 AD 常用)
  B3 易理加权(本方法)

指标: 图像级 AUROC (MVTec 标准指标)
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, feature
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from gua_order import BAGUA

DATA = os.path.join(BASE, "data", "mvtec")
RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)

# ---------------- 易理势能 ----------------
def yao(q, i): return (q >> i) & 1
def U(q):
    bud = sum(1 for i in range(6) if yao(q, i) != (1 if i % 2 == 0 else 0))
    shz = 0 if yao(q, 1) != yao(q, 4) else 1
    buy = sum(1 for a, b in [(0,3),(1,4),(2,5)] if yao(q, a) == yao(q, b))
    cg  = sum(1 for i in range(5) if yao(q, i) == 1 and yao(q, i+1) == 0)
    return bud + 0.8*shz + 0.6*buy + 0.5*cg
ALL = list(range(64))
Uvals = np.array([U(q) for q in ALL]); Umin = Uvals.min()
ANOMALOUS = set(q for q in ALL if U(q) >= np.percentile(Uvals, 75))

# ---------------- 特征提取 ----------------
def extract_features(img_path, size=(128, 128)):
    """提取 6 维可解释特征(对应六爻之"象"):
      0 整体亮度均值     1 局部对比度(局部方差)
      2 纹理粗糙度(Laplacian能量)  3 边缘密度(Sobel)
      4 色度偏移(饱和度偏离)  5 结构不规则度(区域熵)"""
    im = io.imread(img_path)
    if im.ndim == 3:
        gray = color.rgb2gray(im)
        hsv = color.rgb2hsv(im)
        sat = hsv[..., 1]
    else:
        gray = im.astype(float); gray = (gray-gray.min())/(gray.ptp()+1e-9)
        sat = np.zeros_like(gray)
    gray = resize(gray, size, anti_aliasing=True)
    sat = resize(sat, size, anti_aliasing=True)

    f0 = float(gray.mean())
    f1 = float(filters.rank.entropy((gray*255).astype(np.uint8), np.ones((5,5))).mean()/8.0) if gray.size else 0.0
    lap = filters.laplace(gray)
    f2 = float(np.abs(lap).mean())
    sob = filters.sobel(gray)
    f3 = float(sob.mean())
    f4 = float(sat.mean())
    # 区域熵(把图分4x4, 各块方差 -> 熵)
    h, w = gray.shape
    blocks = [gray[i*h//4:(i+1)*h//4, j*w//4:(j+1)*w//4] for i in range(4) for j in range(4)]
    vars_ = np.array([b.var() for b in blocks])
    p = vars_/(vars_.sum()+1e-9)
    f5 = float(-(p*np.log(p+1e-9)).sum()/np.log(len(p)))
    return np.array([f0, f1, f2, f3, f4, f5])

# ---------------- 六爻编码(相对正常基线的偏离) ----------------
def z_from_features(feat, normal_stats):
    """把特征映射为六爻倾向 z: 偏离正常均值越多, |z| 越大(趋向"失和")"""
    mu, sd = normal_stats["mu"], normal_stats["sd"] + 1e-9
    dev = (feat - mu) / sd            # 标准化偏离
    # 偏离 => 推向"异常极性": 阳(Normal高)或阴(Normal低)均视为失和
    z = -np.abs(dev) * 1.5            # 越小=越偏离正常 => 越趋向阴(失位)
    return z

def base_dist(z):
    p = 1/(1+np.exp(-z)); p = np.clip(p, 1e-6, 1-1e-6)
    d = np.ones(64)
    for q in range(64):
        for i in range(6):
            d[q] *= p[i] if yao(q, i) == 1 else (1-p[i])
    return d/d.sum()

def anomaly_mass(dist): return float(sum(dist[q] for q in ANOMALOUS))
def ylyw_weighted(z, lam=0.9):
    d = base_dist(z); w = d*np.exp(-lam*(Uvals-Umin)); return w/w.sum()

# ---------------- 数据加载 ----------------
def load_split(cat, split):
    d = os.path.join(DATA, cat, split)
    if not os.path.isdir(d): return []
    items = []
    for defect in sorted(os.listdir(d)):
        dd = os.path.join(d, defect)
        if not os.path.isdir(dd): continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                items.append((os.path.join(dd, f), defect))
    return items

def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else "bottle"
    train = load_split(cat, "train")
    test  = load_split(cat, "test")
    if not train or not test:
        print(f"数据缺失: train={len(train)} test={len(test)}, 目录={DATA}/{cat}")
        return
    print(f"类别={cat}  train(正常)={len(train)}  test={len(test)}")

    # 1) 正常基线
    print("提取训练集特征...")
    Ftrain = np.array([extract_features(p) for p, _ in train])
    mu, sd = Ftrain.mean(0), Ftrain.std(0)
    stats = dict(mu=mu, sd=sd)
    print(f"  正常特征均值={np.round(mu,3)}  std={np.round(sd,3)}")

    # 2) 测试集打分
    print("测试集打分...")
    scores_y, scores_b = [], []
    labels = []
    for p, defect in test:
        f = extract_features(p)
        z = z_from_features(f, stats)
        scores_b.append(anomaly_mass(base_dist(z)))
        scores_y.append(anomaly_mass(ylyw_weighted(z)))
        labels.append(0 if defect == "good" else 1)
    labels = np.array(labels)
    scores_b = np.array(scores_b); scores_y = np.array(scores_y)
    print(f"  测试集: 正常={int((labels==0).sum())} 异常={int((labels==1).sum())}")

    # 3) AUROC
    r = {}
    try: r["B1_observation"] = float(roc_auc_score(labels, scores_b))
    except Exception: r["B1_observation"] = float("nan")
    try: r["B3_ylyw_weighted"] = float(roc_auc_score(labels, scores_y))
    except Exception: r["B3_ylyw_weighted"] = float("nan")
    # 马氏距离基线
    Ftest = np.array([extract_features(p) for p, _ in test])
    cov = np.cov(Ftrain.T) + np.eye(Ftrain.shape[1])*1e-6
    inv = np.linalg.inv(cov)
    maha = np.array([float(np.sqrt(max(0,(f-mu)@inv@(f-mu)))) for f in Ftest])
    try: r["B2_mahalanobis"] = float(roc_auc_score(labels, maha))
    except Exception: r["B2_mahalanobis"] = float("nan")

    print("="*60); print(f"MVTec {cat} 图像级 AUROC"); print("="*60)
    for k, v in r.items(): print(f"  {k:20s} {v:.4f}")
    print("="*60)

    out = dict(category=cat, n_train=len(train), n_test=len(test),
               n_normal=int((labels==0).sum()), n_anomaly=int((labels==1).sum()),
               auroc=r)
    with open(os.path.join(RES, f"exp2_mvtec_{cat}.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 画图: 分数分布
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for ax, (nm, sc) in zip(axes, [("B1 observation", scores_b), ("B3 YLYW weighted", scores_y)]):
            ax.hist(sc[labels == 0], bins=20, alpha=.6, label="good", color="tab:green", density=True)
            ax.hist(sc[labels == 1], bins=20, alpha=.6, label="defect", color="tab:red", density=True)
            auc = r["B1_observation"] if nm.startswith("B1") else r["B3_ylyw_weighted"]
            ax.set_title(f"{nm}\nAUROC={auc:.3f}"); ax.legend(fontsize=8)
            ax.set_xlabel("anomaly score")
        fig.suptitle(f"MVTec AD ({cat}) - anomaly score distribution")
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, f"exp2_mvtec_{cat}.png"), dpi=140)
        print(f"saved figures/exp2_mvtec_{cat}.png")
    except Exception as e:
        print("plot skipped:", e)

if __name__ == "__main__":
    main()
