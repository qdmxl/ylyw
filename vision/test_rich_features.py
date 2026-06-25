#!/usr/bin/env python3
"""
YLYW 视觉分类器 — Rich Features + Few-Shot 原型 + Brodatz 测试

特征: GLCM(18D) + Gabor(24D) + LBP(10D) = 52D
原型: 每类用 1-2 张 Brodatz 纹理标定质心
测试: 剩余纹理

对比基准:
    v3 (6D手工特征):  12.2%
    v4 (8专用检测器):  22.7%
    数据驱动质心(LOO): 15.1%
"""

import sys
import os
import numpy as np
import cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.rich_features import RichFeatureExtractor

# Brodatz → YLFM 映射
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

# 每类选取 1 张作为 calibration，其余测试
CALIBRATION = {
    '乾': ['1.1.05'],
    '坤': ['1.1.02'],
    '震': ['1.1.07'],
    '巽': ['1.1.12'],
    '坎': ['1.1.04'],
    '离': ['1.1.08'],
    '艮': ['1.1.03'],
    '兑': ['1.3.06'],
}


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4

    print("=" * 70)
    print("  YLYW 视觉分类器 — Rich Features + Few-Shot + Brodatz")
    print("  特征: GLCM(18D) + Gabor(24D) + LBP(10D) = 52D")
    print("  原型: 每类1张标定 → 欧氏距离 → 最近原型分类")
    print("=" * 70)

    extractor = RichFeatureExtractor()

    # Step 1: 收集所有纹理的特征
    all_data = {}  # filename → list of feature vectors (per crop)

    for fname in sorted(os.listdir(textures_dir)):
        if not fname.endswith('.tiff'):
            continue
        if '1.2.' in fname:
            continue

        base = fname.replace('.tiff', '')
        if base not in BRODATZ_MAPPING:
            continue

        filepath = os.path.join(textures_dir, fname)
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue

        h, w = img.shape
        ch, cw = h // 2, w // 2
        crops = [img[:ch, :cw], img[:ch, cw:], img[ch:, :cw], img[ch:, cw:]]

        features = []
        for crop in crops[:n_crops]:
            feat = extractor.extract(crop)
            features.append(feat)
        all_data[base] = np.stack(features)

    print(f"  收集到 {len(all_data)} 张纹理, 每张{n_crops}子图")
    print()

    # Step 2: 构建原型
    prototypes = {}
    for cls, calib_files in CALIBRATION.items():
        proto_feats = []
        for cf in calib_files:
            if cf in all_data:
                proto_feats.append(all_data[cf])
        if proto_feats:
            # 合并所有标定样本的特征
            proto_feats = np.concatenate(proto_feats, axis=0)
            prototypes[cls] = proto_feats.mean(axis=0)
            print(f"  {cls} 原型: {len(proto_feats)} 样本")
        else:
            print(f"  ⚠️ {cls} 原型: 无标定数据!")

    print()

    # Step 3: 测试
    class_order = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤']
    per_class = defaultdict(lambda: {'correct_top1': 0, 'correct_top3': 0, 'total': 0})
    total_t1, total_t3, total_samples = 0, 0, 0
    class_results = defaultdict(list)

    for base, cls in sorted(BRODATZ_MAPPING.items()):
        if base not in all_data:
            continue
        if base in CALIBRATION.get(cls, []):
            continue  # 跳过标定数据

        feats = all_data[base]  # (n_crops, 52)

        for i in range(len(feats)):
            test_vec = feats[i]
            total_samples += 1

            # 计算到每个原型的欧氏距离
            dists = {}
            for proto_cls, proto_vec in prototypes.items():
                dists[proto_cls] = np.sum((test_vec - proto_vec) ** 2)

            # 排序
            ranked = sorted(dists.items(), key=lambda x: x[1])
            top1 = ranked[0][0]
            top3 = [r[0] for r in ranked[:3]]

            is_top1 = top1 == cls
            is_top3 = cls in top3

            if is_top1:
                total_t1 += 1
                per_class[cls]['correct_top1'] += 1
            if is_top3:
                total_t3 += 1
                per_class[cls]['correct_top3'] += 1

            per_class[cls]['total'] += 1
            class_results[cls].append({'top1': top1, 'correct': is_top1})

    # 输出
    print(f"{'类别':<20} {'样本数':>6} {'Top-1正确':>9} {'Top-1率':>8} {'Top-3正确':>9} {'Top-3率':>8}")
    print("-" * 70)

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
            p_idx = class_order.index(pred) if pred in class_order else cls_idx
            confusion[cls_idx][p_idx] += 1

    header = " " * 10 + "".join(f"{c:>6}" for c in class_order)
    print(header)
    for i, cls in enumerate(class_order):
        if per_class[cls]['total'] == 0:
            continue
        row = "".join(f"{confusion[i][j]:>6}" for j in range(8))
        print(f"  {cls:<8}{row}")

    print()
    print(f"  Rich Features Top-1: {t1g:.1f}%")
    print(f"  对比 — v3(6D): 12.2% | v4(8检测器): 22.7% | 数据驱动(LOO): 15.1%")

    return total_t1, total_samples


if __name__ == '__main__':
    main()
