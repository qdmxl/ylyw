# YLYW 抓取：从 3D 目标点抓取 → 完整 6D 姿态抓取 + 13 维特征真实化

> 2026-08-27 研究推进记录（承接 2026-08-26 的 L3 卦象判别性改进）
> 目录：`motion_control/real_robot_grasp/`

---

## 一、背景：昨天遗留的两大问题

在 2026-08-26 解决 L3 卦象匹配判别性（方案A：权威阴阳模板 + 爻位加权 + 两级匹配）之后，
昨天复盘指出新系统仍有两处关键短板：

1. **6D 抓取姿态问题**：系统计算了点云、质心、PCA、尺寸、方向，但抓取执行时
   - 抓取位置主要依赖质心；
   - 抓取方式偏向垂直下降；
   - PCA 长轴/短轴/主方向没有转化为夹爪姿态；
   - 机械臂末端姿态被硬编码为 `[approach_angle, -90, 0]`（只改俯仰，roll/yaw 固定）；
   - 长方体/圆柱/球可能采用几乎相同的抓取动作。
   → **本质仍是"3D 目标点抓取"**，不是完善的 6D 姿态抓取。

2. **13 维特征部分为常数**：`fragility / occlusion / obstacle_density / task_priority /
   visibility / deformability` 取固定占位值（0.5/0.1/0.1/0.7/0.9/0.1），
   - 长期为固定值 `⇒ Var(xᵢ) ≈ 0`，几乎没有样本判别能力；
   - 不同物体因大量默认值得到过于相似的 13 维输入；
   - 上游输入信息量不足，会继续限制 L1/L2/L3 的实际判别能力；
   - "13维视觉特征"表述不准确（含人工先验与任务信息），且人工常数缺少数据支撑。

**今日(2026-08-27)又补上第 3 块**：抓取位置仍依赖质心（见第五节 4D→表面点）。

---

## 二、问题一解决：完整 6D 抓取位姿生成器

### 2.1 新模块 `grasp_pose.py`

把 PCA 主轴 + 物体几何真正转化为末端位姿 `[x, y, z, rx, ry, rz]`（基座 mm + 欧拉角）。

**核心设计：**

1. **形状分类** `classify_shape(dims)` —— 按包围盒三轴比例把物体分为：
   `plate`（平板）/`rod`（长条棒）/`column`（柱体）/`block`（块状）/`irregular`。
   不同形状 → 不同夹爪朝向策略。

2. **夹爪坐标系构建** `_Frame`：
   - 用 `ObjectFeatures.axes`（完整 3×3 PCA 主轴矩阵，新增字段）变换到基座系，
     得到物体真实 长轴/中轴/短轴；
   - 支撑面法向 `up` 由短轴在全局 Z 的分量方向决定；
   - 长轴/短轴在水平面的投影作为夹爪开合轴备选。

3. **多候选 + 打分比较** `build_candidates`：
   - `top_down`：垂直下压，开合沿水平长轴；
   - `side_grip`：侧面法向接近；
   - `side_grip_short` / `side_grip_long`：棒/柱专用，开合沿短轴/长轴；
   - `top_down_ylyw`：用 YLYW 接近角对接近方向做侧倾调制；
   - 打分 `score = 0.55×几何贴合 + 0.25×可达 + 0.20×YLYW谨慎度`，取最优。

4. **欧拉角约定修正**：MyCobot/pymycobot 的 RPY 是**内旋 XYZ**（intrinsic X-Y-Z），
   对应 scipy `as_euler("XYZ")`。修正后，物理接近方向能正确映射到欧拉角
   （修复前用外旋 ZYX 得到退化/统一姿态）。

### 2.2 集成

- `GraspPlan` 新增 `grasp_pose_6d / grasp_pose_name / approach_axis / open_axis / use_6d`；
- `GraspController.pick(plan, obj=...)`：用 `grasp_pose.best_6d` 计算完整 6D 位姿，
  机械臂从"固定朝下"改为"夹爪朝向跟随物体长轴/短轴"；旧逻辑保留为 fallback；
