"""物体特征分析模块 —— 从深度点云提取物体几何特征，供 YLYW 感知。

输入：分割后的单个物体点云(相机系) + 地面平面(法向量/高度)。
输出：`ObjectFeatures`(包围盒三轴、质心、6D 位姿、曲率、支撑面、
      可达性、表面质量、质量/力估计 等)，这些正是 YLYW 先验手册
      `PriorManual.perceive_and_encode()` 期望的 13 维特征字段。

物体分割算法(简单而工程可用)：
  1. RANSAC 拟合地面平面，移除地面点
  2. 剩余点按欧氏距离聚类(DBSCAN 式)，得到一个个物体
  3. 对每个聚类做 PCA → 包围盒 → 特征
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .config import FeaturesConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class ObjectFeatures:
    """单个物体的感知特征(13维，已归一化到 YLYW 可用的 [0,1])。"""

    # —— 几何 ——
    dimensions_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # 长宽高(米)
    center_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)      # 质心(相机系)
    principal_axis: np.ndarray = field(default_factory=lambda: np.zeros(3))
    curvature: float = 0.5          # 平均曲率
    volume_m3: float = 0.0
    n_points: int = 0

    # —— YLYW 13 维特征 ——
    features: dict = field(default_factory=dict)

    # —— 识别/元信息 ——
    label: str = "object"
    confidence: float = 1.0

    @property
    def approachable_pose(self) -> np.ndarray:
        """抓取参考点(质心 + 法向主轴)，供逆解使用。"""
        return np.array([self.center_m[0], self.center_m[1], self.center_m[2]])

    def brief(self) -> str:
        d = self.dimensions_m
        return (
            f"{self.label}(#pts={self.n_points}, {d[0]*1000:.0f}x{d[1]*1000:.0f}"
            f"x{d[2]*1000:.0f}mm, 曲率={self.curvature:.2f})"
        )


# ============ 点云分割与特征提取 ============

def _fit_ground_plane(points: np.ndarray, tolerance: float) -> Tuple[Optional[np.ndarray], Optional[float]]:
    """RANSAC 拟合最大平面。返回 (法向量, 常数d) 使 normal·x + d = 0。"""
    if len(points) < 4:
        return None, None
    best_normal, best_d, best_inliers = None, None, -1
    rng = np.random.default_rng(42)
    for _ in range(50):
        idx = rng.choice(len(points), 3, replace=False)
        p = points[idx]
        v1 = p[1] - p[0]
        v2 = p[2] - p[0]
        normal = np.cross(v1, v2)
        nrm = np.linalg.norm(normal)
        if nrm < 1e-9:
            continue
        normal = normal / nrm
        d = -normal @ p[0]
        if normal[2] < 0:      # 朝上为正
            normal, d = -normal, -d
        dists = np.abs(points @ normal + d)
        inliers = int((dists < tolerance).sum())
        if inliers > best_inliers:
            best_inliers, best_normal, best_d = inliers, normal, d
    return best_normal, best_d


def segment_objects(cloud: np.ndarray, config: FeaturesConfig) -> List[np.ndarray]:
    """点云→物体分割。返回每物体点云列表。"""
    if len(cloud) < 5:
        return []

    # 1. 地面分割
    normal, d = _fit_ground_plane(cloud, config.ground_tolerance)
    if normal is not None and normal[2] > 0.6:
        above = cloud[cloud @ normal + d > config.ground_tolerance * 0.5]
    else:
        above = cloud

    if len(above) < config.min_points:
        return []

    # 2. 欧氏聚类：体素化 + 26-邻域 union-find
    cell = config.max_cluster_dist
    coords = np.floor(above / cell).astype(np.int64)
    keys = [(int(c[0]), int(c[1]), int(c[2])) for c in coords]
    cell2id = {}        # 体素key -> 体素id
    for k in keys:
        if k not in cell2id:
            cell2id[k] = len(cell2id)
    id2cell = {v: k for k, v in cell2id.items()}
    K = len(cell2id)

    parent = list(range(K))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a in range(K):
        x, y, z = id2cell[a]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == dy == dz == 0:
                        continue
                    nb = cell2id.get((x + dx, y + dy, z + dz))
                    if nb is not None:
                        union(a, nb)

    root_to_cells = {}
    for cid in range(K):
        root_to_cells.setdefault(find(cid), []).append(cid)

    cell_mask = {}      # 每个体素对应的点布尔索引
    for i in range(len(above)):
        cid = cell2id[keys[i]]
        if cid not in cell_mask:
            cell_mask[cid] = np.zeros(len(above), dtype=bool)
        cell_mask[cid][i] = True

    objects = []
    for root, cids in root_to_cells.items():
        mask = np.zeros(len(above), dtype=bool)
        for cid in cids:
            mask |= cell_mask[cid]
        pts = above[mask]
        if len(pts) >= config.min_points:
            objects.append(pts)
    return objects


def analyze_object(points: np.ndarray, config: FeaturesConfig,
                   label: str = "object") -> Optional[ObjectFeatures]:
    """从物体点云提取 ObjectFeatures(含 YLYW 特征)。"""
    n = len(points)
    if n < config.min_points:
        return None

    pts = np.asarray(points, dtype=np.float64)
    center = pts.mean(axis=0)

    # PCA 主轴
    centered = pts - center
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvecs = eigvecs[:, order]
    eigvals = eigvals[order]
    axis = eigvecs[:, 0]
    if axis[2] < 0:
        axis = -axis

    # 包围盒尺寸(沿主轴)
    proj = centered @ eigvecs
    mins = proj.min(axis=0)
    maxs = proj.max(axis=0)
    dims = tuple(float(max(maxs[i] - mins[i], 0.005)) for i in range(3))

    volume = dims[0] * dims[1] * dims[2]

    # 曲率(局部 PCA 特征值比)
    curvature = _estimate_curvature(pts, config.curvature_neighbors)
    # 表面质量 = 越平越易抓
    surface_quality = max(0.2, 1.0 - curvature * 1.5)
    # 支撑面积(地面投影的覆盖度) —— 用底面椭圆近似
    support = float(min(1.0, (dims[0] * dims[1]) / 0.01))

    # 可达性：法向越朝上越可达
    normal_upwardness = abs(axis[2])
    reachability = 0.4 + normal_upwardness * 0.6

    # 稳定性 / 滚动倾向
    stability = max(0.1, 1.0 - curvature * 1.2)
    roll_tendency = 0.1 + (1.0 - stability) * 0.3

    # 质量/力估计
    density = config.default_density_kg_m3
    mass_kg = volume * density
    strength_needed = min(1.0, mass_kg / 2.0 + 0.1)
    weight_ratio = mass_kg / 2.0

    features = {
        "stability": float(stability),          # 真实感知(几何+曲率)
        "roll_tendency": float(roll_tendency),  # 真实感知(派生)
        "strength_needed": float(strength_needed),  # 真实感知(体积×密度→质量)
        # ---- 以下为“暂用常数占位”，尚未接入真实感知/Yolo类别先验 ----
        # 实机/论文前需替换为: 脆弱性(Yolo类别/材质), 遮挡(深度缺口),
        # 障碍密度(邻域物体), 任务优先级(任务层), 可见性(点云完整度),
        # 可变形性(类别/材质)。目前取固定值以联调链路。
        "fragility": 0.5,                       # 常数占位(可由 Yolo 类别覆盖)
        "reachability": float(reachability),    # 真实感知(法向/朝向)
        "grasp_surface_quality": float(surface_quality),  # 真实感知(曲率/法向)
        "support_area": float(support),         # 真实感知(投影面积)
        "occlusion": 0.1,                       # 常数占位
        "obstacle_density": 0.1,                # 常数占位
        "task_priority": 0.7,                   # 常数占位
        "weight_ratio": float(weight_ratio),    # 真实感知(派生)
        "visibility": 0.9,                      # 常数占位
        "deformability": 0.1,                   # 常数占位
    }

    return ObjectFeatures(
        dimensions_m=dims,
        center_m=tuple(center),
        principal_axis=axis,
        curvature=float(curvature),
        volume_m3=float(volume),
        n_points=n,
        features=features,
        label=label,
    )


def _estimate_curvature(points: np.ndarray, k: int) -> float:
    """估计物体表面平滑度/弯曲度 [0,1]。

    用物体点云对“最佳拟合平面”的残差比切平面尺度来度量：
      - 平板/平面朝上: 残差小 → 曲率低(易 top-down 抓取)
      - 立方体: 中
      - 球体: 残差大 → 曲率高
    k 参数保留用于兼容(整体点云估计更稳健)。
    """
    n = len(points)
    if n < 4:
        return 0.5
    pts = np.asarray(points, dtype=np.float64)
    center = pts.mean(axis=0)
    c = pts - center
    if np.sum(np.abs(c)) < 1e-9:
        return 0.0
    cov = np.cov(c.T)
    eigvals = np.linalg.eigvalsh(cov)
    eigvals = np.clip(eigvals, 1e-12, None)
    resid = np.sqrt(eigvals[0])     # 法向散布(对最佳平面残差)
    scale = np.sqrt(max(float(eigvals[1] + eigvals[2]), 1e-9))  # 平面内尺度
    ratio = resid / max(scale, 1e-9)
    return float(min(1.0, ratio * 3.0))
