"""抓取动作控制器 —— 把 YLYW 推理出的 GrabPlan 变成机械臂完整动作序列。

参考实例的安全流程，映射到多物体任意抓取：

  1. 移动到位姿目标点(相机系→基座系)
  2. 上升到安全高处
  3. 移动到目标上方(approach 高度)
  4. 张开夹爪
  5. 沿 Z 缓慢下降到抓取高度
  6. 按 YLYW 给出的力/夹紧值 夹紧
  7. 安全抬升
  8. (可选)移动到放置区释放

整个流程每一步都做状态确认，失败即中止并归位 —— 保证实验安全。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np

from .config import RobotConfig, YlywGraspConfig
from .robot_arm import RobotArm
from .ylyw_grasp_planner import GraspPlan
from .coordinate_transform import CameraToRobot

LOGGER = logging.getLogger(__name__)


class GraspController:
    """执行基于 YLYW 规划的抓取动作。"""

    def __init__(self, arm: RobotArm, tfr: CameraToRobot,
                 config: Optional[YlywGraspConfig] = None,
                 robot_config: Optional[RobotConfig] = None):
        self.arm = arm
        self.tfr = tfr
        self.config = config or YlywGraspConfig()
        self.robot_cfg = robot_config or RobotConfig()
        self.home_angles = None

    def capture_home(self) -> None:
        """记录当前关节为归位姿势。"""
        self.home_angles = self.arm.get_angles()

    def goto_home(self) -> None:
        if self.home_angles is None:
            return
        LOGGER.info("归位")
        self.arm.move_to_angles(self.home_angles)

    def pick(self, plan: GraspPlan, force_height_mm: Optional[float] = None) -> bool:
        """对给定抓取方案执行一次抓取。

        plan.grasp_xyz 是相机坐标系(米)下的质心。这里把它变换到基座并执行。
        """
        # 1. 目标位姿(相机系→基座, mm)
        base_xyz_mm = self.tfr.to_base(plan.grasp_xyz, out_mm=True)
        grasp_z_mm = float(base_xyz_mm[2]) if force_height_mm is None else force_height_mm
        # 桌面高度(基座系数值)的安全下限
        lift_z = max(80.0, grasp_z_mm + self.config.lift_height_mm * 0.5)
        approach_z = min(200.0, grasp_z_mm + 60.0)

        target = [base_xyz_mm[0], base_xyz_mm[1], grasp_z_mm,
                  plan.approach_angle_deg, -90.0, 0.0]
        above = [base_xyz_mm[0], base_xyz_mm[1], approach_z,
                 plan.approach_angle_deg, -90.0, 0.0]

        LOGGER.info("→ 目标基座坐标(mm): x=%0.1f y=%0.1f z=%0.1f",
                    base_xyz_mm[0], base_xyz_mm[1], grasp_z_mm)
        LOGGER.info("→ YLYW 抓取类型=%s 夹紧值=%d 速度档=%d",
                    plan.strategy_type, plan.close_value, plan.speed_level)

        try:
            # 2. 先到目标上方
            LOGGER.info("① 移动到目标上方")
            self.arm.move_to_coords(above, speed=3)
            # 3. 张开夹爪
            LOGGER.info("② 张开夹爪")
            self.arm.gripper_open(speed=4)
            # 4. 下降到抓取高度
            LOGGER.info("③ 下降到抓取高度")
            self.arm.move_to_coords(target, speed=2)
            # 5. 夹紧(YLYW 力)
            LOGGER.info("④ 按 YLYW 力夹紧 value=%d", plan.close_value)
            self.arm.gripper_close(plan.close_value, speed=4)
            # 6. 抬升
            LOGGER.info("⑤ 抬升")
            self.arm.move_to_coords(above, speed=3)
            return True
        except Exception as exc:  # noqa: BLE001 —— 安全优先，失败归位
            LOGGER.error("抓取失败: %s", exc)
            try:
                self.goto_home()
            except Exception:
                LOGGER.warning("归位也失败，请人工处理")
            return False

    def place(self, place_xyz_mm) -> bool:
        """移动到放置区并释放物体。"""
        try:
            LOGGER.info("⑥ 移动到放置区")
            lift_above = [place_xyz_mm[0], place_xyz_mm[1], 180.0, 0.0, -90.0, 0.0]
            self.arm.move_to_coords(lift_above, speed=3)
            self.arm.move_to_coords(
                [place_xyz_mm[0], place_xyz_mm[1], place_xyz_mm[2], 0.0, -90.0, 0.0],
                speed=2)
            LOGGER.info("⑦ 释放物体")
            self.arm.gripper_open(speed=4)
            self.goto_home()
            return True
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("放置失败: %s", exc)
            self.goto_home()
            return False
