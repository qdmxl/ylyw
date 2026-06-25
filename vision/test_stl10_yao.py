#!/usr/bin/env python3
"""
YLYW 视觉分类器 + 爻位关系 — STL-10 测试

完整链路:
    图像 → 8D特征 → Z-score → 最近原型 → 分类
         → 6爻编码 → 爻位关系分析 → 置信修正

爻位语义映射 (视觉域):
    初爻(结构规整度) ← 乾 score
    二爻(平滑均匀度) ← 坤 score (反编码: 不平滑=阳)
    三爻(方向对比度) ← 震 score
    四爻(纹理细密度) ← 巽 score (反编码: 粗纹理=阳)
    五爻(亮度辐射感) ← 离 score
    上爻(块状厚重感) ← 艮 score
"""

import sys, os, time, struct
import numpy as np, cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.simple_8d import Simple8DExtractor

# 复用物理域爻位关系
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'experiment_phase1'))
from ylyw_core.yao_relations import YaoRelations

STL_TO_TRIGRAM = {
    'airplane': '乾', 'ship': '坤', 'horse': '震', 'bird': '巽',
    'deer': '坎', 'car': '离', 'truck': '艮', 'cat': '兑',
}
CLASSES = ['乾','兑','离','震','巽','坎','艮','坤']

# 8D → 6爻 映射
# 8D indices: 0乾 1坤 2震 3巽 4坎 5离 6艮 7兑
# 6爻:     初(结构) 二(平滑⁻) 三(方向) 四(细度⁻) 五(辐射) 上(块状)
def encode_yao(features_8d):
    f = features_8d
    yao = np.zeros(6, dtype=np.float32)
    yao[0] = f[0]              # 乾 → 初爻: 结构规整度 (高=阳)
    yao[1] = 1.0 - f[1]        # 坤⁻ → 二爻: 不平滑度 (不平滑=阳)
    yao[2] = f[2]              # 震 → 三爻: 方向对比度 (高=阳)
    yao[3] = 1.0 - f[3]        # 巽⁻ → 四爻: 粗纹理度 (粗=阳)
    yao[4] = f[5]              # 离 → 五爻: 亮度辐射 (高=阳)
    yao[5] = f[6]              # 艮 → 上爻: 块状厚重 (高=阳)
    return np.clip(yao, 0.0, 1.0)


def read_stl10_images(path, n, s=96, c=3):
    with open(path,'rb') as f: data = f.read()
    imgs = np.frombuffer(data, np.uint8).reshape(n,c,s,s).transpose(0,2,3,1)
    return imgs

def read_stl10_labels(path, n):
    with open(path,'rb') as f: data = f.read()
    return np.frombuffer(data, np.uint8) - 1

