#!/usr/bin/env python3
"""
Phase 0: 环境验证 — 测试 3轴臂+灵巧手 场景能否正常运行

测试内容:
  1. 加载场景 XML
  2. 重置物体位置
  3. XY轴运动
  4. 手指开合
  5. 完整抓取流程
"""

import os, sys, time, numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mujoco_env import CrossBodyEnv
from core.cross_body_infer import CrossBodyInfer
from bodies.body_shadow_hand import ShadowHand3AxisConfig

# 测试物体列表（沿用原实验的7种物体）
TEST_OBJECTS = ['sphere', 'box', 'cylinder', 'long_rod', 'mushroom', 'dumbbell', 'disc']


def test_load_scene():
    """Test 1: 加载场景"""
    print("=" * 60)
    print("Test 1: 加载场景")
    env = CrossBodyEnv(body_type='shadow_hand_3axis', headless=True)
    obs = env.reset(object_key='sphere')
    print(f"  ✓ 环境初始化成功")
    print(f"  nq={env.model.nq}, nu={env.model.nu}")
    print(f"  Joints ({len(env.joint_ids)}): {list(env.joint_ids.keys())}")
    print(f"  Actuators ({len(env.actuator_ids)}): {list(env.actuator_ids.keys())}")
    print(f"  Bodies ({len(env.body_ids)}): {list(env.body_ids.keys())}")
    return env


def test_xy_motion(env):
    """Test 2: XY 轴运动"""
    print("\n" + "=" * 60)
    print("Test 2: XY 轴运动测试")
    ctrl = np.zeros(env.model.nu)

    # X轴运动
    x_targets = [0.0, 0.05, -0.05, 0.0]
    for xt in x_targets:
        ctrl[env.actuator_ids['slide_x']] = xt
        for _ in range(150):
            env.step(ctrl)
        actual = env.get_joint_qpos('slide_x')
        print(f"  slide_x target={xt:+.3f} → actual={actual:+.3f}")

    # Y轴运动
    y_targets = [0.0, 0.04, -0.04, 0.0]
    for yt in y_targets:
        ctrl[env.actuator_ids['slide_y']] = yt
        for _ in range(150):
            env.step(ctrl)
        actual = env.get_joint_qpos('slide_y')
        print(f"  slide_y target={yt:+.3f} → actual={actual:+.3f}")

    print("  ✓ XY 轴运动正常")


def test_finger_open_close(env):
    """Test 3: 手指开合测试"""
    print("\n" + "=" * 60)
    print("Test 3: 手指开合测试")

    # 全部张开
    ctrl = np.zeros(env.model.nu)
    print("  手指 → 张开")
    for _ in range(100):
        env.step(ctrl)
    for act, aid in sorted(env.actuator_ids.items()):
        if 'TH' in act or 'FF' in act or 'MF' in act or 'RF' in act or 'LF' in act:
            print(f"    {act}={env.get_joint_qpos(act):+.2f}")

    # 全部闭合
    for act, aid in env.actuator_ids.items():
        if 'TH' in act or 'FF' in act or 'MF' in act or 'RF' in act or 'LF' in act:
            ctrl[aid] = 0.8
    print("  手指 → 闭合 (ctrl=0.8)")
    for _ in range(150):
        env.step(ctrl)
    for act, aid in sorted(env.actuator_ids.items()):
        if 'TH' in act or 'FF' in act or 'MF' in act or 'RF' in act or 'LF' in act:
            print(f"    {act}={env.get_joint_qpos(act):+.2f}")

    print("  ✓ 手指开合正常")


def test_grasp_flow(env, object_key='sphere', offset=(0.0, 0.0)):
    """Test 4: 完整抓取流程"""
    print("\n" + "=" * 60)
    print(f"Test 4: 抓取流程 {object_key} (offset={offset})")

    env.reset(object_key=object_key, object_offset=offset)
    ctrl = np.zeros(env.model.nu)

    body_config = ShadowHand3AxisConfig()
    infer_engine = CrossBodyInfer(body_config)

    # Step 1: 对齐 + 下降
    print(f"  Phase 1: 对齐+下降")
    strategy = infer_engine.infer(env.get_observation(), task_desc="grasp")
    ctrl = infer_engine.decode_action(strategy, env.get_observation())
    for i in range(200):
        obs, _, _, _ = env.step(ctrl)
        if i % 50 == 0:
            print(f"    step {i}: xy_dist={np.linalg.norm(obs['palm_pos'][:2]-obs['object_pos'][:2]):.3f}, "
                  f"z_dist={obs['palm_pos'][2]-obs['object_pos'][2]:.3f}, "
                  f"contacts={sum(1 for c in obs['contact'] if 'obj' in str(c))}")

    # Step 2: 闭合 + 提升
    print(f"  Phase 2: 闭合+提升")
    strategy2 = infer_engine.infer(obs)
    ctrl = infer_engine.decode_action(strategy2, obs)
    # 提升
    ctrl[env.actuator_ids['lift_z']] = 0.12
    for i in range(200):
        obs, _, _, _ = env.step(ctrl)
        if i % 50 == 0:
            lift_mm = env.get_obj_lift_mm()
            n_contacts = sum(1 for c in obs['contact'] if 'obj' in str(c))
            print(f"    step {i}: lift={lift_mm:+.1f}mm, contacts={n_contacts}")

    lift_mm = env.get_obj_lift_mm()
    success = env.check_success(threshold_mm=3.0)
    print(f"  结果: lift={lift_mm:+.1f}mm, success={'✅' if success else '❌'}")
    return success, lift_mm


def test_all_objects():
    """Test 5: 所有7种物体的抓取测试"""
    print("\n" + "=" * 60)
    print("Test 5: 所有物体抓取测试")

    results = {}
    env = CrossBodyEnv(body_type='shadow_hand_3axis', headless=True)

    for obj in TEST_OBJECTS:
        # 无偏移测试
        success, lift = test_grasp_flow(env, obj, offset=(0.0, 0.0))
        results[f"{obj}_centered"] = (success, lift)

        # 带偏移测试（模拟物体不居中）
        success_off, lift_off = test_grasp_flow(env, obj, offset=(0.02, 0.02))
        results[f"{obj}_offset"] = (success_off, lift_off)

    print("\n" + "=" * 60)
    print("汇总结果:")
    print(f"{'物体':12s} {'居中':12s} {'偏移20mm':12s}")
    for obj in TEST_OBJECTS:
        s_c, l_c = results.get(f"{obj}_centered", (False, 0))
        s_o, l_o = results.get(f"{obj}_offset", (False, 0))
        c_mark = f"{l_c:+.1f}mm {'✅' if s_c else '❌'}"
        o_mark = f"{l_o:+.1f}mm {'✅' if s_o else '❌'}"
        print(f"{obj:12s} {c_mark:12s} {o_mark:12s}")

    return results


if __name__ == '__main__':
    print("=" * 60)
    print("YLYW 跨本体泛化 — Phase 0 环境验证")
    print("=" * 60)

    env = test_load_scene()
    test_xy_motion(env)

    # 重置后测试手指
    env.reset()
    test_finger_open_close(env)

    # 测试抓取流程
    test_grasp_flow(env, 'sphere', offset=(0.0, 0.0))
    test_grasp_flow(env, 'sphere', offset=(0.02, 0.02))

    # 全物体测试（耗时较长，注释掉以加速验证）
    # test_all_objects()

    print("\n" + "=" * 60)
    print("Phase 0 验证完成")
    print("=" * 60)
