"""Camera capture and preview, kept independent from detection."""

from __future__ import annotations

import argparse
import logging
from typing import Iterator, Optional

from .config import CameraConfig

LOGGER = logging.getLogger(__name__)


class Camera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._capture = None

    def open(self) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("未安装 opencv-python") from exc
        capture = cv2.VideoCapture(self.config.index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"无法打开摄像头 index={self.config.index}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        capture.set(cv2.CAP_PROP_FPS, self.config.fps)
        self._capture = capture

    @property
    def is_open(self) -> bool:
        return self._capture is not None and self._capture.isOpened()

    def frames(self) -> Iterator[object]:
        if not self.is_open:
            self.open()
        while self.is_open:
            ok, frame = self._capture.read()
            if not ok:
                LOGGER.warning("摄像头读取失败，停止预览")
                break
            yield frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        try:
            import cv2

            cv2.destroyAllWindows()
        except ImportError:
            pass

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def preview(config: CameraConfig) -> int:
    import cv2

    camera = Camera(config)
    try:
        camera.open()
        print("摄像头预览中，按 q 或 Esc 退出")
        for frame in camera.frames():
            if config.display:
                cv2.imshow("camera", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1
    finally:
        camera.close()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="摄像头独立测试")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args(argv)
    return preview(CameraConfig(args.index, args.width, args.height))


if __name__ == "__main__":
    raise SystemExit(main())

