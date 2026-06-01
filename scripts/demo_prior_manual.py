#!/usr/bin/env python3
"""
先验手册演示（纯 Python，无需 PyBullet）

演示如何用硬编码的易理知识，对不同物体进行感知、推理和决策。
完全不依赖任何训练数据——纯粹靠预定义的先验知识。

运行方式:
    cd /home/lijinhan/MXL/科研/YLYW
    python3 scripts/demo_prior_manual.py
"""

import sys
import os

# 将 YLYW 的父目录（科研目录）加入路径，以便 import ylyw
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ylyw.prior_manual import PriorManual


def create_object_features(name, stability, roll_tendency, strength_needed,
                           fragility, task_priority, reachability=0.8,
                           support_area=0.5, occlusion=0.1,
                           obstacle_density=0.1, grasp_surface_quality=0.6,
                           weight_ratio=0.3, visibility=0.7, deformability=0.3):
    """便捷函数：创建物体特征字典"""
    return {
        'stability': stability,
        'roll_tendency': roll_tendency,
        'strength_needed': strength_needed,
        'fragility': fragility,
        'task_priority': task_priority,
        'reachability': reachability,
        'support_area': support_area,
        'occlusion': occlusion,
        'obstacle_density': obstacle_density,
        'grasp_surface_quality': grasp_surface_quality,
        'weight_ratio': weight_ratio,
        'visibility': visibility,
        'deformability': deformability,
        '_name': name,
    }


