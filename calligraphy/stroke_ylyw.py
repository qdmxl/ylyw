"""
书写YLYW (Stroke YLYW) — 临摹模块

将结构卦象转换为机械臂书写策略。
这是"以卦驭笔"的核心——从卦象到笔法再到轨迹。

架构：
- 八卦→笔法映射（每个卦对应笔法原语）
- 六爻→书写参数（速度/压力/提按节奏）
- 笔画轨迹生成（基于笔法+参数）
- 六十四卦→汉字结构模板（整体布局策略）

参考："永字八法"——侧、勒、弩、趯、策、掠、啄、磔
每法对应不同卦象的力道/方向/节奏特征。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Callable
from enum import Enum


# ============================================================
# 笔法类型（对应八卦）
# ============================================================

class BrushMethod(Enum):
    """八种基本笔法，各对应一卦"""
    CENTER_TIP = 'center_tip'         # 乾 中锋直下——力道均勻，笔尖在笔画中心
    SIDE_TIP = 'side_tip'             # 坤 侧锋铺毫——笔锋侧卧，柔和铺展
    LIFT_PRESS = 'lift_press'         # 震 提按变化——轻重快速交替
    PAUSE_HOLD = 'pause_hold'         # 艮 顿笔驻留——停留蓄力
    EXPOSE_TIP = 'expose_tip'         # 离 露锋出尖——笔锋外露
    HIDE_TIP = 'hide_tip'             # 坎 藏锋回锋——笔锋内敛
    LIGHT_SKIP = 'light_skip'         # 兑 轻灵跳跃——轻快短促
    DENSE_CURVE = 'dense_curve'       # 巽 绵密弧转——细长柔韧


# 八卦→笔法映射
TRIGRAM_TO_BRUSH = {
    '乾': BrushMethod.CENTER_TIP,
    '坤': BrushMethod.SIDE_TIP,
    '震': BrushMethod.LIFT_PRESS,
    '艮': BrushMethod.PAUSE_HOLD,
    '离': BrushMethod.EXPOSE_TIP,
    '坎': BrushMethod.HIDE_TIP,
    '兑': BrushMethod.LIGHT_SKIP,
    '巽': BrushMethod.DENSE_CURVE,
}

# 笔法的执行参数
BRUSH_PARAMS = {
    BrushMethod.CENTER_TIP: {
        'pressure_base': 0.7,
        'pressure_variation': 0.05,
        'speed': 0.3,           # 慢而稳
        'tip_tilt': 0.0,        # 笔尖垂直
    },
    BrushMethod.SIDE_TIP: {
        'pressure_base': 0.4,
        'pressure_variation': 0.05,
        'speed': 0.5,
        'tip_tilt': 0.3,
    },
    BrushMethod.LIFT_PRESS: {
        'pressure_base': 0.6,
        'pressure_variation': 0.35,
        'speed': 0.6,
        'tip_tilt': 0.1,
    },
    BrushMethod.PAUSE_HOLD: {
        'pressure_base': 0.9,
        'pressure_variation': 0.05,
        'speed': 0.05,
        'tip_tilt': 0.0,
    },
    BrushMethod.EXPOSE_TIP: {
        'pressure_base': 0.3,
        'pressure_variation': 0.1,
        'speed': 0.8,
        'tip_tilt': 0.15,
    },
    BrushMethod.HIDE_TIP: {
        'pressure_base': 0.5,
        'pressure_variation': 0.1,
        'speed': 0.4,
        'tip_tilt': 0.0,
    },
    BrushMethod.LIGHT_SKIP: {
        'pressure_base': 0.2,
        'pressure_variation': 0.1,
        'speed': 0.9,
        'tip_tilt': 0.1,
    },
    BrushMethod.DENSE_CURVE: {
        'pressure_base': 0.45,
        'pressure_variation': 0.05,
        'speed': 0.35,
        'tip_tilt': 0.2,
    },
}


# ============================================================
# 六爻 → 书写参数
# ============================================================

class YaoToCalligraphyParams:
    """
    将六爻值映射为书写参数

    六爻书写语义：
        初爻(方向主导度) → 笔画方向集中度 → 速度一致性
        二爻(粗细对比)   → 提按幅度
        三爻(曲直复杂度) → 轨迹曲率
        四爻(间架规整度) → 位置精度要求
        五爻(重心x)      → 字心横向偏移修正
        上爻(重心y)      → 字心纵向偏移修正
    """

    @staticmethod
    def encode(yao_features: np.ndarray) -> Dict[str, float]:
        """
        将六爻转换为书写参数

        Returns:
            dict with: speed_consistency, press_amplitude,
                       curvature_factor, position_precision,
                       x_offset, y_offset
        """
        params = {
            'speed_consistency': float(yao_features[0]),      # 初爻
            'press_amplitude': float(yao_features[1]),         # 二爻
            'curvature_factor': float(yao_features[2]),        # 三爻
            'position_precision': float(yao_features[3]),      # 四爻
            'x_offset': float(yao_features[4]) - 0.5,          # 五爻 重心校正
            'y_offset': float(yao_features[5]) - 0.5,          # 上爻 重心校正
        }
        return params


# ============================================================
# 笔画轨迹生成器
# ============================================================

@dataclass
class StrokePlan:
    """一个笔画的执行计划"""
    name: str                             # 笔画名称
    brush_method: BrushMethod             # 笔法类型
    trajectory: np.ndarray                # (N, 2) 轨迹点
    pressures: np.ndarray                 # (N,) 压力序列
    speeds: np.ndarray                    # (N,) 速度序列
    metadata: Dict = field(default_factory=dict)


@dataclass
class CharacterPlan:
    """一个汉字的完整书写计划"""
    character: str                        # 汉字
    strokes: List[StrokePlan]             # 笔画列表
    total_points: int                     # 总轨迹点数
    metadata: Dict = field(default_factory=dict)


class StrokeGenerator:
    """
    笔画轨迹生成器

    基于八种笔法和书写参数生成机械臂轨迹。
    这是"爻→笔"的物理实现。
    """

    def __init__(self, paper_size: float = 0.3,
                 image_size: int = 256):
        """
        Args:
            paper_size: 纸面边长 (m)
            image_size: 参考图像大小 (像素)
        """
        self.paper_size = paper_size
        self.image_size = image_size
        self.half_paper = paper_size / 2

    def image_to_world(self, px: float, py: float) -> Tuple[float, float]:
        """图像坐标 → 世界坐标 (m)"""
        wx = (px / self.image_size - 0.5) * self.paper_size
        wy = (0.5 - py / self.image_size) * self.paper_size  # y翻转
        return wx, wy

    def world_to_image(self, wx: float, wy: float) -> Tuple[float, float]:
        """世界坐标 → 图像坐标"""
        px = (wx / self.paper_size + 0.5) * self.image_size
        py = (0.5 - wy / self.paper_size) * self.image_size
        return px, py

    def generate_stroke(self,
                         start: Tuple[float, float],
                         end: Tuple[float, float],
                         brush_method: BrushMethod,
                         calligraphy_params: Dict[str, float],
                         n_points: int = 100) -> StrokePlan:
        """
        生成一条笔画的完整轨迹（含几何修正）
        """
        sx, sy = self.image_to_world(start[0], start[1])
        ex, ey = self.image_to_world(end[0], end[1])

        bp = BRUSH_PARAMS[brush_method]

        # 几何修正参数
        angle_corr = calligraphy_params.get('stroke_angle_correction', 0.0)
        width_factor = calligraphy_params.get('stroke_width_factor', 1.0)
        curve_factor_mult = calligraphy_params.get('stroke_curve_factor', 1.0)
        jitter_amp = calligraphy_params.get('jitter_amplitude', 0.002)

        # 应用角度修正
        if abs(angle_corr) > 0.001:
            cos_a, sin_a = np.cos(angle_corr), np.sin(angle_corr)
            dx, dy = ex - sx, ey - sy
            ex = sx + dx * cos_a - dy * sin_a
            ey = sy + dx * sin_a + dy * cos_a

        n_points = max(n_points, 30)
        t = np.linspace(0, 1, n_points)
        tx = sx + (ex - sx) * t
        ty = sy + (ey - sy) * t

        # 曲率调制
        curvature = calligraphy_params.get('curvature_factor', 0.5) * curve_factor_mult
        if curvature > 0.15:
            amp = 0.003 * curvature * self.paper_size
            freq = 3 * curvature * np.pi
            perturbation = amp * np.sin(freq * t)
            dx, dy = ex - sx, ey - sy
            length = np.sqrt(dx**2 + dy**2)
            if length > 1e-6:
                nx, ny = -dy / length, dx / length
                tx += nx * perturbation
                ty += ny * perturbation

        # 手写抖动
        if jitter_amp > 1e-6:
            np.random.seed(42)
            tx += np.random.randn(n_points) * jitter_amp * self.paper_size
            ty += np.random.randn(n_points) * jitter_amp * self.paper_size

        trajectory = np.column_stack([tx, ty])

        # 压力序列 — 三段式：起笔顿→行笔提→收笔按或出锋
        # 起笔：0~15% = 从重到轻（顿笔）
        # 行笔：15%~85% = 稳定低压（行笔）
        # 收笔：85%~100% = 根据笔法决定（藏锋回收或出锋渐轻）
        n = n_points
        start_pct = max(0.08, min(0.18, 15/n))  # 起笔占比
        end_pct = max(0.08, min(0.18, 15/n))    # 收笔占比
        
        press_base = bp['pressure_base'] * width_factor * 1.5  # 整体加压
        press_amp = calligraphy_params.get('press_amplitude', 0.5)
        
        pressures = np.ones(n) * press_base * 0.45  # 行笔低压（调节墨色深浅）
        
        # 起笔顿：压力从 1.2*base 降到 0.5*base
        n_start = max(1, int(n * start_pct))
        pressures[:n_start] = np.linspace(press_base * 1.2, press_base * 0.5, n_start)
        
        # 行笔中段：低压稳定
        mid_start, mid_end = n_start, n - max(1, int(n * end_pct))
        pressures[mid_start:mid_end] = press_base * 0.5
        
        # 收笔：根据笔法类型
        if brush_method in [BrushMethod.CENTER_TIP, BrushMethod.HIDE_TIP, BrushMethod.PAUSE_HOLD]:
            # 藏锋/顿笔收 → 压力回升
            n_end = max(1, int(n * end_pct))
            pressures[-n_end:] = np.linspace(press_base * 0.5, press_base * 1.0, n_end)
        else:
            # 露锋/出锋 → 渐轻收笔（模拟笔尖提起）
            n_end = max(1, int(n * end_pct))
            pressures[-n_end:] = np.linspace(press_base * 0.5, press_base * 0.15, n_end)
        
        pressures = np.clip(pressures, 0.10, 1.0)

        # 速度序列（与压力三段式对应）
        speed_base = bp['speed']
        speed_consistency = calligraphy_params.get('speed_consistency', 0.5)
        speeds = np.ones(n) * speed_base
        if speed_consistency < 0.5:
            speed_var = (1.0 - speed_consistency) * speed_base * 0.5
            speeds += speed_var * np.sin(np.linspace(0, 4*np.pi, n))
        # 起笔慢，行笔快，收笔慢
        n_start = max(1, int(n * start_pct))
        n_end = max(1, int(n * end_pct))
        speeds[:n_start] = np.linspace(speed_base * 0.3, speed_base, n_start)
        speeds[-n_end:] = np.linspace(speed_base, speed_base * 0.3, n_end)
        speeds = np.clip(speeds, 0.01, 1.0)

        return StrokePlan(
            name=f'{brush_method.value}',
            brush_method=brush_method,
            trajectory=trajectory,
            pressures=pressures,
            speeds=speeds,
            metadata={
                'angle_correction': angle_corr,
                'width_factor': width_factor,
                'curve_factor': curve_factor_mult,
                'jitter_amp': jitter_amp,
            }
        )

    def generate_horizontal(self, x1: float, y: float, x2: float,
                             brush_method: BrushMethod,
                             params: Dict[str, float],
                             n_points: int = 100) -> StrokePlan:
        """生成横笔画"""
        return self.generate_stroke((x1, y), (x2, y), brush_method, params, n_points)

    def generate_vertical(self, x: float, y1: float, y2: float,
                           brush_method: BrushMethod,
                           params: Dict[str, float],
                           n_points: int = 100) -> StrokePlan:
        """生成竖笔画"""
        return self.generate_stroke((x, y1), (x, y2), brush_method, params, n_points)

    def generate_diagonal(self, x1: float, y1: float, x2: float, y2: float,
                           brush_method: BrushMethod,
                           params: Dict[str, float],
                           n_points: int = 100) -> StrokePlan:
        """生成斜笔画"""
        return self.generate_stroke((x1, y1), (x2, y2), brush_method, params, n_points)

    def generate_arc(self, start: Tuple[float, float],
                     end: Tuple[float, float],
                     control: Tuple[float, float],
                     brush_method: BrushMethod,
                     params: Dict[str, float],
                     n_points: int = 120) -> StrokePlan:
        """
        生成弧线笔画（贝塞尔曲线）

        Args:
            start, end: 起终点（图像坐标）
            control: 控制点（图像坐标）
        """
        # 二次贝塞尔曲线 B(t) = (1-t)²P0 + 2(1-t)t P1 + t²P2
        t = np.linspace(0, 1, n_points)
        sx, sy = start
        ex, ey = end
        cx, cy = control

        bx = (1-t)**2 * sx + 2*(1-t)*t * cx + t**2 * ex
        by = (1-t)**2 * sy + 2*(1-t)*t * cy + t**2 * ey

        wx = (bx / self.image_size - 0.5) * self.paper_size
        wy = (0.5 - by / self.image_size) * self.paper_size

        trajectory = np.column_stack([wx, wy])

        bp = BRUSH_PARAMS[brush_method]

        # 压力：起笔轻→行笔稳→收笔轻（弧线特有）
        press_base = bp['pressure_base']
        pressures = np.ones(n_points) * press_base
        start_ramp = min(15, n_points // 6)
        pressures[:start_ramp] = np.linspace(press_base * 0.7, press_base, start_ramp)
        end_ramp = min(20, n_points // 5)
        pressures[-end_ramp:] = np.linspace(press_base, press_base * 0.4, end_ramp)

        speeds = np.ones(n_points) * bp['speed']

        return StrokePlan(
            name=f'{brush_method.value}_arc',
            brush_method=brush_method,
            trajectory=trajectory,
            pressures=pressures,
            speeds=speeds,
            metadata={
                'start_image': start,
                'end_image': end,
                'control_image': control,
                'type': 'bezier_quad',
            }
        )


# ============================================================
# 书写YLYW主类
# ============================================================

class CalligraphyStrokeYLYW:
    """
    书写YLYW系统

    核心功能：
    - 根据视觉感知结果（结构卦象）生成汉字书写计划
    - 支持预定义汉字模板 + 卦象驱动的参数微调
    - 输出可直接被MuJoCo环境执行的轨迹
    """

    def __init__(self, paper_size: float = 0.3, image_size: int = 256):
        self.generator = StrokeGenerator(paper_size=paper_size, image_size=image_size)
        self.paper_size = paper_size
        self.image_size = image_size

        # 预定义的汉字笔画模板（图像坐标）
        self.char_templates = self._build_char_templates()

    def _build_char_templates(self) -> Dict:
        """构建参考汉字笔画模板"""
        sz = self.image_size
        margin = 50

        templates = {}

        # === '永'字（永字八法） ===
        templates['永'] = {
            'strokes': [
                # 点（侧）— 兑卦轻灵
                {'type': 'arc', 'start': (sz//2, margin+10), 'end': (sz//2+5, margin+25),
                 'control': (sz//2-10, margin+15), 'brush': '兑'},
                # 横（勒）— 乾卦刚健
                {'type': 'line', 'start': (margin+30, sz//3+10), 'end': (sz-margin-20, sz//3+10),
                 'brush': '乾'},
                # 竖（弩）— 艮卦沉稳
                {'type': 'line', 'start': (sz//2, sz//3+10), 'end': (sz//2, sz-margin-30),
                 'brush': '艮'},
                # 钩（趯）— 震卦突转
                {'type': 'arc', 'start': (sz//2, sz-margin-30), 'end': (sz//2+20, sz-margin-10),
                 'control': (sz//2+10, sz-margin-15), 'brush': '震'},
                # 左撇（掠）— 离卦出锋
                {'type': 'line', 'start': (sz//2, sz//2+10), 'end': (margin+20, margin+20),
                 'brush': '离'},
                # 右短撇（啄）— 震卦
                {'type': 'line', 'start': (sz//2+5, sz//2+15), 'end': (sz-margin-15, sz//3-5),
                 'brush': '震'},
                # 捺（磔）— 坤卦铺毫
                {'type': 'arc', 'start': (sz//2+5, sz//2+15), 'end': (sz-margin-10, sz-margin-20),
                 'control': (sz//2+60, sz//2+30), 'brush': '坤'},
            ]
        }

        # === '大'字 ===
        templates['大'] = {
            'strokes': [
                # 横
                {'type': 'line', 'start': (margin+40, sz//3), 'end': (sz-margin-40, sz//3),
                 'brush': '乾'},
                # 左撇
                {'type': 'line', 'start': (sz//2, sz//3), 'end': (margin+15, sz-margin-30),
                 'brush': '震'},
                # 右捺
                {'type': 'line', 'start': (sz//2+5, sz//3+5), 'end': (sz-margin-15, sz-margin-30),
                 'brush': '坤'},
            ]
        }

        # === '人'字 ===
        templates['人'] = {
            'strokes': [
                {'type': 'line', 'start': (sz//2-5, margin+20), 'end': (margin+25, sz-margin-25),
                 'brush': '震'},
                {'type': 'line', 'start': (sz//2+5, margin+20), 'end': (sz-margin-25, sz-margin-25),
                 'brush': '坤'},
            ]
        }

        # === '中'字 ===
        templates['中'] = {
            'strokes': [
                # 口字框上横
                {'type': 'line', 'start': (margin+30, sz//4),
                 'end': (sz-margin-30, sz//4), 'brush': '乾'},
                # 左竖
                {'type': 'line', 'start': (margin+30, sz//4),
                 'end': (margin+30, sz*3//4), 'brush': '艮'},
                # 右竖
                {'type': 'line', 'start': (sz-margin-30, sz//4),
                 'end': (sz-margin-30, sz*3//4), 'brush': '艮'},
                # 下横
                {'type': 'line', 'start': (margin+30, sz*3//4),
                 'end': (sz-margin-30, sz*3//4), 'brush': '乾'},
                # 中竖
                {'type': 'line', 'start': (sz//2, sz//4),
                 'end': (sz//2, sz*3//4), 'brush': '艮'},
            ]
        }

        # === '心'字 ===
        templates['心'] = {
            'strokes': [
                {'type': 'arc', 'start': (margin+30, sz//2+10), 'end': (margin+50, sz//2+20),
                 'control': (margin+35, sz//2+25), 'brush': '兑'},
                {'type': 'arc', 'start': (margin+45, sz//2+10), 'end': (sz-margin-20, sz//2-10),
                 'control': (sz//2, sz//2+80), 'brush': '坎'},
                {'type': 'arc', 'start': (sz//2-5, sz//2-25), 'end': (sz//2+5, sz//2-40),
                 'control': (sz//2-5, sz//2-35), 'brush': '兑'},
                {'type': 'arc', 'start': (sz-margin-45, sz//2-30), 'end': (sz-margin-25, sz//2-45),
                 'control': (sz-margin-40, sz//2-45), 'brush': '兑'},
            ]
        }

        # === '山'字 ===
        templates['山'] = {
            'strokes': [
                # 中竖
                {'type': 'line', 'start': (sz//2, margin+20), 'end': (sz//2, sz-margin-25), 'brush': '艮'},
                # 左竖(短，向外斜)
                {'type': 'line', 'start': (margin+45, sz//3+5), 'end': (margin+20, sz-margin-30), 'brush': '艮'},
                # 底横（最长）
                {'type': 'line', 'start': (margin+15, sz-margin-30), 'end': (sz-margin-15, sz-margin-30), 'brush': '乾'},
            ]
        }

        return templates

    def plan_character(self, character: str,
                        trigram_memberships: Dict[str, float],
                        yao_features: np.ndarray,
                        extra_params: Dict[str, float] = None) -> CharacterPlan:
        """
        为指定汉字生成书写计划

        Args:
            character: 汉字（必须在模板库中）
            trigram_memberships: 8卦隶属度
            yao_features: 6维六爻特征
            extra_params: 额外参数 (包含几何修正参数)
        """
        if character not in self.char_templates:
            raise ValueError(f"汉字 '{character}' 暂不在笔画模板库中。"
                           f"可用：{list(self.char_templates.keys())}")

        template = self.char_templates[character]
        calligraphy_params = YaoToCalligraphyParams.encode(yao_features)

        # 合并额外参数（几何修正等）
        if extra_params:
            calligraphy_params.update(extra_params)

        # 确定主导笔法
        dominant_trigram = max(trigram_memberships, key=trigram_memberships.get)
        dominant_brush = TRIGRAM_TO_BRUSH.get(dominant_trigram, BrushMethod.CENTER_TIP)

        x_offset = calligraphy_params.get('x_offset', 0) * self.paper_size * 0.2
        y_offset = calligraphy_params.get('y_offset', 0) * self.paper_size * 0.2

        strokes = []
        total_points = 0
        for i, sdef in enumerate(template['strokes']):
            if sdef.get('brush'):
                brush = TRIGRAM_TO_BRUSH.get(sdef['brush'], dominant_brush)
            else:
                brush = dominant_brush

            n_pts = 50 if sdef['type'] == 'arc' else 30

            if sdef['type'] == 'arc':
                stroke = self.generator.generate_arc(
                    sdef['start'], sdef['end'], sdef['control'],
                    brush, calligraphy_params, n_pts
                )
            else:
                stroke = self.generator.generate_stroke(
                    sdef['start'], sdef['end'],
                    brush, calligraphy_params, n_pts
                )

            stroke.trajectory[:, 0] -= x_offset
            stroke.trajectory[:, 1] -= y_offset

            stroke.metadata['stroke_index'] = i
            stroke.metadata['dominant_brush'] = dominant_brush.value
            strokes.append(stroke)
            total_points += len(stroke.trajectory)

        return CharacterPlan(
            character=character,
            strokes=strokes,
            total_points=total_points,
            metadata={
                'dominant_trigram': dominant_trigram,
                'dominant_brush': dominant_brush.value,
                'calligraphy_params': calligraphy_params,
                'x_offset': x_offset,
                'y_offset': y_offset,
            }
        )

    def get_available_characters(self) -> List[str]:
        """获取可用汉字列表"""
        return list(self.char_templates.keys())

    def get_trajectory_sequence(self, plan: CharacterPlan) -> Tuple[np.ndarray, np.ndarray]:
        """
        从书写计划中提取连续轨迹序列（可直接给MuJoCo执行）

        Returns:
            (trajectories, pressures) — shapes (N, 2) 和 (N,)
        """
        all_traj = []
        all_press = []
        for stroke in plan.strokes:
            all_traj.append(stroke.trajectory)
            all_press.append(stroke.pressures)

        return np.vstack(all_traj), np.concatenate(all_press)


# ============================================================
# 测试
# ============================================================

def test_stroke_ylyw():
    """测试书写YLYW模块"""
    print("=" * 60)
    print("YLYW书写策略生成测试")
    print("=" * 60)

    ylyw = CalligraphyStrokeYLYW()

    # 模拟视觉YLYW的感知结果
    # 场景：写"永"字，字帖分析得出"坤"卦主导（柔顺、圆转）
    trigram_memberships = {
        '乾': 0.3, '坤': 0.85, '震': 0.4, '艮': 0.35,
        '离': 0.5, '坎': 0.45, '兑': 0.3, '巽': 0.55,
    }

    yao_features = np.array([0.2, 0.6, 0.7, 0.5, 0.48, 0.52], dtype=np.float32)

    for char in ['永', '大', '人', '中', '心']:
        plan = ylyw.plan_character(char, trigram_memberships, yao_features)
        print(f"\n{'='*40}")
        print(f"汉字: {char}")
        print(f"主导卦象: {plan.metadata['dominant_trigram']}")
        print(f"主导笔法: {plan.metadata['dominant_brush']}")
        print(f"笔画数: {len(plan.strokes)}")
        print(f"总轨迹点: {plan.total_points}")

        for i, stroke in enumerate(plan.strokes):
            print(f"  笔画{i+1}: {stroke.name:20s} "
                  f"轨迹={stroke.trajectory.shape[0]}点 "
                  f"压力={stroke.pressures.mean():.2f}±{stroke.pressures.std():.2f} "
                  f"速度={stroke.speeds.mean():.2f}")

    print(f"\n✅ 测试完成！")
    return ylyw


if __name__ == '__main__':
    test_stroke_ylyw()
