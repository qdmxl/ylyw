#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v10, 路径2定稿): 当位本卦 + 变爻位置加权"知几"
================================================================================
易理设定(路径2):
  * 正常本卦 = 最和谐"当位"构型 = 阳阴阳阴阳阴 = 010101 (U=1.5 最低)
      爻位(初..上): 阳位(初/三/五)皆阳, 阴位(二/四/六)皆阴 -> 各爻当位
  * 异常判据 = 偏离"当位":
      阳位(初/三/五)正常为阳; 若观测转阴 -> 该爻"失位"(变爻)
      阴位(二/四/六)正常为阴; 若观测转阳 -> 该爻"失位"(变爻)
    => 六个爻位对称地可触发"变爻", 不再有方向死区
  * 变爻幅度: |观测倾向 - 当位期望| 的连续量
  * 异常分数: S = Σ_i w_i·[爻i变爻]·|幅度_i|
      w = [6,5,4,3,2,1](初重) / [1..6](上重) / 等权
      "知几": 初爻(缺陷萌芽)权重最高
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
FANBEN_BITS=[1,0,1,0,1,0]          # 初..上 = 阳阴阳阴阳阴 (当位构型)

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
    """观测爻倾向 z_i (正值->阳, 负值->阴)。偏离正常越大越负。"""
    dev=(s-mu)/sd
    return np.clip(1.2-2.0*np.clip(dev,0,None),-3.2,3.2)

def bian_yao(z, fanben, weights):
    """变爻评分: 每个爻位偏离'当位'期望即算变爻, 幅度=偏离量。"""
    # 观测极性
    bits=(z>0).astype(int)
    # "当位期望"对应的 z 符号: 阳位期望阳(z>0), 阴位期望阴(z<0)
    exp=np.array([1 if b==1 else -1 for b in fanben],float)
    # 偏离当位程度: 观测 z 与期望符号的"错位量"
    # 用 -z*exp 度量: 当位(z与exp同号) -> -z*exp <0; 失位 -> >0
    misfit=np.maximum(0.0, -z*exp)          # >0 表示失位, 大小=偏离幅度
    changed=(misfit>0).astype(float)        # 变爻指示
    return float((changed*weights*misfit).sum()), changed, misfit

W_LOW=np.array([6,5,4,3,2,1.],float)       # 初重(知几)
W_EQ=np.ones(6)
W_HIGH=np.array([1,2,3,4,5,6.],float)      # 上重

def run_cat(cat, verbose=True):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    if not train or not test: return None
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9

    labels=[]; maxr=[]; s_low=[]; s_eq=[]; s_high=[]; misf_mean=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); z=z_of(s,mu,sd)
        _,ch,mf=bian_yao(z,FANBEN_BITS,W_LOW)
        s_low.append(bian_yao(z,FANBEN_BITS,W_LOW)[0])
        s_eq.append(bian_yao(z,FANBEN_BITS,W_EQ)[0])
        s_high.append(bian_yao(z,FANBEN_BITS,W_HIGH)[0])
        misf_mean.append(mf.mean())
        maxr.append(s[0]); labels.append(0 if d=="good" else 1)
    labels=np.array(labels); maxr=np.array(maxr)
    s_low=np.array(s_low); s_eq=np.array(s_eq); s_high=np.array(s_high); misf_mean=np.array(misf_mean)

    res=dict(category=cat,n_test=len(labels),
             n_normal=int((labels==0).sum()),n_anomaly=int((labels==1).sum()),
             fanben="101010")
    res["C0_max_residual"]=float(roc_auc_score(labels,maxr))
    res["C1_misfit_mean(no-position)"]=float(roc_auc_score(labels,misf_mean))
    res["equal_weight"]=float(roc_auc_score(labels,s_eq))
    res["low_weight(zhi-ji)"]=float(roc_auc_score(labels,s_low))
    res["high_weight"]=float(roc_auc_score(labels,s_high))
    if verbose:
        print(f"  {cat:12s} n={len(labels):3d} 本卦=101010 | "
              f"C0={res['C0_max_residual']:.3f} 失位均={res['C1_misfit_mean(no-position)']:.3f} "
              f"等权={res['equal_weight']:.3f} 初重={res['low_weight(zhi-ji)']:.3f} 上重={res['high_weight']:.3f}")
    return res, (labels, s_low, s_high, s_eq, misf_mean)

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    print("="*104)
    print("MVTec 当位本卦 + 变爻位置加权 '知几' (路径2)")
    print("="*104)
    allres=[]
    for c in cats:
        out=run_cat(c)
        if out: allres.append(out[0])
    print("="*104)
    if len(allres)>1:
        def avg(k): return float(np.mean([r[k] for r in allres]))
        print(f"平均({len(allres)}类): C0={avg('C0_max_residual'):.4f} "
              f"失位均={avg('C1_misfit_mean(no-position)'):.4f} 等权={avg('equal_weight'):.4f} "
              f"初重={avg('low_weight(zhi-ji)'):.4f} 上重={avg('high_weight'):.4f}")
        wins=sum(1 for r in allres if r["low_weight(zhi-ji)"]>r["high_weight"])
        print(f"初重>上重: {wins}/{len(allres)} 类")
    json.dump(allres, open(os.path.join(RES,"exp2_mvtec_v10_multiclass.json"),"w"),
              ensure_ascii=False,indent=2)

if __name__=="__main__": main()
