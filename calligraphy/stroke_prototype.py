#!/usr/bin/env python3
"""
YLYW 书法 — 带起收笔形状的笔画原型

每个笔画用 6 个关键点定义（而不只是起终点 2 点）：
p0: 起笔顿点（重压，宽）
p1: 起笔转折
p2: 行笔起点（轻压，窄）  
p3: 行笔终点（轻压，窄）
p4: 收笔起点
p5: 收笔回锋/出锋点（重压或尖灭）

6个点控制一条笔画的外形，配合逐点压力控制，
让笔画有"起笔重顿→行笔轻提→收笔回锋"的毛笔效果。

YLYW 负责：
- 卦象→选择笔法类型（决定起收笔形态）
- 六爻→调整尺寸/角度/曲率等参数
- 六十四卦→组合笔画为完整的字
- 知几学习→迭代修正参数
"""

import numpy as np, cv2
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from mujoco_env import CalligraphyEnv
from learning_loop import load_copybook


class StrokePrototype:
    """
    6点笔画原型 — 支持起笔顿、行笔、收笔回锋/出锋
    """
    def __init__(self, p0, p1, p2, p3, p4, p5, 
                 brush_type='center_tip',
                 pressures=None):
        """
        p0-p5: 6个控制点 (x,y) 图像坐标
        brush_type: 笔法类型
        pressures: 可选逐点压力覆盖
        """
        self.p0 = np.array(p0, dtype=float)  # 起笔顿
        self.p1 = np.array(p1, dtype=float)  # 起笔转
        self.p2 = np.array(p2, dtype=float)  # 行笔起
        self.p3 = np.array(p3, dtype=float)  # 行笔终
        self.p4 = np.array(p4, dtype=float)  # 收笔起
        self.p5 = np.array(p5, dtype=float)  # 收笔终
        self.brush_type = brush_type
        self.pressures = pressures


