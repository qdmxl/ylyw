"""Move joints 5 and 6 toward conservative targets in small steps."""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def _read_angles(robot: Any, attempts: int = 5, delay: float = 0.4) -> Any:
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _small_steps(start: float, target: float, max_step: float) -> list[float]:
    count = max(1, math.ceil(abs(target - start) / max_step))
    return [start + (target - start) * index / count for index in range(1, count + 1)]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 第 5/6 关节小步回中并保存姿态")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--speed", type=int, default=3)
    parser.add_argument("--joint5-target", type=float, default=-130.0)
    parser.add_argument("--joint6-target", type=float, default=135.0)
    parser.add_argument("--max-step", type=float, default=5.0)
    parser.add_argument("--wait", type=float, default=2.5)
    parser.add_argument("--output", type=Path, default=Path("poses/above_recentered.json"))
    parser.add_argument("--confirm", default="", help="必须精确填写 RECENTER")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "RECENTER":
        print("安全保护：未恢复关节。确认夹爪已打开、周围无物体后加入 --confirm RECENTER。")
        return 2
    if not 1 <= args.speed <= 5:
        parser.error("--speed 必须在 1 到 5 之间")
    if not -145 <= args.joint5_target <= 145:
        parser.error("--joint5-target 必须在 -145 到 145 度之间")
    if not -160 <= args.joint6_target <= 160:
        parser.error("--joint6-target 必须在 -160 到 160 度之间")
    if not 2 <= args.max_step <= 8:
        parser.error("--max-step 必须在 2 到 8 度之间")
    if not 1.5 <= args.wait <= 6:
        parser.error("--wait 必须在 1.5 到 6 秒之间")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        if robot.is_moving() != 0 or robot.get_fresh_mode() != 1:
            raise RuntimeError("机械臂必须停止且 fresh_mode 必须为 1")
        if robot.get_error_information() not in (0, None):
            raise RuntimeError("机械臂有错误码，请先清除")
        angles = _read_angles(robot)
        if not isinstance(angles, list) or len(angles) != 6:
            raise RuntimeError(f"读取角度失败: {angles}")

        targets = {5: args.joint5_target, 6: args.joint6_target}
        for joint_id, target in targets.items():
            current = _read_angles(robot)
            if not isinstance(current, list) or len(current) != 6:
                raise RuntimeError(f"关节 {joint_id} 动作前读取失败: {current}")
            start = float(current[joint_id - 1])
            if abs(target - start) < 0.5:
                print(f"关节 {joint_id} 已在安全范围，跳过")
                continue
            print(
                f"关节 {joint_id}: {start:.2f} -> {target:.2f} 度，"
                f"每步不超过 {args.max_step:.1f} 度"
            )
            previous_error = abs(target - start)
            for step_target in _small_steps(start, target, args.max_step):
                robot.send_angle(joint_id, step_target, args.speed)
                time.sleep(args.wait)
                after = _read_angles(robot)
                error_code = robot.get_error_information()
                if error_code not in (0, None) or not isinstance(after, list) or len(after) != 6:
                    robot.stop()
                    raise RuntimeError("回中过程中出现错误，已停止")
                remaining = abs(target - float(after[joint_id - 1]))
                print(f"  关节 {joint_id}={after[joint_id - 1]:.2f}，剩余 {remaining:.2f} 度")
                if remaining >= previous_error - 0.2:
                    robot.stop()
                    raise RuntimeError(f"关节 {joint_id} 未向目标取得有效进展，已停止")
                previous_error = remaining

        final_angles = _read_angles(robot)
        final_coords = robot.get_coords()
        if not isinstance(final_angles, list) or len(final_angles) != 6:
            raise RuntimeError(f"回中后读取角度失败: {final_angles}")
        if not isinstance(final_coords, list) or len(final_coords) != 6:
            raise RuntimeError(f"回中后读取坐标失败: {final_coords}")
        payload = {
            "name": args.output.stem,
            "model": "280-m5",
            "port": args.port,
            "baudrate": args.baudrate,
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "angles": final_angles,
            "coords": final_coords,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"第 5、6 关节已小步回中；未操作夹爪。姿态已保存: {args.output}")
        return 0
    except Exception as exc:
        LOGGER.error("关节恢复失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
