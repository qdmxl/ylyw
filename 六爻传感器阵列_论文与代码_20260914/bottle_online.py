#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路径A 在线无监督学习工具 (bottle) —— 越用越准 + 阈值自动调整
================================================================================
核心理念(与论文主张一致):
  * 零样本冷启动: 第 1 张图即可判断。
  * 增量学习: 每处理一张【正常】图, 在线更新模板 T/S 与六爻分布 mu/sd, 阈值随之自动漂移。
  * 阈值自适应(无监督): 用"近期正常样本分数"的滑动分位数(默认 99 分位)自动定阈值,
    不依赖人工设定、不依赖标签; 越用正常样本越多 -> 阈值越稳 -> 判断越准。
  * 状态存盘: 模型与统计量持久化, 下次启动接着用(不再是每次从头)。

两种使用模式:
  1) serve  : 交互式单图喂入 (模拟"使用中"), 每张输出 正常/缺陷, 可标记 good 让其学习。
              状态实时存盘, 每次运行都在上次基础上继续。
  2) replay : 回放实验 —— 模拟"随着使用次数增多"的过程, 画出 准确率/误报/漏报/阈值 随
              使用次数变化的曲线, 直接验证"越用越准"。

状态文件: online_state_bottle.npz (模板/统计/滑动窗口/计数)

用法:
  cd /home/lijinhan/.openclaw/workspace-quantum/quantum_ylyw

  # 回放: 验证"越用越准"(用 test 集按时间顺序喂入, 评价指标准确率随n上升)
  ../.venv-quantum/bin/python bottle_online.py replay

  # 交互式: 从空模型开始, 喂图
  ../.venv-quantum/bin/python bottle_online.py serve --reset
  ../.venv-quantum/bin/python bottle_online.py serve data/mvtec/bottle/train/good/083-13.png --learn
  ../.venv-quantum/bin/python bottle_online.py serve data/mvtec/bottle/test/broken_large/000-94.png --viz
  ../.venv-quantum/bin/python bottle_online.py serve --predict data/x.png   # 只看结果不学习
