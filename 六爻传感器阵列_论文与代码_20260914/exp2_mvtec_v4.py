#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v4, 方案C定稿): 纯图像处理 + YLYW 易理加权
================================================================================
诊断结论(diag_features.py):
  残差"峰值"类特征区分力最强: max(AUROC .977) > p99.9(.973) > top50(.974)
  面积/连通类特征较弱。故六爻编码应以峰值类信号为主。

v4 设计:
  【六爻 = 六个残差统计量, 按信号强度排序对齐爻位】
    初爻 残差最大值      二爻 残差 p99.9      三爻 top50均值
    四爻 残差 p99        五爻 异常面积占比     六爻 连通块规模
  每个统计量 s_d 用正常样本标定 (mu_d, sd_d) -> 标准化偏离 dev_d=(s_d-mu_d)/sd_d
  爻倾向: z_d = a - b*clamp(dev_d, 0, ∞)  (偏离正常越大 -> 越"失位"/阴)

  易理加权: P(q) ∝ base(q)·exp(-λU(q))   —— 用"失和卦质量"作异常分数

  对比(同一 z 输入):
    C1 无先验: 异常分数 = Σ_{失和卦} base(q)
    C2 易理加权: 异常分数 = Σ_{失和卦} P(q)
    C3 最强单特征(参照上界): max残差
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES,FIG=os.path.join(BASE,"results"),os.path.join(BASE,"figures")
os.makedirs(RES,exist_ok=True); os.makedirs(FIG,exist_ok=True)
SIZE=(160,160)

# ---------------- 易理 ----------------
def yao(q,i): return (q>>i)&1
def U(q):
    bud=sum(1 for i in range(6) if yao(q,i)!=(1 if i%2==0 else 0))
    shz=0 if yao(q,1)!=yao(q,4) else 1
    buy=sum(1 for a,b in [(0,3),(1,4),(2,5)] if yao(q,a)==yao(q,b))
    cg=sum(1 for i in range(5) if yao(q,i)==1 and yao(q,i+1)==0)
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
def ylyw_weighted(z,lam=0.9):
    d=base_dist(z); w=d*np.exp(-lam*(Uvals-Umin)); return w/w.sum()

# ---------------- 图像 ----------------
def load_gray(path):
    im=io.imread(path)
    g=color.rgb2gray(im) if im.ndim==3 else im.astype(float)
    g=(g-g.min())/(np.ptp(g)+1e-9)
    return resize(g,SIZE,anti_aliasing=True)

def load_split(cat,split):
    d=os.path.join(DATA,cat,split); items=[]
    if not os.path.isdir(d): return items
    for defect in sorted(os.listdir(d)):
        dd=os.path.join(d,defect)
        if not os.path.isdir(dd): continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png",".jpg",".jpeg",".bmp")):
                items.append((os.path.join(dd,f),defect))
    return items

def stats6(g,T,S):
    """6 个残差统计量(按强度排序): max, p99.9, top50, p99, area, conn"""
    R=np.abs(g-T)/(S+1e-3); Rb=filters.gaussian(R,2.0)
    flat=np.sort(Rb.ravel())
    s=np.zeros(6)
    s[0]=Rb.max()
    s[1]=np.percentile(Rb,99.9)
    s[2]=flat[-50:].mean()
    s[3]=np.percentile(Rb,99.0)
    s[4]=(Rb>2.0).mean()
    m2=Rb>3.0
    if m2.any():
        lab=measure.label(m2); sizes=np.bincount(lab.ravel())[1:]
        s[5]=sizes.max() if len(sizes) else 0.0
    else: s[5]=0.0
    return s

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    print(f"类别={cat} train={len(train)} test={len(test)}")

    imgs=np.array([load_gray(p) for p,_ in train])
    T=imgs.mean(0); S=imgs.std(0)

    # 用正常训练样本标定 6 统计量的 mu/sd
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train])
    mu,sd=Str.mean(0),Str.std(0)+1e-9
    print(f"  正常统计量 mu={np.round(mu,3)}")
    print(f"             sd={np.round(sd,3)}")

    A_POS=1.2   # 完全正常 -> 阳(当位)
    B_NEG=1.0   # 偏离放大系数
    labels=[]; sc_obs=[]; sc_ylyw=[]; sc_max=[]
    for p,d in test:
        g=load_gray(p); s=stats6(g,T,S)
        dev=(s-mu)/sd
        # 只惩罚"正向偏离"(异常导致统计量升高)
        z=A_POS - B_NEG*np.clip(dev,0,None)
        z=np.clip(z,-3,3)
        sc_obs.append(anomaly_mass(base_dist(z)))
        sc_ylyw.append(anomaly_mass(ylyw_weighted(z)))
        sc_max.append(s[0])
        labels.append(0 if d=="good" else 1)
    labels=np.array(labels); sc_obs=np.array(sc_obs); sc_ylyw=np.array(sc_ylyw); sc_max=np.array(sc_max)

    r={}
    for nm,sc in [("C0_max_residual",sc_max),
                  ("C1_observation(no prior)",sc_obs),
                  ("C2_YLYW_weighted",sc_ylyw)]:
        r[nm]=float(roc_auc_score(labels,sc))
    print("="*66); print(f"MVTec {cat} 图像级 AUROC (v4 方案C)"); print("="*66)
    for k,v in r.items(): print(f"  {k:26s} {v:.4f}")
    gain=r["C2_YLYW_weighted"]-r["C1_observation(no prior)"]
    print(f"  >>> 易理加权增益 (YLYW - 无先验) = {gain:+.4f}")
    print("="*66)
    print(f"测试: 正常={int((labels==0).sum())} 异常={int((labels==1).sum())}")

    json.dump(dict(category=cat,n_train=len(train),n_test=len(test),
        n_normal=int((labels==0).sum()),n_anomaly=int((labels==1).sum()),
        auroc=r,ylyw_gain=gain),
        open(os.path.join(RES,f"exp2_mvtec_{cat}_v4.json"),"w"),
        ensure_ascii=False,indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(14,4.2))
        for ax,(nm,sc,key) in zip(axes,[("C0 max residual",sc_max,"C0_max_residual"),
                                        ("C1 observation",sc_obs,"C1_observation(no prior)"),
                                        ("C2 YLYW weighted",sc_ylyw,"C2_YLYW_weighted")]):
            ax.hist(sc[labels==0],bins=18,alpha=.6,label="good",color="tab:green",density=True)
            ax.hist(sc[labels==1],bins=18,alpha=.6,label="defect",color="tab:red",density=True)
            ax.set_title(f"{nm}\nAUROC={r[key]:.3f}"); ax.legend(fontsize=8)
        fig.suptitle(f"MVTec AD ({cat}) v4 - pure image processing + YLYW")
        fig.tight_layout(); fig.savefig(os.path.join(FIG,f"exp2_mvtec_{cat}_v4.png"),dpi=140)
        print("saved figure")
    except Exception as e: print("plot skipped:",e)

if __name__=="__main__": main()
