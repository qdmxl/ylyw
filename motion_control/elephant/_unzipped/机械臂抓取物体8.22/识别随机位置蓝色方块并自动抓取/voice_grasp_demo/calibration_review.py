"""Overlay saved calibration point numbers on the live camera image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="查看已保存的相机标定点")
    parser.add_argument("--points", type=Path, required=True)
    parser.add_argument("--camera", type=int)
    args = parser.parse_args(argv)

    import cv2
    import numpy as np

    payload = json.loads(args.points.read_text(encoding="utf-8"))
    points = np.asarray(payload["image_points"], dtype=np.int32)
    width, height = map(int, payload.get("image_size", [640, 480]))
    camera_index = payload.get("camera_index", 0) if args.camera is None else args.camera
    capture = cv2.VideoCapture(int(camera_index), cv2.CAP_DSHOW)
    if not capture.isOpened():
        raise RuntimeError(f"无法打开摄像头 {camera_index}")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    print("正在显示已保存标定点及编号；按 q 或 Esc 退出。")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("读取摄像头画面失败")
            cv2.polylines(frame, [points[:4]], True, (0, 220, 255), 2)
            for index, (x, y) in enumerate(points, start=1):
                cv2.circle(frame, (int(x), int(y)), 7, (0, 0, 255), -1)
                cv2.putText(
                    frame,
                    str(index),
                    (int(x) + 10, int(y) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )
            cv2.imshow("calibration-review", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                return 0
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
