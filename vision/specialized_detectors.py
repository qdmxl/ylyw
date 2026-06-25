"""
视觉八卦专用检测器 (Specialized Trigram Detectors)

重构版本: 每个卦象拥有独立的视觉特征检测器，
直接输出隶属度，跳过共享6维特征和六爻编码层。

每个检测器针对该卦象的视觉原型设计专用算子:
    乾: 网格规整度 + 角点密度
    坤: 局部平滑度 + 低纹理
    震: 定向边缘能量 (Gabor)
    巽: 高频细纹理密度
    坎: 曲线度 + 梯度方向熵
    离: 亮度峰值 + 中心-周边对比
    艮: 大块同质区域
    兑: 高光点检测
"""

import cv2
import numpy as np
from enum import Enum


class Trigram(Enum):
    QIAN = 0  # 乾 - 结构/几何
    KUN = 1   # 坤 - 平滑/均匀
    ZHEN = 2  # 震 - 高对比方向
    XUN = 3   # 巽 - 细纹理
    KAN = 4   # 坎 - 曲线/流动
    LI = 5    # 离 - 亮/辐射
    GEN = 6   # 艮 - 块状/厚重
    DUI = 7   # 兑 - 反射/高光


class SpecializedDetectors:
    """
    8个卦象各自专用的视觉检测器。
    
    每个检测器返回 [0,1] 的隶属度得分,
    表示图像匹配该卦象视觉原型的程度。
    """

    def __init__(self):
        # Gabor 滤波器组 (4方向 × 2尺度)
        self.gabor_kernels = self._build_gabor_kernels()

    def _build_gabor_kernels(self):
        """构建 Gabor 滤波器组"""
        kernels = []
        for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            for sigma in [4.0, 8.0]:
                ksize = int(6 * sigma) | 1  # 奇数
                lamda = sigma * 2
                gamma = 0.5
                kernel = cv2.getGaborKernel(
                    (ksize, ksize), sigma, theta, lamda, gamma, 0, ktype=cv2.CV_32F
                )
                kernels.append((theta, sigma, kernel))
        return kernels

    def detect_all(self, gray: np.ndarray) -> np.ndarray:
        """
        运行所有8个检测器, 输出归一化隶属度。

        使用 softmax 归一化确保8个得分分布合理,
        解决不同检测器输出范围不一致的问题。
        """
        gray = gray.astype(np.float32)
        raw = np.zeros(8, dtype=np.float32)

        raw[0] = self.detect_qian(gray)
        raw[1] = self.detect_kun(gray)
        raw[2] = self.detect_zhen(gray)
        raw[3] = self.detect_xun(gray)
        raw[4] = self.detect_kan(gray)
        raw[5] = self.detect_li(gray)
        raw[6] = self.detect_gen(gray)
        raw[7] = self.detect_dui(gray)

        # Softmax 归一化 (温度 T=0.3 增强差异)
        T = 0.3
        exp_scores = np.exp(raw / T)
        normalized = exp_scores / exp_scores.sum()

        return np.clip(normalized, 0.0, 1.0)

    # ===== 乾: 结构/几何 — 网格规整度 + 角点密度 =====

    def detect_qian(self, gray: np.ndarray) -> float:
        """
        乾检测器: 规则网格/几何结构的强度

        方法:
            1. Harris 角点检测 → 角点分布规整度
            2. 水平/垂直梯度相关性 → 网格结构
        """
        h, w = gray.shape
        gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)

        # Harris 角点
        corners = cv2.cornerHarris(gray_u8, blockSize=4, ksize=3, k=0.04)
        corner_mask = corners > 0.01 * corners.max()

        if corner_mask.sum() < 10:
            return 0.0

        # 角点之间的间距规整度 (网格结构的关键特征)
        corner_pts = np.argwhere(corner_mask)
        if len(corner_pts) < 20:
            return 0.1

        # 计算最近邻距离的变异系数 (CV = std/mean)
        from scipy.spatial import KDTree
        tree = KDTree(corner_pts.astype(np.float32))
        dists, _ = tree.query(corner_pts.astype(np.float32), k=2)
        nn_dists = dists[:, 1]  # 最近邻距离

        if nn_dists.mean() < 1:
            return 0.0

        cv_val = nn_dists.std() / nn_dists.mean()
        # 低CV = 规则间距 = 网格结构
        regularity = np.exp(-cv_val)

        # 角点密度
        density = corner_mask.sum() / (h * w)
        density_score = min(1.0, density * 200)

        return float(np.clip(0.6 * regularity + 0.4 * density_score, 0.0, 1.0))

    # ===== 坤: 平滑/均匀 =====

    def detect_kun(self, gray: np.ndarray) -> float:
        """
        坤检测器: 平滑均匀程度

        方法:
            1. 局部方差 (低=平滑)
            2. 梯度幅值 (低=均匀)
        """
        # 分块局部方差
        ps = 16
        h, w = gray.shape
        local_vars = []
        for i in range(0, h - ps, ps):
            for j in range(0, w - ps, ps):
                patch = gray[i:i+ps, j:j+ps]
                local_vars.append(np.var(patch))

        if not local_vars:
            return 0.5

        mean_var = np.mean(local_vars)
        # 方差越低 → 越平滑 → 隶属度越高
        smoothness = np.exp(-mean_var / 500.0)

        return float(np.clip(smoothness, 0.0, 1.0))

    # ===== 震: 高对比方向 =====

    def detect_zhen(self, gray: np.ndarray) -> float:
        """
        震检测器: 定向边缘强度

        方法:
            1. Gabor 滤波器各方向响应
            2. 方向主导度 (最强方向 vs 次强方向)
            3. 响应强度
        """
        responses = []
        for theta, sigma, kernel in self.gabor_kernels:
            filtered = cv2.filter2D(gray, cv2.CV_32F, kernel)
            energy = np.mean(np.abs(filtered))
            responses.append(energy)

        if not responses:
            return 0.0

        responses = np.array(responses)
        # 按 sigma 分组: 索引 0-3 = sigma=4, 4-7 = sigma=8
        # 取最大方向响应
        max_resp = responses.max()

        # 方向主导度: 最强方向 / (次强方向+ε)
        sorted_resp = np.sort(responses)[::-1]
        directionality = sorted_resp[0] / (sorted_resp[1] + 1e-6) - 1.0

        # 综合: 高响应 + 强方向性
        score = max_resp * min(1.0, directionality / 0.5)
        return float(np.clip(score / 20.0, 0.0, 1.0))

    # ===== 巽: 细纹理 =====

    def detect_xun(self, gray: np.ndarray) -> float:
        """
        巽检测器: 细密纹理密度

        方法:
            1. 高频能量占比 (Gabor sigma=4)
            2. 纹理均匀度 (高频响应的空间一致性)
        """
        # 小尺度 Gabor 响应 (sigma=4)
        fine_responses = []
        for theta, sigma, kernel in self.gabor_kernels:
            if sigma > 5:
                continue
            filtered = cv2.filter2D(gray, cv2.CV_32F, kernel)
            energy = np.mean(np.abs(filtered))
            fine_responses.append(energy)

        # 大尺度 Gabor 响应 (sigma=8)
        coarse_responses = []
        for theta, sigma, kernel in self.gabor_kernels:
            if sigma < 6:
                continue
            filtered = cv2.filter2D(gray, cv2.CV_32F, kernel)
            energy = np.mean(np.abs(filtered))
            coarse_responses.append(energy)

        fine_energy = np.mean(fine_responses) if fine_responses else 0
        coarse_energy = np.mean(coarse_responses) if coarse_responses else 1e-6

        # 高频/低频比 → 纹理细腻度
        texture_fineness = fine_energy / (coarse_energy + 1e-6)

        # 同时考虑总纹理能量
        total_energy = fine_energy + coarse_energy

        score = texture_fineness * min(1.0, total_energy / 10.0)
        return float(np.clip(score / 3.0, 0.0, 1.0))

    # ===== 坎: 曲线/流动 =====

    def detect_kan(self, gray: np.ndarray) -> float:
        """
        坎检测器: 曲线度和流动感

        方法:
            1. 梯度方向熵 (高熵=多方向=曲线)
            2. 边缘弯曲度
            3. 低方向主导度
        """
        # 梯度方向分布
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)
        angle = np.arctan2(gy, gx)

        # 只考虑显著梯度
        mask = mag > mag.mean()
        if mask.sum() < 100:
            return 0.0

        angles = angle[mask]

        # 方向直方图 (18 bins)
        hist, _ = np.histogram(angles, bins=18, range=(-np.pi, np.pi), density=True)
        hist = hist / (hist.sum() + 1e-6)

        # 方向熵: 高熵 = 多方向 = 曲线/流动
        entropy = -np.sum(hist * np.log(hist + 1e-8)) / np.log(18)

        # 还需要足够的边缘能量
        edge_energy = mag[mask].mean() / mag.mean()

        score = entropy * min(1.0, edge_energy / 1.5)
        return float(np.clip(score, 0.0, 1.0))

    # ===== 离: 亮/辐射 =====

    def detect_li(self, gray: np.ndarray) -> float:
        """
        离检测器: 亮度峰值和辐射感

        方法:
            1. 亮度峰值密度 (极端亮度区域)
            2. 中心-周边对比度
            3. 亮点空间聚集度
        """
        h, w = gray.shape
        mean_val = gray.mean()
        std_val = gray.std()

        if std_val < 1:
            return 0.0

        # 显著性: 亮度峰值 (z-score > 2.0)
        z_scores = (gray - mean_val) / std_val
        bright_mask = z_scores > 2.0
        bright_density = bright_mask.sum() / (h * w)

        # 亮点聚集度 (辐射模式: 亮点应聚集在少数区域)
        if bright_mask.sum() > 10:
            bright_pts = np.argwhere(bright_mask)
            from scipy.spatial import KDTree
            tree = KDTree(bright_pts.astype(np.float32))
            dists, _ = tree.query(bright_pts.astype(np.float32), k=min(5, len(bright_pts)))
            if dists.ndim > 1:
                mean_nn_dist = dists[:, 1:].mean()
            else:
                mean_nn_dist = dists.mean()
            # 亮点聚集 = 低NN距离
            clustering = np.exp(-mean_nn_dist / 20.0)
        else:
            clustering = 0.0

        # 中心-周边对比 (简化: 中央区域 vs 周边区域)
        ch, cw = h // 3, w // 3
        center = gray[ch:2*ch, cw:2*cw]
        border = np.concatenate([
            gray[:ch, :].flatten(),
            gray[2*ch:, :].flatten(),
            gray[ch:2*ch, :cw].flatten(),
            gray[ch:2*ch, 2*cw:].flatten(),
        ])
        cs_contrast = (center.mean() - border.mean()) / (border.std() + 1e-6)
        cs_score = np.clip(cs_contrast / 3.0, 0.0, 1.0)

        score = 0.3 * min(1.0, bright_density * 100) + 0.3 * clustering + 0.4 * cs_score
        return float(np.clip(score, 0.0, 1.0))

    # ===== 艮: 块状/厚重 =====

    def detect_gen(self, gray: np.ndarray) -> float:
        """
        艮检测器: 大块同质区域

        方法:
            1. 大尺度同质区域占比
            2. 强边缘包围的区域
            3. 低纹理方差的大块
        """
        h, w = gray.shape

        # 大尺度超像素模拟: 分大块, 计算块内方差
        block_size = 32
        block_vars = []
        block_means = []

        for i in range(0, h - block_size, block_size // 2):
            for j in range(0, w - block_size, block_size // 2):
                patch = gray[i:i+block_size, j:j+block_size]
                block_vars.append(np.var(patch))
                block_means.append(np.mean(patch))

        if not block_vars:
            return 0.0

        block_vars = np.array(block_vars)
        block_means = np.array(block_means)

        # 低方差块占比 (同质区域)
        var_threshold = np.percentile(block_vars, 30)
        homogeneous_ratio = (block_vars < var_threshold).mean()

        # 块间均值差异 (不同块之间应有区分)
        if len(block_means) > 1:
            inter_block_contrast = np.std(block_means) / (np.mean(block_means) + 1e-6)
        else:
            inter_block_contrast = 0.0

        score = 0.5 * homogeneous_ratio + 0.5 * min(1.0, inter_block_contrast / 0.3)
        return float(np.clip(score, 0.0, 1.0))

    # ===== 兑: 反射/高光 =====

    def detect_dui(self, gray: np.ndarray) -> float:
        """
        兑检测器: 高光点和镜面反射

        方法:
            1. 极端亮度点 (top 2% 亮度)
            2. 高光点与其局部的对比度
            3. 高光点的空间离散度
        """
        h, w = gray.shape

        # 极端亮度点
        threshold = np.percentile(gray, 98)
        highlight_mask = gray > threshold
        highlight_density = highlight_mask.sum() / (h * w)

        if highlight_mask.sum() < 5:
            return 0.0

        # 高光点的局部对比度 (高光点亮度 vs 局部均值)
        if highlight_mask.sum() > 0:
            # 局部均值 (大尺度模糊)
            local_mean = cv2.GaussianBlur(gray, (31, 31), 15)
            highlight_vals = gray[highlight_mask]
            local_vals = local_mean[highlight_mask]
            # 高光点应显著亮于局部
            contrast_ratio = np.mean(highlight_vals / (local_vals + 1e-6))
            specularity = min(1.0, (contrast_ratio - 1.0) / 0.5)
        else:
            specularity = 0.0

        # 密度不宜过高 (满幅高光=过曝, 不是"反射")
        density_score = highlight_density * 50 if highlight_density < 0.02 else 0.5

        score = 0.6 * specularity + 0.4 * density_score
        return float(np.clip(score, 0.0, 1.0))
