"""Gripper test harness with a simulation-first safety model."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from .config import SerialConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GripperState:
    position: float = 0.0
    enabled: bool = False


class Gripper:
    """Minimal gripper abstraction.

    ``simulate=True`` is the default.  Hardware writes are deliberately not
    implemented until a vendor protocol is supplied and explicitly enabled.
    """

    def __init__(self, config: Optional[SerialConfig] = None, simulate: bool = True):
        self.config = config or SerialConfig()
        self.simulate = simulate
        self.state = GripperState()
        self._serial = None

    def connect(self) -> None:
        if self.simulate:
            self.state.enabled = True
            LOGGER.info("夹爪模拟器已连接")
            return
        raise RuntimeError(
            "夹爪硬件写入尚未绑定厂商协议。请先实现 Gripper._send_vendor_command，"
            "并在代码审查后显式启用。"
        )

    def open(self) -> GripperState:
        return self._set_position(0.0)

    def close(self) -> GripperState:
        return self._set_position(1.0)

    def stop(self) -> GripperState:
        LOGGER.info("夹爪停止（模拟）")
        return self.state

    def _set_position(self, position: float) -> GripperState:
        if not self.state.enabled:
            raise RuntimeError("夹爪未连接")
        if not self.simulate:
            raise RuntimeError("拒绝发送未知夹爪控制帧")
        self.state.position = position
        LOGGER.info("夹爪位置=%.1f（模拟）", position)
        return self.state

    def close_connection(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
        self.state.enabled = False

    def __enter__(self) -> "Gripper":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close_connection()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="夹爪开合独立测试（默认模拟）")
    parser.add_argument("action", choices=("open", "close", "stop"))
    parser.add_argument("--hardware", action="store_true", help="显式请求硬件模式；当前仍会拒绝未知协议")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        with Gripper(simulate=not args.hardware) as gripper:
            state = getattr(gripper, args.action)()
            print(f"position={state.position:.1f}, enabled={state.enabled}")
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

