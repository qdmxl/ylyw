"""YLYW 易理抓取规划模块 —— 深度相机特征 → 六十四卦 → 抓取动作规划。

核心链路（YLYW 分层推理，直接复用项目既有的先验手册 PriorManual）：

    ObjectFeatures(13维感知特征)
        ↓  L1 八卦基元隶属度
        物体物理属性分类
        ↓  L2 六爻编码
        状态向量化
        ↓  L3 六十四卦匹配
        最佳卦象 + 匹配度
        ↓  L3+ 爻位关系(乘承比应当位得中)
        综合质量 / 谨慎度
        ↓  决策
        抓取策略: {type, force, approach_angle, speed, cautions, hexagram}

本类再把 YLYW 抽象策略具体化为真实机械臂可执行的抓取参数
(`GraspPlan`)，并整体记录推理链(供论文链路可视化)。

依赖：`ylyw_core`（先验手册主类）。路径由 `YlywConfig.ylyw_core_path`
指向。项目内自带副本：`api_docs/`(ylyw_core 在其下) 或
`x2/ylyw_full_pipeline/`(ylyw_core 在其下)。
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .config import YlywConfig, YlywGraspConfig
from .object_features import ObjectFeatures

LOGGER = logging.getLogger(__name__)


@dataclass
class GraspPlan:
    """YLYW 推理得出的最终抓取方案。"""

    label: str                     # 物体类别
    # — YLYW 推理中间结果 —
    dominant_trigram: str = ""     # 主导八卦
    hexagram: str = ""             # 匹配卦象名(英文枚举，如 SHENG)
    hexagram_cn: str = ""          # 卦名(中文，如 地风升)
    hexagram_upper_lower: str = "" # 上下卦组合，如 坤巽
    hexagram_desc: str = ""        # 卦辞
    hexagram_score: float = 0.0
    yin_yang: str = ""             # 六爻阴阳串，如 "——— — —"
    top_k: list = field(default_factory=list)
    yao_quality: float = 0.0
    caution_level: str = ""
    force_modifier: float = 1.0
    strategy_type: str = ""        # YLYW抓取类型
    # — 映射到机械臂 —
    approach_angle_deg: float = 0.0
    speed_level: int = 3           # MyCobot 1~5
    close_value: int = 30          # 夹爪夹紧值(越小越紧)
    force: float = 0.5
    cautions: list = field(default_factory=list)
    # — 目标位姿(相机系, 米) —
    grasp_xyz: np.ndarray = field(default_factory=lambda: np.zeros(3))
    # — 特征快照 —
    features: dict = field(default_factory=dict)

    def reasoning_chain(self) -> Dict:
        """返回完整推理链(供论文可视化/记录)。"""
        return {
            "label": self.label,
            "dominant_trigram": self.dominant_trigram,
            "hexagram": self.hexagram,
            "hexagram_cn": self.hexagram_cn,
            "upper_lower": self.hexagram_upper_lower,
            "description": self.hexagram_desc,
            "hexagram_score": round(self.hexagram_score, 4),
            "top_k_hexagrams": [(h, round(s, 4)) for h, s in self.top_k],
            "yin_yang": self.yin_yang,
            "yao_quality": round(self.yao_quality, 4),
            "caution_level": self.caution_level,
            "strategy_type": self.strategy_type,
            "force": round(self.force, 3),
            "force_modifier": round(self.force_modifier, 3),
            "approach_angle_deg": round(self.approach_angle_deg, 1),
            "speed_level": self.speed_level,
            "close_value": self.close_value,
            "cautions": self.cautions,
        }


class YlywGraspPlanner:
    """把物体特征喂给 YLYW 先验手册，得到抓取策略并参数化。"""

    def __init__(self, config: Optional[YlywConfig] = None,
                 grasp: Optional[YlywGraspConfig] = None):
        self.config = config or YlywConfig()
        self.grasp_cfg = grasp or YlywGraspConfig()
        self._manual = None
        self._strategy_maps = self._build_class_maps()

    def load(self) -> None:
        """加载 YLYW 先验手册。"""
        if self._manual is not None:
            return
        core_dir = Path(self.config.ylyw_core_path)
        if not (core_dir / "ylyw_core").is_dir():
            raise RuntimeError(
                f"ylyw_core 目录不存在: {core_dir}. 请核对 YlywConfig.ylyw_core_path"
            )
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))
        try:
            from ylyw_core.prior_manual import PriorManual
        except ImportError as exc:
            raise RuntimeError(
                f"无法导入 ylyw_core.prior_manual (from {core_dir}): {exc}"
            ) from exc
        self._manual = PriorManual(verbose=self.config.verbose)
        LOGGER.info("YLYW 先验手册已加载")

    # ---- 类别缺省覆盖(可由 YOLO 类别更新 fragility/质量等) ----
    def _build_class_maps(self) -> dict:
        return {
            # label: {fragility, deformability, default_mass}
            "bottle":    {"fragility": 0.3, "deformability": 0.1, "default_mass": 0.4},
            "cup":       {"fragility": 0.5, "deformability": 0.1, "default_mass": 0.2},
            "can":       {"fragility": 0.6, "deformability": 0.15, "default_mass": 0.33},
            "book":      {"fragility": 0.2, "deformability": 0.2, "default_mass": 0.4},
            "box":       {"fragility": 0.3, "deformability": 0.3, "default_mass": 0.3},
            "block":     {"fragility": 0.2, "deformability": 0.05, "default_mass": 0.1},
            "cup_cube":  {"fragility": 0.3, "deformability": 0.1, "default_mass": 0.12},
            "object":    {"fragility": 0.5, "deformability": 0.1, "default_mass": 0.15},
        }

    def build_features(self, obj: ObjectFeatures, mass_kg: Optional[float] = None,
                       fragility: Optional[float] = None) -> dict:
        """构造喂给 YLYW 的 13 维特征(可叠加类别先验)。"""
        feats = dict(obj.features)
        meta = self._strategy_maps.get(obj.label, self._strategy_maps["object"])
        if fragility is None:
            fragility = meta["fragility"]
        if mass_kg is None:
            mass_kg = meta["default_mass"]
        feats["fragility"] = float(fragility)
        feats["deformability"] = float(meta["deformability"])
        feats["strength_needed"] = min(1.0, mass_kg / 2.0 + 0.1)
        feats["weight_ratio"] = mass_kg / 2.0
        return feats

    # ---- 主入口 ----
    def plan(self, obj: ObjectFeatures, mass_kg: Optional[float] = None,
             fragility: Optional[float] = None) -> GraspPlan:
        """对单个物体做 YLYW 抓取规划。"""
        self.load()
        feats = self.build_features(obj, mass_kg, fragility)

        perception = self._manual.perceive_and_encode(feats)
        strategy = self._manual.get_grasp_strategy(perception)

        plan = GraspPlan(label=obj.label, grasp_xyz=obj.approachable_pose,
                         features=feats)

        # — 填充 YLYW 推理结果 —
        if perception.get("best_hexagram") is not None:
            hx = perception["best_hexagram"]
            plan.hexagram = getattr(hx, "name", "")
            plan.hexagram_score = float(perception.get("hexagram_match_score", 0.0))
            plan.yin_yang = self._yao_to_str(perception.get("yao_vector"))
            # 卦辞/卦名/上下卦
            try:
                rule = self._manual.hexagram_rules.get_rule(hx)
                if isinstance(rule, dict):
                    plan.hexagram_cn = rule.get("name", "")
                    ul = rule.get("upper_lower", "")
                    plan.hexagram_upper_lower = str(ul)
                    plan.hexagram_desc = rule.get("description", "")
            except Exception:
                pass
        plan.dominant_trigram = self._trigram_name(
            perception.get("dominant_trigram"))
        plan.top_k = [
            (getattr(h, "name", str(h)), float(s))
            for h, s in perception.get("top_k_hexagrams", [])
        ][:3]
        yr = perception.get("yao_relations")
        if yr is not None:
            plan.yao_quality = float(getattr(yr, "score_overall", 0.0))
            plan.caution_level = str(getattr(yr, "caution_level", ""))
            plan.force_modifier = float(getattr(yr, "strategy_modifier", 1.0))

        # — 策略参数化 —
        plan.strategy_type = strategy.get("type", "")
        plan.force = float(strategy.get("force", 0.5))
        try:
            plan.approach_angle_deg = float(strategy.get("approach_angle", 0.0))
        except (TypeError, ValueError):
            plan.approach_angle_deg = 0.0
        plan.cautions = list(strategy.get("cautions", []))
        plan.speed_level = self.grasp_cfg.speed_map.get(
            str(strategy.get("speed", "normal")).lower(), 3)
        plan.close_value = self._force_to_close(plan.force)

        return plan

    def _force_to_close(self, force: float) -> int:
        """力预设[0,1] → 夹爪夹紧值(越小越紧)。"""
        lo, hi = self.grasp_cfg.force_to_close_value
        # force 越大夹得越紧(值越小)
        f = float(np.clip(force, 0, 1))
        return int(round(hi - (hi - lo) * f))

    def _yao_to_str(self, yao_vec) -> str:
        if yao_vec is None:
            return ""
        try:
            return "".join("一" if v >= 0.5 else "阴" for v in np.asarray(yao_vec, dtype=float))
        except Exception:
            return str(yao_vec)

    def _trigram_name(self, trigram) -> str:
        if trigram is None:
            return ""
        try:
            return trigram.name
        except AttributeError:
            return str(trigram)


def format_plan(plan: GraspPlan) -> str:
    """人类可读的推理链(用于控制台/论文日志)。"""
    return (
        f"\n『{plan.label}』 → YLYW 推理链\n"
        f"  L1 主导卦: {plan.dominant_trigram}  "
        f"| L2 六爻: {plan.yin_yang or '-'}\n"
        f"  L3 匹配卦: {plan.hexagram_cn or plan.hexagram} "
        f"({plan.hexagram_upper_lower}) 得分 {plan.hexagram_score:.3f}  "
        f"Top3: {plan.top_k}\n"
        f"  卦辞: {plan.hexagram_desc or '-'}\n"
        f"  L3+ 爻位质量: {plan.yao_quality:.3f} | 谨慎度: {plan.caution_level}\n"
        f"  ── 决策 ──\n"
        f"  抓取类型: {plan.strategy_type} | 力: {plan.force:.2f} "
        f"(修正 ×{plan.force_modifier:.2f})\n"
        f"  接近角: {plan.approach_angle_deg:.0f}° | 速度档: {plan.speed_level} "
        f"| 夹爪夹紧值: {plan.close_value}\n"
        f"  注意事项: {'; '.join(plan.cautions) if plan.cautions else '无'}"
    )
