#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v3, 真实数据, 方案C): 纯图像处理 + YLYW 易理加权
================================================================================
核心科学问题(方案C):
   在【同一套纯图像特征】输入下, 加易理先验(加权) vs 不加(无先验),
   异常检测性能提升多少? —— 干净地证明易理加权的价值。

v1/v2 教训:
  * v1: 全图统计特征 → 正常/异常不可分
  * v2: 分块统计, 但用"正常样本块间波动的90分位"作阈值 → excess≈0,
        被正常物体的形状/位置天然变化淹没。

v3 修正 —— 纯图像处理模板法(不依赖深度学习):
  1. 【正常模板】对齐后对正常样本取逐像素均值模板 T, 及逐像素标准差 S。
     (对 bottle, 先做简单对齐: 用前景质心+尺度归一, 避免位置漂移)
  2. 【残差图】对每张测试图: R(x) = |I(x) - T(x)| / (S(x)+eps)  逐像素标准化残差
  3. 【六爻编码】把残差图按 6 个区域/通道聚合成 6 爻倾向:
       初爻=整体残差均值   二爻=残差>阈值的面积占比
       三爻=残差峰值       四爻=残差纹理能量
       五爻=残差空间聚集度 六爻=残差方向一致性
     正常图 -> 六爻"当位"(残差小, 偏阳)
     异常图 -> 局部残差大 -> 对应爻"失位"(偏阴) -> 失和卦涌现
  4. 【易理加权】P(q) ∝ base(q)·exp(-λU(q))
  5. 对比: 同一 6 爻倾向 z 下, 易理加权 vs 纯观测(base) 的 AUROC。
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, transform, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)

# ---------------- 易理势能 ----------------
def yao(q,i): return (q>>i)&1
def U(q):
    bud = sum(1 for i in range(6) if yao(q,i)!=(1 if i%2==0 else 0))
    shz = 0 if yao(q,1)!=yao(q,4) else 1
    buy = sum(1 for a,b in [(0,3),(1,4),(2,5)] if yao(q,a)==yao(q,b))
    cg  = sum(1 for i in range(5) if yao(q,i)==1 and yao(q,i+1)==0)
    return bud+0.8*shz+0.6*buy+0.5*cg
ALL=list(range(64)); Uvals=np.array([U(q) for q in ALL]); Umin=Uvals.min()
ANOMALOUS=set(q for q in ALL if U(q)>=np.percentile(Uvals,75))
HARMONIC =set(q for q in ALL if U(q)<=np.percentile(Uvals,25))

def base_dist(z):
    p=1/(1+np.exp(-z)); p=np.clip(p,1e-6,1-1e-6)
    d=np.ones(64)
    for q in range(64):
        for i in range(6): d[q]*= p[i] if yao(q,i)==1 else (1-p[i])
    return d/d.sum()
def anomaly_mass(d): return float(sum(d[q] for q in ANOMALOUS))
def harmony_mass(d): return float(sum(d[q] for q in HARMONIC))
def ylyw_weighted(z, lam=0.9):
    d=base_dist(z); w=d*np.exp(-lam*(Uvals-Umin)); return w/w.sum()

# ---------------- 纯图像处理: 模板法 ----------------
SIZE = (160, 160)
def load_gray(path):
    im = io.imread(path)
    if im.ndim==3: g = color.rgb2gray(im)
    else: g = im.astype(float)
    g = (g - g.min())/(np.ptp(g)+1e-9)
    return resize(g, SIZE, anti_aliasing=True)

def build_template(paths):
    imgs = np.array([load_gray(p) for p in paths])
    T = imgs.mean(0)
    S = imgs.std(0)
    return T, S

def residual_features(g, T, S, eps=1e-3):
    """逐像素标准化残差 -> 6 爻特征。"""
    R = np.abs(g - T) / (S + eps)          # 标准化残差
    Rb = filters.gaussian(R, 2.0)          # 平滑, 抑制单像素噪声
    f = np.zeros(6)
    f[0] = float(np.clip(Rb.mean()/2.0, 0, 1))                       # 整体残差
    f[1] = float(np.clip((Rb > 2.0).mean()*10, 0, 1))                # 异常面积占比
    f[2] = float(np.clip(np.percentile(Rb, 99.5)/4.0, 0, 1))         # 峰值
    lap = np.abs(filters.laplace(Rb))
    f[3] = float(np.clip(lap.mean()*3, 0, 1))                        # 纹理能量
    # 空间聚集度: 残差高值区域的连通性(最大连通块占比)
    mask = Rb > 2.0
    if mask.any():
        lab = measure.label(mask)
        if lab.max() > 0:
            sizes = np.bincount(lab.ravel())[1:]
            f[4] = float(np.clip(sizes.max()/max(mask.sum(),1), 0, 1))  # 最大连通块/总异常
        else: f[4] = 0.0
    else: f[4] = 0.0
    # 方向一致性: 残差梯度主方向强度
    gy, gx = np.gradient(Rb)
    f[5] = float(np.clip(np.sqrt(gy**2+gx**2).mean()*3, 0, 1))
    return f, R

