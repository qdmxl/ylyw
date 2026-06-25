"""
知几学习闭环 (Zhiji Learning Loop) — 自省+精进模块

YLYW书法学习的核心创新：观帖→临摹→对比→修正→再写→越来越好

这个模块实现了：
1. 差异追踪：字帖卦象 vs 书写结果卦象
2. 知几诊断：精确定位哪个爻位/哪个层出了问题
3. 定向参数修正：只修改问题参数，不全部打乱
4. 经验积累：修正后的参数迁移到新字
5. 学习曲线：记录每次迭代的改善

与强化学习的根本区别：
    RL: 随机探索 → 获得奖励 → 大量试错 → 偶然变好
    YLYW: 先验推理 → 对比诊断 → 精确定位 → 定向修正 → 系统性变好

诊断能力（人类书法家级别）：
    "这一横太细" → 二爻(粗细)偏差 → 降低压力阈值
    "重心偏左"   → 五爻(重心x)偏差 → 调整x偏移
    "整体太柔弱" → 主导卦象错误 → 重新评估隶属度
"""

import numpy as np
import cv2
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict

# 导入YLYW书法模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from visual_calligraphy import (
    CalligraphyVisualYLYW, CalligraphyPerception
)
from stroke_ylyw import (
    CalligraphyStrokeYLYW, CharacterPlan, StrokePlan,
    TRIGRAM_TO_BRUSH, BrushMethod
)
from mujoco_env import CalligraphyEnv


# ============================================================
# 诊断系统：爻位→修正规则
# ============================================================

@dataclass
class ZhijiDiagnosis:
    """知几诊断报告"""
    iteration: int
    character: str

    # 卦象差异
    same_trigram: bool
    same_hexagram: bool
    target_trigram: str
    actual_trigram: str
    trigram_shift: str          # 卦象迁移描述

    # 爻级差异
    yao_diff: np.ndarray        # 六爻差异向量
    max_diff_yao: str           # 最大偏差爻位
    max_diff_val: float         # 最大偏差值

    # 总体评估
    total_distance: float       # 总卦象距离
    improvement: Optional[float]  # 相比上次的改善量
    grade: str                  # 评级：优/良/中/差

    # 修正建议
    parameter_fixes: List[Dict]  # 需要修正的参数


