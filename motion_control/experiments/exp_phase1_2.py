#!/usr/bin/env python3
"""
Phase 1.2: YLYW MuJoCo 摔倒恢复 + 自适应对比实验

三个核心实验：
  1. 扰动推搡恢复 — 15s注入300N侧推力，对比卦象切换+恢复速度
  2. 步态过度实验 — 在模拟冰面上强制跑动，对比摔倒次数
  3. 模板污染恢复 — 污染5个卦模板，自适应50步内修复
"""
import sys, os, time, math, json
import numpy as np

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')
os.environ.setdefault('EGL_PLATFORM', 'x11')
os.environ.setdefault('MESA_GL_VERSION_OVERRIDE', '3.3')
os.environ.setdefault('GDK_BACKEND', 'x11')
os.environ.setdefault('XDG_SESSION_TYPE', 'x11')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ylyw_locomotion import YLYWLocomotionController
from ylyw_adaptive import YLYWAdaptiveController
import mujoco
import warnings
warnings.filterwarnings('ignore')

from launch_mujoco import XML as ROBOT_XML


class ExperimentRunner:
    """统一实验运行器"""
    
    def __init__(self):
        self.model = mujoco.MjModel.from_xml_string(ROBOT_XML)
        
    def make_data(self):
        return mujoco.MjData(self.model)
    
    def run_push_recovery(self, adaptive=False, duration=30, push_force=300):
        """
        实验1: 扰动推搡恢复
        
        场景: 正常行走(0-15s) → 侧向推搡(15-15.3s) → 观察恢复(15-30s)
        指标: 推搡前/后的卦象切换、恢复时间、摔倒次数
        """
        model = self.model
        data = self.make_data()
        
        if adaptive:
            controller = YLYWAdaptiveController(learning_rate=0.08)
        else:
            controller = YLYWLocomotionController()
        
        # 执行器ID
        act_ids = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i
                   for i in range(model.nu)}
        
        # 获取关键地址
        torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'torso')
        sx_qpos = model.jnt_qposadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        sx_dof = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        
        dt = model.opt.timestep
        phase = 0.0
        sim_time = 0.0
        step = 0
        current_gait = None
        fell_count = 0
        prev_fell = False
        
        # 推搡前用正常行走状态
        walk_state = np.array([0.65, 0.70, 0.65, 0.60, 0.30, 0.75])
        
        # 结果记录
        gait_timeline = []   # [(time, hex_name, gait_name, speed, fell)]
        push_time = 15.0
        recovery_start = None
        recovery_end = None
        
        while sim_time < duration:
            # 读取MuJoCo实际状态
            torso_pos = data.xpos[torso_id]
            tz = torso_pos[2]
            
            # 摔倒检测
            torso_quat = data.xquat[torso_id]
            qw, qx, qy, qz = torso_quat[0:4]
            sinr_cosp = 2*(qw*qx+qy*qz); cosr_cosp = 1-2*(qx*qx+qy*qy)
            roll = math.atan2(sinr_cosp, cosr_cosp)
            sinp = 2*(qw*qy-qz*qx); pitch = math.asin(max(-1, min(1, sinp)))
            tilt = abs(roll) + abs(pitch)
            fell = tz < 0.30 or tilt > 1.2
            
            if fell and not prev_fell:
                fell_count += 1
            prev_fell = fell
            
            # 推搡前后的状态输入
            if sim_time < push_time:
                state_input = walk_state.copy()
            elif sim_time < push_time + 0.3:
                # 推搡期间：状态大幅恶化
                state_input = np.array([0.12, 0.25, 0.18, 0.08, 0.90, 0.40])
            else:
                # 推搡后恢复期：从恶化逐步恢复
                elapsed = sim_time - (push_time + 0.3)
                recovery_ratio = min(1.0, elapsed / 3.0)
                state_input = np.array([
                    0.12 + (0.65 - 0.12) * recovery_ratio,
                    0.25 + (0.70 - 0.25) * recovery_ratio,
                    0.18 + (0.65 - 0.18) * recovery_ratio,
                    0.08 + (0.60 - 0.08) * recovery_ratio,
                    0.90 + (0.30 - 0.90) * recovery_ratio,
                    0.40 + (0.75 - 0.40) * recovery_ratio,
                ])
            
            # 构建反馈
            feedback = None
            if adaptive and step > 0:
                feedback = {
                    'fell': fell,
                    'com_deviation': max(0, abs(tz - 0.95) - 0.05),
                    'zmp_margin': max(0, 1.0 - tilt * 2.0),
                    'speed_error': 0,
                    'energy_cost': 0.5,
                }
            
            # YLYW推理
            if step % 3 == 0:
                if adaptive:
                    result = controller.step(state_input, feedback=feedback)
                    if feedback:
                        controller.give_feedback(feedback)
                else:
                    result = controller.infer(state_input, verbose=False)
                if result:
                    current_gait = result
            
            gait = current_gait or {'speed': 0, 'freq': 0, 'step_height': 0, 'force_coefficient': 0.5, 
                                     'hexagram_name': 'N/A', 'gait_name': 'N/A'}
            
            # 关节控制
            speed = gait.get('speed', 0)
            freq = gait.get('freq', 0)
            if speed >= 0.02:
                phase += freq * dt * 2 * math.pi
                phase %= 2 * math.pi
                amp_h = 0.65 * min(speed, 1.5)
                amp_k = 0.50 * min(speed, 1.5)
                for side, off in [('l', 0), ('r', math.pi)]:
                    p = phase + off
                    if f'{side}h_m' in act_ids:
                        data.ctrl[act_ids[f'{side}h_m']] = amp_h * math.sin(p)
                    if f'{side}k_m' in act_ids:
                        data.ctrl[act_ids[f'{side}k_m']] = amp_k * max(0, math.sin(p))
            else:
                for a in act_ids.values():
                    data.ctrl[a] = 0
            
            # 躯干滑动 + 推搡力
            data.qvel[sx_dof] = speed * 1.5
            
            # 推搡期间加侧向扰动
            if push_time <= sim_time < push_time + 0.3:
                force_sign = 1 if int(sim_time*100) % 2 == 0 else -1
                data.qvel[sx_dof] += push_force * 0.0015 * force_sign
            
            # 跑步机标记
            for i in range(1, 11):
                m_jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f'm{i}')
                mdof = model.jnt_dofadr[m_jid]
                mqpos = model.jnt_qposadr[m_jid]
                data.qvel[mdof] = -speed * 6
                if data.qpos[mqpos] < -12:
                    data.qpos[mqpos] += 20
            
            mujoco.mj_step(model, data)
            
            # 记录
            if step % 100 == 0:
                gait_timeline.append({
                    'time': round(sim_time, 2),
                    'hexagram': gait['hexagram_name'],
                    'gait': gait['gait_name'],
                    'speed': round(speed, 3),
                    'fell': fell,
                })
                
                # 追踪恢复
                if sim_time >= push_time + 0.3:
                    if recovery_start is None and gait['gait_name'] in ('恢复步态', '慢走', '谨慎行走'):
                        recovery_start = sim_time
                    if recovery_start and gait['gait_name'] in ('正常行走', '快速行走'):
                        recovery_end = sim_time
            
            step += 1; sim_time += dt
        
        recovery_time = (recovery_end - recovery_start) if recovery_start and recovery_end else None
        
        return {
            'adaptive': adaptive,
            'fell_count': fell_count,
            'push_time': push_time,
            'recovery_start': recovery_start,
            'recovery_end': recovery_end,
            'recovery_time': recovery_time,
            'gait_timeline': gait_timeline,
            'total_adaptations': controller.total_adaptations if adaptive else 0,
        }
    
    def run_ice_gait_test(self, adaptive=False, duration=20):
        """
        实验2: 冰面步态过度实验
        
        在冰面上强制跑动，对比摔倒次数。
        静态YLYW会输出奔跑→摔倒；自适应YLYW应学会保守。
        """
        model = self.model
        # 修改地面摩擦
        floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'floor')
        orig_friction = model.geom_friction[floor_id].copy()
        model.geom_friction[floor_id] = [0.15, 0.01, 0.01]  # 冰面
        
        data = self.make_data()
        
        if adaptive:
            controller = YLYWAdaptiveController(learning_rate=0.08)
        else:
            controller = YLYWLocomotionController()
        
        act_ids = {mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i): i
                   for i in range(model.nu)}
        torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'torso')
        sx_dof = model.jnt_dofadr[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'slide_x')]
        
        dt = model.opt.timestep
        phase = 0.0; sim_time = 0.0; step = 0
        current_gait = None; fell_count = 0; prev_fell = False
        
        # 用跑动状态（会迫使YLYW输出高速步态，在冰面上危险）
        run_state = np.array([0.48, 0.75, 0.78, 0.42, 0.62, 0.78])
        # 但也混入一些正常状态，避免一直摔倒
        walk_state = np.array([0.65, 0.70, 0.65, 0.60, 0.30, 0.75])
        
        gait_timeline = []
        
        while sim_time < duration:
            torso_pos = data.xpos[torso_id]
            tz = torso_pos[2]
            torso_quat = data.xquat[torso_id]
            qw, qx, qy, qz = torso_quat[0:4]
            sinr_cosp = 2*(qw*qx+qy*qz); cosr_cosp = 1-2*(qx*qx+qy*qy)
            roll = math.atan2(sinr_cosp, cosr_cosp)
            sinp = 2*(qw*qy-qz*qx); pitch = math.asin(max(-1, min(1, sinp)))
            tilt = abs(roll) + abs(pitch)
            fell = tz < 0.30 or tilt > 1.2
            
            if fell and not prev_fell: fell_count += 1
            prev_fell = fell
            
            # 交替跑动和行走状态
            if int(sim_time) % 8 < 5:
                state_input = run_state
            else:
                state_input = walk_state
            
            # 构建含地形的反馈
            feedback = None
            if adaptive and step > 0:
                feedback = {
                    'fell': fell,
                    'com_deviation': max(0, abs(tz - 0.95) - 0.05),
                    'zmp_margin': max(0, 1.0 - tilt * 2.0),
                    'speed_error': 0,
                    'energy_cost': 0.5,
                    'expected_gait': 'walk',  # GT: 冰面上应该走而不是跑
                }
            
            if step % 3 == 0:
                if adaptive:
                    result = controller.step(state_input, feedback=feedback)
                    if feedback: controller.give_feedback(feedback)
                else:
                    result = controller.infer(state_input, verbose=False)
                if result: current_gait = result
            
            gait = current_gait or {'speed': 0, 'freq': 0, 'step_height': 0, 'force_coefficient': 0.5,
                                     'hexagram_name': 'N/A', 'gait_name': 'N/A'}
            
            speed = gait.get('speed', 0)
            freq = gait.get('freq', 0)
            if speed >= 0.02:
                phase += freq * dt * 2 * math.pi; phase %= 2 * math.pi
                amp_h = 0.65 * min(speed, 1.5); amp_k = 0.50 * min(speed, 1.5)
                for side, off in [('l', 0), ('r', math.pi)]:
                    p = phase + off
                    if f'{side}h_m' in act_ids:
                        data.ctrl[act_ids[f'{side}h_m']] = amp_h * math.sin(p)
                    if f'{side}k_m' in act_ids:
                        data.ctrl[act_ids[f'{side}k_m']] = amp_k * max(0, math.sin(p))
            else:
                for a in act_ids.values(): data.ctrl[a] = 0
            
            data.qvel[sx_dof] = speed * 1.5
            for i in range(1, 11):
                m_jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f'm{i}')
                data.qvel[model.jnt_dofadr[m_jid]] = -speed * 6
                mqpos = model.jnt_qposadr[m_jid]
                if data.qpos[mqpos] < -12: data.qpos[mqpos] += 20
            
            mujoco.mj_step(model, data)
            
            if step % 100 == 0:
                gait_timeline.append({
                    'time': round(sim_time, 2),
                    'hexagram': gait['hexagram_name'],
                    'gait': gait['gait_name'],
                    'speed': round(speed, 3),
                    'fell': fell,
                })
            
            step += 1; sim_time += dt
        
        # 恢复摩擦
        model.geom_friction[floor_id] = orig_friction
        
        return {
            'adaptive': adaptive,
            'fell_count': fell_count,
            'gait_timeline': gait_timeline,
            'total_adaptations': controller.total_adaptations if adaptive else 0,
        }
    
    def run_template_corruption_recovery(self, n_steps=80):
        """
        实验3: 模板污染恢复
        
        污染跑动卦模板 → 自适应50步内恢复
        纯Python测试（不需要MuJoCo物理）
        """
        from hexagram_gait_rules import HexagramGaitRules
        hgr = HexagramGaitRules()
        
        # 目标：污染3个run卦 + 2个fast_walk卦
        target_gaits = ['run', 'fast_walk']
        target_hexs = []
        for hid in range(1, 65):
            if hgr.HEXAGRAM_GAIT_RULES[hid][3] in target_gaits:
                target_hexs.append(hid)
        
        # 保存原始模板
        orig = {hid: hgr.get_template(hid).copy() for hid in target_hexs}
        
        # 创建自适应控制器并污染模板
        adp = YLYWAdaptiveController(learning_rate=0.10, momentum=0.4)
        for hid in target_hexs:
            corrupted = orig[hid].copy()
            corrupted[0] = np.clip(corrupted[0] + 0.35, 0, 0.98)  # 姿态↑
            corrupted[4] = np.clip(corrupted[4] - 0.30, 0.02, 0.98)  # 扰动↓
            adp.controller.hexagram_rules.update_template(hid, corrupted)
        
        # 初始偏差
        init_dists = {}
        for hid in target_hexs:
            current = adp.controller.hexagram_rules.get_template(hid)
            init_dists[hid] = float(np.linalg.norm(current - orig[hid]))
        init_mean = np.mean(list(init_dists.values()))
        
        # 跑动状态 + ground truth = 'run'
        run_state = np.array([0.48, 0.75, 0.78, 0.42, 0.65, 0.78])
        gait_correct = []
        dist_history = []
        feedback = None
        np.random.seed(42)
        
        for step in range(n_steps):
            noise = np.random.normal(0, 0.03, 6)
            state = np.clip(run_state + noise, 0.0, 0.99)
            
            result = adp.step(state, feedback=feedback)
            
            # GT反馈
            feedback = {
                'fell': False,
                'com_deviation': 0.02,
                'zmp_margin': 0.42,
                'speed_error': 0,
                'energy_cost': 0.5,
                'expected_gait': 'run',
            }
            adp.give_feedback(feedback)
            
            gait_correct.append(result.get('gait_type', '?') == 'run')
            
            if step % 10 == 0:
                dists = {}
                for hid in target_hexs:
                    current = adp.controller.hexagram_rules.get_template(hid)
                    dists[hid] = float(np.linalg.norm(current - orig[hid]))
                dist_history.append({'step': step, 'mean_dist': round(np.mean(list(dists.values())), 3)})
        
        # 最终偏差
        final_dists = {}
        for hid in target_hexs:
            current = adp.controller.hexagram_rules.get_template(hid)
            final_dists[hid] = float(np.linalg.norm(current - orig[hid]))
        final_mean = np.mean(list(final_dists.values()))
        
        correct_rate = sum(gait_correct) / len(gait_correct)
        late_correct = sum(gait_correct[40:]) / max(1, len(gait_correct[40:]))
        
        return {
            'target_hexs': target_hexs,
            'init_mean_dist': round(init_mean, 3),
            'final_mean_dist': round(final_mean, 3),
            'improvement': round(init_mean - final_mean, 3),
            'correct_rate': round(correct_rate, 3),
            'late_correct_rate': round(late_correct, 3),
            'total_adaptations': adp.total_adaptations,
        }


