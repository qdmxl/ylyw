"""
MuJoCo 2D书法书写环境

在MuJoCo物理引擎中模拟毛笔在纸面书写的过程。
环境特点:
- 2D书写平面 + 虚拟毛笔末端执行器
- 可记录笔迹轨迹（用于视觉反馈）
- 支持力控（笔尖压力模拟）
- 可渲染为"字帖"风格的图像（用于视觉YLYW分析）

架构:
- 虚拟平面：位置控制xy，力控z（笔尖压力）
- 笔迹记录：轨迹+压力→渲染为手写效果图
- 观测输出：书写结果图像（供视觉YLYW对比分析）
"""

import os
import numpy as np
import cv2
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
from pathlib import Path

# 设置MuJoCo离屏渲染后端（无GUI环境）
if 'MUJOCO_GL' not in os.environ:
    os.environ['MUJOCO_GL'] = 'egl'

# MuJoCo imports
import mujoco
from mujoco import viewer


@dataclass
class StrokePoint:
    """笔迹采样点"""
    x: float       # 纸面x坐标 (m)
    y: float       # 纸面y坐标 (m)
    pressure: float  # 笔尖压力 [0,1]
    t: float       # 时间戳
    thickness: float = 1.0  # 笔触粗细倍率


@dataclass
class CalligraphyResult:
    """一次书写的结果"""
    stroke_points: List[StrokePoint] = field(default_factory=list)
    rendered_image: Optional[np.ndarray] = None   # 渲染的书写结果图
    total_duration: float = 0.0
    metadata: Dict = field(default_factory=dict)


