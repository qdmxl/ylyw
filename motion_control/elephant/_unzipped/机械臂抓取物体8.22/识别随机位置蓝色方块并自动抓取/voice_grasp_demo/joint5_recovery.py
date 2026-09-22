"""Recover joint 5 from below its SDK command limit without other motion."""

from __future__ import annotations

import argparse
import logging
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def _read_angles(robot: Any, attempts: int = 6, delay: float = 0.5) -> Any:
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 第 5 关节负限位恢复")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--target", type=float, default=-154.0)
    parser.add_argument("--speed", type=int, default=5)
    parser.add_argument("--wait", type=float, default=5.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 RECOVER")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "RECOVER":
        print("安全保护：未执行恢复。确认末端周围无障碍后加入 --confirm RECOVER。")
        return 2
    if not -154.0 <= args.target <= -150.0:
        parser.error("恢复目标必须在 -154 到 -150 度之间")
    if not 1 <= args.speed <= 5:
        parser.error("恢复速度必须在 1 到 5 之间")

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
        joint5 = float(before[4])
        if joint5 >= -155.0:
            raise RuntimeError(f"第 5 关节已在合法范围内 ({joint5:.2f})，无需恢复")
        if args.target <= joint5:
            raise RuntimeError("恢复目标必须远离当前负限位")
        if error_before not in (0, 5, None):
            raise RuntimeError(f"机械臂存在非预期错误码 {error_before}，未运动")

        if error_before == 5:
            print("检测到第 5 关节限位错误码 5，正在清除后执行脱离限位动作。")
            robot.clear_error_information()
            time.sleep(0.5)
            cleared_error = robot.get_error_information()
            if cleared_error not in (0, None):
                raise RuntimeError(f"错误码未能清除 ({cleared_error})，未运动")

        print(f"当前第 5 关节: {joint5:.2f} 度")
        print(f"恢复目标: {args.target:.2f} 度，速度 {args.speed}")
        print("只移动第 5 关节；请确认夹爪周围无人手、无物体，并能立即切断电源。")
        robot.send_angle(5, args.target, args.speed)
        time.sleep(args.wait)
        after = _read_angles(robot)
        error_after = robot.get_error_information()
        print(f"恢复后角度: {after}")
        print(f"恢复后错误码: {error_after}")
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
        LOGGER.error("第 5 关节恢复失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
