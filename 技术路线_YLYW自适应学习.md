# YLYW 自适应学习技术路线

> 2026-06-06 整理  
> 基于现有 YLYW 三层架构（L1 八卦隶属度 → L2 六爻编码 → L3 卦象匹配），  
> 探索基于可解释性的定向参数修正与在线自适应能力。

---

## 一、背景与动机

### 1.1 问题

当前 YLYW 是**静态前馈推理系统**：给定传感器状态，经过 L1→L2→L3 推理链输出步态/抓取参数。这个系统在零样本条件下已经达到较高合理率（抓取 92.7%、运动控制合理率约 90%+），但它**不会从失败中学习**。

实际应用中存在以下需求：

- **抓取场景**：物体滑脱后，需要找到原因（力不够？摩擦力误判？抓取点偏移？），并针对性微调
- **运动控制**：初始参数不合适（如质心偏了、地面摩擦系数变了），需要快速在线调整
- **长期运行**：电机老化、部件磨损导致动力学模型偏移，系统需要持续自我校准

### 1.2 核心洞察

YLYW 与黑箱深度模型的本质区别：**每一步推理都是人类可读的**。

```
失败时：
  DRL/端到端模型 → "某个隐藏层权重需要调整"（不可审计）
  YLYW → "第3爻（力分布）被判为阳，实际应该是阴，导致匹配到大壮卦而非谦卦"（可精确定位）
```

这使得 YLYW 的自适应学习可以走一条完全不同的路线——
**不需大量样本**，一次失败即可追溯推理链、定位责任层、修正对应参数。

---

## 二、YLYW 的可解释性基础（回顾）

### 2.1 三层推理架构

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  L1 八卦隶属度 │ → │  L2 六爻编码   │ → │  L3 卦象匹配   │
│  8维模糊隶属  │    │  6维阴阳判定   │    │  64卦模板匹配  │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               ↓
                                        ┌──────────────┐
                                        │  爻位关系分析  │
                                        │  力修正系数    │
                                        └──────────────┘
```

### 2.2 各层可调参数

| 层级 | 参数 | 数量 | 语义 |
|---|---|---|---|
| L1 | 八卦原型向量 (8×6D) | 48 | "什么样的状态算乾？" |
| L2 | 六爻阴阳判定阈值 (6维) | 6 | "多少才算阳爻？" |
| L3 | 六十四卦爻模板 (64×6D) | 384 | "每个卦的理想状态是什么" |
| 爻位关系 | 五类关系权重 (5维) | 5 | "当位、得中、乘承、比、应各占多重" |
| **合计** | | **443** | 远小于深度网络的百万级参数 |

### 2.3 失败诊断的粒度

每一步失败都可以通过推理链回放来定位：

```
推理链回放示例（抓取滑脱）：

  L1: 物体表面特征 → 乾:0.72 兑:0.45 离:0.38 ...
      主导八卦: 乾 (刚硬) ← 正确
  
  L2: 六爻编码:
      初爻(刚度):    阳 0.82 ← 正确
      二爻(表面纹理): 阳 0.68 ← 正确
      三爻(摩擦力):   阳 0.72 ← ? 实际是光滑表面，应为阴
      四爻(重量):     阴 0.35 ← 正确
      五爻(形变):     阴 0.22 ← 正确
      上爻(综合):     阳 0.58 ← 受三爻影响偏高
  
  L3: 匹配 → 大壮卦(hex 34) 相似度 0.88
      步态映射 → 高力抓取 (力系数 0.90)
      
  爻位关系: 二五得中 ✓ | 一四不应 ✗ | 三爻不当位 ✗
      力修正系数: 0.85 (减弱)
      谨慎级别: cautious
      建议: "多爻不当位，建议降低力预设"
      
  → 诊断结论: L2 三爻阈值过高，导致光滑表面仍判为阳
  → 修正方案: 降低摩擦力维度的阴阳阈值 0.50 → 0.30
```

---

## 三、自适应闭环方案

### 3.1 总览

```
        ┌──────────────────────────────────────────┐
        │            YLYW 自适应闭环                │
        │                                           │
        │  状态S ─→ L1 ─→ L2 ─→ L3 ─→ 动作A        │
        │    ↑                          ↓           │
        │    │                    执行动作           │
        │    │                          ↓           │
        │    │                    观测结果O          │
        │    │                          ↓           │
        │    └── 参数更新 ←── 失败诊断 ←── 反馈F     │
        │         (定向修正)    (推理链回放)  (成功?) │
        └──────────────────────────────────────────┘
```

### 3.2 反馈信号设计

不同任务需要不同的反馈信号：

| 任务 | 反馈信号 | 来源 |
|---|---|---|
| 抓取 | 是否滑脱 / 接触力曲线 / 位移量 | 力传感器 + 视觉 |
| 运动控制 | 是否摔倒 / COM偏差 / ZMP裕度 / 能耗 | IMU + 关节编码器 |
| 视觉分类 | Top-1是否错误 / 置信度 | 标签 |
| 触觉感知 | 压力场估计误差 / 时序一致性 | 标定数据 |

### 3.3 诊断与修正策略

#### 策略A：参数级修正（轻量）

直接调整对应层的可调参数，适用于小幅偏差。

```
规则:
  IF L1 隶属度偏差 > 阈值 → 调整八卦原型质心
  IF L2 阴阳判错         → 调整该爻的判定阈值
  IF L3 卦象匹配错误      → 调整目标卦的爻模板
  IF 力系数不合适         → 调整爻位关系权重

