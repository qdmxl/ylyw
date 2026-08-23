"""真实机械臂 + 深度相机 + YLYW 多物体任意抓取系统。

包内模块：
  config              配置
  depth_camera        深度相机(RealSense/OpenCV) → 点云
  object_features     物体特征分析(分割/尺寸/曲率/13维特征)
  ylyw_grasp_planner  YLYW 易理抓取规划(卦象→策略→抓取参数)
  robot_arm           MyCobot 280 安全执行器
  coordinate_transform 相机→基座坐标变换
  grasp_controller    抓取动作序列
  experiment_recorder 实验数据记录(CSV/JSONL)
  main                主流程(多物体任意抓取)
"""

__version__ = "0.1.0"
