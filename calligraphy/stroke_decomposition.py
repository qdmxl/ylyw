"""
笔画自主分解与轨迹生成 (Stroke Decomposition & Generation)

从字帖图像自动分解笔画，由卦象驱动笔画顺序和轨迹生成。
这是YLYW从"辅助调参"升级到"自主规划"的核心模块。

架构：
- 视觉笔画骨架提取：细化→分叉点检测→笔画段分割
- 卦象→笔画顺序推理：爻位关系→笔画先后
- 笔画段→轨迹生成：方向卦象映射→笔法选择→轨迹参数化

与焊接的映射：
    汉字笔画分解  ←→  焊缝分段分解
    笔画顺序推理  ←→  焊接顺序规划
    笔法选择      ←→  焊接工艺选择
    轨迹生成      ←→  焊枪路径生成
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum
from collections import defaultdict


# ============================================================
# 笔画段数据结构
# ============================================================

class StrokeType(Enum):
    """笔画类型（基于方向+形态）"""
    HENG = '横'      # 水平笔画
    SHU = '竖'       # 垂直笔画
    PIE = '撇'       # 左上→右下斜线
    NA = '捺'        # 左上→右下斜笔（重按出锋）
    DIAN = '点'      # 短小笔画
    GOU = '钩'       # 转折钩
    ZHE = '折'       # 转折
    ARC = '弧'       # 弧线


@dataclass
class StrokeSegment:
    """一个笔画段"""
    id: int
    points: np.ndarray                  # (N, 2) 像素坐标序列
    start: np.ndarray                   # (2,) 起点
    end: np.ndarray                     # (2,) 终点
    direction: float                    # 主方向 (弧度)
    length: float                       # 笔画长度 (像素)
    thickness: float                    # 平均粗细 (像素)
    stroke_type: StrokeType             # 笔画类型
    neighbors_start: List[int] = field(default_factory=list)  # 起点连接的笔画id
    neighbors_end: List[int] = field(default_factory=list)    # 终点连接的笔画id
    brush_method: str = 'center_tip'    # 推荐笔法


@dataclass
class CharacterDecomposition:
    """一个字的完整分解结果"""
    character_image: np.ndarray         # 原始字帖图像
    skeleton: np.ndarray                # 骨架图像
    strokes: List[StrokeSegment]        # 笔画段列表
    stroke_order: List[int]             # 笔画书写顺序（笔画id列表）
    trigram_analysis: Dict              # 卦象分析结果
    writing_plan: Dict                  # 书写计划


# ============================================================
# 笔画骨架提取器
# ============================================================

class StrokeSkeletonExtractor:
    """
    从字帖图像中提取笔画骨架并进行分割。

    流程：
    1. 预处理：二值化→去噪
    2. 细化：Zhang-Suen算法提取单像素骨架
    3. 节点检测：端点+分叉点
    4. 笔画分割：从端点沿骨架追踪到节点
    5. 笔画分类：根据方向/形态分类
    """

    def __init__(self, min_stroke_length: int = 10,
                 direction_threshold: float = 0.3):
        self.min_stroke_length = min_stroke_length
        self.direction_threshold = direction_threshold

    def extract(self, image: np.ndarray, verbose: bool = False) -> CharacterDecomposition:
        """
        从字帖图像分解笔画

        Args:
            image: 灰度或RGB图像
            verbose: 是否打印详细信息

        Returns:
            CharacterDecomposition
        """
        # Step 1: 预处理
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 用Otsu自适应二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if binary.sum() / 255 < 50:
            _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # 轻微闭运算
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        if verbose:
            print(f"[骨架] 二值化完成，笔画像素: {binary.sum()/255:.0f}")

        # Step 2: 细化
        skeleton = self._thin(binary)

        if verbose:
            print(f"[骨架] 细化完成")

        # Step 2.5: 骨架修剪（去除毛刺）
        skeleton = self._prune_skeleton(skeleton, max_prune_length=6)

        # Step 3: 检测节点（分叉点和端点）
        nodes, endpoints, junctions = self._detect_nodes(skeleton)

        if verbose:
            print(f"[骨架] 节点: {len(nodes)} (端点={len(endpoints)}, 分叉点={len(junctions)})")

        # Step 4: 笔画分割
        strokes = self._segment_strokes(skeleton, endpoints, junctions, verbose)

        if verbose:
            print(f"[骨架] 笔画段: {len(strokes)}")

        # Step 5: 笔画分类
        for stroke in strokes:
            stroke.stroke_type = self._classify_stroke(stroke)

        # Step 6: 构建连接关系
        self._build_connectivity(strokes)

        return CharacterDecomposition(
            character_image=image,
            skeleton=skeleton,
            strokes=strokes,
            stroke_order=[],
            trigram_analysis={},
            writing_plan={},
        )

    def _thin(self, binary: np.ndarray) -> np.ndarray:
        """Zhang-Suen细化算法（纯Python实现）"""
        skel = (binary > 0).astype(np.uint8)
        h, w = skel.shape

        for iteration in range(100):
            # Step 1: 删除东南边界点
            to_del = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if skel[y, x] == 0:
                        continue
                    # 8邻域 P2..P9 顺时针
                    p = [
                        skel[y-1, x],   skel[y-1, x+1],
                        skel[y, x+1],   skel[y+1, x+1],
                        skel[y+1, x],   skel[y+1, x-1],
                        skel[y, x-1],   skel[y-1, x-1],
                    ]
                    b = sum(p)
                    if b < 2 or b > 6:
                        continue
                    # A(P1): 0→1转换次数
                    a = sum(1 for i in range(8) if p[i] == 0 and p[(i+1) % 8] == 1)
                    if a != 1:
                        continue
                    if p[0] * p[2] * p[4] != 0:  # P2*P4*P6
                        continue
                    if p[2] * p[4] * p[6] != 0:  # P4*P6*P8
                        continue
                    to_del.append((y, x))

            for y, x in to_del:
                skel[y, x] = 0

            if not to_del:
                break

            # Step 2: 删除西北边界点
            to_del = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if skel[y, x] == 0:
                        continue
                    p = [
                        skel[y-1, x],   skel[y-1, x+1],
                        skel[y, x+1],   skel[y+1, x+1],
                        skel[y+1, x],   skel[y+1, x-1],
                        skel[y, x-1],   skel[y-1, x-1],
                    ]
                    b = sum(p)
                    if b < 2 or b > 6:
                        continue
                    a = sum(1 for i in range(8) if p[i] == 0 and p[(i+1) % 8] == 1)
                    if a != 1:
                        continue
                    if p[0] * p[2] * p[6] != 0:  # P2*P4*P8
                        continue
                    if p[0] * p[4] * p[6] != 0:  # P2*P6*P8
                        continue
                    to_del.append((y, x))

            for y, x in to_del:
                skel[y, x] = 0

            if not to_del:
                break

        return (skel * 255).astype(np.uint8)

    def _prune_skeleton(self, skeleton: np.ndarray,
                        max_prune_length: int = 6) -> np.ndarray:
        """
        修剪骨架毛刺。
        
        对细化后的骨架，反复删除长度小于max_prune_length的端点分支。
        这对消除笔画交叉处的毛刺至关重要。
        """
        skel = (skeleton > 0).astype(np.uint8)
        h, w = skel.shape
        
        for iteration in range(max_prune_length):
            # 找端点
            endpoints = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if skel[y, x] == 0:
                        continue
                    n_count = 0
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dy == 0 and dx == 0:
                                continue
                            if skel[y + dy, x + dx] > 0:
                                n_count += 1
                    if n_count == 1:
                        endpoints.append((y, x))
            
            if not endpoints:
                break
            
            # 删除所有端点
            for y, x in endpoints:
                skel[y, x] = 0
        
        return (skel * 255).astype(np.uint8)

    def _detect_nodes(self, skeleton: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        检测骨架中的端点和分叉点。
        
        通过3x3邻域分析（排除自身）：
        - 端点：只有1个8邻域邻居
        - 分叉点：3个或更多8邻域邻居
        - 交叉点：4个8邻域邻居
        """
        h, w = skeleton.shape
        binary = (skeleton > 0).astype(np.uint8)

        endpoints = []
        junctions = []

        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if binary[y, x] == 0:
                    continue

                # 统计8邻域非零邻居数
                n_count = 0
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dy == 0 and dx == 0:
                            continue
                        if binary[y + dy, x + dx] > 0:
                            n_count += 1

                if n_count == 1:
                    endpoints.append((y, x))
                elif n_count >= 3:
                    junctions.append((y, x))

        endpoints = np.array(endpoints, dtype=np.int32) if endpoints else np.zeros((0, 2), dtype=np.int32)
        junctions = np.array(junctions, dtype=np.int32) if junctions else np.zeros((0, 2), dtype=np.int32)

        all_nodes = np.vstack([endpoints, junctions]) if len(endpoints) > 0 and len(junctions) > 0 else (
            endpoints if len(endpoints) > 0 else junctions
        )

        return all_nodes, endpoints, junctions

    def _segment_strokes(self, skeleton: np.ndarray,
                         endpoints: np.ndarray,
                         junctions: np.ndarray,
                         verbose: bool = False) -> List[StrokeSegment]:
        """
        从骨架中分割笔画段。
        
        改进策略：
        1. 从端点出发，沿骨架追踪到下一个节点（端点或分叉点）
        2. 合并被分叉点截断的共线段（方向一致+端点接近）
        3. 过滤毛刺（过短的笔画段）
        """
        h, w = skeleton.shape
        visited = np.zeros((h, w), dtype=bool)
        skel = (skeleton > 0).astype(np.uint8)

        node_set = set()
        for pt in endpoints:
            node_set.add((int(pt[0]), int(pt[1])))
        for pt in junctions:
            node_set.add((int(pt[0]), int(pt[1])))

        neighbors_8 = [(-1, -1), (-1, 0), (-1, 1),
                       (0, -1),           (0, 1),
                       (1, -1),  (1, 0),  (1, 1)]

        raw_segments = []

        for ey, ex in endpoints:
            visited[ey, ex] = True

            # 找到唯一的出方向
            start_ny, start_nx = None, None
            for dy, dx in neighbors_8:
                ny, nx = ey + dy, ex + dx
                if 0 <= ny < h and 0 <= nx < w:
                    if skel[ny, nx] > 0:
                        start_ny, start_nx = ny, nx
                        break

            if start_ny is None:
                continue

            # 追踪
            path = [(ey, ex), (start_ny, start_nx)]
            visited[start_ny, start_nx] = True
            curr_y, curr_x = start_ny, start_nx

            while True:
                # 到达另一个端点就停
                if (curr_y, curr_x) in node_set and len(path) > 2:
                    break

                found_next = False
                for dy, dx in neighbors_8:
                    ny, nx = curr_y + dy, curr_x + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        if skel[ny, nx] > 0 and not visited[ny, nx]:
                            visited[ny, nx] = True
                            path.append((ny, nx))
                            curr_y, curr_x = ny, nx
                            found_next = True
                            break

                if not found_next:
                    break

            if len(path) < self.min_stroke_length:
                continue

            points = np.array([(x, y) for y, x in path], dtype=np.float32)
            raw_segments.append(points)

        # 合并共线段
        strokes = self._merge_colinear(raw_segments, node_set)

        # 构建StrokeSegment
        result = []
        for sid, points in enumerate(strokes):
            start_pt = points[0]
            end_pt = points[-1]
            diffs = np.diff(points, axis=0)
            length = np.sum(np.sqrt(np.sum(diffs ** 2, axis=1)))
            vec = end_pt - start_pt
            direction = float(np.arctan2(vec[1], vec[0]))
            thickness = self._estimate_thickness(points, skeleton)

            stroke = StrokeSegment(
                id=sid,
                points=points,
                start=start_pt,
                end=end_pt,
                direction=direction,
                length=length,
                thickness=thickness,
                stroke_type=StrokeType.HENG,
            )
            result.append(stroke)

        return result

    def _merge_colinear(self, segments: List[np.ndarray],
                        node_set: set) -> List[np.ndarray]:
        """
        合并被分叉点截断的共线段。
        
        判断标准：
        1. 两端点接近（< 8像素）
        2. 方向一致（夹角 < 30°）
        """
        if len(segments) <= 1:
            return segments

        merged = [s for s in segments]
        changed = True

        while changed:
            changed = False
            n = len(merged)
            for i in range(n):
                for j in range(i + 1, n):
                    si, sj = merged[i], merged[j]

                    # 检查端点是否接近
                    d_ee = np.linalg.norm(si[-1] - sj[-1])
                    d_es = np.linalg.norm(si[-1] - sj[0])
                    d_se = np.linalg.norm(si[0] - sj[-1])
                    d_ss = np.linalg.norm(si[0] - sj[0])

                    min_dist = min(d_ee, d_es, d_se, d_ss)
                    if min_dist > 8:
                        continue

                    # 检查方向一致性
                    di = si[-1] - si[0]
                    dj = sj[-1] - sj[0]
                    ni, nj = np.linalg.norm(di), np.linalg.norm(dj)
                    if ni < 1 or nj < 1:
                        continue
                    cos_angle = np.dot(di, dj) / (ni * nj)
                    
                    # 允许反向（因为笔画可能被反向追踪）
                    if abs(cos_angle) < 0.866:  # cos(30°)
                        continue

                    # 合并
                    if d_ee < 8 or d_ss < 8:
                        # 同向：si + sj.reverse() 或 si.reverse() + sj
                        if d_ee < 8:
                            merged[i] = np.vstack([si, sj[::-1]])
                        else:
                            merged[i] = np.vstack([si[::-1], sj])
                    else:
                        # 首尾相接
                        if d_es < 8:
                            merged[i] = np.vstack([si, sj])
                        else:
                            merged[i] = np.vstack([sj, si])

                    merged.pop(j)
                    changed = True
                    break
                if changed:
                    break

        return merged

    def _estimate_thickness(self, points: np.ndarray, skeleton: np.ndarray) -> float:
        """估算笔画在某点的粗细"""
        # 简化：取骨架附近的笔画像素距离
        mid_idx = len(points) // 2
        mx, my = int(points[mid_idx][0]), int(points[mid_idx][1])

        # 沿法线方向搜索边缘
        dir_vec = points[-1] - points[0]
        length = np.linalg.norm(dir_vec)
        if length < 1e-6:
            return 4.0

        normal = np.array([-dir_vec[1], dir_vec[0]]) / length

        # 双向搜索
        thickness = 4.0
        for sign in [1, -1]:
            for d in range(1, 30):
                nx = int(mx + normal[0] * d)
                ny = int(my + normal[1] * d)
                if nx < 0 or nx >= skeleton.shape[1] or ny < 0 or ny >= skeleton.shape[0]:
                    break
                if skeleton[ny, nx] == 0:
                    thickness = max(thickness, d * 2)
                    break

        return thickness

    def _classify_stroke(self, stroke: StrokeSegment) -> StrokeType:
        """根据方向和形态分类笔画"""
        # 将方向归一化到 [-π/2, π/2)
        direction = stroke.direction % np.pi
        if direction > np.pi / 2:
            direction -= np.pi

        # 基于方向分类
        abs_dir = abs(direction)

        if stroke.length < 15:  # 短笔画 → 点
            return StrokeType.DIAN
        elif abs_dir < np.pi / 8:  # 接近水平 → 横
            return StrokeType.HENG
        elif abs_dir > 3 * np.pi / 8:  # 接近垂直 → 竖
            return StrokeType.SHU
        elif direction > 0:  # 正角度 → 撇（左斜）
            return StrokeType.PIE
        else:  # 负角度 → 捺（右斜）
            return StrokeType.NA

    def _build_connectivity(self, strokes: List[StrokeSegment]) -> None:
        """构建笔画之间的连接关系"""
        for i, si in enumerate(strokes):
            for j, sj in enumerate(strokes):
                if i == j:
                    continue
                # 检查起点连接
                dist_ss = np.linalg.norm(si.start - sj.start)
                dist_se = np.linalg.norm(si.start - sj.end)
                if dist_ss < 5 or dist_se < 5:
                    si.neighbors_start.append(j)
                # 检查终点连接
                dist_es = np.linalg.norm(si.end - sj.start)
                dist_ee = np.linalg.norm(si.end - sj.end)
                if dist_es < 5 or dist_ee < 5:
                    si.neighbors_end.append(j)


