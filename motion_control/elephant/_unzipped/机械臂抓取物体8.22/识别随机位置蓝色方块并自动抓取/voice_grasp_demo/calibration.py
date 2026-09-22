"""Planar camera-to-robot calibration using four or more correspondence points."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


def _load_points(path: Path):
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("标定需要 numpy") from exc
    payload = json.loads(path.read_text(encoding="utf-8"))
    image_points = np.asarray(payload["image_points"], dtype=np.float64)
    robot_points = np.asarray(payload["robot_points"], dtype=np.float64)
    if image_points.shape != robot_points.shape or image_points.ndim != 2 or image_points.shape[1] != 2:
        raise ValueError("image_points 和 robot_points 必须都是 N x 2")
    if len(image_points) < 4:
        raise ValueError("至少需要 4 组对应点")
    z_value = payload.get("z")
    z = None if z_value is None else float(z_value)
    return payload, image_points, robot_points, z


def fit(input_path: Path, output_path: Path) -> int:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("标定需要 opencv-python 和 numpy") from exc
    payload, image_points, robot_points, z = _load_points(input_path)
    matrix, mask = cv2.findHomography(image_points, robot_points, method=0)
    if matrix is None:
        raise RuntimeError("无法计算单应矩阵，请检查标记点是否共线或重复")
    projected = cv2.perspectiveTransform(image_points.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    errors = np.linalg.norm(projected - robot_points, axis=1)
    result = {
        "type": "planar_homography",
        "source": str(input_path),
        "image_points": image_points.tolist(),
        "robot_points": robot_points.tolist(),
        "image_size": payload.get("image_size", [640, 480]),
        "camera_index": payload.get("camera_index"),
        "z": z,
        "motion_allowed": False,
        "status": payload.get("status", "calibration_only"),
        "matrix": matrix.tolist(),
        "reprojection_error_mm": {
            "max": float(errors.max()),
            "mean": float(errors.mean()),
            "per_point": errors.tolist(),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"标定文件已保存: {output_path}")
    return 0


def map_point(calibration_path: Path, u: float, v: float) -> int:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("映射需要 opencv-python 和 numpy") from exc
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    matrix = np.asarray(payload["matrix"], dtype=np.float64)
    point = np.asarray([[[u, v]]], dtype=np.float64)
    mapped = cv2.perspectiveTransform(point, matrix).reshape(2)
    print(json.dumps({
        "pixel": [u, v],
        "robot_xy_mm": mapped.tolist(),
        "z_mm": payload.get("z"),
        "motion_allowed": False,
    }, ensure_ascii=False))
    return 0


def pair_points(image_path: Path, robot_path: Path, output_path: Path) -> int:
    image_payload = json.loads(image_path.read_text(encoding="utf-8"))
    robot_payload = json.loads(robot_path.read_text(encoding="utf-8"))
    image_points = image_payload.get("image_points")
    saved_points = robot_payload.get("points")
    if not isinstance(image_points, list) or not isinstance(saved_points, list):
        raise ValueError("输入文件缺少 image_points 或 points")
    if len(image_points) != len(saved_points) or len(image_points) < 4:
        raise ValueError(
            f"像素点与机器人点数量必须相同且至少为 4："
            f"{len(image_points)} != {len(saved_points)}"
        )
    robot_points = []
    for index, item in enumerate(saved_points, start=1):
        coords = item.get("coords") if isinstance(item, dict) else None
        if not isinstance(coords, list) or len(coords) != 6:
            raise ValueError(f"机器人点 {index} 缺少 6 个 coords")
        robot_points.append([float(coords[0]), float(coords[1])])
    result = {
        "image_points": image_points,
        "robot_points": robot_points,
        "image_size": image_payload.get("image_size", [640, 480]),
        "camera_index": image_payload.get("camera_index"),
        "z": None,
        "status": "xy_calibration_z_unset_do_not_move_robot",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"对应点文件已保存: {output_path}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="桌面平面像素到机器人坐标标定")
    sub = parser.add_subparsers(dest="action", required=True)
    pair_parser = sub.add_parser("pair", help="合并像素点和机器人点文件")
    pair_parser.add_argument("--image-points", type=Path, required=True)
    pair_parser.add_argument("--robot-points", type=Path, required=True)
    pair_parser.add_argument("--output", type=Path, required=True)
    fit_parser = sub.add_parser("fit", help="根据对应点计算单应矩阵")
    fit_parser.add_argument("--input", type=Path, required=True)
    fit_parser.add_argument("--output", type=Path, default=Path("calibration/table.json"))
    map_parser = sub.add_parser("map", help="将像素点映射为机器人坐标")
    map_parser.add_argument("--calibration", type=Path, required=True)
    map_parser.add_argument("--u", type=float, required=True)
    map_parser.add_argument("--v", type=float, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.action == "pair":
            return pair_points(args.image_points, args.robot_points, args.output)
        if args.action == "fit":
            return fit(args.input, args.output)
        return map_point(args.calibration, args.u, args.v)
    except (OSError, KeyError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
