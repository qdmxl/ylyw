# -*- coding: utf-8 -*-
"""fig: 检测器层对比 —— YLYW 爻变判据 vs 统计判据 (逐类 AUROC)。"""
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
d = json.load(open(os.path.join(BASE,"results","ylyw_detector.json")))
pc = {r["cat"]: r for r in d["per_cat"]}

series = [
    ("D1 Welford残差(统计)", [pc[c]["D1-welford"] for c in CATS], "#888888"),
    ("D2 马氏(统计)",       [pc[c]["D2-mahal"] for c in CATS], "#4c72b0"),
    ("D3 YLYW定性爻变",     [pc[c]["D3-ylyw-qual"] for c in CATS], "#c44e52"),
    ("D4 YLYW连续爻变",     [pc[c]["D4-ylyw-cont"] for c in CATS], "#55a868"),
    ("D5 融合(马氏+连续)",  [pc[c]["D5-fuse"] for c in CATS], "#8172b3"),
]
x = np.arange(len(CATS)); n = len(series); w = 0.16
fig, ax = plt.subplots(figsize=(15,5.4))
for i,(lab,v,c) in enumerate(series):
    ax.bar(x + (i-(n-1)/2)*w, v, w, label=lab+" (%.3f)"%np.mean(v), color=c)
ax.set_xticks(x); ax.set_xticklabels(CATS, rotation=40, ha="right", fontsize=9)
ax.set_ylabel("图像级 AUROC"); ax.set_ylim(0,1.06)
ax.set_title("检测器层对比：YLYW 爻变判据 vs 统计判据（同一传感器输出，逐类 AUROC）")
ax.legend(fontsize=8.5, loc="lower center", ncol=3)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
out = os.path.join(BASE,"figures","fig_detector_compare.png")
fig.savefig(out, dpi=180); print("saved:", out)
for lab,v,c in series: print("%-22s %.4f"%(lab,np.mean(v)))