# ============================================================
# 卦象驱动的笔画顺序推理
# ============================================================

class HexagramStrokeOrder:
    """
    基于爻位关系推理笔画书写顺序。

    核心思想：
    - 传统书法笔画顺序遵循"从上到下、从左到右、先横后竖、先撇后捺"等规则
    - 这些规则可以映射为爻位关系：
        · 上爻尊→下爻卑 → 从上到下
        · 阳气左→阴气右 → 从左到右
        · 当位优先 → 先主笔后辅笔
        · 乘承关系 → 先承后乘（先奠定基础再构建上层）

    爻位关系在此发挥真正作用——不是静态分类，而是动态规划因果序列！
    """

    # 笔画类型→卦象映射
    STROKE_TO_TRIGRAM = {
        StrokeType.HENG: '乾',   # 横平竖直→刚健
        StrokeType.SHU: '艮',    # 竖→沉稳
        StrokeType.PIE: '震',    # 撇→动态
        StrokeType.NA: '坤',     # 捺→铺展
        StrokeType.DIAN: '兑',   # 点→轻灵
        StrokeType.GOU: '坎',    # 钩→险转
        StrokeType.ZHE: '巽',    # 折→深入转向
        StrokeType.ARC: '离',    # 弧→明快
    }

    # 卦象书写优先级（数字化）
    TRIGRAM_PRIORITY = {
        '乾': 1,   # 横 → 最先
        '艮': 2,   # 竖 → 其次
        '震': 3,   # 撇
        '坤': 4,   # 捺
        '兑': 5,   # 点
        '坎': 6,   # 钩
        '巽': 7,   # 折
        '离': 8,   # 弧
    }

    def determine_order(self, decomposition: CharacterDecomposition,
                       trigram_analysis: Dict) -> List[int]:
        """
        根据卦象推理笔画书写顺序。

        算法：
        1. 每个笔画映射到主导卦象
        2. 按卦象优先级初排
        3. 应用爻位关系约束（从上到下、从左到右）
        4. 输出最终顺序

        Args:
            decomposition: 笔画分解结果
            trigram_analysis: 视觉YLYW的卦象分析结果

        Returns:
            笔画id的排序列表
        """
        strokes = decomposition.strokes
        if len(strokes) <= 1:
            return [s.id for s in strokes]

        # Step 1: 每个笔画映射卦象
        stroke_trigrams = {}
        for s in strokes:
            stroke_trigrams[s.id] = self.STROKE_TO_TRIGRAM.get(s.stroke_type, '离')

        # Step 2: 基于空间关系 + 卦象优先级排序
        # 排序键：(y位置/从上到下, x位置/从左到右, 卦象优先级)
        scored_strokes = []
        for s in strokes:
            # y坐标（row）→ 从上到下
            y_score = s.start[1]  # y坐标越小越靠上

            # x坐标（col）→ 从左到右
            x_score = s.start[0]  # x坐标越小越靠左

            # 卦象优先级
            tri_priority = self.TRIGRAM_PRIORITY.get(
                stroke_trigrams[s.id], 5
            )

            # 长度权重（长笔画通常先写）
            length_score = -s.length

            scored_strokes.append({
                'id': s.id,
                'y': y_score,
                'x': x_score,
                'priority': tri_priority,
                'length': length_score,
                'trigram': stroke_trigrams[s.id],
            })

        # Step 3: 综合排序
        # 主要按y（从上到下），次要按x（从左到右），微调按卦象优先级
        scored_strokes.sort(key=lambda s: (
            int(s['y'] / 30),      # 粗粒度：每30像素为一个层级
            int(s['x'] / 30),
            s['priority'],
            s['length'],
        ))

        order = [s['id'] for s in scored_strokes]

        # Step 4: 爻位关系微调
        # 处理"先横后竖"的特殊规则：如果横和竖的y接近，横优先
        order = self._apply_heng_before_shu(order, strokes)
        # 处理"先撇后捺"：如果撇和捺的位置接近，撇优先
        order = self._apply_pie_before_na(order, strokes)

        return order

    def _apply_heng_before_shu(self, order: List[int],
                                strokes: List[StrokeSegment]) -> List[int]:
        """应用'先横后竖'规则"""
        # 查找所有横和竖
        heng_ids = {s.id for s in strokes if s.stroke_type == StrokeType.HENG}
        shu_ids = {s.id for s in strokes if s.stroke_type == StrokeType.SHU}

        # 如果横和竖相邻且竖在横前面，调换
        for i in range(len(order) - 1):
            if (order[i] in shu_ids and order[i+1] in heng_ids):
                # 检查空间上是否相关（位置接近）
                si = strokes[order[i]]
                sj = strokes[order[i+1]]
                if abs(si.start[0] - sj.start[0]) < 30:  # x接近
                    order[i], order[i+1] = order[i+1], order[i]

        return order

    def _apply_pie_before_na(self, order: List[int],
                              strokes: List[StrokeSegment]) -> List[int]:
        """应用'先撇后捺'规则"""
        pie_ids = {s.id for s in strokes if s.stroke_type == StrokeType.PIE}
        na_ids = {s.id for s in strokes if s.stroke_type == StrokeType.NA}

        for i in range(len(order) - 1):
            if (order[i] in na_ids and order[i+1] in pie_ids):
                si = strokes[order[i]]
                sj = strokes[order[i+1]]
                if abs(si.start[1] - sj.start[1]) < 30:  # y接近
                    order[i], order[i+1] = order[i+1], order[i]

        return order


