# YLYW + 官方 ALFWorld 仿真器 — 最终分析报告

## 2026-06-13 16:30

---

## 核心问题：轻量版 100% vs 官方版 ~7% 的差异来源

### 轻量版 ALFWorldLight 的 "100% 成功率" 来自三个层面的作弊

| 作弊层次 | 轻量版 | 官方版 |
|---------|--------|--------|
| **数据集** | 前85个全是 look_at_obj_in_light（最简单类型） | 134个混合6种类型 |
| **admissible_commands** | 手工注入 expert plan 的位置（包括不可见的 countertop/sinkbasin） | PDDL 引擎真实可达位置 |
| **动作成功判定** | `actual == expected`（字符串比对） | PDDL precondition 验证 |

轻量版 Game 0 示例：
- walkthrough: go to desk → take alarmclock → go to desklamp → use desklamp
- 如果 agent 选了 "go to desklamp 1"（被注入的 command），但不在 desk 旁 → 轻量版照常推进
- 官方版：去了 desklamp 但没有 alarmclock 在手 → fail

**结论：轻量版 100% ≠ agent 能力，= 环境没有真实约束。**

---

## 官方版上能成功的条件

### 必要条件：目标物体在初始房间内

- 61.2% 的游戏，目标物体不在初始房间的任何位置 → agent 不可能完成
- 38.8% 的游戏，目标物体在初始房间内 → agent 可能完成

### 成功案例（嵌套 YLYW v3）

3/18 个 look_at_obj_in_light 类型 — 全在物体可达的配置中:

| Game | 描述 | 步骤 |
|------|------|------|
| 6 | Look at a mug in lamp light | P0:desk1 → P1:desk2 → take mug → shelf1 → shelf2 → desk1 → use lamp (7步) |
| 8 | Look at a mug in lamp light | P0:desk1 → P1:desk2 → take mug → desk1 → use lamp (5步) |
| 27 | Look at a mug in lamp light | P0:desk1 → P1:desk2 → take mug → shelf1 → desk1 → use lamp (7步) |

### 失败但可达的案例

pick_heat/cool/clean 类型在物体可达时 **agent 能推进到 task 中间步骤但卡在后半段**。原因是：
- pick_clean: take → go to sinkbasin → clean → go to countertop → put
- 但 agent 在 "go to sinkbasin" 阶段找到正确位置后，clean 命令可能不可用（因为没有同时持有目标物体和站在正确位置）
- 需要更严格的动作序列约束

---

## 嵌套 YLYW 空间模型改进效果

| 特性 | 旧 v2 | 嵌套 v3 |
|------|-------|---------|
| 常识先验固化 | LLM guide 字典 | **YLYW 卦象化 + 置信度矩阵** |
| 场景自适应 | 无 | **每步更新位置置信度** |
| 循环避免 | 死循环在俩位置间 | **自学习降权 → 自动跳出** |
| Game 0 行为 | shelf1→shelf2→shelf1→... | shelf1(0.9)→shelf2(0.7)→...→shelf(0)→bed→desk→... |
| look_at_obj 成功率 | ~1/18 | **3/18 (稳定)** |

---

## 最终结论

"如果目标物体在初始房间内，轻量版 100% 成功" → **这个推论不成立**。

轻量版的 100% 不是 "目标在房间内" 带来的，而是 **绕过了所有环境约束** 带来的。如果把官方版的 look_at_obj_in_light（3/3 物体在房间内）放入轻量版同样的作弊环境，确实会 100%；但在真实 PDDL 环境下，agent 必须真的找到物体、真的拿起来、真的走到正确位置——这才是真正的 zero-shot 挑战。
