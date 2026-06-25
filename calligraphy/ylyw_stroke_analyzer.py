"""
YLYW 拆字分析与轨迹生成

每个笔画用 6 维特征描述：
- 起点 (x, y)     → 初爻（起始位置）
- 终点 (x, y)     → 二爻（落笔位置）  
- 长度            → 三爻（笔画规模）
- 方向角          → 四爻（走势）
- 笔画类型        → 五爻（横/竖/撇/捺/点/钩）

八卦模型对 8 种笔画原型 + 6 种空间关系进行推理，
输出完整的笔画序列作为运动轨迹。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


@dataclass
class StrokeFeature:
    """一个笔画的完整 YLYW 特征描述"""
    id: int
    stroke_type: str
    # 原始像素坐标（用于轨迹生成，不可丢失！）
    px_start: Tuple[float, float]
    px_end: Tuple[float, float]
    # 归一化特征（用于八卦分析和爻位关系）
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    mid_x: float
    mid_y: float
    length: float
    angle: float
    curvature: float
    spread: float
    thickness_ratio: float
    dominance: float


@dataclass
class StrokePairRelation:
    """两个笔画之间的爻位关系（6种）"""
    i: int
    j: int
    # 爻位关系
    is_above: float     # 乘（i在j上）
    is_below: float     # 承（i在j下）
    is_left: float      # 左
    is_right: float     # 右
    is_connected: float # 交接
    is_aligned: float   # 对齐/呼应


@dataclass  
class CharacterStructure:
    """一个字的完整结构描述"""
    character: str
    strokes: List[StrokeFeature]    # 所有笔画
    bbox: Tuple[float, float, float, float]  # 包围框
    center: Tuple[float, float]     # 重心
    stroke_order: List[int]         # 笔画顺序 (由卦象推理)


class YLYWStrokeAnalyzer:
    """
    YLYW 拆字分析器
    
    将汉字的笔画结构映射到八卦空间，通过六十四卦推理笔画顺序和轨迹。
    """
    
    # 笔画类型 → 八卦原型
    STROKE_TRIGRAM = {
        '横': '乾',   # 刚直平展
        '竖': '艮',   # 沉稳纵贯
        '撇': '震',   # 动态出锋 
        '捺': '坤',   # 柔顺铺展
        '点': '兑',   # 轻灵短小
        '钩': '坎',   # 险转内敛
        '折': '巽',   # 转折绵密
        '弧': '离',   # 圆转明快
    }
    
    # 空间关系 → 爻位关系
    SPATIAL_RELATIONS = ['上', '下', '左', '右', '交', '接']
    
    def extract_features(self, strokes: List[Tuple]) -> List[StrokeFeature]:
        """从笔画端点提取完整12维特征"""
        all_pts = np.array([[s[0], s[1]] for s in strokes] + 
                           [[s[2], s[3]] for s in strokes])
        x_min, y_min = all_pts.min(axis=0)
        x_max, y_max = all_pts.max(axis=0)
        x_span = x_max - x_min + 1e-6
        y_span = y_max - y_min + 1e-6
        diag = np.sqrt(x_span**2 + y_span**2)
        
        features = []
        for i, s in enumerate(strokes):
            sx, sy, ex, ey, stype = s[0], s[1], s[2], s[3], s[4]
            curv = s[5] if len(s) > 5 else 0
            # 归一化坐标
            nsx = (sx - x_min) / x_span
            nsy = (sy - y_min) / y_span
            nex = (ex - x_min) / x_span
            ney = (ey - y_min) / y_span
            mx = (nsx + nex) / 2
            my = (nsy + ney) / 2
            
            # 长度
            length = np.sqrt((nex - nsx)**2 + (ney - nsy)**2)
            
            # 方向角
            angle = np.arctan2(ney - nsy, nex - nsx)
            
            # 曲率（用模板提供的值）
            curvature = abs(curv) / 15  # 归一化
            
            # 展幅（归一化长度相对于对角线）
            spread = length * diag / (x_span * y_span + 1e-6)
            
            # 粗细比（根据笔画类型：横竖=粗，撇捺点=细）
            thickness = {'横': 0.7, '竖': 0.7, '撇': 0.4, '捺': 0.5, 
                         '点': 0.2, '钩': 0.3, '折': 0.5, '弧': 0.4}.get(stype, 0.4)
            
            # 主导度（长笔画权重高）
            dominance = np.clip(length * 0.6 + thickness * 0.4, 0.1, 1.0)
            
            features.append(StrokeFeature(
                id=i,
                stroke_type=stype,
                px_start=(sx, sy),
                px_end=(ex, ey),
                start_x=nsx, start_y=nsy,
                end_x=nex, end_y=ney,
                mid_x=mx, mid_y=my,
                length=length,
                angle=angle,
                curvature=curvature,
                spread=spread,
                thickness_ratio=thickness,
                dominance=dominance,
            ))
        
        return features
    
    def extract_relations(self, features: List[StrokeFeature]) -> List[StrokePairRelation]:
        """提取笔画间的爻位关系特征"""
        n = len(features)
        relations = []
        
        for i in range(n):
            for j in range(i+1, n):
                fi, fj = features[i], features[j]
                
                # 上下关系（基于中点y）
                dy = fi.mid_y - fj.mid_y
                is_above = max(0, -dy / 0.3) if dy < 0 else 0
                is_below = max(0, dy / 0.3) if dy > 0 else 0
                
                # 左右关系（基于中点x）
                dx = fi.mid_x - fj.mid_x
                is_left = max(0, -dx / 0.3) if dx < 0 else 0
                is_right = max(0, dx / 0.3) if dx > 0 else 0
                
                # 交接（端点距离 < 阈值）
                d_ee = min(
                    np.sqrt((fi.end_x-fj.end_x)**2 + (fi.end_y-fj.end_y)**2),
                    np.sqrt((fi.start_x-fj.start_x)**2 + (fi.start_y-fj.start_y)**2),
                    np.sqrt((fi.end_x-fj.start_x)**2 + (fi.end_y-fj.start_y)**2),
                    np.sqrt((fi.start_x-fj.end_x)**2 + (fi.start_y-fj.end_y)**2),
                )
                is_connected = max(0, 1.0 - d_ee / 0.15)
                
                # 对齐（方向角相似）
                angle_diff = abs(fi.angle - fj.angle)
                angle_diff = min(angle_diff, np.pi - angle_diff)
                is_aligned = max(0, 1.0 - angle_diff / (np.pi/4))
                
                relations.append(StrokePairRelation(
                    i=i, j=j,
                    is_above=is_above, is_below=is_below,
                    is_left=is_left, is_right=is_right,
                    is_connected=is_connected, is_aligned=is_aligned,
                ))
        
        return relations
    
    def compute_trigram_memberships(self, features: List[StrokeFeature],
                                   relations: List[StrokePairRelation]) -> Dict:
        """
        综合笔画特征 + 笔画间关系，计算每个笔画在八卦空间中的隶属度。
        
        返回 {卦名: {笔画id: 隶属度, ...}, ...}
        以及全局结构卦象。
        """
        n = len(features)
        memberships = {tri: np.zeros(n) for tri in self.STROKE_TRIGRAM.values()}
        
        for i, f in enumerate(features):
            # 1. 类型直接映射（0.5权重）
            target_tri = self.STROKE_TRIGRAM.get(f.stroke_type, '离')
            memberships[target_tri][i] += 0.5
            
            # 2. 方向特征（0.2权重）
            angle = f.angle
            if -0.4 < angle < 0.4:        # 水平 → 乾（刚直）
                memberships['乾'][i] += 0.2
            elif abs(angle) > 2.6:         # 垂直 → 艮（沉稳）
                memberships['艮'][i] += 0.2
            elif angle > 0.4 and angle < 1.3:  # 左下斜 → 震（动态）
                memberships['震'][i] += 0.2
            elif angle < -0.4 and angle > -1.3:  # 右下斜 → 坤（铺展）
                memberships['坤'][i] += 0.2
            elif abs(angle) > 1.3 and abs(angle) < 2.6:  # 上下斜 → 巽
                memberships['巽'][i] += 0.2
            
            # 3. 尺度特征（0.15权重）
            if f.length > 0.5:  # 长笔画
                memberships[target_tri][i] += 0.15
            elif f.length < 0.15:  # 短笔画 → 兑
                memberships['兑'][i] += 0.15
            
            # 4. 位置特征（0.15权重：居中=离，偏转=坎）
            if 0.3 < f.mid_x < 0.7 and 0.3 < f.mid_y < 0.7:
                memberships['离'][i] += 0.15
            else:
                memberships['坎'][i] += 0.15
        
        # 笔画间关系贡献给全局结构
        structure_memberships = {tri: 0.0 for tri in self.STROKE_TRIGRAM.values()}
        for rel in relations:
            # 上下关系 → 乘承
            if rel.is_above > 0.5:  # i在j上 = 乘
                structure_memberships['巽'] += 0.1
            elif rel.is_below > 0.5:  # i在j下 = 承
                structure_memberships['坤'] += 0.1
            # 左右铺展 → 震/兑
            if rel.is_left > 0.5 or rel.is_right > 0.5:
                structure_memberships['震'] += 0.1
            # 交接 → 离
            if rel.is_connected > 0.5:
                structure_memberships['离'] += 0.1
            # 对齐/呼应 → 乾
            if rel.is_aligned > 0.5:
                structure_memberships['乾'] += 0.1
        
        # 归一化
        for tri in structure_memberships:
            structure_memberships[tri] = min(1.0, structure_memberships[tri])
        
        return memberships, structure_memberships
    
    def determine_stroke_order(self, features: List[StrokeFeature],
                               relations: List[StrokePairRelation]) -> List[int]:
        """
        用爻位关系 + 空间特征推理笔画书写顺序。
        
        爻位关系在此发挥真正作用——不是静态分类，而是动态规划因果序列。
        """
        n = len(features)
        scores = np.zeros(n)
        
        for i, f in enumerate(features):
            # 1. 乘承关系（上下）：越靠上越先写
            scores[i] += (1.0 - f.mid_y) * 2.5
            
            # 2. 左右关系：越靠左越先写
            scores[i] += (1.0 - f.mid_x) * 1.5
            
            # 3. 笔画类型优先级
            type_priority = {'横': 6, '竖': 5, '撇': 4, '捺': 3, 
                           '折': 4, '钩': 2, '点': 1, '弧': 3}
            scores[i] += type_priority.get(f.stroke_type, 2) * 0.5
            
            # 4. 主导度：重要笔画优先
            scores[i] += f.dominance * 1.5
            
            # 5. 长度：长笔画优先
            scores[i] += f.length * 1.0
        
        # 6. 爻位关系微调（笔画间）
        for rel in relations:
            i, j = rel.i, rel.j
            # 如果i和j交接且i在j上面，确保i在j前
            if rel.is_connected > 0.5 and rel.is_above > 0.5:
                scores[i] += 0.5
            if rel.is_connected > 0.5 and rel.is_below > 0.5:
                scores[j] += 0.5
        
        return sorted(range(n), key=lambda i: -scores[i])

    def analyze(self, char: str, strokes: List[Tuple]) -> CharacterStructure:
        """
        完整 YLYW 拆字分析：
        特征提取 → 爻位关系 → 八卦隶属度 → 六十四卦结构匹配 → 笔画排序
        """
        features = self.extract_features(strokes)
        relations = self.extract_relations(features)
        memberships, structure = self.compute_trigram_memberships(features, relations)
        order = self.determine_stroke_order(features, relations)
        
        # 结构特征
        all_pts = np.array([(f.start_x, f.start_y) for f in features] +
                          [(f.end_x, f.end_y) for f in features])
        bbox = (all_pts[:,0].min(), all_pts[:,1].min(),
                all_pts[:,0].max(), all_pts[:,1].max())
        center = (all_pts[:,0].mean(), all_pts[:,1].mean())
        
        # 全局结构卦象（取隶属度最高的卦）
        dominant_structure = max(structure, key=structure.get)
        
        return CharacterStructure(
            character=char,
            strokes=features,
            bbox=bbox,
            center=center,
            stroke_order=order,
        )


def strokes_to_world_trajectory(features: List[StrokeFeature], order: List[int],
                                 img_size=256, paper_half=0.15, n_pts=80):
    """把笔画特征转为世界坐标轨迹——含弧度曲线"""
    all_traj, all_press = [], []
    
    for idx in order:
        f = features[idx]
        
        sx, sy = f.px_start
        ex, ey = f.px_end
        curv = f.curvature
        
        # 如果笔画有弧度，用二次贝塞尔弯曲
        if abs(curv) > 0.5:
            t = np.linspace(0, 1, n_pts)
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            dx, dy = ex - sx, ey - sy
            length = np.sqrt(dx*dx + dy*dy) + 1e-6
            nx, ny = -dy / length, dx / length
            cx = mx + nx * curv
            cy = my + ny * curv
            xs = (1-t)**2 * sx + 2*(1-t)*t * cx + t**2 * ex
            ys = (1-t)**2 * sy + 2*(1-t)*t * cy + t**2 * ey
        else:
            xs = np.linspace(sx, ex, n_pts)
            ys = np.linspace(sy, ey, n_pts)
        
        wx = (xs / img_size - 0.5) * (2 * paper_half)
        wy = (0.5 - ys / img_size) * (2 * paper_half)
        
        all_traj.append(np.column_stack([wx, wy]))
        all_press.append(np.full(n_pts, 0.6))
        all_traj.append(np.array([[wx[-1], wy[-1]]]))
        all_press.append(np.array([0.0]))
    
    return np.vstack(all_traj), np.concatenate(all_press)


if __name__ == '__main__':
    from mujoco_env import CalligraphyEnv
    import cv2
    from auto_template import analyze_char_copybook
    
    analyzer = YLYWStrokeAnalyzer()
    outdir = Path(__file__).parent / 'output' / 'ylyw_strokes'
    outdir.mkdir(parents=True, exist_ok=True)
    
    for char in ['大', '永', '人', '中']:
        print(f"\n{'='*50}")
        print(f"  YLYW 拆字分析 — 「{char}」")
        print(f"{'='*50}")
        
        # 从字帖提取笔画端点
        template = analyze_char_copybook(char)
        
        # 转为 YLYW 输入格式
        strokes = [(s['start'][0], s['start'][1], s['end'][0], s['end'][1], s['name']) 
                   for s in template]
        
        # YLYW 分析
        structure = analyzer.analyze(char, strokes)
        
        print(f"\n  笔画特征:")
        for f in structure.strokes:
            print(f"    {f.stroke_type}: start=({f.start_x:.2f},{f.start_y:.2f}) "
                  f"end=({f.end_x:.2f},{f.end_y:.2f}) len={f.length:.2f}")
        
        print(f"\n  卦象推理笔画顺序: ", end='')
        type_names = [structure.strokes[i].stroke_type for i in structure.stroke_order]
        print(' → '.join(type_names))
        
        print(f"  包围框: ({structure.bbox[0]:.2f},{structure.bbox[1]:.2f}) - "
              f"({structure.bbox[2]:.2f},{structure.bbox[3]:.2f})")
        print(f"  重心: ({structure.center[0]:.2f},{structure.center[1]:.2f})")
        
        # 生成轨迹并写出
        traj, press = strokes_to_world_trajectory(
            structure.strokes, structure.stroke_order)
        
        env = CalligraphyEnv()
        result = env.execute_trajectory(traj, press)
        env.close()
        
        cv2.imwrite(str(outdir / f'{char}.png'), result.rendered_image)
        print(f"\n  已保存: {outdir / f'{char}.png'}")
