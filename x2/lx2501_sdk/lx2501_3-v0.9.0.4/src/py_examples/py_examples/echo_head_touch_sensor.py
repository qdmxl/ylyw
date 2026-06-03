#!/usr/bin/env python3
"""
Head touch state subscription example
"""

import rclpy
from rclpy.node import Node
from aimdk_msgs.msg import TouchState


class TouchStateSubscriber(Node):
    def __init__(self):
        super().__init__('touch_state_subscriber')

        # touch event types
        self.event_type_map = {
            TouchState.UNKNOWN: "UNKNOWN",
            TouchState.IDLE: "IDLE",
            TouchState.TOUCH: "TOUCH",
            TouchState.SLIDE: "SLIDE",
            TouchState.PAT_ONCE: "PAT_ONCE",
            TouchState.PAT_TWICE: "PAT_TWICE",
            TouchState.PAT_TRIPLE: "PAT_TRIPLE"
        }

        # create subscriber
        self.subscription = self.create_subscription(
            TouchState,
            '/aima/hal/sensor/touch_head',
            self.touch_callback,
            10
        )

        self.get_logger().info(
            'TouchState subscriber started, listening to /aima/hal/sensor/touch_head')

    def touch_callback(self, msg):
        event_str = self.event_type_map.get(
            msg.event_type, f"INVALID({msg.event_type})")

        self.get_logger().info(f'Timestamp: {msg.header.stamp.sec}.{msg.header.stamp.nanosec:09d}, '
                               f'Event: {event_str} ({msg.event_type})')


def main(args=None):
    rclpy.init(args=args)
    node = TouchStateSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
