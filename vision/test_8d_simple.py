#!/usr/bin/env python3
"""YLYW — 8D 简单算子 (一卦一个) + Brodatz LOTO 测试"""
import sys, os, numpy as np, cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.simple_8d import Simple8DExtractor

MAPPING = {
    '1.1.05':'乾','1.1.11':'乾','1.3.07':'乾','1.4.05':'乾','1.4.07':'乾','1.4.12':'乾','1.5.01':'乾',
    '1.1.02':'坤','1.3.03':'坤','1.3.04':'坤','1.3.05':'坤','1.5.02':'坤','1.5.09':'坤','1.5.10':'坤',
    '1.1.07':'震','1.1.10':'震','1.4.01':'震','1.4.02':'震','1.4.03':'震','1.4.04':'震',
    '1.4.08':'震','1.4.09':'震','1.4.10':'震',
    '1.1.12':'巽','1.1.13':'巽','1.3.01':'巽','1.3.02':'巽','1.3.08':'巽','1.3.09':'巽',
    '1.3.12':'巽','1.3.13':'巽','1.4.06':'巽','1.4.13':'巽','1.5.04':'巽','1.5.05':'巽',
    '1.5.06':'巽','1.5.07':'巽','1.5.08':'巽',
    '1.1.04':'坎','1.1.09':'坎','1.3.10':'坎',
    '1.1.08':'离','1.5.03':'离',
    '1.1.03':'艮','1.3.11':'艮','1.5.11':'艮','1.5.12':'艮',
    '1.3.06':'兑','1.4.11':'兑',
}
CLASSES = ['乾','兑','离','震','巽','坎','艮','坤']

def main():
    d = '/tmp/brodatz/textures'
    ext = Simple8DExtractor()
    nc = 4

    # 收集
    feats, labels = {}, {}
    for f in sorted(os.listdir(d)):
        if not f.endswith('.tiff') or '1.2.' in f: continue
        b = f.replace('.tiff','')
        if b not in MAPPING: continue
        img = cv2.imread(f'{d}/{f}', 0)
        if img is None: continue
        h, w = img.shape
        ch, cw = h//2, w//2
        crops = [img[:ch,:cw], img[:ch,cw:], img[ch:,:cw], img[ch:,cw:]]
        v = np.stack([ext.extract(c.astype(np.float32)) for c in crops[:nc]])
        feats[b] = v
        labels[b] = MAPPING[b]

    print(f"8D 特征收集: {len(feats)} 纹理 × {nc} 子图 = {sum(v.shape[0] for v in feats.values())} 样本")
    print()

    # LOTO
    pc = defaultdict(lambda: {'t1':0,'t3':0,'n':0})
    tt1, tt3, tn = 0, 0, 0
    cr = defaultdict(list)

    for tb, tl in labels.items():
        # 标定
        cv, cl = [], []
        for b, l in labels.items():
            if b == tb: continue
            cv.append(feats[b])
            cl.extend([l]*feats[b].shape[0])
        ca = np.concatenate(cv)
        cm, cs = ca.mean(0), ca.std(0) + 1e-8

        proto = {}
        for cls in CLASSES:
            mask = np.array([ll==cls for ll in cl])
            proto[cls] = ((ca[mask]-cm)/cs).mean(0) if mask.any() else np.zeros(8)

        # 测试
        tnorm = (feats[tb]-cm)/cs
        for i in range(len(tnorm)):
            x, tn = tnorm[i], tn+1
            dists = {c: np.sum((x-proto[c])**2) for c in CLASSES}
            ranked = sorted(dists.items(), key=lambda kv: kv[1])
            t1, ok = ranked[0][0], tl in [r[0] for r in ranked[:3]]
            if t1 == tl: tt1 += 1; pc[tl]['t1'] += 1
            if ok: tt3 += 1; pc[tl]['t3'] += 1
            pc[tl]['n'] += 1
            cr[tl].append({'top1': t1})

    # 输出
    print(f"{'类别':<18} {'样本':>5} {'Top-1':>6} {'%':>6} {'Top-3':>6} {'%':>6}")
    print("-"*54)
    for cls in CLASSES:
        s = pc[cls]
        if s['n']==0: continue
        print(f"  {cls:<16} {s['n']:>5} {s['t1']:>6} {100*s['t1']/s['n']:>5.1f}% {s['t3']:>6} {100*s['t3']/s['n']:>5.1f}%")
    print("-"*54)
    print(f"  {'总计':<16} {tn:>5} {tt1:>6} {100*tt1/max(tn,1):>5.1f}% {tt3:>6} {100*tt3/max(tn,1):>5.1f}%")

    # 混淆
    print(f"\n  混淆矩阵")
    conf = np.zeros((8,8), int)
    for ci, cls in enumerate(CLASSES):
        for r in cr.get(cls, []):
            p = CLASSES.index(r['top1']) if r['top1'] in CLASSES else ci
            conf[ci][p] += 1
    print(" "*10 + "".join(f"{c:>5}" for c in CLASSES))
    for i, cls in enumerate(CLASSES):
        if pc[cls]['n']==0: continue
        print(f"  {cls:<8}" + "".join(f"{conf[i][j]:>5}" for j in range(8)))

    print(f"\n  对比: v3=12.2% | v4=22.7% | Rich=30.2% | 8D简单={100*tt1/max(tn,1):.1f}%")

if __name__ == '__main__':
    main()