class ZhijiDiagnosisEngine:
    """
    知几诊断引擎

    核心能力：
    - 解释"为什么写得不像"（可追溯到具体爻位）
    - 给出"应该怎么改"（定向参数修正）
    - 评估"改了多少"（量化进步）

    这是与DL方法最根本的差异：
    DL只能给"loss=0.37"，YLYW能给"三爻(曲直)偏差0.23，建议增强笔画曲率"
    """

    # 爻位语义映射（书法域）
    YAO_NAMES = [
        '初爻(笔画方向)', '二爻(粗细对比)', '三爻(曲直复杂度)',
        '四爻(间架规整)', '五爻(重心横向)', '上爻(重心纵向)'
    ]

    # 爻位偏差→具体的执行修正
    YAO_FIX_RULES = {
        0: {  # 初爻：笔画方向
            'param': 'speed_consistency',
            'direction': 'increase_if_positive',
            'description': '方向主导度偏差。阳偏→笔画方向太统一(僵硬)；阴偏→方向太散(杂乱)',
        },
        1: {  # 二爻：粗细对比
            'param': 'press_amplitude',
            'direction': 'increase_if_positive',
            'description': '粗细对比偏差。阳偏→笔画太粗；阴偏→笔画太细',
        },
        2: {  # 三爻：曲直复杂度
            'param': 'curvature_factor',
            'direction': 'increase_if_positive',
            'description': '曲直偏差。阳偏→太直(缺乏曲线)；阴偏→太弯(缺乏骨力)',
        },
        3: {  # 四爻：间架规整
            'param': 'position_precision',
            'direction': 'increase_if_positive',
            'description': '间架偏差。阳偏→太规整(死板)；阴偏→太松散',
        },
        4: {  # 五爻：重心横向
            'param': 'x_offset',
            'direction': 'decrease_if_positive',  # 反向修正
            'description': '重心横向偏移。阳偏→重心偏右；阴偏→重心偏左',
        },
        5: {  # 上爻：重心纵向
            'param': 'y_offset',
            'direction': 'decrease_if_positive',  # 反向修正
            'description': '重心纵向偏移。阳偏→重心偏下；阴偏→重心偏上',
        },
    }

    def diagnose(self, iteration: int, character: str,
                 target_perception: CalligraphyPerception,
                 actual_perception: CalligraphyPerception,
                 prev_compare: Optional[Dict] = None) -> ZhijiDiagnosis:
        """
        生成诊断报告

        Args:
            iteration: 当前迭代次数
            character: 汉字
            target_perception: 字帖的感知结果
            actual_perception: 书写结果的感知结果
            prev_compare: 上一次的对比结果（用于计算improvement）

        Returns:
            ZhijiDiagnosis
        """
        from visual_calligraphy import CalligraphyVisualYLYW
        visual = CalligraphyVisualYLYW()
        compare = visual.compare(target_perception, actual_perception)

        yao_diff = compare['yao_diff']
        total_distance = compare['total_yao_distance']

        # 定位最大偏差爻
        max_idx = np.argmax(np.abs(yao_diff))
        max_val = float(yao_diff[max_idx])

        # 卦象迁移
        if compare['same_trigram']:
            trigram_shift = f"卦象一致[{target_perception.dominant_trigram}]，爻级微调即可"
        else:
            trigram_shift = (f"卦象迁移：{target_perception.dominant_trigram}→"
                           f"{actual_perception.dominant_trigram}，需调整主导笔法")

        # 计算改善
        improvement = None
        if prev_compare is not None:
            improvement = float(prev_compare['total_yao_distance'] - total_distance)

        # 评级
        if total_distance < 0.05:
            grade = '优'
        elif total_distance < 0.15:
            grade = '良'
        elif total_distance < 0.5:
            grade = '中'
        else:
            grade = '差'

        # 生成参数修正建议
        parameter_fixes = []
        for idx in range(6):
            diff = float(yao_diff[idx])
            if abs(diff) > 0.05:  # 有显著偏差
                rule = self.YAO_FIX_RULES[idx]
                fix_magnitude = abs(diff) * 0.5  # 修正幅度（不宜过大，防震荡）

                if rule['direction'] == 'increase_if_positive':
                    fix_direction = 'increase' if diff > 0 else 'decrease'
                elif rule['direction'] == 'decrease_if_positive':
                    fix_direction = 'decrease' if diff > 0 else 'increase'
                else:
                    fix_direction = 'adjust'

                parameter_fixes.append({
                    'yao_index': idx,
                    'yao_name': self.YAO_NAMES[idx],
                    'param': rule['param'],
                    'current_deviation': diff,
                    'fix_direction': fix_direction,
                    'fix_magnitude': fix_magnitude,
                    'description': rule['description'],
                })

        return ZhijiDiagnosis(
            iteration=iteration,
            character=character,
            same_trigram=compare['same_trigram'],
            same_hexagram=compare['same_hexagram'],
            target_trigram=target_perception.dominant_trigram,
            actual_trigram=actual_perception.dominant_trigram,
            trigram_shift=trigram_shift,
            yao_diff=yao_diff,
            max_diff_yao=self.YAO_NAMES[max_idx],
            max_diff_val=max_val,
            total_distance=total_distance,
            improvement=improvement,
            grade=grade,
            parameter_fixes=parameter_fixes,
        )


# ============================================================
# 知几学习闭环
# ============================================================

@dataclass
class IterationRecord:
    """一次迭代的完整记录"""
    iteration: int
    character: str
    perception: CalligraphyPerception      # 感知结果
    plan: CharacterPlan                     # 书写计划
    result_image: np.ndarray                # 书写结果图像
    actual_perception: CalligraphyPerception # 书写结果的感知
    diagnosis: ZhijiDiagnosis              # 诊断报告
    calligraphy_params: Dict[str, float]   # 书写参数快照
    yao_features: np.ndarray               # 六爻特征快照


@dataclass
class CharacterLearningHistory:
    """单个汉字的学习历史"""
    character: str
    iterations: List[IterationRecord] = field(default_factory=list)
    distance_curve: List[float] = field(default_factory=list)
    improvement_curve: List[float] = field(default_factory=list)


