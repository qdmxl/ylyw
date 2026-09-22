"""Read or explicitly clear a MyCobot controller error without moving it."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 错误码查询/清除（不运动）")
    parser.add_argument("action", choices=("read", "clear"))
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--confirm", default="", help="清除时必须精确填写 CLEAR")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.action == "clear" and args.confirm != "CLEAR":
        print("安全保护：未清除错误。确认机械臂已停止后加入 --confirm CLEAR。")
        return 2

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        before = robot.get_error_information()
        print(f"当前错误码: {before}")
        if args.action == "read":
            return 0
        robot.clear_error_information()
        time.sleep(1.0)
        after = robot.get_error_information()
        print(f"清除后错误码: {after}")
        print("未发送任何运动或夹爪命令。")
        return 0 if after in (0, None) else 1
    except Exception as exc:
        LOGGER.error("错误码操作失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
