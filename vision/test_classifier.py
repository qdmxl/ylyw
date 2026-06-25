#!/usr/bin/env python3
"""
YLYW 视觉分类器 — 零样本测试

生成8类合成图像（每类5张，共40张），
测试 YLYW 视觉分类器的零样本分类能力。

视觉类别:
    0 乾: 结构/几何 — 棋盘格/条纹    (expected: 0/乾类)
    1 兑: 反射/高光 — 高亮点+渐变    (expected: 1/兑类)
    2 离: 亮/辐射   — 放射线+亮点    (expected: 2/离类)
    3 震: 高对比方向 — 密集条纹      (expected: 3/震类)
    4 巽: 细纹理   — 随机细纹理      (expected: 4/巽类)
    5 坎: 曲线/流动 — Perlin噪声     (expected: 5/坎类)
    6 艮: 块状/厚重 — 随机矩形块      (expected: 6/艮类)
    7 坤: 平滑/均匀 — 纯色+微噪      (expected: 7/坤类)
"""

import sys
import os
import time
import numpy as np
import cv2

# 将 vision 目录的父目录加入 path，以便作为包导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.classifier import VisionClassifier

# ============================================================
#  合成图像生成器
# ============================================================

def generate_checkerboard(size=200, block_size=20):
    """乾: 棋盘格 — 结构/几何"""
    img = np.zeros((size, size), dtype=np.float32)
    n = size // block_size
    for i in range(n):
        for j in range(n):
            if (i + j) % 2 == 0:
                y1, y2 = i * block_size, (i + 1) * block_size
                x1, x2 = j * block_size, (j + 1) * block_size
                val = 180 + np.random.uniform(-20, 20)
                img[y1:y2, x1:x2] = val
    img = np.clip(img + np.random.randn(size, size) * 5, 0, 255)
    return img.astype(np.uint8)


def generate_specular(size=200, num_spots=5):
    """兑: 反射/高光 — 暗底+随机高亮斑"""
    img = np.full((size, size), 30.0, dtype=np.float32)
    for _ in range(num_spots):
        cx, cy = np.random.randint(20, size - 20, 2)
        r = np.random.randint(15, 50)
        intensity = np.random.uniform(180, 255)
        Y, X = np.ogrid[:size, :size]
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        spot = intensity * np.exp(-dist ** 2 / (2 * r ** 2))
        img += spot
    img = np.clip(img + np.random.randn(size, size) * 8, 0, 255)
    return img.astype(np.uint8)