class ZhijiLearningLoop:
    """
    知几学习闭环

    这是YLYW书法系统的"大脑"——
    协调视觉分析、书写执行和参数修正，实现闭环学习。

    核心流程：
        1. 分析字帖 → 得到目标卦象
        2. 生成书写计划 → 执行书写
        3. 分析书写结果 → 得到实际卦象
        4. 诊断差异 → 精确定位问题
        5. 修正参数 → 更新书写策略
        6. 重写 → 迭代改进
    """

    def __init__(self, output_dir: str = None):
        self.visual_ylyw = CalligraphyVisualYLYW()
        self.stroke_ylyw = CalligraphyStrokeYLYW()
        self.diagnosis_engine = ZhijiDiagnosisEngine()
        self.env = CalligraphyEnv(render_mode='offscreen')

        # 输出目录
        if output_dir is None:
            output_dir = str(Path(__file__).parent / 'output')
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 学习状态
        self.histories: Dict[str, CharacterLearningHistory] = {}
        self.global_parameter_memory: Dict[str, float] = {}  # 跨字迁移的参数记忆

    def run_learning_loop(self, character: str,
                           target_image: np.ndarray,
                           max_iterations: int = 5,
                           verbose: bool = True) -> CharacterLearningHistory:
        """
        对单个汉字运行完整的学习闭环

        Args:
            character: 汉字
            target_image: 字帖图像（灰度图）
            max_iterations: 最大迭代次数
            verbose: 是否打印详细信息

        Returns:
            CharacterLearningHistory
        """
        history = CharacterLearningHistory(character=character)

        # Step 1: 分析字帖（只做一次）
        if verbose:
            print(f"\n{'='*60}")
            print(f"  YLYW知几书法学习 — 「{character}」")
            print(f"  最大迭代: {max_iterations}")
            print(f"{'='*60}")

        target_perception = self.visual_ylyw.perceive(target_image)
        if verbose:
            print(f"\n📖 字帖分析: 卦象={target_perception.hexagram_name} "
                  f"(#{target_perception.hexagram_number}), "
                  f"主导={target_perception.dominant_trigram} "
                  f"({target_perception.trigram_desc})")

        # 初始化书写参数
        current_params = {
            'stroke_angle_correction': 0.0,
            'stroke_width_factor': 1.0,
            'stroke_curve_factor': 0.0,
            'jitter_amplitude': 0.0,
        }

        prev_score = None
        prev_compare = None

        # 导入新轨迹生成器
        from trajectory_gen import generate_trajectory as gen_traj
        from eval_skeleton import evaluate_similarity

        for iteration in range(max_iterations):
            if verbose:
                print(f"\n--- 第 {iteration+1}/{max_iterations} 次书写 ---")

            # Step 2: 从字帖生成轨迹（带扰动）
            traj, press = gen_traj(character)
            
            # 应用参数扰动到轨迹
            if iteration > 0:
                perturb = current_params.get('jitter_amplitude', 0)
                if perturb > 0:
                    traj = traj + np.random.randn(*traj.shape) * perturb * 0.003
                # 角度修正
                angle = current_params.get('stroke_angle_correction', 0)
                if abs(angle) > 0.001:
                    c, s = np.cos(angle), np.sin(angle)
                    cx, cy = traj[:,0].mean(), traj[:,1].mean()
                    dx, dy = traj[:,0]-cx, traj[:,1]-cy
                    traj[:,0] = cx + dx*c - dy*s
                    traj[:,1] = cy + dx*s + dy*c

            # Step 3: 执行书写
            result = self.env.execute_trajectory(traj, press)
            result_image = result.rendered_image

            # 保存
            cv2.imwrite(
                str(self.output_dir / f'{character}_iter{iteration+1}.png'),
                result_image
            )

            # Step 4: 骨架相似度评价
            eval_result = evaluate_similarity(target_image, result_image, verbose=False)
            score = eval_result.score
            overlap = eval_result.overlap
            chamfer = eval_result.chamfer

            # Step 5: 诊断（保留爻位分析用于可解释性）
            actual_perception = self.visual_ylyw.perceive(result_image)

            # Step 5: 诊断
            diagnosis = self.diagnosis_engine.diagnose(
                iteration=iteration,
                character=character,
                target_perception=target_perception,
                actual_perception=actual_perception,
                prev_compare=prev_compare,
            )
            # 用骨架分数覆盖卦象距离
            diagnosis.total_distance = 1.0 - score

            improvement = None
            if prev_score is not None:
                improvement = float(score - prev_score)

            if verbose:
                print(f"  骨架分: {score:.3f} (overlap={overlap:.3f}, chamfer={chamfer:.1f})", end="")
                if improvement is not None:
                    arrow = '↑' if improvement > 0 else '↓'
                    print(f" {arrow}{abs(improvement):.3f}", end="")
                print()
                print(f"  爻位诊断: {diagnosis.max_diff_yao}偏差{diagnosis.max_diff_val:+.3f}")

            # 记录迭代
            record = IterationRecord(
                iteration=iteration,
                character=character,
                perception=target_perception,
                plan=None,
                result_image=result_image,
                actual_perception=actual_perception,
                diagnosis=diagnosis,
                calligraphy_params=dict(current_params),
                yao_features=target_perception.yao_features.copy(),
            )
            history.iterations.append(record)
            history.distance_curve.append(1.0 - score)
            if improvement is not None:
                history.improvement_curve.append(improvement)

            prev_score = score
            prev_compare = {'total_yao_distance': 1.0 - score}

            # Step 6: 修正参数
            # 用骨架分为收敛目标
            if iteration > 0 and improvement is not None and improvement < 0.005:
                if verbose:
                    print(f"\n  ⚠️ 骨架分已收敛，停止迭代。")
                break

            self._apply_parameter_fixes(
                current_params,
                target_perception.yao_features,
                actual_perception.yao_features
            )

        # 保存历史记录
        self.histories[character] = history

        if verbose:
            self._print_learning_summary(history)

        return history

    def _params_to_yao(self, params: Dict[str, float]) -> np.ndarray:
        """从参数重建六爻特征向量"""
        return np.array([
            params['speed_consistency'],
            params['press_amplitude'],
            params['curvature_factor'],
            params['position_precision'],
            params.get('x_offset', 0.0) + 0.5,  # 反归一化
            params.get('y_offset', 0.0) + 0.5,
        ], dtype=np.float32)

    def _apply_parameter_fixes(self, params: Dict[str, float],
                                target_yao: np.ndarray,
                                actual_yao: np.ndarray) -> None:
        """
        应用参数修正——基于爻位差异修正书写参数。
        
        核心创新：修正不仅改变速度/压力这类"感觉"参数，
        更关键的是改变**轨迹几何修正参数**，从而直接改变笔画形状。
        
        几何修正：
        - 初爻(方向): stroke_angle_correction (调整笔画角度)
        - 二爻(粗细): stroke_width_factor (笔画宽度比例)
        - 三爻(曲直): stroke_curve_factor (弧线曲率)
        - 四爻(规整): jitter_amplitude (抖动幅度)
        - 五爻/上爻(重心): x_offset/y_offset (整体位移)
        """
        lr = 0.5  # 学习率
        
        diff = target_yao - actual_yao  # 正=需要增加, 负=需要减少
        
        # 初爻：方向修正
        current_angle_corr = params.get('stroke_angle_correction', 0.0)
        params['stroke_angle_correction'] = np.clip(
            current_angle_corr + diff[0] * lr * 0.3, -0.3, 0.3)
        
        # 二爻：笔画宽度
        current_width = params.get('stroke_width_factor', 1.0)
        params['stroke_width_factor'] = np.clip(
            current_width + diff[1] * lr * 0.5, 0.5, 2.0)
        
        # 三爻：曲率
        current_curve = params.get('stroke_curve_factor', 1.0)
        params['stroke_curve_factor'] = np.clip(
            current_curve + diff[2] * lr * 0.5, 0.3, 2.5)
        
        # 四爻：抖动
        current_jitter = params.get('jitter_amplitude', 0.002)
        params['jitter_amplitude'] = np.clip(
            current_jitter - diff[3] * lr * 0.003, 0.0, 0.015)
        
        # 五爻/上爻：重心（如果存在offset参数才修正）
        if 'x_offset' in params:
            params['x_offset'] = np.clip(
                params['x_offset'] - diff[4] * lr * 0.15, -0.15, 0.15)
        if 'y_offset' in params:
            params['y_offset'] = np.clip(
                params['y_offset'] - diff[5] * lr * 0.15, -0.15, 0.15)
        
        # 同步更新六爻参数（如果存在才修正）
        for key in ['speed_consistency', 'press_amplitude', 'curvature_factor', 'position_precision']:
            if key in params:
                idx = {'speed_consistency': 0, 'press_amplitude': 1, 'curvature_factor': 2, 'position_precision': 3}[key]
                params[key] = np.clip(params[key] + diff[idx] * lr, 0.05, 0.95)

    def _print_diagnosis(self, diagnosis: ZhijiDiagnosis) -> None:
        """打印诊断报告"""
        print(f"  📊 评级: {diagnosis.grade} | "
              f"卦象: {diagnosis.target_trigram}→{diagnosis.actual_trigram} | "
              f"总距离: {diagnosis.total_distance:.3f}", end="")
        if diagnosis.improvement is not None:
            sign = '↓' if diagnosis.improvement > 0 else '↑'
            print(f" ({sign}{abs(diagnosis.improvement):.3f})", end="")
        print()

        print(f"  🔍 最大偏差: {diagnosis.max_diff_yao} ({diagnosis.max_diff_val:+.3f})")
        print(f"  📝 卦象迁移: {diagnosis.trigram_shift}")

        # 六爻偏差详情
        yao_names = ZhijiDiagnosisEngine.YAO_NAMES
        yao_str = ', '.join(f'{yao_names[i]}:{diagnosis.yao_diff[i]:+.3f}' for i in range(6))
        print(f"  📐 六爻偏差: [{yao_str}]")

        if diagnosis.parameter_fixes:
            print(f"  🔧 修正建议 ({len(diagnosis.parameter_fixes)}项):")
            for fix in diagnosis.parameter_fixes[:3]:
                direction = '↑' if fix['fix_direction'] == 'increase' else '↓'
                print(f"    - {fix['yao_name']}: {fix['param']} {direction}{fix['fix_magnitude']:.3f}")
                print(f"      {fix['description']}")

    def _print_learning_summary(self, history: CharacterLearningHistory) -> None:
        """打印学习总结"""
        print(f"\n{'='*60}")
        print(f"  「{history.character}」学习总结")
        print(f"{'='*60}")

        n = len(history.iterations)
        if n == 0:
            print("  无有效迭代")
            return

        first_d = history.distance_curve[0]
        last_d = history.distance_curve[-1]
        total_improvement = first_d - last_d
        # 用骨架分显示
        first_score = 1.0 - first_d
        last_score = 1.0 - last_d

        print(f"  总迭代: {n}")
        print(f"  初始骨架分: {first_score:.3f}")
        print(f"  最终骨架分: {last_score:.3f}")
        print(f"  总改善: {total_improvement:+.3f} (距离)")
        print(f"  骨架分变化: {first_score:.3f} → {last_score:.3f}")
        print(f"  学习曲线: {', '.join(f'{1.0-d:.3f}' for d in history.distance_curve)}")

    def generate_learning_report(self) -> str:
        """生成学习报告（Markdown格式）"""
        lines = []
        lines.append("# YLYW知几书法学习报告")
        lines.append("")
        lines.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        for char, history in self.histories.items():
            lines.append(f"## 「{char}」字")
            lines.append("")
            lines.append("| 迭代 | 评级 | 卦象距离 | 主导卦象 | 最大偏差爻 | 修正数 |")
            lines.append("|------|------|---------|---------|-----------|--------|")

            for rec in history.iterations:
                d = rec.diagnosis
                imp_str = ""
                if d.improvement is not None:
                    imp_str = f" ({d.improvement:+.3f})"
                lines.append(
                    f"| {d.iteration+1} | {d.grade} | "
                    f"{d.total_distance:.3f}{imp_str} | "
                    f"{d.target_trigram} | "
                    f"{d.max_diff_yao}({d.max_diff_val:+.3f}) | "
                    f"{len(d.parameter_fixes)} |"
                )
            lines.append("")

            if history.distance_curve:
                sc = ", ".join(f"{v:.3f}" for v in history.distance_curve)
                lines.append(f"**学习曲线**: [{sc}]")
                lines.append("")

        return "\n".join(lines)


