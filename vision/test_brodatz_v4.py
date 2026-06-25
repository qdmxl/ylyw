#!/usr/bin/env python3
"""
YLYW 视觉分类器 v4 — Brodatz 标准纹理数据集测试

v4 架构: 跳过六爻编码, 8个专用检测器直达卦象
"""

import sys
import os
import numpy as np
import cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.classifier_v4 import VisionClassifierV4

# Brodatz → YLFM 映射 (同 test_brodatz.py)
BRODATZ_MAPPING = {
    '1.1.05': '乾', '1.1.11': '乾', '1.3.07': '乾',
    '1.4.05': '乾', '1.4.07': '乾', '1.4.12': '乾', '1.5.01': '乾',
    '1.1.02': '坤', '1.3.03': '坤', '1.3.04': '坤',
    '1.3.05': '坤', '1.5.02': '坤', '1.5.09': '坤', '1.5.10': '坤',
    '1.1.07': '震', '1.1.10': '震', '1.4.01': '震',
    '1.4.02': '震', '1.4.03': '震', '1.4.04': '震',
    '1.4.08': '震', '1.4.09': '震', '1.4.10': '震',
    '1.1.12': '巽', '1.1.13': '巽', '1.3.01': '巽',
    '1.3.02': '巽', '1.3.08': '巽', '1.3.09': '巽',
    '1.3.12': '巽', '1.3.13': '巽', '1.4.06': '巽',
    '1.4.13': '巽', '1.5.04': '巽', '1.5.05': '巽',
    '1.5.06': '巽', '1.5.07': '巽', '1.5.08': '巽',
    '1.1.04': '坎', '1.1.09': '坎', '1.3.10': '坎',
    '1.1.08': '离', '1.5.03': '离',
    '1.1.03': '艮', '1.3.11': '艮', '1.5.11': '艮', '1.5.12': '艮',
    '1.3.06': '兑', '1.4.11': '兑',
}


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4

    print("=" * 70)
    print("  YLYW 视觉分类器 v4 — Brodatz 标准纹理数据集测试")
    print("  v4 架构: 8个专用检测器 → 8D隶属度 → 直达分类")
    print("  (跳过 六爻编码 + 六十四卦匹配 + 爻位关系)")
    print("=" * 70)
    print(f"  纹理张数: {len(BRODATZ_MAPPING)}, 每张切{n_crops}子图")
    print()

    classifier = VisionClassifierV4()

    per_class = defaultdict(lambda: {'correct_top1': 0, 'correct_top3': 0, 'total': 0})
    total_t1, total_t3, total_samples = 0, 0, 0
    class_results = defaultdict(list)

    for filename, expected_class in sorted(BRODATZ_MAPPING.items()):
        filepath = os.path.join(textures_dir, filename + '.tiff')
        if not os.path.exists(filepath):
            continue

        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        h, w = img.shape
        ch, cw = h // 2, w // 2
        crops = [img[:ch, :cw], img[:ch, cw:], img[ch:, :cw], img[ch:, cw:]]

        for crop_idx, crop in enumerate(crops[:n_crops]):
            total_samples += 1
            result = classifier.classify(crop, top_k=3)
            top1_class = result['top_results'][0]['class_name']
            top1_score = result['top_results'][0]['score']

            is_top1 = expected_class in top1_class
            is_top3 = any(expected_class in r['class_name'] for r in result['top_results'])

            if is_top1:
                total_t1 += 1
                per_class[expected_class]['correct_top1'] += 1
            if is_top3:
                total_t3 += 1
                per_class[expected_class]['correct_top3'] += 1

            per_class[expected_class]['total'] += 1
            class_results[expected_class].append({
                'sample': f"{filename}#{crop_idx}",
                'top1': top1_class,
                'score': top1_score,
                'correct': is_top1,
            })

    # 输出
    print()
    print(f"{'类别':<20} {'样本数':>6} {'Top-1正确':>9} {'Top-1率':>8} {'Top-3正确':>9} {'Top-3率':>8}")
    print("-" * 70)

    class_order = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤']
    for cls in class_order:
        stats = per_class[cls]
        if stats['total'] == 0:
            continue
        t1r = 100 * stats['correct_top1'] / stats['total']
        t3r = 100 * stats['correct_top3'] / stats['total']
        print(f"  {cls:<18} {stats['total']:>6} {stats['correct_top1']:>9} {t1r:>7.1f}% "
              f"{stats['correct_top3']:>9} {t3r:>7.1f}%")

    print("-" * 70)
    t1g = 100 * total_t1 / max(total_samples, 1)
    t3g = 100 * total_t3 / max(total_samples, 1)
    print(f"  {'总计':<18} {total_samples:>6} {total_t1:>9} {t1g:>7.1f}% "
          f"{total_t3:>9} {t3g:>7.1f}%")
    print()

    # 混淆矩阵
    print("  混淆矩阵 (行=真值, 列=预测Top-1)")
    print("  " + "─" * 70)
    confusion = np.zeros((8, 8), dtype=int)
    for cls_idx, cls in enumerate(class_order):
        if cls not in class_results:
            continue
        for r in class_results[cls]:
            pred = r['top1']
            for p_idx, p_cls in enumerate(class_order):
                if p_cls in pred:
                    confusion[cls_idx][p_idx] += 1
                    break
            else:
                confusion[cls_idx][cls_idx] += 1

    header = " " * 10 + "".join(f"{c:>6}" for c in class_order)
    print(header)
    for i, cls in enumerate(class_order):
        if per_class[cls]['total'] == 0:
            continue
        row = "".join(f"{confusion[i][j]:>6}" for j in range(8))
        print(f"  {cls:<8}{row}")

    print()
    print(f"  v4 Top-1: {t1g:.1f}%  |  v3 Top-1: 12.2%")

    return total_t1, total_samples


if __name__ == '__main__':
    main()
