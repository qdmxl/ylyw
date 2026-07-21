#!/usr/bin/env python3
"""
YLYW 灵巧手闭环抓取 + 知几学习

核心流程：
  1. 首次抓取：YLYW 推理手腕/手指/力矩
  2. 检测接触：获取各手指在物体局部坐标系的接触点
  3. 知几分析：接触点分布 → 判断"手掌偏了"
     - 如果手指全部触到物体一侧 → 手腕偏转不对
     - 如果接触高度都在物体上部 → 前伸不够
     - 如果接触高度都在物体下部 → 前伸太多/手掌太低
  4. 修正：根据知几分析结果调整（手腕pitch/yaw、前伸reach）
  5. 重试：最多3轮，记录成功配置
"""

import os, sys, math, time, numpy as np
os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
import mujoco

from grasp_env import FINGER_NAMES
from benchmark_screenshot import load_model
from geometric_ylyw import GeometricYLYW

MAX_RETRIES = 3
LIFT_THRESHOLD = 3.0  # mm

# 物体几何参数（用于知几判断）
from geometry_adapter import OBJECT_GEOMETRY


def get_contact_info(m, d, obj_key='sphere'):
    """
    获取物体上各手指接触点的局部位置。
    
    返回: {
        'contacts': {'thumb': (x,y,z), ...},  # 手指接触点在物体局部坐标系的坐标
        'n_fingers': int,
        'z_min': float, 'z_max': float,  # 接触点高度范围（相对物体底部）
    }
    """
    obj_bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')
    obj_xpos = d.xpos[obj_bid]
    obj_xmat = d.xmat[obj_bid].reshape(3, 3)  # 物体旋转矩阵
    
    geo = OBJECT_GEOMETRY.get(obj_key, OBJECT_GEOMETRY['sphere'])
    obj_h = geo['height']
    obj_bottom_z = obj_xpos[2] - obj_h / 2  # 物体底部z
    
    contacts = {f: {} for f in FINGER_NAMES}
    
    for i in range(d.ncon):
        c = d.contact[i]
        g1_name = m.geom(c.geom1).name
        g2_name = m.geom(c.geom2).name
        
        # 检查是否手指触碰到物体
        obj_contact = None
        finger_name = None
        for f in FINGER_NAMES:
            # 检查 geom1 是否包含手指名，geom2 是否包含物体相关标签
            is_finger1 = f in g1_name or f.split('_')[0] in g1_name
            is_finger2 = f in g2_name or f.split('_')[0] in g2_name
            is_obj_geom1 = 'obj' in g1_name or 'head' in g1_name or 'stem' in g1_name or 'left' in g1_name or 'right' in g1_name or 'bar' in g1_name
            is_obj_geom2 = 'obj' in g2_name or 'head' in g2_name or 'stem' in g2_name or 'left' in g2_name or 'right' in g2_name or 'bar' in g2_name
            
            if is_finger1 and is_obj_geom2:
                finger_name = f
                break
            elif is_finger2 and is_obj_geom1:
                finger_name = f
                break
        
        if finger_name:
            # 接触点全局坐标
            contact_pos = c.pos  # (3,) 全局坐标
            # 转到物体局部坐标
            local_pos = obj_xmat.T @ (contact_pos - obj_xpos)
            contacts[finger_name] = {
                'global': contact_pos.copy(),
                'local': local_pos,
                'height_ratio': (contact_pos[2] - obj_bottom_z) / max(obj_h, 0.001),
            }
    
    # 统计
    actives = {f: v for f, v in contacts.items() if v}
    n_fingers = len(actives)
    z_ratios = [v['height_ratio'] for v in actives.values()]
    
    return {
        'contacts': actives,
        'n_fingers': n_fingers,
        'z_min_ratio': min(z_ratios) if z_ratios else 0.5,
        'z_max_ratio': max(z_ratios) if z_ratios else 0.5,
        'z_avg_ratio': np.mean(z_ratios) if z_ratios else 0.5,
    }


