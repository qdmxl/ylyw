"""Search alternative IK branches without sending motion commands."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)

LIMITS = [
    (-168.0, 168.0),
    (-140.0, 140.0),
    (-150.0, 150.0),
    (-150.0, 150.0),
    (-155.0, 160.0),
    (-180.0, 180.0),
]


def _valid_solution(solution: object) -> bool:
    return (
        isinstance(solution, list)
        and len(solution) == 6
        and all(
            isinstance(value, (int, float)) and low <= float(value) <= high
            for value, (low, high) in zip(solution, LIMITS)
        )
    )


def _margin(solution: list[float]) -> float:
    return min(
        min(float(value) - low, high - float(value))
        for value, (low, high) in zip(solution, LIMITS)
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MyCobot 备用逆解搜索（不运动）")
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    parser.add_argument("--z", type=float, required=True)
    parser.add_argument("--rx", type=float, required=True)
    parser.add_argument("--ry", type=float, required=True)
    parser.add_argument("--rz", type=float, required=True)
    parser.add_argument("--min-margin", type=float, default=10.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        from pymycobot import MyCobot280
    except ImportError:
        LOGGER.error("未安装 pymycobot")
        return 1

    robot = None
    try:
        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        current = robot.get_angles()
        error_code = robot.get_error_information()
        if not isinstance(current, list) or len(current) != 6 or any(value == -1 for value in current):
            raise RuntimeError(f"读取当前角度失败: {current}")
        if error_code not in (0, None):
            raise RuntimeError(f"机械臂当前错误码为 {error_code}，未搜索")

        target = [args.x, args.y, args.z, args.rx, args.ry, args.rz]
        seeds = [list(map(float, current))]
        for joint5 in (-120.0, -60.0, 0.0, 60.0, 120.0):
            for joint6 in (-120.0, -60.0, 0.0, 60.0, 120.0):
                seed = list(map(float, current))
                seed[4] = joint5
                seed[5] = joint6
                seeds.append(seed)
        seeds.extend(
            [
                [current[0], 0.0, 90.0, 0.0, -90.0, -90.0],
                [current[0], 20.0, 120.0, -40.0, -90.0, -90.0],
                [current[0], -20.0, 90.0, 40.0, 0.0, 0.0],
                [0.0, 0.0, 90.0, 0.0, 0.0, 0.0],
            ]
        )

        candidates: dict[tuple[float, ...], dict[str, object]] = {}
        for seed in seeds:
            solution = robot.solve_inv_kinematics(target, seed)
            if not _valid_solution(solution):
                continue
            rounded = tuple(round(float(value), 2) for value in solution)
            candidates[rounded] = {
                "angles": list(rounded),
                "limit_margin_deg": round(_margin(list(rounded)), 2),
            }

        ranked = sorted(candidates.values(), key=lambda item: float(item["limit_margin_deg"]), reverse=True)
        safe = [item for item in ranked if float(item["limit_margin_deg"]) >= args.min_margin]
        result = {
            "target_coords": target,
            "current_angles": current,
            "solutions_found": len(ranked),
            "safe_solutions_found": len(safe),
            "min_margin_deg": args.min_margin,
            "best_candidates": ranked[:5],
            "motion_allowed": False,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("仅搜索备用逆解：未发送运动、夹爪或 IO 命令。")
        return 0 if safe else 1
    except Exception as exc:
        LOGGER.error("备用逆解搜索失败: %s", exc)
        return 1
    finally:
        if robot is not None:
            robot.close()


if __name__ == "__main__":
    raise SystemExit(main())
