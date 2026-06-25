# YLYW-ALFWorld 零样本推理实验结果报告

## 实验概述

- **方法**: YLYW (易理模糊模型) 三层先验推理系统
- **测试平台**: ALFWorld valid_unseen (85个任务, 7种类型)
- **Agent类型**: YLYW_3layer_PriorInference (零样本, 无训练)
- **最大步数**: 50步/任务
- **耗时**: 102.5秒

---

## 总体指标

| 指标 | 值 |
|------|-----|
| 总任务数 | 85 |
| 成功 | 46 |
| 失败 | 39 |
| **成功率** | **54.12%** |
| **任务类型识别率** | **69.41%** |
| 平均步数 | 32.7 |
| 总步数 | 2776 |

---

## 按任务类型划分

| 任务类型 | 数量 | 成功 | 成功率 | 平均步数 |
|----------|------|------|--------|----------|
| look_at_obj_in_light | 18 | 16 | **88.9%** | 17.0 |
| pick_two_obj_and_place | 8 | 7 | **87.5%** | 27.9 |
| pick_and_place_simple | 10 | 8 | **80.0%** | 22.0 |
| pick_cool_then_place_in_recep | 12 | 8 | **66.7%** | 32.0 |
| pick_heat_then_place_in_recep | 14 | 7 | **50.0%** | 35.2 |
| pick_clean_then_place_in_recep | 12 | 0 | 0.0% | 50.0 |
| pick_and_place_with_movable_recep | 11 | 0 | 0.0% | 50.0 |

---

## YLYW 三层推理架构

```
宏观层 (Task Type Recognition)
  task_desc → 关键词匹配 → 7种任务类型识别
  准确率: 69.41%

中观层 (Subgoal Decomposition)  
  任务类型 → 步进子目标序列
  例: pick_heat → [go, take, go, heat, go, put]

微观层 (Action Selection)
  admissible_commands → YLYW六爻编码 → 64卦匹配 → 语义评分 → 最优动作
  核心: 每个候选动作计算6爻向量，匹配64卦规则库
```

---

## 关键发现

### 优势
1. **简单任务零样本表现优秀**: look_at_obj_in_light (89%), pick_two (88%), simple (80%)
2. **YLYW先验知识有效**: 64卦规则库提供了有意义的动作语义编码
3. **语义匹配辅助导航**: task_desc与动作参数的模糊匹配帮助选择目标

### 不足
1. **movable_recep和clean任务全部失败**: 任务类型识别错误，需要更精确的关键词匹配
2. **遍历策略效率低**: go to目标太多导致步数浪费
3. **类型识别依赖简单关键词**: 缺少深层语义理解

---

## 改进方向

1. 增强任务类型识别的语义解析（LLM辅助）
2. 优化go to探索策略（启发式排序）
3. 减少无效遍历（预过滤无效目标）
4. 对clean/movable_recep增加专门的关键词检测

---

## 代码路径

- Agent代码: `/home/lijinhan/MXL/科研/ylyw/alfworld_exp/ylyw_alfworld_agent.py`
- 结果JSON: `/home/lijinhan/MXL/科研/ylyw/alfworld_exp/ylyw_alfworld_results.json`
- YLYW内核: `/home/lijinhan/MXL/科研/ylyw/api_docs/ylyw_core/`

## 运行命令

```bash
cd /home/lijinhan/MXL/科研/ylyw/alfworld_exp
PYTHONPATH=/home/lijinhan/MXL/科研/ylyw/api_docs:$PYTHONPATH \
  python3 -u ylyw_alfworld_agent.py --mode all
```
