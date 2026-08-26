# 真实机械臂 + 深度相机 + YLYW 易理模型 —— 多物体任意抓取系统

位于：`motion_control/real_robot_grasp/`

这是基于参考实例（`motion_control/elephant/…/识别随机位置蓝色方块并自动抓取`）开发的一套
**面向真实机械臂的完整抓取控制程序**，创新点在于：

1. **深度相机**（RealSense 优先，OpenCV 回退，合成模式便于无硬件联调）实现**物体特征分析**
   —— 点云分割、尺寸/6D位姿/质心/曲率/质量估计，输出 YLYW 可用的 13 维感知特征。
2. **YLYW 易理模型**实现**抓取动作规划** —— 深度特征 → 八卦隶属度(L1) → 六爻编码(L2) →
   六十四卦匹配(L3) → 爻位关系(L3+) → 抓取策略(类型/力/接近角/速度/夹紧值)。
3. **多物体任意抓取** —— 每轮自动检测多个物体、YLYW 各自规划、逐次抓取。
4. **实验数据记录** —— CSV + JSONL + 分析图，为抓取论文补充定量数据。

---

## 目录结构

```
real_robot_grasp/
├── config.py               # 全部配置(相机/机械臂/YLYW/抓取安全)
├── depth_camera.py         # 深度相机: 彩色/深度 → 点云 (realsense/opencv/synthetic)
├── object_features.py      # 物体特征分析: 分割/尺寸/质心/曲率/6D/13维特征
├── ylyw_grasp_planner.py   # YLYW 易理抓取规划: 特征→卦象→策略→抓取参数
├── robot_arm.py            # MyCobot 280 安全执行器(运动/逆解/夹爪/模拟)
├── coordinate_transform.py # 相机→机械臂基座 坐标变换(手眼标定)
├── grasp_controller.py     # 抓取动作序列(接近/下降/夹紧/抬升/放置)
├── experiment_recorder.py  # 实验记录(CSV/JSONL/汇总)
├── main.py                 # 主流程: 多物体任意抓取循环
├── dev_demo.py             # 无硬件的流水线联调(合成点云)
└── run_paper_experiments.py# 论文实验数据生成(批量场景+统计+分析图)
```

---

## 依赖

```bash
pip install numpy opencv-python pyserial scipy matplotlib
pip install ultralytics        # 可选，目标类别识别
pip install pymycobot          # MyCobot 280 机械臂
pip install pyrealsense2       # 深度相机(可选，可用 opencv/synthetic 替代)
```

YLYW 先验手册 (`ylyw_core`) 复用项目现有副本，路径在 `YlywConfig.ylyw_core_path`
(默认 `…/ylyw/api_docs`)。无需额外安装。

---

## 快速开始（无硬件联调）

合成相机 + 模拟机械臂，验证整条流水线并生成示例数据：

```bash
cd /home/lijinhan/MXL/科研/ylyw/motion_control

# 1. 完整流水线(含模拟抓取执行)
python3 -m real_robot_grasp.main --camera-backend synthetic --simulate --rounds 3 --verbose

# 2. 仅感知+YLYW规划(不执行机械臂，论文数据采集用)
python3 -m real_robot_grasp.main --camera-backend synthetic --dryrun --rounds 3 --verbose

# 3. 批量论文实验数据
python3 real_robot_grasp/run_paper_experiments.py --rounds 30 --seed 2026

# 4. 单条流水线联调(合成点云)
python3 real_robot_grasp/dev_demo.py
```

输出位置（默认）：
- 单次正常抓取：`real_robot_grasp/experiments/`
- 论文批量：`real_robot_grasp/experiments/paper/`
  - `grasp_experiments.csv`：扁平统计表
  - `grasp_reasoning.jsonl`：完整推理链(每轮一行)
  - `paper_rows.json`：详细记录
  - `ylyw_grasp_analysis.png`：卦象/策略分布图

---

## 真实硬件使用

```bash
# Linux (Arduino 版 MyCobot 280, 波特率 1_000_000)
python3 -m real_robot_grasp.main --camera-backend realsense \
    --port /dev/ttyUSB0 --baudrate 1000000 --rounds 10

# Windows (M5 版, 波特率 115200)
python3 -m real_robot_grasp.main --camera-backend realsense \
    --port COM3 --baudrate 115200 --rounds 10

# 指定抓取某类物体(可选；否则自动任意抓取)
python3 -m real_robot_grasp.main --target bottle --rounds 10
```

