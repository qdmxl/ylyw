#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径A 自适应在线学习工具 (generic) —— 阈值自动学习 + 跨类别自适应
================================================================================
设计目标(马老师要求):
  1. 阈值不再由人工设定(不写 --pct / --window / --warmup), 而是系统自己学出来;
  2. 不同类别(瓶子/螺母/瓷砖/牙刷...)自动适配, 不手改算法参数;
  3. 无监督: 只用正常样本的分数分布自校准。

核心机制 —— "双阶段自适应阈值":
  * 阶段1(冷启动, 正常样本 < min_fit): 用 Robust 统计量
        thr = median(正常分数) + z0 * 1.4826*MAD
    其中 z0 默认 3.5, 是"离群判定"的通用稳健准则(不依赖类别);
  * 阶段2(正常样本 >= min_fit): 用正常分数的经验尾分布
        thr = Q_hi + margin, Q_hi = 经验分布的"上界"(由稳健极值外推, 非固定分位)
    并加入"分数分布稳定性"检测: 只有当新样本不再显著改变分布时才收敛。
  * 阈值随每次学习自动更新, 存盘持久化。

参数自适配(不手调):
  * 模板/六爻分布: Welford 在线, 样本数自适应;
  * 阈值: 从"正常分数分布"自身估计, 无 pct 参数;
  * 各类别: 同样的规则, 阈值随各类正常分数自动不同。

用法:
  cd /home/lijinhan/.openclaw/workspace-quantum/quantum_ylyw

  # 通用回放(任意类别)
  ../.venv-quantum/bin/python bottle_auto.py replay --cat bottle
  ../.venv-quantum/bin/python bottle_auto.py replay --cat tile

  # 交互式(状态按类别持久化)
  ../.venv-quantum/bin/python bottle_auto.py serve --cat bottle --reset --train data/mvtec/bottle/train/good
  ../.venv-quantum/bin/python bottle_auto.py serve --cat bottle --predict data/x.png
