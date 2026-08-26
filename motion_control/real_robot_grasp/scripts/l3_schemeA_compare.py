"""方案 A：爻位加权 + 离散阴阳模板 —— L3 判别性改进对比实验。

对比两组:
  [基线] 现状: 余弦相似度 + 窄带浮点模板 (hexagram_rules 现有实现)
  [方案A] 改进: 爻位加权距离 + 易经真实阴阳模板(0/1) + 混合得分

方案 A 的逻辑依据:
  1. 64 卦的阴阳爻结构是《周易》确定的(每卦六爻非阴即阳)，
     而不是手写的一堆相近浮点数。用真实阴阳模式(0/1)作为模板，
     彼此天然正交、可分性远高于现有窄带模板。
  2. 给关键爻位加权: 中位(二爻、五爻)权重高于边缘位 —— 呼应 L3+ 得中思想。
  3. 匹配度量用"加权汉明/加权距离"而非纯余弦 —— 直接可读、稳定。

输出同样三组指标, 与基线并排对比:
  模板两两相似度 / top1-top2 区分度 / 扰动敏感性
"""

import sys
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parents[3] / "api_docs"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from ylyw_core.hexagram_rules import Hexagram, HexagramRuleBase
from ylyw_core.yao_encoder import YaoEncoder


# ============ 易经真实阴阳模板(64卦, 从下往上: 初->上) ============
# 1 表示阳爻, 0 表示阴爻。来源《周易》标准卦序, 与 hexagram_rules 枚举一一对应。
# 顺序: 初、二、三、四、五、上
YINYANG = {
    Hexagram.QIAN:   [1,1,1,1,1,1],   # 乾  ☰☰
    Hexagram.KUN:    [0,0,0,0,0,0],   # 坤  ☷☷
    Hexagram.ZHUN:   [1,0,0,0,1,0],   # 屯  ☵☳  (初九六二六三六四九五上六)
    Hexagram.MENG:   [0,1,0,0,0,1],   # 蒙  ☶☵
    Hexagram.XU:     [1,0,1,0,0,1],   # 需  ☵☰
    Hexagram.SONG:   [0,1,0,1,1,0],   # 讼  ☰☵
    Hexagram.SHI:    [0,1,0,0,0,0],   # 师  ☷☵
    Hexagram.BI:     [0,0,0,0,1,0],   # 比  ☵☷
    Hexagram.XIAOXU: [1,0,1,0,1,1],   # 小畜 ☴☰
    Hexagram.LU:     [0,1,0,1,1,0],   # 履  ☰☱
    Hexagram.TAI:    [1,0,1,0,1,0],   # 泰  ☷☰
    Hexagram.PI:     [0,1,0,1,0,1],   # 否  ☰☷
    Hexagram.TONGREN:[0,0,1,0,1,1],   # 同人 ☰☲
    Hexagram.DAYOU:  [1,0,1,1,0,1],   # 大有 ☲☰
    Hexagram.QIAN_GUA:[0,0,0,0,1,1],  # 谦  ☷☶
    Hexagram.YU:     [0,0,1,0,0,1],   # 豫  ☳☷
    Hexagram.SUI:    [0,0,1,0,1,0],   # 随  ☱☳
    Hexagram.GU:     [0,1,0,0,0,1],   # 蛊  ☶☴
    Hexagram.LIN:    [1,0,1,0,1,0],   # 临  ☷☱
    Hexagram.GUAN:   [0,0,0,0,1,1],   # 观  ☴☷
    Hexagram.SHIHE:  [0,0,1,1,0,1],   # 噬嗑 ☲☳
    Hexagram.BI_GUA: [0,1,0,1,0,1],   # 贲  ☶☲
    Hexagram.BO:     [0,0,0,0,0,1],   # 剥  ☶☷
    Hexagram.FU:     [1,0,0,0,0,0],   # 复  ☷☳
    Hexagram.WUWANG: [1,0,1,0,1,0],   # 无妄 ☰☳
    Hexagram.DACHU:  [0,1,0,1,0,1],   # 大畜 ☶☰
    Hexagram.YI:     [1,0,0,0,0,1],   # 颐  ☶☳
    Hexagram.DAGUO:  [0,1,1,1,1,0],   # 大过 ☱☴
    Hexagram.KAN_GUA:[1,0,0,0,1,0],   # 坎  ☵☵
    Hexagram.LI_GUA: [0,1,0,1,0,1],   # 离  ☲☲
    Hexagram.XIAN:   [0,0,0,1,0,1],   # 咸  ☱☶
    Hexagram.HENG:   [0,1,1,0,1,0],   # 恒  ☳☴
    Hexagram.DUN:    [1,1,0,1,0,0],   # 遁  ☰☶
    Hexagram.DAZHUANG:[1,1,0,1,1,0],  # 大壮 ☳☰
    Hexagram.JIN:    [0,1,1,0,1,0],   # 晋  ☲☷
    Hexagram.MINGYI: [0,1,0,0,1,0],   # 明夷 ☷☲
    Hexagram.JIAREN: [1,1,0,1,1,0],   # 家人 ☴☲
    Hexagram.KUI:    [0,1,0,1,1,0],   # 睽  ☲☱
    Hexagram.JIAN:   [1,0,0,0,0,0],   # 蹇  ☵☶
    Hexagram.XIE:    [1,1,0,0,1,0],   # 解  ☳☵
    Hexagram.SUN:    [0,1,0,0,1,0],   # 损  ☶☱
    Hexagram.YI_GUA: [0,0,0,1,1,0],   # 益  ☴☳
    Hexagram.GUAI:   [1,0,1,0,1,0],   # 夬  ☱☰
    Hexagram.GOU:    [0,1,1,1,1,1],   # 姤  ☰☴
    Hexagram.CUI:    [0,0,1,0,0,0],   # 萃  ☱☷
    Hexagram.SHENG:  [1,0,1,0,0,0],   # 升  ☷☴
    Hexagram.KUN_GUA:[0,0,1,0,0,1],   # 困  ☱☵
    Hexagram.JING:   [1,0,1,0,0,1],   # 井  ☵☴
    Hexagram.GE:     [0,1,1,0,1,0],   # 革  ☱☲
    Hexagram.DING:   [1,0,1,1,0,1],   # 鼎  ☲☴
    Hexagram.ZHEN_GUA:[1,0,1,0,1,0],  # 震  ☳☳
    Hexagram.GEN_GUA:[0,0,1,0,0,1],   # 艮  ☶☶
    Hexagram.JIAN_GUA:[0,0,1,1,1,1],  # 渐  ☴☶
    Hexagram.GUIMEI: [0,0,1,1,0,1],   # 归妹 ☳☱
    Hexagram.FENG:   [0,1,1,0,1,0],   # 丰  ☳☲
    Hexagram.LU_GUA: [0,0,0,0,1,1],   # 旅  ☲☶
    Hexagram.XUN_GUA:[0,1,1,0,1,0],   # 巽  ☴☴
    Hexagram.DUI_GUA:[0,0,1,1,0,1],   # 兑  ☱☱
    Hexagram.HUAN:   [0,1,0,1,1,0],   # 涣  ☴☵
    Hexagram.JIE:    [1,0,1,1,0,1],   # 节  ☵☱
    Hexagram.ZHONGFU:[1,1,0,1,1,0],   # 中孚 ☴☱
    Hexagram.XIAOGUO:[0,0,1,0,0,1],   # 小过 ☳☶
    Hexagram.JIJI:   [1,0,0,1,1,0],   # 既济 ☵☲
    Hexagram.WEIJI:  [0,1,1,0,0,1],   # 未济 ☲☵
}


