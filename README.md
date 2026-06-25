# YLYW（易理研物）

> **从《易经》符号先验到通用具身智能的工程研究**

YLYW 是一个基于《易经》六十四卦作为结构化先验知识的具身智能推理系统。它使用八卦隶属度、六爻编码和六十四卦策略映射三层架构，在完全零训练数据的条件下，为机器人抓取、运动控制、具身导航等多域任务提供可解释的物理推理。

**核心特性：**
- 🚫 **零样本推理** — 无需任何训练数据，443个参数即可输出物理合理策略
- 🔍 **完全可解释** — 每一步推理可追溯到具体的易经概念（八卦→六爻→卦象→爻位关系）
- 🛡️ **天生安全** — 双八卦并行仲裁架构，安全通道拥有最终否决权
- 📦 **嵌入式部署** — 8051单片机定点化版本仅需~80KB，推理约1-2ms
- 🌐 **多域跨域** — 同一架构应用于：物理抓取、运动控制、具身导航、视觉分类、语言审查

---

## 项目结构

```
ylyw/
├── experiment_phase1/          # 核心实验：YCB物体抓取策略推理
│   ├── ylyw_core/              #   YLYW三层核心引擎
│   │   ├── trigram_base.py     #     L1: 八卦隶属度计算
│   │   ├── yao_encoder.py      #     L2: 六爻编码器
│   │   ├── hexagram_rules.py   #     L3: 64卦策略映射库
│   │   ├── prior_manual.py     #     先验手册主类（统一推理接口）
│   │   └── yao_relations.py    #     L3+: 爻位关系运算(当位/得中/乘承/亲比/呼应)
│   ├── scripts/                #   实验脚本与批量推理引擎
│   │   ├── ylyw_engine.py      #     YLYW推理引擎CLI
│   │   ├── experiment.py       #     批量实验
│   │   └── data/               #     实验数据
│   └── object_presets.py       #    物体预设特征库（40+种物体）
│
├── anti_hallucination/         # 反幻觉审查系统
│   ├── pipeline.py             #   LLM输出三层审查管线
│   ├── layer1_facts.py         #   事实性审查层
│   ├── layer2_physics.py       #   逻辑/物理一致性审查层
│   ├── layer3_values.py        #   价值合规审查层
│   ├── zhiji_learning.py       #   知几学习（征兆预判）
│   └── demo.py                 #   系统演示
│
├── motion_control/             # 运动控制域：人形机器人步态推理
│   ├── hexagram_gait_rules.py  #   64卦步态模板库
│   ├── trigram_base_motion.py  #   运动L1: 八卦运动原语
│   ├── yao_encoder_motion.py   #   运动L2: 六爻状态编码
│   ├── ylyw_adaptive.py        #   自适应步态引擎
│   ├── real_robot/             #   真实机器人部署
│   │   ├── ylyw_8051.h         #     8051定点推理头文件
│   │   ├── ylyw_standalone.c   #     8051独立运行版
│   │   └── ylyw_xlt_serial.py  #     学灵通机器人串口适配器
│   ├── lingxi/                 #   灵犀人形机器人
│   └── experiments/            #   步态实验
│
├── alfworld_exp/               # ALFWorld具身导航域实验
│   ├── ylyw_agent_v10.py       #   YLYW Agent V10（含知几知耻学习）
│   ├── zhiji_learning.py       #   知几学习（先验征兆辨识）
│   ├── zhichi_learning.py      #   知耻学习（失败驱动校准）
│   ├── task_desc_parser.py     #   自然语言任务描述解析
│   └── run_v10.py              #   实验运行入口
│
├── safety_bagua/               # 双八卦安全约束系统
│   └── double_bagua.py         #   策略八卦 + 安全八卦并行仲裁
│
├── calligraphy/                # 书法轨迹学习域
│   ├── calligraphy_rules.py    #   书法规则库
│   ├── mujoco_env.py           #   MuJoCo书法环境
│   └── learning_loop.py        #   学习回路
│
├── vision/                     # 视觉分类域
│   ├── ylyw_visual_bagua.py    #   八卦视觉分类器
│   └── stl10_eval.py           #   STL-10评估
│
├── perception/                 # 感知前端（视觉→13维特征）
│   └── feature_extractor.py
│
├── language/                   # 语言审查域
│   └── ylyw_language_gate.py
│
├── recursive_ym/               # 递归易经（层次化嵌套原型）
│
├── simulation/                 # 仿真环境
│   └── simulation.py
│
├── prior_manual/               # 先验手册独立版
│   └── prior_manual.py
│
├── monograph/                  # 专著《易理研物》（md源文件）
│   └── ch*.md                  #   第1-10章
│
├── api_docs/                   # API文档
│   └── ylyw_core/              #   核心API文档
│
└── scripts/                    # 通用工具脚本
```

---

## 快速开始

### 安装

```bash
git clone https://github.com/qdmxl/ylyw.git
cd ylyw

# 核心推理引擎只需 numpy
pip install numpy

# 完整实验（可选）
pip install pygame mujoco matplotlib
```

### 运行第一个推理

