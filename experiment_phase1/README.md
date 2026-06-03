# YLYW 阶段一：物理验证实验

> 独立实验项目 | 与阶段二研究并行 | 2026-06-02

## 目录结构

```
experiment_phase1/
├── ylyw_core/              # YLYW 推理引擎（从主项目复制，只读）
│   ├── trigram_base.py      # L1 八卦基元
│   ├── yao_encoder.py       # L2 六爻编码
│   ├── hexagram_rules.py    # L3 六十四卦规则（64卦）
│   ├── yao_relations.py     # L3+ 爻位关系运算
│   └── prior_manual.py      # 统一接口
├── perception/              # 视觉特征提取
│   └── feature_extractor.py # 仿真生成 / 真实视觉提取
├── adapter/                 # 灵犀X2 适配层
│   └── ylyw_lingxi_adapter.py  # YLYW策略 → ROS2指令
├── scripts/
│   ├── experiment_main.py   # 实验主控（仿真 + 实物）
│   └── analyze_results.py   # 结果分析与可视化
├── data/                    # 实验数据（JSON）
├── config/                  # 配置文件
└── README.md
```

## 快速开始

### 仿真模式（无需硬件）

```bash
cd experiment_phase1

# 完整实验: 40物体 × 3重复 = 120次推理
python3 scripts/experiment_main.py --objects 40 --repeats 3

# 快速测试: 8物体 × 1次
python3 scripts/experiment_main.py --objects 8 --repeats 1

# 演示模式（逐步展示推理过程）
python3 scripts/experiment_main.py --demo
```

### 实物模式（需灵犀X2 + ROS2）

```bash
# 终端1: 启动灵犀X2 ROS2
# (在机器人计算平台上)
ros2 launch ...  # 待SDK就绪后补充

# 终端2: 运行实验
python3 scripts/experiment_main.py --objects 40 --repeats 3 --physical
```

## 四个实验

| 实验 | 命令 | 输出 |
|------|------|------|
| 一：零样本基线 | `--objects 40 --repeats 3` | `data/experiment_*.json` |
| 二：爻位力修正 | （在主控中自动统计脆弱/坚固组） | modifier 对比 |
| 三：策略多样性演示 | `--demo` | 终端展示 |
| 四：视角鲁棒性 | （待实现） | — |

## 输出数据格式

```json
{
  "experiment_id": "20260602_140000",
  "results": [
    {
      "obj_id": 0,
      "obj_type": "球体",
      "hexagram_name": "震为雷",
      "strategy_type": "dynamic_grasp",
      "force_preset": 0.65,
      "modifier": 0.92,
      "S_yao": 0.51,
      "strategy_label": "reasonable",
      "inference_ms": 1.7
    }
  ]
}
```

## 与主项目的关系

- **共享模块**: `ylyw_core/` 从 `prior_manual/` 复制，阶段一期间锁定版本
- **独立模块**: `perception/`, `adapter/`, `scripts/` 仅存在于实验项目
- 如果主项目 `prior_manual/` 有更新，手动同步到 `ylyw_core/`
- 实验代码的修改**不影响**阶段二研究

## 实验助手

专门的实验助手可通过以下方式启动：
- 在此目录下与 AI 对话
- 负责：运行实验、调试问题、分析数据、维护代码
- 不干涉：阶段二研究、论文写作、主项目开发
