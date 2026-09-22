#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验3(Y1+Y3, 定稿): 在线基线学习 —— 真·冷启动
================================================================================
核心修正:
  六爻必须是"相对正常基线的偏离", 不能是图内绝对量(绝对量方向反了)。

在线流程(单遍, 完全零样本):
  for 每张正常图 x_t:
      f_t = 六爻绝对特征(x_t)
      (1) 在线更新基线 (mu_t, sd_t)  [Welford]  <- 这就是"正常是什么"
      (2) 在线更新卦分布 [Welford]
  测试: z = 偏离基线 -> (a)马氏偏离 (b)变爻位置加权
  关键的"冷启动": t=1 时只有1张正常图 -> 基线=自身; 随 t 增大基线渐准。

注: 基线即"正常模板", 只用正常样本 -> 仍是零样本(没见过缺陷)。
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize
from scipy import ndimage
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES=os.path.join(BASE,"results"); os.makedirs(RES,exist_ok=True)
SIZE=(160,160)
FANBEN=[1,0,1,0,1,0]
W_LOW=np.array([6,5,4,3,2,1.]); W_EQ=np.ones(6); W_HIGH=np.array([1,2,3,4,5,6.])

def load_gray(path):
    im=io.imread(path)
    g=color.rgb2gray(im) if im.ndim==3 else im.astype(float)
    g=(g-g.min())/(np.ptp(g)+1e-9); return resize(g,SIZE,anti_aliasing=True)
def load_rgb(path):
    im=io.imread(path)
    rgb=np.stack([im]*3,-1)/255.0 if im.ndim==2 else im[...,:3]/255.0
    return resize(rgb,SIZE,anti_aliasing=True)
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

def yao6(g, rgb):
    """六爻绝对特征(图内). 偏离基线的部分才是"异常"。"""
    out=np.zeros(6)
    base=filters.gaussian(g,6.0)
    out[0]=np.percentile(np.maximum(np.maximum(0.0,g-base),np.maximum(0.0,base-g)),99.5)  # 点
    lg=np.abs(filters.laplace(filters.gaussian(g,1.5)))
    out[1]=np.percentile(filters.gaussian(lg,2),99.5)                                      # 纹理
    eg=np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2)
    out[2]=np.percentile(eg,99.5)                                                          # 边缘
    lv=filters.gaussian(g**2,3)-filters.gaussian(g,3)**2
    out[3]=np.percentile(np.sqrt(np.maximum(lv,0)),99.5)                                   # 对比
    hsv=color.rgb2hsv(np.clip(rgb,0,1))
    out[4]=np.percentile(np.maximum(hsv[...,1],hsv[...,2]),99.5)                            # 色泽
    fg=(g>np.percentile(g,60)).astype(float)
    out[5]=np.abs(ndimage.gaussian_filter(fg,5)-fg).mean()                                  # 结构
    return out

class Welford:
    def __init__(self,dim): self.n=0; self.mean=np.zeros(dim); self.M2=np.zeros(dim)
    def update(self,x):
        self.n+=1; d=x-self.mean; self.mean=self.mean+d/self.n; self.M2=self.M2+d*(x-self.mean)
    def std(self): return np.sqrt(np.maximum(self.M2/max(self.n-1,1),1e-6))
    def set_first(self,x): self.n=1; self.mean=x.copy(); self.M2=np.zeros_like(x)

def z_of(f, base):
    """六爻绝对特征 -> 爻倾向 z (与基线同向=阳, 偏离=阴)"""
    dev=(f-base.mean)/(base.std()+1e-9)
    return np.clip(1.2-2.0*np.clip(dev,0,None),-3.2,3.2), dev

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    allcurves={}
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        Ftr=np.array([yao6(load_gray(p),load_rgb(p)) for p,_ in train])
        Flab=[]; Fte=[]
        for p,d in test:
            Fte.append(yao6(load_gray(p),load_rgb(p))); Flab.append(0 if d=="good" else 1)
        Flab=np.array(Flab); Fte=np.array(Fte)

        base=Welford(6); gmodel=Welford(6)
        curve=[]; ckpts=sorted(set([c for c in [1,2,3,5,8,12,20,30,50,80,120,200] if c<=len(Ftr)]+[len(Ftr)]))
        for i,(p,_) in enumerate(train):
            k=i+1; f=Ftr[i]
            if k==1:
                base.set_first(f); gmodel.set_first(np.zeros(6))
                z_ref=np.zeros(6)
            else:
                base.update(f)
                z=np.clip(1.2-2.0*np.clip((f-base.mean)/(base.std()+1e-9),0,None),-3.2,3.2)
                gmodel.update(z)
            if k in ckpts:
                nd=[];pl=[];pe=[];ph=[]
                for ft in Fte:
                    zt,_=z_of(ft,base)
                    dev=np.abs(zt-gmodel.mean)/(gmodel.std()+1e-6)
                    exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
                    mf=np.maximum(0.0,-zt*exp); ch=(mf>0).astype(float)
                    nd.append(dev.mean()); pl.append((ch*W_LOW*mf).sum())
                    pe.append((ch*W_EQ*mf).sum()); ph.append((ch*W_HIGH*mf).sum())
                nd=np.array(nd)
                curve.append(dict(n_train=k,
                    auroc_maha=float(roc_auc_score(Flab,nd)),
                    auroc_low=float(roc_auc_score(Flab,nd+np.array(pl))),
                    auroc_eq=float(roc_auc_score(Flab,nd+np.array(pe))),
                    auroc_high=float(roc_auc_score(Flab,nd+np.array(ph))),
                    auroc_devonly=float(roc_auc_score(Flab,np.abs(np.array([z_of(ft,base)[1].mean() for ft in Fte]))))))
                if k in (1,2,3,5,8,12,20,50,len(Ftr)):
                    r=curve[-1]
                    print(f"  {cat}: n={k:3d} 偏离={r['auroc_devonly']:.3f} 马氏={r['auroc_maha']:.3f} 初重={r['auroc_low']:.3f} 等权={r['auroc_eq']:.3f} 上重={r['auroc_high']:.3f}")
        allcurves[cat]=curve
    json.dump(allcurves, open(os.path.join(RES,"exp3_online_v3.json"),"w"),ensure_ascii=False,indent=2)
    print("saved exp3_online_v3.json")

if __name__=="__main__": main()
