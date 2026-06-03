#!/usr/bin/env python3
"""
YLYW → 灵犀X2 适配层 (LingxiX2Adapter)

将 YLYW 推理引擎的策略输出映射为灵犀X2 SDK 控制指令。
基于 lx2501_3-v0.9.0.4 SDK / ROS2 Humble

依赖:
  - ylyw (论文现有推理引擎)
  - rclpy, aimdk_msgs (灵犀X2 SDK)
  - sensor_msgs, cv_bridge (视觉处理)
  - numpy
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from aimdk_msgs.msg import HandCommandArray, HandCommand, HandType, JointCommandArray, JointCommand
from sensor_msgs.msg import Image, PointCloud2, CameraInfo
from cv_bridge import CvBridge
import numpy as np
import time
from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum


# ============================================================
# 策略类型枚举
# ============================================================
class GraspStrategy(Enum):
    POWER_GRASP = "power_grasp"           # 乾: 全掌包覆
    PRECISE_PICK = "precise_pick"         # 坤: 指尖捏取
    DYNAMIC_GRASP = "dynamic_grasp"       # 震: 动态快速
    CAUTIOUS_GRASP = "cautious_grasp"     # 履: 谨慎试探
    ADAPTIVE_GRASP = "adaptive_grasp"     # 睽: 异形自适应
    WRAP_GRASP = "wrap_grasp"             # 随: 环绕包络
    INCREMENTAL = "incremental_grasp"     # 渐: 渐进夹紧
    CONDITIONAL = "conditional_grasp"     # 需: 条件判断
    GENERIC = "generic_grasp"             # 降级通用


# ============================================================
# YLYW 策略输出数据结构
# ============================================================
@dataclass
class YLYWOutput:
    strategy_type: str           # 策略类型名
    force_preset: float          # 力预设 [0, 1]（来自卦象规则）
    modifier: float              # 爻位修正系数 [0.75, 1.05]
    approach_angle: float        # 接近角度（度）
    speed: str                   # 速度等级: slow/medium/fast
    hexagram_name: str           # 匹配卦象名
    hexagram_similarity: float   # 余弦相似度
    S_yao: float                 # 爻位综合评分
    precautions: List[str]       # 注意事项
    yao_vector: np.ndarray       # 6维爻向量 [0,1]⁶
    trigram_membership: np.ndarray  # 8维隶属度

    @property
    def effective_force(self) -> float:
        """实际执行力 = 力预设 × 爻位修正系数"""
        return np.clip(self.force_preset * self.modifier, 0.1, 1.0)


# ============================================================
# 灵巧手策略参数映射表
# ============================================================
# 格式: {策略名: {手指名: (开合position, velocity, effort比例)}}
# NIMBLE_HANDS 有10个手指电机:
#   thumb(3电机), index(2电机), middle(1电机), ring(1电机), pinky(1电机)
#   剩余2个自由度用于对掌/侧摆

STRATEGY_HAND_PARAMS: Dict[str, Dict[str, tuple]] = {
    "power_grasp": {
        # 全掌包覆: 所有手指均匀用力闭合
        "thumb":  (0.0, 1.0, 1.0),
        "index":  (0.0, 1.0, 1.0),
        "middle": (0.0, 1.0, 1.0),
        "ring":   (0.0, 1.0, 1.0),
        "pinky":  (0.0, 1.0, 1.0),
    },
    "precise_pick": {
        # 指尖捏取: 仅拇指+食指参与，低力矩
        "thumb":  (0.0, 0.3, 0.25),
        "index":  (0.0, 0.3, 0.25),
        "middle": (1.0, 0.3, 0.0),   # 不参与
        "ring":   (1.0, 0.3, 0.0),
        "pinky":  (1.0, 0.3, 0.0),
    },
    "dynamic_grasp": {
        # 动态抓取: 快速闭合，中高力矩
        "thumb":  (0.0, 1.0, 0.70),
        "index":  (0.0, 1.0, 0.70),
        "middle": (0.0, 1.0, 0.70),
        "ring":   (0.0, 1.0, 0.70),
        "pinky":  (0.0, 1.0, 0.70),
    },
    "cautious_grasp": {
        # 谨慎试探: 慢速闭合，低力矩，触停
        "thumb":  (0.0, 0.2, 0.30),
        "index":  (0.0, 0.2, 0.30),
        "middle": (0.0, 0.2, 0.30),
        "ring":   (0.0, 0.2, 0.30),
        "pinky":  (0.0, 0.2, 0.30),
    },
    "adaptive_grasp": {
        # 异形自适应: 交叉指型（拇+中+小指用力，食+无名指轻触）
        "thumb":  (0.0, 0.5, 0.50),
        "index":  (0.0, 0.5, 0.20),
        "middle": (0.0, 0.5, 0.50),
        "ring":   (0.0, 0.5, 0.20),
        "pinky":  (0.0, 0.5, 0.50),
    },
    "wrap_grasp": {
        # 环绕包络: 全手指大幅度闭合
        "thumb":  (0.0, 0.8, 0.60),
        "index":  (0.0, 0.8, 0.60),
        "middle": (0.0, 0.8, 0.60),
        "ring":   (0.0, 0.8, 0.60),
        "pinky":  (0.0, 0.8, 0.60),
    },
    "incremental_grasp": {
        # 渐进夹紧: 初始仅部分闭合，逐步增加
        "thumb":  (0.0, 0.3, 0.40),
        "index":  (0.0, 0.3, 0.40),
        "middle": (0.0, 0.3, 0.40),
        "ring":   (0.0, 0.3, 0.40),
        "pinky":  (0.0, 0.3, 0.40),
    },
    "conditional_grasp": {
        # 条件判断: 中速中力闭合
        "thumb":  (0.0, 0.5, 0.50),
        "index":  (0.0, 0.5, 0.50),
        "middle": (0.0, 0.5, 0.50),
        "ring":   (0.0, 0.5, 0.50),
        "pinky":  (0.0, 0.5, 0.50),
    },
    "generic_grasp": {
        # 降级通用
        "thumb":  (0.0, 0.5, 0.50),
        "index":  (0.0, 0.5, 0.50),
        "middle": (0.0, 0.5, 0.50),
        "ring":   (0.0, 0.5, 0.50),
        "pinky":  (0.0, 0.5, 0.50),
    },
}


# ============================================================
# 灵犀X2 适配器
# ============================================================
class LingxiX2Adapter(Node):
    """YLYW 策略 → 灵犀X2 灵巧手 + 手臂控制"""

    def __init__(self, hand_side: str = "right"):
        """
        Args:
            hand_side: 使用哪只灵巧手 ("left" / "right" / "both")
        """
        super().__init__('ylyw_lingxi_adapter')
        self.hand_side = hand_side
        self.bridge = CvBridge()

        # --- QoS 配置 ---
        hand_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        arm_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )

        # --- 发布者 ---
        self.hand_pub = self.create_publisher(
            HandCommandArray,
            '/aima/hal/joint/hand/command',
            hand_qos
        )
        self.arm_pub = self.create_publisher(
            JointCommandArray,
            '/aima/hal/joint/arm/command',
            arm_qos
        )

        # --- 订阅者 (视觉) ---
        self.rgb_sub = self.create_subscription(
            Image,
            '/aima/hal/sensor/rgbd_head_front/rgb_image',
            self._rgb_callback,
            sensor_qos
        )
        self.depth_sub = self.create_subscription(
            Image,
            '/aima/hal/sensor/rgbd_head_front/depth_image',
            self._depth_callback,
            sensor_qos
        )
        self.pointcloud_sub = self.create_subscription(
            PointCloud2,
            '/aima/hal/sensor/rgbd_head_front/depth_pointcloud',
            self._pointcloud_callback,
            sensor_qos
        )
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            '/aima/hal/sensor/rgbd_head_front/rgb_camera_info',
            self._camera_info_callback,
            sensor_qos
        )

        # --- 内部状态 ---
        self._latest_rgb: Optional[np.ndarray] = None
        self._latest_depth: Optional[np.ndarray] = None
        self._latest_pointcloud: Optional[np.ndarray] = None
        self._camera_info: Optional[CameraInfo] = None
        self._grasping = False

        # --- 手臂预设位置 ---
        self.home_position = {  # 收拢位
            "left_shoulder_pitch": -0.5,
            "left_shoulder_roll": 1.5,
            "left_shoulder_yaw": 0.0,
            "left_elbow": -1.0,
            "left_wrist_yaw": 0.0,
            "left_wrist_pitch": 0.0,
            "left_wrist_roll": 0.0,
        }
        self.approach_position = {  # 接近位（伸出）
            "left_shoulder_pitch": 1.0,
            "left_shoulder_roll": 0.5,
            "left_shoulder_yaw": 0.0,
            "left_elbow": -0.3,
            "left_wrist_yaw": 0.0,
            "left_wrist_pitch": -0.2,
            "left_wrist_roll": 0.0,
        }

        # 手臂关节参数 (kp=kd=20/2)
        self.arm_kp = 20.0
        self.arm_kd = 2.0

        self.get_logger().info("✅ LingxiX2Adapter initialized")
        self.get_logger().info(f"   Hand side: {hand_side}")
        self.get_logger().info(f"   Subscribed to RGB-D camera topics")

    # ============================================================
    # 视觉回调
    # ============================================================
    def _rgb_callback(self, msg: Image):
        self._latest_rgb = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def _depth_callback(self, msg: Image):
        self._latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')

    def _pointcloud_callback(self, msg: PointCloud2):
        # PointCloud2 → numpy (简化版，完整版需解析字段)
        self._latest_pointcloud = msg

    def _camera_info_callback(self, msg: CameraInfo):
        if self._camera_info is None:
            self._camera_info = msg
            self.get_logger().info(f"Camera intrinsics: {msg.width}x{msg.height}, "
                                   f"fx={msg.k[0]:.1f}, fy={msg.k[4]:.1f}")

    @property
    def vision_ready(self) -> bool:
        """视觉数据就绪"""
        return (self._latest_rgb is not None and
                self._latest_depth is not None and
                self._camera_info is not None)

    # ============================================================
    # 手臂控制
    # ============================================================
    def move_arm_to_home(self):
        """手臂回到收拢位置"""
        self._publish_arm_command(self.home_position)

    def move_arm_approach(self):
        """手臂伸出到接近位置"""
        self._publish_arm_command(self.approach_position)

    def _publish_arm_command(self, joint_positions: Dict[str, float]):
        """发布手臂关节命令（带Ruckig轨迹规划）"""
        msg = JointCommandArray()

        for joint_name, position in joint_positions.items():
            cmd = JointCommand()
            cmd.name = joint_name
            cmd.position = float(position)
            cmd.velocity = 0.0
            cmd.effort = 0.0
            cmd.stiffness = self.arm_kp
            cmd.damping = self.arm_kd
            msg.joints.append(cmd)

        self.arm_pub.publish(msg)

    # ============================================================
    # 灵巧手控制
    # ============================================================
    def open_hand(self):
        """张开灵巧手（抓取前准备）"""
        msg = self._build_hand_command("open")
        self.hand_pub.publish(msg)

    def execute_grasp(self, ylyw_output: YLYWOutput) -> bool:
        """
        根据 YLYW 策略输出执行灵巧手抓取

        Returns:
            bool: 抓取是否成功
        """
        strategy = ylyw_output.strategy_type
        effective_force = ylyw_output.effective_force

        self.get_logger().info(
            f"🎯 Executing: {strategy} | "
            f"hexagram={ylyw_output.hexagram_name} | "
            f"force={ylyw_output.force_preset:.2f}×{ylyw_output.modifier:.2f}"
            f"={effective_force:.2f} | "
            f"S_yao={ylyw_output.S_yao:.2f}"
        )

        # 1. 张开灵巧手
        self.open_hand()
        time.sleep(0.3)

        # 2. 闭合（执行策略）
        msg = self._build_hand_command(strategy, effective_force)
        self.hand_pub.publish(msg)

        # 3. 等待抓取完成
        time.sleep(0.5)

        # TODO: 通过 joint state 反馈判断是否成功抓取
        return True

    def _build_hand_command(self, strategy: str,
                            force_scale: float = 1.0) -> HandCommandArray:
        """
        构建灵巧手控制消息

        Args:
            strategy: 策略类型名 (或用 "open" 表示张开)
            force_scale: 力缩放系数 (来自 YLYW force_preset × modifier)
        """
        msg = HandCommandArray()
        msg.left_hand_type = HandType(value=1)   # NIMBLE_HANDS
        msg.right_hand_type = HandType(value=1)  # NIMBLE_HANDS

        # 获取策略参数
        params = STRATEGY_HAND_PARAMS.get(strategy,
                                          STRATEGY_HAND_PARAMS["generic_grasp"])

        # 构建左右手的手指指令
        # NIMBLE_HANDS: 10个电机/手
        # 手指映射 (简化): 0=thumb, 1-2=index, 3-4=middle, 5-6=ring, 7-8=pinky, 9=对掌
        finger_mapping = {
            "thumb":  [0],
            "index":  [1, 2],
            "middle": [3, 4],
            "ring":   [5, 6],
            "pinky":  [7, 8],
        }

        left_commands = [self._make_default_hand_cmd(f"left_motor_{i}") for i in range(10)]
        right_commands = [self._make_default_hand_cmd(f"right_motor_{i}") for i in range(10)]

        for finger_name, motor_indices in finger_mapping.items():
            pos, vel, eff = params.get(finger_name, (0.0, 0.5, 0.5))
            for idx in motor_indices:
                if self.hand_side in ("left", "both"):
                    left_commands[idx].position = float(pos)
                    left_commands[idx].velocity = float(vel)
                    left_commands[idx].effort = float(eff * force_scale)
                if self.hand_side in ("right", "both"):
                    right_commands[idx].position = float(pos)
                    right_commands[idx].velocity = float(vel)
                    right_commands[idx].effort = float(eff * force_scale)

        msg.left_hands = left_commands
        msg.right_hands = right_commands
        return msg

    @staticmethod
    def _make_default_hand_cmd(name: str) -> HandCommand:
        """创建默认手指指令"""
        cmd = HandCommand()
        cmd.name = name
        cmd.position = 0.5   # 半开
        cmd.velocity = 0.5
        cmd.acceleration = 1.0
        cmd.deceleration = 1.0
        cmd.effort = 0.5
        return cmd

    # ============================================================
    # 完整抓取流程
    # ============================================================
    def grasp_sequence(self, ylyw_output: YLYWOutput) -> bool:
        """
        完整抓取序列: 手臂接近 → 灵巧手抓取 → 手臂回位

        Args:
            ylyw_output: YLYW 推理输出

        Returns:
            bool: 是否成功
        """
        if self._grasping:
            self.get_logger().warn("Already grasping, skipping")
            return False

        self._grasping = True
        try:
            # Step 1: 手臂伸出
            self.get_logger().info("▶ Step 1: Moving arm to approach position")
            self.move_arm_approach()
            time.sleep(1.0)  # 等待手臂到位

            # Step 2: 灵巧手抓取
            self.get_logger().info("▶ Step 2: Executing grasp")
            success = self.execute_grasp(ylyw_output)
            time.sleep(0.3)

            # Step 3: 手臂回位（带物体）
            self.get_logger().info("▶ Step 3: Moving arm to home")
            # 可以调整回位力控以保护物体
            self.move_arm_to_home()
            time.sleep(1.0)

            return success

        finally:
            self._grasping = False

    # ============================================================
    # 视觉数据获取（供 YLYW 特征提取器使用）
    # ============================================================
    def get_latest_frame(self) -> Optional[dict]:
        """获取最新一帧视觉数据"""
        if not self.vision_ready:
            return None
        return {
            "rgb": self._latest_rgb,
            "depth": self._latest_depth,
            "pointcloud": self._latest_pointcloud,
            "camera_info": self._camera_info,
        }


# ============================================================
# 主控节点 (实验编排)
# ============================================================
class YLYWExperimentNode(Node):
    """
    YLYW 物理验证实验主控节点
    协调: 视觉特征提取 → YLYW推理 → 灵犀X2执行
    """

    def __init__(self):
        super().__init__('ylyw_experiment')
        self.adapter = LingxiX2Adapter(hand_side="right")

        # TODO: 导入 YLYW 推理引擎
        # from ylyw.prior_manual import PriorManual
        # from ylyw.perception import FeatureExtractor
        # self.ylyw = PriorManual()
        # self.extractor = FeatureExtractor()

        self.results = []
        self.get_logger().info("✅ YLYW Experiment Node initialized")

    def run_single_trial(self, object_id: int, object_type: str) -> dict:
        """
        单次实验:
        1. 采集视觉 → 提取13维特征
        2. YLYW 推理 → 输出策略
        3. 灵犀X2 执行抓取
        4. 记录结果
        """
        # Step 1: 获取视觉
        frame = self.adapter.get_latest_frame()
        if frame is None:
            self.get_logger().error("Vision not ready")
            return {"error": "no_frame"}

        # Step 2: YLYW 推理 (待集成)
        # features = self.extractor.extract(frame["rgb"], frame["depth"])
        # t0 = time.time()
        # ylyw_out = self.ylyw.infer(features)
        # t_infer = time.time() - t0

        # Step 3: 执行抓取
        # success = self.adapter.grasp_sequence(ylyw_out)

        # Step 4: 记录
        # result = {
        #     "obj_id": object_id,
        #     "obj_type": object_type,
        #     "hexagram": ylyw_out.hexagram_name,
        #     "strategy": ylyw_out.strategy_type,
        #     "force_preset": ylyw_out.force_preset,
        #     "modifier": ylyw_out.modifier,
        #     "S_yao": ylyw_out.S_yao,
        #     "inference_ms": t_infer * 1000,
        #     "success": success,
        # }
        # self.results.append(result)
        # return result

        self.get_logger().info(f"Trial: {object_id} ({object_type})")
        return {"status": "placeholder"}

    def print_summary(self):
        """打印实验汇总"""
        if not self.results:
            self.get_logger().info("No results yet")
            return

        total = len(self.results)
        success = sum(1 for r in self.results if r.get("success"))
        strategies = set(r.get("strategy") for r in self.results)
        avg_infer = np.mean([r.get("inference_ms", 0) for r in self.results])

        self.get_logger().info("=" * 50)
        self.get_logger().info(f"Total trials: {total}")
        self.get_logger().info(f"Success rate: {success}/{total} ({100*success/total:.1f}%)")
        self.get_logger().info(f"Unique strategies: {len(strategies)}")
        self.get_logger().info(f"Avg inference: {avg_infer:.1f} ms")
        self.get_logger().info("=" * 50)


def main(args=None):
    rclpy.init(args=args)
    node = YLYWExperimentNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.print_summary()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
