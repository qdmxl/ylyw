"""Explicit MyCobot 280-M5 gripper test.

The default action is read-only. Hardware writes require the exact
``--confirm GRIPPER`` token and use a low speed.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 280-M5 夹爪测试")
    parser.add_argument("--port", required=True, help="例如 COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--action", choices=("read", "open", "position"), default="read")
    parser.add_argument("--value", type=int, default=10, help="position 动作的夹爪位置 0-100")
    parser.add_argument("--speed", type=int, default=10, help="动作速度 1-20")
    parser.add_argument("--wait", type=float, default=2.0)
    parser.add_argument("--confirm", default="", help="硬件动作必须精确填写 GRIPPER")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.action != "read" and args.confirm != "GRIPPER":
        print("安全保护：未执行真实夹爪动作。确认现场安全后加入 --confirm GRIPPER。")
        return 2
    if not 0 <= args.value <= 100:
        parser.error("--value 必须在 0 到 100 之间")
    if not 1 <= args.speed <= 20:
        parser.error("--speed 必须在 1 到 20 之间")
    if args.wait <= 0:
        parser.error("--wait 必须大于 0")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot，请执行: python -m pip install pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        before = robot.get_gripper_value()
        print(f"动作前夹爪值: {before}")
        if before == -1:
            LOGGER.error("无法读取夹爪值，未执行夹爪动作")
            return 1

        if args.action == "read":
            return 0

        print("请确认夹爪附近无人手、没有夹持物，并能立即切断电源。")
        if args.action == "open":
            robot.set_gripper_state(0, args.speed)
        else:
            robot.set_gripper_value(args.value, args.speed)
        time.sleep(args.wait)
        print(f"动作后夹爪值: {robot.get_gripper_value()}")
        return 0
    except KeyboardInterrupt:
        print("\n已停止夹爪测试，请确认夹爪已停止并处于安全状态。")
        return 130
    except Exception as exc:
        LOGGER.error("夹爪测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
