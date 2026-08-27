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
