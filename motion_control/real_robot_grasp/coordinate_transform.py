"""相机→机械臂基座坐标变换模块。

深度相机给出的是相机坐标系下的物体质心(米)。要抓取，需要把该点
变换到机械臂基座坐标系(MyCobot 用 mm + 欧拉角)。

实现：手-眼标定所需的外参(旋转R + 平移t)。提供两种方式：
  1. 配置式：直接给出 R(3x3) 与 t(3x1)（由标定工具/OpenCV solvePnP 得到）
  2. 简化式：给出相机相对机械臂基座的角度与位置——适用于"相机固定在
     工作区上方、近似垂直向下"的常见布局。

相机坐标 → 基座坐标:  p_base = R @ p_cam + t   （单位米）
本模块统一输出米，由调用方转 mm。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

LOGGER = logging.getLogger(__name__)


class CameraToRobot:
    """相机-机械臂外参(Eye-to-Hand 简化)。"""

    def __init__(self, R: Optional[np.ndarray] = None,
                 t: Optional[np.ndarray] = None):
        self.R = np.eye(3) if R is None else np.asarray(R, dtype=np.float64)
        self.t = np.zeros(3) if t is None else np.asarray(t, dtype=np.float64)

    # ---- 加载 ----
    @classmethod
    def from_json(cls, path: Path) -> "CameraToRobot":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(np.asarray(data["R"], dtype=np.float64),
                   np.asarray(data["t"], dtype=np.float64))

    @classmethod
    def from_overhead(cls, cam_pos_m=(0.0, 0.0, 0.45),
                      cam_yaw_deg=0.0, cam_pitch_deg=90.0):
        """顶部近似：相机朝下(pitch 90°)，光轴与机械臂Z大致一致。

        简化：R = 绕Z旋转(cam_yaw)，t = 相机在基座坐标位置。
        对齐：相机 +Z(前)指向基座 -X 等，若近似则将光轴翻到 -Z。
        """
        yaw = np.deg2rad(cam_yaw_deg)
        Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0],
                       [np.sin(yaw), np.cos(yaw), 0],
                       [0, 0, 1]], dtype=np.float64)
        # 相机系(Z朝外前) → 机械臂系(Z朝上)：绕X转180°
        Rx = np.array([[1, 0, 0],
                       [0, -1, 0],
                       [0, 0, -1]], dtype=np.float64)
        R = Rz @ Rx
        return cls(R, np.asarray(cam_pos_m, dtype=np.float64))

    # ---- 变换 ----
    def to_base(self, cam_xyz_m, out_mm: bool = True):
        """相机系(米) → 基座坐标。out_mm=True 时返回 mm。"""
        p = np.asarray(cam_xyz_m, dtype=np.float64).reshape(-1)
        base = self.R @ p + self.t
        if out_mm:
            return base * 1000.0
        return base


def save_example_calibration(out_dir: Path = Path("calibration")) -> Path:
    """生成一个示例标定文件(顶部近似)，便于使用者按实际替代。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "hand_eye_example.json"
    tfr = CameraToRobot.from_overhead(cam_pos_m=(0.0, 0.20, 0.45))
    payload = {"R": tfr.R.tolist(), "t": tfr.t.tolist(),
               "note": "示例(顶部近似)。请用标定工具/solvePnP 替换为实际外参。"}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("示例标定已写入 %s", path)
    return path