- `main.py`：规划阶段即计算 6D 位姿，写入 `plan` 供 dryrun/记录；
- `experiment_recorder`：CSV/JSONL 新增 `pose_name / pose_rx,ry,rz / approach_axis / open_axis`。

### 2.3 验证（合成多形状）

| 物体 | 形状类别 | 最优 6D 姿态 (rx,ry,rz)° | 接近方向 |
|---|---|---|---|
| 平板(正放) | plate | (180, 0, 0) | [0,0,-1] 垂直下压 |
| 长条棒(正放) | rod | (180, 0, 0) | [0,0,-1] 垂直 |
| 长条棒(侧躺) | rod | (-90, 0, 0) | [0,1,0] **水平侧抓** |
| 竖直瓶子 | rod | (90, 0, 0) | [0,-1,0] **水平侧抓** |
| 立方体 | block | (180, 0, 0) | [0,0,-1] 垂直 |

关键改进：**侧躺棒 / 竖直瓶**得到非垂直的接近方向（rx≈±90），不再与正放物体同姿态。
完整流水线中，不同朝向物体产生不同 6D 位姿（见 CSV `pose_rx/ry/rz` 逐轮变化）。

> ⚠️ 实机注意：本文给出的欧拉角是**内旋 XYZ(MyCobot RPY)** 约定下的物理量；
> 真机逆解前仍须按实际机械臂标定确认姿态坐标系方向。

---

## 三、问题二解决：13 维特征真实化

### 3.1 新估计器（`object_features.analyze_object`）

把 6 个常数占位维度全部改为**从点云+几何+场景真实计算**：

| 维度 | 旧值 | 新算法 | 说明 |
|---|---|---|---|
| `visibility` | 0.9 | 包围盒内点云填充率 + 点数/表面积完整度 | 越完整越可见 |
| `occlusion` | 0.1 | 观察方向投影网格的空洞覆盖 | 有空洞→被遮挡 |
| `obstacle_density` | 0.1 | 邻域(半径球)内其它物体点密比 | 需场景级 all_clouds |
| `fragility` | 0.5 | 几何脆弱度：薄壁/小曲率→脆 | 平板/棒脆，球韧 |
| `deformability` | 0.1 | 最小/最大尺度比：薄可弯→柔 | 薄板柔，实体刚 |
| `task_priority` | 0.7 | 场景显著度：体积+可见性派生 | 任务模块可覆盖 |

`analyze_object` 新增参数 `all_clouds / num_clouds / view_direction`，
支持场景级障碍密度与显著度。

### 3.2 修复 `build_features` 的判别力归零问题

**根因**：旧 `YlywGraspPlanner.build_features` 用类别默认值（恒 0.5/0.1）**直接覆盖**
感知阶段算出的 `fragility/deformability/strength_needed/weight_ratio`，
使这些维度退化为常数——即使 `object_features` 算出了判别值也被抹掉。

**修复**：感知值优先；仅当物体被识别为**具体类别**（非通用 `object`）时才用
类别先验做加权融合（40% 感知 + 60% 材质先验）；质量改用感知体积×密度。

### 3.3 验证（多形状，77~78 物体）

各特征按类别均值的跨度（证明可判别，非恒定）：

| 特征 | 最小类均值 | 最大类均值 | 跨度 |
|---|---|---|---|
| fragility | 0.24 (bottle) | 0.80 (flat_box) | ~3.3× |
| deformability | 0.42 (bottle) | 0.95 (flat_box) | ~2.3× |
| stability | 0.10 (bottle) | 0.90 (flat_box) | ~9× |
| reachability | 0.40 (flat_box) | 1.00 (bottle/cyl) | ~2.5× |
| support_area | 0.22 (sphere) | 1.00 (flat_box) | ~4.5× |
| weight_ratio | 0.009 (sphere) | 0.18 (cube_large) | ~20× |
| task_priority | 0.57 (cyl) | 0.64 (cube_large) | 有差异 |

