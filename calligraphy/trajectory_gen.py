#!/usr/bin/env python3
"""
YLYW 书法 — 轨迹生成子系统（重写版）

从楷体字帖图像提取骨架 → 分解为笔画段 → Catmull-Rom平滑 → 输出轨迹

核心改进：
- 不再用人工设计的笔画模板
- 直接从字帖像素提取真实笔画走向
- 骨架分段保证笔画独立（不会连成一片）
- 样条平滑保证轨迹连续可执行
"""

import numpy as np
import cv2
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from learning_loop import load_copybook
from mujoco_env import CalligraphyEnv


def thin_zhang_suen(binary):
    """Zhang-Suen骨架细化"""
    skel = (binary > 0).astype(np.uint8)
    h, w = skel.shape
    for _ in range(80):
        # Step 1
        to_del = []
        for y in range(1, h-1):
            for x in range(1, w-1):
                if skel[y,x] == 0: continue
                p = [skel[y-1,x],skel[y-1,x+1],skel[y,x+1],skel[y+1,x+1],
                     skel[y+1,x],skel[y+1,x-1],skel[y,x-1],skel[y-1,x-1]]
                b = sum(p)
                if b < 2 or b > 6: continue
                a = sum(1 for i in range(8) if p[i]==0 and p[(i+1)%8]==1)
                if a != 1: continue
                if p[0]*p[2]*p[4] != 0 or p[2]*p[4]*p[6] != 0: continue
                to_del.append((y,x))
        for y,x in to_del: skel[y,x] = 0
        if not to_del: break
        
        # Step 2
        to_del = []
        for y in range(1, h-1):
            for x in range(1, w-1):
                if skel[y,x] == 0: continue
                p = [skel[y-1,x],skel[y-1,x+1],skel[y,x+1],skel[y+1,x+1],
                     skel[y+1,x],skel[y+1,x-1],skel[y,x-1],skel[y-1,x-1]]
                b = sum(p)
                if b < 2 or b > 6: continue
                a = sum(1 for i in range(8) if p[i]==0 and p[(i+1)%8]==1)
                if a != 1: continue
                if p[0]*p[2]*p[6] != 0 or p[0]*p[4]*p[6] != 0: continue
                to_del.append((y,x))
        for y,x in to_del: skel[y,x] = 0
        if not to_del: break
    return (skel * 255).astype(np.uint8)


def detect_nodes(skel):
    """检测骨架的端点和分叉点"""
    h, w = skel.shape
    binary = (skel > 0).astype(np.uint8)
    endpoints, junctions = [], []
    for y in range(1, h-1):
        for x in range(1, w-1):
            if binary[y,x] == 0: continue
            n = 0
            for dy in [-1,0,1]:
                for dx in [-1,0,1]:
                    if dy==0 and dx==0: continue
                    if binary[y+dy, x+dx] > 0: n += 1
            if n == 1: endpoints.append((y,x))
            elif n >= 3: junctions.append((y,x))
    return endpoints, junctions


def trace_strokes(skel, endpoints, junctions, min_len=8):
    """从端点追踪出独立笔画段"""
    h, w = skel.shape
    binary = (skel > 0).astype(np.uint8)
    visited = np.zeros((h,w), dtype=bool)
    
    node_set = set()
    for pt in endpoints: node_set.add((int(pt[0]), int(pt[1])))
    for pt in junctions: node_set.add((int(pt[0]), int(pt[1])))
    
    neighbors = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    segments = []
    
    for ey, ex in endpoints:
        visited[ey, ex] = True
        # 找起始出方向
        start_ny, start_nx = None, None
        for dy, dx in neighbors:
            ny, nx = ey+dy, ex+dx
            if 0<=ny<h and 0<=nx<w and binary[ny,nx] > 0 and not visited[ny,nx]:
                start_ny, start_nx = ny, nx
                break
        if start_ny is None: continue
        
        path = [(ey,ex)]
        visited[start_ny, start_nx] = True
        cy, cx = start_ny, start_nx
        
        while True:
            path.append((cy,cx))
            if (cy,cx) in node_set: break
            
            found = False
            for dy, dx in neighbors:
                ny, nx = cy+dy, cx+dx
                if 0<=ny<h and 0<=nx<w and binary[ny,nx] > 0 and not visited[ny,nx]:
                    visited[ny,nx] = True
                    cy, cx = ny, nx
                    found = True
                    break
            if not found: break
        
        if len(path) >= min_len:
            # 转为像素坐标 (x,y)
            pts = np.array([(x, y) for y,x in path], dtype=np.float32)
            segments.append(pts)
    
    return segments


