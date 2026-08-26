"""真实机械臂 + 深度相机 + YLYW 多物体抓取系统 —— 配置模块。

集中管理相机 / 机械臂 / YLYW / 抓取安全参数，方便在不同硬件上切换。
所有可调阈值都放在这里，便于实验复现与论文数据采集。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============ 深度相机配置 ============
@dataclass(slots=True)
class DepthCameraConfig:
    """深度相机配置。

    backend:
      - "realsense": Intel RealSense（用 pyrealsense2，提供真实深度图与厂家内参）
      - "opencv":   通用 USB 摄像头 + stereo/结构光深度模式（fallback）
    """
    backend: str = "realsense"   # realsense | opencv | synthetic
    serial: Optional[str] = None          # 指定 RealSense 序列号（多机时）
    width: int = 640
    height: int = 480
    fps: int = 30
    depth_scale: float = 0.001            # 默认 1mm = 0.001 m
    align_depth: bool = True              # 深度与彩色图像对齐
    # —— OpenCV 后端参数（backend="opencv" 时使用）——
    # 无硬件深度时，用单色 + 已知标定高度做 2.5D 估计
    cv_table_height_m: float = 0.05       # 桌面平面在相机坐标系高度（相对相机光轴原点）
    # —— 点云下采样 ——
    voxel_size: float = 0.005             # 体素滤波网格（米）
    max_range: float = 1.0                # 有效深度范围上限（米）


# ============ 物体特征分析 ============
@dataclass(slots=True)
class FeaturesConfig:
    """物体特征分析参数。"""
    min_points: int = 30                  # 一个物体至少需要多少个点才分析
    max_cluster_dist: float = 0.03        # 聚类最大欧氏距离（米）
    ground_tolerance: float = 0.015       # 地面拟合容忍（米）
    # 曲率估计
    curvature_neighbors: int = 8          # 局部 PCA 邻域点数
    # 质量/力估计：由包围盒体积 + 密度估算
    default_density_kg_m3: float = 800.0  # 常见塑料/木块密度近似


# ============ YLYW 先验手册位置 ============
@dataclass(slots=True)
class YlywConfig:
    """YLYW 易理抓取规划配置。

    ylyw_core_path: 指向 YLYW 先验手册(prior_manual)的一级父目录。
    例如本项目自带副本位于 x2/ylyw_full_pipeline/，其下 ylyw_core/ 可直接导入。
    """
    ylyw_core_path: Path = field(
        default_factory=lambda: Path(
            "/home/lijinhan/MXL/科研/ylyw/api_docs"
        )
    )
    verbose: bool = True                  # 打印推理链（L1→L2→L3→策略）
    # 特征缺省值（某些特征无法从视觉测得时用）
    default_mass_kg: float = 0.15
    default_fragility: float = 0.5
    default_deformability: float = 0.1


# ============ YLYW→抓取策略 参数化 ============
@dataclass(slots=True)
class YlywGraspConfig:
    """将 YLYW 输出的 卦象策略 参数化为真实机械臂抓取参数。

    YLYW 给出: type(抓取类型), force(力预设0~1), approach_angle(接近角),
                speed(接近速度档), cautions(注意事项)。

    我们把它们映射到机械臂可执行参数。
    """
    # 抓取类型映射表：策略 type -> 夹爪模式
    force_range_mm: tuple[float, float] = (20.0, 60.0)   # 夹爪开度范围(mm)
    force_to_close_value: tuple[int, int] = (5, 50)       # 夹爪夹紧值(越小越紧)
    # 接近速度档映射（MyCobot 280 speed 范围 1~100）
    speed_map: dict = field(default_factory=lambda: {
        "slow": 20, "normal": 35, "fast": 50,
    })
    # 默认安全姿态（MyCobot 280 Cartesian, mm + 欧拉角）
    home_pose: list = field(default_factory=lambda: [0.0, 0.0, 200.0])
    approach_offset_mm: float = 60.0      # 目标上方安全接近距离
    lift_height_mm: float = 120.0         # 抓取后抬升高度
    placeholder_z_mm: float = 35.0        # 抓取逼近的末端 Z（桌面之上）


# ============ 机械臂执行器 ============
@dataclass(slots=True)
class RobotConfig:
    """MyCobot 280 执行器配置。"""
    port: str = "COM3"                    # Windows 例；Linux 用 /dev/ttyUSB0
    baudrate: int = 1000000               # 280-Arduino 用 1_000_000；280-M5 用 115200
    model: str = "280-arduino"            # 280-arduino | 280-m5
    timeout: float = 2.0
    # 关节限位(度)，与参考实例一致
    joint_limits: list = field(default_factory=lambda: [
        (-168.0, 168.0), (-140.0, 140.0), (-150.0, 150.0),
        (-150.0, 150.0), (-155.0, 160.0), (-180.0, 180.0),
    ])
    # 运动安全（speed 1~100）
    speed: int = 35                       # 1~100
    joint_step_deg: float = 4.0           # 关节插值最大步长
    max_joint_change: float = 8.0         # 单步最大关节变化
    min_margin: float = 8.0               # 关节限位安全余量
    settle_wait: float = 1.5              # 路径点停滞判定等待(秒)
    simulate: bool = False                # True 时仅打印，不驱动硬件


# ============ 主流程 ============
@dataclass(slots=True)
class AppConfig:
    grab_rounds: int = 5                  # 连续抓取轮数(多物体任意抓取)
    auto_pick_any: bool = True            # True:自动选最佳物体（任意抓取）
    target_class: Optional[str] = None    # 指定抓取某类物体（None=任意）
    place_pose: list = field(default_factory=lambda: [220.0, 0.0, 160.0])  # 放置区
    # 默认记录到本包目录下的 experiments（相对 cwd 用参数覆盖）
    record_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent / "experiments"
    )
    verbose: bool = True


def build_default() -> dict:
    """返回全部默认配置字典，便于序列化记录。"""
    return {
        "depth_camera": DepthCameraConfig.__dataclass_fields__,
        "robot": RobotConfig.__dataclass_fields__,
        "ylyw": YlywConfig.__dataclass_fields__,
    }