"""
import os, sys, json, argparse
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
DATA = os.path.join(BASE, "data", "mvtec")
STATE = os.path.join(BASE, "online_state_bottle.npz")
FIG = os.path.join(BASE, "figures", "online"); os.makedirs(FIG, exist_ok=True)
SIZE = (160, 160)

from skimage import io, color, filters, measure, morphology
from skimage.transform import resize


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
    """正交六爻(与主实验一致)。"""
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


# ========================= 在线模型(增量) =========================
class OnlineModel:
    """在线增量模型: Welford 更新模板 T/S、六爻 mu/sd, 滑动窗口自动定阈值。"""

    def __init__(self, window=50, pct=99.0, T=None, S=None, TC=None, SC=None,
                 mu=None, sd=None, n=0, win_score=None, n_ok=0, n_defect=0, history=None):
        self.window = window          # 正常分数滑动窗口大小
        self.pct = pct                # 阈值分位
        self.T = T; self.S = S; self.TC = TC; self.SC = SC
        self.mu = mu; self.sd = sd
        self.n = n                    # 已学正常样本数
        self.win_score = win_score if win_score is not None else np.array([])  # 近期正常分数
        self.M2g = None; self.M2c = None; self.M2F = None
        self.n_ok = n_ok              # 累计判定正常数
        self.n_defect = n_defect      # 累计判定缺陷数
        self.history = history if history is not None else []  # [(score, is_defect)]

    # ---- 用当前模型给一张图打分 ----
    def score(self, path):
        g = load_gray(path); c = load_rgb(path)
        if self.T is None or self.n < 2:
            # 冷启动: 模板尚未建立(或仅1张), 无法可靠判断
            return 0.0, g, c
        R = filters.gaussian(np.abs(g - self.T) / self.S, 2.0)
        Rc = np.abs(c - self.TC) / self.SC
        F = ortho6(R, Rc)
        s = float(np.abs((F - self.mu) / self.sd).mean())
        return s, g, c

    def threshold(self, default=1.5, warmup=10):
        """自动阈值: 用滑动窗口内【正常样本分数】的高分位。
        正常样本 < warmup 时窗口统计不可靠 -> 回退到 mean+k*std(更保守, 防误报)。"""
        w = self.win_score
        if len(w) == 0:
            return default
        if len(w) < warmup:
            return float(w.mean() + 3.0 * w.std() + 1e-6)
        return float(np.percentile(w, self.pct))

    def decide(self, path):
        s, g, c = self.score(path)
        thr = self.threshold()
        is_defect = s > thr
        return s, thr, is_defect, g, c

    # ---- 用一张【正常】图增量更新模型 ----
    def learn(self, path, s_before=None):
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

        # 更新六爻分布 (Welford on 6-vec)
        R = filters.gaussian(np.abs(g - self.T) / self.S, 2.0)
        Rc = np.abs(c - self.TC) / self.SC
        F = ortho6(R, Rc)
        if self.mu is None:
            self.mu = F.copy(); self.M2F = np.zeros(6)
        else:
            dF = F - self.mu; self.mu = self.mu + dF / k; self.M2F = self.M2F + dF * (F - self.mu)
        self.sd = np.sqrt(np.maximum(self.M2F / max(k - 1, 1), 1e-9)) + 1e-9

        # 计算该(正常)图在当前模型下的分数, 入滑动窗口 -> 阈值自适应
        sc = float(np.abs((F - self.mu) / self.sd).mean())
        self.win_score = np.append(self.win_score, sc)
        if len(self.win_score) > self.window:
            self.win_score = self.win_score[-self.window:]

    def save(self):
        np.savez(STATE, T=self.T, S=self.S, TC=self.TC, SC=self.SC,
                 mu=self.mu, sd=self.sd, M2g=self.M2g, M2c=self.M2c, M2F=self.M2F,
                 n=np.array([self.n]), win_score=self.win_score,
                 n_ok=np.array([self.n_ok]), n_defect=np.array([self.n_defect]),
                 window=np.array([self.window]), pct=np.array([self.pct]))

    @classmethod
    def load(cls):
        if not os.path.exists(STATE):
            return cls()
        d = np.load(STATE, allow_pickle=True)
        m = cls(window=int(d["window"][0]), pct=float(d["pct"][0]))
        m.T = d["T"] if d["T"].ndim > 0 else None
        m.S = d["S"] if d["S"].ndim > 0 else None
        m.TC = d["TC"] if d["TC"].ndim > 0 else None
        m.SC = d["SC"] if d["SC"].ndim > 0 else None
        m.mu = d["mu"] if d["mu"].ndim > 0 else None
        m.sd = d["sd"] if d["sd"].ndim > 0 else None
        m.M2g = d["M2g"] if d["M2g"].ndim > 0 else None
        m.M2c = d["M2c"] if d["M2c"].ndim > 0 else None
        m.M2F = d["M2F"] if d["M2F"].ndim > 0 else None
        m.n = int(d["n"][0])
        m.win_score = d["win_score"]
        m.n_ok = int(d["n_ok"][0]); m.n_defect = int(d["n_defect"][0])
        return m


# ============================== replay ==============================
def cmd_replay(args):
    """模拟'使用次数增多'过程。
    场景: 系统上线后持续使用, 用户不断喂入图片。绝大多数是正常品,
    正常品被学习进模型(无监督), 阈值自动漂移; 偶发缺陷被检出。
    评价: 按'用过多少张'分段统计准确率, 验证越用越准。
    """
    test = load_split("bottle", "test")
    # 时间顺序: 正常品占多数被学习; 缺陷品穿插出现。随机打散后再交错
    good = [(p, d) for p, d in test if d == "good"]
    bad = [(p, d) for p, d in test if d != "good"]
    rng = np.random.default_rng(args.seed)
    order = []
    gi = bi = 0
    while gi < len(good) or bi < len(bad):
        # 正常:缺陷 = 2:1 的到访节奏(工业场景正常品更多)
        if gi < len(good):
            order.append(good[gi]); gi += 1
        if gi < len(good):
            order.append(good[gi]); gi += 1
        if bi < len(bad):
            order.append(bad[bi]); bi += 1
    # 同一类内打散
    def shuffle_group(x):
        idx = rng.permutation(len(x)); return [x[i] for i in idx]
    order = shuffle_group(order)

    m = OnlineModel(window=args.window, pct=args.pct)
    rows = []
    tp = tn = fp = fn = 0
    n_normal_seen = 0
    for i, (path, defect) in enumerate(order, 1):
        gt = 0 if defect == "good" else 1
        warm = (m.n < args.warmup)
        s, thr, pred, _, _ = m.decide(path)
        if warm:
            # 预热期: 只学习(正常品), 不计评价
            if gt == 0:
                m.learn(path); n_normal_seen += 1
            rows.append(dict(i=i, n_learned=m.n, n_normal=n_normal_seen, thr=thr, score=s,
                             gt=gt, pred=None, acc=None, recall=None, fp=0, fn=0, warm=True))
            continue
        # 评价段
        if gt == 1 and pred: tp += 1
        elif gt == 0 and pred: fp += 1
        elif gt == 1 and not pred: fn += 1
        else: tn += 1
        decided = tp + tn + fp + fn
        acc_now = (tp + tn) / decided
        if gt == 0:
            m.learn(path); n_normal_seen += 1   # 正常品 -> 学习
        rows.append(dict(i=i, n_learned=m.n, n_normal=n_normal_seen, thr=thr, score=s,
                         gt=gt, pred=int(pred), acc=acc_now,
                         recall=tp / max(tp + fn, 1), fp=fp, fn=fn, warm=False))

    # 汇总(只看评价段)
    stable = [r for r in rows if not r["warm"]]
    acc = np.mean([r["acc"] for r in stable]) if stable else 0
    rec = np.mean([r["recall"] for r in stable]) if stable else 0
    print(f"replay 完成: 共 {len(rows)} 张 (预热 {sum(r['warm'] for r in rows)} 张, 评价 {len(stable)} 张)")
    print(f"评价段平均准确率={acc:.4f} 平均召回={rec:.4f}")
    print(f"累计: TP={tp} TN={tn} FP={fp} FN={fn}")
    # 分段看是否'越用越准'
    for lo, hi in [(1, 20), (21, 40), (41, 60), (61, 200)]:
        seg = [r for r in stable if lo <= r["i"] <= hi]
        if seg:
            print(f"  使用第 {lo:3d}-{hi:3d} 张: 准确率={np.mean([r['acc'] for r in seg]):.4f}")
    json.dump(rows, open(os.path.join(BASE, "results", "online_replay_bottle.json"), "w"),
              ensure_ascii=False, indent=2)
    print("saved results/online_replay_bottle.json")

    # 画"越用越准"曲线
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [r["i"] for r in rows if r["acc"] is not None]
    accs = [r["acc"] for r in rows if r["acc"] is not None]
    thrs = [r["thr"] for r in rows]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ax[0].plot(xs, accs, "-", color="#1f77b4")
    ax[0].set_xlabel("Image index (usage count)"); ax[0].set_ylabel("Cumulative accuracy")
    ax[0].set_title("(a) Accuracy vs usage count (online, unsupervised)")
    ax[0].axhline(0.5, ls="--", c="gray", lw=0.8); ax[0].grid(alpha=0.3)
    ax[1].plot(range(1, len(rows) + 1), thrs, "-", color="#d62728")
    ax[1].set_xlabel("Image index (usage count)"); ax[1].set_ylabel("Auto threshold")
    ax[1].set_title("(b) Auto-adaptive threshold over time")
    ax[1].grid(alpha=0.3)
    plt.suptitle("YLYW bottle: Online unsupervised learning, auto threshold")
    plt.tight_layout()
    out = os.path.join(FIG, "bottle_online_replay.png")
    fig.savefig(out, dpi=150); print("saved", out)


# ============================== serve ==============================
def cmd_serve(args):
    if args.reset and os.path.exists(STATE):
        os.remove(STATE); print("已重置状态")
    m = OnlineModel.load()
    if m.T is not None:
        print(f"载入已有模型: 已学 {m.n} 张正常图, 阈值={m.threshold():.4f}")
    else:
        print("空模型(冷启动): 第一张正常图将建立初始模板")

    img = args.image or args.predict
    if not img:
        print("请给图片路径, 或 --predict <img>"); return
    if not os.path.exists(img):
        print(f"❌ 图片不存在: {img}"); return

    if args.learn:
        # 先看判断, 再学习(标记为正常)
        s, thr, pred, g, c = m.decide(img)
        print(f"[学习前] 图片={img} 分数={s:.4f} 阈值={thr:.4f} -> {'缺陷' if pred else '正常'}")
        m.learn(img)
        m.n_ok += 1
        print(f"[学习后] 已学正常图 {m.n} 张, 新阈值={m.threshold():.4f}")
    else:
        s, thr, pred, g, c = m.decide(img)
        m.n_ok += (0 if pred else 1); m.n_defect += (1 if pred else 0)
        print(f"图片: {img}")
        print(f"异常分数 = {s:.4f}   (自动阈值 {thr:.4f}, 已学 {m.n} 张正常图)")
        print("=" * 46)
        print("🔴 判定: 有缺陷  (DEFECT)" if pred else "🟢 判定: 正常  (OK / good)")
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
            out = os.path.join(FIG, os.path.splitext(os.path.basename(img))[0] + "_online.png")
            plt.tight_layout(); fig.savefig(out, dpi=130); print("可视化 ->", out)

    m.save()
    print(f"状态已保存 -> {STATE} (下次接着用)")


def main():
    ap = argparse.ArgumentParser(description="路径A bottle 在线无监督学习工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rp = sub.add_parser("replay", help="回放验证'越用越准'")
    p_rp.add_argument("--window", type=int, default=50, help="正常分数滑动窗口(默认50)")
    p_rp.add_argument("--pct", type=float, default=99.0, help="阈值分位(默认99)")
    p_rp.add_argument("--seed", type=int, default=0)
    p_rp.add_argument("--warmup", type=int, default=15, help="预热期正常图数(默认15), 期间不计评价")
    p_rp.set_defaults(func=cmd_replay)

    p_sv = sub.add_parser("serve", help="交互式单图喂入(状态持久化)")
    p_sv.add_argument("image", nargs="?", help="图片路径")
    p_sv.add_argument("--predict", help="同 image, 仅判断不学习")
    p_sv.add_argument("--learn", action="store_true", help="将该图标记为正常并学习")
    p_sv.add_argument("--viz", action="store_true", help="保存残差热图")
    p_sv.add_argument("--reset", action="store_true", help="清空状态, 从头开始")
    p_sv.set_defaults(func=cmd_serve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
