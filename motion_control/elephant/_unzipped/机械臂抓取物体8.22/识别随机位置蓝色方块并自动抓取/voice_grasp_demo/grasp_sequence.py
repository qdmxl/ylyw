"""Execute a verified fixed-pose grasp sequence with explicit confirmation."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)
LIMITS = [(-168, 168), (-140, 140), (-150, 150), (-150, 150), (-155, 160), (-180, 180)]


def _pose(path: Path, min_margin: float) -> list[float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    angles = payload.get("angles")
    if not isinstance(angles, list) or len(angles) != 6:
        raise RuntimeError(f"姿态文件缺少 6 个 angles: {path}")
    values = [float(value) for value in angles]
    for index, (value, (low, high)) in enumerate(zip(values, LIMITS), start=1):
        if not low + min_margin <= value <= high - min_margin:
            raise RuntimeError(f"{path} 的关节 {index} 过于接近限位: {value:.2f}")
    return values


def _read_angles(robot: Any, attempts: int = 5, delay: float = 0.5) -> Any:
    last = None
    for attempt in range(attempts):
        last = robot.get_angles()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _wait_for_pose(robot: Any, target: list[float], timeout: float) -> list[float]:
    deadline = time.monotonic() + timeout
    last: Any = None
    previous: Any = None
    stable_target_reads = 0
    while time.monotonic() < deadline:
        error_code = robot.get_error_information()
        if error_code not in (0, None):
            robot.stop()
            raise RuntimeError(f"运动过程中错误码为 {error_code}")
        last = _read_angles(robot, attempts=1, delay=0.0)
        if isinstance(last, list) and len(last) == 6:
            difference = max(abs(float(actual) - expected) for actual, expected in zip(last, target))
            if difference <= 3.0:
                stable = isinstance(previous, list) and max(
                    abs(float(actual) - float(old)) for actual, old in zip(last, previous)
                ) <= 0.25
                stable_target_reads = stable_target_reads + 1 if stable else 0
                if robot.is_moving() == 0 or stable_target_reads >= 3:
                    return last
            else:
                stable_target_reads = 0
            previous = list(last)
        time.sleep(0.3)
    robot.stop()
    raise RuntimeError(f"姿态未在限定时间内到位，已停止: {last}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="固定姿态安全抓取流程")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--above-pose", type=Path, required=True)
    parser.add_argument("--grasp-pose", type=Path, required=True)
    parser.add_argument("--close-value", type=int, default=45)
    parser.add_argument("--speed", type=int, default=3)
    parser.add_argument("--wait", type=float, default=5.0)
    parser.add_argument("--min-margin", type=float, default=10.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 GRASP_SEQUENCE")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "GRASP_SEQUENCE":
        print("安全保护：未执行抓取。确认姿态已验证后加入 --confirm GRASP_SEQUENCE。")
        return 2
    if not 1 <= args.speed <= 5 or not 20 <= args.close_value <= 50:
        parser.error("速度必须为 1-5，夹爪值必须为 20-50；数值越小夹得越紧")
    if not 8.0 <= args.min_margin <= 20.0:
        parser.error("关节安全余量必须为 8-20 度")

    try:
        from pymycobot import MyCobot280
        above = _pose(args.above_pose, args.min_margin)
        grasp = _pose(args.grasp_pose, args.min_margin)
    except (ImportError, OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        LOGGER.error("姿态检查失败: %s", exc)
        return 1

    if max(abs(a - b) for a, b in zip(above, grasp)) > 45:
        LOGGER.error("上方姿态与夹取姿态差异过大，未执行")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        if robot.is_moving() != 0 or robot.get_fresh_mode() != 1:
            raise RuntimeError("机械臂必须停止且 fresh_mode=1")
        if robot.get_error_information() not in (0, None):
            raise RuntimeError("机械臂当前有错误码")
        current = _read_angles(robot)
        if not isinstance(current, list) or len(current) != 6:
            raise RuntimeError(f"读取当前角度失败: {current}")
        if max(abs(float(a) - float(b)) for a, b in zip(current, above)) > 60:
            raise RuntimeError("当前位置到上方姿态变化过大，未执行")

        print(json.dumps({"above_pose": above, "grasp_pose": grasp, "motion_allowed": True}, ensure_ascii=False, indent=2))
        print("请确认目标物体位于夹爪之间、底座固定、工作区无人手，并能立即断电。")
        robot.set_fresh_mode(1)
        robot.set_gripper_state(0, args.speed)
        time.sleep(2.0)
        robot.send_angles(above, args.speed)
        _wait_for_pose(robot, above, max(args.wait, 20.0))
        robot.send_angles(grasp, args.speed)
        _wait_for_pose(robot, grasp, max(args.wait, 20.0))
        robot.set_gripper_value(args.close_value, args.speed)
        time.sleep(3.0)
        gripper_value = robot.get_gripper_value()
        if gripper_value == -1:
            raise RuntimeError("夹紧后无法读取夹爪状态，未执行抬升")
        if robot.get_error_information() not in (0, None):
            raise RuntimeError("夹紧后机械臂出现错误，未执行抬升")

        # Gripper and arm commands share the controller link. Re-arm latest-command
        # mode after the gripper settles so the lift cannot be hidden behind a
        # stale or still-active command.
        robot.stop()
        robot.set_fresh_mode(1)
        time.sleep(0.5)
        lift_speed = max(args.speed, 3)
        print(f"夹爪值: {gripper_value}；开始返回上方姿态，速度 {lift_speed}")
        robot.send_angles(above, lift_speed)
        after = _wait_for_pose(robot, above, max(args.wait, 30.0))
        error_code = robot.get_error_information()
        if error_code not in (0, None):
            robot.stop()
        print(json.dumps({"gripper_value": gripper_value, "after_angles": after, "error": error_code}, ensure_ascii=False, indent=2))
        return 0 if error_code in (0, None) else 1
    except KeyboardInterrupt:
        if robot is not None:
            robot.stop()
        print("\n已发送停止请求，请立即确认机械臂停止。")
        return 130
    except Exception as exc:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        LOGGER.error("抓取流程失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
