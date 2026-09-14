#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fig2_yao_operators.py  --  Fig.2 六爻算子示意图
================================================================================
用一张合成"缺陷图"演示 6 个算子各自的响应。
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "figures_paper")
os.makedirs(OUT, exist_ok=True)

for fp in ["/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if os.path.exists(fp):
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

# 合成残差场: 平滑背景 + 局部峰(划痕) + 高频纹理 + 方向边缘
np.random.seed(0)
H = W = 64
yy, xx = np.mgrid[0:H, 0:W]
R = 0.1 + 0.05*np.random.randn(H, W)
# 局部细划痕
R[30:34, 10:45] += 0.9*np.exp(-((yy[30:34, 10:45]-32)**2)/2)
# 局部斑点
R[45:52, 45:52] += 0.8
# 方向边缘
R[:, 55:] += 0.4
R = np.abs(R)

# 六爻算子
Rc = R
bk = ndimage.uniform_filter(Rc, 7)
s1 = np.maximum(Rc - bk, 0)
s2 = np.abs(ndimage.laplace(s1))
gy, gx = np.gradient(Rc)
s3 = np.sqrt(gy**2 + gx**2)
s4 = np.abs(ndimage.laplace(Rc))          # 通道分散(此处单通道用laplace近似展示)
s5 = s1**2
Bk = ndimage.uniform_filter(Rc**2, 5) - ndimage.uniform_filter(Rc, 5)**2
s6 = np.sqrt(np.maximum(Bk, 0))

ops = [("初 · 残差峰值\n(top-hat)", s1), ("二 · 高频\n|∇²|", s2),
       ("三 · 梯度\n|∇R|", s3), ("四 · 非高斯残差\n通道分散", s4),
       ("五 · 局部能量\ns₁²", s5), ("六 · 连通域密度\n窗口方差", s6)]

fig, axes = plt.subplots(2, 4, figsize=(13, 6.4))
ax0 = axes[0, 0]
ax0.imshow(R, cmap="inferno"); ax0.set_title("合成残差场 R", fontsize=11, fontweight="bold")
ax0.axis("off")

for k, (name, im) in enumerate(ops):
    r, c = divmod(k+1, 4)
    ax = axes[r, c]
    ax.imshow(im, cmap="inferno")
    ax.set_title(name, fontsize=9)
    ax.axis("off")

# 隐藏多余子图
axes[0, 1].imshow(ops[0][1], cmap="inferno"); axes[0, 1].set_title(ops[0][0], fontsize=9); axes[0, 1].axis("off")
axes[0, 2].imshow(ops[1][1], cmap="inferno"); axes[0, 2].set_title(ops[1][0], fontsize=9); axes[0, 2].axis("off")
axes[0, 3].imshow(ops[2][1], cmap="inferno"); axes[0, 3].set_title(ops[2][0], fontsize=9); axes[0, 3].axis("off")
axes[1, 0].imshow(ops[3][1], cmap="inferno"); axes[1, 0].set_title(ops[3][0], fontsize=9); axes[1, 0].axis("off")
axes[1, 1].imshow(ops[4][1], cmap="inferno"); axes[1, 1].set_title(ops[4][0], fontsize=9); axes[1, 1].axis("off")
axes[1, 2].imshow(ops[5][1], cmap="inferno"); axes[1, 2].set_title(ops[5][0], fontsize=9); axes[1, 2].axis("off")
axes[1, 3].axis("off")

fig.suptitle("六爻算子示意：同一残差场的六种响应", fontsize=13, fontweight="bold")
plt.tight_layout()
p = os.path.join(OUT, "fig2_yao_operators.png")
plt.savefig(p, dpi=170, bbox_inches="tight")
print("saved:", p)