# ============================================================
# 笔画→轨迹生成
# ============================================================

class StrokeToTrajectory:
    """
    将笔画骨架转换为机械臂书写轨迹。

    这是"卦象→笔法→轨迹"的完整链路。
    """

    def __init__(self, paper_size: float = 0.3, image_size: int = 256):
        self.paper_size = paper_size
        self.image_size = image_size

    def image_to_world(self, px: float, py: float) -> Tuple[float, float]:
        wx = (px / self.image_size - 0.5) * self.paper_size
        wy = (0.5 - py / self.image_size) * self.paper_size
        return wx, wy

    def generate(self, stroke: StrokeSegment,
                 brush_method: str = None,
                 yao_params: Dict = None) -> Dict:
        """
        从笔画段生成机械臂轨迹

        Args:
            stroke: 笔画段
            brush_method: 笔法（None则自动选择）
            yao_params: 六爻参数

        Returns:
            dict: 含world_trajectory、pressures、brush_method
        """
        if brush_method is None:
            # 根据笔画类型自动选择笔法
            brush_method = self._auto_select_brush(stroke)

        if yao_params is None:
            yao_params = {
                'speed_consistency': 0.5,
                'press_amplitude': 0.5,
                'curvature_factor': 0.5,
            }

        # 骨架点→世界坐标轨迹
        world_points = []
        for px, py in stroke.points:
            wx, wy = self.image_to_world(px, py)
            world_points.append([wx, wy])

        trajectory = np.array(world_points)

        # 压力序列（基于笔画类型+粗细）
        thickness_factor = min(1.5, max(0.5, stroke.thickness / 8.0))
        n = len(trajectory)
        pressures = self._generate_pressure_profile(n, thickness_factor, yao_params)

        return {
            'image_points': stroke.points,
            'world_trajectory': trajectory,
            'pressures': pressures,
            'brush_method': brush_method,
            'stroke_type': stroke.stroke_type.value,
            'length': stroke.length,
            'thickness': stroke.thickness,
        }

    def _auto_select_brush(self, stroke: StrokeSegment) -> str:
        """根据笔画类型自动选择笔法"""
        # 映射到对应的卦象→笔法
        trigram = HexagramStrokeOrder.STROKE_TO_TRIGRAM.get(stroke.stroke_type, '离')

        from stroke_ylyw import TRIGRAM_TO_BRUSH
        brush = TRIGRAM_TO_BRUSH.get(trigram, 'center_tip')
        return brush if isinstance(brush, str) else brush.value

    def _generate_pressure_profile(self, n_points: int,
                                    thickness_factor: float,
                                    yao_params: Dict) -> np.ndarray:
        """生成压力曲线"""
        press_amplitude = yao_params.get('press_amplitude', 0.5)

        base_pressure = 0.4 + 0.2 * thickness_factor
        pressures = np.ones(n_points) * base_pressure

        # 起笔轻→行笔重→收笔轻
        start_ramp = min(20, n_points // 4)
        end_ramp = min(20, n_points // 4)
        pressures[:start_ramp] = np.linspace(base_pressure * 0.3, base_pressure, start_ramp)
        pressures[-end_ramp:] = np.linspace(base_pressure, base_pressure * 0.2, end_ramp)

        # 中间压力波动
        mid_variation = press_amplitude * 0.3 * np.sin(np.linspace(0, 2 * np.pi, n_points))
        pressures += mid_variation * base_pressure
        pressures = np.clip(pressures, 0.05, 1.0)

        return pressures


# ============================================================
# 自主书写YLYW（集成类）
# ============================================================

class AutonomousCalligraphyYLYW:
    """
    自主书法YLYW：从字帖图像到完整书写计划，无需预定义模板。

    流程：
    字帖图像 → 骨架提取 → 笔画分割 → 笔画分类
    → 视觉YLYW分析(结构卦象)
    → 卦象驱动笔画排序
    → 笔画→轨迹生成
    → 知几学习闭环
    """

    def __init__(self):
        self.skeleton_extractor = StrokeSkeletonExtractor()
        self.order_planner = HexagramStrokeOrder()
        self.trajectory_generator = StrokeToTrajectory()

        # 延迟导入避免循环
        from visual_calligraphy import CalligraphyVisualYLYW
        self.visual_ylyw = CalligraphyVisualYLYW()

    def decompose_and_plan(self, image: np.ndarray,
                           verbose: bool = False) -> CharacterDecomposition:
        """
        完整的自主分解+规划流程

        Args:
            image: 字帖图像
            verbose: 详细输出

        Returns:
            CharacterDecomposition (含完整书写计划)
        """
        if verbose:
            print("=" * 60)
            print("  YLYW 自主笔画分解与规划")
            print("=" * 60)

        # Step 1: 笔画骨架提取
        if verbose:
            print("\n[Step 1] 笔画骨架提取...")
        decomposition = self.skeleton_extractor.extract(image, verbose=verbose)

        if verbose:
            print(f"  提取 {len(decomposition.strokes)} 个笔画段")

        # Step 2: 视觉YLYW结构分析
        if verbose:
            print("\n[Step 2] 结构卦象分析...")
        perception = self.visual_ylyw.perceive(image, verbose=False)

        trigram_analysis = {
            'dominant_trigram': perception.dominant_trigram,
            'dominant_score': perception.dominant_score,
            'hexagram_name': perception.hexagram_name,
            'trigram_memberships': perception.trigram_memberships,
            'yao_features': perception.yao_features,
        }
        decomposition.trigram_analysis = trigram_analysis

        if verbose:
            print(f"  主导卦象: {perception.dominant_trigram} "
                  f"({perception.hexagram_name})")

        # Step 3: 卦象驱动笔画排序
        if verbose:
            print("\n[Step 3] 卦象驱动笔画排序...")
        stroke_order = self.order_planner.determine_order(
            decomposition, trigram_analysis
        )
        decomposition.stroke_order = stroke_order

        if verbose:
            stroke_names = [
                decomposition.strokes[oid].stroke_type.value
                for oid in stroke_order
            ]
            print(f"  笔画顺序: {' → '.join(stroke_names)}")

        # Step 4: 笔画→轨迹生成
        if verbose:
            print("\n[Step 4] 笔画→轨迹生成...")

        yao_params = {
            'speed_consistency': float(perception.yao_features[0]),
            'press_amplitude': float(perception.yao_features[1]),
            'curvature_factor': float(perception.yao_features[2]),
        }

        writing_plan = {
            'strokes': [],
            'total_points': 0,
            'stroke_order': stroke_order,
            'dominant_trigram': perception.dominant_trigram,
        }

        for oid in stroke_order:
            stroke = decomposition.strokes[oid]
            trajectory = self.trajectory_generator.generate(
                stroke, yao_params=yao_params
            )
            writing_plan['strokes'].append(trajectory)
            writing_plan['total_points'] += len(trajectory['world_trajectory'])

        decomposition.writing_plan = writing_plan

        if verbose:
            print(f"  生成 {len(writing_plan['strokes'])} 条轨迹")
            print(f"  总轨迹点: {writing_plan['total_points']}")

        return decomposition


# ============================================================
# 可视化
# ============================================================

def visualize_decomposition(decomposition: CharacterDecomposition,
                            output_path: str = None) -> np.ndarray:
    """可视化笔画分解结果"""
    h, w = decomposition.skeleton.shape[:2]
    canvas = np.ones((h, w, 3), dtype=np.uint8) * 255

    # 颜色表（每笔画不同颜色）
    colors = [
        (255, 0, 0),   # 红
        (0, 0, 255),   # 蓝
        (0, 180, 0),   # 绿
        (255, 128, 0), # 橙
        (128, 0, 128), # 紫
        (0, 180, 180), # 青
        (180, 180, 0), # 黄
        (180, 0, 180), # 品红
        (0, 100, 100), # 深青
        (100, 100, 0), # 橄榄
        (100, 0, 100), # 深紫
        (0, 0, 100),   # 深蓝
    ]

    # 书写顺序标注
    for rank, oid in enumerate(decomposition.stroke_order):
        stroke = decomposition.strokes[oid]
        color = colors[rank % len(colors)]

        # 绘制笔画点
        for px, py in stroke.points.astype(int):
            if 0 <= px < w and 0 <= py < h:
                canvas[py, px] = color

        # 绘制起点（白色圆）
        sx, sy = int(stroke.start[0]), int(stroke.start[1])
        if 0 <= sx < w and 0 <= sy < h:
            cv2.circle(canvas, (sx, sy), 5, (0, 0, 0), -1)
            cv2.putText(canvas, str(rank + 1), (sx + 8, sy - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    if output_path:
        cv2.imwrite(output_path, canvas)

    return canvas


# ============================================================
# 测试
# ============================================================

def test_decomposition():
    """测试笔画自主分解"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from learning_loop import _generate_target_calligraphy

    print("=" * 60)
    print("  YLYW 自主笔画分解测试")
    print("=" * 60)

    ylyw = AutonomousCalligraphyYLYW()

    for char in ['大', '人', '中', '山']:
        print(f"\n{'#'*50}")
        print(f"### 汉字: 「{char}」###")

        # 生成字帖图像
        target = _generate_target_calligraphy(char)

        # 自主分解+规划
        decomp = ylyw.decompose_and_plan(target, verbose=True)

        # 可视化
        output_dir = Path(__file__).parent / 'output' / 'decomposition'
        output_dir.mkdir(parents=True, exist_ok=True)
        vis_path = output_dir / f'{char}_decomposed.png'
        visualize_decomposition(decomp, str(vis_path))
        print(f"\n  可视化: {vis_path}")

    print(f"\n✅ 测试完成！")


if __name__ == '__main__':
    test_decomposition()
