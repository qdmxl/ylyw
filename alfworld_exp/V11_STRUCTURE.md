# YLYW Agent V11 — 程序结构和运行过程

## 一、文件结构

```
alfworld_exp/
├── run_v11.py                  # 主入口：环境创建 + 经验加载 + 游戏循环
├── ylyw_agent_v11.py           # Agent决策核心 (V10 + 场景记忆/知几V11)
├── zhiji_v11.py                # 知几V11：同义词/位置先验/六爻模板 学习
├── zhichi_learning.py          # 知耻：失败驱动校准（排除/否定/瓶颈/提醒）
├── scene_memory.py             # 场景记忆（V11新增，跨局场景知识）
├── yao_online_tuner.py         # 爻参数在线微调
├── alfworld_official_wrapper.py # ALFWorld 官方环境封装
├── task_desc_parser.py          # 任务描述解析器
└── other files...
```

## 二、运行入口 (run_v11.py)

### 2.1 `__main__` 启动流程

```
1. 创建 env = ALFWorldOfficial(split="valid_unseen")
   - 扫描指定split下的所有游戏文件（134个game.tw-pddl）
   - 返回 env.num_games = 134

2. 创建各学习模块：
   - agent = YLYWAgentV11(verbose, use_oracle_type=False)
   - zhiji = ZhijiV11(verbose)          # 知几
   - zhichi = ZhichiLearning(verbose)   # 知耻
   - scene_memory = SceneMemory(verbose) # 场景记忆
   - yao_tuner = YaoOnlineTuner(verbose) # 爻调

3. 加载经验（如有 --load-exp）
   - 读取 *_zhiji.json, *_zhichi.json, *_scene_mem.json, *_yao.json

4. 知几→爻播种（仅首次运行）
   - 用zhiji.object_location_counts中high-confidence对→初始化yao_tuner.release_confidence

5. 模式选择：
   - --mode single: 单局 verbose 模式
   - --mode all: 全部/指定局数运行

6. 保存经验（如指定 --save-exp）
```

### 2.2 `run_single()` 单局流程

```python
def run_single(env, game_idx, agent, zhiji, zhichi, scene_memory, yao_tuner, verbose):
```

1. **env.reset(game_idx=i)**  →  返回 obs(初始房间描述) + info
   - info 内容：
     - `task_desc`: "Put a clean plate on the counter."
     - `task_type`: "pick_clean_then_place_in_recep"
     - `pddl_params`: {"object_target": "Plate", "parent_target": "CounterTop", ...}
     - `scene`: {"floor_plan": "FloorPlan10", "scene_num": 10}
     - `admissible_commands`: ["go to cabinet 1", ..., "go to countertop 1", ...]
     - `won`: False, `done`: False, `game_file`: "...game.tw-pddl"

2. **parse_task_desc(task_desc)**  →  解析任务类型/目标物体/目标容器/工具
   - 如 "Put a clean plate on the counter." → task_type='pick_clean_then_place_in_recep', targets=['plate'], recep=['countertop'], tool=['sinkbasin']

3. **注入学习引擎**：
   - agent._zhiji = zhiji
   - agent._zhiji_v11 = zhiji (如有get_yao_template方法)
   - agent._zhichi = zhichi
   - agent._scene_memory = scene_memory
   - agent._yao_tuner = yao_tuner

4. **agent.reset(task_desc, task_type, scene=FloorPlan10)**
   - 设置目标物体、目标容器、工具
   - 设置2阶段计划: find_object → take_object → find_tool → use_tool → find_recep → put_object
   - 从场景记忆加载已知物体位置
   - 知几扩展目标物体列表（同义词映射）

5. **主循环** (while steps < MAX_STEPS=50)：
   ```
   a. cmds = info['admissible_commands']  (当前可选动作列表)
   b. action = agent.act(obs, cmds)       (Agent选择动作)
   c. obs, info = env.step(action)        (环境执行动作)
   d. trajectory.append((action, obs, cmds))
   e. agent.update(action, obs, info)     (更新Agent状态/爻调/场景记忆)
   f. 如 won=True → 跳出
   ```

