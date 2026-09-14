#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知几实验 V3 (爻变框架): 初爻是否先动
================================================================================
理念: 要的是"爻变"——爻随演化时间的【变化】, 以及变化的传导。
本次实验: 用 good->defect 的物理插值序列(损伤渐变), 观察六爻各自"动"的时刻,
  统计初爻(几/萌芽)是否显著先于其他爻。

关键: 不再用"爻的正交特征越阈", 而用【爻变 dy_i = y_i(t)-y_i(t-1)】的
  首次显著变化时刻。这才对应"爻动"。

输出:
  1) 六爻"动量"随演化时间曲线(平均);
  2) 各爻首次"动"时刻分布;
  3) 初爻最早动的比例 + Spearman;
  4) 预警提前量(相对肉眼可见)。
"""
import os, sys, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yao_variation import (load_gray, load_rgb, load_split, build_templates,
                           yao_from_img, YAO)
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures"); RES = os.path.join(BASE, "results")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="bottle")
    ap.add_argument("--trials", type=int, default=80)
    ap.add_argument("--T", type=int, default=20)
    a = ap.parse_args()

    train = [p for p, d in load_split(a.cat, "train")]
    T0, S0, TC0, SC0, F0 = build_templates(train, 40)
    mu, sd = F0.mean(0), F0.std(0) + 1e-9
    def ny(f): return (f - mu) / sd

    good_paths = train[:min(60, len(train))]
    g_imgs = [(load_gray(p), load_rgb(p)) for p in good_paths]

    first_t = {i: [] for i in range(6)}
    curves = []
    vis_lead = []
    rng = np.random.default_rng(0)
    # 先估"正常变化"的稳健上界 —— 用【同一 good 图的微小噪声扰动】(同源基线)
    norm_dy = []
    for _ in range(60):
        gi = rng.integers(len(g_imgs)); ga, ca = g_imgs[gi]
        noise = rng.normal(0, 0.01, ga.shape)
        ga2 = np.clip(ga + noise, 0, 1)
        ca2 = np.clip(ca + noise[..., None], 0, 1)
        f = ny(yao_from_img(ga2, ca2, T0, S0, TC0, SC0)) - ny(yao_from_img(ga, ca, T0, S0, TC0, SC0))
        norm_dy.append(np.abs(f))
    norm_dy = np.array(norm_dy)
    dy_med = np.median(norm_dy, 0)
    dy_mad = np.median(np.abs(norm_dy - dy_med), 0) * 1.4826 + 1e-9
    dy_thr = np.maximum(dy_med + 4 * dy_mad, 0.2)      # 每爻的"显著动"阈值
    for tr in range(a.trials):
        # 随机 good 起点, 随机 defect 终点
        gi = rng.integers(len(g_imgs)); dg, dr = g_imgs[gi]
        # 制造一个"损伤": 随机位置【尖锐点核】渐变(物理: 裂纹/斑点萌生)
        h, w = dg.shape
        cy = rng.integers(h // 3, 2 * h // 3); cx = rng.integers(w // 3, 2 * w // 3)
        yy, xx = np.mgrid[0:h, 0:w]
        r = rng.uniform(1.0, 4.0)                    # 很小 -> 尖锐点核
        D = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
        amp = rng.uniform(0.3, 0.6)
        seq_y = []
        for t in range(a.T + 1):
            aa = t / a.T
            sg = np.clip(dg - amp * aa * D, 0, 1)
            srgb = np.clip(dr - amp * aa * D[..., None] * 0.35, 0, 1)
            seq_y.append(ny(yao_from_img(sg, srgb, T0, S0, TC0, SC0)))
        seq_y = np.array(seq_y)
        curves.append(seq_y)
        # 爻变
        dy = np.abs(np.diff(seq_y, axis=0))          # (T,6)
        # 每爻首次"显著动": dy 超过正常变化的稳健上界
        for i in range(6):
            v = dy[:, i]
            idx = np.where(v > dy_thr[i])[0]
            first_t[i].append(int(idx[0] + 1) if len(idx) else -1)   # +1: 相对起点
        # 肉眼可见: amp*aa > 0.05
        vt = -1
        for t in range(a.T + 1):
            if amp * (t / a.T) > 0.05:
                vt = t; break
        crosses = [min([t for t in [first_t[i][-1]] if t >= 0], default=-1) for i in range(6)]
        crosses = [c for c in crosses if c >= 0]
        if crosses and vt >= 0:
            vis_lead.append(vt - min(crosses))

    mc = np.mean(curves, 0)
    print(f"\n[{a.cat}] 爻变知几实验 trials={a.trials} T={a.T}")
    print("六爻标准化值随时间(平均):")
    for t in [0, 4, 8, 12, 16, 20]:
        if t <= a.T:
            print(f"  t{t:2d}: " + " ".join(f"{mc[t,i]:6.2f}" for i in range(6)))
    print("\n各爻首次'动'时刻(越小越早):")
    for i in range(6):
        vals = [t for t in first_t[i] if t >= 0]
        if vals:
            print(f"  {YAO[i]:8s}: 中位={np.median(vals):5.1f} 均值={np.mean(vals):5.1f} 动率={len(vals)/a.trials:.2f}")
        else:
            print(f"  {YAO[i]:8s}: 从未显著动")
    init_first = 0
    for k in range(a.trials):
        f0 = first_t[0][k]
        if f0 >= 0 and all((first_t[i][k] >= f0) or (first_t[i][k] < 0) for i in range(6)):
            init_first += 1
    print(f"\n初爻(几)最先动的比例: {init_first}/{a.trials} = {init_first/a.trials:.2f}")
    if vis_lead:
        print(f"预警提前量(肉眼 - 检测): 中位={np.median(vis_lead):.1f} 均值={np.mean(vis_lead):.1f} 步")

    # 出图
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd", "#8c564b"]
    for i in range(6):
        ax[0].plot(range(a.T + 1), mc[:, i], "-", color=colors[i], label=YAO[i])
    ax[0].set_xlabel("evolution step"); ax[0].set_ylabel("yao value (z)")
    ax[0].set_title(f"({a.cat}) six-yao over damage evolution"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    for i in range(6):
        vals = [t for t in first_t[i] if t >= 0]
        if vals:
            ax[1].hist(vals, bins=range(0, a.T + 2), alpha=0.5, color=colors[i], label=YAO[i])
    ax[1].set_xlabel("first significant movement"); ax[1].set_ylabel("count")
    ax[1].set_title("activation order"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    plt.suptitle(f"Zhi-Ji (yao-variation), {a.cat}")
    plt.tight_layout()
    out = os.path.join(FIG, f"exp7_zhiji_{a.cat}.png")
    fig.savefig(out, dpi=150); print("saved", out)
    json.dump(dict(cat=a.cat, first_t=first_t, init_first_ratio=init_first / a.trials,
                   lead_median=float(np.median(vis_lead)) if vis_lead else None),
              open(os.path.join(RES, f"exp7_zhiji_{a.cat}.json"), "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
