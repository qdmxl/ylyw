#!/usr/bin/env python3
"""
YLYW 视觉特征提取模块 — Visual Feature Extractor

将场景 RGB 图像映射到 YLYW 所需的 6 维物理特征：
  strength_needed, stability, deformability, roll_tendency, visibility, fragility

支持两种模式：
  1. 视觉推理模式（视觉模型 → 特征）：从图像提取物体形状/尺寸/姿态 → 推断物理特征
  2. 颜色+几何模式（传统CV）：从轮廓检测+几何分析估计特征（无GPU降级方案）

设计原则：
  - L1 八卦隶属度的底层特征来源可以是视觉的，也可以是状态量的，不影响L2/L3
  - 视觉特征与状态特征融合：视觉提供物体先验，状态提供实时反馈
"""

import numpy as np
import cv2
from typing import Dict, Optional, Tuple

# 物体几何类型的物理特征模板（与 zhiji_infer.OBJECT_FEATURES 共享）
GEOMETRY_FEATURES = {
    'sphere':   {'strength_needed': 0.3, 'stability': 0.6, 'deformability': 0.5,
                 'roll_tendency': 0.8, 'visibility': 0.7, 'fragility': 0.3},
    'cube':     {'strength_needed': 0.4, 'stability': 0.8, 'deformability': 0.3,
                 'roll_tendency': 0.1, 'visibility': 0.6, 'fragility': 0.4},
    'cylinder': {'strength_needed': 0.4, 'stability': 0.6, 'deformability': 0.4,
                 'roll_tendency': 0.7, 'visibility': 0.6, 'fragility': 0.4},
    'bowl':     {'strength_needed': 0.4, 'stability': 0.5, 'deformability': 0.4,
                 'roll_tendency': 0.3, 'visibility': 0.8, 'fragility': 0.6},
    'bottle':   {'strength_needed': 0.5, 'stability': 0.5, 'deformability': 0.3,
                 'roll_tendency': 0.6, 'visibility': 0.8, 'fragility': 0.5},
    'plate':    {'strength_needed': 0.3, 'stability': 0.3, 'deformability': 0.2,
                 'roll_tendency': 0.5, 'visibility': 0.9, 'fragility': 0.7},
    'rock':     {'strength_needed': 0.7, 'stability': 0.8, 'deformability': 0.1,
                 'roll_tendency': 0.3, 'visibility': 0.5, 'fragility': 0.2},
    'vase':     {'strength_needed': 0.4, 'stability': 0.4, 'deformability': 0.2,
                 'roll_tendency': 0.4, 'visibility': 0.9, 'fragility': 0.8},
    'textured': {'strength_needed': 0.5, 'stability': 0.5, 'deformability': 0.4,
                 'roll_tendency': 0.5, 'visibility': 0.6, 'fragility': 0.5},
    'unknown':  {'strength_needed': 0.5, 'stability': 0.5, 'deformability': 0.5,
                 'roll_tendency': 0.5, 'visibility': 0.5, 'fragility': 0.5},
}


