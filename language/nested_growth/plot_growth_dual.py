#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plot_growth_dual.py — 方案甲三维成长可视化"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 中文字体（直接指定字体文件）
_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_fon = fm.FontProperties(fname=_CJK)
plt.rcParams["font.sans-serif"] = [_fon.get_name()]
plt.rcParams["axes.unicode_minus"] = False

def _fs(size=11):
    _p = fm.FontProperties(fname=_CJK)
    _p.set_size(size)
    return _p

d = json.load(open("growth_metrics.json", encoding="utf-8"))
res, conv = d["growth"], d["conv"]

fig, axes = plt.subplots(1, 3, figsize=(16, 5))

sents = [r["n_sent"] for r in res]
chars = [r["G1_chars"] for r in res]
words = [r["G2_word_cells"] for r in res]
total = [r["G2_total_cells"] for r in res]

# G1 覆盖面
ax = axes[0]
ax.plot(sents, chars, "o-", color="#2c7fb8", lw=2)
ax.set_title("G1 阅读量 → 覆盖面 (认识字符)", fontsize=12, fontproperties=_fs(12))
ax.set_xlabel("阅读句数", fontproperties=_fs(11)); ax.set_ylabel("认识不同字符数", fontproperties=_fs(11))
ax.grid(alpha=0.3)

# G2 复杂度
ax = axes[1]
ax.plot(sents, words, "s-", color="#d95f0e", lw=2, label="词元胞(嵌套)")
ax.plot(sents, total, "^--", color="#756bb1", lw=2, label="总元胞")
ax.set_title("G2 阅读量 → 系统复杂度 (元胞繁殖)", fontsize=12, fontproperties=_fs(12))
ax.set_xlabel("阅读句数", fontproperties=_fs(11)); ax.set_ylabel("元胞数", fontproperties=_fs(11))
ax.legend(prop=_fs(10)); ax.grid(alpha=0.3)

# G3 语义收敛
ax = axes[2]
fs = [r["frac"]*100 for r in conv]
st = [r["stable"]*100 if r["stable"] is not None else None for r in conv]
xs = [f for f, s in zip(fs, st) if s is not None]
ys = [s for s in st if s is not None]
ax.plot(xs, ys, "D-", color="#31a354", lw=2)
ax.set_title("G3 阅读增量 → 语义收敛 (理解巩固)", fontsize=12, fontproperties=_fs(12))
ax.set_xlabel("累计阅读比例 (%)", fontproperties=_fs(11)); ax.set_ylabel("语义划分稳定率 (%)", fontproperties=_fs(11))
ax.set_ylim(0, 100); ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("growth_dual.png", dpi=130, bbox_inches="tight")
print("已生成 growth_dual.png")
