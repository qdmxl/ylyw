#!/usr/bin/env python3
"""
YLYW 视觉分类器 — 小样本微调 (Few-Shot Fine-Tuning) + Brodatz

方法:
    1. 用1-2张纹理标定初始原型
    2. 用2-3张纹理做微调: 优化原型位置使分类损失最小
    3. 剩余纹理做测试
    4. 对比: 零样本 vs 微调后

优化:
    L-BFGS-B 最小化 margin-based loss:
    loss = Σ max(0, d_correct - d_wrong + margin)
"""

import sys, os, time, json
import numpy as np
import cv2
from collections import defaultdict
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.rich_features import RichFeatureExtractor

# ============================================================
#  Brodatz 映射和划分
# ============================================================

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

# 每类划分: calib(标定初始原型) + finetune(微调) + test(测试)
SPLIT = {
    '乾': {'calib': ['1.1.05'],       'finetune': ['1.1.11', '1.4.12'], 'test': ['1.3.07','1.4.05','1.4.07','1.5.01']},
    '坤': {'calib': ['1.1.02'],       'finetune': ['1.3.03', '1.5.02'], 'test': ['1.3.04','1.3.05','1.5.09','1.5.10']},
    '震': {'calib': ['1.1.07'],       'finetune': ['1.4.01', '1.4.04'], 'test': ['1.1.10','1.4.02','1.4.03','1.4.08','1.4.09','1.4.10']},
    '巽': {'calib': ['1.1.12'],       'finetune': ['1.3.01', '1.4.06'], 'test': ['1.1.13','1.3.02','1.3.08','1.3.09','1.3.12','1.3.13','1.4.13','1.5.04','1.5.05','1.5.06','1.5.07','1.5.08']},
    '坎': {'calib': ['1.1.04'],       'finetune': ['1.1.09'],           'test': ['1.3.10']},
    '离': {'calib': ['1.1.08'],       'finetune': [],                   'test': ['1.5.03']},
    '艮': {'calib': ['1.1.03'],       'finetune': ['1.3.11'],           'test': ['1.5.11','1.5.12']},
    '兑': {'calib': ['1.3.06'],       'finetune': ['1.4.11'],           'test': []},
}

CLASS_ORDER = ['乾','兑','离','震','巽','坎','艮','坤']


def load_features(textures_dir, extractor, filename_list, n_crops=4):
    """加载指定纹理列表的特征"""
    all_feats = []
    all_labels = []
    for base, cls in BRODATZ_MAPPING.items():
        if base not in filename_list:
            continue
        fpath = os.path.join(textures_dir, base + '.tiff')
        if not os.path.exists(fpath):
            continue
        img = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        h, w = img.shape
        ch, cw = h // 2, w // 2
        for crop in [img[:ch,:cw], img[:ch,cw:], img[ch:,:cw], img[ch:,cw:]][:n_crops]:
            feat = extractor.extract(crop)
            all_feats.append(feat)
            all_labels.append(cls)
    return np.array(all_feats), all_labels


def compute_loss(params, prototypes_flat, finetune_feats, finetune_labels,
                 class_order, temperature=1.0):
    """
    Softmax Cross-Entropy 分类损失

    prototypes_flat: 初始原型 (8 × D), 固定
    params: 原型偏移量 (8 × D)

    loss = -Σ log( exp(-d_correct/T) / Σ_j exp(-d_j/T) ) / N + λ·||params||²
    """
    n_classes = len(class_order)
    D = len(prototypes_flat) // n_classes
    proto = (prototypes_flat + params).reshape(n_classes, D)

    # Z-score normalize
    feat_mean = finetune_feats.mean(axis=0)
    feat_std = finetune_feats.std(axis=0) + 1e-8
    feats_norm = (finetune_feats - feat_mean) / feat_std
    proto_norm = (proto - feat_mean) / feat_std

    # 距离矩阵 (N × 8)
    loss_val = 0.0
    N = len(finetune_feats)

    for i in range(N):
        x = feats_norm[i]
        label = finetune_labels[i]
        c = class_order.index(label)

        dists = np.sum((proto_norm - x) ** 2, axis=1)  # (8,)

        # Softmax over negative distances
        logits = -dists / temperature
        logits = logits - logits.max()  # 数值稳定
        probs = np.exp(logits)
        probs = probs / probs.sum()

        loss_val -= np.log(probs[c] + 1e-10)

    loss_val = loss_val / N

    # L2 正则
    reg = 0.001 * np.sum(params ** 2) / n_classes
    return loss_val + reg


