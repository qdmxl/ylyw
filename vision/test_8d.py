#!/usr/bin/env python3
"""
YLYW 视觉分类器 — 8D 特征 (一卦一算子) + Brodatz

每个卦用1个最对口的视觉算子:
    乾: 角点间距规整度    (网格结构)
    坤: 局部方差          (平滑度)
    震: Gabor 方向主导度  (定向性)
    巽: 高频/低频能量比   (细纹理)
    坎: 梯度方向熵        (曲线度)
    离: 亮度峰值密度      (辐射感)
    艮: 大块低方差占比    (块状同质)
    兑: 高光局部对比      (反射感)

8D 特征 → 欧氏距离 → 最近原型 → 分类
"""

import sys, os, time
import numpy as np
import cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.specialized_detectors_v2 import SpecializedDetectorsV2

# Brodatz 映射
BRODATZ_MAPPING = {
    '1.1.05':'乾','1.1.11':'乾','1.3.07':'乾',
    '1.4.05':'乾','1.4.07':'乾','1.4.12':'乾','1.5.01':'乾',
    '1.1.02':'坤','1.3.03':'坤','1.3.04':'坤',
    '1.3.05':'坤','1.5.02':'坤','1.5.09':'坤','1.5.10':'坤',
    '1.1.07':'震','1.1.10':'震','1.4.01':'震',
    '1.4.02':'震','1.4.03':'震','1.4.04':'震',
    '1.4.08':'震','1.4.09':'震','1.4.10':'震',
    '1.1.12':'巽','1.1.13':'巽','1.3.01':'巽',
    '1.3.02':'巽','1.3.08':'巽','1.3.09':'巽',
    '1.3.12':'巽','1.3.13':'巽','1.4.06':'巽',
    '1.4.13':'巽','1.5.04':'巽','1.5.05':'巽',
    '1.5.06':'巽','1.5.07':'巽','1.5.08':'巽',
    '1.1.04':'坎','1.1.09':'坎','1.3.10':'坎',
    '1.1.08':'离','1.5.03':'离',
    '1.1.03':'艮','1.3.11':'艮','1.5.11':'艮','1.5.12':'艮',
    '1.3.06':'兑','1.4.11':'兑',
}

CLASS_ORDER = ['乾','兑','离','震','巽','坎','艮','坤']


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4
    detectors = SpecializedDetectorsV2()

    print("=" * 70)
    print("  YLYW 视觉分类器 — 8D 特征 (一卦一算子) + Brodatz")
    print("=" * 70)

    # ---- 收集特征 ----
    all_feats = {}  # basename → (n_crops, 8)
    all_labels = {}

    for fname in sorted(os.listdir(textures_dir)):
        if not fname.endswith('.tiff'): continue
        if '1.2.' in fname: continue
        base = fname.replace('.tiff', '')
        if base not in BRODATZ_MAPPING: continue

        fpath = os.path.join(textures_dir, fname)
        img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if img is None: continue

        h, w = img.shape
        ch, cw = h // 2, w // 2
        feats = []
        for crop in [img[:ch,:cw], img[:ch,cw:], img[ch:,:cw], img[ch:,cw:]][:n_crops]:
            f = detectors.detect_all(crop.astype(np.float32))
            feats.append(f)
        all_feats[base] = np.stack(feats)
        all_labels[base] = BRODATZ_MAPPING[base]

    print(f"  收集: {len(all_feats)} 纹理, 每张{n_crops}子图")
    print(f"  特征维度: 8 (一卦一算子)")

    # ---- Leave-One-Texture-Out 交叉验证 ----
    # 每次留一张纹理作测试, 其余作标定
    # 用标定集做 Z-score 归一化

    per_class = defaultdict(lambda: {'t1':0,'t3':0,'n':0})
    total_t1, total_t3, total_n = 0, 0, 0
    class_results = defaultdict(list)

    for test_base, test_cls in all_labels.items():
        # 标定集: 除测试纹理外的所有
        calib_feats = []
        calib_labels = []
        for base, label in all_labels.items():
            if base == test_base:
                continue
            calib_feats.append(all_feats[base])
            calib_labels.extend([label] * all_feats[base].shape[0])

        calib_all = np.concatenate(calib_feats, axis=0)

        # Z-score 归一化参数 (从标定集计算)
        calib_mean = calib_all.mean(axis=0)
        calib_std = calib_all.std(axis=0) + 1e-8

        # 构建归一化原型
        calib = {}
        for cls in CLASS_ORDER:
            mask = np.array([l == cls for l in calib_labels])
            if mask.any():
                cls_feats = (calib_all[mask] - calib_mean) / calib_std
                calib[cls] = cls_feats.mean(axis=0)
            else:
                calib[cls] = np.zeros(8)

        # 测试 (用标定集的归一化参数)
        test_norm = (all_feats[test_base] - calib_mean) / calib_std
        for i in range(len(test_norm)):
            x = test_norm[i]
            total_n += 1

            dists = {c: np.sum((x - calib[c])**2) for c in CLASS_ORDER}
            ranked = sorted(dists.items(), key=lambda kv: kv[1])
            top1 = ranked[0][0]
            top3 = [r[0] for r in ranked[:3]]

            is_t1 = top1 == test_cls
            is_t3 = test_cls in top3

            if is_t1: total_t1 += 1; per_class[test_cls]['t1'] += 1
            if is_t3: total_t3 += 1; per_class[test_cls]['t3'] += 1
            per_class[test_cls]['n'] += 1
            class_results[test_cls].append({'top1': top1, 'correct': is_t1})

    # ---- 输出 ----
    print(f"\n{'类别':<20} {'样本':>5} {'Top-1':>6} {'Top-1%':>7} {'Top-3':>6} {'Top-3%':>7}")
    print("-" * 58)
    for cls in CLASS_ORDER:
        s = per_class[cls]
        if s['n'] == 0: continue
        print(f"  {cls:<18} {s['n']:>5} {s['t1']:>6} {100*s['t1']/s['n']:>6.1f}% "
              f"{s['t3']:>6} {100*s['t3']/s['n']:>6.1f}%")
    print("-" * 58)
    t1r = 100 * total_t1 / max(total_n, 1)
    t3r = 100 * total_t3 / max(total_n, 1)
    print(f"  {'总计':<18} {total_n:>5} {total_t1:>6} {t1r:>6.1f}% "
          f"{total_t3:>6} {t3r:>6.1f}%")

    # 混淆矩阵
    print(f"\n  混淆矩阵")
    confusion = np.zeros((8,8), dtype=int)
    for ci, cls in enumerate(CLASS_ORDER):
        if cls not in class_results: continue
        for r in class_results[cls]:
            pred = r['top1']
            confusion[ci][CLASS_ORDER.index(pred) if pred in CLASS_ORDER else ci] += 1

    header = " " * 10 + "".join(f"{c:>5}" for c in CLASS_ORDER)
    print(header)
    for i, cls in enumerate(CLASS_ORDER):
        if per_class[cls]['n'] == 0: continue
        row = "".join(f"{confusion[i][j]:>5}" for j in range(8))
        print(f"  {cls:<8}{row}")

    print(f"\n  对比: v3(6D)={12.2}% | v4(8检)={22.7}% | Rich(52D)={30.2}% | 8D={t1r:.1f}%")


if __name__ == '__main__':
    main()
