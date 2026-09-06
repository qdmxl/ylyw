# MicroDuck 仿真基座 —— ylyw 算法验证环境 (CPU / 无 GPU)

把 [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck) 这只 ~25cm / ~800g
双足鸭形机器人(from MuJoCo MJCF)在本机 **CPU-only** 场景下搭成一个轻量仿真,
作为 ylyw(易理模糊模型)运动/步态/平衡类算法的**验证沙盒**。

## 目录结构

```
MicroDuck/
├── microduck_rl/        # 官方训练仓库(已克隆只读,做参考,含任务/奖励/导出)
└── sim/                 # ★ 本项目:CPU 可跑的自给仿真
    ├── README.md
    ├── env/
    │   ├── __init__.py
    │   └── microduck_env.py        # 环境核心类
    ├── models/microduck/           # MJCF + 精简后 assets(stl 副本)
    │   ├── robot_walk.xml          # 官方几何/关节模型(只读原始)
    │   ├── _ylyw_control_robot.xml # 生成:重写执行器增益(可稳定站立)
    │   └── _ylyw_control_scene.xml # 生成:含地面的 scene wrapper
    ├── cache/microduck_meshes.npz  # 低模缓存(可视化)
    ├── data/                        # 输出 PNG / 轨迹
    ├── scripts/
    │   ├── demo_stand.py           # 站立保持 PASS 自检
    │   ├── demo_balance.py         # 推力扰动 → 恢复评估
    │   ├── draw_state.py           # headless 网格/点云成图(不需 OpenGL)
    │   └── render_shot.py          # (需 GL,预留)
    └── ylyw_algos/                  # ★ 放你的 ylyw 算法调用端
```

## 为什么有 `_ylyw_control_*.xml`?

官方 `microduck_rl` 在 **MuJoCo Warp(GPU)+ BAM 电压控制执行器**下训练,仓库自带的
`robot_*.xml` 里那组 XML 位置执行器(kp≈0.55, forcerange±0.96)是很老的弱 PD 残留,
不足以让鸭子站住(仅用于几何/运动学结构)。

我们**不改几何、质量、关节、自由度**,只重写执行器增益(kp=60, kv=4, ±3 N·m),
得到 CPU 上能稳定跟踪关节目标、能站住的控制友好模型。这用于验证 ylyw 的
**控制结构与步态/姿态决策逻辑**;若日后要真机 sim2real,再接官方 BAM(GPU)。

> 每次模型文件变化后删除 `models/microduck/_ylyw_control_*.xml` 再跑会自动重生,
> 或 `ensure_control_model(force=True)`。

## 关节布局(与官方动作/观测契约一致)

14 个执行关节,顺序如下(经实测与官方 mj_model actuator 顺序逐一核对):
```
 0 left_hip_yaw    1 left_hip_roll   2 left_hip_pitch  3 left_knee    4 left_ankle
 5 neck_pitch      6 head_pitch      7 head_yaw        8 head_roll
 9 right_hip_yaw  10 right_hip_roll 11 right_hip_pitch 12 right_knee  13 right_ankle
```
HOME(站立)目标(弧度): hip_yaw=0, hip_roll=∓0.0873, hip_pitch=∓0.458,
knee=∓0.005, ankle=±0.453, neck/head_pitch=0.349, 头 yaw/roll=0
(左腿带负号/右腿正号按左右)。

关键帧: `INIT / STAND / SIT / FOLD`(scene keyframes 已带全 qpos+ctrl)。

## 快速开始

```bash
pip install mujoco numpy lxml trimesh matplotlib   # numpy 已有

cd MicroDuck/sim

# 1) 生成控制友好模型并做 4s 站立自检(应 PASS)
python scripts/demo_stand.py

# 2) 抗扰评估:施加前向冲量 0.4 m/s,观察 hold-stand 控制器能否恢复
python scripts/demo_balance.py --push 0.4 --horizon 3.0

# 3) headless 渲染姿态帧(无 GUI 也能出图)
python scripts/draw_state.py --precache          # 一次性生成低模缓存
python scripts/draw_state.py --key STAND --out data/stand.png
python scripts/draw_state.py --key SIT   --out data/sit.png
```

## 在你代码(ylyw)里怎么用

```python
import numpy as np
from env.microduck_env import StandingEnv, ensure_control_model, SERVO_JOINTS, _HOME

HOME = np.array([_HOME[j] for j in SERVO_JOINTS])
env = StandingEnv(control_dt=0.02)     # 50Hz 控制
obs = env.reset("STAND")               # obs 43 维 (见 microduck_env.observe)

def my_ylyw_controller(env, obs, t):
    # 在这里放 ylyw 决策:根据 obs(状态) 输出 14 维关节目标角
    target = HOME.copy()
    # ...... ylyw 策略:步子相位(64卦/时序)→ 腿髋/膝/踝角增量
    return target

records, summary = env.run_gait_record(my_ylyw_controller, seconds=5.0)
print(summary)                          # {upright_frac, final_x, final_z, final_upright}
```

`obs(43,)` 布局 = `[base_pos(3), base_quat(4), lin_vel(3), ang_vel(3),
joint_pos(14), joint_vel(14), foot_l, foot_r]`。

## 已验证 / 已知事实(重要)

- ✅ CPU(MuJoCo 3.9)加载、复位 STAND、物理仿真均正常;关节/执行器顺序逐一核对正确。
- ✅ **静立保持 STABLE**:STAND 4s 躯干高≈0.116–0.12m,最大倾角~6°,漂移小。demo_stand PASS。
- ✅ **小扰恢复**:前向冲量 0.4 m/s,h=3s 一直保持竖直(final_upright=True)。
- ⚠️ **开环纯摆动(无主动平衡)会倒**:给 6s 交替摆腿而不用 CoM/平衡策略,鸭子向后倒
  (这是真实双足动力学;证明环境忠实,也说明*行走必须靠 ylyw 的主动平衡控制器来做*)。
- ℹ️ 足底碰撞 geom 略高于地面(~2.8mm),`foot_l/r` 触地标志会抖动;判断“站地/腾空”
  更稳妥的指标是 `trunk z` 与 CoM(见 `observe`/is_upright)。低模可视化为点云,仅示意结构。

## 关于官方观测量(给想对齐 RL 的人)

官方 61 维 actor 观测 = 48 本体感觉 + 命令(twist3 + head_pose4 + body_pose6),
本基座当前提供的是简化 43 维。若你的 ylyw 实验需要和官方 ONNX/策略横评观测对齐,
在 `microduck_rl/src/mjlab_microduck/tasks/mdp.py` 与 `microduck_velocity_env_cfg.py`
里参考官方组装逻辑,按需补齐即可(本基座不依赖其 GPU 栈)。

## 依赖 / 环境

- Python 3.14(实测)、mujoco 3.9、numpy、lxml;可视化另需 trimesh+matplotlib。
- 训练执行器(BAM/Warp)走官方 `microduck_rl`;本基座 CPU 全程可跑,无需 GPU。
- 许可证:模型/代码源自 Apache-2.0 官方项目(3D 模型 CC BY-SA-NC)。
