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
    # PCA 主轴矩阵(3x3, 列=长/中/短轴, 相机系单位向量)。供 6D 抓取姿态构建。
    axes: np.ndarray = field(default_factory=lambda: np.eye(3))
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
                   label: str = "object",
                   all_clouds: Optional[List[np.ndarray]] = None,
                   view_direction: Optional[np.ndarray] = None,
                   num_clouds: Optional[int] = None
                   ) -> Optional[ObjectFeatures]:
    """从物体点云提取 ObjectFeatures(含 YLYW 特征)。

    参数:
      all_clouds    : 场景内全部物体的点云列表(不含本物体)，用于算邻域障碍密度
                      与场景显著度。不传则 obstacle_density≈0、saliency 退化为自身体积。
      view_direction: 观察/相机方向(基座系单位向量)。默认 GlobalZ 朝上(俯视相机)。
      num_clouds    : 场景内物体总数(用于归一化障碍密度占比)。
    """
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
    # 主轴矩阵：列分别对应 长/中/短 轴(由协方差特征值降序)。
    # 全部约定 z 分量非负, 与 short 轴的方向轴对齐。
    _axes = eigvecs.copy()
    for _i in range(3):
        if _axes[_i, 2] < 0:
            _axes[:, _i] = -_axes[:, _i]

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

    # 质量/力估计（由体积×密度）
    density = config.default_density_kg_m3
    mass_kg = volume * density
    strength_needed = min(1.0, mass_kg / 2.0 + 0.1)
    weight_ratio = mass_kg / 2.0

    # —— 2026-08: 把原“常数占位”维度改为可感知/可计算，见下方各估计器 ——
    # 可见性：自身点云在包围盒内的填充率(越完整越可见)
    visibility = _estimate_visibility(pts, center, dims, config)
    # 遮挡：相对观察方向(相机近似沿 -Z/前向)的点云缺口覆盖率
    occlusion = _estimate_occlusion(pts, center, dims, view_direction)
    # 障碍密度：邻域内其它物体点数占比(需要场景级 all_clouds；默认约0)
    obstacle_density = _estimate_obstacle_density(center, all_clouds, num_clouds)
    # 脆弱性：几何脆弱度(薄壁/小曲率半径)，可由 Yolo 类别先验再覆盖
    fragility = _geometric_fragility(dims, curvature)
    # 可变形性：曲率分布 → 表面刚柔估计(规则小曲率=刚直, 大而弥散=柔)
    deformability = _estimate_deformability(pts, curvature)
    # 任务优先级：由几何显著性派生(体积+可见性)——任务层可再覆盖
    saliency = _scene_saliency(center, dims, visibility, all_clouds)

    features = {
        "stability": float(stability),          # 真实感知(几何+曲率)
        "roll_tendency": float(roll_tendency),  # 真实感知(派生)
        "strength_needed": float(strength_needed),  # 真实感知(体积×密度→质量)
        "_mass_kg": float(mass_kg),             # 感知质量(kg)，供上层力/优先级
        # ---- 2026-08: 已由“常数占位”改为可感知/可计算 ----
        "fragility": float(fragility),          # 几何脆弱度+类别先验
        "reachability": float(reachability),    # 真实感知(法向/朝向)
        "grasp_surface_quality": float(surface_quality),  # 真实感知(曲率/法向)
        "support_area": float(support),         # 真实感知(投影面积)
        "occlusion": float(occlusion),          # 真实感知(观察缺口)
        "obstacle_density": float(obstacle_density),  # 真实感知(邻域障碍)
        "task_priority": float(saliency),       # 场景显著度派生(天花板=任务层可覆盖)
        "weight_ratio": float(weight_ratio),    # 真实感知(派生)
        "visibility": float(visibility),        # 真实感知(点云完整度)
        "deformability": float(deformability),  # 真实感知(曲率分布)
    }

    return ObjectFeatures(
        dimensions_m=dims,
        center_m=tuple(center),
        principal_axis=axis,
        axes=_axes,
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


# ============ 2026-08: “常数占位”特征的真实化估计器 ============
# 目标：让 fragility / occlusion / obstacle_density / task_priority /
# visibility / deformability 由点云+几何+场景真实计算，逐物体不同，
# 具备样本判别力(不再全是 0.5/0.1/0.7/0.9 的固定值)。


def _estimate_visibility(pts: np.ndarray, center: np.ndarray,
                         dims, config: "FeaturesConfig") -> float:
    """可见性：物体表面点云在自身体包围盒内的填充完整度 [0,1]。

    推理：同样体积的物体，如果点云越能填满其包围盒，说明更多表面
    暴露在观察方向(遮挡/自遮蔽越少) → 可见性越高。用“包围盒切分”的
    占用体素比例近似；点数太少时按点数/期望点数回落。
    """
    n = len(pts)
    if n < 8:
        return 1.0
    # 期望能覆盖表面的点数(与表面面积成正比)；点太少→不完全可见
    surf_m2 = 2.0 * (dims[0] * dims[1] + dims[1] * dims[2] + dims[0] * dims[2])
    # 用点密度经验：1cm 网格约 1 点 → 表面面积(㎡)换算成期望点数
    expected = max(20, int(surf_m2 / (0.01 * 0.01)))     # 每 cm² 约 1 点
    completeness = min(1.0, n / expected)
    # 占用体素比例：把包围盒分成 5³ 网格，看多少被占据(受观察方向影响)
    try:
        ncell = 5
        lo = np.asarray(center) - np.asarray(dims) / 2.0
        idx = np.floor((pts - lo) / (np.asarray(dims) / ncell + 1e-9)).astype(int)
        idx = np.clip(idx, 0, ncell - 1)
        occupied = len(np.unique(idx[:, 0] * ncell * ncell + idx[:, 1] * ncell + idx[:, 2]))
        fill = occupied / (ncell ** 3)
    except Exception:
        fill = 0.5
    return float(max(0.05, min(1.0, 0.6 * completeness + 0.4 * fill)))


def _estimate_occlusion(pts: np.ndarray, center: np.ndarray, dims,
                        view_direction: Optional[np.ndarray] = None) -> float:
    """遮挡：相对观察方向的表面点云缺口/空洞程度 [0,1](0=无遮挡,1=严重)。

    把物体沿观察方向(默认 +Z 俯视)投影到垂直平面，点云的投影覆盖应与
    物体投影面积相当；被别的物体/自遮蔽挡住时，投影有空洞 → 覆盖不足。
    """
    n = len(pts)
    if n < 8:
        return 1.0
    v = np.array([0.0, 0.0, 1.0]) if view_direction is None else \
        np.asarray(view_direction, dtype=float) / (np.linalg.norm(view_direction) + 1e-9)
    # 投影基(垂直于 v 的平面)
    ref = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(ref, v)) > 0.9:
        ref = np.array([0.0, 1.0, 0.0])
    u1 = np.cross(v, ref); u1 /= (np.linalg.norm(u1) + 1e-9)
    u2 = np.cross(v, u1); u2 /= (np.linalg.norm(u2) + 1e-9)
    p = pts - center
    proj = np.column_stack([p @ u1, p @ u2])
    # 网格覆盖比例
    try:
        grid = 16
        lo = proj.min(axis=0); hi = proj.max(axis=0)
        span = np.maximum(hi - lo, 1e-6)
        idx = np.clip(np.floor((proj - lo) / (span / grid)).astype(int), 0, grid - 1)
        occupied = len(np.unique(idx[:, 0] * grid + idx[:, 1])) / (grid * grid)
        # 投影占据高 → 表面连续无遮挡；低 → 有空洞/自遮蔽
        occlusion = min(1.0, max(0.0, 1.0 - occupied * 1.5))
    except Exception:
        occlusion = 0.2
    return float(occlusion)


