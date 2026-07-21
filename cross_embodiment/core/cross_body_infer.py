#!/usr/bin/env python3
"""
YLYW 跨本体推理引擎 — 串联 L1→L2→L3

数据流:
  1. L1: 传感器状态 → 八卦隶属度 (8维)
  2. L2: 八卦+传感器 → 六爻编码 (6维)  [本体配置化]
  3. L3: 六爻 → 64卦匹配 → 策略参数   [跨本体共享]
  4. 动作解码: 策略 → 关节控制        [本体配置化]

使用:
    engine = CrossBodyInfer(body_config)
    strategy = engine.infer(obs, task_desc="grasp")
    ctrl = engine.decode_action(strategy, obs)
"""

import os, sys, numpy as np
from typing import Dict, Any, Optional

# YLYW 核心 API
YLYW_CORE = os.path.expanduser('~/MXL/科研/ylyw/api_docs/ylyw_core')
sys.path.insert(0, YLYW_CORE)

from trigram_base import TrigramBase
from hexagram_rules import HexagramRuleBase


class CrossBodyInfer:
    """
    跨本体推理引擎

    Args:
        body_config: 本体配置实例 (必须提供 encode_yao 和 decode_action)
    """

    def __init__(self, body_config):
        self.body_config = body_config

        # L1: 八卦基元 (跨本体共享)
        self.trigram_base = TrigramBase()

        # L3: 64卦规则 (跨本体共享)
        self.hexagram_base = HexagramRuleBase()

        # 视觉特征提取器（懒加载, 通过 set_visual_extractor 注入）
        self.visual_extractor = None
        self._use_visual = False

        # 推理历史
        self.history = []

    def infer(self, obs: dict, task_desc: str = None) -> dict:
        """
        完整推理: 状态 → 卦象策略

        Args:
            obs: 环境观测字典
            task_desc: 任务描述 (可选，如 "grasp", "pick")

        Returns:
            strategy: {
                "bagua": 8维隶属度,
                "yao": 6维爻向量,
                "hexagram": 卦象枚举,
                "hexagram_name": 卦名,
                "grasp_strategy": 策略字典,
                "params": 统一参数模板
            }
        """
        # L1: 传感器 → 八卦隶属度
        bagua = self._bagua_from_obs(obs)

        # L2: 八卦+传感器 → 六爻编码 (本体特化)
        yao = self.body_config.encode_yao(bagua, obs)

        # L3: 六爻 → 最佳匹配卦象
        best_hexagram, score = self.hexagram_base.get_best_hexagram(yao)
        rule = self.hexagram_base.get_rule(best_hexagram)

        # 提取统一策略参数
        gs = rule.get('grasp_strategy', {})
        strategy = {
            'bagua': bagua,
            'yao': yao,
            'hexagram': best_hexagram,
            'hexagram_name': best_hexagram.name if best_hexagram else '未知',
            'match_score': score,
            'grasp_strategy': gs,
            'params': self._strategy_to_params(gs),
            'strategy_type': gs.get('type', 'standard_grasp'),
            'description': rule.get('description', ''),
            'timestamp': len(self.history),
        }

        self.history.append(strategy)
        return strategy

    def decode_action(self, strategy: dict, obs: dict,
                      current_ctrl: np.ndarray = None) -> np.ndarray:
        """将策略解码为本体控制信号"""
        return self.body_config.decode_action(strategy, obs, current_ctrl)

    def set_visual_extractor(self, extractor):
        """注入视觉特征提取器"""
        self.visual_extractor = extractor
        self._use_visual = True

    def _bagua_from_obs(self, obs: dict) -> np.ndarray:
        """从传感器观测生成八卦隶属度（多视角视觉+状态融合）"""
        features = self._extract_features(obs)

        # 多视角视觉特征融合
        if self._use_visual and self.visual_extractor is not None:
            rgb = obs.get('rgb', {})
            depth = obs.get('depth', {})

            # 构建多视角视图字典
            views = {}
            for cam_name in ['topview', 'sideview', 'egocentric']:
                if cam_name in rgb and rgb[cam_name] is not None:
                    views[cam_name] = {
                        'rgb': rgb[cam_name],
                        'depth': depth.get(cam_name),
                    }

            if views:
                vis_feat = self.visual_extractor.extract_multiview(views)
                # 视觉特征覆盖物体库预设值
                for k in ['strength_needed', 'stability', 'deformability',
                          'roll_tendency', 'visibility', 'fragility']:
                    if k in vis_feat:
                        features[k] = vis_feat[k]

        # 保存本次特征供外部查询
        self._last_features = dict(features)

        memberships = self.trigram_base.get_all_memberships(features)
        if isinstance(memberships, dict):
            return np.array(list(memberships.values()))
        return np.array(memberships)

    def _extract_features(self, obs: dict) -> dict:
        """从观测提取物理特征 (泛化版)"""
        lift = obs.get('lift_height', 0.0) * 5
        contacts = obs.get('contact', [])
        obj_pos = obs.get('object_pos', np.array([0, 0, 0.76]))
        palm_pos = obs.get('palm_pos', np.array([0, 0, 1.00]))
        xy_dist = np.linalg.norm(palm_pos[:2] - obj_pos[:2])
        z_dist = palm_pos[2] - obj_pos[2]
        n_contacts = len(contacts)

        # 物体特征：先从 obs 取，有 missing 时用 obs 中的物体类型推算
        obj_feat = obs.get('object_features', {})

        return {
            'strength_needed': obj_feat.get('strength_needed', min(1.0, 0.3 + abs(lift) * 2)),
            'stability': obj_feat.get('stability', 1.0 if n_contacts >= 3 else (0.5 if n_contacts >= 1 else 0.1)),
            'deformability': obj_feat.get('deformability', 0.5),
            'roll_tendency': obj_feat.get('roll_tendency', 0.3),
            'visibility': obj_feat.get('visibility', 1.0),
            'fragility': obj_feat.get('fragility', 0.3),
            'lift': float(lift),
            'xy_distance': float(xy_dist),
            'z_distance': float(z_dist),
            'n_contacts': n_contacts,
        }

    def _strategy_to_params(self, gs: dict) -> dict:
        """将 grasp_strategy 转为统一参数模板"""
        force_map = {'low': 0.3, 'medium': 0.5, 'high': 0.7, 'fast': 0.9}
        f = gs.get('force', 0.5)
        speed_str = gs.get('speed', 'medium')
        return {
            'speed': force_map.get(speed_str, 0.5),
            'force': f if isinstance(f, (int, float)) else 0.5,
            'precision': 'high' if speed_str in ('slow',) else 'medium',
        }

    def get_last_strategy(self) -> Optional[dict]:
        return self.history[-1] if self.history else None

    def print_chain(self, strategy: dict = None):
        if strategy is None:
            strategy = self.get_last_strategy()
        if strategy is None:
            print("No inference yet")
            return
        print(f"  L1 八卦: {np.round(strategy['bagua'], 3)}")
        print(f"  L2 六爻: {np.round(strategy['yao'], 3)}")
        print(f"  L3 卦象: {strategy['hexagram_name']} (score={strategy['match_score']:.3f})")
        print(f"     策略: {strategy['strategy_type']}")
        print(f"     参数: {strategy['params']}")


# 快捷导入
trigram_base = TrigramBase()
hexagram_base = HexagramRuleBase()