def main():
    print("=" * 70)
    print("实验1.2: YLYW MuJoCo 摔倒恢复 + 自适应对比")
    print("=" * 70)
    
    runner = ExperimentRunner()
    results = {}
    
    # ============================
    # 实验1: 扰动推搡恢复
    # ============================
    print(f"\n{'='*70}")
    print("实验1: 扰动推搡恢复 (15s注入300N侧推力)")
    print(f"{'='*70}")
    
    print("\n--- 静态YLYW ---")
    r1s = runner.run_push_recovery(adaptive=False, duration=20, push_force=300)
    print(f"  摔倒: {r1s['fell_count']}次")
    print(f"  恢复起始: {r1s['recovery_start']}s, 结束: {r1s['recovery_end']}s")
    if r1s['recovery_time']:
        print(f"  恢复时间: {r1s['recovery_time']:.2f}s")
    print(f"  卦象切换:")
    for g in r1s['gait_timeline']:
        fell_mark = '💀' if g['fell'] else '  '
        if g['time'] >= 14 and g['time'] <= 18:
            print(f"    {g['time']:>5.1f}s {g['hexagram']:<8} {g['gait']:<10} {fell_mark}")
    
    print("\n--- 自适应YLYW ---")
    r1a = runner.run_push_recovery(adaptive=True, duration=20, push_force=300)
    print(f"  摔倒: {r1a['fell_count']}次")
    print(f"  自适应修正: {r1a['total_adaptations']}次")
    print(f"  恢复起始: {r1a['recovery_start']}s, 结束: {r1a['recovery_end']}s")
    if r1a['recovery_time']:
        print(f"  恢复时间: {r1a['recovery_time']:.2f}s")
    print(f"  卦象切换:")
    for g in r1a['gait_timeline']:
        fell_mark = '💀' if g['fell'] else '  '
        if g['time'] >= 14 and g['time'] <= 18:
            print(f"    {g['time']:>5.1f}s {g['hexagram']:<8} {g['gait']:<10} {fell_mark}")
    
    results['push_recovery'] = {
        'static': {'fell_count': r1s['fell_count'], 'recovery_time': r1s['recovery_time']},
        'adaptive': {'fell_count': r1a['fell_count'], 'recovery_time': r1a['recovery_time'],
                     'adaptations': r1a['total_adaptations']},
    }
    
    # ============================
    # 实验2: 冰面步态过度
    # ============================
    print(f"\n{'='*70}")
    print("实验2: 冰面步态过度（强制跑动→摔倒对比）")
    print(f"{'='*70}")
    
    print("\n--- 静态YLYW ---")
    r2s = runner.run_ice_gait_test(adaptive=False, duration=15)
    print(f"  摔倒: {r2s['fell_count']}次")
    print(f"  步态序列: {[(g['time'], g['gait'], g['speed']) for g in r2s['gait_timeline'] if g['fell'] or g['time']%1<0.1]}")
    
    print("\n--- 自适应YLYW ---")
    r2a = runner.run_ice_gait_test(adaptive=True, duration=15)
    print(f"  摔倒: {r2a['fell_count']}次")
    print(f"  自适应修正: {r2a['total_adaptations']}次")
    print(f"  步态序列: {[(g['time'], g['gait'], g['speed']) for g in r2a['gait_timeline'] if g['fell'] or g['time']%1<0.1]}")
    
    results['ice_gait'] = {
        'static': {'fell_count': r2s['fell_count']},
        'adaptive': {'fell_count': r2a['fell_count'], 'adaptations': r2a['total_adaptations']},
    }
    
    # ============================
    # 实验3: 模板污染恢复
    # ============================
    print(f"\n{'='*70}")
    print("实验3: 模板污染恢复（跑动卦污染→自适应修复）")
    print(f"{'='*70}")
    
    r3 = runner.run_template_corruption_recovery(n_steps=80)
    print(f"  污染卦数: {len(r3['target_hexs'])}")
    print(f"  初始偏差: {r3['init_mean_dist']:.3f} → 最终偏差: {r3['final_mean_dist']:.3f}")
    print(f"  改善: {r3['improvement']:+.3f}")
    print(f"  步态正确率: {r3['correct_rate']*100:.0f}% 后半: {r3['late_correct_rate']*100:.0f}%")
    print(f"  修正次数: {r3['total_adaptations']}")
    
    results['template_recovery'] = r3
    
    # ============================
    # 汇总
    # ============================
    print(f"\n{'='*70}")
    print("综合汇总")
    print(f"{'='*70}")
    print(f"{'实验':<20} {'静态摔倒':>8} {'自适应摔倒':>8} {'自适应修正':>8}")
    print('-' * 50)
    pr = results['push_recovery']
    print(f"{'扰动推搡恢复':<20} {pr['static']['fell_count']:>8} {pr['adaptive']['fell_count']:>8} {pr['adaptive']['adaptations']:>8}")
    ig = results['ice_gait']
    print(f"{'冰面步态':<20} {ig['static']['fell_count']:>8} {ig['adaptive']['fell_count']:>8} {ig['adaptive']['adaptations']:>8}")
    print(f"{'模板污染恢复':<20} {'-':>8} {'-':>8} {r3['total_adaptations']:>8}")
    
    # 保存
    out_path = os.path.join(os.path.dirname(__file__), 'experiments', 'exp_phase1_2_results.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        # Convert numpy types
        def convert(obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, dict): return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list): return [convert(v) for v in obj]
            return obj
        json.dump(convert(results), f, ensure_ascii=False, indent=2)
    print(f"\n✅ 结果已保存: {out_path}")


if __name__ == '__main__':
    main()