def evaluate_classifier(prototypes, features, labels, class_order):
    """评估分类准确率"""
    # Z-score
    feats_mean = features.mean(axis=0)
    feats_std = features.std(axis=0) + 1e-8
    feats_norm = (features - feats_mean) / feats_std
    proto_norm = (prototypes - feats_mean) / feats_std

    correct_top1, correct_top3, total = 0, 0, len(features)
    per_class = defaultdict(lambda: {'t1':0,'t3':0,'n':0})

    for i in range(total):
        x = feats_norm[i]
        dists = np.sum((proto_norm - x) ** 2, axis=1)
        ranked = np.argsort(dists)
        top1 = class_order[ranked[0]]
        top3 = [class_order[j] for j in ranked[:3]]

        if top1 == labels[i]:
            correct_top1 += 1
            per_class[labels[i]]['t1'] += 1
        if labels[i] in top3:
            correct_top3 += 1
            per_class[labels[i]]['t3'] += 1
        per_class[labels[i]]['n'] += 1

    return {
        'top1': correct_top1, 'top3': correct_top3, 'total': total,
        'top1_rate': correct_top1 / max(total, 1),
        'top3_rate': correct_top3 / max(total, 1),
        'per_class': dict(per_class),
    }


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4
    extractor = RichFeatureExtractor()

    print("=" * 70)
    print("  YLYW 视觉 — 小样本微调 + Brodatz 测试")
    print("=" * 70)

    # ---- 收集全部数据 ----
    all_files = set()
    for cls in CLASS_ORDER:
        for split in ['calib', 'finetune', 'test']:
            all_files.update(SPLIT[cls].get(split, []))

    calib_feats, calib_labels = load_features(textures_dir, extractor,
                                               [f for cls in CLASS_ORDER
                                                for f in SPLIT[cls]['calib']])
    ft_files = [f for cls in CLASS_ORDER for f in SPLIT[cls]['finetune']]
    finetune_feats, finetune_labels = load_features(textures_dir, extractor, ft_files)
    test_files = [f for cls in CLASS_ORDER for f in SPLIT[cls]['test']]
    test_feats, test_labels = load_features(textures_dir, extractor, test_files)

    print(f"  标定: {len(calib_feats)} 样本")
    print(f"  微调: {len(finetune_feats)} 样本")
    print(f"  测试: {len(test_feats)} 样本")
    D = calib_feats.shape[1]
    print(f"  特征维度: {D}")

    # ---- 初始原型 ----
    init_proto = np.zeros((8, D))
    for ci, cls in enumerate(CLASS_ORDER):
        mask = [l == cls for l in calib_labels]
        if any(mask):
            init_proto[ci] = calib_feats[mask].mean(axis=0)
        else:
            init_proto[ci] = np.random.randn(D) * 0.1

    print(f"\n  [零样本基线]")
    baseline = evaluate_classifier(init_proto, test_feats, test_labels, CLASS_ORDER)
    print(f"  Top-1: {baseline['top1_rate']:.1%} | Top-3: {baseline['top3_rate']:.1%}")

    # ---- 小样本微调 ----
    if len(finetune_feats) > 0:
        print(f"\n  [小样本微调] {len(finetune_feats)} 样本, scipy L-BFGS-B...")
        n_params = 8 * D
        init_params = np.zeros(n_params)

        t0 = time.time()
        result = minimize(
            compute_loss,
            init_params,
            args=(init_proto.flatten(), finetune_feats, finetune_labels,
                  CLASS_ORDER, 1.0),
            method='L-BFGS-B',
            options={'maxiter': 500, 'maxfun': 2000},
        )
        elapsed = time.time() - t0

        fine_proto = (init_proto.flatten() + result.x).reshape(8, D)
        print(f"  优化完成 ({elapsed:.1f}s, {result.nit} iters, loss={result.fun:.4f})")

        # 打印原型位移
        shifts = np.sqrt(np.sum((fine_proto - init_proto) ** 2, axis=1))
        print(f"  原型位移: {' '.join(f'{CLASS_ORDER[i]}={shifts[i]:.2f}' for i in range(8))}")
    else:
        fine_proto = init_proto
        print(f"\n  [小样本微调] 跳过 (无微调数据)")

    # ---- 测试 ----
    print(f"\n  [微调后评估]")
    after = evaluate_classifier(fine_proto, test_feats, test_labels, CLASS_ORDER)
    print(f"  Top-1: {after['top1_rate']:.1%} | Top-3: {after['top3_rate']:.1%}")

    # ---- 对比 ----
    print(f"\n{'='*70}")
    print(f"  结果对比")
    print(f"{'='*70}")
    print(f"\n{'类别':<20} {'零样本':>8} {'微调后':>8} {'提升':>8}")
    print("-" * 50)
    for cls in CLASS_ORDER:
        b = baseline['per_class'].get(cls, {}).get('t1', 0)
        a = after['per_class'].get(cls, {}).get('t1', 0)
        n = after['per_class'].get(cls, {}).get('n', 0)
        if n == 0: continue
        br = b / max(n, 1)
        ar = a / max(n, 1)
        delta = ar - br
        marker = '✅' if ar > br else ('➖' if ar == br else '❌')
        print(f"  {cls:<18} {br:>7.1%} {ar:>7.1%} {marker} {delta:>+6.1%}")

    print("-" * 50)
    b1 = baseline['top1_rate']
    a1 = after['top1_rate']
    b3 = baseline['top3_rate']
    a3 = after['top3_rate']
    print(f"  {'总计':<18} {b1:>7.1%} {a1:>7.1%} {'✅' if a1>b1 else '➖'} {a1-b1:>+6.1%}")
    print(f"\n  Top-3: {b3:.1%} → {a3:.1%} (+{a3-b3:+.1%})")

    print(f"\n  对比: v3={12.2}% | Rich零样本={b1*100:.1f}% | +微调={a1*100:.1f}%")


if __name__ == '__main__':
    main()
