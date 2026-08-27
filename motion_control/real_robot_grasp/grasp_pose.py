"""6D 抓取位姿生成模块 —— 把 PCA 几何信息转化为完整末端位姿 [x,y,z,rx,ry,rz]。

背景（2026-08 研究推进）：
  旧实现只把质心作为抓取点(x,y,z)，姿态硬编码为 {pitch 由 approach_angle 决定,
  roll=-90°, yaw=0°}，意味着"夹爪永远朝下、只改俯仰"——本质是 3D 目标点抓取，
  物体的长轴/短轴/主方向没有真正转化为夹爪朝向，长方体/圆柱/球可能用几乎相同动作。

本模块解决：
  1. 用 PCA 主轴(principal_axis) + 三轴尺寸构建夹爪坐标系旋转矩阵 R。
  2. 按形状(平板/长条/柱体/块状/不规则)生成多个候选抓取姿态。
  3. 每个候选 = 完整 6D 位姿 [x,y,z,rx,ry,rz]（米 + 欧拉角 RPY 度，机械臂接口格式）。
  4. 用 几何贴合×可达性×YLYW谨慎度 打分，多候选比较后选最优。
  5. 保留方向向量在相机系↔基座系之间的变换。

依赖：numpy + scipy(Rotation)。均在现有 requirements 中。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .object_features import ObjectFeatures
from .ylyw_grasp_planner import GraspPlan

LOGGER = logging.getLogger(__name__)

try:
    from scipy.spatial.transform import Rotation as _R
    _HAS_SCIPY = True
except Exception:  # noqa: BLE001
    _HAS_SCIPY = False


# ============ 形状分类 ============

@dataclass
class ShapeClass:
    """物体几何形状类别(由三轴尺寸比例判定)。"""
    name: str              # plate | rod | column | block | sphere | irregular
    aspect_ratio: float    # 最长轴 / 最短轴
    flatness: float        # (第二长-最短)/最长，衡量扁平度
    grip_dim: int          # 夹爪开合方向应沿的 PCA 轴索引(0,1,2)
    approach_type: str     # top_down | side_grip | multi


def classify_shape(dims: Tuple[float, float, float]) -> ShapeClass:
    """根据物体包围盒三轴尺寸比例判定抓取形状类别。

    dims 已按 PCA 主轴排序 dims[0]>=dims[1]>=dims[2](最长/中/最短)。
    若调用方未按降序传，这里内部强制降序，避免误判。"""
    d = np.asarray(sorted(dims, reverse=True), dtype=float)
    a, b, c = d[0], d[1], d[2]           # a 长轴, b 中轴, c 短轴
    a = max(a, 1e-6)
    aspect = a / max(c, 1e-6)            # 长/短
    flatness = (b - c) / a               # (中-短)/长 ≈ 扁平度
    # 平板：a 与 b 接近且都远大于 c(短轴很薄)
    if c < 0.6 * b and b > 0.7 * a:
        return ShapeClass("plate", aspect, flatness, 2, "top_down")
    # 长条/棒状：a >> b ≈ c(一条边特别长)
    if aspect > 2.2 and b < 0.55 * a:
        return ShapeClass("rod", aspect, flatness, 1, "side_grip")
    # 柱体(圆柱/瓶/棱柱)：a 明显长但 b≈c(横向一个方向是回转轴)
    if aspect > 1.6:
        return ShapeClass("column", aspect, flatness, 1, "side_grip")
    # 块状(立方体/长方体)：三轴差不太多
    if aspect < 1.6 and flatness < 0.35:
        return ShapeClass("block", aspect, flatness, 2, "multi")
    # 不规则
    return ShapeClass("irregular", aspect, flatness, 2, "multi")


def _make_approach_axis(shape: ShapeClass, axis3: np.ndarray,
                        normal: np.ndarray) -> np.ndarray:
    """确定接近方向(末端 -Z 应指向的方向，基座系)。

    - top_down(平板/块状)：接近方向 = 地面法向朝上 → 夹爪自顶向下(-Z 指向 -up)。
    - side_grip(长条/柱体)：接近方向 = 垂直长轴的侧面方向(由角度参数旋转)。
    """
    if shape.approach_type == "top_down":
        return normal                     # 沿支撑面法向(朝上)接近
    # side_grip: 接近方向沿长轴垂直平面内，由候选姿态角度决定，此处返回长轴用于旋转
    return axis3


# ============ 旋转矩阵 → 欧拉角 ============

def _rpy_deg(R: np.ndarray) -> Tuple[float, float, float]:
    """旋转矩阵 → (rx,ry,rz) 欧拉角(度)。

    采用**内旋 XYZ(intrinsic X-Y-Z)** = MyCobot/pymycobot 的 RPY 约定：
    机械臂收到 [Rx,Ry,Rz] 后，先绕自身工具X转Rx、再绕新Y转Ry、再绕新Z转Rz
    得到最终工具姿态。对应 scipy 的 `as_euler('XYZ', intrinsic)`。
    验证：工具Z朝下矩阵在 t=[(1,0,0),(0,0,1),(0,-1,0)] 时给出 (180,0,0)。
    """
    if not _HAS_SCIPY:
        raise RuntimeError("需要 scipy 做旋转矩阵→欧拉角；请 pip install scipy")
    r = _R.from_matrix(R)
    # 内旋 XYZ = 外旋 ZYX。as_euler('XYZ', degrees=True) 即内旋 XYZ。
    return tuple(map(float, r.as_euler("XYZ", degrees=True)))


def _mat(rx, ry, rz):
    """欧拉角(度) → 旋转矩阵(与 _rpy_deg 互逆，内旋 XYZ / MyCobot RPY)。"""
    if not _HAS_SCIPY:
        raise RuntimeError("需要 scipy；请 pip install scipy")
    return _R.from_euler("XYZ", [rx, ry, rz], degrees=True).as_matrix()


# ============ 6D 位姿 候选 ============

@dataclass
class GraspCandidate:
    """一个抓取候选：6D 方向 + 打分。位置(x,y,z)由质心/候选接触点决定。"""
    name: str                     # 候选名: top_down / side_axis1_0 / side_axis1_90 ...
    approach_axis: np.ndarray     # 接近方向(基座系, 单位向量)
    x_axis: np.ndarray            # 夹爪开合轴(基座系)
    # 接近点相对质心的偏移(基座系,mm)——用于把夹爪中心对准接触点而非仅质心
    offset_mm: np.ndarray = None
    # 2026-08-27：物体表面实际抓取接触点(基座系,mm)——非质心时由它定位
    contact_base_mm: np.ndarray = None
    # 2026-08-27：接触点局部表面平整度 [0,1]，供评分降权边缘/曲面
    local_planarity: float = 0.0
    score: float = 0.0            # 综合得分
    fit: float = 0.0              # 几何贴合度(夹爪开合宽度 vs 抓取维度)
    reach: float = 0.0            # 可达性
    cautious: float = 0.0         # YLYW 谨慎度调制


class _Frame:
    """由完整 PCA 主轴构建的物体局部坐标系(基座系方向)。

    使用 ObjectFeatures.axes (3x3, 列=长/中/短轴, 相机系) 变换到基座系：
      long / mid / short = 物体真实主轴方向。
    """

    def __init__(self, obj: ObjectFeatures, tfr_R: np.ndarray):
        # axes 列顺序: [长轴, 中轴, 短轴] (由协方差特征值降序)
        axes = np.asarray(obj.axes, dtype=np.float64).reshape(3, 3)
        self.long = tfr_R @ (axes[:, 0] / (np.linalg.norm(axes[:, 0]) + 1e-9))
        self.mid = tfr_R @ (axes[:, 1] / (np.linalg.norm(axes[:, 1]) + 1e-9))
        self.short = tfr_R @ (axes[:, 2] / (np.linalg.norm(axes[:, 2]) + 1e-9))
        # 支撑面法向：短轴在全局Z的分量方向；若物体侧躺则抓侧面。
        self.up = self.short if self.short[2] >= 0 else -self.short
        # 长轴在水平面投影(夹爪开合轴备选)
        lh = self.long.copy(); lh[2] = 0.0
        self.long_h = lh / (np.linalg.norm(lh) + 1e-9) if np.linalg.norm(lh) > 1e-6 \
            else np.array([1.0, 0.0, 0.0])
        # 短轴在水平面投影
        sh = self.short.copy(); sh[2] = 0.0
        self.short_h = sh / (np.linalg.norm(sh) + 1e-9) if np.linalg.norm(sh) > 1e-6 \
            else np.array([1.0, 0.0, 0.0])


def build_candidates(obj: ObjectFeatures, plan: GraspPlan,
                     tfr_R: np.ndarray,
                     grip_half_open_mm: float = 60.0) -> List[GraspCandidate]:
    """为物体生成多个 6D 抓取候选姿态(方向部分)。位置由质心+偏移给。

    参数:
      obj          : 物体特征(PCA 主轴/尺寸)
      plan         : YLYW 抓取方案(提供谨慎度调制)
      tfr_R        : 相机→基座 旋转矩阵(方向变换，不含平移)
      grip_half_open_mm : 夹爪张开半宽(mm)，用于几何贴合度评估

    返回按 score 降序的候选列表。候选接近轴/开合轴均为基座系单位向量。
    """
    dims = np.asarray(obj.dimensions_m) * 1000.0        # to mm
    dl = np.sort(dims)[::-1]                            # [长,中,短] mm
    frame = _Frame(obj, tfr_R)
    shape = classify_shape(obj.dimensions_m)

    ylyw_cautious = plan.yao_quality if plan.yao_quality > 0 else 0.5
    ylyw_angle = float(plan.approach_angle_deg)         # YLYW 给出的接近角(度)
    cands: List[GraspCandidate] = []

    def push(name, z_axis, x_axis, fit, offset_z=None):
        # 正交化：夹爪开合轴 x 必须垂直于接近轴 z(否则旋转矩阵非正交/左手系)。
        z_axis = np.asarray(z_axis, dtype=float)
        x_axis = np.asarray(x_axis, dtype=float)
        zn = np.linalg.norm(z_axis)
        if zn < 1e-9:
            z_axis = np.array([0.0, 0.0, 1.0]); zn = 1.0
        z_axis /= zn
        # 把 x 投影到垂直 z 的平面
        x_axis = x_axis - np.dot(x_axis, z_axis) * z_axis
        xn = np.linalg.norm(x_axis)
        if xn < 1e-6:                                  # 退化：任取垂直方向
            ref = np.array([1.0, 0.0, 0.0])
            if abs(np.dot(ref, z_axis)) > 0.9:
                ref = np.array([0.0, 1.0, 0.0])
            x_axis = ref - np.dot(ref, z_axis) * z_axis
            xn = np.linalg.norm(x_axis) + 1e-9
        x_axis /= xn
        y_axis = np.cross(z_axis, x_axis)
        y_axis /= (np.linalg.norm(y_axis) + 1e-9)
        reach = 0.4 + abs(z_axis[2]) * 0.6              # 接近越朝下越可达
        score = 0.55 * fit + 0.25 * reach + 0.20 * ylyw_cautious
        cands.append(GraspCandidate(
            name=name, approach_axis=z_axis, x_axis=x_axis,
            offset_mm=np.array([0.0, 0.0, float(offset_z)]) if offset_z else None,
            score=float(score), fit=float(fit), reach=float(reach),
            cautious=float(ylyw_cautious),
        ))

    # ── 候选1: 自顶向下(夹爪下压 / 开合沿水平长轴) —— 通用且可达性高 ——
    fit_top = min(1.0, grip_half_open_mm / max(dl[0], 1e-3))
    push("top_down", -frame.up, frame.long_h, fit_top)

    # ── 候选2: 侧面法向接近(开合沿长轴水平投影) ——
    contact_mm = max(dl[1], dl[2] * 1.1)
    fit_side = min(1.0, grip_half_open_mm / max(contact_mm, 1e-3))
    push("side_grip", -frame.up, frame.long_h, fit_side, dl[1] * 0.5)

    # ── 候选3/4: 棒状/柱体专用, 开合沿短轴/长轴 ——
    if shape.approach_type == "side_grip" or shape.name == "rod":
        push("side_grip_short", -frame.up, frame.short_h,
             min(1.0, grip_half_open_mm / max(dl[2], dl[2] * 0.5 + 1e-3)),
             dl[2] * 0.5)
        push("side_grip_long", -frame.up, frame.long_h,
             min(1.0, grip_half_open_mm / max(dl[1], dl[1] * 0.5 + 1e-3)),
             dl[1] * 0.5)

    if ylyw_angle != 0.0:
        # 用 YLYW 接近角对 top_down 的接近方向做侧倾调制，形成"随卦变"的接近姿态。
        rot = _R.from_rotvec(frame.long_h * np.deg2rad(ylyw_angle)).as_matrix()
        z_mod = rot @ (-frame.up)
        nrm = np.linalg.norm(z_mod)
        if nrm > 1e-9:
            push("top_down_ylyw", z_mod / nrm, frame.long_h, fit_top)

    if not cands:
        push("fallback", np.array([0.0, 0.0, -1.0]), frame.long_h, 0.5)

    cands.sort(key=lambda c: c.score, reverse=True)
    return cands


def to_rpy(cand: GraspCandidate) -> Tuple[float, float, float]:
    """候选 → (rx,ry,rz) 欧拉角(度)。"""
    y = np.cross(cand.approach_axis, cand.x_axis)
    y /= (np.linalg.norm(y) + 1e-9)
    R = np.column_stack([cand.x_axis, y, cand.approach_axis])
    return _rpy_deg(R)


def best_6d(obj: ObjectFeatures, plan: GraspPlan, tfr_R: np.ndarray,
            grasp_xyz_base_mm: np.ndarray,
            grip_half_open_mm: float = 60.0):
    """便捷入口：返回 (最优候选, 完整6D位姿[x,y,z,rx,ry,rz])。

    grasp_xyz_base_mm: 质心在基座坐标(mm)。offset 会叠加到 z。
    """
    cands = build_candidates(obj, plan, tfr_R, grip_half_open_mm)
    best = cands[0]
    rx, ry, rz = to_rpy(best)
    x, y, z = grasp_xyz_base_mm
    if best.offset_mm is not None:
        z = float(z) + float(best.offset_mm[2])
    pose6d = np.array([float(x), float(y), float(z), rx, ry, rz])
    return best, pose6d, cands


# =====================================================================
# 2026-08-27：表面多候选抓取点 + 各自完整 6D 位姿 + 统一评分
# 目标：不再只用质心，而是从物体表面采样多个抓取接触点(如沿长轴两端、
# 中段、侧翼)，每个接触点×每个方向候选构成一个完整 6D 位姿并打分，
# 用“几何贴合×可达×YLYW谨慎×接触面局部平整度”统一选优。
# =====================================================================

def _local_planarity(points: np.ndarray, query: np.ndarray, k: int = 16)\
        -> Tuple[float, np.ndarray]:
    """在点云中 query 附近点的局部平面度与法向。

    返回 (planarity, normal)：
      planarity ∈[0,1]，1=局部完全平坦(适合夹取)，0=附近很散(边缘/弯曲)。
      normal 为该邻域最小特征值对应方向(局部法向)。
    """
    if len(points) < 3:
        return 0.5, np.array([0.0, 0.0, 1.0])
    d2 = np.sum((points - query) ** 2, axis=1)
    idx = np.argsort(d2)[:k]
    nbr = points[idx]
    c = nbr.mean(axis=0)
    cov = np.cov((nbr - c).T)
    try:
        evals, evecs = np.linalg.eigh(cov)
    except np.linalg.LinAlgError:
        return 0.5, np.array([0.0, 0.0, 1.0])
    evals = np.clip(evals, 0, None)
    total = evals.sum() + 1e-9
    planarity = 1.0 - evals.min() / total          # 1-最扁特征值占比
    normal = evecs[:, 0]
    if normal[2] < 0:
        normal = -normal
    return float(min(1.0, max(planarity, 0.0))), normal


@dataclass
class SurfacePoint:
    """一个物体表面抓取接触点候选。"""
    name: str
    xyz_cam_m: np.ndarray       # 接触点(相机系, 米)
    normal: np.ndarray          # 局部表面法向(相机系, 单位向量)
    planarity: float            # 局部平整度 [0,1]
    along_frac: float           # 沿长轴采样位置 [-1,1]，1=长轴正向端


def sample_surface_contacts(obj: ObjectFeatures,
                            n_per_end: int = 2) -> List[SurfacePoint]:
    """从物体表面采样多个候选抓取接触点(相机系)。

    思路：沿 PCA 长轴 [-1,+1] 取若干位置(两端、中段)，在每个位置取
    “该位置的表面点”。表面点 = 沿该位置法向/主轴投影到点云最近邻。
    同时配合局部法向与平整度，供评分把“边缘/曲面”的接触点降权。
    """
    pts = np.asarray(obj.points_m, dtype=np.float64)
    out: List[SurfacePoint] = []
    if len(pts) < 4:
        # 无点云时退回到质心单点
        return [SurfacePoint("centroid", np.asarray(obj.center_m, dtype=float),
                             np.array([0.0, 0.0, 1.0]), 0.5, 0.0)]

    axes = np.asarray(obj.axes, dtype=np.float64).reshape(3, 3)
    long_ax = axes[:, 0]
    center = np.asarray(obj.center_m, dtype=float)
    dims = np.asarray(obj.dimensions_m)
    proj = (pts - center) @ long_ax                 # 沿长轴的一维位置
    lo, hi = proj.min(), proj.max()
    span = max(hi - lo, 1e-6)

    # 采样位置：两端 + 中段（沿长轴分数）
    fracs = [-1.0, 1.0]
    if n_per_end >= 2:
        fracs = [-1.0, -0.5, 0.5, 1.0]

    def take_at(pos: float, tag: str) -> None:
        # 与目标一维位置最近的点作为接触点
        i = int(np.argmin(np.abs(proj - pos)))
        surf_pt = pts[i]
        # 沿法向(支撑面法向或长轴方向)投影到“表面”：取该柱内离质心最远的点
        planarity, normal = _local_planarity(pts, surf_pt)
        out.append(SurfacePoint(
            name=f"{tag}", xyz_cam_m=surf_pt.astype(float),
            normal=normal, planarity=planarity,
            along_frac=float(np.clip((pos - lo) / span * 2.0 - 1.0, -1, 1))))

    # 左右两端 + 中段共 3~5 个接触点
    seen = set()
    for f in fracs:
        pos = (lo + hi) / 2 + f * (hi - lo) / 2
        key = round(pos / max(span, 1e-6), 2)
        if key in seen:
            continue
        seen.add(key)
        take_at(pos, f"surf_{('L' if f < -0.25 else 'R' if f > 0.25 else 'M')}")
    # 沿中轴/短轴各取一个侧翼点，增加候选多样性
    for _axis_idx, tag in ((1, "midW"), (2, "shortW")):
        ax = axes[:, _axis_idx]
        ap = (pts - center) @ ax
        pos = ap.max() if (ax @ np.array([0, 0, 1.0])) >= 0 else ap.min()
        i = int(np.argmax(np.abs(ap)))
        surf_pt = pts[i]
        planarity, normal = _local_planarity(pts, surf_pt)
        out.append(SurfacePoint(name=f"{tag}", xyz_cam_m=surf_pt.astype(float),
                                normal=normal, planarity=planarity, along_frac=0.0))
    return out


def build_surface_candidates(obj: ObjectFeatures, plan: GraspPlan,
                             tfr_R: np.ndarray, tfr_t: Optional[np.ndarray] = None,
                             grip_half_open_mm: float = 60.0,
                             n_per_end: int = 2) -> List[GraspCandidate]:
    """从表面多个接触点 × 多个方向候选，构建带位置的完整 6D 抓取候选。

    每个候选的抓取位置来自物体表面实际点(不是质心)，方向来自 PCA 主轴形状
    策略。评分 = 0.40×几何贴合 + 0.20×局部平整 + 0.20×可达 + 0.20×YLYW。

    参数:
      tfr_R : 相机→基座 旋转(3x3)，用于方向(主轴/法向)
      tfr_t : 相机→基座 平移(3,)，用于位置；缺省按 0(仅旋转)
    """
    tfr_t = np.zeros(3) if tfr_t is None else np.asarray(tfr_t, dtype=np.float64)
    dims = np.asarray(obj.dimensions_m) * 1000.0
    dl = np.sort(dims)[::-1]
    frame = _Frame(obj, tfr_R)
    shape = classify_shape(obj.dimensions_m)
    ylyw_cautious = plan.yao_quality if plan.yao_quality > 0 else 0.5

    # 1) 方向子候选(不带位置，只取接近轴/开合轴/几何贴合分)
    def orientations():
        # (name, z_axis, x_axis, fit)
        list_o = []
        fit_top = min(1.0, grip_half_open_mm / max(dl[0], 1e-3))
        list_o.append(("top_down", -frame.up, frame.long_h, fit_top))
        contact_mm = max(dl[1], dl[2] * 1.1)
        fit_side = min(1.0, grip_half_open_mm / max(contact_mm, 1e-3))
        list_o.append(("side_grip", -frame.up, frame.long_h, fit_side))
        if shape.approach_type == "side_grip" or shape.name == "rod":
            list_o.append(("side_grip_short", -frame.up, frame.short_h,
                           min(1.0, grip_half_open_mm / max(dl[2], dl[2] * 0.5 + 1e-3))))
            list_o.append(("side_grip_long", -frame.up, frame.long_h,
                           min(1.0, grip_half_open_mm / max(dl[1], dl[1] * 0.5 + 1e-3))))
        return list_o

    # 2) 表面接触点(相机系)
    surf_pts = sample_surface_contacts(obj, n_per_end)
    tfr_R_inv = np.linalg.inv(tfr_R)

    cands: List[GraspCandidate] = []
    for sp in surf_pts:
        # 把表面点的局部法向变换到基座系，作为该点的接近方向依据
        normal_base = tfr_R @ sp.normal
        n2 = np.linalg.norm(normal_base)
        normal_base = normal_base / n2 if n2 > 1e-9 else np.array([0.0, 0.0, 1.0])
        for (oname, z_c, x_c, fit) in orientations():
            z_axis = np.asarray(z_c, dtype=float); x_axis = np.asarray(x_c, dtype=float)
            zn = np.linalg.norm(z_axis); z_axis = z_axis / (zn if zn > 1e-9 else 1.0)
            x_axis = x_axis - np.dot(x_axis, z_axis) * z_axis
            xn = np.linalg.norm(x_axis)
            if xn < 1e-6:
                ref = np.array([0.0, 1.0, 0.0]) if abs(z_axis[2]) < 0.9 \
                    else np.array([1.0, 0.0, 0.0])
                x_axis = ref - np.dot(ref, z_axis) * z_axis
                xn = np.linalg.norm(x_axis) + 1e-9
            x_axis /= xn
            y_axis = np.cross(z_axis, x_axis); y_axis /= (np.linalg.norm(y_axis) + 1e-9)
            reach = 0.4 + abs(z_axis[2]) * 0.6
            score = (0.40 * fit + 0.20 * sp.planarity
                     + 0.20 * reach + 0.20 * ylyw_cautious)
            # 位置：表面点(相机系,m) → 基座系(mm)，需 R@p + t 全变换
            pos_base = tfr_R @ sp.xyz_cam_m + tfr_t
            cands.append(GraspCandidate(
                name=f"{oname}@{sp.name}",
                approach_axis=z_axis, x_axis=x_axis,
                offset_mm=None,       # 位置由接触点直接给出，不再用质心偏移
                contact_base_mm=pos_base * 1000.0,
                score=float(score), fit=float(fit), reach=float(reach),
                cautious=float(ylyw_cautious),
                local_planarity=float(sp.planarity),
            ))
    if not cands:
        return build_candidates(obj, plan, tfr_R, grip_half_open_mm)
    cands.sort(key=lambda c: c.score, reverse=True)
    return cands


def best_surface_6d(obj: ObjectFeatures, plan: GraspPlan, tfr_R: np.ndarray,
                    tfr_t: Optional[np.ndarray] = None,
                    grip_half_open_mm: float = 60.0,
                    n_per_end: int = 2):
    """便捷入口：返回 (最优候选, 完整6D位姿, 候选列表)。

    位置来自物体表面实际抓取接触点(基座系 mm)，不再用质心。
    tfr_R 与 tfr_t 为 相机→基座 旋转/平移(R@p+t)。
    """
    cands = build_surface_candidates(obj, plan, tfr_R, tfr_t,
                                     grip_half_open_mm, n_per_end)
    best = cands[0]
    rx, ry, rz = to_rpy(best)
    if best.contact_base_mm is None:
        # 兜底：无表面点时退回质心
        xyz = best.offset_mm if best.offset_mm is not None else np.zeros(3)
        best6 = np.array([float(xyz[0]), float(xyz[1]), float(xyz[2]), rx, ry, rz])
        return best, best6, cands
    pos = best.contact_base_mm
    pose6d = np.array([float(pos[0]), float(pos[1]), float(pos[2]), rx, ry, rz])
    return best, pose6d, cands
