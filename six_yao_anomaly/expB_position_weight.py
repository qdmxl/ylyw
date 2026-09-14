#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径B: 正交六爻 + 位置权重(知几) 检验
================================================================================
用 expB_ortho6 的正交六爻, 检验"初重 vs 上重"是否成立。
方法: 六爻残差统计 -> 逐爻失位幅度 -> 位置加权
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); RES=os.path.join(BASE,"results")
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
    out=np.zeros(6)
    Rb=filters.gaussian(R,1.5)
    peaks=Rb-morphology.opening(Rb, morphology.disk(3)); out[0]=np.percentile(peaks,99.9)
    F=np.fft.fftshift(np.abs(np.fft.fft2(Rb-Rb.mean())))
    h,w=F.shape; cy,cx=h//2,w//2
    yy,xx=np.ogrid[:h,:w]; rad=np.sqrt((yy-cy)**2+(xx-cx)**2)
    out[1]=F[rad>min(h,w)*0.25].sum()/(F.sum()+1e-9)
    gy,gx=np.gradient(Rb)
    Jxx=filters.gaussian(gx*gx,2);Jyy=filters.gaussian(gy*gy,2);Jxy=filters.gaussian(gx*gy,2)
    out[2]=np.percentile(np.sqrt((Jxx-Jyy)**2+4*Jxy**2)/(Jxx+Jyy+1e-9),99.0)
    m=Rb.mean(); s=Rb.std()+1e-9; out[3]=float(((Rb-m)**3).mean()/s**3)
    out[4]=np.percentile(Rc[...,1],99.5)
    msk=Rb>np.percentile(Rb,99.0); lab=measure.label(msk); n=lab.max()
    if n>0:
        per=measure.regionprops(lab)
        comp=np.mean([p.perimeter**2/(4*np.pi*p.area+1e-9) for p in per]); out[5]=n*(1+comp)
    return out

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    allres=[]
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        tr_g=[load_gray(p) for p,_ in train]; tr_c=[load_rgb(p) for p,_ in train]
        G=np.array(tr_g); T=G.mean(0); S=G.std(0)+1e-3
        C=np.array(tr_c); TC=C.mean(0); SC=C.std(0)+1e-3
        Ftr=np.array([ortho6(filters.gaussian(np.abs(tr_g[i]-T)/S,2.0),np.abs(tr_c[i]-TC)/SC) for i in range(len(train))])
        mu,sd=Ftr.mean(0),Ftr.std(0)+1e-9
        labels=[]; Fte=[]
        for p,d in test:
            R=filters.gaussian(np.abs(load_gray(p)-T)/S,2.0); Rc=np.abs(load_rgb(p)-TC)/SC
            Fte.append(ortho6(R,Rc)); labels.append(0 if d=="good" else 1)
        labels=np.array(labels); Fte=np.array(Fte)
        # 六爻倾向 z: 偏离正常越大越负
        z=1.2-2.0*np.clip((Fte-mu)/sd,0,None); z=np.clip(z,-3.2,3.2)
        exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
        mf=np.maximum(0.0,-z*exp); ch=(mf>0).astype(float)
        s_low=(ch*W_LOW*mf).sum(1); s_eq=(ch*W_EQ*mf).sum(1); s_high=(ch*W_HIGH*mf).sum(1)
        s_sum=mf.sum(1)   # 无位置权重
        a_low=roc_auc_score(labels,s_low); a_eq=roc_auc_score(labels,s_eq)
        a_high=roc_auc_score(labels,s_high); a_sum=roc_auc_score(labels,s_sum)
        print(f"{cat:12s} 无序={a_sum:.3f} 等权={a_eq:.3f} 初重={a_low:.3f} 上重={a_high:.3f}  (初-上={a_low-a_high:+.3f})")
        allres.append(dict(category=cat,no_order=float(a_sum),equal=float(a_eq),
                           low=float(a_low),high=float(a_high),diff=float(a_low-a_high)))
    wins=sum(1 for r in allres if r["low"]>r["high"])
    print(f"\n初重>上重: {wins}/{len(allres)} 类")
    print(f"平均: 初重={np.mean([r['low'] for r in allres]):.4f} 上重={np.mean([r['high'] for r in allres]):.4f}")
    json.dump(allres, open(os.path.join(RES,"expB_position_weight.json"),"w"),ensure_ascii=False,indent=2)

if __name__=="__main__": main()