6. **知几学习**: zhiji.observe_trajectory(result, trajectory, scene, task_desc)
   - 从完整轨迹中学习同义词 + 位置先验

7. **知耻学习**: (仅失败时) zhichi.observe_failure(...)
   - 分析失败原因，记录错拿/否定先验/瓶颈等

## 三、Agent 决策核心 (ylyw_agent_v11.py)

### 3.1 `reset(task_desc, task_type, pddl_params, initial_admissible, scene)`

```
输入:
  task_desc: "Put a clean plate on the counter."
  task_type: "pick_clean_then_place_in_recep"
  scene: "FloorPlan10"  (V11新增)

处理流程:
  1. 清空状态 (visited, explored, history, object_memory等)
  2. 设置场景记忆 (self._scene_memory.set_scene(scene))
  
  3. 解析目标:
     - self.target_objects = ['plate']  (小写去编号)
     - self.target_receps = ['countertop']
     - self.target_tools = ['sinkbasin']
     (从 task_desc 和 pddl_params 中提取)
  
  4. 知几扩展目标:
     if hasattr(self, '_zhiji'):
         self.target_objects = self._zhiji.get_expanded_objects(self.target_objects)
         # 如学到 mug↔cup，则扩展后可能变成 ['mug', 'cup']
  
  5. 知耻排除:
     exclusions = self._zhichi.get_wrong_take_exclusions(self.target_objects)
     # 如学到 knife→排除butterknife，则过滤掉butterknife
  
  6. 场景记忆注入:
     scene_objects = self._scene_memory.get_all_object_memory()
     for obj, loc in scene_objects.items():
         self.object_memory[obj] = loc    # 注入已知物体位置
  
  7. 生成计划 (6阶段):
     plan = ['find_object','take_object','find_tool','use_tool','find_recep','put_object']
     
     phase对应：
       0=find_object    (搜索目标物体位置)
       1=take_object    (抓取目标物体)
       2=find_tool      (找工具如sinkbasin)
       3=use_tool       (使用工具清洗/加热/冷却)
       4=find_recep     (找目标放置容器)
       5=put_object     (放置/在目标容器)
       6=done           (完成)
  
  8. 知耻open优先级:
     self._prioritize_open = self._zhichi.should_prioritize_open(task_type)
```

### 3.2 `act(obs, admissible_commands)` → action_str

```
输入:
  obs: 环境描述文本
  admissible_commands: ["go to cabinet 1", "take plate from countertop 2", ...]

处理流程:
  1. _memorize_objects(obs, cmds)
     - 从take命令中提取物体的位置 → 记入 object_memory
     - 同步写入场景记忆 (scene_memory.observe_object_at)

  2. 确定当前阶段 goal = self._current_goal()
     - 基于self.phase返回计划阶段的名称

  3. 优先检查open (V6启发式):
     action = _maybe_open(cmds, goal, obs)
     - 如果在find阶段 且 有open命令可用 且 (未打开或已知需要开)
     - 返回 打开容器的动作

  4. 优先检查机会行为 (V6启发式):
     action = _check_opportunistic(cmds, goal)
     - 如在find_object阶段→检查是否有"take 目标物体"的cmd→直接取
     - 如在find_recep阶段→检查是否有"put/move 手中物体到目标位置"→直接放

  5. 按阶段选择策略:
     case 'find_object':  → _act_find(cmds, 'find_object', obs)
         位置评分系统：对每个 go to 位置计算分数
         评分要素：
           - 基础分 5.0
           - _object_location_prior(objects, location) → 知几位置先验(0-5)
           - 知耻否定先验惩罚(0-2)
           - 知耻瓶颈提示奖励
           - 遍历过的地方减分
         选择最高分位置
     
     case 'take_object':  → _act_take(cmds, goal, obs)
         从可用的take命令中选择目标物体的take
         - 用知耻排除已知错拿物体
     
     case 'find_tool':    → _act_find(cmds, 'find_tool', obs) 
         (类似find，找工具位置)
     
     case 'use_tool':     → _act_use_tool(cmds, obs)
         - 选第一条可用的 use/clean/heat/cool 命令
     
     case 'find_recep':   → _act_find(cmds, 'find_recep', obs)
         (类似find，找目标接收容器)
     
     case 'put_object':   → _act_put(cmds, obs)
         - 爻调评分: 对每个可放置位置，查yao_tuner.get_release_score
         - 排除被爻调blocked的位置
         - 选择最高分位置
         - 如无高分可用→_explore()/fallback()
     
     default/fallback:    → _explore() 或 _fallback()

  6. 返回选中的 action 字符串
```

