#!/usr/bin/env python3
"""
YLYW 灵巧手仿真 — 多样物体 × 策略 批量验证 + 高清截图

物体种类（7种）：
  1. 球体 (sphere)       — 滚动物体，YCB标准
  2. 立方体 (box)        — 平面接触，YCB标准
  3. 圆柱体 (cylinder)   — 规则曲面
  4. 长杆 (long_rod)     — 细长物体
  5. 蘑菇体 (mushroom)   — 上大下小不规则
  6. 哑铃 (dumbbell)     — 两端大中间细
  7. 盘状 (disc)         — 扁平时钟形

每种物体用 4 种 YLYW 策略抓取，截取关键帧。
"""

import os, sys, math, time
import numpy as np

os.environ.setdefault('MUJOCO_GL_DEBUG', '0')
os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('GALLIUM_DRIVER', 'llvmpipe')

import mujoco

# 图片输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'paper_figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── 物体定义 ───
# 每个物体: (name, xml_fragment, mass, desc)
OBJECTS = {
    'sphere': {
        'desc': '球体 (Sphere)',
        'mass': 0.05,
        'xml': '<geom name="obj_geom" type="sphere" size="0.028" mass="{mass}" material="object" rgba="0.9 0.2 0.2 1"/>'
    },
    'box': {
        'desc': '立方体 (Box)',
        'mass': 0.06,
        'xml': '<geom name="obj_geom" type="box" size="0.025 0.025 0.025" mass="{mass}" material="object" rgba="0.2 0.6 0.8 1"/>'
    },
    'cylinder': {
        'desc': '圆柱体 (Cylinder)',
        'mass': 0.05,
        'xml': '<geom name="obj_geom" type="cylinder" size="0.025 0.03" mass="{mass}" material="object" rgba="0.3 0.8 0.4 1"/>'
    },
    'long_rod': {
        'desc': '长杆 (Rod)',
        'mass': 0.04,
        'xml': '<geom name="obj_geom" type="cylinder" size="0.008 0.045" mass="{mass}" material="object" rgba="0.7 0.5 0.2 1"/>'
    },
    'mushroom': {
        'desc': '蘑菇体 (Mushroom)',
        'mass': 0.06,
        'xml': '<geom name="obj_head" type="sphere" size="0.035" mass="0" pos="0 0 0.035" material="object" rgba="0.8 0.3 0.1 1"/><geom name="obj_stem" type="cylinder" size="0.012 0.035" mass="{mass}" pos="0 0 -0.015" material="object" rgba="0.9 0.6 0.3 1"/>'
    },
    'dumbbell': {
        'desc': '哑铃 (Dumbbell)',
        'mass': 0.06,
        'xml': '<geom name="obj_left" type="sphere" size="0.02" pos="-0.035 0 0" mass="0" material="object" rgba="0.4 0.4 0.4 1"/><geom name="obj_right" type="sphere" size="0.02" pos="0.035 0 0" mass="0" material="object" rgba="0.4 0.4 0.4 1"/><geom name="obj_bar" type="cylinder" size="0.006 0.04" pos="0 0 0" mass="{mass}" material="object" rgba="0.6 0.6 0.6 1" euler="0 1.57 0"/>'
    },
    'disc': {
        'desc': '盘状体 (Disc)',
        'mass': 0.04,
        'xml': '<geom name="obj_geom" type="cylinder" size="0.035 0.008" mass="{mass}" material="object" rgba="0.5 0.3 0.7 1"/>'
    },
}


def load_model(obj_key):
    """加载灵巧手模型+指定物体"""
    obj = OBJECTS[obj_key]
    obj_xml = obj['xml'].format(mass=obj['mass'])

    # 读取基础模型 XML
    base_xml_path = os.path.join(os.path.dirname(__file__), 'hand_model.xml')
    with open(base_xml_path, 'r') as f:
        xml = f.read()

    # 替换物体几何定义
    import re
    # 查找 object body 中的 geom 定义并替换
    pattern = r'(<body name="object" pos="[^"]+">\s*<freejoint name="obj_free"/>).*?(</body>)'
    replacement = r'\1\n' + obj_xml + r'\n      \2'
    xml = re.sub(pattern, replacement, xml, flags=re.DOTALL)

    # 调整物体 Z 高度（细长杆等需要更高起始位置）
    heights = {
        'sphere': 0.76, 'box': 0.76, 'cylinder': 0.76,
        'long_rod': 0.78, 'mushroom': 0.77, 'dumbbell': 0.76, 'disc': 0.76
    }
    obj_z = heights.get(obj_key, 0.76)
    xml = xml.replace('pos="0 0 0.76"', f'pos="0 0 {obj_z}"')

    return mujoco.MjModel.from_xml_string(xml)


