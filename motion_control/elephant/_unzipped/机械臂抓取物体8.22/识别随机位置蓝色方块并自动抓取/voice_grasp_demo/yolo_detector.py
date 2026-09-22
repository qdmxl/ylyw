"""YOLO inference adapter.  It only observes frames and never controls a robot."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .camera import Camera
from .config import CameraConfig, YoloConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class Detection:
    label: str
    confidence: float
    xyxy: tuple[int, int, int, int]


class YoloDetector:
    def __init__(self, config: YoloConfig):
        self.config = config
        self._model = None

    def load(self) -> None:
        model_path = Path(self.config.model).expanduser()
        if model_path.suffix.lower() == ".pt" and (model_path.parent != Path(".") or model_path.name != self.config.model):
            if not model_path.is_file():
                raise RuntimeError(
                    f"YOLO 模型文件不存在: {model_path}。请提供正确路径，"
                    "或先训练包含目标类别的自定义模型。"
                )
        elif self.config.model.endswith(".pt") and not model_path.is_file() and "/" not in self.config.model and "\\" not in self.config.model:
            # A bare custom filename such as headphones.pt should not be
            # mistaken for a downloadable Ultralytics model.
            if self.config.model not in {"yolo11n.pt", "yolo11s.pt", "yolo11m.pt", "yolo11l.pt", "yolo11x.pt"}:
                raise RuntimeError(
                    f"YOLO 模型文件不存在: {self.config.model}。请先准备自定义模型文件。"
                )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("未安装 ultralytics") from exc
        try:
            self._model = YOLO(self.config.model)
        except Exception as exc:
            raise RuntimeError(f"加载 YOLO 模型失败: {exc}") from exc

    def detect(self, frame: object) -> list[Detection]:
        if self._model is None:
            self.load()
        kwargs = {
            "conf": self.config.confidence,
            "iou": self.config.iou,
            "imgsz": self.config.image_size,
            "max_det": self.config.max_detections,
            "verbose": False,
        }
        if self.config.device:
            kwargs["device"] = self.config.device
        if self.config.classes is not None:
            kwargs["classes"] = self.config.classes
        try:
            results = self._model.predict(frame, **kwargs)
        except Exception as exc:
            raise RuntimeError(f"YOLO 推理失败: {exc}") from exc
        detections: list[Detection] = []
        names = self._model.names
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls.item())
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                detections.append(Detection(str(names[cls_id]), confidence, (x1, y1, x2, y2)))
        return detections


def preview_with_detection(camera_config: CameraConfig, yolo_config: YoloConfig) -> int:
    import cv2

    camera = Camera(camera_config)
    detector = YoloDetector(yolo_config)
    try:
        camera.open()
        detector.load()
        print("YOLO 预览中，按 q 或 Esc 退出；此模式不会发送机械臂/夹爪命令")
        for frame_index, frame in enumerate(camera.frames()):
            if frame_index == 0:
                preview = frame.copy()
                cv2.putText(
                    preview,
                    "YOLO warming up...",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 220, 255),
                    2,
                )
                cv2.imshow("yolo", preview)
                cv2.waitKey(1)
            started = time.perf_counter()
            detections = detector.detect(frame)
            elapsed_ms = (time.perf_counter() - started) * 1000
            for detection in detections:
                x1, y1, x2, y2 = detection.xyxy
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
                cv2.putText(
                    frame,
                    f"{detection.label} {detection.confidence:.2f}",
                    (x1, max(y1 - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 200, 0),
                    2,
                )
            cv2.putText(
                frame,
                f"inference {elapsed_ms:.0f} ms",
                (20, 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 220, 255),
                2,
            )
            cv2.imshow("yolo", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        print("\n已通过 Ctrl+C 停止 YOLO 预览。")
        return 130
    finally:
        camera.close()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="YOLO 独立测试")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--confidence", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=416, help="推理尺寸；CPU 较慢时使用 320")
    parser.add_argument("--device", default=None, help="例如 cpu、0；默认自动选择")
    args = parser.parse_args(argv)
    return preview_with_detection(
        CameraConfig(index=args.camera),
        YoloConfig(
            model=args.model,
            confidence=args.confidence,
            image_size=args.imgsz,
            device=args.device,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
