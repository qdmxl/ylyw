# YLYW零样本任务决策 — 改造方案

## 一、现状问题

Agent依赖硬编码 `TASK_PLANS` 预设阶段顺序，不是真正的零样本：
- 每类任务有几个阶段、什么顺序是写死的
- 新任务类型需要手动添加模板

## 二、改造目标

把顶层规划从:
```
task_desc → task_type → TASK_PLANS[type] → 按阶段选cmd
```
改为:
```
task_desc + obs + history → YLYW六爻评估每个cmd → 选吉爻执行
```

## 三、具体改动方案

### 3.1 删除硬编码
去掉 `ylyw_agent_v11.py` 顶部的：
- `TASK_PLANS` 字典（约60行）
- `TASK_TOOLS` 字典
- 所有 `phase` 相关的阶段推进逻辑

### 3.2 新增模块：YLYW顶层任务规划器

**ylyw_task_planner.py**（已写好初始版本，需集成）：

核心接口 `plan()`：
```
输入: task_desc, admissible_commands, 当前状态(手持/去过哪/已知目标)
处理: 
  1. 将 task_desc 输入 hanzi_engine.sentence() 得到"整体任务六爻"
  2. 对每个cmd分类(action_type)，查其动作六爻模板
  3. 余弦匹配 action_yao vs context_yao 得到评分
  4. 加经验偏置 + 启发式规则修正
输出: 选中的命令 + 评分
```

学习反馈 `observe_step()`：
```
输入: 执行了的命令 + 是否成功
处理:
  成功: 该动作六爻向"成功方向"微调
  失败: 该动作六爻向"失败方向"微调
  学习具体 (action_type:target_base) → 六爻关联
```

### 3.3 改造agent

| 硬编码版本 | YLYW版本 |
|-----------|---------|
| act() 内按 `self.plan[self.phase]` 分阶段调用函数 | act() 内直接用 `planner.plan()` 在所有cmd中选 |
| `_auto_advance()` 推phase | 保留简化版本，仅用于生成反馈信号给planner学习 |
| 每个阶段有独立策略(find/take/put) | 统一评分，不同cmd类别有不同的六爻模板和评分规则 |

### 3.4 需要保留的部分

- `_memorize_objects()` — 物体位置记忆仍然有用
- 知几位置先验 (`zhiji.get_location_prior_boost()`) — 纳入YLYW评分因子
- 知耻排除 (`zhichi.get_wrong_take_exclusions()`) — 作为预过滤
- 爻调 (`yao_tuner.get_release_score()`) — 作为"put"类cmd评分的子因子

## 四、YLYW六爻评分的评分结构

```
score(cmd) = 
  0.30 × cos_sim(action_yao, context_yao)   # 六爻匹配（核心）
+ 0.20 × state_action_experience              # 具体(动作:目标)的经验
+ 0.15 × zhiji_location_boost                 # 知几位置先验
+ 0.10 × yao_tuner_score                      # 爻调（仅put动作）
+ 0.10 × history_bias                         # 去过的位置/失败过的动作减分
+ 0.15 × heuristic_rules                      # 简单启发式（非硬编码计划）
```

六爻匹配中的 `context_yao` 由以下因子融合：
- task_desc 经 hanzi_engine 得到的句级六爻
- 当前步数（步数多了→卦象向"探索"偏移）
- 是否空手（空手→找/取方向；持物→放/用方向）
- 目标是否已知（已知→聚焦方向）

## 五、零样本验证方法

1. **训练集**：不设训练集，从零开始跑
2. **对比基线**：硬编码V11的47%
3. **测试**：同一个 valid_unseen 134局
4. **成功率走势**：前10局（盲走）→ 50局后（有经验）→ 134局（收敛）

## 六、预期结果

- 前10局：肯定低于硬编码（盲走），可能20-30%
- 30-50局后：开始接近硬编码
- 如果能超过硬编码，说明YLYW学到了跨任务泛化的规划知识
- 真正的价值：换一套完全不同结构的任务，零样本可以直接跑