### 3.3 `update(action, obs, info)` — 每步后更新状态

```
1. 记录步数和历史 (self.history, self.step_count)
2. 跟踪当前所在位置 (从 obs 中提取)
3. 跟踪打开的容器 self.opened_containers (→场景记忆)
4. 爻调跟踪:
   - take 成功/失败 → yao_tuner.observe_take_success/miss
   - put/move 成功/失败 → yao_tuner.observe_release_success/fail
5. _auto_advance(action, obs, info) → 判断是否推进phase
   - took: 如果取了目标物体 → phase+1
   - at tool: 如果到了工具位置 → phase+1
   - used tool: 如果用了工具 → phase+1
   - at recep: 如果到了放置位置 → phase+1
   - placed: 如果放置成功 → phase+1 (完成)
   - found: 如果在find阶段看到了目标物体 → 尝试取
```

### 3.4 `get_trajectory_state()` — 轨迹状态快照

```
返回当前agent的内部状态供知耻学习:
  - holding, phase, visited, object_memory, history等
  - yao_tuner的统计数据
```

## 四、知几V11学习 (zhiji_v11.py)

### 4.1 `observe_trajectory(result, trajectory, scene, task_desc, task_type)`

```
每次游戏完成后调用:

1. 计数 games_played += 1
2. 如成功 → _learn_from_success()
3. 如失败 → total_failure_trajectories += 1
4. _learn_synonyms(trajectory, task_desc) — 同义词学习
5. 从全部trajectory的admissible命令中学习位置先验 (object_location_counts)
   - 对所有take命令: object_location_counts[obj_base][loc_base] += 1
```

### 4.2 `_learn_from_success(result, trajectory, scene, task_desc, task_type)`

```
从成功轨迹学到:
1. 位置关系: object_location_counts[obj_base][loc_base] += 1
2. 跨场景关联: scene_object_dist[scene][loc_base][obj_base] += 1
3. 六爻模板: _learn_yao_from_action(action, phase, task_type)
   - 调用 hanzi_engine 将动词转为六爻向量
   - 累积至 yao_templates[verb]
```

### 4.3 关键接口（被agent调用）

| 方法 | 用途 | 被谁调用 |
|------|------|----------|
| `get_expanded_objects(objects)` | 用同义词扩展目标物 | agent.reset() |
| `get_location_prior_boost(obj, location)` | 位置先验评分(0-5) | agent._act_find() |
| `get_stats()` | 返回学习统计 | run_v11.py 汇总 |
| `save_experience(path)` | 保存经验到JSON | run_v11.py |
| `load_experience(path)` | 加载经验JSON | run_v11.py |

## 五、环境信息详解 (ALFWorld)

### 5.1 env.reset(game_idx=0) 返回的完整信息

```
obs:
  '-= Welcome to TextWorld, ALFRED! =-\n\n
   You are in the middle of a room. Looking quickly around you,
   you see a cabinet 6, a cabinet 5, ..., a countertop 3, a countertop 2,
   a countertop 1, ..., a sinkbasin 1, ...'

info:
  won: False
  done: False
  score: 0
  game_idx: 0
  game_file: '/home/.../game.tw-pddl'
  task_desc: 'Put a clean plate on the counter.'
  task_type: 'pick_clean_then_place_in_recep'
  pddl_params: {
    'object_target': 'Plate',
    'parent_target': 'CounterTop',
    'mrecep_target': '',
    'toggle_target': '',
    'object_sliced': False
  }
  scene: {'floor_plan': 'FloorPlan10', 'scene_num': 10}
  walkthrough_len: 7
  admissible_commands: [
    'go to cabinet 1', 'go to cabinet 2', ..., 'go to countertop 1', ...
  ]  (约28条，全部是go to)
```

