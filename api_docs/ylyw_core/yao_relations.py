"""
爻位关系运算模块 (Yao Relations)

实现《易经》中六爻之间的结构关系运算：
    - 当位/不当位：阳爻居阳位（初三五），阴爻居阴位（二四上）
    - 得中：二爻和五爻为中位，象征"中道"
    - 乘：阴爻在上，压制下方阳爻（逆）
    - 承：阴爻在下，承载上方阳爻（顺）
    - 比：相邻两爻的关系（同性/异性）
    - 应：初-四、二-五、三-上的远程呼应

这些关系运算构成了易经的"结构语法"——
不仅是看单个爻值，更看爻之间的相互关系。

用法：
    >>> rel = YaoRelations()
    >>> analysis = rel.analyze(yao_vector)
    >>> print(analysis['summary'])  # 人类可读总结
    >>> print(analysis['scores'])   # 数值评分
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class YaoRelationReport:
    """爻位关系分析报告"""
    # 当位分析
    dangwei_count: int = 0           # 当位爻数（0-6）
    dangwei_details: List[str] = None  # 每个爻的当位情况
    
    # 得中分析
    dezhong: bool = False            # 二爻是否得中
    dezhong_wu: bool = False         # 五爻是否得中
    
    # 乘承关系
    cheng_count: int = 0             # 乘（阴乘阳）次数
    cheng_pairs: List[Tuple[int, int]] = None
    cheng_detail: List[str] = None
    
    # 比的关系
    bi_harmony: int = 0              # 相邻和谐对数
    bi_disharmony: int = 0           # 相邻不和谐对数
    bi_detail: List[str] = None
    
    # 应的关系
    ying_count: int = 0              # 有应对数（0-3）
    ying_detail: List[str] = None
    
    # 综合评分
    score_overall: float = 0.0       # 综合爻位质量评分 (0-1)
    score_dangwei: float = 0.0
    score_dezhong: float = 0.0
    score_cheng_cheng: float = 0.0   # 乘承得分（承为正，乘为负）
    score_bi: float = 0.0
    score_ying: float = 0.0
    
    # 策略修正建议
    strategy_modifier: float = 1.0   # 力预设修正系数 (>1加力, <1减力)
    caution_level: str = 'normal'    # 谨慎级别: relaxed/normal/cautious/very_cautious
    advice: List[str] = None         # 策略建议


class YaoRelations:
    """
    六爻关系运算器
    
    实现《周易》中的爻位关系规则，将阴阳爻之间的
    乘承比应当位得中转化为可计算的评分和策略建议。
    
    核心思想：
        卦象决定了"做什么"（策略类型），
        爻位关系决定了"怎么做"（参数微调）。
    """
    
    def __init__(self):
        # 阳位（奇数位，从下往上数）：初(1)、三(3)、五(5)
        # Python 0-index: 0, 2, 4
        self.yang_positions = {0, 2, 4}
        # 阴位（偶数位）：二(2)、四(4)、上(6)
        # Python 0-index: 1, 3, 5
        self.yin_positions = {1, 3, 5}
        
        # 中位：二爻(1)和五爻(4)
        self.zhong_positions = {1, 4}
        
        # 应位对应关系：初-四, 二-五, 三-上
        self.ying_pairs = [(0, 3), (1, 4), (2, 5)]
        self.ying_names = ['初-四', '二-五', '三-上']
        
        # 爻位名称
        self.position_names = ['初爻', '二爻', '三爻', '四爻', '五爻', '上爻']
    
    def analyze(self, yao_vector: np.ndarray) -> YaoRelationReport:
        """
        对六爻向量进行完整的关系分析
        
        Args:
            yao_vector: shape (6,), 每爻值 ∈ [0, 1]
        
        Returns:
            YaoRelationReport: 完整的爻位关系分析
        """
        report = YaoRelationReport()
        
        # 1. 当位分析
        report.dangwei_count, report.dangwei_details, report.score_dangwei = \
            self._analyze_dangwei(yao_vector)
        
        # 2. 得中分析
        report.dezhong, report.dezhong_wu, report.score_dezhong = \
            self._analyze_dezhong(yao_vector)
        
        # 3. 乘承分析
        report.cheng_count, report.cheng_pairs, report.cheng_detail, report.score_cheng_cheng = \
            self._analyze_cheng_cheng(yao_vector)
        
        # 4. 比的分析
        report.bi_harmony, report.bi_disharmony, report.bi_detail, report.score_bi = \
            self._analyze_bi(yao_vector)
        
        # 5. 应的分析
        report.ying_count, report.ying_detail, report.score_ying = \
            self._analyze_ying(yao_vector)
        
        # 6. 综合评分
        report.score_overall = self._compute_overall_score(report)
        
        # 7. 策略修正建议
        report.strategy_modifier, report.caution_level, report.advice = \
            self._derive_strategy_advice(report)
        
        return report
    
    def _analyze_dangwei(self, yao: np.ndarray) -> Tuple[int, List[str], float]:
        """
        当位分析
        
        阳爻（≥0.5）应居阳位（初、三、五）
        阴爻（<0.5）应居阴位（二、四、上）
        """
        details = []
        count = 0
        
        for i in range(6):
            is_yang = yao[i] >= 0.5
            should_be_yang = i in self.yang_positions
            
            if is_yang == should_be_yang:
                count += 1
                yin_yang = "阳" if is_yang else "阴"
                pos_type = "阳位" if should_be_yang else "阴位"
                details.append(f"{self.position_names[i]}{yin_yang}居{pos_type} ✓ 当位")
            else:
                yin_yang = "阳" if is_yang else "阴"
                pos_type = "阳位" if should_be_yang else "阴位"
                details.append(f"{self.position_names[i]}{yin_yang}居{pos_type} ✗ 不当位")
        
        score = count / 6.0
        return count, details, score
    
    def _analyze_dezhong(self, yao: np.ndarray) -> Tuple[bool, bool, float]:
        """
        得中分析
        
        二爻和五爻为"中位"，得中则吉。
        六二（阴爻居二位）和九五（阳爻居五位）为最佳。
        """
        er_yao = yao[1]   # 二爻
        wu_yao = yao[4]   # 五爻
        
        dezhong_er = er_yao >= 0.5  # 二爻偏阳
        dezhong_wu = wu_yao >= 0.5  # 五爻偏阳
        
        # 得中不一定要求阴阳必须对应——只要中位爻值合理即可
        # 但六二（阴居二）和九五（阳居五）加分
        er_ideal = (not dezhong_er)  # 六二为阴爻
        wu_ideal = dezhong_wu       # 九五为阳爻
        
        score = 0.0
        if er_ideal:
            score += 0.5  # 六二得中
        elif dezhong_er:
            score += 0.25  # 九二（阳居二，次优）
        
        if wu_ideal:
            score += 0.5  # 九五得中
        elif not dezhong_wu:
            score += 0.25  # 六五（阴居五，次优）
        
        return dezhong_er, dezhong_wu, score
    
    def _analyze_cheng_cheng(self, yao: np.ndarray) -> Tuple[int, List, List[str], float]:
        """
        乘承分析
        
        乘：阴爻在上压制阳爻（下阳上阴）→ 不利
        承：阴爻在下承载阳爻（下阴上阳）→ 有利
        
        从下往上（i=0到5），检查相邻爻对(i, i+1)
        """
        pairs = []
        details = []
        cheng_count = 0  # 乘（不利）
        cheng_count_good = 0  # 承（有利）
        
        for i in range(5):
            lower = yao[i]     # 下爻
            upper = yao[i+1]  # 上爻
            lower_yang = lower >= 0.5
            upper_yang = upper >= 0.5
            
            if (not upper_yang) and lower_yang:
                # 上阴下阳 → 乘（阴乘阳）
                cheng_count += 1
                pairs.append((i, i+1))
                severity = abs(upper - lower)
                if severity > 0.5:
                    details.append(f"{self.position_names[i+1]}阴乘{self.position_names[i]}阳 ⚠️ 严重")
                else:
                    details.append(f"{self.position_names[i+1]}阴乘{self.position_names[i]}阳 ⚠")
            elif (not lower_yang) and upper_yang:
                # 下阴上阳 → 承（阴承阳）
                cheng_count_good += 1
                details.append(f"{self.position_names[i]}阴承{self.position_names[i+1]}阳 ✓ 顺承")
            elif lower_yang and upper_yang:
                details.append(f"{self.position_names[i]}阳-{self.position_names[i+1]}阳 — 两阳对峙")
            else:
                details.append(f"{self.position_names[i]}阴-{self.position_names[i+1]}阴 — 两阴沉寂")
        
        # 乘减少分，承增加分
        score = max(0.0, 1.0 - cheng_count * 0.3 + cheng_count_good * 0.15)
        score = min(1.0, score)
        
        return cheng_count, pairs, details, score
    
    def _analyze_bi(self, yao: np.ndarray) -> Tuple[int, int, List[str], float]:
        """
        比的分析
        
        相邻两爻的关系：
        - 同阴阳（阳-阳 或 阴-阴）→ 和谐（同类相从）
        - 异阴阳（阳-阴 或 阴-阳）→ 有张力
        """
        details = []
        harmony = 0
        disharmony = 0
        
        for i in range(5):
            lower_yang = yao[i] >= 0.5
            upper_yang = yao[i+1] >= 0.5
            
            if lower_yang == upper_yang:
                harmony += 1
                y_type = "阳" if lower_yang else "阴"
                details.append(f"{self.position_names[i]}-{self.position_names[i+1]}{y_type}{y_type} 亲比")
            else:
                disharmony += 1
                details.append(f"{self.position_names[i]}-{self.position_names[i+1]}阴阳 有间")
        
        score = harmony / 5.0  # 5对相邻关系
        return harmony, disharmony, details, score
    
    def _analyze_ying(self, yao: np.ndarray) -> Tuple[int, List[str], float]:
        """
        应的分析
        
        初-四、二-五、三-上为应位。
        两爻阴阳相反 → 有应（互相呼应）
        两爻阴阳相同 → 无应
        """
        details = []
        count = 0
        
        for idx, (lower_i, upper_i) in enumerate(self.ying_pairs):
            lower_yang = yao[lower_i] >= 0.5
            upper_yang = yao[upper_i] >= 0.5
            
            if lower_yang != upper_yang:
                count += 1
                details.append(f"{self.ying_names[idx]} 阴阳相应 ✓")
            else:
                y_type = "阳" if lower_yang else "阴"
                details.append(f"{self.ying_names[idx]} 同为{y_type} 无应")
        
        score = count / 3.0
        return count, details, score
    
    def _compute_overall_score(self, report: YaoRelationReport) -> float:
        """综合爻位质量评分"""
        # 权重分配：当位40%，得中20%，乘承15%，比10%，应15%
        weights = {
            'dangwei': 0.40,
            'dezhong': 0.20,
            'cheng_cheng': 0.15,
            'bi': 0.10,
            'ying': 0.15,
        }
        
        overall = (
            weights['dangwei'] * report.score_dangwei +
            weights['dezhong'] * report.score_dezhong +
            weights['cheng_cheng'] * report.score_cheng_cheng +
            weights['bi'] * report.score_bi +
            weights['ying'] * report.score_ying
        )
        
        return round(overall, 4)
    
    def _derive_strategy_advice(self, report: YaoRelationReport) -> Tuple[float, str, List[str]]:
        """
        根据爻位关系推导策略修正建议
        
        Returns:
            strategy_modifier: 力预设修正系数
            caution_level: 谨慎级别
            advice: 策略建议列表
        """
        advice = []
        modifier = 1.0
        
        # 当位分析 → 影响策略稳定性
        if report.score_dangwei >= 0.83:  # 5/6以上当位
            modifier += 0.05
            advice.append("爻多当位，策略稳固，可按预设力执行")
        elif report.score_dangwei <= 0.33:  # 2/6以下当位
            modifier -= 0.10
            advice.append("多爻不当位，状态不稳，建议降低力预设")
        
        # 得中分析 → 影响决策优先级
        if report.score_dezhong >= 0.75:
            advice.append("二五得中，决策优先级高")
        elif report.score_dezhong == 0.0:
            advice.append("中位失据，需额外谨慎")
            modifier -= 0.05
        
        # 乘承分析 → 影响力方向
        if report.cheng_count >= 2:
            modifier -= 0.10
            advice.append(f"出现{report.cheng_count}处阴乘阳，力阻力增大，降低期望力")
        elif report.cheng_count == 0 and report.score_cheng_cheng > 0.8:
            modifier += 0.05
            advice.append("无乘多承，阴阳顺承，策略流畅")
        
        # 比的分析 → 影响动作连贯性
        if report.bi_disharmony >= 3:
            advice.append("多爻不相亲比，动作需分段执行")
        
        # 应的分析 → 影响策略确信度
        if report.ying_count == 0:
            modifier -= 0.05
            advice.append("上下无应，缺乏呼应，降低策略确信度")
        elif report.ying_count == 3:
            modifier += 0.05
            advice.append("三对应俱全，上下呼应良好")
        
        # 确定谨慎级别
        if report.score_overall >= 0.70:
            caution = 'relaxed'
        elif report.score_overall >= 0.50:
            caution = 'normal'
        elif report.score_overall >= 0.30:
            caution = 'cautious'
        else:
            caution = 'very_cautious'
        
        return round(modifier, 2), caution, advice
    
    def format_report(self, yao_vector: np.ndarray, report: YaoRelationReport = None) -> str:
        """
        将爻位关系分析格式化为可读文本
        
        Args:
            yao_vector: 六爻向量
            report: 分析报告（如果None则自动分析）
        """
        if report is None:
            report = self.analyze(yao_vector)
        
        lines = []
        lines.append("▎爻位关系分析")
        lines.append("-" * 50)
        
        # 当位
        lines.append(f"\n【当位】 {report.dangwei_count}/6 爻当位 (得分: {report.score_dangwei:.2f})")
        for d in report.dangwei_details:
            lines.append(f"  {d}")
        
        # 得中
        er_yao = "阳" if yao_vector[1] >= 0.5 else "阴"
        wu_yao = "阳" if yao_vector[4] >= 0.5 else "阴"
        lines.append(f"\n【得中】 二爻{er_yao} 五爻{wu_yao} (得分: {report.score_dezhong:.2f})")
        
        # 乘承
        lines.append(f"\n【乘承】 乘(逆):{report.cheng_count}处 (得分: {report.score_cheng_cheng:.2f})")
        for d in report.cheng_detail:
            lines.append(f"  {d}")
        
        # 比
        lines.append(f"\n【亲比】 和谐:{report.bi_harmony}/5 不睦:{report.bi_disharmony}/5 (得分: {report.score_bi:.2f})")
        for d in report.bi_detail:
            lines.append(f"  {d}")
        
        # 应
        lines.append(f"\n【呼应】 有应:{report.ying_count}/3 (得分: {report.score_ying:.2f})")
        for d in report.ying_detail:
            lines.append(f"  {d}")
        
        # 综合
        lines.append(f"\n{'='*50}")
        lines.append(f"【综合爻位质量】 {report.score_overall:.2f}")
        lines.append(f"【谨慎级别】 {report.caution_level}")
        lines.append(f"【力修正系数】 {report.strategy_modifier:.2f}")
        if report.advice:
            lines.append(f"【策略建议】")
            for a in report.advice:
                lines.append(f"  • {a}")
        
        return "\n".join(lines)


# ========================
#  便捷函数
# ========================

def analyze_yao_relations(yao_vector: np.ndarray) -> YaoRelationReport:
    """快捷分析函数"""
    rel = YaoRelations()
    return rel.analyze(yao_vector)
