#!/usr/bin/env python3
"""
YLYW 灵犀X2 + OmniHand 2025 抓取实物验证 — 主实验脚本

Phase 1: 手动特征 → YLYW推理 → 左灵巧手控制（无摄像头）

用法:
  # 列出所有可用物体
  python3 grasp_experiment.py --list

  # 单物体演示（详细推理过程，不执行灵巧手）
  python3 grasp_experiment.py --object tennis_ball --demo

  # 单物体执行（推理 + 灵巧手控制）
  python3 grasp_experiment.py --object tennis_ball --execute

  # 完整实验序列（所有物体，不执行灵巧手，仅推理）
  python3 grasp_experiment.py --batch

  # 完整实验序列 + 灵巧手执行
  python3 grasp_experiment.py --batch --execute

  # 只测试灵巧手通讯（全开→半开→全闭→全开）
  python3 grasp_experiment.py --test-hand

  # 指定某类物体批量测试
  python3 grasp_experiment.py --type sphere --batch --execute

依赖:
  - Python 3.10+
  - rclpy, aimdk_msgs (灵犀X2 SDK)
  - numpy
  - ylyw.prior_manual (YLYW推理引擎)
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目路径 — 确保能导入 YLYW
SCRIPT_DIR = Path(__file__).parent
YLYW_ROOT = SCRIPT_DIR.parent.parent  # /ylyw/ 目录
sys.path.insert(0, str(YLYW_ROOT))

import numpy as np
from prior_manual import PriorManual
from prior_manual.prior_manual import PriorManual as PM

# 物体预设
from object_presets import (
    OBJECT_PRESETS,
    STRATEGY_FINGER_PARAMS,
    get_feature_dict,
    list_object_types,
    get_objects_by_type,
)

# ROS2 导入（在灵犀X2上需要）
try:
    import rclpy
    from rclpy.node import Node
    from aimdk_msgs.msg import HandCommandArray, HandCommand, HandType, MessageHeader
    HAS_ROS2 = True
except ImportError:
    HAS_ROS2 = False
    Node = object  # placeholder
    print("⚠️  ROS2 未安装，灵巧手控制不可用（推理模式仍可使用）")


# ============================================================
# 灵巧手控制器
# ============================================================
class OmniHandController(Node if HAS_ROS2 else object):
    """左手 OmniHand 2025 控制器（需要 ROS2）"""

    LEFT_MOTORS = [
        'left_thumb', 'left_index', 'left_index',
        'left_middle', 'left_middle', 'left_ring',
        'left_ring', 'left_pinky', 'left_pinky', 'left_thumb',
    ]

    def __init__(self, use_nimble: bool = False):
        if not HAS_ROS2:
            raise RuntimeError("ROS2 未安装，无法控制灵巧手")
        super().__init__('ylyw_grasp_experiment')
        self.use_nimble = use_nimble

        self.publisher = self.create_publisher(
            HandCommandArray,
            '/aima/hal/joint/hand/command',
            10
        )
        self.get_logger().info("✅ OmniHandController 就绪")

    def open_hand(self, width: float = 1.0):
        """张开灵巧手"""
        self.get_logger().info(f"🖐 张开灵巧手 (width={width:.1f})")
        self._publish_hand(position=width, effort=0.3)

    def close_hand(self, position: float = 0.0, velocity: float = 0.5,
                   effort: float = 0.5):
        """闭合灵巧手"""
        self.get_logger().info(
            f"✊ 闭合灵巧手 (pos={position:.1f}, vel={velocity:.1f}, "
            f"effort={effort:.2f})"
        )
        self._publish_hand(position=position, velocity=velocity, effort=effort)

    def execute_strategy(self, strategy_name: str, force_scale: float = 1.0):
        """执行YLYW输出的抓取策略"""
        params = STRATEGY_FINGER_PARAMS.get(
            strategy_name,
            STRATEGY_FINGER_PARAMS["conditional_grasp"]
        )

        # 力缩放 = YLYW的force_preset × modifier
        scaled_effort = min(1.0, max(0.1, params['effort'] * force_scale))

        self.get_logger().info(
            f"🎯 执行策略: {params['description']} "
            f"| force_scale={force_scale:.2f} "
            f"| effort={scaled_effort:.2f}"
        )

        # 第一步: 张开
        self.open_hand()
        time.sleep(0.5)

        # 第二步: 闭合
        self._publish_hand(
            position=params['position'],
            velocity=params['velocity'],
            effort=scaled_effort
        )
        time.sleep(1.0)

    def _publish_hand(self, position: float, velocity: float = 1.0,
                      effort: float = 0.5):
        """发布左手控制指令"""
        msg = HandCommandArray()
        msg.header = MessageHeader()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'ylyw_grasp'

        if self.use_nimble:
            # NIMBLE_HANDS: 10指独立控制
            msg.left_hand_type = HandType(value=1)
            msg.right_hand_type = HandType(value=1)
            msg.left_hands = []
            for name in self.LEFT_MOTORS:
                cmd = HandCommand()
                cmd.name = name
                cmd.position = float(position)
                cmd.velocity = float(velocity)
                cmd.acceleration = 1.0
                cmd.deceleration = 1.0
                cmd.effort = float(effort)
                msg.left_hands.append(cmd)
            msg.right_hands = []
        else:
            # Gripper: 简易夹爪模式
            msg.left_hand_type = HandType(value=2)
            msg.right_hand_type = HandType(value=2)
            cmd = HandCommand()
            cmd.name = "left_hand"
            cmd.position = float(position)
            cmd.velocity = float(velocity)
            cmd.acceleration = 1.0
            cmd.deceleration = 1.0
            cmd.effort = float(effort)
            msg.left_hands = [cmd]
            msg.right_hands = []

        self.publisher.publish(msg)

    def test_sequence(self):
        """运行灵巧手测试序列"""
        self.get_logger().info("=== 灵巧手通讯测试 ===")
        time.sleep(1.0)

        for i, (pos, desc) in enumerate([
            (1.0, "全开"), (0.5, "半开"), (0.0, "全闭"), (1.0, "再开")
        ], 1):
            self.get_logger().info(f"[{i}/4] {desc} (position={pos:.1f})")
            self._publish_hand(position=pos)
            time.sleep(2.5)

        self.get_logger().info("✅ 测试完成")


# ============================================================
# 实验管理器
# ============================================================
class GraspExperiment:
    """YLYW 抓取实物验证实验"""

    def __init__(self, execute: bool = False, verbose: bool = True,
                 use_nimble: bool = False):
        self.execute = execute
        self.verbose = verbose
        self.use_nimble = use_nimble

        # YLYW 推理引擎
        self.ylyw = PriorManual(verbose=verbose)

        # 灵巧手控制器
        self.hand = None
        if execute:
            if not HAS_ROS2:
                raise RuntimeError("无法执行模式: ROS2 未安装")
            self.hand = OmniHandController(use_nimble=use_nimble)

        # 实验结果
        self.results = []

    # ============================================================
    # 单物体实验
    # ============================================================
    def run_single(self, obj_key: str):
        """对单个物体运行推理 + 可选执行"""
        if obj_key not in OBJECT_PRESETS:
            print(f"❌ 未知物体: {obj_key}")
            print(f"   可用: {', '.join(OBJECT_PRESETS.keys())}")
            return None

        obj_info = OBJECT_PRESETS[obj_key]
        features = obj_info['features']

        # === 显示物体信息 ===
        print(f"\n{'='*60}")
        print(f"  物体: {obj_info['name']} ({obj_key})")
        print(f"  类型: {obj_info['type']}")
        print(f"{'='*60}")

        # 特征值
        print(f"\n  📐 13维物理特征:")
        feat_names = [
            '稳定性', '滚动倾向', '力需求', '脆弱性',
            '可达性', '抓取表面', '支撑面积', '遮挡',
            '障碍密度', '任务优先', '重量比', '可见性', '变形能力'
        ]
        for name, val in zip(feat_names, [
            features['stability'], features['roll_tendency'],
            features['strength_needed'], features['fragility'],
            features['reachability'], features['grasp_surface_quality'],
            features['support_area'], features['occlusion'],
            features['obstacle_density'], features['task_priority'],
            features['weight_ratio'], features['visibility'],
            features['deformability']
        ]):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"    {name:8s} [{bar}] {val:.3f}")

        # === YLYW 推理 ===
        t0 = time.perf_counter()
        perception, strategy = self.ylyw.process(features)
        t_infer = time.perf_counter() - t0

        # === 结果汇总 ===
        effective_force = strategy['force'] * strategy.get('force_modifier', 1.0)
        strategy_type = strategy['type']

        print(f"\n  ── YLYW 推理结果 ──")
        print(f"  卦象:    {strategy.get('hexagram', '?')}")
        print(f"  策略:    {strategy_type}")
        print(f"  力预设:  {strategy['force']:.2f}")
        print(f"  修正系数: {strategy.get('force_modifier', 1.0):.2f}")
        print(f"  有效力:  {effective_force:.2f}")
        print(f"  速度:    {strategy.get('speed', 'medium')}")
        print(f"  爻位评分: {strategy.get('yao_quality', 0):.2f}")
        print(f"  推理耗时: {t_infer*1000:.1f} ms")
        if strategy.get('cautions'):
            print(f"  注意事项: {'; '.join(strategy['cautions'])}")

        # 完整的可解释推理链
        if self.verbose:
            print(f"\n  ── 完整推理链 ──")
            chain = self.ylyw.explain_reasoning(perception)
            print(chain)

        # === 灵巧手执行 ===
        if self.execute and self.hand:
            print(f"\n  ── 灵巧手执行 ──")
            safety = input(f"  ⚠️  确认执行抓取? (y/N): ").strip().lower()
            if safety == 'y':
                self.hand.execute_strategy(strategy_type, effective_force)
                print(f"  ✅ 抓取执行完成")
            else:
                print(f"  ⏭ 跳过执行")

        # 记录结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "obj_key": obj_key,
            "obj_name": obj_info['name'],
            "obj_type": obj_info['type'],
            "hexagram": strategy.get('hexagram', '?'),
            "strategy": strategy_type,
            "force_preset": strategy['force'],
            "modifier": strategy.get('force_modifier', 1.0),
            "effective_force": effective_force,
            "S_yao": strategy.get('yao_quality', 0),
            "inference_ms": round(t_infer * 1000, 2),
            "similarity": float(perception.get('hexagram_match_score', 0)),
            "executed": self.execute,
        }
        self.results.append(result)

        return result

    # ============================================================
    # 批量实验
    # ============================================================
    def run_batch(self, obj_type: str = None):
        """对一批物体运行实验"""
        if obj_type:
            objects = get_objects_by_type(obj_type)
            if not objects:
                print(f"❌ 无效类型: {obj_type}")
                return
            print(f"\n{'='*60}")
            print(f"  批量实验: 类型={obj_type}, 实例数={len(objects)}")
            print(f"{'='*60}")
        else:
            objects = list(OBJECT_PRESETS.items())
            print(f"\n{'='*60}")
            print(f"  批量实验: 全部物体, 总数={len(objects)}")
            print(f"{'='*60}")

        # 如果是执行模式，先确认
        if self.execute and self.hand:
            print(f"\n  ⚠️  将依次对 {len(objects)} 个物体执行灵巧手抓取")
            print(f"  请确保实验台安全，灵巧手工作区域无障碍")
            safety = input(f"  确认开始? (y/N): ").strip().lower()
            if safety != 'y':
                print(f"  ⏭ 取消执行")
                return

        for i, (key, info) in enumerate(objects, 1):
            print(f"\n  [{i}/{len(objects)}] ", end="")
            if self.execute and self.hand:
                print(f"⏳ 请将 {info['name']} 放在实验台后按 Enter...", end="")
                input()

            self.run_single(key)
            time.sleep(1.0)  # 物体间间隔

        self.print_summary()

    # ============================================================
    # 汇总报告
    # ============================================================
    def print_summary(self):
        """打印实验汇总"""
        if not self.results:
            return

        print(f"\n{'='*60}")
        print(f"  实验汇总")
        print(f"{'='*60}")

        n = len(self.results)
        strategies = {}
        types_ok = {}

        for r in self.results:
            s = r['strategy']
            strategies[s] = strategies.get(s, 0) + 1
            t = r['obj_type']
            if t not in types_ok:
                types_ok[t] = {'total': 0, 'strategies': set()}
            types_ok[t]['total'] += 1
            types_ok[t]['strategies'].add(s)

        avg_infer = np.mean([r['inference_ms'] for r in self.results])
        avg_S = np.mean([r['S_yao'] for r in self.results])
        avg_sim = np.mean([r['similarity'] for r in self.results])

        print(f"  总实验数:   {n}")
        print(f"  平均推理:   {avg_infer:.1f} ms")
        print(f"  平均爻位评分: {avg_S:.2f}")
        print(f"  平均相似度:  {avg_sim:.4f}")
        print(f"")
        print(f"  策略分布:")
        for s, c in sorted(strategies.items(), key=lambda x: -x[1]):
            bar = "█" * (c * 30 // max(strategies.values()))
            print(f"    {s:25s} {bar} {c}")
        print(f"")
        print(f"  按类型统计:")
        for t, info in sorted(types_ok.items()):
            print(f"    {t:8s}: {info['total']}个 → "
                  f"{len(info['strategies'])}种策略 "
                  f"({', '.join(sorted(info['strategies']))})")
        print(f"{'='*60}\n")

        # 保存 JSON
        path = Path(f"grasp_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        print(f"📁 结果已保存: {path}")


# ============================================================
# main
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='YLYW 灵犀X2 灵巧手抓取实物验证',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 grasp_experiment.py --list              # 列出所有物体
  python3 grasp_experiment.py --object tennis_ball --demo       # 单物体演示
  python3 grasp_experiment.py --object tennis_ball --execute    # 单物体执行
  python3 grasp_experiment.py --batch --execute   # 批量执行
  python3 grasp_experiment.py --test-hand          # 测试灵巧手
        """
    )

    # 模式选择
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--list', action='store_true',
                       help='列出所有可用物体')
    group.add_argument('--test-hand', action='store_true',
                       help='测试灵巧手通讯')
    group.add_argument('--object', type=str, metavar='KEY',
                       help='指定物体 (如 tennis_ball)')
    group.add_argument('--batch', action='store_true',
                       help='批量运行所有物体')

    # 参数
    parser.add_argument('--type', type=str, metavar='TYPE',
                        help='批量时限定物体类型 (sphere/cube/cylinder/bowl/bottle/plate/rock/vase)')
    parser.add_argument('--demo', action='store_true',
                        help='演示模式（详细推理链）')
    parser.add_argument('--execute', action='store_true',
                        help='执行灵巧手控制（需要ROS2）')
    parser.add_argument('--nimble', action='store_true',
                        help='使用 NIMBLE_HANDS 10指模式（默认Gripper模式）')
    parser.add_argument('--quiet', action='store_true',
                        help='安静模式（减少日志输出）')

    args = parser.parse_args()

    # ── --list ──
    if args.list:
        list_object_types()
        return 0

    # ── --test-hand ──
    if args.test_hand:
        if not HAS_ROS2:
            print("❌ ROS2 未安装，无法测试灵巧手")
            return 1
        rclpy.init()
        try:
            node = OmniHandController(use_nimble=args.nimble)
            node.test_sequence()
        finally:
            node.destroy_node()
            rclpy.shutdown()
        return 0

    # ── 实验模式 ──
    verbose = not args.quiet
    experiment = GraspExperiment(
        execute=args.execute,
        verbose=verbose,
        use_nimble=args.nimble,
    )

    # ROS2 初始化（执行模式需要）
    if args.execute:
        if not HAS_ROS2:
            print("❌ ROS2 未安装，无法执行灵巧手控制")
            print("   请使用 --demo 模式仅推理")
            return 1
        rclpy.init()

    try:
        if args.batch:
            experiment.run_batch(obj_type=args.type)
        elif args.object:
            experiment.run_single(args.object)
        else:
            # 默认: 演示第一个物体
            print("未指定物体，使用默认演示模式")
            first_key = list(OBJECT_PRESETS.keys())[0]
            experiment.run_single(first_key)

    except KeyboardInterrupt:
        print(f"\n⏹ 用户中断")
    finally:
        if args.execute and experiment.hand:
            # 实验结束，张开灵巧手
            experiment.hand.open_hand()
            time.sleep(1.0)
            experiment.hand.destroy_node()
            rclpy.shutdown()

    return 0


if __name__ == '__main__':
    sys.exit(main())
