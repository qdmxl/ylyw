"""主流程 —— 多物体任意抓取。

流程(每轮):
  1. 深度相机采集 → 点云
  2. 物体分割 + 特征分析(尺寸/质心/曲率/13维特征)
  3. YLYW 推理 → 抓取策略(卦象/力/接近角/速度/夹紧值)
  4. 识别：auto_pick_any → 自动选最佳物体；否则按指定类别
  5. 机械臂执行抓取 + 放置
  6. 实验数据记录 + 汇总

用法:
  python -m real_robot_grasp.main --simulate            # 无硬件联调
  python -m real_robot_grasp.main --port /dev/ttyUSB0   # 真实硬件
  python -m real_robot_grasp.main --rounds 10 --simulate
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

from .config import (AppConfig, DepthCameraConfig, FeaturesConfig,
                     RobotConfig, YlywConfig, YlywGraspConfig)
from .coordinate_transform import CameraToRobot
from .depth_camera import DepthCamera
from .experiment_recorder import ExperimentRecorder, attach_geometry
from .grasp_controller import GraspController
from .object_features import (ObjectFeatures, analyze_object,
                              segment_objects)
from .robot_arm import RobotArm
from .ylyw_grasp_planner import (YlywGraspPlanner, format_plan)
from . import grasp_pose

LOGGER = logging.getLogger(__name__)


def _build_pose(obj: ObjectFeatures, plan, tfr: CameraToRobot,
                grasp_cfg: YlywGraspConfig):
    """由物体特征 + YLYW方案 → 完整 6D 抓取位姿(基座mm+欧拉°)。

    2026-08-27：改用表面多候选抓取点(best_surface_6d)，抓取位置来自物体
    表面实际接触点而非质心；若物体无点云则回退到质心(best_6d)。
    """
    grip_half = float(grasp_cfg.force_range_mm[1] / 2.0)
    if obj.n_points >= 4:
        return grasp_pose.best_surface_6d(obj, plan, tfr.R, tfr.t,
                                          grip_half_open_mm=grip_half)
    base_xyz_mm = tfr.to_base(obj.center_m, out_mm=True)[:3]
    return grasp_pose.best_6d(obj, plan, tfr.R, base_xyz_mm,
                              grip_half_open_mm=grip_half)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="YLYW 深度相机多物体任意抓取")
    p.add_argument("--simulate", action="store_true",
                   help="模拟机械臂(不驱动硬件)，用于无硬件联调")
    p.add_argument("--rounds", type=int, default=5, help="连续抓取轮数")
    p.add_argument("--port", default="COM3", help="机械臂串口")
    p.add_argument("--baudrate", type=int, default=115200,
                  help="机械臂波特率(真机 280-M5 用 115200；280-Arduino 则用 1000000)")
    p.add_argument("--camera-backend", choices=("realsense", "opencv", "synthetic"),
                   default="realsense")
    p.add_argument("--target", default=None,
                   help="指定抓取类别(如 bottle)；默认任意抓取")
    p.add_argument("--ylyw-core", default="/home/lijinhan/MXL/科研/ylyw/api_docs")
    p.add_argument("--record-dir", default=None,
                   help="实验记录目录(默认本包目录下 experiments)")
    p.add_argument("--calibration", default=None,
                   help="手眼标定 JSON；默认顶部近似")
    p.add_argument("--min-points", type=int, default=30)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--dryrun", action="store_true",
                   help="仅感知+YLYW规划，不执行机械臂(论文数据采集模式)")
    args = p.parse_args(argv)
    args.rounds = max(1, args.rounds)
    return args


def _choose_target(objects: List[ObjectFeatures],
                   target_class: Optional[str]) -> Optional[ObjectFeatures]:
    """选目标：指定类别则选该类置信度最高；否则选点最多(最明显)的。"""
    if target_class:
        cand = [o for o in objects if o.label == target_class]
        if not cand:
            return None
        return max(cand, key=lambda o: o.confidence)
    if not objects:
        return None
    # 任意抓取：优先抓取"更容易"的(点云多=可见好、主轴朝上=可达)
    def key(o):
        reach = o.features.get("reachability", 0.5)
        return o.n_points * (0.5 + reach)
    return max(objects, key=key)


def run_app(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")

    # 解析实验记录目录：默认包目录下 experiments，相对路径基于包目录
    pkg_dir = Path(__file__).resolve().parent
    if args.record_dir:
        record_dir = Path(args.record_dir)
        if not record_dir.is_absolute():
            record_dir = pkg_dir / record_dir
    else:
        record_dir = pkg_dir / "experiments"

    app_cfg = AppConfig(grab_rounds=args.rounds, target_class=args.target,
                        record_dir=record_dir, auto_pick_any=not args.target)
    cam_cfg = DepthCameraConfig(backend=args.camera_backend)
    feat_cfg = FeaturesConfig(min_points=args.min_points)
    robot_cfg = RobotConfig(port=args.port, baudrate=args.baudrate,
                            simulate=args.simulate)
    ylyw_cfg = YlywConfig(ylyw_core_path=args.ylyw_core, verbose=args.verbose)
    grasp_cfg = YlywGraspConfig()

    # 相机→基座
    if args.calibration:
        tfr = CameraToRobot.from_json(args.calibration)
    else:
        tfr = CameraToRobot.from_overhead(cam_pos_m=(0.0, 0.20, 0.45))

    # YLYW 规划器
    planner = YlywGraspPlanner(ylyw_cfg, grasp_cfg)
    planner.load()

    recorder = ExperimentRecorder(app_cfg.record_dir)

    # 机械臂(非 dryrun 时连接)
    arm = None
    controller = None
    if not args.dryrun:
        arm = RobotArm(robot_cfg)
        arm.connect()
        controller = GraspController(arm, tfr, grasp_cfg, robot_cfg)
        controller.capture_home()

    camera = DepthCamera(cam_cfg)
    successes = 0
    try:
        camera.open()
        for rnd in range(1, app_cfg.grab_rounds + 1):
            LOGGER.info("========== 第 %d / %d 轮 ==========", rnd, app_cfg.grab_rounds)
            t0 = time.time()

            # 1. 采集
            color, depth, cloud = camera.grab()
            cloud = camera.filter_cloud(cloud)
            LOGGER.debug("点云点数=%d", len(cloud))

            # 2. 分割 + 特征
            pointclouds = segment_objects(cloud, feat_cfg)
            objects: List[ObjectFeatures] = []
            for i, pts in enumerate(pointclouds):
                obj = analyze_object(pts, feat_cfg, label=args.target or "object",
                                     all_clouds=[c for j, c in enumerate(pointclouds)
                                                 if j != i],
                                     num_clouds=len(pointclouds))
                if obj is not None:
                    objects.append(obj)
            if not objects:
                LOGGER.warning("第%d轮：未检测到物体，跳过", rnd)
                recorder.log_result(_empty_plan("none"), False, time.time() - t0)
                continue
            LOGGER.info("检测到 %d 个物体", len(objects))

            # 3. 选目标(当前逻辑：每轮检测多个 → 只选1个最优目标抓取)
            target_obj = _choose_target(objects, app_cfg.target_class)
            if target_obj is None:
                LOGGER.warning("第%d轮：无匹配物体，跳过", rnd)
                recorder.log_result(_empty_plan(args.target or "none"),
                                    False, time.time() - t0)
                continue
            LOGGER.info("本轮检测 %d 个物体，选择目标: %s",
                        len(objects), target_obj.label)

            # 4. YLYW 规划
            plan = planner.plan(target_obj)
            attach_geometry(plan, target_obj.dimensions_m, target_obj.curvature)
            # 规划阶段即计算 6D 抓取位姿(基座系 mm+欧拉角) —— 供实验记录/复现
            if plan.use_6d:
                best, pose6d, _cands = _build_pose(target_obj, plan, tfr, grasp_cfg)
                plan.grasp_pose_6d = np.asarray(pose6d, dtype=float)
                plan.grasp_pose_name = best.name
                plan.approach_axis = np.asarray(best.approach_axis, dtype=float)
                plan.open_axis = np.asarray(best.x_axis, dtype=float)
                if args.verbose or args.dryrun:
                    print(f"  ── 6D抓取位姿(基座mm+欧拉°) ── {np.round(pose6d,1)}")
                    print(f"  候选={best.name} 接近方向={np.round(best.approach_axis,2)} "
                          f"开合方向={np.round(best.x_axis,2)}")
            if args.verbose or args.dryrun:
                print(format_plan(plan))

            # 5. 执行
            success = False
            if not args.dryrun:
                assert controller is not None
                success = controller.pick(plan, obj=target_obj)
                if success:
                    success &= controller.place(app_cfg.place_pose)
                if success:
                    successes += 1
            else:
                # dryrun：只验证“规划流程无异常”，不执行机械臂。
                # 此处 success=True 仅表示“规划成功”，不是物理抓取成功。
                success = True
                successes += 1
                LOGGER.info("[dryrun] 已规划抓取 %s（未执行机械臂，success=规划成功）",
                            target_obj.label)

            recorder.log_result(plan, success, time.time() - t0,
                                extra={"n_objects": len(objects)})

        # 汇总
        summary = recorder.summary()
        if args.dryrun:
            LOGGER.info("==== 汇总(dryrun) ==== 规划成功率=%s（≠抓取成功率）",
                        summary.get("success_rate"))
        else:
            LOGGER.info("==== 实验汇总 ==== 抓取成功率=%s",
                        summary.get("success_rate"))
        if args.verbose:
            import json as _json
            print("实验汇总:\n" + _json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        camera.close()
        if arm is not None:
            arm.close()
        recorder.close()


def _empty_plan(label: str):
    from .ylyw_grasp_planner import GraspPlan
    return GraspPlan(label=label)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.rounds <= 0:
        args.rounds = 1
    return run_app(args)


if __name__ == "__main__":
    raise SystemExit(main())