def prototype_to_trajectory(proto, n_points=40, paper_half=0.15, img_size=256):
    """
    把6点原型展开为连续轨迹+压力序列
    """
    pts = [proto.p0, proto.p1, proto.p2, proto.p3, proto.p4, proto.p5]
    pts = np.array(pts)
    
    # Catmull-Rom 样条插值（经过所有控制点）
    traj_img = catmull_rom(pts, n_points)
    
    # 图像坐标→世界坐标
    wx = (traj_img[:,0] / img_size - 0.5) * (2 * paper_half)
    wy = (0.5 - traj_img[:,1] / img_size) * (2 * paper_half)
    world = np.column_stack([wx, wy])
    
    # 压力序列 — 对应起收笔形状
    n = n_points
    pressures = np.ones(n) * 0.45  # 行笔默认
    
    n_start = max(1, n // 6)     # 起笔段
    n_run   = max(1, n * 4 // 6) # 行笔段
    n_end   = n - n_start - n_run  # 收笔段
    
    pressures[:n_start] = np.linspace(0.95, 0.45, n_start)  # 起笔顿→轻
    pressures[n_start:n_start+n_run] = 0.45  # 行笔轻
    if proto.brush_type in ['center_tip', 'hide_tip', 'pause_hold']:
        pressures[-n_end:] = np.linspace(0.45, 0.85, n_end)  # 回锋
    else:
        pressures[-n_end:] = np.linspace(0.45, 0.08, n_end)  # 出锋渐灭
    
    return world, pressures


def catmull_rom(P, n_points):
    """Catmull-Rom 样条经过所有控制点"""
    n = len(P)
    result = []
    pts_per_seg = n_points // (n-1)
    
    for i in range(n-1):
        p0 = P[max(0, i-1)]
        p1 = P[i]
        p2 = P[i+1]
        p3 = P[min(n-1, i+2)]
        
        for t in np.linspace(0, 1, pts_per_seg + (1 if i==n-2 else 0)):
            t2, t3 = t*t, t*t*t
            pt = 0.5 * (
                (2*p1) +
                (-p0 + p2) * t +
                (2*p0 - 5*p1 + 4*p2 - p3) * t2 +
                (-p0 + 3*p1 - 3*p2 + p3) * t3
            )
            result.append(pt)
    
    return np.array(result[:n_points])


# ============ 大字原型 ============
SZ = 256
M = 40  # margin

DA_PROTOTYPES = [
    # 横（乾-中锋）：起笔顿→行笔平整→收笔回锋
    StrokePrototype(
        p0=(M+50, SZ//3-5),   # 起笔顿（稍上偏）
        p1=(M+60, SZ//3),
        p2=(M+55, SZ//3+2),   # 行笔起
        p3=(SZ-M-40, SZ//3+2),  # 行笔终
        p4=(SZ-M-20, SZ//3),
        p5=(SZ-M-15, SZ//3-5),  # 收笔回锋上提
        brush_type='center_tip'
    ),
    # 左撇（震-提按）：起笔重→出锋渐尖
    StrokePrototype(
        p0=(SZ//2+10, SZ//3+5),   # 起笔顿
        p1=(SZ//2+5, SZ//3+8),
        p2=(SZ//2, SZ//3+10),     # 行笔起
        p3=(M+25, SZ-60),           # 行笔终
        p4=(M+20, SZ-30),
        p5=(M+10, SZ-15),          # 出锋尖
        brush_type='lift_press'
    ),
    # 右捺（坤-侧锋）：起笔轻→铺毫展开→渐收
    StrokePrototype(
        p0=(SZ//2+15, SZ//3+10),  # 起笔
        p1=(SZ//2+20, SZ//3+12),
        p2=(SZ//2+25, SZ//3+15),  # 行笔起
        p3=(SZ-M-10, SZ-55),        # 行笔终（铺毫位置）
        p4=(SZ-M+5, SZ-30),
        p5=(SZ-M+20, SZ-15),        # 出锋
        brush_type='side_tip'
    ),
]


YONG_PROTOTYPES = [
    # 点（兑-轻灵）
    StrokePrototype(
        p0=(SZ//2+10, M+15),
        p1=(SZ//2+5, M+20),
        p2=(SZ//2, M+25),
        p3=(SZ//2-5, M+30),
        p4=(SZ//2, M+33),
        p5=(SZ//2+5, M+35),
        brush_type='light_skip'
    ),
    # 横（乾-中锋）
    StrokePrototype(
        p0=(M+45, SZ//3+15),
        p1=(M+55, SZ//3+17),
        p2=(M+50, SZ//3+19),
        p3=(SZ-M-30, SZ//3+19),
        p4=(SZ-M-15, SZ//3+17),
        p5=(SZ-M-10, SZ//3+13),
        brush_type='center_tip'
    ),
    # 竖（艮-沉稳）
    StrokePrototype(
        p0=(SZ//2+3, SZ//3+20),
        p1=(SZ//2-2, SZ//3+25),
        p2=(SZ//2, SZ//3+30),
        p3=(SZ//2, SZ-M-15),
        p4=(SZ//2, SZ-M-5),
        p5=(SZ//2+8, SZ-M+5),
        brush_type='pause_hold'
    ),
    # 左撇（离-出锋）
    StrokePrototype(
        p0=(SZ//2+3, SZ//2+10),
        p1=(SZ//2, SZ//2+15),
        p2=(SZ//2-5, SZ//2+20),
        p3=(M+25, M+30),
        p4=(M+15, M+15),
        p5=(M+8, M+5),
        brush_type='expose_tip'
    ),
    # 右短撇
    StrokePrototype(
        p0=(SZ//2+8, SZ//2+15),
        p1=(SZ//2+12, SZ//2+10),
        p2=(SZ//2+15, SZ//2+5),
        p3=(SZ-M+10, SZ//3+5),
        p4=(SZ-M+20, SZ//3-5),
        p5=(SZ-M+25, SZ//3-10),
        brush_type='lift_press'
    ),
    # 捺（坤-铺毫）
    StrokePrototype(
        p0=(SZ//2+8, SZ//2+18),
        p1=(SZ//2+15, SZ//2+20),
        p2=(SZ//2+20, SZ//2+25),
        p3=(SZ-M+5, SZ-M-35),
        p4=(SZ-M+15, SZ-M-10),
        p5=(SZ-M+25, SZ-M+5),
        brush_type='side_tip'
    ),
    # 钩（坎-险转）— 竖的末端钩
    StrokePrototype(
        p0=(SZ//2, SZ-M-15),
        p1=(SZ//2, SZ-M-5),
        p2=(SZ//2, SZ-M+2),
        p3=(SZ//2+15, SZ-M-5),
        p4=(SZ//2+20, SZ-M-8),
        p5=(SZ//2+25, SZ-M-12),
        brush_type='hide_tip'
    ),
]


def write_char(prototypes, character, outpath, perturb=0):
    """用原型写一个字"""
    all_traj, all_press = [], []
    
    for p in prototypes:
        traj, press = prototype_to_trajectory(p, n_points=40)
        # 加扰动
        if perturb > 0:
            traj += np.random.randn(*traj.shape) * perturb * 0.003
        all_traj.append(traj)
        all_press.append(press)
        # 抬笔
        all_traj.append(np.array([[traj[-1,0], traj[-1,1]]]))
        all_press.append(np.array([0.0]))
    
    full_traj = np.vstack(all_traj)
    full_press = np.concatenate(all_press)
    
    env = CalligraphyEnv()
    result = env.execute_trajectory(full_traj, full_press)
    env.close()
    
    img = result.rendered_image
    cv2.imwrite(outpath, img)
    ink = (img < 200).sum() / img.size * 100
    print(f'{character}: {len(prototypes)}笔, {len(full_traj)}点, ink={ink:.1f}%, saved={outpath}')
    return img


if __name__ == '__main__':
    print("=== YLYW 笔画原型书写测试 ===\n")
    write_char(DA_PROTOTYPES, '大', 'output/大_prototype.png')
    write_char(YONG_PROTOTYPES, '永', 'output/永_prototype.png')
