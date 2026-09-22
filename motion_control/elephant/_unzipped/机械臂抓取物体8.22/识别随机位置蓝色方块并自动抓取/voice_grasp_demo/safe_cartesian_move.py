"""Move to a Cartesian target through small, checked joint-space increments."""

from __future__ import annotations

import argparse
import logging
import math
import time
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)
LIMITS = [(-168, 168), (-140, 140), (-150, 150), (-150, 150), (-155, 160), (-180, 180)]


def _read(robot: Any, name: str, attempts: int = 5, delay: float = 0.3) -> Any:
    method = getattr(robot, name)
    last = None
    for attempt in range(attempts):
        last = method()
        if isinstance(last, list) and len(last) == 6 and all(value != -1 for value in last):
            return last
        if attempt + 1 < attempts:
            time.sleep(delay)
    return last


def _wait_stopped(robot: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        moving = robot.is_moving()
        if moving == 0:
            return
        if moving == -1:
            break
        time.sleep(0.2)
    robot.stop()
    raise RuntimeError("分段运动未及时停止，已发送停止请求")


def _valid_solution(solution: Any) -> bool:
    return isinstance(solution, list) and len(solution) == 6 and all(
        isinstance(value, (int, float)) and low <= float(value) <= high
        for value, (low, high) in zip(solution, LIMITS)
    )


def _next_target(current: list[float], target: list[float], step_mm: float, step_deg: float) -> list[float]:
    result = list(current)
    for index in range(3):
        delta = target[index] - current[index]
        if abs(delta) <= step_mm:
            result[index] = target[index]
        else:
            result[index] += math.copysign(step_mm, delta)
    for index in range(3, 6):
        delta = target[index] - current[index]
        if abs(delta) <= step_deg:
            result[index] = target[index]
        else:
            result[index] += math.copysign(step_deg, delta)
    return result


def _distance(current: list[float], target: list[float]) -> float:
    return math.sqrt(sum((float(current[index]) - float(target[index])) ** 2 for index in range(3)))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 分段安全移动到笛卡尔目标")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--z", type=float, required=True)
    parser.add_argument("--rx", type=float, required=True)
    parser.add_argument("--ry", type=float, required=True)
    parser.add_argument("--rz", type=float, required=True)
    parser.add_argument("--clearance-z", type=float, default=210.0)
    parser.add_argument("--step-mm", type=float, default=3.0)
    parser.add_argument("--step-deg", type=float, default=5.0)
    parser.add_argument("--speed", type=int, default=3)
    parser.add_argument("--max-joint-change", type=float, default=8.0)
    parser.add_argument("--confirm", default="", help="必须精确填写 CART_MOVE")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.confirm != "CART_MOVE":
        print("安全保护：未执行分段移动。确认路径无障碍后加入 --confirm CART_MOVE。")
        return 2
    if not 180 <= args.clearance_z <= 300 or args.z > args.clearance_z:
        parser.error("要求 180 <= clearance-z <= 300，且目标 z 不得高于 clearance-z")
    if not 1 <= args.step_mm <= 5 or not 1 <= args.step_deg <= 10:
        parser.error("步长必须为 1-5 mm、1-10 度")
    if not 1 <= args.speed <= 5 or not 1 <= args.max_joint_change <= 10:
        parser.error("速度和单步关节变化必须在 1-5、1-10 范围内")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        if robot.is_moving() != 0 or robot.get_fresh_mode() != 1:
            raise RuntimeError("机械臂必须停止且 fresh_mode=1")
        if robot.get_error_information() not in (0, None):
            raise RuntimeError("机械臂当前存在错误码")
        coords = _read(robot, "get_coords")
        angles = _read(robot, "get_angles")
        if not isinstance(coords, list) or not isinstance(angles, list):
            raise RuntimeError(f"读取当前状态失败: coords={coords}, angles={angles}")

        target = [args.x, args.y, args.z, args.rx, args.ry, args.rz]
        clearance = [coords[0], coords[1], args.clearance_z, coords[3], coords[4], coords[5]]
        waypoints = [clearance, [args.x, args.y, args.clearance_z, coords[3], coords[4], coords[5]], target]
        print(f"当前 coords: {coords}")
        print(f"分段目标: {waypoints}")
        print("将先抬高，再水平移动，最后调整末端姿态；不会控制夹爪。")

        for waypoint_index, waypoint in enumerate(waypoints, start=1):
            while _distance(coords, waypoint) > args.step_mm or any(
                abs(float(coords[index]) - float(waypoint[index])) > args.step_deg for index in range(3, 6)
            ):
                next_coords = _next_target(coords, waypoint, args.step_mm, args.step_deg)
                solution = robot.solve_inv_kinematics(next_coords, angles)
                if not _valid_solution(solution):
                    raise RuntimeError(f"第 {waypoint_index} 段没有有效逆解，已停止: {solution}")
                changes = [float(new) - float(old) for new, old in zip(solution, angles)]
                if max(abs(change) for change in changes) > args.max_joint_change:
                    raise RuntimeError(f"第 {waypoint_index} 段单步关节变化过大，已停止: {changes}")
                robot.send_angles(solution, args.speed)
                _wait_stopped(robot)
                new_coords = _read(robot, "get_coords")
                new_angles = _read(robot, "get_angles")
                error_code = robot.get_error_information()
                if error_code not in (0, None) or not isinstance(new_coords, list) or not isinstance(new_angles, list):
                    robot.stop()
                    raise RuntimeError(f"第 {waypoint_index} 段动作后状态异常: error={error_code}, coords={new_coords}")
                if _distance(new_coords, coords) < 0.2:
                    raise RuntimeError("实际坐标没有有效变化，已停止")
                coords, angles = new_coords, new_angles
                print(f"段 {waypoint_index}: coords={coords}")

        print(f"分段移动完成: {coords}")
        return 0
    except KeyboardInterrupt:
        if robot is not None:
            robot.stop()
        print("\n已发送停止请求，请确认机械臂停止。")
        return 130
    except Exception as exc:
        if robot is not None:
            try:
                robot.stop()
            except Exception:
                pass
        LOGGER.error("分段移动失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
