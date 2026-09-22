#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规范视频"知几"实验 (exp5)
================================================================================
目标: 检验易理"知几"(缺陷演化中【初爻(几/萌芽)是否最先动】), 并测预警提前量。

与旧 exp4b 的关键区别(消除"把答案写进假设"):
  * 旧做法: 直接给不同物理通道(亮度/梯度/颜色)人为设定滞后 delay, 再观察谁先动
    -> 结论是设计出来的, 不算证据。
  * 规范做法: 只定义一个【单一物理损伤场】的时空演化(损伤核按物理规律萌生-扩展),
    六爻从【同一个演化场】自然提取响应, 谁先动由物理与特征定义共同决定, 不由我们指定。
  * 多情形/多随机核位置/多强度曲线 重复, 统计"首次越阈时刻"的分布, 检验
    初爻是否【统计显著】早于其他爻。

物理损伤模型(单一过程):
  以"裂纹/腐蚀斑"为例。损伤强度场 D(x,y,t) = A(t) * G(x,y; c(t), r(t))
    - A(t): 损伤幅度, 随时间单调增(S 型或线性)
    - r(t): 损伤核半径, 随时间增(从点到面)
    - c(t): 核中心 (可轻微漂移)
  D 直接作用于像素: I_obs = I0 * (1 - a*D) + noise*D  (明暗 + 纹理扰动同源)
  -> 早期 D 是小而尖的点(只激活"点/几"), 扩展后出现边界(激活梯度),
     后期大面积改变(激活分布/颜色/形态)。
  六爻用与主实验一致的 ortho6 定义从【残差】提取。

关键点: 我们【不指定】哪一爻先激活。如果易理成立, 初爻应自然最早。

用法:
  ../.venv-quantum/bin/python exp5_zhi_ji.py --cat bottle --trials 40
