#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验3(Y1+Y3): 易理六爻 + 在线增量学习 的工业异常检测
================================================================================
方法论定位:
  * 无监督(理解一): 只用正常样本, 缺陷样本永不参与学习 -> 零样本(没见过缺陷)
  * Y1 增量学习: 正常"卦分布"用 Welford 在线更新, 支持冷启动与累积
  * Y3 易理结构: 六爻语义人工指定(可解释), 变爻位置加权(初重="知几")

六爻语义(易理 ↔ 视觉):
  初(几/萌芽) 局部点状异常   : 小尺度残差尖峰
  二(内中之柔)纹理一致性     : LoG 纹理能量偏离
  三(内卦之极)边缘/轮廓      : 边缘能量偏离
  四(外卦之初)邻域对比       : 残差空间梯度
  五(外卦之中)色泽/材质      : 饱和度+亮度偏移
  六(事之成)  全局结构       : 前景形状偏离

在线学习流程:
  t=1: 用 1 张正常图 -> 初始卦分布(方差取经验下限)
  t=2..N: 每张正常图 -> 六爻 -> 卦象 -> Welford 增量更新
  测试: 新图 -> 卦象 -> 对数似然(异常度) + 变爻位置加权

输出: 学习曲线(正常样本数 vs AUROC) + 冷启动/饱和性能
"""
import os, sys, json
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize
from scipy import ndimage
from sklearn.metrics import roc_auc_score

BASE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,BASE)
DATA=os.path.join(BASE,"data","mvtec")
RES,FIG=os.path.join(BASE,"results"),os.path.join(BASE,"figures")
os.makedirs(RES,exist_ok=True); os.makedirs(FIG,exist_ok=True)
SIZE=(160,160)
FANBEN=[1,0,1,0,1,0]                       # 当位本卦(阳阴阳阴阳阴)
W_LOW=np.array([6,5,4,3,2,1.])              # 初重(知几)

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

def yao6(g, rgb):
    """六爻失位幅度(0~∞, 越大越异常)。不依赖任何模板, 用图内自参考量。"""
    out=np.zeros(6); R=None
    # 初: 点状尖峰 (对自身做多尺度, 不用模板)
    base=filters.gaussian(g,6.0)
    point=np.maximum(0.0, g-base)                    # 亮点
    point2=np.maximum(0.0, base-g)                   # 暗点
    out[0]=np.percentile(np.maximum(point,point2),99.5)
    # 二: 纹理能量(LoG)
    lg=np.abs(filters.laplace(filters.gaussian(g,1.5)))
    out[1]=np.percentile(filters.gaussian(lg,2),99.5)
    # 三: 边缘能量
    eg=np.sqrt(filters.sobel_h(g)**2+filters.sobel_v(g)**2)
    out[2]=np.percentile(eg,99.5)
    # 四: 空间对比(局部方差)
    loc_var=filters.gaussian(g**2,3)-filters.gaussian(g,3)**2
    out[3]=np.percentile(np.sqrt(np.maximum(loc_var,0)),99.5)
    # 五: 饱和度+亮度通道
    hsv=color.rgb2hsv(np.clip(rgb,0,1))
    out[4]=np.percentile(np.maximum(hsv[...,1], hsv[...,2]),99.5)
    # 六: 全局结构(前景分布的二阶矩范围)
    fg=(g>np.percentile(g,60)).astype(float)
    out[5]=np.abs(ndimage.gaussian_filter(fg,5)-fg).mean()
    return out

class OnlineGuaModel:
    """在线"卦分布"模型: 对六爻倾向 z 的多元高斯做 Welford 增量更新。
    异常分数 = 马氏距离(偏离正常卦分布) + 变爻位置加权。"""
    def __init__(self, dim=6):
        self.n=0; self.mean=np.zeros(dim); self.M2=np.zeros(dim)
        self.var=np.ones(dim)
    def update(self, z):
        self.n+=1; d=z-self.mean
        self.mean=self.mean+d/self.n
        self.M2=self.M2+d*(z-self.mean)
        if self.n>1:
            self.var=np.maximum(self.M2/(self.n-1), 1e-3)
    def score(self, z, position_weight=True):
        # 标准化偏离 (单变量马氏, 稳健)
        dev=np.abs(z-self.mean)/(np.sqrt(self.var)+1e-6)
        # 变爻: z 偏离当位期望的幅度
        exp=np.array([1 if b==1 else -1 for b in FANBEN],float)
        misfit=np.maximum(0.0,-z*exp)
        ch=(misfit>0).astype(float)
        pos=(ch*W_LOW*misfit).sum() if position_weight else (ch*misfit).sum()
        return float(dev.mean()+pos), float(dev.mean()), float(pos)

def z_from_yao(f, mu, sd):
    """六爻幅度 -> 六爻倾向 z (偏离正常越大越负)"""
    dev=(f-mu)/(sd+1e-9)
    return np.clip(1.2-2.0*np.clip(dev,0,None),-3.2,3.2)

def main():
    cats=sys.argv[1].split(",") if len(sys.argv)>1 else ["bottle"]
    allcurves={}
    for cat in cats:
        train=load_split(cat,"train"); test=load_split(cat,"test")
        # 预提取所有正常训练样本的六爻
        Ftr=np.array([yao6(load_gray(p),load_rgb(p)) for p,_ in train])
        # 用全训练集定 mu/sd(模拟"最终"标定; 在线学习单独体现在卦分布更新)
        mu,sd=Ftr.mean(0),Ftr.std(0)+1e-9
        # 测试集
        Flab=[]; Fte=[]
        for p,d in test:
            Fte.append(yao6(load_gray(p),load_rgb(p))); Flab.append(0 if d=="good" else 1)
        Flab=np.array(Flab); Fte=np.array(Fte)
        Zte=np.array([z_from_yao(f,mu,sd) for f in Fte])

        # 学习曲线: 用 1,2,4,...N 张正常样本增量训练
        N=len(Ftr)
        ckpts=[1,2,3,5,8,12,20,30,50,80,120,N]
        ckpts=sorted(set([c for c in ckpts if c<=N]))
        curve=[]
        for k in ckpts:
            model=OnlineGuaModel()
            for i in range(k):
                model.update(z_from_yao(Ftr[i],mu,sd))
            sc=np.array([model.score(z)[0] for z in Zte])
            sc_np=np.array([model.score(z)[2] for z in Zte])   # 纯位置加权项
            auc=roc_auc_score(Flab,sc); auc_np=roc_auc_score(Flab,sc_np)
            curve.append(dict(n_train=k,auroc=float(auc),auroc_posonly=float(auc_np)))
            print(f"  {cat}: n_train={k:3d}  AUROC={auc:.4f}  (仅位置项={auc_np:.4f})")

        # 用全部正常样本, 冷启动对比: 只用1张 vs 全量, 但用"固定判据"
        allcurves[cat]=curve

    json.dump(allcurves, open(os.path.join(RES,"exp3_online_learning.json"),"w"),
              ensure_ascii=False,indent=2)
    print("saved results/exp3_online_learning.json")

if __name__=="__main__": main()
