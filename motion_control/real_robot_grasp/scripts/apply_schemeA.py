#!/usr/bin/env python3
"""应用方案A到 hexagram_rules.py：替换 get_best_hexagram / get_top_k_hexagrams /
_get_ideal_yao_template 三个方法为"权威阴阳模板 + 爻位加权 + 两级匹配"。

用法: python apply_schemeA.py <target_file>
只替换从 "    def get_best_hexagram" 到 "        return templates.get(hexagram, None)\n"
(旧的 _get_ideal_yao_template 末尾) 的这一整段。
"""
import sys

NEW_BLOCK = '''    def get_best_hexagram(self, yao_vector):
        """
        根据六爻向量匹配最佳卦象

        方案A（爻位加权 + 权威阴阳模板 + 两级匹配）：
          阶段一：将六爻向量二值化(>=0.5 为阳)，与 64 卦权威阴阳模板
                  做加权汉明匹配，取候选（保证稳定、可分）。
          阶段二：在候选中用原始连续爻值做加权距离精细排序，
                  打破离散阶段可能出现的并列（tie），返回唯一最佳卦。

        相比旧版纯余弦匹配（模板挤在窄带、top1 与 top2 分数差仅 ~0.001、
        近半数输入随微扰跳变），本方案模板可分性、区分度、稳定性均有
        数量级提升（基准实验见 scripts/l3_*）。

        Args:
            yao_vector: np.ndarray, 形状(6,)

        Returns:
            (Hexagram, float): 最佳卦象及其匹配分数
        """
        yao = np.asarray(yao_vector, dtype=float).reshape(-1)
        if yao.size != 6:
            raise ValueError(f"六爻向量长度必须为 6，实际 {yao.size}")
        ranked = self._rank_hexagrams(yao)
        if not ranked:
            return None, 0.0
        best, score = ranked[0]
        return best, float(score)

    def get_top_k_hexagrams(self, yao_vector, k=3):
        """
        获取匹配度最高的 k 个卦象

        用于"变卦"分析——不仅看最匹配的卦，也看次匹配的卦。

        采用方案A两级匹配（见 get_best_hexagram 说明）：
          阶段一加权汉明粗选 → 阶段二连续值细化排序。

        Returns:
            list of (Hexagram, float): 按匹配度降序排列
        """
        yao = np.asarray(yao_vector, dtype=float).reshape(-1)
        if yao.size != 6:
            raise ValueError(f"六爻向量长度必须为 6，实际 {yao.size}")
        ranked = self._rank_hexagrams(yao)
        return ranked[:k]

    def _get_ideal_yao_template(self, hexagram):
        """
        获取一个卦的理想六爻模板（方案A：权威阴阳模板）。

        返回 64 卦的权威六爻阴阳模板（阳=1.0，阴=0.0）。

        推导方式：64 卦 = 上卦(外卦) + 下卦(内卦)，每个卦的上下卦由
        本规则库 upper_lower 字段给出。六爻从下往上(初->上)
        = 下卦三爻 ++ 上卦三爻。八卦三爻阴阳是《周易》确定的：

          乾☰=[1,1,1] 兑☱=[1,1,0] 离☲=[1,0,1] 震☳=[1,0,0]
          巽☴=[0,1,1] 坎☵=[0,1,0] 艮☶=[0,0,1] 坤☷=[0,0,0]

        如此生成的模板彼此可分性强、零重复，且严格符合《周易》卦象，
        完全可复现（论文方法论站得住）。

        返回: np.ndarray(6,) 或 None（未定义规则的卦）
        """
        rule = self.rules.get(hexagram)
        if rule is None:
            return None
        up_sym, low_sym = rule["upper_lower"]
        t = self._derive_six_yao(up_sym, low_sym)
        if t is None:
            return None
        return np.asarray(t, dtype=float)

    # ---- 方案A 辅助：八卦符号→六爻阴阳 推导 ----
    _TRIGRAM_YINYANG = {
        # 上/下卦符号(U+2630..U+2637) -> 该卦三爻阴阳(从下往上, 阳=1阴=0)
        # 与 self.rules[hexagram]['upper_lower'] 的实际符号码点严格一致
        "\u2630": (1.0, 1.0, 1.0),  # 乾 ☰
        "\u2631": (1.0, 1.0, 0.0),  # 兑 ☱
        "\u2632": (1.0, 0.0, 1.0),  # 离 ☲
        "\u2633": (1.0, 0.0, 0.0),  # 震 ☳
        "\u2634": (0.0, 1.0, 1.0),  # 巽 ☴
        "\u2635": (0.0, 1.0, 0.0),  # 坎 ☵
        "\u2636": (0.0, 0.0, 1.0),  # 艮 ☶
        "\u2637": (0.0, 0.0, 0.0),  # 坤 ☷
    }

    # 爻位权重：得中的二爻、五爻权重更高(呼应L3+得中思想)
    _YAO_WEIGHTS = (1.0, 2.0, 1.0, 1.0, 2.0, 1.0)

    def _derive_six_yao(self, up_sym, low_sym):
        """由上下卦符号推导六爻阴阳(从下往上)。"""
        up = self._TRIGRAM_YINYANG.get(up_sym)
        low = self._TRIGRAM_YINYANG.get(low_sym)
        if up is None or low is None:
            return None
        # 六爻从下往上 = 下卦三爻 + 上卦三爻
        return list(low) + list(up)

    def _rank_hexagrams(self, yao_vector):
        """方案A两级匹配，返回按得分降序的 [(Hexagram, score), ...]。

        阶段一：二值化 + 权威阴阳模板加权汉明，粗选稳定候选。
        阶段二：在候选内用原始连续爻值加权距离细化排序，打破离散并列。
        """
        weights = np.asarray(self._YAO_WEIGHTS, dtype=float)
        total_w = weights.sum()
        b = (np.asarray(yao_vector, dtype=float) >= 0.5).astype(float)

        scores = []
        for hexagram in self.rules:
            t = self._get_ideal_yao_template(hexagram)
            if t is None:
                continue
            hamming = 1.0 - (np.abs(b - t) * weights).sum() / total_w
            cont_dist = (np.abs(np.asarray(yao_vector, dtype=float) - t)
                         * weights).sum()
            scores.append((hexagram, float(hamming), float(cont_dist)))

        if not scores:
            return []

        max_dist = float(2.0 * total_w)  # |yao-t| 每维最大1
        refined = []
        for hexagram, hamming, cont_dist in scores:
            cont_norm = 1.0 - (cont_dist / max_dist)
            # 汉明占主导(0.9)，连续值微调(0.1)打破并列
            final = 0.9 * hamming + 0.1 * cont_norm
            refined.append((hexagram, final, hamming, cont_dist))

        refined.sort(key=lambda x: (-x[1], -x[2]))
        return [(h, s) for h, s, _h, _c in refined]

'''

START = "    def get_best_hexagram(self, yao_vector):\n"
END = "        return templates.get(hexagram, None)\n"


def apply_to(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    i = src.find(START)
    if i == -1:
        print(f"[SKIP] {path}: 未找到起始标记")
        return False
    j = src.find(END, i)
    if j == -1:
        print(f"[SKIP] {path}: 未找到结束标记")
        return False
    j += len(END)
    new_src = src[:i] + NEW_BLOCK + src[j:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_src)
    print(f"[OK] {path}: 已替换 {j-i} 字符 → {len(NEW_BLOCK)} 字符")
    return True


if __name__ == "__main__":
    target = sys.argv[1]
    ok = apply_to(target)
    if not ok:
        sys.exit(1)
