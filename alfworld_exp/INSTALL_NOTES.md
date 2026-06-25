# ALFWorld 官方仿真器安装记录

## 安装时间
2026-06-13

## 环境
- Python 3.14.4
- Ubuntu 26.04 LTS (x86_64, VirtualBox)
- textworld 1.7.0
- alfworld 0.5.0 (editable install)

## 安装步骤

### 1. Clone ALFWorld
```bash
git clone https://github.com/alfworld/alfworld.git /home/lijinhan/alfworld
```

### 2. 安装依赖
```bash
pip install --break-system-packages -e /home/lijinhan/alfworld
```

注：因为 Ubuntu 26.04 的 Python 3.14 是 externally-managed，需要用 `--break-system-packages`。如果需要虚拟环境，可以在 ext4 分区（非共享文件夹）创建 venv。

### 3. 下载数据
```bash
alfworld-download
```

### 4. 重新生成 game files
```bash
yes y | alfworld-generate --data_path ~/.cache/alfworld/json_2.1.1/valid_unseen --save_path ~/.cache/alfworld/json_2.1.1/valid_unseen
```

### 5. 关键修复

#### 修复 1: Python 3.14 `locals()` 兼容性问题

**文件**: `/home/lijinhan/.local/lib/python3.14/site-packages/textworld/envs/pddl/textgen/__init__.py`

**原因**: TextWorld 的 `EvalSymbol.derive()` 使用 `locals().update(context["variables"])` 来将 context 变量注入 eval 作用域。Python 3.13+ (PEP 667) 中 `locals()` 返回的字典是只读快照，修改它不会影响实际的局部变量绑定。

**修改** (line ~95):
```python
# 旧代码:
def derive(self, context=None):
    context = context or self.context
    locals().update(context["variables"])
    value = eval(self.expression)
    return [TerminalSymbol(value)]

# 新代码:
def derive(self, context=None):
    context = context or self.context
    value = eval(self.expression, {"__builtins__": {}}, context["variables"])
    return [TerminalSymbol(value)]
```

#### 修复 2: Grammar 文件 `look-variations` fallback

**文件**: `~/.cache/alfworld/logic/alfred.twl2`

**原因**: 某些游戏 Agent 初始位置没有 receptacle，`look-variations` 规则需要在 receptacle 不存在时有 fallback。

**修改**: 在 `look-variations` 规则中添加了 fallback `{"rhs": "a wall"}`。

## 验证结果

```
Game 0: ✅ task_type=, adm_cmds=21, obs_len=56
Game 1: ✅ task_type=, adm_cmds=28, obs_len=67
...
Games with proper admissible commands: 10/10
```

## 用法

```python
import os, yaml
from pathlib import Path
from alfworld.agents.environment import get_environment

config_path = Path('/home/lijinhan/alfworld') / 'configs' / 'base_config.yaml'
with open(config_path) as f:
    config = yaml.safe_load(f)
os.environ['ALFWORLD_DATA'] = os.path.expanduser('~/.cache/alfworld')

env = get_environment('AlfredTWEnv')(config, train_eval='eval_out_of_distribution')
env = env.init_env(batch_size=1)

obs, info = env.reset()  # 134 valid_unseen games
# obs: observation string
# info: dict with 'admissible_commands', 'won', 'done', etc.
```

## split 选项
- `train_eval='train'` — 训练集 (~3500 games)
- `train_eval='eval_in_distribution'` — valid_seen (~140 games)
- `train_eval='eval_out_of_distribution'` — valid_unseen (134 games, 推荐用于实验)

## 备份
- grammar 原始备份: `~/.cache/alfworld/logic/alfred.twl2.bak`
- ALFWorld 源码: `/home/lijinhan/alfworld/`
