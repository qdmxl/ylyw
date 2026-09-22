"""Collect image coordinates by clicking calibration marks in a camera view."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="点击桌面标记采集像素坐标")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", type=Path, default=Path("calibration/image_points.json"))
    args = parser.parse_args(argv)
    if args.count < 4:
        parser.error("--count 至少为 4")

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("需要 opencv-python") from exc

    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        raise RuntimeError(f"无法打开摄像头 {args.camera}")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_width = round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    points: list[list[int]] = []
    window = "calibration-click"

    def on_click(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < args.count:
            points.append([int(x), int(y)])

    cv2.namedWindow(window)
    cv2.setMouseCallback(window, on_click)
    print(f"请按顺序点击 {args.count} 个标记中心；按 r 重置，按 q/Esc 取消。")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("读取摄像头画面失败")
            display = frame.copy()
            for index, (x, y) in enumerate(points, start=1):
                cv2.circle(display, (x, y), 6, (0, 0, 255), -1)
                cv2.putText(display, str(index), (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(window, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                print("已取消，未保存像素坐标。")
                return 130
            if key == ord("r"):
                points.clear()
                print("已重置点击点。")
            if len(points) >= args.count:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "image_points": points,
                    "image_size": [actual_width, actual_height],
                    "camera_index": args.camera,
                }
                args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                print(f"像素坐标已保存: {args.output}")
                return 0
    finally:
        capture.release()
        cv2.destroyWindow(window)


if __name__ == "__main__":
    raise SystemExit(main())
