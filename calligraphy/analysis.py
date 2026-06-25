"""
YLYW 书法学习 — 实验分析报告生成

分析批量实验结果，生成可解释的学习报告。
包括：
- 每个字的学习曲线
- 爻位收敛分析
- 卦象迁移图
- 知几诊断的语义解释
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import json
import numpy as np
from collections import defaultdict


def analyze_experiment(json_path: str):
    """分析实验JSON结果"""
    with open(json_path) as f:
        data = json.load(f)

    report_lines = []
    report_lines.append("# YLYW 知几书法学习 — 实验分析")
    report_lines.append("")
    report_lines.append(f"实验时间: {data.get('experiment_time', 'N/A')}")
    report_lines.append(f"汉字数量: {len(data.get('characters', []))}")
    report_lines.append(f"每字迭代: {data.get('max_iterations', 'N/A')}")
    report_lines.append("")

    # 总体统计
    summary = data.get('summary', {})
    report_lines.append("## 总体统计")
    report_lines.append("")
    report_lines.append(f"- 总迭代次数: {summary.get('total_iterations', 0)}")
    report_lines.append(f"- 平均初始距离: {summary.get('avg_initial_distance', 0):.3f}")
    report_lines.append(f"- 平均最终距离: {summary.get('avg_final_distance', 0):.3f}")
    report_lines.append(f"- 平均改善率: {summary.get('avg_improvement_pct', 0):.1f}%")
    report_lines.append(f"- 评级分布: {summary.get('grade_distribution', {})}")
    report_lines.append(f"- 收敛率: {summary.get('convergence_rate', 0):.1f}%")
    report_lines.append("")

    # 各字详情
    yao_names = ['初爻(方向)', '二爻(粗细)', '三爻(曲直)', '四爻(规整)', '五爻(重心x)', '上爻(重心y)']

    for char, char_data in data.get('results', {}).items():
        iterations = char_data.get('iterations', [])
        if not iterations:
            continue

        report_lines.append(f"## 「{char}」")
        report_lines.append(f"- 目标卦象: {char_data.get('target_trigram', '?')} "
                          f"({char_data.get('target_hexagram', '?')})")
        report_lines.append("")

        # 迭代表
        report_lines.append("| 迭代 | 评级 | 距离 | 改善 | 主导卦 | 最大偏差爻 | 修正数 |")
        report_lines.append("|------|------|------|------|--------|-----------|--------|")

        for it in iterations:
            imp = it.get('improvement')
            imp_str = f"{imp:+.3f}" if imp is not None else "-"
            report_lines.append(
                f"| {it['iteration']+1} | {it['grade']} | "
                f"{it['distance']:.3f} | {imp_str} | "
                f"{it['target_trigram']} | "
                f"{it['max_diff_yao']}({it['max_diff_val']:+.3f}) | "
                f"- |"
            )
        report_lines.append("")

        # 爻位收敛分析
        if len(iterations) >= 2:
            first_diffs = np.array(iterations[0]['yao_diff'])
            last_diffs = np.array(iterations[-1]['yao_diff'])

            report_lines.append("### 爻位收敛")
            report_lines.append("")
            report_lines.append("| 爻位 | 初始偏差 | 最终偏差 | 变化 | 趋势 |")
            report_lines.append("|------|---------|---------|------|------|")

            for i, name in enumerate(yao_names):
                diff_change = abs(first_diffs[i]) - abs(last_diffs[i])
                trend = '✅ 改善' if diff_change > 0.01 else ('⚠ 不变' if abs(diff_change) < 0.01 else '❌ 恶化')
                report_lines.append(
                    f"| {name} | {first_diffs[i]:+.3f} | {last_diffs[i]:+.3f} | "
                    f"{diff_change:+.3f} | {trend} |"
                )
            report_lines.append("")

        # 学习曲线
        curve = [it['distance'] for it in iterations]
        report_lines.append(f"**学习曲线**: `{', '.join(f'{v:.3f}' for v in curve)}`")
        report_lines.append("")

        # 关键发现
        if len(curve) >= 2 and curve[-1] < curve[0]:
            pct = (curve[0] - curve[-1]) / curve[0] * 100
            report_lines.append(f"✅ **改善**: 距离从 {curve[0]:.3f} 降至 {curve[-1]:.3f} (-{pct:.1f}%)")
            # 找出改善最大的爻
            max_improvement_idx = np.argmax(abs(first_diffs) - abs(last_diffs))
            report_lines.append(f"   最大改善爻位: {yao_names[max_improvement_idx]}")
        else:
            report_lines.append(f"⚠ **未收敛**: 距离保持在 {curve[-1]:.3f}")

        report_lines.append("")

    return "\n".join(report_lines)


if __name__ == '__main__':
    json_path = Path(__file__).parent / 'output' / 'batch_experiment' / 'experiment_results.json'

    if json_path.exists():
        report = analyze_experiment(str(json_path))
        report_path = Path(__file__).parent / 'output' / 'batch_experiment' / 'analysis_report.md'
        report_path.write_text(report)
        print(report)
    else:
        print(f"实验数据文件不存在: {json_path}")
        print("请先运行 experiment_batch.py")