```python
from experiment_phase1.ylyw_core.prior_manual import PriorManual

# 创建先验手册
manual = PriorManual(verbose=True)

# 定义物体特征
features = {
    'stability': 0.10,           # 球体：极不稳定（点接触）
    'roll_tendency': 0.92,       # 极高滚动倾向
    'strength_needed': 0.35,     # 力需求中等
    'fragility': 0.72,           # 脆弱性偏高
    'reachability': 0.80,        # 可达性好
    'grasp_surface_quality': 0.65,
    'support_area': 0.08,        # 支撑面积极小
    'occlusion': 0.05,
    'obstacle_density': 0.10,
    'task_priority': 0.50,
    'weight_ratio': 0.20,
    'visibility': 0.85,
    'deformability': 0.15,
}

# 完整推理链：特征 → L1八卦隶属度 → L2六爻编码 → L3卦象匹配 → 策略
perception, strategy = manual.process(features)

print(f"策略类型: {strategy['type']}")
print(f"力预设: {strategy['force']:.2f}")
print(f"来源卦象: {strategy['hexagram']}")

# 输出可解释推理链
print(manual.explain_reasoning(perception))
```

**预期输出：**
```
策略类型: dynamic_grasp
力预设: 0.45
来源卦象: 震为雷

════════════════════════════════════════
【YLYW 先验推理链】
────────────────────────────────────────
▎L1 八卦基元映射
  物体呈现「震」卦（动）特性
  隶属度: 0.87

▎L2 六爻状态分析
  初爻(稳定性): [█░░░░░░░░░] 0.163 → 阴爻（-- 弱/不利）
  二爻(可达性): [████████░░] 0.815 → 阳爻（— 强/利）
  ...

▎L3 卦象综合判断
  卦象: 「震为雷」 ☳☳
  卦辞: 震动不安，动态万变
  匹配度: 0.941

▎决策输出
  抓取类型: dynamic_grasp
  力预设: 0.45  |  接近角: 10°
  速度: medium
════════════════════════════════════════
```

### 命令行批量推理

```bash
cd experiment_phase1/scripts

# 单物体推理
python3 ylyw_engine.py --object tennis_ball

# 批量推理（40物体×3重复）
python3 ylyw_engine.py --batch --objects 40 --repeats 3 --csv results.csv

# 演示模式（展示完整推理链）
python3 ylyw_engine.py --demo
```

---

## 核心架构

YLYW基于三层联邦式神经符号架构：

```
传感器 → 13维物理特征 f
         │
    ┌────▼─────────────────────────────────────┐
    │  L1: 八卦隶属度                          │
    │  f → 高斯核 → μ∈[0,1]⁸                   │
    │  输出: 物体对8卦的连续隶属程度              │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │  L2: 六爻编码                            │
    │  μ → 6条加权聚合公式 → y∈[0,1]⁶           │
    │  输出: 6个语义爻值 + 阴阳判定              │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │  L3: 六十四卦匹配                         │
    │  y → 余弦相似度 → 最佳卦象 g*              │
    │  输出: 策略类型 + 初始力预设               │
    │  Top-3 备选卦象（供变卦使用）              │
    └────┬─────────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────┐
    │  L3+: 爻位关系运算                        │
    │  当位 · 得中 · 乘承 · 亲比 · 呼应          │
    │  输出: S_yao质量评分 + 力修正系数          │
    └────┬─────────────────────────────────────┘
         │
         ▼
    最终策略: (类型, 力, 速度, 角度, 注意事项)
```

总参数量：443个。单次推理约1.7ms（CPU）。

---

## 实验结果摘要

| 域 | 实验 | 关键指标 | 训练数据 |
|:---|------|:---:|:---:|
| 物理抓取 | YCB 300物体零样本 | 92.7%策略合理率 | 0 |
| 运动控制 | 11种步态零样本映射 | 10/14场景合理 | 0 |
| ALFWorld | 文本交互具身导航 | 90.0%一致子集 | 0 |
| 视觉分类 | STL-10零样本八卦分类 | 37% Top-1 | 0 |
| 语言审查 | 三层LLM输出反幻觉 | 红/黄/蓝/绿四级判定 | 0 |
| 安全仲裁 | 304物体双八卦审核 | 0%严重错误，100%拦截率 | 0 |
| 嵌入式 | 8051定点推理 | 1-2ms推理，80KB | 0 |

---

## 相关论文

- **YLYW技术论文**: `arxiv_submission/YLYW技术论文_v0.4.pdf`
- **ALFWorld实验报告**: `alfworld_exp/EXPERIMENT_REPORT.md`
- **反幻觉系统**: `anti_hallucination/paper_and_code/`
- **API文档**: `api_docs/README.md`

---

## 引用

```bibtex
@book{ma2026ylyw,
  title     = {易理研物：从符号先验到通用智能的工程研究},
  author    = {马兴录},
  year      = {2026},
  publisher = {青岛科技大学}
}
```

---

## 许可

本项目代码仅供学术研究使用。详见各子目录中的许可声明。

© 2026 马兴录. 青岛科技大学 信息科学技术学院.
