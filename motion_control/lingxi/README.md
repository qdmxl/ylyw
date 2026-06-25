# YLYW → 灵犀X2 运动控制适配层

## 文件结构

```
lingxi/
├── __init__.py                  # 包初始化
├── launch_lingxi_sim.py         # PyBullet 仿真（本机运行）
│   ├── SimulatedIMU             # 模拟灵犀X2胸部IMU传感器
│   ├── IMUtoState               # IMU → YLYW 6维状态映射器
│   ├── GaitToVelocity           # YLYW步态 → 灵犀X2速度指令
│   └── run_simulation()         # 主仿真循环
└── ylyw_lingxi_locomotion.py    # ROS2 适配器（部署到灵犀X2）
    └── YLYWLingxiLocomotion     # ROS2节点：IMU→YLYW→Velocity指令
```

## 仿真运行 (PyBullet)

在 VirtualBox / 本机运行，无需 ROS2：

```bash
cd /home/lijinhan/MXL/科研/ylyw/motion_control/lingxi
python3 launch_lingxi_sim.py --duration 60
```

### 仿真功能

- **IMU 模拟**：根据步态速度产生真实的姿态摆动（roll/pitch）、角速度、垂直加速度
- **闭环推理**：模拟IMU → 6D状态 → YLYW → 步态 → 速度指令 → 动画
- **扰动注入**：10s/20s/35s 自动注入侧向推力，测试抗扰恢复
- **安全兜底**：倾角过大时强制降速/停止
- **实时显示**：黄色文字显示卦象+步态+速度

### 数据流

```
机器人运动 → SimulatedIMU → IMU数据(quat/gyro/accel)
    → IMUtoState.convert() → [posture,com_h,force_dist,zmp,disturbance,terrain]
    → YLYWLocomotionController.infer() → gait_params
    → GaitToVelocity.convert() → {forward,lateral,angular}_velocity
    → PyBullet动画
```

## 实物部署 (灵犀X2)

将 `ylyw_lingxi_locomotion.py` 拷贝到灵犀X2机载计算平台：

```bash
# 灵犀X2上运行
python3 ylyw_lingxi_locomotion.py
```

### 前提条件

- ROS2 Humble
- aimdk_msgs (灵犀X2 SDK消息包)
- IMU topic: `/aima/hal/imu/chest/state`

### 实物数据流

```
灵犀X2 IMU(sensor_msgs/Imu, 100Hz)
    → IMU→6D状态 (同仿真映射器)
    → YLYW推理 (10Hz)
    → McLocomotionVelocity (50Hz发布)
    → /aima/mc/locomotion/velocity
    → 灵犀X2 MC 执行
```

### 安全机制

1. **倾角三级保护**：
   - tilt > 0.4rad (23°): 速度减半 + 警告
   - tilt > 0.7rad (40°): 强制停止
2. **Ctrl+C 安全退出**：零速 + 打印统计
3. **无IMU数据保护**：超时自动零速

## 速度映射表

| YLYW 步态 | 灵犀X2 速度 (m/s) |
|-----------|:--:|
| 静止站立 | 0.0 |
| 慢走 | 0.25 |
| 谨慎行走 | 0.22 |
| 正常行走 | 0.45 |
| 快速行走 | 0.70 |
| 小跑步态 | 0.85 |
| 奔跑 | 1.0 |
| 恢复步态 | 0.0 |

## 仿真 vs 实物对比

| | 仿真 (PyBullet) | 实物 (灵犀X2) |
|------|------|------|
| IMU来源 | 步态参数模拟 | 真实胸部IMU |
| 推理引擎 | 相同 YLYW | 相同 YLYW |
| 输出格式 | 相同速度指令 | 相同速度指令 |
| 接口 | 直接函数调用 | ROS2 topic |
| 依赖 | PyBullet | ROS2 + aimdk_msgs |