### 5.2 env.step(action) 返回

```
成功时:
  obs: 描述文本 (到达新位置/拾取成功/清洗成功等)
  info: {won(是否完成任务), done, score, admissible_commands(更新后)}

失败时:
  obs: 'Nothing happens.' 或类似
  info: {won=False, action_success=False, ...}
```

### 5.3 动作空间

| 动作类型 | 示例 | 效果 |
|----------|------|------|
| `go to <位置>` | `go to countertop 1` | 移动到指定家具 |
| `take <物> from <位置>` | `take plate 2 from countertop 2` | 从位置拿起物体 |
| `open <容器>` | `open fridge 1` | 打开容器查看内部 |
| `close <容器>` | `close fridge 1` | 关闭容器 |
| `put/move <物> in/on/to <位置>` | `move plate 2 to countertop 3` | 放置物体 |
| `clean <物> with <工具>` | `clean plate 2 with sinkbasin 1` | 用水槽清洗 |
| `heat <物> with <工具>` | `heat potato 1 with microwave 1` | 用微波炉加热 |
| `cool <物> with <工具>` | `cool apple 1 with fridge 1` | 用冰箱冷却 |
| `use <工具> on <物>` | `use sinkbasin 1 on plate 2` | 其他工具用法 |
| `look` | `look` | 重新描述当前位置 |
| `examine <物>` | `examine plate 2` | 查看物体详情 |

## 六、单局完整运行示例（verbose模式）

### 游戏 #0: "Put a clean plate on the counter."

**环境初始化后的完整输出：**

```
obs: '-= Welcome to TextWorld, ALFRED! =-\n\n
     You are in the middle of a room. Looking quickly around you,
     you see a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3,
     a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 3,
     a countertop 2, a countertop 1, a drawer 3, a drawer 2,
     a drawer 1, a fridge 1, a garbagecan 1, a microwave 1,
     a shelf 3, a shelf 2, a shelf 1, a sinkbasin 1, a stoveburner 4,
     a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1.'

admissible_commands = 28条全部是go to (初始位置没有take/open/put命令)
```

**Step 0: 第一次act**
```
agent.act() 调用链：
  1. _memorize_objects(obs, cmds)
     - 当前在'中间位置'(无location)，不记忆
  2. _current_goal() → 'find_object' (phase=0)
  3. _maybe_open() → None (没有open命令)
  4. _check_opportunistic() → None (没有take命令)
  5. _act_find(cmds, 'find_object', obs)
     - targets = ['plate']
     - 对14个go_to位置评分：
       countertop 1: 5.0 + 0(知几先验) + ... = 5.0  (目标物plate可能在的柜台)
       countertop 2: 5.0 + ... = 5.0
       countertop 3: 5.0 + ... = 5.0
       cabinet 1: 4.0 (因为不是目标位置)
       ...
     - 选最高分: 'go to countertop 1'

  → agent返回action = 'go to countertop 1'
```

**Step 0: 执行后**
```
obs = 'You arrive at countertop 1. On the countertop 1,
       you see a apple 2, a dishsponge 2, a potato 3, and a ...'

admissible_commands 更新为：
  take命令: 可能出现在当前位置可取的物体
  go_to命令: 可见的其他位置
```

**Step 1: 第二次act**
```
_act_find 重新评分:
  现在当前位置= countertop 1 -> visited +1
  countertop 2: 5.0 (没去过)
  countertop 3: 5.0 (没去过)
  cabinet 1: 3.0 (已经被扣分因为刚才去过的是柜台，但可能仍有高分)
  
  选择 'go to countertop 2'
```

