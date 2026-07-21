#!/usr/bin/env python3
"""
知几学习引擎 — 跨本体适配版 (Zhiji Learning for Cross-Embodiment)

《系辞下》："知几其神乎！几者，动之微，吉之先见者也。君子见几而作，不俟终日。"

核心思想：K' = K_prior ⊕ K_calibration

在跨本体泛化中，"几"（征兆）指的是：
  1. YLYW通用推理在本体上的表现偏差
  2. 同种策略在不同本体上的效果差异
  3. 从成功/失败轨迹中提取的本体特性参数

三层次学习:
  L1-参数校准: 本体动作参数微调 (速度/力/精度 的偏移量)
  L2-六爻偏移: 六爻编码函数的偏差校准 (感知偏置)
  L3-规则重映射: 极端情况下重新映射卦象→策略 (少量)

设计原则:
  - 一次观察即校准（"见几而作，不俟终日"）
  - 先验只增强不覆盖（K_calibration是校准不是替换）
  - 经验跨本体复用（同一本体类型共享参数）
  - 可持久化（保存为 JSON）
"""

import os, json, numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field, asdict


@dataclass
class TrajectoryStep:
    """一次抓取尝试中的单步记录"""
    step: int
    yao: List[float]          # 六爻值
    hexagram: str              # 匹配卦象
    strategy: str              # 执行策略
    ctrl: List[float]          # 控制信号
    lift_mm: float             # 提升高度
    n_contacts: int            # 接触手指数
    success_step: bool         # 该步是否产生有效提升


@dataclass
class GraspTrajectory:
    """一次完整抓取尝试的轨迹"""
    body_type: str             # 本体类型
    object_key: str            # 物体类型
    object_offset: Tuple[float, float]  # 物体偏移
    steps: List[TrajectoryStep] = field(default_factory=list)
    final_success: bool = False
    final_lift_mm: float = 0.0

    def add_step(self, step_data: dict):
        self.steps.append(TrajectoryStep(**step_data))

    def summary(self) -> str:
        return (f"{self.object_key} on {self.body_type}: "
                f"{'✅' if self.final_success else '❌'} "
                f"lift={self.final_lift_mm:+.1f}mm, "
                f"{len(self.steps)} steps")


# ─── 可校准参数模板 ───

DEFAULT_PARAMS = {
    # ===== 基础控制增益（本体级）=====
    'speed_factor': 1.0,          # 全局速度系数
    'force_factor': 1.0,          # 全局力系数
    'xy_tracking_gain': 1.0,      # XY追踪灵敏度
    'lift_target': 0.12,          # 提升目标高度(m)

    # ===== 解码器增益表（策略×关节索引，替代decode_action的硬编码增益）=====
    # body_type→strategy→{ctrl_idx: gain, ...}
    # 例: '全力抓取/执行': {0: 50.0, 1: 50.0, 2: 30.0, 6: 0.8}
    'decoder_gains': {},  

    # ===== 编码器阈值表（策略×爻位，替代encode_yao的硬编码阈值）=====
    # body_type→strategy→{yao_index: {center, sigma, ...}}
    'encoder_thresholds': {},

    # ===== L1校准步长（数据驱动，默认手写回退）=====
    'l1_step_force': 0.1,         # 力校准步长
    'l1_step_xy': 0.05,           # XY增益校准步长
    'l1_step_lift': 0.01,         # 提升高度校准步长

    # ===== 策略属性（策略×本体的属性描述）=====
    # 例: {'全力抓取/执行': {'force': 0.8, 'speed': 0.9}}
    'strategy_attrs': {},
}