学习率: 0.02-0.10（保守，防止振荡）
方向: 向正确方向梯度移动（非数学梯度，而是语义方向）
```

#### 策略B：结构级修正（深层）

调整爻位关系权重或步态类型的映射，适用于系统性偏差或跨域适配。

```
场景:
  1. 任务域切换（抓取→运动控制→触觉感知）
     → 动态调整爻位关系权重（当位/得中/乘承/比/应）
     
  2. 设备老化（电机功率下降20%）
     → 系统性降低所有卦的力系数 0.10
     
  3. 环境变化（地面从水泥→冰面）
     → 系统性提升 caution 卦的匹配优先级
```

---

## 四、具体实现设计

### 4.1 自适应控制器基类

```python
class YLYWAdaptiveController:
    """
    带在线自适应的YLYW控制器
    
    新增能力:
    - 推理链记录与回放
    - 失败诊断
    - 定向参数修正
    - 长期性能追踪
    """
    
    def __init__(self, learning_rate=0.05):
        self.controller = YLYWLocomotionController()
        self.lr = learning_rate
        
        # 推理链轨迹
        self.trajectory = []  # [(state, result, feedback)]
        
        # 参数修正历史（可审计）
        self.adaptation_log = []
    
    def step(self, state, feedback=None):
        """
        执行一步推理 + 自适应
        
        Args:
            state: 6D传感器状态
            feedback: 上一步的反馈信号（None表示第一步）
        
        Returns:
            action: 动作参数
        """
        # 如果有反馈，先做自适应修正
        if feedback is not None and self.trajectory:
            self._adapt_from_feedback(feedback)
        
        # 正常推理
        result = self.controller.infer(state)
        
        # 记录轨迹
        self.trajectory.append({
            'state': state,
            'result': result,
            'feedback': None  # 待填充
        })
        
        return result
    
    def give_feedback(self, feedback):
        """外部传入反馈信号"""
        if self.trajectory:
            self.trajectory[-1]['feedback'] = feedback
    
    def _adapt_from_feedback(self, feedback):
        """
        核心：根据反馈执行定向参数修正
        
        三步法：
          1. 回放推理链
          2. 定位责任层
          3. 修正对应参数
        """
        last = self.trajectory[-1]
        result = last['result']
        
        # 1. 回放推理链
        diagnosis = self._diagnose(result, feedback)
        
        # 2. & 3. 修正
        self._apply_correction(diagnosis)
        
        # 记录
        self.adaptation_log.append(diagnosis)
    
    def _diagnose(self, result, feedback):
        """诊断失败原因"""
        raise NotImplementedError
    
    def _apply_correction(self, diagnosis):
        """应用参数修正"""
        raise NotImplementedError
```

### 4.2 运动控制自适应（具体实现）

运动控制是最适合做自适应的领域，因为：
- 反馈信号丰富（COM偏差、ZMP裕度、是否摔倒）
- 爻位关系在运动控制中已验证有效（力修正系数0.94）
- 已有 motion_control 仿真环境

#### 反馈信号

```python
motion_feedback = {
    'fell': False,           # 是否摔倒
    'com_deviation': 0.12,   # COM偏离期望位置
    'zmp_margin': 0.35,      # ZMP稳定性裕度
    'energy_cost': 0.65,     # 能耗（归一化）
    'speed_error': 0.08,     # 速度偏差
}
```

#### 失败诊断规则

```
IF fell == True:
    严重失败 → 回放推理链
    常见原因:
      1. L2 编码过于乐观（稳定爻判阳）→ 降低相关爻阈值
      2. L3 匹配到高速卦但实际状态不稳 → 调整该状态的目标卦模板
      3. 爻位关系修正不足 → 增加 cautious 权重

IF com_deviation > 0.3:
    中度偏差 → 调整对应卦的 COM维度爻模板
    将当前卦模板的com维度降低 0.05*lr

IF zmp_margin < 0.2:
    ZMP裕度不足 → 调高ZMP维度在卦模板中的权重
    同时通过爻位关系增加力修正系数降幅
```

#### 自适应策略

```python
def _apply_motion_correction(self, diagnosis):
    hex_id = diagnosis['hexagram_id']
    layer = diagnosis['layer']  # 'L1' | 'L2' | 'L3' | 'relation'
    dim = diagnosis['dimension']  # 0-5
    
    if layer == 'L2':
        # 调整阴阳判定阈值
        old = self.controller.yao_encoder.thresholds[dim]
        delta = self.lr * diagnosis['direction']  # +1 or -1
        new = np.clip(old + delta, 0.1, 0.9)
        self.controller.yao_encoder.thresholds[dim] = new
        
    elif layer == 'L3':
        # 调整卦模板
        template = self.controller.hexagram_rules.HEXAGRAM_YAO_TEMPLATES[hex_id]
        old = template[dim]
        delta = self.lr * diagnosis['direction'] * 0.1
        new = np.clip(old + delta, 0.02, 0.98)
        template[dim] = new
        
    elif layer == 'relation':
        # 调整爻位关系权重
        self.controller.hexagram_rules.relation_weights[dim] += \
            self.lr * diagnosis['direction'] * 0.05
