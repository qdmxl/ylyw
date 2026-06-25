#!/usr/bin/env python3
"""
从楷体字帖自动提取笔画模板。

不再用人眼看手动设置端点——而是自动分析字帖中每个笔画的
起止位置、长度、方向，生成精确匹配的笔画定义。
"""

import numpy as np, cv2
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from learning_loop import load_copybook


def analyze_char_copybook(char, img_size=256):
    """分析楷体字帖，提取笔画布局参数"""
    img = load_copybook(char)
    h, w = img.shape
    
    _, binary = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY_INV)
    
    # 1. 投影分析：横笔画
    row_sums = binary.sum(axis=1) / 255  # 每行黑色像素数
    
    # 找上半部分最长的黑色行（主横）
    top_half = h // 2
    best_row = np.argmax(row_sums[20:top_half]) + 20
    dark_cols = np.where(img[best_row] < 128)[0]
    heng = {
        'y': best_row,
        'x_start': dark_cols[0],
        'x_end': dark_cols[-1],
        'length': len(dark_cols),
    }
    
    # 2. 中线位置
    mid_x = (heng['x_start'] + heng['x_end']) // 2
    
    # 3. 找分叉点（撇和捺分离的位置）
    fork_row = None
    for row in range(best_row + 5, h - 10):
        dark = np.where(img[row] < 128)[0]
        if len(dark) < 3: continue
        left = dark[dark < mid_x + 5]
        right = dark[dark > mid_x - 5]
        if len(left) > 3 and len(right) > 3 and left[-1] < right[0]:
            fork_row = row
            break
    
    if fork_row is None:
        fork_row = best_row + (h - best_row) // 4
    
    # 4. 撇的端点
    pie_start = None
    for row in range(best_row, fork_row + 10):
        dark = np.where(img[row] < 128)[0]
        left = dark[dark < mid_x + 5]
        if len(left) > 2:
            pie_start = (left[-1], row)  # 撇起点取横下偏右
            break
    if pie_start is None:
        pie_start = (mid_x + 5, best_row + 5)
    
    pie_end = None
    for row in range(h - 15, fork_row, -1):
        dark = np.where(img[row] < 128)[0]
        left = dark[dark < mid_x + 10]
        if len(left) > 1:
            pie_end = (left[0], row)
            break
    if pie_end is None:
        pie_end = (30, h - 30)
    
    # 5. 捺的端点
    na_start = None
    for row in range(best_row, fork_row + 10):
        dark = np.where(img[row] < 128)[0]
        right = dark[dark > mid_x - 5]
        if len(right) > 2:
            na_start = (right[0], row)
            break
    if na_start is None:
        na_start = (mid_x + 10, best_row + 10)
    
    na_end = None
    for row in range(h - 15, fork_row, -1):
        dark = np.where(img[row] < 128)[0]
        right = dark[dark > mid_x - 10]
        if len(right) > 1:
            na_end = (right[-1], row)
            break
    if na_end is None:
        na_end = (w - 30, h - 30)
    
    strokes = [
        {'name': '横', 'type': 'line', 'start': (heng['x_start'], heng['y']), 
         'end': (heng['x_end'], heng['y'])},
        {'name': '撇', 'type': 'line', 'start': pie_start, 'end': pie_end},
        {'name': '捺', 'type': 'line', 'start': na_start, 'end': na_end},
    ]
    
    print(f"  「{char}」笔画分析:")
    for s in strokes:
        print(f"    {s['name']}: ({s['start'][0]},{s['start'][1]}) → ({s['end'][0]},{s['end'][1]})")
    
    return strokes


def strokes_to_trajectory(strokes, img_size=256, paper_half=0.15, n_pts=30):
    """笔画定义 → 世界坐标轨迹"""
    all_traj, all_press = [], []
    
    for s in strokes:
        sx, sy = s['start']
        ex, ey = s['end']
        
        # 直线插值
        xs = np.linspace(sx, ex, n_pts)
        ys = np.linspace(sy, ey, n_pts)
        
        # 图像 → 世界
        wx = (xs / img_size - 0.5) * (2 * paper_half)
        wy = (0.5 - ys / img_size) * (2 * paper_half)
        
        all_traj.append(np.column_stack([wx, wy]))
        all_press.append(np.full(n_pts, 0.6))
        
        # 抬笔
        all_traj.append(np.array([[wx[-1], wy[-1]]]))
        all_press.append(np.array([0.0]))
    
    return np.vstack(all_traj), np.concatenate(all_press)


if __name__ == '__main__':
    from mujoco_env import CalligraphyEnv
    outdir = Path(__file__).parent / 'output' / 'auto_template'
    outdir.mkdir(parents=True, exist_ok=True)
    
    for char in ['大', '永', '人', '中']:
        print(f"\n=== {char} ===")
        strokes = analyze_char_copybook(char)
        traj, press = strokes_to_trajectory(strokes)
        
        env = CalligraphyEnv()
        result = env.execute_trajectory(traj, press)
        env.close()
        
        cv2.imwrite(str(outdir / f'{char}.png'), result.rendered_image)
        print(f"  已保存: {outdir / f'{char}.png'}")
