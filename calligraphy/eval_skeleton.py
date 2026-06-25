#!/usr/bin/env python3
"""
YLYW 书法系统 — 骨架级视觉评价子系统

用骨架级比较替代统计特征比较，让评价真正反映「字形好不好」。

流程:
  1. 输入两张 256x256 灰度图（字帖 + 书写结果）
  2. 笔画宽度归一化 → Zhang-Suen 骨架细化 → 两幅单像素骨架
  3. 计算骨架间的倒角距离 (Chamfer Distance) 和骨架重叠率
  4. 输出 0~1 的相似度分数

  最终分数 = 0.5 * (1 - chamfer_norm) + 0.5 * overlap  — 越高越好

定位:
  - 这个分数替代原有的卦象距离作为知几学习的目标函数
  - 原有的六爻特征提取保留用于知几诊断（告诉你"哪出了问题"）
  - 但优化方向由骨架相似度决定

笔画宽度归一化:
  不同渲染管线（MuJoCo/轨迹直接/扫描件等）产生的墨迹粗细不一致。
  归一化通过距离变换找到中轴，再膨胀到统一宽度，确保骨架比较不受粗细影响。
"""

import numpy as np
import cv2
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from pathlib import Path


# ============================================================
# Zhang-Suen 骨架细化
# ============================================================

def thin_zhang_suen(binary: np.ndarray, max_iters: int = 200) -> np.ndarray:
    """
    Zhang-Suen 骨架细化算法，输出单像素宽度骨架。

    Args:
        binary: 二值图，前景=255，背景=0
        max_iters: 最大迭代次数

    Returns:
        二值骨架图，前景=255
    """
    skel = (binary > 0).astype(np.uint8)
    h, w = skel.shape

    for _ in range(max_iters):
        to_del = []

        # ---- 子迭代 1 ----
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x] == 0:
                    continue
                # 8邻域 P2..P9 顺序
                p2 = skel[y - 1, x]
                p3 = skel[y - 1, x + 1]
                p4 = skel[y,     x + 1]
                p5 = skel[y + 1, x + 1]
                p6 = skel[y + 1, x]
                p7 = skel[y + 1, x - 1]
                p8 = skel[y,     x - 1]
                p9 = skel[y - 1, x - 1]
                neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]

                b = sum(neighbors)
                if b < 2 or b > 6:
                    continue
                a = sum(1 for i in range(8)
                        if neighbors[i] == 0 and neighbors[(i + 1) % 8] == 1)
                if a != 1:
                    continue
                if p2 * p4 * p6 != 0 or p4 * p6 * p8 != 0:
                    continue
                to_del.append((y, x))

        for y, x in to_del:
            skel[y, x] = 0
        if not to_del:
            break

        to_del = []

        # ---- 子迭代 2 ----
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if skel[y, x] == 0:
                    continue
                p2 = skel[y - 1, x]
                p3 = skel[y - 1, x + 1]
                p4 = skel[y,     x + 1]
                p5 = skel[y + 1, x + 1]
                p6 = skel[y + 1, x]
                p7 = skel[y + 1, x - 1]
                p8 = skel[y,     x - 1]
                p9 = skel[y - 1, x - 1]
                neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]

                b = sum(neighbors)
                if b < 2 or b > 6:
                    continue
                a = sum(1 for i in range(8)
                        if neighbors[i] == 0 and neighbors[(i + 1) % 8] == 1)
                if a != 1:
                    continue
                if p2 * p4 * p8 != 0 or p2 * p6 * p8 != 0:
                    continue
                to_del.append((y, x))

        for y, x in to_del:
            skel[y, x] = 0
        if not to_del:
            break

    return (skel * 255).astype(np.uint8)


# ============================================================
# 笔画宽度归一化
# ============================================================

