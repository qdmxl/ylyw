#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径A+正交六爻: 在线学习 + 正交六爻编码
================================================================================
把路径A 的"在线学习正常模板"与路径B 的"正交六爻编码"结合:
  在线学习: 逐像素模板 T,S (Welford) + 六爻分布 (Welford)
  正交六爻: 频域/梯度域/颜色域/形态域 (来自路径B)
  异常分数: 六爻马氏偏离 + 变爻位置加权

对比三种打分:
  S1 残差峰值(纯图像基线)
  S2 六爻马氏偏离(无位置权重)
  S3 六爻马氏 + 变爻位置加权(初重)
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES=os.path.join(BASE,"results"); os.makedirs(RES,exist_ok=True)
SIZE=(160,160); FANBEN=[1,0,1,0,1,0]
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

def ortho6(R, Rc):
    """R: 灰度残差; Rc: RGB残差(H,W,3)。返回六爻正交特征。"""
    out=np.zeros(6); Rb=filters.gaussian(R,1.5)
    peaks=Rb-morphology.opening(Rb, morphology.disk(3)); out[0]=np.percentile(peaks,99.9)
    F=np.fft.fftshift(np.abs(np.fft.fft2(Rb-Rb.mean())))
    h,w=F.shape; cy,cx=h//2,w//2
    yy,xx=np.ogrid[:h,:w]; rad=np.sqrt((yy-cy)**2+(xx-cx)**2)
    out[1]=F[rad>min(h,w)*0.25].sum()/(F.sum()+1e-9)
    gy,gx=np.gradient(Rb)
    Jxx=filters.gaussian(gx*gx,2);Jyy=filters.gaussian(gy*gy,2);Jxy=filters.gaussian(gx*gy,2)
    out[2]=np.percentile(np.sqrt((Jxx-Jyy)**2+4*Jxy**2)/(Jxx+Jyy+1e-9),99.0)
    m=Rb.mean(); s=Rb.std()+1e-9; out[3]=float(((Rb-m)**3).mean()/s**3)
    out[4]=np.percentile(Rc[...,1],99.5) if Rc.ndim==3 else np.percentile(Rc,99.5)
    msk=Rb>np.percentile(Rb,99.0); lab=measure.label(msk); n=lab.max()
    if n>0:
        per=measure.regionprops(lab)
        comp=np.mean([p.perimeter**2/(4*np.pi*p.area+1e-9) for p in per]); out[5]=n*(1+comp)
    return out

def feats_of_templates(g, c, T, S, TC, SC):
    R=filters.gaussian(np.abs(g-T)/S,2.0); Rc=np.abs(c-TC)/SC
    return ortho6(R,Rc)

def run(cat, ckpts, reps=3):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    tr_g=[load_gray(p) for p,_ in train]; tr_c=[load_rgb(p) for p,_ in train]
    te_g=[load_gray(p) for p,_ in test]; te_c=[load_rgb(p) for p,_ in test]
    Flab=np.array([0 if d=="good" else 1 for _,d in test])
    curves={k:{"s1":[],"s2":[],"s3":[]} for k in ckpts}
    for rep in range(reps):
        rng=np.random.default_rng(rep); order=rng.permutation(len(tr_g))
        Tm=None;Sg=None;TCm=None;SCg=None
        for k in range(1,len(order)+1):
            i=order[k-1]; g=tr_g[i]; c=tr_c[i]
            if k==1:
                Tm=g.copy(); M2g=np.zeros_like(g); TCm=c.copy(); M2c=np.zeros_like(c)
            else:
                dg=g-Tm; Tm=Tm+dg/k; M2g=M2g+dg*(g-Tm)
                dc=c-TCm; TCm=TCm+dc/k; M2c=M2c+dc*(c-TCm)
            if k not in ckpts: continue
            Sg=np.sqrt(np.maximum(M2g/max(k-1,1),1e-6))+1e-3
            SCg=np.sqrt(np.maximum(M2c/max(k-1,1),1e-6))+1e-3
            # 训练(已见)样本的六爻 -> 标定
            Ftr=np.array([feats_of_templates(tr_g[order[j]],tr_c[order[j]],Tm,Sg,TCm,SCg) for j in range(k)])
            mu= Ftr.mean(0); sd= Ftr.std(0)+1e-9
            s1=[];s2=[];s3=[]
            for j in range(len(te_g)):
                Fte=feats_of_templates(te_g[j],te_c[j],Tm,Sg,TCm,SCg)
                z=1.2-2.0*np.clip((Fte-mu)/sd,0,None); z=np.clip(z,-3.2,3.2)
                # 马氏偏离
                dev=np.abs(z-mu*0)/(np.ones(6))
                s2.append(np.abs((Fte-mu)/sd).mean())
                exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
                mf=np.maximum(0.0,-z*exp); ch=(mf>0).astype(float)
                s3.append(np.abs((Fte-mu)/sd).mean()+(ch*W_LOW*mf).sum())
                R=np.abs(te_g[j]-Tm)/Sg; s1.append(float(np.percentile(filters.gaussian(R,2.0),99.9)))
            curves[k]["s1"].append(float(roc_auc_score(Flab,s1)))
            curves[k]["s2"].append(float(roc_auc_score(Flab,s2)))
            curves[k]["s3"].append(float(roc_auc_score(Flab,s3)))
    return curves

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    out={}
    for cat in cats:
        train=load_split(cat,"train")
        ckpts=sorted(set([c for c in [1,2,3,5,8,12,20,30,50,80,120,200] if c<=len(train)]+[len(train)]))
        cv=run(cat,ckpts)
        out[cat]=[dict(n_train=k,
                       s1_peak=float(np.mean(cv[k]["s1"])),
                       s2_ortho=float(np.mean(cv[k]["s2"])),
                       s3_ortho_pos=float(np.mean(cv[k]["s3"])),
                       s2_std=float(np.std(cv[k]["s2"])),
                       s3_std=float(np.std(cv[k]["s3"]))) for k in ckpts]
        print(f"\n{cat}:")
        for r in out[cat]:
            print(f"  n={r['n_train']:3d} 残差峰={r['s1_peak']:.4f} 正交六爻={r['s2_ortho']:.4f}±{r['s2_std']:.3f} 六爻+位置={r['s3_ortho_pos']:.4f}±{r['s3_std']:.3f}")
    json.dump(out, open(os.path.join(RES,"expA_ortho_online.json"),"w"),ensure_ascii=False,indent=2)
    print("\nsaved expA_ortho_online.json")

if __name__=="__main__": main()
