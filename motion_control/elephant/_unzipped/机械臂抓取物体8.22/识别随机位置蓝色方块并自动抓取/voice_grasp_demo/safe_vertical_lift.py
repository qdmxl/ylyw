"""Lift vertically from the current pose without operating the gripper."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

from .auto_grasp_once import _move_checked, _preflight, _read_six

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 从当前位置分段垂直抬升")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--lift-mm", type=float, default=40.0)
    parser.add_argument("--step-mm", type=float, default=2.0)
    parser.add_argument("--speed", type=int, default=2)
    parser.add_argument("--max-joint-change", type=float, default=8.0)
    parser.add_argument("--min-margin", type=float, default=5.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 LIFT")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not 5.0 <= args.lift_mm <= 50.0:
        parser.error("--lift-mm 必须在 5 到 50 mm 之间")
    if not 1.0 <= args.step_mm <= 5.0:
        parser.error("--step-mm 必须在 1 到 5 mm 之间")
    if not 1 <= args.speed <= 5:
        parser.error("--speed 必须在 1 到 5 之间")
    if not 1.0 <= args.max_joint_change <= 10.0:
        parser.error("--max-joint-change 必须在 1 到 10 度之间")
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
        target = list(coords)
        target[2] += args.lift_mm
        if target[2] > 250.0:
            raise RuntimeError(f"抬升目标 Z={target[2]:.1f} mm 超过保守上限 250 mm")
        planned_steps = _preflight(
            robot,
            coords,
            angles,
            [target],
            args.step_mm,
            args.max_joint_change,
            args.min_margin,
        )
        preview = {
            "current_coords": coords,
            "target_coords": target,
            "planned_steps": planned_steps,
            "gripper_command_sent": False,
            "motion_allowed": args.confirm == "LIFT",
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if args.confirm != "LIFT":
            print("预检通过，但未抬升。确认现场安全后加入 --confirm LIFT。")
            return 2

        print(f"即将从当前位置垂直抬升 {args.lift_mm:.1f} mm；不会控制夹爪。")
        coords, angles = _move_checked(
            robot,
            coords,
            angles,
            target,
            args.step_mm,
            args.speed,
            args.max_joint_change,
            args.min_margin,
            "抬升",
            linear_mode=True,
        )
        result = {
            "final_coords": coords,
            "final_angles": angles,
            "actual_lift_mm": round(coords[2] - preview["current_coords"][2], 2),
            "error": robot.get_error_information(),
            "is_moving": robot.is_moving(),
            "gripper_command_sent": False,
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
        LOGGER.error("垂直抬升失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