def normalize_stroke_width(binary: np.ndarray,
                           target_radius: int = 2) -> np.ndarray:
    """
    归一化笔画宽度，使粗细不同的图像产生可比较的骨架。

    方法:
      距离变换 → 提取局部极大值（中轴）→ 膨胀到目标半径

    这样不管原图笔画厚薄，最终骨架结构一致。

    Args:
        binary: 二值图，前景=255
        target_radius: 中轴膨胀半径（像素）

    Returns:
        宽度归一化后的二值图
    """
    if binary.sum() < 10:
        return binary

    # 距离变换
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)

    # 提取中轴：距离值等于 3x3 邻域最大值 且在前景内
    kernel = np.ones((3, 3), dtype=np.uint8)
    dilated = cv2.dilate(dist, kernel)
    medial = (dist == dilated) & (binary > 0)
    medial_axis = (medial.astype(np.uint8) * 255)

    if medial.sum() < 3:
        return binary  # 回退

    # 从中轴膨胀到目标宽度
    if target_radius > 0:
        ks = 2 * target_radius + 1
        dk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks))
        return cv2.dilate(medial_axis, dk)

    return medial_axis


# ============================================================
# 图像 → 骨架 流水线
# ============================================================

def get_skeleton(img: np.ndarray,
                 size: int = 256,
                 threshold: int = 128,
                 normalize_width: bool = True,
                 min_area: int = 50) -> np.ndarray:
    """
    从输入图像提取单像素骨架。

    流水线:
      resize → 灰度 → 二值化 → 去噪 → 宽度归一化 → 细化

    Args:
        img: 输入图像（灰度或RGB）
        size: 统一输出尺寸
        threshold: 二值化阈值
        normalize_width: 是否进行笔画宽度归一化
        min_area: 最小连通域面积

    Returns:
        骨架图（前景=255）
    """
    # 转灰度
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    if gray.shape[:2] != (size, size):
        gray = cv2.resize(gray, (size, size))

    # 二值化（墨迹=暗→反转成前景白）
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)

    # 闭运算连接断线
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # 去小连通域
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    clean = np.zeros_like(binary)
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            clean[labels == i] = 255
    binary = clean

    # 确保前景 < 背景
    if binary.sum() > binary.size * 0.5:
        binary = 255 - binary

    # 笔画宽度归一化
    if normalize_width and binary.sum() > 0:
        binary = normalize_stroke_width(binary, target_radius=1)

    # 细化
    skeleton = thin_zhang_suen(binary)
    if skeleton.sum() == 0:
        return binary  # 回退

    return skeleton


# ============================================================
# 倒角距离
# ============================================================

def chamfer_distance(skel_a: np.ndarray, skel_b: np.ndarray) -> float:
    """
    双向对称倒角距离。

    CD(A,B) = mean_{p in A} d(p, B)
    CD(B,A) = mean_{p in B} d(p, A)
    对称 CD = (CD_AB + CD_BA) / 2

    Args:
        skel_a, skel_b: 骨架图（前景=255）

    Returns:
        对称倒角距离（像素单位），inf 表示无骨架
    """
    pts_a = np.argwhere(skel_a > 0)  # (N, 2) [y, x]
    pts_b = np.argwhere(skel_b > 0)

    if len(pts_a) == 0 or len(pts_b) == 0:
        return float('inf')

    # 用距离变换加速 A→B
    dist_map_b = cv2.distanceTransform(
        (skel_b == 0).astype(np.uint8) * 255,
        cv2.DIST_L2, cv2.DIST_MASK_PRECISE
    )
    cd_ab = float(dist_map_b[pts_a[:, 0], pts_a[:, 1]].mean())

    # B→A
    dist_map_a = cv2.distanceTransform(
        (skel_a == 0).astype(np.uint8) * 255,
        cv2.DIST_L2, cv2.DIST_MASK_PRECISE
    )
    cd_ba = float(dist_map_a[pts_b[:, 0], pts_b[:, 1]].mean())

    return (cd_ab + cd_ba) / 2.0


# ============================================================
# 骨架重叠率
# ============================================================

def skeleton_overlap(skel_a: np.ndarray, skel_b: np.ndarray,
                     dilate_radius: int = 3) -> float:
    """
    骨架A的像素中，有多少比例落在骨架B的膨胀区域内。

    Args:
        skel_a, skel_b: 骨架图（前景=255）
        dilate_radius: 膨胀半径

    Returns:
        重叠率 [0, 1]
    """
    n_a = int((skel_a > 0).sum())
    if n_a == 0:
        return 0.0

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (2 * dilate_radius + 1, 2 * dilate_radius + 1)
    )
    dilated_b = cv2.dilate(skel_b, kernel)
    overlap = int(((skel_a > 0) & (dilated_b > 0)).sum())

    return float(overlap) / float(n_a)


