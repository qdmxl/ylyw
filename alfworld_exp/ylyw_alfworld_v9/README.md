# YLYW ALFWorld Agent V9（知几学习版）

**基于YLYW先验知识 + 知几学习的ALFWorld零样本具身决策Agent**

## 核心结果

| 版本 | 成功率 | 说明 |
|------|:------:|------|
| V7 (静态先验) | 67.2% (90/134) | K_prior only |
| **V9 (知几学习)** | **70.1% (94/134)** | **K_prior ⊕ K_calibration** |
| 标注一致子集 | **90.0% (90/100)** | 排除标注不一致的34个任务 |

- 不使用任何LLM或API调用
- 纯CPU运行，134个任务约180秒
- 接近ReAct(GPT-4, 71%)的水平

---

## 文件说明

| 文件 | 行数 | 说明 |
|------|:----:|------|
| `run_v9.py` | 194 | 运行入口（含知几学习集成） |
| `ylyw_agent_v9.py` | 809 | Agent核心（状态机+先验+信号驱动+知几校准） |
| `zhiji_learning.py` | 225 | 知几学习模块（同义词校准+位置校准+场景校准） |
| `task_desc_parser.py` | 266 | NL任务描述解析器 |
| `alfworld_official_wrapper.py` | 412 | 环境适配器（方案B: per-game env） |
| **总计** | **1906** | |

---

## 知几学习机制

**K = K_prior ⊕ K_calibration**

```
K_prior（先验知识）：
  - YLYW物体-位置常识先验矩阵
  - 6种任务类型子目标模板
  - NL解析规则

K_calibration（经验校准，运行时积累）：
  第一层：同义词校准
    从admissible中学到: cup→mug, salt→peppershaker, soap→soapbottle
  第二层：位置先验校准
    从成功游戏中学到: plate常在countertop, book常在desk
  第三层：场景结构校准
    从容器交互中学到: 哪些容器需open, 哪些位置是空的
```

按顺序执行134个游戏，每局后从轨迹中"见几而作"，后续游戏自动受益。

---

## 运行方式

```bash
# 环境要求
pip install alfworld textworld pyyaml
export ALFWORLD_DATA=~/.cache/alfworld

# 全量测试（知几学习模式）
cd ylyw_alfworld_v9/
TMPDIR=/tmp python3 -u run_v9.py --mode all

# 单游戏调试
TMPDIR=/tmp python3 -u run_v9.py --mode single --game 0 -v
```

---

## 版本演进

```
V4 (3.7%)  → 修复环境BUG
V5 (64.2%) → admissible信号驱动 + PDDL参数
V6 (92.5%) → +open操作 + 容器遍历 + 记忆（含PDDL）
V7 (67.2%) → 去掉PDDL，纯NL解析
V9 (70.1%) → +知几学习（K_prior ⊕ K_calibration）
```

## 引用

```bibtex
@article{ma2026ylyw,
  title={基于YLYW先验知识的零样本具身决策方法及其在ALFWorld基准上的验证},
  author={马兴录 and 张国安 and 李金函 and 于敬涛 and 李望 and 马圣洁},
  journal={中国科学: 信息科学},
  year={2026}
}
```
