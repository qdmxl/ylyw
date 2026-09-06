# MicroDuck —— ylyw 算法验证仿真基座

把 [pollen-robotics/microduck](https://github.com/pollen-robotics/microduck) 这只
双足鸭形机器人(25cm / ~800g,14 舵机构直接驱动 MuJoCo MJCF)的 **仿真本体** 提取出来,
在 **CPU / 无 GPU** 的 MuJoCo 3 上搭成可自给运行的环境,用来验证 ylyw(易理模糊模型)
的运动/步态/平衡算法。

- **核心结论已打通**:环境可加载、复位、按关节目标驱动、站立保持稳定、小扰动可自行恢复。
- **诚实提示**:要想“走得起来”,需要 ylyw 提供带主动平衡/质心控制的高层控制器,
  开环摆腿(无平衡)会真实地倒 —— 这正是环境的价值:让算法在真实双足动力学上迭代。
- **在线文档**:见 `sim/README.md`(结构、关节布局、快速开始、ylyw 接入示例)。

## 目录

```
MicroDuck/
├── microduck_rl/     # 官方 RL 训练仓库(只读参考;训练需 GPU,本基座不依赖)
└── sim/              # ★ 本项目:CPU 可跑的自给仿真 + ylyw 接入点
  ├── env/            环境核心(microduck_env.py)
  ├── models/         官方 MJCF + 精简资产; _ylyw_control_* 为自动生成的可平衡模型
  ├── scripts/        demo_stand / demo_balance / draw_state(无GUI成图)
  ├── data/           渲染 PNG 输出
  └── ylyw_algos/     放你的 ylyw 策略(见 example.py)
```

## 快速跑 (在 MicroDuck/sim 下)

```bash
pip install mujoco numpy lxml trimesh matplotlib
python scripts/demo_stand.py            # 站立 PASS 自检
python scripts/demo_balance.py          # 推力扰动恢复评估
python scripts/draw_state.py --precache && python scripts/draw_state.py --key STAND
```

License note: geometry/XML/per-model code 源自官方 Apache-2.0 项目;其中 3D 模型为
CC BY-SA-NC,仅供本机科研用。
