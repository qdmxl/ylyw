#!/usr/bin/env python3
"""
YLYW 自适应运动控制器 (Adaptive Locomotion Controller)
在静态 YLYWLocomotionController 基础上增加在线自适应能力

核心机制：
  1. 推理链记录与回放
  2. 反馈信号驱动的失败诊断
  3. 定向参数修正（L1/L2/L3/爻位关系）
  4. 长期性能追踪

用法：
  controller = YLYWAdaptiveController(learning_rate=0.05)
  for step in range(N):
      state = get_robot_state()
      action = controller.step(state)        # 推理 + 自适应
      execute(action)
      feedback = get_feedback()              # 摔倒/COM偏差/...
      controller.give_feedback(feedback)     # 触发修正
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from ylyw_locomotion import YLYWLocomotionController
from hexagram_gait_rules import HexagramGaitRules


class YLYWAdaptiveController:
    """
    YLYW 自适应运动控制器
    
    与静态控制器的区别：
    - 推理链轨迹可回放
    - 接收反馈信号并自动诊断失败
    - 定向修正 L1/L2/L3/爻位关系 的四层可调参数
    - 记录所有修正历史（可审计、可回滚）
    """
    
    # 默认修正方向映射：对于每个维度，增加爻值的方向（+1=更偏阳, -1=更偏阴）
    YAO_DIM_NAMES = ['姿态', '质心高度', '力分布', 'ZMP裕度', '扰动/能耗', '地形']
    
    def __init__(self, learning_rate=0.05, momentum=0.7, max_correction_per_step=0.08):
        self.controller = YLYWLocomotionController()
        self.lr = learning_rate
        self.momentum = momentum
        self.max_correction = max_correction_per_step
        
        # 推理链轨迹（环形缓冲，保留最近100步）
        self.trajectory = []
        self.max_trajectory = 100
        
        # 参数修正历史
        self.adaptation_log = []
        
        # 动量记忆（防止振荡）
        self._momentum_memory = {
            'L2': np.zeros(6),       # 6维爻阈值动量
            'L3': {hid: np.zeros(6) for hid in range(1, 65)},  # 每个卦的模板动量
            'relation': np.zeros(5),  # 5种关系权重动量
        }
        
        # 统计
        self.total_adaptations = 0
        self.last_diagnosis = None
    
    def step(self, state, feedback=None):
        """
        执行一步推理 + 自适应
        
        Args:
            state: 6D传感器状态向量 [posture, com_h, force_dist, zmp, dist, terrain]
            feedback: dict 上一步的反馈信号（None表示没有反馈/第一步）
                {
                    'fell': bool,           # 是否摔倒
                    'com_deviation': float, # COM偏离期望位置 [0,1]
                    'zmp_margin': float,    # ZMP稳定性裕度 [0,1]
                    'speed_error': float,   # 速度偏差 [0,1]
                    'energy_cost': float,   # 能耗（归一化）
                }
        
        Returns:
            action: gait_params dict（与 YLYWLocomotionController.infer 相同）
        """
        # 如果有反馈，先做自适应修正
        if feedback is not None and len(self.trajectory) > 0:
            self._adapt_from_feedback(feedback)
        
        # 正常推理
        result = self.controller.infer(state, verbose=False)
        
        # 记录轨迹
        self.trajectory.append({
            'state': np.array(state),
            'result': result,
            'feedback': None
        })
        if len(self.trajectory) > self.max_trajectory:
            self.trajectory.pop(0)
        
        return result
    
    def give_feedback(self, feedback):
        """外部传入反馈信号（覆盖最近一步的反馈）"""
        if self.trajectory:
            self.trajectory[-1]['feedback'] = feedback
            # 如果需要立即修正，也可以在这里触发
            # self._adapt_from_feedback(feedback)
    
    def _adapt_from_feedback(self, feedback):
        """
        核心：根据反馈执行定向参数修正
        
        三步法：
          1. 回放最近推理链
          2. 诊断失败原因 → 定位责任层+维度+方向
          3. 修正对应参数
        """
        last = self.trajectory[-1]
        result = last['result']
        
        # 保存反馈
        last['feedback'] = feedback
        
        # 1. 回放推理链（已有结果中的完整信息）
        yao = np.array(result['yao_vector'])
        hex_id = result['hexagram_id']
        gait_name = result['gait_name']
        speed = result['speed']
        
        # 2. 诊断
        diagnosis = self._diagnose_motion(result, feedback)
        
        if diagnosis is None:
            return  # 不需要修正
        
        # 3. 修正
        self._apply_correction(diagnosis)
        
        # 记录
        self.adaptation_log.append({
            'time': time.time(),
            'hexagram_id': hex_id,
            'hexagram_name': result['hexagram_name'],
            'gait_name': gait_name,
            'speed': speed,
            'diagnosis': diagnosis,
            'feedback': {k: v for k, v in feedback.items() if isinstance(v, (int, float, bool))},
        })
        self.total_adaptations += 1
        self.last_diagnosis = diagnosis
    
    def _diagnose_motion(self, result, feedback):
        """
        运动控制失败诊断
        
        诊断优先级：
          1. 步态类型不匹配（来自ground truth标签反馈）
          2. 摔倒（严重）→ L2编码或L3匹配问题
          3. COM偏差大 → L3模板该维度偏高
          4. ZMP裕度不足 → L3模板ZMP维度 + 爻位关系降力
          5. 速度偏差大 → L3模板速度约束
        """
        fell = feedback.get('fell', False)
        com_dev = feedback.get('com_deviation', 0.0)
        zmp_margin = feedback.get('zmp_margin', 0.5)
        speed_err = feedback.get('speed_error', 0.0)
        expected_gait = feedback.get('expected_gait', None)
        
        hex_id = result['hexagram_id']
        yao = np.array(result['yao_vector'])
        template = self.controller.hexagram_rules.get_template(hex_id)
        current_gait = result.get('gait_type', '')
        
        diagnosis = {
            'hexagram_id': hex_id,
            'hexagram_name': result['hexagram_name'],
            'layer': None,
            'dimension': None,
            'direction': 0,  # -1=降低(偏阴), +1=升高(偏阳)
            'reason': '',
            'severity': 'none',
        }
        
        # === 优先: 步态类型标签不匹配（ground truth反馈）===
        if expected_gait and current_gait and current_gait != expected_gait:
            gt_gait = HexagramGaitRules.GAIT_TYPES.get(expected_gait, {})
            gt_speed = gt_gait.get('speed', 0.5)
            current_speed = result.get('speed', 0.5)
            
            if current_speed > gt_speed * 1.2:
                diagnosis['severity'] = 'moderate'
                diagnosis['layer'] = 'L3'
                diagnosis['dimension'] = [0, 2, 4]
                diagnosis['direction'] = -1
                diagnosis['reason'] = (
                    f"步态不匹配: cur={current_gait}(spd={current_speed:.2f}) "
                    f"exp={expected_gait}(spd={gt_speed:.2f}), 降低速度维度"
                )
                return diagnosis
            elif current_speed < gt_speed * 0.8:
                diagnosis['severity'] = 'moderate'
                diagnosis['layer'] = 'L3'
                diagnosis['dimension'] = [0, 2, 4]
                diagnosis['direction'] = +1
                diagnosis['reason'] = (
                    f"步态太慢: cur={current_gait}(spd={current_speed:.2f}) "
                    f"exp={expected_gait}(spd={gt_speed:.2f}), 提升速度维度"
                )
                return diagnosis
            else:
                diagnosis['severity'] = 'mild'
                diagnosis['layer'] = 'L3'
                diagnosis['dimension'] = [0, 3]
                diagnosis['direction'] = -1 if current_speed > gt_speed else +1
                diagnosis['reason'] = (
                    f"步态类型差异: {current_gait} vs {expected_gait} "
                    f"(spd {current_speed:.2f} vs {gt_speed:.2f})"
                )
                return diagnosis
        
        # === 严重：摔倒 ===
        if fell:
            diagnosis['severity'] = 'critical'
            # 检查哪个爻编码最乐观（阳爻但状态差）
            yao_errors = yao - template
            most_optimistic_dim = np.argmax(yao_errors)  # 实际比模板高 = 过于乐观
            
            if yao_errors[most_optimistic_dim] > 0.1:
                # L2: 该维度的阴阳阈值太宽，把不稳的也判成阳
                diagnosis['layer'] = 'L2'
                diagnosis['dimension'] = int(most_optimistic_dim)
                diagnosis['direction'] = -1  # 升高阈值 → 更少判阳
                diagnosis['reason'] = (
                    f"摔倒！第{most_optimistic_dim+1}爻({self.YAO_DIM_NAMES[most_optimistic_dim]})"
                    f" 实际={yao[most_optimistic_dim]:.2f} > 模板={template[most_optimistic_dim]:.2f}，"
                    f"编码过于乐观，升高该爻的阴阳阈值"
                )
            else:
                # L3: 模板本身不对，整体调低
                diagnosis['layer'] = 'L3'
                # 找模板中稳定性相关维度（姿态=0, ZMP=3）
                stable_dims = [0, 3]
                avg_stable_err = np.mean([yao[d] - template[d] for d in stable_dims])
                diagnosis['dimension'] = stable_dims
                diagnosis['direction'] = -1
                diagnosis['reason'] = (
                    f"摔倒！当前卦 {result['hexagram_name']}({hex_id}) "
                    f"稳定性维度偏差{avg_stable_err:+.2f}，调低模板期望"
                )
            return diagnosis
        
        # === 中度：COM偏差大 ===
        if com_dev > 0.20:
            diagnosis['severity'] = 'moderate'
            diagnosis['reason'] = f"COM偏差 {com_dev:.2f} > 0.20"
            
            # COM对应第1爻（index 1: com_height）
            # 偏差大 → 当前卦在该维度的模板值可能偏高
            if template[1] > yao[1] + 0.10:
                diagnosis['layer'] = 'L3'
                diagnosis['dimension'] = 1
                diagnosis['direction'] = -1
                diagnosis['reason'] += f" | 模板COM维度={template[1]:.2f} > 实际={yao[1]:.2f}，降低模板COM期望"
                return diagnosis
            else:
                # L2编码问题
                diagnosis['layer'] = 'L2'
                diagnosis['dimension'] = 1
                diagnosis['direction'] = -1
                diagnosis['reason'] += f" | COM编码偏高，降低阈值"
                return diagnosis
        
        # === 轻度：ZMP裕度不足 ===
        if zmp_margin < 0.25:
            diagnosis['severity'] = 'mild'
            diagnosis['reason'] = f"ZMP裕度 {zmp_margin:.2f} < 0.25"
            
            # ZMP对应第3爻（index 3: zmp_margin）
            diagnosis['layer'] = 'L3'
            diagnosis['dimension'] = 3
            diagnosis['direction'] = -1  # 降低ZMP模板期望 → 更保守
            diagnosis['reason'] += " | 降低ZMP模板期望 + 增强爻位关系保守修正"
            
            # 同时调整爻位关系权重：增加乘承的权重（更注重力学结构）
            diagnosis['relation_adjust'] = {
                'dangwei': 0.00,
                'dezhong': 0.00,
                'cheng_cheng': +0.02,  # 加重乘承
                'bi': 0.00,
                'ying': 0.00,
            }
            return diagnosis
        
        # === 轻度：速度偏差大 ===
        if speed_err > 0.15:
            diagnosis['severity'] = 'mild'
            diagnosis['reason'] = f"速度偏差 {speed_err:.2f} > 0.15"
            diagnosis['layer'] = 'L3'
            # 速度不由单一爻决定，而是卦象整体的步态类型
            # 降低当前卦中速度相关维度（姿态=0, 扰动=4, 地形=5）的模板期望
            diagnosis['dimension'] = [0, 4]
            diagnosis['direction'] = -1
            diagnosis['reason'] += " | 降低姿态和扰动维度的模板期望"
            return diagnosis
        
        # 一切正常
        return None
    
    def _apply_correction(self, diagnosis):
        """
        应用参数修正
        
        根据诊断结果，定向修改L1/L2/L3/爻位关系 的可调参数
        """
        layer = diagnosis['layer']
        direction = diagnosis['direction']
        severity = diagnosis['severity']
        
        # 严重程度决定修正幅度
        severity_scale = {
            'critical': 1.5,
            'moderate': 1.0,
            'mild': 0.6,
        }
        scale = severity_scale.get(severity, 0.5)
        
        if layer == 'L2':
            self._apply_L2_correction(diagnosis, direction, scale)
        elif layer == 'L3':
            self._apply_L3_correction(diagnosis, direction, scale)
        elif layer == 'relation':
            self._apply_relation_correction(diagnosis, direction, scale)
        
        # 如果有额外的爻位关系调整
        if 'relation_adjust' in diagnosis:
            self._apply_relation_weight_adjust(diagnosis['relation_adjust'])
    
    def _apply_L2_correction(self, diagnosis, direction, scale):
        """修正L2阴阳判定阈值"""
        dim = diagnosis['dimension']
        delta = self.max_correction * scale * direction
        
        # 动量平滑
        mem = self._momentum_memory['L2'][dim]
        smoothed = self.momentum * mem + (1 - self.momentum) * delta
        self._momentum_memory['L2'][dim] = smoothed
        
        old = self.controller.yao_encoder.thresholds[dim]
        new = np.clip(old + smoothed, 0.20, 0.80)
        self.controller.yao_encoder.thresholds[dim] = float(new)
        
        direction_str = '↑' if direction > 0 else '↓'
        diagnosis['correction_detail'] = (
            f"L2 第{dim+1}爻({self.YAO_DIM_NAMES[dim]})阈值: "
            f"{old:.3f} → {new:.3f} {direction_str}"
        )
    
    def _apply_L3_correction(self, diagnosis, direction, scale):
        """修正L3爻模板"""
        hex_id = diagnosis['hexagram_id']
        dims = diagnosis['dimension']
        if isinstance(dims, (int, np.integer)):
            dims = [dims]
        
        template = self.controller.hexagram_rules.get_template(hex_id)
        delta = self.max_correction * scale * direction * 0.5  # L3修正幅度减半
        
        for dim in dims:
            mem = self._momentum_memory['L3'][hex_id][dim]
            smoothed = self.momentum * mem + (1 - self.momentum) * delta
            self._momentum_memory['L3'][hex_id][dim] = smoothed
            
            old = template[dim]
            new = np.clip(old + smoothed, 0.02, 0.98)
            template[dim] = new
        
        # 写回
        self.controller.hexagram_rules.update_template(hex_id, template)
        
        dim_names = [self.YAO_DIM_NAMES[d] for d in dims]
        direction_str = '↑' if direction > 0 else '↓'
        diagnosis['correction_detail'] = (
            f"L3 卦{hex_id}({diagnosis['hexagram_name']})模板 {dim_names}: {direction_str}"
        )
    
    def _apply_relation_correction(self, diagnosis, direction, scale):
        """修正爻位关系权重"""
        delta = self.max_correction * scale * direction * 0.3
        
        for i, key in enumerate(['dangwei', 'dezhong', 'cheng_cheng', 'bi', 'ying']):
            if key in self.controller.hexagram_rules.relation_weights:
                mem = self._momentum_memory['relation'][i]
                smoothed = self.momentum * mem + (1 - self.momentum) * delta
                self._momentum_memory['relation'][i] = smoothed
                
                old = self.controller.hexagram_rules.relation_weights[key]
                new = np.clip(old + smoothed, 0.05, 0.60)
                self.controller.hexagram_rules.relation_weights[key] = float(new)
    
    def _apply_relation_weight_adjust(self, adjusts):
        """直接调整爻位关系权重"""
        for key, delta in adjusts.items():
            if key in self.controller.hexagram_rules.relation_weights:
                old = self.controller.hexagram_rules.relation_weights[key]
                new = np.clip(old + delta, 0.05, 0.60)
                self.controller.hexagram_rules.relation_weights[key] = float(new)
    
    def get_adaptation_summary(self):
        """获取自适应修正的汇总报告"""
        if not self.adaptation_log:
            return "无修正记录"
        
        by_severity = {}
        by_layer = {}
        for entry in self.adaptation_log:
            sev = entry['diagnosis']['severity']
            layer = entry['diagnosis']['layer']
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_layer[layer] = by_layer.get(layer, 0) + 1
        
        lines = [
            f"自适应修正汇总: {len(self.adaptation_log)}次修正",
            f"  按严重程度: {by_severity}",
            f"  按修正层: {by_layer}",
            f"",
            f"最近5次修正:",
        ]
        for entry in self.adaptation_log[-5:]:
            d = entry['diagnosis']
            lines.append(f"  [{d['severity']:>8}] {d['reason'][:80]}")
        
        # 当前参数状态
        lines.append(f"\n当前参数状态:")
        lines.append(f"  L2阈值: {np.round(self.controller.yao_encoder.thresholds, 3)}")
        lines.append(f"  爻位关系权重: {self.controller.hexagram_rules.relation_weights}")
        lines.append(f"  推理次数: {self.controller.step_count}")
        
        return '\n'.join(lines)
    
    def export_log(self, path=None):
        """导出完整的自适应日志为JSON"""
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'experiments', 'adaptive_log.json')
        
        data = {
            'total_adaptations': self.total_adaptations,
            'current_thresholds': self.controller.yao_encoder.thresholds.tolist(),
            'current_relation_weights': self.controller.hexagram_rules.relation_weights,
            'adaptation_log': self.adaptation_log,
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path
    
    def reset(self):
        """重置自适应控制器到初始状态"""
        self.controller = YLYWLocomotionController()
        self.trajectory = []
        self.adaptation_log = []
        self._momentum_memory = {
            'L2': np.zeros(6),
            'L3': {hid: np.zeros(6) for hid in range(1, 65)},
            'relation': np.zeros(5),
        }
        self.total_adaptations = 0
        self.last_diagnosis = None


# ============================================================
#  便捷函数
# ============================================================

def simulate_motion_feedback(gait_result, state, delta_t=0.1):
    """
    模拟运动控制反馈信号
    
    在真实系统中，这些信号来自IMU、编码器、力传感器。
    这里基于推理结果和状态的差异来模拟。
    """
    posture = state[0]
    com_h = state[1]
    zmp = state[3]
    disturbance = state[4]
    
    # 摔倒判定：姿态极低 + ZMP极低
    fell = (posture < 0.15 and zmp < 0.12) or (posture < 0.08)
    
    # COM偏差：偏离理想质心高度（0.7-0.85是舒适区）
    ideal_com = 0.75
    com_dev = max(0, abs(com_h - ideal_com) - 0.08)
    
    # ZMP裕度
    zmp_margin = zmp
    
    # 速度偏差：基于该步态的速度 vs 实际状态允许的速度
    # 如果状态很差但步态很快 → 偏差大
    expected_speed_from_state = min(2.0, posture * 1.2 + zmp * 0.8)
    actual_speed = gait_result['speed']
    speed_err = max(0, actual_speed - expected_speed_from_state) / max(0.15, expected_speed_from_state)
    speed_err = min(1.0, speed_err)
    
    # 能耗模型
    energy = actual_speed * 0.4 + gait_result['force_coefficient'] * 0.3 + disturbance * 0.3
    
    return {
        'fell': fell,
        'com_deviation': round(com_dev, 3),
        'zmp_margin': round(zmp_margin, 3),
        'speed_error': round(speed_err, 3),
        'energy_cost': round(min(1.0, energy), 3),
    }


if __name__ == '__main__':
    # 快速自测
    print("=" * 60)
    print("YLYW 自适应控制器 - 快速自测")
    print("=" * 60)
    
    controller = YLYWAdaptiveController(learning_rate=0.05)
    
    # 模拟一组场景：从稳定→逐渐恶化→摔倒→恢复
    test_sequence = [
        # (时间序, 场景名, 状态, 预期行为)
        (0,  "初始稳定", [0.92, 0.85, 0.80, 0.90, 0.05, 0.80]),
        (1,  "正常行走", [0.65, 0.70, 0.65, 0.60, 0.30, 0.75]),
        (2,  "开始不稳", [0.35, 0.45, 0.42, 0.28, 0.55, 0.60]),
        (3,  "非常不稳", [0.18, 0.32, 0.28, 0.14, 0.75, 0.50]),
        (4,  "摔倒!",    [0.08, 0.25, 0.18, 0.08, 0.85, 0.35]),
        (5,  "尝试恢复", [0.42, 0.40, 0.45, 0.32, 0.60, 0.55]),
        (6,  "继续恢复", [0.60, 0.55, 0.55, 0.48, 0.40, 0.60]),
        (7,  "接近正常", [0.78, 0.68, 0.65, 0.62, 0.22, 0.75]),
        (8,  "恢复稳定", [0.88, 0.80, 0.75, 0.85, 0.10, 0.80]),
    ]
    
    prev_feedback = None
    for t, name, state in test_sequence:
        action = controller.step(np.array(state), feedback=prev_feedback)
        
        # 模拟反馈
        prev_feedback = simulate_motion_feedback(action, np.array(state))
        
        hex_name = action['hexagram_name']
        gait = action['gait_name']
        print(f"\nT{t} {name:<8} → {hex_name:<8} {gait:<10} spd={action['speed']:.2f} "
              f"force={action['force_coefficient']:.2f}")
        print(f"  状态: {[f'{v:.2f}' for v in state]}")
        print(f"  六爻: {action['yin_yang']}")
        print(f"  反馈: fell={prev_feedback['fell']} com_dev={prev_feedback['com_deviation']:.2f} "
              f"zmp={prev_feedback['zmp_margin']:.2f}")
        
        if controller.last_diagnosis:
            d = controller.last_diagnosis
            print(f"  ⚡ 修正: [{d['severity']}] {d['reason'][:100]}")
            if 'correction_detail' in d:
                print(f"     → {d['correction_detail']}")
    
    print(f"\n{'='*60}")
    print(controller.get_adaptation_summary())
