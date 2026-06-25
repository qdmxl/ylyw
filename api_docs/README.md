# YLYW 层次嵌套模型 — API 文档

> **YLYW**（易理研物）：一种基于《易经》先验符号知识的联邦式神经符号具身决策框架

---

## 目录

1. [架构总览](#1-架构总览)
2. [快速开始](#2-快速开始)
3. [API 参考](#3-api-参考)
   - [PriorManual（主入口）](#31-priormanual主入口)
   - [TrigramBase（L1 八卦基元）](#32-trigrambase-l1)
   - [YaoEncoder（L2 六爻编码器）](#33-yaoencoder-l2)
   - [HexagramRuleBase（L3 六十四卦规则库）](#34-hexagramrulebase-l3)
   - [YaoRelations（L3+ 爻位关系运算）](#35-yaorelations-l3)
4. [数据格式约定](#4-数据格式约定)
5. [完整使用示例](#5-完整使用示例)
6. [源代码位置](#6-源代码位置)

---

## 1. 架构总览

```
┌────────────────────────────────────────────────────┐
│                 PriorManual（主控）                 │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ perceive_and │  │ explain_     │                │
│  │ encode()     │  │ reasoning()  │                │
│  └──────┬───────┘  └──────────────┘                │
│         │                                           │
│  ┌──────▼──────────────────────────────────────┐   │
│  │   L1 → L2 → L3 推理链路                      │   │
│  │                                              │   │
│  │  L1: TrigramBase                             │   │
│  │    物理特征 → 八卦隶属度向量(8维)             │   │
│  │       ↓                                      │   │
│  │  L2: YaoEncoder                              │   │
│  │    物理特征 → 六爻向量(6维)                   │   │
│  │       ↓                                      │   │
│  │  L3: HexagramRuleBase                        │   │
│  │    六爻向量 → 余弦匹配 → 最佳卦象 → 策略      │   │
│  │       ↓                                      │   │
│  │  L3+: YaoRelations                           │   │
│  │    六爻内部结构分析 → 策略参数修正             │   │
│  └─────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────┘
```

### 层次职责

| 层次 | 模块 | 输入 | 输出 | 核心方法 |
|------|------|------|------|----------|
| **L1** 八卦 | `TrigramBase` | 物体物理特征 dict | 8维隶属度向量 | `get_all_memberships()` |
| **L2** 爻编码 | `YaoEncoder` | 物体物理特征 dict | 6维爻向量 | `encode()` |
| **L3** 卦匹配 | `HexagramRuleBase` | 6维爻向量 | 最佳卦象+策略 | `get_best_hexagram()` |
| **L3+** 爻关系 | `YaoRelations` | 6维爻向量 | 关系分析+力修正 | `analyze()` |

---

## 2. 快速开始

```python
from ylyw.prior_manual import PriorManual

# 1. 初始化（无GPU，无训练）
manual = PriorManual(verbose=True)

# 2. 构造物体物理特征
sphere = {
    'stability': 0.1,          # 极不稳定（球体）
    'roll_tendency': 0.95,     # 极易滚动
    'strength_needed': 0.3,    # 轻物，不需大力
    'fragility': 0.4,          # 中等脆弱
    'task_priority': 0.5,      # 普通优先级
    'reachability': 0.8,       # 容易到达
    'support_area': 0.05,      # 极小支撑面（点接触）
    'occlusion': 0.0,          # 无遮挡
    'obstacle_density': 0.0,   # 无环境障碍
    'grasp_surface_quality': 0.6,
    'weight_ratio': 0.3,
}

# 3. 一站式推理（感知 + 编码 + 决策）
perception, strategy = manual.process(sphere)

# 4. 查看结果
print(f"匹配卦象: {perception['best_hexagram'].name}")
print(f"抓取策略: {strategy['type']}")
print(f"力预设: {strategy['force']}")

# 5. 查看完整推理链
print(manual.explain_reasoning(perception))
```

---

## 3. API 参考

### 3.1 PriorManual（主入口）

**`class PriorManual(verbose: bool = False)`**

整个 YLYW 系统的统一入口，整合 L1-L3+ 四层推理。

**属性**

| 属性 | 类型 | 说明 |
|------|------|------|
| `trigram_base` | `TrigramBase` | L1 八卦基元 |
| `yao_encoder` | `YaoEncoder` | L2 六爻编码器 |
| `hexagram_rules` | `HexagramRuleBase` | L3 六十四卦规则库 |
| `yao_relations` | `YaoRelations` | L3+ 爻位关系运算 |
| `verbose` | `bool` | 是否打印详细日志 |

**方法**

#### `perceive_and_encode(object_features: dict) -> dict`

完成完整的 L1→L2→L3→L3+ 推理链路。

**参数 `object_features`**

```python
{
    # ── 必需字段 ──
    'stability': float,        # 稳定性 [0,1]，0=极易倾倒，1=极稳
    'roll_tendency': float,    # 滚动倾向 [0,1]
    'strength_needed': float,  # 所需抓取力 [0,1]
    'fragility': float,        # 脆弱性 [0,1]，1=极易碎
    'task_priority': float,    # 任务优先级 [0,1]
    'reachability': float,     # 抓取点可达性 [0,1]

    # ── 可选字段 ──
    'support_area': float,         # 支撑面积 [0,1]，小→易倒
    'occlusion': float,            # 遮挡程度 [0,1]
    'obstacle_density': float,     # 周围障碍密度 [0,1]
    'grasp_surface_quality': float,# 抓取表面质量 [0,1]
    'weight_ratio': float,         # 重量比 [0,1]
}
```

**返回 dict**

```python
{
    'yao_vector': np.ndarray(6,),       # 六爻值向量，每维 ∈ [0,1]
    'trigram_memberships': np.ndarray(8,),  # 8卦隶属度
    'dominant_trigram': Trigram,        # 主导卦象枚举
    'dominant_trigram_score': float,    # 隶属度得分
    'best_hexagram': Hexagram,          # 最佳匹配卦象
    'hexagram_match_score': float,      # 余弦相似度
    'top_k_hexagrams': list,            # Top-3卦象 [(Hexagram, score),...]
    'yao_relations': YaoRelationReport, # 爻位关系分析
}
```

#### `process(object_features: dict) -> (dict, dict)`

一站式处理：`perceive_and_encode()` + `get_grasp_strategy()`。

返回 `(perception_result, grasp_strategy)` 二元组。

#### `get_grasp_strategy(perception_result: dict) -> dict`

根据感知结果输出抓取策略。

```python
{
    'type': str,              # 策略类型（power_grasp/precision_grasp/...）
    'force': float,           # 力预设 [0.1, 1.0]，已含爻位修正
    'approach_angle': int,    # 接近角度（度）
    'speed': str,             # 'slow' | 'medium' | 'fast'
    'cautions': list[str],    # 注意事项
    'hexagram': str,          # 来源卦象名
    'force_modifier': float,  # 力修正系数（爻位关系产生）
    'caution_level': str,     # 谨慎级别
    'yao_quality': float,     # 爻位质量评分
}
```

#### `explain_reasoning(perception_result: dict) -> str`

生成完整的可读推理链文本。这是 YLYW 可解释性的核心体现。

#### `set_verbose(verbose: bool)`

切换详细日志开关。

---

### 3.2 TrigramBase（L1）

**`class TrigramBase()`**

八卦基元：8 个卦象的物理原型。每个卦对应一组"理想物理特征"。

**枚举 `Trigram`**

| 枚举值 | 卦名 | 卦符 | 卦德 | 自然 | 物理特性 |
|--------|------|------|------|------|----------|
| `QIAN` | 乾 | ☰ | 健 | 天 | 高刚性、强力需求 |
| `KUN` | 坤 | ☷ | 顺 | 地 | 高柔性、包容变形 |
| `ZHEN` | 震 | ☳ | 动 | 雷 | 高滚动倾向、动态 |
| `GEN` | 艮 | ☶ | 止 | 山 | 高稳定性、静止 |
| `LI` | 离 | ☲ | 明/附丽 | 火 | 高可见性、附着 |
| `KAN` | 坎 | ☵ | 陷/险 | 水 | 凹陷、高风险 |
| `DUI` | 兑 | ☱ | 悦 | 泽 | 柔软、和悦 |
| `XUN` | 巽 | ☴ | 入 | 风 | 渗透、自适应 |

**方法**

| 方法 | 签名 | 说明 |
|------|------|------|
| `compute_membership` | `(features: dict, trigram: Trigram) -> float` | 计算物体对某卦隶属度 [0,1] |
| `get_dominant_trigram` | `(features: dict) -> (Trigram, float)` | 获取主导卦象及得分 |
| `get_all_memberships` | `(features: dict) -> np.ndarray(8,)` | 获取8卦隶属度向量 |
| `get_trigram_info` | `(trigram: Trigram) -> dict` | 获取卦象元信息 |

**隶属度计算原理**

使用高斯核计算物体特征与卦象原型的差异：
```
membership = mean(1.0 - |actual - prototype| × 1.5)
```
参数 1.5 为敏感度系数（先验设定，不可学习）。

---

### 3.3 YaoEncoder（L2）

**`class YaoEncoder()`**

六爻编码器：将 13 维物理特征压缩为 6 维爻值向量。每个爻对应一个物理语义维度，编码公式为硬编码的先验知识。

**枚举 `YaoPosition`**

| 枚举值 | 爻位 | 名称 | 物理语义 | 阳爻含义 | 阴爻含义 |
|--------|------|------|----------|----------|----------|
| `FIRST` | 初爻 | 基础稳定性 | 物体的支撑基础 | 稳定、不易倾倒 | 不稳、易倾倒 |
| `SECOND` | 二爻 | 抓取点可达性 | 夹爪能否到达 | 可达性好 | 被遮挡/难达 |
| `THIRD` | 三爻 | 抓取力需求 | 所需握力 | 需要大力（重物） | 轻力即可 |
| `FOURTH` | 四爻 | 物体脆弱性 | 物体易碎程度 | 坚固 | 脆弱易碎 |
| `FIFTH` | 五爻 | 任务优先级 | 在任务中的重要性 | 高优先级 | 低优先级 |
| `SIXTH` | 上爻 | 环境约束 | 周围空间宽敞度 | 空间宽敞 | 拥挤受限 |

**方法**

| 方法 | 签名 | 说明 |
|------|------|------|
| `encode` | `(features: dict) -> np.ndarray(6,)` | 单物体编码 |
| `encode_batch` | `(features_list: list) -> np.ndarray(N,6)` | 批量编码 |
| `get_yao_interpretation` | `(yao: np.ndarray) -> list[dict]` | 人类可读爻解读 |
| `enable_logging` | `() -> None` | 开启编码日志 |
| `disable_logging` | `() -> None` | 关闭编码日志 |

**编码公式示例**

```python
# 初爻（基础稳定性）
yao[0] = 0.4 × stability + 0.3 × (1 - roll_tendency) + 0.3 × support_area

# 四爻（脆弱性，反向编码）
yao[3] = 1.0 - fragility
# 脆弱 → 爻值低（阴，不利）
# 坚固 → 爻值高（阳，有利）
```

---

### 3.4 HexagramRuleBase（L3）

**`class HexagramRuleBase()`**

六十四卦规则库。完整定义了 64 卦的理想爻模板、抓取策略映射。策略来自《周易》卦辞爻辞的工程转译。

**枚举 `Hexagram`**

包含全部 64 卦枚举值。上经 30 卦（`QIAN`～`LI_GUA`），下经 34 卦（`XIAN`～`WEIJI`）。

**策略类型全集（39 种）**

| 策略类型 | 说明 | 典型卦象 |
|----------|------|----------|
| `power_grasp` | 强力抓取 | 乾为天 |
| `precision_grasp` | 精确轻抓 | 坤为地 |
| `dynamic_grasp` | 动态跟踪抓取 | 震为雷 |
| `stable_grasp` | 稳定抓取 | 艮为山 |
| `cautious_grasp` | 极度谨慎 | 天泽履、坎为水 |
| `adaptive_grasp` | 自适应学习 | 山水蒙 |
| `progressive_grasp` | 渐进加力 | 风天小畜、火地晋 |
| `reduced_force_grasp` | 轻柔减力 | 山泽损 |
| `tactile_feedback_grasp` | 触觉反馈 | 泽山咸 |
| `direct_grasp` | 直接果断 | 天雷无妄 |
| `interlocking_grasp` | 啮合抓取 | 火雷噬嗑 |
| `...` | （共 39 种） | |

**方法**

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_best_hexagram` | `(yao_vector: ndarray(6,)) -> (Hexagram, float)` | 余弦匹配最佳卦象 |
| `get_top_k_hexagrams` | `(yao_vector, k=3) -> list` | 获取Top-k卦象 |
| `get_rule` | `(hexagram: Hexagram) -> dict` | 获取卦象完整规则 |
| `count_rules` | `() -> int` | 已定义规则数 |
| `list_all_hexagrams` | `() -> list[dict]` | 列出所有卦象摘要 |

**匹配算法**

```python
cosine_sim = dot(yao_vector, template) / (||yao_vector|| × ||template||)
```

---

### 3.5 YaoRelations（L3+）

**`class YaoRelations()`**

爻位关系运算器。将《周易》中"乘、承、比、应、当位、得中、中正"等关系形式化为可计算算子。

**dataclass `YaoRelationReport`**

| 字段 | 类型 | 说明 |
|------|------|------|
| `dangwei_count` | `int` | 当位爻数 (0-6) |
| `dangwei_details` | `list[str]` | 每爻当位情况 |
| `dezhong` | `bool` | 二爻是否得中 |
| `dezhong_wu` | `bool` | 五爻是否得中 |
| `cheng_count` | `int` | 阴乘阳次数（逆） |
| `bi_harmony` | `int` | 相邻和谐对数 (0-5) |
| `bi_disharmony` | `int` | 相邻不睦对数 |
| `ying_count` | `int` | 有应对数 (0-3) |
| `score_overall` | `float` | 综合爻位质量 [0,1] |
| `strategy_modifier` | `float` | 力修正系数 [0.75, 1.05] |
| `caution_level` | `str` | 谨慎级别 |
| `advice` | `list[str]` | 策略建议列表 |

**五种爻位关系**

| 关系 | 含义 | 计算规则 |
|------|------|----------|
| **当位** (Dangwei) | 阳爻居阳位/阴爻居阴位 | 计数 0-6，权重 40% |
| **得中** (Dezhong) | 二爻/五爻居中 | 六二/九五最优，权重 20% |
| **乘承** (Cheng) | 阴乘阳（逆）/ 阴承阳（顺） | 逐对检查 5 个相邻对，权重 15% |
| **亲比** (Bi) | 相邻爻同性/异性 | 同性=和谐，权重 10% |
| **呼应** (Ying) | 初-四/二-五/三-上 | 阴阳相反=有应，权重 15% |

**方法**

| 方法 | 签名 | 说明 |
|------|------|------|
| `analyze` | `(yao_vector: ndarray(6,)) -> YaoRelationReport` | 完整分析 |
| `format_report` | `(yao_vector, report=None) -> str` | 格式化为可读文本 |

**便捷函数**

```python
from ylyw.prior_manual.yao_relations import analyze_yao_relations

report = analyze_yao_relations(yao_vector)
```

---

## 4. 数据格式约定

### 物体特征字段

| 字段 | 类型 | 范围 | 语义 |
|------|------|------|------|
| `stability` | float | [0,1] | 0=极易倾倒（球体），1=极稳（立方体） |
| `roll_tendency` | float | [0,1] | 0=不滚动，1=极易滚动 |
| `strength_needed` | float | [0,1] | 0=轻力，1=最大力 |
| `fragility` | float | [0,1] | 0=坚固，1=极度脆弱 |
| `task_priority` | float | [0,1] | 0=可忽略，1=最高优先级 |
| `reachability` | float | [0,1] | 0=不可达，1=完美可达 |
| `support_area` | float | [0,1] | 0=点支撑，1=全底面支撑 |
| `occlusion` | float | [0,1] | 0=无遮挡，1=完全遮挡 |
| `obstacle_density` | float | [0,1] | 0=无障碍，1=密集拥挤 |
| `grasp_surface_quality` | float | [0,1] | 0=不适合抓取，1=理想表面 |
| `weight_ratio` | float | [0,1] | 相对于夹爪最大承重 |

### 爻向量的"阴阳"判别

```python
yao ≥ 0.5 → 阳爻（—，强/利/积极）
yao < 0.5 → 阴爻（--，弱/不利/消极）
```

### 设计约束

- **零学习依赖**：所有规则均为硬编码先验，推理时无梯度计算
- **完全可解释**：每一步推理有明确语义
- **确定性**：相同输入永远产生相同输出
- **无 GPU 依赖**：纯 NumPy 实现

---

## 5. 完整使用示例

### 5.1 最简调用

```python
from ylyw.prior_manual import PriorManual

manual = PriorManual()
perception, strategy = manual.process({
    'stability': 0.8,
    'roll_tendency': 0.1,
    'strength_needed': 0.6,
    'fragility': 0.2,
    'task_priority': 0.7,
    'reachability': 0.9,
})

print(strategy['type'])   # 输出: power_grasp / precision_grasp / ...
print(strategy['force'])  # 输出: 0.xx
```

### 5.2 分步调用（细粒度控制）

```python
from ylyw.prior_manual import PriorManual

manual = PriorManual(verbose=True)

cube = {
    'stability': 0.9,
    'roll_tendency': 0.05,
    'strength_needed': 0.75,
    'fragility': 0.1,
    'task_priority': 0.5,
    'reachability': 0.95,
    'support_area': 0.9,
    'occlusion': 0.0,
    'obstacle_density': 0.1,
    'grasp_surface_quality': 0.8,
    'weight_ratio': 0.7,
}

# 步骤1：感知与编码
perception = manual.perceive_and_encode(cube)

# 步骤2：获取策略
strategy = manual.get_grasp_strategy(perception)

# 步骤3：查看推理链
print(manual.explain_reasoning(perception))

# 单独访问各层
yao = perception['yao_vector']           # 六爻向量
best = perception['best_hexagram']       # 最佳卦象枚举
yao_report = perception['yao_relations'] # 爻位关系
print(f"当位: {yao_report.dangwei_count}/6")
print(f"谨慎级别: {yao_report.caution_level}")
```

### 5.3 只使用 L1 八卦映射

```python
from ylyw.prior_manual import TrigramBase

trigram_base = TrigramBase()
features = {'stability': 0.2, 'roll_tendency': 0.9, 'strength_needed': 0.3,
            'deformability': 0.4, 'visibility': 0.6, 'fragility': 0.5}

# 获取对八卦的隶属度
memberships = trigram_base.get_all_memberships(features)
print(f"八卦隶属度: {memberships}")  # [0.xx, 0.xx, ...]

# 主导卦象
dominant, score = trigram_base.get_dominant_trigram(features)
print(f"主导卦: {dominant.name}, 得分: {score:.3f}")
```

### 5.4 只使用 L2 六爻编码

```python
from ylyw.prior_manual import YaoEncoder

encoder = YaoEncoder()
features = {
    'stability': 0.3, 'roll_tendency': 0.7,
    'reachability': 0.8, 'occlusion': 0.2, 'grasp_surface_quality': 0.6,
    'strength_needed': 0.5, 'weight_ratio': 0.4,
    'fragility': 0.6, 'task_priority': 0.7, 'obstacle_density': 0.1
}

yao = encoder.encode(features)
print(f"六爻: {yao}")

# 解读
for item in encoder.get_yao_interpretation(yao):
    print(f"  {item['name']}: {item['value']:.3f} ({item['nature']})")
```

### 5.5 只使用 L3+ 爻位关系运算

```python
from ylyw.prior_manual import YaoRelations
import numpy as np

rel = YaoRelations()
yao = np.array([0.7, 0.3, 0.8, 0.2, 0.6, 0.4], dtype=np.float32)

report = rel.analyze(yao)
print(f"当位: {report.dangwei_count}/6")
print(f"综合质量: {report.score_overall:.2f}")
print(f"力修正: {report.strategy_modifier:.2f}")
print(f"谨慎级别: {report.caution_level}")

# 格式化输出
print(rel.format_report(yao, report))
```

### 5.6 批量处理

```python
from ylyw.prior_manual import PriorManual, YaoEncoder

manual = PriorManual()
encoder = YaoEncoder()

# 定义多类物体
objects = [
    {'stability': 0.1, 'roll_tendency': 0.95, ...},  # 球体
    {'stability': 0.9, 'roll_tendency': 0.05, ...},  # 立方体
    {'stability': 0.3, 'roll_tendency': 0.7, ...},   # 圆柱体
]

# 批量编码
yao_batch = encoder.encode_batch(objects)
print(f"批量爻向量形状: {yao_batch.shape}")  # (3, 6)

# 逐个推理
for obj in objects:
    _, strategy = manual.process(obj)
    print(f"类型={strategy['type']}, 力={strategy['force']:.2f}")
```

---

## 6. 源代码位置

```
ylyw/
├── experiment_phase1/ylyw_core/   ← 核心库（推荐使用）
│   ├── __init__.py                # 导出 PriorManual, TrigramBase 等
│   ├── trigram_base.py            # L1 八卦基元（231 行）
│   ├── yao_encoder.py             # L2 六爻编码器（186 行）
│   ├── hexagram_rules.py          # L3 六十四卦规则库（1333 行）
│   ├── yao_relations.py           # L3+ 爻位关系运算（431 行）
│   └── prior_manual.py            # 主控类（325 行）
│                                  #   总计：2526 行
│
├── motion_control/                ← 运动控制扩展
│   └── ylyw_adaptive.py           # 自适应控制（561 行）
│
├── perception/                    ← 感知模块（特征提取）
├── prior_manual/                  ← 先验手册副本
├── scripts/                       ← 实验脚本
│   ├── baseline_50objects.py
│   ├── ablation_study.py
│   ├── fewshot_finetune.py
│   └── optimize_templates.py
│
└── x2/ylyw_full_pipeline/         ← 灵犀X2机器人完整流水线

依赖：Python 3.8+, NumPy 1.24+（纯 CPU，零 GPU 依赖）
```

---

## 附录：常见物体特征参考值

| 物体类型 | stability | roll_tendency | strength_needed | fragility | support_area |
|----------|-----------|---------------|-----------------|-----------|--------------|
| 球体 | 0.05-0.2 | 0.85-1.0 | 0.2-0.5 | 0.3-0.6 | 0.02-0.1 |
| 立方体 | 0.7-1.0 | 0.02-0.1 | 0.5-0.9 | 0.05-0.3 | 0.8-1.0 |
| 圆柱体 | 0.2-0.5 | 0.5-0.9 | 0.3-0.6 | 0.2-0.5 | 0.3-0.6 |
| 碗 | 0.5-0.8 | 0.2-0.5 | 0.2-0.5 | 0.3-0.7 | 0.6-0.9 |
| 花瓶 | 0.3-0.6 | 0.2-0.5 | 0.2-0.4 | 0.7-1.0 | 0.3-0.6 |
| 盘子 | 0.6-0.9 | 0.1-0.3 | 0.2-0.4 | 0.3-0.6 | 0.7-1.0 |
| 不规则石块 | 0.2-0.7 | 0.1-0.5 | 0.4-0.8 | 0.1-0.4 | 0.1-0.6 |
| 瓶子 | 0.3-0.6 | 0.4-0.7 | 0.2-0.5 | 0.5-0.9 | 0.2-0.5 |
