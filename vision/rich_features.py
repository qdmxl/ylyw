"""
丰富纹理特征提取器 v2 (优化版)

GLCM + Gabor + LBP, 全部使用向量化/skimage 实现。
"""

import cv2
import numpy as np
from skimage.feature import local_binary_pattern


class RichFeatureExtractor:
    """52D 纹理特征提取器"""

    def __init__(self):
        self.gabor_kernels = []
        for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            for sigma in [3.0, 6.0, 10.0]:
                ksize = int(6 * sigma) | 1
                lamda = sigma * 2.5
                kernel = cv2.getGaborKernel(
                    (ksize, ksize), sigma, theta, lamda, 0.5, 0, ktype=cv2.CV_32F
                )
                self.gabor_kernels.append(kernel)

    def extract(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        glcm = self._glcm(gray.astype(np.float32))
        gabor = self._gabor(gray.astype(np.float32))
        lbp = self._lbp(gray)

        return np.concatenate([glcm, gabor, lbp]).astype(np.float32)

    def extract_batch(self, images):
        return np.stack([self.extract(img) for img in images])

    @property
    def feature_dim(self):
        return 52

    # ================================================================

    def _glcm(self, gray):
        """GLCM: 3距离 × 6统计量 = 18D"""
        levels = 32
        gray_q = np.floor(gray / 256.0 * levels).clip(0, levels-1).astype(np.int32)
        h, w = gray_q.shape

        all_feats = []
        angles = [0, np.pi/4, np.pi/2, 3*np.pi/4]

        for d in [1, 3, 5]:
            angle_feats = []
            for angle in angles:
                dx = int(round(d * np.cos(angle)))
                dy = int(round(d * np.sin(angle)))

                # 有效区域
                i_s = max(0, -dy)
                i_e = min(h, h - dy)
                j_s = max(0, -dx)
                j_e = min(w, w - dx)

                if i_e <= i_s or j_e <= j_s:
                    angle_feats.append([0]*6)
                    continue

                src = gray_q[i_s:i_e, j_s:j_e].ravel()
                dst = gray_q[i_s+dy:i_e+dy, j_s+dx:j_e+dx].ravel()

                glcm = np.zeros((levels, levels), dtype=np.float64)
                np.add.at(glcm, (src, dst), 1)
                glcm = glcm + glcm.T
                glcm /= glcm.sum() + 1e-10

                angle_feats.append(self._glcm_stats(glcm))

            all_feats.extend(np.mean(angle_feats, axis=0))

        return np.array(all_feats, dtype=np.float32)

    def _glcm_stats(self, glcm):
        levels = glcm.shape[0]
        I, J = np.ogrid[:levels, :levels]
        px = glcm.sum(axis=1); py = glcm.sum(axis=0)
        mu_x = np.sum(I.ravel()[:levels] * px)
        mu_y = np.sum(J.ravel()[:levels] * py)
        sig_x = np.sqrt(np.sum((I.ravel()[:levels] - mu_x)**2 * px))
        sig_y = np.sqrt(np.sum((J.ravel()[:levels] - mu_y)**2 * py))

        contrast = np.sum((I - J)**2 * glcm)
        diss = np.sum(np.abs(I - J) * glcm)
        homo = np.sum(glcm / (1 + (I - J)**2))
        asm = np.sum(glcm**2)
        corr = np.sum((I - mu_x) * (J - mu_y) * glcm) / (sig_x * sig_y + 1e-10)
        entropy = -np.sum(glcm * np.log(glcm + 1e-10))

        return [contrast, diss, homo, asm, corr, entropy]

    def _gabor(self, gray):
        """Gabor: 12滤波器 × 2统计量 = 24D"""
        feats = []
        for kernel in self.gabor_kernels:
            resp = cv2.filter2D(gray, cv2.CV_32F, kernel)
            mag = np.abs(resp)
            feats.append(float(np.mean(mag)))
            feats.append(float(np.std(mag)))
        return np.array(feats, dtype=np.float32)

    def _lbp(self, gray):
        """LBP: 均匀模式 10 bins = 10D (使用 skimage)"""
        lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')
        hist, _ = np.histogram(lbp.ravel(), bins=10, range=(0, 10), density=True)
        return hist.astype(np.float32)
