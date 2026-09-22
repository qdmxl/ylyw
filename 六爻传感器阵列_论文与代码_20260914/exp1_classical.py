#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验1(经典加权版): YLYW 易理加权 —— "知几"式早期缺陷预警
==============================================================================
主方法: 经典易理加权
    P(q) = base(q) * exp(-λ·U(q)) / Z
  - base(q): 观测六爻模糊隶属度给出的卦象似然(相机/CNN 提取的"象")
  - U(q):    易理势能(不当位/失中/不应/乘刚 的加权和)
  - λ:       易理先验强度

修正说明(2026-09-12):
  1. 64卦降维/归类一律按【上卦】(gua_order.hex64_to_bagua8), 废除错误的 i//8 分组;
  2. 卦变序列沿【分宫卦象次序】的汉明距离-1 路径演化, 使"渐变"有典籍依据。

对比基线:
  B1 观测法(no-prior)     : 直接取 base(q) 的 argmax —— 纯观测, 无易理
  B2 阈值法(单帧统计)      : 每帧算异常分数, 固定阈值
  B3 平滑观测(EMA)        : base 的时间指数平滑, 无易理先验
  YLYW 易理加权(本方法)

核心指标:
  * 预警提前量 lead = t_visible − t_trigger  (越大越好)
  * 误报率 FPR     (正常段触发比例, 越小越好)
  * 检测 AUROC     (区分正常/缺陷帧)
  * 判别比 DR      = harmony_mass / anomaly_mass
