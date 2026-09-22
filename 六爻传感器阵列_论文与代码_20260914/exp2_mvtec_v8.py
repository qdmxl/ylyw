#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8: 显著性检验 + 消融 —— 证明"初爻权重高(知几)"带来的是真实增益
================================================================================
* Bootstrap 置信区间: 初重 vs 上重 vs 等权 的 AUROC 差
* 消融: 去掉位置权重 / 去掉变爻指示 / 只保留单一爻位
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); RES=os.path.join(BASE,"results")
SIZE=(160,160); os.makedirs(RES,exist_ok=True)

def load_gray(path):
    im=io.imread(path)
    g=color.rgb2gray(im) if im.ndim==3 else im.astype(float)
    g=(g-g.min())/(np.ptp(g)+1e-9); return resize(g,SIZE,anti_aliasing=True)
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
    fb=np.array([(0b111111>>i)&1 for i in range(6)])
    Z=[]; labels=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); dev=(s-mu)/sd
        z=1.2-2.0*np.clip(dev,0,None); z=np.clip(z,-3.2,3.2)
        Z.append(z); labels.append(0 if d=="good" else 1)
    Z=np.array(Z); labels=np.array(labels)
    bits=(Z>0).astype(int); changed=(bits!=fb).astype(float); mag=np.abs(Z)

    w_low=np.array([2,1.5,1,1,0.5,0.5]); w_high=np.array([0.5,0.5,1,1,1.5,2.]); w_eq=np.ones(6)
    s_low=(changed*w_low*mag).sum(1); s_high=(changed*w_high*mag).sum(1); s_eq=(changed*w_eq*mag).sum(1)

    auc_low=roc_auc_score(labels,s_low); auc_high=roc_auc_score(labels,s_high); auc_eq=roc_auc_score(labels,s_eq)
    print(f"{cat}: AUROC  初重={auc_low:.4f}  上重={auc_high:.4f}  等权={auc_eq:.4f}")

    # Bootstrap 置信区间 (初重-上重)
    rng=np.random.default_rng(0); n=len(labels); B=2000
    diffs=[]
    for _ in range(B):
        idx=rng.integers(0,n,n)
        if len(np.unique(labels[idx]))<2: continue
        diffs.append(roc_auc_score(labels[idx],s_low[idx])-roc_auc_score(labels[idx],s_high[idx]))
    diffs=np.array(diffs)
    lo,hi=np.percentile(diffs,[2.5,97.5])
    print(f"  初重-上重 ΔAUROC = {auc_low-auc_high:+.4f}  95%CI=[{lo:+.4f},{hi:+.4f}]  {'显著(不含0)' if lo>0 or hi<0 else '不显著'}")

    # 单爻位消融
    print("  单爻位贡献(仅该爻变爻·幅度):")
    for i in range(6):
        sc=changed[:,i]*mag[:,i]
        try: a=roc_auc_score(labels,sc)
        except: a=float('nan')
        print(f"    第{i}爻(初->上): AUROC={a:.4f}")
    json.dump(dict(category=cat,auc_low=float(auc_low),auc_high=float(auc_high),
                   auc_eq=float(auc_eq),diff_low_high=float(auc_low-auc_high),
                   ci95=[float(lo),float(hi)]),
              open(os.path.join(RES,f"exp2_mvtec_{cat}_v8.json"),"w"),ensure_ascii=False,indent=2)

if __name__=="__main__": main()
