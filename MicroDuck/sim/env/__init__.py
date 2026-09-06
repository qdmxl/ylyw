"""MicroDuck CPU 仿真环境 —— ylyw 算法验证基座。

独立、无 GPU 依赖。提供:
  - MJCF 加载与“控制友好执行器”生成(改强 XML PD,使能稳定站立/步态)
  - 14 关节命名/顺序映射(HOME 姿态、动作向量顺序与官方 microduck_rl 对齐)
  - 基于 MuJoCo 原生 API 的 step / reset / 状态观测读取
  - 简洁的观测向量接口,便于 ylyw(64卦步态/时序决策)直接消费
"""
from .microduck_env import MicroDuckEnv, StandingEnv, ensure_control_model

__all__ = [
    "MicroDuckEnv",
    "StandingEnv",
    "ensure_control_model",
]