**Step 1: 执行后**
```
obs = 'You arrive at countertop 2. On the countertop 2,
       you see a bread 1, a cellphone 2, ... and a plate 2.'

此时CMDs出现 'take plate 2 from countertop 2'

agent.act() 内部检测:
  _check_opportunistic() → 检测到有 'take plate 2 from countertop 2'
  → 这是目标物体，可以跳过find直接take

  _auto_advance 检测到'目标出现' → phase从0推进到1(take_object)

  → 返回 'take plate 2 from countertop 2'
```

**Step 2: 抓取**
```
obs = 'You pick up the plate 2 from the countertop 2.'
info: won=False

agent.update():
  - 爻调: yao_tuner.observe_take_success('plate', 'countertop') 成功
  - _auto_advance: took → phase=2 (find_tool)
```

**Step 3: 找工具**
```
_act_find(cmds, 'find_tool', obs)
  targets = ['sinkbasin']
  sinkbasin 1: 12.0 (工具位置+知几先验高分)
  cabinet 1: 2.0
  ...
  选择 'go to sinkbasin 1'
```

**Step 4: 使用工具**
```
到达 sinkbasin 1 → phase自动推进到3 (use_tool)
_act_use_tool() → 'clean plate 2 with sinkbasin 1'
```

**Step 5: 找接收容器**
```
_act_find(cmds, 'find_recep', obs)
  targets = ['countertop']
  countertop 3: 12.0 (最高分)
  countertop 1: 7.0
  countertop 2: 7.0
  选择 'go to countertop 3'
```

**Step 6: 放置**
```
到达 countertop 3 → phase=5 (put_object)
_act_put() → 爻调评分后选 'move plate 2 to countertop 3'
  obs = 'You move the plate 2 to the countertop 3.'
  info: won=True → 跳出循环
```

**学习阶段：**
```
zhiji.observe_trajectory(won=True, trajectory, scene='FloorPlan10', ...):
  - 从trajectory的admissible命令中:
    - take plate 2 from countertop 2 → object_location_counts['plate']['countertop'] += 1
    - clean plate 2 with sinkbasin 1 → 工具位置学习
    - 同义词校准: _learn_synonyms()
      - task_desc里有'plate', take到的也是'plate' → 无新同义词

zhichi.observe_failure: 本局成功，不调用
```

## 七、各模块数据流向图

```
run_v11.py (主循环)
   │
   ├─→ env.reset() → obs + info
   │
   ├─→ agent.act(obs, cmds) → action
   │      │
   │      ├─→ _memorize_objects()
   │      │      └─→ scene_memory.observe_object_at()
   │      │
   │      ├─→ _act_find() → score by:
   │      │      ├─ zhiji.get_location_prior_boost()    (知几先验)
   │      │      ├─ zhichi.get_location_penalty()       (知耻否定)
   │      │      ├─ zhichi.get_failure_hint()           (知耻提示)
   │      │      └─ scene_memory.score_location...()    (场景记忆，已禁用)
   │      │
   │      ├─→ _act_take() → filtered by:
   │      │      └─ zhichi.get_wrong_take_exclusions()  (知耻排除)
   │      │
   │      ├─→ _act_put() → scored by:
   │      │      └─ yao_tuner.get_release_score()       (爻调评分)
   │      │
   │      └─→ _explore() / _fallback()                 (兜底)
   │
   ├─→ env.step(action) → obs + info
   │
   ├─→ agent.update()
   │      ├─→ yao_tuner.observe_take_success/fail()     (爻调学习)
   │      ├─→ yao_tuner.observe_release_success/fail()  (爻调学习)
   │      └─→ _auto_advance() → phase推进
   │
   └─→ 循环结束 → 知几/知耻学习
          ├─ zhiji.observe_trajectory()
          └─ zhichi.observe_failure() (仅失败)
```

## 八、成功判断标准

- **env.step()后 info['won']==True** → 任务完成
- 单局**MAX_STEPS=50**步上限，超时判负
- **阶段判断**：agent.plan有6个阶段，phase=6表示所有子目标完成
- agent内部通过 `_auto_advance()` 推测是否推进阶段（不依赖env信号）
- env的won信号是官方标准（基于PDDL goal checking）
