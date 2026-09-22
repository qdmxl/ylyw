#!/usr/bin/env python3
"""
乘承比应量子化验证 — 物体抓取子项目

用6量子位乘承比应酉演化替代经典YaoEncoder的规则公式，
保留L1八卦基元和L3卦象匹配不变，对比零样本合理率。

流程:
    物理特征(6维)
      → L1: 八卦隶属度(不变) 
      → 马老师方案: 八卦8维→6量子位编码→乘承比应酉演化→新六爻
      → L3: 64卦模板cosine匹配(不变) → 抓取策略

评估: 300物体零样本合理率 vs 经典版
"""

import sys, os, json, time, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
from prior_manual import PriorManual, TrigramBase, YaoEncoder, HexagramRuleBase, Hexagram
from prior_manual.yao_relations import YaoRelations


# ==========================================================
# 乘承比应哈密顿量（6量子位）
# ==========================================================
I2 = np.eye(2, dtype=complex)
Z = np.array([[1,0],[0,-1]], dtype=complex)
X = np.array([[0,1],[1,0]], dtype=complex)

def _pop(ops):
    r = ops[-1].copy()
    for o in reversed(ops[:-1]):
        r = np.kron(r, o)
    return r

def build_chengbcheng_hamiltonian():
    """构建乘承比应哈密顿量 H_cbcy"""
    H = np.zeros((64, 64), dtype=complex)
    
    # 各爻位能级（初→上）
    h_yao = np.array([0.3, 0.5, 0.7, 0.5, 0.8, 0.4])
    for i in range(6):
        H += h_yao[i] * _pop([Z if q==i else I2 for q in range(6)])
        H += 0.15 * _pop([X if q==i else I2 for q in range(6)])
    
    # 乘(下承上) — 邻爻正向耦合
    for i in range(5):
        H += 0.7 * _pop([Z if q in (i,i+1) else I2 for q in range(6)])
    
    # 承(上载下) — 邻爻反向耦合
    for i in range(5):
        H += 0.5 * _pop([Z if q in (i+1,i) else I2 for q in range(6)])
    
    # 比(隔位交感)
    for i in range(4):
        H += 0.25 * _pop([Z if q in (i,i+2) else I2 for q in range(6)])
    
    # 应(初四/二五/三六)
    for i,j in [(0,3),(1,4),(2,5)]:
        H += 0.35 * _pop([Z if q in (i,j) else I2 for q in range(6)])
    
    # 三体纠缠(三生万物)
    for tri in [(0,1,2),(1,2,3),(2,3,4),(3,4,5)]:
        H += 0.08 * _pop([Z if q in tri else I2 for q in range(6)])
    
    return H

H = build_chengbcheng_hamiltonian()
evals, evecs = np.linalg.eigh(H)
TAU = 0.5  # 演化时间
U_cbcy = evecs @ np.diag(np.exp(-1j * TAU * evals)) @ evecs.conj().T


# ==========================================================
# 乘承比应量子六爻编码器
# ==========================================================
def trigram_to_quantum_yao(bagua_8d):
    """
    8维八卦隶属度 → 乘承比应酉演化 → 六爻
    
    编码方案:
      y0 = 乾(0), y1 = 兑(1), y2 = 离(2)
      y3 = 震(3), y4 = 巽(4), y5 = 坎(5)+0.5*艮(6)+0.5*坤(7)
    """
    b = np.array(bagua_8d, dtype=float).clip(0.05, 0.95)
    
    # 8→6维编码
    raw6 = np.zeros(6)
    raw6[0] = b[0]  # 乾
    raw6[1] = b[1]  # 兑
    raw6[2] = b[2]  # 离
    raw6[3] = b[3]  # 震
    raw6[4] = b[4]  # 巽
    raw6[5] = min(0.95, b[5] + 0.5*b[6] + 0.5*b[7])  # 坎+艮+坤
    
    y = np.array([max(0.05, min(0.95, v)) for v in raw6])
    
    # 编码为6量子位初态
    psi = np.ones(1, dtype=complex)
    for v in y:
        psi = np.kron(psi, np.array([np.sqrt(1.0 - v), np.sqrt(v)], dtype=complex))
    psi /= np.linalg.norm(psi)
    
    # 乘承比应酉演化
    psi_ev = U_cbcy @ psi
    probs = np.abs(psi_ev) ** 2
    probs /= (probs.sum() + 1e-12)
    
    # 从纠缠态提取六爻（各qubit的|1⟩边缘概率）
    new_yao = np.zeros(6)
    for i in range(6):
        mask = np.zeros(64, dtype=bool)
        for idx in range(64):
            if (idx >> (5 - i)) & 1:
                mask[idx] = True
        new_yao[i] = 0.05 + 0.90 * float(probs[mask].sum())
    
    return new_yao


# ==========================================================
# 经典版（对照）
# ==========================================================
def classic_encode(object_features):
    """经典YaoEncoder六爻编码"""
    encoder = YaoEncoder()
    return encoder.encode(object_features)