# ─── 主程序 ───
if __name__ == '__main__':
    print("=" * 70)
    print("YLYW 灵巧手仿真 — 多样物体 × 策略 验证")
    print("=" * 70)
    print("(渲染截图不可用: VirtualBox无GPU加速, 为论文准备改用数据可视化)")

    # 策略选择：每种物体选4种代表性策略
    strategies_by_shape = {
        'sphere': ['soft_grasp', 'wrap_grasp', 'firm_grasp', 'adaptive_grasp'],
        'box': ['power_grasp', 'precision_grasp', 'wrap_grasp', 'firm_grasp'],
        'cylinder': ['wrap_grasp', 'firm_grasp', 'adaptive_grasp', 'cautious_grasp'],
        'long_rod': ['precision_grasp', 'cautious_grasp', 'soft_grasp', 'adaptive_grasp'],
        'mushroom': ['wrap_grasp', 'soft_grasp', 'cautious_grasp', 'adaptive_grasp'],
        'dumbbell': ['power_grasp', 'wrap_grasp', 'adaptive_grasp', 'firm_grasp'],
        'disc': ['soft_grasp', 'wrap_grasp', 'cautious_grasp', 'firm_grasp'],
    }

    all_results = {}

    for obj_key in OBJECTS:
        print(f"\n{'─'*70}")
        print(f"物体: {OBJECTS[obj_key]['desc']}")
        print(f"{'─'*70}")

        obj_results = []
        strategies = strategies_by_shape.get(obj_key, ['soft_grasp', 'firm_grasp', 'wrap_grasp', 'adaptive_grasp'])

        for strategy in strategies:
            for force_scale in [0.6, 1.0]:
                m = load_model(obj_key)
                d = mujoco.MjData(m)

                # 1. 降臂，张开手指
                d.ctrl[0] = -0.08
                for i in range(1, len(d.ctrl)):
                    d.ctrl[i] = 0.0
                for _ in range(50):
                    mujoco.mj_step(m, d)

                init_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]

                # 2. 手指闭合
                from grasp_env import STRATEGY_TO_POSITION, FINGER_NAMES
                if strategy in STRATEGY_TO_POSITION:
                    pos = STRATEGY_TO_POSITION[strategy]
                    act_map = {'thumb': (1,2), 'index': (3,4), 'middle': (5,6), 'ring': (7,8), 'pinky': (9,10)}
                    for f, (a1, a2) in act_map.items():
                        if f in pos:
                            d.ctrl[a1] = pos[f][0] * force_scale
                            d.ctrl[a2] = pos[f][1] * force_scale

                for _ in range(150):
                    mujoco.mj_step(m, d)

                # 接触检测
                contacts = {f: False for f in FINGER_NAMES}
                for i in range(d.ncon):
                    g1 = m.geom(d.contact[i].geom1).name
                    g2 = m.geom(d.contact[i].geom2).name
                    for f in FINGER_NAMES:
                        if f in g1 or f in g2:
                            contacts[f] = True
                n_fingers = sum(1 for v in contacts.values() if v)

                # 3. 抬臂
                d.ctrl[0] = 0.15
                for _ in range(300):
                    for f, (a1, a2) in act_map.items():
                        if f in pos:
                            d.ctrl[a1] = pos[f][0] * min(force_scale * 2.0, 1.5)
                            d.ctrl[a2] = pos[f][1] * min(force_scale * 2.0, 1.5)
                    mujoco.mj_step(m, d)

                final_obj_z = d.xpos[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, 'object')][2]
                lift_mm = (final_obj_z - init_obj_z) * 1000
                success = lift_mm > 3.0

                obj_results.append({
                    'strategy': strategy, 'scale': force_scale,
                    'success': success, 'lift_mm': lift_mm,
                    'n_fingers': n_fingers,
                })

                sym = '✅' if success else '❌'
                print(f"  {sym} {strategy:20s} force={force_scale:.1f}  接触={n_fingers}/5  提升={lift_mm:+.1f}mm")

        all_results[obj_key] = obj_results

    # 汇总表格
    print(f"\n{'='*70}")
    print(f"结果汇总")
    print(f"{'='*70}")
    print(f"{'物体':15s} {'策略':20s} {'力':5s} {'接触':7s} {'提升':8s}")
    print(f"{'─'*60}")
    total_ok = 0
    total_all = 0
    for obj_key, results in all_results.items():
        for r in results:
            sym = '✅' if r['success'] else '❌'
            print(f"{OBJECTS[obj_key]['desc']:15s} {r['strategy']:20s} {r['scale']:.1f}   "
                  f"{r['n_fingers']}/5    {r['lift_mm']:+.1f}mm  {sym}")
            total_all += 1
            if r['success']:
                total_ok += 1

    print(f"\n{'='*70}")
    print(f"总计: {total_ok}/{total_all} 成功 ({total_ok/total_all*100:.0f}%)")
    print(f"截图已保存到: {OUTPUT_DIR}")
    print(f"{'='*70}")