def z_from_features(f):
    """6爻特征 -> 6爻倾向 z。
    特征越大(残差越强) => 该爻越"失位"(阴, z负)。"""
    a = 1.2
    z = a - 2.2*f          # f∈[0,1] -> z 从 +1.2 降到 -1.0
    return z

# ---------------- 数据 ----------------
def load_split(cat, split):
    d=os.path.join(DATA,cat,split); items=[]
    if not os.path.isdir(d): return items
    for defect in sorted(os.listdir(d)):
        dd=os.path.join(d,defect)
        if not os.path.isdir(dd): continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png",".jpg",".jpeg",".bmp")):
                items.append((os.path.join(dd,f), defect))
    return items

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    print(f"类别={cat} train={len(train)} test={len(test)}")

    # 正常模板
    print("构建正常模板...")
    T, S = build_template([p for p,_ in train])
    print(f"  模板尺寸={T.shape}, 正常区域平均std={S.mean():.4f}")

    labels=[]; sc_obs=[]; sc_ylyw=[]; sc_raw=[]
    feats_by_def={}
    for p,d in test:
        g=load_gray(p)
        f,R=residual_features(g,T,S)
        z=z_from_features(f)
        sc_obs.append(anomaly_mass(base_dist(z)))
        sc_ylyw.append(anomaly_mass(ylyw_weighted(z)))
        sc_raw.append(float(R.mean()))          # 最朴素: 平均残差
        labels.append(0 if d=="good" else 1)
        feats_by_def.setdefault(d,[]).append(f)
    labels=np.array(labels)
    sc_obs=np.array(sc_obs); sc_ylyw=np.array(sc_ylyw); sc_raw=np.array(sc_raw)
    print(f"  测试: 正常={int((labels==0).sum())} 异常={int((labels==1).sum())}")

    r={}
    for nm,sc in [("C0_raw_residual",sc_raw),("C1_observation(no prior)",sc_obs),
                  ("C2_YLYW_weighted",sc_ylyw)]:
        try: r[nm]=float(roc_auc_score(labels,sc))
        except Exception: r[nm]=float("nan")
    print("="*64); print(f"MVTec {cat} 图像级 AUROC (v3, 方案C)"); print("="*64)
    for k,v in r.items(): print(f"  {k:26s} {v:.4f}")
    gain = r["C2_YLYW_weighted"]-r["C1_observation(no prior)"]
    print(f"  >>> 易理加权增益 (YLYW - 无先验) = {gain:+.4f}")
    print("="*64)

    # 各缺陷类型的平均特征(诊断易理编码)
    print("各缺陷的六爻特征均值:")
    for d,fs in feats_by_def.items():
        print(f"  {d:14s} {np.round(np.mean(fs,0),3)}")

    json.dump(dict(category=cat,n_train=len(train),n_test=len(test),
                   auroc=r,ylyw_gain=gain),
              open(os.path.join(RES,f"exp2_mvtec_{cat}_v3.json"),"w"),
              ensure_ascii=False,indent=2)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for ax,(nm,sc,key) in zip(axes,[("C0 raw residual",sc_raw,"C0_raw_residual"),
                                        ("C1 observation",sc_obs,"C1_observation(no prior)"),
                                        ("C2 YLYW weighted",sc_ylyw,"C2_YLYW_weighted")]):
            ax.hist(sc[labels==0],bins=18,alpha=.6,label="good",color="tab:green",density=True)
            ax.hist(sc[labels==1],bins=18,alpha=.6,label="defect",color="tab:red",density=True)
            ax.set_title(f"{nm}\nAUROC={r[key]:.3f}"); ax.legend(fontsize=8)
        fig.suptitle(f"MVTec AD ({cat}) v3 - pure image processing + YLYW")
        fig.tight_layout(); fig.savefig(os.path.join(FIG,f"exp2_mvtec_{cat}_v3.png"),dpi=140)
        print("saved figure")
    except Exception as e: print("plot skipped:",e)

if __name__=="__main__":
    main()
