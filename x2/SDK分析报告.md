# 灵犀X2 SDK 分析报告

> 版本: lx2501_3-v0.9.0.4 | ROS2 Humble | 2026-06-02

---

## SDK 架构

```
灵犀X2 计算平台 (Ubuntu + ROS2 Humble)
│
├── aimdk_msgs (自定义消息包)
│   ├── HandCommandArray / HandCommand / HandType
│   ├── JointCommandArray / JointCommand / JointStateArray
│   └── 标准 sensor_msgs (Image, PointCloud2, CameraInfo)
│
├── ROS2 Topics
│   ├── /aima/hal/joint/hand/command      ← 灵巧手控制 (YLYW核心)
│   ├── /aima/hal/joint/arm/command       ← 手臂控制 (接近物体)
│   ├── /aima/hal/sensor/rgbd_head_front/ ← 视觉感知 (YLYW核心)
│   ├── /aima/hal/joint/*/state           ← 关节状态反馈
│   └── /aima/hal/sensor/imu/data         ← IMU数据
│
└── 软件依赖
    ├── rclpy (ROS2 Python)
    ├── ruckig (轨迹规划)
    └── numpy (计算)
```

---

## 关键接口 → YLYW 映射

### 1. 灵巧手控制 → YLYW 决策输出

| SDK 参数 | 类型 | YLYW 映射 |
|----------|------|-----------|
| `HandType` | 1=NIMBLE_HANDS / 2=Gripper | 使用 NIMBLE_HANDS (type=1) |
| `name` | 手指名 (left_thumb, left_index, ...) | 按策略分配手指组合 |
| `position` | float (0.0=闭合, 1.0=全开) | YLYW force_preset × modifier |
| `velocity` | float | YLYW speed (slow/0.3, medium/0.6, fast/1.0) |
| `effort` | float (力矩上限) | YLYW force_preset × modifier |

**话题**: `/aima/hal/joint/hand/command` (类型: `HandCommandArray`)
**发布频率**: 最高 50 Hz (20ms)

### 2. 手臂控制 → 接近物体

| 关节 | 运动范围 (rad) | 用途 |
|------|---------------|------|
| left_shoulder_pitch | -3.08 ~ 2.04 | 手臂前伸/后缩 |
| left_shoulder_roll | -0.061 ~ 2.993 | 手臂内外旋 |
| left_shoulder_yaw | -2.556 ~ 2.556 | 手臂左右摆 |
| left_elbow | -2.356 ~ 0 | 肘部屈伸 |
| left_wrist_yaw | -2.556 ~ 2.556 | 腕部左右转 |
| left_wrist_pitch | -0.558 ~ 0.558 | 腕部俯仰 |
| left_wrist_roll | -1.571 ~ 0.724 | 腕部旋转 |

**话题**: `/aima/hal/joint/arm/command` (类型: `JointCommandArray`)
**发布频率**: 最高 500 Hz (2ms)

### 3. 视觉感知 → YLYW L1 输入

| Topic | 类型 | 分辨率 | 用途 |
|-------|------|--------|------|
| `/aima/hal/sensor/rgbd_head_front/rgb_image` | sensor_msgs/Image | 待确认 (CameraInfo) | 材质/纹理识别 |
| `/aima/hal/sensor/rgbd_head_front/depth_image` | sensor_msgs/Image | 待确认 | 3D几何特征 |
| `/aima/hal/sensor/rgbd_head_front/depth_pointcloud` | sensor_msgs/PointCloud2 | 待确认 | 点云处理 |
| `/aima/hal/sensor/rgbd_head_front/rgb_camera_info` | sensor_msgs/CameraInfo | — | 内参标定 |

**QoS**: BEST_EFFORT, KEEP_LAST(5)

---

## YLYW 策略 → 灵巧手动作映射（细化版）

基于 NIMBLE_HANDS (10个手指电机，5指独立控制):

| YLYW 策略 | 拇指 | 食指 | 中指 | 无名指 | 小指 | position | velocity | effort |
|-----------|------|------|------|--------|------|----------|----------|--------|
| power_grasp (乾) | 0.85 | 0.85 | 0.85 | 0.85 | 0.85 | 0.0 | 1.0 | 0.85 |
| precise_pick (坤) | 0.40 | 0.40 | 0.05 | 0.05 | 0.05 | 0.0 | 0.3 | 0.25 |
| dynamic_grasp (震) | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | 0.0 | 1.0 | 0.70 |
| cautious_grasp (履) | 0.50 | 0.50 | 0.30 | 0.30 | 0.30 | 0.0 | 0.2 | 0.30 |
| adaptive_grasp (睽) | 0.70 | 0.40 | 0.70 | 0.40 | 0.70 | 0.0 | 0.5 | 0.50 |
| wrap_grasp (随) | 0.90 | 0.90 | 0.90 | 0.90 | 0.90 | 0.0 | 0.8 | 0.60 |
| incremental_grasp (渐) | 0.30→0.80 | 0.30→0.80 | 0.30→0.80 | 0.30→0.80 | 0.30→0.80 | 渐变 | 0.3 | 0.40 |
| conditional_grasp (需) | 0.60 | 0.60 | 0.60 | 0.60 | 0.60 | 0.0 | 0.5 | 0.50 |

**说明**:
- `position`: 手指开合度 (0.0=闭合, 1.0=全开)。这里给的是"张开预设"，灵巧手到达物体后闭合
- `velocity`: 手指运动速度 (对应 YLYW speed 等级)
- `effort`: 力矩上限 (对应 YLYW force_preset × modifier)

---

## 适配注意事项

1. **NIMBLE_HANDS (type=1)**: 必须指定全部10个手指的指令，即使某些手指不参与动作
2. **手臂必须先到位**: 在灵巧手抓取前，需要控制手臂将灵巧手送到抓取位置附近
3. **视觉与手臂坐标系**: 需要手眼标定，将相机坐标系的物体位置转换到手臂基座坐标系
4. **力控替代**: 如果灵巧手不支持直接力矩控制，用 `position` 控制夹紧程度，配合 `effort` 做力矩限制
5. **ROS2 通信**: 所有节点需要在机器人计算平台上运行（或通过网络与机器人通信）
