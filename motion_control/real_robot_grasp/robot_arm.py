"""真实机械臂执行器 —— MyCobot 280，安全运动 / 逆解 / 夹爪。

本模块把参考实例(识别随机位置蓝色方块并自动抓取)的安全运动经验
抽成通用可复用的执行层：

  - 只读状态 + 安全启动预检(is_moving/fresh_mode/error)
  - 关节限位 + 安全余量检查
  - 分段关节插值(避免单步大跳变)
  - 逆运动学通过 pymycobot 内置 `solve_inv_kinematics` + 连续性校验
  - 夹爪开合(带确认)

`simulate=True` 时只打印，不驱动硬件 —— 便于无机械臂环境联调。
"""

from __future__ import annotations

import logging
import math
import time
from typing import List, Optional, Tuple

import numpy as np

from .config import RobotConfig

LOGGER = logging.getLogger(__name__)


class RobotError(Exception):
    """机械臂操作安全错误。"""


def _read_six(robot, method_name: str, attempts: int = 6) -> List[float]:
    method = getattr(robot, method_name)
    last = None
    for _ in range(attempts):
        last = method()
        if isinstance(last, list) and len(last) == 6 and all(v != -1 for v in last):
            return [float(v) for v in last]
        time.sleep(0.35)
    raise RobotError(f"读取 {method_name} 失败: {last}")


def _joint_dist(a: List[float], b: List[float]) -> float:
    return max(abs(float(a[i]) - float(b[i])) for i in range(6))


class RobotArm:
    """MyCobot 280 执行器封装。"""

    def __init__(self, config: Optional[RobotConfig] = None):
        self.config = config or RobotConfig()
        self._robot = None

    # ---------- 连接 ----------
    def connect(self) -> None:
        if self.config.simulate:
            LOGGER.info("【模拟】机械臂连接(不驱动硬件)")
            self._robot = _SimRobot()
            return
        try:
            from pymycobot import MyCobot280
        except ImportError as exc:
            raise RuntimeError(
                "未安装 pymycobot，请 `pip install pymycobot`；"
                "或用 simulate 模式联调。"
            ) from exc
        try:
            self._robot = MyCobot280(
                self.config.port, self.config.baudrate, timeout=self.config.timeout
            )
        except Exception as exc:
            raise RuntimeError(f"连接机械臂失败({self.config.port}): {exc}") from exc
        LOGGER.info("已连接 MyCobot %s @ %s", self.config.model, self.config.port)
        self._preflight()

    def _preflight(self) -> None:
        try:
            if self._robot.is_moving() != 0:
                raise RobotError("机械臂正在运动，需先停止")
            if self._robot.get_fresh_mode() != 1:
                raise RobotError("fresh_mode 必须为 1")
            err = self._robot.get_error_information()
            if err not in (0, None):
                raise RobotError(f"机械臂存在错误码: {err}")
        except AttributeError:
            LOGGER.warning("部分预检字段不可用，跳过")

    def close(self) -> None:
        if self._robot is not None:
            try:
                self._robot.close()
            finally:
                self._robot = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *a):
        self.close()

    # ---------- 状态 ----------
    def get_angles(self) -> List[float]:
        return _read_six(self._robot, "get_angles")

    def get_coords(self) -> List[float]:
        return _read_six(self._robot, "get_coords")

    def wait_stopped(self, timeout: float = 15.0, min_wait: float = 1.0) -> None:
        if self.config.simulate:
            return
        start = time.monotonic()
        deadline = start + timeout
        saw_moving = False
        stable = 0
        while time.monotonic() < deadline:
            moving = self._robot.is_moving()
            if moving == 1:
                saw_moving = True
                stable = 0
            elif moving == 0 and time.monotonic() - start >= min_wait:
                stable += 1
                if saw_moving or stable >= 3:
                    return
            else:
                stable = 0
            time.sleep(0.15)
        self._robot.stop()
        raise RobotError("运动未及时停止，已发送停止请求")

    # ---------- 安全逆解 ----------
    def _check_solution(self, solution, seed: List[float],
                        max_joint_change: float, min_margin: float) -> List[float]:
        if not isinstance(solution, list) or len(solution) != 6:
            raise RobotError(f"无有效逆解: {solution}")
        vals = [float(v) for v in solution]
        for i, (val, (low, high)) in enumerate(zip(vals, self.config.joint_limits)):
            if not math.isfinite(val) or not low + min_margin <= val <= high - min_margin:
                raise RobotError(
                    f"关节{i+1} {val:.1f}° 未保留 {min_margin:.1f}° 安全余量"
                )
        changes = [n - o for n, o in zip(vals, seed)]
        if max(abs(c) for c in changes) > max_joint_change:
            raise RobotError(
                f"单步关节变化过大: {[round(c, 2) for c in changes]}"
            )
        return vals

    def _interp_angles(self, start: List[float], target: List[float],
                       max_step: float) -> List[List[float]]:
        steps = max(1, math.ceil(_joint_dist(start, target) / max_step))
        return [
            [start[i] + (target[i] - start[i]) * s / steps for i in range(6)]
            for s in range(1, steps + 1)
        ]

    # ---------- 运动 ----------
    def move_to_angles(self, target: List[float], speed: Optional[int] = None,
                       block: bool = True) -> None:
        speed = speed or self.config.speed
        current = self.get_angles()
        path = self._interp_angles(current, target, self.config.joint_step_deg)
        # 最后一段单发，其余逐段
        for pts in path[:-1]:
            self._robot.send_angles(pts, speed)
            time.sleep(0.3)
        self._robot.send_angles(path[-1], speed)
        # 等价 target 直接
        if block:
            self.wait_stopped()

    def move_to_coords(self, target: List[float], speed: Optional[int] = None,
                       block: bool = True) -> None:
        """笛卡尔位姿 → 逆解 → 关节运动(带连续性与限位校验)。

        注意：这里做的是“目标位姿一次性逆解 + 关节空间分段插值”。
        关节插值过程中末端轨迹并非笛卡尔直线，且不会逐点重新逆解验证。
        对桌面安全更严格的需求应改用采样笛卡尔路径后逐点逆解(见 _validate_path)。
        """
        speed = speed or self.config.speed
        current = self.get_angles()
        target = [float(v) for v in target]
        # 目标逆解校验
        sol = self._robot.solve_inv_kinematics(target, current)
        target_angles = self._check_solution(
            sol, current, self.config.max_joint_change * 4, self.config.min_margin
        )
        path = self._interp_angles(current, target_angles, self.config.joint_step_deg)
        # 逐点校验：确保插值出的每个中间关节角都在安全限位内(移除旧的占位IK)
        self._validate_path(path, speed)
        if block:
            self.wait_stopped()

    def _validate_path(self, path: List[List[float]], speed: int) -> None:
        """逐点校验关节插值路径：每点都在限位内且无致命跳变。

        这是对“路径中间点安全”的真实检查(旧版只算了占位IK没做任何事)：
          - 发送每个中间点前，确认其关节角在限位+安全余量内；
          - 若某点越界/非有限，立即中止并报错(不继续发送，安全优先)。
        """
        low = [c[0] + self.config.min_margin for c in self.config.joint_limits]
        high = [c[1] - self.config.min_margin for c in self.config.joint_limits]
        prev = None
        for pts in path[:-1]:
            vals = [float(v) for v in pts]
            for i, v in enumerate(vals):
                if not math.isfinite(v) or not (low[i] <= v <= high[i]):
                    raise RobotError(
                        f"路径中间点关节{i+1} {v:.1f}° 超出安全限位，已中止；"
                        f"(终点IK合法，但关节空间插值路径不安全)"
                    )
            if prev is not None and max(abs(v - p) for v, p in zip(vals, prev)) \
                    > self.config.max_joint_change:
                raise RobotError("路径中间点单步关节跳变过大，已中止")
            self._robot.send_angles(pts, speed)
            time.sleep(0.3)
            prev = vals
        if not path:
            return
        self._robot.send_angles(path[-1], speed)

    # ---------- 夹爪 ----------
    def gripper_open(self, speed: int = 35) -> None:
        """张开夹爪。set_gripper_state(0)=张开，为 MyCobot 官方语义。"""
        self._robot.set_gripper_state(0, speed)
        time.sleep(1.2)
        if self.config.simulate:
            LOGGER.info("【模拟】夹爪张开(打开状态)")
            return
        val = self._robot.get_gripper_value()
        if val == -1:
            raise RobotError("无法确认夹爪张开")
        LOGGER.info("夹爪张开 value=%s(打开→开度大)", val)

    def gripper_close(self, value: int = 30, speed: int = 35) -> None:
        """按闭合值夹紧。set_gripper_value(value): value 越小闭合越多(夹越紧)。

        value 语义是夹爪位置/开合值(官方 set_gripper_value)，不是物理夹持力(N)。
        真机夹爪型号与标定决定 value↔实际开度/力量的方向，实机前务必确认。
        """
        self._robot.set_gripper_value(value, speed)
        time.sleep(1.5)
        if self.config.simulate:
            LOGGER.info("【模拟】夹爪闭合 value=%d(贴合度/开合值)", value)
            return
        val = self._robot.get_gripper_value()
        if val == -1:
            raise RobotError("无法确认夹爪夹紧")
        LOGGER.info("夹爪闭合 value=%s (期望 %d)", val, value)

    # ---------- 便捷 ----------
    def pick_and_place(self, grasp_xyz_camera, grasp_angle_deg: float = 0.0,
                       plan_close: int = 30, place_xyz=None,
                       approach_offset_mm: float = 60.0,
                       lift_height_mm: float = 120.0) -> None:
        raise NotImplementedError("见 grasp_controller.py 的完整流程")


