"""
视觉特征提取器 (Visual Feature Extractor)

从图像中提取6维视觉特征向量，对应六爻编码的六个维度:
    初爻 - 纹理均匀度 (texture_uniformity)
    二爻 - 边缘清晰度 (edge_clarity)
    三爻 - 局部对比度 (local_contrast)
    四爻 - 形状规整度 (shape_regularity)
    五爻 - 显著性 (saliency)
    上爻 - 背景复杂度 (background_complexity)

所有特征归一化到 [0, 1]。

用法:
    >>> extractor = VisualFeatureExtractor()
    >>> features = extractor.extract(image)  # image: np.ndarray (H, W) or (H, W, 3)
    >>> print(features)
    {'texture_uniformity': 0.72, 'edge_clarity': 0.45, ...}
"""

import cv2
import numpy as np


class VisualFeatureExtractor:
    """图像 → 6维视觉特征向量"""

    def __init__(self, patch_size: int = 16):
        """
        Args:
            patch_size: 纹理/对比度分析的块大小
        """
        self.patch_size = patch_size

    def extract(self, image: np.ndarray) -> dict:
        """
        从图像提取全部6维视觉特征

        Args:
            image: np.ndarray, (H,W) 灰度图 或 (H,W,3) RGB图

        Returns:
            dict with keys: texture_uniformity, edge_clarity, local_contrast,
                           shape_regularity, saliency, background_complexity
        """
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.astype(np.float32)

        gray = gray.astype(np.float32)
        h, w = gray.shape

        features = {
            'texture_uniformity': self._texture_uniformity(gray),
            'edge_clarity': self._edge_clarity(gray),
            'local_contrast': self._local_contrast(gray),
            'shape_regularity': self._shape_regularity(gray),
            'saliency': self._saliency(gray),
            'background_complexity': self._background_complexity(gray),
        }

        return features

    # ============================================================
    #  初爻: 纹理均匀度
    #  高值 = 纹理均匀平滑; 低值 = 纹理杂乱多变
    # ============================================================

    def _texture_uniformity(self, gray: np.ndarray) -> float:
        """
        纹理均匀度: 梯度幅值的分块方差取反

        方法:
            1. Sobel算子计算梯度幅值
            2. 分块计算梯度幅值方差
            3. 方差均值越低 → 纹理越均匀 → 特征值越高
        """
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)

        # 分块计算局部方差
        ps = self.patch_size
        h, w = grad_mag.shape
        local_vars = []

        for i in range(0, h - ps, ps):
            for j in range(0, w - ps, ps):
                patch = grad_mag[i:i + ps, j:j + ps]
                local_vars.append(np.var(patch))

        if not local_vars:
            return 0.5

        mean_var = np.mean(local_vars)
        # 归一化: var≈0→1.0(完全均匀), var≈5000→0.0
        uniformity = np.exp(-mean_var / 800.0)
        return float(np.clip(uniformity, 0.0, 1.0))

    # ============================================================
    #  二爻: 边缘清晰度
    #  高值 = 边缘清晰锐利; 低值 = 边缘模糊/无边缘
    # ============================================================

    def _edge_clarity(self, gray: np.ndarray) -> float:
        """
        边缘清晰度: Canny边缘密度 × 边缘强度

        方法:
            1. Canny边缘检测
            2. 边缘像素占比
            3. 边缘处Sobel强度均值
            4. 两者乘积归一化
        """
        # Canny 自适应阈值
        median_val = np.median(gray)
        low_thresh = int(max(0, 0.66 * median_val))
        high_thresh = int(min(255, 1.33 * median_val))
        edges = cv2.Canny(gray.astype(np.uint8), low_thresh, high_thresh)

        edge_density = np.mean(edges > 0)

        # 边缘处梯度强度
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        edge_mask = edges > 0
        if edge_mask.sum() > 0:
            edge_strength = np.mean(grad_mag[edge_mask])
        else:
            edge_strength = 0.0

        clarity = edge_density * (edge_strength / 100.0)
        return float(np.clip(clarity, 0.0, 1.0))

    # ============================================================
    #  三爻: 局部对比度 (RMS Contrast)
    #  高值 = 局部明暗变化剧烈; 低值 = 局部变化平缓
    # ============================================================

    def _local_contrast(self, gray: np.ndarray) -> float:
        """
        RMS 对比度: 分块标准差 / 全局均值

        方法:
            1. 分块计算像素标准差
            2. 均值 / 全局均值 = RMS对比度
            3. 归一化
        """
        ps = self.patch_size
        h, w = gray.shape
        rms_vals = []

        for i in range(0, h - ps, ps):
            for j in range(0, w - ps, ps):
                patch = gray[i:i + ps, j:j + ps]
                if patch.std() > 0:
                    rms_vals.append(patch.std() / (patch.mean() + 1e-6))

        if not rms_vals:
            return 0.5

        mean_rms = np.mean(rms_vals)
        # RMS≈0→0(无对比), RMS≈0.8→1.0
        contrast = mean_rms / 0.5
        return float(np.clip(contrast, 0.0, 1.0))

    # ============================================================
    #  四爻: 形状规整度
    #  高值 = 规则几何形状; 低值 = 不规则/无形状
    # ============================================================

    def _shape_regularity(self, gray: np.ndarray) -> float:
        """
        形状规整度: 基于轮廓的紧致度/矩形度/圆度

        方法:
            1. 大津法二值化
            2. 找最大轮廓
            3. 紧致度 = 4π·面积/周长² (圆=1)
            4. 矩形度 = 面积/包围盒面积
            5. 规整度 = max(紧致度, 矩形度)
        """
        # 二值化
        _, binary = cv2.threshold(
            gray.astype(np.uint8), 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return 0.0

        # 取面积最大的轮廓
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        perimeter = cv2.arcLength(main_contour, True)

        if area < 10 or perimeter < 1:
            return 0.0

        # 紧致度 (圆 = 1.0)
        compactness = 4 * np.pi * area / (perimeter ** 2) if perimeter > 0 else 0

        # 矩形度
        x, y, bw, bh = cv2.boundingRect(main_contour)
        rect_area = bw * bh
        rectangularity = area / rect_area if rect_area > 0 else 0

        # 轮廓面积占比 (排除"全是背景"的情况)
        img_area = gray.shape[0] * gray.shape[1]
        coverage = area / img_area

        # 综合: 取紧致度和矩形度的较大者, 乘以覆盖率避免背景图得高分
        regularity = max(compactness, rectangularity) * min(1.0, coverage * 5)

        return float(np.clip(regularity, 0.0, 1.0))

    # ============================================================
    #  五爻: 显著性
    #  高值 = 有突出显著区域; 低值 = 画面平淡
    # ============================================================

    def _saliency(self, gray: np.ndarray) -> float:
        """
        显著性: 频谱残差法 (Spectral Residual)

        方法:
            1. FFT → 幅度谱 + 相位谱
            2. 幅度谱取log → 均值滤波 → 残差 = log - 平滑log
            3. 逆FFT → 显著性图
            4. 显著性图的均值/峰值作为特征
        """
        h, w = gray.shape

        # FFT
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)

        # 幅度谱和相位谱
        magnitude = np.abs(fshift)
        phase = np.angle(fshift)

        # Log幅度谱
        log_mag = np.log(magnitude + 1e-8)

        # 均值滤波 (频谱残差)
        kernel_size = 3
        kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size ** 2)
        log_mag_smooth = cv2.filter2D(log_mag, -1, kernel)

        # 残差
        residual = log_mag - log_mag_smooth

        # 逆FFT
        saliency_map = np.abs(np.fft.ifft2(
            np.fft.ifftshift(np.exp(residual + 1j * phase))
        ))

        # 高斯平滑显著性图
        saliency_map = cv2.GaussianBlur(saliency_map.astype(np.float32), (9, 9), 4)

        # 归一化特征: 峰值 / 均值比
        if saliency_map.max() > 0:
            saliency = saliency_map.max() / (saliency_map.mean() + 1e-6)
        else:
            saliency = 0.0

        return float(np.clip(saliency / 15.0, 0.0, 1.0))

    # ============================================================
    #  上爻: 背景复杂度
    #  高值 = 背景杂乱; 低值 = 背景干净
    # ============================================================

    def _background_complexity(self, gray: np.ndarray) -> float:
        """
        背景复杂度: 图像边缘区域(外围20%)的边缘密度

        方法:
            1. 提取外围20%区域
            2. 计算该区域的边缘密度
            3. 高密度 = 背景复杂
        """
        h, w = gray.shape
        border_h = int(h * 0.2)
        border_w = int(w * 0.2)

        # 四条边框区域
        top = gray[:border_h, :]
        bottom = gray[h - border_h:, :]
        left = gray[border_h:h - border_h, :border_w]
        right = gray[border_h:h - border_h, w - border_w:]

        # 分别计算四条边区域的梯度，取平均
        all_grad_mags = []
        for region in [top, bottom, left, right]:
            if region.size < 100:
                continue
            # 对每条边单独计算梯度
            sx = cv2.Sobel(region, cv2.CV_64F, 1, 0, ksize=3)
            sy = cv2.Sobel(region, cv2.CV_64F, 0, 1, ksize=3)
            gm = np.sqrt(sx ** 2 + sy ** 2)
            all_grad_mags.append(np.mean(gm))

        if not all_grad_mags:
            return 0.5

        mean_grad = np.mean(all_grad_mags)
        complexity = mean_grad / 50.0
        return float(np.clip(complexity, 0.0, 1.0))