# ============================================================
# 综合评价
# ============================================================

@dataclass
class SkeletonEvalResult:
    """骨架评价结果"""
    score: float              # 综合相似度 [0, 1]
    chamfer: float            # 倒角距离（像素）
    chamfer_norm: float       # 归一化倒角距离 [0, 1]
    overlap: float            # 骨架重叠率
    n_pts_a: int              # 骨架A点数
    n_pts_b: int              # 骨架B点数


def evaluate_similarity(img_target: np.ndarray,
                        img_result: np.ndarray,
                        image_size: int = 256,
                        dilate_radius: int = 3,
                        chamfer_max: float = 100.0,
                        normalize_width: bool = True,
                        verbose: bool = True) -> SkeletonEvalResult:
    """
    评估书写结果与字帖的骨架相似度。

    Args:
        img_target: 字帖图像
        img_result: 书写结果图像
        image_size: 统一处理尺寸
        dilate_radius: 骨架膨胀半径
        chamfer_max: 倒角距离归一化上限（像素）
        normalize_width: 是否归一化笔画宽度
        verbose: 打印详细信息

    Returns:
        SkeletonEvalResult
    """
    # Step 1: 提取骨架
    skel_target = get_skeleton(img_target, size=image_size,
                               normalize_width=normalize_width)
    skel_result = get_skeleton(img_result, size=image_size,
                               normalize_width=normalize_width)

    n_a = int((skel_target > 0).sum())
    n_b = int((skel_result > 0).sum())

    # Step 2: 倒角距离
    chamf = chamfer_distance(skel_target, skel_result)
    chamf_norm = min(1.0, chamf / chamfer_max)

    # Step 3: 重叠率
    overlap = skeleton_overlap(skel_target, skel_result, dilate_radius)

    # Step 4: 综合分 = 0.5*(1-chamfer_norm) + 0.5*overlap
    score = 0.5 * (1.0 - chamf_norm) + 0.5 * overlap
    score = max(0.0, min(1.0, score))

    result = SkeletonEvalResult(
        score=score,
        chamfer=chamf,
        chamfer_norm=chamf_norm,
        overlap=overlap,
        n_pts_a=n_a,
        n_pts_b=n_b,
    )

    if verbose:
        print(f"  骨架相似度: {score:.4f}")
        print(f"    倒角距离: {chamf:.1f}px (归一化={chamf_norm:.4f})")
        print(f"    骨架重叠: {overlap:.4f}")
        print(f"    骨架点数: 字帖={n_a}, 书写={n_b}")

    return result


# ============================================================
# 可视化
# ============================================================

def visualize_skeletons(img_target: np.ndarray,
                        img_result: np.ndarray,
                        normalize_width: bool = True,
                        save_path: Optional[str] = None) -> np.ndarray:
    """生成骨架对比图：字帖骨架 | 书写骨架 | 重叠叠加"""
    skel_t = get_skeleton(img_target, normalize_width=normalize_width)
    skel_r = get_skeleton(img_result, normalize_width=normalize_width)

    h, w = 256, 256

    # 三色叠加：红=字帖，蓝=书写，紫=重叠
    overlay = np.zeros((h, w, 3), dtype=np.uint8)
    overlay[:, :, 2] = (skel_t > 0).astype(np.uint8) * 200  # 红
    overlay[:, :, 0] = (skel_r > 0).astype(np.uint8) * 200  # 蓝

    left = cv2.cvtColor(skel_t, cv2.COLOR_GRAY2BGR)
    mid = cv2.cvtColor(skel_r, cv2.COLOR_GRAY2BGR)
    combined = np.hstack([left, mid, overlay])

    if save_path:
        cv2.imwrite(save_path, combined)

    return combined


# ============================================================
# 测试主程序
# ============================================================

