# 六爻传感器异常检测 —— 研究生交接任务书

> 目标：补强实验，使论文达到《模式识别与人工智能》（EI/中文核心）投稿标准
> 交接人：马兴录 ｜ 交接日期：2026-09-14
> 项目仓库：https://github.com/qdmxl/ylyw 的 `six_yao_anomaly/` 目录

---

## 〇、先做：环境与数据重建（用 git）

### 1. 克隆仓库

```bash
git clone git@github.com:qdmxl/ylyw.git
cd ylyw/six_yao_anomaly
```

> 需要 SSH 访问权限。若没有，可改用 HTTPS：
> `git clone https://github.com/qdmxl/ylyw.git`
> 并请马老师添加 collaborator 权限。

### 2. 建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install numpy scipy pillow scikit-learn matplotlib python-docx
```

> 论文实验用 CPU 即可（原实验在 3.4GB 内存机器上完成）。
> **重要**：机器内存若 ≤4GB，务必按现有脚本的"Welford 增量 + float32 + 逐类清零"
> 策略，否则会 OOM。

### 3. 下载 MVTec AD 数据集

数据集不进 git（体积大）。用仓库脚本下载：

```bash
python download_mvtec.py data/mvtec_full bottle,cable,capsule,...   # 15 类
```

或从官方下载 <https://www.mvtec.com/company/research/datasets/mvtec-ad>
后放到 `data/mvtec_full/<类别>/{train,test}/...`。

> 目录结构必须是标准 MVTec AD 布局，脚本默认路径 `data/mvtec_full`。

### 4. 复现主结果（自检环境是否正确）

```bash
# 层扫描（15 类，逐层）
python exp31_full15.py --layer 3 --cats all --tag L3
# 应与 results/exp31_full15_L3.json 一致，平均 AUROC ≈ 0.862
```

---

## 一、核心补强任务（必做）：多数据集泛化验证

**问题**：当前论文只在 MVTec AD 一个数据集上验证。审稿人几乎必然质疑
"方法是否只在 MVTec AD 上有效"。必须补至少 **1–2 个**其他数据集。

### 推荐数据集（按优先级）

| 数据集 | 规模 | 获取 | 说明 |
|---|---|---|---|
| **VisA** | 12 类，10821 图 | [公开](https://github.com/amazon-science/spot-diff) | 与 MVTec 互补，最常被同时使用 |
| **MPDD** | 6 类，金属零件 | [公开](https://github.com/stepanje/MPDD) | 工业金属件，贴近真实 |
| **BTAD** | 3 类 | [公开](http://avires.dimi.uniud.it/papers/btad/btad.zip) | 小，易跑 |
| **MVTec LOCO / 3D** | — | 官方 | 若时间充裕可选 |

### 具体做法

1. **适配数据加载**：现有 `exp31_full15.py` 里 `load_split(cat, split)` 是针对
   MVTec 目录结构的。为每个新数据集写一个同接口的 loader（统一返回
   `(图片路径, 标签)` 列表，标签 0=正常 1=异常）。
2. **跑同样的实验矩阵**：手工 / L1 / L2 / L3 / L1+L3 融合，5 个变体。
3. **产出**：每个数据集一张逐类 AUROC 表 + 平均。
4. **论文改动**：主结果表从单数据集扩成多数据集（可放一张大表或用表格组）。

**预期结论**：如果方法在 VisA 上仍能保持"L3 最佳、手工可用"的规律，
泛化性论证就成立了。

---

## 二、必修补强（审稿必问）

### 2.1 random 消融补齐到 15 类

**现状**：random 初始化 ResNet 只测了 4 类（bottle/tile/metal_nut/toothbrush，
均值 0.772）。审稿人必问为何不是 15 类。

**技术坑（重要）**：random ResNet 经 ReLU 后大量通道为 0 → 模板 SD 近零 →
残差 `|F-T|/SD` 数值爆炸 → 极慢/NaN。仓库里 `exp32c_random_fast.py` 已加了
SD 下限保护（`SD_FLOOR=0.1`）和 `np.clip(R,0,50)`，但 carpet 等大图类仍慢。

**任务**：
- 优化 `exp32c_random_fast.py`（或另写高效版），跑完全 15 类；
- 若确实跑不动，明确记录原因（数值病态），作为"方法局限"诚实报告；
- 更新论文中所有 random 相关数字（英文 4 处、中文 4 处）。

### 2.2 SOTA 数字核对

论文里 PaDiM=0.975、PatchCore=0.992 及**逐类**数值是文献报告值。
任务：逐项核对 PaDiM / PatchCore **原论文**的 MVTec AD 逐类 AUROC，
确认与本文表格一致，并补全精确引用（卷期页码已在参考文献里）。

### 2.3 运行时间/复杂度定量

已有"存储省 52×、推理快 55×"（`exp29`）。任务：
- 补一张完整的复杂度对比表（参数量、存储、推理时延，含 PaDiM/PatchCore）；
- 说明硬件环境。

---

## 三、理论补强（提升严谨性，降低"玄学"质疑）

「爻变」目前偏哲学表述。**任务**：把它形式化为可检验的统计判据。

建议方向：
1. 明确"爻间关联结构"的数学定义（如 6 维爻读数的协方差矩阵 / 相关矩阵）；
2. 把"偏离正常流形"写成可计算的统计量（如马氏距离、相关矩阵的谱扰动、
   或流形上的测地距离）；
3. 给出为什么"相关性是有信息的、正交化会损失信号"的理论/实验论证
   （论文 §爻变 vs 正交 已有实验，强化其理论解释）。

> 目标：让审稿人看到这是一个**有明确数学定义的异常判据**，易经是"灵感来源"
> 而非"方法本身"。

---

## 四、写作与投稿材料整理

- [ ] 4.1 主结果表扩为多数据集
- [ ] 4.2 补中文摘要/正文中所有因新实验结果需要更新的数字
- [ ] 4.3 图表题注已双语化（`paper/prai_submission/main_prai.tex`），新图照此格式
- [ ] 4.4 检查全文数字一致性（手工 0.709 / L3 0.862 / 阶梯 0.772-0.799-0.854-0.932）
- [ ] 4.5 基金项目号填入投稿声明
- [ ] 4.6 生成投稿 PDF 或 Word（见下）

---

## 五、投稿格式（我来处理或与研究生确认）

- 目标期刊：《模式识别与人工智能》
- 投稿版目录：`paper/prai_submission/`
- 已有：`main_prai.tex`（含中英文摘要、关键词、双语题注、规范参考文献）、
  `工作背景说明.md`、`投稿声明.md`
- 待办：按该刊模板排版 → 生成 PDF/Word（该刊以 Word 模板为主流）

---

## 六、里程碑与建议顺序

| 阶段 | 任务 | 预估 |
|---|---|---|
| 第 1 周 | 环境重建 + 复现主结果 + 下载 VisA | 1 周 |
| 第 2–3 周 | VisA 数据适配 + 跑完整实验矩阵 | 2 周 |
| 第 3 周 | random 15 类 + SOTA 核对 + 复杂度表 | 1 周 |
| 第 4 周 | 理论形式化 + 论文改稿 | 1 周 |
| 第 5 周 | 格式排版 + 内部审阅 + 投稿 | 1 周 |

---

## 七、注意事项

1. **科研数据保密**：数据与中间结果不要外泄；
2. **版本管理**：所有代码改动走 git，commit message 写清楚；
3. **诚实报告**：负面结果（如 hazelnut 0.529、random 数值病态）如实保留，
   不要为了好看而隐藏——这是本文的方法论特色；
4. **可复现**：每个实验脚本要能一键重跑，随机种子固定。
