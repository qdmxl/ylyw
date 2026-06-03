#!/usr/bin/env python3
"""
YLYW → 学灵通机器人 串口适配器
通过USB转TTL连接机器人UART1，实时发送舵机角度
"""
import sys, os, time, struct, serial, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ylyw_locomotion import YLYWLocomotionController


class XLT_Robot:
    """学灵通机器人串口控制"""
    
    # 协议帧格式: 0xAA [24舵机角度] 0x55
    FRAME_HEAD = 0xAA
    FRAME_TAIL = 0x55
    FRAME_SIZE = 26  # 1头 + 24数据 + 1尾
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.controller = YLYWLocomotionController()
        
        # 舵机初始位置（中位=128）
        self.servo_positions = [128] * 24
        self.phase = 0
    
    def connect(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.5)
        print(f"✅ 连接机器人 {self.port} @ {self.baudrate}bps")
    
    def disconnect(self):
        if self.ser:
            self.ser.close()
    
    def send_angles(self, angles):
        """发送24舵机角度"""
        frame = bytearray([self.FRAME_HEAD])
        frame.extend(angles)
        frame.append(self.FRAME_TAIL)
        self.ser.write(frame)
    
    def ylyw_to_servo(self, gait_params):
        """
        YLYW步态参数 → 24舵机角度
        
        舵机映射（从basal.c注释推断）:
          0-5:   右腿(髋前后[0,2], 膝[1], 左腿髋[3,5], 膝[4])
          6-7:   未用
          8-11:  侧向平衡
          12-15: 双臂
          16-23: Z轴(踝等)
        """
        speed = gait_params['speed']
        freq = gait_params['freq']
        height = gait_params['step_height']
        
        ANGLE_MID = 128  # 中位
        ANGLE_RANGE = 60  # 最大摆幅
        
        angles = [ANGLE_MID] * 24
        
        if speed < 0.02:
            # 站立不动
            return angles
        
        # 相位推进
        self.phase += freq * 0.02 * 2 * np.pi
        self.phase %= 2 * np.pi
        
        # 步态参数 → 舵机摆幅
        hip_amp = int(ANGLE_RANGE * 0.5 * speed)
        knee_amp = int(ANGLE_RANGE * 0.3 * speed)
        
        # 左腿（相位=0时前摆）
        left_hip  = int(hip_amp * np.sin(self.phase))
        left_knee = int(knee_amp * max(0, np.sin(self.phase)))
        
        # 右腿（相位偏移π）
        right_hip  = int(hip_amp * np.sin(self.phase + np.pi))
        right_knee = int(knee_amp * max(0, np.sin(self.phase + np.pi)))
        
        # X轴舵机（髋前后）
        angles[0] = ANGLE_MID + right_hip  # 右髋
        angles[2] = ANGLE_MID + right_hip
        angles[3] = ANGLE_MID + left_hip   # 左髋
        angles[5] = ANGLE_MID + left_hip
        
        # 膝关节弯曲
        angles[1] = ANGLE_MID - right_knee
        angles[4] = ANGLE_MID - left_knee
        
        # 侧向平衡（速度越快越前倾）
        angles[8]  = ANGLE_MID + speed * 15
        angles[10] = ANGLE_MID - speed * 15
        
        return angles
    
    def run_demo(self, duration=60):
        """运行YLYW步态演示"""
        demo = [
            (0,  "初始站立", [0.90,0.82,0.75,0.88,0.05,0.82]),
            (5,  "开始慢走", [0.72,0.72,0.68,0.65,0.20,0.80]),
            (10, "加速行走", [0.65,0.70,0.65,0.60,0.30,0.78]),
            (16, "快速小跑", [0.55,0.72,0.72,0.50,0.52,0.76]),
            (22, "全力奔跑", [0.48,0.75,0.78,0.42,0.62,0.78]),
            (28, "急停恢复", [0.20,0.32,0.28,0.15,0.80,0.55]),
            (33, "减速站立", [0.88,0.78,0.72,0.85,0.10,0.80]),
        ]
        
        demo_idx = 0
        sim_time = 0
        dt = 0.05
        current_gait = None
        
        print(f"{'='*55}")
        print(f"YLYW → 学灵通机器人 步态演示")
        print(f"{'='*55}")
        
        try:
            while sim_time < duration:
                while demo_idx+1 < len(demo) and sim_time >= demo[demo_idx+1][0]:
                    demo_idx += 1
                name, dstate = demo[demo_idx][1], demo[demo_idx][2]
                
                current_gait = self.controller.infer(np.array(dstate), verbose=False)
                angles = self.ylyw_to_servo(current_gait)
                
                if self.ser:
                    self.send_angles(angles)
                else:
                    # 无串口时打印角度
                    if int(sim_time) % 2 == 0:
                        print(f"{sim_time:>4.1f}s {name:<8} {current_gait['hexagram_name']:<6} "
                              f"{current_gait['gait_name']:<8} "
                              f"Hip:[{angles[3]:>3},{angles[0]:>3}] Knee:[{angles[4]:>3},{angles[1]:>3}]")
                
                time.sleep(dt)
                sim_time += dt
                
        except KeyboardInterrupt:
            print("\n⏹ 停止")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='YLYW学灵通机器人控制')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='串口设备')
    parser.add_argument('--no-serial', action='store_true', help='不连接串口（仅打印）')
    parser.add_argument('--duration', type=int, default=45, help='演示时长(秒)')
    args = parser.parse_args()
    
    robot = XLT_Robot(port=args.port)
    
    if not args.no_serial:
        try:
            robot.connect()
        except Exception as e:
            print(f"⚠️  串口连接失败: {e}")
            print("使用 --no-serial 模式仅打印角度")
            robot.ser = None
    
    robot.run_demo(duration=args.duration)
    robot.disconnect()
