# YLYW ALFWorld Agent V7

**基于YLYW易理先验知识的ALFWorld零样本具身决策Agent**

- 成功率：67.2%（纯NL，无PDDL）/ 92.5%（含PDDL参数）
- 不使用任何LLM或API调用
- 纯CPU运行，134个任务约180秒

---

## 文件结构

### 核心文件（V7运行必需，共1608行）

| 文件 | 行数 | 说明 |
|------|:----:|------|
| `run_v7.py` | 128 | 运行入口（单游戏/全量测试） |
| `ylyw_agent_v7.py` | 805 | V7 Agent核心（层次化状态机+先验+信号驱动） |
| `task_desc_parser.py` | 266 | 纯NL任务描述解析器（替代PDDL参数） |
| `alfworld_official_wrapper.py` | 409 | 环境适配器（方案B: per-game env） |

### 六层架构扩展模块（已实现，V7部分集成，共2612行）

| 文件 | 行数 | 层级 | 说明 |
|------|:----:|:----:|------|
| `ylyw_nested_spatial.py` | 782 | L0 | 嵌套空间探索模型（八卦空间编码→六爻→64卦策略） |
| `spatial_exploration_layer.py` | 482 | L0 | 空间探索层（八卦框架+位置卦象） |
| `structural_cognition_layer.py` | 353 | L-1 | 结构化认知层（睽/困/艮/既济卦元认知） |
| `skill_evolution_layer.py` | 593 | L-2 | 技能演化层（Skill-Aware Reflection） |
| `llm_semantic_guide.py` | 402 | 辅助 | LLM语义引导器（可选，用于增强NL解析） |

**总计：4220行 Python**

---

## 六层嵌套架构

```
┌──────────────────────────────────────────┐
│  L-2  技能演化层 (SkillEvolution)         │ ← 元学习
│       SKILL_DEFECT / LAPSE / DISCOVERY    │
├──────────────────────────────────────────┤
│  L-1  结构化认知层 (StructuralCognition)  │ ← 元认知
│       睽卦=矛盾 | 困卦=围困 | 艮卦=知止   │
├──────────────────────────────────────────┤
│  L0   空间态势感知层 (NestedSpatial)      │ ← 探索
│       八卦空间编码 → 六爻状态 → 64卦策略   │
├──────────────────────────────────────────┤
│  L3   六十四卦规则匹配层                   │ ← 推理
│       爻向量 × 卦象模板 → 最优策略         │
├──────────────────────────────────────────┤
│  L2   六爻编码层                          │ ← 编码
│       物体匹配·位置·操作·先验·阶段·探索度  │
├──────────────────────────────────────────┤
│  L1   八卦基元/信号提取层                  │ ← 感知
│       take信号 | open信号 | clean信号      │
└──────────────────────────────────────────┘
         ↕ admissible_commands ↕
    ┌────────────────────────────┐
    │   ALFWorld TextWorld 环境   │
    └────────────────────────────┘
```

---

## 运行方式

### 环境要求

```bash
# Python 3.11+
pip install alfworld textworld pyyaml
# ALFWorld数据（首次运行自动下载到~/.cache/alfworld/）
export ALFWORLD_DATA=~/.cache/alfworld
```

### 运行命令

```bash
cd ylyw_alfworld_v7/

# 单个游戏（verbose模式）
TMPDIR=/tmp python3 run_v7.py --mode single --game 0 --no-oracle -v

# 全量134游戏测试（纯NL解析，无PDDL）
TMPDIR=/tmp python3 run_v7.py --mode all --no-oracle

# 全量测试（使用oracle task_type，对比用）
TMPDIR=/tmp python3 run_v7.py --mode all
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--mode single/all` | 单游戏调试 / 全量测试 |
| `--game N` | 指定游戏编号（单游戏模式） |
| `-n N` | 最多测试N个游戏（0=全部） |
| `--no-oracle` | 不使用oracle task_type，完全从NL解析 |
| `-v` | 详细输出 |

---

## 实验结果

### V7（无PDDL依赖，完全公平）

| 任务类型 | 成功率 | 成功/总数 |
|---------|:------:|:---------:|
| look_at_obj_in_light | 83.3% | 15/18 |
| pick_and_place_simple | 50.0% | 12/24 |
| pick_clean_then_place | 74.2% | 23/31 |
| pick_cool_then_place | 71.4% | 15/21 |
| pick_heat_then_place | 73.9% | 17/23 |
| pick_two_obj_and_place | 47.1% | 8/17 |
| **总计** | **67.2%** | **90/134** |

### 对比

| 方法 | 成功率 | 需要LLM | 动作空间 |
|------|:------:|:-------:|:--------:|
| BUTLER | 37% | 否(训练) | generation |
| **YLYW V7** | **67.2%** | **否** | admissible |
| ReAct (GPT-4) | 71% | 是 | admissible |
| Reflexion (GPT-4) | 77% | 是 | admissible |

---

## 核心设计要点

1. **admissible_commands信号驱动**：从合法动作列表中提取物体/位置/操作信号
2. **层次化状态机**：6种任务类型×子目标模板，阶段推进+回退
3. **YLYW常识先验矩阵**：30+物体×10+位置的先验概率，引导探索顺序
4. **Open操作**：自动打开closed容器探索内部物体
5. **容器遍历**：put失败时自动尝试下一个同类容器
6. **物体位置记忆**：记录探索中发现的物体位置

---

## 引用

如使用本代码，请引用：

```
Ma X L, et al. YLYW: A Federated Neuro-Symbolic Embodied Decision-Making
Framework Based on I Ching Prior Symbolic Knowledge. arXiv preprint, 2026.
```
