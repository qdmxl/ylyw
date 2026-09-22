#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验2(v2, 真实数据): MVTec AD 上的 YLYW 易理加权异常检测
================================================================================
v1 教训:
  * 用"全图特征偏离正常均值的绝对值"当爻倾向 -> 正常/异常不可分(AUROC 0.29)
  * 根因: 单张图全图统计对小缺陷不敏感; 丢失方向; 未做局部聚合。

v2 设计(修正):
  1. 【局部化】把图分 NxN 网格, 每块提特征 -> 与"正常块统计"比较,
     取偏离最大的若干块(缺陷是局部的, 会体现在局部块)。
  2. 【方向保持】每爻的倾向 z 由"局部偏离的极性"决定:
       正常 -> 各爻趋向"当位"构型(稳定卦)
       异常 -> 偏离加剧, 逐爻"失位", 高U(失和)卦涌现
  3. 【六爻语义】六爻对应六类"象":
       初=整体亮度  二=局部对比  三=纹理粗糙   四=边缘密度  五=色度偏移  六=结构复杂度
  4. 六爻倾向 z_i ∈ [-a, +a]:
       该维度"正常" -> z_i 取正(阳/当位侧)
       该维度"异常偏离" -> z_i 变负(阴/失位侧), 偏离越大越负
     使得异常图 -> 更多阴爻 -> 失位/失和卦。