class ZhijiLearning:
    """
    知几学习引擎 — 跨本体适配版

    从抓取轨迹中观察"几"（性能偏差的征兆），
    自动校准 YLYW 推理参数以适应特定本体。

    使用:
        zhiji = ZhijiLearning()
        zhiji.observe_trajectory(trajectory)  # 从执行中学习
        params = zhiji.get_calibrated_params(body_type, object_key)  # 获取校准后的参数
    """

    def __init__(self, save_dir: str = None, verbose: bool = True):
        self.verbose = verbose

        # 存储目录
        if save_dir is None:
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'results')
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

        # ====== L1: 动作参数校准 ======
        # body_type → object_key → calibrated_params
        self.param_calibration: Dict[str, Dict[str, dict]] = defaultdict(
            lambda: defaultdict(lambda: dict(DEFAULT_PARAMS))
        )

        # 全局统计（本体级别）
        self.body_stats: Dict[str, dict] = defaultdict(lambda: {
            'total_attempts': 0,
            'total_successes': 0,
            'avg_lift': 0.0,
            'strategies_used': defaultdict(int),
            'objects_tried': set(),
        })

        # ====== L2: 六爻偏移校准 ======
        # body_type → 六爻偏移向量
        self.yao_bias: Dict[str, np.ndarray] = defaultdict(lambda: np.zeros(6))

        # 六爻偏差累积（用于统计）
        self.yao_deviation_history: Dict[str, List[np.ndarray]] = defaultdict(list)

        # ====== L3: 规则重映射 ======
        # body_type → { (旧卦象, 旧策略) → 新策略 }
        self.strategy_remap: Dict[str, Dict[tuple, str]] = defaultdict(dict)

        # ====== 最近轨迹缓存 ======
        self.recent_trajectories: List[GraspTrajectory] = []

        # ====== 词汇表 ======
        self._log_prefix = "[知几]"

    # ─── 核心：观察轨迹并学习 ───

    def observe_trajectory(self, trajectory: GraspTrajectory):
        """
        从一次抓取轨迹中学习经验。

        "见几而作"——一次失败的抓取就应该触发校准。
        """
        body = trajectory.body_type
        obj = trajectory.object_key
        success = trajectory.final_success
        lift = trajectory.final_lift_mm

        # 更新全局统计
        stats = self.body_stats[body]
        stats['total_attempts'] += 1
        if success:
            stats['total_successes'] += 1
        stats['avg_lift'] = (stats['avg_lift'] * (stats['total_attempts'] - 1) + lift) / stats['total_attempts']
        stats['strategies_used'][trajectory.steps[-1].strategy if trajectory.steps else 'unknown'] += 1
        stats['objects_tried'].add(obj)

        # 缓存轨迹
        self.recent_trajectories.append(trajectory)

        # === L1 校准：动作参数 ===
        self._calibrate_action_params(trajectory)

        # === L2 校准：六爻偏移 ===
        if not success and trajectory.steps:
            self._calibrate_yao_bias(trajectory)

        # === L3 校准：策略重映射（仅在连续失败时触发） ===
        if not success and self._is_consistently_failing(body, obj, threshold=3):
            self._calibrate_strategy_remap(trajectory)

        if self.verbose:
            print(f"  {self._log_prefix} {body}/{obj}: "
                  f"{'✅' if success else '❌'} "
                  f"总{stats['total_attempts']}次, "
                  f"成功{stats['total_successes']}次 "
                  f"({stats['total_successes']/max(1,stats['total_attempts'])*100:.0f}%)")

        # 保存
        self.save()

    def _calibrate_action_params(self, traj: GraspTrajectory):
        """
        L1 校准 (增强版): 从执行数据中同时学习三类参数
          a) 全局增益: force_factor, xy_tracking_gain, lift_target
          b) 解码器增益: 每个策略×关节索引的特定增益
          c) 编码器阈值: strategy-dependent threshold adaptation

        学习步长也是从历史中统计的（数据驱动），不再硬编码。
        """
        body = traj.body_type
        obj = traj.object_key
        params = self.param_calibration[body][obj]

        # ---- Step 0: 从历史统计中动态调整步长 ----
        step_force = self._estimate_step_size(body, 'force', traj.final_success)
        step_xy = self._estimate_step_size(body, 'xy', traj.final_success)
        step_lift = self._estimate_step_size(body, 'lift', traj.final_success)

        if traj.final_success:
            # 成功: 记录成功时的策略和参数
            if traj.final_lift_mm > 50:
                # 力太过了，稍微降低
                params['force_factor'] = max(0.7, params['force_factor'] - step_force * 0.5)

            # 成功时记录解码器增益的参考值
            if traj.steps:
                last_step = traj.steps[-1]
                # 记录最后一步的策略，供增益表学习
                strategy = last_step.strategy
                if strategy:
                    gains = params.setdefault('decoder_gains', {})
                    sgain = gains.setdefault(strategy, {})
                    ctrl_array = last_step.ctrl
                    for idx, val in enumerate(ctrl_array):
                        if abs(val) > 0.001:
                            sgain[str(idx)] = sgain.get(str(idx), 0.0) * 0.8 + abs(val) * 0.2
        else:
            # 失败分析
            last_steps = traj.steps[-3:] if len(traj.steps) >= 3 else traj.steps

            had_contact = any(s.n_contacts > 0 for s in last_steps)
            had_lift = any(s.lift_mm > 1.0 for s in last_steps)

            if had_contact and not had_lift:
                # 接触了没提起 → 力量不足
                params['force_factor'] = min(1.5, params['force_factor'] + step_force)
                if self.verbose:
                    print(f"    {self._log_prefix} L1: 力不足(步长{step_force:.3f}) → force={params['force_factor']:.2f}")

                # 同时微调最后一步所用策略的力增益
                if last_steps:
                    ls = last_steps[-1]
                    gains = params.setdefault('decoder_gains', {})
                    sgain = gains.setdefault(ls.strategy, {})
                    for i in range(len(ls.ctrl)):
                        # 对非零的力关节增益
                        if abs(ls.ctrl[i]) > 0.05:
                            sgain[str(i)] = min(1.5, sgain.get(str(i), 1.0) + step_force * 0.05)

            elif not had_contact:
                # 没接触 → XY追踪或Z接近距离有问题
                params['xy_tracking_gain'] = min(1.5, params['xy_tracking_gain'] + step_xy)
                if self.verbose:
                    print(f"    {self._log_prefix} L1: 未接触(步长{step_xy:.3f}) → xy_gain={params['xy_tracking_gain']:.2f}")

            else:
                # 接触+提升但失败 → 可能提升目标太高或编码器阈值有偏
                params['lift_target'] = max(0.08, params['lift_target'] - step_lift)
                if self.verbose:
                    print(f"    {self._log_prefix} L1: 提升不足(步长{step_lift:.3f}) → lift={params['lift_target']:.3f}")

    def _estimate_step_size(self, body: str, param_type: str, success: bool) -> float:
        """
        从历史统计中估计校准步长 (数据驱动)
        成功率高时用小步长微调，成功率低时用大步长校正。
        """
        stats = self.body_stats.get(body, {})
        n = stats.get('total_attempts', 0)
        s = stats.get('total_successes', 0)
        rate = s / max(1, n)

        # 成功率高→步长小（微调），成功率低→步长大（调整）
        base_step = {'force': 0.10, 'xy': 0.05, 'lift': 0.010}
        step = base_step.get(param_type, 0.05)

        if rate < 0.3:
            # 成功率低 → 用1.5倍步长快速调整
            return step * 1.5
        elif rate > 0.8:
            # 成功率高 → 用0.5倍步长微调
            return step * 0.5
        else:
            return step

    def _calibrate_yao_bias(self, traj: GraspTrajectory):
        """
        L2 校准: 六爻偏置微调

        原理：如果某个爻的值一直偏高/偏低导致错误策略，
        需要给该爻加上偏置。

        "几"的识别：
          - 某爻在失败时一直为阴/阳 → 可能需要反转阈值
          - 例: 手指已经接触但三爻=0 → 接触力阈值太高
        """
        body = traj.body_type

        # 检查最后几步的六爻序列
        if len(traj.steps) < 2:
            return

        for step in traj.steps[-3:]:
            if step.n_contacts >= 3 and step.yao[2] < 0.5:
                # 明明接触了但三爻=0 → 接触力感知有偏
                self.yao_bias[body][2] += 0.1  # 增加接触感知灵敏度
                if self.verbose:
                    print(f"    {self._log_prefix} L2: 接触感知校准 → yao[2] bias+0.1")
                break

        # 限幅
        self.yao_bias[body] = np.clip(self.yao_bias[body], -0.3, 0.3)

    def _calibrate_strategy_remap(self, traj: GraspTrajectory):
        """
        L3 校准: 策略重映射

        仅当同一物体在同一本体上连续失败时才触发。
        将当前卦象→策略映射替换为更保守或更激进的版本。
        """
        body = traj.body_type
        if not traj.steps:
            return

        last = traj.steps[-1]
        key = (last.hexagram, last.strategy)

        # 如果是"全力抓取"失败 → 换为"缓慢接近"
        if '全力' in last.strategy or 'power' in last.strategy:
            self.strategy_remap[body][key] = '缓慢接近/精确对准'
        # 如果是"未完成"策略连续失败 → 换为"保持接触"
        elif '未完成' in last.strategy:
            self.strategy_remap[body][key] = '保持接触/轻微调整'
        else:
            # 默认降级
            self.strategy_remap[body][key] = '缓慢接近/精确对准'

        if self.verbose:
            print(f"    {self._log_prefix} L3: 策略重映射 {key} → {self.strategy_remap[body][key]}")

    def _is_consistently_failing(self, body: str, obj: str, threshold: int = 3) -> bool:
        """检查是否在连续失败"""
        recent = [t for t in self.recent_trajectories[-10:]
                  if t.body_type == body and t.object_key == obj]
        if len(recent) < threshold:
            return False
        return not any(t.final_success for t in recent[-threshold:])

    # ─── 校准参数获取 ───

    def get_calibrated_params(self, body_type: str,
                              object_key: str,
                              base_params: dict = None) -> dict:
        """
        获取校准后的参数: K' = K_prior ⊕ K_calibration

        Args:
            body_type: 本体类型
            object_key: 物体类型
            base_params: 基础参数 (可选的)

        Returns:
            calibrated_params: 融合先验和校准的参数
        """
        result = dict(DEFAULT_PARAMS)
        if base_params:
            result.update(base_params)

        # 应用L1参数校准
        if body_type in self.param_calibration:
            obj_params = self.param_calibration[body_type].get(object_key, {})
            for k, v in obj_params.items():
                if k not in result:
                    # 旧版特有字段（joint_bias 等）直接跳过
                    continue
                if isinstance(v, (int, float)):
                    result[k] = result.get(k, 1.0) * v if k.endswith('factor') or k.endswith('gain') else v
                elif isinstance(v, dict) and isinstance(result.get(k), dict):
                    result[k].update(v)
                else:
                    result[k] = v

        # 应用L2六爻偏置
        result['yao_bias'] = self.yao_bias.get(body_type, np.zeros(6)).copy()

        # 应用L3策略重映射
        result['strategy_remap'] = dict(self.strategy_remap.get(body_type, {}))

        return result

    def apply_yao_bias(self, body_type: str, yao: np.ndarray) -> np.ndarray:
        """对六爻向量应用校准偏置"""
        bias = self.yao_bias.get(body_type, np.zeros(6))
        return np.clip(yao + bias, 0.0, 1.0)

    def apply_strategy_remap(self, body_type: str,
                             hexagram: str, strategy: str) -> str:
        """检查是否有策略重映射"""
        remaps = self.strategy_remap.get(body_type, {})
        return remaps.get((hexagram, strategy), strategy)

    # ─── 解码器增益表 ───

    def get_decoder_gains(self, body_type: str, strategy: str) -> dict:
        """
        获取学习到的解码器增益表。
        body_config 用它替代 decode_action 中的硬编码增益系数。

        Returns:
            {ctrl_idx: gain_value, ...}
            例: {'0': 45.0, '1': 45.0, '2': 28.0, '6': 0.75}
        """
        params = self.param_calibration.get(body_type, {})
        for obj_key, p in params.items():
            gains = p.get('decoder_gains', {})
            if strategy in gains:
                return dict(gains[strategy])
        return {}

    def get_encoder_thresholds(self, body_type: str, strategy: str) -> dict:
        """
        获取学习到的编码器阈值。
        body_config 用它替代 encode_yao 中的硬编码阈值。

        Returns:
            {yao_index: {center: float, sigma: float}, ...}
        """
        params = self.param_calibration.get(body_type, {})
        for obj_key, p in params.items():
            ths = p.get('encoder_thresholds', {})
            if strategy in ths:
                return dict(ths[strategy])
        return {}

    # ─── 统计查询 ───

    def get_body_stats(self, body_type: str = None) -> dict:
        """获取本体性能统计"""
        if body_type:
            return dict(self.body_stats.get(body_type, {}))
        return {k: dict(v) for k, v in self.body_stats.items()}

    def get_summary(self) -> str:
        """打印总结"""
        lines = ["=" * 60, "知几学习总结", "=" * 60]
        for body, stats in sorted(self.body_stats.items()):
            rate = stats['total_successes'] / max(1, stats['total_attempts']) * 100
            lines.append(f"  {body:20s}: {stats['total_attempts']:3d}次 "
                        f"{rate:3.0f}%成功 "
                        f"avg_lift={stats['avg_lift']:+.1f}mm "
                        f"物体={len(stats['objects_tried'])}种")
            # 显示校准参数
            params = self.param_calibration.get(body, {})
            if params:
                for obj, p in params.items():
                    lines.append(f"    {obj:12s}: force={p['force_factor']:.2f} "
                               f"xy_gain={p['xy_tracking_gain']:.2f}")
            # 显示六爻偏置
            bias = self.yao_bias.get(body)
            if bias is not None and np.any(np.abs(bias) > 0.01):
                lines.append(f"    yao_bias: {np.round(bias, 3)}")

        return "\n".join(lines)

    # ─── 持久化 ───

    def save(self):
        """保存知几经验到文件"""
        path = os.path.join(self.save_dir, 'zhiji_calibration.json')
        data = {
            'version': 2,
            'body_stats': {},
            'param_calibration': {},
            'yao_bias': {},
            'strategy_remap': {},
        }

        # 序列化 body_stats
        for body, stats in self.body_stats.items():
            data['body_stats'][body] = dict(stats)
            data['body_stats'][body]['objects_tried'] = list(stats['objects_tried'])
            data['body_stats'][body]['strategies_used'] = dict(stats['strategies_used'])

        # 序列化 param_calibration
        for body, objs in self.param_calibration.items():
            data['param_calibration'][body] = {}
            for obj, params in objs.items():
                # 只保存新版参数（兼容旧数据不污染新结构）
                valid_keys = {'speed_factor','force_factor','xy_tracking_gain','lift_target',
                              'decoder_gains','encoder_thresholds',
                              'l1_step_force','l1_step_xy','l1_step_lift','strategy_attrs'}
                cleaned = {k: v for k, v in params.items() if k in valid_keys or k.startswith(('l1_','l2_','l3_'))}
                if 'yao_bias' in cleaned:
                    cleaned['yao_bias'] = cleaned['yao_bias'].tolist()
                # 确保主要字段存在
                for k in DEFAULT_PARAMS:
                    if k not in cleaned and k in params:
                        cleaned[k] = params[k]
                data['param_calibration'][body][obj] = cleaned

        # 序列化 yao_bias
        for body, bias in self.yao_bias.items():
            data['yao_bias'][body] = bias.tolist()

        # 序列化 strategy_remap
        for body, remaps in self.strategy_remap.items():
            data['strategy_remap'][body] = {str(k): v for k, v in remaps.items()}

        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: str = None):
        """加载知几经验"""
        if path is None:
            path = os.path.join(self.save_dir, 'zhiji_calibration.json')
        if not os.path.exists(path):
            return False

        with open(path) as f:
            data = json.load(f)

        # 恢复 body_stats
        for body, stats in data.get('body_stats', {}).items():
            self.body_stats[body].update(stats)
            self.body_stats[body]['objects_tried'] = set(stats.get('objects_tried', []))
            self.body_stats[body]['strategies_used'] = defaultdict(int, stats.get('strategies_used', {}))

        # 恢复 param_calibration
        for body, objs in data.get('param_calibration', {}).items():
            for obj, params in objs.items():
                p = dict(DEFAULT_PARAMS)
                p.update(params)
                self.param_calibration[body][obj] = p

        # 恢复 yao_bias
        for body, bias_list in data.get('yao_bias', {}).items():
            self.yao_bias[body] = np.array(bias_list)

        # 恢复 strategy_remap
        for body, remaps in data.get('strategy_remap', {}).items():
            for key_str, val in remaps.items():
                import ast
                key = ast.literal_eval(key_str)
                self.strategy_remap[body][key] = val

        return True

    def reset_body(self, body_type: str):
        """重置某本体的所有校准（用于对比实验）"""
        if body_type in self.param_calibration:
            del self.param_calibration[body_type]
        if body_type in self.yao_bias:
            del self.yao_bias[body_type]
        if body_type in self.strategy_remap:
            del self.strategy_remap[body_type]
        if body_type in self.body_stats:
            self.body_stats[body_type] = {
                'total_attempts': 0, 'total_successes': 0, 'avg_lift': 0.0,
                'strategies_used': defaultdict(int), 'objects_tried': set(),
            }