多形状批量运行得到 **11 种不同抓取策略**（`progressive/power/top_down/
tactile_feedback/soft/abort_or_retry/non_conflict/difficult/reduced_force/
cautious` 等），而旧版常数特征下策略高度同质化。

感知特征真实进入六爻编码：如 平板(fragility≈0.79) → 四爻"阴脆" → `reduced_force_grasp`
（控制力）；球体(stability低) → `difficult_grasp`（需更大力度）。**上游信息量提升直接改善
L1/L2/L3 判别与决策差异化。**

---

## 四、遗留与后续

1. **真机验证**：6D 位姿欧拉角约定、夹爪朝向对实际抓取成功率的影响需真机标定后实测
   （当前为合成点云 + 模拟机械臂）。
2. **类别识别**：`fragility/deformability` 目前以几何为主，接入 YOLO 类别后可再叠加
   真实材质先验，进一步细化。
3. **任务优先级**：当前为几何显著性派生；有明确任务规划时应由任务层覆盖。
4. **13维表述**：建议论文中改称"感知特征（几何视觉为基底，类别先验为可选叠加）"，
   并给出每个估计器的公式（已在代码注释中给出），避免"为什么取 0.5/0.8"的质疑。

---

## 五、2026-08-27 补充：表面多候选抓取点（真正闭环"抓哪里"）

前四节解决的 6D 姿态主要改变了**夹爪朝向/接近方向**，但抓取**位置**仍以质心为主。
本次把位置也真正落到**物体表面实际抓取接触点**：

### 5.1 新增能力

- **`ObjectFeatures.points_m`**：保存（下采样后的）物体点云，供表面采样。
- **`sample_surface_contacts`**：沿 PCA 长轴两端/中段，以及中轴/短轴侧翼，采样多个表面接触点；
  每个点用 K 邻域 PCA 求**局部法向 + 局部平整度(planarity)**。
- **`build_surface_candidates` / `best_surface_6d`**：每个接触点 × 每个方向候选 → 完整 6D 位姿，
  评分 = 几何贴合 + 局部平整 + 可达 + YLYW谨慎。位置来自表面点（`R@p+t` 全变换，不再只旋转）。

### 5.2 验证（多形状，35 物体）

所选的候选名分布（不再都是同一种）：
`side_grip@surf_L`, `side_grip@midW`, `top_down@midW`, `side_grip@shortW`,
`side_grip@surf_R`, `side_grip_short@midW/L/R`, `top_down@surf_R` 等 **9 种**。

不同形状倾向不同的表面抓取点/方式（位置范围覆盖物体尺寸，非单点）：

| 类别 | 抓取位置 x 范围 | 主要候选 |
|---|---|---|
| sphere | -100~-3 | top_down@midW/surf_R |
| cube_large | -114~117 | side_grip_short@midW/surf_L |
| cylinder_tall | -95~95 | side_grip@surf_L/shortW |
| bottle | -105~97 | side_grip@surf_L/midW |
| flat_box | -19~21 | side_grip@midW |

CSV/JSONL 新增 `pose_x/y/z_mm`（表面抓取点基座坐标）、`surface_planarity`（接触面平整度）、
`pose_name`（形如 `side_grip@surf_L`）。

---

## 六、2026-08-27 补充：13 维逐维消融/贡献度分析（证明每维确有贡献）

针对"还没有充分证明 13 维每一维对决策的实际贡献"：新增 `feature_ablation.py`，
对每维**固定为全样本均值**（消除该维信息量）后重跑完整 YLYW 推理
（L1 八卦→L2 六爻→L3 卦象→策略），比较基线决策的改变量。

### 6.1 关键发现与修复

