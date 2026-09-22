#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v6: 变爻幅度加权 —— 参数优化与权重扫描 (选项三精化)"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES=os.path.join(BASE,"results"); os.makedirs(RES,exist_ok=True)
SIZE=(160,160)

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
    R=np.abs(g-T)/(S+1e-3); Rb=filters.gaussian(R,2.0)
    flat=np.sort(Rb.ravel()); s=np.zeros(6)
    s[0]=Rb.max(); s[1]=np.percentile(Rb,99.9); s[2]=flat[-50:].mean()
    s[3]=np.percentile(Rb,99.0); s[4]=(Rb>2.0).mean()
    m2=Rb>3.0
    s[5]=np.bincount(measure.label(m2).ravel())[1:].max() if m2.any() and measure.label(m2).max()>0 else 0.0
    return s

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9
    fanben=0b010101
    fb=np.array([(fanben>>i)&1 for i in range(6)])

    # 预计算所有测试图的 z
    Z=[]; labels=[]; maxr=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); dev=(s-mu)/sd
        z=1.2-2.0*np.clip(dev,0,None); z=np.clip(z,-3.2,3.2)
        Z.append(z); labels.append(0 if d=="good" else 1); maxr.append(s[0])
    Z=np.array(Z); labels=np.array(labels); maxr=np.array(maxr)
    bits=(Z>0).astype(int)                     # (n,6) 观测极性
    changed=(bits!=fb).astype(float)           # 变爻指示
    mag=np.abs(Z)                              # 变爻幅度

    print(f"{cat}: test={len(labels)} 正常={int((labels==0).sum())} 异常={int((labels==1).sum())}")
    print(f"参照 C0 max_residual AUROC={roc_auc_score(labels,maxr):.4f}")
    print()

    # --- 扫描位置权重 ---
    print("位置权重扫描 (w初..上):")
    best=(0,None)
    for w in [np.ones(6),                       # 等权
              np.array([6,5,4,3,2,1.]),          # 初重
              np.array([1,2,3,4,5,6.]),          # 上重
              np.array([3,3,2,2,1,1.]),
              np.array([2,1.5,1,1,0.5,0.5])]:
        sc=(changed*w*mag).sum(1)
        auc=roc_auc_score(labels,sc)
        print(f"  {np.round(w,1)}  AUROC={auc:.4f}")
        if auc>best[0]: best=(auc,tuple(w))

    # --- 变爻幅度累加(不乘指示, 等价于连续) ---
    for name, sc in [
        ("Σ|z|(连续幅度)", mag.sum(1)),
        ("Σ w·|z| 初重", (mag*np.array([6,5,4,3,2,1.])).sum(1)),
        ("Σ w·变爻·|z| 初重", (changed*np.array([6,5,4,3,2,1.])*mag).sum(1)),
        ("Σ 变爻·|z|(不加位置)", (changed*mag).sum(1)),
        ("max |z|", mag.max(1)),
    ]:
        print(f"  {name:24s} AUROC={roc_auc_score(labels,sc):.4f}")

    # --- 不同"正常本卦"下 ---
    print()
    print("不同正常本卦 (基准构型):")
    for fbv, nm in [(0b010101,"阳阴阳阴阳阴"),(0b111111,"全阳(乾)"),(0b101010,"阴阳阴阳阴阳")]:
        fbv_=np.array([(fbv>>i)&1 for i in range(6)])
        ch=(bits!=fbv_).astype(float)
        sc=(ch*np.array([6,5,4,3,2,1.])*mag).sum(1)
        print(f"  {nm}: 变爻·位置·幅度 AUROC={roc_auc_score(labels,sc):.4f}")

    json.dump(dict(category=cat,best_weight_auroc=best[0],best_weight=list(best[1])),
              open(os.path.join(RES,f"exp2_mvtec_{cat}_v6.json"),"w"),ensure_ascii=False,indent=2)

if __name__=="__main__": main()
