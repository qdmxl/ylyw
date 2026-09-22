# 路径A 手工测试说明（bottle）

## 工具
`bottle_manual_test.py` —— 支持"学习一次→保存模型→单图推理"。

## 关键点：现在的实验程序**不留模型**
- `expA_ortho_online.py`：每次从头跑，在线学习模板 T/S 与六爻标定 μ/σ 全在内存里，
  跑完只输出 AUROC 曲线 JSON（`results/expA_ortho_online.json`），**不保存模型、无单图推理入口**。
- 本工具补上这两件事：模型存盘 + 单图判"正常/缺陷"。

## 命令

```bash
cd /home/lijinhan/.openclaw/workspace-quantum/quantum_ylyw

# 1) 学习正常模板并保存模型（一次即可）
../.venv-quantum/bin/python bottle_manual_test.py train --n 209
#    --n 用多少张正常图；建议全量 209（少样本阈值偏紧，好图会误报）

# 2) 单图测试
../.venv-quantum/bin/python bottle_manual_test.py test data/mvtec/bottle/test/good/000-95.png --viz
../.venv-quantum/bin/python bottle_manual_test.py test data/mvtec/bottle/test/broken_large/000-94.png --viz
#    --viz 保存残差热图到 figures/manual/

# 3) 批量测试整个 test 集
../.venv-quantum/bin/python bottle_manual_test.py test --all --show-wrong
```

## 判断逻辑
- 异常分数 = 六爻标准化偏离均值（相对训练期正常分布 μ/σ），与主实验 S2 完全一致。
- 阈值 = 训练期正常样本分数的 mean + k·std（默认 k=3，可 `--k` 调）。
- 分数 > 阈值 → 缺陷。

## 实测结果（n=209 训练，阈值 1.884）
- 正常 20/20 判对（0 误报）；缺陷 53/63 判对；准确率 0.879，召回 0.841。
- 漏报集中在 broken_small（细裂纹）与少量 contamination —— 与报告结论一致（细长/微弱缺陷靠单点峰值更直接）。

## 模型文件
`model_bottle.npz`（T/S 灰度+色彩模板、六爻 μ/σ、阈值、训练图数）。