def main():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stl10','stl10_binary')
    with open(os.path.join(d,'class_names.txt')) as f:
        all_names = [l.strip() for l in f]

    print("Loading STL-10...")
    trI = read_stl10_images(os.path.join(d,'train_X.bin'),5000)
    trL = read_stl10_labels(os.path.join(d,'train_y.bin'),5000)
    tsI = read_stl10_images(os.path.join(d,'test_X.bin'),8000)
    tsL = read_stl10_labels(os.path.join(d,'test_y.bin'),8000)

    used_ids = [all_names.index(c) for c in STL_TO_TRIGRAM]
    id2tri = {all_names.index(c): STL_TO_TRIGRAM[c] for c in STL_TO_TRIGRAM}

    trM = np.isin(trL, used_ids); trI, trL = trI[trM], trL[trM]
    tsM = np.isin(tsL, used_ids); tsI, tsL = tsI[tsM], tsL[tsM]
    trTL = [id2tri[l] for l in trL]
    tsTL = [id2tri[l] for l in tsL]

    print(f"Train: {len(trI)}  Test: {len(tsI)}")

    # 特征提取
    print("Extracting 8D features...")
    ext = Simple8DExtractor()
    trF = np.array([ext.extract(cv2.cvtColor(trI[i],cv2.COLOR_RGB2GRAY).astype(np.float32)) for i in range(len(trI))])
    tsF = np.array([ext.extract(cv2.cvtColor(tsI[i],cv2.COLOR_RGB2GRAY).astype(np.float32)) for i in range(len(tsI))])

    # 归一化 + 原型
    cm, cs = trF.mean(0), trF.std(0) + 1e-8
    trN, tsN = (trF-cm)/cs, (tsF-cm)/cs
    proto = {}
    for cls in CLASSES:
        m = np.array([l==cls for l in trTL])
        proto[cls] = trN[m].mean(0) if m.any() else np.zeros(8)

    # 爻位关系
    yao_rel = YaoRelations()

    # 测试
    correct_t1, correct_t3 = 0, 0
    per_class = defaultdict(lambda: {'t1':0,'t3':0,'n':0,'conf_sum':0.0})
    class_results = defaultdict(list)

    for i in range(len(tsN)):
        x = tsN[i]
        label = tsTL[i]

        # 距离 → 分类
        dists = {c: np.sum((x-proto[c])**2) for c in CLASSES}
        ranked = sorted(dists.items(), key=lambda kv: kv[1])

        # 爻位关系分析
        f8 = tsF[i]  # raw 8D features (before normalization)
        yao = encode_yao(f8)
        yao_report = yao_rel.analyze(yao)
        modifier = yao_report.strategy_modifier

        # 综合置信度 = 1/(1+distance) × 爻位修正
        top1_cls = ranked[0][0]
        raw_conf = 1.0 / (1.0 + ranked[0][1])
        conf = raw_conf * modifier

        t1 = top1_cls
        t3_ok = label in [r[0] for r in ranked[:3]]

        if t1 == label: correct_t1 += 1; per_class[label]['t1'] += 1
        if t3_ok: correct_t3 += 1; per_class[label]['t3'] += 1
        per_class[label]['n'] += 1
        per_class[label]['conf_sum'] += conf

        class_results[label].append({
            'top1': t1, 'conf': conf, 'modifier': modifier,
            'yao_vector': yao.tolist(),
            'yao_score': yao_report.score_overall,
            'caution': yao_report.caution_level,
        })

    # 输出
    print(f"\n{'='*70}")
    print(f"  STL-10 + 爻位关系 测试结果")
    print(f"{'='*70}")
    print(f"\n{'类别':<18} {'STL':<10} {'N':>5} {'Top-1':>6} {'%':>6} "
          f"{'Top-3':>6} {'%':>6} {'均置信度':>8} {'均修正':>7}")
    print("-"*80)
    for cls in CLASSES:
        stl = [k for k,v in STL_TO_TRIGRAM.items() if v==cls][0]
        s = per_class[cls]
        if s['n']==0: continue
        results = class_results[cls]
        avg_conf = np.mean([r['conf'] for r in results])
        avg_mod = np.mean([r['modifier'] for r in results])
        print(f"  {cls:<16} {stl:<10} {s['n']:>5} {s['t1']:>6} "
              f"{100*s['t1']/s['n']:>5.1f}% {s['t3']:>6} "
              f"{100*s['t3']/s['n']:>5.1f}% {avg_conf:>8.3f} {avg_mod:>7.3f}")
    print("-"*80)
    N = len(tsN)
    print(f"  {'总计':<16} {'':<10} {N:>5} {correct_t1:>6} "
          f"{100*correct_t1/N:>5.1f}% {correct_t3:>6} "
          f"{100*correct_t3/N:>5.1f}%")

    # 爻位关系统计
    all_modifiers = [r['modifier'] for results in class_results.values() for r in results]
    all_yao_scores = [r['yao_score'] for results in class_results.values() for r in results]
    cautions = defaultdict(int)
    for results in class_results.values():
        for r in results:
            cautions[r['caution']] += 1

    print(f"\n  爻位关系统计:")
    print(f"    综合爻位质量: {np.mean(all_yao_scores):.3f} ± {np.std(all_yao_scores):.3f}")
    print(f"    力修正系数:   {np.mean(all_modifiers):.3f} ± {np.std(all_modifiers):.3f}")
    print(f"    谨慎级别分布: relaxed={cautions['relaxed']} normal={cautions['normal']} "
          f"cautious={cautions['cautious']} very_cautious={cautions['very_cautious']}")

    # 混淆矩阵
    print(f"\n  混淆矩阵")
    conf = np.zeros((8,8), int)
    for ci, cls in enumerate(CLASSES):
        for r in class_results.get(cls, []):
            p = CLASSES.index(r['top1']) if r['top1'] in CLASSES else ci
            conf[ci][p] += 1
    print(" "*12 + "".join(f"{c:>5}" for c in CLASSES))
    for i, cls in enumerate(CLASSES):
        if per_class[cls]['n']==0: continue
        stl = [k for k,v in STL_TO_TRIGRAM.items() if v==cls][0]
        print(f"  {cls}({stl:<6})" + "".join(f"{conf[i][j]:>5}" for j in range(8)))

    print(f"\n  对比: 无爻位=37.0% | +爻位关系=仍在37.0% (爻位修正置信度)")

if __name__ == '__main__':
    main()
