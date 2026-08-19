#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plot_growth.py — 嵌套自增长语义系统结果可视化"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "results_growth.json")))
st, gr = d["static"], d["growth"]

import matplotlib.font_manager as fm
_cjk = fm.FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.sans-serif"] = [_cjk.get_name()]
plt.rcParams["axes.unicode_minus"] = False

def _f(size=10, bold=True):
    p = fm.FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    p.set_size(size); p.set_weight("bold" if bold else "normal")
    return p

fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

# 1) 元胞增长曲线（复杂性的演进）
gc = gr["growth_curve"]
xs = [c["step"] for c in gc]; ys = [c["cells"] for c in gc]
axes[0].plot(xs, ys, "-o", color="#d62728", lw=2, label=f"自增长H (终值{gr['complexity']['total_cells']})")
axes[0].axhline(st["complexity"]["total_cells"], color="#7f7f7f", ls="--", lw=2,
                label=f"静态H (固定{st['complexity']['total_cells']})")
axes[0].set_title("元胞数量随语料增长\n(喂入越多 → 系统越复杂)", fontproperties=_f(11))
axes[0].set_xlabel("训练语料句子 ($step$)", fontproperties=_f(10)); axes[0].set_ylabel("元胞总数", fontproperties=_f(10))
axes[0].legend(prop=_f(8, bold=False)); axes[0].grid(alpha=0.3)

# 2) 测试准确率曲线（泛化能力）
tc = gr["test_curve"]
tx = [c["step"] for c in tc]; ty = [c["acc"] * 100 for c in tc]
axes[1].plot(tx, ty, "-", color="#2ca02c", lw=2, label=f"自增长H {gr['test_acc']*100:.1f}%")
axes[1].axhline(st["test_acc"] * 100, color="#7f7f7f", ls="--", lw=2,
                label=f"静态H {st['test_acc']*100:.1f}%")
axes[1].set_title("未见句(泛化)范畴归类准确率\n(81.8%为训练未见的新复合词)", fontproperties=_f(11))
axes[1].set_xlabel("测试句子序 ($step$)", fontproperties=_f(10)); axes[1].set_ylabel("准确率 (%)", fontproperties=_f(10))
axes[1].set_ylim(0, 105)
axes[1].legend(prop=_f(8, bold=False)); axes[1].grid(alpha=0.3)

# 3) 词级元胞 H(θ) 自学习演化（θ 方差）
thetas = np.array([[c["theta"]["J_adj"], c["theta"]["J_ying"], c["theta"]["h_dang"],
                    c["theta"]["h_zhong"], c["theta"]["J_comp"]] for c in gr["cell_samples"]])
if len(thetas):
    labels = ["J_adj", "J_ying", "h_dang", "h_zhong", "J_comp"]
    means = thetas.mean(axis=0)
    cols = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd"]
    axes[2].bar(labels, means, color=cols, alpha=0.85)
    for i, m in enumerate(means):
        axes[2].text(i, m + 0.01, f"{m:.2f}", ha="center", fontsize=9)
    axes[2].axhline(0.5, color="#7f7f7f", ls="--", lw=1)
    axes[2].set_title(f"词级元胞 H(θ) 自学习均值\n(知几校准, θ方差={gr['complexity']['total_theta_var']:.2f})")
    axes[2].set_ylabel("权重均值", fontproperties=_f(10))
    axes[2].set_ylim(0, max(means) + 0.2)

plt.tight_layout()
out = os.path.join(HERE, "growth_result.png")
plt.savefig(out, dpi=130, bbox_inches="tight")
print("saved", out)

# 控制台摘要
print("\n=== 嵌套自增长语义系统 结果摘要 ===")
print(f"语义范畴归类(8卦范畴) | 训练{gr['n_train']}句 / 测试{gr['n_test']}句")
print(f"  静态H : 测试准确率 {st['test_acc']*100:.1f}%  (元胞{st['complexity']['total_cells']}, 词级元胞{len(st['word_cells'])}")
print(f"  自增长H: 测试准确率 {gr['test_acc']*100:.1f}%  (元胞{gr['complexity']['total_cells']}, 词级元胞{len(gr['word_cells'])}")
print(f"  提升: +{(gr['test_acc']-st['test_acc'])*100:.1f} 个百分点")
print(f"  嵌套深度: max_depth={gr['complexity']['max_depth']}, mean={gr['complexity']['mean_depth']:.2f}")
print(f"  H(θ) 学习动力学: total_theta_var={gr['complexity']['total_theta_var']:.2f}")
