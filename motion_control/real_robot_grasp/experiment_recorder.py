"""实验数据记录模块 —— 为物体抓取论文补充定量数据。

每轮抓取记录：
  - 输入：物体类别、感知特征(尺寸/曲率/质心/13维特征)、YLYW推理链
         (主导卦/卦象/得分/六爻/Top3/爻位质量/谨慎度/策略/力)
  - 决策：接近角、速度档、夹紧值
  - 结果：抓取是否成功、耗时、置信度

输出格式：
  - CSV：扁平化，便于统计(matching率、平均力、卦象分布等)
  - JSON：完整推理链，便于论文画链路图
  - 日志：人类可读
"""

from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .ylyw_grasp_planner import GraspPlan

LOGGER = logging.getLogger(__name__)

CSV_FIELDS = [
    "round", "timestamp", "label", "success",
    "dim_l_mm", "dim_w_mm", "dim_h_mm", "curvature", "volume_cm3",
    "grasp_x_mm", "grasp_y_mm", "grasp_z_mm",
    "pose_name", "pose_rx_deg", "pose_ry_deg", "pose_rz_deg",
    "pose_x_mm", "pose_y_mm", "pose_z_mm", "surface_planarity",
    "approach_axis", "open_axis",
    "dominant_trigram", "hexagram", "hexagram_cn", "hexagram_score",
    "yin_yang", "yao_quality", "caution_level", "strategy_type",
    "force", "approach_angle_deg", "speed_level", "close_value",
    "duration_s",
]


class ExperimentRecorder:
    def __init__(self, record_dir: Path):
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.record_dir / "grasp_experiments.csv"
        self.jsonl_path = self.record_dir / "grasp_reasoning.jsonl"
        self.log_path = self.record_dir / "grasp_console.log"
        self._csv_writer = None
        self.round = 0
        self._init_csv()

    def _init_csv(self) -> None:
        exists = self.csv_path.exists()
        self._csv_file = open(self.csv_path, "a", newline="", encoding="utf-8")
        self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=CSV_FIELDS)
        if not exists:
            self._csv_writer.writeheader()

    def log_result(self, plan: GraspPlan, success: bool, duration_s: float,
                   extra: Optional[Dict[str, Any]] = None) -> None:
        """记录一轮结果到 CSV + JSONL。"""
        self.round += 1
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        grasp = getattr(plan, "grasp_xyz", np.zeros(3))
        try:
            gx, gy, gz = float(grasp[0]) * 1000, float(grasp[1]) * 1000, float(grasp[2]) * 1000
        except Exception:
            gx = gy = gz = 0.0

        meta = getattr(plan, "_geometry", {})   # 由 attach_geometry 写入
        dims = meta.get("dimensions_m")
        curv = meta.get("curvature")
        row = {
            "round": self.round, "timestamp": ts, "label": plan.label,
            "success": int(success),
            "dim_l_mm": dims[0] * 1000 if dims else "",
            "dim_w_mm": dims[1] * 1000 if dims else "",
            "dim_h_mm": dims[2] * 1000 if dims else "",
            "curvature": round(curv, 3) if isinstance(curv, (int, float)) else "",
            "volume_cm3": round(self._vol_cm3(dims), 1) if dims else "",
            "grasp_x_mm": round(gx, 1), "grasp_y_mm": round(gy, 1),
            "grasp_z_mm": round(gz, 1),
            "pose_name": plan.grasp_pose_name,
            "pose_rx_deg": round(plan.grasp_pose_6d[3], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "pose_ry_deg": round(plan.grasp_pose_6d[4], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "pose_rz_deg": round(plan.grasp_pose_6d[5], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "pose_x_mm": round(plan.grasp_pose_6d[0], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "pose_y_mm": round(plan.grasp_pose_6d[1], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "pose_z_mm": round(plan.grasp_pose_6d[2], 1)
            if len(getattr(plan, "grasp_pose_6d", ())) == 6 else "",
            "surface_planarity": round(plan.grasp_surface_planarity, 3)
            if getattr(plan, "grasp_surface_planarity", 0) else "",
            "approach_axis": self._fmt_axis(plan.approach_axis),
            "open_axis": self._fmt_axis(plan.open_axis),
            "dominant_trigram": plan.dominant_trigram,
            "hexagram": plan.hexagram,
            "hexagram_cn": plan.hexagram_cn,
            "hexagram_score": round(plan.hexagram_score, 4),
            "yin_yang": plan.yin_yang,
            "yao_quality": round(plan.yao_quality, 4),
            "caution_level": plan.caution_level,
            "strategy_type": plan.strategy_type,
            "force": round(plan.force, 3),
            "approach_angle_deg": round(plan.approach_angle_deg, 1),
            "speed_level": plan.speed_level,
            "close_value": plan.close_value,
            "duration_s": round(duration_s, 2),
        }
        self._csv_writer.writerow(row)
        self._csv_file.flush()

        jsonl = {
            "round": self.round, "success": success, "duration_s": duration_s,
            "reasoning": plan.reasoning_chain(),
            "perception": {
                k: v for k, v in plan.features.items() if isinstance(v, (int, float))
            },
            "extra": extra or {},
        }
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(jsonl, ensure_ascii=False) + "\n")

        LOGGER.info(
            "【实验#%d】%s %s | 卦=%s(%.3f) 爻=%s 策略=%s 力=%.2f | 成功=%s (%.1fs)",
            self.round, plan.label, "成功" if success else "失败",
            plan.hexagram, plan.hexagram_score, plan.yin_yang,
            plan.strategy_type, plan.force, success, duration_s,
        )

    @staticmethod
    def _fmt_axis(v) -> str:
        try:
            arr = np.asarray(v, dtype=float).reshape(-1)
            if arr.size == 3:
                return "[" + ",".join(f"{x:.2f}" for x in arr) + "]"
        except Exception:
            pass
        return ""

    @staticmethod
    def _vol_cm3(dims) -> float:
        if not dims:
            return 0.0
        return dims[0] * dims[1] * dims[2] * 1e6

    def summary(self) -> Dict[str, Any]:
        """统计汇总(论文用)：成功率、卦象分布等。"""
        if not self.jsonl_path.exists():
            return {}
        rows = []
        with open(self.jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        if not rows:
            return {}
        n = len(rows)
        ok = sum(r["success"] for r in rows)
        from collections import Counter
        hex_dist = Counter(r["reasoning"]["hexagram"] for r in rows)
        type_dist = Counter(r["reasoning"]["strategy_type"] for r in rows)
        return {
            "total_rounds": n,
            "success": ok,
            "success_rate": round(ok / n, 3),
            "hexagram_distribution": dict(hex_dist.most_common()),
            "strategy_distribution": dict(type_dist.most_common()),
            "avg_duration_s": round(sum(r["duration_s"] for r in rows) / n, 2),
        }

    def close(self) -> None:
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


# 便于使用
def attach_geometry(plan: GraspPlan, dims, curvature=None) -> None:
    """附加物体几何(尺寸/曲率)到 plan(供 CSV 记录)。"""
    plan._geometry = {"dimensions_m": dims, "curvature": curvature}
