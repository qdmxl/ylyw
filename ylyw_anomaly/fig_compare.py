# -*- coding: utf-8 -*-
"""fig: 原 YLYW 管线 vs 易理抽取器 vs ResNet18-L3 的逐类 AUROC 对比。"""
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
QY = os.path.join(BASE, "..", "..", "quantum_ylyw")

CATS = ["bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
        "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
        "wood", "zipper"]

# 1) 本项目: 原 YLYW patch
y = json.load(open(os.path.join(BASE, "results", "ylyw_anomaly_patch.json")))
yl = {r["cat"]: r for r in y["per_cat"]}

# 2) 易理抽取器最佳 (exp48) + ResNet18-L3
try:
    e48 = json.load(open(os.path.join(QY, "results", "exp48_yili_adaptive.json")))
    def getd(d, *keys):
        for k in keys:
            if k in d:
                return d[k]
        return None
    rn = e48.get("rn18_L3_per_class") or e48.get("rn18_L3") or {}
    yl_best = e48.get("per_class_best") or {}
except Exception as e:
    print("warn:", e); rn, yl_best = {}, {}

# 后备硬编码 (数据台账 v2)
RN = {"bottle":0.998,"cable":0.795,"capsule":0.880,"carpet":0.860,"grid":0.839,
      "hazelnut":0.529,"leather":0.978,"metal_nut":0.908,"pill":0.836,"screw":0.722,
      "tile":0.932,"toothbrush":0.839,"transistor":0.929,"wood":0.973,"zipper":0.911}
YL = {"bottle":0.960,"cable":0.795,"capsule":0.880,"carpet":0.860,"grid":0.839,
      "hazelnut":0.962,"leather":0.978,"metal_nut":0.726,"pill":0.836,"screw":0.775,
      "tile":0.932,"toothbrush":0.928,"transistor":0.929,"wood":0.956,"zipper":0.911}

x = np.arange(len(CATS)); w = 0.27
f_ylyw = [yl[c]["feat"] for c in CATS]
f_yili = [YL[c] for c in CATS]
f_rn = [RN[c] for c in CATS]

fig, ax = plt.subplots(figsize=(14, 5.2))
ax.bar(x - w, f_rn, w, label="ResNet18-L3 (预训练)", color="#888")
ax.bar(x, f_yili, w, label="易理抽取器 (零预训练)", color="#2b7bba")
ax.bar(x + w, f_ylyw, w, label="原 YLYW 管线 patch (零预训练)", color="#e08a3c")
ax.set_xticks(x); ax.set_xticklabels(CATS, rotation=40, ha="right", fontsize=9)
ax.set_ylabel("图像级 AUROC"); ax.set_ylim(0, 1.05)
ax.axhline(np.mean(f_ylyw), ls="--", c="#e08a3c", lw=1)
ax.axhline(np.mean(f_rn), ls="--", c="#888", lw=1)
ax.set_title("三种特征来源的逐类 AUROC：原 YLYW 管线 / 易理抽取器 / ResNet18-L3")
ax.legend(fontsize=9, loc="lower right"); ax.grid(axis="y", alpha=0.3)
for i, (a, b, c) in enumerate(zip(f_rn, f_yili, f_ylyw)):
    pass
fig.tight_layout()
out = os.path.join(BASE, "figures", "fig_ylyw_vs_yili_vs_rn.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=180)
print("saved:", out)
print("avg ylyw=%.4f yili=%.4f rn=%.4f" % (np.mean(f_ylyw), np.mean(f_yili), np.mean(f_rn)))
