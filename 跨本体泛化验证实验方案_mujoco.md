# YLYW 跨本体泛化——MuJoCo 验证实验方案

> 基于 ICRA 2026 跨本体泛化三条技术路线分析
> 仿真引擎: MuJoCo 3.9.0
> 版本: v2.0-mujoco | 2026-06-28

---

## 一、实验目标（不变）

**核心假设 H0**: YLYW 的 64 卦符号系统可以作为跨本体的统一动作表示协议，在零训练数据条件下实现跨本体策略迁移。

---

## 二、选择的本体集合（基于现有 MuJoCo 模型）

充分利用已有模型 + 需要新建的模型：

### 2.1 已有模型 ✅

| 编号 | 本体 | 类型 | 自由度 | 末端 | 已有位置 |
|---|---|---|---|---|---|
| R1 | **Shadow Hand 灵巧手** | 灵巧手 | 10+2腕 | 5指 | `dexterous_sim/hand_model.xml` |
| R2 | **力控夹爪** | 二指夹爪+升降 | 2指+1Z | 平行夹爪 | `experiment_phase1/mujoco_eval/grasp_env.py`（XML内嵌） |
| R3 | **Unitree G1** | 人形机器人 | 23+6 | 足+手 | `motion_control/unitree_models/g1_23dof.xml` |

### 2.2 需要新建的模型 🏗️

| 编号 | 本体 | 类型 | 理由 |
|---|---|---|---|
| R4 | **Franka Panda 机械臂** | 7轴单臂 | 工业机械臂基准，与论文对比 |
| R5 | **双臂操作台** | 7+7轴双臂 | 验证双臂协调 |

### 2.3 差异性矩阵

| 差异维度 | R1↔R2 | R1↔R3 | R1↔R4 | R2↔R3 |
|---|---|---|---|---|
| 自由度数量 | 高(12 vs 3) | 高(12 vs 29) | 中(12 vs 7) | 极高(3 vs 29) |
| 末端类型 | 灵巧手 vs 夹爪 | 手 vs 足 | 手 vs 夹爪 | 夹爪 vs 全身 |
| 基座 | 固定 | 可移动 | 固定 | 可移动 |
| 控制精度需求 | 高(mm) | 中(cm) | 中(mm) | 低(cm) |
| **跨本体难度** | **中** | **极高** | **中低** | **极高** |

---

## 三、实验任务设计（6个）

### 任务场景统一设计

每个任务在 MuJoCo 中的场景：桌面 + 物体 + 机器人末端接近

```xml
<!-- 标准场景模板 (base_scene.xml) -->
<mujoco model="cross_embodiment_base">
  <option timestep="0.002" gravity="0 0 -9.81"/>
  <worldbody>
    <light pos="0 0 5" dir="0 0 -1"/>
    <geom name="floor" type="plane" size="2 2 0.01"/>
    <geom name="table" type="box" size="0.3 0.3 0.02" pos="0 0 0.72"/>
    <!-- 物体（各任务自定义） -->
    <!-- 机器人（各本体插入） -->
  </worldbody>
</mujoco>
```

| 编号 | 任务 | 描述 | 适用本体 | 难度 |
|---|---|---|---|---|
| T1 | **桌面抓取** | 抓取桌面小球/方块并提升 | R1,R2,R4 | ⭐ |
| T2 | **推拉操作** | 将物体推到指定区域 | R1,R2,R3,R4 | ⭐⭐ |
| T3 | **打开容器** | 打开抽屉/门 | R1,R4,R5 | ⭐⭐⭐ |
| T4 | **接触擦拭** | 擦拭桌面污渍 | R1,R3,R4 | ⭐⭐⭐⭐ |
| T5 | **多步操作** | 先后完成抓取+放置+开关 | R4,R5 | ⭐⭐⭐⭐ |
| T6 | **双臂协调** | 一手开盖一手取物 | R5 | ⭐⭐⭐⭐⭐ |

---

## 四、YLYW 跨本体推理架构（核心设计）

### 4.1 架构总图

