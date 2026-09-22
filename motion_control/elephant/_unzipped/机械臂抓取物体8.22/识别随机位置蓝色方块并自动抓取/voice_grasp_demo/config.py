"""Configuration models shared by the demo modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class CameraConfig:
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    display: bool = True


@dataclass(slots=True)
class YoloConfig:
    model: str = "yolo11n.pt"
    confidence: float = 0.45
    iou: float = 0.7
    image_size: int = 416
    max_detections: int = 50
    device: Optional[str] = None
    classes: Optional[list[int]] = None


@dataclass(slots=True)
class SerialConfig:
    port: str = "COM3"
    baudrate: int = 115200
    timeout: float = 0.5
    write_timeout: float = 1.0
    encoding: str = "utf-8"


@dataclass(slots=True)
class VoiceConfig:
    sample_rate: int = 16_000
    channels: int = 1
    record_seconds: float = 5.0
    output_dir: Path = field(default_factory=lambda: Path("recordings"))
    whisper_model: str = "openai/whisper-tiny"
    language: Optional[str] = "zh"
