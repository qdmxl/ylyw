import rclpy
from rclpy.node import Node
from aimdk_msgs.msg import HandCommandArray, HandCommand, HandType, MessageHeader
import time


class HandControl(Node):
    def __init__(self):
        super().__init__('hand_control')

        # Create publisher
        self.publisher_ = self.create_publisher(
            HandCommandArray,
            '/aima/hal/joint/hand/command',
            10
        )

        self.timer_ = self.create_timer(
            0.8,
            self.publish_hand_commands
        )

        # Initialize variables
        self.target_finger = 0
        self.step = 1
        self.increasing = True
        self.get_logger().info("Hand control node started!")

    def build_hand_cmd(self, name: str) -> HandCommand:
        cmd = HandCommand()
        cmd.name = name
        cmd.position = 0.0
        cmd.velocity = 0.1
        cmd.acceleration = 0.0
        cmd.deceleration = 0.0
        cmd.effort = 0.0
        return cmd

    def publish_hand_commands(self):
        msg = HandCommandArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'hand_command'
        msg.left_hand_type.value = 1      # NIMBLE_HANDS
        msg.right_hand_type.value = 1     # NIMBLE_HANDS

        # left hand
        msg.left_hands = [self.build_hand_cmd('') for _ in range(10)]
        msg.left_hands[0].name = 'left_thumb'
        for i in range(1, 10):
            msg.left_hands[i].name = 'left_index'

        # right hand
        msg.right_hands = [self.build_hand_cmd('') for _ in range(10)]
        msg.right_hands[0].name = 'right_thumb'
        for i in range(1, 10):
            msg.right_hands[i].name = 'right_pinky'

        if self.target_finger < 10:
            msg.right_hands[self.target_finger].position = 0.8
        else:
            target_finger_ = self.target_finger - 10
            target_position = 0.8
            if target_finger_ < 3:
                # The three thumb motors on the left hand need their signs inverted to mirror the right hand's motion
                target_position = -target_position
            msg.left_hands[target_finger_].position = target_position

        self.publisher_.publish(msg)
        self.get_logger().info(
            f'Published hand command with target_finger: {self.target_finger}')
        self.update_target_finger()

    def update_target_finger(self):
        if self.increasing:
            self.target_finger += self.step
            if self.target_finger >= 19:
                self.target_finger = 19
                self.increasing = False
        else:
            self.target_finger -= self.step
            if self.target_finger <= 0:
                self.target_finger = 0
                self.increasing = True


def main(args=None):
    rclpy.init(args=args)
    hand_control_node = HandControl()

    try:
        rclpy.spin(hand_control_node)
    except KeyboardInterrupt:
        pass
    finally:
        hand_control_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
