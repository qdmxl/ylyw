#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径B: 正交六爻设计 (四域构造)
================================================================================
核心: 六爻来自【不同数学域】, 期望低相关(真正正交)。
  初 空间·点   : 残差孤立尖峰(局部极大值统计)
  二 频域·高频 : 残差 FFT 高频能量占比
  三 梯度域    : 残差梯度方向一致性(结构张量)
  四 空间·分布 : 残差分布的偏度(三阶矩)
  五 颜色域    : 颜色残差(色相+饱和度独立)
  六 形态域    : 残差连通区域数量与形状复杂度

本脚本: 用模板法产生的残差, 计算六个正交特征, 检查相关性 + 单爻判别力。
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); RES=os.path.join(BASE,"results")
os.makedirs(RES,exist_ok=True); SIZE=(160,160)

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

def ortho6(R, Rc):
    """R: 灰度残差图(标准化); Rc: 颜色残差图(H,W,3)。返回 6 个正交特征。"""
    out=np.zeros(6)
    # 初: 空间·点 -> 局部极大值的孤立性(用形态学: 残差 - 开运算)
    Rb=filters.gaussian(R,1.5)
    peaks=Rb-morphology.opening(Rb, morphology.disk(3))
    out[0]=np.percentile(peaks,99.9)
    # 二: 频域·高频 -> FFT 高频能量占比
    F=np.fft.fftshift(np.abs(np.fft.fft2(Rb-Rb.mean())))
    h,w=F.shape; cy,cx=h//2,w//2
    yy,xx=np.ogrid[:h,:w]; rad=np.sqrt((yy-cy)**2+(xx-cx)**2)
    hi=F[rad>min(h,w)*0.25].sum(); tot=F.sum()+1e-9
    out[1]=hi/tot
    # 三: 梯度域 -> 结构张量的方向一致性
    gy,gx=np.gradient(Rb)
    Jxx=filters.gaussian(gx*gx,2); Jyy=filters.gaussian(gy*gy,2); Jxy=filters.gaussian(gx*gy,2)
    coh=np.sqrt((Jxx-Jyy)**2+4*Jxy**2)/(Jxx+Jyy+1e-9)
    out[2]=np.percentile(coh,99.0)
    # 四: 空间·分布 -> 残差偏度(三阶矩)
    m=Rb.mean(); s=Rb.std()+1e-9
    out[3]=float(((Rb-m)**3).mean()/s**3)
    # 五: 颜色域 -> 色相+饱和度残差(独立于亮度)
    hsv=color.rgb2hsv(np.clip(Rc,0,None))
    out[4]=np.percentile(Rc[...,1],99.5) if Rc.ndim==3 else np.percentile(Rc,99.5)
    # 六: 形态域 -> 连通区域数量×形状复杂度
    msk=Rb>np.percentile(Rb,99.0)
    lab=measure.label(msk)
    n=lab.max()
    if n>0:
        sizes=np.bincount(lab.ravel())[1:]
        per=measure.regionprops(lab)
        comp=np.mean([p.perimeter**2/(4*np.pi*p.area+1e-9) for p in per])  # 形状复杂度
        out[5]=n*(1+comp)
    else: out[5]=0.0
    return out

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        tr_g=[load_gray(p) for p,_ in train]; tr_c=[load_rgb(p) for p,_ in train]
        G=np.array(tr_g); T=G.mean(0); S=G.std(0)+1e-3
        C=np.array(tr_c); TC=C.mean(0); SC=C.std(0)+1e-3
        # 正常训练样本的六爻
        Ftr=np.array([ortho6(filters.gaussian(np.abs(tr_g[i]-T)/S,2.0),
                             np.abs(tr_c[i]-TC)/SC) for i in range(len(train))])
        mu,sd=Ftr.mean(0),Ftr.std(0)+1e-9
        Corr=np.corrcoef(((Ftr-mu)/sd).T)
        evals=np.linalg.eigvalsh(Corr)[::-1]
        # 测试集
        labels=[]; Fte=[]
        for p,d in test:
            R=filters.gaussian(np.abs(load_gray(p)-T)/S,2.0)
            Rc=np.abs(load_rgb(p)-TC)/SC
            Fte.append(ortho6(R,Rc)); labels.append(0 if d=="good" else 1)
        labels=np.array(labels); Fte=np.array(Fte)
        aucs=[roc_auc_score(labels,Fte[:,i]) for i in range(6)]
        mx=max(abs(Corr[i,j]) for i in range(6) for j in range(6) if i!=j)
        print(f"{cat:12s} 有效维度={int((evals>1).sum())} 最大相关={mx:.2f} | " +
              " ".join(f"爻{i}={a:.2f}" for i,a in enumerate(aucs)))
    print("\n说明: 有效维度越大越正交; 各爻AUROC差异大=分工明确")

if __name__=="__main__": main()