def main():
    output_dir = Path(__file__).parent / 'output'

    print(f"\n{'='*60}")
    print(f"  YLYW 骨架级视觉评价 — 测试")
    print(f"{'='*60}")

    # ================================================================
    # Test 1: 干净测试（验证算法本身正确）
    # ================================================================
    print(f"\n{'─'*40}")
    print(f"  测试 1：干净测试（验证算法）")
    print(f"{'─'*40}")

    target = cv2.imread(
        str(Path(__file__).parent / 'input' / 'copybook' / '大_楷体.png'),
        cv2.IMREAD_GRAYSCALE
    )

    # 好字：轻微仿射
    M_good = cv2.getRotationMatrix2D((128, 128), 2, 1.0)
    good = cv2.warpAffine(target, M_good, (256, 256), borderValue=255)

    # 坏字：大幅仿射
    M_bad = cv2.getRotationMatrix2D((128, 128), 15, 0.8)
    bad = cv2.warpAffine(target, M_bad, (256, 256), borderValue=255)

    r_good = evaluate_similarity(target, good, verbose=True)
    print()
    r_bad = evaluate_similarity(target, bad, verbose=True)

    print(f"\n  好字分: {r_good.score:.4f}  |  坏字分: {r_bad.score:.4f}  "
          f"|  差值: {r_good.score - r_bad.score:+.4f}")
    print(f"  {'✅ 通过' if r_good.score > r_bad.score + 0.05 else '❌ 失败'}")

    # ================================================================
    # Test 2: 轨迹渲染测试（实际场景）
    # ================================================================
    print(f"\n{'─'*40}")
    print(f"  测试 2：轨迹渲染场景")
    print(f"{'─'*40}")

    good_path = output_dir / 'debug_traj_direct.png'
    bad_path = output_dir / 'debug_traj_bad.png'

    if not good_path.exists() or not bad_path.exists():
        print("  ⚠️  未找到 debug_traj_direct.png / debug_traj_bad.png")
        print("  请先运行 eval_fix.py 生成轨迹测试图像")
    else:
        good_img = cv2.imread(str(good_path), cv2.IMREAD_GRAYSCALE)
        bad_img = cv2.imread(str(bad_path), cv2.IMREAD_GRAYSCALE)

        if good_img is None or bad_img is None:
            print("  ❌ 无法加载图像")
        else:
            # 带宽度归一化
            print("  【宽度归一化 ON】")
            r_good2 = evaluate_similarity(target, good_img,
                                          normalize_width=True, verbose=True)
            print()
            r_bad2 = evaluate_similarity(target, bad_img,
                                         normalize_width=True, verbose=True)

            print(f"\n  好字分: {r_good2.score:.4f}  |  坏字分: {r_bad2.score:.4f}  "
                  f"|  差值: {r_good2.score - r_bad2.score:+.4f}")

            if r_good2.score > r_bad2.score:
                print(f"  ✅ 骨架评价区分成功")
            else:
                print(f"  ⚠️  轨迹渲染的'好字'骨架与字帖偏差大于'坏字'")
                print(f"      字帖骨架={r_good2.n_pts_a}点, "
                      f"好字骨架={r_good2.n_pts_b}点, "
                      f"坏字骨架={r_bad2.n_pts_b}点")
                print(f"      提示：轨迹渲染管线可能导致好字笔画过细/偏移")

    # ================================================================
    # Test 3: 对比旧评价系统
    # ================================================================
    print(f"\n{'─'*40}")
    print(f"  测试 3：对比旧评价系统")
    print(f"{'─'*40}")

    try:
        from visual_calligraphy import CalligraphyVisualYLYW
        visual = CalligraphyVisualYLYW()
        p_target = visual.perceive(target)
        p_good = visual.perceive(good)
        p_bad = visual.perceive(bad)

        comp_good = visual.compare(p_target, p_good)
        comp_bad = visual.compare(p_target, p_bad)

        d_good = comp_good['total_yao_distance']
        d_bad = comp_bad['total_yao_distance']

        print(f"  旧卦象距离 — 好: {d_good:.4f}, 坏: {d_bad:.4f}")
        if d_good < d_bad:
            print(f"  ✅ 旧系统也能区分")
        else:
            print(f"  ⚠️  旧系统无法区分（好字距离≥坏字）→ 骨架评价解决了这个问题")
    except Exception as e:
        print(f"  (跳过: {e})")

    # ================================================================
    # 可视化保存
    # ================================================================
    vis = visualize_skeletons(
        target, good,
        save_path=str(output_dir / 'skeleton_compare_good.png')
    )
    vis_b = visualize_skeletons(
        target, bad,
        save_path=str(output_dir / 'skeleton_compare_bad.png')
    )
    print(f"\n📊 骨架对比图: {output_dir}/skeleton_compare_*.png")

    return r_good, r_bad


if __name__ == '__main__':
    main()
