#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验4: 连续视频"知几"时序预警验证
================================================================================
目标(核心):
  验证易理"知几"—— 缺陷演化中【初爻是否先动】, 并测量预警提前量。

设计:
  1. 取一张正常图作为"初始帧"。
  2. 沿时间轴 t=0..T 逐步注入缺陷(从小到大的渐进退化):
       退化强度 a(t) 从 0 线性/指数增长到 1。
  3. 每帧提取六爻(正交六爻), 计算每爻相对正常基线的"失位幅度"。
  4. 观察:
       - 各爻失位随时间的曲线 m_i(t)
       - 【关键】初爻(爻0)是否比其他爻更早达到阈值? -> "知几"
       - 首次超过检测阈值的时刻 t_detect, 与"肉眼可见"时刻 t_vis 之差 = 提前量

缺陷注入模型(物理可信):
  * 用"局部退化": 在随机位置注入一个逐渐增强/扩大的异常区
     - 亮度偏移(dark spot) / 纹理扰动 / 颜色偏移 / 结构变化
  * a(t) 控制强度, 面积随 t 同时增长(渐变缺陷)
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters, measure, morphology, draw
from skimage.transform import resize
from scipy import ndimage
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES,FIG=os.path.join(BASE,"results"),os.path.join(BASE,"figures")
os.makedirs(RES,exist_ok=True); os.makedirs(FIG,exist_ok=True)
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

def ortho6(R, Rc):
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

def inject_defect(g, rgb, a, rng, kind="mix"):
    """在图像上注入渐进缺陷。a∈[0,1] 强度。"""
    g2=g.copy(); rgb2=rgb.copy()
    h,w=g.shape
    yy,xx=np.mgrid[0:h,0:w]
    # 缺陷中心随机
    cy=rng.integers(h//4,3*h//4); cx=rng.integers(w//4,3*w//4)
    radius=6+int(a*22)                      # 面积随强度增长
    mask=((yy-cy)**2+(xx-cx)**2) <= radius**2
    maskf=filters.gaussian(mask.astype(float),2.0)
    if kind in ("mix","dark"):
        g2=g2-a*0.5*maskf                    # 变暗
    if kind in ("mix","color") and rgb2.ndim==3:
        rgb2[...,0]=np.clip(rgb2[...,0]-a*0.3*maskf,0,1)  # 偏色
        rgb2[...,1]=np.clip(rgb2[...,1]-a*0.15*maskf,0,1)
    if kind in ("mix","texture"):
        noise=rng.normal(0,a*0.15,g.shape)
        g2=g2+noise*maskf
    return np.clip(g2,0,1), np.clip(rgb2,0,1), mask

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    n_trials=int(sys.argv[2]) if len(sys.argv)>2 else 10
    T=20                                    # 时间步
    train=load_split(cat,"train")
    # 正常基线: 用前 30 张正常图建模板
    ref_g=[load_gray(p) for p,_ in train[:30]]; ref_c=[load_rgb(p) for p,_ in train[:30]]
    T0=np.mean(ref_g,0); S0=np.std(ref_g,0)+1e-3
    TC0=np.mean(ref_c,0); SC0=np.std(ref_c,0)+1e-3
    # 正常六爻分布(用于标定)
    F0=np.array([ortho6(filters.gaussian(np.abs(ref_g[i]-T0)/S0,2.0),np.abs(ref_c[i]-TC0)/SC0) for i in range(len(ref_g))])
    mu0,sd0=F0.mean(0),F0.std(0)+1e-9

    # 逐 trial: 随机初始图 + 随机缺陷, 记录每帧六爻失位
    curves=[]   # (T+1, 6)
    for trial in range(n_trials):
        rng=np.random.default_rng(trial)
        base_g=ref_g[trial % len(ref_g)]; base_c=ref_c[trial % len(ref_c)]
        seq=np.zeros((T+1,6))
        for t in range(T+1):
            a=t/T
            gg,cc,_=inject_defect(base_g,base_c,a,rng)
            R=filters.gaussian(np.abs(gg-T0)/S0,2.0); Rc=np.abs(cc-TC0)/SC0
            f=ortho6(R,Rc)
            dev=(f-mu0)/sd0                     # 标准化偏离
            seq[t]=np.maximum(0,dev)            # 失位幅度(只取正向偏离)
        curves.append(seq)
    curves=np.array(curves)                     # (n_trials, T+1, 6)
    mean_curve=curves.mean(0)                   # (T+1, 6)

    print(f"\n类别={cat} trials={n_trials} 时间步={T}")
    print("六爻平均失位随时间 (t=0..T):")
    print("      " + " ".join(f"t{t:<2d}" for t in range(0,T+1,2)))
    names=["初(点)","二(频)","三(梯)","四(偏)","五(色)","六(形)"]
    for i in range(6):
        row=" ".join(f"{mean_curve[t,i]:4.1f}" for t in range(0,T+1,2))
        print(f"  {names[i]} {row}")

    # 关键: 各爻"首次达到阈值"的时刻
    # 阈值取该爻在 t=0(正常)时的 2 倍 or 固定
    print("\n各爻首次超过阈值的时刻 (阈值=1.0 标准化偏离):")
    first_t={}
    for i in range(6):
        c=mean_curve[:,i]
        idx=np.where(c>1.0)[0]
        first_t[i]=int(idx[0]) if len(idx) else -1
        print(f"  {names[i]}: t={first_t[i]}")
    ge=np.array([first_t[i] for i in range(6) if first_t[i]>=0])
    if len(ge):
        print(f"\n>>> 最早动的爻: {names[np.argmin([first_t[i] if first_t[i]>=0 else 999 for i in range(6)])]} (t={ge.min()})")
        print(f">>> 初爻(爻0)首次动: t={first_t[0]}  | 全体均值 t={ge.mean():.1f}")
        print(f">>> '知几'验证: 初爻是否最早? {'是' if first_t[0]==ge.min() else '否'}")

    json.dump(dict(category=cat,curve=mean_curve.tolist(),first_t=first_t),
              open(os.path.join(RES,f"exp4_video_{cat}.json"),"w"),ensure_ascii=False,indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        plt.figure(figsize=(9,5))
        for i in range(6):
            plt.plot(range(T+1),mean_curve[:,i],"o-",markersize=3,label=names[i])
        plt.axhline(1.0,ls="--",c="gray",lw=0.8,label="threshold")
        plt.xlabel("time step t (defect develops 0->1)")
        plt.ylabel("mean yi-yao misfit (std)")
        plt.title(f"Six-yao temporal evolution ({cat}): who moves first?")
        plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(FIG,f"exp4_video_{cat}.png"),dpi=150)
        print("saved figure")
    except Exception as e: print("plot skipped",e)

if __name__=="__main__": main()