class VisualFeatureExtractor:
    """
    视觉特征提取器——从 RGB 图像中估计物体的 6 维物理特征。

    两种模式:
      - Mode A ('color_geom'): OpenCV 轮廓检测+几何分析 (无需GPU)
      - Mode B ('vision_model'): 视觉编码器推理 (需 torch, 预留接口)
    """

    def __init__(self, mode: str = 'color_geom', verbose: bool = False):
        self.mode = mode
        self.verbose = verbose
        self._last_features: Optional[dict] = None

        # Mode B 预留（接入 DINOv2/CLIP 等视觉模型）
        self._vision_model = None

    def extract(self, rgb: np.ndarray, depth: Optional[np.ndarray] = None,
                crop_bbox: Optional[Tuple] = None) -> dict:
        """
        从单张 RGB 图像提取 YLYW 6维物理特征（单视图接口）。
        """
        if self.mode == 'color_geom':
            features = self._extract_color_geom(rgb, depth, crop_bbox)
        elif self.mode == 'vision_model':
            features = self._extract_vision_model(rgb, depth, crop_bbox)
        else:
            features = dict(GEOMETRY_FEATURES['unknown'])

        self._last_features = features
        return features

    def extract_multiview(self, views: Dict[str, Dict[str, np.ndarray]]) -> dict:
        """
        多视角融合特征提取。

        Args:
            views: dict of {view_name: {'rgb': ndarray, 'depth': ndarray or None}}

        融合策略：
          1. 每张图像独立提取特征 + 几何类型 + 置信度
          2. 按置信度加权融合
          3. sideview 优先决定 roll_tendency（侧视图能看到滚动方向）
          4. depth 信息修正三维形状
          5. 任意视角检测到 'fragility' 高则提高整体 fragility
        """
        if not views:
            return dict(GEOMETRY_FEATURES['unknown'])

        voters = []  # list of (features, weight, geom_type)
        all_geoms = []

        for view_name, vdata in views.items():
            rgb = vdata.get('rgb')
            depth = vdata.get('depth')
            if rgb is None:
                continue

            feat, geom, conf = self._extract_with_confidence(rgb, depth)
            voters.append((feat, conf, geom))
            all_geoms.append(geom)

            if self.verbose:
                print(f"    [多视角][{view_name}] geom={geom:10s} conf={conf:.2f}")

        if not voters:
            return dict(GEOMETRY_FEATURES['unknown'])

        # 加权融合
        total_w = sum(w for _, w, _ in voters)
        if total_w == 0:
            total_w = 1e-6

        fused = {k: 0.0 for k in GEOMETRY_FEATURES['unknown']}
        for feat, w, _ in voters:
            for k in fused:
                fused[k] += feat.get(k, 0.5) * w / total_w

        # 安全策略：任何视角检测到高脆弱性则提高
        for feat, w, _ in voters:
            if feat.get('fragility', 0.5) > 0.7:
                fused['fragility'] = max(fused['fragility'], feat['fragility'])

        # sideview 优先决定 roll_tendency
        if 'sideview' in views:
            sv_feat, _, _ = self._extract_with_confidence(
                views['sideview']['rgb'], views['sideview'].get('depth'))
            fused['roll_tendency'] = sv_feat.get('roll_tendency', fused['roll_tendency'])

        if self.verbose:
            print(f"    [多视角融合] geom_votes={all_geoms} → fused={dict((k,round(v,3)) for k,v in fused.items())}")

        self._last_features = fused
        return fused

    def _extract_with_confidence(self, rgb: np.ndarray,
                                  depth: Optional[np.ndarray] = None) -> Tuple[dict, str, float]:
        """提取特征并返回几何类型和置信度"""
        if self.mode == 'color_geom':
            feat, geom, conf = self._extract_color_geom_wc(rgb, depth)
        else:
            feat = dict(GEOMETRY_FEATURES['unknown'])
            geom = 'unknown'
            conf = 0.3
        return feat, geom, conf

    def _extract_color_geom(self, rgb: np.ndarray, depth: Optional[np.ndarray],
                            bbox: Optional[Tuple]) -> dict:
        """
        颜色+几何模式（含深度修正三维形状）。
        """
        h, w = rgb.shape[:2]

        if bbox:
            x1, y1, x2, y2 = bbox
            roi = rgb[y1:y2, x1:x2]
        else:
            roi = rgb

        hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
        lower_obj = np.array([0, 30, 30])
        upper_obj = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower_obj, upper_obj)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return dict(GEOMETRY_FEATURES['unknown'])

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < 50:
            return dict(GEOMETRY_FEATURES['unknown'])

        x, y, wc, hc = cv2.boundingRect(largest)
        aspect = wc / max(hc, 1)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.04 * peri, True)
        n_vertices = len(approx)
        circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
        hull = cv2.convexHull(largest)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        # ---- 类型判定 ----
        if circularity > 0.85 and abs(1 - aspect) < 0.3:
            geom = 'sphere'
        elif 4 <= n_vertices <= 8 and abs(1 - aspect) < 0.4 and solidity > 0.9:
            geom = 'cube'
        elif circularity > 0.7 and abs(aspect - 1.5) < 0.8:
            geom = 'cylinder'
        elif solidity < 0.8:
            geom = 'rock'
        elif wc > hc * 1.8:
            geom = 'plate'
        elif hc > wc * 1.8:
            geom = 'bottle'
        else:
            geom = 'textured'

        features = dict(GEOMETRY_FEATURES.get(geom, GEOMETRY_FEATURES['unknown']))

        # ---- Step 5: 深度信息修正三维形状 ----
        if depth is not None:
            # 用轮廓bounding box裁剪depth ROI
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(depth.shape[1], x + wc)
            y2 = min(depth.shape[0], y + hc)
            depth_roi = depth[y1:y2, x1:x2]
            obj_depth = depth_roi[(depth_roi > 0) & (depth_roi < 10)]  # 排除无效和远景
            if len(obj_depth) > 10:
                z_extent = np.max(obj_depth) - np.min(obj_depth)
                # z_extent > 0.04m = 4cm 通常是有高度的物体
                if z_extent > 0.04:
                    features['strength_needed'] = min(1.0, features['strength_needed'] + z_extent * 0.3)
                    # depth跨度大 → 修正

        if self.verbose:
            print(f"[视觉特征] geom={geom:10s} circularity={circularity:.2f} "
                  f"vertices={n_vertices} solidity={solidity:.2f} "
                  f"features={features}")

        return features

    def _extract_color_geom_wc(self, rgb: np.ndarray,
                                depth: Optional[np.ndarray] = None) -> Tuple[dict, str, float]:
        """
        带置信度的几何特征提取。

        Returns:
            (features_dict, geom_type, confidence)
        """
        h, w = rgb.shape[:2]
        roi = rgb

        # 颜色分割
        hsv = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
        lower_obj = np.array([0, 30, 30])
        upper_obj = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower_obj, upper_obj)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return dict(GEOMETRY_FEATURES['unknown']), 'unknown', 0.1

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < 50:
            return dict(GEOMETRY_FEATURES['unknown']), 'unknown', 0.1

        # 几何参数
        x, y, wc, hc = cv2.boundingRect(largest)
        aspect = wc / max(hc, 1)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.04 * peri, True)
        n_vertices = len(approx)
        circularity = 4 * np.pi * area / (peri * peri) if peri > 0 else 0
        hull = cv2.convexHull(largest)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        # 类型判定 + 置信度
        # 置信度策略：几何参数越接近理想值，置信度越高
        if circularity > 0.85 and abs(1 - aspect) < 0.3:
            geom = 'sphere'
            conf = min(1.0, circularity)
        elif 4 <= n_vertices <= 8 and abs(1 - aspect) < 0.4 and solidity > 0.9:
            geom = 'cube'
            conf = min(1.0, solidity * 0.9 + 0.1)
        elif circularity > 0.7 and 1.0 < aspect < 3.0:
            # 侧视图下圆柱体是矩形，俯视图下是圆形
            geom = 'cylinder'
            conf = min(1.0, circularity * 0.6 + 0.2)
        elif solidity < 0.8:
            geom = 'rock'
            conf = 0.5
        elif wc > hc * 1.8:
            geom = 'plate'
            conf = 0.6
        elif hc > wc * 1.8:
            geom = 'bottle'
            conf = 0.6
        else:
            geom = 'textured'
            conf = 0.4

        features = dict(GEOMETRY_FEATURES.get(geom, GEOMETRY_FEATURES['unknown']))

        # 深度修正：使用RGB轮廓mask裁剪depth，只取物体深度
        if depth is not None:
            # 用HSV mask裁剪depth ROI
            d_roi = depth[max(0,y):min(h,y+hc), max(0,x):min(w,x+wc)]
            # 用轮廓mask排除背景
            obj_mask = mask[max(0,y):min(h,y+hc), max(0,x):min(w,x+wc)] if mask.size > 0 else None
            
            if obj_mask is not None and obj_mask.size > 0:
                obj_d = d_roi[obj_mask > 0]
            else:
                obj_d = d_roi[(d_roi > 0) & (d_roi < 3.0)]  # 3m以内视为有效物体
            
            if len(obj_d) > 10:
                z_min = np.percentile(obj_d, 5)
                z_max = np.percentile(obj_d, 95)
                z_extent = z_max - z_min
                
                if 0.02 < z_extent < 2.0:  # 2cm~2m有效范围
                    features['strength_needed'] = min(1.0, features['strength_needed'] + z_extent * 0.3)
                    # 深度跨度大(>6cm) → 更像bottle/cylinder而非sphere
                    if geom == 'sphere' and z_extent > 0.06:
                        geom = 'cylinder'
                        features.update(GEOMETRY_FEATURES.get('cylinder'))
                        conf = 0.5
                    # depth跨度很小 → 扁平的plate
                    if z_extent < 0.03 and (geom == 'cube' or geom == 'sphere'):
                        pass  # 维持原状，因为俯视图下plate也可能是圆形

        return features, geom, conf

    def _extract_vision_model(self, rgb: np.ndarray, depth: Optional[np.ndarray],
                               bbox: Optional[Tuple]) -> dict:
        """
        视觉模型模式（预留接口）。
        用 DINOv2/CLIP 等视觉模型从图像提取物体向量 → 映射物理特征。
        """
        # 预留：接入 torch 视觉模型的接口
        if self._vision_model is None:
            # 这里尝试导入 vision model
            try:
                import torch  # noqa
                import torchvision.models as models  # noqa
                # model = models.resnet18(pretrained=True)
                # self._vision_model = model
                features = dict(GEOMETRY_FEATURES['unknown'])
            except ImportError:
                features = dict(GEOMETRY_FEATURES['unknown'])
            if self.verbose:
                print("[视觉特征] 视觉模型模式：需安装 torch 和 torchvision。回退到未知特征。")
        else:
            features = dict(GEOMETRY_FEATURES['unknown'])

        return features

    def get_last_features(self) -> dict:
        """获取最近一次提取的特征"""
        return dict(self._last_features) if self._last_features else dict(GEOMETRY_FEATURES['unknown'])
