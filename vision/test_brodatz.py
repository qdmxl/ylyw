#!/usr/bin/env python3
"""
YLYW 视觉分类器 — Brodatz 标准纹理数据集测试

Brodatz Textures (USC-SIPI): 纹理分类的标准基准。
测试零样本分类能力 —— 不训练，不微调，直接用视觉原型匹配。

Brodatz → YLFM 8类 映射
    乾·结构几何: herringbone, netting, wire mesh, ceiling tile, stepped grid
    坤·平滑均匀: cork, leather, sand, pigskin
    震·高对比方向: grass lawn, straw, wood grain, straw mat
    巽·细纹理:   wool, canvas, fur, paper, cotton, raffia
    坎·曲线流动: expanded cork, bark, plastic sponge
    离·亮辐射:   bubbles, plastic
    艮·块状厚重: pressed cork, brick
    兑·反射高光: water droplets, aluminum foil
"""

import sys
import os
import numpy as np
import cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.classifier import VisionClassifier

# ============================================================
#  Brodatz → YLFM 类别映射
#  格式: {SIPI文件名: YLFM类名}
#  基于 Brodatz 纹理的公认视觉特征
# ============================================================

BRODATZ_MAPPING = {
    # ── 乾: 结构/几何 ──
    '1.1.05': '乾',  # D6  woven mat — 规则编织网格
    '1.1.11': '乾',  # D16 herringbone weave — 人字纹
    '1.3.07': '乾',  # D34 netting/metal mesh — 金属网格
    '1.4.05': '乾',  # D56 aluminum wire mesh — 铝线网格
    '1.4.07': '乾',  # D64 ceiling tile — 天花板网格
    '1.4.12': '乾',  # D76 aluminum mesh — 铝网
    '1.5.01': '乾',  # D78 stepped surface — 阶梯图案

    # ── 坤: 平滑/均匀 ──
    '1.1.02': '坤',  # D3  cork — 平滑软木
    '1.3.03': '坤',  # D24 calf leather — 小牛皮
    '1.3.04': '坤',  # D28 beach sand — 沙滩(细)
    '1.3.05': '坤',  # D29 beach sand — 沙滩
    '1.5.02': '坤',  # D79 beach sand — 沙滩
    '1.5.09': '坤',  # D92 pigskin — 猪皮(平滑)
    '1.5.10': '坤',  # D93 pigskin — 猪皮

    # ── 震: 高对比方向 ──
    '1.1.07': '震',  # D9  grass lawn — 定向草纹
    '1.1.10': '震',  # D15 straw — 稻草
    '1.4.01': '震',  # D52 oriented wood grain — 木纹
    '1.4.02': '震',  # D53 oriented wood grain — 木纹
    '1.4.03': '震',  # D54 oriented wood grain — 木纹
    '1.4.04': '震',  # D55 straw matting — 草席
    '1.4.08': '震',  # D65 wood grain — 木纹
    '1.4.09': '震',  # D66 wood grain — 木纹
    '1.4.10': '震',  # D68 wood grain — 木纹

    # ── 巽: 细纹理 ──
    '1.1.12': '巽',  # D17 pressed wool — 压羊毛
    '1.1.13': '巽',  # D19 woolen cloth — 毛织物
    '1.3.01': '巽',  # D20 French canvas — 帆布
    '1.3.02': '巽',  # D21 French canvas — 帆布
    '1.3.08': '巽',  # D36 lizard skin — 蜥蜴皮
    '1.3.09': '巽',  # D38 fur — 皮毛
    '1.3.12': '巽',  # D49 wrapping paper — 包装纸
    '1.3.13': '巽',  # D51 wrapping paper — 包装纸
    '1.4.06': '巽',  # D57 handmade paper/cotton — 手工纸
    '1.4.13': '巽',  # D77 cotton canvas — 棉帆布
    '1.5.04': '巽',  # D81 grass lawn — 草地
    '1.5.05': '巽',  # D82 grass cloth — 草布
    '1.5.06': '巽',  # D83 woven canvas — 编织帆布
    '1.5.07': '巽',  # D84 raffia looped — 拉菲草
    '1.5.08': '巽',  # D87 cotton cloth — 棉布

    # ── 坎: 曲线/流动 ──
    '1.1.04': '坎',  # D5  expanded cork — 多孔海绵状
    '1.1.09': '坎',  # D12 tree bark — 树皮
    '1.3.10': '坎',  # D46 plastic sponge — 塑料海绵

    # ── 离: 亮/辐射 ──
    '1.1.08': '离',  # D11 bubbles/plastic — 气泡(高光)
    '1.5.03': '离',  # D80 plastic bubbles — 塑料气泡

    # ── 艮: 块状/厚重 ──
    '1.1.03': '艮',  # D4  pressed cork — 压软木(块状)
    '1.3.11': '艮',  # D47 brick wall — 砖墙
    '1.5.11': '艮',  # D94 brick wall — 砖墙
    '1.5.12': '艮',  # D95 brick wall — 砖墙

    # ── 兑: 反射/高光 ──
    '1.3.06': '兑',  # D32 water droplets — 水滴(反光)
    '1.4.11': '兑',  # D74 aluminum foil — 铝箔(反光)
}


