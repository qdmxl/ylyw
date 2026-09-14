#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验3(Y1+Y3, 定稿v4): 在线学习正常模板 + 易理六爻 —— 真·冷启动学习曲线
================================================================================
核心:
  * 在线学习的对象 = 正常模板 T(逐像素均值) 与 S(逐像素标准差)
      t=1: T=x_1 (冷启动, 只有一张正常图)
      t↑ : Welford 在线更新 -> T,S 渐准
  * 缺陷 = 像素级残差 R=|x-T|/(S+ε)
  * 六爻 = 六种残差统计(点/纹理/边缘/对比/色泽/结构)
  * z -> 变爻位置加权(初重="知几")
  * 全程只用正常样本 -> 零样本(没见过缺陷)

输出学习曲线: 正常样本数 k vs AUROC (马氏/初重/等权/上重)
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize
from scipy import ndimage
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES,FIG=os.path.join(BASE,"results"),os.path.join(BASE,"figures")
os.makedirs(RES,exist_ok=True); os.makedirs(FIG,exist_ok=True)
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

def yao6_from_residual(R, rgb_res=None):
    """从残差图 R 提取六爻统计量(0~∞, 越大越异常)。"""
    out=np.zeros(6)
    out[0]=np.percentile(R,99.9)                                    # 点: 残差尖峰
    # 纹理: 残差的局部纹理能量
    lg=np.abs(filters.laplace(filters.gaussian(R,1.0)))
    out[1]=np.percentile(filters.gaussian(lg,2),99.0)
    # 边缘: 残差梯度
    eg=np.sqrt(filters.sobel_h(R)**2+filters.sobel_v(R)**2)
    out[2]=np.percentile(eg,99.5)
    # 对比: 残差局部方差的峰
    lv=filters.gaussian(R**2,3)-filters.gaussian(R,3)**2
    out[3]=np.percentile(np.sqrt(np.maximum(lv,0)),99.5)
    # 色泽: 颜色残差(若有)
    if rgb_res is not None:
        out[4]=np.percentile(rgb_res,99.5)
    else:
        out[4]=np.percentile(R,99.0)
    # 结构: 残差分布的全局展布
    out[5]=np.sqrt((R**2).mean())
    return out

class OnlineTemplate:
    """在线学习正常模板: 逐像素 Welford 均值/方差。"""
    def __init__(self, shape, nch=1):
        self.n=0; self.shape=shape
        self.mean=np.zeros(shape); self.M2=np.zeros(shape)
    def update(self, x):
        self.n+=1; d=x-self.mean; self.mean=self.mean+d/self.n; self.M2=self.M2+d*(x-self.mean)
    def std(self): return np.sqrt(np.maximum(self.M2/max(self.n-1,1),1e-6))
    def set_first(self,x): self.n=1; self.mean=x.copy(); self.M2=np.zeros_like(x)

class WelfordVec:
    def __init__(self,dim): self.n=0; self.mean=np.zeros(dim); self.M2=np.zeros(dim)
    def update(self,x):
        self.n+=1; d=x-self.mean; self.mean=self.mean+d/self.n; self.M2=self.M2+d*(x-self.mean)
    def std(self): return np.sqrt(np.maximum(self.M2/max(self.n-1,1),1e-6))
    def set_first(self,x): self.n=1; self.mean=x.copy(); self.M2=np.zeros_like(x)

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    allcurves={}
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        # 预载所有图(避免重复IO)
        tr_g=[load_gray(p) for p,_ in train]; tr_c=[load_rgb(p) for p,_ in train]
        te_g=[];te_c=[];Flab=[]
        for p,d in test:
            te_g.append(load_gray(p)); te_c.append(load_rgb(p)); Flab.append(0 if d=="good" else 1)
        te_g=np.array(te_g); te_c=np.array(te_c); Flab=np.array(Flab)

        Tmpl=OnlineTemplate((SIZE[0],SIZE[1]))
        TmplC=OnlineTemplate((SIZE[0],SIZE[1],3))
        curve=[]; ckpts=sorted(set([c for c in [1,2,3,5,8,12,20,30,50,80,120,200] if c<=len(train)]+[len(train)]))
        for i in range(len(train)):
            k=i+1
            if k==1:
                Tmpl.set_first(tr_g[0]); TmplC.set_first(tr_c[0])
            else:
                Tmpl.update(tr_g[i]); TmplC.update(tr_c[i])
            if k not in ckpts: continue
            T=Tmpl.mean; S=Tmpl.std()+1e-3
            TC=TmplC.mean; SC=TmplC.std()+1e-3
            Fte=[]
            for j in range(len(te_g)):
                R=np.abs(te_g[j]-T)/S
                Rb=filters.gaussian(R,2.0)
                Rc=np.abs(te_c[j]-TC)/(SC+1e-3)
                rgbres=np.percentile(Rc.mean(-1),99.5)
                Fte.append(yao6_from_residual(Rb,rgbres))
            Fte=np.array(Fte)
            # 六爻倾向: 用【只用正常训练样本】的六爻分布标定(不偷看测试集)
            Rtr_norm=[np.abs(tr_g[j]-T)/S for j in range(k)]
            Ftr_yao=np.array([yao6_from_residual(filters.gaussian(Rtr_norm[j],2.0),
                              np.percentile(np.abs(tr_c[j]-TC)/(SC+1e-3),99.5)) for j in range(k)])
            mm= Ftr_yao.mean(0); ss= Ftr_yao.std(0)+1e-9
            z=1.2-2.0*np.clip((Fte-mm)/ss,0,None)
            z=np.clip(z,-3.2,3.2)
            exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
            mf=np.maximum(0.0,-z*exp); ch=(mf>0).astype(float)
            # 无先验: 纯残差峰值
            raw=np.array([yao6_from_residual(filters.gaussian(np.abs(te_g[j]-T)/S,2.0),
                          np.percentile(np.abs(te_c[j]-TC)/(SC+1e-3),99.5))[0] for j in range(len(te_g))])
            rec=dict(n_train=k,
                auroc_rawpeak=float(roc_auc_score(Flab,raw)),
                auroc_low=float(roc_auc_score(Flab,(ch*W_LOW*mf).sum(1))),
                auroc_eq=float(roc_auc_score(Flab,(ch*W_EQ*mf).sum(1))),
                auroc_high=float(roc_auc_score(Flab,(ch*W_HIGH*mf).sum(1))),
                auroc_low_mag=float(roc_auc_score(Flab,(ch*W_LOW*mf).sum(1)+raw*0)))
            curve.append(rec)
            if k in (1,2,3,5,8,12,20,50,len(train)):
                print(f"  {cat}: n={k:3d} 残差峰={rec['auroc_rawpeak']:.3f} 初重={rec['auroc_low']:.3f} 等权={rec['auroc_eq']:.3f} 上重={rec['auroc_high']:.3f}")
        allcurves[cat]=curve
    json.dump(allcurves, open(os.path.join(RES,"exp3_online_v4.json"),"w"),ensure_ascii=False,indent=2)
    print("saved exp3_online_v4.json")

if __name__=="__main__": main()