"""
import json, os, sys
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)

# ---------------- 易理势能 ----------------
def yao(q,i): return (q>>i)&1
def U(q):
    bud = sum(1 for i in range(6) if yao(q,i)!=(1 if i%2==0 else 0))
    shz = 0 if yao(q,1)!=yao(q,4) else 1
    buy = sum(1 for a,b in [(0,3),(1,4),(2,5)] if yao(q,a)==yao(q,b))
    cg  = sum(1 for i in range(5) if yao(q,i)==1 and yao(q,i+1)==0)
    return bud+0.8*shz+0.6*buy+0.5*cg
ALL=list(range(64)); Uvals=np.array([U(q) for q in ALL]); Umin=Uvals.min()
ANOMALOUS=set(q for q in ALL if U(q)>=np.percentile(Uvals,75))
HARMONIC =set(q for q in ALL if U(q)<=np.percentile(Uvals,25))

def base_dist(z):
    p=1/(1+np.exp(-z)); p=np.clip(p,1e-6,1-1e-6)
    d=np.ones(64)
    for q in range(64):
        for i in range(6): d[q]*= p[i] if yao(q,i)==1 else (1-p[i])
    return d/d.sum()
def anomaly_mass(d): return float(sum(d[q] for q in ANOMALOUS))
def ylyw_weighted(z, lam=0.9):
    d=base_dist(z); w=d*np.exp(-lam*(Uvals-Umin)); return w/w.sum()

# ---------------- 分块特征 ----------------
GRID = 4
def block_features(img_path, size=(160,160)):
    im = io.imread(img_path)
    if im.ndim==3:
        gray=color.rgb2gray(im); hsv=color.rgb2hsv(im); sat=hsv[...,1]
    else:
        gray=im.astype(float); gray=(gray-gray.min())/(gray.ptp()+1e-9); sat=np.zeros_like(gray)
    gray=resize(gray,size,anti_aliasing=True); sat=resize(sat,size,anti_aliasing=True)
    h,w=gray.shape
    feats=[]  # 每块6维: 亮度/局部对比/纹理/边缘/色度/结构熵
    for i in range(GRID):
        for j in range(GRID):
            gy=gray[i*h//GRID:(i+1)*h//GRID, j*w//GRID:(j+1)*w//GRID]
            sa=sat[i*h//GRID:(i+1)*h//GRID, j*w//GRID:(j+1)*w//GRID]
            if gy.size==0: continue
            lap=filters.laplace(gy); sob=filters.sobel(gy)
            f0=gy.mean()
            f1=gy.std()
            f2=np.abs(lap).mean()
            f3=sob.mean()
            f4=sa.mean()
            g8=(gy*255).astype(np.uint8)
            f5=filters.rank.entropy(g8,np.ones((5,5))).mean()/8.0
            feats.append([f0,f1,f2,f3,f4,f5])
    return np.array(feats)   # (GRID*GRID, 6)

# ---------------- 六爻编码 v2 ----------------
def z_from_blocks(block_feats, normal_model):
    """normal_model: 每个特征维的 (mu, sd) + 每块的典型偏离分布。
    对每个特征维 d: 计算所有块中 |偏离| 的最大值(max_dev_d)与均值(mean_dev_d),
    取 max_dev 作为"该维是否被异常激发"的指标 -> 转成爻倾向。"""
    mu, sd, dev_scale = normal_model["mu"], normal_model["sd"], normal_model["dev_scale"]
    dev = (block_feats - mu)/sd          # (nblock, 6)
    absdev = np.abs(dev)
    max_dev = absdev.max(0)              # 每维的最大偏离(最异常的块)
    # 相对正常正常波动(dev_scale=正常样本 max_dev 的分位) 的超出程度
    excess = np.maximum(0.0, max_dev - dev_scale)  # 超过正常波动的部分
    # 爻倾向: 无超出 -> 阳(+a, 当位); 超出越多 -> 越阴(-), 失位
    a = 1.2
    z = a - 2.2*np.tanh(excess/3.0)
    return z

def fit_normal_model(Fblocks):
    """Fblocks: (n_sample, nblock, 6)"""
    allb = Fblocks.reshape(-1, 6)
    mu, sd = allb.mean(0), allb.std(0)+1e-9
    # 正常样本每维 max_dev 的分布(用来定"正常波动上界")
    sample_maxdev = []
    for fb in Fblocks:
        dev = np.abs((fb-mu)/sd)
        sample_maxdev.append(dev.max(0))
    sample_maxdev = np.array(sample_maxdev)
    dev_scale = np.percentile(sample_maxdev, 90, axis=0)  # 90分位作正常上界
    return dict(mu=mu, sd=sd, dev_scale=dev_scale)

# ---------------- 数据 ----------------
def load_split(cat, split):
    d=os.path.join(DATA,cat,split); items=[]
    if not os.path.isdir(d): return items
    for defect in sorted(os.listdir(d)):
        dd=os.path.join(d,defect)
        if not os.path.isdir(dd): continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png",".jpg",".jpeg",".bmp")):
                items.append((os.path.join(dd,f), defect))
    return items

def main():
    cat=sys.argv[1] if len(sys.argv)>1 else "bottle"
    train=load_split(cat,"train"); test=load_split(cat,"test")
    print(f"类别={cat} train={len(train)} test={len(test)}")
    print("提取训练集分块特征...")
    Ftr=np.array([block_features(p) for p,_ in train])   # (n, nblock, 6)
    model=fit_normal_model(Ftr)
    print(f"  正常 dev_scale(90%)= {np.round(model['dev_scale'],2)}")

    labels=[]; sc_y=[]; sc_b=[]; sc_maha=[]
    for p,d in test:
        fb=block_features(p); z=z_from_blocks(fb,model)
        sc_b.append(anomaly_mass(base_dist(z)))
        sc_y.append(anomaly_mass(ylyw_weighted(z)))
        # 马氏: 用块级特征偏离的统计
        dev=((fb-model['mu'])/model['sd'])
        sc_maha.append(float(np.sqrt((dev**2).sum(1)).max()))  # 最大块偏离
        labels.append(0 if d=="good" else 1)
    labels=np.array(labels); sc_y=np.array(sc_y); sc_b=np.array(sc_b); sc_maha=np.array(sc_maha)
    print(f"  测试: 正常={int((labels==0).sum())} 异常={int((labels==1).sum())}")

    r={}
    for nm,sc in [("B1_observation",sc_b),("B3_ylyw_weighted",sc_y),("B2_maxblock_dev",sc_maha)]:
        try: r[nm]=float(roc_auc_score(labels,sc))
        except Exception: r[nm]=float("nan")
    print("="*60); print(f"MVTec {cat} 图像级 AUROC (v2)"); print("="*60)
    for k,v in r.items(): print(f"  {k:20s} {v:.4f}")
    print("="*60)

    json.dump(dict(category=cat,n_train=len(train),n_test=len(test),
                   n_normal=int((labels==0).sum()),n_anomaly=int((labels==1).sum()),
                   auroc=r),
              open(os.path.join(RES,f"exp2_mvtec_{cat}_v2.json"),"w"),
              ensure_ascii=False,indent=2)
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for ax,(nm,sc) in zip(axes,[("B1 obs",sc_b),("B3 YLYW",sc_y),("B2 maxblkdev",sc_maha)]):
            ax.hist(sc[labels==0],bins=18,alpha=.6,label="good",color="tab:green",density=True)
            ax.hist(sc[labels==1],bins=18,alpha=.6,label="defect",color="tab:red",density=True)
            key={"B1 obs":"B1_observation","B3 YLYW":"B3_ylyw_weighted","B2 maxblkdev":"B2_maxblock_dev"}[nm]
            ax.set_title(f"{nm} AUROC={r[key]:.3f}"); ax.legend(fontsize=8)
        fig.suptitle(f"MVTec AD ({cat}) v2")
        fig.tight_layout(); fig.savefig(os.path.join(FIG,f"exp2_mvtec_{cat}_v2.png"),dpi=140)
        print("saved figure")
    except Exception as e: print("plot skipped:",e)

if __name__=="__main__":
    main()