class CalligraphyEnv:
    """
    MuJoCo 书法书写环境

    XML模型结构:
    - 一个固定平面（纸面，白色）
    - 一个受控的"毛笔"末端执行器（2D位置+压力）
    - 纸面上方有相机用于观测

    动作空间:
    - [x, y, pressure] 其中 x,y ∈ [-0.15, 0.15] (纸面范围), pressure ∈ [0, 1]

    观测:
    - 书写结果渲染图 (128x128灰度)
    - 当前笔尖位置和压力
    """

    # 纸面参数
    PAPER_WIDTH = 0.3     # 30cm
    PAPER_HEIGHT = 0.3    # 30cm
    PAPER_Z = 0.001       # 纸面高度

    # 渲染参数
    RENDER_SIZE = 256     
    BRUSH_RADIUS_BASE = 10.0  # 基础笔触半径——配合thickness_ratio使用
    INK_COLOR = 255       # 深黑

    def __init__(self, render_mode: str = 'offscreen'):
        """
        Args:
            render_mode: 'offscreen' (无GUI) 或 'gui' (带可视化)
        """
        self.render_mode = render_mode
        self.model = None
        self.data = None
        self.renderer = None
        self.viewer = None

        # 笔迹缓冲
        self.stroke_buffer: List[StrokePoint] = []
        self.start_time = time.time()

        # 当前状态
        self.current_pen_x = 0.0
        self.current_pen_y = 0.0
        self.current_pressure = 0.0

        # 建仿真
        self._build_mujoco_model()

    def _build_mujoco_model(self):
        """构建MuJoCo模型"""

        xml = f"""
        <mujoco model="calligraphy">
            <compiler angle="degree"/>

            <visual>
                <headlight diffuse="0.8 0.8 0.8" ambient="0.3 0.3 0.3" specular="0.1 0.1 0.1"/>
            </visual>

            <worldbody>
                <!-- 纸面 -->
                <body name="paper" pos="0 0 0">
                    <geom type="box" size="{self.PAPER_WIDTH/2} {self.PAPER_HEIGHT/2} 0.001"
                          rgba="0.95 0.93 0.85 1" name="paper_geom"/>
                </body>

                <!-- 毛笔末端执行器 -->
                <body name="brush_tip" pos="0 0 0.05">
                    <joint name="brush_x" type="slide" axis="1 0 0" range="-0.15 0.15"/>
                    <joint name="brush_y" type="slide" axis="0 1 0" range="-0.15 0.15"/>
                    <joint name="brush_z" type="slide" axis="0 0 1" range="0.001 0.05"/>

                    <!-- 笔尖几何体 -->
                    <geom name="brush_geom" type="ellipsoid" size="0.003 0.003 0.008"
                          pos="0 0 -0.004" rgba="0.05 0.05 0.05 1"/>

                    <!-- 笔杆几何体 -->
                    <geom name="brush_body" type="capsule" size="0.005 0.04"
                          pos="0 0 0.03" rgba="0.3 0.15 0.05 1"/>

                    <!-- 笔尖site（用于传感器和相机跟踪） -->
                    <site name="brush_site" pos="0 0 -0.008" size="0.001"/>
                </body>

                <!-- 顶部相机：俯视纸面 -->
                <camera name="top_camera" mode="fixed" pos="0 0 0.5" xyaxes="1 0 0 0 -1 0"
                        fovy="45"/>
            </worldbody>

            <actuator>
                <!-- x位置执行器 -->
                <position name="act_x" joint="brush_x" kp="500"/>
                <!-- y位置执行器 -->
                <position name="act_y" joint="brush_y" kp="500"/>
                <!-- z位置/压力执行器 -->
                <position name="act_z" joint="brush_z" kp="300"/>
            </actuator>

            <sensor>
                <!-- 接触力传感器（笔尖site-纸面） -->
                <touch name="touch_sensor" site="brush_site"/>
            </sensor>
        </mujoco>
        """

        # 从字符串加载模型
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)

        # 创建离屏渲染器
        if self.render_mode == 'offscreen':
            self.renderer = mujoco.Renderer(self.model, self.RENDER_SIZE, self.RENDER_SIZE)
        else:
            self.renderer = mujoco.Renderer(self.model, self.RENDER_SIZE, self.RENDER_SIZE)

        print(f"[YLYW书法] MuJoCo环境初始化完成")
        print(f"  纸面: {self.PAPER_WIDTH*100:.0f}×{self.PAPER_HEIGHT*100:.0f}cm")
        print(f"  渲染: {self.RENDER_SIZE}×{self.RENDER_SIZE}")

    def reset(self) -> np.ndarray:
        """
        重置环境：清空笔迹，将笔移到起始位置

        Returns:
            初始渲染图像 (RENDER_SIZE×RENDER_SIZE×3)
        """
        mujoco.mj_resetData(self.model, self.data)

        # 初始化笔位置：纸面中心上方
        self.data.joint('brush_x').qpos = 0.0
        self.data.joint('brush_y').qpos = 0.0
        self.data.joint('brush_z').qpos = 0.03

        mujoco.mj_forward(self.model, self.data)

        # 清空笔迹缓冲
        self.stroke_buffer = []
        self.start_time = time.time()

        self.current_pen_x = 0.0
        self.current_pen_y = 0.0
        self.current_pressure = 0.0

        # 渲染初始帧
        self.renderer.update_scene(self.data, camera='top_camera')
        img = self.renderer.render()

        return img

    def step(self, target_x: float, target_y: float, target_pressure: float,
             thickness: float = 1.0) -> Tuple[np.ndarray, Dict]:
        """
        执行一步书写动作

        Args:
            target_x: 目标x位置
            target_y: 目标y位置
            target_pressure: 目标压力 [0, 1]
            thickness: 笔触粗细倍率
        """
        # Clip to paper bounds
        half_w = self.PAPER_WIDTH / 2
        half_h = self.PAPER_HEIGHT / 2
        tx = np.clip(target_x, -half_w, half_w)
        ty = np.clip(target_y, -half_h, half_h)
        tp = np.clip(target_pressure, 0.0, 1.0)

        # 计算笔尖Z位置：0压力时悬空，1压力时接触纸面
        z_target = self.PAPER_Z + 0.0005 - tp * 0.005
        z_target = max(0.0001, z_target)

        # 设置MuJoCo控制
        self.data.ctrl[0] = tx
        self.data.ctrl[1] = ty
        self.data.ctrl[2] = z_target

        # 执行物理步（多步以收敛到位）
        for _ in range(5):  # 每控制步跑5个物理步
            mujoco.mj_step(self.model, self.data)

        # 更新状态 — 使用 target 位置（已 clip）而非实际物理位置
        self.current_pen_x = tx
        self.current_pen_y = ty
        self.current_pressure = tp

        # 记录笔迹
        if tp > 0.01:  # 有接触压力时记录
            sp = StrokePoint(
                x=self.current_pen_x,
                y=self.current_pen_y,
                pressure=tp,
                thickness=thickness,
                t=time.time() - self.start_time
            )
            self.stroke_buffer.append(sp)

        # 渲染
        self.renderer.update_scene(self.data, camera='top_camera')
        img = self.renderer.render()

        # 状态信息
        info = {
            'pen_x': self.current_pen_x,
            'pen_y': self.current_pen_y,
            'pressure': self.current_pressure,
            'stroke_length': len(self.stroke_buffer),
        }

        return img, info

    def render_strokes(self, image_size: int = 256) -> np.ndarray:
        """
        将记录的笔迹渲染为"书写结果"图像。

        使用基于压力的笔触模型：
        - 笔触半径 = BRUSH_RADIUS_BASE × (0.5 + 0.5 × pressure)
        - 颜色渐变模拟墨迹

        Returns:
            np.ndarray: (image_size, image_size) 灰度图, 0=黑(墨), 255=白(纸)
        """
        # 白色背景
        canvas = np.ones((image_size, image_size), dtype=np.float32) * 255

        if len(self.stroke_buffer) < 2:
            return canvas.astype(np.uint8)

        # 转换坐标：MuJoCo世界坐标 → 图像像素坐标
        half_w = self.PAPER_WIDTH / 2
        half_h = self.PAPER_HEIGHT / 2

        def world_to_pixel(wx, wy):
            """世界坐标 (m) → 像素坐标"""
            px = int((wx + half_w) / self.PAPER_WIDTH * image_size)
            py = int((half_h - wy) / self.PAPER_HEIGHT * image_size)  # y翻转
            return np.clip(px, 0, image_size-1), np.clip(py, 0, image_size-1)

        # 逐段渲染笔触
        for i in range(len(self.stroke_buffer) - 1):
            p0 = self.stroke_buffer[i]
            p1 = self.stroke_buffer[i + 1]

            x0, y0 = world_to_pixel(p0.x, p0.y)
            x1, y1 = world_to_pixel(p1.x, p1.y)

            # 笔触半径（基于压力 + thickness倍率）
            avg_pressure = (p0.pressure + p1.pressure) / 2
            avg_thickness = (getattr(p0, 'thickness', 1.0) + getattr(p1, 'thickness', 1.0)) / 2
            radius = max(1.5, self.BRUSH_RADIUS_BASE * (0.4 + 0.6 * avg_pressure) * avg_thickness)

            # 墨色浓度
            ink_intensity = self.INK_COLOR * (0.5 + 0.5 * avg_pressure)

            # 绘制线段
            dist = np.sqrt((x1-x0)**2 + (y1-y0)**2)
            if dist < 0.5:
                self._draw_brush_point(canvas, x0, y0, radius, ink_intensity)
            else:
                # 只采样子段数 = 线段长度 / 半径（避免过度叠加）
                n_segments = max(1, int(dist / radius))
                for j in range(n_segments + 1):
                    t = j / n_segments
                    px = int(x0 + (x1 - x0) * t)
                    py = int(y0 + (y1 - y0) * t)
                    self._draw_brush_point(canvas, px, py, radius, ink_intensity)

        return canvas.astype(np.uint8)

    def _draw_brush_point(self, canvas: np.ndarray, cx: int, cy: int,
                           radius: float, intensity: float):
        """在画布上绘制圆形笔触（不是高斯，就是实心圆+边缘渐变）"""
        h, w = canvas.shape
        r_int = int(np.ceil(radius))

        x_min = max(0, cx - r_int - 1)
        x_max = min(w, cx + r_int + 2)
        y_min = max(0, cy - r_int - 1)
        y_max = min(h, cy + r_int + 2)

        if x_min >= x_max or y_min >= y_max:
            return

        yy, xx = np.mgrid[y_min:y_max, x_min:x_max]
        dist = np.sqrt((xx - cx)**2 + (yy - cy)**2)
        
        # 实心圆：半径内=全黑，半径到半径+1=边缘过渡
        mask_inner = dist <= radius
        mask_edge = (dist > radius) & (dist <= radius + 1.5)
        
        region = canvas[y_min:y_max, x_min:x_max]
        darkness = intensity * 0.8
        
        # 实心部分
        region[mask_inner] = np.maximum(0, region[mask_inner] - darkness)
        # 边缘部分
        if mask_edge.any():
            edge_factor = (radius + 1.5 - dist[mask_edge]) / 1.5
            region[mask_edge] = np.maximum(0, region[mask_edge] - darkness * edge_factor[:, np.newaxis] if len(region.shape)>2 else region[mask_edge] - darkness * edge_factor)

    def get_stroke_image(self, image_size: int = 256) -> np.ndarray:
        """
        获取书写结果的渲染图（供视觉YLYW分析）

        Returns:
            np.ndarray: (image_size, image_size) 灰度图
        """
        return self.render_strokes(image_size)

    def execute_stroke_plan(self, stroke_plan: List[dict],
                            render_interval: int = 5) -> CalligraphyResult:
        """
        执行一个笔画的完整计划。

        Args:
            stroke_plan: List of dicts, each with {'x', 'y', 'pressure'}
            render_interval: 每N步渲染一次

        Returns:
            CalligraphyResult
        """
        self.reset()

        total_steps = len(stroke_plan)
        for i, action in enumerate(stroke_plan):
            tx = action['x']
            ty = action['y']
            tp = action.get('pressure', 0.5)

            self.step(tx, ty, tp)

        # 渲染最终结果
        result_image = self.render_strokes()

        return CalligraphyResult(
            stroke_points=list(self.stroke_buffer),
            rendered_image=result_image,
            total_duration=time.time() - self.start_time,
            metadata={
                'total_steps': total_steps,
                'stroke_count': len(self.stroke_buffer),
            }
        )

    def execute_trajectory(self, trajectory: np.ndarray,
                           pressure: np.ndarray = None,
                           thickness: np.ndarray = None) -> CalligraphyResult:
        """
        执行轨迹数组。

        Args:
            trajectory: shape (N, 2), xy坐标对
            pressure: shape (N,), 压力值
            thickness: shape (N,), 笔触粗细倍率
        """
        self.reset()

        if pressure is None:
            pressure = np.ones(len(trajectory)) * 0.5
        if thickness is None:
            thickness = np.ones(len(trajectory)) * 1.0

        # 预热：先把笔移到第一个轨迹点附近（不画）
        first_x, first_y = float(trajectory[0, 0]), float(trajectory[0, 1])
        for _ in range(30):
            self.data.ctrl[0] = first_x
            self.data.ctrl[1] = first_y
            self.data.ctrl[2] = 0.02  # 悬空
            mujoco.mj_step(self.model, self.data)

        for i in range(len(trajectory)):
            self.step(
                float(trajectory[i, 0]),
                float(trajectory[i, 1]),
                float(pressure[i]),
                thickness=float(thickness[i]),
            )

        result_image = self.render_strokes()
        return CalligraphyResult(
            stroke_points=list(self.stroke_buffer),
            rendered_image=result_image,
            total_duration=time.time() - self.start_time,
            metadata={
                'total_points': len(trajectory),
                'stroke_length': len(self.stroke_buffer),
            }
        )

    def get_canvas_snapshot(self, image_size: int = 256) -> np.ndarray:
        """获取当前书写画布的快照"""
        return self.render_strokes(image_size)

    def close(self):
        """关闭环境"""
        if self.renderer is not None:
            self.renderer.close()
        if self.viewer is not None:
            self.viewer.close()


def test_environment():
    """测试环境：画一个简单的圆"""
    print("=" * 60)
    print("YLYW书法环境测试")
    print("=" * 60)

    env = CalligraphyEnv(render_mode='offscreen')
    env.reset()

    # 画一个圆
    trajectory = []
    n_points = 200
    radius = 0.06
    for i in range(n_points):
        angle = 2 * np.pi * i / n_points
        pressure = 0.5 + 0.3 * np.sin(angle)  # 压力变化模拟提按
        trajectory.append({
            'x': radius * np.cos(angle),
            'y': radius * np.sin(angle),
            'pressure': float(np.clip(pressure, 0.1, 1.0)),
        })

    result = env.execute_stroke_plan(trajectory)

    # 保存结果
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    cv2.imwrite(str(output_dir / 'test_circle.png'), result.rendered_image)

    print(f"\n✅ 测试完成！")
    print(f"  笔画点数: {len(result.stroke_points)}")
    print(f"  持续时间: {result.total_duration:.2f}s")
    print(f"  输出图像: {output_dir / 'test_circle.png'}")

    env.close()
    return result


if __name__ == '__main__':
    test_environment()
