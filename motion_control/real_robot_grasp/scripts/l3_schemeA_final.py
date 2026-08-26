"""方案 A 最终版：权威八卦推导 64 卦阴阳模板 + 两级匹配。

权威推导(标准《周易》八卦, 从下往上, 阳=1阴=0):
  乾☰=[1,1,1] 兑☱=[1,1,0] 离☲=[1,0,1] 震☳=[1,0,0]
  巽☴=[0,1,1] 坎☵=[0,1,0] 艮☶=[0,0,1] 坤☷=[0,0,0]

64卦 = 上卦(外) + 下卦(内)。六爻(从下往上 初->上)
     = 下卦3爻 ++ 上卦3爻

模板取自仓库 hexagram_rules 的 upper_lower 符号字段(权威), 
据此推导六爻阴阳, 彻底避免手写错误。

匹配: 
  阶段一(粗): 阴阳模板加权汉明, 保证可分、稳定
  阶段二(细): 用原始连续爻值在 top 候选内二次排序, 解决离散 tie

对比指标与基线同构: 模板可分性 / top1-top2 区分度 / 扰动敏感性。
"""

import sys
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parents[3] / "api_docs"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from ylyw_core.hexagram_rules import Hexagram, HexagramRuleBase
from ylyw_core.yao_encoder import YaoEncoder

# 八卦符号 -> 三爻阴阳(从下往上)
SYM = {
    "☰": [1, 1, 1], "☷": [0, 0, 0], "☳": [1, 0, 0], "☶": [0, 0, 1],
    "☵": [0, 1, 0], "☲": [1, 0, 1], "☱": [1, 1, 0], "☴": [0, 1, 1],
}


def derive_templates(base):
    """从 upper_lower 符号权威推导 64 卦六爻阴阳模板。"""
    templates = {}
    for h, rule in base.rules.items():
        up_sym, low_sym = rule["upper_lower"]
        if up_sym not in SYM or low_sym not in SYM:
            continue
        # 六爻从下往上: 下卦3爻 + 上卦3爻
        liu = SYM[low_sym] + SYM[up_sym]
        templates[h] = np.asarray(liu, dtype=float)
    return templates


def main():
    base = HexagramRuleBase()
    names, V = build_templates(base)
    n = V.shape[0]

    # 权威阴阳模板
    templates = derive_templates(base)
    print(f"推导出的卦模板数: {len(templates)} / {n}")

    # 检查唯一性 + 爻位权重
    weights = np.array([1.0, 2.0, 1.0, 1.0, 2.0, 1.0])
    seen = {}
    dup = 0
    for h, t in templates.items():
        seen.setdefault(tuple(t), []).append(base.get_rule(h)["name"])
    for k, v in seen.items():
        if len(v) > 1:
            dup += 1
            print(f"  重复模板: {v}")
    print(f"重复模板组数: {dup}")

    # 模板两两加权相似度
    total_w = weights.sum()
    n2 = len(templates)
    hs = list(templates.keys())
    S_bin = np.zeros((n2, n2))
    for i in range(n2):
        for j in range(n2):
            S_bin[i, j] = 1.0 - (np.abs(templates[hs[i]] - templates[hs[j]]) * weights).sum() / total_w
    off_bin = S_bin[~np.eye(n2, dtype=bool)]

    # 基线
    S = cos_sim_matrix(V)
    off_base = S[~np.eye(n, dtype=bool)]

    print("\n" + "=" * 66)
    print("方案A 最终版(权威阴阳模板+加权) vs 基线(现状余弦) —— 判别性对比")
    print("=" * 66)
    print(f"\n[1] 模板两两相似度 —— 越低越可分")
    for tag, o in (("基线(余弦浮点模板)", off_base), ("方案A(权威阴阳模板+加权)", off_bin)):
        print(f"  {tag}: 均值={o.mean():.3f} 中位={np.median(o):.3f} "
              f"p90={np.percentile(o,90):.3f} p95={np.percentile(o,95):.3f}")
        print(f"       >0.9占{float((o>0.9).mean())*100:.1f}%  >0.95占{float((o>0.95).mean())*100:.1f}%")

    # 匹配器
    class Matcher:
        def score_rank(self, yao):
            b = (yao >= 0.5).astype(float)
            sc = {}
            for h, t in templates.items():
                sc[h] = 1.0 - (np.abs(b - t) * weights).sum() / total_w
            # 阶段一 top3
            top = sorted(sc.items(), key=lambda kv: -kv[1])[:3]
            # 阶段二: 用连续爻值在 top 内精细排序(解决 tie)
            best = min(top, key=lambda kv: float((np.abs(yao - templates[kv[0]]) * weights).sum()))
            ranked = sorted(sc.items(), key=lambda kv: - (kv[1] + 1e-9 * (1 - (np.abs(yao - templates[kv[0]])*weights).sum()/ (2*total_w))))
            return ranked, best[0]

    matcher = Matcher()
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
    print(f"\n[2] 对{N}个合成输入 top1-top2 分数差 —— 越大越好")
    for tag, mode in (("基线(余弦)", "cos"), ("方案A(两级)", "bin")):
        gaps = []
        for _ in range(N):
            feats = {k: float(np.clip(v + rng.normal(0, 0.08), 0.01, 0.99))
                     for k, v in base_feats.items()}
            yao = enc.encode(feats)
            if mode == "cos":
                sc = []
                for h in Hexagram:
                    t = base._get_ideal_yao_template(h)
                    if t is None:
                        continue
                    d = np.dot(yao, t); nm = np.linalg.norm(yao)*np.linalg.norm(t)
                    sc.append(d/nm if nm > 0 else 0.0)
                sc = sorted(sc, reverse=True)
                gaps.append(sc[0]-sc[1])
            else:
                ranked, _ = matcher.score_rank(yao)
                gaps.append(ranked[0][1]-ranked[1][1])
        gaps = np.array(gaps)
        frac = float((gaps > 0.05).mean())*100
        print(f"  {tag}: 均值={gaps.mean():.4f} 中位={np.median(gaps):.4f} "
              f">0.05明显胜出占{frac:.1f}%")

    print(f"\n[3] 扰动敏感性(±0.03) —— 跳变率越低越稳定")
    for tag, mode in (("基线(余弦)", "cos"), ("方案A(两级)", "bin")):
        def best(feats):
            yao = enc.encode(feats)
            if mode == "cos":
                b, _ = base.get_best_hexagram(yao); return b
            _, b = matcher.score_rank(yao); return b
        h0 = best(base_feats)
        trials = 300; swaps = 0
        for _ in range(trials):
            jit = {k: float(np.clip(v+rng.normal(0,0.03),0.01,0.99)) for k,v in base_feats.items()}
            if best(jit) != h0:
                swaps += 1
        print(f"  {tag}: 跳变 {swaps}/{trials} ({swaps/trials*100:.1f}%)")


def build_templates(base):
    names, vecs = [], []
    for h in Hexagram:
        t = base._get_ideal_yao_template(h)
        if t is not None:
            names.append(base.get_rule(h)["name"])
            vecs.append(np.asarray(t, dtype=float))
    return names, np.array(vecs, dtype=float)


def cos_sim_matrix(V):
    V = V / (np.linalg.norm(V, axis=1, keepdims=True)+1e-12)
    return V @ V.T


if __name__ == "__main__":
    main()
