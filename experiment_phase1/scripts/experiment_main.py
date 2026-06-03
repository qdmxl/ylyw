#!/usr/bin/env python3
"""
YLYW 阶段一实验 — 主控脚本

协调完整闭环: 视觉感知 → YLYW推理 → 灵犀X2执行 → 数据记录

用法:
    python3 experiment_main.py --objects 40 --repeats 3
    python3 experiment_main.py --demo  # 演示模式（录视频）
"""

import sys
import os
import time
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# YLYW 推理引擎（论文现有代码，只读使用）
from ylyw_core.prior_manual import PriorManual

# 仿真物体生成（论文现有代码）
import sys
_path_root = Path(__file__).parent.parent.parent.parent  # /home/lijinhan/MXL/科研/ 即 ylyw 包所在目录
sys.path.insert(0, str(_path_root))
from ylyw.simulation import SimulationScene, OBJECT_TEMPLATES

# 物体类型列表
OBJECT_TYPES = list(OBJECT_TEMPLATES.keys())
FEATURE_NAMES = [
    'stability', 'roll_tendency', 'force_needed', 'fragility',
    'reachability', 'grasp_surface_quality', 'support_area',
    'occlusion', 'obstacle_density', 'task_priority',
    'weight_ratio', 'visibility', 'deformability'
]

# 灵犀X2适配层（ROS2节点，独立进程运行）
# from adapter.ylyw_lingxi_adapter import LingxiX2Adapter


# ============================================================
# 实验配置
# ============================================================
@dataclass
class ExperimentConfig:
    """实验参数配置"""
    # 物体配置
    num_objects: int = 40          # 物体总数
    object_types: List[str] = field(default_factory=lambda: OBJECT_TYPES.copy())
    objects_per_type: int = 5      # 每类物体数量
    
    # 重复实验
    repeats: int = 3               # 每个物体重复次数
    
    # 推理配置
    use_yao_relations: bool = True  # 启用爻位关系运算
    
    # 执行模式
    simulation_mode: bool = True    # True=仿真模式, False=实物模式
    demo_mode: bool = False         # 演示模式（详细日志+录像）
    
    # 输出
    output_dir: str = "data"
    experiment_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))


# ============================================================
# 实验结果数据结构
# ============================================================
@dataclass
class TrialResult:
    """单次实验结果"""
    obj_id: int
    obj_type: str
    trial: int                     # 第几次重复
    
    # 推理输出
    hexagram_name: str
    hexagram_similarity: float
    strategy_type: str
    force_preset: float
    modifier: float                # 爻位修正系数
    S_yao: float                   # 爻位综合评分
    yao_vector: List[float]
    trigram_membership: List[float]
    
    # 性能
    inference_ms: float
    
    # 评估（人工标注或自动）
    strategy_reasonable: Optional[bool] = None
    execution_success: Optional[bool] = None
    strategy_label: str = "neutral"  # reasonable / neutral / error
    
    # 备注
    notes: str = ""


