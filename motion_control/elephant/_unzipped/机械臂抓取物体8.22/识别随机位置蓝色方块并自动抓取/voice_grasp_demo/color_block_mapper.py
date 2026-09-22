"""Locate a colored block and map its center to robot XY without actuation."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Optional

from .camera import Camera
from .config import CameraConfig


HSV_RANGES = {
    "red": [((0, 90, 70), (10, 255, 255)), ((170, 90, 70), (179, 255, 255))],
    "orange": [((8, 90, 70), (24, 255, 255))],
    "yellow": [((20, 80, 70), (38, 255, 255))],
    "green": [((38, 55, 45), (90, 255, 255))],
    "blue": [((90, 70, 45), (135, 255, 255))],
    "purple": [((130, 55, 45), (170, 255, 255))],
}


def _mask_for_color(hsv, color: str, cv2, np):
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for low, high in HSV_RANGES[color]:
        mask = cv2.bitwise_or(
            mask,
            cv2.inRange(hsv, np.asarray(low, dtype=np.uint8), np.asarray(high, dtype=np.uint8)),
        )
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _best_square(mask, min_area: float, max_area: float, cv2):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not min_area <= area <= max_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if width == 0 or height == 0:
            continue
        aspect = width / height
        extent = area / (width * height)
        if 0.55 <= aspect <= 1.8 and extent >= 0.5:
            candidates.append((area, x, y, width, height, contour))
    return max(candidates, default=None, key=lambda item: item[0])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="彩色方块中心到机械臂 XY 预览（不执行运动）")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--color", choices=sorted(HSV_RANGES), required=True)
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--min-area", type=float, default=300.0)
    parser.add_argument("--max-area", type=float, default=50000.0)
    parser.add_argument("--max-frames", type=int, default=450)
    args = parser.parse_args(argv)
    if args.samples < 5 or args.max_frames < args.samples:
        parser.error("--samples 至少为 5，且 --max-frames 不能小于 samples")
    if args.min_area <= 0 or args.max_area <= args.min_area:
        parser.error("面积范围无效")

    import cv2
    import numpy as np

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    matrix = np.asarray(calibration["matrix"], dtype=np.float64)
    polygon = np.asarray(calibration["image_points"], dtype=np.int32)
    image_size = calibration.get("image_size", [640, 480])
    width, height = int(image_size[0]), int(image_size[1])
    camera = Camera(CameraConfig(index=args.camera, width=width, height=height))
    samples: list[tuple[float, float, float]] = []

    try:
        camera.open()
        print(
            f"请把 {args.color} 方块单独放入标定区域；黄色线是有效区域。"
            "按 q/Esc 取消。此模式不控制机械臂或夹爪。"
        )
        for frame_number, frame in enumerate(camera.frames(), start=1):
            if frame.shape[1] != width or frame.shape[0] != height:
                raise RuntimeError(
                    f"摄像头实际分辨率 {frame.shape[1]}x{frame.shape[0]} 与标定分辨率 "
                    f"{width}x{height} 不一致"
                )
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = _mask_for_color(hsv, args.color, cv2, np)
            best = _best_square(mask, args.min_area, args.max_area, cv2)
            cv2.polylines(frame, [polygon], True, (0, 220, 255), 2)
            if best is not None:
                area, x, y, box_width, box_height, _contour = best
                u = x + box_width / 2.0
                v = y + box_height / 2.0
                inside = cv2.pointPolygonTest(polygon, (u, v), False) >= 0
                draw_color = (0, 200, 0) if inside else (0, 0, 255)
                cv2.rectangle(frame, (x, y), (x + box_width, y + box_height), draw_color, 2)
                cv2.circle(frame, (round(u), round(v)), 5, draw_color, -1)
                label = f"{args.color} block area={area:.0f}"
                if inside:
                    samples.append((u, v, area))
                    label += f" sample {len(samples)}/{args.samples}"
                else:
                    label += " OUTSIDE CALIBRATION"
                cv2.putText(
                    frame,
                    label,
                    (x, max(20, y - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.52,
                    draw_color,
                    2,
                )
            cv2.imshow("color-block-mapper", frame)
            cv2.imshow("color-mask", mask)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                print("已取消，未生成目标坐标。")
                return 130
            if len(samples) >= args.samples:
                break
            if frame_number >= args.max_frames:
                print(f"样本不足，仅得到 {len(samples)}/{args.samples}。")
                return 1
    finally:
        camera.close()

    u = statistics.median(item[0] for item in samples)
    v = statistics.median(item[1] for item in samples)
    area = statistics.median(item[2] for item in samples)
    source = np.asarray([[[u, v]]], dtype=np.float64)
    x, y = cv2.perspectiveTransform(source, matrix).reshape(2).tolist()
    result = {
        "target": f"{args.color}_block",
        "samples": len(samples),
        "pixel_center": [u, v],
        "median_area_px": area,
        "robot_xy_mm": [x, y],
        "z_mm": calibration.get("z"),
        "inside_calibration": True,
        "motion_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("仅完成彩色方块坐标预览：未发送机械臂或夹爪命令。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
