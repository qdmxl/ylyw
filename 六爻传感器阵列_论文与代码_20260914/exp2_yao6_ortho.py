#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
六爻正交化: 六个本质不同的视觉"象"
================================================================================
诊断结论: 原六统计量相关性0.99, 有效维度=1 -> 六爻实为同一信息。
本方案: 六爻 = 六个物理意义不同的视觉量, 期望低相关、各有判别力。

六爻语义:
  初(几/萌芽)  : 局部小异常点强度  -> 残差局部峰值的"点状性"
  二(内中之柔) : 区域内部纹理一致性 -> 残差纹理熵(局部)
  三(内卦之极) : 边缘/轮廓破坏     -> 梯度/边缘能量变化
  四(外卦之初) : 局部邻域对比度     -> 残差的空间梯度(对比)
  五(外卦之中) : 色度/材质偏移     -> 颜色通道偏离(HSV色度/饱和度)
  六(事之成)   : 全局结构/形状偏差  -> 前景形状/全局残差分布

每爻给出 0~1 的"失位幅度", 再按变爻位置加权。
"""
import os, sys
import numpy as np
from skimage import io, color, filters, measure, feature
from skimage.transform import resize
from scipy import ndimage

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); SIZE=(160,160)

def load_gray(path):
    im=io.imread(path)
    g=color.rgb2gray(im) if im.ndim==3 else im.astype(float)
    g=(g-g.min())/(np.ptp(g)+1e-9); return resize(g,SIZE,anti_aliasing=True)
def load_hsv(path):
    im=io.imread(path)
    if im.ndim==2:
        rgb=np.stack([im]*3,-1)/255.0
    else:
        rgb=im[...,:3]/255.0
    rgb=resize(rgb,SIZE,anti_aliasing=True)
    return color.rgb2hsv(rgb)
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

# ---------------- 六个"象" ----------------
def yao6(g, hsv, T, S, Th, Sh):
    """返回 6 个非负"失位幅度"(越大越异常/越失位)。"""
    out=np.zeros(6)
    R=np.abs(g-T)/(S+1e-3); Rb=filters.gaussian(R,2.0)

    # 初爻(几): 局部点状异常强度 -> 用小尺度高斯(点)对比大尺度(背景)的峰
    small=filters.gaussian(R,1.0); large=filters.gaussian(R,6.0)
    pointness=np.maximum(0.0, small-large)                 # 局部尖峰
    out[0]=np.percentile(pointness,99.5)

    # 二爻(纹理一致性): 残差图局部纹理熵(高熵=纹理紊乱)
    g8=np.clip(Rb/ (Rb.max()+1e-9) *255,0,255).astype(np.uint8)
    ent=filters.rank.entropy(g8,np.ones((7,7))).astype(float)/8.0
    out[1]=np.mean(ent)

    # 三爻(边缘破坏): 边缘能量相对正常模板
    eg=np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2)
    et=np.sqrt(filters.sobel_h(T)**2+filters.sobel_v(T)**2)
    out[2]=np.mean(np.abs(eg-et))

    # 四爻(邻域对比): 残差的空间梯度
    gy,gx=np.gradient(Rb)
    out[3]=np.mean(np.sqrt(gy**2+gx**2))

    # 五爻(色度偏移): 色度/饱和度偏离正常
    Rh=np.abs(hsv[...,0]-Th[...,0]); Rh=np.minimum(Rh,1-Rh)  # 色相环形距离
    Rs=np.abs(hsv[...,1]-Th[...,1])
    out[4]=np.percentile(np.maximum(Rh/ (Sh[...,0]+1e-3), Rs/(Sh[...,1]+1e-3)),99.5)

    # 六爻(结构/形状): 前景形状与正常模板的差异(用二值前景质心/面积/分布)
    fg=g> (np.percentile(g,60)); ft=T> (np.percentile(T,60))
    out[5]=np.mean(np.abs(ndimage.gaussian_filter(fg.astype(float),4)-
                          ndimage.gaussian_filter(ft.astype(float),4)))
    return out

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        G=np.array([load_gray(p) for p,_ in train]); T=G.mean(0); S=G.std(0)
        H=np.array([load_hsv(p) for p,_ in train]); Th=H.mean(0); Sh=H.std(0)
        Ftr=np.array([yao6(load_gray(p),load_hsv(p),T,S,Th,Sh) for p,_ in train])
        mu,sd=Ftr.mean(0),Ftr.std(0)+1e-9
        # 六爻相关性
        C=np.corrcoef(((Ftr-mu)/sd).T)
        evals=np.linalg.eigvalsh(C)[::-1]
        print(f"\n{'='*72}\n{cat}: train={len(train)} test={len(test)}")
        print("六爻相关性矩阵(初..上):")
        for i in range(6):
            print("   "+" ".join(f"{C[i,j]:+.2f}" for j in range(6)))
        print(f"有效维度(特征值>1)= {int((evals>1).sum())}  evals={np.round(evals,2)}")
        # 各爻单独判别力
        labels=[]; Fte=[]
        for p,d in test:
            Fte.append(yao6(load_gray(p),load_hsv(p),T,S,Th,Sh)); labels.append(0 if d=="good" else 1)
        labels=np.array(labels); Fte=np.array(Fte)
        from sklearn.metrics import roc_auc_score
        aucs=[]
        print("各爻单独 AUROC (初..上):")
        for i in range(6):
            a=roc_auc_score(labels,Fte[:,i]); aucs.append(a)
        print("   "+" ".join(f"爻{i}={a:.3f}" for i,a in enumerate(aucs)))

if __name__=="__main__": main()