```
┌────────────────────────────────────────────────────────────────┐
│                       YLYW 跨本体推理引擎                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  任务指令 (如 "pick up the red cube")                           │
│       ↓                                                        │
│  ┌──────────────────────────────────────────┐                  │
│  │  L1: 八卦基元层 (跨本体共享)              │                  │
│  │  任务 → 解析 → 八卦隶属度向量 [8维]       │                  │
│  └──────────────────────────────────────────┘                  │
│       ↓                                                        │
│  ┌──────────────────────────────────────────┐                  │
│  │  L2: 六爻编码层 (本体配置化)              │  ← 每个本体不同   │
│  │  八卦隶属度 + 传感器状态 → 六爻向量 [6维] │                  │
│  └──────────────────────────────────────────┘                  │
│       ↓                                                        │
│  ┌──────────────────────────────────────────┐                  │
│  │  L3: 64卦规则层 (跨本体共享)              │                  │
│  │  六爻向量 → 卦象匹配 → 策略类型+参数模板  │                  │
│  └──────────────────────────────────────────┘                  │
│       ↓                                                        │
│  ┌──────────────────────────────────────────┐                  │
│  │  动作解码器 (本体特异的)                  │  ← 每个本体不同   │
│  │  策略参数 → 关节命令 / 末端位姿           │                  │
│  └──────────────────────────────────────────┘                  │
│       ↓                                                        │
│  MuJoCo 仿真环境 ← 关节命令执行                               │
│       ↓ (反馈)                                                  │
│  传感器观测 → 更新状态 → 下一轮推理                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 4.2 L1: 八卦基元层（任务解析 → 8维隶属度向量）

跨本体共享，从 YLYW 核心 API 直接引用：

```python
# ylyw_core/trigram_base.py (已有)
class TrigramBase:
    # 8个卦的物理语义原型（跨本体不变）
    QIAN(乾): 刚性/强力   KUN(坤): 柔性/包容   ZHEN(震): 动态/振动
    GEN(艮): 稳固/静止    LI(离): 轻质/附着     KAN(坎): 凹陷/危险
    DUI(兑): 柔软/悦纳    XUN(巽): 渗透/适应
    
    def from_task(self, task_desc: str) -> np.ndarray:
        """任务描述 → 8维八卦隶属度"""
        
    def from_sensor(self, state: dict) -> np.ndarray:
        """传感器状态 → 8维八卦隶属度"""
```

**示例**：任务 "pick up the cube"
```python
# 解析结果（先验知识）
bagua = [0.9, 0.3, 0.2, 0.8, 0.1, 0.2, 0.3, 0.4]
#       乾   坤   震   艮   离   坎   兑   巽
#       艮(静止/稳定抓取)为主，乾(强力)为辅
```

### 4.3 L2: 六爻编码层（本体配置化）

**核心设计**: 每个本体有一个 `BodyConfig`，定义本体特的六爻编码：

```python
# ─── 本体配置文件基类 ───
class BodyConfig:
    """本体配置抽象基类"""
    name: str
    n_dof: int
    end_effector: str
    
    def encode_yao(self, bagua: np.ndarray, sensor: dict) -> np.ndarray:
        """八卦(8维) + 传感器 → 六爻(6维)"""
        raise NotImplementedError


# ─── R1: Shadow Hand 灵巧手配置 ───
class ShadowHandConfig(BodyConfig):
    name = "shadow_hand"
    n_dof = 12
    
    def encode_yao(self, bagua, sensor):
        # 初爻: 手指接近物体? (最接近的手指距离)
        y1 = 1.0 if sensor["min_finger_dist"] < 0.03 else 0.0
        # 二爻: 物体在掌心? 
        y2 = 1.0 if sensor["object_in_palm"] else 0.0
        # 三爻: 接触力足够?
        y3 = 1.0 if sensor["contact_force"] > 0.2 else 0.0
        # 四爻: 手指弯曲到位?
        y4 = 1.0 if sensor["finger_curvature"] > 0.6 else 0.0
        # 五爻: 提升成功?
        y5 = 1.0 if sensor["lift_height"] > 0.05 else 0.0
        # 上爻: 存在干扰/滑动?
        y6 = 0.0 if sensor["slip_detected"] else 1.0
        return np.array([y1, y2, y3, y4, y5, y6])


