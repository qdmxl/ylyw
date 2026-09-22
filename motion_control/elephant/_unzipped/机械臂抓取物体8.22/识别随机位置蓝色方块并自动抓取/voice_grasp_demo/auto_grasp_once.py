"""Perform one guarded descend, close, and lift cycle from above a target."""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)
LIMITS = [(-168.0, 168.0), (-140.0, 140.0), (-150.0, 150.0),
          (-150.0, 150.0), (-155.0, 160.0), (-180.0, 180.0)]


def _read_six(robot: Any, method_name: str, attempts: int = 6) -> list[float]:
    method = getattr(robot, method_name)
    last: Any = None
    for attempt in range(attempts):
        last = method()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return [float(value) for value in last]
        if attempt + 1 < attempts:
            time.sleep(0.35)
    raise RuntimeError(f"读取 {method_name} 失败: {last}")


def _wait_stopped(robot: Any, timeout: float = 10.0, min_wait: float = 1.0) -> None:
    started_at = time.monotonic()
    deadline = time.monotonic() + timeout
    saw_moving = False
    stable_reads = 0
    while time.monotonic() < deadline:
        moving = robot.is_moving()
        if moving == 1:
            saw_moving = True
            stable_reads = 0
        elif moving == 0 and time.monotonic() - started_at >= min_wait:
            stable_reads += 1
            if saw_moving or stable_reads >= 3:
                return
        else:
            stable_reads = 0
        time.sleep(0.15)
    robot.stop()
    raise RuntimeError("运动未及时停止，已发送停止请求")


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def _next_xyz(current: list[float], target: list[float], step_mm: float) -> list[float]:
    distance = _distance(current, target)
    if distance <= step_mm:
        return list(target)
    ratio = step_mm / distance
    result = list(current)
    for index in range(3):
        result[index] += (target[index] - current[index]) * ratio
    result[3:] = target[3:]
    return result


def _checked_solution(
    solution: Any,
    seed: list[float],
    max_joint_change: float,
    min_margin: float,
) -> list[float]:
    if not isinstance(solution, list) or len(solution) != 6:
        raise RuntimeError(f"没有有效逆解: {solution}")
    values = [float(value) for value in solution]
    for index, (value, (low, high)) in enumerate(zip(values, LIMITS), start=1):
        if not math.isfinite(value) or not low + min_margin <= value <= high - min_margin:
            raise RuntimeError(
                f"关节 {index} 逆解 {value:.2f} 度未保留 {min_margin:.1f} 度安全余量"
            )
    changes = [new - old for new, old in zip(values, seed)]
    if max(abs(change) for change in changes) > max_joint_change:
        raise RuntimeError(f"单步关节变化过大: {[round(value, 2) for value in changes]}")
    return values


def _preflight(
    robot: Any,
    coords: list[float],
    angles: list[float],
    targets: list[list[float]],
    step_mm: float,
    max_joint_change: float,
    min_margin: float,
) -> int:
    simulated_coords = list(coords)
    simulated_angles = list(angles)
    steps = 0
    for target in targets:
        while _distance(simulated_coords, target) > 0.5:
            next_coords = _next_xyz(simulated_coords, target, step_mm)
            solution = robot.solve_inv_kinematics(next_coords, simulated_angles)
            simulated_angles = _checked_solution(
                solution, simulated_angles, max_joint_change, min_margin
            )
            simulated_coords = next_coords
            steps += 1
            if steps > 200:
                raise RuntimeError("规划步数异常，未执行")
    return steps


