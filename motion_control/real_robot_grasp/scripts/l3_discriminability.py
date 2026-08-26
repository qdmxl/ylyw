"""L3 卦象判别性分析 —— 检验 64 卦理想爻模板是否彼此可分。

核心问题：
  hexagram_rules.get_best_hexagram() 用余弦相似度选"最佳卦象"。
  如果 64 个模板向量彼此高度相似(余弦≈1)，那么：
    - 对任意输入六爻向量，匹配分差异极小(噪声级)
    - "最佳卦"近似随机/对微小扰动敏感 → 决策不稳定
    - 论文'观象取卦'的解释力弱

本脚本量化输出：
  1. 64×64 模板两两余弦相似度矩阵
  2. 相似度分布统计(均值/分位数/>0.85/>0.9/>0.95占比)
  3. 对一批合成六爻向量，检验 top1/top2/top3 分数差(区分度)
  4. 扰动敏感性：对同一特征微扰，卦象是否跳变
  5. 保存热力图 PNG
"""

import sys
from pathlib import Path

import numpy as np

# 让 ylyw_core 可导入: 脚本位于 .../ylyw/motion_control/real_robot_grasp/scripts/
# 上溯 3 级到 ylyw/，再进 api_docs/
CORE = Path(__file__).resolve().parents[3] / "api_docs"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from ylyw_core.hexagram_rules import Hexagram, HexagramRuleBase
from ylyw_core.yao_encoder import YaoEncoder
from ylyw_core.prior_manual import PriorManual


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


def main():
    names, V = build_templates()
    n = V.shape[0]
    S = cos_sim_matrix(V)

    # 去掉自相似(对角)
    off = S[~np.eye(n, dtype=bool)]
    print(f"== 模板统计 ==")
    print(f"  卦数: {n}")
    print(f"  模板向量的均值范数: {np.linalg.norm(V, axis=1).mean():.3f}")
    print(f"  两两余弦相似度: 均值={off.mean():.3f} 中位={np.median(off):.3f} "
          f"p75={np.percentile(off,75):.3f} p90={np.percentile(off,90):.3f} p95={np.percentile(off,95):.3f}")
    for thr in (0.80, 0.85, 0.90, 0.95, 0.98):
        frac = float((off > thr).mean())
        print(f"    相似度>{thr}: {frac*100:.1f}%  ({int((off>thr).sum())} 对)")

    # 每个卦 vs 其它卦的"最近邻相似度"——衡量最接近它的竞争卦有多近
    np.fill_diagonal(S, -1)
    nearest = S.max(axis=1)
    print(f"\n== 最近邻竞争 ==")
    print(f"  每个卦与'最相似的另一卦'的余弦: 均值={nearest.mean():.3f} "
          f"最大={nearest.max():.3f} 最小={nearest.min():.3f}")
    worst = np.argsort(nearest)[-8:][::-1]
    print("  与最近邻最接近的8个卦(最易混淆):")
    for i in worst:
        j = int(np.argmax(S[i]))
        print(f"    {names[i]} ↔ {names[j]}: {nearest[i]:.3f}")
    np.fill_diagonal(S, 0)

    # 生成一批合成六爻向量，看 top1-top2 分数差(区分度)
    rng = np.random.default_rng(2026)
    enc = YaoEncoder()
    manual = PriorManual(verbose=False)
    # 用一个真实特征模板生成多样输入
    base_feats = {
        "stability": 0.6, "roll_tendency": 0.3, "strength_needed": 0.4,
        "fragility": 0.3, "task_priority": 0.6, "reachability": 0.7,
        "support_area": 0.6, "occlusion": 0.2, "obstacle_density": 0.2,
        "grasp_surface_quality": 0.6, "weight_ratio": 0.3,
        "visibility": 0.8, "deformability": 0.2,
    }
    N = 400
    gaps12, gaps23 = [], []
    top_swaps = 0
    for _ in range(N):
        feats = {k: float(np.clip(v + rng.normal(0, 0.08), 0.01, 0.99))
                 for k, v in base_feats.items()}
        yao = enc.encode(feats)
        # 直接调用真实(改后)匹配器, 报告当前实现的实际区分度
        top = manual.hexagram_rules.get_top_k_hexagrams(yao, 3)
        if len(top) >= 2:
            gaps12.append(top[0][1] - top[1][1])
        if len(top) >= 3:
            gaps23.append(top[1][1] - top[2][1])
        if len(top) >= 2 and top[0][1] - top[1][1] < 0.005:
            top_swaps += 1

    gaps12 = np.array(gaps12); gaps23 = np.array(gaps23)
    print(f"\n== 对{N}个合成输入的卦象区分度 ==")
    print(f"  top1-top2 分数差: 均值={gaps12.mean():.4f} 中位={np.median(gaps12):.4f} "
          f"p25={np.percentile(gaps12,25):.4f}")
    print(f"  top2-top3 分数差: 均值={gaps23.mean():.4f} 中位={np.median(gaps23):.4f}")
    for thr in (0.005, 0.01, 0.02, 0.05):
        print(f"    top1-top2<{thr}: {float((gaps12<thr).mean())*100:.1f}% 的输入，最佳卦是'噪声级'胜出")
    print(f"  top1-top2<0.005(近似平手)的输入占比: {float((gaps12<0.005).mean())*100:.1f}%")

    # 扰动敏感性：固定特征场景，看 top1 是否随微小扰动跳变
    base_yao = enc.encode(base_feats)
    def best_hex(feats):
        yao = enc.encode(feats)
        best, _ = manual.hexagram_rules.get_best_hexagram(yao)
        return best
    h0 = best_hex(base_feats)
    swaps = 0
    trials = 300
    for _ in range(trials):
        jitter = {k: float(np.clip(v + rng.normal(0, 0.03), 0.01, 0.99))
                  for k, v in base_feats.items()}
        if best_hex(jitter) != h0:
            swaps += 1
    print(f"\n== 扰动敏感性(±0.03 特征噪声, {trials}次) ==")
    print(f"  最佳卦象跳变次数: {swaps}  ({swaps/trials*100:.1f}%)")

    # 保存热力图
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    # 指定中文字体，避免标签乱码
    for fp in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
               "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
        try:
            font_manager.fontManager.addfont(fp)
        except Exception:
            pass
    plt.rcParams["font.family"] = "Noto Sans CJK SC"
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(cos_sim_matrix(V), cmap="viridis", vmin=0.5, vmax=1.0)
    ax.set_xticks(range(n)); ax.set_xticklabels(names, rotation=90, fontsize=4)
    ax.set_yticks(range(n)); ax.set_yticklabels(names, fontsize=4)
    ax.set_title("64卦理想爻模板 两两余弦相似度 (L3 判别性)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("cosine similarity")
    fig.tight_layout()
    out = Path(__file__).resolve().parent / "l3_similarity_heatmap.png"
    fig.savefig(out, dpi=150)
    print(f"\n热力图已保存: {out}")


if __name__ == "__main__":
    main()
