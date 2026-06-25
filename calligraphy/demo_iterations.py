#!/usr/bin/env python3
"""
YLYW 书法学习 — 迭代效果对比图

对一个汉字运行知几学习闭环，每轮迭代输出一张墨迹图，
最后生成一张对比大图：目标字帖 + 每轮迭代结果。
"""

import os, sys
import numpy as np
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')

sys.path.insert(0, str(Path(__file__).parent))
from learning_loop import ZhijiLearningLoop, load_copybook
import cv2


def run_and_save_iterations(character='大', max_iterations=8):
    outdir = Path(__file__).parent / 'output' / 'iteration_compare' / character
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"=== YLYW 迭代书写 — 「{character}」===")
    print(f"  最大迭代: {max_iterations}")
    print(f"  输出目录: {outdir}")
    print()

    loop = ZhijiLearningLoop(output_dir=str(outdir))

    target_image = load_copybook(character)
    target_path = outdir / f'target_{character}.png'
    cv2.imwrite(str(target_path), target_image)
    print(f"📖 目标字帖: {target_path}")

    history = loop.run_learning_loop(
        character=character,
        target_image=target_image,
        max_iterations=max_iterations,
        verbose=True,
    )

    # 把每轮书写结果拷贝到统一命名
    for rec in history.iterations:
        src = outdir / f'{character}_iter{rec.iteration+1}.png'
        # already saved by learning loop
        print(f"  ✅ iter{rec.iteration+1}: distance={rec.diagnosis.total_distance:.3f} grade={rec.diagnosis.grade}")

    # 生成对比大图
    make_comparison_image(character, outdir, history)

    return history


def make_comparison_image(character, outdir, history):
    """生成目标字帖 + 所有迭代结果的对比大图"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    zh_path = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
    if os.path.exists(zh_path):
        fm.fontManager.addfont(zh_path)
        plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=zh_path).get_name()]

    n_iters = len(history.iterations)
    n_cols = min(4, n_iters + 1)
    n_rows = (n_iters + 2) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
    if n_rows * n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)

    # 目标字帖
    ax = axes[0, 0]
    target = cv2.imread(str(outdir / f'target_{character}.png'), cv2.IMREAD_GRAYSCALE)
    ax.imshow(target, cmap='gray_r')
    ax.set_title(f'目标字帖「{character}」', fontsize=14, fontweight='bold', color='#c0392b')
    ax.set_xticks([])
    ax.set_yticks([])

    # 各轮迭代
    for idx, rec in enumerate(history.iterations):
        row = (idx + 1) // n_cols
        col = (idx + 1) % n_cols
        ax = axes[row, col]

        img = rec.result_image
        if img is not None:
            ax.imshow(img, cmap='gray_r')

        d = rec.diagnosis
        title = f'第{d.iteration+1}轮  {d.grade}\n距离={d.total_distance:.3f}'
        ax.set_title(title, fontsize=11, fontweight='bold',
                    color={'优': '#27ae60', '良': '#f39c12', '中': '#e74c3c', '差': '#c0392b'}.get(d.grade, 'black'))
        ax.set_xticks([])
        ax.set_yticks([])

    # 隐藏多余子图
    for idx in range(n_iters + 1, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].axis('off')

    fig.suptitle(f'YLYW 知几书法学习 — 「{character}」迭代效果对比',
                fontsize=18, fontweight='bold')
    plt.tight_layout()

    cmp_path = outdir / f'{character}_comparison.png'
    plt.savefig(cmp_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"\n📸 对比大图: {cmp_path}")


if __name__ == '__main__':
    char = sys.argv[1] if len(sys.argv) > 1 else '大'
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    run_and_save_iterations(char, iters)
