# LIBERO-PRO × YLYW —— 易理模型零样本泛化验证

> 子项目目标：在 **LIBERO-PRO** 基准上评估 YLYW（易理研物）模型能达到什么水平，
> 验证"先验规则推理"相对"统计记忆（VLA）"在零样本扰动下是否更鲁棒。

本子项目归属 `ylyw` 项目，源自 `易理探讨15.docx` 的调研结论。

---

## 1. 背景：为什么要做 LIBERO-PRO

| 基准 | 测什么 | 对 YLYW 的价值 |
|------|--------|----------------|
| 标准 LIBERO | 训练/测试任务几乎相同，VLA 靠"记忆"拿 90%+ | 参考基线，不具说服力 |
| **LIBERO-PRO** | 在 4 个维度系统扰动，揭露"死记硬背" | **主战场**：零样本泛化 + 物理合规 |
| ALFWorld | 抽象文本规划（"大脑"） | 补充验证，证明规划能力 |

**LIBERO-PRO 四类扰动**（`libero_pro` 官方定义）：

| 扰动 | 英文 | 含义 | YLYW 对应机制 |
|------|------|------|---------------|
| 物体扰动 | Object Perturbation | 换目标物体的颜色/尺寸/外观 | L1 八卦隶属度按物理特征重算，非视觉 token 匹配 |
| 位置扰动 | Position Perturbation | 改变初始空间位置 | 重算 `reachability` 等爻值 → 卦象随情境变化 |
| 语义扰动 | Semantic Perturbation | 指令改写（grab→pick up） | 语义等价 → 隶属度近似 → 卦象保持一致 |
| 任务扰动 | Task Perturbation | 重新定义任务逻辑 | 关系推理（乘承比应）而非动作序列回放 |

**当前 SOTA 分数（调研数据，2025-10）**：π0 ≈ 44%，SUREFlow ≈ 49%，PRTS ≈ 53.8%，AtomVLA ≈ 48%；
RPent ≈ 92.6%（多模块系统）。→ 分数普遍低迷，任何显著提升学术冲击力都很大。

---

## 2. 现实约束（本地环境实测，2026-09-22）

| 项 | 状态 | 影响 |
|----|------|------|
| MuJoCo | ✅ 3.9.0 可用 | 可做物理仿真 |
| robosuite | ❌ 未安装 | LIBERO/LIBERO-PRO 官方管线依赖它 |
| GPU | ❌ 无（`nvidia-smi` 不存在，VirtualBox） | 无法跑 osmesa/egl 渲染的大规模评测 |
| 磁盘 | ⚠️ 11G 可用（99% 满） | **无法**安装 robosuite+数据集（数 GB） |
| numpy | 2.4.6 | LIBERO 要求 `numpy==1.24.4`，冲突 |

**结论：本地无法直接跑官方 LIBERO-PRO 全流程。** 因此本子项目采取 **三阶段路线**：

1. **阶段一（本机可跑，已完成）**：`sim/` —— 自建轻量 MuJoCo 平面抓取环境 + LIBERO-PRO 四类扰动，
   验证 YLYW 在"位置/物体/语义"扰动下的零样本成功率与稳定性。作为**方法可行性证据**。
2. **阶段二（需算力，待环境）**：接入官方 `libero_pro` 包与数据集，在真·LIBERO-PRO 上跑 YLYW 推理层。
3. **阶段三（论文）**：与 VLA 基线（π0/OpenVLA）对比，产出实验报告与论文。

---

## 3. 目录结构

```
libero_pro/
├── README.md                 # 本文件
├── ROADMAP.md                # 分阶段工作计划与验收标准
├── configs/
│   └── perturbation.yaml     # 四类扰动的参数化配置
├── sim/                      # 阶段一：自建轻量仿真（本机可跑）
│   ├── env.py                #   平面抓取 MuJoCo 环境
│   ├── perturb.py            #   LIBERO-PRO 四类扰动生成器
│   ├── features.py           #   仿真观测 → YLYW 13 维物理特征
│   └── runner.py             #   评测主循环（YLYW 推理 → 动作 → 成功率）
├── ylyw_adapter/
│   └── inference.py          # YLYW 推理层适配（封装 PriorManual）
├── scripts/
│   └── run_local_eval.py     # 一键运行本地评测
├── results/                  # 评测输出（JSON + 图）
└── docs/
    └── 调研摘要_易理探讨15.md # 原始调研结论文档
```

---

## 4. 快速开始（阶段一）

```bash
cd ~/MXL/科研/ylyw/libero_pro
python3 scripts/run_local_eval.py --episodes 20 --perturb all
```

输出：`results/local_eval_<timestamp>.json`

---

## 5. 关键设计决策

1. **YLYW 接哪一层？** LIBERO 输出连续关节力矩；YLYW 输出符号策略 + 力/速度/角度。
   → 采用 `ylyw_adapter/inference.py` 把策略映射为笛卡尔末端目标速度，交由仿真底层 IK/PD 执行。
2. **特征从哪来？** 真·LIBERO-PRO 用视觉+本体状态。本机阶段一从仿真真值提取 13 维物理特征
   （避免依赖视觉模型，聚焦"推理层"验证）；阶段二再接视觉特征。
3. **可解释性优势**：每次决策记录完整卦象推理链，可量化"决策归因覆盖率"。

---

## 6. 关联

- 调研来源：`~/MXL/科研/ylyw/易理探讨15.docx`
- YLYW 核心：`experiment_phase1/ylyw_core/`（`PriorManual`）
- 相近实验：`cross_embodiment/`（MuJoCo + 跨本体，可复用 env 基类）
- ALFWorld 对照：`alfworld_exp/`
