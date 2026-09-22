"""Explicit staged close-and-lift test with conservative motion guards."""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)

LIMITS = [
    (-168.0, 168.0),
    (-140.0, 140.0),
    (-150.0, 150.0),
    (-150.0, 150.0),
    (-155.0, 160.0),
    (-180.0, 180.0),
]


def _read_six(robot: Any, method_name: str, attempts: int = 5, delay: float = 0.5) -> Any:
    method = getattr(robot, method_name)
    last = None
    for attempt in range(attempts):
        last = method()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _commandable_solution(solution: Any) -> list[float]:
    if not isinstance(solution, list) or len(solution) != 6:
        raise RuntimeError(f"抬升目标没有有效逆解: {solution}")
    adjusted: list[float] = []
    for index, (value, (low, high)) in enumerate(zip(solution, LIMITS), start=1):
        value = float(value)
        if not math.isfinite(value):
            raise RuntimeError(f"关节 {index} 的逆解不是有限数值")
        if value < low:
            if low - value > 1.5:
                raise RuntimeError(f"关节 {index} 逆解 {value:.2f} 度越过下限过多")
            value = low + 1.0
        elif value > high:
            if value - high > 1.5:
                raise RuntimeError(f"关节 {index} 逆解 {value:.2f} 度越过上限过多")
            value = high - 1.0
        adjusted.append(round(value, 2))
    return adjusted


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 分步夹紧并小幅抬升测试")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--close-value", type=int, default=45)
    parser.add_argument("--lift-mm", type=float, default=10.0)
    parser.add_argument("--gripper-speed", type=int, default=3)
    parser.add_argument("--arm-speed", type=int, default=3)
    parser.add_argument("--wait", type=float, default=5.0)
    parser.add_argument("--max-joint-change", type=float, default=10.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 GRASP_LIFT")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not 35 <= args.close_value <= 50:
        parser.error("--close-value 必须在 35 到 50 之间")
    if not 2.0 <= args.lift_mm <= 10.0:
        parser.error("--lift-mm 必须在 2 到 10 mm 之间")
    if not 1 <= args.gripper_speed <= 5 or not 1 <= args.arm_speed <= 5:
        parser.error("夹爪和机械臂速度必须在 1 到 5 之间")
    if not 1.0 <= args.max_joint_change <= 10.0:
        parser.error("--max-joint-change 必须在 1 到 10 度之间")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        state = {
            "is_moving": robot.is_moving(),
            "fresh_mode": robot.get_fresh_mode(),
            "error": robot.get_error_information(),
        }
        if state["is_moving"] != 0:
            raise RuntimeError(f"机械臂仍在运动: {state['is_moving']}")
        if state["fresh_mode"] != 1:
            raise RuntimeError(f"fresh_mode={state['fresh_mode']}，必须先设置为 1")
        if state["error"] not in (0, None):
            raise RuntimeError(f"机械臂当前错误码为 {state['error']}")

        before_angles = _read_six(robot, "get_angles")
        before_coords = _read_six(robot, "get_coords")
        before_gripper = robot.get_gripper_value()
        if not isinstance(before_angles, list) or len(before_angles) != 6:
            raise RuntimeError(f"读取当前角度失败: {before_angles}")
        if not isinstance(before_coords, list) or len(before_coords) != 6:
            raise RuntimeError(f"读取当前坐标失败: {before_coords}")
        if before_gripper == -1:
            raise RuntimeError("读取夹爪值失败")

        target_coords = list(map(float, before_coords))
        target_coords[2] += args.lift_mm
        raw_solution = robot.solve_inv_kinematics(target_coords, before_angles)
        command_angles = _commandable_solution(raw_solution)
        changes = [round(target - float(current), 2) for target, current in zip(command_angles, before_angles)]
        if max(abs(change) for change in changes) > args.max_joint_change:
            raise RuntimeError(
                f"抬升所需单关节变化超过 {args.max_joint_change:.1f} 度，未执行: {changes}"
            )

        preview = {
            "current_angles": before_angles,
            "current_coords": before_coords,
            "current_gripper": before_gripper,
            "target_coords": target_coords,
            "raw_ik_solution": raw_solution,
            "command_angles": command_angles,
            "joint_changes": changes,
            "close_value": args.close_value,
            "motion_allowed": args.confirm == "GRASP_LIFT",
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if args.confirm != "GRASP_LIFT":
            print("预览完成：未发送夹爪或运动命令。")
            return 2

        print("即将夹紧并抬升最多 10 mm。请确认工作区无人手，并能立即切断电源。")
        robot.stop()
        robot.set_fresh_mode(1)
        if before_gripper > args.close_value:
            robot.set_gripper_value(args.close_value, args.gripper_speed)
            time.sleep(2.0)
        gripper_after_close = robot.get_gripper_value()
        if gripper_after_close == -1:
            raise RuntimeError("夹紧后无法读取夹爪值，未抬升")

        robot.send_angles(command_angles, args.arm_speed)
        time.sleep(args.wait)
        after_angles = _read_six(robot, "get_angles")
        after_coords = _read_six(robot, "get_coords")
        error_after = robot.get_error_information()
        moving_after = robot.is_moving()
        if error_after not in (0, None):
            robot.stop()

        result = {
            "gripper_after_close": gripper_after_close,
            "after_angles": after_angles,
            "after_coords": after_coords,
            "actual_lift_mm": (
                round(float(after_coords[2]) - float(before_coords[2]), 2)
                if isinstance(after_coords, list) and len(after_coords) == 6
                else None
            ),
            "error": error_after,
            "is_moving": moving_after,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if error_after in (0, None) and moving_after == 0 else 1
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
        LOGGER.error("夹紧抬升测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
