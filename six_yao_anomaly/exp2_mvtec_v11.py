#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v11: 路径2 的显著性检验 (bootstrap CI) + 逐爻位消融"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); RES=os.path.join(BASE,"results")
SIZE=(160,160); FANBEN=[1,0,1,0,1,0]

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
def z_of(s,mu,sd):
    dev=(s-mu)/sd; return np.clip(1.2-2.0*np.clip(dev,0,None),-3.2,3.2)

def prep(cat):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9
    Z=[];labels=[]
    for p,d in test:
        Z.append(z_of(stats6(load_gray(p),T,S),mu,sd)); labels.append(0 if d=="good" else 1)
    Z=np.array(Z); labels=np.array(labels)
    exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
    misfit=np.maximum(0.0,-Z*exp)               # (n,6) 逐爻失位幅度
    return labels, misfit

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    W_LOW=np.array([6,5,4,3,2,1.]); W_HIGH=np.array([1,2,3,4,5,6.])
    print("逐类别显著性: 初重 vs 上重")
    rows=[]
    for c in cats:
        labels,mf=prep(c)
        ch=(mf>0).astype(float)
        s_low=(ch*W_LOW*mf).sum(1); s_high=(ch*W_HIGH*mf).sum(1)
        a_low=roc_auc_score(labels,s_low); a_high=roc_auc_score(labels,s_high)
        rng=np.random.default_rng(0); n=len(labels); diffs=[]
        for _ in range(2000):
            idx=rng.integers(0,n,n)
            if len(np.unique(labels[idx]))<2: continue
            diffs.append(roc_auc_score(labels[idx],s_low[idx])-roc_auc_score(labels[idx],s_high[idx]))
        lo,hi=np.percentile(diffs,[2.5,97.5])
        sig="显著" if lo>0 else "不显著"
        print(f"  {c:12s} 初重={a_low:.4f} 上重={a_high:.4f} Δ={a_low-a_high:+.4f} CI=[{lo:+.4f},{hi:+.4f}] {sig}")
        rows.append((c,a_low,a_high,a_low-a_high,lo,hi))
    print()
    print("逐类别: 单爻位失位幅度 AUROC (初->上)")
    for c in cats:
        labels,mf=prep(c)
        print(f"  {c:12s} " + " ".join(f"{roc_auc_score(labels,mf[:,i]):.3f}" for i in range(6)))
    json.dump([dict(category=r[0],low=r[1],high=r[2],diff=r[3],ci=[r[4],r[5]]) for r in rows],
              open(os.path.join(RES,"exp2_mvtec_v11_sig.json"),"w"),ensure_ascii=False,indent=2)

if __name__=="__main__": main()
