#!/usr/bin/env python3
"""
直接从楷体字帖提取书写轨迹。

方案：二值化→轮廓提取→轮廓点转世界坐标→生成轨迹。
写出来的就是字帖的形状，字形必须有保证。
"""

import cv2, numpy as np
from pathlib import Path

sys_path = str(Path(__file__).parent)
import sys
sys.path.insert(0, sys_path)

from mujoco_env import CalligraphyEnv
from learning_loop import load_copybook


def copybook_to_trajectory(character: str, paper_half: float = 0.15):
    """
    把楷体字帖的笔画像素直接转为机器人轨迹。
    
    步骤：
    1. 二值化（反色：墨→白）
    2. 形态学细化  
    3. 骨架像素按从上到下、从左到右排序
    4. 作为连续轨迹（抬笔在笔画之间）
    """
    img = load_copybook(character)
    if img is None:
        raise ValueError(f"No copybook for {character}")
    
    h, w = img.shape
    
    # 二值化
    _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
    
    # 细化
    skel = thin_zhang_suen(binary)
    
    # 提取所有骨架像素坐标
    ys, xs = np.where(skel > 0)
    if len(ys) == 0:
        raise ValueError(f"No skeleton pixels for {character}")
    
    # 按从上到下、从左到右排序（模拟书写顺序的粗略近似）
    order = np.lexsort((xs, ys))
    xs = xs[order]
    ys = ys[order]
    
    # 像素 → 世界坐标
    wx = (xs / w - 0.5) * (2 * paper_half)
    wy = (0.5 - ys / h) * (2 * paper_half)
    
    # 笔画分段：在像素跳跃大处断开（抬笔）
    trajectory = []
    pressures = []
    
    i = 0
    while i < len(xs):
        # 开始新笔画
        trajectory.append([wx[i], wy[i]])
        pressures.append(0.6)
        prev_x, prev_y = xs[i], ys[i]
        i += 1
        
        # 沿着这条笔画继续
        while i < len(xs):
            dist = np.sqrt((xs[i]-prev_x)**2 + (ys[i]-prev_y)**2)
            if dist > 3:  # 跳跃超过3像素 = 新笔画
                # 抬笔
                trajectory.append([wx[i], wy[i]])
                pressures.append(0.0)
                break
            trajectory.append([wx[i], wy[i]])
            pressures.append(0.6)
            prev_x, prev_y = xs[i], ys[i]
            i += 1
    
    return np.array(trajectory), np.array(pressures)


def thin_zhang_suen(binary):
    """Zhang-Suen 细化"""
    skel = (binary > 0).astype(np.uint8)
    h, w = skel.shape
    
    for _ in range(50):
        # step 1
        to_del = []
        for y in range(1, h-1):
            for x in range(1, w-1):
                if skel[y,x] == 0: continue
                p = [skel[y-1,x], skel[y-1,x+1], skel[y,x+1], skel[y+1,x+1],
                     skel[y+1,x], skel[y+1,x-1], skel[y,x-1], skel[y-1,x-1]]
                b = sum(p)
                if b < 2 or b > 6: continue
                a = sum(1 for i in range(8) if p[i]==0 and p[(i+1)%8]==1)
                if a != 1: continue
                if p[0]*p[2]*p[4] != 0: continue
                if p[2]*p[4]*p[6] != 0: continue
                to_del.append((y,x))
        for y,x in to_del: skel[y,x] = 0
        if not to_del: break
        
        # step 2
        to_del = []
        for y in range(1, h-1):
            for x in range(1, w-1):
                if skel[y,x] == 0: continue
                p = [skel[y-1,x], skel[y-1,x+1], skel[y,x+1], skel[y+1,x+1],
                     skel[y+1,x], skel[y+1,x-1], skel[y,x-1], skel[y-1,x-1]]
                b = sum(p)
                if b < 2 or b > 6: continue
                a = sum(1 for i in range(8) if p[i]==0 and p[(i+1)%8]==1)
                if a != 1: continue
                if p[0]*p[2]*p[6] != 0: continue
                if p[0]*p[4]*p[6] != 0: continue
                to_del.append((y,x))
        for y,x in to_del: skel[y,x] = 0
        if not to_del: break
    
    return (skel * 255).astype(np.uint8)


if __name__ == '__main__':
    for char in ['大', '永']:
        print(f"=== {char} ===")
        traj, press = copybook_to_trajectory(char)
        print(f"  Trajectory: {len(traj)} points")
        print(f"  x range: [{traj[:,0].min():.3f}, {traj[:,0].max():.3f}]")
        print(f"  y range: [{traj[:,1].min():.3f}, {traj[:,1].max():.3f}]")
        
        env = CalligraphyEnv()
        result = env.execute_trajectory(traj, press)
        env.close()
        
        img = result.rendered_image
        ink = (img < 200).sum() / img.size * 100
        print(f"  Image: mean={img.mean():.0f}, ink={ink:.1f}%")
        cv2.imwrite(f'output/{char}_skeleton_copy.png', img)
        print(f"  Saved: output/{char}_skeleton_copy.png\n")
