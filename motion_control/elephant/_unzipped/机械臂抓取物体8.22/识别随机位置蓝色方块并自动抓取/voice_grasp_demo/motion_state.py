"""Read MyCobot motion and command-queue state without moving it."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 运动/命令模式只读检查")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
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
        result = {
            "is_moving": robot.is_moving(),
            "fresh_mode": robot.get_fresh_mode(),
            "error": robot.get_error_information(),
            "angles": robot.get_angles(),
            "coords": robot.get_coords(),
            "motion_command_sent": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("仅查询控制器状态：未发送运动、夹爪或 IO 命令。")
        return 0
    except Exception as exc:
        LOGGER.error("控制器状态查询失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
