"""List usable OpenCV camera indices on Windows."""

from __future__ import annotations

import argparse
from typing import Optional


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="枚举摄像头编号")
    parser.add_argument("--max-index", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("需要 opencv-python") from exc

    found = 0
    for index in range(max(0, args.max_index + 1)):
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            if not camera.isOpened():
                continue
            ok, frame = camera.read()
            if ok and frame is not None:
                height, width = frame.shape[:2]
                print(f"camera={index}, resolution={width}x{height}")
                found += 1
        finally:
            camera.release()
    if not found:
        print("未找到可读取的摄像头。请检查 USB 连接、权限和其他占用摄像头的软件。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
