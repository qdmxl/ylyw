#!/usr/bin/env python3
"""
YLYW 书法完整闭环 — 拆字分析 + 规则库执行 + 骨架评价 + 知几学习

完整流程：
1. 观帖：字帖 → 自动笔画分析 → 12维特征 → 八卦隶属度 → 爻位关系
2. 规划：规则库 → 每个笔画的笔法/压力/速度/起收笔指令
3. 执行：生成轨迹 → 写出
4. 自省：骨架相似度评价（重叠率+倒角距离）
5. 精进：爻位级诊断 → 定向修正笔画参数 → 重写

每轮迭代记录：
- 骨架分（越高越好）
- 倒角距离（越小越好）
- 每笔画卦象匹配度
- 爻位关系偏差
"""

import numpy as np
import cv2
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mujoco_env import CalligraphyEnv
from learning_loop import load_copybook
from ylyw_stroke_analyzer import (YLYWStrokeAnalyzer, StrokeFeature, 
                                   strokes_to_world_trajectory)
from manual_templates import get_strokes
from calligraphy_rules import CalligraphyRuleBase
from eval_skeleton import evaluate_similarity


class CalligraphyLearningLoop:
    """YLYW 书法知几学习闭环"""
    
    def __init__(self, output_dir='output/closed_loop'):
        self.analyzer = YLYWStrokeAnalyzer()
        self.rulebase = CalligraphyRuleBase()
        self.env = CalligraphyEnv()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 学习状态
        self.iteration = 0
        self.history = []
    
    def observe(self, char):
        """观帖：用人工标注的精确笔画端点+弧度"""
        target_img = load_copybook(char)
        raw_strokes = get_strokes(char)
        if not raw_strokes:
            raise ValueError(f"无人工模板: {char}")
        # 提取笔画数据 (x1, y1, x2, y2, type, curvature)
        strokes = []
        for s in raw_strokes:
            if len(s) >= 4:
                strokes.append((s[1][0], s[1][1], s[2][0], s[2][1], s[0], s[3]))
            else:
                strokes.append((s[1][0], s[1][1], s[2][0], s[2][1], s[0], 0))
        
        features = self.analyzer.extract_features(strokes)
        relations = self.analyzer.extract_relations(features)
        memberships, structure = self.analyzer.compute_trigram_memberships(features, relations)
        order = self.analyzer.determine_stroke_order(features, relations)
        
        # 六十四卦匹配
        upper_tri = max(structure, key=structure.get)
        avg_membership = {t: memberships[t].mean() for t in memberships}
        lower_tri = max(avg_membership, key=avg_membership.get)
        hex_name = self.rulebase.get_rule_by_trigrams(upper_tri, lower_tri).description if hasattr(self.rulebase, 'get_rule_by_trigrams') else f'{upper_tri}{lower_tri}'
        
        return {
            'target_img': target_img,
            'features': features,
            'relations': relations,
            'memberships': memberships,
            'structure': structure,
            'order': order,
            'char': char,
            'hexagram': hex_name,
            'upper_trigram': upper_tri,
            'lower_trigram': lower_tri,
        }
    
    def plan(self, observation):
        """规划：规则库生成执行计划"""
        plans = self.rulebase.generate_execution_plan(
            observation['features'],
            observation['memberships'],
            observation['relations']
        )
        return plans
    
    def execute(self, observation, plans):
        """执行：生成轨迹并写出——规则库指令+学习修正"""
        traj, press = strokes_to_world_trajectory(
            observation['features'],
            observation['order']
        )
        
        # 生成 thickness 数组（默认全1.0）
        thickness = np.ones(len(press))
        
        # 应用规则库指令 + 学习修正
        for plan in plans:
            sid = plan['stroke_id']
            feat = observation['features'][sid]
            n_pts = 80
            start_idx = sid * (n_pts + 1)
            end_idx = start_idx + n_pts
            if end_idx <= len(press):
                seg = press[start_idx:end_idx]
                thick_seg = thickness[start_idx:end_idx]
                n = len(seg)
                if n > 0:
                    n_start = max(1, n // 5)
                    n_end = max(1, n // 5)
                    # 起笔
                    seg[:n_start] = np.linspace(plan['start_pressure'], 
                                                 plan['pressure_base'], n_start)
                    # 行笔——thickness_ratio 直接控制笔触粗细
                    seg[n_start:-n_start] = plan['pressure_base'] * feat.thickness_ratio
                    # 收笔
                    seg[-n_end:] = np.linspace(plan['pressure_base'],
                                                plan['end_pressure'], n_end)
                    press[start_idx:end_idx] = np.clip(seg, 0.1, 1.0)
                    # thickness 直接用学习到的倍率
                    thick_seg[:] = feat.thickness_ratio
                    thickness[start_idx:end_idx] = thick_seg
        
        result = self.env.execute_trajectory(traj, press, thickness)
        return result.rendered_image, traj, press
    
    def evaluate(self, target_img, result_img, observation=None):
        """自省：逐笔画像素级评价"""
        # 全局评价
        _, t_bin = cv2.threshold(target_img, 128, 1, cv2.THRESH_BINARY_INV)
        _, r_bin = cv2.threshold(result_img, 128, 1, cv2.THRESH_BINARY_INV)
        
        intersection = (t_bin & r_bin).sum()
        union = (t_bin | r_bin).sum()
        iou = intersection / (union + 1e-6)
        
        target_pixels = t_bin.sum()
        coverage = intersection / (target_pixels + 1e-6)
        result_pixels = r_bin.sum()
        redundancy = 1.0 - intersection / (result_pixels + 1e-6)
        score = 0.6 * iou + 0.4 * coverage
        
        # 逐笔画评价
        per_stroke = []
        if observation is not None:
            per_stroke = self._eval_per_stroke(target_img, result_img, observation)
        
        return {
            'score': score, 'iou': iou, 'coverage': coverage, 'redundancy': redundancy,
            'per_stroke': per_stroke,
        }
    
    def _eval_per_stroke(self, target_img, result_img, observation):
        """
        逐笔画形状相似度评价——含爻位关系偏差。
        
        对每个笔画计算：
        - 长度比得分
        - 中点位置偏差（像素）
        - 方向角偏差
        - 爻位关系达标情况
        """
        per_stroke = []
        features = observation['features']
        relations = observation['relations']
        img_size = result_img.shape[1]
        _, r_bin = cv2.threshold(result_img, 128, 1, cv2.THRESH_BINARY_INV)
        
        for f in features:
            # 包围框
            margin = 20
            sx, sy = f.px_start
            ex, ey = f.px_end
            x0 = max(0, int(min(sx, ex)) - margin)
            y0 = max(0, int(min(sy, ey)) - margin)
            x1 = min(img_size, int(max(sx, ex)) + margin)
            y1 = min(img_size, int(max(sy, ey)) + margin)
            
            # 结果图像中的笔画像素
            r_patch = result_img[y0:y1, x0:x1]
            _, r_b = cv2.threshold(r_patch, 128, 1, cv2.THRESH_BINARY_INV)
            result_px = r_b.sum()
            result_len_est = result_px / 8  # 粗略长度估算
            target_px_len = f.length * img_size
            
            len_ratio = min(result_len_est / max(target_px_len, 1), 2.0)
            len_score = min(1.0, len_ratio)
            
            # 中点在包围框中是否偏了
            t_patch = target_img[y0:y1, x0:x1]
            _, t_b = cv2.threshold(t_patch, 128, 1, cv2.THRESH_BINARY_INV)
            inter = (t_b & r_b).sum()
            t_px = t_b.sum()
            local_cov = inter / (t_px + 1e-6)
            
            # 中点偏移估计（用局部重心差）
            if t_px > 5 and result_px > 5:
                ty, tx = np.where(t_b > 0)
                ry, rx = np.where(r_b > 0)
                t_cy, t_cx = ty.mean(), tx.mean()
                r_cy, r_cx = ry.mean(), rx.mean()
                offset_px = np.sqrt((t_cy-r_cy)**2 + (t_cx-r_cx)**2)
            else:
                offset_px = 0
            
            shape_score = 0.5 * len_score + 0.3 * (1.0 if local_cov > 0.3 else local_cov/0.3) + 0.2
            shape_score = min(1.0, shape_score)
            
            per_stroke.append({
                'id': f.id, 'type': f.stroke_type,
                'shape_score': shape_score, 'len_ratio': len_ratio,
                'local_coverage': local_cov, 'offset_px': offset_px,
            })
        return per_stroke
    
    def diagnose(self, observation, eval_result):
        """
        诊断：爻位关系达标情况 + 笔画相对位置偏差。
        
        用端点距离判断"接"，用中点距离判断"乘/承/左/右"。
        """
        iou = eval_result['iou']
        coverage = eval_result['coverage']
        per_stroke = eval_result.get('per_stroke', [])
        features = observation['features']
        relations = observation['relations']
        
        stroke_pos = {}
        for f in features:
            stroke_pos[f.id] = {
                'start': (f.start_x, f.start_y),
                'end': (f.end_x, f.end_y),
                'mid': (f.mid_x, f.mid_y),
                'type': f.stroke_type,
            }
        
        relation_deviations = []
        for rel in relations:
            if rel.i not in stroke_pos or rel.j not in stroke_pos:
                continue
            pi, pj = stroke_pos[rel.i], stroke_pos[rel.j]
            
            # 中点距离（用于上下左右判断）
            mid_dy = pj['mid'][1] - pi['mid'][1]
            mid_dx = pj['mid'][0] - pi['mid'][0]
            mid_dist = np.sqrt(mid_dx**2 + mid_dy**2)
            
            # 端点最小距离（用于交接判断）
            starts_dist = np.sqrt((pj['start'][0]-pi['end'][0])**2 + (pj['start'][1]-pi['end'][1])**2)
            ends_dist = np.sqrt((pj['end'][0]-pi['start'][0])**2 + (pj['end'][1]-pi['start'][1])**2)
            min_endpoint_dist = min(starts_dist, ends_dist)
            
            dev = {}
            if rel.is_above > 0.5:
                # pi在pj上方：mid_dy应该 < 0（pi的y更小）
                dev['above_dev'] = max(0, mid_dy + 0.08)  # pi应该在pj上面至少0.08
            if rel.is_left > 0.5:
                dev['left_dev'] = max(0, 0.08 - mid_dx)  # pi应该在pj左边至少0.08
            if rel.is_right > 0.5:
                dev['right_dev'] = max(0, mid_dx + 0.08)
            if rel.is_connected > 0.5:
                # 端点应该很近
                dev['connect_dev'] = max(0, min_endpoint_dist - 0.04)
            if rel.is_aligned > 0.5:
                # 方向角相似（已在extract中计算，此处用abs(dy)近似）
                dev['align_dev'] = max(0, abs(mid_dy) - 0.02)
            
            if dev:
                total_dev = sum(dev.values())
                if total_dev > 0.005:
                    relation_deviations.append({
                        'i': rel.i, 'j': rel.j,
                        'total_dev': total_dev,
                        'details': dev,
                    })
        
        # 找最严重的爻位偏差
        worst_rel = max(relation_deviations, key=lambda r: r['total_dev']) if relation_deviations else None
        
        # 判断
        if iou > 0.35 and coverage > 0.5 and (worst_rel is None or worst_rel['total_dev'] < 0.02):
            issue = '良好'
        elif worst_rel:
            fi, fj = features[worst_rel['i']], features[worst_rel['j']]
            issue = f'{fi.stroke_type}↔{fj.stroke_type}爻位偏差{worst_rel["total_dev"]:.3f}'
        elif coverage < 0.3:
            issue = '覆盖率不足'
        else:
            issue = '需微调'
        
        return {
            'iou': iou, 'coverage': coverage,
            'score': eval_result['score'],
            'need_improvement': iou < 0.4 or (worst_rel and worst_rel['total_dev'] > 0.01),
            'main_issue': issue,
            'per_stroke': per_stroke,
            'relation_deviations': relation_deviations,
            'worst_relation': worst_rel,
        }
    
    def learn(self, observation, diagnosis, step_size=0.05):
        """
        精进：位移驱动位置修正 + 爻位关系诊断展示。
        
        策略：
        - 检测爻位偏差（诊断用途，向用户展示"哪两笔画关系不对"）
        - 实际修正用绝对位移量（向字帖重心方向移动）
        - 修正量受爻位关系约束（交接关系下的笔画移动幅度减半）
        """
        if not diagnosis['need_improvement']:
            return False
        
        features = observation['features']
        per_stroke = diagnosis.get('per_stroke', [])
        rel_devs = diagnosis.get('relation_deviations', [])
        coverage = diagnosis['coverage']
        iou = diagnosis['iou']
        
        any_changed = False
        
        # 1. 绝对位移修正（向字帖重心方向微调，收敛速度可控）
        for ps in sorted(per_stroke, key=lambda s: -s.get('offset_px', 0)):
            offset = ps.get('offset_px', 0)
            if offset < 5: continue
            
            f = features[ps['id']]
            # 修正量：越小越精细
            correction = min(offset * 0.25, 5.0)
            target_cx, target_cy = 0.5, 0.5
            dx = (target_cx - f.mid_x) * correction * 0.02
            dy = (target_cy - f.mid_y) * correction * 0.02
            
            # 检查是否有交接关系约束
            has_connect = any(
                (r['i'] == ps['id'] or r['j'] == ps['id']) and 
                r['details'].get('connect_dev', 0) > 0.01
                for r in rel_devs
            )
            if has_connect:
                dx *= 0.5; dy *= 0.5  # 交接关系下减少移动量
            
            f.px_start = (f.px_start[0] + dx, f.px_start[1] + dy)
            f.px_end = (f.px_end[0] + dx, f.px_end[1] + dy)
            f.mid_x += dx / 256
            f.mid_y += dy / 256
            any_changed = True
            break
        
        # 2. 覆盖率不足
        if not any_changed and coverage < 0.3:
            for f in features:
                f.thickness_ratio = min(1.2, f.thickness_ratio + 0.05)
            any_changed = True
        
        # 3. 覆盖好但IoU低
        if not any_changed and iou < 0.3 and coverage > 0.5:
            for f in features:
                f.thickness_ratio = max(0.7, f.thickness_ratio - 0.05)
            any_changed = True
        
        return any_changed
    
    def run(self, char, max_iterations=8, verbose=True):
        """运行完整闭环"""
        if verbose:
            print(f"\n{'='*60}")
            print(f"  YLYW 书法知几学习闭环 — 「{char}」")
            print(f"{'='*60}")
        
        # Step 1: 观帖
        if verbose:
            print("\n[1. 观帖] 分析字帖结构...")
        obs = self.observe(char)
        
        if verbose:
            n_strokes = len(obs['features'])
            print(f"  笔画数: {n_strokes}")
            for f in obs['features']:
                print(f"    {f.stroke_type}: ({f.px_start[0]:.0f},{f.px_start[1]:.0f})→({f.px_end[0]:.0f},{f.px_end[1]:.0f}) "
                      f"中({f.mid_x:.2f},{f.mid_y:.2f}) 长{f.length:.2f}")
            print(f"  全局结构: {obs['upper_trigram']}上{obs['lower_trigram']}下 → {obs['hexagram']}")
        
        scores = []
        
        for it in range(max_iterations):
            if verbose:
                print(f"\n--- 第 {it+1}/{max_iterations} 轮 ---")
            
            # Step 2: 规划
            if verbose:
                print("[2. 规划] 规则库生成执行计划...")
            plans = self.plan(obs)
            
            if verbose and it == 0:
                for p in plans:
                    print(f"  笔画{p['stroke_id']}: {p['trigram']}→{p['brush_method']} "
                          f"压{p['pressure_base']:.2f}")
            
            # Step 3: 执行
            if verbose:
                print("[3. 执行] 书写中...")
            result_img, traj, press = self.execute(obs, plans)
            
            cv2.imwrite(str(self.output_dir / f'{char}_iter{it+1}.png'), result_img)
            
            # Step 4: 自省
            if verbose:
                print("[4. 自省] 骨架评价...")
            eval_result = self.evaluate(obs['target_img'], result_img, obs)
            
            # Step 5: 诊断
            if verbose:
                print("[5. 诊断] 爻位分析...")
            diagnosis = self.diagnose(obs, eval_result)
            
            score = eval_result['score']
            iou = eval_result['iou']
            coverage = eval_result['coverage']
            scores.append(score)
            
            improvement = score - (scores[-2] if len(scores) > 1 else 0)
            if verbose:
                arrow = '↑' if improvement > 0 else ('↓' if improvement < 0 else '→')
                print(f"  像素分: {score:.3f} {arrow}{improvement:+.3f} "
                      f"(IoU={iou:.3f}, 覆盖={coverage:.3f})")
                print(f"  诊断: {diagnosis['main_issue']}")
                # 爻位偏差
                rel_devs = diagnosis.get('relation_deviations', [])
                if rel_devs:
                    for rd in sorted(rel_devs, key=lambda r: -r['total_dev'])[:2]:
                        print(f"    爻位: {rd['i']}↔{rd['j']} 偏差{rd['total_dev']:.3f}")
                # 逐笔画
                ps_str = " | ".join(
                    f"{s['type']}:形{s['shape_score']:.2f}" 
                    for s in diagnosis.get('per_stroke', [])
                )
                print(f"  逐笔画: {ps_str}")
            
            # 记录
            self.history.append({
                'iteration': it,
                'score': score,
                'iou': iou,
                'coverage': coverage,
                'redundancy': eval_result['redundancy'],
                'diagnosis': diagnosis,
            })
            
            # Step 6: 精进
            if not diagnosis['need_improvement']:
                if verbose:
                    print(f"\n  ✅ 已达到目标，停止迭代。")
                break
            
            if verbose:
                print(f"[6. 精进] 修正参数...")
            changed = self.learn(obs, diagnosis)
            
            # 连续6轮无显著改善才收敛（给位移修正足够时间）
            if len(scores) >= 7 and max(scores[-5:]) - min(scores[-5:]) < 0.003:
                if verbose:
                    print(f"\n  ⚠️ 分数已收敛，停止迭代。")
                break
        
        # 总结
        if verbose:
            print(f"\n{'='*60}")
            print(f"  「{char}」学习总结")
            print(f"{'='*60}")
            print(f"  迭代数: {len(scores)}")
            print(f"  像素分: {scores[0]:.3f} → {scores[-1]:.3f} "
                  f"({'↑' if scores[-1]>scores[0] else '↓'}{abs(scores[-1]-scores[0]):+.3f})")
            if self.history:
                last = self.history[-1]
                ps = last['diagnosis'].get('per_stroke', [])
                if ps:
                    covs = " | ".join(f"{s['type']}:{s['shape_score']:.2f}" for s in ps)
                    offs = " | ".join(f"{s['type']}:偏{s.get('offset_px',0):.0f}px" for s in ps)
                    print(f"  最终逐笔画: {covs}")
                    print(f"  位移偏差:   {offs}")
            print(f"  学习曲线: {[f'{s:.3f}' for s in scores]}")
        
        return scores


if __name__ == '__main__':
    loop = CalligraphyLearningLoop()
    
    for char in ['大', '永', '人']:
        scores = loop.run(char, max_iterations=5, verbose=True)