def generate_radiant(size=200, num_rays=12):
    """离: 亮/辐射 — 中心放射线"""
    center = size // 2
    img = np.zeros((size, size), dtype=np.float32)
    Y, X = np.ogrid[:size, :size]
    for i in range(num_rays):
        angle = 2 * np.pi * i / num_rays + np.random.uniform(-0.1, 0.1)
        dx, dy = np.cos(angle), np.sin(angle)
        # 点到射线的投影距离
        proj = (X - center) * dx + (Y - center) * dy
        perp = np.abs(-(X - center) * dy + (Y - center) * dx)
        ray_width = np.random.uniform(3, 10)
        mask = (perp < ray_width) & (proj > 0) & (proj < size // 2)
        img[mask] += np.random.uniform(180, 255)
    # 中心亮点
    r_center = np.sqrt((X - center) ** 2 + (Y - center) ** 2)
    img += 200 * np.exp(-r_center ** 2 / (2 * 15 ** 2))
    img = np.clip(img + np.random.randn(size, size) * 5, 0, 255)
    return img.astype(np.uint8)


def generate_directional(size=200):
    """震: 高对比方向 — 密集水平/垂直条纹"""
    img = np.zeros((size, size), dtype=np.float32)
    direction = np.random.choice(['h', 'v'])
    period = np.random.randint(4, 12)
    for i in range(size):
        val = 220 if (i // period) % 2 == 0 else 30
        val += np.random.uniform(-15, 15)
        if direction == 'h':
            img[i, :] = val
        else:
            img[:, i] = val
    img = np.clip(img + np.random.randn(size, size) * 5, 0, 255)
    return img.astype(np.uint8)


def generate_fine_texture(size=200, grain=3):
    """巽: 细纹理 — 高频随机噪声 + 高斯平滑"""
    img = np.random.randn(size, size) * 40 + 128
    img = cv2.GaussianBlur(img, (grain, grain), 0.8)
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)


def generate_flowing(size=200):
    """坎: 曲线/流动 — 正弦波叠加"""
    img = np.zeros((size, size), dtype=np.float32)
    Y, X = np.ogrid[:size, :size]
    for _ in range(5):
        amp = np.random.uniform(20, 50)
        freq = np.random.uniform(0.02, 0.08)
        phase_x = np.random.uniform(0, 2 * np.pi)
        phase_y = np.random.uniform(0, 2 * np.pi)
        wave = amp * np.sin(freq * X + phase_x) * np.cos(freq * Y + phase_y)
        img += wave
    img = img - img.min()
    img = img / img.max() * 255
    img = np.clip(img + np.random.randn(size, size) * 10, 0, 255)
    return img.astype(np.uint8)


def generate_blocky(size=200, max_blocks=12):
    """艮: 块状/厚重 — 随机矩形块"""
    img = np.full((size, size), 50.0, dtype=np.float32)
    for _ in range(np.random.randint(4, max_blocks)):
        x = np.random.randint(0, size - 30)
        y = np.random.randint(0, size - 30)
        w = np.random.randint(20, min(80, size - x))
        h = np.random.randint(20, min(80, size - y))
        val = np.random.uniform(140, 230)
        img[y:y + h, x:x + w] = val
    # 加边框效果
    block_mask = img > 100
    img[block_mask] += np.random.uniform(-15, 15)
    img = np.clip(img + np.random.randn(size, size) * 3, 0, 255)
    return img.astype(np.uint8)


def generate_smooth(size=200):
    """坤: 平滑/均匀 — 纯色+微噪+渐变"""
    base_val = np.random.uniform(60, 200)
    img = np.full((size, size), base_val, dtype=np.float32)
    # 轻渐变
    Y, X = np.ogrid[:size, :size]
    gradient = 20 * (Y / size - 0.5) + 20 * (X / size - 0.5)
    img += gradient
    img = np.clip(img + np.random.randn(size, size) * 3, 0, 255)
    return img.astype(np.uint8)


# 生成器映射
GENERATORS = {
    '乾·结构几何': generate_checkerboard,
    '兑·反射高光': generate_specular,
    '离·亮辐射': generate_radiant,
    '震·高对比方向': generate_directional,
    '巽·细纹理': generate_fine_texture,
    '坎·曲线流动': generate_flowing,
    '艮·块状厚重': generate_blocky,
    '坤·平滑均匀': generate_smooth,
}

EXPECTED_CLASSES = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤']


# ============================================================
#  测试主函数
# ============================================================

def main():
    print("=" * 70)
    print("  YLYW 视觉分类器 — 零样本合成图像测试")
    print("=" * 70)

    classifier = VisionClassifier(sensitivity=0.8)

    n_per_class = 5
    total = 0
    correct_top1 = 0
    correct_top3 = 0

    results_detail = []

    for class_idx, (class_name, generator) in enumerate(GENERATORS.items()):
        expected = EXPECTED_CLASSES[class_idx]
        class_correct_top1 = 0
        class_correct_top3 = 0

        for sample_idx in range(n_per_class):
            total += 1
            seed = class_idx * 100 + sample_idx
            np.random.seed(seed)
            image = generator()

            result = classifier.classify(image, top_k=3)
            top1 = result['top_results'][0]

            # 判断正确性
            is_top1 = expected in top1['class_name']
            is_top3 = any(expected in r['class_name'] for r in result['top_results'])

            if is_top1:
                correct_top1 += 1
                class_correct_top1 += 1
            if is_top3:
                correct_top3 += 1
                class_correct_top3 += 1

            results_detail.append({
                'sample': f"{class_name}#{sample_idx + 1}",
                'expected': expected,
                'top1_class': top1['class_name'],
                'top1_confidence': top1['confidence'],
                'top1_hexagram': top1['hexagram_name'],
                'dominant_trigram': result['dominant_trigram']['name'],
                'is_top1_correct': is_top1,
                'is_top3_correct': is_top3,
            })

            marker = "✅" if is_top1 else ("⚠️" if is_top3 else "❌")
            print(f"  [{marker}] {class_name}#{sample_idx + 1} "
                  f"→ {top1['class_name']} "
                  f"(置信度:{top1['confidence']:.3f} | {top1['hexagram_name']})")

        print(f"  {'─' * 50}")
        print(f"  该类 Top-1: {class_correct_top1}/{n_per_class} "
              f"({100 * class_correct_top1 / n_per_class:.0f}%) | "
              f"Top-3: {class_correct_top3}/{n_per_class} "
              f"({100 * class_correct_top3 / n_per_class:.0f}%)")
        print()

    # ========================================
    #  汇总
    # ========================================
    print("=" * 70)
    print("  测试汇总")
    print("=" * 70)
    print(f"  总样本数:     {total}")
    print(f"  Top-1 准确率: {correct_top1}/{total} ({100 * correct_top1 / total:.1f}%)")
    print(f"  Top-3 准确率: {correct_top3}/{total} ({100 * correct_top3 / total:.1f}%)")
    print()

    # 混淆矩阵
    print("  分类混淆矩阵 (行=真值, 列=预测)")
    print("  " + "─" * 65)
    confusion = np.zeros((8, 8), dtype=int)
    for r in results_detail:
        exp_idx = EXPECTED_CLASSES.index(r['expected'])
        # Top-1 预测类别
        pred_class_name = r['top1_class']
        for ci, ec in enumerate(EXPECTED_CLASSES):
            if ec in pred_class_name:
                pred_idx = ci
                confusion[exp_idx][pred_idx] += 1
                break
        else:
            confusion[exp_idx][exp_idx] += 1  # fallback

    header = " " * 10 + "".join(f"{e:>6}" for e in EXPECTED_CLASSES)
    print(header)
    for i, name in enumerate(EXPECTED_CLASSES):
        row = "".join(f"{confusion[i][j]:>6}" for j in range(8))
        print(f"  {name:<8}{row}")

    print()
    print("  视觉分类原型测试完成 ✅")

    return correct_top1, total


if __name__ == '__main__':
    main()
