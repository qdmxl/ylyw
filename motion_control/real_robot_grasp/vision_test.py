"""深度相机 + 物体特征分析 独立测试脚本。

在真实深度相机上：
  python3 vision_test.py --backend realsense
在合成数据上：
  python3 vision_test.py --backend synthetic
只测点云生成 + 分割 + 特征(不动机械臂)。
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from real_robot_grasp.config import DepthCameraConfig, FeaturesConfig
from real_robot_grasp.depth_camera import DepthCamera
from real_robot_grasp.object_features import analyze_object, segment_objects


def run(backend: str):
    cam_cfg = DepthCameraConfig(backend=backend)
    feat_cfg = FeaturesConfig()
    cam = DepthCamera(cam_cfg)
    try:
        cam.open()
        color, depth, cloud = cam.grab()
        cloud = cam.filter_cloud(cloud)
        print(f"相机: {backend} | 点云点数(raw后过滤) = {len(cloud)}")
        if backend == "synthetic":
            print(f"  点云 Z 范围: {cloud[:,2].min():.3f} ~ {cloud[:,2].max():.3f} m")

        objs = segment_objects(cloud, feat_cfg)
        print(f"\n分割出 {len(objs)} 个物体:")
        for i, pts in enumerate(objs):
            obj = analyze_object(pts, feat_cfg)
            if obj is None:
                continue
            print(f"  [{i}] {obj.label} | 点数={obj.n_points} "
                  f"尺寸(mm)={[round(d*1000,1) for d in obj.dimensions_m]} "
                  f"质心(m)={[round(c,3) for c in obj.center_m]} "
                  f"曲率={obj.curvature:.2f}")
    finally:
        cam.close()


if __name__ == "__main__":
    backend = sys.argv[1] if len(sys.argv) > 1 else "synthetic"
    run(backend)
