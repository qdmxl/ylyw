#!/usr/bin/env python3
"""
YLYW 视觉分类器 — Rich Features v2 (Z-score 归一化) + Few-Shot + Brodatz

改进: 特征先做Z-score归一化, 消除量纲差异
"""

import sys, os, numpy as np, cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.rich_features import RichFeatureExtractor

BRODATZ_MAPPING = {
    '1.1.05':'乾','1.1.11':'乾','1.3.07':'乾','1.4.05':'乾','1.4.07':'乾','1.4.12':'乾','1.5.01':'乾',
    '1.1.02':'坤','1.3.03':'坤','1.3.04':'坤','1.3.05':'坤','1.5.02':'坤','1.5.09':'坤','1.5.10':'坤',
    '1.1.07':'震','1.1.10':'震','1.4.01':'震','1.4.02':'震','1.4.03':'震','1.4.04':'震',
    '1.4.08':'震','1.4.09':'震','1.4.10':'震',
    '1.1.12':'巽','1.1.13':'巽','1.3.01':'巽','1.3.02':'巽','1.3.08':'巽','1.3.09':'巽',
    '1.3.12':'巽','1.3.13':'巽','1.4.06':'巽','1.4.13':'巽','1.5.04':'巽','1.5.05':'巽',
    '1.5.06':'巽','1.5.07':'巽','1.5.08':'巽',
    '1.1.04':'坎','1.1.09':'坎','1.3.10':'坎',
    '1.1.08':'离','1.5.03':'离',
    '1.1.03':'艮','1.3.11':'艮','1.5.11':'艮','1.5.12':'艮',
    '1.3.06':'兑','1.4.11':'兑',
}

CALIBRATION = {
    '乾': ['1.1.05'], '坤': ['1.1.02'], '震': ['1.1.07'], '巽': ['1.1.12'],
    '坎': ['1.1.04'], '离': ['1.1.08'], '艮': ['1.1.03'], '兑': ['1.3.06'],
}


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4
    extractor = RichFeatureExtractor()
    class_order = ['乾','兑','离','震','巽','坎','艮','坤']

    print("=" * 70)
    print("  YLYW — Rich Features (Z-score) + Few-Shot + Brodatz")
    print("=" * 70)

    # Step 1: 收集所有特征
    all_data = {}
    all_features = []  # for Z-score stats

    for fname in sorted(os.listdir(textures_dir)):
        if not fname.endswith('.tiff'): continue
        if '1.2.' in fname: continue
        base = fname.replace('.tiff', '')
        if base not in BRODATZ_MAPPING: continue

        filepath = os.path.join(textures_dir, fname)
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None: continue

        h, w = img.shape
        ch, cw = h // 2, w // 2
        crops = [img[:ch,:cw], img[:ch,cw:], img[ch:,:cw], img[ch:,cw:]]
        features = np.stack([extractor.extract(c) for c in crops[:n_crops]])
        all_data[base] = features
        all_features.append(features)

    all_feats = np.concatenate(all_features, axis=0)
    feat_mean = all_feats.mean(axis=0)
    feat_std = all_feats.std(axis=0) + 1e-8

    print(f"  收集: {len(all_data)} 纹理, {len(all_feats)} 特征向量")
    print(f"  特征维度: {all_feats.shape[1]}")

    # Normalize
    for base in all_data:
        all_data[base] = (all_data[base] - feat_mean) / feat_std

    # Step 2: 构建归一化原型
    prototypes = {}
    for cls, calib_files in CALIBRATION.items():
        proto_feats = []
        for cf in calib_files:
            if cf in all_data:
                proto_feats.append(all_data[cf])
        if proto_feats:
            prototypes[cls] = np.concatenate(proto_feats, axis=0).mean(axis=0)

    # Step 3: 测试
    per_class = defaultdict(lambda: {'t1':0,'t3':0,'n':0})
    total_t1, total_t3, total_n = 0, 0, 0
    class_results = defaultdict(list)

    for base, cls in sorted(BRODATZ_MAPPING.items()):
        if base not in all_data: continue
        if base in CALIBRATION.get(cls, []): continue

        feats = all_data[base]
        for i in range(len(feats)):
            test_vec = feats[i]
            total_n += 1
            dists = {pc: np.sum((test_vec - pv)**2) for pc, pv in prototypes.items()}
            ranked = sorted(dists.items(), key=lambda x: x[1])
            top1, top3 = ranked[0][0], [r[0] for r in ranked[:3]]
            is_t1, is_t3 = top1 == cls, cls in top3

            if is_t1: total_t1 += 1; per_class[cls]['t1'] += 1
            if is_t3: total_t3 += 1; per_class[cls]['t3'] += 1
            per_class[cls]['n'] += 1
            class_results[cls].append({'top1': top1, 'correct': is_t1})

    # 输出
    print(f"\n{'类别':<20} {'样本':>5} {'Top-1':>6} {'Top-1%':>7} {'Top-3':>6} {'Top-3%':>7}")
    print("-" * 58)
    for cls in class_order:
        s = per_class[cls]
        if s['n'] == 0: continue
        print(f"  {cls:<18} {s['n']:>5} {s['t1']:>6} {100*s['t1']/s['n']:>6.1f}% "
              f"{s['t3']:>6} {100*s['t3']/s['n']:>6.1f}%")
    print("-" * 58)
    print(f"  {'总计':<18} {total_n:>5} {total_t1:>6} {100*total_t1/max(total_n,1):>6.1f}% "
          f"{total_t3:>6} {100*total_t3/max(total_n,1):>6.1f}%")

    # 混淆矩阵
    print(f"\n  混淆矩阵")
    confusion = np.zeros((8,8), dtype=int)
    for ci, cls in enumerate(class_order):
        if cls not in class_results: continue
        for r in class_results[cls]:
            pred = r['top1']
            confusion[ci][class_order.index(pred) if pred in class_order else ci] += 1

    header = " " * 10 + "".join(f"{c:>5}" for c in class_order)
    print(header)
    for i, cls in enumerate(class_order):
        if per_class[cls]['n'] == 0: continue
        row = "".join(f"{confusion[i][j]:>5}" for j in range(8))
        print(f"  {cls:<8}{row}")

    print(f"\n  对比: v3={12.2}% | Rich(raw)={20.0}% | Rich(zscore)={100*total_t1/max(total_n,1):.1f}%")


if __name__ == '__main__':
    main()
