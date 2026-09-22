#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v7, 多类别): 变爻位置加权(选项三) 跨 MVTec 类别验证
================================================================================
验证"初爻权重高(知几)"这一易理结构规律在不同类别上是否普适。
方法(定稿):
    S = Σ_i w_i · [爻i变爻] · |z_i|      w = [2,1.5,1,1,0.5,0.5] (初..上)
对比: C0 max_residual(纯图像上界), 等权变爻, 初重, 上重
"""
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

def run_cat(cat, verbose=True):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    if not train or not test: return None
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9
    fanben=0b010101; fb=np.array([(fanben>>i)&1 for i in range(6)])
    Z=[]; labels=[]; maxr=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); dev=(s-mu)/sd
        z=1.2-2.0*np.clip(dev,0,None); z=np.clip(z,-3.2,3.2)
        Z.append(z); labels.append(0 if d=="good" else 1); maxr.append(s[0])
    Z=np.array(Z); labels=np.array(labels); maxr=np.array(maxr)
    bits=(Z>0).astype(int); changed=(bits!=fb).astype(float); mag=np.abs(Z)
    w_equal=np.ones(6)
    w_low=np.array([2,1.5,1,1,0.5,0.5])        # 初重
    w_high=np.array([0.5,0.5,1,1,1.5,2.])      # 上重
    res=dict(category=cat, n_test=len(labels),
             n_normal=int((labels==0).sum()), n_anomaly=int((labels==1).sum()))
    res["C0_max_residual"]=float(roc_auc_score(labels,maxr))
    res["equal_weight"]=float(roc_auc_score(labels,(changed*w_equal*mag).sum(1)))
    res["low_weight(zhi-ji)"]=float(roc_auc_score(labels,(changed*w_low*mag).sum(1)))
    res["high_weight"]=float(roc_auc_score(labels,(changed*w_high*mag).sum(1)))
    if verbose:
        print(f"  {cat:12s} n={len(labels):3d} | C0={res['C0_max_residual']:.3f} "
              f"| 等权={res['equal_weight']:.3f} 初重={res['low_weight(zhi-ji)']:.3f} "
              f"上重={res['high_weight']:.3f} | 初重-上重={res['low_weight(zhi-ji)']-res['high_weight']:+.3f}")
    return res

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    print("="*84)
    print("MVTec 多类别: 变爻位置加权 (选项三) —— 验证'初爻权重高(知几)'普适性")
    print("="*84)
    allres=[]
    for c in cats:
        r=run_cat(c)
        if r: allres.append(r)
    print("="*84)
    if allres:
        def avg(k): return float(np.mean([r[k] for r in allres]))
        print(f"平均: C0={avg('C0_max_residual'):.4f} 等权={avg('equal_weight'):.4f} "
              f"初重={avg('low_weight(zhi-ji)'):.4f} 上重={avg('high_weight'):.4f}")
        print(f"初重 vs 上重 平均差: {avg('low_weight(zhi-ji)')-avg('high_weight'):+.4f}")
        # 初重 vs 等权
        print(f"初重 vs 等权 平均差: {avg('low_weight(zhi-ji)')-avg('equal_weight'):+.4f}")
    json.dump(allres, open(os.path.join(RES,"exp2_mvtec_multiclass.json"),"w"),
              ensure_ascii=False,indent=2)

if __name__=="__main__": main()