def run_demo():
    """运行演示"""
    manual = PriorManual(verbose=True)

    # ========================
    #  定义测试物体
    # ========================
    test_objects = [
        {
            'name': '🔴 红色球体',
            'desc': '易滚动、稳定性差、需要动态跟踪抓取',
            'features': create_object_features(
                '红色球体',
                stability=0.20,       # 很不稳定
                roll_tendency=0.90,   # 极易滚动
                strength_needed=0.30, # 轻，不需要大力
                fragility=0.25,       # 不易碎
                task_priority=0.85,   # 目标物体，优先级高
                reachability=0.90,
                support_area=0.10,    # 支撑面积极小
                occlusion=0.05,
                obstacle_density=0.20,
                grasp_surface_quality=0.55,
                weight_ratio=0.20,
                visibility=0.95,
                deformability=0.10,
            )
        },
        {
            'name': '🏺 易碎花瓶',
            'desc': '重心高、易碎、需要轻柔精确抓取',
            'features': create_object_features(
                '易碎花瓶',
                stability=0.55,       # 中等稳定
                roll_tendency=0.15,   # 不易滚动
                strength_needed=0.20, # 轻
                fragility=0.90,       # 极易碎
                task_priority=0.90,   # 目标物体
                reachability=0.75,
                support_area=0.35,
                occlusion=0.15,
                obstacle_density=0.25,
                grasp_surface_quality=0.60,
                weight_ratio=0.25,
                visibility=0.80,
                deformability=0.25,
            )
        },
        {
            'name': '📦 重型金属方块',
            'desc': '非常稳定、重、不易碎、需要强力抓取',
            'features': create_object_features(
                '重型金属方块',
                stability=0.95,       # 非常稳定
                roll_tendency=0.05,   # 几乎不滚动
                strength_needed=0.90, # 很重，大力抓
                fragility=0.10,       # 不易碎
                task_priority=0.70,   # 中等优先级
                reachability=0.85,
                support_area=0.70,
                occlusion=0.05,
                obstacle_density=0.10,
                grasp_surface_quality=0.75,
                weight_ratio=0.85,
                visibility=0.60,
                deformability=0.05,
            )
        },
        {
            'name': '🥣 陶瓷碗',
            'desc': '中空、有一定易碎性、可从凹陷处抓取',
            'features': create_object_features(
                '陶瓷碗',
                stability=0.60,
                roll_tendency=0.35,
                strength_needed=0.30,
                fragility=0.65,       # 较易碎
                task_priority=0.55,
                reachability=0.80,
                support_area=0.45,
                occlusion=0.10,
                obstacle_density=0.15,
                grasp_surface_quality=0.80,  # 有凹陷，好抓
                weight_ratio=0.20,
                visibility=0.60,
                deformability=0.15,
            )
        },
        {
            'name': '🪨 不规则石块',
            'desc': '形状不规则、重心偏移、表面粗糙',
            'features': create_object_features(
                '不规则石块',
                stability=0.45,
                roll_tendency=0.50,
                strength_needed=0.55,
                fragility=0.30,
                task_priority=0.40,    # 非目标，优先级低
                reachability=0.55,     # 被遮挡
                support_area=0.30,
                occlusion=0.70,        # 明显遮挡
                obstacle_density=0.65, # 周围拥挤
                grasp_surface_quality=0.35,
                weight_ratio=0.45,
                visibility=0.35,
                deformability=0.20,
            )
        },
        {
            'name': '🍽️ 磁盘子',
            'desc': '扁薄、易碎、需要从边缘小心抓取',
            'features': create_object_features(
                '磁盘子',
                stability=0.75,
                roll_tendency=0.10,
                strength_needed=0.15,
                fragility=0.85,       # 非常易碎
                task_priority=0.80,
                reachability=0.70,
                support_area=0.65,
                occlusion=0.20,
                obstacle_density=0.10,
                grasp_surface_quality=0.35,  # 太薄不好抓
                weight_ratio=0.10,
                visibility=0.55,
                deformability=0.15,
            )
        },
    ]

    # ========================
    #  执行推理
    # ========================
    print("\n" + "=" * 70)
    print("  YLYW 先验手册 — 零样本物体感知与决策演示")
    print("  （纯先验知识推理，无任何训练数据）")
    print("=" * 70)

    for i, obj in enumerate(test_objects, 1):
        print(f"\n{'─' * 70}")
        print(f"  测试 {i}/{len(test_objects)}: {obj['name']}")
        print(f"  描述: {obj['desc']}")
        print(f"{'─' * 70}")

        perception = manual.perceive_and_encode(obj['features'])
        strategy = manual.get_grasp_strategy(perception)

        # 简明输出
        print(f"\n  📊 结果: {perception['dominant_trigram'].name}卦 → "
              f"「{strategy['hexagram']}」→ {strategy['type']}")
        print(f"  ⚙️  力={strategy['force']:.2f} | 速={strategy['speed']}")

    # ========================
    #  详细推理链（最后一个物体）
    # ========================
    print(f"\n\n{'=' * 70}")
    print("  详细推理链（以「磁盘子」为例）")
    print(f"{'=' * 70}")
    last_obj = test_objects[-1]
    manual_quiet = PriorManual(verbose=False)
    perception = manual_quiet.perceive_and_encode(last_obj['features'])
    print(manual_quiet.explain_reasoning(perception))

    # ========================
    #  批量对比总结
    # ========================
    print(f"\n{'=' * 70}")
    print("  批量对比总结")
    print(f"{'=' * 70}")
    print(f"\n{'物体':<16s} {'主导卦':<8s} {'最佳卦象':<16s} {'抓取策略':<20s} {'力':<6s} {'速度'}")
    print("-" * 70)

    manual_quiet2 = PriorManual(verbose=False)
    for obj in test_objects:
        perception = manual_quiet2.perceive_and_encode(obj['features'])
        strategy = manual_quiet2.get_grasp_strategy(perception)

        name = obj['name']
        tri = perception['dominant_trigram'].name
        hex_name = strategy['hexagram'][:12]
        strat_type = strategy['type']
        force = f"{strategy['force']:.2f}"
        speed = strategy['speed']

        print(f"{name:<16s} {tri:<8s} {hex_name:<16s} {strat_type:<20s} {force:<6s} {speed}")

    print("\n✅ 演示完毕。所有决策均来自硬编码的先验知识，零训练数据！")
    print("💡 下一步：运行 demo_feature_extraction.py 与 PyBullet 仿真集成。\n")


if __name__ == "__main__":
    run_demo()