def build_templates():
    base = HexagramRuleBase()
    names, vecs = [], []
    for h in Hexagram:
        t = base._get_ideal_yao_template(h)
        if t is not None:
            names.append(base.get_rule(h)["name"])
            vecs.append(np.asarray(t, dtype=float))
    return names, np.array(vecs, dtype=float)


def cos_sim_matrix(V):
    V = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-12)
    return V @ V.T


# ============ 方案 A 匹配器 ============
class WeightedYaoMatcher:
    """爻位加权 + 离散阴阳模板 的 L3 匹配器。

    将连续 yao_vector 二值化(>=0.5 阳->1), 用加权汉明距离匹配易经真实阴阳模板。
    权重: 中位(二/五爻)权重 2.0, 当位更强调, 边缘位 1.0。
    得分为负加权距离归一化到 [0,1]。
    """

    def __init__(self, weights=None):
        # 初、二、三、四、五、上 的爻位权重
        self.weights = np.array(weights if weights is not None
                                else [1.0, 2.0, 1.0, 1.0, 2.0, 1.0])
        self.templates = {}  # h -> binary(6,)
        for h in Hexagram:
            if h in YINYANG:
                self.templates[h] = np.asarray(YINYANG[h], dtype=float)

    def score(self, yao_vec):
        """对每个卦返回加权匹配得分 [0,1]。"""
        yao = np.asarray(yao_vec, dtype=float)
        b = (yao >= 0.5).astype(float)
        out = {}
        total_w = self.weights.sum()
        for h, t in self.templates.items():
            match = 1.0 - (np.abs(b - t) * self.weights).sum() / total_w
            out[h] = match
        return out

    def best(self, yao_vec, k=1):
        sc = self.score(yao_vec)
        ranked = sorted(sc.items(), key=lambda kv: -kv[1])
        if k == 1:
            return ranked[0]
        return ranked[:k]


