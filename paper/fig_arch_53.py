#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fig_arch_53.py — 论文图：§5.3 文言文单句语义解析原型系统架构"""
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

fig, ax = plt.subplots(figsize=(12, 7.8))
ax.set_xlim(0, 12); ax.set_ylim(0, 7.8)
ax.axis("off")

def box(x, y, w, h, fc, ec, text, tfs=10.5, bold=True, tc="black", shadow=False, r=0.1):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={r}",
                       fc=fc, ec=ec, lw=1.6)
    ax.add_patch(p)
    ax.text(x+w/2, y+h/2, text, ha="center", va="center",
            fontproperties=fs(tfs, bold), color=tc)

def arrow(x1, y1, x2, y2, color="#333", lw=1.8, ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=17,
                        color=color, lw=lw, linestyle=ls)
    ax.add_patch(a)

# ===== 输入 =====
box(4.2, 6.85, 3.6, 0.85, "#fef9e7", "#d4ac0d", "输入：文言文单句\n学而时习之，不亦说乎", tfs=10)
arrow(6.0, 6.85, 6.0, 6.35, color="#b7950b", lw=2)

# ===== L1 字形层 =====
box(0.4, 5.05, 5.9, 1.25, "#f9e79f", "#b7950b",
    "L1 字形层（单元：爻）\n偏旁部首识别 → 模糊语义隶属度\n对应部首八卦：学(离) 而(兑) 时(明)…", tfs=10.5)
arrow(3.35, 5.05, 3.35, 4.6, color="#288726", lw=2)

# ===== L2 字义层 =====
box(0.4, 3.35, 5.9, 1.25, "#d5f5e3", "#288726",
    "L2 字义层（单元：卦）\n据上下文确定义项（会意字乘承比应）\n知识库：159 会意字 · 模糊隶属度", tfs=10.5)
arrow(3.35, 3.35, 3.35, 2.9, color="#1a5276", lw=2)

# ===== L3 词句层 =====
box(0.4, 1.65, 5.9, 1.25, "#d6eaf8", "#1a5276",
    "L3 词句层（单元：别卦/重卦）\n虚词驱动分词 · 词间乘承比应 · 三通道\n义音形合成，判定句法结构", tfs=10.5)
arrow(3.35, 1.65, 3.35, 1.25, color="#6c3483", lw=2)

# ===== L4 篇章层 =====
box(0.4, 0.0, 5.9, 1.2, "#e8daef", "#6c3483",
    "L4 篇章层（单元：复卦/变卦）\n多句：起承转合 · 修辞分析（扩展）", tfs=10.5)

# ===== 右侧：输出 =====
box(7.2, 3.35, 4.3, 1.5, "#fadbd8", "#c0392b",
    "输出\n完整语义解析\n可追溯推理链（每步回溯到\n部首隶属度阈值 / 词典条目）", tfs=10.5)
# 从 L2/L3 汇聚到输出
arrow(5.15, 4.0, 7.2, 4.1, color="#c0392b", lw=2)
arrow(5.15, 2.6, 7.2, 3.9, color="#c0392b", lw=2)

# ===== 底部：双通道成长 + 知几 =====
box(7.2, 1.4, 4.3, 1.2, "#d7bde2", "#7d3c98",
    "知几学习（跨句校准）\n先验增强 · 经验跨句复用", tfs=10)
box(7.2, 0.0, 4.3, 1.1, "#aed6f1", "#21618c",
    "自适应成长底座（语料分布）\n随阅读自组织 · 覆盖↑理解↑", tfs=10)
arrow(9.35, 1.4, 9.35, 3.35, color="#7d3c98", lw=1.6, ls="--")
arrow(9.35, 1.1, 9.35, 1.4, color="#21618c", lw=1.6, ls="--")

ax.text(6.0, 7.55, "原型系统数据流（字数级 → 篇章级，Eisenwaren 单元-卦象映射）",
        ha="center", fontproperties=fs(12, True), color="#333")

plt.tight_layout()
plt.savefig("fig_arch_53.png", dpi=140, bbox_inches="tight")
print("已生成 fig_arch_53.png")