def run_grasp(m, d, wrist_pitch, wrist_yaw, hand_reach,
              finger_angles, torque_mod=None, force_scale=1.0,
              vision_guided=False, obj_key='sphere'):
    """
    执行一次抓取。
    
    vision_guided=True时：在手指闭合前，先用视觉算出前伸和俯仰的精确值。
    """
    act_map = {'thumb': (4,5), 'index': (6,7), 'middle': (8,9), 'ring': (10,11), 'pinky': (12,13)}
    max_t = {'thumb': 2.5, 'index': 2.0, 'middle': 2.0, 'ring': 1.8, 'pinky': 1.5}
    if torque_mod is None:
        torque_mod = {f: 1.0 for f in FINGER_NAMES}

    def _apply_torque(tighten=1.0):
        for f, (a1, a2) in act_map.items():
            if f in finger_angles:
                j1, j2 = finger_angles[f]
                mt = max_t.get(f, 0.5)
                mod = torque_mod.get(f, 1.0)
                d.ctrl[a1] = j1 * mt / 1.2 * tighten * force_scale * mod
                d.ctrl[a2] = j2 * mt / 1.2 * tighten * force_scale * mod

    # ─── 视觉引导：在手指闭合前，根据物体实际位置精确调整手腕 ───
    if vision_guided:
        obj_bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')
        palm_bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'palm')
        obj_pos = d.xpos[obj_bid].copy()
        palm_pos = d.xpos[palm_bid].copy()
        
        # 先跑几步让手腕姿态到位，再视觉校正
        d.ctrl[1] = wrist_pitch; d.ctrl[2] = wrist_yaw; d.ctrl[3] = hand_reach
        d.ctrl[0] = -0.10
        for _ in range(80): mujoco.mj_step(m, d)
        
        # 重新获取位置（手腕到位后的手掌位置）
        palm_pos = d.xpos[palm_bid].copy()
        
        # 计算指尖到物体的向量
        # 取食指指尖作为代表（第一根手指指尖离物体最近）
        for finger_tip_name in ['index_tip', 'middle_tip', 'thumb_tip', 'ring_tip', 'pinky_tip']:
            tip_bid = None
            for b in range(m.nbody):
                if m.body(b).name == finger_tip_name:
                    tip_bid = b; break
            if tip_bid is not None:
                break
        
        if tip_bid is not None:
            tip_pos = d.xpos[tip_bid]
            # 从指尖到物体的3D向量
            tip_to_obj = obj_pos - tip_pos
            # 在手掌局部坐标系中看这个向量
            # palm_xmat = d.xmat[palm_bid].reshape(3,3)
            # 简化：直接看指尖在物体上方/下方/侧面
            vert_gap = tip_pos[2] - obj_pos[2]  # >0=指尖在物体上方
            horiz_dist = np.linalg.norm(tip_pos[:2] - obj_pos[:2])  # 水平距离
            
            # 如果指尖在物体上方很多，且水平距离小 → 需要前伸让手指垂到物体侧面
            if vert_gap > 0.03 and horiz_dist < 0.03:
                # 手指在物体正上方，垂直下去会被桌面挡住
                # 加大前伸让手指伸到物体侧面去
                extra_reach = vert_gap * 0.6
                hand_reach = max(hand_reach, extra_reach)
            
            # 如果水平距离大 → 调整俯仰让手指朝向物体
            if horiz_dist > 0.05:
                extra_pitch = horiz_dist * 2.0
                wrist_pitch = max(wrist_pitch, extra_pitch)
    
    # 1. 手腕姿态 + 前伸 + 降臂
    d.ctrl[1] = wrist_pitch; d.ctrl[2] = wrist_yaw; d.ctrl[3] = hand_reach
    d.ctrl[0] = -0.20  # 降臂
    for i in range(4, len(d.ctrl)): d.ctrl[i] = 0.0
    for _ in range(200): mujoco.mj_step(m, d)

    init_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]

    # 闭合
    _apply_torque(tighten=1.0)
    for _ in range(150): mujoco.mj_step(m, d)

    # 抬臂
    d.ctrl[0] = 0.12
    for _ in range(300):
        _apply_torque(tighten=1.3)
        mujoco.mj_step(m, d)

    final_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]
    lift_mm = (final_obj_z - init_obj_z) * 1000
    success = lift_mm > LIFT_THRESHOLD

    # 接触检测
    contacts = {f: False for f in FINGER_NAMES}
    for i in range(d.ncon):
        g1 = m.geom(d.contact[i].geom1).name
        g2 = m.geom(d.contact[i].geom2).name
        for f in FINGER_NAMES:
            if f in g1 or f in g2: contacts[f] = True
    n_fingers = sum(1 for v in contacts.values() if v)

    return {'success': success, 'lift_mm': lift_mm, 'n_fingers': n_fingers}


