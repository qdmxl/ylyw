#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根因诊断: 为什么检测效果不好?
=============================================================
假设H1: 只用了灰度, 丢弃颜色 -> 颜色类缺陷(如 contamination 变色)漏检
假设H2: 6个统计量高度相关(全是"残差大小"的变体) -> 信息冗余, 非真正6维
假设H3: "只有正向偏离算数"(dev>0) -> 若某缺陷让特征变小(负偏离)则漏检
假设H4: 缺陷是"局部/空间"的, 但统计量把空间信息压成标量 -> 丢失位置
假设H5: 一个正常样本内部的自然波动 > 缺陷引起的波动
"""
import os, sys
import numpy as np
from skimage import io, color, filters, measure
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec"); SIZE=(160,160)

def load_gray(path):
    im=io.imread(path)
    g=color.rgb2gray(im) if im.ndim==3 else im.astype(float)
    g=(g-g.min())/(np.ptp(g)+1e-9); return resize(g,SIZE,anti_aliasing=True)
def load_rgb(path):
    im=io.imread(path)
    if im.ndim==2: im=np.stack([im]*3,-1)
    return resize(im[...,:3]/255.0,SIZE,anti_aliasing=True)
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

def analyze(cat):
    train=load_split(cat,"train"); test=load_split(cat,"test")
    print(f"\n{'='*70}\n类别 {cat}: train={len(train)} test={len(test)}\n{'='*70}")
    imgs=np.array([load_gray(p) for p,_ in train]); T=imgs.mean(0); S=imgs.std(0)
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train]); mu,sd=Str.mean(0),Str.std(0)+1e-9

    # --- H2: 统计量相关性 ---
    print("H2 六统计量相关性矩阵 (训练正常样本):")
    Ztr=(Str-mu)/sd
    C=np.corrcoef(Ztr.T)
    print("   " + " ".join(f"f{i}" for i in range(6)))
    for i in range(6):
        print(f"  f{i} " + " ".join(f"{C[i,j]:+.2f}" for j in range(6)))
    evals=np.linalg.eigvalsh(C)[::-1]
    print(f"  特征值: {np.round(evals,2)}  -> 有效维度(>1): {int((evals>1).sum())}")

    # --- 正常样本内部的波动 vs 缺陷引起的波动 ---
    print("H5 正常样本内部波动 vs 缺陷波动(统计量标准差):")
    te_by_def={}
    for p,d in test:
        te_by_def.setdefault(d,[]).append(stats6(load_gray(p),T,S))
    print(f"  训练正常 sd = {np.round(sd,3)}")
    for d,arr in te_by_def.items():
        print(f"  {d:14s} 均值={np.round(np.mean(arr,0),3)}")

    # --- H1: 颜色信息是否被灰度化丢弃 ---
    print("H1 颜色通道检查 (bottle 有 contamination 变色缺陷):")
    rgb_tr=np.array([load_rgb(p) for p,_ in train])
    Tc=rgb_tr.mean(0); Sc=rgb_tr.std(0)+1e-3
    def color_res(p):
        rgb=load_rgb(p); Rc=np.abs(rgb-Tc)/Sc
        return float(np.percentile(filters.gaussian(Rc.mean(-1),2),99.9))
    labels=[]; gray_sc=[]; color_sc=[]
    for p,d in test:
        gray_sc.append(np.percentile(filters.gaussian(np.abs(load_gray(p)-T)/(S+1e-3),2),99.9))
        color_sc.append(color_res(p)); labels.append(0 if d=="good" else 1)
    labels=np.array(labels)
    print(f"  灰度 p99.9 AUROC = {roc_auc_score(labels,gray_sc):.4f}")
    print(f"  RGB  p99.9 AUROC = {roc_auc_score(labels,color_sc):.4f}")

    # --- H3: 负向偏离是否存在 ---
    print("H3 缺陷是否也引起'负向偏离'(特征变小)?")
    dev_te=np.array([(stats6(load_gray(p),T,S)-mu)/sd for p,_ in test])
    for i in range(6):
        pos=np.mean([dev_te[j,i] for j in range(len(labels)) if labels[j]==1 and dev_te[j,i]>0])
        neg=np.mean([dev_te[j,i] for j in range(len(labels)) if labels[j]==1 and dev_te[j,i]<0]) if any(dev_te[j,i]<0 for j in range(len(labels)) if labels[j]==1) else 0
        frac_neg=np.mean([dev_te[j,i]<0 for j in range(len(labels)) if labels[j]==1])
        print(f"  f{i}: 异常图正向偏离均值={pos:.2f}, 负向比例={frac_neg:.2f}")

if __name__=="__main__":
    for c in (sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile"]):
        analyze(c)
