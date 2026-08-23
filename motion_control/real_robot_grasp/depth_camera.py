"""深度相机模块 —— 获取彩色图 / 深度图 / 点云。

设计成两层：
  - `DepthCamera`: 统一接口，返回 (color_frame, depth_image, pointcloud):
        - color_frame: BGR ndarray
        - depth_image: 深度图(米)，float32
        - pointcloud:  (N,3) 米，相机坐标系，z=深度
  - backend 可切换：
        - "realsense": Intel RealSense (pyrealsense2)
        - "opencv": 普通 USB 摄像头 + 平面标定高度 2.5D（无真深度时的回退）

本模块只负责"看"，不做物体分析 —— 分离关注点，便于独立测试。
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np

from .config import DepthCameraConfig

LOGGER = logging.getLogger(__name__)

# 类型别名
ColorImage = np.ndarray      # HxWx3 BGR
DepthImage = np.ndarray      # HxW float32 米
PointCloud = np.ndarray      # Nx3 float32 米


def _intrinsics_from_cv(cap, width: int, height: int):
    """OpenCV 后端没有真实内参时的近似(针孔相机, 默认视野)。"""
    import cv2
    f = max(width, height) * 0.8  # 近似焦距
    return np.array([[f, 0, width / 2],
                     [0, f, height / 2],
                     [0, 0, 1]], dtype=np.float64)


class DepthCamera:
    """深度相机统一封装。"""

    def __init__(self, config: DepthCameraConfig):
        self.config = config
        self._realsense = None
        self._cv = None
        self._intrinsics = None
        self._depth_scale = config.depth_scale
        self._pipe = None
        self._align = None
        self._profile = None
        self._synthetic = None
        self._rs = None

    # ---------------- 打开/关闭 ----------------
    def open(self) -> None:
        if self.config.backend == "realsense":
            self._open_realsense()
        elif self.config.backend == "opencv":
            self._open_opencv()
        elif self.config.backend == "synthetic":
            self._open_synthetic()
        else:
            raise RuntimeError(f"未知相机 backend: {self.config.backend}")

    def _open_synthetic(self) -> None:
        """纯合成模式：生成合成的多物体场景点云(无硬件)，便于联调/生成论文数据。"""
        import cv2
        import numpy as np
        self._intrinsics = _intrinsics_from_cv(None, self.config.width, self.config.height)
        rng = np.random.default_rng(1234)
        # 合成一个 640x480 的“伪深度”，并内置一个生成点云的场景
        scene = self._make_synthetic_scene(rng)
        self._synthetic = {"rng": rng, "frame": 0, "scene": scene}
        self._cv = object()  # 标记已打开
        LOGGER.info("合成相机已打开(无硬件，用于联调/论文数据)")

    def _open_realsense(self) -> None:
        try:
            import pyrealsense2 as rs
        except ImportError as exc:
            raise RuntimeError(
                "未安装 pyrealsense2。请 `pip install pyrealsense2`，"
                "或设置 backend='opencv' 使用普通摄像头。"
            ) from exc
        ctx = rs.context()
        device = None
        if self.config.serial:
            device = ctx.query_devices([self.config.serial])
        else:
            ds = ctx.query_devices()
            if ds.size():
                device = [ds[0]]
        if not device:
            raise RuntimeError("未找到 RealSense 深度相机")
        self._realsense = ctx
        pipe = rs.pipeline()
        cfg = rs.config()
        if self.config.serial:
            cfg.enable_device(self.config.serial)
        cfg.enable_stream(rs.stream.depth, self.config.width,
                          self.config.height, rs.format.z16, self.config.fps)
        cfg.enable_stream(rs.stream.color, self.config.width,
                          self.config.height, rs.format.bgr8, self.config.fps)
        profile = pipe.start(cfg)
        dev = profile.get_device()
        depth_sensor = dev.query_sensors()[0]
        self._depth_scale = depth_sensor.get_depth_scale()
        # 颜色对齐到深度
        if self.config.align_depth:
            self._align = rs.align(rs.stream.color)
        else:
            self._align = None
        self._profile = profile
        # 内参
        intr = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
        self._intrinsics = np.array([[intr.fx, 0, intr.ppx],
                                     [0, intr.fy, intr.ppy],
                                     [0, 0, 1]], dtype=np.float64)
        self._rs = rs
        self._pipe = pipe
        LOGGER.info("RealSense 已打开：%s", dev.get_info(rs.camera_info.name))

    def _open_opencv(self) -> None:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise RuntimeError("无法打开 OpenCV 摄像头 index=0")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._cv = cap
        self._intrinsics = _intrinsics_from_cv(cap, self.config.width, self.config.height)
        LOGGER.info("OpenCV 摄像头已打开（2.5D 回退模式）")

    def close(self) -> None:
        if self._pipe is not None:
            self._pipe.stop()
            self._pipe = None
        if self._cv is not None and not self._synthetic:
            self._cv.release()
        self._cv = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *a):
        self.close()

    # ---------------- 采集 ----------------
    def grab(self) -> Tuple[ColorImage, DepthImage, PointCloud]:
        """抓取一帧，返回 (彩色图, 深度图(米), 点云(N,3))。"""
        if self._pipe is not None:
            return self._grab_realsense()
        if self._cv is not None and self._synthetic is not None:
            return self._grab_synthetic()
        if self._cv is not None:
            return self._grab_opencv()
        raise RuntimeError("相机未打开")

    def _grab_realsense(self) -> Tuple[ColorImage, DepthImage, PointCloud]:
        frames = self._pipe.wait_for_frames()
        if self._align is not None:
            frames = self._align.process(frames)
        color = np.asanyarray(frames.get_color_frame().get_data())
        depth = np.asanyarray(frames.get_depth_frame().get_data()).astype(np.float32) * self._depth_scale
        cloud = self._depth_to_pointcloud(depth)
        return color, depth, cloud

    def _grab_opencv(self) -> Tuple[ColorImage, DepthImage, PointCloud]:
        import cv2
        ok, color = self._cv.read()
        if not ok:
            raise RuntimeError("OpenCV 读取失败")
        h, w = color.shape[:2]
        # 2.5D 回退：假设桌面在固定高度，生成一张"平面深度"，物体高度忽略
        depth = np.full((h, w), self.config.cv_table_height_m, dtype=np.float32)
        cloud = self._depth_to_pointcloud(depth)
        return color, depth, cloud

    def _depth_to_pointcloud(self, depth: DepthImage) -> PointCloud:
        """深度图→点云（相机坐标系）。过滤无效/超程深度。"""
        h, w = depth.shape
        fx = self._intrinsics[0, 0]
        fy = self._intrinsics[1, 1]
        cx = self._intrinsics[0, 2]
        cy = self._intrinsics[1, 2]
        valid = (depth > 0.05) & (depth < self.config.max_range)
        ys, xs = np.nonzero(valid)
        if ys.size == 0:
            return np.zeros((0, 3), dtype=np.float32)
        zs = depth[ys, xs]
        x = (xs.astype(np.float32) - cx) * zs / fx
        y = (ys.astype(np.float32) - cy) * zs / fy
        return np.stack([x, y, zs], axis=-1)

    # ---- 合成场景(无硬件联调) ----
    def _make_synthetic_scene(self, rng):
        """构造一个含多个物体、彼此分开的合成点云(相机系)。"""
        objects = []
        # 三个物体横向分开(间距 ~9cm > 聚类阈值 3cm)
        objects.append(self._cube(rng, center=(-0.10, 0.0, 0.44), size=0.05))
        objects.append(self._cylinder(rng, center=(0.0, 0.0, 0.48), r=0.025, h=0.11))
        objects.append(self._sphere(rng, center=(0.10, 0.0, 0.44), r=0.033))
        return np.vstack(objects)

    @staticmethod
    def _cube(rng, center, size):
        pts = rng.uniform(-size/2, size/2, (4000 // 6, 3))
        all_pts = []
        for axis in range(3):
            for s in (-1, 1):
                p = np.copy(pts)
                p[:, axis] = s * size / 2
                all_pts.append(p)
        cloud = np.vstack(all_pts)
        cloud[:, 2] = cloud[:, 2] - cloud[:, 2].min()
        return cloud + np.array([center[0], center[1], 0.0])

    def _cylinder(self, rng, center, r, h):
        n = 5000
        th = rng.uniform(0, 2*np.pi, n)
        rr = r * np.sqrt(rng.uniform(0, 1, n))
        z = rng.uniform(0, h, n)
        cloud = np.column_stack([rr*np.cos(th), rr*np.sin(th), z])
        return cloud + np.array([center[0], center[1], 0.0])

    def _sphere(self, rng, center, r):
        pts = rng.normal(size=(4000, 3))
        pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * r
        pts[:, 2] = np.abs(pts[:, 2])
        return pts + np.array([center[0], center[1], 0.0])

    def _grab_synthetic(self) -> Tuple[ColorImage, DepthImage, PointCloud]:
        import cv2
        import numpy as np
        self._synthetic["frame"] += 1
        scene = self._synthetic["scene"]
        noise = self._synthetic["rng"].normal(0, 0.001, scene.shape)
        cloud = scene + noise
        h, w = self.config.height, self.config.width
        depth = np.zeros((h, w), dtype=np.float32)
        fx = self._intrinsics[0, 0]; fy = self._intrinsics[1, 1]
        cx = self._intrinsics[0, 2]; cy = self._intrinsics[1, 2]
        u = np.round(cloud[:, 0] * fx / cloud[:, 2] + cx).astype(int)
        v = np.round(cloud[:, 1] * fy / cloud[:, 2] + cy).astype(int)
        ok = (u >= 0) & (u < w) & (v >= 0) & (v < h)
        depth[v[ok], u[ok]] = cloud[ok, 2]
        color = np.zeros((h, w, 3), dtype=np.uint8)
        return color, depth, cloud

    def filter_cloud(self, cloud: PointCloud) -> PointCloud:
        """体素下采样：均匀采样到网格并取体素质心，减少点数。"""
        if len(cloud) == 0:
            return cloud
        voxel = self.config.voxel_size
        pts = np.asarray(cloud, dtype=np.float64)
        coords = np.floor(pts / voxel).astype(np.int64)
        # 字典 key 聚合
        mapping = {}
        order = []
        for idx in range(len(pts)):
            key = (coords[idx, 0], coords[idx, 1], coords[idx, 2])
            if key in mapping:
                mapping[key].append(idx)
            else:
                mapping[key] = [idx]
                order.append(key)
        out = np.zeros((len(order), 3), dtype=np.float32)
        for i, key in enumerate(order):
            idxs = mapping[key]
            out[i] = pts[idxs].mean(axis=0)
        return out