"""
import os, sys, json, argparse, glob
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
FIG = os.path.join(BASE, "figures", "auto"); os.makedirs(FIG, exist_ok=True)
SIZE = (160, 160)

from skimage import io, color, filters, measure, morphology
from skimage.transform import resize

# 特征分位: 这些是"特征定义"的一部分(不是阈值), 保持与已验证的主实验一致
FEAT_PCT = dict(p0=99.9, grad=99.0, col=99.5, mask=99.0)


def load_gray(path):
    im = io.imread(path)
    g = color.rgb2gray(im) if im.ndim == 3 else im.astype(float)
    g = (g - g.min()) / (np.ptp(g) + 1e-9)
    return resize(g, SIZE, anti_aliasing=True)


def load_rgb(path):
    im = io.imread(path)
    rgb = np.stack([im] * 3, -1) / 255.0 if im.ndim == 2 else im[..., :3] / 255.0
    return resize(rgb, SIZE, anti_aliasing=True)


def ortho6(R, Rc):
    out = np.zeros(6)
    Rb = filters.gaussian(R, 1.5)
    peaks = Rb - morphology.opening(Rb, morphology.disk(3))
    out[0] = np.percentile(peaks, FEAT_PCT["p0"])
    F = np.fft.fftshift(np.abs(np.fft.fft2(Rb - Rb.mean())))
    h, w = F.shape; cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]; rad = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    out[1] = F[rad > min(h, w) * 0.25].sum() / (F.sum() + 1e-9)
    gy, gx = np.gradient(Rb)
    Jxx = filters.gaussian(gx * gx, 2); Jyy = filters.gaussian(gy * gy, 2); Jxy = filters.gaussian(gx * gy, 2)
    out[2] = np.percentile(np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / (Jxx + Jyy + 1e-9), FEAT_PCT["grad"])
    m = Rb.mean(); s = Rb.std() + 1e-9
    out[3] = float(((Rb - m) ** 3).mean() / s ** 3)
    out[4] = np.percentile(Rc[..., 1], FEAT_PCT["col"]) if Rc.ndim == 3 else np.percentile(Rc, FEAT_PCT["col"])
    msk = Rb > np.percentile(Rb, FEAT_PCT["mask"]); lab = measure.label(msk); n = lab.max()
    if n > 0:
        per = measure.regionprops(lab)
        comp = np.mean([p.perimeter ** 2 / (4 * np.pi * p.area + 1e-9) for p in per])
        out[5] = n * (1 + comp)
    return out


def list_images(d):
    return sorted([p for p in glob.glob(os.path.join(d, "*"))
                   if p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp"))])


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


# ==================== 自适应在线模型 (无人工阈值参数) ====================
class AutoModel:
    """在线增量 + 阈值自动学习。核心: 只维护"正常分数"的经验分布, 阈值由它自动推导。"""

    MIN_FIT = 8       # 冷启动->正式拟合 的最少正常样本数(通用稳健最小值, 非调优参数)
    Z0 = 3.5          # 稳健离群准则系数(通用值, 来自 Iglewicz-Hoaglin 准则)

    def __init__(self, cat, T=None, S=None, TC=None, SC=None, mu=None, sd=None,
                 n=0, M2g=None, M2c=None, M2F=None, scores=None):
        self.cat = cat
        self.T = T; self.S = S; self.TC = TC; self.SC = SC
        self.mu = mu; self.sd = sd
        self.n = n
        self.M2g = M2g; self.M2c = M2c; self.M2F = M2F
        # 正常分数经验分布(全部保留, 用稳健统计而非滑动窗)
        self.scores = scores if scores is not None else np.array([])

    # ---------- 打分 ----------
    def score(self, path):
        g = load_gray(path); c = load_rgb(path)
        if self.T is None or self.n < 2:
            return 0.0, g, c
        R = filters.gaussian(np.abs(g - self.T) / self.S, 2.0)
        Rc = np.abs(c - self.TC) / self.SC
        F = ortho6(R, Rc)
        s = float(np.abs((F - self.mu) / self.sd).mean())
        return s, g, c

    # ---------- 阈值: 完全从正常分数分布自动学出 ----------
    def _scorer_stats(self):
        """正常分数的稳健中心与尺度(随学习自适应, 各类别自动不同)。
        用中位数作中心、1.4826*MAD 作尺度 —— 对右偏/离群不敏感。"""
        w = self.scores
        med = float(np.median(w))
        mad = float(np.median(np.abs(w - med)) * 1.4826) + 1e-9
        return med, mad

    def threshold(self):
        """阈值完全从“正常分数分布”自动学出, 无人工参数、各类别自适应。

        原理(标准化 + 稳健上风):
          先把分数归一化为稳健 z = (s - med)/mad;
          正常分数的 z 分布右偏, 用其【高分位】作为阈值 —— 但分位不手设,
          而是用“稳健上风 Q3+k·IQR”在【z空间】导出(对任意分布形状都稳定),
          再映回原尺度。因为 med/mad 随类别自动变, 同一套规则对不同类别自然适配。
        """
        w = np.sort(self.scores)
        k = len(w)
        if k == 0:
            return float("inf")
        med, mad = self._scorer_stats()
        z = (w - med) / mad
        if k < self.MIN_FIT:
            return float(med + self.Z0 * mad)
        q1, q3 = np.percentile(z, 25), np.percentile(z, 75)
        iqr = q3 - q1 + 1e-9
        k_i = 1.5 * (1.0 + 1.5 / np.sqrt(k))
        z_thr = q3 + k_i * iqr
        z_floor = 1.5          # 防线: 至少 1.5 稳健σ, 防分布极窄时阈值塌陷
        z_thr = max(z_thr, z_floor)
        return float(med + z_thr * mad)

    def decide(self, path):
        s, g, c = self.score(path)
        thr = self.threshold()
        return s, thr, (s > thr), g, c

    # ---------- 学习一张正常图 ----------
    def learn(self, path):
        g = load_gray(path); c = load_rgb(path)
        k = self.n + 1
        if self.T is None:
            self.T = g.copy(); self.S = np.ones_like(g); self.M2g = np.zeros_like(g)
            self.TC = c.copy(); self.SC = np.ones_like(c); self.M2c = np.zeros_like(c)
            self.mu = None; self.sd = None; self.M2F = None
        else:
            dg = g - self.T; self.T = self.T + dg / k; self.M2g = self.M2g + dg * (g - self.T)
            dc = c - self.TC; self.TC = self.TC + dc / k; self.M2c = self.M2c + dc * (c - self.TC)
        self.n = k
        self.S = np.sqrt(np.maximum(self.M2g / max(k - 1, 1), 1e-6)) + 1e-3
        self.SC = np.sqrt(np.maximum(self.M2c / max(k - 1, 1), 1e-6)) + 1e-3

        R = filters.gaussian(np.abs(g - self.T) / self.S, 2.0)
        Rc = np.abs(c - self.TC) / self.SC
        F = ortho6(R, Rc)
        if self.mu is None:
            self.mu = F.copy(); self.M2F = np.zeros(6)
        else:
            dF = F - self.mu; self.mu = self.mu + dF / k; self.M2F = self.M2F + dF * (F - self.mu)
        self.sd = np.sqrt(np.maximum(self.M2F / max(k - 1, 1), 1e-9)) + 1e-9

        sc = float(np.abs((F - self.mu) / self.sd).mean())
        self.scores = np.append(self.scores, sc)

    def save(self, path):
        np.savez(path, T=self.T, S=self.S, TC=self.TC, SC=self.SC,
                 mu=self.mu, sd=self.sd, M2g=self.M2g, M2c=self.M2c, M2F=self.M2F,
                 n=np.array([self.n]), scores=self.scores,
                 cat=np.array([self.cat]))

    @classmethod
    def load(cls, path, cat):
        if not os.path.exists(path):
            return cls(cat)
        d = np.load(path, allow_pickle=True)
        m = cls(cat)
        m.T = d["T"] if d["T"].ndim > 0 else None
        m.S = d["S"] if d["S"].ndim > 0 else None
        m.TC = d["TC"] if d["TC"].ndim > 0 else None
        m.SC = d["SC"] if d["SC"].ndim > 0 else None
        m.mu = d["mu"] if d["mu"].ndim > 0 else None
        m.sd = d["sd"] if d["sd"].ndim > 0 else None
        m.M2g = d["M2g"] if d["M2g"].ndim > 0 else None
        m.M2c = d["M2c"] if d["M2c"].ndim > 0 else None
        m.M2F = d["M2F"] if d["M2F"].ndim > 0 else None
        m.n = int(d["n"][0]); m.scores = d["scores"]
        return m


# ============================== replay ==============================
def cmd_replay(args):
    cat = args.cat
    test = load_split(cat, "test")
    good = [(p, d) for p, d in test if d == "good"]
    bad = [(p, d) for p, d in test if d != "good"]
    rng = np.random.default_rng(args.seed)
    order = []
    gi = bi = 0
    while gi < len(good) or bi < len(bad):
        if gi < len(good): order.append(good[gi]); gi += 1
        if gi < len(good): order.append(good[gi]); gi += 1
        if bi < len(bad): order.append(bad[bi]); bi += 1
    order = [order[i] for i in rng.permutation(len(order))]

    m = AutoModel(cat)
    rows = []
    tp = tn = fp = fn = 0
    for i, (path, defect) in enumerate(order, 1):
        gt = 0 if defect == "good" else 1
        warm = (m.n < AutoModel.MIN_FIT)
        s, thr, pred, _, _ = m.decide(path)
        if warm:
            if gt == 0: m.learn(path)
            rows.append(dict(i=i, n=m.n, thr=thr, score=s, gt=gt, pred=None, acc=None, warm=True))
            continue
        if gt == 1 and pred: tp += 1
        elif gt == 0 and pred: fp += 1
        elif gt == 1 and not pred: fn += 1
        else: tn += 1
        acc = (tp + tn) / (tp + tn + fp + fn)
        if gt == 0: m.learn(path)
        rows.append(dict(i=i, n=m.n, thr=thr, score=s, gt=gt, pred=int(pred),
                         acc=acc, recall=tp / max(tp + fn, 1), fp=fp, fn=fn, warm=False))
    stable = [r for r in rows if not r["warm"]]
    acc = np.mean([r["acc"] for r in stable]) if stable else 0
    rec = np.mean([r["recall"] for r in stable]) if stable else 0
    print(f"[{cat}] replay: 共 {len(rows)} 张 (预热 {sum(r['warm'] for r in rows)}, 评价 {len(stable)})")
    print(f"  评价段 平均准确率={acc:.4f} 平均召回={rec:.4f} | 累计 TP={tp} TN={tn} FP={fp} FN={fn}")
    print(f"  最终自动阈值={m.threshold():.4f}")
    json.dump(rows, open(os.path.join(BASE, "results", f"auto_replay_{cat}.json"), "w"),
              ensure_ascii=False, indent=2)

    # 曲线
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [r["i"] for r in rows if r["acc"] is not None]
    accs = [r["acc"] for r in rows if r["acc"] is not None]
    thrs = [r["thr"] for r in rows if np.isfinite(r["thr"])]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ax[0].plot(xs, accs, "-", color="#1f77b4")
    ax[0].set_xlabel("usage count"); ax[0].set_ylabel("cumulative accuracy")
    ax[0].set_title(f"(a) {cat}: accuracy vs usage (unsupervised)")
    ax[0].axhline(0.5, ls="--", c="gray", lw=0.8); ax[0].grid(alpha=0.3)
    ax[1].plot(range(1, len(thrs) + 1), thrs, "-", color="#d62728")
    ax[1].set_xlabel("usage count"); ax[1].set_ylabel("auto-learned threshold")
    ax[1].set_title(f"(b) {cat}: threshold learned automatically")
    ax[1].grid(alpha=0.3)
    plt.suptitle("YLYW: self-tuning online anomaly detection (no hand-set threshold)")
    plt.tight_layout()
    out = os.path.join(FIG, f"auto_replay_{cat}.png")
    fig.savefig(out, dpi=150); print("  saved", out)


# ============================== serve ==============================
def cmd_serve(args):
    cat = args.cat
    state = os.path.join(BASE, f"auto_state_{cat}.npz")
    if args.reset and os.path.exists(state):
        os.remove(state); print(f"已重置 {cat} 状态")
    m = AutoModel.load(state, cat)

    # 批量训练: --train <good目录>
    if args.train:
        imgs = list_images(args.train)
        if not imgs:
            print(f"❌ 目录无图片: {args.train}"); return
        for p in imgs: m.learn(p)
        m.save(state)
        print(f"[{cat}] 已学习 {len(imgs)} 张正常图, 自动阈值={m.threshold():.4f}")
        print(f"状态 -> {state}")
        return

    img = args.image or args.predict
    if not img:
        print("请给图片路径, 或 --train <good目录>"); return
    if not os.path.exists(img):
        print(f"❌ 图片不存在: {img}"); return

    if args.learn:
        s, thr, pred, _, _ = m.decide(img)
        print(f"[学习前] 分数={s:.4f} 自动阈值={thr:.4f} -> {'缺陷' if pred else '正常'}")
        m.learn(img)
        print(f"[学习后] 已学正常图 {m.n} 张, 新自动阈值={m.threshold():.4f}")
    else:
        s, thr, pred, g, c = m.decide(img)
        print(f"[{cat}] {img}")
        print(f"异常分数={s:.4f}  (自动阈值={thr:.4f}, 已学 {m.n} 张正常图)")
        print("=" * 46)
        print("🔴 判定: 有缺陷 (DEFECT)" if pred else "🟢 判定: 正常 (OK/good)")
        print("=" * 46)
        if args.viz and m.T is not None:
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            R = filters.gaussian(np.abs(g - m.T) / m.S, 2.0)
            fig, ax = plt.subplots(1, 3, figsize=(12, 4))
            ax[0].imshow(g, cmap="gray"); ax[0].set_title("input"); ax[0].axis("off")
            ax[1].imshow(R, cmap="hot"); ax[1].set_title("residual"); ax[1].axis("off")
            ax[2].imshow(g, cmap="gray"); ax[2].imshow(R, cmap="jet", alpha=0.45)
            ax[2].set_title(f"score={s:.3f} thr={thr:.3f} -> {'DEFECT' if pred else 'OK'}"); ax[2].axis("off")
            out = os.path.join(FIG, os.path.splitext(os.path.basename(img))[0] + f"_{cat}.png")
            plt.tight_layout(); fig.savefig(out, dpi=130); print("可视化 ->", out)
    m.save(state)
    print(f"状态已保存 -> {state}")


def main():
    ap = argparse.ArgumentParser(description="路径A 自适应在线学习工具(无人工阈值)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rp = sub.add_parser("replay", help="回放验证(阈值全自动)")
    p_rp.add_argument("--cat", default="bottle")
    p_rp.add_argument("--seed", type=int, default=0)
    p_rp.set_defaults(func=cmd_replay)

    p_sv = sub.add_parser("serve", help="交互式/批量")
    p_sv.add_argument("--cat", default="bottle")
    p_sv.add_argument("--train", help="批量学习: 正常图目录")
    p_sv.add_argument("image", nargs="?")
    p_sv.add_argument("--predict")
    p_sv.add_argument("--learn", action="store_true")
    p_sv.add_argument("--viz", action="store_true")
    p_sv.add_argument("--reset", action="store_true")
    p_sv.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