**部署前必做**：

1. **手眼标定**：把相机拍到目标的点换成机械臂基座坐标。
   生成示例标定文件：
   ```python
   from real_robot_grasp.coordinate_transform import save_example_calibration
   save_example_calibration("calibration")   # 生成 hand_eye_example.json
   ```
   用 OpenCV `solvePnP`/手眼标定工具替换 `R,t`，再 `--calibration <file>` 传入。
   ⚠️ 默认 `from_overhead` 只是占位，抓取高度(Z)需标定后落在机械臂工作区(约140–220mm)。
2. **夹爪/机械臂验证**：先跑 `--dryrun` 确认规划正确，再 `--simulate` 复盘动作，
   最后接真机。真机应预留急停断电。

---

## YLYW 推理链（论文重点）

```
物体深度特征(13维)
  │  L1 八卦隶属度      —— α动/坤顺/震速/艮止/离明/坎险/兑悦/巽入
  │  L2 六爻编码        —— 初爻(稳定)/二爻(可达)/三爻(力)/四爻(脆弱)/五爻(优先级)/上爻(环境)
  │  L3 六十四卦匹配    —— 卦象 + 匹配度 + Top3
  │  L3+ 爻位关系       —— 当位/得中/乘承比应 → 谨慎度、力修正×modifier
  ▼
抓取策略 {type, force, approach_angle, speed, cautions}
  │  参数化
  ▼
机械臂抓取参数 {接近方式, 夹紧值, 速度档, 运动序列}
```

例如合成方块场景得到：
- 卦象 **风雷益**，抓取类型 `progressive_grasp`(从轻到重逐步加力)，力 0.40
- 卦象 **地泽临**，抓取类型 `top_down_grasp`(正上方垂直抓取)，力 0.45
- 卦象 **火山旅**，抓取类型 `conditional_grasp`(适应环境动态调整)，力 0.50

---

## 实验数据字段（CSV）

`round, timestamp, label, success, dim_l_mm, dim_w_mm, dim_h_mm, curvature,
volume_cm3, grasp_x_mm, y, z, dominant_trigram, hexagram, hexagram_cn,
hexagram_score, yin_yang, yao_quality, caution_level, strategy_type, force,
approach_angle_deg, speed_level, close_value, duration_s`

---

## L3 卦象匹配：权威阴阳模板 + 爻位加权（方案A）

2026-08 更新。对 `ylyw_core/hexagram_rules.py` 的 L3 匹配做了判别性改进
（同步到 `api_docs / prior_manual / x2/ylyw_full_pipeline / x2/ylyw_hand_deploy /
experiment_phase1` 五处副本）：

- **旧实现（纯余弦 + 窄带浮点模板）问题**：64 卦模板两两余弦相似度均值 0.879，
  top1−top2 分数差仅 ~0.001（噪声级），±0.03 特征噪声下近半数输入卦象跳变。
- **新实现（方案A）**：
  1. 模板改为**权威《周易》阴阳模板**（阳=1/阴=0），从卦象符号上下卦组合推导
     （六爻 = 下卦三爻 + 上卦三爻），64 卦零重复、可分性强。
  2. **爻位加权**：得中的二爻、五爻权重更高（呼应 L3+ 得中思想）。
  3. **两级匹配**：阶段一加权汉明粗选 → 阶段二连续爻值精细排序打破并列。
- **实测对照（400 合成输入）**：
  | 指标 | 改前 | 改后 |
  |---|---|---|
  | 模板两两相似度均值 | 0.879 | 0.464 |
  | top1−top2 分数差均值 | 0.0013 | 0.1136 |
  | 明确胜出(>0.05)占比 | 0.0% | 100% |
  | ±0.03 扰动跳变率 | 47.3% | 0.0% |

验证脚本：`scripts/l3_discriminability.py`（当前实现判别性）、
`scripts/l3_schemeA_final.py`（方案A开发对比）。

---

## 说明与局限

- `synthetic` 相机与 `--simulate` 臂用于无硬件联调和论文预研；
  真实实验结果请以真机反馈为准。
- `run_paper_experiments --success-rate` 用于生成"假设成功率"下的预研数据；
  正式论文应使用真机实测成功率。
- 物体分类默认统一为 `object`；接入 YOLO 后可按类别覆盖 fragile/质量等先验
  （见 `YlywGraspPlanner._build_class_maps`）。
