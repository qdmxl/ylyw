#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v9, 定稿): 变爻位置加权"知几"异常检测 (选项三 + 构型C)
================================================================================
定稿设计:
  1. 正常本卦: 由数据自动决定(构型C) —— 用正常训练样本的六爻极性多数投票。
  2. 编码方向: 阳=正常/健, 阴=异常/衰退 (阳消阴长)。
     每爻 z_i = a - b·clamp(dev_i, 0, ∞), dev_i 为标准化的正向偏离。
  3. 异常分数: S = Σ_i w_i·[爻i变爻]·|z_i|
     w = 初重位置权重 [2, 1.5, 1, 1, 0.5, 0.5]  (初爻="几", 权重最高)
  4. 对比: C0 残差峰值(纯图像上界), 等权, 初重, 上重。
  5. 输出: 单类 JSON + 多类汇总。
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
W_LOW=np.array([2,1.5,1,1,0.5,0.5])   # 初重(知几)
W_EQ=np.ones(6)
W_HIGH=np.array([0.5,0.5,1,1,1.5,2.])

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
    dev=(s-mu)/sd
    z=1.2-2.0*np.clip(dev,0,None)
    return np.clip(z,-3.2,3.2)

def run_cat(cat, verbose=True):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    if not train or not test: return None
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9

    # --- 构型C: 正常本卦由数据决定 ---
    Ztr=np.array([z_of(s,mu,sd) for s in Str])
    btr=(Ztr>0).astype(int)                     # 正常样本爻极性
    fanben=np.array([1 if btr[:,i].mean()>=0.5 else 0 for i in range(6)])
    fb_str="".join(str(b) for b in fanben)

    Z=[];labels=[];maxr=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); z=z_of(s,mu,sd)
        Z.append(z); labels.append(0 if d=="good" else 1); maxr.append(s[0])
    Z=np.array(Z);labels=np.array(labels);maxr=np.array(maxr)
    bits=(Z>0).astype(int); changed=(bits!=fanben).astype(float); mag=np.abs(Z)

    res=dict(category=cat,n_test=len(labels),
             n_normal=int((labels==0).sum()),n_anomaly=int((labels==1).sum()),
             fanben=fb_str,
             fanben_bits=[int(b) for b in fanben],mu=[float(x) for x in mu],
             sd=[float(x) for x in sd])
    res["C0_max_residual"]=float(roc_auc_score(labels,maxr))
    res["equal_weight"]=float(roc_auc_score(labels,(changed*W_EQ*mag).sum(1)))
    res["low_weight(zhi-ji)"]=float(roc_auc_score(labels,(changed*W_LOW*mag).sum(1)))
    res["high_weight"]=float(roc_auc_score(labels,(changed*W_HIGH*mag).sum(1)))
    if verbose:
        print(f"  {cat:12s} n={len(labels):3d} 本卦={fb_str} | "
              f"C0={res['C0_max_residual']:.3f} 等权={res['equal_weight']:.3f} "
              f"初重={res['low_weight(zhi-ji)']:.3f} 上重={res['high_weight']:.3f}")
    return res

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    print("="*96)
    print("MVTec 变爻位置加权 '知几' 异常检测 (选项三 + 构型C)")
    print("="*96)
    allres=[]
    for c in cats:
        r=run_cat(c)
        if r: allres.append(r)
    print("="*96)
    if len(allres)>1:
        def avg(k): return float(np.mean([r[k] for r in allres]))
        print(f"平均({len(allres)}类): C0={avg('C0_max_residual'):.4f} "
              f"等权={avg('equal_weight'):.4f} 初重={avg('low_weight(zhi-ji)'):.4f} "
              f"上重={avg('high_weight'):.4f}")
        wins=sum(1 for r in allres if r["low_weight(zhi-ji)"]>r["high_weight"])
        print(f"初重>上重 的类别数: {wins}/{len(allres)}")
    json.dump(allres, open(os.path.join(RES,"exp2_mvtec_final_multiclass.json"),"w"),
              ensure_ascii=False,indent=2)

if __name__=="__main__": main()