# ============================================================
# 测试：完整学习闭环
# ============================================================

def test_learning_loop():
    """测试完整的知几学习闭环"""
    print("=" * 60)
    print("YLYW知几书法学习闭环测试")
    print("=" * 60)

    loop = ZhijiLearningLoop(output_dir=str(Path(__file__).parent / 'output'))

    # 加载楷体字帖
    target_image = load_copybook('大')
    cv2.imwrite(str(loop.output_dir / 'target_大.png'), target_image)

    # 运行学习闭环
    history = loop.run_learning_loop(
        character='大',
        target_image=target_image,
        max_iterations=5,
        verbose=True,
    )

    # 生成报告
    report = loop.generate_learning_report()
    report_path = loop.output_dir / 'learning_report.md'
    report_path.write_text(report)
    print(f"\n📄 学习报告已保存: {report_path}")

    return loop, history


def load_copybook(character: str, image_size: int = 256) -> np.ndarray:
    """加载字帖图像：优先楷体渲染，回退程序生成"""
    import cv2
    copybook_path = Path(__file__).parent / 'input' / 'copybook' / f'{character}_楷体.png'
    if copybook_path.exists():
        img = cv2.imread(str(copybook_path), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img
    # 回退
    return _generate_target_calligraphy(character, image_size)


def _generate_target_calligraphy(character: str,
                                  image_size: int = 256) -> np.ndarray:
    """
    生成目标字帖图像。

    使用预定义模板，生成理想化的"字帖"效果。
    这在真实场景中会被真字帖照片替代。
    """
    canvas = np.ones((image_size, image_size), dtype=np.float32) * 255
    margin = 40

    if character == '大':
        sz = image_size
        # 横（标准楷书体）
        cv2.line(canvas, (margin+30, sz//3), (sz-margin-30, sz//3), 20, 3)
        # 左撇
        cv2.line(canvas, (sz//2-5, sz//3), (margin+20, sz-margin-25), 25, 2)
        # 右捺
        cv2.line(canvas, (sz//2+5, sz//3+5), (sz-margin-20, sz-margin-25), 30, 2)

    elif character == '人':
        sz = image_size
        cv2.line(canvas, (sz//2-3, margin+15), (margin+25, sz-margin-20), 28, 2)
        cv2.line(canvas, (sz//2+3, margin+15), (sz-margin-25, sz-margin-20), 32, 2)

    elif character == '中':
        sz = image_size
        cv2.line(canvas, (margin+25, sz//4), (sz-margin-25, sz//4), 22, 3)
        cv2.line(canvas, (sz//2, sz//4-5), (sz//2, sz*3//4+5), 18, 2)
        cv2.line(canvas, (margin+25, sz*3//4), (sz-margin-25, sz*3//4), 22, 3)

    elif character == '永':
        sz = image_size
        # 点
        cv2.circle(canvas, (sz//2, margin+18), 12, 15, -1)
        # 横
        cv2.line(canvas, (margin+30, sz//3+8), (sz-margin-20, sz//3+8), 20, 3)
        # 竖
        cv2.line(canvas, (sz//2, sz//3+8), (sz//2, sz-margin-25), 16, 2)
        # 钩
        cv2.line(canvas, (sz//2, sz-margin-25), (sz//2+22, sz-margin-6), 16, 2)
        # 左撇
        cv2.line(canvas, (sz//2-3, sz//2+8), (margin+20, margin+15), 22, 2)
        # 右撇
        cv2.line(canvas, (sz//2+3, sz//2+12), (sz-margin-30, sz//3+15), 18, 2)
        # 捺
        cv2.line(canvas, (sz//2+3, sz//2+12), (sz-margin-18, sz-margin-25), 30, 2)

    elif character == '心':
        sz = image_size
        # 左点
        cv2.circle(canvas, (margin+30, sz//2+10), 10, 15, -1)
        # 卧钩
        for t in np.linspace(0, 1, 100):
            x = margin+45 + (sz-margin-20-margin-45)*t
            y = sz//2+10 + 40*np.sin(t*np.pi) - 20*t
            cv2.circle(canvas, (int(x), int(y)), 6, 20, -1)
        # 中点
        cv2.circle(canvas, (sz//2, sz//2-20), 9, 15, -1)
        # 右点
        cv2.circle(canvas, (sz-margin-30, sz//2-28), 9, 15, -1)

    return canvas.astype(np.uint8)


if __name__ == '__main__':
    loop, history = test_learning_loop()
