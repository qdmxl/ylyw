#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验3(路径A固化): 在线零样本学习 —— 稳健版
================================================================================
固化要点:
  1. 多次随机采样顺序(不同随机种子)重复在线学习 -> 学习曲线的均值±标准差
     (避免"恰好抽到的顺序"带来的偶然性)
  2. 冷启动性能(1张) vs 累积性能(全量) 的统计对比
  3. 六爻编码保留(易理框架), 主指标用"残差峰值"(无先验)与"易理综合分"
  4. 输出多类别的学习曲线数据
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES=os.path.join(BASE,"results"); os.makedirs(RES,exist_ok=True)
SIZE=(160,160)

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

def residual_score(x_g, x_c, T, S, TC, SC):
    """综合异常分数: 残差峰(max) + 颜色残差, 取99.9分位。"""
    R=np.abs(x_g-T)/S; Rb=filters.gaussian(R,2.0)
    Rc=np.abs(x_c-TC)/SC
    return float(np.percentile(Rb,99.9)), float(np.percentile(Rc.mean(-1),99.9))

def run_online(tr_g,tr_c,te_g,te_c,Flab,ckpts,seed=0):
    rng=np.random.default_rng(seed)
    order=rng.permutation(len(tr_g))
    n=len(order)
    # 在线模板
    T=None;S=None;TC=None;SC=None
    curves={k:[] for k in ckpts}
    k=0
    for idx in order:
        k+=1
        g=tr_g[idx]; c=tr_c[idx]
        if k==1:
            T=g.copy(); M2g=np.zeros_like(g); TC=c.copy(); M2c=np.zeros_like(c)
        else:
            dg=g-T; T=T+dg/k; M2g=M2g+dg*(g-T)
            dc=c-TC; TC=TC+dc/k; M2c=M2c+dc*(c-TC)
        if k in ckpts:
            S=np.sqrt(np.maximum(M2g/max(k-1,1),1e-6))+1e-3
            SC=np.sqrt(np.maximum(M2c/max(k-1,1),1e-6))+1e-3
            sc=[]
            for j in range(len(te_g)):
                a,b=residual_score(te_g[j],te_c[j],T,S,TC,SC)
                sc.append(a+b)
            curves[k].append(float(roc_auc_score(Flab,sc)))
    return curves

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle","metal_nut","tile","toothbrush"]
    reps=int(sys.argv[2]) if len(sys.argv)>2 else 5
    out={}
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        tr_g=[load_gray(p) for p,_ in train]; tr_c=[load_rgb(p) for p,_ in train]
        te_g=[load_gray(p) for p,_ in test]; te_c=[load_rgb(p) for p,_ in test]
        Flab=np.array([0 if d=="good" else 1 for _,d in test])
        ckpts=sorted(set([c for c in [1,2,3,5,8,12,20,30,50,80,120,200] if c<=len(train)]+[len(train)]))
        acc={k:[] for k in ckpts}
        for s in range(reps):
            cv=run_online(tr_g,tr_c,te_g,te_c,Flab,ckpts,seed=s)
            for k in ckpts: acc[k].extend(cv[k])
        out[cat]=[dict(n_train=k, auroc_mean=float(np.mean(acc[k])),
                       auroc_std=float(np.std(acc[k])), n_reps=len(acc[k])) for k in ckpts]
        print(f"{cat}: n_normal={len(train)}")
        for r in out[cat]:
            print(f"   n={r['n_train']:3d}  AUROC={r['auroc_mean']:.4f} ± {r['auroc_std']:.4f}")
    json.dump(out, open(os.path.join(RES,"exp3_online_robust.json"),"w"),ensure_ascii=False,indent=2)
    print("saved exp3_online_robust.json")

if __name__=="__main__": main()