# ==================== 纯模拟后端(无硬件联调) ====================
class _SimRobot:
    """模拟 pymycobot 最小接口。"""

    _HOME_ANGLES = [0.0, -40.0, 45.0, 0.0, 40.0, 0.0]

    def __init__(self):
        self.angles = list(self._HOME_ANGLES)
        self.coords = [200.0, 0.0, 200.0, 0.0, -90.0, 0.0]
        self.gripper = 100
        self.moving = 0

    def send_angles(self, angles, speed=35):
        LOGGER.info("【模拟】send_angles %s", [round(a,1) for a in angles])
        self.angles = list(angles)
        self.moving = 0

    def get_angles(self):
        return list(self.angles)

    def get_coords(self):
        return list(self.coords)

    def is_moving(self):
        return self.moving

    def get_fresh_mode(self):
        return 1

    def get_error_information(self):
        return 0

    def stop(self):
        self.moving = 0

    def solve_inv_kinematics(self, coords, seed):
        """简单模拟逆解：返回输入近似角度(不真正求解，不验证可达性)。

        注：simulate 模式只能验证“软件流程/调用/数据结构”，
        不能验证目标可达性、IK 是否有解、轨迹是否安全。真机前必须用真 IK。
        """
        return list(seed)  # 不真正求解

    def set_gripper_state(self, state, speed=35):
        self.gripper = 0 if state == 0 else 100
        LOGGER.info("【模拟】夹爪 state=%s (0=张开)", state)

    def set_gripper_value(self, value, speed=35):
        self.gripper = value
        LOGGER.info("【模拟】夹爪 value=%d", value)

    def get_gripper_value(self):
        return self.gripper

    def close(self):
        pass