"""
import json, os, sys
import numpy as np
from sklearn.metrics import roc_auc_score

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from gua_order import hex64_to_bagua8, BAGONG_INDEX, bagong_sequence, hamming, BAGUA

RES, FIG = os.path.join(BASE, "results"), os.path.join(BASE, "figures")
os.makedirs(RES, exist_ok=True); os.makedirs(FIG, exist_ok=True)
rng = np.random.default_rng(20260912)

# ==================== 易理势能层(作用在 6 爻 64 卦空间) ====================
def yao(q, i): return (q >> i) & 1          # bit0=初爻 ... bit5=上爻
def n_budangwei(q): return sum(1 for i in range(6) if yao(q, i) != (1 if i % 2 == 0 else 0))
def n_shizhong(q):  return 0 if yao(q, 1) != yao(q, 4) else 1
def n_buying(q):    return sum(1 for a, b in [(0, 3), (1, 4), (2, 5)] if yao(q, a) == yao(q, b))
def n_chenggang(q): return sum(1 for i in range(5) if yao(q, i) == 1 and yao(q, i+1) == 0)

W = dict(budangwei=1.0, shizhong=0.8, buying=0.6, chenggang=0.5)
def U(q):
    return (W["budangwei"]*n_budangwei(q) + W["shizhong"]*n_shizhong(q)
            + W["buying"]*n_buying(q) + W["chenggang"]*n_chenggang(q))

ALL = list(range(64))
Uvals = np.array([U(q) for q in ALL])
Umin = Uvals.min()
# 分宫序标签(用于序列分析)
BAGONG = bagong_sequence()
BAGONG_ORDER = [q for _, _, q, _ in BAGONG]      # 64 卦的分宫排列

HARMONIC  = set(q for q in ALL if U(q) <= np.percentile(Uvals, 25))
ANOMALOUS = set(q for q in ALL if U(q) >= np.percentile(Uvals, 75))

# ==================== 观测层: 六爻模糊隶属度 -> 64卦似然 ====================
def base_dist(z):
    """z: 6维倾向(越大越阳) -> base(q) 独立伯努利乘积"""
    p = 1/(1+np.exp(-z)); p = np.clip(p, 1e-6, 1-1e-6)
    d = np.ones(64)
    for q in range(64):
        for i in range(6):
            d[q] *= p[i] if yao(q, i) == 1 else (1-p[i])
    return d/d.sum()

# ==================== 主方法: 经典易理加权 ====================
def ylyw_weighted(z, lam=0.9):
    d = base_dist(z)
    w = d * np.exp(-lam*(Uvals - Umin))
    return w/w.sum()

def anomaly_mass(dist): return float(sum(dist[q] for q in ANOMALOUS))
def harmony_mass(dist): return float(sum(dist[q] for q in HARMONIC))

# ==================== 基线与指标 ====================
def detect_trigger(series, k=3.0, warmup=12):
    """动态阈值触发: 均值+k*std (基于预热正常段)"""
    mu, sd = series[:warmup].mean(), series[:warmup].std()+1e-9
    thr = mu + k*sd
    idx = np.argmax(series > thr)
    return int(idx) if (series > thr).any() else None

def ema(x, alpha=0.3):
    out = np.zeros_like(x); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha*x[i] + (1-alpha)*out[i-1]
    return out

# ==================== 帧序列: 沿分宫卦变路径演化 ====================
def make_normal_z():
    return np.array([1.1, -1.1, 1.1, -1.1, 1.1, -1.1]) + rng.normal(0, 0.12, 6)

def make_defect_z(prog):
    """prog∈[0,1]: 缺陷发展程度。
    正常基态 = 阳阴阳阴阳阴(当位卦, U 最低)。
    缺陷: 三爻(阳位,本应阳)由阳漂向阴 -> 失位, 并逐步引发不应/失中。"""
    z = np.array([1.1, -1.1, 1.1, -1.1, 1.1, -1.1]) + rng.normal(0, 0.12, 6)
    z[2] -= 2.6*prog        # 三爻(阳位)由阳->阴: 失位, 缺陷萌芽
    z[4] -= 1.6*prog**2     # 五爻(阳位)跟着阴化 -> 破坏得中
    z[1] += 1.2*prog**2     # 二爻(阴位)阳化 -> 破坏相应
    return z

def make_sequence(T=80, onset=0.25, kind="degrading"):
    """返回 z 序列 + 真实"缺陷可见"帧。
    缺陷可见 = 三爻倾向 z[2] 跌破 0(阴化, 肉眼可辨)"""
    zs, tvis = [], None
    for t in range(T):
        if kind == "normal":
            zs.append(make_normal_z())
        else:
            prog = np.clip((t - onset*T)/((1-onset)*T), 0, 1)
            z = make_defect_z(prog)
            zs.append(z)
            if tvis is None and z[2] < 0.0:
                tvis = t
    return zs, tvis

# ==================== 主流程 ====================
def main():
    T, onset = 80, 0.25
    rep = dict(env="classical-YLYW-weighted", T=T, onset=onset,
               lambda_=0.9, n_normal=len(HARMONIC), n_anomalous=len(ANOMALOUS))

    # ---------- (A) 稳态判别能力 ----------
    print("="*74); print("(A) 稳态判别: 正常态 vs 缺陷态"); print("="*74)
    normal_z = np.array([1.1,-1.1,1.1,-1.1,1.1,-1.1])
    defect_z = normal_z + np.array([0,0,-2.6,0,-1.6,0])
    rows=[]
    for tag,z in [("normal",normal_z),("defect",defect_z)]:
        b = base_dist(z); y = ylyw_weighted(z)
        rows.append(dict(state=tag,
            base_anomaly=anomaly_mass(b), base_harmony=harmony_mass(b),
            ylyw_anomaly=anomaly_mass(y), ylyw_harmony=harmony_mass(y),
            base_DR=harmony_mass(b)/max(anomaly_mass(b),1e-12),
            ylyw_DR=harmony_mass(y)/max(anomaly_mass(y),1e-12)))
        print(f"  [{tag:6s}] 观测: anomaly={anomaly_mass(b):.4f} harmony={harmony_mass(b):.4f} DR={rows[-1]['base_DR']:.2f}")
        print(f"           易理: anomaly={anomaly_mass(y):.4f} harmony={harmony_mass(y):.4f} DR={rows[-1]['ylyw_DR']:.2f}")
    rep["steady"]=rows

    # ---------- (B) 时序知几预警 ----------
    print("="*74); print("(B) 时序'知几'预警"); print("="*74)
    zs, tvis = make_sequence(T, onset, "degrading")
    zs_n, _ = make_sequence(T, onset, "normal")

    # 各方法的异常分数序列
    seq_base = np.array([anomaly_mass(base_dist(z)) for z in zs])
    seq_ylyw = np.array([anomaly_mass(ylyw_weighted(z)) for z in zs])
    seq_ema  = ema(seq_base, 0.3)

    # 正常段(假阳性)对照
    nseq_base = np.array([anomaly_mass(base_dist(z)) for z in zs_n])
    nseq_ylyw = np.array([anomaly_mass(ylyw_weighted(z)) for z in zs_n])
    nseq_ema  = ema(nseq_base, 0.3)

    res = {}
    for name, s, sn in [("B1 观测法", seq_base, nseq_base),
                        ("B3 平滑观测", seq_ema, nseq_ema),
                        ("YLYW易理加权", seq_ylyw, nseq_ylyw)]:
        tt = detect_trigger(s, k=3.0)
        # 误报: 正常段超过缺陷段阈值的比例
        mu, sd = s[:12].mean(), s[:12].std()+1e-9
        thr = mu + 3*sd
        fpr = float((sn > thr).mean())
        lead = (tvis - tt) if tt is not None else None
        # AUROC: 用 onset 后为"缺陷"标签
        y_true = np.array([1 if t>=onset*T else 0 for t in range(T)])
        try:
            auc = roc_auc_score(y_true, s)
        except Exception:
            auc = float("nan")
        res[name]=dict(trigger=tt, lead=lead, fpr=fpr, auroc=float(auc),
                       onset=int(onset*T))
        print(f"  {name:12s} 触发t={tt}  提前={lead}帧  FPR={fpr:.3f}  AUROC={auc:.3f}")

    print(f"  (缺陷可见 t={tvis}, 缺陷起始 t={int(onset*T)})")
    rep["temporal"]=dict(visible_t=tvis, onset=int(onset*T), results=res,
        series=dict(base=seq_base.tolist(), ylyw=seq_ylyw.tolist(), ema=seq_ema.tolist()))

    with open(os.path.join(RES,"exp1_ylyw_classical.json"),"w") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)

    # ---------- 画图 ----------
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10,5))
        ax.plot(seq_base, label="B1 observation (no prior)", lw=1.8, ls="-.", color="tab:green")
        ax.plot(seq_ema,  label="B3 smoothed observation", lw=1.8, ls="--", color="tab:orange")
        ax.plot(seq_ylyw, label="YLYW classical weighted", lw=2.5, color="tab:blue")
        ax.axvline(tvis, color="red", alpha=.6, lw=1.8, label=f"defect visible t={tvis}")
        ax.axvline(int(onset*T), color="gray", alpha=.5, ls=":", label=f"defect onset t={int(onset*T)}")
        ax.set_xlabel("frame t"); ax.set_ylabel("anomaly-gua mass")
        ax.set_title("Exp1 (classical YLYW): Zhi-ji early warning of defect")
        ax.legend(loc="upper left", fontsize=9); fig.tight_layout()
        fig.savefig(os.path.join(FIG,"exp1_ylyw_classical.png"), dpi=150)
        print("saved figures/exp1_ylyw_classical.png")
    except Exception as e:
        print("plot skipped:", e)

if __name__ == "__main__":
    main()
