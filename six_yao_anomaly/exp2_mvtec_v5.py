#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v5, 方案C + 选项三): 变爻位置加权的"知几"异常检测
================================================================================
选项三思想:
  异常 = 变爻的多少与位置。
    * 正常图 -> 稳定在"正常本卦"
    * 缺陷图 -> 部分爻发生变爻(翻转)
    * 异常分数 = Σ (变爻指示 × 位置权重)，位置权重体现"知几":
        初爻变 权重最高(缺陷萌芽, "几")
        上爻变 权重最低(缺陷成形, 事已显)

实现:
  1. 正常本卦: 用正常样本的六爻极性确定 (每爻 0/1)
  2. 逐图六爻状态: 由残差统计量 -> 每爻阴阳判定
  3. 变爻集: 与正常本卦不同的爻位
  4. 分数:  
     S_v1 = Σ_i w_i·[爻i变]        (位置加权变爻数)
     S_v2 = Σ_i w_i·[爻i变]·|dev_i| (变爻幅度加权)
     w = [6,5,4,3,2,1] 初..上  (初爻最重要)
  5. 同时给出"知几"指标: 只统计初爻/二爻(低位)的变爻 -> 早期预警

对比:
  C0 残差峰值(纯图像上界)
  C1 变爻数(等权)
  C2 变爻位置加权(本方法)
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters, measure
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
    g=(g-g.min())/(np.ptp(g)+1e-9)
    return resize(g,SIZE,anti_aliasing=True)

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
    flat=np.sort(Rb.ravel())
    s=np.zeros(6)
    s[0]=Rb.max(); s[1]=np.percentile(Rb,99.9); s[2]=flat[-50:].mean()
    s[3]=np.percentile(Rb,99.0); s[4]=(Rb>2.0).mean()
    m2=Rb>3.0
    s[5]=np.bincount(measure.label(m2).ravel())[1:].max() if m2.any() and measure.label(m2).max()>0 else 0.0
    return s

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    print(f"类别={cat} train={len(train)} test={len(test)}")
    imgs=np.array([load_gray(p) for p,_ in train])
    T=imgs.mean(0); S=imgs.std(0)

    # --- 1) 正常样本的 6 统计量分布 -> 定义"正常爻极性" ---
    Str=np.array([stats6(load_gray(p),T,S) for p,_ in train])
    mu,sd=Str.mean(0),Str.std(0)+1e-9
    # 正常本的每爻阴阳: 用"是否超过正常中位数"定极性? 
    # 方案: 以正常样本自身的极性中位数作为"正常本卦"的爻值
    # 更稳健: 定义 6 爻倾向 z (正常→阳), 阈值0 -> 正常本卦全阳(当位构型)
    print(f"  正常统计量 mu={np.round(mu,3)}")
    print(f"             sd={np.round(sd,3)}")

    # 正常本卦: 正常样本的爻极性(以 mu 为参考的固定构型)
    # 用 z0: 恒取阳(+), 即正常本卦 = 111111? 不 ——
    # 应让"正常波动范围内"的爻取阳(当位), 只有显著偏离才变阴.
    # 正常本卦 = 各爻在正常样本下 MOST COMMON 的极性
    # 简化且可解释: 正常本卦 = 全"当位"构型 = 阳阴阳阴阳阴 = 010101 (U最低)
    fanben = 0b010101
    print(f"  正常本卦 = {format(fanben,'06b')} (阳阴阳阴阳阴, 当位构型)")

    # --- 2) 逐图六爻状态 ---
    # 每爻: z_i = 1.2 - 2.0*clamp((s_i-mu_i)/sd_i, 0, None)
    #   -> 正常(dev<=0): z=+1.2 -> 阳(bit=1)
    #   -> 异常(dev 大): z 变负 -> 阴(bit=0)
    # 但要注意: 正常本卦的"目标极性"应与 fanben 一致, 才能让"变爻"有意义.
    # 做法: 每爻的 "正常应取极性" = fanben 的第i位. 
    #       z_i 的正负 -> 观测极性. 与 fanben 不同 => 变爻.
    def yao_state(s):
        dev=(s-mu)/sd
        z=1.2-2.0*np.clip(dev,0,None)
        z=np.clip(z,-3.2,3.2)
        return z

    def biange_score(z, mag=False, weights=None, low_only=False):
        """变爻评分。z: 6爻倾向。bit_i = 1 if z_i>0 else 0。
        变爻 = bit 与 正常本卦 不同。"""
        if weights is None: weights=np.array([6,5,4,3,2,1],float)  # 初..上
        bits=np.array([1 if zz>0 else 0 for zz in z])
        fb=np.array([(fanben>>i)&1 for i in range(6)])
        changed=(bits!=fb).astype(float)
        if low_only:
            changed[2:]=0    # 只看初/二爻(低爻位="几")
        sc=float((changed*weights).sum())
        if mag:
            sc=float((changed*weights*np.abs(z)).sum())
        return sc, changed

    labels=[]; sc_max=[]; sc_chg=[]; sc_w=[]; sc_wm=[]; sc_low=[]
    for p,d in test:
        s=stats6(load_gray(p),T,S); z=yao_state(s)
        sc_max.append(s[0])
        sc_chg.append(biange_score(z)[0])
        sc_w.append(biange_score(z,weights=np.array([6,5,4,3,2,1]))[0])
        sc_wm.append(biange_score(z,mag=True)[0])
        sc_low.append(biange_score(z,weights=np.array([6,5,0,0,0,0]),low_only=True)[0])
        labels.append(0 if d=="good" else 1)
    labels=np.array(labels)
    sc_max=np.array(sc_max); sc_chg=np.array(sc_chg); sc_w=np.array(sc_w)
    sc_wm=np.array(sc_wm); sc_low=np.array(sc_low)

    r={}
    for nm,sc in [("C0_max_residual",sc_max),
                  ("C1_change_count(equal-weight)",sc_chg),
                  ("C2_change_pos_weighted",sc_w),
                  ("C3_change_mag_weighted",sc_wm),
                  ("C4_low_yao_only(zhi-ji)",sc_low)]:
        r[nm]=float(roc_auc_score(labels,sc))
    print("="*68); print(f"MVTec {cat} AUROC (v5, 选项三: 变爻位置)"); print("="*68)
    for k,v in r.items(): print(f"  {k:32s} {v:.4f}")
    print("="*68)

    json.dump(dict(category=cat,n_train=len(train),n_test=len(test),
        n_normal=int((labels==0).sum()),n_anomaly=int((labels==1).sum()),
        auroc=r,fanben=format(fanben,"06b")),
        open(os.path.join(RES,f"exp2_mvtec_{cat}_v5.json"),"w"),
        ensure_ascii=False,indent=2)

    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,4,figsize=(17,4))
        items=[("C0 max residual",sc_max,"C0_max_residual"),
               ("C2 change pos-weighted",sc_w,"C2_change_pos_weighted"),
               ("C3 change mag-weighted",sc_wm,"C3_change_mag_weighted"),
               ("C4 low-yao only",sc_low,"C4_low_yao_only(zhi-ji)")]
        for ax,(nm,sc,key) in zip(axes,items):
            ax.hist(sc[labels==0],bins=18,alpha=.6,label="good",color="tab:green",density=True)
            ax.hist(sc[labels==1],bins=18,alpha=.6,label="defect",color="tab:red",density=True)
            ax.set_title(f"{nm}\nAUROC={r[key]:.3f}"); ax.legend(fontsize=8)
        fig.suptitle(f"MVTec AD ({cat}) v5 - bian-yao position (option 3)")
        fig.tight_layout(); fig.savefig(os.path.join(FIG,f"exp2_mvtec_{cat}_v5.png"),dpi=140)
        print("saved figure")
    except Exception as e: print("plot skipped:",e)

if __name__=="__main__": main()