def main():
    textures_dir = '/tmp/brodatz/textures'
    n_crops = 4  # 每张纹理切4个子图

    print("=" * 70)
    print("  YLYW 视觉分类器 — Brodatz 标准纹理数据集测试")
    print("=" * 70)
    print(f"  数据来源: USC-SIPI Brodatz Textures (标准基准)")
    print(f"  纹理张数: {len(BRODATZ_MAPPING)}")
    print(f"  每张切{n_crops}个子图 → 总计 {len(BRODATZ_MAPPING) * n_crops} 样本")
    print(f"  分类方式: 零样本 (无训练/微调)")
    print()

    classifier = VisionClassifier(sensitivity=0.8)

    # 统计
    per_class = defaultdict(lambda: {'correct_top1': 0, 'correct_top3': 0, 'total': 0})
    total_correct_top1 = 0
    total_correct_top3 = 0
    total_samples = 0

    # 跳过 label (如 "1.2.xx" 是直方图均衡版)
    skip_prefixes = {'1.2.'}
    
    # 按类别分组输出
    class_results = defaultdict(list)

    for filename, expected_class in sorted(BRODATZ_MAPPING.items()):
        filepath = os.path.join(textures_dir, filename + '.tiff')

        if not os.path.exists(filepath):
            print(f"  ⚠️ 文件不存在: {filepath}")
            continue

        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"  ⚠️ 无法读取: {filepath}")
            continue

        h, w = img.shape

        # 切 n_crops 个子图 (2x2 网格)
        crop_h, crop_w = h // 2, w // 2
        crops = [
            img[:crop_h, :crop_w],
            img[:crop_h, crop_w:],
            img[crop_h:, :crop_w],
            img[crop_h:, crop_w:],
        ]

        for crop_idx, crop in enumerate(crops[:n_crops]):
            total_samples += 1

            try:
                result = classifier.classify(crop, top_k=3)
            except Exception as e:
                print(f"  ❌ 分类异常 {filename}#{crop_idx}: {e}")
                continue

            top1_class = result['top_results'][0]['class_name']
            top1_conf = result['top_results'][0]['confidence']

            is_top1 = expected_class in top1_class
            is_top3 = any(expected_class in r['class_name'] for r in result['top_results'])

            if is_top1:
                total_correct_top1 += 1
                per_class[expected_class]['correct_top1'] += 1
            if is_top3:
                total_correct_top3 += 1
                per_class[expected_class]['correct_top3'] += 1

            per_class[expected_class]['total'] += 1

            class_results[expected_class].append({
                'sample': f"{filename}#{crop_idx}",
                'top1': top1_class,
                'conf': top1_conf,
                'correct': is_top1,
            })

    # ========================================
    #  输出结果
    # ========================================
    print()
    print(f"{'类别':<20} {'样本数':>6} {'Top-1正确':>9} {'Top-1率':>8} {'Top-3正确':>9} {'Top-3率':>8}")
    print("-" * 70)

    class_order = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤']
    for cls in class_order:
        stats = per_class[cls]
        if stats['total'] == 0:
            continue
        t1_rate = 100 * stats['correct_top1'] / stats['total']
        t3_rate = 100 * stats['correct_top3'] / stats['total']
        print(f"  {cls:<18} {stats['total']:>6} {stats['correct_top1']:>9} {t1_rate:>7.1f}% "
              f"{stats['correct_top3']:>9} {t3_rate:>7.1f}%")

    print("-" * 70)
    t1_global = 100 * total_correct_top1 / total_samples if total_samples > 0 else 0
    t3_global = 100 * total_correct_top3 / total_samples if total_samples > 0 else 0
    print(f"  {'总计':<18} {total_samples:>6} {total_correct_top1:>9} {t1_global:>7.1f}% "
          f"{total_correct_top3:>9} {t3_global:>7.1f}%")
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
    print(f"  Brodatz 标准纹理数据集零样本测试完成")
    print(f"  Top-1 准确率: {t1_global:.1f}%  |  Top-3 准确率: {t3_global:.1f}%")

    return total_correct_top1, total_samples


if __name__ == '__main__':
    main()
