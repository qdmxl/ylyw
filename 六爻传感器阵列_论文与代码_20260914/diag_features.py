#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""特征级诊断: 逐个爻特征对正常/异常的区分能力 (AUROC), 找出坏特征"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
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

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    imgs=np.array([load_gray(p) for p,_ in train])
    T=imgs.mean(0); S=imgs.std(0)
    print(f"{cat}: train={len(train)} test={len(test)}")

    recs=[]
    for p,d in test:
        g=load_gray(p)
        R=np.abs(g-T)/(S+1e-3)
        Rb=filters.gaussian(R,2.0)
        lap=np.abs(filters.laplace(Rb))
        gy,gx=np.gradient(Rb)
        grad=np.sqrt(gy**2+gx**2)
        mask=Rb>2.0
        f={}
        f["a_mean"]=Rb.mean()
        f["b_area"]=(Rb>2.0).mean()
        f["c_p999"]=np.percentile(Rb,99.5)
        f["d_p9999"]=np.percentile(Rb,99.9)
        f["e_tex"]=lap.mean()
        f["f_grad"]=grad.mean()
        f["g_max"]=Rb.max()
        # 更好的聚集度: 用强阈值(>3)的连通块
        m2=Rb>3.0
        if m2.any():
            lab=measure.label(m2); sizes=np.bincount(lab.ravel())[1:]
            f["h_conn"]=sizes.max() if len(sizes) else 0
            f["i_ncomp"]=len(sizes)
        else:
            f["h_conn"]=0; f["i_ncomp"]=0
        f["j_topk"]=np.sort(Rb.ravel())[-50:].mean()  # top50像素均值
        f["k_p999_area"]=(Rb>np.percentile(Rb,99.5)).mean()
        recs.append((f, 0 if d=="good" else 1))
    labels=np.array([l for _,l in recs])
    keys=list(recs[0][0].keys())
    print("\n逐特征 AUROC:")
    for k in keys:
        v=np.array([f[k] for f,_ in recs])
        auc=roc_auc_score(labels,v)
        print(f"  {k:12s} AUROC={auc:.4f}  (正常均值={v[labels==0].mean():.4f} 异常均值={v[labels==1].mean():.4f})")
    # 组合: 取几个最好的
    print("\n组合特征 AUROC:")
    for combo in [["c_p999"],["g_max"],["d_p9999"],["c_p999","j_topk"],
                  ["c_p999","d_p9999","j_topk"],["b_area","c_p999","h_conn"]]:
        v=np.column_stack([np.array([f[k] for f,_ in recs]) for k in combo])
        # 简单线性组合(等权z-score)
        vz=(v-v.mean(0))/(v.std(0)+1e-9)
        sc=vz.mean(1)
        print(f"  {'+'.join(combo):30s} AUROC={roc_auc_score(labels,sc):.4f}")

if __name__=="__main__": main()
