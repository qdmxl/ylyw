#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成在线学习曲线图 (路径A 核心图)"""
import os, sys, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE=os.path.dirname(os.path.abspath(__file__))
RES=os.path.join(BASE,"results"); FIG=os.path.join(BASE,"figures")
os.makedirs(FIG,exist_ok=True)
data=json.load(open(os.path.join(RES,"exp3_online_robust.json")))

plt.rcParams["font.size"]=10
fig,axes=plt.subplots(1,2,figsize=(13,5))
colors={"bottle":"#d62728","metal_nut":"#1f77b4","tile":"#2ca02c","toothbrush":"#ff7f0e"}
names={"bottle":"bottle","metal_nut":"metal_nut","tile":"tile","toothbrush":"toothbrush"}

ax=axes[0]
for cat,rows in data.items():
    n=[r["n_train"] for r in rows]; m=[r["auroc_mean"] for r in rows]; s=[r["auroc_std"] for r in rows]
    ax.plot(n,m,"o-",color=colors[cat],label=names[cat],markersize=4)
    ax.fill_between(n,[a-b for a,b in zip(m,s)],[a+b for a,b in zip(m,s)],color=colors[cat],alpha=0.15)
ax.set_xscale("log"); ax.set_xlabel("Number of normal training samples (log)")
ax.set_ylabel("Image-level AUROC"); ax.set_ylim(0.3,1.02)
ax.axhline(0.5,ls="--",c="gray",lw=0.8,label="random")
ax.set_title("(a) Online learning curve: AUROC vs #normal samples")
ax.legend(); ax.grid(alpha=0.3)

ax=axes[1]
cats=list(data.keys())
warm=[data[c][0]["auroc_mean"] for c in cats]
sat=[data[c][-1]["auroc_mean"] for c in cats]
x=np.arange(len(cats)); bw=0.35
ax.bar(x-bw/2,warm,bw,label="cold start (1 sample)",color="#ff9999")
ax.bar(x+bw/2,sat,bw,label="saturated (all)",color="#66b3ff")
for i,(a,b) in enumerate(zip(warm,sat)):
    ax.text(i-bw/2,a+0.01,f"{a:.2f}",ha="center",fontsize=8)
    ax.text(i+bw/2,b+0.01,f"{b:.2f}",ha="center",fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=9)
ax.set_ylabel("AUROC"); ax.set_ylim(0,1.05); ax.axhline(0.5,ls="--",c="gray",lw=0.8)
ax.set_title("(b) Cold start vs saturated performance")
ax.legend(); ax.grid(alpha=0.3,axis="y")

plt.suptitle("YLYW Online Zero-Shot Anomaly Detection on MVTec AD",fontsize=12)
plt.tight_layout()
fig.savefig(os.path.join(FIG,"exp3_online_learning_curve.png"),dpi=150)
print("saved", os.path.join(FIG,"exp3_online_learning_curve.png"))