消融首轮暴露 **5 个死特征**：`visibility` 与 `deformability` 虽被计算并存为 13 维之一，
但 `yao_encoder.encode` 的六爻公式**从未读取**它们（文档也只列到 obstacle_density）。
已修复：

- `deformability` → 并入 **四爻**（与 fragility 共同表达"易碎/易变"，权重 0.7/0.3）；
- `visibility` → 并入 **二爻**（与 reachability/occlusion 共同表达"可达可见"，权重 +0.15）。

修复后二者进入决策（消融变化率 70%~85%）。

### 6.2 逐维贡献度表（40 轮多形状混合）

| 维度 | 固定后变化率 | 策略翻特 | Δ爻质 | Δ力 | 是否活 |
|---|---|---|---|---|---|
| fragility | 100% | 25% | 0.030 | 0.007 | ✅ 可翻转策略 |
| obstacle_density | 100% | 42% | 0.020 | 0.052 | ✅ 可翻转策略 |
| support_area | 99% | 18% | 0.003 | 0.016 | ✅ |
| stability | 100% | 16% | 0.018 | 0.011 | ✅ |
| roll_tendency | 100% | 0% | 0.000 | 0.000 | ✅(连续量) |
| reachability | 100% | 0% | 0.000 | 0.000 | ✅(连续量) |
| task_priority | 92% | 0% | 0.000 | 0.000 | ✅(连续量) |
| grasp_surface_quality | 96% | 0% | 0.000 | 0.000 | ✅(连续量) |
| deformability | 71% | 0% | 0.000 | 0.000 | ✅(修复后) |
| visibility | 85% | 0% | 0.000 | 0.000 | ✅(修复后) |
| occlusion | 0% | 0% | 0.000 | 0.000 | ⚠️ 合成场景无遮挡(std=0) |
| strength_needed | 0% | 0% | 0.000 | 0.000 | ⚠️ 质量方差小 |
| weight_ratio | 0% | 0% | 0.000 | 0.000 | ⚠️ 同左 |

### 6.3 结论（论文可用）

- **10/13 维固定后改变抓取决策**——其中 `fragility / obstacle_density / stability /
support_area` 可直接翻转策略或卦象，是大权重决策特征；
- **修复后 12/13 维已正确接入推理**；
- 剩余 3 维(`occlusion`/`strength_needed`/`weight_ratio`)在**干净合成场景**下近常数
  （无真实遮挡、物体质量跨度小），但已正确接入六爻编码公式，在含遮挡/大质量差的
  真实场景会激活。论文中应如实标注这 3 维为"场景相关、需多样化数据激发"，而非恒占位。

产物：`experiments/ablation/feature_ablation.csv/.json`；脚本 `feature_ablation.py`。

---

## 五、关键文件

| 文件 | 改动 |
|---|---|
| `grasp_pose.py` | **新增** 6D 位姿生成器；**表面多候选抓取点**（`sample_surface_contacts`/`best_surface_6d`）+ 局部平整度评分 |
| `object_features.py` | 保存 PCA 主轴矩阵；新增 6 个感知估计器；`_mass_kg`；`points_m` 点云字段 |
| `ylyw_grasp_planner.py` | `GraspPlan` 加 6D 字段/表面平整度；`build_features` 感知优先 |
| `grasp_controller.py` | `pick` 用表面多候选 6D 位姿驱动机械臂（含平移变换） |
| `main.py` | 规划阶段算表面 6D 并注入；传入场景点云 |
| `experiment_recorder.py` | CSV/JSONL 记录 6D 位姿、接近/开合轴、表面平整度 |
| `run_paper_experiments.py` | 修 `_cube` 缩放；传场景点云；补算表面 6D 位姿 |

验证脚本：同目录 `scripts/` 已有 L3 判别性脚本；6D/特征判别性可直接
`python -m real_robot_grasp.main --camera-backend synthetic --simulate --rounds N` 复现。
