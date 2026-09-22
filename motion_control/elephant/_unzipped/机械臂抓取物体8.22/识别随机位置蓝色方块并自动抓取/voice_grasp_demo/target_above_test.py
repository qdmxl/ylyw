"""Safely preview or execute one high-level Cartesian positioning test."""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def _read_valid(robot: Any, method_name: str, attempts: int = 4, delay: float = 0.5) -> Any:
    last = None
    method = getattr(robot, method_name)
    for attempt in range(attempts):
        last = method()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 目标上方高位移动测试")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--z", type=float, required=True)
    parser.add_argument("--rx", type=float, required=True)
    parser.add_argument("--ry", type=float, required=True)
    parser.add_argument("--rz", type=float, required=True)
    parser.add_argument("--speed", type=int, default=10)
    parser.add_argument("--wait", type=float, default=6.0)
    parser.add_argument("--max-xy-distance", type=float, default=150.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 ABOVE 才允许运动")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    target = [args.x, args.y, args.z, args.rx, args.ry, args.rz]
    if not all(math.isfinite(value) for value in target):
        parser.error("目标坐标必须是有限数值")
    if not 1 <= args.speed <= 15:
        parser.error("--speed 必须在 1 到 15 之间")
    if not 200.0 <= args.z <= 300.0:
        parser.error("高位测试要求 --z 在 200 到 300 mm 之间")
    if args.max_xy_distance <= 0 or args.max_xy_distance > 150:
        parser.error("--max-xy-distance 必须在 0 到 150 mm 之间")
    if args.wait <= 0:
        parser.error("--wait 必须大于 0")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        current_angles = _read_valid(robot, "get_angles")
        current_coords = _read_valid(robot, "get_coords")
        error_code = robot.get_error_information()
        if not isinstance(current_angles, list) or len(current_angles) != 6:
            raise RuntimeError(f"读取当前角度失败，未运动: {current_angles}")
        if not isinstance(current_coords, list) or len(current_coords) != 6:
            raise RuntimeError(f"读取当前坐标失败，未运动: {current_coords}")
        if error_code not in (0, None):
            raise RuntimeError(f"机械臂当前错误码为 {error_code}，请先处理错误，未运动")

        xy_distance = math.hypot(args.x - current_coords[0], args.y - current_coords[1])
        if xy_distance > args.max_xy_distance:
            raise RuntimeError(
                f"水平移动距离 {xy_distance:.1f} mm 超过限制 "
                f"{args.max_xy_distance:.1f} mm，未运动"
            )

        solution = robot.solve_inv_kinematics(target, current_angles)
        if not isinstance(solution, list) or len(solution) != 6 or any(value == -1 for value in solution):
            raise RuntimeError(f"目标没有有效逆解，未运动: {solution}")

        preview = {
            "current_coords": current_coords,
            "target_coords": target,
            "xy_distance_mm": round(xy_distance, 2),
            "ik_solution": solution,
            "linear_mode": True,
            "motion_allowed": args.confirm == "ABOVE",
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if args.confirm != "ABOVE":
            print("预览完成：未发送运动命令。确认现场安全后加入 --confirm ABOVE。")
            return 2

        print("即将低速直线移动到目标高位；不会下降，也不会控制夹爪。")
        print("请确认底座固定、路径无障碍、工作区无人手，并能立即切断电源。")
        robot.send_coords(target, args.speed, mode=1)
        time.sleep(args.wait)
        after = _read_valid(robot, "get_coords")
        print(f"动作后坐标: {after}")
        after_error = robot.get_error_information()
        print(f"动作后错误码: {after_error}")
        return 0 if isinstance(after, list) and len(after) == 6 and after_error in (0, None) else 1
    except KeyboardInterrupt:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        print("\n已发送停止请求；请立即确认机械臂停止，必要时切断电源。")
        return 130
    except Exception as exc:
        LOGGER.error("目标上方测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