def catmull_rom_smooth(points, target_count=60):
    """Catmull-Rom样条平滑，输出固定点数"""
    n = len(points)
    if n < 2: return points
    
    # 在原始点间均匀采样
    # 先计算累积弧长
    diffs = np.diff(points, axis=0)
    dists = np.sqrt(np.sum(diffs**2, axis=1))
    cumdist = np.concatenate([[0], np.cumsum(dists)])
    total = cumdist[-1]
    
    if total < 1: return points
    
    # 均匀采样 target_count 个点
    sample_dist = np.linspace(0, total, target_count)
    result = np.zeros((target_count, 2))
    
    for i, sd in enumerate(sample_dist):
        idx = np.searchsorted(cumdist, sd)
        if idx >= n: idx = n-1
        if idx == 0:
            result[i] = points[0]
        else:
            t = (sd - cumdist[idx-1]) / max(dists[idx-1], 1e-6)
            t = np.clip(t, 0, 1)
            result[i] = points[idx-1] * (1-t) + points[idx] * t
    
    return result


def segments_to_trajectory(segments, img_size=256, paper_half=0.15):
    """
    将笔画段转为世界坐标轨迹 + 压力
    
    按从上到下、从左到右排序笔画段
    """
    # 排序：按首点的y坐标（上→下），同y按x（左→右）
    seg_info = [(s[0,1], s[0,0], i, s) for i, s in enumerate(segments)]
    seg_info.sort()
    
    all_traj = []
    all_press = []
    
    for _, _, _, seg in seg_info:
        # 平滑
        smooth = catmull_rom_smooth(seg, 60)
        
        # 图像坐标→世界坐标
        wx = (smooth[:,0] / img_size - 0.5) * (2 * paper_half)
        wy = (0.5 - smooth[:,1] / img_size) * (2 * paper_half)
        
        all_traj.append(np.column_stack([wx, wy]))
        all_press.append(np.full(len(smooth), 0.6))
        
        # 笔画间抬笔
        all_traj.append(np.array([[wx[-1], wy[-1]]]))
        all_press.append(np.array([0.0]))
    
    if not all_traj: return np.zeros((0,2)), np.zeros(0)
    
    return np.vstack(all_traj), np.concatenate(all_press)


def generate_trajectory(char, output_dir=None):
    """主函数：从字帖生成轨迹并写出图片"""
    img = load_copybook(char)
    
    # 二值化
    _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
    
    # 骨架
    skel = thin_zhang_suen(binary)
    
    # 分段
    endpoints, junctions = detect_nodes(skel)
    segments = trace_strokes(skel, endpoints, junctions)
    
    print(f"  {char}: {len(segments)}个笔画段")
    
    # 转轨迹
    traj, press = segments_to_trajectory(segments)
    print(f"  轨迹: {len(traj)}点")
    
    # 写出
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        env = CalligraphyEnv()
        result = env.execute_trajectory(traj, press)
        env.close()
        
        cv2.imwrite(str(output_dir / f'{char}.png'), result.rendered_image)
        cv2.imwrite(str(output_dir / f'{char}_skel.png'), skel)
        print(f"  已保存: {output_dir / f'{char}.png'}")
    
    return traj, press


if __name__ == '__main__':
    outdir = Path(__file__).parent / 'output' / 'new_traj'
    for ch in ['大', '永', '人', '中']:
        generate_trajectory(ch, output_dir=outdir)
    print("\n✅ 完成")
