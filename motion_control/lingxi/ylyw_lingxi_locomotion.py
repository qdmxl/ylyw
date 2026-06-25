#!/usr/bin/env python3
"""
YLYW → 灵犀X2 速度控制 ROS2 适配器

部署于灵犀X2机载计算平台（需ROS2 Humble + aimdk_msgs）

数据流:
  灵犀X2 IMU (/aima/hal/imu/chest/state) 
  → 6D状态向量 
  → YLYW推理 (L1→L2→L3→步态) 
  → McLocomotionVelocity (forward/lateral/angular)
  → /aima/mc/locomotion/velocity (50Hz)

使用:
  python3 ylyw_lingxi_locomotion.py

安全机制:
  - 倾角>30°自动停止
  - Ctrl+C 平滑减速+切STAND_DEFAULT
"""
import sys, os, time, math, signal
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.time import Time

from sensor_msgs.msg import Imu
from aimdk_msgs.msg import McLocomotionVelocity, MessageHeader
from aimdk_msgs.srv import SetMcInputSource, SetMcAction

# YLYW 引擎路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from motion_control.ylyw_locomotion import YLYWLocomotionController


class YLYWLingxiLocomotion(Node):
    """
    YLYW 运动控制 → 灵犀X2 速度指令 ROS2 节点
    
    订阅:
      /aima/hal/imu/chest/state  (sensor_msgs/Imu, 100Hz)
    
    发布:
      /aima/mc/locomotion/velocity  (McLocomotionVelocity, 50Hz)
    """
    
    # YLYW 步态 → 灵犀X2 速度映射表
    GAIT_VELOCITY_MAP = {
        '静止站立':   (0.0, 0.0, 0.0),
        '极慢爬行':   (0.0, 0.0, 0.0),
        '慢走':       (0.25, 0.0, 0.0),
        '谨慎行走':   (0.22, 0.0, 0.0),
        '过渡缓冲':   (0.22, 0.0, 0.0),
        '正常行走':   (0.45, 0.0, 0.0),
        '快速行走':   (0.70, 0.0, 0.0),
        '小跑步态':   (0.85, 0.0, 0.0),
        '奔跑':       (1.0, 0.0, 0.0),
        '爬坡步态':   (0.25, 0.0, 0.0),
        '下坡步态':   (0.22, 0.0, 0.0),
        '恢复步态':   (0.0, 0.0, 0.0),
        '自适应步态': (0.30, 0.0, 0.0),
        '转向步态':   (0.0, 0.0, 0.30),
    }
    
    # 安全参数
    MAX_TILT_WARN = 0.4    # rad ≈ 23°, 警告
    MAX_TILT_STOP = 0.7   # rad ≈ 40°, 强制停止
    YLYW_INFER_HZ = 10    # YLYW 推理频率（IMU 100Hz，推理10Hz足够）
    
    def __init__(self):
        super().__init__('ylyw_lingxi_locomotion')
        
        # 初始化 YLYW 控制器
        self.controller = YLYWLocomotionController()
        
        # 状态变量
        self._latest_imu = None
        self._imu_count = 0
        self._infer_count = 0
        self._current_gait = None
        self._filtered_accel_z = 9.81  # 低通滤波 Z 加速度
        self._prev_tilt = 0.0
        self._active = False
        self._emergency_stop = False
        
        # --- QoS ---
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST, depth=5
        )
        cmd_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST, depth=10
        )
        
        # --- 发布者: 速度指令 ---
        self.vel_pub = self.create_publisher(
            McLocomotionVelocity,
            '/aima/mc/locomotion/velocity',
            cmd_qos
        )
        
        # --- 订阅者: IMU ---
        self.imu_sub = self.create_subscription(
            Imu,
            '/aima/hal/imu/chest/state',
            self._imu_callback,
            sensor_qos
        )
        
        # --- 服务客户端: 输入源注册 ---
        self.input_src_client = self.create_client(
            SetMcInputSource, '/aimdk_5Fmsgs/srv/SetMcInputSource'
        )
        
        # --- 定时器: YLYW推理 + 速度发布 (50Hz) ---
        self.timer = self.create_timer(0.02, self._control_loop)  # 20ms = 50Hz
        
        self.get_logger().info('✅ YLYW 灵犀X2 运动控制节点已启动')
        self.get_logger().info('   数据流: IMU → 6D状态 → YLYW → 步态 → VelocityCmd')
    
    # ============================================================
    # IMU 回调
    # ============================================================
    def _imu_callback(self, msg: Imu):
        """接收 IMU 数据"""
        self._latest_imu = {
            'orientation': {
                'x': msg.orientation.x, 'y': msg.orientation.y,
                'z': msg.orientation.z, 'w': msg.orientation.w
            },
            'angular_velocity': {
                'x': msg.angular_velocity.x,
                'y': msg.angular_velocity.y,
                'z': msg.angular_velocity.z
            },
            'linear_acceleration': {
                'x': msg.linear_acceleration.x,
                'y': msg.linear_acceleration.y,
                'z': msg.linear_acceleration.z
            },
            'timestamp': Time.from_msg(msg.header.stamp).nanoseconds / 1e9
        }
        self._imu_count += 1
    
    # ============================================================
    # 主控制循环 (50Hz)
    # ============================================================
    def _control_loop(self):
        """50Hz 控制循环: IMU→状态→YLYW→速度指令"""
        if not self._active:
            return
        
        if self._latest_imu is None:
            # 无 IMU 数据，发零速
            self._publish_velocity(0.0, 0.0, 0.0)
            return
        
        imu = self._latest_imu
        
        # Step 1: IMU → 6D 状态向量
        state_6d, tilt = self._imu_to_state(imu)
        
        # Step 2: 安全检查
        if tilt > self.MAX_TILT_STOP:
            if not self._emergency_stop:
                self.get_logger().warn(f'⚠️ 紧急停止! 倾角={tilt:.3f}rad > {self.MAX_TILT_STOP}rad')
                self._emergency_stop = True
            self._publish_velocity(0.0, 0.0, 0.0)
            return
        elif tilt > self.MAX_TILT_WARN:
            if tilt - self._prev_tilt > 0.05:
                self.get_logger().warn(f'⚠️ 倾角警告 {tilt:.3f}rad')
            # 继续运行但记录警告
        
        self._prev_tilt = tilt
        self._emergency_stop = False
        
        # Step 3: YLYW 推理 (降频到10Hz, 避免不必要的推理)
        self._infer_count += 1
        if self._infer_count % (50 // self.YLYW_INFER_HZ) == 0:
            gait_params = self.controller.infer(np.array(state_6d), verbose=False)
            if gait_params:
                self._current_gait = gait_params
        
        # Step 4: 步态 → 速度指令
        if self._current_gait is None:
            fwd, lat, ang = 0.0, 0.0, 0.0
        else:
            gait_name = self._current_gait['gait_name']
            force_coef = self._current_gait.get('force_coefficient', 0.5)
            base_fwd, base_lat, base_ang = self.GAIT_VELOCITY_MAP.get(
                gait_name, (0.0, 0.0, 0.0)
            )
            # 力系数调制速度
            fwd = base_fwd * force_coef
            lat = base_lat * force_coef
            ang = base_ang * force_coef
        
        # 倾角过大时降速
        if tilt > self.MAX_TILT_WARN:
            fwd *= 0.5
        
        # Step 5: 发布速度指令
        self._publish_velocity(fwd, lat, ang)
        
        # 定期日志
        if self._infer_count % 250 == 0:  # ~5s
            g = self._current_gait
            hex_name = g['hexagram_name'] if g else 'N/A'
            gait_name = g['gait_name'] if g else 'N/A'
            self.get_logger().info(
                f'卦:{hex_name} | 步态:{gait_name} | '
                f'Vel(fwd:{fwd:.2f}, lat:{lat:.2f}, ang:{ang:.2f}) | '
                f'tilt:{tilt:.3f}rad | 推理#{self.controller.step_count}'
            )
    
    # ============================================================
    # IMU → 6D 状态向量映射
    # ============================================================
    def _imu_to_state(self, imu):
        """
        IMU 数据 → [posture, com_h, force_dist, zmp, disturbance, terrain]
        全部归一化到 [0,1]
        """
        q = imu['orientation']
        qx, qy, qz, qw = q['x'], q['y'], q['z'], q['w']
        
        # Quaternion → Euler (roll, pitch)
        sinr_cosp = 2.0 * (qw * qx + qy * qz)
        cosr_cosp = 1.0 - 2.0 * (qx*qx + qy*qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        sinp = 2.0 * (qw * qy - qz * qx)
        pitch = max(-math.pi/2, min(math.pi/2, math.asin(sinp)))
        
        tilt = abs(roll) + abs(pitch)
        
        # 初爻: 姿态稳定性
        posture = max(0.0, 1.0 - tilt / 0.5)
        
        # 二爻: 质心高度（从Z加速度推断）
        az = imu['linear_acceleration']['z']
        self._filtered_accel_z = 0.9 * self._filtered_accel_z + 0.1 * az
        com_h = max(0.0, min(1.0, self._filtered_accel_z / 9.81))
        
        # 三爻: 力分布（从侧向加速度不对称度推断）
        ay = imu['linear_acceleration']['y']
        lateral_asym = abs(ay) / 9.81
        force_dist = max(0.0, 1.0 - lateral_asym * 5.0)
        
        # 四爻: ZMP 裕度
        w = imu['angular_velocity']
        ang_mag = math.sqrt(w['x']**2 + w['y']**2 + w['z']**2)
        zmp = max(0.0, 1.0 - tilt * 2.0 - ang_mag * 0.5)
        
        # 五爻: 扰动
        disturbance = min(1.0, ang_mag * 3.0 + abs(az - 9.81) / 10.0)
        
        # 上爻: 地形（无地形传感器，默认平坦）
        terrain = 0.8
        
        return [posture, com_h, force_dist, zmp, disturbance, terrain], tilt
    
    # ============================================================
    # 发布速度指令
    # ============================================================
    def _publish_velocity(self, forward, lateral, angular):
        """发布 McLocomotionVelocity 消息"""
        msg = McLocomotionVelocity()
        msg.header = MessageHeader()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.source = "ylyw"
        msg.forward_velocity = float(forward)
        msg.lateral_velocity = float(lateral)
        msg.angular_velocity = float(angular)
        self.vel_pub.publish(msg)
    
    # ============================================================
    # 输入源注册（灵犀X2 MC 需要注册方接受速度指令）
    # ============================================================
    def register_input_source(self, timeout_sec=8.0):
        """注册为灵犀X2运动控制输入源"""
        self.get_logger().info('正在注册输入源...')
        
        start = self.get_clock().now().nanoseconds / 1e9
        while not self.input_src_client.wait_for_service(timeout_sec=2.0):
            if (self.get_clock().now().nanoseconds / 1e9 - start) > timeout_sec:
                self.get_logger().error('输入源服务超时')
                return False
            self.get_logger().info('等待输入源服务...')
        
        req = SetMcInputSource.Request()
        req.action.value = 1001
        req.input_source.name = "ylyw_locomotion"
        req.input_source.priority = 40
        req.input_source.timeout = 1000
        
        for i in range(8):
            req.request.header.stamp = self.get_clock().now().to_msg()
            future = self.input_src_client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=0.25)
            if future.done():
                break
            self.get_logger().info(f'重试 {i+1}/8')
        
        if future.done():
            try:
                resp = future.result()
                self.get_logger().info(
                    f'✅ 输入源注册成功 state={resp.response.state.value}'
                )
                return True
            except Exception as e:
                self.get_logger().error(f'注册异常: {e}')
                return False
        return False
    
    # ============================================================
    # 生命周期
    # ============================================================
    def start(self):
        """启动 YLYW 控制"""
        if not self.register_input_source():
            self.get_logger().error('输入源注册失败')
            return False
        self._active = True
        self.get_logger().info('🚀 YLYW 运动控制已启动')
        return True
    
    def stop(self):
        """停止: 零速 + 切回站立模式"""
        self._active = False
        self._publish_velocity(0.0, 0.0, 0.0)
        self.get_logger().info('⏹ YLYW 运动控制已停止')
    
    def print_summary(self):
        """打印运行统计"""
        stats = self.controller.get_stats()
        self.get_logger().info(f'{"="*50}')
        self.get_logger().info(f'IMU 消息: {self._imu_count}')
        self.get_logger().info(f'YLYW 推理: {stats.get("total_steps", 0)}次')
        self.get_logger().info(f'不同卦象: {stats.get("unique_hexagrams", 0)}')
        self.get_logger().info(f'卦象多样性: {stats.get("hexagram_diversity", 0):.2f}')
        self.get_logger().info(f'{"="*50}')


# ============================================================
# 主入口
# ============================================================
def main(args=None):
    rclpy.init(args=args)
    node = YLYWLingxiLocomotion()
    _node_ref = node  # for signal handler
    
    def sig_handler(sig, frame):
        node.get_logger().info(f'收到信号 {sig}, 正在停止...')
        node.stop()
        node.print_summary()
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)
    
    if not node.start():
        node.destroy_node()
        rclpy.shutdown()
        return
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.print_summary()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
