# ylyw_anomaly —— 用原 YLYW 模型做无监督图像异常检测

> 新建项目 · 2026-09-15 · 目的：在 ylyw 仓库内，**直接复用原 YLYW 视觉管线**
> （而非另起炉灶的易理抽取器）来实现图像特征分层提取，并重跑异常检测实验，
> 与「量子异常检测」项目的易理抽取器 / ResNet 基线对比。

---

## 一、为什么做这个项目

前期"基于易理特征分层抽取"的论文用了一套**新设计**的抽取器
（L1阴阳→L2四象→L3八卦→L4六爻），**未复用**原 YLYW 模型的 L0–L4 计算链与
「乘承比应」爻位关系运算（详见
`../../quantum_ylyw/与前期YLYW_QYUF工作的关系_20260915.md`）。

本项目回答一个自然追问：**如果直接用原 YLYW 模型的视觉管线来做异常检测，结果如何？**

## 二、原 YLYW 视觉管线（本项目直接复用，未改写）

```
图像 → VisualFeatureExtractor    # L0: 6维视觉特征
        纹理均匀度 / 边缘清晰度 / 局部对比度 / 形状规整度 / 显著性 / 背景复杂度
     → VisualTrigramBase          # L1: 8 卦隶属度
     → VisualYaoEncoder           # L2: 六爻向量
     → YaoRelations               # L3: 乘承比应当位得中 → 关系评分
```

代码来源（`../vision/`、`../experiment_phase1/ylyw_core/`）：

| 组件 | 文件 |
|---|---|
| L0 特征 | `vision/feature_extractor_vision.py` |
| L1 八卦隶属度 | `vision/trigram_base_vision.py` |
| L2 六爻编码 | `vision/yao_encoder_vision.py` |
| **L3 乘承比应** | `experiment_phase1/ylyw_core/yao_relations.py` |

## 三、异常检测改造（无监督，仅用 train/good）

1. **正常模板**：对正常图像（或 patch）的 6 维特征 / 六爻 / 关系评分做
   **Welford 增量** 均值与方差估计；
2. **残差**：`r = |f(x) − μ| / σ`（在特征 / 爻 / 关系 三个层面）；
3. **判据**（对比多种组合）：
   - `feat` —— 6 维视觉特征残差
   - `yao` —— 六爻残差
   - `bagua` —— 八卦隶属度残差（仅全图脚本）
   - `chengcheng` —— **乘承比应关系评分**残差
   - `fusion` —— 拼接取 max
4. **打分**：标准化残差取 max，图像级 AUROC。

## 四、两个脚本

| 脚本 | 粒度 | 说明 |
|---|---|---|
| `ylyw_anomaly.py` | **全图** | 每张图 1 组特征。结果是图像级统计量，对缺陷定位**不敏感** |
| `ylyw_anomaly_patch.py` | **逐 patch** | 滑窗（默认 64/32），每 patch 走同一 YLYW 管线，网格取 max |

## 五、结果

### 5.1 全图描述子（ylyw_anomaly.py）

| 类 | feat | yao | bagua | chengcheng | fusion |
|---|---|---|---|---|---|
| bottle | 0.6635 | 0.6635 | 0.4897 | 0.3944 | 0.6536 |

> 结论：全图 6 维描述子是**图像级统计量**，缺陷只占局部几像素 → AUROC 仅 ~0.66，
> 接近随机。**说明原 YLYW 视觉管线需要"空间化"才能做异常定位。**

### 5.2 逐 patch（ylyw_anomaly_patch.py）

| 类 | feat | yao | chengcheng | fusion |
|---|---|---|---|---|
| bottle | **0.9857** | 0.9857 | 0.9603 | 0.9825 |

> 结论：把同一套 YLYW 管线**逐 patch** 应用后，bottle AUROC 从 0.66 → **0.986**，
> 甚至超过易理抽取器在 bottle 上的 0.960。**关键差异不在"用了哪套易理"，而在
> "是否空间化/分层定位"。**

（全 15 类结果见 `results/ylyw_anomaly_patch.json`。）

## 六、与主项目（quantum_ylyw）的对比口径

| 维度 | 本文主项目（易理抽取器） | 本项目（原 YLYW 管线） |
|---|---|---|
| 特征抽取 | 新设计 L1–L4 卷积（固定核） | 原 YLYW L0–L3（6维描述子+爻位关系） |
| 爻位关系 | ❌ 未用 | ✅ **乘承比应** 直接参与 |
| 空间化 | ✅ 特征图逐位置 | ✅ patch 滑窗 |
| 用途 | 异常**检测**（主贡献） | 验证原 YLYW 的**可迁移性** |

## 七、复现

```bash
P=/home/lijinhan/.openclaw/workspace-quantum/.venv-quantum/bin/python
cd ylyw_anomaly

# 单类
$P ylyw_anomaly_patch.py --cat bottle
# 全 15 类
$P ylyw_anomaly_patch.py --all --data /home/lijinhan/MXL/mvtec_full
```

## 八、待办

- [ ] 全 15 类跑完，出汇总表
- [ ] 尝试把 patch 粒度细化 / 多尺度，并与易理抽取器做同口径对比图
- [ ] 评估"乘承比应"是否在 patch 层面带来增量（对比 feat vs chengcheng）
