"""Safe top-level workflow: voice -> perception -> confirmation only.

The workflow never calls robot motion or gripper actuation.  It reports a
candidate target and asks the operator to perform any later action manually.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

from .camera import Camera
from .config import CameraConfig, VoiceConfig, YoloConfig
from .voice import WhisperRecognizer, record_wav
from .yolo_detector import YoloDetector

LOGGER = logging.getLogger(__name__)


def run_safe_workflow(
    voice_config: VoiceConfig,
    camera_config: CameraConfig,
    yolo_config: YoloConfig,
    *,
    skip_voice: bool = False,
    max_frames: int = 30,
) -> int:
    """Run the first version of the pipeline without any actuation."""
    if max_frames <= 0:
        raise ValueError("max_frames 必须大于 0")
    if skip_voice:
        text = "（跳过语音）"
    else:
        wav_path = record_wav(voice_config)
        text = WhisperRecognizer(voice_config.whisper_model, voice_config.language).recognize(wav_path)
    print(f"语音指令: {text}")

    camera = Camera(camera_config)
    detector = YoloDetector(yolo_config)
    try:
        camera.open()
        detector.load()
        for index, frame in enumerate(camera.frames()):
            detections = detector.detect(frame)
            if detections:
                best = max(detections, key=lambda item: item.confidence)
                print(
                    f"候选目标: {best.label}, 置信度={best.confidence:.2f}, "
                    f"框={best.xyxy}（仅观察，不执行抓取）"
                )
            if index + 1 >= max_frames:
                break
    finally:
        camera.close()
    print("流程结束：未发送机械臂或夹爪控制命令。")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="安全主流程：语音+摄像头+YOLO，仅观察")
    parser.add_argument("--skip-voice", action="store_true")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--voice-model", default="openai/whisper-tiny")
    parser.add_argument("--imgsz", type=int, default=416, help="YOLO 推理尺寸；CPU 较慢时使用 320")
    parser.add_argument("--device", default=None, help="YOLO 设备，例如 cpu、0；默认自动选择")
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path, default=Path("recordings"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return run_safe_workflow(
            VoiceConfig(
                record_seconds=args.seconds,
                output_dir=args.output_dir,
                whisper_model=args.voice_model,
            ),
            CameraConfig(index=args.camera),
            YoloConfig(model=args.model, image_size=args.imgsz, device=args.device),
            skip_voice=args.skip_voice,
            max_frames=args.max_frames,
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