# ─── R2: 力控夹爪配置 ───
class GripperConfig(BodyConfig):
    name = "force_gripper"
    n_dof = 3
    
    def encode_yao(self, bagua, sensor):
        # 同上但感知特征不同（夹爪只有开/合状态）
        y1 = 1.0 if sensor["dist_to_obj"] < 0.02 else 0.0
        y2 = 1.0 if sensor["gripper_open"] < 0.5 else 0.0  # 夹爪已靠近
        y3 = 1.0 if sensor["contact_force"] > 0.3 else 0.0
        y4 = 1.0 if sensor["gripper_pos"] < 0.3 else 0.0  # 夹爪闭合度
        y5 = 1.0 if sensor["lift_height"] > 0.05 else 0.0
        y6 = 1.0 if sensor["slip_detected"] == 0 else 0.0
        return np.array([y1, y2, y3, y4, y5, y6])


# ─── R3: Unitree G1 人形机器人配置 ───
class G1Config(BodyConfig):
    name = "unitree_g1"
    n_dof = 29
    
    def encode_yao(self, bagua, sensor):
        # 注意！G1是足式机器人，六爻含义更接近 locomotion 版本
        y1 = 1.0 if sensor["姿态稳定"] else 0.0      # 初爻: 站姿
        y2 = 1.0 if sensor["重心位置"] > 0.5 else 0.0 # 二爻: 重心
        y3 = 1.0 if sensor["足地接触"] > 0 else 0.0   # 三爻: 接触力
        y4 = 1.0 if sensor["ZMP裕度"] > 0.1 else 0.0  # 四爻: ZMP
        y5 = 1.0 if sensor["外界扰动"] < 0.3 else 0.0 # 五爻: 扰动
        y6 = 1.0 if sensor["地形平坦"] else 0.0       # 上爻: 地形
        return np.array([y1, y2, y3, y4, y5, y6])


# ─── R4: Franka Panda 配置（需要新建）───
class FrankaConfig(BodyConfig):
    name = "franka_panda"
    n_dof = 7
    
    def encode_yao(self, bagua, sensor):
        y1 = 1.0 if sensor["末端接近目标"] < 0.1 else 0.0
        y2 = 1.0 if sensor["夹爪对准"] > 0.8 else 0.0
        y3 = 1.0 if sensor["接触力"] > 0.1 else 0.0
        y4 = 1.0 if sensor["夹爪开度合适"] else 0.0
        y5 = 1.0 if sensor["提升高度"] > 0.05 else 0.0
        y6 = 1.0 if sensor["无奇异位形"] else 0.0
        return np.array([y1, y2, y3, y4, y5, y6])
```

### 4.4 L3: 64卦规则层（跨本体共享）

直接从 `api_docs/ylyw_core/hexagram_rules.py` 引用：

```python
# ─── 64卦通用规则表（所有机器人共享！）───
class HexagramRules:
    """64卦规则引擎（跨本体不变）"""
    
    RULES = {
        (6, 5, 4, 3, 2, 1): {   # 爻值二进制表示
            "gua": "䷀ 乾为天",
            "strategy": "全力抓取/执行",
            "params": {"speed": 1.0, "force": 1.0, "precision": "low"}
        },
        (0, 0, 0, 0, 0, 0): {
            "gua": "䷁ 坤为地",
            "strategy": "待机/准备",
            "params": {"speed": 0.0, "force": 0.0, "precision": "none"}
        },
        (1, 0, 1, 0, 1, 0): {
            "gua": "䷾ 既济",
            "strategy": "任务完成/确认",
            "params": {"speed": 0.3, "force": 0.2, "precision": "high"}
        },
        (0, 1, 0, 1, 0, 1): {
            "gua": "䷿ 未济",
            "strategy": "任务未完成/继续尝试",
            "params": {"speed": 0.5, "force": 0.5, "precision": "medium"}
        },
        # ... 全部64卦
    }
    
    def match(self, yao_vector: np.ndarray) -> dict:
        """六爻向量 → 卦象规则"""
        # 将连续向量二值化，匹配最接近的卦
        binary = tuple(int(v >= 0.5) for v in yao_vector)
        return self.RULES.get(binary, self.RULES[(0, 0, 0, 0, 0, 0)])
