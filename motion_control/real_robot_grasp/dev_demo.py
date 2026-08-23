"""端到端联调脚本(无相机/机械臂)：合成点云 → 特征 → YLYW → 记录。

用于无硬件时验证整条流水线 + 生成论文示例数据。
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # motion_control

from real_robot_grasp.config import FeaturesConfig, YlywConfig
from real_robot_grasp.object_features import analyze_object, segment_objects, _fit_ground_plane
from real_robot_grasp.ylyw_grasp_planner import YlywGraspPlanner, format_plan
from real_robot_grasp.experiment_recorder import ExperimentRecorder, attach_geometry


def make_object(rng, kind):
    """合成不同形状物体点云。"""
    if kind == "cube":
        L, W, H = 0.05, 0.05, 0.04
        return np.column_stack([rng.uniform(-L/2, L/2, 4000), rng.uniform(-W/2, W/2, 4000), rng.uniform(0, H, 4000)])
    if kind == "bottle":  # 圆柱
        r, H = 0.025, 0.12
        th = rng.uniform(0, 2*np.pi, 5000)
        rr = r * np.sqrt(rng.uniform(0, 1, 5000))
        z = rng.uniform(0, H, 5000)
        return np.column_stack([rr*np.cos(th), rr*np.sin(th), z])
    if kind == "sphere":
        r = 0.035
        pts = rng.normal(size=(4000, 3))
        pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * r
        pts[:, 2] = np.abs(pts[:, 2])  # 放在地面上
        return pts
    if kind == "flat_box":
        L, W, H = 0.12, 0.08, 0.01
        return np.column_stack([rng.uniform(-L/2, L/2, 4000), rng.uniform(-W/2, W/2, 4000), rng.uniform(0, H, 4000)])
    raise ValueError(kind)


def demo():
    rng = np.random.default_rng(7)
    feat_cfg = FeaturesConfig(min_points=30)
    planner = YlywGraspPlanner(YlywConfig(verbose=False), None)
    planner.load()
    # 写到本模块目录下的 experiments，避免污染父目录
    here = Path(__file__).resolve().parent
    recorder = ExperimentRecorder(here / "experiments")

    objects = ["cube", "bottle", "sphere", "flat_box", "cube"]
    for i, kind in enumerate(objects, 1):
        cloud = make_object(rng, kind)
        # 加一点地面点(测试地面分割)
        ground = np.column_stack([rng.uniform(-0.1, 0.1, 2000), rng.uniform(-0.1, 0.1, 2000), np.zeros(2000)])
        full = np.vstack([cloud, ground])
        objs = segment_objects(full, feat_cfg)
        print(f"\n[{i}] {kind}: 分割出 {len(objs)} 个物体")
        if not objs:
            recorder.log_result(_empty(kind), False, 0.0)
            continue
        obj = analyze_object(objs[0], feat_cfg, label=kind)
        print(f"    尺寸(mm): {[round(d*1000,1) for d in obj.dimensions_m]}, 曲率={obj.curvature:.2f}")
        plan = planner.plan(obj)
        attach_geometry(plan, obj.dimensions_m, obj.curvature)
        print(format_plan(plan))
        recorder.log_result(plan, True, 1.0 + i*0.2)

    summary = recorder.summary()
    print("\n===== 汇总 =====")
    import json
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    recorder.close()
    print("\nCSV:", recorder.csv_path)
    print("JSONL:", recorder.jsonl_path)


def _empty(label):
    from real_robot_grasp.ylyw_grasp_planner import GraspPlan
    return GraspPlan(label=label)


if __name__ == "__main__":
    demo()