def _estimate_obstacle_density(center: np.ndarray,
                               all_clouds: Optional[List[np.ndarray]],
                               num_clouds: Optional[int] = None) -> float:
    """障碍密度：邻域内其它物体对该物体的“拥挤程度” [0,1]。

    统计以本物体为中心、半径=场景物体平均尺度几倍的球内其它物体点数占比；
    物体越多且越近，密度越高。无场景信息时归 0。
    """
    if not all_clouds or len(all_clouds) == 0:
        return 0.0
    n_others = 0
    r_search = 0.12                                  # 邻域半径(米)
    for oc in all_clouds:
        if oc is None or len(oc) == 0:
            continue
        d2 = np.sum((np.asarray(oc, dtype=float) - np.asarray(center)) ** 2, axis=1)
        n_others += int((d2 < r_search * r_search).sum())
    # 归一化：单位体积点密度的饱和映射
    avg_pts = sum(len(c) for c in all_clouds if c is not None) / max(len(all_clouds), 1)
    density = n_others / max(float(avg_pts * max(len(all_clouds), 1)), 1e-6)
    return float(min(1.0, density * 1.2))


def _geometric_fragility(dims, curvature: float) -> float:
    """几何脆弱性 [0,1]：壁越薄/曲率越小越脆(受撞击易碎/易变形)。

    脆弱的物体特征：一个维度显著小于另两个(薄片)、或中等曲率(壳体表面)。
    用“最小维度/最大维度”比 value：极扁(平板)或极薄 → 脆；接近球形 → 韧。
    类别先验(Yolo)可在上层再乘以/覆盖这个几何值。
    """
    d = np.sort(np.asarray(dims, dtype=float))[::-1]
    a, b, c = d[0], d[1], max(d[2], 1e-6)
    thinness = 1.0 - min(1.0, c / max(a, 1e-6) * 2.5)   # c/a 越小越薄→越脆
    # 中等曲率(壳体)比纯平面更容易是易碎外壳；高曲率(球)相对韧
    shell = 1.0 - abs(curvature - 0.4)
    return float(max(0.05, min(0.95, 0.6 * thinness + 0.4 * shell)))


