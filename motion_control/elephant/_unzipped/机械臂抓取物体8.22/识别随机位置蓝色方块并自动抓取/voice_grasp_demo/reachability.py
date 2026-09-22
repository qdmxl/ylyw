"""Inverse-kinematics reachability dry run; never sends motion commands."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 280-M5 目标点可达性测试（不运动）")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--z", type=float, required=True)
    parser.add_argument("--rx", type=float, default=135.9)
    parser.add_argument("--ry", type=float, default=23.32)
    parser.add_argument("--rz", type=float, default=-130.27)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1
    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        current_angles = robot.get_angles()
        if not isinstance(current_angles, list) or len(current_angles) != 6 or any(value == -1 for value in current_angles):
            LOGGER.error("无法读取当前角度: %s", current_angles)
            return 1
        target = [args.x, args.y, args.z, args.rx, args.ry, args.rz]
        solution = robot.solve_inv_kinematics(target, current_angles)
        result = {
            "target_coords": target,
            "current_angles": current_angles,
            "ik_solution": solution,
            "motion_allowed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("仅完成逆运动学可达性计算：未发送运动命令。")
        return 0 if isinstance(solution, list) and len(solution) == 6 and all(value != -1 for value in solution) else 1
    except Exception as exc:
        LOGGER.error("可达性计算失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
