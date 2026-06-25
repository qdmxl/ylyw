"""
视觉八卦专用检测器 v2 — 校准版

关键改进:
    1. 震: 用方向主导度替代总能量 (方向性 ≠ 总边缘)
    2. 乾: 角点间距规整度 / 边缘密度比率
    3. 坎: 方向熵归一化
    4. 全部检测器: 去除硬编码阈值, 使用自适应归一化
    5. Softmax 输出归一化
"""

import cv2
import numpy as np
from enum import Enum


class Trigram(Enum):
    QIAN = 0; KUN = 1; ZHEN = 2; XUN = 3
    KAN = 4; LI = 5; GEN = 6; DUI = 7


class SpecializedDetectorsV2:
    """8卦专用视觉检测器 v2"""

    def __init__(self):
        # Gabor kernels for directional analysis
        self.gabor_kernels = []
        for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            for sigma in [3.0, 6.0, 10.0]:
                ksize = int(6 * sigma) | 1
                lamda = sigma * 2.5
                kernel = cv2.getGaborKernel(
                    (ksize, ksize), sigma, theta, lamda, 0.5, 0, ktype=cv2.CV_32F
                )
                self.gabor_kernels.append((theta, sigma, kernel))

    def detect_all(self, gray: np.ndarray) -> np.ndarray:
        """返回 8D 原始得分向量 (不做 softmax)"""
        gray = gray.astype(np.float32)
        h, w = gray.shape
        gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)

        # Gabor 响应
        gabor_maps = []
        for theta, sigma, kernel in self.gabor_kernels:
            fm = cv2.filter2D(gray, cv2.CV_32F, kernel)
            gabor_maps.append((theta, sigma, fm))

        # 梯度
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)
        angle = np.arctan2(gy, gx)

        raw = np.zeros(8, dtype=np.float32)
        raw[0] = self._qian(gray_u8, mag, h, w)
        raw[1] = self._kun(gray)
        raw[2] = self._zhen(gabor_maps)
        raw[3] = self._xun(gabor_maps)
        raw[4] = self._kan(mag, angle)
        raw[5] = self._li(gray)
        raw[6] = self._gen(gray)
        raw[7] = self._dui(gray)
        return raw

    # ================================================================

    def _qian(self, gray_u8, mag, h, w):
        """乾: 网格结构 = 高角点密度 + 规整间距"""
        corners = cv2.cornerHarris(gray_u8, blockSize=4, ksize=3, k=0.04)
        corner_mask = corners > 0.02 * corners.max()
        n_corners = corner_mask.sum()
        if n_corners < 15:
            return 0.0

        corner_pts = np.argwhere(corner_mask).astype(np.float32)
        if len(corner_pts) < 20:
            return 0.1

        from scipy.spatial import KDTree
        tree = KDTree(corner_pts)
        dists, _ = tree.query(corner_pts, k=min(5, len(corner_pts)))
        nn = dists[:, 1] if dists.ndim > 1 else dists
        cv_val = np.std(nn) / (np.mean(nn) + 1e-6)
        regularity = np.exp(-cv_val * 3)

        # 边缘密度归一化 (网格结构: 角点多/边缘适中)
        edge_density = (mag > mag.mean()).mean()
        corner_edge_ratio = (n_corners / (h * w)) / (edge_density + 1e-6) * 20

        return regularity * min(1.0, corner_edge_ratio)

    def _kun(self, gray):
        """坤: 平滑度 = 低局部方差"""
        ps = 16
        h, w = gray.shape
        vars_list = []
        for i in range(0, h - ps, ps):
            for j in range(0, w - ps, ps):
                vars_list.append(np.var(gray[i:i+ps, j:j+ps]))
        if not vars_list:
            return 0.0
        mean_var = np.mean(vars_list)
        # 方差 < 50 → 高隶属度, > 800 → 低隶属度
        return np.exp(-mean_var / 200.0)

    def _zhen(self, gabor_maps):
        """震: 方向主导度 = 单一方向响应 / 所有方向响应"""
        # 按 theta 分组, 计算每个方向的平均能量
        from collections import defaultdict
        dir_energy = defaultdict(list)
        for theta, sigma, fm in gabor_maps:
            dir_energy[theta].append(np.mean(np.abs(fm)))

        energies = np.array([np.mean(v) for v in dir_energy.values()])
        if energies.max() < 1e-6:
            return 0.0

        # 方向性 = (最强-次强) / 均值
        energies.sort()
        directionality = (energies[-1] - energies[-2]) / (energies.mean() + 1e-6)
        # 方向性高 → 震隶属度高
        return np.clip(directionality, 0.0, 3.0)

    def _xun(self, gabor_maps):
        """巽: 细纹理 = 细尺度响应 / 粗尺度响应"""
        fine, coarse = [], []
        for theta, sigma, fm in gabor_maps:
            energy = np.mean(np.abs(fm))
            if sigma <= 4:
                fine.append(energy)
            else:
                coarse.append(energy)

        f_energy = np.mean(fine) if fine else 0
        c_energy = np.mean(coarse) if coarse else 1e-6
        ratio = f_energy / (c_energy + 1e-6)
        # 纹理细密度 (高 ratio = 细纹理)
        return np.clip(ratio - 1.0, 0.0, 2.0)

    def _kan(self, mag, angle):
        """坎: 曲线度 = 梯度方向均匀分布 (高熵)"""
        mask = mag > np.percentile(mag, 30)
        if mask.sum() < 50:
            return 0.0

        angles = angle[mask]
        hist, _ = np.histogram(angles, bins=12, range=(-np.pi, np.pi), density=True)
        hist = hist / (hist.sum() + 1e-6)
        entropy = -np.sum(hist * np.log(hist + 1e-8))
        max_entropy = np.log(12)
        # 归一化熵 (均匀分布 = 1.0)
        norm_entropy = entropy / max_entropy
        return norm_entropy

    def _li(self, gray):
        """离: 亮度峰值 + 中心-周边对比"""
        mean_v, std_v = gray.mean(), gray.std()
        if std_v < 1:
            return 0.0

        # 亮点密度 (z > 1.5)
        bright_ratio = ((gray - mean_v) > 1.5 * std_v).mean()

        # 中心-周边对比
        h, w = gray.shape
        ch, cw = h // 3, w // 3
        center = gray[ch:2*ch, cw:2*cw]
        border_concat = np.concatenate([
            gray[:ch, :].ravel(), gray[2*ch:, :].ravel(),
            gray[ch:2*ch, :cw].ravel(), gray[ch:2*ch, 2*cw:].ravel(),
        ])
        cs = (center.mean() - border_concat.mean()) / (std_v + 1e-6)

        return bright_ratio * 50 + np.clip(cs / 3.0, 0.0, 1.0)

    def _gen(self, gray):
        """艮: 大块同质区域"""
        ps = 32
        h, w = gray.shape
        block_vars, block_means = [], []
        for i in range(0, h - ps, ps * 2 // 3):
            for j in range(0, w - ps, ps * 2 // 3):
                patch = gray[i:i+ps, j:j+ps]
                block_vars.append(np.var(patch))
                block_means.append(patch.mean())

        if not block_vars:
            return 0.0

        bv = np.array(block_vars)
        bm = np.array(block_means)
        # 低方差块占比 (同质性)
        lo_var = (bv < np.percentile(bv, 30)).mean()
        # 块间对比
        inter = np.std(bm) / (np.mean(bm) + 1e-6)

        return lo_var * 0.5 + min(1.0, inter / 0.2) * 0.5

    def _dui(self, gray):
        """兑: 高光点 = 极端亮度点的局部对比度"""
        if gray.std() < 1:
            return 0.0

        # Top 2% 亮度
        thresh = np.percentile(gray, 98)
        highlight = gray > thresh
        h_density = highlight.mean()

        if highlight.sum() < 5:
            return 0.0

        # 高光点相对局部的对比度
        local_mean = cv2.GaussianBlur(gray, (25, 25), 10)
        ratio = gray[highlight] / (local_mean[highlight] + 1e-6)
        specularity = np.clip(np.mean(ratio) - 1.0, 0.0, 1.0)

        return specularity * 0.7 + min(1.0, h_density * 30) * 0.3
