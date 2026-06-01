# YLYW — 易理研物

> Yi-Li Inspired Physical World Modeling

基于《易经》符号逻辑的先验知识系统，用于机器人抓取任务的零样本/小样本智能决策。

## 核心思想

将《易经》的**八卦、六爻、六十四卦**体系转化为硬编码的先验知识库，不依赖大量数据训练，通过符号推理直接输出抓取策略。

### 三层先验架构

| 层级 | 模块 | 功能 |
|------|------|------|
| **L1** 八卦基元 | `trigram_base.py` | 8卦 → 物理特征映射 + 隶属度计算 |
| **L2** 六爻编码 | `yao_encoder.py` | 物理世界状态 → 6维爻值向量 |
| **L3** 六十四卦 | `hexagram_rules.py` | 卦象 → 抓取策略（类型/力/角/速） |

### 设计哲学

- **零样本**: 不训练任何参数，纯先验推理
- **可解释**: 每一步推理都有明确的语义（八卦→六爻→卦象）
- **小样本友好**: 如果精度不够，只需微调特征提取的参数，不需要百万级数据

## 目录结构

```
YLYW/
├── __init__.py                    # 包初始化
├── prior_manual/                  # 先验手册核心
│   ├── __init__.py
│   ├── trigram_base.py           # L1: 八卦基元（8卦定义+隶属度）
│   ├── yao_encoder.py            # L2: 六爻编码器（物理→爻值）
│   ├── hexagram_rules.py         # L3: 六十四卦规则库（卦象→策略）
│   └── prior_manual.py           # 主整合类（三层联合推理）
├── perception/                    # 感知模块
│   ├── __init__.py
│   └── feature_extractor.py      # PyBullet 物理特征提取
├── scripts/                       # 演示脚本
│   ├── demo_prior_manual.py      # 纯Python演示（无需仿真）
│   └── demo_feature_extraction.py # PyBullet 集成演示
└── README.md
```

## 快速开始

### 1. 纯 Python 演示（不需要仿真环境）

```bash
cd /home/lijinhan/MXL/科研/YLYW
python3 scripts/demo_prior_manual.py
```

会展示6种不同物体（球体、花瓶、方块、碗、石块、盘子）的八卦映射、六爻分析和抓取策略输出。

### 2. PyBullet 仿真集成（需要安装 pybullet）

```bash
pip install pybullet
python3 scripts/demo_feature_extraction.py          # GUI 模式
python3 scripts/demo_feature_extraction.py --no-gui # 无渲染模式
```

在仿真中创建球体、方块、花瓶，从 PyBullet 提取物理特征后输入先验手册进行推理。

### 3. 作为库使用

```python
from ylyw.prior_manual import PriorManual

# 初始化
manual = PriorManual(verbose=True)

# 定义物体特征
features = {
    'stability': 0.2,         # 不稳定
    'roll_tendency': 0.9,     # 极易滚动
    'strength_needed': 0.3,   # 轻物
    'fragility': 0.2,         # 不易碎
    'task_priority': 0.8,     # 高优先级
    'reachability': 0.9,
    'support_area': 0.1,
    'occlusion': 0.1,
    'obstacle_density': 0.2,
    'grasp_surface_quality': 0.6,
    'weight_ratio': 0.2,
    'visibility': 0.9,
    'deformability': 0.1,
}

# 推理
perception, strategy = manual.process(features)

# 输出推理链
print(manual.explain_reasoning(perception))
```

## 八卦—物理映射

| 卦 | 符号 | 含义 | 物理特征 |
|----|------|------|----------|
| 乾 | ☰ | 健 | 刚性、强力、稳定 |
| 坤 | ☷ | 顺 | 柔性、包容、可变形 |
| 震 | ☳ | 动 | 动态、易滚动、需快速响应 |
| 艮 | ☶ | 止 | 稳固、静止、几乎不滚动 |
| 离 | ☲ | 明/附丽 | 醒目、光滑、适合吸附 |
| 坎 | ☵ | 陷/险 | 易碎、有凹陷、高风险的 |
| 兑 | ☱ | 悦 | 柔软、可用小力 |
| 巽 | ☴ | 入 | 需要顺应、不规则 |

## 抓取策略类型

| 策略 | 来源卦象 | 适用场景 |
|------|----------|----------|
| `power_grasp` | 乾 | 重物、硬物、需要大力 |
| `precision_grasp` | 坤 | 易碎品、柔性、不规则 |
| `dynamic_grasp` | 震 | 球体、圆柱、易滚动 |
| `stable_grasp` | 艮 | 静止物体、底部稳固 |
| `adhesion_grasp` | 离 | 光滑平面、轻质物体 |
| `cautious_grasp` | 坎 | 高风险、有凹陷、精密 |
| `soft_grasp` | 兑 | 软质、食品、外观重要 |
| `compliant_grasp` | 巽 | 不规则、需要适应姿态 |

## 实验路线图

1. ✅ **阶段一（当前）**: 先验手册实现 + 纯Python验证
2. ⬜ **阶段二**: PyBullet仿真集成 + 50物体零样本基线
3. ⬜ **阶段三**: 小样本微调（10次示范微调特征参数）
4. ⬜ **阶段四**: 引入注意力机制（"时位注意力"）
5. ⬜ **阶段五**: 论文撰写

## 依赖

- Python ≥ 3.8
- PyTorch ≥ 1.8（用于余弦相似度计算）
- NumPy
- PyBullet（可选，用于仿真集成）

## 作者

马老师课题组 — 青岛科技大学 信息科学技术学院
