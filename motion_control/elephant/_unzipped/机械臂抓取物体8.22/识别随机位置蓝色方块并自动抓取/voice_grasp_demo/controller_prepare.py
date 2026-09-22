"""Stop queued motion and enable latest-command mode without starting motion."""

from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Optional

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 抓取测试前控制器准备")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--confirm", default="", help="必须精确填写 LATEST")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "LATEST":
        print("安全保护：未更改控制器模式。确认机械臂已停止后加入 --confirm LATEST。")
        return 2

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        before = {
            "is_moving": robot.is_moving(),
            "fresh_mode": robot.get_fresh_mode(),
            "error": robot.get_error_information(),
        }
        print("设置前:")
        print(json.dumps(before, ensure_ascii=False, indent=2))
        if before["is_moving"] not in (0, None):
            raise RuntimeError(f"机械臂仍在运动 ({before['is_moving']})，未更改模式")
        if before["error"] not in (0, None):
            raise RuntimeError(f"机械臂存在错误码 {before['error']}，未更改模式")

        robot.stop()
        time.sleep(0.3)
        robot.set_fresh_mode(1)
        time.sleep(0.8)
        after = {
            "is_moving": robot.is_moving(),
            "fresh_mode": robot.get_fresh_mode(),
            "error": robot.get_error_information(),
        }
        print("设置后:")
        print(json.dumps(after, ensure_ascii=False, indent=2))
        print("已停止旧运动并切换为最新命令模式；未发送位置或夹爪命令。")
        return 0 if after["is_moving"] == 0 and after["fresh_mode"] == 1 and after["error"] in (0, None) else 1
    except Exception as exc:
        LOGGER.error("控制器准备失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
