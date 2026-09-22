"""Microphone recording and optional offline speech recognition."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import VoiceConfig

LOGGER = logging.getLogger(__name__)


def record_wav(config: VoiceConfig, output_path: Optional[Path] = None) -> Path:
    """Record from the default microphone and save a PCM WAV file.

    ``sounddevice`` is imported lazily so camera/robot diagnostics do not
    fail on machines without an audio device or PortAudio installation.
    """
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("未安装 sounddevice，无法录音") from exc

    if config.record_seconds <= 0:
        raise ValueError("record_seconds 必须大于 0")
    if config.channels < 1 or config.sample_rate < 8_000:
        raise ValueError("音频参数无效")

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_path or output_dir / (
        datetime.now().strftime("record_%Y%m%d_%H%M%S.wav")
    )
    frames = int(config.record_seconds * config.sample_rate)
    LOGGER.info("开始录音 %.1f 秒，按 Ctrl+C 可中止", config.record_seconds)
    try:
        audio = sd.rec(
            frames,
            samplerate=config.sample_rate,
            channels=config.channels,
            dtype="int16",
        )
        sd.wait()
    except Exception as exc:  # PortAudio errors differ by platform
        raise RuntimeError(f"麦克风录音失败: {exc}") from exc

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(config.channels)
        wav.setsampwidth(2)
        wav.setframerate(config.sample_rate)
        wav.writeframes(audio.tobytes())
    LOGGER.info("录音已保存: %s", path)
    return path


class WhisperRecognizer:
    """Offline Whisper adapter.

    The heavy backend is loaded only when ``recognize`` is called.  Install
    ``faster-whisper`` for a lightweight CPU backend, or use Transformers as
    a fallback (the model is downloaded by Hugging Face on first use).
    """

    def __init__(self, model_name: str = "openai/whisper-tiny", language: Optional[str] = "zh"):
        self.model_name = model_name
        self.language = language
        self._backend = None

    def recognize(self, wav_path: Path) -> str:
        if not wav_path.exists():
            raise FileNotFoundError(wav_path)
        try:
            if importlib.util.find_spec("faster_whisper"):
                return self._recognize_faster_whisper(wav_path)
            if importlib.util.find_spec("transformers"):
                return self._recognize_transformers(wav_path)
        except Exception as exc:
            raise RuntimeError(f"语音识别失败（模型或音频后端）: {exc}") from exc
        raise RuntimeError("未找到语音识别后端。请安装 faster-whisper，或安装 transformers + torch。")

    def _recognize_faster_whisper(self, wav_path: Path) -> str:
        from faster_whisper import WhisperModel

        if self._backend is None:
            # A local model directory avoids a second Hub lookup and works
            # on machines whose network cannot reach the model repository.
            local_model = Path(self.model_name).expanduser()
            if local_model.is_dir():
                required = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
                missing = [name for name in required if not (local_model / name).is_file()]
                if missing:
                    raise RuntimeError(
                        f"本地 Whisper 模型不完整，缺少: {', '.join(missing)}"
                    )
                model_name = str(local_model)
            else:
                # CPU/int8 is the conservative default for a first prototype.
                model_name = self.model_name.rsplit("/", 1)[-1]
                # Accept both faster-whisper repository names and the short
                # model names expected by WhisperModel (for example
                # ``Systran/faster-whisper-base`` -> ``base``).
                for prefix in ("faster-whisper-", "whisper-"):
                    if model_name.startswith(prefix):
                        model_name = model_name.removeprefix(prefix)
                        break
            self._backend = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = self._backend.transcribe(
            str(wav_path), language=self.language, vad_filter=True
        )
        return "".join(segment.text for segment in segments).strip()

    def _recognize_transformers(self, wav_path: Path) -> str:
        from transformers import pipeline

        if self._backend is None:
            self._backend = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=-1,
            )
        result = self._backend(str(wav_path), generate_kwargs={"language": self.language})
        return str(result.get("text", "")).strip()


def record_and_recognize(config: VoiceConfig) -> tuple[Path, str]:
    path = record_wav(config)
    return path, WhisperRecognizer(config.whisper_model, config.language).recognize(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="录音与语音识别独立测试")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path, default=Path("recordings"))
    parser.add_argument("--recognize", action="store_true", help="录音后执行 Whisper 识别")
    parser.add_argument("--model", default="openai/whisper-tiny")
    parser.add_argument("--language", default="zh")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    config = VoiceConfig(
        record_seconds=args.seconds,
        output_dir=args.output_dir,
        whisper_model=args.model,
        language=args.language,
    )
    try:
        path = record_wav(config)
        print(f"录音文件: {path}")
        if args.recognize:
            print(f"识别结果: {WhisperRecognizer(args.model, args.language).recognize(path)}")
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