if __name__ == '__main__':
    # 简单测试
    zhiji = ZhijiLearning(save_dir='/tmp/zhiji_test', verbose=True)

    # 模拟一次失败的抓取轨迹
    traj = GraspTrajectory(
        body_type='shadow_hand_3axis',
        object_key='dumbbell',
        object_offset=(0.0, 0.0),
        final_success=False, final_lift_mm=-1.2
    )
    traj.add_step({'step': 0, 'yao': [0.1, 0.2, 0.8, 0.7, 0.0, 0.9],
                   'hexagram': '䷾ 既济', 'strategy': '全力抓取/执行',
                   'ctrl': [0]*16, 'lift_mm': 0.0, 'n_contacts': 4, 'success_step': False})
    traj.add_step({'step': 1, 'yao': [0.2, 0.3, 0.9, 0.8, 0.1, 0.8],
                   'hexagram': '䷀ 乾为天', 'strategy': '全力抓取/执行',
                   'ctrl': [0]*16, 'lift_mm': -1.2, 'n_contacts': 4, 'success_step': False})

    zhiji.observe_trajectory(traj)

    # 获取校准参数
    params = zhiji.get_calibrated_params('shadow_hand_3axis', 'dumbbell')
    print(f"\n校准后参数: force_factor={params['force_factor']:.2f}")
    print(f"            xy_tracking_gain={params['xy_tracking_gain']:.2f}")

    print("\n" + zhiji.get_summary())
    print("\n✅ ZhijiLearning 测试通过")
