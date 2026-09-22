"""Speech-command normalization and intent parsing without hardware writes."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    raw: str
    normalized: str
    intent: str
    actuation_allowed: bool = False


def normalize_text(text: str) -> str:
    value = re.sub(r"[，。！？、,.!?\s]+", "", text.strip())
    for source, target in (
        ("打開", "打开"),
        ("關閉", "关闭"),
        ("夾爪", "夹爪"),
        ("鬆開", "松开"),
        ("加爪", "夹爪"),
        ("加转", "夹爪"),
        ("加抓", "夹爪"),
        ("夹抓", "夹爪"),
        ("抓手", "夹爪"),
        ("夹子", "夹爪"),
    ):
        value = value.replace(source, target)
    # Whisper can repeat a short command when the recording contains trailing
    # silence. Collapse exactly repeated halves but leave other text intact.
    if len(value) % 2 == 0:
        half = len(value) // 2
        if value[:half] == value[half:]:
            value = value[:half]
    return value


def parse_command(text: str) -> ParsedCommand:
    normalized = normalize_text(text)
    if ("打开" in normalized or "松开" in normalized) and "夹爪" in normalized:
        intent = "gripper_open"
    elif ("关闭" in normalized or "闭合" in normalized or "夹住" in normalized) and "夹爪" in normalized:
        intent = "gripper_close"
    elif any(word in normalized for word in ("抓取", "夹取", "拿起", "捡起")):
        intent = "grasp"
    elif "停止" in normalized or "急停" in normalized:
        intent = "stop"
    else:
        intent = "unknown"
    return ParsedCommand(text, normalized, intent)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="语音指令解析测试（不控制硬件）")
    parser.add_argument("--text", required=True, help="待解析的识别文本")
    args = parser.parse_args(argv)
    print(json.dumps(asdict(parse_command(args.text)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
