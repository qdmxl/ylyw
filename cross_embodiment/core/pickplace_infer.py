#!/usr/bin/env python3
"""
放置任务推理引擎 — 精简版

完全由 YLYW 的 L3 卦象规则驱动。
六爻中的上爻（安全释放信号）自然触发 L3 匹配到"松开/释放"策略。

PickPlaceInfer 仅做最轻量的进度跟踪，不干涉 YLYW 的推理。
"""

import os, sys, math
import numpy as np
from enum import IntEnum

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zhiji_infer import ZhijiInfer

PHASE_NAMES = {0: "执行中", 1: "已完成"}


class PickPlaceInfer(ZhijiInfer):
    """卦象驱动的放置推理"""

    def __init__(self, body_config, body_type='arm6_hand', zhiji=None, target_pos=None):
        super().__init__(body_config, body_type=body_type, zhiji=zhiji)
        self.target_pos = target_pos if target_pos is not None else np.array([0.0, 0.0])
        self.task_completed = False
        self.peak_lift = 0.0

    def start_trajectory(self, object_key='sphere', object_offset=(0, 0)):
        super().start_trajectory(object_key, object_offset)
        # 重置 BodyConfig 中的释放计数器和释放锁
        if hasattr(self.body_config, '_release_counter'):
            self.body_config._release_counter = 0
        if hasattr(self.body_config, '_released_once'):
            self.body_config._released_once = False
        self.task_completed = False
        self.peak_lift = 0.0

    def infer(self, obs, task_desc=None, object_key='sphere', object_offset=(0, 0)):
        lift_mm = obs.get('lift_height', 0.0) * 1000
        self.peak_lift = max(self.peak_lift, lift_mm)

        strategy = super().infer(obs, task_desc=task_desc,
                                 object_key=object_key, object_offset=object_offset)

        st = strategy.get('strategy_type', '')
        if st in ("松开/释放",):
            self.task_completed = True

        strategy['task_completed'] = self.task_completed
        return strategy

    def decode_action(self, strategy, obs, current_ctrl=None):
        return self.body_config.decode_action(strategy, obs, current_ctrl)
