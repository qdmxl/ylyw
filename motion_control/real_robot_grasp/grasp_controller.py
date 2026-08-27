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
from .object_features import ObjectFeatures
from . import grasp_pose

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

    def pick(self, plan: GraspPlan, force_height_mm: Optional[float] = None,
             obj: Optional[ObjectFeatures] = None) -> bool:
        """对给定抓取方案执行一次抓取。

        plan.grasp_xyz 是相机坐标系(米)下的质心。这里把它变换到基座并执行。
        若传入 obj(物体特征)，则用 6D 姿态生成器构建完整末端位姿
        [x,y,z,rx,ry,rz](基座mm+欧拉角)，让夹爪朝向跟随物体长轴/短轴(不再固定朝下)；
        否则退回旧版固定朝下位姿(仅改俯仰)。

        Z 方向约定（基座系，Z 朝上为正，mm）：
          桌面/抓取在较低处，安全接近点在该处上方偏移处。
          故 approach_z_mm > grasp_z_mm。
          先到 approach（高位）→ 张开 → 下降至 grasp（低位）夹取
          → 抬升回 approach。
        """
        sm = self.config.speed_map
        speed_fast = int(sm.get("fast", 50))
        speed_norm = int(sm.get("normal", 35))
        speed_slow = int(sm.get("slow", 20))

        # 1. 目标位姿(相机系→基座, mm)
        base_xyz_mm = self.tfr.to_base(plan.grasp_xyz, out_mm=True)
        grasp_z_mm = float(base_xyz_mm[2]) if force_height_mm is None else force_height_mm

        # 安全校验：抓取高度必须在合理桌面范围内，防止坐标换算异常/Z反向直接上真机
        z_min, z_max = 20.0, 500.0
        if not (z_min <= grasp_z_mm <= z_max):
            raise ValueError(
                f"抓取高度异常 z={grasp_z_mm:.1f}mm，不在 [z_min, z_max] 安全区间；"
                f"请先做手-眼标定并检查 from_overhead 默认外参（严禁用占位外参直接抓取）"
            )

        # 安全接近点：在抓取高度上方偏移（approach_z > grasp_z）
        approach_off = float(self.config.approach_offset_mm)  # 默认 60
        approach_z_mm = grasp_z_mm + approach_off
        # 抓取后抬升到本目标上方更高处
        lift_z_mm = max(approach_z_mm, grasp_z_mm + float(self.config.lift_height_mm))

        # —— 6D 姿态生成：夹爪朝向跟随物体几何 ——
        if obj is not None and plan.use_6d:
            best, pose6d, _cands = grasp_pose.best_6d(
                obj, plan, self.tfr.R,
                np.array([base_xyz_mm[0], base_xyz_mm[1], grasp_z_mm]),
                grip_half_open_mm=float(self.config.force_range_mm[1] / 2.0))
            gx, gy, gz, rx, ry, rz = pose6d
            # 用 6D 位姿作为抓取目标姿态；高位/抬升位保持同一姿态但抬高
            target = [float(gx), float(gy), float(gz), float(rx), float(ry), float(rz)]
            above = [float(gx), float(gy), float(approach_z_mm), float(rx), float(ry), float(rz)]
            lift = [float(gx), float(gy), float(lift_z_mm), float(rx), float(ry), float(rz)]
            # 回写 6D 信息供实验记录
            plan.grasp_pose_6d = np.array(pose6d, dtype=float)
            plan.grasp_pose_name = best.name
            plan.approach_axis = np.asarray(best.approach_axis, dtype=float)
            plan.open_axis = np.asarray(best.x_axis, dtype=float)
            LOGGER.info("→ 6D抓取位姿=%s 候选=%s (rx,ry,rz=[%.0f,%.0f,%.0f]°)",
                        np.round(pose6d[:3], 1), best.name, rx, ry, rz)
            LOGGER.info("→ 接近方向=%s 开合方向=%s",
                        np.round(best.approach_axis, 2), np.round(best.x_axis, 2))
        else:
            # 旧版行为：夹爪固定"朝下"，仅用 YLYW 接近角改俯仰(pitch)
            target = [base_xyz_mm[0], base_xyz_mm[1], grasp_z_mm,
                      plan.approach_angle_deg, -90.0, 0.0]
            above = [base_xyz_mm[0], base_xyz_mm[1], approach_z_mm,
                     plan.approach_angle_deg, -90.0, 0.0]
            lift = [base_xyz_mm[0], base_xyz_mm[1], lift_z_mm,
                    plan.approach_angle_deg, -90.0, 0.0]

        LOGGER.info("→ 目标基座坐标(mm): x=%0.1f y=%0.1f z=%0.1f(抓取)",
                    target[0], target[1], target[2])
        LOGGER.info("→ 接近/抬升 z(mm): %.1f / %.1f", approach_z_mm, lift_z_mm)
        LOGGER.info("→ YLYW 策略=%s 夹爪闭合度=%d 速度档=%s",
                    plan.strategy_type, plan.close_value, plan.speed_level)

        try:
            # 2. 先到目标上方(高位)张开
            LOGGER.info("① 移动到目标上方(接近位)")
            self.arm.move_to_coords(above, speed=speed_fast)
            # 3. 张开夹爪
            LOGGER.info("② 张开夹爪")
            self.arm.gripper_open(speed=speed_norm)
            # 4. 下降到抓取高度(低位)
            LOGGER.info("③ 下降到抓取高度")
            self.arm.move_to_coords(target, speed=speed_slow)
            # 5. 夹紧(YLYW 闭合度)
            LOGGER.info("④ 按 YLYW 闭合度夹紧 value=%d", plan.close_value)
            self.arm.gripper_close(plan.close_value, speed=speed_norm)
            # 6. 抬升到更高处
            LOGGER.info("⑤ 抬升")
            self.arm.move_to_coords(lift, speed=speed_fast)
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
        sm = self.config.speed_map
        speed_fast = int(sm.get("fast", 50))
        speed_slow = int(sm.get("slow", 20))
        try:
            LOGGER.info("⑥ 移动到放置区")
            lift_above = [place_xyz_mm[0], place_xyz_mm[1], 180.0, 0.0, -90.0, 0.0]
            self.arm.move_to_coords(lift_above, speed=speed_fast)
            self.arm.move_to_coords(
                [place_xyz_mm[0], place_xyz_mm[1], place_xyz_mm[2], 0.0, -90.0, 0.0],
                speed=speed_slow)
            LOGGER.info("⑦ 释放物体")
            self.arm.gripper_open(speed=speed_fast)
            self.goto_home()
            return True
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("放置失败: %s", exc)
            self.goto_home()
            return False
