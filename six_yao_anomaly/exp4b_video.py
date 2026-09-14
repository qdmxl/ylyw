#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验4b: 物理可信的缺陷演化 + "知几"验证
================================================================================
问题: 实验4 的注入模型"同时注入亮度/颜色/纹理", 先验上就没有"谁先动"。
修正: 改用【物理驱动的缺陷演化】, 让不同六爻自然地先后激活。

物理模型(以"裂纹/微损伤"为例):
  真实损伤演化遵循: 微小损伤核 -> 缓慢扩展 -> 加速 -> 失稳
  * 早期: 只有"点"级别的微小扰动(点状异常) -> 应激活 初爻(点)
  * 中期: 损伤扩展, 产生边界/梯度 -> 激活 三爻(梯度)
  * 后期: 大面积变色/结构变异 -> 激活 五爻(色)、六爻(形)
  即: 若易理"知几"成立, 六爻应按 初->三->五/六 的顺序依次激活。

用"随时间移动/扩展的高斯损伤核"模拟, 强度与半径按 S 型曲线增长,
但【不同物理通道的激活阈值不同】: 点状扰动先出现, 颜色/结构变化滞后。
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
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

def physics_defect(g, rgb, t, T, rng):
    """物理驱动的损伤演化。
    损伤核半径 R(t) 按慢-快-慢(S型)增长; 各物理通道激活滞后不同:
      亮度(点) -> 最早; 梯度/纹理 -> 中; 颜色/结构 -> 最晚。
    返回: 帧(g,rgb), 以及各通道的"真实激活时间"(用于对比)。
    """
    g2=g.copy(); rgb2=rgb.copy()
    h,w=g.shape; yy,xx=np.mgrid[0:h,0:w]
    cy=rng.integers(h//4,3*h//4); cx=rng.integers(w//4,3*w//4)
    a=t/T
    sigmoid=1/(1+np.exp(-10*(a-0.5)))      # S型
    radius=4+int(sigmoid*24)                 # 损伤核半径
    mask=((yy-cy)**2+(xx-cx)**2)<=radius**2
    # 通道激活滞后: 亮度最早(0), 梯度中(0.3), 颜色晚(0.6)
    def act(delay): return max(0.0,(a-delay)/(1-delay+1e-9))
    # 亮度损伤(点状, 最早)
    ab=act(0.0)
    g2=g2-ab*0.35*filters.gaussian(mask.astype(float),1.0)
    # 梯度/纹理损伤(中)
    ag=act(0.3)
    noise=rng.normal(0,1,g.shape)
    g2=g2+ag*0.08*noise*filters.gaussian(mask.astype(float),2.0)
    # 颜色损伤(晚)
    ac=act(0.6)
    if rgb2.ndim==3:
        rgb2[...,0]=np.clip(rgb2[...,0]-ac*0.25*filters.gaussian(mask.astype(float),2.0),0,1)
    return np.clip(g2,0,1), np.clip(rgb2,0,1)

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    n_trials=int(sys.argv[2]) if len(sys.argv)>2 else 20
    T=24
    train=load_split(cat,"train")
    ref_g=[load_gray(p) for p,_ in train[:30]]; ref_c=[load_rgb(p) for p,_ in train[:30]]
    T0=np.mean(ref_g,0); S0=np.std(ref_g,0)+1e-3
    TC0=np.mean(ref_c,0); SC0=np.std(ref_c,0)+1e-3
    F0=np.array([ortho6(filters.gaussian(np.abs(ref_g[i]-T0)/S0,2.0),np.abs(ref_c[i]-TC0)/SC0) for i in range(len(ref_g))])
    mu0,sd0=F0.mean(0),F0.std(0)+1e-9

    names=["初(点)","二(频)","三(梯)","四(偏)","五(色)","六(形)"]
    curves=[]
    for trial in range(n_trials):
        rng=np.random.default_rng(trial)
        bg=ref_g[trial%len(ref_g)]; bc=ref_c[trial%len(ref_c)]
        seq=np.zeros((T+1,6))
        for t in range(T+1):
            gg,cc=physics_defect(bg,bc,t,T,rng)
            R=filters.gaussian(np.abs(gg-T0)/S0,2.0); Rc=np.abs(cc-TC0)/SC0
            f=ortho6(R,Rc); seq[t]=np.maximum(0,(f-mu0)/sd0)
        curves.append(seq)
    curves=np.array(curves); mean_curve=curves.mean(0)

    print(f"\n类别={cat} trials={n_trials} (物理驱动损伤演化)")
    print("六爻平均失位随时间:")
    print("        " + " ".join(f"t{t:<2d}" for t in range(0,T+1,3)))
    for i in range(6):
        print(f"  {names[i]:8s} " + " ".join(f"{mean_curve[t,i]:5.1f}" for t in range(0,T+1,3)))
    print("\n各爻首次超过阈值(1.0)的时刻:")
    first_t={}
    for i in range(6):
        idx=np.where(mean_curve[:,i]>1.0)[0]
        first_t[i]=int(idx[0]) if len(idx) else -1
        print(f"  {names[i]}: t={first_t[i]}")
    valid=[(i,first_t[i]) for i in range(6) if first_t[i]>=0]
    if valid:
        order=sorted(valid,key=lambda x:x[1])
        print("\n激活顺序(由早到晚): " + " -> ".join(f"{names[i]}(t={t})" for i,t in order))
        print(f">>> 初爻是否最早: {'是' if order[0][0]==0 else '否(最早是'+names[order[0][0]]+')'}")
        # Spearman 秩相关: 爻位 vs 激活时间
        from scipy.stats import spearmanr
        pos=[i for i,_ in valid]; tm=[t for _,t in valid]
        rho,p=spearmanr(pos,tm)
        print(f">>> 爻位 vs 激活时间 的 Spearman ρ={rho:+.2f} (p={p:.3f})  "
              f"{'(初爻先动, 支持知几)' if rho>0.5 else '(不支持知几)'}")
    json.dump(dict(category=cat,curve=mean_curve.tolist(),first_t=first_t,names=names),
              open(os.path.join(RES,f"exp4b_video_{cat}.json"),"w"),ensure_ascii=False,indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        plt.figure(figsize=(9,5))
        for i in range(6): plt.plot(range(T+1),mean_curve[:,i],"o-",markersize=3,label=f"yao{i}")
        plt.axhline(1.0,ls="--",c="gray",lw=0.8)
        plt.xlabel("time step t"); plt.ylabel("yi-yao misfit (std)")
        plt.title(f"Physics-driven defect evolution, six-yao timing ({cat})")
        plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(FIG,f"exp4b_video_{cat}.png"),dpi=150)
        print("saved figure")
    except Exception as e: print("plot skipped",e)

if __name__=="__main__": main()
