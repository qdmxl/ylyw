"""Voice-to-intent dry run, with an optional explicit gripper confirmation."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Optional

from .command_parser import parse_command
from .config import VoiceConfig
from .voice import WhisperRecognizer, record_wav

LOGGER = logging.getLogger(__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="语音指令联动测试（默认不执行硬件）")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--voice-model", default="base")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--output-dir", type=Path, default=Path("recordings"))
    parser.add_argument("--port", default="COM10")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--speed", type=int, default=10)
    parser.add_argument("--close-value", type=int, default=70)
    parser.add_argument("--above-pose", type=Path, default=Path("poses/above_safe.json"))
    parser.add_argument("--grasp-pose", type=Path, default=Path("poses/grasp_safe.json"))
    parser.add_argument("--min-margin", type=float, default=10.0)
    parser.add_argument("--execute", action="store_true", help="允许在二次确认后执行夹爪动作")
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="在已明确使用 --execute 的前提下跳过交互式 EXECUTE 输入；仍会执行现场安全检查提示",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not 1 <= args.speed <= 20:
        parser.error("--speed 必须在 1 到 20 之间")
    if not 0 <= args.close_value <= 100:
        parser.error("--close-value 必须在 0 到 100 之间")
    if not 8.0 <= args.min_margin <= 20.0:
        parser.error("--min-margin 必须在 8 到 20 度之间")

    try:
        voice_config = VoiceConfig(
            record_seconds=args.seconds,
            output_dir=args.output_dir,
            whisper_model=args.voice_model,
            language=args.language,
        )
        wav_path = record_wav(voice_config)
        raw_text = WhisperRecognizer(args.voice_model, args.language).recognize(wav_path)
        command = parse_command(raw_text)
        print(f"识别文本: {command.raw}")
        print(f"规范文本: {command.normalized}")
        print(f"指令意图: {command.intent}")

        if not args.execute:
            print("预览模式：未执行机械臂或夹爪命令。")
            return 0
        if command.intent not in ("gripper_open", "gripper_close", "grasp"):
            print("该指令不是允许的夹爪动作，已拒绝执行。")
            return 2
        if args.auto_confirm:
            print("已使用 --auto-confirm，跳过交互式 EXECUTE 输入。")
        else:
            typed = input("确认现场安全后输入 EXECUTE 才执行：").strip()
            if typed != "EXECUTE":
                print("未获得明确确认，未执行硬件命令。")
                return 2

        if command.intent == "grasp":
            if not args.above_pose.exists() or not args.grasp_pose.exists():
                print(f"缺少已验证姿态文件: {args.above_pose}, {args.grasp_pose}")
                return 2
            from .grasp_sequence import main as grasp_main

            return grasp_main(
                [
                    "--port",
                    args.port,
                    "--baudrate",
                    str(args.baudrate),
                    "--above-pose",
                    str(args.above_pose),
                    "--grasp-pose",
                    str(args.grasp_pose),
                    "--close-value",
                    str(args.close_value),
                    "--speed",
                    str(min(args.speed, 5)),
                    "--min-margin",
                    str(args.min_margin),
                    "--confirm",
                    "GRASP_SEQUENCE",
                ]
            )

        from pymycobot import MyCobot280

        robot = MyCobot280(args.port, args.baudrate, timeout=2)
        try:
            print(f"动作前夹爪值: {robot.get_gripper_value()}")
            if command.intent == "gripper_open":
                robot.set_gripper_state(0, args.speed)
            else:
                robot.set_gripper_value(args.close_value, args.speed)
            time.sleep(2.0)
            print(f"动作后夹爪值: {robot.get_gripper_value()}")
            print("夹爪命令已发送。")
        finally:
            robot.close()
        return 0
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        print("\n已停止语音指令测试，未继续执行。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