```

### 4.5 动作解码器（本体特异的）

```python
# ─── R1: Shadow Hand 动作解码 ───
class ShadowHandDecoder:
    def decode(self, strategy: str, params: dict, obj_info: dict) -> dict:
        """策略 → 12个关节角度"""
        mapping = {
            "全力抓取": {"thumb": (0.8, 0.8), "index": (1.0, 0.9), ...},
            "待机":     {"thumb": (0.0, 0.0), "index": (0.0, 0.0), ...},
            "完成确认": {"thumb": (0.6, 0.6), "index": (0.7, 0.6), ...},
        }
        return mapping.get(strategy, mapping["待机"])


# ─── R2: 力控夹爪动作解码 ───
class GripperDecoder:
    def decode(self, strategy, params, obj_info):
        """策略 → 夹爪力矩 + Z轴升降"""
        if strategy == "全力抓取":
            return {"gripper_force": 0.5, "lift_target": 0.05}
        elif strategy == "待机":
            return {"gripper_force": 0.0, "lift_target": 0.0}
        elif strategy == "完成确认":
            return {"gripper_force": 0.3, "lift_target": 0.08}
        elif strategy == "继续尝试":
            return {"gripper_force": 0.7, "lift_target": 0.02}
        # ...
```

---

## 五、代码结构

```
ylyw/cross_embodiment/
├── README.md
├── core/                              # 跨本体共享推理核心
│   ├── trigram_base.py                # L1: 八卦基元 (已有, 直接引用)
│   ├── yao_encoder.py                 # L2: 六爻引擎 (调用 BodyConfig)
│   ├── hexagram_rules.py              # L3: 64卦规则 (已有, 直接引用)
│   └── cross_body_infer.py            # 串联 L1→L2→L3 的统一推理入口
│
├── bodies/                            # 本体配置
│   ├── __init__.py
│   ├── base_config.py                 # BodyConfig 基类
│   ├── body_shadow_hand.py            # R1: Shadow Hand
│   ├── body_gripper.py                # R2: 力控夹爪
│   ├── body_g1.py                     # R3: Unitree G1
│   ├── body_franka.py                 # R4: Franka Panda (需新建)
│   └── body_bimanual.py               # R5: 双臂 (需新建)
│
├── decoders/                          # 动作解码器
│   ├── decoder_shadow_hand.py
│   ├── decoder_gripper.py
│   ├── decoder_g1.py
│   ├── decoder_franka.py
│   └── decoder_bimanual.py
│
├── scenes/                            # MuJoCo XML 场景
│   ├── base_scene.xml                 # 标准场景模板
│   ├── scene_hand.xml                 # 灵巧手场景
│   ├── scene_gripper.xml              # 夹爪场景
│   ├── scene_g1.xml                   # G1 场景（利用已有）
│   ├── scene_franka.xml               # Franka 场景 (需新建)
│   └── scene_bimanual.xml             # 双臂场景 (需新建)
│
├── tasks/                             # 任务实现
│   ├── task_base.py                   # 任务基类
│   ├── task_pick_place.py
│   ├── task_push_pull.py
│   ├── task_open_close.py
│   ├── task_wiping.py
│   ├── task_long_horizon.py
│   └── task_bimanual.py
│
├── baselines/                         # 对比基线
│   ├── baseline_random.py
│   ├── baseline_bc.py
│   └── baseline_open_loop.py
│
├── experiments/
│   ├── run_phase1_baseline.py         # 单本体基准
│   ├── run_phase2_cross_body.py       # 跨本体迁移
│   ├── run_phase3_ablation.py         # 消融实验
│   └── run_phase4_extreme.py          # 极限测试
│
├── analysis/
│   ├── plot_results.py
│   └── statistics.py
│
└── results/                           # 输出目录
```

---

## 六、实验分阶段实施

### Phase 0: 环境搭建（3天）

**Day 1-2: 统一 MuJoCo 工具包**
```python
# 统一的 MuJoCo 环境类 (mujoco_env.py)
class CrossBodyEnv:
    """跨本体 MuJoCo 环境"""
    
    def __init__(self, body_type: str, task_type: str, headless=True):
        # 1. 加载对应本体的 XML
        # 2. 加载对应任务的物体
        # 3. 设置 MuJoCo 渲染
        # 4. 初始化 YLYW 推理引擎
    
    def reset(self):
        # 重置仿真到初始状态
    
    def step(self, ylyw_action: dict) -> tuple:
        # 执行 YLYW 解码后的动作
        # 返回 (观测, 奖励, 完成, info)
