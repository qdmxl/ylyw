#!/usr/bin/env python3
"""
Robot joint control example
This script implements a ROS2-based robot joint control system, using the Ruckig trajectory
planner to achieve smooth joint motion control.

Main features:
1. Supports controlling multiple joint areas (head, arm, waist, leg)
2. Uses Ruckig for trajectory planning to ensure smooth motion
3. Supports real-time control of joint position, velocity, and acceleration
4. Provides joint limit and PID (stiffness/damping) parameter configuration
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from aimdk_msgs.msg import JointCommandArray, JointStateArray, JointCommand
from std_msgs.msg import Header
import ruckig
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict
from threading import Lock

# QoS config: define ROS2 Quality of Service parameters
# Subscriber QoS: best-effort reliability, keep last 10 messages
subscriber_qos = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
    durability=DurabilityPolicy.VOLATILE
)

# Publisher QoS: reliable transport, keep last 10 messages
publisher_qos = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
    durability=DurabilityPolicy.VOLATILE
)


class JointArea(Enum):
    HEAD = 'HEAD'    # Head joints
    ARM = 'ARM'      # Arm joints
    WAIST = 'WAIST'  # Waist joints
    LEG = 'LEG'      # Leg joints


@dataclass
class JointInfo:
    # Joint information data class
    name: str           # Joint name
    lower_limit: float  # Joint lower angle limit
    upper_limit: float  # Joint upper angle limit
    kp: float           # Position control proportional gain
    kd: float           # Velocity control derivative gain


# Robot model configuration: define all joint parameters
robot_model: Dict[JointArea, List[JointInfo]] = {
    # Leg joint configuration
    JointArea.LEG: [
        # Left leg joints
        JointInfo("left_hip_pitch_joint", -2.704, 2.556, 40.0, 4.0),
        JointInfo("left_hip_roll_joint", -0.235, 2.906, 40.0, 4.0),
        JointInfo("left_hip_yaw_joint", -1.684, 3.430, 30.0, 3.0),
        JointInfo("left_knee_joint", 0.0000, 2.4073, 80.0, 8.0),
        JointInfo("left_ankle_pitch_joint", -0.803, 0.453, 40.0, 4.0),
        JointInfo("left_ankle_roll_joint", -0.2625, 0.2625, 20.0, 2.0),
        # Right leg joints
        JointInfo("right_hip_pitch_joint", -2.704, 2.556, 40.0, 4.0),
        JointInfo("right_hip_roll_joint", -2.906, 0.235, 40.0, 4.0),
        JointInfo("right_hip_yaw_joint", -3.430, 1.684, 30.0, 3.0),
        JointInfo("right_knee_joint", 0.0000, 2.4073, 80.0, 8.0),
        JointInfo("right_ankle_pitch_joint", -0.803, 0.453, 40.0, 4.0),
        JointInfo("right_ankle_roll_joint", -0.2625, 0.2625, 20.0, 2.0),
    ],
    # Waist joint configuration
    JointArea.WAIST: [
        JointInfo("waist_yaw_joint", -3.43, 2.382, 20.0, 4.0),
        JointInfo("waist_pitch_joint", -0.314, 0.314, 20.0, 4.0),
        JointInfo("waist_roll_joint", -0.488, 0.488, 20.0, 4.0),
    ],
    # Arm joint configuration
    JointArea.ARM: [
        # Left arm
        JointInfo("left_shoulder_pitch_joint", -3.08, 2.04, 20.0, 2.0),
        JointInfo("left_shoulder_roll_joint", -0.061, 2.993, 20.0, 2.0),
        JointInfo("left_shoulder_yaw_joint", -2.556, 2.556, 20.0, 2.0),
        JointInfo("left_elbow_joint", -2.3556, 0.0, 20.0, 2.0),
        JointInfo("left_wrist_yaw_joint", -2.556, 2.556, 20.0, 2.0),
        JointInfo("left_wrist_pitch_joint", -0.558, 0.558, 20.0, 2.0),
        JointInfo("left_wrist_roll_joint", -1.571, 0.724, 20.0, 2.0),
        # Right arm
        JointInfo("right_shoulder_pitch_joint", -3.08, 2.04, 20.0, 2.0),
        JointInfo("right_shoulder_roll_joint", -2.993, 0.061, 20.0, 2.0),
        JointInfo("right_shoulder_yaw_joint", -2.556, 2.556, 20.0, 2.0),
        JointInfo("right_elbow_joint", -2.3556, 0.0000, 20.0, 2.0),
        JointInfo("right_wrist_yaw_joint", -2.556, 2.556, 20.0, 2.0),
        JointInfo("right_wrist_pitch_joint", -0.558, 0.558, 20.0, 2.0),
        JointInfo("right_wrist_roll_joint", -0.724, 1.571, 20.0, 2.0),
    ],
    # Head joint configuration
    JointArea.HEAD: [
        JointInfo("head_yaw_joint", -0.366, 0.366, 20.0, 2.0),
        JointInfo("head_pitch_joint", -0.3838, 0.3838, 20.0, 2.0),
    ],
}


class JointControllerNode(Node):
    """
    Joint controller node
    Responsible for receiving joint states, using Ruckig for trajectory planning,
    and publishing joint commands.
    """

    def __init__(self, node_name: str, sub_topic: str, pub_topic: str, area: JointArea, dofs: int):
        """
        Initialize joint controller
        Args:
            node_name: node name
            sub_topic: topic name to subscribe (joint states)
            pub_topic: topic name to publish (joint commands)
            area: joint area (head/arm/waist/leg)
            dofs: number of DOFs
        """
        super().__init__(node_name)
        self.lock = Lock()
        self.joint_info = robot_model[area]
        self.dofs = dofs
        self.ruckig = ruckig.Ruckig(dofs, 0.002)  # 2 ms control period
        self.input = ruckig.InputParameter(dofs)
        self.output = ruckig.OutputParameter(dofs)
        self.ruckig_initialized = False

        # Initialize trajectory parameters
        self.input.current_position = [0.0] * dofs
        self.input.current_velocity = [0.0] * dofs
        self.input.current_acceleration = [0.0] * dofs

        # Motion limits
        self.input.max_velocity = [1.0] * dofs
        self.input.max_acceleration = [1.0] * dofs
        self.input.max_jerk = [25.0] * dofs

        # ROS2 subscriber and publisher
        self.sub = self.create_subscription(
            JointStateArray,
            sub_topic,
            self.joint_state_callback,
            subscriber_qos
        )
        self.pub = self.create_publisher(
            JointCommandArray,
            pub_topic,
            publisher_qos
        )

    def joint_state_callback(self, msg: JointStateArray):
        """
        Joint state callback
        Receives and processes joint state messages
        """
        self.ruckig_initialized = True

    def control_callback(self, joint_idx):
        """
        Control callback
        Uses Ruckig for trajectory planning and publishes control commands
        Args:
            joint_idx: target joint index
        """
        # Run Ruckig until the target is reached
        while self.ruckig.update(self.input, self.output) in [ruckig.Result.Working, ruckig.Result.Finished]:
            # Update current state
            self.input.current_position = self.output.new_position
            self.input.current_velocity = self.output.new_velocity
            self.input.current_acceleration = self.output.new_acceleration

            # Check if target is reached
            tolerance = 1e-6
            current_p = self.output.new_position[joint_idx]
            if abs(current_p - self.input.target_position[joint_idx]) < tolerance:
                break

            # Create and publish command
            cmd = JointCommandArray()
            for i, joint in enumerate(self.joint_info):
                j = JointCommand()
                j.name = joint.name
                j.position = self.output.new_position[i]
                j.velocity = self.output.new_velocity[i]
                j.effort = 0.0
                j.stiffness = joint.kp
                j.damping = joint.kd
                cmd.joints.append(j)

            self.pub.publish(cmd)

    def set_target_position(self, joint_name, position):
        """
        Set target joint position
        Args:
            joint_name: joint name
            position: target position
        """
        p_s = [0.0] * self.dofs
        joint_idx = 0
        for i, joint in enumerate(self.joint_info):
            if joint.name == joint_name:
                p_s[i] = position
                joint_idx = i
        self.input.target_position = p_s
        self.input.target_velocity = [0.0] * self.dofs
        self.input.target_acceleration = [0.0] * self.dofs
        self.control_callback(joint_idx)


def main(args=None):
    """
    Main function
    Initialize ROS2 node and start joint controller
    """
    rclpy.init(args=args)

    # Create leg controller node
    leg_node = JointControllerNode(
        "leg_node",
        "/aima/hal/joint/leg/state",
        "/aima/hal/joint/leg/command",
        JointArea.LEG,
        12
    )

    # waist_node = JointControllerNode(
    #     "waist_node",
    #     "/aima/hal/joint/waist/state",
    #     "/aima/hal/joint/waist/command",
    #     JointArea.WAIST,
    #     3
    # )

    # arm_node = JointControllerNode(
    #     "arm_node",
    #     "/aima/hal/joint/arm/state",
    #     "/aima/hal/joint/arm/command",
    #     JointArea.ARM,
    #     14
    # )

    # head_node = JointControllerNode(
    #     "head_node",
    #     "/aima/hal/joint/head/state",
    #     "/aima/hal/joint/head/command",
    #     JointArea.HEAD,
    #     2
    # )

    position = 0.8

    # Only control the left leg joint. If you want to control a specific joint, assign it directly.
    def timer_callback():
        """
        Timer callback
        Periodically change target position to achieve oscillating motion
        """
        nonlocal position
        position = -position
        position = 1.3 + position
        leg_node.set_target_position("left_knee_joint", position)

    #     arm_node.set_target_position("left_shoulder_pitch_joint", position)
    #     waist_node.set_target_position("waist_yaw_joint", position)
    #     head_node.set_target_position("head_pitch_joint", position)

    leg_node.create_timer(3.0, timer_callback)

    # Multi-threaded executor
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(leg_node)

    # executor.add_node(waist_node)
    # executor.add_node(arm_node)
    # executor.add_node(head_node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        leg_node.destroy_node()
        # waist_node.destroy_node()
        # arm_node.destroy_node()
        # head_node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
