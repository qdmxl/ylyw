#!/usr/bin/env python3
"""
灵犀X2 左手 OmniHand 2025 通讯测试

用途：在正式开始抓取实验前，先验证灵巧手基本控制是否正常。

测试项目:
  1. 全开 → 等待2秒
  2. 半开 → 等待2秒
  3. 全闭 → 等待2秒
  4. 再开 → 完成

用法:
  python3 test_left_hand.py
  python3 test_left_hand.py --nimble   # 使用 NIMBLE_HANDS 10指模式
"""

import rclpy
from rclpy.node import Node
from aimdk_msgs.msg import HandCommandArray, HandCommand, HandType, MessageHeader
import time
import argparse


LEFT_HAND_MOTORS_NIMBLE = [
    'left_thumb',    # 0: 拇指
    'left_index',    # 1: 食指
    'left_index',    # 2: 食指(第2电机)
    'left_middle',   # 3: 中指
    'left_middle',   # 4: 中指(第2电机)
    'left_ring',     # 5: 无名指
    'left_ring',     # 6: 无名指(第2电机)
    'left_pinky',    # 7: 小指
    'left_pinky',    # 8: 小指(第2电机)
    'left_thumb',    # 9: 拇指(第3电机)
]


class LeftHandTester(Node):
    """左手灵巧手通讯测试"""

    def __init__(self, use_nimble: bool = False):
        super().__init__('left_hand_tester')
        self.use_nimble = use_nimble

        # 发布者
        self.publisher = self.create_publisher(
            HandCommandArray,
            '/aima/hal/joint/hand/command',
            10
        )

        mode_name = "NIMBLE_HANDS (10指独立)" if use_nimble else "Gripper (简易夹爪)"
        self.get_logger().info(f"=== 左手 OmniHand 2025 通讯测试 ===")
        self.get_logger().info(f"控制模式: {mode_name}")
        self.get_logger().info(f"发布话题: /aima/hal/joint/hand/command")
        self.get_logger().info(f"")

    def publish_hand(self, position: float, effort: float = 1.0):
        """发布左手控制指令"""

        msg = HandCommandArray()
        msg.header = MessageHeader()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'hand_test'

        if self.use_nimble:
            # NIMBLE_HANDS: 10个手指电机独立控制
            msg.left_hand_type = HandType(value=1)
            msg.right_hand_type = HandType(value=1)
            msg.left_hands = []
            msg.right_hands = []

            for name in LEFT_HAND_MOTORS_NIMBLE:
                cmd = HandCommand()
                cmd.name = name
                cmd.position = float(position)
                cmd.velocity = 1.0
                cmd.acceleration = 1.0
                cmd.deceleration = 1.0
                cmd.effort = float(effort)
                msg.left_hands.append(cmd)
        else:
            # Gripper: 简易夹爪模式
            msg.left_hand_type = HandType(value=2)
            msg.right_hand_type = HandType(value=2)

            left_cmd = HandCommand()
            left_cmd.name = "left_hand"
            left_cmd.position = float(position)
            left_cmd.velocity = 1.0
            left_cmd.acceleration = 1.0
            left_cmd.deceleration = 1.0
            left_cmd.effort = float(effort)
            msg.left_hands = [left_cmd]
            msg.right_hands = []

        self.publisher.publish(msg)

    def run_sequence(self):
        """运行测试序列"""
        self.get_logger().info("⏳ 2秒后开始测试序列...")
        time.sleep(2.0)

        # 测试1: 全开
        self.get_logger().info("▶ [1/4] 全开 (position=1.0)")
        self.publish_hand(1.0)
        time.sleep(3.0)

        # 测试2: 半开
        self.get_logger().info("▶ [2/4] 半开 (position=0.5)")
        self.publish_hand(0.5)
        time.sleep(3.0)

        # 测试3: 全闭
        self.get_logger().info("▶ [3/4] 全闭 (position=0.0)")
        self.publish_hand(0.0)
        time.sleep(3.0)

        # 测试4: 再开
        self.get_logger().info("▶ [4/4] 再开 (position=1.0)")
        self.publish_hand(1.0)
        time.sleep(2.0)

        self.get_logger().info("✅ 测试完成!")
        self.get_logger().info("请观察灵巧手是否按照 全开→半开→全闭→再开 的顺序运动")


def main(args=None):
    parser = argparse.ArgumentParser(description='左手灵巧手通讯测试')
    parser.add_argument('--nimble', action='store_true',
                        help='使用 NIMBLE_HANDS 10指模式（默认Gripper模式）')
    parsed, _ = parser.parse_known_args()

    rclpy.init(args=args)
    node = LeftHandTester(use_nimble=parsed.nimble)

    try:
        node.run_sequence()
    except KeyboardInterrupt:
        node.get_logger().info("⏹ 用户中断")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
