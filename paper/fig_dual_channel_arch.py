#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fig_dual_channel_arch.py — 论文级示意图：四层架构 + 双通道融合语义系统"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_fon = fm.FontProperties(fname=_CJK)
plt.rcParams["font.sans-serif"] = [_fon.get_name()]
plt.rcParams["axes.unicode_minus"] = False

def fs(size=10, bold=False):
    p = fm.FontProperties(fname=_CJK, weight="bold" if bold else "normal")
    p.set_size(size)
    return p

fig, ax = plt.subplots(figsize=(13, 7.6))
ax.set_xlim(0, 13); ax.set_ylim(0, 7.6)
ax.axis("off")

def box(x, y, w, h, fc, ec, text, tfs=11, tc="black", bold=True, radius=0.12):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={radius}",
                       fc=fc, ec=ec, lw=1.6)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontproperties=fs(tfs, bold), color=tc)

def arrow(x1, y1, x2, y2, color="#333", lw=1.8, style="-|>", ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=18,
                        color=color, lw=lw, linestyle=ls)
    ax.add_patch(a)

# ===== 左栏：YLYW 四层架构 =====
ax.text(1.45, 7.25, "YLYW 四层嵌套架构", ha="center", fontproperties=fs(13, True), color="#1a5276")
layers = [
    ("L4 篇章层", "变卦序列 · 起承转合", "#d6eaf8"),
    ("L3 词句层", "词义模糊隶属度网络", "#d4efdf"),
    ("L2 字义层", "会意字 · 乘承比应", "#fdebd0"),
    ("L1 字形层", "部首八卦 · 六爻", "#f9e79f"),
]
for i, (nm, desc, c) in enumerate(layers):
    y = 6.3 - i*1.28
    box(0.25, y, 2.4, 0.95, c, "#5dade2", f"{nm}\n{desc}", tfs=11)
for i in range(3):
    a = FancyArrowPatch((1.45, 6.3 - i*1.28 - 0.0), (1.45, 6.3 - (i+1)*1.28 + 0.95),
                        arrowstyle="-|>", mutation_scale=16, color="#2e86c1", lw=1.6)
    ax.add_patch(a)

# 左-中 连接
arrow(2.7, 4.75, 3.6, 4.6, color="#2e86c1", lw=2)

# ===== 中栏：双通道融合评分（核心，放大） =====
ax.text(6.0, 7.25, "语义元胞 · 双通道融合评分", ha="center", fontproperties=fs(13, True), color="#922b21")

# 先天字形通道
box(3.55, 5.3, 2.3, 1.5, "#f9e79f", "#b7950b", "字形通道（先天）\n部首八卦六爻\n粗范畴先验(8维)", tfs=10.5)
# 后天语料通道
box(6.35, 5.3, 2.3, 1.5, "#d5f5e3", "#229954", "语料通道（后天）\nPMI 共现指纹\nt ∈ R^N\n语义证据（主力）", tfs=10.5)
# 知几校准
box(8.95, 5.3, 2.0, 1.5, "#e8daef", "#7d3c98", "知几校准\nb ∈ R^C\n经验修正", tfs=10.5)

# 统一评分
box(4.6, 3.5, 3.4, 1.15, "#fadbd8", "#c0392b",
    "统一评分\nscore(c) = λ·G(y) + (1-λ)·cos(t,q_c) + b_c", tfs=10.5)
arrow(4.7, 5.3, 5.3, 4.68, color="#b7950b", lw=1.8)
arrow(7.5, 5.3, 7.1, 4.68, color="#229954", lw=1.8)
arrow(9.95, 5.3, 8.2, 4.68, color="#7d3c98", lw=1.8)

# 语义类输出
box(4.2, 1.9, 4.2, 1.1, "#aed6f1", "#21618c",
    f"判别:  c_hat = argmax_c score(c)\n归属语义类（自组织知识库）", tfs=10.5)
arrow(6.3, 3.5, 6.3, 3.05, color="#c0392b", lw=2)

# 语义类示例
ax.text(6.3, 1.55, "语义类（自动涌现）", ha="center", fontproperties=fs(10.5, True), color="#21618c")
cls = ["水·火·木（字形可判）", "计算技术", "伦理治理", "生命身心", "学习成长"]
for i, c in enumerate(cls):
    x = 0.6 + i*2.55
    box(x, 0.25, 2.3, 1.0, "#d6eaf8", "#5dade2", c, tfs=9.5, bold=(i==0))

# ===== 右栏：成长环 =====
ax.text(11.3, 7.25, "成长（读得越多越懂）", ha="center", fontproperties=fs(13, True), color="#1e8449")
growth = [
    ("G1 覆盖面", "认识字符 ↑", "#f9e79f"),
    ("G2 复杂度", "嵌套词元胞 ↑", "#d4efdf"),
    ("G3 语义收敛", "划分稳定率 ↑", "#aed6f1"),
    ("G4 判别准确", "97.7%", "#f5b7b1"),
]
for i, (nm, v, c) in enumerate(growth):
    y = 6.15 - i*1.3
    box(10.4, y, 1.85, 0.95, c, "#2e86c1", f"{nm}\n{v}", tfs=10)
for i in range(3):
    a = FancyArrowPatch((11.3, 6.15 - i*1.3 - 0.0), (11.3, 6.15 - (i+1)*1.3 + 0.0),
                        arrowstyle="-|>", mutation_scale=14, color="#1e8449", lw=1.5)
    ax.add_patch(a)
# 右栏-中 连接（成长回馈到元胞）
arrow(10.4, 3.6, 8.4, 3.3, color="#1e8449", lw=2, ls="--")

ax.text(6.5, 0.05, "语义理解 = 先天认知框架（易理字形） + 后天语境阅读（分布语义）——在嵌套元胞中持续自组织成长",
        ha="center", fontproperties=fs(11, True), color="#333")

plt.tight_layout()
plt.savefig("fig_dual_channel_arch.png", dpi=140, bbox_inches="tight")
print("已生成 fig_dual_channel_arch.png")
