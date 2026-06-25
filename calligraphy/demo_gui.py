#!/usr/bin/env python3
"""
YLYW 书法仿真 — 墨水尾迹 GUI 演示

方案：在 MuJoCo viewer 中，毛笔移动时在纸面上留下彩色小球标记。
用多个小几何体作为"墨点"，直观展示书写轨迹。

优点：纯 MuJoCo viewer，无需额外窗口或依赖。
"""

import os, sys, time, numpy as np
from pathlib import Path

XAUTH_FILES = list(Path('/run/user/1000').glob('.mutter-Xwaylandauth.*'))
if XAUTH_FILES:
    os.environ.setdefault('XAUTHORITY', str(XAUTH_FILES[0]))
os.environ.setdefault('DISPLAY', ':0')

import mujoco
from mujoco import viewer

sys.path.insert(0, str(Path(__file__).parent))
from stroke_ylyw import CalligraphyStrokeYLYW
from visual_calligraphy import CalligraphyVisualYLYW


def main():
    character = '大'
    speed = 3
    ink_spacing = 3     # 每隔多少步放一个墨点
    max_ink_dots = 300  # 最多墨点数（受内存限制）

    print(f"=== YLYW 书法仿真 — 「{character}」===")
    print(f"   MuJoCo Viewer: 毛笔(3D) + 墨迹小球")
    print(f"   速度={speed}  |  按 ESC 退出")
    print()

    # 从楷体字帖加载（优先），回退到程序生成
    import cv2
    copybook_path = Path(__file__).parent / 'input' / 'copybook' / f'{character}_楷体.png'
    if copybook_path.exists():
        target_img = cv2.imread(str(copybook_path), cv2.IMREAD_GRAYSCALE)
        print(f"字帖来源: 楷体渲染 ({copybook_path})")
    else:
        from learning_loop import _generate_target_calligraphy
        target_img = _generate_target_calligraphy(character)
        print(f"字帖来源: 程序生成")
    
    visual = CalligraphyVisualYLYW()
    perception = visual.perceive(target_img, verbose=False)
    print(f"字帖卦象: {perception.dominant_trigram} ({perception.hexagram_name})")
    print(f"字帖卦象: {perception.dominant_trigram} ({perception.hexagram_name})")

    # 生成计划
    stroke_ylyw = CalligraphyStrokeYLYW()
    plan = stroke_ylyw.plan_character(
        character, perception.trigram_memberships, perception.yao_features
    )
    trajectories, pressures = stroke_ylyw.get_trajectory_sequence(plan)

    # 合并轨迹
    all_traj, all_press = [], []
    for i, s in enumerate(plan.strokes):
        all_traj.append(s.trajectory)
        all_press.append(s.pressures)
        if i < len(plan.strokes) - 1:
            gap = np.linspace(s.trajectory[-1], plan.strokes[i+1].trajectory[0], 15)
            all_traj.append(gap)
            all_press.append(np.zeros(15))
    full_traj = np.vstack(all_traj)
    full_press = np.concatenate(all_press)
    total = len(full_traj)
    print(f"笔画数: {len(plan.strokes)}, 总点: {total}")

    # 构建模型（含预留墨点几何体）
    ink_dot_xml = ""
    for i in range(max_ink_dots):
        ink_dot_xml += f"""
        <body name="ink{i}" pos="0 0 -0.01">
            <geom name="inkg{i}" type="ellipsoid" size="0.003 0.003 0.0005"
                  rgba="0.05 0.05 0.05 0" pos="0 0 0.0015"/>
        </body>"""

    xml = f"""<mujoco model="c"><compiler angle="degree"/>
<visual><headlight diffuse="0.8 0.8 0.8" ambient="0.3 0.3 0.3"/></visual>
<worldbody>
<body name="paper" pos="0 0 0"><geom type="box" size="0.15 0.15 0.001" rgba="0.95 0.93 0.85 1"/></body>
<body name="brush_tip" pos="0 0 0.05">
<joint name="bx" type="slide" axis="1 0 0" range="-0.15 0.15"/>
<joint name="by" type="slide" axis="0 1 0" range="-0.15 0.15"/>
<joint name="bz" type="slide" axis="0 0 1" range="0.001 0.05"/>
<geom type="ellipsoid" size="0.004 0.004 0.01" pos="0 0 -0.005" rgba="0.1 0.1 0.1 1"/>
<geom type="capsule" size="0.006 0.05" pos="0 0 0.035" rgba="0.35 0.18 0.08 1"/>
</body>
{ink_dot_xml}
<camera name="top" mode="fixed" pos="0 0 0.5" xyaxes="1 0 0 0 -1 0" fovy="48"/>
</worldbody>
<actuator>
<position name="ax" joint="bx" kp="500"/><position name="ay" joint="by" kp="500"/>
<position name="az" joint="bz" kp="300"/>
</actuator></mujoco>"""

    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)

    step = 0
    ink_idx = 0  # 当前墨点序号
    last_ink_step = -ink_spacing

    # 预计算墨点颜色（随压力变化）
    stroke_colors = []
    for i in range(len(all_traj)):
        for j in range(len(all_traj[i])):
            tp = all_press[i][j] if i < len(all_press) else all_press[-1][j]
            # 有压力 = 墨色，无压力 = 跳过
            if tp > 0.01:
                gray = max(20, int(80 - 60 * tp))
                stroke_colors.append((gray/255, gray/255, gray/255, 1.0))
            else:
                stroke_colors.append(None)

    with viewer.launch_passive(model, data) as v:
        v.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
        v.cam.fixedcamid = 0
        print("  演示开始！墨点随时间出现...\n")

        while v.is_running():
            if step < total:
                for _ in range(speed):
                    if step >= total:
                        break
                    tx, ty = float(full_traj[step, 0]), float(full_traj[step, 1])
                    tp = float(full_press[step])
                    z_target = 0.0015 - tp * 0.005
                    z_target = max(0.0001, z_target)
                    data.ctrl[0] = tx
                    data.ctrl[1] = ty
                    data.ctrl[2] = z_target
                    mujoco.mj_step(model, data)

                    # 在当前笔尖位置放墨点
                    if tp > 0.01 and step - last_ink_step >= ink_spacing and ink_idx < max_ink_dots:
                        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f'inkg{ink_idx}')
                        # 用 geom 的父 body 位置
                        body_id = model.geom_bodyid[geom_id]
                        jnt_addr = model.body_jntadr[body_id]
                        if model.body_jntnum[body_id] >= 1:
                            data.qpos[jnt_addr] = tx
                            data.qpos[jnt_addr + 1] = ty
                            data.qpos[jnt_addr + 2] = 0.0015
                        model.geom_rgba[geom_id] = [0.05, 0.05, 0.05, 1.0]
                        ink_idx += 1
                        last_ink_step = step

                    step += 1
            else:
                mujoco.mj_step(model, data)

            v.sync()
            time.sleep(0.003)

    print(f"\n  演示结束 | 步数: {step}/{total} | 墨点: {ink_idx}")


if __name__ == '__main__':
    main()