```

**Day 3: 测试 3 个已有模型**
- Shadow Hand 灵巧手: 验证已有 XML 可加载
- 力控夹爪: 验证抓取功能
- Unitree G1: 验证已有 locomotion 控制

### Phase 1: 单本体基准（4天）

1. 在 R1 (Shadow Hand) 上实现完整 YLYW 推理链
2. 运行 T1-T4 各 20 次
3. 调优 L3 策略参数

### Phase 2: 跨本体迁移（3天）

1. 为 R2 (夹爪), R3 (G1) 编写 BodyConfig（仅六爻编码不同！）
2. **零样本**运行（L3 规则表不改一字）
3. 对比 R1 ↔ R2 ↔ R3 的性能差距

### Phase 3: 对比实验（4天）

1. YLYW vs Baseline Random vs Baseline Open-Loop
2. 消融实验：去掉 L3 / 换为 32卦 / 改变六爻维度
3. 统计分析

### Phase 4: 极限测试（3天）

1. 物体尺寸/重量变化
2. 初始位置扰动
3. 传感器噪声

---

## 七、现有资源的利用

| 已有模块 | 路径 | 用途 |
|---|---|---|
| 八卦基元 | `api_docs/ylyw_core/trigram_base.py` | L1 直接引用 |
| 六爻编码(运动版) | `motion_control/yao_encoder_motion.py` | L2 参考实现 |
| 64卦步态规则 | `motion_control/hexagram_gait_rules.py` | L3 参考（但需改为操作规则） |
| 力控夹爪环境 | `experiment_phase1/mujoco_eval/grasp_env.py` | R2 直接复用 |
| 灵巧手模型 | `dexterous_sim/hand_model.xml` | R1 直接使用 |
| Unitree G1 | `motion_control/unitree_models/g1_23dof.xml` | R3 直接使用 |
| 灵巧手抓取 | `dexterous_sim/geometric_ylyw.py` | 跨本体抓取策略参考 |
| YLYW 自适应 | `motion_control/ylyw_adaptive.py` | 本体自适应参考 |

---

## 八、评价指标

| 指标 | 定义 |
|---|---|
| SR (Success Rate) | 成功比例 (20次中) |
| Steps | 完成任务所需步数 |
| TGT (Transfer Gap) | SR_{本体B} - SR_{本体A} |
| ZSR (Zero-Shot Rate) | 零样本在新本体的成功率 |
| 推理延迟 | 单次 YLYW 推理时间 |
| 适配成本 | 新本体的配置代码行数 |

---

## 九、立即开始的第一步

建议从 **Phase 0 Day 1** 做起：

1. 新建 `ylyw/cross_embodiment/` 目录
2. 复制已有的环境和核心模块
3. 在 Shadow Hand 上跑通一个简单的 YLYW 推理→抓取闭环
4. 再逐步扩展到其他本体

需要我现在就开始搭建这个目录结构和基础代码吗？