def _move_checked(
    robot: Any,
    coords: list[float],
    angles: list[float],
    target: list[float],
    step_mm: float,
    speed: int,
    max_joint_change: float,
    min_margin: float,
    label: str,
    linear_mode: bool = False,
) -> tuple[list[float], list[float]]:
    step_number = 0
    while _distance(coords, target) > 0.8:
        next_coords = _next_xyz(coords, target, step_mm)
        solution = _checked_solution(
            robot.solve_inv_kinematics(next_coords, angles),
            angles,
            max_joint_change,
            min_margin,
        )
        before_distance = _distance(coords, target)
        if linear_mode:
            robot.send_coords(next_coords, speed, 1)
        else:
            robot.send_angles(solution, speed)
        _wait_stopped(robot, min_wait=max(1.0, 5.0 / speed))
        new_coords = _read_six(robot, "get_coords")
        new_angles = _read_six(robot, "get_angles")
        error_code = robot.get_error_information()
        if error_code not in (0, None):
            robot.stop()
            raise RuntimeError(f"{label}过程中错误码为 {error_code}")
        after_distance = _distance(new_coords, target)
        if after_distance >= before_distance - 0.15:
            robot.stop()
            raise RuntimeError(
                f"{label}没有取得有效进展，已停止: {before_distance:.2f} -> {after_distance:.2f} mm"
            )
        if _distance(coords, new_coords) > step_mm * 3.0:
            robot.stop()
            raise RuntimeError(f"{label}出现异常位移，已停止")
        coords, angles = new_coords, new_angles
        step_number += 1
        print(f"{label} {step_number}: z={coords[2]:.1f} mm")
    return coords, angles


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 单次分段下降、夹紧并抬升")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--grasp-z", type=float, required=True)
    parser.add_argument("--lift-z", type=float, default=170.0)
    parser.add_argument("--step-mm", type=float, default=3.0)
    parser.add_argument("--arm-speed", type=int, default=3)
    parser.add_argument("--gripper-speed", type=int, default=3)
    parser.add_argument("--close-value", type=int, default=45)
    parser.add_argument("--max-joint-change", type=float, default=8.0)
    parser.add_argument("--min-margin", type=float, default=5.0)
    parser.add_argument("--xy-tolerance", type=float, default=12.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 AUTO_GRASP")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not 85.0 <= args.grasp_z <= 140.0:
        parser.error("--grasp-z 必须在 85 到 140 mm 之间")
    if not args.grasp_z + 20.0 <= args.lift_z <= 220.0:
        parser.error("--lift-z 必须至少比 grasp-z 高 20 mm，且不超过 220 mm")
    if not 1.0 <= args.step_mm <= 4.0:
        parser.error("--step-mm 必须在 1 到 4 mm 之间")
    if not 1 <= args.arm_speed <= 5 or not 1 <= args.gripper_speed <= 5:
        parser.error("速度必须在 1 到 5 之间")
    if not 35 <= args.close_value <= 50:
        parser.error("--close-value 必须在 35 到 50 之间")
    if not 3.0 <= args.min_margin <= 15.0:
        parser.error("--min-margin 必须在 3 到 15 度之间")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        if robot.is_moving() != 0:
            raise RuntimeError("机械臂仍在运动")
        if robot.get_fresh_mode() != 1:
            raise RuntimeError("fresh_mode 不是 1，请先运行 controller_prepare")
        error_before = robot.get_error_information()
        if error_before not in (0, None):
            raise RuntimeError(f"机械臂当前错误码为 {error_before}")

        coords = _read_six(robot, "get_coords")
        angles = _read_six(robot, "get_angles")
        xy_error = math.hypot(coords[0] - args.x, coords[1] - args.y)
        if xy_error > args.xy_tolerance:
            raise RuntimeError(
                f"当前位置没有对准目标 XY，相差 {xy_error:.1f} mm，未执行"
            )
        if coords[2] < args.lift_z:
            raise RuntimeError(f"起始高度仅 {coords[2]:.1f} mm，必须先回到目标上方")

        orientation = coords[3:]
        grasp_target = [args.x, args.y, args.grasp_z, *orientation]
        lift_target = [args.x, args.y, args.lift_z, *orientation]
        planned_steps = _preflight(
            robot,
            coords,
            angles,
            [grasp_target, lift_target],
            args.step_mm,
            args.max_joint_change,
            args.min_margin,
        )
        preview = {
            "current_coords": coords,
            "current_angles": angles,
            "grasp_target": grasp_target,
            "lift_target": lift_target,
            "planned_steps": planned_steps,
            "close_value": args.close_value,
            "motion_allowed": args.confirm == "AUTO_GRASP",
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if args.confirm != "AUTO_GRASP":
            print("预检通过，但未执行。确认现场安全后加入 --confirm AUTO_GRASP。")
            return 2

        print("即将张开夹爪、分段下降、夹紧并抬升。请确保夹爪正对瓶颈且工作区无人手。")
        robot.set_gripper_state(0, args.gripper_speed)
        time.sleep(2.0)
        opened_value = robot.get_gripper_value()
        if opened_value == -1:
            raise RuntimeError("无法确认夹爪已张开，未下降")

        coords, angles = _move_checked(
            robot,
            coords,
            angles,
            grasp_target,
            args.step_mm,
            args.arm_speed,
            args.max_joint_change,
            args.min_margin,
            "下降",
        )
        robot.set_gripper_value(args.close_value, args.gripper_speed)
        time.sleep(2.5)
        closed_value = robot.get_gripper_value()
        if closed_value == -1:
            raise RuntimeError("夹紧后无法读取夹爪值，未抬升")

        coords, angles = _move_checked(
            robot,
            coords,
            angles,
            lift_target,
            args.step_mm,
            args.arm_speed,
            args.max_joint_change,
            args.min_margin,
            "抬升",
        )
        result = {
            "opened_gripper": opened_value,
            "closed_gripper": closed_value,
            "final_coords": coords,
            "final_angles": angles,
            "error": robot.get_error_information(),
            "is_moving": robot.is_moving(),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["error"] in (0, None) and result["is_moving"] == 0 else 1
    except KeyboardInterrupt:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        print("\n已发送停止请求；请立即确认机械臂停止。")
        return 130
    except Exception as exc:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        LOGGER.error("自动抓取测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
