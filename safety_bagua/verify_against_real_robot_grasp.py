"""最小验证：把 safety_bagua 双八卦仲裁接到 real_robot_grasp，对比力修正。

跑法：cd /home/lijinhan/MXL/科研/ylyw && python3 _verify_safety_bagua.py
不修改任何项目文件，只导入现有模块。
"""
import sys
from pathlib import Path

ROOT = Path("/home/lijinhan/MXL/科研/ylyw")
SCI = ROOT.parent                     # /home/lijinhan/MXL/科研
sys.path.insert(0, str(SCI))          # 使 ylyw.safety_bagua 可解析
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "motion_control"))

import numpy as np

from real_robot_grasp.config import AppConfig, FeaturesConfig, YlywConfig, YlywGraspConfig
from real_robot_grasp.ylyw_grasp_planner import YlywGraspPlanner
from real_robot_grasp.object_features import analyze_object

from ylyw.safety_bagua.dual_bagua_arbiter import DualBaguaArbiter
from ylyw.safety_bagua.safety_hexagram_rules import SafetyLevel


def _cube(r, L, W, H):
    nside = 2000
    pts = r.uniform(-1, 1, (nside, 3)) * 0.5
    sizes = np.array([L, W, H])
    all_pts = []
    for axis in range(3):
        for s in (-1, 1):
            p = np.copy(pts)
            p[:, axis] = s * 0.5
            p = p * sizes
            all_pts.append(p)
    cloud = np.vstack(all_pts)
    cloud[:, 2] = cloud[:, 2] - cloud[:, 2].min()
    return cloud


def _bottle(r, radius, height):
    n = 4000
    th = r.uniform(0, 2*np.pi, n)
    rr = radius * np.sqrt(r.uniform(0, 1, n))
    z = r.uniform(0, height, n)
    return np.column_stack([rr*np.cos(th), rr*np.sin(th), z])


def _sphere(r, rad):
    pts = r.normal(size=(3000, 3))
    pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * rad
    pts[:, 2] = np.abs(pts[:, 2])
    return pts


KINDS = {
    "cube_large":    lambda r: _cube(r, 0.10, 0.08, 0.06),
    "cube_small":    lambda r: _cube(r, 0.04, 0.04, 0.03),
    "flat_box":      lambda r: _cube(r, 0.13, 0.09, 0.012),
    "bottle":        lambda r: _bottle(r, 0.025, 0.12),
    "sphere":        lambda r: _sphere(r, 0.033),
    "cylinder_tall": lambda r: _bottle(r, 0.015, 0.16),
}


def main():
    feat_cfg = FeaturesConfig(min_points=30)
    planner = YlywGraspPlanner(YlywConfig(verbose=False), None)
    planner.load()                      # 载入 ylyw_core
    arbiter = DualBaguaArbiter(robot_tau_max=5.0)

    print(f"{'物体':<16}{'策略(卦)':<14}{'形状技策略':<18}"
          f"{'策略力':<7}{'稳定修正':<8}{'安全等级':<11}{'安全卦':<7}"
          f"{'力修正':<8}{'最终力':<8}备注")
    print("-" * 128)

    for seed, kind in enumerate(KINDS, 1):
        try:
            pts = KINDS[kind](np.random.default_rng(seed))
            obj = analyze_object(pts, feat_cfg, label=kind)
            if obj is None:
                print(f"{kind:<16} 分析失败(点数不足)"); continue
            plan = planner.plan(obj)

            # 当前 real_robot_grasp 路径：只乘策略爻位修正
            cur_final = plan.force * plan.force_modifier

            # 双八卦路径：策略时输出 + 安全八卦仲裁
            strategy_out = {
                "type": plan.strategy_type,
                "force": plan.force,
                "approach_angle": plan.approach_angle_deg,
                "speed": "medium",
                "force_modifier": plan.force_modifier,
            }
            safe = arbiter.arbitrate(features=obj.features,
                                     strategy_output=strategy_out, perception={})

            note = ""
            if safe.safety_level == SafetyLevel.CRITICAL:
                note = "🚨应终止"
            elif safe.safety_level == SafetyLevel.DANGER:
                note = "⚠️人工确认"
            elif safe.needs_hexagram_change:
                note = "需变卦"
            delta = (safe.final_force - cur_final)
            extra = f" Δ={delta:+.2f}" if abs(delta) > 1e-9 else "  (不变)"
            print(f"{kind:<16}{plan.hexagram:<14}{plan.strategy_type[:17]:<18}"
                  f"{plan.force:<7.2f}{plan.force_modifier:<8.2f}"
                  f"{safe.safety_level.value:<11}{safe.safety_hexagram:<7}"
                  f"{safe.force_modifier_total:<8.2f}{safe.final_force:<8.2f}{note}{extra}")
            if safe.risk_tags:
                print(f"{'':<16}           风险: {safe.risk_tags}")
        except Exception as e:
            print(f"{kind:<16} 出错: {type(e).__name__}: {e}")

    print("\n对照：")
    print("  当前 real_robot_grasp 最终力 = 策略力 × 爻位修正(plan.force_modifier，来自策略八卦 L3+)。")
    print("  双八卦最终力 = 策略力 × (爻位修正 × 安全等级修正)，安全等级由 6 条物理公式六爻判定，")
    print("  DANGER/CRITICAL 可触发降力/降速/变卦/终止。")


if __name__ == "__main__":
    main()
