"""
视觉书法YLYW (Visual Calligraphy YLYW) — 观帖模块

从字帖图像中提取笔画结构特征，输出"结构卦象"。
这相当于书法家的"读帖"能力——看到一个字，理解其结构。

架构：
- 笔画结构特征提取（12维 → 6爻）
- 八卦视觉基元复用（升级到书法领域语义）
- 六十四卦匹配（从抓取域映射到笔画结构域）

创新点：
- 将笔画方向场映射到"八卦笔法原型"
- 将间架结构映射到"乘承比应"空间关系
- 将重心/疏密等全局特征映射到"当位得中"

输入：字帖图像（灰度图）
输出：结构卦象 + 笔画分析报告
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# ============================================================
# 12维笔画结构特征定义
# ============================================================

FEATURE_NAMES = [
    'stroke_directionality',    # 初爻: 笔画方向主导度
    'stroke_thickness_contrast', # 二爻: 粗细对比度
    'curvature_complexity',      # 三爻: 曲直复杂度
    'structure_regularity',      # 四爻: 间架规整度
    'center_of_mass_x',          # 五爻: 重心横向位置
    'center_of_mass_y',          # 上爻: 重心纵向位置
    'stroke_density',            # 附加: 笔画密度
    'top_bottom_balance',        # 附加: 上下均衡
    'left_right_balance',        # 附加: 左右均衡
    'enclosure_ratio',           # 附加: 包围比例
    'corner_density',            # 附加: 折角密度
    'smoothness',                # 附加: 整体流畅度
]


# ============================================================
# 书法视觉八卦原型
# ============================================================
# 
# 八卦在书法域的语义映射：
# 
#   乾 ☰ → 刚健 → 横平竖直、方正结构（如"田""国"）
#   坤 ☷ → 柔顺 → 圆转流畅、均匀分布（如"永""水"）
#   震 ☳ → 动态 → 撇捺张扬、有明显方向性（如"人""大"）
#   艮 ☶ → 静止 → 紧凑收敛、重心沉稳（如"山""石"）
#   离 ☲ → 明亮 → 疏朗通透、笔画分明（如"日""月"）
#   坎 ☵ → 险陷 → 内收外张、有包围感（如"风""飞"）
#   兑 ☱ → 悦 → 短小精悍、轻灵跳跃（如"口""小"）
#   巽 ☴ → 入 → 纵长绵密、上下贯通（如"身""耳"）

class CalligraphyTrigramBase:
    """书法视觉八卦基元"""

    def __init__(self):
        # 书法域八卦原型（6维：方向主导度/粗细对比/曲直复杂度/间架规整度/重心x/重心y）
        self.prototypes = {
            '乾': {
                'prototype': np.array([0.90, 0.10, 0.05, 0.90, 0.50, 0.50], dtype=np.float32),
                'desc': '刚健方正：横平竖直，结构规整',
                'canonical_chars': '田国正回',
            },
            '坤': {
                'prototype': np.array([0.10, 0.50, 0.70, 0.40, 0.50, 0.50], dtype=np.float32),
                'desc': '柔顺圆转：曲线流畅，均匀布局',
                'canonical_chars': '永水心云',
            },
            '震': {
                'prototype': np.array([0.90, 0.80, 0.40, 0.30, 0.50, 0.40], dtype=np.float32),
                'desc': '动态张扬：撇捺舒展，重心上提',
                'canonical_chars': '人大春今',
            },
            '艮': {
                'prototype': np.array([0.40, 0.60, 0.20, 0.70, 0.50, 0.70], dtype=np.float32),
                'desc': '沉稳收敛：结构紧凑，重心偏下',
                'canonical_chars': '山石土止',
            },
            '离': {
                'prototype': np.array([0.20, 0.20, 0.30, 0.60, 0.50, 0.50], dtype=np.float32),
                'desc': '疏朗通透：笔画分明，均匀疏朗',
                'canonical_chars': '日月门四',
            },
            '坎': {
                'prototype': np.array([0.50, 0.40, 0.60, 0.30, 0.50, 0.50], dtype=np.float32),
                'desc': '险陷包裹：内收外张，有包围',
                'canonical_chars': '风飞国周',
            },
            '兑': {
                'prototype': np.array([0.30, 0.30, 0.40, 0.60, 0.50, 0.50], dtype=np.float32),
                'desc': '轻灵小巧：短笔画多，结构紧凑',
                'canonical_chars': '口小吕品',
            },
            '巽': {
                'prototype': np.array([0.60, 0.20, 0.50, 0.40, 0.50, 0.50], dtype=np.float32),
                'desc': '纵长绵密：上下贯通，细密匀称',
                'canonical_chars': '身耳自目',
            },
        }

    def get_memberships(self, feature_vec: np.ndarray) -> Dict[str, float]:
        """计算对8个卦象的隶属度"""
        memberships = {}
        for name, info in self.prototypes.items():
            dist = np.sum((feature_vec - info['prototype']) ** 2)
            membership = np.exp(-0.8 * dist)
            memberships[name] = float(np.clip(membership, 0.0, 1.0))
        return memberships

    def get_dominant(self, feature_vec: np.ndarray) -> Tuple[str, float, str]:
        """获取主导卦象"""
        memberships = self.get_memberships(feature_vec)
        best_name = max(memberships, key=memberships.get)
        return best_name, memberships[best_name], self.prototypes[best_name]['desc']


# ============================================================
# 笔画结构特征提取器
# ============================================================

class StrokeStructureExtractor:
    """
    从字帖/书写结果图像中提取12维笔画结构特征。

    特征分两组：
    - 前6维 → 映射为六爻（结构卦象）
    - 后6维 → 用于精细对比分析

    所有特征归一化到 [0, 1]
    """

    def __init__(self, image_size: int = 256):
        self.image_size = image_size
        self._last_debug = {}

    def extract(self, image: np.ndarray) -> Dict[str, float]:
        """
        从图像中提取笔画结构特征

        Args:
            image: 灰度图或RGB图

        Returns:
            dict: 12维特征字典
        """
        # 转灰度
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 确保尺寸一致
        if gray.shape[0] != self.image_size:
            gray = cv2.resize(gray, (self.image_size, self.image_size))

        gray_f = gray.astype(np.float32)

        # 反转：墨迹(暗)→前景(亮)，便于后续处理
        foreground = 255.0 - gray_f

        features = {}

        # --- 基础特征 ---
        features.update(self._extract_basic(gray_f, foreground))

        # --- 方向特征 ---
        features.update(self._extract_directional(gray_f, foreground))

        # --- 结构特征 ---
        features.update(self._extract_structural(gray_f, foreground))

        self._last_debug = features
        return features

    def _extract_basic(self, gray: np.ndarray, fg: np.ndarray) -> Dict[str, float]:
        """提取基础特征"""
        h, w = gray.shape

        # 笔画密度（前景像素占比）
        fg_mask = fg > 30  # 墨迹阈值
        stroke_density = float(np.clip(fg_mask.sum() / (h * w) * 3.0, 0, 1))

        # 粗细对比度（笔画宽度分布的方差）
        # 用距离变换近似笔画宽度
        dist = cv2.distanceTransform((fg_mask * 255).astype(np.uint8),
                                      cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        valid = dist[fg_mask]
        if len(valid) > 0:
            thickness_contrast = float(np.clip(np.std(valid) / (np.mean(valid) + 1e-6) / 3, 0, 1))
        else:
            thickness_contrast = 0.0

        # 折角密度（Harris角点检测）
        # 墨迹的二值化图像做角点
        bin_img = (fg > 30).astype(np.float32)
        corners = cv2.cornerHarris(bin_img, 5, 3, 0.04)
        corner_mask = corners > 0.01 * corners.max()
        corner_density = float(np.clip(corner_mask.sum() / (h * w) * 200, 0, 1))

        # 整体流畅度（梯度一致性）
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx**2 + gy**2)
        grad_mask = grad_mag > 10
        if grad_mask.sum() > 0:
            # 梯度方向的集中度（高度集中=流畅）
            grad_dir = np.arctan2(gy, gx)
            dir_hist = np.histogram(grad_dir[grad_mask] % np.pi, bins=8, range=(0, np.pi))[0]
            smoothness = float(np.clip(dir_hist.max() / dir_hist.sum() * 2, 0, 1))
        else:
            smoothness = 0.0

        # 包围比例（封闭轮廓）
        contours, _ = cv2.findContours((fg > 30).astype(np.uint8),
                                        cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        enclosure_ratio = 0.0
        if contours:
            total_area = h * w
            for cnt in contours:
                if len(cnt) > 10:
                    area = cv2.contourArea(cnt)
                    hull = cv2.convexHull(cnt)
                    hull_area = cv2.contourArea(hull)
                    if hull_area > 0:
                        enclosure_ratio += (hull_area - area) / hull_area
            enclosure_ratio = float(np.clip(enclosure_ratio / max(1, len(contours)), 0, 1))

        return {
            'stroke_density': stroke_density,
            'stroke_thickness_contrast': thickness_contrast,
            'corner_density': corner_density,
            'smoothness': smoothness,
            'enclosure_ratio': enclosure_ratio,
        }

    def _extract_directional(self, gray: np.ndarray, fg: np.ndarray) -> Dict[str, float]:
        """提取方向性特征"""
        h, w = gray.shape

        # 笔画方向主导度（Gabor响应方向集中度）
        gabor_energies = []
        gabor_kernels = []
        for theta in [0, np.pi/6, np.pi/3, np.pi/2, 2*np.pi/3, 5*np.pi/6]:
            for sigma in [4.0, 8.0]:
                ksize = int(6 * sigma) | 1
                k = cv2.getGaborKernel((min(ksize, 31), min(ksize, 31)),
                                       sigma, theta, sigma*2.5, 0.5, 0, cv2.CV_32F)
                gabor_kernels.append((theta, k))
                resp = cv2.filter2D(fg, cv2.CV_32F, k)
                gabor_energies.append(float(np.mean(np.abs(resp))))

        # 按方向分组
        dir_energies = {}
        for (theta, _), e in zip(gabor_kernels, gabor_energies):
            dir_key = int(theta / (np.pi/6) + 0.5) % 6
            dir_energies[dir_key] = dir_energies.get(dir_key, 0) + e

        energies = np.array(list(dir_energies.values()))
        if energies.max() > 0:
            sorted_e = np.sort(energies)
            directionality = float(np.clip((sorted_e[-1] - sorted_e[-2]) / (energies.mean() + 1e-6), 0, 1))
        else:
            directionality = 0.0

        # 左右均衡
        left_fg = fg[:, :w//2].sum() / 255
        right_fg = fg[:, w//2:].sum() / 255
        total_fg = left_fg + right_fg
        left_right_balance = float(1.0 - abs(left_fg - right_fg) / (total_fg + 1e-6))

        # 上下均衡
        top_fg = fg[:h//2, :].sum() / 255
        bottom_fg = fg[h//2:, :].sum() / 255
        total_fg = top_fg + bottom_fg
        top_bottom_balance = float(1.0 - abs(top_fg - bottom_fg) / (total_fg + 1e-6))

        return {
            'stroke_directionality': directionality,
            'left_right_balance': left_right_balance,
            'top_bottom_balance': top_bottom_balance,
        }

    def _extract_structural(self, gray: np.ndarray, fg: np.ndarray) -> Dict[str, float]:
        """提取结构特征"""
        h, w = gray.shape

        # 重心位置
        y_coords, x_coords = np.where(fg > 30)
        if len(x_coords) > 0:
            com_x = float(np.clip(x_coords.mean() / w, 0, 1))
            com_y = float(np.clip(y_coords.mean() / h, 0, 1))
        else:
            com_x = 0.5
            com_y = 0.5

        # 曲直复杂度（等高线的曲率变化）
        edges = cv2.Canny(gray.astype(np.uint8), 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        curvature_complexity = 0.0
        if contours:
            total_curvature = 0
            total_len = 0
            for cnt in contours:
                if len(cnt) > 10:
                    # 近似曲率：方向变化率
                    pts = cnt[:, 0, :].astype(np.float32)
                    for i in range(1, len(pts)-1):
                        v1 = pts[i] - pts[i-1]
                        v2 = pts[i+1] - pts[i]
                        n1 = np.linalg.norm(v1)
                        n2 = np.linalg.norm(v2)
                        if n1 > 0 and n2 > 0:
                            cos_angle = np.dot(v1, v2) / (n1 * n2)
                            cos_angle = np.clip(cos_angle, -1, 1)
                            angle_change = np.arccos(cos_angle)
                            total_curvature += angle_change
                            total_len += 1
            if total_len > 0:
                avg_curvature = total_curvature / total_len
                curvature_complexity = float(np.clip(avg_curvature / np.pi, 0, 1))

        # 间架规整度（矩形的规整程度）
        fg_mask = (fg > 30).astype(np.uint8)
        moments = cv2.moments(fg_mask)
        if moments['m00'] > 0:
            # 用Hu矩的不变性来度量规整度
            hu = cv2.HuMoments(moments)
            # 第2个Hu矩描述形状的紧凑度
            regularity = float(np.clip(1.0 - abs(np.log(abs(hu[1][0]) + 1e-6)) / 3, 0, 1))
        else:
            regularity = 0.5

        return {
            'center_of_mass_x': com_x,
            'center_of_mass_y': com_y,
            'curvature_complexity': curvature_complexity,
            'structure_regularity': regularity,
        }

    def get_yao_features(self, features: Dict[str, float]) -> np.ndarray:
        """
        从12维特征中提取6维六爻特征向量，用于卦象匹配

        六爻映射：
            初爻: stroke_directionality
            二爻: stroke_thickness_contrast
            三爻: curvature_complexity
            四爻: structure_regularity
            五爻: center_of_mass_x
            上爻: center_of_mass_y
        """
        yao_feats = np.array([
            features.get('stroke_directionality', 0.5),
            features.get('stroke_thickness_contrast', 0.5),
            features.get('curvature_complexity', 0.5),
            features.get('structure_regularity', 0.5),
            features.get('center_of_mass_x', 0.5),
            features.get('center_of_mass_y', 0.5),
        ], dtype=np.float32)
        return yao_feats


# ============================================================
# 书法视觉YLYW主类
# ============================================================

@dataclass
class CalligraphyPerception:
    """书法视觉YLYW的感知结果"""
    image: np.ndarray                              # 输入图像
    features: Dict[str, float]                     # 12维特征
    yao_features: np.ndarray                       # 6维六爻特征
    trigram_memberships: Dict[str, float]          # 8卦隶属度
    dominant_trigram: str                          # 主导卦象
    dominant_score: float                          # 主导卦隶属度
    trigram_desc: str                              # 卦象描述
    hexagram_name: str                             # 六十四卦名（通过卦象匹配）
    hexagram_number: int                           # 卦序号


class CalligraphyVisualYLYW:
    """
    书法视觉YLYW系统

    功能：
    1. 读帖：分析字帖图像，提取笔画结构
    2. 卦象映射：笔画结构 → 八卦隶属度 → 六十四卦
    3. 对比分析：字帖卦象 vs 书写结果卦象 → 差异向量
    """

    def __init__(self):
        self.extractor = StrokeStructureExtractor(image_size=256)
        self.trigram_base = CalligraphyTrigramBase()

    def perceive(self, image: np.ndarray, verbose: bool = False) -> CalligraphyPerception:
        """
        分析字帖/书写结果图像

        Args:
            image: 图像 (灰度或RGB)
            verbose: 是否打印分析过程

        Returns:
            CalligraphyPerception: 完整感知结果
        """
        # Step 1: 笔画结构特征提取
        features = self.extractor.extract(image)
        yao_features = self.extractor.get_yao_features(features)

        # Step 2: 八卦隶属度
        trigram_memberships = self.trigram_base.get_memberships(yao_features)
        trigram_name, trigram_score, trigram_desc = self.trigram_base.get_dominant(yao_features)

        # Step 3: 六十四卦匹配（简化版：基于八卦隶属度）
        # 这里用八卦隶属度向量做六十四卦的近似匹配
        hexagram_name, hexagram_number = self._match_hexagram(trigram_memberships)

        if verbose:
            print("\n" + "=" * 60)
            print("[YLYW书法视觉] 结构卦象分析")
            print("=" * 60)
            print(f"\n  12维笔画结构特征:")
            for k, v in features.items():
                print(f"    {k:30s}: {v:.3f}")
            print(f"\n  六爻特征向量: {yao_features}")
            print(f"\n  八卦隶属度:")
            sorted_tri = sorted(trigram_memberships.items(), key=lambda x: -x[1])
            for name, score in sorted_tri:
                bar = '█' * int(score * 20)
                print(f"    {name}: {score:.3f} {bar}")
            print(f"\n  ★ 主导卦象: {trigram_name} ({trigram_desc}) - 隶属度 {trigram_score:.3f}")
            print(f"  ★ 六十四卦: {hexagram_name} (#{hexagram_number})")

        return CalligraphyPerception(
            image=image,
            features=features,
            yao_features=yao_features,
            trigram_memberships=trigram_memberships,
            dominant_trigram=trigram_name,
            dominant_score=trigram_score,
            trigram_desc=trigram_desc,
            hexagram_name=hexagram_name,
            hexagram_number=hexagram_number,
        )

    def _match_hexagram(self, trigram_memberships: Dict[str, float]) -> Tuple[str, int]:
        """
        基于八卦隶属度匹配六十四卦。

        简化近似：取隶属度最高的两个卦组成上下卦
        （实际YLYW中应该用完整的64卦爻模板匹配）
        """
        sorted_tri = sorted(trigram_memberships.items(), key=lambda x: -x[1])

        # 取top-2作为上下卦，参考现有YLYW的六十四卦名
        upper_names = {'乾': '乾', '坤': '坤', '震': '震', '艮': '艮',
                       '离': '离', '坎': '坎', '兑': '兑', '巽': '巽'}
        upper = sorted_tri[0][0]
        lower = sorted_tri[1][0]

        # 简单的卦名拼接
        hexagram_mapping = {
            ('乾', '乾'): ('乾为天', 1),
            ('乾', '震'): ('天雷无妄', 25),
            ('乾', '艮'): ('天山遁', 33),
            ('乾', '离'): ('天火同人', 13),
            ('乾', '坎'): ('天水讼', 6),
            ('乾', '兑'): ('天泽履', 10),
            ('乾', '巽'): ('天风姤', 44),
            ('坤', '乾'): ('地天泰', 11),
            ('坤', '坤'): ('坤为地', 2),
            ('坤', '震'): ('地雷复', 24),
            ('坤', '艮'): ('地山谦', 15),
            ('坤', '离'): ('地火明夷', 36),
            ('坤', '坎'): ('地水师', 7),
            ('坤', '兑'): ('地泽临', 19),
            ('坤', '巽'): ('地风升', 46),
            ('震', '乾'): ('雷天大壮', 34),
            ('震', '坤'): ('雷地豫', 16),
            ('震', '震'): ('震为雷', 51),
            ('震', '艮'): ('雷山小过', 62),
            ('震', '离'): ('雷火丰', 55),
            ('震', '坎'): ('雷水解', 40),
            ('震', '兑'): ('雷泽归妹', 54),
            ('震', '巽'): ('雷风恒', 32),
            ('艮', '乾'): ('山天大畜', 26),
            ('艮', '坤'): ('山地剥', 23),
            ('艮', '震'): ('山雷颐', 27),
            ('艮', '艮'): ('艮为山', 52),
            ('艮', '离'): ('山火贲', 22),
            ('艮', '坎'): ('山水蒙', 4),
            ('艮', '兑'): ('山泽损', 41),
            ('艮', '巽'): ('山风蛊', 18),
            ('离', '乾'): ('火天大有', 14),
            ('离', '坤'): ('火地晋', 35),
            ('离', '震'): ('火雷噬嗑', 21),
            ('离', '艮'): ('火山旅', 56),
            ('离', '离'): ('离为火', 30),
            ('离', '坎'): ('火水未济', 64),
            ('离', '兑'): ('火泽睽', 38),
            ('离', '巽'): ('火风鼎', 50),
            ('坎', '乾'): ('水天需', 5),
            ('坎', '坤'): ('水地比', 8),
            ('坎', '震'): ('水雷屯', 3),
            ('坎', '艮'): ('水山蹇', 39),
            ('坎', '离'): ('水火既济', 63),
            ('坎', '坎'): ('坎为水', 29),
            ('坎', '兑'): ('水泽节', 60),
            ('坎', '巽'): ('水风井', 48),
            ('兑', '乾'): ('泽天夬', 43),
            ('兑', '坤'): ('泽地萃', 45),
            ('兑', '震'): ('泽雷随', 17),
            ('兑', '艮'): ('泽山咸', 31),
            ('兑', '离'): ('泽火革', 49),
            ('兑', '坎'): ('泽水困', 47),
            ('兑', '兑'): ('兑为泽', 58),
            ('兑', '巽'): ('泽风大过', 28),
            ('巽', '乾'): ('风天小畜', 9),
            ('巽', '坤'): ('风地观', 20),
            ('巽', '震'): ('风雷益', 42),
            ('巽', '艮'): ('风山渐', 53),
            ('巽', '离'): ('风火家人', 37),
            ('巽', '坎'): ('风水涣', 59),
            ('巽', '兑'): ('风泽中孚', 61),
            ('巽', '巽'): ('巽为风', 57),
        }

        name, num = hexagram_mapping.get((upper, lower), (f'{upper}{lower}卦', 0))
        return name, num

    def compare(self, target: CalligraphyPerception,
                actual: CalligraphyPerception) -> Dict:
        """
        对比字帖与书写结果的卦象差异

        Args:
            target: 字帖的感知结果
            actual: 书写结果的感知结果

        Returns:
            dict: 差异分析报告
        """
        # 六爻差异向量
        yao_diff = actual.yao_features - target.yao_features

        # 八卦隶属度差异
        tri_diff = {}
        for name in actual.trigram_memberships:
            tri_diff[name] = actual.trigram_memberships[name] - target.trigram_memberships[name]

        # 定位最大差异爻位
        yao_names = ['初爻(方向)', '二爻(粗细)', '三爻(曲直)', '四爻(规整)', '五爻(重心x)', '上爻(重心y)']
        max_diff_idx = np.argmax(np.abs(yao_diff))
        max_diff_val = yao_diff[max_diff_idx]

        # 卦象是否一致
        same_trigram = (actual.dominant_trigram == target.dominant_trigram)
        same_hexagram = (actual.hexagram_name == target.hexagram_name)

        report = {
            'same_trigram': same_trigram,
            'same_hexagram': same_hexagram,
            'yao_diff': yao_diff,
            'trigram_diff': tri_diff,
            'max_diff_yao': yao_names[max_diff_idx],
            'max_diff_val': float(max_diff_val),
            'total_yao_distance': float(np.sqrt(np.sum(yao_diff ** 2))),
            'target_trigram': target.dominant_trigram,
            'actual_trigram': actual.dominant_trigram,
            'target_hexagram': target.hexagram_name,
            'actual_hexagram': actual.hexagram_name,
        }

        return report


# ============================================================
# 测试
# ============================================================

def test_visual_ylyw():
    """测试书法视觉YLYW：生成简单字帖图像并分析"""
    print("=" * 60)
    print("YLYW书法视觉分析测试")
    print("=" * 60)

    visual = CalligraphyVisualYLYW()

    # 生成一个测试"字帖"：模拟不同结构的字
    test_images = {}
    for name, shape_fn in [
        ('方正型(乾)', _make_rect_image),
        ('圆转型(坤)', _make_circle_image),
        ('动态型(震)', _make_triangle_image),
        ('紧促型(艮)', _make_compact_image),
    ]:
        img = shape_fn()
        test_images[name] = img

    print("\n生成测试图像，分析结构卦象...\n")

    for name, img in test_images.items():
        perception = visual.perceive(img, verbose=True)
        print()

    return visual, test_images


def _make_rect_image(size=256) -> np.ndarray:
    """生成方正型测试图像（模拟田/国结构）"""
    canvas = np.ones((size, size), dtype=np.float32) * 255
    margin = 40
    # 外框
    cv2.rectangle(canvas, (margin, margin), (size-margin-1, size-margin-1), 20, 3)
    # 内十字
    cv2.line(canvas, (size//2, margin+20), (size//2, size-margin-20), 20, 3)
    cv2.line(canvas, (margin+20, size//2), (size-margin-20, size//2), 20, 3)
    return canvas.astype(np.uint8)


def _make_circle_image(size=256) -> np.ndarray:
    """生成圆转型测试图像（模拟永/水结构）"""
    canvas = np.ones((size, size), dtype=np.float32) * 255
    # 几个椭圆模拟曲线笔画
    cv2.ellipse(canvas, (size//2, size//2), (size//4, size//3), 30, 0, 300, 40, 3)
    cv2.ellipse(canvas, (size//2, size//2), (size//6, size//2), -20, 0, 200, 30, 2)
    cv2.ellipse(canvas, (size//3, size//3), (size//8, size//5), 60, 0, 270, 25, 2)
    return canvas.astype(np.uint8)


def _make_triangle_image(size=256) -> np.ndarray:
    """生成动态型测试图像（模拟人/大结构）"""
    canvas = np.ones((size, size), dtype=np.float32) * 255
    # 类似大字的结构
    cx, cy = size//2, size//2
    cv2.line(canvas, (cx, size-30), (cx-80, 30), 25, 2)  # 左撇
    cv2.line(canvas, (cx, size-30), (cx+80, 30), 25, 2)  # 右捺
    cv2.line(canvas, (cx, size-30), (cx, cy+30), 15, 2)  # 竖
    return canvas.astype(np.uint8)


def _make_compact_image(size=256) -> np.ndarray:
    """生成紧凑型测试图像（模拟山/石结构）"""
    canvas = np.ones((size, size), dtype=np.float32) * 255
    # 几个紧凑的方块
    cv2.rectangle(canvas, (60, 60), (200, 200), 40, 3)
    cv2.rectangle(canvas, (80, 80), (180, 180), 40, -1)
    return canvas.astype(np.uint8)


if __name__ == '__main__':
    visual, images = test_visual_ylyw()
    print("\n✅ 测试完成！视觉YLYW书法分析模块正常")
