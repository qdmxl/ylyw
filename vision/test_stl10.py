#!/usr/bin/env python3
"""
YLYW 视觉分类器 — STL-10 标准数据集测试

STL-10: 10类自然物体, 96×96 RGB
映射8类到八卦:
    乾=airplane  坤=ship    震=horse   巽=bird
    坎=deer      离=car     艮=truck   兑=cat

方法: 8D 简单算子 → Z-score → 最近原型 → 分类
"""

import sys, os, time, struct
import numpy as np, cv2
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.simple_8d import Simple8DExtractor

# STL-10 → 八卦 映射
STL_TO_TRIGRAM = {
    'airplane': '乾',  # 结构/几何 — 机翼刚性结构
    'ship':     '坤',  # 平滑/均匀 — 大面积平滑表面
    'horse':    '震',  # 高对比方向 — 长体动态
    'bird':     '巽',  # 细纹理 — 羽毛
    'deer':     '坎',  # 曲线/流动 — 鹿角曲线
    'car':      '离',  # 亮/辐射 — 反光漆面车灯
    'truck':    '艮',  # 块状/厚重 — 方形车体
    'cat':      '兑',  # 反射/高光 — 毛发反光眼睛
}
CLASSES = ['乾','兑','离','震','巽','坎','艮','坤']


def read_stl10_images(path, n_images, img_size=96, n_channels=3):
    """读取 STL-10 二进制图像"""
    with open(path, 'rb') as f:
        data = f.read()
    expected = n_images * img_size * img_size * n_channels
    assert len(data) == expected, f"Expected {expected} bytes, got {len(data)}"
    # STL-10 uses column-major (F) order: (C, W, H) → transpose
    imgs = np.frombuffer(data, dtype=np.uint8).reshape(n_images, n_channels, img_size, img_size)
    imgs = imgs.transpose(0, 2, 3, 1)  # → (N, H, W, C)
    return imgs


def read_stl10_labels(path, n_images):
    """读取 STL-10 标签 (1-indexed)"""
    with open(path, 'rb') as f:
        data = f.read()
    assert len(data) == n_images, f"Expected {n_images} bytes, got {len(data)}"
    return np.frombuffer(data, dtype=np.uint8) - 1  # 0-indexed


def main():
    stl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stl10', 'stl10_binary')

    # 读取类别名
    with open(os.path.join(stl_dir, 'class_names.txt')) as f:
        all_class_names = [line.strip() for line in f]

    # 读取数据
    print("Loading STL-10...")
    train_imgs = read_stl10_images(os.path.join(stl_dir, 'train_X.bin'), 5000)
    train_labels = read_stl10_labels(os.path.join(stl_dir, 'train_y.bin'), 5000)
    test_imgs = read_stl10_images(os.path.join(stl_dir, 'test_X.bin'), 8000)
    test_labels = read_stl10_labels(os.path.join(stl_dir, 'test_y.bin'), 8000)

    # 只保留映射表中的8类
    used_class_names = list(STL_TO_TRIGRAM.keys())
    used_class_ids = [all_class_names.index(c) for c in used_class_names]

    # 筛选训练集
    train_mask = np.isin(train_labels, used_class_ids)
    train_imgs = train_imgs[train_mask]
    train_labels_raw = train_labels[train_mask]
    # 重新映射 label → trigram
    id_to_trigram = {all_class_names.index(c): STL_TO_TRIGRAM[c] for c in used_class_names}
    train_trigram_labels = [id_to_trigram[l] for l in train_labels_raw]

    # 筛选测试集
    test_mask = np.isin(test_labels, used_class_ids)
    test_imgs = test_imgs[test_mask]
    test_labels_raw = test_labels[test_mask]
    test_trigram_labels = [id_to_trigram[l] for l in test_labels_raw]

    print(f"Train: {len(train_imgs)} images")
    print(f"Test:  {len(test_imgs)} images")
    for c in used_class_names:
        n_train = sum(1 for l in train_labels_raw if all_class_names[l] == c)
        n_test = sum(1 for l in test_labels_raw if all_class_names[l] == c)
        print(f"  {c} → {STL_TO_TRIGRAM[c]}: train={n_train} test={n_test}")

    # 特征提取
    print("\nExtracting 8D features...")
    extractor = Simple8DExtractor()

    train_feats = []
    for i in range(len(train_imgs)):
        gray = cv2.cvtColor(train_imgs[i], cv2.COLOR_RGB2GRAY)
        train_feats.append(extractor.extract(gray.astype(np.float32)))
        if (i+1) % 500 == 0:
            print(f"  train: {i+1}/{len(train_imgs)}")

    train_feats = np.array(train_feats)

    test_feats = []
    for i in range(len(test_imgs)):
        gray = cv2.cvtColor(test_imgs[i], cv2.COLOR_RGB2GRAY)
        test_feats.append(extractor.extract(gray.astype(np.float32)))
        if (i+1) % 1000 == 0:
            print(f"  test: {i+1}/{len(test_imgs)}")

    test_feats = np.array(test_feats)

    # Z-score 归一化 + 原型
    cm, cs = train_feats.mean(axis=0), train_feats.std(axis=0) + 1e-8
    train_norm = (train_feats - cm) / cs
    test_norm = (test_feats - cm) / cs

    proto = {}
    for cls in CLASSES:
        mask = np.array([l == cls for l in train_trigram_labels])
        if mask.any():
            proto[cls] = train_norm[mask].mean(axis=0)
        else:
            proto[cls] = np.zeros(8)

    # 测试
    correct_t1, correct_t3 = 0, 0
    per_class = defaultdict(lambda: {'t1':0,'t3':0,'n':0})
    class_results = defaultdict(list)

    for i in range(len(test_norm)):
        x = test_norm[i]
        dists = {c: np.sum((x - proto[c])**2) for c in CLASSES}
        ranked = sorted(dists.items(), key=lambda kv: kv[1])
        t1 = ranked[0][0]
        label = test_trigram_labels[i]

        if t1 == label: correct_t1 += 1; per_class[label]['t1'] += 1
        if label in [r[0] for r in ranked[:3]]: correct_t3 += 1; per_class[label]['t3'] += 1
        per_class[label]['n'] += 1
        class_results[label].append({'top1': t1})

    # 输出
    print(f"\n{'='*70}")
    print(f"  STL-10 测试结果")
    print(f"{'='*70}")
    print(f"\n{'类别':<20} {'STL-10':<12} {'样本':>5} {'Top-1':>6} {'%':>6} {'Top-3':>6} {'%':>6}")
    print("-"*68)
    for cls in CLASSES:
        stl_name = [k for k,v in STL_TO_TRIGRAM.items() if v==cls][0]
        s = per_class[cls]
        if s['n'] == 0: continue
        print(f"  {cls:<18} {stl_name:<12} {s['n']:>5} {s['t1']:>6} {100*s['t1']/s['n']:>5.1f}% "
              f"{s['t3']:>6} {100*s['t3']/s['n']:>5.1f}%")
    print("-"*68)
    N = len(test_norm)
    print(f"  {'总计':<18} {'':<12} {N:>5} {correct_t1:>6} {100*correct_t1/N:>5.1f}% "
          f"{correct_t3:>6} {100*correct_t3/N:>5.1f}%")

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

    print(f"\n  对比: 合成物体=89.6% | Brodatz纹理=14.0% | STL-10={100*correct_t1/N:.1f}%")


if __name__ == '__main__':
    main()
