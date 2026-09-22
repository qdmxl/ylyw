"""Explicit, small single-joint motion test for MyCobot 280-M5.

This module is intentionally separate from the read-only diagnostics and the
voice/vision pipeline. It refuses to move unless the caller passes the exact
confirmation token ``--confirm MOVE``.
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

LOGGER = logging.getLogger(__name__)


def _read_angles_with_retry(robot, attempts: int = 3, delay: float = 0.5):
    """Tolerate a transient -1 reply immediately after a motion command."""
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 280-M5 单关节小幅度运动测试")
    parser.add_argument("--port", required=True, help="例如 COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--joint", type=int, default=1, help="关节编号 1-6")
    parser.add_argument("--delta", type=float, default=3.0, help="相对当前角度的变化，范围 -3 到 3 度")
    parser.add_argument("--speed", type=int, default=10, help="运动速度，范围 1-20")
    parser.add_argument("--wait", type=float, default=3.0, help="动作后等待秒数")
    parser.add_argument("--confirm", default="", help="必须精确填写 MOVE 才允许发送运动命令")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "MOVE":
        print("安全保护：未执行运动。确认现场安全后，在命令末尾加入 --confirm MOVE。")
        return 2
    if not 1 <= args.joint <= 6:
        parser.error("--joint 必须是 1 到 6")
    if not -3.0 <= args.delta <= 3.0 or args.delta == 0:
        parser.error("--delta 必须在 -3 到 3 度之间且不能为 0")
    if not 1 <= args.speed <= 20:
        parser.error("--speed 必须在 1 到 20 之间")
    if args.wait <= 0:
        parser.error("--wait 必须大于 0")

    try:
        from pymycobot import MyCobot280
    except ImportError as exc:
        LOGGER.error("未安装 pymycobot，请执行: python -m pip install pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        before = _read_angles_with_retry(robot)
        if not isinstance(before, list) or len(before) != 6 or any(value == -1 for value in before):
            LOGGER.error("运动前读取角度失败，未发送运动命令: %s", before)
            return 1

        current = float(before[args.joint - 1])
        target = current + args.delta
        print(f"当前角度: {before}")
        print(f"即将移动关节 {args.joint}: {current:.2f} -> {target:.2f} 度，速度 {args.speed}")
        print("请确认底座固定、工作区无人手、末端无负载，并能立即切断电源。")

        robot.send_angle(args.joint, target, args.speed)
        time.sleep(args.wait)
        after = _read_angles_with_retry(robot)
        print(f"动作后角度: {after}")
        return 0
    except KeyboardInterrupt:
        print("\n已停止测试。请通过急停或断电确保机械臂处于安全状态。")
        return 130
    except Exception as exc:
        LOGGER.error("运动测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
