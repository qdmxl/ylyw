"""Guarded random-position grasping for a single blue or purple block.

The detector and robot path are deliberately kept in one explicit command:
default mode only observes and preflights. Hardware writes require both
``--execute`` and the exact ``--confirm DYNAMIC_GRASP`` token.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import time
from pathlib import Path
from typing import Any, Optional

from .auto_grasp_once import LIMITS, _checked_solution, _read_six
from .camera import Camera
from .color_block_mapper import HSV_RANGES, _best_square, _mask_for_color
from .config import CameraConfig

LOGGER = logging.getLogger(__name__)


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _joint_distance(a: list[float], b: list[float]) -> float:
    return max(abs(float(a[i]) - float(b[i])) for i in range(6))


def _checked_target_angles(solution: Any, min_margin: float, label: str) -> list[float]:
    if not isinstance(solution, list) or len(solution) != 6:
        raise RuntimeError(f"{label}没有有效逆解: {solution}")
    values = [float(value) for value in solution]
    for index, (value, (low, high)) in enumerate(zip(values, LIMITS), start=1):
        if not math.isfinite(value) or not low + min_margin <= value <= high - min_margin:
            raise RuntimeError(
                f"{label}第 {index} 关节 {value:.2f} 度未保留 "
                f"{min_margin:.1f} 度安全余量"
            )
    return values


def _interpolate_angles(
    start: list[float], target: list[float], max_step_deg: float
) -> list[list[float]]:
    steps = max(1, math.ceil(_joint_distance(start, target) / max_step_deg))
    return [
        [
            float(start[index]) + (float(target[index]) - float(start[index])) * step / steps
            for index in range(6)
        ]
        for step in range(1, steps + 1)
    ]


def _join_angle_paths(*paths: list[list[float]]) -> list[list[float]]:
    result: list[list[float]] = []
    for path in paths:
        for angles in path:
            if not result or _joint_distance(result[-1], angles) > 0.1:
                result.append(list(angles))
    return result


def _compress_angle_path(
    start: list[float], path: list[list[float]], min_step_deg: float = 0.8
) -> list[list[float]]:
    """Drop commands smaller than the controller's practical servo step."""
    result: list[list[float]] = []
    anchor = list(start)
    for index, target in enumerate(path):
        if index == len(path) - 1 or _joint_distance(anchor, target) >= min_step_deg:
            result.append(list(target))
            anchor = list(target)
    return result


def _next_pose(current: list[float], target: list[float], step_mm: float, step_deg: float) -> list[float]:
    result = list(current)
    distance = _distance(current, target)
    if distance <= step_mm:
        result[:3] = target[:3]
    else:
        ratio = step_mm / distance
        for index in range(3):
            result[index] += (target[index] - current[index]) * ratio
    for index in range(3, 6):
        delta = target[index] - current[index]
        result[index] = target[index] if abs(delta) <= step_deg else current[index] + math.copysign(step_deg, delta)
    return result