# ==========================================================
# 测试函数
# ==========================================================
def test_trigram_bagua_consistency():
    """验证八卦隶属度在经典和量子版之间的一致性"""
    trigram_base = TrigramBase()
    encoder = YaoEncoder()
    
    # 8种典型物体的特征
    test_features = [
        # (name, features)
        ("钢球",   {"stability":0.9, "roll_tendency":0.9, "strength_needed":0.3, 
                    "fragility":0.1, "task_priority":0.5, "reachability":0.8}),
        ("泡沫球", {"stability":0.3, "roll_tendency":0.7, "strength_needed":0.1, 
                    "fragility":0.9, "task_priority":0.3, "reachability":0.7}),
        ("木块",   {"stability":0.8, "roll_tendency":0.3, "strength_needed":0.5, 
                    "fragility":0.2, "task_priority":0.6, "reachability":0.6}),
        ("瓷碗",   {"stability":0.4, "roll_tendency":0.2, "strength_needed":0.4, 
                    "fragility":0.8, "task_priority":0.4, "reachability":0.6}),
        ("玻璃瓶", {"stability":0.5, "roll_tendency":0.3, "strength_needed":0.4, 
                    "fragility":0.8, "task_priority":0.5, "reachability":0.7}),
        ("盘子",   {"stability":0.3, "roll_tendency":0.2, "strength_needed":0.2, 
                    "fragility":0.8, "task_priority":0.4, "reachability":0.5}),
        ("石块",   {"stability":0.7, "roll_tendency":0.4, "strength_needed":0.8, 
                    "fragility":0.2, "task_priority":0.3, "reachability":0.5}),
        ("花瓶",   {"stability":0.4, "roll_tendency":0.3, "strength_needed":0.3, 
                    "fragility":0.7, "task_priority":0.6, "reachability":0.6}),
    ]
    
    print(f"{'物体':8s} {'主导卦':4s} {'经典六爻':42s} {'量子六爻':42s} {'经典卦':6s} {'量子卦':6s}")
    print("-" * 115)
    
    hex_rules = HexagramRuleBase()
    
    for name, features in test_features:
        # 经典六爻
        klass_yao = encoder.encode(features)
        hk, ck = hex_rules.get_best_hexagram(klass_yao)
        
        # 八卦隶属度
        trigram_memberships = trigram_base.get_all_memberships(features)
        dom_tri, dom_score = trigram_base.get_dominant_trigram(features)
        
        # 量子六爻
        qyao = trigram_to_quantum_yao(trigram_memberships)
        hq, cq = hex_rules.get_best_hexagram(qyao)
        
        k_str = '[' + ','.join(f'{v:.2f}' for v in klass_yao) + ']'
        q_str = '[' + ','.join(f'{v:.2f}' for v in qyao) + ']'
        
        hk_name = (list(Hexagram)[hk.value].name if hk else '?')[:6]
        hq_name = (list(Hexagram)[hq.value].name if hq else '?')[:6]
        
        tri_name = dom_tri.name[:4] if dom_tri else '?'
        
        print(f"{name:8s} {tri_name:>4s} {k_str:42s} {q_str:42s} {hk_name:>6s} {hq_name:>6s}")


def run_full_baseline(version='quantum', verbose=False):
    """
    运行完整基线测试
    
    从 simulation 获取物体特征数据，测试零样本合理率
    
    Args:
        version: 'classic' 或 'quantum'
        verbose: 是否打印详细日志
    """
    from simulation import SimulationScene
    
    manual = PriorManual(verbose=verbose)
    trigram_base = TrigramBase()
    hex_rules = HexagramRuleBase()
    scene = SimulationScene()
    
    # 生成304个物体（8种类型各38个）
    scene_types = ['sphere','cube','cylinder','bowl','bottle','plate','rock','vase']
    objects = scene.generate_scene_with_types(scene_types * 38)  # 8*38=304
    
    total = len(objects)
    correct = 0
    wrong = 0
    by_type = {}
    
    for obj in objects:
        obj_type = obj.object_type
        features = obj.features.to_dict()
        
        if version == 'quantum':
            # 量子版：八卦乘承比应 → 六爻
            trigram_memberships = trigram_base.get_all_memberships(features)
            yao_vec = trigram_to_quantum_yao(trigram_memberships)
            best_hx, match = hex_rules.get_best_hexagram(yao_vec)
        else:
            # 经典版
            perception = manual.perceive_and_encode(features)
            yao_vec = perception['yao_vector']
            best_hx = perception['best_hexagram']
            match = perception['hexagram_match_score']
        
        # 获取策略
        if best_hx is not None:
            rule = hex_rules.get_rule(best_hx)
            strategy = rule['grasp_strategy']['type']
        else:
            strategy = 'unknown'
        
        # 检查合理性
        from scripts.baseline_50objects import REASONABLE_STRATEGIES
        reasonable = REASONABLE_STRATEGIES.get(obj_type, set())
        
        is_reasonable = strategy in reasonable
        if is_reasonable:
            correct += 1
        else:
            wrong += 1
        
        if obj_type not in by_type:
            by_type[obj_type] = {'correct': 0, 'wrong': 0, 'total': 0}
        by_type[obj_type]['total'] += 1
        if is_reasonable:
            by_type[obj_type]['correct'] += 1
        else:
            by_type[obj_type]['wrong'] += 1
    
    rate = correct / total if total > 0 else 0.0
    return {
        'version': version,
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'rate': rate,
        'by_type': {k: {**v, 'rate': v['correct']/v['total']} 
                     for k, v in by_type.items()}
    }


