#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规范视频"知几"实验 V2 (路线甲): 用 V3 正交六爻
================================================================================
- 单一物理损伤场演化(裂纹/斑点/磨损), 不预设通道滞后;
- 六爻用 V3 定义(六个独立物理模态: 点奇异/频域/结构各向异性/空间聚集/色度/形态拓扑);
- 统计各爻首次越阈时刻, 检验初爻(点/几)是否显著先动;
- 测预警提前量(相对"肉眼可见"阈值)。
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters
from skimage.transform import resize

BASE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, BASE)
sys.path.insert(0, BASE)
from yao_v3 import (load_gray, load_rgb, load_split, build_baseline,
                    yao6_with_baseline, YAO)
RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")


def damage_sequence(g0, rgb0, T, rng, mode="crack", amp=0.6):
    """物理忠实损伤演化。关键: 损伤从【尖锐点核】萌生 -> 扩展。
    - crack: 初始亚像素尖锐点核 -> 沿方向拉成缝(尖锐→线)
    - spot : 初始尖锐小点 -> 扩展成斑
    - wear : 面状磨损(无尖锐点, 对照组)
    尖锐度通过“小 r + 高 A”实现(点奇异), 与“大 r 平滑”区分。
    """
    h, w = g0.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cy = rng.integers(h // 3, 2 * h // 3); cx = rng.integers(w // 3, 2 * w // 3)
    ang = rng.uniform(0, np.pi)
    frames = []
    for t in range(T + 1):
        a = t / T
        if mode == "crack":
            # 初: 尖锐点核(r极小, 幅度不弱); 随 t 拉长
            L = 0.5 + a * 30
            r = 0.4 + a * 1.8                     # 很尖
            vx, vy = np.cos(ang), np.sin(ang)
            proj = (xx - cx) * vx + (yy - cy) * vy
            perp = -(xx - cx) * vy + (yy - cy) * vx
            D = np.exp(-(perp ** 2) / (2 * r ** 2)) * np.exp(-(np.clip(np.abs(proj) - L / 2, 0, None) ** 2) / (2 * (L * .5 + 0.6) ** 2))
            A = amp * (0.35 + 0.65 * a ** 0.5)     # 早期已有幅度
        elif mode == "spot":
            r = 0.8 + a * 24                        # 从尖点长起
            A = amp * (0.35 + 0.65 * a ** 0.6)
            D = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
        else:  # wear
            r = 8 + a * 40
            A = amp * a
            D = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
        g = np.clip(g0 - A * D, 0, 1)
        if rgb0.ndim == 3:
            rgb = np.clip(rgb0 - A * 0.35 * D[..., None], 0, 1)
        else:
            rgb = g
        frames.append((g, rgb, D))
    return frames


def _scale_of(F0):
    """每爻的稳健尺度, 防退化(sd→~0 时用 mu 的百分比兼兼底)。"""
    mu = F0.mean(0)
    sd = F0.std(0)
    # 兼底: 若 sd 过小, 用 |mu| 的 5% 或整体幅度的 2% 作尺度
    gmax = np.abs(F0).max(0) - np.abs(F0).min(0) + 1e-12
    floor = np.maximum(0.05 * np.abs(mu) + 1e-6, 0.02 * gmax)
    return mu, np.maximum(sd, floor)


def run(cat, trials, T, modes):
    train = [p for p, d in load_split(cat, "train")]
    T0, S0, TC0, SC0, F0, base = build_baseline(train, 40)
    mu0, sd0 = _scale_of(F0)
    # 阈值: 每爻用【正常偏离的稳健上界】
    Z0 = np.abs((F0 - mu0) / sd0)
    med0 = np.median(Z0, axis=0)
    mad0 = np.median(np.abs(Z0 - med0), axis=0) * 1.4826 + 1e-9
    thr = np.maximum(med0 + 4.0 * mad0, 2.0)

    all_curves = []; first_t_all = []; vis_t_all = []
    for trial in range(trials):
        rng = np.random.default_rng(trial)
        mode = modes[trial % len(modes)]
        train_imgs = [p for p, d in load_split(cat, "train")]
        bg = load_gray(train_imgs[trial % len(train_imgs)])
        bc = load_rgb(train_imgs[trial % len(train_imgs)])
        frames = damage_sequence(bg, bc, T, rng, mode=mode)
        seq = np.zeros((T + 1, 6))
        for t, (g, rgb, D) in enumerate(frames):
            ft = yao6_with_baseline(g, rgb, T0, S0, TC0, SC0, base)
            z = np.abs((ft - mu0) / sd0)
            # 软截断: 防止个别爻无上限爆炸(Y2 频域尤甚)
            z = np.minimum(z, 50.0)
            seq[t] = z
        all_curves.append(seq)
        ft_cross = {}
        for i in range(6):
            idx = np.where(seq[:, i] > thr[i])[0]
            ft_cross[i] = int(idx[0]) if len(idx) else -1
        first_t_all.append(ft_cross)
        # 肉眼可见: 损伤幅度 A*D 超过人眼阈值(灰度差>0.05)
        vis = -1
        for t, (g, rgb, D) in enumerate(frames):
            A = 0.6 * (t / T)
            if np.max(A * D) > 0.05:
                vis = t; break
        vis_t_all.append(vis)
    return np.array(all_curves), first_t_all, thr, vis_t_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="bottle")
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--T", type=int, default=30)
    a = ap.parse_args()
    modes = ["crack", "spot", "wear"]
    curves, first_t, thr, vis_t = run(a.cat, a.trials, a.T, modes)
    mc = curves.mean(0)
    print(f"\n类别={a.cat} trials={a.trials} 情形={modes} T={a.T}  (V3 正交六爻)")
    show = [0, 5, 10, 15, 20, 25, 30]
    print("六爻平均失位(z)随时间:")
    print("          " + " ".join(f"t{t:>2d}" for t in show))
    for i in range(6):
        print(f"  {YAO[i]:8s} " + " ".join(f"{mc[t,i]:5.2f}" for t in show))
    print("\n各爻首次越阈(越小越早):")
    for i in range(6):
        vals = [ft[i] for ft in first_t if ft[i] >= 0]
        if vals:
            print(f"  {YAO[i]:8s}: 中位={np.median(vals):5.1f} 均值={np.mean(vals):5.1f} 越率={len(vals)/len(first_t):.2f}")
        else:
            print(f"  {YAO[i]:8s}: 从未越阈")
    init_first = sum(1 for ft in first_t if ft[0] >= 0 and all(ft[0] <= ft[j] for j in range(6) if ft[j] >= 0))
    print(f"\n初爻(点/几)最早越阈比例: {init_first}/{len(first_t)} = {init_first/len(first_t):.2f}")
    # 预警提前量: 检测时刻(任一爻最早越阈) vs 肉眼可见
    lead = []
    for ft, vt in zip(first_t, vis_t):
        crosses = [ft[i] for i in range(6) if ft[i] >= 0]
        if crosses and vt >= 0:
            lead.append(vt - min(crosses))
    if lead:
        print(f"预警提前量(肉眼可见 - 检测): 中位={np.median(lead):.1f} 均值={np.mean(lead):.1f} 步 (n={len(lead)})")
    json.dump(dict(cat=a.cat, trials=a.trials, mean_curve=mc.tolist(), first_t=first_t,
                   init_first_ratio=init_first / len(first_t), thr=thr.tolist(),
                   lead_median=float(np.median(lead)) if lead else None),
              open(os.path.join(RES, f"exp5v2_zhi_ji_{a.cat}.json"), "w"), ensure_ascii=False, indent=2)

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    tt = np.arange(a.T + 1)
    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd", "#8c564b"]
    for i in range(6):
        ax[0].plot(tt, mc[:, i], "-", color=colors[i], label=YAO[i])
    ax[0].set_xlabel("time step"); ax[0].set_ylabel("yao displacement (z)")
    ax[0].set_title(f"({a.cat}) V3 six-yao response over evolution")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    for i in range(6):
        vals = [ft[i] for ft in first_t if ft[i] >= 0]
        if vals:
            ax[1].hist(vals, bins=range(0, a.T + 2), alpha=0.5, color=colors[i], label=YAO[i])
    ax[1].set_xlabel("first-threshold-crossing time"); ax[1].set_ylabel("count")
    ax[1].set_title("Activation order (V3 orthogonal yao)"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    plt.suptitle(f"Zhi-Ji test with orthogonal six-yao (route A), {a.cat}")
    plt.tight_layout()
    out = os.path.join(FIG, f"exp5v2_zhi_ji_{a.cat}.png")
    fig.savefig(out, dpi=150); print("saved", out)


if __name__ == "__main__":
    main()
