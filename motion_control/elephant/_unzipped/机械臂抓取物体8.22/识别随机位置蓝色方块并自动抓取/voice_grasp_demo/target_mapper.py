"""Detect one target and map its image center to calibrated robot XY.

This module is observation-only. It rejects detections outside the calibrated
quadrilateral and never opens a robot serial port.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Optional

from .camera import Camera
from .config import CameraConfig, YoloConfig
from .yolo_detector import YoloDetector


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="YOLO 目标中心到机器人 XY 预览（不执行运动）")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--calibration", type=Path, default=Path("calibration/board_robot_table.json"))
    parser.add_argument("--target", default="bottle", help="YOLO 类别名，例如 bottle、cup")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--confidence", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--max-frames", type=int, default=300)
    args = parser.parse_args(argv)
    if args.samples < 3 or args.max_frames < args.samples:
        parser.error("--samples 至少为 3，且 --max-frames 不能小于 samples")

    import cv2
    import numpy as np

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    matrix = np.asarray(calibration["matrix"], dtype=np.float64)
    polygon = np.asarray(calibration["image_points"], dtype=np.int32)
    target_name = args.target.strip().lower()
    centers: list[tuple[float, float]] = []
    image_size = calibration.get("image_size", [640, 480])
    camera = Camera(CameraConfig(index=args.camera, width=int(image_size[0]), height=int(image_size[1])))
    detector = YoloDetector(YoloConfig(
        model=args.model,
        confidence=args.confidence,
        image_size=args.imgsz,
        device=args.device,
    ))
    try:
        camera.open()
        detector.load()
        print(f"请把 {target_name} 放在标定区域内；按 q/Esc 退出。此模式不控制机械臂或夹爪。")
        for frame_number, frame in enumerate(camera.frames(), start=1):
            cv2.polylines(frame, [polygon], True, (0, 220, 255), 2)
            matches = [item for item in detector.detect(frame) if item.label.lower() == target_name]
            if matches:
                best = max(matches, key=lambda item: item.confidence)
                x1, y1, x2, y2 = best.xyxy
                u = (x1 + x2) / 2.0
                v = (y1 + y2) / 2.0
                inside = cv2.pointPolygonTest(polygon, (u, v), False) >= 0
                color = (0, 200, 0) if inside else (0, 0, 255)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.circle(frame, (round(u), round(v)), 5, color, -1)
                label = f"{best.label} {best.confidence:.2f}"
                if inside:
                    centers.append((u, v))
                    label += f" sample {len(centers)}/{args.samples}"
                else:
                    label += " OUTSIDE CALIBRATION"
                cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            cv2.imshow("target-mapper", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                print("已取消，未生成目标坐标。")
                return 130
            if len(centers) >= args.samples:
                break
            if frame_number >= args.max_frames:
                print(f"未收集到足够的目标样本，仅得到 {len(centers)}/{args.samples}。")
                return 1
    finally:
        camera.close()

    u = statistics.median(point[0] for point in centers)
    v = statistics.median(point[1] for point in centers)
    source = np.asarray([[[u, v]]], dtype=np.float64)
    x, y = cv2.perspectiveTransform(source, matrix).reshape(2).tolist()
    result = {
        "target": target_name,
        "samples": len(centers),
        "pixel_center": [u, v],
        "robot_xy_mm": [x, y],
        "z_mm": calibration.get("z"),
        "inside_calibration": True,
        "motion_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("仅完成坐标预览：未发送机械臂或夹爪命令。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