def zhiji_analysis(contact_info, current_wrist, obj_key='sphere', attempt=0):
    """
    知几分析：根据尝试次数系统性地搜索手腕参数空间。
    
    attempt=0: YLYW首次推理
    attempt=1: 尝试前伸+0.04
    attempt=2: 尝试俯仰-0.15（更大范围搜索）
    """
    pitch, yaw, reach = current_wrist
    feedback = []
    
    if attempt == 0:
        # 第一次失败：加大前伸
        reach += 0.04
        feedback.append(f"首次失败→前伸+0.04")
    elif attempt == 1:
        # 第二次失败：大幅调整俯仰
        if pitch > 0:
            pitch -= 0.15
            feedback.append(f"前伸失败→俯仰-0.15")
        else:
            pitch += 0.20
            feedback.append(f"前伸失败→俯仰+0.20")
    
    pitch = max(-0.5, min(pitch, 0.6))
    yaw = max(-0.4, min(yaw, 0.4))
    reach = max(0.0, min(reach, 0.12))
    return feedback, (pitch, yaw, reach)


def save_learning(obj_key, wrist_params, success):
    """
    知几学习：记录最佳手腕参数
    """
    import json
    record_path = os.path.join(os.path.dirname(__file__), 'zhiji_learning.json')
    records = {}
    if os.path.exists(record_path):
        try:
            with open(record_path) as f:
                records = json.load(f)
        except: pass
    
    key = obj_key
    if key not in records or (success and not records[key].get('success', False)):
        records[key] = {
            'pitch': wrist_params[0],
            'yaw': wrist_params[1],
            'reach': wrist_params[2],
            'success': success,
        }
        with open(record_path, 'w') as f:
            json.dump(records, f, indent=2)


if __name__ == '__main__':
    print("=" * 70)
    print("YLYW 灵巧手 — 闭环抓取 + 知几学习")
    print("=" * 70)

    objects = ['sphere', 'box', 'cylinder', 'long_rod', 'mushroom', 'dumbbell', 'disc']
    gylyw = GeometricYLYW()
    
    for obj_key in objects:
        print(f"\n{'─'*70}")
        print(f"物体: {obj_key}")
        
        # YLYW 首次推理
        angles = gylyw.infer_finger_angles(obj_key)
        pitch, yaw, reach = gylyw._wrist
        torque_mod = gylyw._torque_mod
        
        print(f"  YLYW首次: pitch={pitch:+.2f} yaw={yaw:+.2f} reach={reach:.3f}")
        
        # 知几闭环
        best_lift = -999
        best_wrist = (pitch, yaw, reach)
        
        for attempt in range(MAX_RETRIES):
            print(f"\n  尝试 {attempt+1}/{MAX_RETRIES}:")
            
            m = load_model(obj_key)
            d = mujoco.MjData(m)
            
            r = run_grasp(m, d, pitch, yaw, reach, angles,
                         torque_mod=torque_mod, force_scale=1.0,
                         vision_guided=True, obj_key=obj_key)
            
            lift = r['lift_mm']
            sym = '✅' if r['success'] else '❌'
            print(f"    lift={lift:+.1f}mm  contact={r['n_fingers']}/5  {sym}")
            
            if lift > best_lift:
                best_lift = lift
                best_wrist = (pitch, yaw, reach)
            
            if r['success']:
                print(f"  ✅ 成功！最终手腕: pitch={pitch:+.2f} yaw={yaw:+.2f} reach={reach:.3f}")
                save_learning(obj_key, best_wrist, True)
                break
            
            # 知几分析
            if attempt < MAX_RETRIES - 1:
                contact_info = get_contact_info(m, d, obj_key)
                feedback, (pitch, yaw, reach) = zhiji_analysis(
                    contact_info, (pitch, yaw, reach), obj_key, attempt=attempt)
                
                for fb in feedback:
                    print(f"    知几: {fb}")
        else:
            print(f"  ❌ {MAX_RETRIES}次均失败")
            save_learning(obj_key, best_wrist, False)
    
    # 汇总
    import json
    record_path = os.path.join(os.path.dirname(__file__), 'zhiji_learning.json')
    if os.path.exists(record_path):
        with open(record_path) as f:
            records = json.load(f)
        print(f"\n{'='*70}")
        print("知几学习记录:")
        for obj, data in records.items():
            status = '✅' if data.get('success') else '❌'
            print(f"  {obj:12s} {status} pitch={data['pitch']:+.2f} yaw={data['yaw']:+.2f} reach={data['reach']:.3f}")
    
    print(f"\n{'='*70}")
    print("完成")