"""
import os, sys, json, argparse
import numpy as np
from skimage import io, color, filters, measure, morphology
from skimage.transform import resize
from scipy import ndimage

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)
SIZE = (160, 160)
YAO = ["Y1(point)", "Y2(freq)", "Y3(grad)", "Y4(skew)", "Y5(color)", "Y6(morph)"]


def load_gray(path):
    im = io.imread(path)
    g = color.rgb2gray(im) if im.ndim == 3 else im.astype(float)
    g = (g - g.min()) / (np.ptp(g) + 1e-9)
    return resize(g, SIZE, anti_aliasing=True)


def load_rgb(path):
    im = io.imread(path)
    rgb = np.stack([im] * 3, -1) / 255.0 if im.ndim == 2 else im[..., :3] / 255.0
    return resize(rgb, SIZE, anti_aliasing=True)


def load_split(cat, split):
    d = os.path.join(DATA, cat, split); items = []
    if not os.path.isdir(d):
        return items
    for defect in sorted(os.listdir(d)):
        dd = os.path.join(d, defect)
        if not os.path.isdir(dd):
            continue
        for f in sorted(os.listdir(dd)):
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                items.append((os.path.join(dd, f), defect))
    return items


def ortho6(R, Rc):
    out = np.zeros(6)
    Rb = filters.gaussian(R, 1.5)
    peaks = Rb - morphology.opening(Rb, morphology.disk(3))
    out[0] = np.percentile(peaks, 99.9)
    F = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = F.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = F[rad > min(h, w) * 0.25].sum() / (F.sum() + 1e-9)
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), 99.0)
    m = Rb.mean(); s = Rb.std() + 1e-9
    out[3] = float(((Rb - m) ** 3).mean() / s ** 3)
    out[4] = np.percentile(Rc[..., 1], 99.5) if Rc.ndim == 3 else np.percentile(Rc, 99.5)
    msk = Rb > np.percentile(Rb, 99.0); lab = measure.label(msk); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp)
    return out


def damage_sequence(g0, rgb0, T, rng, mode="crack", amp=0.6):
    """单一物理损伤场 D(x,y,t) 的演化, 返回每帧 (g, rgb, D)。
    - mode='crack' : 点状萌生 -> 扩展成缝(边界强)
    - mode='spot'  : 斑状(腐蚀/污染)增长(面积增长)
    - mode='wear'  : 面状磨损(渐变整体)
    不指定任何"通道滞后"。六爻响应由 D 与实际图像变化自然产生。
    """
    h, w = g0.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cy = rng.integers(h // 3, 2 * h // 3); cx = rng.integers(w // 3, 2 * w // 3)
    frames = []
    for t in range(T + 1):
        a = t / T
        if mode == "crack":
            # 点->线扩展: 初始极小半径, 之后沿某方向拉长(缝)
            ang = rng.uniform(0, np.pi) if t == 0 else ang
            L = 1 + a * 28
            r = 1.0 + a * 2.5
            vx, vy = np.cos(ang), np.sin(ang)
            proj = (xx - cx) * vx + (yy - cy) * vy
            perp = -(xx - cx) * vy + (yy - cy) * vx
            D = np.exp(-(perp ** 2) / (2 * r ** 2)) * np.exp(-(np.clip(np.abs(proj) - L / 2, 0, None) ** 2) / (2 * (L * .5 + 1) ** 2))
            A = amp * (a ** 0.7)
        elif mode == "spot":
            r = 2 + a * 26
            D = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
            A = amp * (a ** 0.8)
        else:  # wear
            r = 8 + a * 40
            D = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
            A = amp * a
        g = np.clip(g0 - A * D, 0, 1)
        if rgb0.ndim == 3:
            # 损伤场对各颜色通道【同源等权】作用(不指定任何颜色偏好)
            #   物理上: 损伤只是改变局部反射率, 灰度与三通道同比例受影响
            scale = 0.35
            rgb = np.clip(rgb0 - A * scale * D[..., None], 0, 1)
        else:
            rgb = g
        frames.append((g, rgb, D))
    return frames


def run(cat, trials, T, modes):
    train = [p for p, d in load_split(cat, "train")]
    ref_g = [load_gray(p) for p in train[:40]]
    ref_c = [load_rgb(p) for p in train[:40]]
    T0 = np.mean(ref_g, 0); S0 = np.std(ref_g, 0) + 1e-3
    TC0 = np.mean(ref_c, 0); SC0 = np.std(ref_c, 0) + 1e-3
    F0 = np.array([ortho6(filters.gaussian(np.abs(ref_g[i] - T0) / S0, 2.0),
                          np.abs(ref_c[i] - TC0) / SC0) for i in range(len(ref_g))])
    mu0, sd0 = F0.mean(0), F0.std(0) + 1e-9
    # 正常波动的阈值: 每爻用【各自正常分布】的稳健上界(z 空间), 保证可比/公平
    Z0 = np.abs((F0 - mu0) / sd0)
    thr = np.percentile(Z0, 99, axis=0) + 1e-9
    thr = np.maximum(thr, 1.0)

    all_curves = []
    first_t_all = []
    for trial in range(trials):
        rng = np.random.default_rng(trial)
        mode = modes[trial % len(modes)]
        bg = ref_g[trial % len(ref_g)]; bc = ref_c[trial % len(ref_c)]
        frames = damage_sequence(bg, bc, T, rng, mode=mode)
        seq = np.zeros((T + 1, 6))
        for t, (g, rgb, D) in enumerate(frames):
            R = filters.gaussian(np.abs(g - T0) / S0, 2.0)
            Rc = np.abs(rgb - TC0) / SC0
            f = ortho6(R, Rc)
            seq[t] = np.abs((f - mu0) / sd0)      # 每爻标准化偏离(绝对值, 正比于异常)
        all_curves.append(seq)
        # 各爻首次越阈时刻
        ft = {}
        for i in range(6):
            idx = np.where(seq[:, i] > thr[i])[0]
            ft[i] = int(idx[0]) if len(idx) else -1
        first_t_all.append(ft)
    return np.array(all_curves), first_t_all, thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", default="bottle")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--T", type=int, default=30)
    a = ap.parse_args()
    modes = ["crack", "spot", "wear"]
    curves, first_t, thr = run(a.cat, a.trials, a.T, modes)
    mean_curve = curves.mean(0)

    print(f"\n类别={a.cat} trials={a.trials} 情形={modes} T={a.T}")
    print("六爻平均失位(标准化)随时间:")
    show = [0, 5, 10, 15, 20, 25, 30]
    print("        " + " ".join(f"t{t:>2d}" for t in show))
    for i in range(6):
        print(f"  {YAO[i]:6s} " + " ".join(f"{mean_curve[t,i]:5.2f}" for t in show))

    print("\n各爻首次越阈时刻(越小越早):")
    for i in range(6):
        vals = [ft[i] for ft in first_t if ft[i] >= 0]
        if vals:
            print(f"  {YAO[i]:6s}: 中位={np.median(vals):5.1f} 均值={np.mean(vals):5.1f} 越阈率={len(vals)/len(first_t):.2f}")
        else:
            print(f"  {YAO[i]:6s}: 从未越阈")

    # 统计"初爻是否最早"
    init_first = sum(1 for ft in first_t if ft[0] >= 0 and all(ft[0] <= ft[j] for j in range(6) if ft[j] >= 0))
    print(f"\n初爻(几)最早越阈的比例: {init_first}/{len(first_t)} = {init_first/len(first_t):.2f}")

    # Spearman: 爻位 vs 首次时刻
    from scipy.stats import spearmanr
    pairs = [(i, np.mean([ft[i] for ft in first_t if ft[i] >= 0]))
             for i in range(6) if any(ft[i] >= 0 for ft in first_t)]
    if len(pairs) >= 3:
        rho, p = spearmanr([x[0] for x in pairs], [x[1] for x in pairs])
        print(f"爻位 vs 激活时间 Spearman ρ={rho:.3f} (p={p:.3f})  [负=越靠下越早, 支持知几]")

    json.dump(dict(cat=a.cat, trials=a.trials, modes=modes,
                   mean_curve=mean_curve.tolist(),
                   first_t=first_t,
                   init_first_ratio=init_first / len(first_t),
                   thr=thr.tolist()),
              open(os.path.join(RES, f"exp5_zhi_ji_{a.cat}.json"), "w"), ensure_ascii=False, indent=2)

    # 出图
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(14, 5))
    tt = np.arange(a.T + 1)
    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4", "#9467bd", "#8c564b"]
    for i in range(6):
        ax[0].plot(tt, mean_curve[:, i], "-", color=colors[i], label=YAO[i])
    ax[0].set_xlabel("time step t"); ax[0].set_ylabel("yao displacement (std)")
    ax[0].set_title(f"({a.cat}) Six-yao response over defect evolution")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    # 首次越阈时刻分布
    for i in range(6):
        vals = [ft[i] for ft in first_t if ft[i] >= 0]
        if vals:
            ax[1].hist(vals, bins=range(0, a.T + 2), alpha=0.5, color=colors[i], label=YAO[i])
    ax[1].set_xlabel("first-threshold-crossing time"); ax[1].set_ylabel("count")
    ax[1].set_title("Activation order distribution")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    plt.suptitle(f"Zhi-Ji test (physically-driven damage evolution), {a.cat}")
    plt.tight_layout()
    out = os.path.join(FIG, f"exp5_zhi_ji_{a.cat}.png")
    fig.savefig(out, dpi=150); print("saved", out)


if __name__ == "__main__":
    main()
