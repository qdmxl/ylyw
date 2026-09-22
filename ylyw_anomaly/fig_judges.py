# -*- coding: utf-8 -*-
"""fig: YLYW 三种判据层 vs 传感器基线 vs 易理抽取器 (逐类 AUROC)。"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
try:
    fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
except Exception:
    pass
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
CATS = ["bottle","cable","capsule","carpet","grid","hazelnut","leather","metal_nut",
        "pill","screw","tile","toothbrush","transistor","wood","zipper"]

def load(fn, key):
    d = json.load(open(os.path.join(BASE,"results",fn)))["per_cat"]
    return {r["cat"]: r[key] for r in d}

yl_patch = load("ylyw_anomaly_patch.json","feat")
cc = load("ylyw_anomaly_patch.json","chengcheng")
sens = load("ylyw_sensor_input.json","raw6")
yb = load("ylyw_yaobian.json","ylyw-cont")

YL = {"bottle":0.960,"cable":0.795,"capsule":0.880,"carpet":0.860,"grid":0.839,
      "hazelnut":0.962,"leather":0.978,"metal_nut":0.726,"pill":0.836,"screw":0.775,
      "tile":0.932,"toothbrush":0.928,"transistor":0.929,"wood":0.956,"zipper":0.911}

series = [
    ("易理抽取器 (主项目)", [YL[c] for c in CATS], "#2b7bba"),
    ("YLYW:6维特征", [yl_patch[c] for c in CATS], "#e08a3c"),
    ("六爻传感器→YLYW输入", [sens[c] for c in CATS], "#3ca06a"),
    ("连续爻变算子", [yb[c] for c in CATS], "#b5459a"),
    ("原乘承比应(定性)", [cc[c] for c in CATS], "#999999"),
]
x = np.arange(len(CATS)); n = len(series); w = 0.16
fig, ax = plt.subplots(figsize=(15,5.4))
for i,(lab,v,c) in enumerate(series):
    ax.bar(x + (i-(n-1)/2)*w, v, w, label=lab+" (%.3f)"%np.mean(v), color=c)
ax.set_xticks(x); ax.set_xticklabels(CATS, rotation=40, ha="right", fontsize=9)
ax.set_ylabel("图像级 AUROC"); ax.set_ylim(0,1.06)
ax.set_title("YLYW 不同判据层 vs 易理抽取器：逐类 AUROC")
ax.legend(fontsize=8.5, loc="lower center", ncol=3)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
out = os.path.join(BASE,"figures","fig_ylyw_judges.png")
fig.savefig(out, dpi=180); print("saved:", out)
for lab,v,c in series: print("%-22s %.4f"%(lab,np.mean(v)))
