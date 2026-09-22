import unittest

from voice_grasp_demo.gripper import Gripper
from voice_grasp_demo.robot import MyCobot280ReadOnly, ReadOnlyRobot
from voice_grasp_demo.config import SerialConfig


class FakeSerial:
    is_open = True

    def __init__(self):
        self.writes = []

    def readline(self):
        return b"READY\r\n"

    def close(self):
        self.is_open = False


class FakeMyCobot:
    def __init__(self):
        self.calls = []

    def get_angles(self):
        self.calls.append("get_angles")
        return [0.0] * 6

    def get_coords(self):
        self.calls.append("get_coords")
        return [0.0] * 6

    def get_error_information(self):
        self.calls.append("get_error_information")
        return 0

    def close(self):
        self.calls.append("close")


class SafetyTests(unittest.TestCase):
    def test_gripper_is_simulation_first(self):
        with Gripper() as gripper:
            self.assertEqual(gripper.open().position, 0.0)
            self.assertEqual(gripper.close().position, 1.0)

    def test_hardware_gripper_rejects_unknown_protocol(self):
        with self.assertRaises(RuntimeError):
            Gripper(simulate=False).connect()

    def test_robot_read_status_never_writes(self):
        robot = ReadOnlyRobot(SerialConfig())
        fake = FakeSerial()
        robot._serial = fake
        status = robot.read_status()
        self.assertEqual(status.raw, "READY")
        self.assertEqual(fake.writes, [])

    def test_mycobot_adapter_calls_query_methods_only(self):
        robot = MyCobot280ReadOnly(SerialConfig())
        fake = FakeMyCobot()
        robot._robot = fake
        status = robot.read_status()
        self.assertEqual(status.angles, [0.0] * 6)
        self.assertTrue(status.connected)
        self.assertEqual(
            fake.calls,
            ["get_angles", "get_coords", "get_error_information"],
        )


if __name__ == "__main__":
    unittest.main()