def _estimate_deformability(pts: np.ndarray, curvature: float) -> float:
    """可变形性 [0,1]：由表面几何推断刚柔。

    关键是“薄壁可弯”而非“各向同性”：
      - 柔韧可变形：至少一个维度显著薄(薄板/膜/软管)，可弯曲；
      - 刚硬不可变形：三个维度都成实体块(立方体/球)或形状规整(棒)。
    用“最小/最大维度比”奖励薄度(→柔)。
    """
    n = len(pts)
    if n < 8:
        return 0.3
    c = np.asarray(pts, dtype=float)
    cov = np.cov((c - c.mean(axis=0)).T)
    ev = np.linalg.eigvalsh(cov)
    ev = np.clip(ev, 1e-12, None)
    longest = np.sqrt(ev[2])
    shortest = np.sqrt(ev[0])
    # 薄度：最小尺度远小于最大尺度 → 可弯 → 柔
    thinness = 1.0 - min(1.0, (shortest / max(longest, 1e-9)) / 4.0)
    return float(max(0.05, min(0.95, thinness)))


def _scene_saliency(center: np.ndarray, dims, visibility: float,
                    all_clouds: Optional[List[np.ndarray]]) -> float:
    """场景显著度 → 任务优先级 [0,1]。

    任务优先级(抽象任务层)在没有明确任务指令时，用几何显著性近似：
    体积大、可见性好 → 更“显眼/易抓” → 优先级偏高。
    有任务模块时此值可被任务规划覆盖。
    """
    vol = float(np.prod(np.asarray(dims)))
    # 体积映射(参照常见桌面物体 0.05m³ 量级)
    vol_score = min(1.0, vol / 0.05)
    return float(max(0.1, min(1.0, 0.7 * vis_score(visibility) + 0.3 * vol_score)))


def vis_score(visibility: float, a: float = 0.4, b: float = 0.6) -> float:
    """可见性→优先级权重换算(可替换为任何单调映射)。"""
    return a + b * float(visibility)