def main():
    names, V = build_templates()
    n = V.shape[0]

    # ---- 基线: 现有模板相似度 ----
    S = cos_sim_matrix(V)
    off = S[~np.eye(n, dtype=bool)]

    # ---- 方案A: 离散阴阳模板相似度(加权) ----
    matcher = WeightedYaoMatcher()
    # 每个卦模板的"原型"就是它自身 -> 模板两两加权距离转相似度
    T = np.zeros((n, 6))
    for i, h in enumerate(Hexagram):
        if h in YINYANG:
            T[i] = np.asarray(YINYANG[h], dtype=float)
    total_w = matcher.weights.sum()
    SA = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            SA[i, j] = 1.0 - (np.abs(T[i] - T[j]) * matcher.weights).sum() / total_w
    offA = SA[~np.eye(n, dtype=bool)]

    print("=" * 64)
    print("L3 判别性对比: 基线(现状) vs 方案A(爻位加权+阴阳模板)")
    print("=" * 64)

    print(f"\n[1] 模板两两相似度 —— 越低越可分(理想应尽量低)")
    for tag, o in (("基线", off), ("方案A", offA)):
        print(f"  {tag}: 均值={o.mean():.3f} 中位={np.median(o):.3f} "
              f"p90={np.percentile(o,90):.3f} p95={np.percentile(o,95):.3f}")
    for tag, o in (("基线", off), ("方案A", offA)):
        f90 = float((o > 0.9).mean()) * 100
        f95 = float((o > 0.95).mean()) * 100
        print(f"  {tag}: 相似度>0.9 占 {f90:.1f}%  >0.95 占 {f95:.1f}%")

    # ---- 判别性: 对合成输入, top1-top2 分数差 ----
    enc = YaoEncoder()
    rng = np.random.default_rng(2026)
    base_feats = {
        "stability": 0.6, "roll_tendency": 0.3, "strength_needed": 0.4,
        "fragility": 0.3, "task_priority": 0.6, "reachability": 0.7,
        "support_area": 0.6, "occlusion": 0.2, "obstacle_density": 0.2,
        "grasp_surface_quality": 0.6, "weight_ratio": 0.3,
        "visibility": 0.8, "deformability": 0.2,
    }
    N = 400
    print(f"\n[2] 对{N}个合成输入的 top1-top2 分数差 —— 越大越好(区分度)")
    for tag, method in (("基线", "cos"), ("方案A", "weighted")):
        gaps = []
        for _ in range(N):
            feats = {k: float(np.clip(v + rng.normal(0, 0.08), 0.01, 0.99))
                     for k, v in base_feats.items()}
            yao = enc.encode(feats)
            if method == "cos":
                scores = []
                for h in Hexagram:
                    t = None
                    try:
                        t = HexagramRuleBase()._get_ideal_yao_template(h)
                    except Exception:
                        pass
                    if t is None:
                        continue
                    dot = np.dot(yao, t)
                    norm = np.linalg.norm(yao) * np.linalg.norm(t)
                    scores.append(dot / norm if norm > 0 else 0.0)
                scores = sorted(scores, reverse=True)
                gaps.append(scores[0] - scores[1])
            else:
                sc = matcher.score(yao)
                ranked = sorted(sc.values(), reverse=True)
                gaps.append(ranked[0] - ranked[1])
        gaps = np.array(gaps)
        low = float((gaps < 0.2).mean()) * 100
        print(f"  {tag}: 均值={gaps.mean():.4f} 中位={np.median(gaps):.4f} "
              f">0.2的占比(明显胜出)={(100-low):.1f}%")

    # ---- 扰动敏感性 ----
    print(f"\n[3] 扰动敏感性(±0.03 特征噪声) —— 跳变率越低越稳定")
    base_yao = enc.encode(base_feats)
    for tag, method in (("基线", "cos"), ("方案A", "weighted")):
        def best(feats):
            yao = enc.encode(feats)
            if method == "cos":
                b, _ = HexagramRuleBase().get_best_hexagram(yao)
                return b
            return matcher.best(yao, 1)[0]
        h0 = best(base_feats)
        swaps = 0
        trials = 300
        for _ in range(trials):
            jitter = {k: float(np.clip(v + rng.normal(0, 0.03), 0.01, 0.99))
                      for k, v in base_feats.items()}
            if best(jitter) != h0:
                swaps += 1
        print(f"  {tag}: 跳变 {swaps}/{trials} ({swaps/trials*100:.1f}%)")

    # ---- 输出方案A模板冲突检查 ----
    print(f"\n[4] 方案A 模板唯一性: 64卦阴阳模板是否两两不同")
    seen = {}
    dup = 0
    for h in Hexagram:
        if h in YINYANG:
            key = tuple(YINYANG[h])
            seen.setdefault(key, []).append(HexagramRuleBase().get_rule(h)["name"])
    for k, v in seen.items():
        if len(v) > 1:
            dup += 1
            print(f"    重复: {v}")
    print(f"  完全重复的卦组数: {dup} (方案A应避免 dupe)")


if __name__ == "__main__":
    main()