```

### 4.3 抓取自适应

抓取与运动控制的自适应逻辑相同，但关注的维度不同：

| 抓取关注维度 | 对应爻位 | 判断标准 |
|---|---|---|
| 物体刚度 | 初爻 | 硬→微调增大/软→微调减小 |
| 表面纹理 | 二爻 | 粗糙→增加摩擦预判 |
| 摩擦力 | 三爻 | 滑脱→降低该爻值 |
| 重量预期 | 四爻 | 超重→升高该爻值 |
| 形变程度 | 五爻 | 形变大→触发柔性策略 |
| 综合稳定性 | 上爻 | 不稳定→增加安全系数 |

---

## 五、技术路线分阶段规划

### 阶段一：离线参数优化（已有基础）✅

- [x] `optimize_templates.py` — 基于步态质心的模板优化
- [x] 三步法：采集质心 → 卦象步态映射 → 模板重算
- [x] 问题卦识别与极端化修复

### 阶段二：运动控制在线自适应（下一步）⏸️

- [ ] 实现 `YLYWAdaptiveController` 基类
- [ ] 在 PyBullet/MuJoCo 仿真中验证：
  - 质心偏移后自动恢复
  - 地面摩擦变化后自适应
  - 外部推搡后的快速调整
- [ ] 对比实验：
  - YLYW + 自适应 vs YLYW 静态
  - YLYW + 自适应 vs 传统 PID / MPC
- [ ] 指标：摔倒频率、COM偏差恢复时间、能耗

### 阶段三：抓取自适应 ⏸️

- [ ] 在抓取仿真/Gazebo 中实现反馈闭环
- [ ] 验证三种典型失败模式的自我修复：
  - 力不足 → 自动提升力系数
  - 摩擦力误判 → 调整表面维度阈值
  - 抓取点偏移 → 调整位姿策略
- [ ] 多物体连续抓取的在线学习曲线

### 阶段四：跨域参数迁移 ⏸️

- [ ] 运动控制域 → 抓取域的爻位关系权重迁移
- [ ] 触觉感知域的专用自适应策略
- [ ] 研究"学到的参数"是否可跨域复用

### 阶段五：长期自校准 ⏸️

- [ ] 设备老化模拟（逐步降低电机功率）
- [ ] YLYW 能否自动检测并补偿？
- [ ] 长期运行稳定性跟踪

---

## 六、预期优势与风险

### 6.1 独特优势

| 特性 | 说明 |
|---|---|
| **样本效率** | 一次失败即可精确定位并修正，不需要大量试错 |
| **可审计** | 每次参数修正都有推理链依据，可回放可复查 |
| **安全** | 符号约束防止灾难性遗忘，修正范围可控 |
| **可干预** | 人类可以查看 adaptation_log，手动回滚任何一步 |
| **参数效率** | 仅 ~443 个可调参数，vs 深度RL的百万级 |

### 6.2 风险与限制

| 风险 | 缓解方案 |
|---|---|
| 过度修正导致振荡 | 小学习率 + 动量平滑 + 修正上限 |
| 多故障耦合难以定位 | 按优先级诊断（先 L2 后 L3，先单爻后多爻） |
| 符号离散性限制精细度 | 保留连续隶属度 + 软阈值 |
| 复杂场景推理链过长 | 可配置诊断深度（快速模式 vs 完整模式） |

---

## 七、与现有项目的衔接

### 7.1 代码位置

```
motion_control/
├── ylyw_locomotion.py       ← 现有控制器（静态）
├── ylyw_adaptive.py          ← [新建] 自适应控制器
├── hexagram_gait_rules.py    ← 可复用
├── trigram_base_motion.py    ← 可复用
├── yao_encoder_motion.py     ← 需增强（可调阈值）
└── experiments/
    ├── exp_a_zero_shot.py    ← 现有基线
    ├── optimize_templates.py ← 现有离线优化
    └── exp_b_adaptive.py     ← [新建] 在线自适应实验
```

### 7.2 关键依赖

- `yao_encoder_motion.py` 需要暴露阴阳判定阈值为可调参数
- `hexagram_gait_rules.py` 的爻模板需要支持增量更新
- 仿真环境已就绪（PyBullet/MuJoCo）

---

## 八、参考文献方向

- 可解释强化学习 (XRL)：与本文的"推理链回放诊断"思路对比
- 基于模型的强化学习 (MBRL)：YLYW 的六十四卦策略库本质是一个离散世界模型
- Sim-to-Real Transfer：自适应能力是域迁移的关键技术
- Meta-Learning：快速适应新环境的能力

---

*下一步：马老师审阅后决定是否启动阶段二（运动控制在线自适应实现）。*
