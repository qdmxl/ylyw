"""Capture and explicitly replay a verified MyCobot 280-M5 pose."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def _read_angles(robot, attempts: int = 3, delay: float = 0.5) -> Any:
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _connect(port: str, baudrate: int):
    try:
        from pymycobot import MyCobot280
    except ImportError as exc:
        raise RuntimeError("未安装 pymycobot") from exc
    return MyCobot280(port, baudrate, timeout=2)


def capture(port: str, baudrate: int, output: Path, name: str) -> int:
    robot = _connect(port, baudrate)
    try:
        angles = _read_angles(robot)
        coords = robot.get_coords()
        if not isinstance(angles, list) or len(angles) != 6 or any(value == -1 for value in angles):
            raise RuntimeError(f"读取角度失败，未保存姿态: {angles}")
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": name,
            "model": "280-m5",
            "port": port,
            "baudrate": baudrate,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "angles": angles,
            "coords": coords,
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"姿态已保存: {output}")
        return 0
    finally:
        robot.close()


def move(port: str, baudrate: int, pose_file: Path, speed: int, wait: float, confirm: str) -> int:
    if confirm != "POSE":
        print("安全保护：未执行姿态运动。确认现场安全后加入 --confirm POSE。")
        return 2
    payload = json.loads(pose_file.read_text(encoding="utf-8"))
    target = payload.get("angles")
    if not isinstance(target, list) or len(target) != 6:
        raise RuntimeError("姿态文件必须包含 6 个 angles 值")
    if not all(isinstance(value, (int, float)) and -170 <= float(value) <= 170 for value in target):
        raise RuntimeError("姿态角度超出 -170 到 170 度的保守范围")

    robot = _connect(port, baudrate)
    try:
        before = _read_angles(robot)
        if not isinstance(before, list) or len(before) != 6 or any(value == -1 for value in before):
            raise RuntimeError(f"运动前读取角度失败，未发送姿态命令: {before}")
        print(f"当前角度: {before}")
        print(f"目标姿态: {target}")
        print("请确认底座固定、工作区无人手、夹爪无物体，并能立即切断电源。")
        robot.send_angles(target, speed)
        time.sleep(wait)
        after = _read_angles(robot)
        print(f"动作后角度: {after}")
        return 0
    finally:
        robot.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="安全姿态保存/复现")
    sub = parser.add_subparsers(dest="action", required=True)

    capture_parser = sub.add_parser("capture", help="只读取并保存当前姿态")
    capture_parser.add_argument("--port", default="COM10")
    capture_parser.add_argument("--baudrate", type=int, default=115200)
    capture_parser.add_argument("--output", type=Path, default=Path("poses/home.json"))
    capture_parser.add_argument("--name", default="home")

    move_parser = sub.add_parser("move", help="回到已保存姿态")
    move_parser.add_argument("--port", default="COM10")
    move_parser.add_argument("--baudrate", type=int, default=115200)
    move_parser.add_argument("--pose-file", type=Path, default=Path("poses/home.json"))
    move_parser.add_argument("--speed", type=int, default=10)
    move_parser.add_argument("--wait", type=float, default=4.0)
    move_parser.add_argument("--confirm", default="")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.action == "capture":
            return capture(args.port, args.baudrate, args.output, args.name)
        if not 1 <= args.speed <= 20:
            parser.error("--speed 必须在 1 到 20 之间")
        return move(args.port, args.baudrate, args.pose_file, args.speed, args.wait, args.confirm)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        print("\n已停止姿态测试，请确认机械臂处于安全状态。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
