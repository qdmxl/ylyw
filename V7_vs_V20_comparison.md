# V7/V9 与 V18/V20 技术路线对比分析

## 1. 架构层次对比

### V7/V9: 纯规则线性流水线
```
task_desc → 手工先验(keyword匹配) → 任务类型分类 
→ hardcode子目标序列(6种类型固定plan) 
→ 逐阶段 score-based动作选择(线性评分)
→ 遇到困难: fallback到_explore(广度优先)
```
- 世界模型: **无**。只有 visited/explored/object_memory 几个 Set/Dict
- 状体追踪: 纯字符串匹配 ("you see" → 提取物体名)
- 先验知识: 硬编码的 `_object_location_prior` 字典 (~100条)
- 决策: 基于 **scoring heuristic**（目标匹配+未探索加分+先验加分）
- 回退: 线性 `phase--` 回退 + `_explore` 广度优先

### V18/V20: YLYW 易经决策引擎
```
task_desc → GoalParser(NL解析+正则融合) → 目标结构体 
→ 策略池(12+种策略) → 对所有候选动作计算6维六爻编码 
→ 64卦模板匹配 → 吉凶评分 → 最高分执行 
→ 失败检测(state_key比较) → 失败记录+重试
```
- 世界模型: V18符号WorldModel / V20汉字CnWorldModel（完整状态追踪）
- 状态追踪: 容器状态(open/visited/searched/exhausted) + 物体位置 + 工序状态
- 先验知识: YLYW 64卦吉凶评分表 + 六爻编码规则(=先验知识的形式化)
- 决策: 基于 **YLYW评分**(六爻编码+64卦匹配+吉凶打分)
- 回退: 失败检测(state_key不变) → 失败记录 + 策略池重选

## 2. 核心差异：决策机制

| 维度 | V7/V9 | V18/V20 |
|------|-------|---------|
| 决策单位 | "当前阶段" (phase) | "每个候选动作" (per-action) |
| 候选动作数 | 每次1个(输出phase决定) | 所有合法动作(12+策略产出) |
| 评分维度 | 线性(3-4个因素:目标匹配+未探索+先验) | 六维六爻(目标差距/持有/过程/容器/关联/新 颖性) |
| 匹配机制 | if-else 规则 | 64卦余弦相似度 |
| 先验知识 | `_object_location_prior`散列表 | 卦象吉凶评分表(64个固定值) |
| 失败检测 | 无(依赖手工phase++信号) | state_key指纹比较 |
| 回退策略 | phase-- 回到上一阶段 | 失败记录→策略池重选 |

### V7 为什么经常失败？

**根本原因: 线性plan的脆弱性**

1. **无状态追踪**：V7不知道"门关着没"，不知道"这个物体我已经拿过了"，全靠正则从admissible list反向推理
2. **无失败检测**：plan推进靠"如果我执行了go_to且obs包含目标物体名，phase++"。如果物体在closed容器里，V7会卡在 find_phase 反复go_to
3. **单候选动作**：每个phase只产出一个动作，没有"从多个候选中选最优"的机制。如果这个动作不对（如走错房间），浪费步数
4. **先验稀疏**：`_object_location_prior` 只有约100条硬编码规则，每个物体3-4个可能位置，覆盖率有限
5. **plan固化**：6种任务类型各自固定一个plan序列。pick_two_obj_and_place 需要执行8个phase，任何一个phase卡住就全丢
6. **无过程跟踪**：没有"物体是否已加热/已冷却/已清洁"的状态标记。`use_tool` 后的phase推进可能导致重复执行
7. **分步推进**: 需要推进phase时以`task_type`为唯一判断标准

## 3. V18/V20 的改进点

### 3.1 基于六爻的全局面评分
- 不是"找目标→拿→放"的线性plan
- 每个候选a都算一个6维评分向量Y(a)，从6个维度评估动作价值
- 64卦匹配 + 吉凶评分 → 所有候选动作之间可比
- **效果**: 不会出现"phase 2推进了但phase 1没完成"的死锁

### 3.2 完整状态追踪
- 容器状态: visited/is_open/searched/exhausted + contents
- 物体状态: location/inventory(手中)/deposited/processed(工序标记)
- 失败历史: state_key指纹 → failed_sa集合 → 避免重复无效动作
- **效果**: 知道"这个柜子我已经搜过了"、"这个苹果已经洗过了"

### 3.3 策略池：多路候选
- 12+种策略 → 每次产生多个候选动作
- 评分统一入口 → 选最高分
- **效果**: "放苹果"和"开冰箱"同时评分，冰箱没开时"开冰箱"得分更高

### 3.4 YLYW评分 vs 线性评分
- V7: score = match×10 + unexplored×2 + prior×? - recent×3
- V18: Y(a)=[goal_gap, holding, process, container, goal_assoc, novelty]
  score = linear(Y) × f(H*) × aff
- **效果**: 6维编码比3-4个因素的线性组合更精细

## 4. V7 成功率不高的具体原因

### 4.1 找不到物体(最多)
- V7: "go to counter 1" → obs="on counter 1 you see nothing" → phase不变 → 继续go to → 直到遍历完所有位置
- V18/V20: 标记counter 1为searched, exhausted, 策略池自动选下一个未探索容器

### 4.2 不知道关着门
- V7: 到达fridge 1, obs="fridge 1 is closed", V7不处理 → 反复go to
- V18/V20: is_open=True → 策略池生成"open fridge 1" → 执行 → 再看里面

### 4.3 不知道工序完成了没
- V7: 执行了heat → phase++ → 如果有多个物体，不知道哪个热了
- V18/V20: `processed` 标记 + `_hanzi_mark_processed("heat", "hot")` → 精确追踪

### 4.4 双物体任务容易超步
- V7: 8个phase严格依次执行; 放完#1找#2时如果#2在另一个房间→来回跑→超步
- V18/V20: 策略池 + 全局评分 → 不会机械执行plan

### 4.5 无缓存导致重复推理
- V7: 每次都重新匹配、重新提取
- V20: LRU缓存 + 知识库持久化 → 快速

## 5. 对比总结

| 指标 | V7/V9 | V18 | V20 |
|------|-------|-----|-----|
| valid_unseen | ~65% | 79.9% | **98.5%** |
| valid_seen | ~60% | 75.0% | **92.1%** |
| 世界模型 | 无(仅Set/Dict) | 符号WorldModel | 汉字CnWorldModel |
| 命名匹配 | 散列表(100条) | 规则 | 知识库(241条) |
| 决策机制 | 线性phase+score | 六爻+64卦 | 六爻+64卦+知识库 |
| 失败恢复 | phase-- | state_key+重试 | state_key+重试+学习 |
| 缓存 | 无 | 无 | LRU 4096 |
| 每局时间 | ~1.5秒 | ~2.7秒 | ~2.7秒 |
| 行数 | 805行 | 727+596+360+478行 | 756+514+97行 |

**结论**: V7到V20的提升主要来自3个转变:
1. **无世界模型 → 有世界模型**: 从"记住了什么"到"知道了什么"
2. **线性plan → 全局面评分**: 从"按顺序执行"到"从候选里选最优"
3. **散列先验 → 形式化知识**: 从"物体可能在X位置"到"动作的六爻编码+64卦吉凶"
