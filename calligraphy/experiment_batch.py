"""
YLYW 书法学习批量实验

对多个汉字运行知几学习闭环，对比学习曲线，
验证YLYW的可解释学习和经验迁移。

实验设计：
- 10个汉字：永 大 人 中 心 山 水 天 地 国
- 每字5轮迭代
- 记录学习曲线、爻位收敛、卦象迁移
- 分析跨字经验迁移效果
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import cv2
import time
import json
from collections import defaultdict

from learning_loop import (
    ZhijiLearningLoop, ZhijiDiagnosisEngine,
    _generate_target_calligraphy, load_copybook
)
from visual_calligraphy import CalligraphyVisualYLYW


def run_multi_char_experiment(
    characters: list = None,
    max_iterations: int = 5,
    output_dir: str = None,
    verbose: bool = True,
):
    """
    运行多字批量实验

    Returns:
        dict: 包含所有实验数据的字典
    """
    if characters is None:
        characters = ['永', '大', '人', '中', '心', '山', '水', '天', '地', '国']

    if output_dir is None:
        output_dir = str(Path(__file__).parent / 'output')

    result_dir = Path(output_dir) / 'batch_experiment'
    result_dir.mkdir(parents=True, exist_ok=True)

    loop = ZhijiLearningLoop(output_dir=str(result_dir))

    all_results = {
        'experiment_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'characters': characters,
        'max_iterations': max_iterations,
        'results': {},
        'summary': {},
    }

    if verbose:
        print("=" * 70)
        print("  YLYW 知几书法学习 — 批量实验")
        print("=" * 70)
        print(f"  汉字: {len(characters)}个 ({', '.join(characters)})")
        print(f"  每字迭代: {max_iterations}次")
        print(f"  总实验数: {len(characters) * max_iterations}")
        print("=" * 70)

    start_time = time.time()

    for char in characters:
        if verbose:
            print(f"\n{'#'*70}")
            print(f"### 「{char}」 ###")
            print(f"{'#'*70}")

        # 生成字帖
        target_image = load_copybook(char)

        # 先分析字帖，记录目标
        visual = CalligraphyVisualYLYW()
        target = visual.perceive(target_image)
        all_results['results'][char] = {
            'target_trigram': target.dominant_trigram,
            'target_hexagram': target.hexagram_name,
            'iterations': [],
        }

        # 运行学习闭环
        history = loop.run_learning_loop(
            character=char,
            target_image=target_image,
            max_iterations=max_iterations,
            verbose=verbose,
        )

        # 记录每轮数据
        for rec in history.iterations:
            d = rec.diagnosis
            all_results['results'][char]['iterations'].append({
                'iteration': d.iteration,
                'grade': d.grade,
                'distance': d.total_distance,
                'improvement': d.improvement,
                'yao_diff': d.yao_diff.tolist(),
                'target_trigram': d.target_trigram,
                'actual_trigram': d.actual_trigram,
                'max_diff_yao': d.max_diff_yao,
                'max_diff_val': d.max_diff_val,
                'calligraphy_params': {
                    k: v for k, v in rec.calligraphy_params.items()
                    if isinstance(v, (int, float))
                },
            })

    elapsed = time.time() - start_time

    # 汇总
    summary = _compute_summary(all_results)
    all_results['summary'] = summary

    if verbose:
        print(f"\n{'='*70}")
        print(f"  批量实验完成！")
        print(f"{'='*70}")
        print(f"  总耗时: {elapsed:.1f}s")
        print(f"  总迭代: {summary['total_iterations']}")
        print(f"  平均初始距离: {summary['avg_initial_distance']:.3f}")
        print(f"  平均最终距离: {summary['avg_final_distance']:.3f}")
        print(f"  平均改善率: {summary['avg_improvement_pct']:.1f}%")
        print(f"  评级分布: {summary['grade_distribution']}")
        print(f"  收敛率: {summary['convergence_rate']:.1f}%")

        # 打印每个字的学习曲线
        print(f"\n  学习曲线汇总:")
        for char in characters:
            curve = [it['distance'] for it in all_results['results'][char]['iterations']]
            direction = '↓' if len(curve) >= 2 and curve[-1] < curve[0] else '→'
            start_g = all_results['results'][char]['iterations'][0]['grade']
            end_g = all_results['results'][char]['iterations'][-1]['grade']
            print(f"    {char}: {start_g}→{end_g} {direction} "
                  f"[{', '.join(f'{v:.3f}' for v in curve)}]")

    # 保存结果
    json_path = result_dir / 'experiment_results.json'
    with open(json_path, 'w') as f:
        # 清理不可序列化的对象
        clean_results = _sanitize_for_json(all_results)
        json.dump(clean_results, f, indent=2, ensure_ascii=False)
    print(f"\n  📄 实验数据: {json_path}")

    # 生成学习报告
    report = loop.generate_learning_report()
    report_path = result_dir / 'batch_learning_report.md'
    report_path.write_text(report)
    print(f"  📄 学习报告: {report_path}")

    return all_results


def _compute_summary(results: dict) -> dict:
    """计算汇总统计"""
    total_iters = 0
    initial_dists = []
    final_dists = []
    improvements = []
    grade_counts = defaultdict(int)
    converged = 0

    for char, data in results['results'].items():
        iterations = data['iterations']
        if not iterations:
            continue

        total_iters += len(iterations)
        initial_dists.append(iterations[0]['distance'])
        final_dists.append(iterations[-1]['distance'])

        imp = iterations[0]['distance'] - iterations[-1]['distance']
        improvements.append(imp)

        for it in iterations:
            grade_counts[it['grade']] += 1

        # 收敛判定：最后3次距离变化 < 0.01
        if len(iterations) >= 3:
            last3 = [it['distance'] for it in iterations[-3:]]
            if max(last3) - min(last3) < 0.01:
                converged += 1

    avg_init = np.mean(initial_dists) if initial_dists else 0
    avg_final = np.mean(final_dists) if final_dists else 0
    avg_imp = np.mean(improvements) if improvements else 0
    avg_imp_pct = (avg_imp / avg_init * 100) if avg_init > 0 else 0

    return {
        'total_iterations': total_iters,
        'avg_initial_distance': float(avg_init),
        'avg_final_distance': float(avg_final),
        'avg_improvement': float(avg_imp),
        'avg_improvement_pct': float(avg_imp_pct),
        'grade_distribution': dict(grade_counts),
        'convergence_rate': float(converged / len(results['results']) * 100),
    }


def _sanitize_for_json(obj):
    """清理对象使其可JSON序列化"""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


if __name__ == '__main__':
    # 运行完整批量实验（10个字）
    results = run_multi_char_experiment(
        characters=['永', '大', '人', '中', '心'],
        max_iterations=5,
        verbose=True,
    )
