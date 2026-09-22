#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验3(Y1+Y3, 修正): 真·在线增量学习 —— 冷启动到累积
================================================================================
修正 v1 的方法论漏洞:
  v1 用全部训练集定 mu/sd, 再声称"只用k张" -> 冷启动是假的(偷看全量).
  本版: mu/sd 也随 k 张正常样本在线更新, 全程只用当前可见的正常样本。

流程(完全在线, 单遍):
  for 每张正常图 x_t (t=1..N):
       (1) 六爻幅度 f_t = yao6(x_t)
       (2) 在线更新 六爻标定 (mu_t, sd_t)     [Welford]
       (3) 六爻倾向 z_t = f(f_t; mu_t, sd_t)
       (4) 在线更新 卦分布 (mean_t, var_t)     [Welford]
  for 每张测试图:
       (用 t 时刻的模型) 异常分数 = 马氏偏离 + 变爻位置加权
  记录 k=1,2,...,N 各时刻的 AUROC -> 学习曲线

注意: 六爻幅度 yao6 是"图内自参考"的绝对量, 无需模板 -> 保证真正零样本冷启动。
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
    out=np.zeros(6)
    base=filters.gaussian(g,6.0)
    out[0]=np.percentile(np.maximum(np.maximum(0.0,g-base),np.maximum(0.0,base-g)),99.5)
    lg=np.abs(filters.laplace(filters.gaussian(g,1.5)))
    out[1]=np.percentile(filters.gaussian(lg,2),99.5)
    eg=np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2)
    out[2]=np.percentile(eg,99.5)
    lv=filters.gaussian(g**2,3)-filters.gaussian(g,3)**2
    out[3]=np.percentile(np.sqrt(np.maximum(lv,0)),99.5)
    hsv=color.rgb2hsv(np.clip(rgb,0,1))
    out[4]=np.percentile(np.maximum(hsv[...,1],hsv[...,2]),99.5)
    fg=(g>np.percentile(g,60)).astype(float)
    out[5]=np.abs(ndimage.gaussian_filter(fg,5)-fg).mean()
    return out

class Welford:
    def __init__(self,dim): self.n=0; self.mean=np.zeros(dim); self.M2=np.zeros(dim)
    def update(self,x):
        self.n+=1; d=x-self.mean; self.mean=self.mean+d/self.n; self.M2=self.M2+d*(x-self.mean)
    def std(self):
        return np.sqrt(np.maximum(self.M2/max(self.n-1,1),1e-6))

def score_of(z, gmodel):
    dev=np.abs(z-gmodel.mean)/(gmodel.std()+1e-6)
    exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
    misfit=np.maximum(0.0,-z*exp); ch=(misfit>0).astype(float)
    return float(dev.mean()), float((ch*W_LOW*misfit).sum()), float((ch*W_EQ*misfit).sum()), float((ch*W_HIGH*misfit).sum())

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

        # --- 真·在线: 同步更新 爻标定 + 卦分布 ---
        cal=Welford(6); gmodel=Welford(6)
        curve=[]
        ckpts=sorted(set([c for c in [1,2,3,5,8,12,20,30,50,80,120,200] if c<=len(Ftr)]+[len(Ftr)]))
        k=0
        for i,(p,_) in enumerate(train):
            k+=1
            f=Ftr[i]
            if k==1:
                cal.mean=f.copy(); cal.n=1; gmodel.mean=np.zeros(6); gmodel.n=1
                # 首样本: z 定义为0(基准), 卦分布 mean=0, 给初始方差
                continue
            cal.update(f)
            z=np.clip(1.2-2.0*np.clip((f-cal.mean)/(cal.std()+1e-9),0,None),-3.2,3.2)
            gmodel.update(z)
            if k in ckpts:
                nd=[]; pl=[]; pe=[]; ph=[]
                for zt in Fte:
                    zz=np.clip(1.2-2.0*np.clip((zt-cal.mean)/(cal.std()+1e-9),0,None),-3.2,3.2)
                    a,b,c,d=score_of(zz,gmodel); nd.append(a);pl.append(b);pe.append(c);ph.append(d)
                # 总分数 = 马氏偏离 + 位置加权项
                sc=np.array(nd)+np.array(pl)
                curve.append(dict(n_train=k,
                    auroc=float(roc_auc_score(Flab,sc)),
                    auroc_maha=float(roc_auc_score(Flab,nd)),
                    auroc_low=float(roc_auc_score(Flab,np.array(nd)+np.array(pl))),
                    auroc_eq=float(roc_auc_score(Flab,np.array(nd)+np.array(pe))),
                    auroc_high=float(roc_auc_score(Flab,np.array(nd)+np.array(ph)))))
                if k in (1,2,3,5,8,12,20,50,len(Ftr)):
                    r=curve[-1]
                    print(f"  {cat}: n={k:3d} AUROC={r['auroc']:.4f} | 马氏={r['auroc_maha']:.4f} 初重={r['auroc_low']:.4f} 等权={r['auroc_eq']:.4f} 上重={r['auroc_high']:.4f}")
        allcurves[cat]=curve
    json.dump(allcurves, open(os.path.join(RES,"exp3_online_v2.json"),"w"),ensure_ascii=False,indent=2)
    print("saved exp3_online_v2.json")

if __name__=="__main__": main()
