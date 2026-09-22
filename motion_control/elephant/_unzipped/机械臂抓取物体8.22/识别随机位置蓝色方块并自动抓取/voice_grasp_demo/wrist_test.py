"""Explicit low-speed incremental joint-6 rotation test."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def _read_angles(robot: Any, attempts: int = 4, delay: float = 0.5) -> Any:
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 第 6 关节分段旋转测试")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--delta", type=float, required=True, help="单次变化，范围 -10 到 10 度")
    parser.add_argument("--speed", type=int, default=8)
    parser.add_argument("--wait", type=float, default=3.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 WRIST")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "WRIST":
        print("安全保护：未旋转夹爪。确认线缆有余量后加入 --confirm WRIST。")
        return 2
    if args.delta == 0 or not -10 <= args.delta <= 10:
        parser.error("--delta 必须在 -10 到 10 度之间且不能为 0")
    if not 1 <= args.speed <= 10:
        parser.error("--speed 必须在 1 到 10 之间")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        before = _read_angles(robot)
        error_before = robot.get_error_information()
        if not isinstance(before, list) or len(before) != 6:
            raise RuntimeError(f"读取当前角度失败，未运动: {before}")
        if error_before not in (0, None):
            raise RuntimeError(f"机械臂当前错误码为 {error_before}，未运动")
        target = float(before[5]) + args.delta
        if not -165 <= target <= 165:
            raise RuntimeError(f"第 6 关节目标 {target:.2f} 度超出保守范围，未运动")

        print(f"当前第 6 关节: {before[5]:.2f} 度")
        print(f"目标第 6 关节: {target:.2f} 度（变化 {args.delta:+.2f} 度）")
        print("请确认夹爪线缆有余量、周围无人手，并能立即切断电源。")
        robot.send_angle(6, target, args.speed)
        time.sleep(args.wait)
        after = _read_angles(robot)
        error_after = robot.get_error_information()
        print(f"动作后角度: {after}")
        print(f"动作后错误码: {error_after}")
        return 0 if isinstance(after, list) and len(after) == 6 and error_after in (0, None) else 1
    except KeyboardInterrupt:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        print("\n已发送停止请求；请确认机械臂停止。")
        return 130
    except Exception as exc:
        LOGGER.error("第 6 关节旋转测试失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