def _load_pose(path: Path) -> tuple[list[float], list[float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    angles = payload.get("angles")
    coords = payload.get("coords")
    if not isinstance(angles, list) or len(angles) != 6 or not isinstance(coords, list) or len(coords) != 6:
        raise RuntimeError(f"姿态文件缺少 angles/coords: {path}")
    return [float(value) for value in angles], [float(value) for value in coords]


def _yaw_candidates(max_offset_deg: float) -> list[float]:
    """Try the taught yaw first, then nearby wrist orientations."""
    candidates = [0.0]
    offset = 5.0
    while offset <= max_offset_deg + 1e-6:
        candidates.extend((offset, -offset))
        offset += 5.0
    return candidates


def _plan_segment(
    robot: Any,
    start_coords: list[float],
    start_angles: list[float],
    target: list[float],
    step_mm: float,
    step_deg: float,
    max_joint_change: float,
    min_margin: float,
) -> tuple[list[tuple[list[float], list[float]]], list[float], list[float]]:
    coords = list(start_coords)
    angles = list(start_angles)
    planned: list[tuple[list[float], list[float]]] = []
    for _ in range(600):
        if _distance(coords, target) <= 0.6 and max(abs(coords[i] - target[i]) for i in range(3, 6)) <= 1.0:
            return planned, coords, angles
        local_step_mm = step_mm
        local_step_deg = step_deg
        last_error: Optional[Exception] = None
        for _attempt in range(8):
            next_coords = _next_pose(coords, target, local_step_mm, local_step_deg)
            solution = robot.solve_inv_kinematics(next_coords, angles)
            try:
                next_angles = _checked_solution(solution, angles, max_joint_change, min_margin)
                break
            except RuntimeError as exc:
                last_error = exc
                local_step_mm *= 0.5
                local_step_deg *= 0.5
        else:
            raise RuntimeError(f"逆解连续跳变，无法规划安全小步: {last_error}")
        planned.append((next_coords, next_angles))
        coords, angles = next_coords, next_angles
    raise RuntimeError("动态路径规划步数超过限制，请缩小目标范围或重新标定")


def _detect_target(args: argparse.Namespace, calibration: dict[str, Any]) -> tuple[float, float, float, float]:
    import cv2
    import numpy as np

    matrix = np.asarray(calibration["matrix"], dtype=np.float64)
    polygon = np.asarray(calibration["image_points"], dtype=np.int32)
    image_size = calibration.get("image_size", [640, 480])
    width, height = int(image_size[0]), int(image_size[1])
    camera = Camera(CameraConfig(index=args.camera, width=width, height=height))
    samples: list[tuple[float, float, float]] = []
    try:
        camera.open()
        print(f"请把唯一的 {args.color} 方块放在标定区域内；按 q/Esc 取消。")
        for frame_number, frame in enumerate(camera.frames(), start=1):
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = _mask_for_color(hsv, args.color, cv2, np)
            best = _best_square(mask, args.min_area, args.max_area, cv2)
            cv2.polylines(frame, [polygon], True, (0, 220, 255), 2)
            if best is not None:
                area, x, y, box_width, box_height, _ = best
                u = x + box_width / 2.0
                v = y + box_height / 2.0
                inside = cv2.pointPolygonTest(polygon, (u, v), False) >= 0
                color = (0, 200, 0) if inside else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + box_width, y + box_height), color, 2)
                cv2.circle(frame, (round(u), round(v)), 5, color, -1)
                if inside:
                    samples.append((u, v, area))
                cv2.putText(frame, f"{args.color} {len(samples)}/{args.samples}", (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            cv2.imshow("dynamic-color-grasp", frame)
            cv2.imshow("dynamic-color-mask", mask)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                raise KeyboardInterrupt
            if len(samples) >= args.samples:
                break
            if frame_number >= args.max_frames:
                raise RuntimeError(f"有效样本不足，仅得到 {len(samples)}/{args.samples}")
    finally:
        camera.close()
    u = statistics.median(item[0] for item in samples)
    v = statistics.median(item[1] for item in samples)
    x, y = cv2.perspectiveTransform(np.asarray([[[u, v]]], dtype=np.float64), matrix).reshape(2).tolist()
    return float(x), float(y), float(u), float(v)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="单个蓝/紫色方块随机位置抓取")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--calibration", type=Path, default=Path("calibration/board_robot_table_new.json"))
    parser.add_argument("--color", choices=("blue", "purple"), required=True)
    parser.add_argument("--above-pose", type=Path, default=Path("poses/above_blue_block.json"))
    parser.add_argument("--grasp-pose", type=Path, default=Path("poses/grasp_blue_block.json"))
    parser.add_argument("--above-z", type=float, default=None, help="覆盖上方安全高度，范围 140-220 mm")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--max-frames", type=int, default=450)
    parser.add_argument("--min-area", type=float, default=300.0)
    parser.add_argument("--max-area", type=float, default=50000.0)
    parser.add_argument("--step-mm", type=float, default=3.0, help="兼容参数；执行阶段使用关节插值")
    parser.add_argument("--step-deg", type=float, default=4.0, help="关节插值最大步长，实际不超过 4 度")
    parser.add_argument("--arm-speed", type=int, default=3)
    parser.add_argument("--grasp-speed", type=int, default=2, help="最后下降到抓取位置的速度")
    parser.add_argument("--lift-speed", type=int, default=3, help="夹紧后的抬升速度")
    parser.add_argument("--gripper-speed", type=int, default=4)
    parser.add_argument("--close-value", type=int, default=20)
    parser.add_argument("--max-joint-change", type=float, default=8.0)
    parser.add_argument("--min-margin", type=float, default=8.0)
    parser.add_argument("--settle-wait", type=float, default=1.5, help="判断路径点停滞的基础等待秒数")
    parser.add_argument("--progress-retries", type=int, default=3, help="无明显进展时的复查次数")
    parser.add_argument(
        "--execution-mode",
        choices=("incremental", "staged"),
        default="incremental",
        help="incremental 为小路径点；staged 为上方/下降/抬升完整阶段动作",
    )
    parser.add_argument(
        "--yaw-search",
        type=float,
        default=20.0,
        help="第 6 关节接近限位时，自动搜索的夹爪偏航范围（0-30 度）",
    )
    parser.add_argument(
        "--keep-above-orientation",
        action="store_true",
        help="下降和抬升保持上方姿态的末端朝向，仅使用抓取姿态的 Z 高度",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="", help="执行时必须精确填写 DYNAMIC_GRASP")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not 5 <= args.samples <= 60 or not 1 <= args.step_mm <= 5 or not 1 <= args.step_deg <= 8:
        parser.error("samples、step-mm 或 step-deg 超出安全范围")
    if not 1.0 <= args.settle_wait <= 8.0 or not 1 <= args.progress_retries <= 5:
        parser.error("settle-wait 必须在 1-8 秒，progress-retries 必须在 1-5 次")
    if not 0 <= args.yaw_search <= 30:
        parser.error("yaw-search 必须在 0-30 度")
    if not all(
        1 <= speed <= 5
        for speed in (args.arm_speed, args.grasp_speed, args.lift_speed, args.gripper_speed)
    ):
        parser.error("速度必须在 1-5 之间")
    if not 15 <= args.close_value <= 50:
        parser.error("close-value 必须在 15-50 之间；数值越小夹得越紧")
    if not 5 <= args.min_margin <= 20 or not 1 <= args.max_joint_change <= 10:
        parser.error("关节安全参数超出范围")
    if not args.calibration.exists() or not args.above_pose.exists() or not args.grasp_pose.exists():
        parser.error("标定文件或姿态文件不存在")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot，请在已激活的虚拟环境中运行")
        return 1

    try:
        calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
        target_x, target_y, pixel_u, pixel_v = _detect_target(args, calibration)
        above_angles, above_coords = _load_pose(args.above_pose)
        grasp_angles, grasp_coords = _load_pose(args.grasp_pose)
        above_z = above_coords[2] if args.above_z is None else float(args.above_z)
        if not 140.0 <= above_z <= 220.0 or above_z < grasp_coords[2] + 40.0:
            raise RuntimeError(
                f"上方高度 {above_z:.1f} mm 不安全；要求 140-220 mm，且至少高于抓取高度 40 mm"
            )
        if not calibration.get("image_points") or not calibration.get("matrix"):
            raise RuntimeError("标定文件缺少 image_points 或 matrix")
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        try:
            if robot.is_moving() != 0 or robot.get_fresh_mode() != 1:
                raise RuntimeError("机械臂必须停止且 fresh_mode=1")
            if robot.get_error_information() not in (0, None):
                raise RuntimeError("机械臂当前存在错误码")
            current_coords = _read_six(robot, "get_coords")
            current_angles = _read_six(robot, "get_angles")
            if current_coords[2] < above_z - 8.0:
                raise RuntimeError(
                    f"当前高度 Z={current_coords[2]:.1f} mm 低于安全上方高度 "
                    f"{above_z:.1f} mm，请先移动到上方姿态"
                )
            joint_step_deg = min(float(args.step_deg), float(args.max_joint_change), 4.0)
            _checked_target_angles(current_angles, args.min_margin, "当前姿态")
            above_target_angles = _checked_target_angles(
                above_angles, args.min_margin, "保存的上方姿态"
            )
            # Keep the verified IK branch while allowing a small yaw change.
            # Random XY positions can otherwise wrap J6 close to +/-180 deg.
            planning_errors: list[str] = []
            for yaw_offset in _yaw_candidates(args.yaw_search):
                grasp_orientation = (
                    above_coords[3:] if args.keep_above_orientation else grasp_coords[3:]
                )
                dynamic_above = [
                    target_x,
                    target_y,
                    above_z,
                    *above_coords[3:5],
                    above_coords[5] + yaw_offset,
                ]
                dynamic_grasp = [
                    target_x,
                    target_y,
                    grasp_coords[2],
                    *grasp_orientation[:2],
                    grasp_orientation[2] + yaw_offset,
                ]
                try:
                    above_segment, _, dynamic_above_angles = _plan_segment(
                        robot,
                        above_coords,
                        above_target_angles,
                        dynamic_above,
                        args.step_mm,
                        args.step_deg,
                        args.max_joint_change,
                        args.min_margin,
                    )
                    grasp_segment, _, dynamic_grasp_angles = _plan_segment(
                        robot,
                        dynamic_above,
                        dynamic_above_angles,
                        dynamic_grasp,
                        args.step_mm,
                        args.step_deg,
                        args.max_joint_change,
                        args.min_margin,
                    )
                    break
                except RuntimeError as exc:
                    planning_errors.append(f"yaw {yaw_offset:+.0f}: {exc}")
            else:
                details = "; ".join(planning_errors[-3:])
                raise RuntimeError(
                    f"目标 XY=({target_x:.1f}, {target_y:.1f}) 在偏航搜索范围内"
                    f"仍无安全路径: {details}"
                )
            above_path = [angles for _, angles in above_segment]
            grasp_path = [angles for _, angles in grasp_segment]
            plan = _join_angle_paths(
                _interpolate_angles(current_angles, above_target_angles, joint_step_deg),
                above_path,
                grasp_path,
                list(reversed(grasp_path[:-1])) + [dynamic_above_angles],
                list(reversed(above_path[:-1])) + [above_target_angles],
            )
            preview = {
                "target": f"{args.color}_block",
                "pixel_center": [pixel_u, pixel_v],
                "robot_xy_mm": [target_x, target_y],
                "above_z_mm": above_z,
                "grasp_z_mm": grasp_coords[2],
                "selected_yaw_offset_deg": yaw_offset,
                "orientation_source": (
                    "above_pose" if args.keep_above_orientation else "grasp_pose"
                ),
                "close_value": args.close_value,
                "planned_steps": 5 if args.execution_mode == "staged" else len(plan),
                "execution_mode": (
                    "staged_joint_targets"
                    if args.execution_mode == "staged"
                    else "incremental_ik_joint_path"
                ),
                "motion_allowed": args.execute and args.confirm == "DYNAMIC_GRASP",
            }
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            if not args.execute or args.confirm != "DYNAMIC_GRASP":
                print("动态路径预检完成，未发送运动或夹爪命令。")
                return 2
            print("即将执行：上方定位、下降、夹紧、抬升。请确认只有一个目标，工作区无人手，并能立即断电。")
            robot.set_gripper_state(0, args.gripper_speed)
            time.sleep(2.0)
            if robot.get_gripper_value() == -1:
                raise RuntimeError("无法确认夹爪已张开")
            # Rebuild only the first interpolation segment from the actual
            # post-open joint state. The IK targets remain fixed, so the path
            # cannot switch branches halfway through the grasp.
            current_angles = _read_six(robot, "get_angles")
            pre_close_plan = _join_angle_paths(
                _interpolate_angles(current_angles, above_target_angles, joint_step_deg),
                above_path,
                grasp_path,
            )
            pre_close_plan = _compress_angle_path(current_angles, pre_close_plan)

            def execute_stage(
                label: str, target_angles: list[float], speed: int
            ) -> None:
                before = _read_six(robot, "get_angles")
                initial_distance = _joint_distance(before, target_angles)
                if initial_distance <= 3.0:
                    print(f"{label}: 已在目标容差内，跳过重复运动")
                    return
                print(f"{label}: 最大关节变化 {initial_distance:.2f} 度")
                robot.send_angles(target_angles, speed)
                best_distance = initial_distance
                last_progress_at = time.monotonic()
                deadline = time.monotonic() + 35.0
                after = before
                while time.monotonic() < deadline:
                    time.sleep(0.5)
                    after = _read_six(robot, "get_angles")
                    error_code = robot.get_error_information()
                    if error_code not in (0, None):
                        robot.stop()
                        raise RuntimeError(f"{label}出现错误码 {error_code}，已停止")
                    distance = _joint_distance(after, target_angles)
                    if distance <= 3.0:
                        print(f"{label}: 已到位，剩余最大关节误差 {distance:.2f} 度")
                        return
                    if distance < best_distance - 0.15:
                        best_distance = distance
                        last_progress_at = time.monotonic()
                    if time.monotonic() - last_progress_at >= 8.0:
                        robot.stop()
                        raise RuntimeError(
                            f"{label}连续 8 秒没有取得进展，已停止: "
                            f"关节误差 {initial_distance:.2f} -> {distance:.2f} 度; "
                            f"angles {before} -> {after}"
                        )
                robot.stop()
                raise RuntimeError(
                    f"{label}在 35 秒内未到位，已停止: "
                    f"剩余最大关节误差 {_joint_distance(after, target_angles):.2f} 度"
                )

            def execute_joint_path(path: list[list[float]], start_index: int) -> int:
                index = start_index
                for target_angles in path:
                    before = _read_six(robot, "get_angles")
                    initial_distance = _joint_distance(before, target_angles)
                    robot.send_angles(target_angles, args.arm_speed)
                    best_distance = initial_distance
                    last_progress_at = time.monotonic()
                    retries = 0
                    deadline = time.monotonic() + max(
                        15.0, args.settle_wait * (args.progress_retries + 7)
                    )
                    after = before
                    while time.monotonic() < deadline:
                        time.sleep(0.35)
                        after = _read_six(robot, "get_angles")
                        error_code = robot.get_error_information()
                        if error_code not in (0, None):
                            robot.stop()
                            raise RuntimeError(f"第 {index} 步错误码为 {error_code}")
                        after_distance = _joint_distance(after, target_angles)
                        # The controller does not report every small servo
                        # update. A waypoint is close enough once all joints
                        # are within 1.5 degrees; the next verified waypoint
                        # then keeps the motion continuous.
                        if after_distance <= 1.5:
                            break
                        if after_distance < best_distance - 0.1:
                            best_distance = after_distance
                            last_progress_at = time.monotonic()
                        if after_distance > initial_distance + 4.0:
                            robot.stop()
                            raise RuntimeError(
                                f"第 {index} 步明显偏离路径，已停止: "
                                f"关节误差 {initial_distance:.2f} -> {after_distance:.2f} 度"
                            )
                        stall_window = max(3.0, args.settle_wait * 2.0)
                        if time.monotonic() - last_progress_at >= stall_window:
                            if retries >= args.progress_retries:
                                robot.stop()
                                raise RuntimeError(
                                    f"第 {index} 步连续 {stall_window:.1f} 秒无进展，已停止: "
                                    f"关节误差 {initial_distance:.2f} -> {after_distance:.2f} 度; "
                                    f"angles {before} -> {after}"
                                )
                            # Retry exactly the same verified target. Do not
                            # skip a waypoint or increase its movement.
                            robot.send_angles(target_angles, args.arm_speed)
                            retries += 1
                            last_progress_at = time.monotonic()
                            print(f"第 {index} 步控制器延迟，重发同一路径点 {retries}/{args.progress_retries}")
                    else:
                        robot.stop()
                        raise RuntimeError(
                            f"第 {index} 步在限定时间内未跟随路径，已停止: "
                            f"关节误差 {initial_distance:.2f} -> "
                            f"{_joint_distance(after, target_angles):.2f} 度"
                        )
                    index += 1
                return index

            if args.execution_mode == "staged":
                execute_stage(
                    "阶段 1/5 回到安全上方姿态", above_target_angles, args.arm_speed
                )
                execute_stage(
                    "阶段 2/5 移动到目标上方", dynamic_above_angles, args.arm_speed
                )
                execute_stage(
                    "阶段 3/5 一次下降到抓取位置",
                    dynamic_grasp_angles,
                    args.grasp_speed,
                )
                next_index = 4
            else:
                next_index = execute_joint_path(pre_close_plan, 1)
            robot.set_gripper_value(args.close_value, args.gripper_speed)
            time.sleep(3.0)
            closed = robot.get_gripper_value()
            if closed == -1:
                raise RuntimeError("夹紧后无法读取夹爪状态，未抬升")

            if args.execution_mode == "staged":
                execute_stage(
                    "阶段 4/5 一次抬升到目标上方",
                    dynamic_above_angles,
                    args.lift_speed,
                )
                execute_stage(
                    "阶段 5/5 返回安全上方姿态",
                    above_target_angles,
                    args.arm_speed,
                )
            else:
                post_close_plan = _join_angle_paths(
                    list(reversed(grasp_path[:-1])) + [dynamic_above_angles],
                    list(reversed(above_path[:-1])) + [above_target_angles],
                )
                post_close_plan = _compress_angle_path(dynamic_grasp_angles, post_close_plan)
                execute_joint_path(post_close_plan, next_index)
            robot.stop()
            robot.set_fresh_mode(1)
            print(json.dumps({"gripper_after_close": closed, "error": robot.get_error_information(), "motion_allowed": True}, ensure_ascii=False, indent=2))
            return 0
        finally:
            robot.close()
    except KeyboardInterrupt:
        print("\n已取消或停止，未继续执行。")
        return 130
    except Exception as exc:
        LOGGER.error("动态抓取失败: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
