"""Read-only communication for a robot controller.

The generic backend only consumes unsolicited text lines.  The MyCobot 280-M5
backend uses the vendor SDK's query methods (which send read-request frames)
and never calls motion, gripper, or IO write methods.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .config import SerialConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RobotStatus:
    timestamp: float
    raw: str
    connected: bool = True


@dataclass(slots=True, frozen=True)
class MyCobotStatus:
    timestamp: float
    angles: Any
    coords: Any
    error: Any
    connected: bool = True


class ReadOnlyRobot:
    """Serial monitor that opens the port and only consumes incoming bytes."""

    def __init__(self, config: SerialConfig):
        self.config = config
        self._serial = None

    def connect(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("未安装 pyserial") from exc
        try:
            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=0,
            )
        except Exception as exc:
            raise RuntimeError(f"打开机械臂串口失败: {exc}") from exc
        LOGGER.info("已连接机械臂串口 %s（只读）", self.config.port)

    def read_status(self) -> Optional[RobotStatus]:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("机械臂未连接")
        raw = self._serial.readline()
        if not raw:
            return None
        text = raw.decode(self.config.encoding, errors="replace").strip()
        return RobotStatus(time.time(), text)

    def monitor(self, seconds: float = 10.0) -> list[RobotStatus]:
        if seconds <= 0:
            raise ValueError("seconds 必须大于 0")
        end = time.monotonic() + seconds
        statuses: list[RobotStatus] = []
        while time.monotonic() < end:
            status = self.read_status()
            if status:
                statuses.append(status)
                print(json.dumps(asdict(status), ensure_ascii=False))
        return statuses

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def __enter__(self) -> "ReadOnlyRobot":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class MyCobot280ReadOnly:
    """MyCobot 280-M5 status reader using query-only SDK methods.

    The SDK writes request frames for methods such as ``get_angles``. These
    requests query state and do not command motion. No mutating SDK method is
    exposed by this wrapper.
    """

    def __init__(self, config: SerialConfig, model: str = "280-arduino"):
        self.config = config
        self.model = model
        self._robot = None

    def connect(self) -> None:
        try:
            from pymycobot import MyCobot280
        except ImportError as exc:
            raise RuntimeError("未安装 pymycobot，请执行: python -m pip install pymycobot") from exc
        try:
            self._robot = MyCobot280(
                self.config.port,
                self.config.baudrate,
                timeout=self.config.timeout,
            )
            # pymycobot does not expose write_timeout in its constructor.
            # Bound the SDK's query-frame write so a driver/USB fault cannot
            # leave this diagnostic process blocked indefinitely.
            self._robot._serial_port.write_timeout = self.config.write_timeout
        except Exception as exc:
            raise RuntimeError(f"打开 MyCobot 280-M5 串口失败: {exc}") from exc
        LOGGER.info(
            "已连接 MyCobot %s %s（只查询，不执行运动/夹爪/IO命令）",
            self.model,
            self.config.port,
        )

    def read_status(self) -> MyCobotStatus:
        if self._robot is None:
            raise RuntimeError("MyCobot 280-M5 未连接")
        try:
            angles = self._robot.get_angles()
            coords = self._robot.get_coords()
            error = self._robot.get_error_information()
        except Exception as exc:
            raise RuntimeError(f"读取 MyCobot 状态失败: {exc}") from exc
        responded = not (angles == -1 and coords == -1 and error == -1)
        return MyCobotStatus(time.time(), angles, coords, error, connected=responded)

    def monitor(self, seconds: float = 10.0, interval: float = 1.0) -> list[MyCobotStatus]:
        if seconds <= 0 or interval <= 0:
            raise ValueError("seconds 和 interval 必须大于 0")
        end = time.monotonic() + seconds
        statuses: list[MyCobotStatus] = []
        while time.monotonic() < end:
            status = self.read_status()
            statuses.append(status)
            print(json.dumps(asdict(status), ensure_ascii=False))
            time.sleep(interval)
        return statuses

    def close(self) -> None:
        if self._robot is not None:
            try:
                self._robot.close()
            finally:
                self._robot = None

    def __enter__(self) -> "MyCobot280ReadOnly":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="机械臂串口只读测试")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--model", choices=("280-arduino", "280-m5"), default="280-arduino")
    parser.add_argument("--baudrate", type=int, default=None, help="省略时按型号选择")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--write-timeout", type=float, default=1.0)
    parser.add_argument(
        "--backend",
        choices=("mycobot280", "passive"),
        default="mycobot280",
        help="280 Arduino/M5 使用 mycobot280；其他设备可用 passive 被动监听",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    baudrate = args.baudrate
    if baudrate is None:
        baudrate = 1_000_000 if args.model == "280-arduino" else 115_200
    config = SerialConfig(args.port, baudrate, write_timeout=args.write_timeout)
    robot = (
        MyCobot280ReadOnly(config, model=args.model)
        if args.backend == "mycobot280"
        else ReadOnlyRobot(config)
    )
    try:
        robot.connect()
        if args.backend == "mycobot280":
            robot.monitor(args.seconds, args.interval)
        else:
            statuses = robot.monitor(args.seconds)
            if not statuses:
                print(
                    f"{args.seconds:.1f} 秒内未收到换行结尾的状态数据；"
                    "请核对 COM 口、波特率和机械臂是否主动上报。"
                )
    except (RuntimeError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        print("\n已停止机械臂状态查询，未执行运动命令。")
        return 130
    finally:
        robot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
