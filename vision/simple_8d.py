"""
八卦8D特征提取器 — 每卦一个简单直接算子

乾: 角点密度 × 规整度
坤: 局部方差 (低=平滑)
震: Gabor 方向主导度
巽: GLCM 对比度
坎: GLCM 熵
离: 亮区占比
艮: 低方差块占比
兑: 极端亮度局部对比度
"""

import cv2
import numpy as np


class Simple8DExtractor:
    """8D 特征提取器 — 每卦一个算子"""

    def __init__(self):
        self.gabor_kernels = []
        for theta in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            for sigma in [3.0, 6.0, 10.0]:
                ksize = int(6 * sigma) | 1
                k = cv2.getGaborKernel((ksize, ksize), sigma, theta, sigma*2.5, 0.5, 0, cv2.CV_32F)
                self.gabor_kernels.append((theta, sigma, k))

    def extract(self, gray: np.ndarray) -> np.ndarray:
        gray = gray.astype(np.float32)
        gray_u8 = np.clip(gray, 0, 255).astype(np.uint8)
        h, w = gray.shape

        # 共享: Gabor 响应
        gabor_energies = []
        for theta, sigma, k in self.gabor_kernels:
            resp = cv2.filter2D(gray, cv2.CV_32F, k)
            gabor_energies.append(float(np.mean(np.abs(resp))))

        # 共享: 梯度
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)

        feats = np.zeros(8, dtype=np.float32)

        # 乾: 角点规整度
        corners = cv2.cornerHarris(gray_u8, 4, 3, 0.04)
        cm = corners > 0.02 * corners.max()
        n = cm.sum()
        if n > 20:
            pts = np.argwhere(cm).astype(np.float32)
            from scipy.spatial import KDTree
            tree = KDTree(pts)
            d, _ = tree.query(pts, k=2)
            nn = d[:, 1]
            cv_val = np.std(nn) / (np.mean(nn) + 1e-6)
            feats[0] = np.exp(-cv_val * 5) * min(1.0, n / (h*w) * 500)
        else:
            feats[0] = 0.0

        # 坤: 平滑度 (低局部方差)
        ps = 16
        vars_ = []
        for i in range(0, h-ps, ps):
            for j in range(0, w-ps, ps):
                vars_.append(np.var(gray[i:i+ps, j:j+ps]))
        feats[1] = np.exp(-np.mean(vars_) / 400.0)

        # 震: Gabor 方向主导度
        # 按 theta 分组
        dir_mean = {}
        for (theta, sigma, k), e in zip(self.gabor_kernels, gabor_energies):
            dir_mean.setdefault(theta, []).append(e)
        dir_avg = np.array([np.mean(v) for v in dir_mean.values()])
        if dir_avg.max() > 0:
            sorted_d = np.sort(dir_avg)
            feats[2] = np.clip((sorted_d[-1] - sorted_d[-2]) / (dir_avg.mean() + 1e-6), 0, 3) / 3
        else:
            feats[2] = 0.0

        # 巽: GLCM 对比度 (高对比=粗纹理, 低对比=细纹理 → 反编码)
        glcm_contrast = self._glcm_contrast(gray_u8)
        feats[3] = np.exp(-glcm_contrast / 50.0)  # 低对比=细纹理=高巽

        # 坎: 梯度方向熵
        mask = mag > np.percentile(mag, 30)
        if mask.sum() > 50:
            angles = np.arctan2(gy[mask], gx[mask])
            hist, _ = np.histogram(angles, bins=12, range=(-np.pi, np.pi), density=True)
            hist = hist / (hist.sum() + 1e-6)
            entropy = -np.sum(hist * np.log(hist + 1e-8))
            feats[4] = entropy / np.log(12)  # 归一化到 [0,1]
        else:
            feats[4] = 0.0

        # 离: 亮区占比
        m, s = gray.mean(), gray.std()
        feats[5] = np.clip(((gray > m + 1.5*s).mean() * 100), 0, 1) if s > 1 else 0.0

        # 艮: 低方差大块占比
        bs = 32
        bvars, bmeans = [], []
        for i in range(0, h-bs, bs//2):
            for j in range(0, w-bs, bs//2):
                p = gray[i:i+bs, j:j+bs]
                bvars.append(np.var(p))
                bmeans.append(np.mean(p))
        if bvars:
            bv = np.array(bvars)
            bm = np.array(bmeans)
            lo = (bv < np.percentile(bv, 25)).mean()
            ic = np.std(bm) / (np.mean(bm) + 1e-6)
            feats[6] = lo * 0.5 + np.clip(ic / 0.2, 0, 1) * 0.5
        else:
            feats[6] = 0.0

        # 兑: 极端亮度对比度
        if gray.std() > 1:
            thresh = np.percentile(gray, 97)
            hm = gray > thresh
            if hm.sum() > 5:
                lm = cv2.GaussianBlur(gray, (21, 21), 8)
                ratio = gray[hm] / (lm[hm] + 1e-6)
                feats[7] = np.clip(np.mean(ratio) - 1.0, 0, 1)
            else:
                feats[7] = 0.0
        else:
            feats[7] = 0.0

        return feats

    def _glcm_contrast(self, gray_u8):
        """GLCM 对比度 (d=1, avg over 4 angles)"""
        levels = 32
        gq = np.floor(gray_u8.astype(np.float64) / 256 * levels).clip(0, levels-1).astype(np.int32)
        h, w = gq.shape
        contrasts = []

        for angle in [0, np.pi/4, np.pi/2, 3*np.pi/4]:
            dx = int(round(np.cos(angle)))
            dy = int(round(np.sin(angle)))
            is_ = max(0, -dy); ie = min(h, h-dy)
            js = max(0, -dx); je = min(w, w-dx)
            if ie <= is_ or je <= js:
                continue
            src = gq[is_:ie, js:je].ravel()
            dst = gq[is_+dy:ie+dy, js+dx:je+dx].ravel()
            glcm = np.zeros((levels, levels), dtype=np.float64)
            np.add.at(glcm, (src, dst), 1)
            glcm = glcm + glcm.T
            glcm /= glcm.sum() + 1e-10
            I, J = np.ogrid[:levels, :levels]
            contrasts.append(float(np.sum((I - J)**2 * glcm)))

        return np.mean(contrasts) if contrasts else 0.0
