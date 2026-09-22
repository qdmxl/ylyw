#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""路径A+正交六爻: 学习曲线图 (主结果图)"""
import os, json
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE=os.path.dirname(os.path.abspath(__file__))
RES=os.path.join(BASE,"results"); FIG=os.path.join(BASE,"figures")
data=json.load(open(os.path.join(RES,"expA_ortho_online.json")))
colors={"bottle":"#d62728","metal_nut":"#1f77b4","tile":"#2ca02c","toothbrush":"#ff7f0e"}

fig,axes=plt.subplots(1,2,figsize=(14,5.2))
ax=axes[0]
for cat,rows in data.items():
    n=[r["n_train"] for r in rows]
    m=[r["s2_ortho"] for r in rows]; s=[r["s2_std"] for r in rows]
    ax.plot(n,m,"o-",color=colors[cat],label=f"{cat} (ortho6)",markersize=4)
    ax.fill_between(n,[a-b for a,b in zip(m,s)],[a+b for a,b in zip(m,s)],color=colors[cat],alpha=0.15)
    mp=[r["s1_peak"] for r in rows]
    ax.plot(n,mp,":",color=colors[cat],alpha=0.6,label=f"{cat} (peak)",markersize=3)
ax.set_xscale("log"); ax.set_xlabel("Number of normal training samples (log)")
ax.set_ylabel("Image-level AUROC"); ax.set_ylim(0.25,1.02)
ax.axhline(0.5,ls="--",c="gray",lw=0.8)
ax.set_title("(a) Online learning: ortho-6yao vs residual peak")
ax.legend(fontsize=7,ncol=2); ax.grid(alpha=0.3)

ax=axes[1]
cats=list(data.keys()); x=np.arange(len(cats)); bw=0.35
peak=[data[c][-1]["s1_peak"] for c in cats]
ortho=[data[c][-1]["s2_ortho"] for c in cats]
ax.bar(x-bw/2,peak,bw,label="residual peak (S1)",color="#ff9999")
ax.bar(x+bw/2,ortho,bw,label="ortho-6yao (S2)",color="#66b3ff")
for i,(a,b) in enumerate(zip(peak,ortho)):
    ax.text(i-bw/2,a+0.01,f"{a:.2f}",ha="center",fontsize=8)
    ax.text(i+bw/2,b+0.01,f"{b:.2f}",ha="center",fontsize=8)
    ax.text(i,max(a,b)+0.05,f"{b-a:+.2f}",ha="center",fontsize=8,color="darkgreen")
ax.set_xticks(x); ax.set_xticklabels(cats,fontsize=9)
ax.set_ylabel("AUROC (saturated)"); ax.set_ylim(0,1.08); ax.axhline(0.5,ls="--",c="gray",lw=0.8)
ax.set_title("(b) Saturated AUROC: ortho-6yao vs peak")
ax.legend(); ax.grid(alpha=0.3,axis="y")

plt.suptitle("YLYW: Online Zero-Shot Anomaly Detection with Orthogonal Six-Yao Coding",fontsize=12)
plt.tight_layout(); fig.savefig(os.path.join(FIG,"expA_ortho_learning_curve.png"),dpi=150)
print("saved",os.path.join(FIG,"expA_ortho_learning_curve.png"))

# 汇总表
print("\n=== 汇总 (全量AUROC) ===")
for c in cats:
    print(f"{c:12s} peak={data[c][-1]['s1_peak']:.4f} ortho6={data[c][-1]['s2_ortho']:.4f} "
          f"gain={data[c][-1]['s2_ortho']-data[c][-1]['s1_peak']:+.4f}")
print(f"{'平均':12s} peak={np.mean(peak):.4f} ortho6={np.mean(ortho):.4f} gain={np.mean(ortho)-np.mean(peak):+.4f}")
