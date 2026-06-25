#!/usr/bin/env python3
"""
修复视觉YLYW的评价基准：加入像素级相似度+笔画结构匹配

原来的纯统计特征（方向/粗细/曲直/重心）无法分辨字形好坏。
新方案：多尺度结构相似度(MS-SSIM) + 笔画骨架匹配
"""

import numpy as np
import cv2
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from stroke_ylyw import CalligraphyStrokeYLYW, StrokeGenerator
from visual_calligraphy import CalligraphyVisualYLYW
from mujoco_env import CalligraphyEnv
from learning_loop import load_copybook


def pixel_similarity(img1, img2):
    """基于像素的结构相似度（组合指标）"""
    # 确保尺寸一致
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    
    # 归一化到 [0,1]
    a = img1.astype(np.float32) / 255.0
    b = img2.astype(np.float32) / 255.0
    
    # 1. 像素重叠率（二值化后）
    _, ba = cv2.threshold(img1, 128, 1, cv2.THRESH_BINARY_INV)
    _, bb = cv2.threshold(img2, 128, 1, cv2.THRESH_BINARY_INV)
    intersection = (ba & bb).sum()
    union = (ba | bb).sum()
    iou = intersection / (union + 1e-6)
    
    # 2. 归一化互相关
    a_norm = (a - a.mean()) / (a.std() + 1e-6)
    b_norm = (b - b.mean()) / (b.std() + 1e-6)
    ncc = (a_norm * b_norm).mean()
    
    # 3. 梯度方向相似度（笔画方向匹配）
    gx1 = cv2.Sobel(img1, cv2.CV_32F, 1, 0, ksize=3)
    gy1 = cv2.Sobel(img1, cv2.CV_32F, 0, 1, ksize=3)
    gx2 = cv2.Sobel(img2, cv2.CV_32F, 1, 0, ksize=3)
    gy2 = cv2.Sobel(img2, cv2.CV_32F, 0, 1, ksize=3)
    mag1 = np.sqrt(gx1**2 + gy1**2)
    mag2 = np.sqrt(gx2**2 + gy2**2)
    mask = (mag1 > 5) & (mag2 > 5)
    if mask.sum() > 0:
        cos_sim = (gx1[mask]*gx2[mask] + gy1[mask]*gy2[mask]) / ((mag1[mask]*mag2[mask]) + 1e-6)
        grad_sim = np.clip(cos_sim.mean(), 0, 1)
    else:
        grad_sim = 0
    
    # 综合分数
    score = 0.3 * iou + 0.3 * max(0, ncc) + 0.4 * grad_sim
    return score, {'iou': iou, 'ncc': ncc, 'grad_sim': grad_sim}


def trajectory_to_image(trajectory, pressures, size=256, paper_half=0.15):
    """把轨迹直接渲染为图像（绕过MuJoCo+墨迹渲染）"""
    canvas = np.ones((size, size), dtype=np.uint8) * 255
    prev_x, prev_y = None, None
    
    for i in range(len(trajectory)):
        tx, ty = trajectory[i, 0], trajectory[i, 1]
        tp = pressures[i]
        if tp < 0.05:
            prev_x, prev_y = None, None
            continue
        
        px = int((tx + paper_half) / (2 * paper_half) * size)
        py = int((paper_half - ty) / (2 * paper_half) * size)
        px, py = np.clip(px, 0, size-1), np.clip(py, 0, size-1)
        
        if prev_x is not None:
            cv2.line(canvas, (prev_x, prev_y), (px, py), 0, max(1, int(tp * 4 + 1)))
        
        prev_x, prev_y = px, py
    
    return canvas


def main():
    char = '大'
    print(f"=== 视觉评价对比 — 「{char}」===\n")
    
    # 字帖
    target = load_copybook(char)
    
    # YLYW 生成轨迹
    visual = CalligraphyVisualYLYW()
    p = visual.perceive(target)
    stroke_ylyw = CalligraphyStrokeYLYW()
    plan = stroke_ylyw.plan_character(char, p.trigram_memberships, p.yao_features,
        extra_params={'stroke_curve_factor': 0, 'jitter_amplitude': 0})
    traj, press = stroke_ylyw.get_trajectory_sequence(plan)
    
    # 渲染轨迹图
    traj_img = trajectory_to_image(traj, press)
    
    # 原始 YLYW 视觉评价
    p_original = visual.perceive(traj_img)
    print(f"【原始 YLYW 视觉评价】")
    print(f"  卦象: {p_original.hexagram_name}, 主导: {p_original.dominant_trigram}")
    print(f"  六爻: {p_original.yao_features}")
    print(f"  与字帖的卦象距离: {np.sqrt(np.sum((p_original.yao_features - p.yao_features)**2)):.3f}")
    
    # 新像素级评价
    score, details = pixel_similarity(target, traj_img)
    print(f"\n【像素级评价】")
    print(f"  综合分: {score:.3f}")
    print(f"  IoU: {details['iou']:.3f}")
    print(f"  NCC: {details['ncc']:.3f}")
    print(f"  梯度相似: {details['grad_sim']:.3f}")
    
    # 对比：好字 vs 坏字
    print(f"\n【对比测试】")
    # 生成一个"坏字"（加乱扰动）
    bad_plan = stroke_ylyw.plan_character(char, p.trigram_memberships, p.yao_features,
        extra_params={'stroke_angle_correction': 0.15, 'stroke_curve_factor': 3.0, 
                      'jitter_amplitude': 0.01, 'stroke_width_factor': 2.0})
    bad_traj, bad_press = stroke_ylyw.get_trajectory_sequence(bad_plan)
    bad_img = trajectory_to_image(bad_traj, bad_press)
    
    score_good, _ = pixel_similarity(target, traj_img)
    score_bad, _ = pixel_similarity(target, bad_img)
    p_bad_old = visual.perceive(bad_img)
    dist_old = np.sqrt(np.sum((p_bad_old.yao_features - p.yao_features)**2))
    
    print(f"  好字: 像素分={score_good:.3f}, YLYW距离={np.sqrt(np.sum((p_original.yao_features-p.yao_features)**2)):.3f}")
    print(f"  坏字: 像素分={score_bad:.3f}, YLYW距离={dist_old:.3f}")
    
    if score_good > score_bad and dist_old < 0.15:
        print(f"  ⚠️ YLYW给乱字也高分——评价基准有待改进")
    elif score_good > score_bad:
        print(f"  ✓ 区分度正常")
    
    # 保存
    cv2.imwrite('output/debug_traj_direct.png', traj_img)
    cv2.imwrite('output/debug_traj_bad.png', bad_img)
    print(f"\n图片已保存: output/debug_traj_direct.png / bad.png")
    
    return score, details


if __name__ == '__main__':
    main()
