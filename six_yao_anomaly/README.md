# 六爻传感器阵列 — 论文与代码快照

> 快照日期：2026-09-14
> 主题：量子易理（六爻）框架用于工业图像异常检测（MVTec AD 全 15 类）

## 目录结构

```
├── paper/
│   ├── en/main.tex                     英文论文（LaTeX 源）
│   ├── zh/main.tex                     中文论文（LaTeX 源）
│   ├── six_yao_arrays_draft_en.docx    英文稿 docx
│   └── 六爻传感器阵列_中文初稿.docx      中文稿 docx
├── results/                            全部实验结果 JSON（含 15 类主结果）
├── figures_paper/                      论文插图（PNG）
├── figures/                            早期实验图
├── tex2docx.py                         LaTeX→docx 转换脚本（用系统 python3 运行）
├── exp*.py                            实验脚本（主线：exp31~exp33）
├── fig*.py                            绘图脚本
└── *.md                               实验报告与说明
```

## 核心结果（15 类图像级 AUROC）

| 变体 | 平均 AUROC |
|---|---|
| 手工固定卷积（无预训练） | 0.709 |
| 六爻传感器 L1 层 | 0.751 |
| 六爻传感器 L2 层 | 0.815 |
| **六爻传感器 L3 层（本文最佳）** | **0.862** |
| L1+L3 融合 | 0.825 |
| PaDiM（文献报告） | 0.975 |
| PatchCore（文献报告） | 0.992 |

信号无关性阶梯（4 类共同子集）：随机 ResNet 0.772 < 手工固定卷积 0.799 <
手工六爻信号 0.854 < ImageNet 预训练 ResNet 0.932。

数据汇总见 `results/exp31_MASTER_15class.json`。

## 数据依赖（未包含在快照中）

因体积原因 `data/` 未拷贝。复现实验需准备 MVTec AD 15 类数据集，
放到 `data/mvtec_full/`（软链即可），目录结构为标准 MVTec AD 布局：

```
data/mvtec_full/<类别>/{train,test}/...
```

脚本默认路径为 `data/mvtec_full`（见 `exp31_full15.py`）。

## 环境

- Python venv：torch 2.14.0+cpu / torchvision 0.29.0+cpu（ResNet18 预训练权重）
- 生成 docx 需 **系统 python3**（含 python-docx），非 venv

## 运行主线实验

```bash
# 层扫描（L1/L2/L3，全 15 类）
python exp31_full15.py --layer 3 --cats all --tag L3
# 手工消融
python exp32_ladder15.py handmade
# L1+L3 融合
python exp33_fusion15.py
# 生成论文图
python fig10_main_results.py && python fig7_layer_heatmap.py
# 生成 docx
python3 tex2docx.py paper/zh/main.tex paper/六爻传感器阵列_中文初稿.docx
```
