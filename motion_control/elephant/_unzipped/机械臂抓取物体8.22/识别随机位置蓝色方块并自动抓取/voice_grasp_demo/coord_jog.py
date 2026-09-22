"""Low-speed Cartesian jogging and coordinate capture for calibration.

This is an explicit tool, separate from the automatic workflow. It uses small
coordinate increments and requires ``--confirm JOG`` before sending commands.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


def _read_coords(robot, attempts: int = 3, delay: float = 0.4):
    last = None
    for attempt in range(attempts):
        last = robot.get_coords()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _read_angles(robot, attempts: int = 3, delay: float = 0.4):
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _wait_until_stopped(robot, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        moving = robot.is_moving()
        if moving == 0:
            return
        if moving == -1:
            break
        time.sleep(0.2)
    robot.stop()
    raise RuntimeError("点动未在限定时间内停止，已发送停止请求")


def _save_point(output: Path, name: str, coords: list[float]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        payload = json.loads(output.read_text(encoding="utf-8"))
    else:
        payload = {"points": []}
    payload["points"].append({
        "name": name,
        "coords": coords,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
    })
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 {name}: {coords} -> {output}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 280-M5 低速坐标点动与记录")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--step", type=float, default=2.0, help="每次 X/Y/Z 步进，建议 1-2 mm")
    parser.add_argument("--speed", type=int, default=5, help="速度，建议 5")
    parser.add_argument("--output", type=Path, default=Path("calibration/robot_points.json"))
    parser.add_argument(
        "--lock-tool",
        action="store_true",
        help="锁定启动时的 Z 和末端姿态，只允许 X/Y 点动（用于平面标定）",
    )
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "JOG":
        print("安全保护：未启动点动。确认现场安全后加入 --confirm JOG。")
        return 2
    if not 0.5 <= args.step <= 5:
        parser.error("--step 必须在 0.5 到 5 mm 之间")
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
        coords = _read_coords(robot)
        if not isinstance(coords, list) or len(coords) != 6 or any(value == -1 for value in coords):
            LOGGER.error("无法读取初始坐标: %s", coords)
            return 1
        initial_error = robot.get_error_information()
        fresh_mode = robot.get_fresh_mode()
        if initial_error not in (0, None):
            LOGGER.error("机械臂当前错误码为 %s，未启动点动", initial_error)
            return 1
        if fresh_mode != 1:
            LOGGER.error("控制器 fresh_mode=%s，不是最新命令模式 1，未启动点动", fresh_mode)
            return 1
        print(f"当前 coords: {coords}")
        locked_tool = list(map(float, coords[2:])) if args.lock_tool else None
        if locked_tool is not None:
            print(f"平面标定锁定值: z/rx/ry/rz={locked_tool}；本次只允许 X/Y 点动。")
        print("命令: x+, x-, y+, y-, z+, z- 点动；p 读取；save 名称 保存；q 退出")
        print("注意：只做小步调整，始终观察夹爪和机械臂周围。")
        axis_ids = {"x": 1, "y": 2, "z": 3}
        while True:
            command = input("jog> ").strip().lower()
            if command in ("q", "quit", "exit"):
                print("已退出点动工具。")
                return 0
            if command in ("p", "print"):
                coords = _read_coords(robot)
                print(f"coords: {coords}")
                if args.lock_tool:
                    angles = _read_angles(robot)
                    print(f"angles: {angles}")
                continue
            if command.startswith("save "):
                name = command[5:].strip()
                if not name:
                    print("用法: save corner1")
                    continue
                coords = _read_coords(robot)
                if isinstance(coords, list) and len(coords) == 6 and all(value != -1 for value in coords):
                    if locked_tool is not None:
                        z_drift = abs(float(coords[2]) - locked_tool[0])
                        orientation_drift = max(
                            abs((float(actual) - expected + 180.0) % 360.0 - 180.0)
                            for actual, expected in zip(coords[3:], locked_tool[1:])
                        )
                        if z_drift > 3.0 or orientation_drift > 8.0:
                            print(
                                f"工具姿态已漂移：Z={z_drift:.2f} mm，"
                                f"角度={orientation_drift:.2f} 度；未保存。"
                            )
                            continue
                    _save_point(args.output, name, coords)
                else:
                    print(f"读取失败，未保存: {coords}")
                continue
            if len(command) == 2 and command[0] in axis_ids and command[1] in "+-":
                if args.lock_tool and command[0] == "z":
                    print("锁定姿态模式不允许 Z 点动；如需改变高度，请退出后重新启动工具。")
                    continue
                axis_id = axis_ids[command[0]]
                increment = args.step if command[1] == "+" else -args.step
                before_step = _read_coords(robot)
                before_angles = _read_angles(robot)
                if not isinstance(before_step, list) or len(before_step) != 6:
                    print(f"动作前坐标读取失败，未点动: {before_step}")
                    continue
                if not isinstance(before_angles, list) or len(before_angles) != 6:
                    print(f"动作前角度读取失败，未点动: {before_angles}")
                    continue
                target_coords = list(map(float, before_step))
                if locked_tool is not None:
                    target_coords[2:] = locked_tool
                target_coords[axis_id - 1] += increment
                solution = robot.solve_inv_kinematics(target_coords, before_angles)
                if not isinstance(solution, list) or len(solution) != 6 or any(value == -1 for value in solution):
                    print(f"目标没有有效逆解，未点动: {solution}")
                    continue
                joint_changes = [float(target) - float(current) for target, current in zip(solution, before_angles)]
                if max(abs(change) for change in joint_changes) > 5.0:
                    print(f"逆解所需关节变化过大，未点动: {joint_changes}")
                    continue
                robot.send_angles(solution, args.speed)
                _wait_until_stopped(robot)
                coords = _read_coords(robot)
                print(f"动作后 coords: {coords}")
                error_code = robot.get_error_information()
                print(f"动作后错误码: {error_code}")
                if error_code not in (0, None):
                    robot.stop()
                    print("检测到错误，已发送停止请求并退出点动工具。")
                    return 1
                if isinstance(coords, list) and len(coords) == 6:
                    if locked_tool is not None:
                        z_drift = abs(float(coords[2]) - locked_tool[0])
                        orientation_drift = max(
                            abs((float(actual) - expected + 180.0) % 360.0 - 180.0)
                            for actual, expected in zip(coords[3:], locked_tool[1:])
                        )
                        if z_drift > 3.0 or orientation_drift > 8.0:
                            robot.stop()
                            print(
                                f"检测到工具姿态漂移：Z={z_drift:.2f} mm，"
                                f"角度={orientation_drift:.2f} 度；已停止并退出。"
                            )
                            return 1
                    actual_delta = float(coords[axis_id - 1]) - float(before_step[axis_id - 1])
                    if abs(actual_delta - increment) > max(3.0, abs(args.step) * 2.0):
                        robot.stop()
                        print(
                            f"检测到异常位移 {actual_delta:.2f} mm（期望 {increment:.2f} mm），"
                            "已发送停止请求并退出点动工具。"
                        )
                        return 1
                continue
            print("无效命令。可用: x+, x-, y+, y-, z+, z-, p, save 名称, q")
    except KeyboardInterrupt:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        print("\n已发送停止请求，请确认机械臂已经停止。")
        return 130
    except Exception as exc:
        LOGGER.error("点动失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
