#!/usr/bin/env python3
"""
特征提取 + 先验手册集成演示

在 PyBullet 仿真环境中提取物体特征，输入先验手册进行推理。
需要安装: pybullet

运行方式:
    pip install pybullet
    cd /home/lijinhan/MXL/科研/YLYW
    python3 scripts/demo_feature_extraction.py

如果没有 GUI 环境，请设置:
    export DISPLAY=:0
    或使用 p.DIRECT 模式（无渲染）
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from ylyw.prior_manual import PriorManual
from ylyw.perception import FeatureExtractor


def create_simulation(gui: bool = True):
    """
    创建仿真的测试环境

    Returns:
        (client_id, robot_id, gripper_id, object_ids)
    """
    import pybullet as p
    import pybullet_data

    # 连接
    if gui:
        client_id = p.connect(p.GUI)
    else:
        client_id = p.connect(p.DIRECT)

    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1.0 / 240.0)

    # 加载地面
    plane_id = p.loadURDF("plane.urdf")

    # 加载机械臂（可选，这里只演示特征提取）
    robot_id = -1
    gripper_id = -1

    # 创建物体（用字典记录类型，pybullet返回的int不支持setattr）
    object_ids = []
    object_types = {}  # {obj_id: type_name}

    # 红色球体（使用 sphere2.urdf 或 sphere_small.urdf）
    sphere_id = p.loadURDF("sphere2.urdf", [0.3, 0.0, 0.15],
                           globalScaling=0.15)
    object_types[sphere_id] = 'sphere'
    object_ids.append(sphere_id)

    # 蓝色立方体
    cube_id = p.loadURDF("cube.urdf", [-0.2, 0.2, 0.05],
                          globalScaling=0.1)
    object_types[cube_id] = 'cube'
    object_ids.append(cube_id)

    # 易碎花瓶（用小立方体代替）
    vase_id = p.loadURDF("cube_small.urdf", [0.0, -0.3, 0.08],
                          globalScaling=0.08)
    object_types[vase_id] = 'bottle'
    object_ids.append(vase_id)

    # 等待物理稳定
    for _ in range(100):
        p.stepSimulation()

    return client_id, robot_id, gripper_id, object_ids, object_types


def run_demo(gui: bool = True):
    """运行完整演示"""

    # ========== 检查依赖 ==========
    try:
        import pybullet as p
    except ImportError:
        print("❌ 请先安装 pybullet: pip install pybullet")
        return

    # ========== 初始化 ==========
    print("=" * 70)
    print("  YLYW 特征提取 + 先验推理集成演示")
    print("=" * 70)

    print("\n[1/4] 创建仿真环境...")
    client_id, robot_id, gripper_id, objects, object_types = create_simulation(gui=gui)

    print("[2/4] 初始化特征提取器 & 先验手册...")
    extractor = FeatureExtractor(robot_id, gripper_id, client_id)
    manual = PriorManual(verbose=True)

    print(f"[3/4] 场景中有 {len(objects)} 个物体，开始逐个分析...\n")

    # 目标位置（假设要抓取红球）
    target_pos = [0.3, 0.0, 0.15]

    results = []

    for obj_id in objects:
        obj_name = object_types.get(obj_id, 'unknown')
        obj_pos, _ = p.getBasePositionAndOrientation(obj_id, client_id)
        is_target = (np.linalg.norm(np.array(obj_pos) - np.array(target_pos)) < 0.1)

        print(f"\n{'─' * 60}")
        print(f"  物体: {obj_name} {'⭐ 目标' if is_target else ''}")
        print(f"  位置: ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})")
        print(f"{'─' * 60}")

        # 提取特征
        features = extractor.extract_all_features(
            obj_id,
            target_position=target_pos if is_target else None,
            obstacles_ids=[o for o in objects if o != obj_id]
        )

        # 显示特征
        print(f"\n  [提取的特征]")
        print(f"    稳定性: {features.stability:.3f}  | 滚动: {features.roll_tendency:.3f}")
        print(f"    所需力: {features.strength_needed:.3f}  | 脆弱: {features.fragility:.3f}")
        print(f"    可达性: {features.reachability:.3f}  | 抓取面: {features.grasp_surface_quality:.3f}")
        print(f"    支撑: {features.support_area:.3f}    | 遮挡: {features.occlusion:.3f}")
        print(f"    障碍: {features.obstacle_density:.3f}  | 优先级: {features.task_priority:.3f}")

        # 输入先验手册
        features_dict = features.to_dict()
        perception = manual.perceive_and_encode(features_dict)
        strategy = manual.get_grasp_strategy(perception)

        results.append({
            'name': obj_name,
            'is_target': is_target,
            'perception': perception,
            'strategy': strategy,
        })

    # ========== 总结 ==========
    print(f"\n\n{'=' * 70}")
    print("  [4/4] 推理汇总")
    print(f"{'=' * 70}")
    print(f"\n{'物体':<12s} {'目标':<6s} {'主导卦':<8s} {'最佳卦象':<16s} {'策略':<20s} {'力':<6s} {'速度'}")
    print("-" * 85)

    for r in results:
        name = r['name']
        target = '⭐' if r['is_target'] else ''
        tri = r['perception']['dominant_trigram'].name
        hex_name = r['strategy']['hexagram'][:12]
        strat = r['strategy']['type']
        force = f"{r['strategy']['force']:.2f}"
        speed = r['strategy']['speed']

        print(f"{name:<12s} {target:<6s} {tri:<8s} {hex_name:<16s} {strat:<20s} {force:<6s} {speed}")

    print("\n" + "=" * 70)
    print("  ✅ 集成演示完毕！")
    print("=" * 70)
    print("""
  💡 下一步:
     1. 在场景中添加更多物体（碗、盘子等）
     2. 实现完整的抓取执行（运动规划 + 夹爪控制）
     3. 记录50次抓取实验的成功率作为零样本基线
     4. 引入小样本微调：用10次成功示范微调特征参数
    """)

    # 如果 GUI 模式，保持窗口打开
    if gui:
        print("\n  仿真窗口保持打开，按 Ctrl+C 退出...")
        try:
            while True:
                p.stepSimulation()
                time.sleep(1.0 / 240.0)
        except KeyboardInterrupt:
            pass
    else:
        print("  使用 p.DIRECT 模式，自动关闭。")

    p.disconnect()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YLYW 特征提取演示")
    parser.add_argument("--no-gui", action="store_true",
                        help="使用无渲染模式（适合服务器）")
    args = parser.parse_args()

    run_demo(gui=not args.no_gui)
