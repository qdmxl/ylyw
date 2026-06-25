# YLYW Agent v2 改进报告

## 完成时间
2026-06-13

## 新增模块

### 1. `llm_semantic_guide.py` — LLM 语义引导器 (Layer 0)
- 从 task_desc 提取目标物体、位置、工具
- 物体→位置关联知识库（50+ 物体 × 位置映射）
- 空间探索优先级排序

### 2. `spatial_exploration_layer.py` — YLYW 空间探索层 (Layer S)
- 八卦框架编码空间状态：位置类型 → 八卦（countertop→坤, sinkbasin→坎, desklamp→离...）
- 空间记忆：记录已访问位置及其物体
- 卦象搜索：根据目标物体卦象决定探索优先级（找兑(金属) → 优先坤(台面)）
- `select_explore_target()`：多层次探索策略

### 3. 修改 `ylyw_alfworld_agent.py`
- `init_v2()`: 初始化增强模块
- `select_action()`: 集成 spatial explorer 接管 go to 决策
- `update_phase()`: 智能阶段推进（检查目标物体/工具是否在当前位置）
- `_entity_match_bonus()`: 实体引导评分
- `_semantic_match()`: 扩充到 100+ 语义对（含大量别名）

## 已验证成功

单游戏测试 **Game 6 (`look_at_obj_in_light`)** 在 v2 下 →
```
[0] P0 go to desk 1
[1] P1 go to desk 2
[2] P2 take mug 3 from desk 2
[3] P3 go to desk 1
[4] P4 use desklamp 1 → *** WON! ***
```

Agent 正确执行了完整任务：先找到 desklamp (desk 1)，再找 mug (desk 2)，拿取 mug，回到 desklamp 位置，使用光源。

## 遗留问题

### 死亡循环 Bug
某些游戏配置中，spatial explorer 在两个"都无法满足目标"的位置之间无限切换。原因是：
- 所有可导航位置都已被访问过
- 没有一个位置含有目标物体（物体在未解锁区域）
- `select_explore_target` 在两个相近评分位置间交替

**建议修复方案**：
- 加入步数限制 + 强制推进（visited > N → 选最佳可用位置强制推进 P1）
- 或者在 spatial explorer 中使用 `history` 的最后几个动作检测循环

### 模块缓存问题
批量运行时 Python 模块缓存导致旧版本代码被使用。需要用 `python3 -u -B` 或子进程来确保最新代码加载。

## 核心洞见

模拟 vs 真实的差异在于：
1. **模拟**：exact match walkthrough → 总能正确推进
2. **真实**：PDDL preconditions → 必须实际找到正确物体/位置

v2 的 LLM + 空间探索方案证明了**可行性**（game 6 在 4 步内完成），但要达到稳定的成功率还需要解决循环探索和更准确的物体定位。
