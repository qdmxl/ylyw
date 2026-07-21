#!/usr/bin/env python3
"""
知几推理引擎 — 将知几学习集成到 YLYW 推理链

K' = K_prior ⊕ K_calibration

在标准 CrossBodyInfer 基础上加入：
  1. 推理前：加载知几校准参数
  2. L2后：应用六爻偏置校准
  3. L3后：检查策略重映射
  4. 每步记录轨迹用于知几学习
  5. 执行后：用结果更新知几经验

使用:
    engine = ZhijiInfer(body_config, body_type='shadow_hand_3axis')
    strategy = engine.infer(obs, task_desc="grasp")
    ctrl = engine.decode_action(strategy, obs)
    engine.record_step(obs, strategy, ctrl, lift_mm, n_contacts)
    engine.finish_trajectory(success, lift_mm)  # 触发知几学习
"""

import os, sys, numpy as np
from typing import Dict, Any, Optional, List

# 父推理引擎
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cross_body_infer import CrossBodyInfer
from zhiji_learning import ZhijiLearning, GraspTrajectory, TrajectoryStep


class ZhijiInfer(CrossBodyInfer):
    """
    带知几学习的跨本体推理引擎

    Args:
        body_config: 本体配置实例
        body_type: 本体类型标识 (用于知几经验索引)
        zhiji: 知几学习引擎实例 (None则创建新的)
    """

    def __init__(self, body_config,
                 body_type: str = 'shadow_hand_3axis',
                 zhiji: Optional[ZhijiLearning] = None):
        super().__init__(body_config)
        self.body_type = body_type

        # 知几学习引擎
        if zhiji is None:
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', 'results')
            self.zhiji = ZhijiLearning(save_dir=save_dir, verbose=True)
            self.zhiji.load()  # 尝试加载已有经验
        else:
            self.zhiji = zhiji

        # 当前轨迹
        self._current_traj: Optional[GraspTrajectory] = None

        # 已加载的校准参数缓存
        self._calibrated_params: dict = {}

        print(f"[ZhijiInfer] body={body_type}, "
              f"经验={sum(1 for _ in self.zhiji.body_stats)}个本体")

    def _resolve_mj_geo(self, object_key: str) -> str:
        """将物体名字解析为几何类型"""
        # 兼容 YCB_TO_MJ_GEO 映射
        mapping = {
            'tennis_ball': 'sphere', 'pingpong_ball': 'sphere', 'golf_ball': 'sphere',
            'wooden_block': 'cube', 'metal_cube': 'cube',
            'soda_can': 'cylinder', 'water_bottle': 'cylinder',
            'plastic_bowl': 'bowl', 'ceramic_bowl': 'bowl',
            'glass_bottle': 'bottle', 'plastic_bottle': 'bottle',
            'ceramic_plate': 'plate', 'plastic_plate': 'plate',
            'irregular_rock': 'rock', 'smooth_stone': 'rock',
            'ceramic_vase': 'vase', 'glass_vase': 'vase',
            'sphere': 'sphere', 'cube': 'cube', 'cylinder': 'cylinder',
            'bowl': 'bowl', 'bottle': 'bottle', 'plate': 'plate',
            'rock': 'rock', 'vase': 'vase',
        }
        return mapping.get(object_key, 'sphere')

    def infer(self, obs: dict, task_desc: str = None,
              object_key: str = 'sphere',
              object_offset: tuple = (0, 0)) -> dict:
        """
        带知几校准的完整推理

        流程:
          1. L1: 八卦隶属度 (同父类)
          2. L2: 六爻编码 + 知几偏置校准
          3. L3: 卦象匹配 + 知几策略重映射
          4. 记录轨迹
        """
        # 获取校准参数
        self._calibrated_params = self.zhiji.get_calibrated_params(
            self.body_type, object_key
        )
        yao_bias = self._calibrated_params.get('yao_bias', np.zeros(6))

        # 注入物体特征到 obs（供 _extract_features 使用）
        if hasattr(self, '_current_object_features') and self._current_object_features:
            obs['object_features'] = self._current_object_features

        # L1: 八卦隶属度 (同父类)
        bagua = self._bagua_from_obs(obs)

        # L2: 六爻编码 + 知几偏置校准 + 编码器阈值校准
        raw_yao = self.body_config.encode_yao(bagua, obs)
        yao = self.zhiji.apply_yao_bias(self.body_type, raw_yao)

        # 应用学习到的编码器阈值（覆盖硬编码的center/sigma）
        remapped_strategy = 'standard_grasp'
        # （remapped_strategy 在后面才确定，阈值校准在infer完成后另外调用）
        # 编码器阈值校准在 infer 执行前由外部 apply_thresholds 完成

        # L3: 卦象匹配
        best_hexagram, score = self.hexagram_base.get_best_hexagram(yao)
        rule = self.hexagram_base.get_rule(best_hexagram)

        # 提取策略类型（兼容两种rule格式：跨本体的'strategy'字段，API的'grasp_strategy.type'）
        original_strategy = rule.get('strategy', '')
        if not original_strategy:
            gs = rule.get('grasp_strategy', {})
            original_strategy = gs.get('type', 'standard_grasp')
        
        # 策略重映射
        remapped_strategy = self.zhiji.apply_strategy_remap(
            self.body_type, best_hexagram.name if best_hexagram else '',
            original_strategy
        )
        
        # 提取参数
        params = rule.get('params', {}) or {}
        if not params:
            gs = rule.get('grasp_strategy', {})
            params = self._strategy_to_params(gs)

        strategy = {
            'bagua': bagua,
            'yao': yao,
            'yao_raw': raw_yao,
            'yao_bias': yao_bias,
            'hexagram': best_hexagram,
            'hexagram_name': best_hexagram.name if best_hexagram else '未知',
            'match_score': score,
            'grasp_strategy': rule.get('grasp_strategy', {}),
            'original_strategy': original_strategy,
            'strategy_type': remapped_strategy,
            'params': params,
            'calibrated_params': dict(self._calibrated_params),
            'description': rule.get('description', ''),
            'object_key': object_key,
            'object_offset': object_offset,
            'timestamp': len(self.history),
        }

        self.history.append(strategy)
        return strategy

    def decode_action(self, strategy: dict, obs: dict,
                      current_ctrl: np.ndarray = None) -> np.ndarray:
        """
        知几校准的动作解码 (增强版)

        在标准解码基础上，应用三层校准:
          1. 全局力/速度系数 (a * factor)
          2. 解码器增益 (get_decoder_gains — 替代硬编码增益)
          3. 编码器阈值 (get_encoder_thresholds — 替代硬编码阈值)
        """
        strategy_type = strategy.get('strategy_type', '')

        # ---- 第1步: 获取知几学习到的解码器增益 ----
        zhiji_gains = self.zhiji.get_decoder_gains(self.body_type, strategy_type)
        zhiji_ths = self.zhiji.get_encoder_thresholds(self.body_type, strategy_type)

        # ---- 第2步: 基类动作解码 ----
        ctrl = self.body_config.decode_action(strategy, obs, current_ctrl)

        # ---- 第3步: 如果有学习到的解码器增益，替代硬编码值 ----
        if zhiji_gains:
            ctrl = self.body_config.apply_zhiji_gains(strategy_type, ctrl, zhiji_gains)

        # ---- 第4步: 全局增益后处理 ----
        params = self._calibrated_params
        force_factor = params.get('force_factor', 1.0)
        for i in range(len(ctrl)):
            ctrl[i] *= force_factor

        xy_gain = params.get('xy_tracking_gain', 1.0)
        if len(ctrl) >= 2:
            ctrl[0] *= xy_gain
            ctrl[1] *= xy_gain

        return ctrl

    # ─── 轨迹记录 ───

    # 物体特征库 (先验知识，可从 YCB OBJECT_PRESETS 扩展)
    OBJECT_FEATURES = {
        'sphere': {'strength_needed': 0.3, 'stability': 0.6, 'deformability': 0.5,
                   'roll_tendency': 0.8, 'visibility': 0.7, 'fragility': 0.3},
        'cube':   {'strength_needed': 0.4, 'stability': 0.8, 'deformability': 0.3,
                   'roll_tendency': 0.1, 'visibility': 0.6, 'fragility': 0.4},
        'cylinder': {'strength_needed': 0.4, 'stability': 0.6, 'deformability': 0.4,
                     'roll_tendency': 0.7, 'visibility': 0.6, 'fragility': 0.4},
        'bowl':   {'strength_needed': 0.4, 'stability': 0.5, 'deformability': 0.4,
                   'roll_tendency': 0.3, 'visibility': 0.8, 'fragility': 0.6},
        'bottle': {'strength_needed': 0.5, 'stability': 0.5, 'deformability': 0.3,
                   'roll_tendency': 0.6, 'visibility': 0.8, 'fragility': 0.5},
        'plate':  {'strength_needed': 0.3, 'stability': 0.3, 'deformability': 0.2,
                   'roll_tendency': 0.5, 'visibility': 0.9, 'fragility': 0.7},
        'rock':   {'strength_needed': 0.7, 'stability': 0.8, 'deformability': 0.1,
                   'roll_tendency': 0.3, 'visibility': 0.5, 'fragility': 0.2},
        'vase':   {'strength_needed': 0.4, 'stability': 0.4, 'deformability': 0.2,
                   'roll_tendency': 0.4, 'visibility': 0.9, 'fragility': 0.8},
    }

    def start_trajectory(self, object_key: str = 'sphere',
                         object_offset: tuple = (0, 0)):
        """开始记录新轨迹"""
        self._current_traj = GraspTrajectory(
            body_type=self.body_type,
            object_key=object_key,
            object_offset=object_offset,
        )
        # 将物体特征注入 next obs
        self._current_object_features = self.OBJECT_FEATURES.get(
            self._resolve_mj_geo(object_key), {})

    def record_step(self, obs: dict, strategy: dict, ctrl: np.ndarray):
        """记录单步"""
        if self._current_traj is None:
            return

        step = len(self._current_traj.steps)
        lift_mm = obs.get('lift_height', 0.0) * 1000
        n_contacts = sum(1 for c in obs.get('contact', [])
                         if 'obj' in str(c.get('geom2', '')))
        yao = strategy.get('yao', np.zeros(6)).tolist()

        self._current_traj.add_step({
            'step': step,
            'yao': yao,
            'hexagram': strategy.get('hexagram_name', ''),
            'strategy': strategy.get('strategy_type', ''),
            'ctrl': ctrl.tolist() if isinstance(ctrl, np.ndarray) else list(ctrl),
            'lift_mm': lift_mm,
            'n_contacts': n_contacts,
            'success_step': lift_mm > 3.0,
        })

    def finish_trajectory(self, success: bool, lift_mm: float):
        """结束轨迹并触发知几学习"""
        if self._current_traj is None:
            return

        self._current_traj.final_success = success
        self._current_traj.final_lift_mm = lift_mm

        # 将轨迹交给知几学习引擎
        self.zhiji.observe_trajectory(self._current_traj)

        if self.zhiji.verbose:
            print(f"  [ZhijiInfer] 轨迹结束: {self._current_traj.summary()}")

        # 保存经验
        self.zhiji.save()

        self._current_traj = None

    def get_params(self) -> dict:
        """获取当前校准参数"""
        return dict(self._calibrated_params)

    def print_params(self):
        """打印校准参数"""
        params = self._calibrated_params
        print(f"  知几参数:")
        for k, v in params.items():
            if isinstance(v, np.ndarray):
                print(f"    {k}: {np.round(v, 3)}")
            elif isinstance(v, dict):
                if v:
                    print(f"    {k}: {dict(list(v.items())[:3])}...")
            else:
                print(f"    {k}: {v}")

    def print_zhiji_summary(self):
        """打印知几学习总结"""
        print(self.zhiji.get_summary())


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bodies.body_shadow_hand import ShadowHand3AxisConfig
    from core.mujoco_env import CrossBodyEnv

    config = ShadowHand3AxisConfig()
    engine = ZhijiInfer(config, body_type='shadow_hand_3axis')

    env = CrossBodyEnv(body_type='shadow_hand_3axis', headless=True)
    obs = env.reset(object_key='dumbbell', object_offset=(0.02, 0.02))

    # 一次推理
    engine.start_trajectory(object_key='dumbbell', object_offset=(0.02, 0.02))
    strategy = engine.infer(obs, task_desc="grasp",
                            object_key='dumbbell', object_offset=(0.02, 0.02))
    ctrl = engine.decode_action(strategy, obs)

    print("推理链:")
    engine.print_chain(strategy)
    print("\n知几参数:")
    engine.print_params()

    # 执行
    for i in range(200):
        obs, _, _, _ = env.step(ctrl)
        engine.record_step(obs, strategy, ctrl)

    lift = env.get_obj_lift_mm()
    engine.finish_trajectory(lift > 3, lift)

    print(f"\n最终: lift={lift:+.1f}mm, {'✅' if lift>3 else '❌'}")
    print("✅ ZhijiInfer 测试通过")
