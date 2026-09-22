#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻正交化 v2: 明确语义 + 逐爻正交性验证
================================================================================
诊断:
  * 原六统计量全相关0.99 (无效)
  * 正交v1: 有效维度2-3; 但爻1(熵)失败(残差图稀疏), 爻4(hue/sat混)语义不清
  * 关键: 不同类别缺陷类型不同 -> 需要"六个互补的象", 每类缺陷至少激活其中一个

六爻语义(修订):
  初 几/萌芽   : 局部点状异常(小尺度尖峰)      -> 点缺陷/脏点/小破洞
  二 纹理一致  : 局部纹理规律性破坏(用LBP/LoG) -> 纹理缺陷
  三 边缘/轮廓 : 边缘能量/方向异常             -> 裂纹/划痕/断裂
  四 邻域对比  : 残差空间梯度(边界锐度)        -> 区域异常边界
  五 色泽/材质 : 饱和度+亮度通道偏移(不混hue)  -> 变色/油渍/污染
  六 全局结构  : 前景形状/分布偏差             -> 形状变形/大范围缺陷
"""
import os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from scipy import ndimage
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); SIZE=(160,160)

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

def yao6(g, rgb, ref):
    """ref: 正常模板字典 {T,S,Rt,St,Et,Vt}"""
    T,S,Rt,St,Et=ref["T"],ref["S"],ref["Rt"],ref["St"],ref["Et"]
    R=np.abs(g-T)/(S+1e-3); Rb=filters.gaussian(R,2.0)
    out=np.zeros(6)
    # 初: 点状尖峰(小尺度 - 大尺度)
    out[0]=np.percentile(np.maximum(0.0,filters.gaussian(R,1.0)-filters.gaussian(R,6.0)),99.5)
    # 二: 纹理规律性破坏 -> 用 LoG 能量与正常模板比
    lg=np.abs(filters.laplace(filters.gaussian(g,1.5)))
    out[1]=np.mean(np.abs(filters.gaussian(lg,2)-filters.gaussian(Et,2)))
    # 三: 边缘方向异常
    eg=np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2)
    out[2]=np.mean(np.abs(eg-Et))+np.std(np.abs(eg-Et))
    # 四: 残差空间梯度(边界锐度)
    gy,gx=np.gradient(Rb); out[3]=np.percentile(np.sqrt(gy**2+gx**2),99.5)
    # 五: 饱和度 + 亮度通道偏移(不混hue)
    hsv=color.rgb2hsv(np.clip(rgb,0,1)); Th,Shh=ref["Th"],ref["Sh"]
    ds=np.abs(hsv[...,1]-Th[...,1])/(Shh[...,1]+1e-3)
    dv=np.abs(hsv[...,2]-Th[...,2])/(Shh[...,2]+1e-3)
    out[4]=np.percentile(np.maximum(ds,dv),99.5)
    # 六: 全局形状/分布(前景质心矩偏离)
    fg=(g>np.percentile(g,60)).astype(float); ft=(T>np.percentile(T,60)).astype(float)
    out[5]=np.mean(np.abs(ndimage.gaussian_filter(fg,5)-ndimage.gaussian_filter(ft,5)))
    return out

def build_ref(train):
    G=np.array([load_gray(p) for p,_ in train]); T=G.mean(0); S=G.std(0)
    RGB=np.array([load_rgb(p) for p,_ in train]); Rt=RGB.mean(0); St=RGB.std(0)
    Et=np.mean([np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2) for g in G],0)
    HSV=np.array([color.rgb2hsv(np.clip(r,0,1)) for r in RGB])
    return dict(T=T,S=S,Rt=Rt,St=St,Et=Et,Th=HSV.mean(0),Sh=HSV.std(0))

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        ref=build_ref(train)
        Ftr=np.array([yao6(load_gray(p),load_rgb(p),ref) for p,_ in train])
        mu,sd=Ftr.mean(0),Ftr.std(0)+1e-9
        C=np.corrcoef(((Ftr-mu)/sd).T); evals=np.linalg.eigvalsh(C)[::-1]
        labels=[]; Fte=[]
        for p,d in test:
            Fte.append(yao6(load_gray(p),load_rgb(p),ref)); labels.append(0 if d=="good" else 1)
        labels=np.array(labels); Fte=np.array(Fte)
        aucs=[roc_auc_score(labels,Fte[:,i]) for i in range(6)]
        print(f"\n{cat:12s} 有效维度={int((evals>1).sum())} | 各爻AUROC: " +
              " ".join(f"爻{i}={a:.2f}" for i,a in enumerate(aucs)))
        print("  最大相关(非对角): " +
              f"{max(abs(C[i,j]) for i in range(6) for j in range(6) if i!=j):.2f}")

if __name__=="__main__": main()
