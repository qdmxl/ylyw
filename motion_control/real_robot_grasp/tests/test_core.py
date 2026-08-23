"""核心逻辑单元测试(无硬件)。

运行: python3 -m pytest tests/ -v   或   python3 tests/test_core.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from real_robot_grasp.config import (FeaturesConfig, RobotConfig, YlywConfig,
                                     YlywGraspConfig)
from real_robot_grasp.coordinate_transform import CameraToRobot
from real_robot_grasp.depth_camera import DepthCamera, DepthCameraConfig
from real_robot_grasp.experiment_recorder import ExperimentRecorder, attach_geometry
from real_robot_grasp.object_features import analyze_object, segment_objects
from real_robot_grasp.robot_arm import RobotArm
from real_robot_grasp.ylyw_grasp_planner import YlywGraspPlanner, GraspPlan


def _rng_cloud(rng, kind="cube"):
    if kind == "cube":
        L, W, H = 0.05, 0.05, 0.04
        return np.column_stack([rng.uniform(-L/2, L/2, 3000),
                                rng.uniform(-W/2, W/2, 3000),
                                np.abs(rng.uniform(0, H, 3000))])
    if kind == "sphere":
        r = 0.03
        pts = rng.normal(size=(2000, 3))
        pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * r
        pts[:, 2] = np.abs(pts[:, 2])
        return pts
    raise ValueError(kind)


def test_segment_single():
    rng = np.random.default_rng(0)
    obj = _rng_cloud(rng)
    ground = np.column_stack([rng.uniform(-0.2, 0.2, 2000),
                              rng.uniform(-0.2, 0.2, 2000), np.zeros(2000)])
    full = np.vstack([obj, ground])
    objs = segment_objects(full, FeaturesConfig(min_points=30))
    assert len(objs) == 1, f"期望1个物体，得到 {len(objs)}"


def test_segment_multiple():
    rng = np.random.default_rng(3)
    a = _rng_cloud(rng) + np.array([-0.1, 0, 0])
    b = _rng_cloud(rng, "sphere") + np.array([0.1, 0, 0])
    objs = segment_objects(np.vstack([a, b]), FeaturesConfig(min_points=30))
    assert len(objs) == 2, f"期望2个物体，得到 {len(objs)}"


def test_feature_curvature():
    # 平面(曲率低) vs 球(曲率高)
    rng = np.random.default_rng(5)
    flat = rng.uniform(-0.05, 0.05, (3000, 3))
    flat[:, 2] = np.abs(flat[:, 2]) * 0.001  # 薄平板
    obj_flat = analyze_object(flat, FeaturesConfig())
    assert obj_flat.curvature < 0.3, f"平板曲率应低: {obj_flat.curvature}"


def test_ylyw_planner_output():
    rng = np.random.default_rng(9)
    obj = analyze_object(_rng_cloud(rng), FeaturesConfig(min_points=30))
    planner = YlywGraspPlanner(YlywConfig(verbose=False))
    planner.load()
    plan = planner.plan(obj)
    assert isinstance(plan, GraspPlan)
    assert plan.hexagram, "卦象为空"
    assert plan.strategy_type, "策略为空"
    assert 5 <= plan.close_value <= 50, "夹紧值越界"
    assert 1 <= plan.speed_level <= 5, "速度档越界"
    assert 0.0 <= plan.force <= 1.0, "力预设越界"


def test_coordinate_transform():
    tfr = CameraToRobot.from_overhead(cam_pos_m=(0, 0, 0.5))
    # 相机正前方远处一点 → 变换到基座，应得到合理值
    base = tfr.to_base([0.1, 0.0, 0.45], out_mm=True)
    assert base.shape == (3,)
    assert np.isfinite(base).all()


def test_recorder(tmpdir=None):
    import tempfile as _t
    with _t.TemporaryDirectory() as d:
        rec = ExperimentRecorder(Path(d))
        plan = GraspPlan(label="object", grasp_xyz=np.array([0.0, 0.0, 0.05]))
        attach_geometry(plan, (0.05, 0.05, 0.04), 0.3)
        rec.log_result(plan, True, 1.5)
        rec.close()
        assert (Path(d) / "grasp_experiments.csv").exists()
        assert (Path(d) / "grasp_reasoning.jsonl").exists()


def test_robot_sim():
    arm = RobotArm(RobotConfig(simulate=True))
    arm.connect()
    a = arm.get_angles()
    assert len(a) == 6
    arm.close()


def test_depth_synthetic():
    cam = DepthCamera(DepthCameraConfig(backend="synthetic"))
    cam.open()
    color, depth, cloud = cam.grab()
    assert color.shape[2] == 3
    assert depth.ndim == 2
    assert cloud.shape[1] == 3
    cam.close()


if __name__ == "__main__":
    for name in sorted(list(globals())):
        if name.startswith("test_"):
            try:
                fn = globals()[name]
                if name == "test_recorder":
                    fn()
                else:
                    fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