# ==========================================================
# 爻位关系分析：乘承比应当位得中
# ==========================================================
def analyze_yao_relations(yao_vec):
    """分析六爻的乘承比应当位得中"""
    yao_rel = YaoRelations()
    return yao_rel.analyze(yao_vec)


def compare_yao_relations():
    """对比经典版和量子版的爻位关系"""
    trigram_base = TrigramBase()
    encoder = YaoEncoder()
    yao_rel = YaoRelations()
    
    features = {
        "stability": 0.6, "roll_tendency": 0.5, "strength_needed": 0.5,
        "fragility": 0.5, "task_priority": 0.5, "reachability": 0.5,
        "support_area": 0.5, "occlusion": 0.5, "grasp_surface_quality": 0.5,
        "weight_ratio": 0.5, "obstacle_density": 0.3
    }
    
    klass_yao = encoder.encode(features)
    bagua = trigram_base.get_all_memberships(features)
    qyao = trigram_to_quantum_yao(bagua)
    
    print(f"\n爻位关系对比:")
    print(f"  经典六爻: [{','.join(f'{v:.2f}' for v in klass_yao)}]")
    print(f"  量子六爻: [{','.join(f'{v:.2f}' for v in qyao)}]")
    
    for name, y in [("经典", klass_yao), ("量子", qyao)]:
        report = yao_rel.analyze(y)
        print(f"\n  [{name}]")
        report.print()


# ==========================================================
# 主入口
# ==========================================================
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='乘承比应量子化 — 物体抓取验证')
    parser.add_argument('--mode', choices=['test', 'baseline', 'all'], default='all',
                       help='测试模式: test=单个测试, baseline=完整基线, all=全部')
    parser.add_argument('--version', choices=['classic', 'quantum', 'both'], default='both',
                       help='版本: classic/quantum/both')
    parser.add_argument('--output', type=str, default=None,
                       help='结果JSON输出路径')
    parser.add_argument('--verbose', action='store_true',
                       help='详细日志')
    args = parser.parse_args()
    
    if args.mode in ('test', 'all'):
        print("=" * 70)
        print(" 八卦一致性 + 六爻对比测试")
        print("=" * 70)
        test_trigram_bagua_consistency()
        print()
    
    if args.mode in ('all',):
        print("=" * 70)
        print(" 爻位关系对比")
        print("=" * 70)
        compare_yao_relations()
        print()
    
    if args.mode in ('baseline', 'all'):
        versions = ['classic', 'quantum'] if args.version == 'both' else [args.version]
        results = {}
        
        for ver in versions:
            print(f"\n{'='*70}")
            print(f" 基线测试: {ver}版")
            print(f"{'='*70}")
            t0 = time.time()
            result = run_full_baseline(ver, verbose=args.verbose)
            elapsed = time.time() - t0
            
            print(f"\n  总数: {result['total']}")
            print(f"  合理: {result['correct']} ({result['rate']*100:.1f}%)")
            print(f"  异常: {result['wrong']} ({(1-result['rate'])*100:.1f}%)")
            print(f"  耗时: {elapsed:.2f}s")
            print(f"\n  各类别:")
            for t, v in sorted(result['by_type'].items()):
                print(f"    {t:12s}: {v['correct']:3d}/{v['total']:3d} = {v['rate']*100:5.1f}%")
            
            results[ver] = result
        
        # 如果两个版本都跑了，对比差异
        if len(versions) == 2:
            r1, r2 = results['classic'], results['quantum']
            diff = r2['rate'] - r1['rate']
            print(f"\n{'='*70}")
            print(f" 对比: 量子版 vs 经典版")
            print(f"{'='*70}")
            print(f"  经典: {r1['rate']*100:.1f}% ({r1['correct']}/{r1['total']})")
            print(f"  量子: {r2['rate']*100:.1f}% ({r2['correct']}/{r2['total']})")
            print(f"  差异: {diff*100:+.1f}%")
            
            # 各类别对比
            print(f"\n  各类别对比:")
            for t in sorted(set(list(r1['by_type'].keys()) + list(r2['by_type'].keys()))):
                v1 = r1['by_type'].get(t, {'rate': 0, 'correct': 0, 'total': 0})
                v2 = r2['by_type'].get(t, {'rate': 0, 'correct': 0, 'total': 0})
                d = v2['rate'] - v1['rate']
                print(f"    {t:12s}: 经典{v1['rate']*100:5.1f}% vs 量子{v2['rate']*100:5.1f}% ({d*100:+.1f}%)")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n结果已保存: {args.output}")
