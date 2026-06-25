# YLYW Agent + 官方 ALFWorld 仿真器 — 适配完成报告

## 完成时间
2026-06-13

## 修改文件列表

### 新增文件
1. **`alfworld_official_wrapper.py`** — ALFWorld 官方环境适配器
   - 将 `AlfredTWEnv` (batch mode) 适配为单任务接口
   - 批量处理 `reset()`/`step()` 的结果提取 (batch[0])
   - 从 `traj_data.json` 读取 task_desc/task_type
   - 动作成功/失败判定（基于观测文本关键词）
   - Admissible commands 裁剪（防过长）

2. **`ylyw_alfworld_official.py`** — YLYW + 官方仿真器 主入口
   - 与 `ylyw_alfworld_agent.py` 相同参数接口
   - `--mode all|single|stats`, `--oracle`, `--num`, `--verbose`
   - 结果保存为 JSON

3. **`INSTALL_NOTES.md`** — 官方仿真器安装记录

### 修改文件
1. **`ylyw_alfworld_agent.py`** — `YLYWAgent.update_phase()` 修复
   - 添加 `admissible_commands` 参数
   - 防止 phase 无限递增（检查 subgoal 匹配）
   - 排除 look/inventory/examine 等中性动作

2. **`~/.cache/alfworld/logic/alfred.twl2`** — Grammar fallback
   - `look-variations` 添加 "a wall" fallback

3. **`~/.local/lib/python3.14/site-packages/textworld/envs/pddl/textgen/__init__.py`** — Python 3.14 兼容性修复
   - `EvalSymbol.derive()`: `locals().update()` → `eval(expr, {"__builtins__": {}}, context["variables"])`

## 接口适配

| 维度 | 轻量版 ALFWorldLight | 官方 AlfredTWEnv | 适配后 |
|------|---------------------|-----------------|--------|
| reset() 返回 | (obs:str, info:dict) | tuple of (obs_tuple, info_dict) | ✅ (obs:str, info:dict) |
| step() 返回 | (obs:str, info:dict) | tuple of (obs, scores, dones, infos) | ✅ (obs:str, info:dict) |
| admissible_commands | list | info['admissible_commands'][0] | ✅ list |
| task_type | info['task_type'] | 从 traj_data.json | ✅ info['task_type'] |
| task_desc | info['task_desc'] | 从 traj_data.json | ✅ info['task_desc'] |
| won | info['won'] | info['won'][0] | ✅ info['won'] |
| action_success | exact match vs walkthrough | 基于观测关键词 | ✅ info['action_success'] |

## 初步实验结果

### Oracle 模式 (ground truth task type)
| 仿真器 | 测试数 | 成功数 | 成功率 | 备注 |
|--------|--------|--------|--------|------|
| 轻量版 | 10 | 10 | 100% | 全是 look_at_obj_in_light（前10个按类型排序） |
| 官方版 | 10 | 1 | 10% | 混合任务类型 |

### 已知问题
1. **Phase 卡住**: Agent 在 clean/heat/cool/put 阶段找不到正确的交互对象，导致无限循环
2. **语义匹配弱**: YLYW 的语义评分主要靠单词重叠，对物体-动作的正确配对缺乏理解
3. **探索策略简单**: 按 YLYW 评分排序，失败后没有智能探索

### 轻量版 vs 官方版 差异原因
轻量版 `ALFWorldLight` 的核心逻辑是：
- `step()` 中比较 `actual == expected` → 匹配则推进
- 这意味着只要按 walkthrough 顺序做就能成功

官方版 `AlfredTWEnv` 是真正的交互式环境：
- 需要正确的物体、正确的位置、正确的动作顺序
- 拿错物体会失败（环境真的检查 preconditions）
- 这是真实的 zero-shot 挑战

## 下一步建议
1. **改进 YLYW agent 的语义理解**: 从 task_desc 中提取目标物体名，优先匹配
2. **Phase 恢复机制**: 检测卡住时回退到前一 phase 重试
3. **全量运行**: 跑完 134 个 valid_unseen 任务获取完整结果
4. **论文写作**: 可以先写方法+结果对比，突出 zero-shot 特点

## 运行命令

```bash
# 官方版（推荐用于论文实验）
cd ~/MXL/科研/ylyw/alfworld_exp
python3 ylyw_alfworld_official.py --mode all --oracle --num 134
python3 ylyw_alfworld_official.py --mode single --game 0 --verbose --oracle

# 轻量版（快速原型）
python3 ylyw_alfworld_agent.py --mode all --num 85
```