# ============================================================
# 实验管理器
# ============================================================
class ExperimentManager:
    """阶段一实验总控"""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.ylyw = PriorManual()
        self.results: List[TrialResult] = []
        self.start_time = None
        
        # 仿真物体生成器
        self.objects = []  # (id, type, features)
        self._generate_objects()
        
        # 策略合理性规则（人工标注用）
        # 策略合理性规则（按关键词匹配）
        self.reasonable_strategies = {
            "sphere":   ["dynamic", "wrap", "adaptive", "following", "non_conflict", "conditional"],
            "cube":     ["power", "forceful", "wrap", "precise", "direct", "conditional"],
            "cylinder": ["dynamic", "wrap", "power", "following", "adaptive"],
            "bowl":     ["precise", "cautious", "wrap", "conditional", "gentle"],
            "bottle":   ["cautious", "precise", "conditional", "gentle"],
            "plate":    ["precise", "conditional", "gentle"],
            "rock":     ["adaptive", "power", "wrap", "forceful"],
            "vase":     ["cautious", "precise", "gentle", "conditional"],
        }
        self.error_strategies = {
            "sphere":   ["power_grasp", "forceful"],
            "cube":     ["dynamic"],
            "bowl":     ["power_grasp", "forceful", "dynamic"],
            "bottle":   ["power_grasp", "forceful", "dynamic"],
            "plate":    ["power_grasp", "forceful", "dynamic"],
            "vase":     ["power_grasp", "forceful", "dynamic"],
        }
    
    def _generate_objects(self):
        """生成实验物体 — 每类均匀分布"""
        scene = SimulationScene(seed=42)
        per_type = self.config.objects_per_type
        types = self.config.object_types
        
        # 每类物体独立生成，确保均匀分布
        obj_id = 0
        for t in types:
            for _ in range(per_type):
                if obj_id >= self.config.num_objects:
                    break
                objs = scene.generate_scene_with_types([t])
                obj = objs[0]
                fd = obj.features.to_dict()
                features = np.array([
                    fd['stability'], fd['roll_tendency'], fd['strength_needed'],
                    fd['fragility'], fd['reachability'], fd['grasp_surface_quality'],
                    fd['support_area'], fd['occlusion'], fd['obstacle_density'],
                    fd['task_priority'], fd['weight_ratio'], fd['visibility'],
                    fd['deformability']
                ])
                self.objects.append((obj_id, t, features))
                obj_id += 1
    
    def run(self):
        """执行完整实验"""
        self.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"  YLYW Phase 1 Experiment")
        print(f"  Mode: {'SIMULATION' if self.config.simulation_mode else 'PHYSICAL'}")
        print(f"  Objects: {len(self.objects)} ({len(self.config.object_types)} types)")
        print(f"  Repeats: {self.config.repeats}")
        print(f"  Total trials: {len(self.objects) * self.config.repeats}")
        print(f"  Experiment ID: {self.config.experiment_id}")
        print(f"{'='*60}\n")
        
        trial_count = 0
        total_trials = len(self.objects) * self.config.repeats
        
        for obj_id, obj_type, features in self.objects:
            for trial in range(self.config.repeats):
                trial_count += 1
                result = self._run_trial(obj_id, obj_type, features, trial)
                self.results.append(result)
                
                # 进度
                pct = 100 * trial_count / total_trials
                bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
                print(f"\r[{bar}] {trial_count}/{total_trials} "
                      f"| {obj_type:6s} → {result.strategy_type:20s} "
                      f"| force={result.force_preset*result.modifier:.2f} "
                      f"| {result.strategy_label}", end="")
        
        print("\n")
        self._save_results()
        self._print_summary()
    
    def _run_trial(self, obj_id: int, obj_type: str, 
                   features: np.ndarray, trial: int) -> TrialResult:
        """执行单次推理（仿真模式）"""
        
        # 将 numpy 转为 dict（PriorManual 接口要求）
        feature_dict = {
            'stability':        float(features[0]),
            'roll_tendency':    float(features[1]),
            'strength_needed':  float(features[2]),
            'fragility':        float(features[3]),
            'reachability':     float(features[4]),
            'grasp_surface_quality': float(features[5]),
            'support_area':     float(features[6]),
            'occlusion':        float(features[7]),
            'obstacle_density': float(features[8]),
            'task_priority':    float(features[9]),
            'weight_ratio':     float(features[10]),
            'visibility':       float(features[11]),
            'deformability':    float(features[12]),
        }
        
        # === YLYW 推理 ===
        t0 = time.perf_counter()
        perception, strategy = self.ylyw.process(feature_dict)
        t_total = time.perf_counter() - t0
        
        # 提取推理结果
        hexagram_name = perception['best_hexagram'].name if perception['best_hexagram'] else 'unknown'
        similarity = perception['hexagram_match_score']
        strategy_type = strategy['type']
        force_preset = strategy['force']
        modifier = strategy.get('force_modifier', 1.0)
        S_yao = strategy.get('yao_quality', 
                   perception['yao_relations'].score_overall)
        yao_vector = perception['yao_vector']
        trigram_membership = perception['trigram_memberships']
        
        # === 评估策略合理性 ===
        label, is_reasonable = self._evaluate_strategy(obj_type, strategy_type)
        
        # === 构建结果 ===
        return TrialResult(
            obj_id=obj_id,
            obj_type=obj_type,
            trial=trial,
            hexagram_name=hexagram_name,
            hexagram_similarity=float(similarity),
            strategy_type=strategy_type,
            force_preset=float(force_preset),
            modifier=float(modifier),
            S_yao=float(S_yao),
            yao_vector=yao_vector.tolist() if hasattr(yao_vector, 'tolist') else list(yao_vector),
            trigram_membership=trigram_membership.tolist() if hasattr(trigram_membership, 'tolist') else list(trigram_membership),
            inference_ms=t_total * 1000,
            strategy_reasonable=is_reasonable,
            execution_success=True if self.config.simulation_mode else None,
            strategy_label=label,
        )
    
    def _evaluate_strategy(self, obj_type: str, strategy: str) -> tuple:
        """评估策略合理性（关键词匹配）"""
        reasonable = self.reasonable_strategies.get(obj_type, [])
        errors = self.error_strategies.get(obj_type, [])
        
        if any(e in strategy for e in errors):
            return "error", False
        elif any(r in strategy for r in reasonable):
            return "reasonable", True
        else:
            return "neutral", None
    
    def _save_results(self):
        """保存实验结果"""
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        results_dict = {
            "experiment_id": self.config.experiment_id,
            "timestamp": self.start_time,
            "config": {
                "num_objects": self.config.num_objects,
                "repeats": self.config.repeats,
                "simulation_mode": self.config.simulation_mode,
                "use_yao_relations": self.config.use_yao_relations,
            },
            "results": [
                {
                    "obj_id": r.obj_id,
                    "obj_type": r.obj_type,
                    "trial": r.trial,
                    "hexagram_name": r.hexagram_name,
                    "hexagram_similarity": r.hexagram_similarity,
                    "strategy_type": r.strategy_type,
                    "force_preset": r.force_preset,
                    "modifier": r.modifier,
                    "S_yao": r.S_yao,
                    "yao_vector": r.yao_vector,
                    "trigram_membership": r.trigram_membership,
                    "inference_ms": r.inference_ms,
                    "strategy_label": r.strategy_label,
                    "strategy_reasonable": r.strategy_reasonable,
                }
                for r in self.results
            ]
        }
        
        path = Path(self.config.output_dir) / f"experiment_{self.config.experiment_id}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"Results saved to {path}")
    
    def _print_summary(self):
        """打印实验汇总"""
        total = len(self.results)
        reasonable = sum(1 for r in self.results if r.strategy_reasonable == True)
        errors = sum(1 for r in self.results if r.strategy_label == "error")
        neutral = sum(1 for r in self.results if r.strategy_label == "neutral")
        
        strategies = {}
        for r in self.results:
            s = r.strategy_type
            strategies[s] = strategies.get(s, 0) + 1
        
        avg_infer = np.mean([r.inference_ms for r in self.results])
        avg_similarity = np.mean([r.hexagram_similarity for r in self.results])
        avg_S_yao = np.mean([r.S_yao for r in self.results])
        
        print(f"\n{'='*60}")
        print(f"  EXPERIMENT SUMMARY")
        print(f"{'='*60}")
        print(f"  Total trials:      {total}")
        print(f"  Reasonable:        {reasonable} ({100*reasonable/total:.1f}%)")
        print(f"  Neutral:           {neutral} ({100*neutral/total:.1f}%)")
        print(f"  Errors:            {errors} ({100*errors/total:.1f}%)")
        print(f"  Avg inference:     {avg_infer:.2f} ms")
        print(f"  Avg similarity:    {avg_similarity:.4f}")
        print(f"  Avg S_yao:         {avg_S_yao:.4f}")
        print(f"")
        print(f"  Strategy distribution:")
        for s, c in sorted(strategies.items(), key=lambda x: -x[1]):
            bar = "█" * (c * 50 // max(strategies.values()))
            print(f"    {s:25s} {bar} {c}")
        print(f"{'='*60}\n")
        
        # 按物体类型统计
        print(f"  Per-type reasonable rate:")
        for t in self.config.object_types:
            t_results = [r for r in self.results if r.obj_type == t]
            if not t_results:
                continue
            t_ok = sum(1 for r in t_results if r.strategy_reasonable == True)
            t_err = sum(1 for r in t_results if r.strategy_label == "error")
            print(f"    {t:6s}: {100*t_ok/len(t_results):5.1f}% reasonable, "
                  f"{t_err} errors ({len(t_results)} trials)")


# ============================================================
# 演示模式（用于录制视频素材）
# ============================================================
def demo_mode():
    """演示模式：逐一展示物体的推理过程和策略输出"""
    config = ExperimentConfig(
        num_objects=8,   # 每类1个
        objects_per_type=1,
        repeats=1,
        demo_mode=True,
    )
    mgr = ExperimentManager(config)
    ylyw = mgr.ylyw
    
    print("\n" + "="*60)
    print("  YLYW DEMO MODE — One object per type")
    print("="*60)
    
    trigram_names = ['乾☰', '坤☷', '震☳', '艮☶', '离☲', '坎☵', '兑☱', '巽☴']
    yao_names = ['初爻(稳)', '二爻(达)', '三爻(力)', '四爻(脆)', '五爻(优)', '上爻(环)']
    
    for obj_id, obj_type, features in mgr.objects:
        print(f"\n{'─'*60}")
        print(f"  Object #{obj_id}: {obj_type}")
        print(f"{'─'*60}")
        
        # 13维特征
        print(f"  13D Features:")
        for i, (name, val) in enumerate(zip(FEATURE_NAMES, features)):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"    {name:25s} [{bar}] {val:.3f}")
        
        # YLYW 推理
        feature_dict = {
            'stability': float(features[0]),
            'roll_tendency': float(features[1]),
            'strength_needed': float(features[2]),
            'fragility': float(features[3]),
            'reachability': float(features[4]),
            'grasp_surface_quality': float(features[5]),
            'support_area': float(features[6]),
            'occlusion': float(features[7]),
            'obstacle_density': float(features[8]),
            'task_priority': float(features[9]),
            'weight_ratio': float(features[10]),
            'visibility': float(features[11]),
            'deformability': float(features[12]),
        }
        perception, strategy = ylyw.process(feature_dict)
        
        # L1: 八卦隶属度
        print(f"\n  L1 Bagua Membership:")
        for name, val in zip(trigram_names, perception['trigram_memberships']):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            print(f"    {name:6s} [{bar}] {val:.3f}")
        
        # L2: 六爻
        yao_vec = perception['yao_vector']
        yao_bin = ''.join('—' if v >= 0.5 else '--' for v in yao_vec)
        print(f"\n  L2 Yao Vector: {yao_bin}")
        for name, val in zip(yao_names, yao_vec):
            bar = "█" * int(val * 20) + "░" * (20 - int(val * 20))
            yin_yang = '— 阳' if val >= 0.5 else '-- 阴'
            print(f"    {name:8s} [{bar}] {val:.3f} {yin_yang}")
        
        # L3: 卦象匹配
        top3 = perception['top_k_hexagrams']
        print(f"\n  L3 Hexagram Match:")
        for i, (h, s) in enumerate(top3, 1):
            print(f"    Top-{i}: {h.name} (similarity={s:.4f})")
        
        # 策略
        print(f"\n  Decision Output:")
        print(f"    Strategy:     {strategy['type']}")
        print(f"    Force Preset: {strategy['force']:.2f}")
        print(f"    Speed:        {strategy.get('speed', 'medium')}")
        print(f"    Precautions:  {', '.join(strategy.get('cautions', []))}")
        
        # L3+: 爻位关系
        yao_r = perception['yao_relations']
        print(f"\n  L3+ Yao Relations:")
        print(f"    S_yao:        {yao_r.score_overall:.2f}")
        print(f"    Modifier:     ×{yao_r.strategy_modifier:.2f}")
        print(f"    Caution:      {yao_r.caution_level}")
        
        input("\n  Press Enter for next object...")


# ============================================================
# main
# ============================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YLYW Phase 1 Experiment')
    parser.add_argument('--objects', type=int, default=40, help='Number of objects')
    parser.add_argument('--repeats', type=int, default=3, help='Repeats per object')
    parser.add_argument('--no-yao', action='store_true', help='Disable yao relations')
    parser.add_argument('--demo', action='store_true', help='Demo mode')
    parser.add_argument('--output', type=str, default='data', help='Output directory')
    args = parser.parse_args()
    
    if args.demo:
        demo_mode()
    else:
        config = ExperimentConfig(
            num_objects=args.objects,
            repeats=args.repeats,
            use_yao_relations=not args.no_yao,
            output_dir=args.output,
        )
        mgr = ExperimentManager(config)
        mgr.run()
