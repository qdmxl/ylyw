# YLYW Agent V10 源代码

## 概述

YLYW V10 Agent = V9 + 知耻学习（失败驱动校准）

核心公式：K = K_prior ⊕ K_zhiji(成功校准) ⊕ K_zhichi(失败校准) ⊕ K_persist(经验持久化)

实验结果：
- V7（静态先验）：90/134 = 67.2%
- V9（+知几学习）：94/134 = 70.1%
- V10（+知几+知耻）：98/134 = 73.1%
- V10+经验持久化（R2收敛）：99/134 = 73.9%

## 文件说明

| 文件 | 行数 | 说明 |
|------|------|------|
| `ylyw_agent_v10.py` | ~850行 | V10 Agent主体（层次化状态机+知耻学习集成） |
| `zhichi_learning.py` | ~530行 | 知耻学习模块（五层失败校准机制） |
| `zhiji_learning.py` | ~260行 | 知己学习模块（同义词/位置/场景校准） |
| `run_v10.py` | ~240行 | 运行脚本（支持--load-exp/--save-exp经验持久化） |
| `task_desc_parser.py` | ~250行 | NL任务描述解析器（方向性解析+同义词） |
| `alfworld_official_wrapper.py` | ~300行 | ALFWorld环境封装（Per-Game Env方案） |

## 运行方式

```bash
# 基础运行（134局）
python3 run_v10.py --mode all

# 带经验持久化
python3 run_v10.py --mode all --save-exp exp_round1 --output v10_round1.json

# 加载经验再跑
python3 run_v10.py --mode all --load-exp exp_round1 --save-exp exp_round2 --output v10_round2.json

# 单局调试
python3 run_v10.py --mode single --game 41 -v
```

## 依赖

- Python 3.10+
- ALFWorld 0.5.0
- TextWorld 1.7.0
- 无GPU，无LLM，无外部API

## 知耻学习五层机制

| 层 | 名称 | 卦象 | 机制 |
|----|------|------|------|
| L1 | 错拿校准 | 睽（乖离）| 对比实际take vs 目标，记录排除映射 |
| L2 | 否定先验 | 困（穷困）| 统计"物体不在某位置"频次，施加惩罚 |
| L3 | 阶段瓶颈 | 蹇（艰难）| 统计(task_type, phase)失败频率 |
| L4 | 步数预算 | 节（节制）| 分析探索比例，建议优先open |
| L5 | 失败聚类 | 明夷（前车之鉴）| 按fingerprint聚类失败模式 |

## 经验持久化格式

### 知几经验 (exp_XXX_zhiji.json)
```json
{
  "synonym_map": {"coffee": ["mug", "cup"], ...},
  "object_location_counts": {"plate": {"countertop": 5, ...}, ...},
  "scene_object_map": {"FloorPlan10": {...}, ...},
  "scene_empty_locations": {...}
}
```

### 知耻经验 (exp_XXX_zhichi.json)
```json
{
  "wrong_take_map": {"knife": ["butterknife"]},
  "object_negative_locations": {"tomato": {"cabinet": 38, ...}, ...},
  "phase_fail_counts": {...},
  "failure_clusters": {...}
}
```

## 版权

青岛科技大学 信息科学技术学院
马兴录教授课题组
2026年6月
